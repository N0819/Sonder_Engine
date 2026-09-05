"""The export-based debug harness (`tools/export_bench.py`): a synthetic
source database is exported chat by chat over a read-only connection,
imported into a fresh scratch database, and the provider and settings rows a
beat needs are copied table-to-table. No model, no network. The source must
come out untouched, the key must arrive without ever being read, and the
report writer's leak check must see it in text."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time

import pytest

from tools import export_bench as eb

FAKE_KEY = "sk-test-0123456789abcdef-never-printed"
RESEARCH_KEY = "rk-test-fedcba9876543210-never-printed"


def _digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture
def source_db(tmp_path):
    """A tiny engine database with one played chat, one provider and the
    settings a beat reads, built through `core.db` and then released."""
    from core import db
    path = str(tmp_path / "source.db")
    previous = db.DB
    db.configure(path)
    db.init()
    try:
        with db.transaction():
            cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                        ("Source", "A tannery town.", time.time()))
            db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                  (cid, 0, "", time.time()))
            db.qi("INSERT INTO providers(id,name,kind,base_url,api_key,enabled) "
                  "VALUES(?,?,?,?,?,?)", (3, "router", "openrouter", "https://x/v1",
                                          FAKE_KEY, 1))
        db.wset(cid, "scene", {"location": "Town", "rooms": {
            "quay": {"name": "Quay", "extent": {"w": 4, "d": 9}, "shape": "rectangle",
                     "adjacent": [{"to": "shed", "barrier": "open_door", "dir": "e",
                                   "offset": 0.25}]},
            "shed": {"name": "Shed", "adjacent": [{"to": "quay", "barrier": "open_door",
                                                   "dir": "w"}]},
        }, "positions": {"Player": "quay"}, "entities": {
            "lamp": {"name": "a lamp", "kind": "object", "light_source": "lit",
                     "light_height": "full", "state": {"lit": True}}}, "attire": {}})
        db.set_setting("agent_models", json.dumps({"default": {"provider": 3, "model": "m"}}))
        db.set_setting("nsfw_enabled", "1")
        db.set_setting("host_pw_hash", "hash-that-must-not-travel")
        db.set_setting("host_username", "owner")
        db.set_setting("research_key", RESEARCH_KEY)
        db.set_setting("director_fanout_mode", "serial")
        db.set_setting("reasoning_effort", json.dumps({"director": "high"}))
        db.set_setting("llm_capture_enabled", "0")
    finally:
        db.close_connection()
        db.configure(previous)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    return path, cid


def test_prepare_exports_read_only_imports_and_copies_the_rows(source_db, tmp_path):
    from core import db
    source, cid = source_db
    before = _digest(source)
    out = str(tmp_path / "scratch" / "bench.db")
    previous = db.DB
    try:
        recipe = eb.prepare(source, [cid], out, models=["default=3:other/model"])
        assert recipe["chats"] == {cid: recipe["chats"][cid]}
        new_cid = recipe["chats"][cid]
        assert recipe["copied"]["tables"] == ["providers"]
        # Every settings row travels, by name, except the host account.
        assert "agent_models" in recipe["copied"]["settings"]
        assert "reasoning_effort" in recipe["copied"]["settings"]
        assert "research_key" in recipe["copied"]["settings"]
        assert not set(recipe["copied"]["settings"]) & set(eb.SETTINGS_EXCLUDED)
        assert recipe["models"]["default"] == {"provider": 3, "model": "other/model"}

        # The scratch database holds the chat, its scene and the turn.
        scene = db.wget(new_cid, "scene")
        assert scene["rooms"]["quay"]["extent"] == {"w": 4, "d": 9}
        assert scene["entities"]["lamp"]["light_height"] == "full"
        assert db.q("SELECT count(*) n FROM turns WHERE chat_id=?", (new_cid,), one=True)["n"] == 1

        # The provider row travelled whole, key included, under its own id
        # -- checked with SQL that answers yes/no, never with the value.
        row = db.q("SELECT id, name, api_key=? AS same FROM providers WHERE id=3",
                   (FAKE_KEY,), one=True)
        assert row["name"] == "router" and row["same"] == 1

        # Settings: everything the owner's engine has for model wiring came
        # (the owner's ruling, 2026-09-05), the host account did not, and the
        # forced values won over the source's -- capture ON among them.
        assert db.get_setting("director_fanout_mode") == "serial"
        assert json.loads(db.get_setting("reasoning_effort")) == {"director": "high"}
        assert db.q("SELECT value=? AS same FROM settings WHERE key='research_key'",
                    (RESEARCH_KEY,), one=True)["same"] == 1
        assert db.get_setting("host_pw_hash") is None
        assert db.get_setting("host_username") is None
        assert db.get_setting("nsfw_enabled") == "0"
        assert db.get_setting("backdrops_enabled") == "0"
        assert db.get_setting("llm_capture_enabled") == "1"
        assert db.get_setting("llm_capture_bodies") == "full"
        assert json.loads(db.get_setting("agent_models"))["default"]["model"] == "other/model"

        # The leak check sees either key in text and nothing else, and
        # `scan` applies it to what a run wrote.
        assert eb.leaks("prefix %s suffix" % FAKE_KEY, out) is True
        assert eb.leaks("prefix %s suffix" % RESEARCH_KEY, out) is True
        assert eb.leaks(json.dumps(recipe), out) is False
        assert eb.leaks("a report with no secret in it", out) is False
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "clean.json").write_text(json.dumps(recipe))
        (run_dir / "dirty.log").write_text("Authorization: Bearer %s" % FAKE_KEY)
        assert eb.scan([str(run_dir)], out) == [str(run_dir / "dirty.log")]

        # The trace reader runs on a turn with no captured calls (the
        # synthetic turn ran no model): steps only, and it says so.
        tid = eb.turn_id_of(new_cid, 0)
        trace = eb.read_trace(tid, out_dir=str(run_dir))
        assert trace["captured"] is False and trace["calls"] == []
        assert os.path.exists(trace["file"])
    finally:
        db.close_connection()
        db.configure(previous)

    # The source is byte-identical. A read-only open of a WAL database
    # still creates an EMPTY -wal and a -shm index beside it when none exist
    # (SQLite's own behaviour, measured); what matters is that nothing was
    # written into either.
    assert _digest(source) == before
    if os.path.exists(source + "-wal"):
        assert os.path.getsize(source + "-wal") == 0


def test_read_only_session_refuses_a_write(source_db):
    from core import db
    source, _cid = source_db
    previous = db.DB
    with eb.read_only_session(source) as ro:
        assert db.q("SELECT count(*) n FROM chats", one=True)["n"] == 1
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("INSERT INTO settings(key,value) VALUES('x','y')")
        with pytest.raises(sqlite3.OperationalError):
            db.set_setting("x", "y")
    assert db.DB == previous
    assert db._local.conn is None


def test_prepare_refuses_a_scratch_path_that_is_not_scratch(source_db):
    source, cid = source_db
    with pytest.raises(SystemExit):
        eb.prepare(source, [cid], "/srv/stories/engine.db")


def test_the_forced_policy_and_the_excluded_rows():
    assert not set(eb.SETTINGS_EXCLUDED) & set(eb.SETTINGS_FORCED)
    for key in ("nsfw_enabled", "backdrops_enabled", "ambience_enabled"):
        assert eb.SETTINGS_FORCED[key] == "0"
    assert eb.SETTINGS_FORCED["llm_capture_enabled"] == "1"
    assert eb.SETTINGS_FORCED["llm_capture_bodies"] == "full"
    for key in ("host_pw_hash", "host_pw_salt", "host_secret", "host_secret_hash"):
        assert key in eb.SETTINGS_EXCLUDED


def test_the_f1_rule_reads_the_reasoning_only_failure_and_nothing_else():
    assert eb._is_f1("ReasoningBudgetExhausted: openrouter: m returned reasoning but no answer")
    assert eb._is_f1("LLMError: m returned reasoning but no answer (6159 chars of trace)")
    assert not eb._is_f1("LLMError: all providers failed")
    assert not eb._is_f1(None)


def test_scene_before_after_reads_the_pre_turn_checkpoints(source_db, tmp_path):
    from core import db
    source, cid = source_db
    previous = db.DB
    db.configure(source)
    try:
        for idx, light in ((0, "dark"), (1, "lit")):
            db.qi("INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
                  (cid, idx, json.dumps({"world": {"scene": {"rooms": {
                      "quay": {"name": "Quay", "light": light}}}}}), time.time()))
        before, after = eb.scene_before_after(cid, 0)
        assert before["rooms"]["quay"]["light"] == "dark"
        assert after["rooms"]["quay"]["light"] == "lit"
        before, after = eb.scene_before_after(cid, 1)
        assert before["rooms"]["quay"]["light"] == "lit"
        assert after["rooms"]["quay"]["extent"] == {"w": 4, "d": 9}   # the live scene
        digest = eb.scene_digest(after)
        assert digest["rooms"]["quay"]["adjacent"][0]["offset"] == 0.25
        assert digest["entities"]["lamp"]["light_height"] == "full"
    finally:
        db.close_connection()
        db.configure(previous)
