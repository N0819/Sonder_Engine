"""The commit tail must actually SCHEDULE its out-of-band work.

Three producers ride the tail of `_commit_all_locked`, after the turn's facts
are durable: autobiographical memory consolidation, offscreen profile ticks,
and the paid `character_agent` rung. Each is expensive, each is deliberately
off the player's wall clock, and each is invisible when it stops running --
the turn still commits, the story still reads, and nothing warns.

They were pinned by asserting a substring of `inspect.getsource`, on the
stated grounds that driving the whole of `_commit_all_locked` "would test
everything except the one line that regressed". An audit disproved that: with

    job = None if True else schedule_memory_consolidation(ctx)

the source text is unchanged, the call never executes, and the entire suite
stays green. All three could be switched off silently. That is the exact shape
of the failure recorded in AGENTS.md as five mechanisms "built, documented,
tested and never ran once".

These drive a real commit and assert on the RESULT the tail returns, which is
what a caller and the pipeline drawer actually see.
"""

from __future__ import annotations

import time

import pytest

from pipeline_context import ChatData, PipelineContext, TurnData


#: What `_prepare_turn_commit` hands the domains. The tail is under test, so
#: preparation is stubbed -- preparing a real scene would test preparation.
def _prepared(_ctx):
    return {"scene": {"scene": {}, "clock": None}, "mapping": {},
            "memories": {}, "claims": {}}


def _context(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "test", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="test", created=time.time()),
        cast=[], input="test")


@pytest.fixture
def commit_tail(temp_db, monkeypatch):
    """Drive a real `commit_all`, recording which producers were reached.

    Everything before the tail is stubbed -- the tail is what is under test,
    and preparing a full scene would test the preparation instead.
    """
    import commit as commit_module
    import offscreen as offscreen_module

    monkeypatch.setattr(commit_module, "_prepare_turn_commit", lambda ctx: {
            "scene": {"scene": {}, "clock": None}, "mapping": {},
            "memories": {}, "claims": {}})

    called = {}

    def record(name, result=None):
        def scheduler(*args, **kwargs):
            called[name] = True
            return result
        return scheduler

    monkeypatch.setattr(commit_module, "schedule_memory_consolidation",
                        record("memory_consolidation"))
    monkeypatch.setattr(offscreen_module, "schedule_profile_ticks",
                        record("profile_ticks"))
    monkeypatch.setattr(offscreen_module, "schedule_agent_ticks",
                        record("agent_ticks"))

    ctx = _context(temp_db)
    commit_module.commit_all(ctx, nonce=0)
    return called


@pytest.mark.parametrize("producer", [
    "memory_consolidation",   # autobiographical summaries
    "profile_ticks",          # offscreen dormant-character ticks
    "agent_ticks",            # the paid character_agent rung
])
def test_the_commit_tail_reaches_every_out_of_band_producer(commit_tail, producer):
    assert commit_tail.get(producer), (
        f"{producer} was never called: the commit tail committed the turn and "
        "silently did not schedule it")


def test_the_blocking_twin_is_not_used_by_the_tail(temp_db, monkeypatch):
    """Consolidation has an in-band twin kept for direct callers and tests.
    The tail must not reach for it -- measured live, the first consolidation
    of a chat was 29.5s of a 45.8s commit, inside the player's wait.
    """
    import commit as commit_module

    monkeypatch.setattr(commit_module, "_prepare_turn_commit", lambda ctx: {
            "scene": {"scene": {}, "clock": None}, "mapping": {},
            "memories": {}, "claims": {}})
    monkeypatch.setattr(commit_module, "schedule_memory_consolidation",
                        lambda ctx: None)

    def blocking(*args, **kwargs):
        raise AssertionError(
            "_consolidate_committed_memories ran inside the commit: the "
            "player is now waiting for a background summarisation")

    # commit_memories resolves this name in commit_memory_write's globals
    # since the split; patched on the facade, this stub is INERT and the
    # test goes green while proving nothing (it asserts by absence).
    import commit_memory_write
    monkeypatch.setattr(commit_memory_write,
                        "_consolidate_committed_memories", blocking)
    commit_module.commit_all(_context(temp_db), nonce=0)


def test_a_failing_producer_warns_and_does_not_roll_the_turn_back(
        temp_db, monkeypatch):
    """Every one of the three is wrapped: a failure is a warning, never a
    rollback, and never silence."""
    import commit as commit_module

    monkeypatch.setattr(commit_module, "_prepare_turn_commit", lambda ctx: {
            "scene": {"scene": {}, "clock": None}, "mapping": {},
            "memories": {}, "claims": {}})

    def boom(*args, **kwargs):
        raise RuntimeError("scheduler exploded")

    monkeypatch.setattr(commit_module, "schedule_memory_consolidation", boom)
    ctx = _context(temp_db)
    results = commit_module.commit_all(ctx, nonce=0)

    assert results is not None, "a failing producer must not abort the commit"
    assert any("consolidation" in w.lower() for w in ctx.warnings), (
        "a failed producer must warn -- never silence")
