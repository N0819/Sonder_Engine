"""The debug capture keeps its window, and leaves with the story.

`persist/llm_capture.py` has a retention rule -- `RETAIN_TURNS` turns per
chat, `prune` to enforce it, `vacuum_blobs` to collect what nothing
references -- and neither function had a caller (audit 2026-11-01,
persistence F15; DATABASE.md said capture was "pruned to RETAIN_TURNS per
chat"). With capture on, the owner's setting, `llm_capture` grew with every
turn of every chat, and a deleted story's prompts, payloads and reasoning --
its text -- stayed in `llm_blobs` after the story was gone.

The rule: a turn's first captured call prunes its chat to the window, and
deleting a story collects every blob nothing references any more.
"""

from __future__ import annotations

import time

from core.db import q, set_setting
from persist import llm_capture
from persist.chat_delete import delete_chat_data


def _story(db, turns):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Captured", "", time.time()))
    ids = [db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                 (cid, idx, "", time.time())) for idx in range(turns)]
    return cid, ids


def _capture_on():
    set_setting("llm_capture_enabled", "1")
    set_setting("llm_capture_bodies", "full")


def test_a_new_turns_capture_prunes_its_chat_to_the_window(temp_db, monkeypatch):
    _capture_on()
    monkeypatch.setattr(llm_capture, "RETAIN_TURNS", 3)
    cid, turns = _story(temp_db, 5)
    for tid in turns:
        llm_capture.record_exchange(turn_id=tid, step_key="narrator", role="narrator",
                                    system="sheet", response=f"prose {tid}")
    kept = sorted({r["turn_id"] for r in q("SELECT turn_id FROM llm_capture")})
    assert kept == turns[-3:]


def test_deleting_a_story_collects_the_blobs_only_it_referenced(temp_db):
    _capture_on()
    cid, (tid,) = _story(temp_db, 1)
    other, (other_tid,) = _story(temp_db, 1)
    llm_capture.record_exchange(turn_id=tid, step_key="narrator", role="narrator",
                                system="shared sheet", response="the doomed story's prose")
    llm_capture.record_exchange(turn_id=other_tid, step_key="narrator", role="narrator",
                                system="shared sheet", response="the kept story's prose")

    delete_chat_data(cid)

    bodies = {r["body"] for r in q("SELECT body FROM llm_blobs")}
    assert "the doomed story's prose" not in bodies
    assert {"shared sheet", "the kept story's prose"} <= bodies
