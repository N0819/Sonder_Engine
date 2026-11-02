"""The guest's payload says which beats can still arrive, and which of the
guest's own lines no beat has taken yet.

Two fields the guest page already reads when they are present (L15a's
client half, frontend_core F7 and F9, audit 2026-11-01):

* `pending` on each turn -- the beat has not committed and it is a beat of
  the guest's own era. Without it the page could only guess "the newest
  turn", and fifty beats from before a friend joined read "Waiting for this
  beat to resolve…" for good.
* `pending_input` -- the lines this guest filed that no beat of their era has
  taken yet. `guest_input` files a line under an index no turn row has, and
  the payload listed only turn rows, so a sent line vanished; a guest who
  thought it had failed sent again and silently REPLACED it (the input table
  upserts on chat, index and persona).
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Harbour", "", time.time()))
    pid = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                ("Guest", "{}", "{}"))
    db.qi("INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')",
          (cid, pid))
    return cid, pid


def _turn(db, cid, idx, *, committed, frame_id=None):
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                "VALUES(?,?,?,?,?)", (cid, idx, "", time.time(), frame_id))
    for order, key in enumerate(["director_interpret"] + (["commit"] if committed else [])):
        sid = db.qi("INSERT INTO steps(turn_id,key,ord,label) VALUES(?,?,?,?)",
                    (tid, key, order, key))
        db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
              (sid, json.dumps({}), time.time()))
    return tid


def _guest(cid, pid):
    return SimpleNamespace(state=SimpleNamespace(
        guest_grant={"chat_id": cid, "persona_id": pid}))


def test_only_an_uncommitted_beat_of_the_guests_era_is_pending(temp_db):
    from core.frames import create_frame
    from web import app

    cid, pid = _story(temp_db)
    elsewhere = create_frame(cid, label="Before", ordinal=0, kind="past")
    _turn(temp_db, cid, 0, committed=True)
    _turn(temp_db, cid, 1, committed=False, frame_id=elsewhere)
    _turn(temp_db, cid, 2, committed=False)
    turns = app.guest_state(_guest(cid, pid))["turns"]
    assert [t["pending"] for t in turns] == [False, False, True]


def test_a_line_no_beat_has_taken_is_listed_as_pending(temp_db):
    from web import app

    cid, pid = _story(temp_db)
    _turn(temp_db, cid, 0, committed=True)
    app.guest_input(_guest(cid, pid), {"idx": 1, "input": "I wave from the pier."})
    state = app.guest_state(_guest(cid, pid))
    assert state["pending_input"] == [{"idx": 1, "input": "I wave from the pier."}]

    _turn(temp_db, cid, 1, committed=True)   # the beat that takes it
    state = app.guest_state(_guest(cid, pid))
    assert state["pending_input"] == []
    assert state["turns"][1]["player_input"] == "I wave from the pier."
