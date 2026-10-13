"""A thread that has ended takes no new beat; a prose edit waits only for
its own turn. Two of Home 10's controls (docs/experiments/
OBSERVE_2026_10_13_home10.md, item 6), neither of which waits on how an
off-screen beat is rewound.

* Chat 166 turn 4583: a player line ("You yawn and stretch a little...") was
  played into bubble frame 7 after it had rejoined -- on that frame's frozen
  copy of the world, committed where nobody reads it.
* Home 10: for the 28 s Tamamo's off-screen beat ran, every control on the
  page answered "Abort it", a typo fix on page 2 included, and nothing on
  the page could reach her frame.
"""
from __future__ import annotations

import time

import pytest
from fastapi import HTTPException


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Home", "", time.time()))


def _turn(db, cid, idx, frame_id=None, prose="The lamp gutters."):
    import json
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                "VALUES(?,?,?,?,?)", (cid, idx, "", time.time(), frame_id))
    sid = db.qi("INSERT INTO steps(turn_id,key,ord,label) VALUES(?,?,?,?)",
                (tid, "narrator", 8, "narrator"))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps({"prose": prose}), time.time()))
    return tid


class TestAnEndedThread:
    def test_a_beat_played_into_a_rejoined_frame_is_refused(self, temp_db):
        from core.frames import create_frame
        from web import app
        cid = _chat(temp_db)
        bubble = create_frame(cid, label="Bubble — Tamamo", ordinal=0, kind="spatial",
                              parent_frame_id=None, split_turn_idx=0)
        temp_db.qi("UPDATE frames SET merged_turn_idx=? WHERE id=?", (1, bubble))
        with pytest.raises(HTTPException) as refused:
            app.turn_new(cid, {"input": "You yawn and stretch.", "frame_id": bubble})
        assert refused.value.status_code == 409
        assert "rejoined" in refused.value.detail
        assert temp_db.q("SELECT COUNT(*) AS n FROM turns WHERE chat_id=?",
                         (cid,), one=True)["n"] == 0, "no row left behind"
        assert (cid, bubble) not in app.ABORTS, "no slot left claimed"


class TestAProseEditWaitsOnlyForItsOwnTurn:
    def test_a_beat_running_in_another_frame_does_not_hold_it(self, temp_db):
        from web import app
        cid = _chat(temp_db)
        page2 = _turn(temp_db, cid, 2)
        app.ABORTS[(cid, 12)] = object()                 # a bubble's beat runs
        try:
            assert app.edit_prose(page2, {"prose": "The lamp gutters out."})["ok"]
        finally:
            app.ABORTS.pop((cid, 12), None)

    def test_a_new_beat_after_it_does_not_hold_it(self, temp_db):
        from web import app
        cid = _chat(temp_db)
        page2 = _turn(temp_db, cid, 2)
        _turn(temp_db, cid, 3)                           # the beat being written
        app.ABORTS[(cid, None)] = object()
        try:
            assert app.edit_prose(page2, {"prose": "The lamp gutters out."})["ok"]
        finally:
            app.ABORTS.pop((cid, None), None)

    def test_the_turn_a_run_may_be_rewriting_waits(self, temp_db):
        from web import app
        cid = _chat(temp_db)
        page2 = _turn(temp_db, cid, 2)
        app.ABORTS[(cid, None)] = object()               # a reroll of page 2
        try:
            with pytest.raises(HTTPException) as refused:
                app.edit_prose(page2, {"prose": "The lamp gutters out."})
            assert refused.value.status_code == 409
            assert "Abort" not in refused.value.detail
        finally:
            app.ABORTS.pop((cid, None), None)
