"""The obligations ledger is gone, and a stray write to its channel is still said.

The owner, 2026-11-01: "obligations caused hyperfixation." The `obligations`
channel left the prose Director on 2026-10-02 (`director_prose.
RETIRED_CHANNELS`): what a mind owes is that mind's own to keep -- its
notebook, `commit_background.owed_to` and `still_waiting_for`, a presence's
`pending_reply` and `pending_act` -- never a Director ledger pressed as
must-discharge. The 2026-11-01 review then found the encoder's stray writes
still dispatched and stripped them (lane L7b, `agents_director_prose_movement_
rooms` F16), after which nothing opened a `pending_obligations` entry: the
ledger was read-only history. So it is deleted -- the commit domain, its world
key, the channel's owner entry, its schema fields and its encoder chunk -- and
these pin that:

* no engine module binds a deleted name, or names the world key;
* no owner table, schema or language pack carries the channel;
* the commit runs no `obligations` domain, and still runs `world_pressure`,
  the ledger that shared the module and stays;
* a stray `obligations` write is still stripped and warned at both stages,
  and an old story's stored ledger reaches no model;
* an archive carrying `pending_obligations` still imports, and a checkpoint
  carrying it still restores. Its rows are the story's record and ride
  verbatim; no migration deletes them (`docs/guides/DATABASE.md`, "A retired
  setting's row outlives its feature": deleting a host's rows is the host's
  call).
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
import time
from pathlib import Path

import pytest

import agents.director as director
from tests.director_fakes import _fake_agent, _make_ctx, encoder_event

ROOT = Path(__file__).resolve().parents[1]

#: Every name the ledger's half of `persist/commit_ledgers.py` bound (and the
#: facade re-exported), deleted with it.
DELETED_NAMES = frozenset({
    "commit_obligations", "causal_obligation_ops", "pending_obligation_view",
    "_find_obligation", "_beats_open", "_demand_unheard_by", "_zip_rows",
    "OBLIGATION_OVERDUE_AGE", "OBLIGATION_CAP",
})

#: The ledger's world key.
LEDGER_KEY = "pending_obligations"

_OLD_LEDGER = [{"id": "obl:3:0", "who": "Mara", "what": "mend the lamp",
                "kind": "promise", "opened_turn": 3}]


def _engine_paths():
    sys.path.insert(0, str(ROOT / "tools"))
    from project_check import engine_python_paths
    return engine_python_paths()


def _bound_names(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for leaf in ast.walk(target):
                    if isinstance(leaf, ast.Name):
                        yield leaf.id, node.lineno
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                yield (alias.asname or alias.name).split(".")[0], node.lineno


def test_no_engine_module_binds_a_deleted_name_or_names_the_key():
    bound, keyed = [], []
    for path in _engine_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT).as_posix()
        bound += [f"{rel}:{line} {name}" for name, line in _bound_names(tree)
                  if name in DELETED_NAMES]
        # The key as a VALUE (a read, a write, a list of keys) -- prose in a
        # docstring that recalls the retired ledger is history, not a reader.
        keyed += [f"{rel}:{node.lineno}" for node in ast.walk(tree)
                  if isinstance(node, ast.Constant) and node.value == LEDGER_KEY]
    assert not bound, bound
    assert not keyed, keyed

    # The facade re-exports every name its siblings bind, so this is the
    # module's own surface too (the scan above read its source).
    from persist import commit
    assert not [n for n in DELETED_NAMES if hasattr(commit, n)]
    # The ledger the module kept.
    assert callable(commit.commit_world_pressure)
    assert callable(commit.world_pressure_view)


def test_no_owner_schema_or_pack_carries_the_channel():
    from agents import director_prose
    from core.db import FRAME_SCOPED_WORLD_KEYS
    from language_runtime import raw_card
    from llm import schemas
    from world.causality import LIST_CHANNELS

    owned = {c for spec in director.SPECIALISTS.values() for c in spec["channels"]}
    assert "obligations" not in owned
    assert "obligations" not in {c for channels in schemas.SPECIALIST_CHANNELS.values()
                                 for c in channels}
    assert "obligations" not in director._CATEGORY_CHANNELS
    assert "obligations" not in director.SPEECH_WRITTEN_CHANNELS
    assert "obligations" not in LIST_CHANNELS
    for model in (schemas.DirectorInterpret, schemas.DirectorResolve,
                  schemas.DirectorSocialSpecialist):
        assert "obligations" not in schemas._fields(model), model.__name__
    assert LEDGER_KEY not in FRAME_SCOPED_WORLD_KEYS
    for language in ("en", "ja"):
        card = raw_card(language)
        assert "obligations" not in card["encoder"], language
        assert "obligations" not in card["specialists"]["social"]["order"], language
        assert not (ROOT / "language_packs" / language / "cards" / "system_prompts"
                    / "encoder" / "obligations.txt").exists(), language
    # The decision model is told no debts: nothing passes it any.
    for function in (director_prose.select_channels, director_prose._jev_state):
        assert "owed" not in inspect.signature(function).parameters, function.__name__
    # ...and the name stays retired, so a write the encoder makes anyway is
    # stripped and said (below) instead of meeting no owner in silence.
    assert "obligations" in director_prose.RETIRED_CHANNELS


def test_the_commit_runs_no_obligations_domain(temp_db, monkeypatch):
    """Every domain the transaction registers, in order, with none of them
    run: the last one raises so the transaction rolls back before the tail."""
    from persist import commit

    names = []

    class _Stop(Exception):
        pass

    def record(ctx, results, name, operation):
        names.append(name)
        if name == "pending":
            raise _Stop(name)

    monkeypatch.setattr(commit, "_commit_domain", record)
    monkeypatch.setattr(commit, "_prepare_turn_commit", lambda ctx: {
        "scene": {"scene": {}, "clock": None}, "mapping": {}, "memories": {},
        "claims": {}})
    ctx = _make_ctx(temp_db)
    with pytest.raises(RuntimeError, match="rolled back"):
        commit.commit_all(ctx, nonce=0)
    assert names[-1] == "pending", names
    assert "obligations" not in names, names
    assert "world_pressure" in names, names


@pytest.mark.parametrize("stage", ["interpret", "resolve"])
def test_a_stray_obligations_write_is_still_dropped_out_loud(
        temp_db, monkeypatch, prose_director, stage):
    """Ported from `tests/test_causal_obligations.py` (retired with the
    ledger): the encoder writes the retired channel anyway, and the stage
    names it in `retired_channels`, warns, and keeps it nowhere -- no output
    key, no state, no causal step, no transform. And an old story's stored
    ledger is read by nothing, so it reaches no model's payload."""
    calls = []
    promise = encoder_event(
        "I promise to bring the report.", speech=True,
        transforms=[{"item": "The Stranger", "patch": {"obligations": [
            {"op": "open", "who": "The Stranger", "what": "bring the report",
             "kind": "promise"}]}}])
    responses = {
        "director_prose": {"prose": 'The Stranger says, "I promise to bring the report."'},
        "director_specialist": {"events": [promise], "missing_tools": [],
                                "missing_referents": [], "notes": []}}
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, interp={"sequence": []},
                    player_input="I promise to bring the report.")
    temp_db.wset(ctx.chat.id, LEDGER_KEY, _OLD_LEDGER)

    out = getattr(director, f"director_{stage}")(ctx, 0)

    assert "obligations" not in out
    state = out["state_assertions" if stage == "interpret" else "state_diff"]
    assert "obligations" not in state
    assert all("obligations" not in step["patch"] for step in state["causal_steps"])
    assert not any(row["patch"].get("obligations")
                   for row in out["orchestration"]["transform_history"])
    assert out["orchestration"]["prose_contract"]["retired_channels"] == ["obligations"]
    assert any("obligations" in w and "retired" in w for w in ctx.warnings)
    assert calls
    for call in calls:
        assert LEDGER_KEY not in json.dumps(call["payload"], default=str), call["step_key"]


