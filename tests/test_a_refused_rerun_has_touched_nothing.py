"""A rerun the runtime refuses is refused before it touches the world.

The `from_key` paths restored the pre-turn checkpoint, swept every later
checkpoint, took back the unseen off-screen beats, claimed the turn and
marked its commit stale -- and only then raised "not in this turn's plan" or
"director_interpret is stale" (audit of 2026-11-01, agents_runtime_loops_
mapping F1). Reproduced on a scratch database: two committed turns, a rerun
of the first from a key its plan does not hold, and after the refusal
checkpoints [1, 2] had become [1], the world marker the commit wrote was
gone, and the commit read stale. The route passes the drawer's "Run from
here" key unvalidated, and that button is drawn on every step row --
including an orphan kept for its variants and an `ext:` step of an extension
since disabled. The single-step reroll already refused first; every path now
decides its refusal while the world is untouched.
"""

from __future__ import annotations

import time

import pytest

import agents.runtime as runtime
from agents.runtime import StaleStepError
from core.db import wget, wset


def _stub(monkeypatch):
    import extension_runtime
    monkeypatch.setattr(extension_runtime, "apply_plan_splices",
                        lambda plan, chat_id=None: plan)
    stubs = {
        "director_interpret": lambda c, n: {"flow": {"reactors": []}},
        "compile_world_context": lambda c, n: {"compiled": True},
        "perception_act": lambda c, n: {"views": {}},
        "director_resolve": lambda c, n: {"state_diff": {}},
        "background_react": lambda c, n: {"fired": False},
        "perception_outcome": lambda c, n: {"views": {}},
        "narrator": lambda c, n: {"prose": "ok"},
        "director_establish": lambda c, n: {"established": True},
        "perception_establish": lambda c, n: {"views": {}},
        "commit": lambda c, n: (wset(c.chat.id, "marker", c.turn.idx)
                                or {"committed": True}),
    }
    for key, fn in stubs.items():
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Refused", "", time.time()))


def _turn(db, cid, idx):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, "go on", time.time()))


def _state(db, cid, tid):
    return {
        "checkpoints": [r["turn_idx"] for r in db.q(
            "SELECT turn_idx FROM checkpoints WHERE chat_id=? ORDER BY turn_idx",
            (cid,))],
        "marker": wget(cid, "marker"),
        "stale": sorted(r["key"] for r in db.q(
            "SELECT key FROM steps WHERE turn_id=? AND stale=1", (tid,))),
        "offscreen": db.q("SELECT offscreen FROM turns WHERE id=?", (tid,),
                          one=True)["offscreen"],
    }


@pytest.fixture
def two_turns(temp_db, monkeypatch):
    _stub(monkeypatch)
    cid = _chat(temp_db)
    t1 = _turn(temp_db, cid, 1)
    list(runtime._run_pipeline(cid, t1))
    t2 = _turn(temp_db, cid, 2)
    list(runtime._run_pipeline(cid, t2))
    return cid, t1


def test_a_key_the_plan_does_not_hold_is_refused_before_the_rewind(
        temp_db, two_turns):
    cid, t1 = two_turns
    before = _state(temp_db, cid, t1)
    assert before["checkpoints"] == [1, 2] and before["marker"] == 2
    with pytest.raises(RuntimeError, match="not in this turn's plan"):
        list(runtime._run_pipeline(cid, t1, from_key="narrator_typo"))
    assert _state(temp_db, cid, t1) == before


def test_a_stale_interpretation_is_refused_before_the_rewind(temp_db,
                                                             two_turns):
    cid, t1 = two_turns
    temp_db.qi("UPDATE steps SET stale=1 WHERE turn_id=? "
               "AND key='director_interpret'", (t1,))
    before = _state(temp_db, cid, t1)
    with pytest.raises(StaleStepError):
        list(runtime._run_pipeline(cid, t1, from_key="narrator"))
    assert _state(temp_db, cid, t1) == before


def test_a_stale_step_before_the_key_is_refused_before_the_rewind(
        temp_db, two_turns):
    cid, t1 = two_turns
    temp_db.qi("UPDATE steps SET stale=1 WHERE turn_id=? "
               "AND key='perception_act'", (t1,))
    before = _state(temp_db, cid, t1)
    with pytest.raises(StaleStepError, match="perception_act"):
        list(runtime._run_pipeline(cid, t1, from_key="narrator"))
    assert _state(temp_db, cid, t1) == before


def test_a_key_the_opening_does_not_hold_is_refused_before_the_rewind(
        temp_db, monkeypatch):
    _stub(monkeypatch)
    cid = _chat(temp_db)
    t0 = _turn(temp_db, cid, 0)
    list(runtime._run_pipeline(cid, t0))
    t1 = _turn(temp_db, cid, 1)
    list(runtime._run_pipeline(cid, t1))
    before = _state(temp_db, cid, t0)
    assert before["checkpoints"] == [0, 1]
    with pytest.raises(RuntimeError, match="not in the establishment plan"):
        list(runtime._run_pipeline(cid, t0, from_key="director_interpret"))
    assert _state(temp_db, cid, t0) == before


def test_a_key_the_plan_holds_still_reruns_from_it(temp_db, two_turns):
    """The refusal moved; the rerun itself did not change."""
    cid, t1 = two_turns
    events = list(runtime._run_pipeline(cid, t1, from_key="narrator"))
    assert events[-1]["type"] == "done"
    assert _state(temp_db, cid, t1)["stale"] == []
