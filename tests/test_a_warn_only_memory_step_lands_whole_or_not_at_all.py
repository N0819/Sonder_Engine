"""A memory-commit step the commit only warns about lands whole or not at
all.

`commit_memories` catches and warns around the evidence floor, disputes,
memory looks, importance bumps and recall access counts, inside the turn's
transaction. Each writes row by row, and inside a transaction a write runs
on the outer connection with no savepoint, so a raise part-way kept the rows
already written -- committed with the turn under a warning saying the step
was not applied (review 2026-11-01, persist_background_memory F22). Each
guarded call is now its own savepoint.
"""

from __future__ import annotations

import time

import persist.commit_memory_write as commit_memory_write
from core.db import qi
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_memories


def test_a_step_that_fails_half_way_leaves_nothing_and_the_turn_lands(
        temp_db, monkeypatch):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 4, "x", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=4, player_input="x",
                      created=time.time()),
        cast=[], input="x")

    def half_a_look(chat_id_, char_id, ref, look):
        qi("INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
           (chat_id_, "half_written_look", '"partial"'))
        raise RuntimeError("the second row failed")

    monkeypatch.setattr(commit_memory_write, "record_memory_look", half_a_look)
    prepared = {"memory_batch": {"prepared": [], "embedded": None},
                "relationship_ops": [], "state_updates": [],
                "memory_looks": [(chat_id, 1, "t1:7:episode", {"why": "x"})],
                "event_content": "the beat"}
    commit_memories(ctx, 0, prepared=prepared, consolidate=False)
    assert temp_db.q("SELECT value FROM world WHERE chat_id=? AND key=?",
                     (chat_id, "half_written_look"), one=True) is None, \
        "half the step landed under a warning that said it did not"
    assert any("memory feeling not kept" in w for w in ctx.warnings)
    assert temp_db.q("SELECT content FROM events WHERE chat_id=? AND "
                     "turn_id=?", (chat_id, turn_id),
                     one=True)["content"] == "the beat"