def _scoped(frame):
    """The storage key a frame-scoped row of the ledger was written under.
    Spelled out, because the key is no longer frame-scoped: `wset_for_frame`
    now writes the present's row, as for any key that never was."""
    from core.db import _FRAME_KEY_SEP
    return f"{LEDGER_KEY}{_FRAME_KEY_SEP}{frame}"


def _story_with_the_old_ledger(db):
    """A story whose world and whose checkpoint both hold the ledger's rows,
    present and frame-scoped, as one written before the retirement does."""
    from core.frames import create_frame
    from persist.checkpoints import ensure_checkpoint

    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Old story", "", time.time()))
    frame = create_frame(cid, label="Elsewhere", ordinal=0, kind="spatial",
                         split_turn_idx=0)
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 1, "begin", time.time()))
    db.wset(cid, "scene", {"rooms": {}, "positions": {}})
    db.wset(cid, LEDGER_KEY, _OLD_LEDGER)
    db.wset(cid, _scoped(frame), _OLD_LEDGER)
    assert len(db.q("SELECT key FROM world WHERE chat_id=? AND key LIKE ?",
                    (cid, LEDGER_KEY + "%"))) == 2
    ensure_checkpoint(cid, 1)
    return cid, frame


def test_a_checkpoint_carrying_the_old_ledger_still_restores(temp_db):
    from persist.checkpoints import restore_checkpoint

    cid, frame = _story_with_the_old_ledger(temp_db)
    temp_db.wset(cid, "scene", {"rooms": {"crypt": {}}, "positions": {}})
    temp_db.qi("DELETE FROM world WHERE chat_id=? AND key LIKE ?",
               (cid, LEDGER_KEY + "%"))

    restore_checkpoint(cid, 1)

    assert temp_db.wget(cid, "scene", {})["rooms"] == {}
    assert temp_db.wget(cid, LEDGER_KEY, None) == _OLD_LEDGER
    assert temp_db.wget(cid, _scoped(frame), None) == _OLD_LEDGER


def test_an_archive_carrying_the_old_ledger_still_imports(temp_db):
    from web import app

    cid, _frame = _story_with_the_old_ledger(temp_db)
    archive = json.loads(json.dumps(app.chat_export(cid)))
    assert archive["world"][LEDGER_KEY] == _OLD_LEDGER
    assert any(LEDGER_KEY in json.loads(cp["blob"])["world"]
               for cp in archive["checkpoints"])

    new_cid = app.chat_import({"data": archive})["id"]

    assert new_cid != cid
    assert temp_db.wget(new_cid, LEDGER_KEY, None) == _OLD_LEDGER
    scoped = [row["key"] for row in temp_db.q(
        "SELECT key FROM world WHERE chat_id=? AND key LIKE ?",
        (new_cid, LEDGER_KEY + "%"))]
    assert len(scoped) == 2, scoped
    cp = temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=?", (new_cid,), one=True)
    assert json.loads(cp["blob"])["world"][LEDGER_KEY] == _OLD_LEDGER
