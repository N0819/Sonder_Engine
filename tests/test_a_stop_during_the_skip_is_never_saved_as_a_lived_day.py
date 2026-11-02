"""A Stop pressed while a stage runs is never saved as that stage's answer.

`Aborted` is a `RuntimeError`, and the skip stage caught it as an ordinary
failure at every model seam: each mind asked when the user pressed Stop got
`None` back, lived the default day (empty `doing`, so its own work told the
encoder nothing and nothing re-raised), and `skip_lives` returned normally --
and the runtime saved it `stale=0`, because `compute_step` checks the flag
only on entry. Resume then treated the skip as done and the commit made
canon a stretch in which every asked mind slept in place (audit of
2026-11-01, agents_runtime_loops_mapping F2: `ask()` returned `None | no
answer (Aborted: generation aborted by user)`).

Two floors, the class and the instance: no stage that FINISHES under a set
Stop is saved (the commit excepted -- its writes are durable when it returns,
and its row is the record that they are), and the skip stage re-raises
`Aborted` at its seams the way `director`, `background` and `skip_work` do.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

import agents.runtime as runtime
from agents import skip_stage
from agents.storage import variant_count
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.providers import Aborted, cancel_event


def _ctx(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Stop", "", time.time()))
    tid = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "wait a week", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Stop", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=tid, chat_id=cid, idx=1, player_input="x",
                      created=time.time()),
        cast=[], input="x")
    return ctx, tid


@pytest.fixture
def armed():
    event = threading.Event()
    token = cancel_event.set(event)
    yield event
    cancel_event.reset(token)


def test_a_stage_that_finishes_under_a_stop_is_not_saved(temp_db, monkeypatch,
                                                          armed):
    ctx, tid = _ctx(temp_db)

    def swallowed_the_stop(key, _ctx, _nonce):
        armed.set()                       # the Stop lands mid-stage...
        return {"minds": {}, "span": {}}  # ...and the stage answers anyway

    monkeypatch.setattr(runtime, "compute_step", swallowed_the_stop)
    with pytest.raises(Aborted):
        list(runtime._step_stream(runtime.Bus(), tid, "skip_lives", "Skip", 2,
                                  ctx, 0))
    assert variant_count(tid, "skip_lives") == 0
    assert ctx.get("skip_lives") is None


def test_a_group_that_finishes_under_a_stop_is_not_saved(temp_db, monkeypatch,
                                                         armed):
    ctx, tid = _ctx(temp_db)

    def swallowed_the_stop(key, _ctx, _nonce):
        armed.set()
        return {"declared": key}

    monkeypatch.setattr(runtime, "compute_step", swallowed_the_stop)
    group = [("character:1", "One"), ("character:2", "Two")]
    with pytest.raises(Aborted):
        list(runtime._run_parallel_group(
            runtime.Bus(), tid, group, ["character:1", "character:2"], ctx))
    assert variant_count(tid, "character:1") == 0
    assert variant_count(tid, "character:2") == 0


def test_the_commit_that_landed_under_a_stop_keeps_its_record(
        temp_db, monkeypatch, armed):
    """The commit's writes are durable when it returns; dropping its row would
    leave the world holding a commit the turn says it lacks."""
    ctx, tid = _ctx(temp_db)

    def landed(key, _ctx, _nonce):
        armed.set()
        return {"committed": True}

    monkeypatch.setattr(runtime, "compute_step", landed)
    list(runtime._step_stream(runtime.Bus(), tid, "commit", "Commit", 9, ctx, 0))
    assert variant_count(tid, "commit") == 1


def test_a_stage_with_no_stop_is_saved_as_before(temp_db, monkeypatch, armed):
    ctx, tid = _ctx(temp_db)
    monkeypatch.setattr(runtime, "compute_step",
                        lambda key, _c, _n: {"prose": "fine"})
    list(runtime._step_stream(runtime.Bus(), tid, "narrator", "Narrate", 7,
                              ctx, 0))
    assert variant_count(tid, "narrator") == 1


# ---- the skip stage's own seams ------------------------------------------------

def _stopped(*_a, **_k):
    raise Aborted("generation aborted by user")


def test_the_skip_question_lets_a_stop_through(monkeypatch):
    import agents.character as character
    import agents.character_bare as character_bare
    import agents.character_evidence as character_evidence
    import story.scene as scene
    from world import skip_itinerary as itin

    monkeypatch.setattr(character, "character_step",
                        lambda ctx, cid, nonce, skip=None: {
                            "payload": {"self": {}}, "role": "character_mid"})
    monkeypatch.setattr(skip_stage, "last_view", lambda ctx, cid: (None, []))
    monkeypatch.setattr(skip_stage, "_standing_place",
                        lambda chat_id, name, row: ("hall", None))
    monkeypatch.setattr(skip_stage, "_stored_scene",
                        lambda chat_id: {"rooms": {"hall": {"name": "Hall"}}})
    monkeypatch.setattr(scene, "awareness_map", lambda chat_id: {})
    monkeypatch.setattr(character_evidence, "compact_character_evidence",
                        lambda payload: (payload, {}))
    monkeypatch.setattr(character_bare, "reading_order", lambda w: w)
    monkeypatch.setattr(character_bare, "without_engine_numbers", lambda w: w)
    monkeypatch.setattr(skip_stage, "_agent_json", _stopped)
    ctx = PipelineContext(
        chat=ChatData(id=7, name="c", persona_id=None, lorebook_id=None,
                      scenario="", created=0.0),
        turn=TurnData(id=1, chat_id=7, idx=5, player_input="x", created=0.0),
        cast=[], input="x")
    row = {"id": 1, "sheet": json.dumps({"identity": {"name": "Elias"}}),
           "status": "active"}
    with pytest.raises(Aborted):
        skip_stage.ask(ctx, row, itin.Span(0.0, 7200.0, 8.0, 24.0))


def test_the_skips_decision_requests_let_a_stop_through(monkeypatch):
    from llm import decisions
    from world import skip_itinerary as itin

    monkeypatch.setattr(decisions, "decide", _stopped)
    monkeypatch.setattr(itin, "short_of", lambda log: [0])
    monkeypatch.setattr(itin, "without_questions",
                        lambda name, log, language=None: {"without:0": {}})
    with pytest.raises(Aborted):
        skip_stage.judge_what_was_missing(
            "Elias", [{"doing": "mend the net", "missing": ["twine"]}])
