"""A turn row is a beat that happened, and a variant is an alternative.

Two findings from the play campaign of 2026-09-05
(`docs/experiments/PLAY_2026_09_05C_quiet.md`,
`docs/experiments/PLAY_2026_09_05C_multitude.md`):

  * PQ10 -- the turn row is written before the pipeline runs and nothing
    removed it when the run died before the first stage saved anything. A
    provider ran out of credit and left one half-committed turn and eight
    rows with zero steps; the chat's `idx` walked from 10 to 19 across beats
    that never happened, which overran the Writers' Room's scheduled arrival
    (it was retired stale) and ticked an NPC's intention counters against
    nothing.
  * PM19 -- `perception_act` is deterministic and its inputs never changed,
    and a resume re-ran it once per failure: sixteen variants on one turn,
    fifteen of them inactive and byte-equivalent, while every model stage
    held one.
"""

from __future__ import annotations

import json
import time

import pytest

import agents.runtime as runtime
from agents.runtime import _discard_stepless_turn, _step_stream
from agents.storage import save_step, variant_count
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.checkpoints import ensure_checkpoint


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Test", "", time.time()))


def _turn(db, cid, idx=1, text="hold the door"):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, text, time.time()))


def _ctx(db, cid, tid, idx=1):
    return PipelineContext(
        chat=ChatData(id=cid, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=tid, chat_id=cid, idx=idx, player_input="x",
                      created=time.time()),
        cast=[], input="x")


# ---- PQ10 -----------------------------------------------------------------

def test_a_beat_that_produced_no_step_is_not_a_turn(temp_db):
    """quiet 2026-09-05, PQ10. The provider failed at `director_interpret`
    and the row stayed, holding the player's line and nothing else -- and the
    next beat allocated its idx off it."""
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid, idx=1)
    ensure_checkpoint(cid, 1)

    assert _discard_stepless_turn(cid, tid) is True
    assert temp_db.q("SELECT COUNT(*) c FROM turns WHERE chat_id=?", (cid,),
                     one=True)["c"] == 0
    assert temp_db.q("SELECT COUNT(*) c FROM checkpoints WHERE chat_id=? "
                     "AND turn_idx=?", (cid, 1), one=True)["c"] == 0


def test_a_partial_beat_with_real_work_in_it_survives(temp_db):
    """NO STEP, not "no commit". A turn that ran three stages and then failed
    is resumable from the pipeline drawer, and deleting it would destroy the
    record -- which is exactly what the live run's `turn_id 13` was."""
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid, idx=1)
    save_step(tid, "director_interpret", "Interpret", 0, {"flow": {}})

    assert _discard_stepless_turn(cid, tid) is False
    assert temp_db.q("SELECT COUNT(*) c FROM turns WHERE id=?", (tid,),
                     one=True)["c"] == 1


def test_a_first_stage_failure_leaves_the_clock_where_it_was(temp_db,
                                                             monkeypatch):
    """The whole point of PQ10: the story clock must not advance across a
    beat that never ran. Driven through `run_pipeline` so the wiring is under
    test, not only the helper."""
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid, idx=3)
    ensure_checkpoint(cid, 3)

    def explode(*_a, **_kw):
        raise RuntimeError("HTTP 402: out of credit")
        yield  # pragma: no cover -- generator shape

    monkeypatch.setattr(runtime, "_run_pipeline", explode)
    with pytest.raises(RuntimeError):
        list(runtime.run_pipeline(cid, tid))

    assert temp_db.q("SELECT COUNT(*) c FROM turns WHERE chat_id=?", (cid,),
                     one=True)["c"] == 0
    latest = temp_db.q("SELECT MAX(idx) m FROM turns WHERE chat_id=?", (cid,),
                       one=True)["m"]
    assert latest is None


def test_an_abort_before_the_first_step_removes_the_row_too(temp_db,
                                                            monkeypatch):
    """A player who stops the beat before anything ran did not play a beat."""
    from llm.providers import Aborted
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid, idx=0)

    def stop(*_a, **_kw):
        raise Aborted("stopped")
        yield  # pragma: no cover

    monkeypatch.setattr(runtime, "_run_pipeline", stop)
    events = list(runtime.run_pipeline(cid, tid))

    assert [e["type"] for e in events] == ["aborted"]
    assert temp_db.q("SELECT COUNT(*) c FROM turns WHERE id=?", (tid,),
                     one=True)["c"] == 0


def test_a_failure_never_replaces_itself_with_a_cleanup_failure(temp_db,
                                                                monkeypatch):
    """Housekeeping is not allowed to become the error the caller sees."""
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid, idx=1)

    def boom(*_a, **_kw):
        raise AssertionError("cleanup exploded")

    monkeypatch.setattr(runtime, "q", boom)
    assert _discard_stepless_turn(cid, tid) is False


# ---- PM19 -----------------------------------------------------------------

def test_a_deterministic_stage_rerun_unchanged_mints_no_second_variant(
        temp_db, monkeypatch):
    """multitude 2026-09-05, PM19. Fifteen byte-equivalent dead variants of
    `perception_act` on one turn, one per provider retry."""
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid)
    ctx = _ctx(temp_db, cid, tid)
    answer = {"views": {"player": "You stand in the hall."}}
    monkeypatch.setattr(runtime, "compute_step",
                        lambda key, _ctx, _n: dict(answer))

    for _ in range(3):
        list(_step_stream(runtime.Bus(), tid, "perception_act", "Perceive", 2,
                          ctx, variant_count(tid, "perception_act")))

    assert variant_count(tid, "perception_act") == 1


def test_a_stage_that_answers_differently_still_gets_its_variant(
        temp_db, monkeypatch):
    """Stated over the CONTENT, not over a list of deterministic keys: a
    genuinely new answer is a genuine alternative and is kept."""
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid)
    ctx = _ctx(temp_db, cid, tid)
    answers = iter([{"prose": "one"}, {"prose": "two"}, {"prose": "two"}])
    monkeypatch.setattr(runtime, "compute_step",
                        lambda key, _ctx, _n: next(answers))

    for _ in range(3):
        list(_step_stream(runtime.Bus(), tid, "narrator", "Narrate", 7, ctx,
                          variant_count(tid, "narrator")))

    assert variant_count(tid, "narrator") == 2


def test_the_reused_variant_is_the_active_one_and_clears_stale(
        temp_db, monkeypatch):
    """A resumed step still has to come out of this un-stale, or the next
    resume refuses to build on it."""
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid)
    ctx = _ctx(temp_db, cid, tid)
    monkeypatch.setattr(runtime, "compute_step",
                        lambda key, _ctx, _n: {"views": {"player": "still"}})
    list(_step_stream(runtime.Bus(), tid, "perception_act", "Perceive", 2, ctx,
                      0))
    temp_db.qi("UPDATE steps SET stale=1 WHERE turn_id=?", (tid,))

    list(_step_stream(runtime.Bus(), tid, "perception_act", "Perceive", 2, ctx,
                      1))

    row = temp_db.q("SELECT stale FROM steps WHERE turn_id=? AND key=?",
                    (tid, "perception_act"), one=True)
    assert row["stale"] == 0
    active = temp_db.q(
        "SELECT COUNT(*) c FROM steps s JOIN variants v ON v.step_id=s.id "
        "WHERE s.turn_id=? AND v.active=1", (tid,), one=True)
    assert active["c"] == 1
