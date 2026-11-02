"""A guest's poll sends the prose that changed since the page's last read, and
every turn's flags every time.

The guest page polls `/api/guest/state` every ten seconds and was sent every
turn's prose each time: ~199 KB a poll on a 171-turn story (chat 64), for a
transcript that grows only at its end (web_routes_extensions efficiency 3,
audit 2026-11-01). The answer now carries `mark` -- the creation time of the
newest prose it holds -- and a page that sends it back as `?since=` gets
`prose` only on the rows whose prose was written after it: a new beat, or an
older one a rerun rewrote. Every row still carries `stale`, `stale_from`,
`prose_stale` and the guest's own line, and `rev` -- its prose's own time --
so a page that holds a different `rev` for a row without `prose` knows to read
the whole story again (a host who re-activated an older rendering).

A page that sends nothing is answered exactly as before.
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


def _turn(db, cid, pid, idx, prose, created):
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, idx, "", time.time()))
    sid = db.qi("INSERT INTO steps(turn_id,key,ord,label) VALUES(?,?,?,?)",
                (tid, "narrator_extra", 0, "Narrator · render (other players)"))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps({str(pid): {"prose": prose}}), created))
    return tid, sid


def _rerun(db, sid, pid, prose, created):
    db.qi("UPDATE variants SET active=0 WHERE step_id=?", (sid,))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps({str(pid): {"prose": prose}}), created))


def _guest(cid, pid):
    return SimpleNamespace(state=SimpleNamespace(
        guest_grant={"chat_id": cid, "persona_id": pid}))


def _prose(state):
    return {row["idx"]: row["prose"] for row in state["turns"] if "prose" in row}


def test_a_page_that_sends_nothing_is_answered_whole(temp_db):
    from web import app

    cid, pid = _story(temp_db)
    _turn(temp_db, cid, pid, 0, "Dawn.", 1000.0)
    _turn(temp_db, cid, pid, 1, "Gulls.", 2000.0)
    state = app.guest_state(_guest(cid, pid))
    assert _prose(state) == {0: "Dawn.", 1: "Gulls."}
    assert state["mark"] == 2000.0
    assert [row["rev"] for row in state["turns"]] == [1000.0, 2000.0]


def test_since_the_mark_only_what_was_written_after_it_is_sent(temp_db):
    from web import app

    cid, pid = _story(temp_db)
    _first, first_step = _turn(temp_db, cid, pid, 0, "Dawn.", 1000.0)
    _turn(temp_db, cid, pid, 1, "Gulls.", 2000.0)
    mark = app.guest_state(_guest(cid, pid))["mark"]

    quiet = app.guest_state(_guest(cid, pid), since=mark)
    assert _prose(quiet) == {}
    assert [row["idx"] for row in quiet["turns"]] == [0, 1], "every row, every poll"
    assert quiet["mark"] == mark

    _turn(temp_db, cid, pid, 2, "A bell.", 3000.0)
    assert _prose(app.guest_state(_guest(cid, pid), since=mark)) == {2: "A bell."}

    _rerun(temp_db, first_step, pid, "Dawn, again.", 4000.0)
    later = app.guest_state(_guest(cid, pid), since=mark)
    assert _prose(later) == {0: "Dawn, again.", 2: "A bell."}
    assert later["mark"] == 4000.0


def test_the_flags_ride_every_row_whether_or_not_its_prose_does(temp_db):
    from web import app

    cid, pid = _story(temp_db)
    tid, sid = _turn(temp_db, cid, pid, 0, "Dawn.", 1000.0)
    mark = app.guest_state(_guest(cid, pid))["mark"]
    temp_db.qi("UPDATE steps SET stale=1 WHERE id=?", (sid,))
    row = app.guest_state(_guest(cid, pid), since=mark)["turns"][0]
    assert "prose" not in row
    assert row["stale"] is True and row["prose_stale"] is True
    assert row["rev"] == 1000.0
