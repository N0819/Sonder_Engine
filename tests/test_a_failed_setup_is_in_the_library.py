"""A quick start that failed is shown as a setup, with a way out of it.

Owner ruling, 2026-09-08: "maybe it should have a temporary story library
entry with a discard or retry button instead and have a little error
triangle in it", and "an export debugging log button".

Before it, a failed start deleted its chat, so the author was left with
nothing to act on -- no record of what happened, and no way to retry that did
not mean redoing the modal and paying for the model calls again. The row is
kept and MARKED instead. The marker is what makes it not a story: it has no
turn, the library refuses to open it, and the three things worth doing to it
are all on the row.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.db import QUICK_START_FAILURE_KEY, q, qi, wget, wset


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "static/js/app.js").read_text(encoding="utf-8")


def _failed_chat(temp_db, *, error="the location generator returned junk"):
    import time

    cid = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
             ("The Doctor — Hinami", "", time.time()))
    wset(cid, QUICK_START_FAILURE_KEY, {
        "version": 1, "when": time.time(), "stage": "planning",
        "error": error, "error_type": "ValueError",
        "traceback": "Traceback (most recent call last): ...",
        "plan_kept": True,
        "retry": {"char_id": 58, "persona_id": 10, "greeting_index": 0,
                  "lorebook_id": None, "already_known": True,
                  "language": "en",
                  "lived_location": {"enabled": True, "brief": "the port"}},
        "character_name": "The Doctor", "persona_name": "Hinami",
    })
    return cid


def _client():
    from fastapi.testclient import TestClient

    from web import app as app_module
    from web import guest_access as guest

    guest.reset_host_account()
    client = TestClient(app_module.app)
    client.__enter__()
    assert client.post("/api/auth/setup",
                       json={"username": "host", "password": "pw12345"}).status_code == 200
    return client


def test_the_library_is_told_which_rows_are_failed_setups(temp_db):
    cid = _failed_chat(temp_db)
    client = _client()
    try:
        boot = client.get("/api/bootstrap").json()
    finally:
        client.__exit__(None, None, None)

    entry = boot["failed_setups"][str(cid)]
    assert entry["error_type"] == "ValueError"
    assert entry["character_name"] == "The Doctor"
    assert entry["plan_kept"] is True
    # The chat is still in the list; what changes is how it is READ.
    assert any(c["id"] == cid for c in boot["chats"])


def test_an_ordinary_story_is_not_listed_as_a_failed_setup(temp_db):
    import time
    qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
       ("An ordinary story", "", time.time()))
    client = _client()
    try:
        assert client.get("/api/bootstrap").json()["failed_setups"] == {}
    finally:
        client.__exit__(None, None, None)


def test_the_setup_log_carries_what_the_attempt_recorded(temp_db):
    cid = _failed_chat(temp_db, error="Expecting value: line 1 column 1")
    client = _client()
    try:
        doc = client.get(f"/api/chats/{cid}/setup_log").json()
    finally:
        client.__exit__(None, None, None)

    assert doc["kind"] == "quick_start_failure" and doc["chat_id"] == cid
    assert "Expecting value" in doc["failure"]["error"]
    assert doc["failure"]["traceback"]
    # What was asked for travels with it, so the report is reproducible.
    assert doc["failure"]["retry"]["lived_location"]["brief"] == "the port"
    assert "exchanges" in doc and "turns" in doc


def test_a_story_that_did_not_fail_has_no_setup_log(temp_db):
    import time
    cid = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
             ("Fine", "", time.time()))
    client = _client()
    try:
        assert client.get(f"/api/chats/{cid}/setup_log").status_code == 404
        assert client.post(f"/api/chats/{cid}/retry_start").status_code == 404
    finally:
        client.__exit__(None, None, None)


def test_a_retry_resumes_the_same_story_rather_than_starting_another(
        temp_db, monkeypatch):
    """RESUMED IN PLACE (owner, 2026-09-08): "have it overwrite the existing
    temp entry for this particular story with each attempt instead of opening
    new entries", and "resume off the failed step, to actually save what
    succeeded". The failed attempt's chat IS the retry's chat, so what already
    landed in it is kept and the library never grows a second row for one
    story."""
    cid = _failed_chat(temp_db)
    asked = {}

    def fake_start(char_id, persona_id, greeting_index=0, **kwargs):
        asked.update({"char_id": char_id, "persona_id": persona_id,
                      "greeting_index": greeting_index, **kwargs})
        wset(kwargs["resume_chat_id"], QUICK_START_FAILURE_KEY, {})
        return kwargs["resume_chat_id"], 1

    from story import greetings
    monkeypatch.setattr(greetings, "start_story", fake_start)

    client = _client()
    try:
        out = client.post(f"/api/chats/{cid}/retry_start")
        assert out.status_code == 200, out.text
    finally:
        client.__exit__(None, None, None)

    assert asked["char_id"] == 58 and asked["persona_id"] == 10
    assert asked["lived_location"] == {"enabled": True, "brief": "the port"}
    assert asked["resume_chat_id"] == cid
    # One story, still there, and no longer a failed setup.
    assert out.json()["chat_id"] == cid
    assert q("SELECT id FROM chats WHERE id=?", (cid,), one=True) is not None
    assert len(q("SELECT id FROM chats")) == 1
    assert not wget(cid, QUICK_START_FAILURE_KEY, None)


def test_a_retry_that_fails_leaves_the_setup_where_it_was(temp_db, monkeypatch):
    """The author must never be left with nothing again: a retry that fails is
    one failed setup, not none."""
    cid = _failed_chat(temp_db)

    def fail(*a, **k):
        raise ValueError("the location generator returned junk again")

    from story import greetings
    monkeypatch.setattr(greetings, "start_story", fail)

    client = _client()
    try:
        out = client.post(f"/api/chats/{cid}/retry_start")
        assert out.status_code == 422, out.text
    finally:
        client.__exit__(None, None, None)

    assert q("SELECT id FROM chats WHERE id=?", (cid,), one=True) is not None
    assert wget(cid, QUICK_START_FAILURE_KEY, None)


def test_the_row_is_rendered_as_a_setup_rather_than_opened():
    """The browser half, pinned at the source the way this repo pins its
    frontend rules: a failed setup takes its own row, and that row does not
    open a chat."""
    assert "failed_setups" in APP_JS
    assert "function failedSetupRow(" in APP_JS
    match = re.search(r"function failedSetupRow\(.*?\n}\n", APP_JS, re.S)
    assert match, "failedSetupRow has no body"
    body = match.group(0)
    # It may open the story a RETRY produces; it may never open itself,
    # because there is no story behind it.
    assert "openChat(chat.id)" not in body, "a failed setup has none to open"
    for needed in ("retry_start", "setup_log", "DELETE", "⚠"):
        assert needed in body, needed


def test_a_failure_anywhere_in_the_start_leaves_a_setup(temp_db, monkeypatch):
    """The marker used to be written only around the location generation, so
    a start that got PAST it and died later -- the journey history, the minds
    routing, turn zero -- left a chat with no turn, no mark and no way back:
    "no retry entry in chat library" (owner, 2026-09-08). The guard is around
    everything after the chat exists, because the author is in the same
    position whichever stage raised.
    """
    from story import greetings

    cid_char = qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Doc", json.dumps({
            "identity": {"name": "Doc"},
            "opening": {"greetings": [{"prose": "You arrive at the gate."}]},
        }), "{}", 0.0, "char_doc"))
    pid = qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
             ("Wren", json.dumps({"name": "Wren"}), "{}"))

    monkeypatch.setattr(greetings, "extract_greeting",
                        lambda sheet, prose: {"knowledge_seeds": [],
                                              "time": "now"})
    # A failure at the LAST stage, well past the location step.
    monkeypatch.setattr(greetings, "_run_pipeline",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("LLM returned invalid JSON")))

    with pytest.raises(RuntimeError):
        greetings.start_story(cid_char, pid)

    rows = q("SELECT id FROM chats")
    assert len(rows) == 1
    record = wget(rows[0]["id"], QUICK_START_FAILURE_KEY, None)
    assert record and record["error_type"] == "RuntimeError"
    assert record["retry"]["char_id"] == cid_char


def test_recording_the_failure_never_replaces_it(temp_db, monkeypatch):
    """The marker is written against the chat row, and a sibling path used to
    delete that row first -- so the FOREIGN KEY error from writing the mark
    travelled in place of the JSON error that actually happened, and the
    author got a 500 about the database and no entry at all (2026-09-08).
    Recording a failure is best-effort; the failure itself is not.
    """
    from core import db as core_db
    from story import greetings

    def boom(*a, **k):
        raise RuntimeError("the marker could not be written")

    monkeypatch.setattr(core_db, "wset", boom)
    # Must not raise, and must not replace the caller's exception.
    greetings._mark_failed_setup(
        999999, ValueError("the real failure"), char_id=1, persona_id=2,
        greeting_index=0, lorebook_id=None, already_known=True,
        language="en", lived_location=None)


def test_no_stage_of_a_start_deletes_its_own_chat():
    """The class, so the next stage added does not reintroduce it: three
    stages each deleted the chat on failure, and removing the first two left
    the third to hand the guard a row that was gone."""
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1]
              / "story/greetings.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    start = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "start_story")
    called = {getattr(n.func, "id", None) or getattr(n.func, "attr", None)
              for n in ast.walk(start) if isinstance(n, ast.Call)}
    assert "delete_chat_data" not in called, (
        "a failed start is kept and marked; the library discards it")


def test_a_failed_start_refreshes_the_library_that_shows_it():
    """The record is only half of a recovery path; being SEEN is the other.

    The story list renders from `S.boot`, and only the success path refreshed
    it -- so a failed start wrote its entry, kept its plan, armed its retry,
    and left the author looking at an unchanged library: "still no temp story
    library entry and everything is just gone and deleted with no recover
    path" (owner, 2026-09-08), when a page reload would have shown it. Both
    surfaces that can leave a setup behind re-read the library on failure.
    """
    editors = (ROOT / "static/js/editors.js").read_text(encoding="utf-8")

    start = editors.index("/api/characters/${character.id}/start")
    block = editors[start:start + 1400]
    assert "onError" in block, "the quick start does not refresh on failure"
    # The comment above it is long on purpose; the call is what matters.
    assert "boot()" in block.split("onError", 1)[1][:1200]

    # And the retry, which leaves the setup where it was when it fails.
    retry = APP_JS.index("/api/chats/${chat.id}/retry_start")
    retry_block = APP_JS[retry:retry + 600]
    assert "onError" in retry_block
    assert "boot()" in retry_block.split("onError", 1)[1][:200]


def test_the_export_carries_everything_sent_and_received(temp_db, monkeypatch):
    """"logging capabilities similar to others where the export contains
    everything sent and received" (owner, 2026-09-08).

    A quick start runs OUTSIDE any pipeline step, and the exchange funnel a
    step arms is what every rung of the quality ladder reports through -- so
    the attempt's traffic was invisible and the export could say what broke
    but not what was asked. The start now arms that same funnel for itself.
    """
    from core.pipeline_context import current_exchange_sink
    from story import greetings

    # The recorder is the engine's own sink, so anything reporting through
    # `note_provider_exchange` while a start runs is captured.
    with greetings._recording_exchanges() as collected:
        from llm.llm_quality import note_provider_exchange
        note_provider_exchange(role="utility", system="SYS", payload={"a": 1},
                               response='{"ok": true}', ok=True, started=0.0)
    assert collected and collected[0]["response"] == '{"ok": true}'
    assert current_exchange_sink.get() is None, "the sink is not left armed"

    # ...and what it keeps is bounded, with the trim said out loud.
    big = "x" * (greetings.SETUP_EXCHANGE_CHARS + 500)
    trimmed = greetings._trimmed_exchanges([{"system": big, "response": big}])
    assert len(trimmed[0]["system"]) < len(big)
    assert "trimmed" in trimmed[0]["system"]


def test_the_setup_log_hands_over_the_traffic(temp_db):
    cid = _failed_chat(temp_db)
    record = wget(cid, QUICK_START_FAILURE_KEY, None)
    record["exchanges"] = [{"role": "utility", "system": "SYS",
                            "payload": {"ask": "a town"},
                            "response": "{}", "ok": False}]
    wset(cid, QUICK_START_FAILURE_KEY, record)

    client = _client()
    try:
        doc = client.get(f"/api/chats/{cid}/setup_log").json()
    finally:
        client.__exit__(None, None, None)

    assert doc["exchanges"][0]["system"] == "SYS"
    assert doc["exchanges"][0]["payload"] == {"ask": "a town"}
    assert "turns" in doc


def test_a_resumed_start_keeps_the_town_it_already_planted(temp_db, monkeypatch):
    """"resume off the failed step, to actually save what succeeded" (owner,
    2026-09-08). The location generation is three model calls and most of the
    minute a start takes; when the chat already holds a planted registry, a
    resume does not pay for it again. The check asks the CHAT, not a recorded
    stage name -- the registry rows are the fact, a marker is a claim about it.
    """
    import time

    from story import greetings

    cid_char = qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Doc", json.dumps({
            "identity": {"name": "Doc"},
            "opening": {"greetings": [{"prose": "You arrive at the gate."}]},
        }), "{}", 0.0, "char_doc2"))
    pid = qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
             ("Wren", json.dumps({"name": "Wren"}), "{}"))
    cid = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
             ("half-built", "", time.time()))
    # A planted registry: the fact a resume reads.
    qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
       "VALUES(?,?,?,?,?)", (cid, "gate", "The Gate", "[]", "{}"))

    monkeypatch.setattr(greetings, "extract_greeting",
                        lambda sheet, prose: {"knowledge_seeds": [],
                                              "time": "now"})
    called = []
    from world import charter_runtime
    monkeypatch.setattr(charter_runtime, "generate_lived_location",
                        lambda *a, **k: called.append(1))
    # Stop before turn 0; the location decision has already been taken by then.
    monkeypatch.setattr(greetings, "_seed_minds",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("stop here")))

    with pytest.raises(RuntimeError):
        greetings.start_story(cid_char, pid, resume_chat_id=cid,
                              lived_location={"enabled": True,
                                              "brief": "the port"})

    assert called == [], "a resume regenerated a location the chat already had"
    assert len(q("SELECT id FROM chats")) == 1, "no second story was minted"
