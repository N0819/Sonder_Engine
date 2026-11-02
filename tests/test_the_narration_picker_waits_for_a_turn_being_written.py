"""Choosing between a turn's renderings waits for a pipeline still writing it.

`turn_narration_select` flips the narrator step's active variant -- the same
`UPDATE variants SET active=0` pair `edit_prose` writes, and `edit_prose`
names the race: a reroll of the same turn writes that step too, so whichever
lands second wins and the choice either vanishes or silences the beat the
run just produced. `edit_prose` holds `_require_turn_idle`; the picker held
only `_require_latest` (audit 2026-11-01, web_app F13). The page's own
`S.busy` blocks it in one tab, not from a second tab or another client.
"""
from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi import HTTPException


def _page(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Story", "", time.time()))
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 0, "I look around.", time.time()))
    sid = db.qi("INSERT INTO steps(turn_id,key,ord,label) VALUES(?,?,?,?)",
                (tid, "narrator", 0, "Narrator · render"))
    first = db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,0)",
                  (sid, json.dumps({"prose": "First."}), time.time()))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps({"prose": "Second."}), time.time()))
    return cid, tid, first


def test_a_choice_while_the_turn_is_being_written_is_refused(temp_db):
    from agents.runtime import ABORTS
    from web import app

    cid, tid, first = _page(temp_db)
    ABORTS[(cid, None)] = threading.Event()
    try:
        with pytest.raises(HTTPException) as refused:
            app.turn_narration_select(tid, {"variant_id": first})
    finally:
        ABORTS.pop((cid, None), None)
    assert refused.value.status_code == 409
    active = temp_db.q("SELECT v.content FROM variants v JOIN steps s ON s.id=v.step_id "
                       "WHERE s.turn_id=? AND v.active=1", (tid,), one=True)["content"]
    assert json.loads(active)["prose"] == "Second."


def test_a_choice_on_an_idle_turn_still_lands(temp_db):
    from web import app

    cid, tid, first = _page(temp_db)
    assert app.turn_narration_select(tid, {"variant_id": first}) == {
        "ok": True, "prose": "First."}
