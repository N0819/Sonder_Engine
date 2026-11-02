"""Every beat's memories are reviewed for tension, including a beat that
commits while an earlier beat's pass is still running.

`schedule_memory_tension_pass` queued its out-of-band review under ONE
constant job key, and the job reads only the memories minted on the turn it
was scheduled from. `core.jobs.submit` JOINS an in-flight job with the same
key, so a beat committed while a pass was running scheduled nothing, and its
rows were never reviewed. The pass costs ~114 s (its own docstring) against
~1-minute beats, so roughly every other beat went unreviewed (review
2026-11-01, persist_background_memory F14). The skip-memories job beside it
fixed exactly this class with a per-turn key.
"""

from __future__ import annotations

import json
import threading
import time

import mind.memory_judge as memory_judge
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import schedule_memory_tension_pass
from story.character_schema import default_character_data


def _ctx(temp_db, chat_id, idx, cast):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "x", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx, player_input="x",
                      created=time.time()),
        cast=cast, input="x")


def _wait(job, seconds=10.0):
    deadline = time.monotonic() + seconds
    while job.state in ("pending", "running") and time.monotonic() < deadline:
        time.sleep(0.01)


def test_a_beat_committed_during_a_pass_is_still_reviewed(temp_db,
                                                          monkeypatch):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Alice", json.dumps(default_character_data("Alice")), "{}",
         time.time(), "char_alice"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    release = threading.Event()
    reviewed = []

    def review(cid, member_id, name, minted, *, current_turn_idx, frame_id):
        reviewed.append(current_turn_idx)
        if current_turn_idx == 5:
            release.wait(5.0)       # the first beat's pass is still running
        return 0

    monkeypatch.setattr(memory_judge, "review_minted_memories", review)
    first = schedule_memory_tension_pass(_ctx(temp_db, chat_id, 5, cast))
    deadline = time.monotonic() + 5.0
    while not reviewed and time.monotonic() < deadline:
        time.sleep(0.01)
    second = schedule_memory_tension_pass(_ctx(temp_db, chat_id, 6, cast))
    release.set()
    _wait(first)
    _wait(second)
    assert sorted(reviewed) == [5, 6], \
        "the beat committed during the running pass was never reviewed"
