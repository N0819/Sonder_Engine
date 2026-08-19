"""What a concurrent group of steps keeps, and what it hands back.

Two properties the sequential path already has and the parallel copy did not:
the reasoning trace of the call each member paid for, and the output of a
member that succeeded beside one that raised.
"""

from __future__ import annotations

import time

import pytest

import agents.runtime as runtime
from agents.runtime import Bus, _run_parallel_group, _stream_parallel
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(chat_id=1):
    return PipelineContext(
        chat=ChatData(id=chat_id, name="", persona_id=None, lorebook_id=None,
                      scenario="", created=0.0),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="",
                      created=0.0),
        cast=[], input="",
    )


def test_each_worker_carries_its_own_reasoning_trace_out():
    from llm.providers import last_reasoning

    def job(text):
        def run():
            last_reasoning.set(text)
            return {"prose": text}
        return run

    bus = Bus()
    holders = {}
    jobs = [("narrator", job("thought about the narrator")),
            ("narrator_extra", job("thought about the co-player"))]
    list(_stream_parallel(bus, jobs, holders))

    # A ContextVar set inside a worker is invisible to the generator thread,
    # so `save_step`'s own fallback read cannot see it -- the value has to be
    # handed back through `holders`, exactly as the single-step path does.
    assert holders["narrator"]["reasoning"] == "thought about the narrator"
    assert holders["narrator_extra"]["reasoning"] == "thought about the co-player"
    assert last_reasoning.get() in (None, "")


def test_a_failed_member_does_not_discard_a_sibling_that_finished(
        temp_db, monkeypatch):
    from agents.storage import active_content

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Parallel", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))

    def boom(ctx, nonce):
        raise RuntimeError("the first member failed")

    monkeypatch.setitem(runtime.STEP_HANDLERS, "narrator", boom)
    monkeypatch.setitem(runtime.STEP_HANDLERS, "narrator_extra",
                        lambda ctx, nonce: {"prose": "rendered for the co-player"})

    ctx = _ctx(chat_id)
    group = [("narrator", "Narrator · render"),
             ("narrator_extra", "Narrator · render (other players)")]
    keys = ["narrator", "narrator_extra"]

    with pytest.raises(RuntimeError):
        list(_run_parallel_group(Bus(), turn_id, group, keys, ctx))

    # Every member of a group has already finished by the time the first
    # failure is seen -- `_stream_parallel` joins them all. Raising in plan
    # order used to throw away a later sibling's paid output unsaved, so the
    # resume re-ran and re-paid for a call that had already succeeded.
    saved = active_content(turn_id, "narrator_extra")
    assert saved and saved.get("prose") == "rendered for the co-player"
    assert ctx.get("narrator_extra") == {"prose": "rendered for the co-player"}
    # The failure is still the failure: nothing was saved for it, and the
    # exception still reaches the caller.
    assert active_content(turn_id, "narrator") is None
