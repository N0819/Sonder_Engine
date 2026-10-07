"""A scenario story's first line is a beat, and whoever it speaks to can answer.

Measured twice (scratch stories 165 and 166, 2026-10-07): the player's first
submission walked the assessor up to the pilot she had come to meet,
introduced her and asked a question. Turn 0 runs the establishment plan,
which has no character step, so the pilot could not answer, and the page
closed on "The bell answered nothing. Neither did she." -- the engine's
silence, written down as hers. A greeting launch never had the gap: its turn
0 is the greeting and the player's first line is turn 1, a beat like any
other. A scenario chat now has the same shape: the scenario is established
as turn 0 with no input, inside the slot the submission claimed, and the line
is played as turn 1. With no scenario the line is the only passage there is,
and it opens the story as it always did.
"""

import time

import pytest
from fastapi import HTTPException

from agents import runtime
from agents import story_planner as sp
from agents.runtime import ABORTS
from agents.storage import save_step
from web import app as app_module

SCENE = "Dusk on the landing stage. The pilot waits at its far end."
LINE = ('I walk the stage to her. "Hester Gale? That bell -- fire, flood, '
        'or somebody dead?"')


def _chat(db, scenario):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Fen", scenario, time.time()))


@pytest.fixture
def recorded(monkeypatch):
    """The pipeline and the opening plan, recorded. The pipeline stub keeps
    the slot discipline the real one does: it releases the slot in its own
    `finally` unless asked to keep it."""
    runs, plans, threads = [], [], []
    abort_first = {"on": False}

    def fake_run_pipeline(cid, tid, abort=None, frame_id=None, keep_slot=False,
                          **kw):
        try:
            runs.append({"tid": tid, "keep_slot": keep_slot,
                         "slot_held": (cid, frame_id) in ABORTS})
            if abort_first["on"] and len(runs) == 1:
                yield {"type": "aborted", "turn_id": tid}
                return
            save_step(tid, "commit", "commit", 0, {"key": "commit"})
            yield {"type": "step", "key": "commit"}
        finally:
            if not keep_slot:
                ABORTS.pop((cid, frame_id), None)

    def fake_plan(cid, frame_id=None, *, passage, first_beat=""):
        plans.append({"passage": passage, "first_beat": first_beat})
        return {}

    real_drain = app_module._drain_on_own_thread

    def drain(gen, sink):
        thread = real_drain(gen, sink)
        threads.append(thread)
        return thread

    monkeypatch.setattr(app_module, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(sp, "run_opening_plan", fake_plan)
    monkeypatch.setattr(app_module, "_drain_on_own_thread", drain)
    yield {"runs": runs, "plans": plans, "abort_first": abort_first}
    for thread in threads:
        thread.join(timeout=5)


def _turns(db, cid):
    return [(r["idx"], r["player_input"], r["id"]) for r in db.q(
        "SELECT id, idx, player_input FROM turns WHERE chat_id=? ORDER BY idx",
        (cid,))]


def _join(recorded):
    deadline = time.time() + 5
    while time.time() < deadline and len(recorded["runs"]) < 2:
        time.sleep(0.02)


def test_the_scenario_is_turn_zero_and_the_line_is_turn_one(temp_db, recorded):
    cid = _chat(temp_db, SCENE)
    out = app_module.turn_new(cid, {"input": LINE}, detach=1)
    _join(recorded)
    turns = _turns(temp_db, cid)
    assert [(idx, text) for idx, text, _ in turns] == [(0, ""), (1, LINE)]
    assert out["turn_id"] == turns[1][2], "the beat the player wrote is the one returned"
    assert recorded["plans"] == [{"passage": SCENE, "first_beat": LINE}], (
        "the line is played next, so the plan places bodies before it")
    runs = recorded["runs"]
    assert [r["tid"] for r in runs] == [turns[0][2], turns[1][2]]
    assert runs[0]["keep_slot"] is True and runs[1]["keep_slot"] is False
    assert runs[1]["slot_held"], "nothing entered the frame between them"
    assert sorted(r["turn_idx"] for r in temp_db.q(
        "SELECT turn_idx FROM checkpoints WHERE chat_id=?", (cid,))) == [0, 1], (
        "the line's checkpoint is the state the opening committed")


def test_without_a_scenario_the_line_opens_the_story(temp_db, recorded):
    cid = _chat(temp_db, "")
    app_module.turn_new(cid, {"input": LINE}, detach=1)
    assert [(idx, text) for idx, text, _ in _turns(temp_db, cid)] == [(0, LINE)]
    assert recorded["plans"] == [{"passage": LINE, "first_beat": ""}]
    assert [r["keep_slot"] for r in recorded["runs"]] == [False]


def test_an_empty_first_line_is_only_the_opening(temp_db, recorded):
    cid = _chat(temp_db, SCENE)
    app_module.turn_new(cid, {"input": "   "}, detach=1)
    assert [idx for idx, _text, _ in _turns(temp_db, cid)] == [0]
    assert recorded["plans"] == [{"passage": SCENE, "first_beat": ""}]


def test_a_stopped_opening_plays_no_line_and_frees_the_frame(temp_db, recorded):
    recorded["abort_first"]["on"] = True
    cid = _chat(temp_db, SCENE)
    with pytest.raises(HTTPException) as caught:
        app_module.turn_new(cid, {"input": LINE}, detach=1)
    assert caught.value.status_code == 409
    assert all(idx == 0 for idx, _text, _ in _turns(temp_db, cid))
    assert (cid, None) not in ABORTS


def test_the_opening_task_carries_the_line_beside_the_passage(temp_db):
    cid = _chat(temp_db, SCENE)
    task = sp._opening_task(cid, None, SCENE, LINE)
    assert task["passage"] == SCENE and task["first_beat"] == LINE
    assert "first_beat" not in sp._opening_task(cid, None, SCENE)


def test_a_run_can_keep_its_slot(temp_db, monkeypatch):
    cid = _chat(temp_db, SCENE)
    monkeypatch.setattr(runtime, "_run_pipeline", lambda *a, **k: iter(()))
    abort = runtime.begin_pipeline(cid, None)
    list(runtime.run_pipeline(cid, 1, abort=abort, keep_slot=True))
    assert ABORTS.get((cid, None)) is abort
    list(runtime.run_pipeline(cid, 1, abort=abort))
    assert (cid, None) not in ABORTS
