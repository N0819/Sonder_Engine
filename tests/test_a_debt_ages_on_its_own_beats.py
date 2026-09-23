"""A debt ages on the beats of the life that owes it.

A turn index is chat-wide, and two causality bubbles interleave their turns on
it, so `now - opened` counted the other bubble's beats too: a debt aged twice
as fast as the life that owed it -- "age 22 beats" on Emory's twelfth beat,
and 22 "MUST be discharged" warnings in one run (playerless Aldermill round 8,
2026-09-23).
"""
import time

from core.db import active_frame_id, wset_for_frame
from core.frames import create_frame
from persist.commit import pending_obligation_view


def _two_lives(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Aldermill", "", time.time()))
    emory = create_frame(cid, label="Emory", ordinal=0, kind="spatial",
                         split_turn_idx=0)
    sal = create_frame(cid, label="Sal", ordinal=0, kind="spatial",
                       split_turn_idx=0)
    for idx in range(1, 7):                     # 1,3,5 Emory's; 2,4,6 Sal's
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
              "VALUES(?,?,?,?,?)",
              (cid, idx, "", time.time(), emory if idx % 2 else sal))
    wset_for_frame(cid, "pending_obligations", [
        {"id": "o1", "who": "Emory Vane", "what": "grease the neck",
         "kind": "demand", "opened_turn": 1}], emory)
    return cid, emory


def test_a_debt_in_one_bubble_ages_on_that_bubbles_beats(temp_db):
    cid, emory = _two_lives(temp_db)
    token = active_frame_id.set(emory)
    try:
        view = pending_obligation_view(cid, 5)
    finally:
        active_frame_id.reset(token)
    assert view[0]["age_beats"] == 2               # turns 3 and 5, not 2..5
    assert view[0]["must_discharge_this_beat"] is True


def test_a_story_with_one_frame_ages_as_it_always_did(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Plain", "", time.time()))
    for idx in range(1, 5):
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                   "VALUES(?,?,?,?)", (cid, idx, "", time.time()))
    temp_db.wset(cid, "pending_obligations", [
        {"id": "o1", "who": "Mara", "what": "fetch the lamp", "kind": "demand",
         "opened_turn": 2}])
    assert pending_obligation_view(cid, 4)[0]["age_beats"] == 2
