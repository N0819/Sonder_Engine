"""What is still standing HERE is a question about a room (A63).

Three sites asked it -- a body walking in, a crowd standing there, a caravan
pulling up -- and all three asked with ONE chat-wide
`ORDER BY occurred_at DESC LIMIT ARRIVAL_SURFACES * 4`, then filtered by room
in Python. That is a window over the STORY: twelve located events anywhere
newer than the barred gate, and the room holding the gate offers nothing to
anyone, forever. `carriers.standing_surfaces_reader` is the one helper and it
queries per room.
"""

from __future__ import annotations

import json
import time
import types

from story.carriers import ARRIVAL_SURFACES, standing_surfaces_reader


def _event(db, cid, turn_id, event_id, room, at, witnessed="something stands"):
    db.qi(
        "INSERT INTO world_events(event_id,chat_id,turn_id,frame_id,"
        "occurred_at,duration_seconds,kind,location_id,payload,seed,committed) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, cid, turn_id, None, float(at), 0.0, "consequence", room,
         json.dumps({"what": "the mechanism failed", "witnessed": witnessed,
                     "source_event_id": "scheduled"}),
         "seed", time.time()))


def _story(db):
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Carrier story", "", time.time()))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 3, "", time.time()))
    return cid, turn_id


#: How many newer events elsewhere it takes to bury a quiet room's surface
#: under the OLD chat-wide window. One more than the window read.
_BUSY = ARRIVAL_SURFACES * 4 + 1


def test_a_quiet_rooms_surface_survives_a_busy_story(temp_db):
    cid, turn_id = _story(temp_db)
    _event(temp_db, cid, turn_id, "gate", "quiet_yard", 10.0,
           witnessed="the gate is barred from the far side")
    for n in range(_BUSY):
        _event(temp_db, cid, turn_id, f"market_{n}", "market", 100.0 + n)

    surfaces = standing_surfaces_reader(cid, None)
    here = surfaces("quiet_yard")
    assert [row["event_id"] for row, _, _ in here] == ["gate"]
    assert here[0][2] == "the gate is barred from the far side"


def test_a_room_offers_its_own_newest_surfaces_and_no_more(temp_db):
    cid, turn_id = _story(temp_db)
    for n in range(ARRIVAL_SURFACES + 2):
        _event(temp_db, cid, turn_id, f"yard_{n}", "quiet_yard", 10.0 + n)

    surfaces = standing_surfaces_reader(cid, None)
    here = surfaces("quiet_yard")
    assert len(here) == ARRIVAL_SURFACES
    # Newest first: this is walking in and seeing what happened, not
    # archaeology.
    assert [row["event_id"] for row, _, _ in here] == [
        "yard_4", "yard_3", "yard_2"]


def test_an_event_with_no_public_surface_is_not_one(temp_db):
    cid, turn_id = _story(temp_db)
    _event(temp_db, cid, turn_id, "private", "quiet_yard", 20.0, witnessed="")
    _event(temp_db, cid, turn_id, "gate", "quiet_yard", 10.0)
    surfaces = standing_surfaces_reader(cid, None)
    assert [row["event_id"] for row, _, _ in surfaces("quiet_yard")] == ["gate"]


def test_the_beats_own_events_are_skipped(temp_db):
    cid, turn_id = _story(temp_db)
    _event(temp_db, cid, turn_id, "gate", "quiet_yard", 10.0)
    _event(temp_db, cid, turn_id, "bell", "quiet_yard", 20.0)
    surfaces = standing_surfaces_reader(cid, None, skip_event_ids=["bell"])
    assert [row["event_id"] for row, _, _ in surfaces("quiet_yard")] == ["gate"]


def test_another_era_is_another_story(temp_db):
    cid, turn_id = _story(temp_db)
    _event(temp_db, cid, turn_id, "gate", "quiet_yard", 10.0)
    from web import app

    future = app.frames_create(
        cid, {"label": "Future", "ordinal": 10, "kind": "future"})["id"]
    temp_db.qi("UPDATE world_events SET frame_id=? WHERE chat_id=?",
               (future, cid))
    assert standing_surfaces_reader(cid, None)("quiet_yard") == []
    assert [row["event_id"] for row, _, _
            in standing_surfaces_reader(cid, future)("quiet_yard")] == ["gate"]


def test_a_body_walking_into_the_quiet_room_learns_the_gate(temp_db):
    """The end-to-end shape: the acquisition path, not just the reader."""
    from story.carriers import advance_carriers

    cid, turn_id = _story(temp_db)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mora", json.dumps({"identity": {"name": "Mora", "uid": "mora_uid"}}),
         "{}", time.time()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) "
        "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
    temp_db.wset(cid, "living_world", {"rumor_ledger": "floor"})
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    _event(temp_db, cid, turn_id, "gate", "quiet_yard", 10.0,
           witnessed="the gate is barred from the far side")
    for n in range(_BUSY):
        _event(temp_db, cid, turn_id, f"market_{n}", "market", 100.0 + n)

    scene = {"rooms": {"quiet_yard": {"name": "Yard", "adjacent": []},
                       "market": {"name": "Market", "adjacent": []}},
             "positions": {"Mora": "quiet_yard"}}
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=turn_id, idx=3, frame_id=None))

    advance_carriers(ctx, scene, {"events": []})
    row = temp_db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
                    (cid, char_id), one=True)
    held = json.loads(row["state"] or "{}").get("carried_reports") or []
    assert [r["world_event_id"] for r in held] == ["gate"]
