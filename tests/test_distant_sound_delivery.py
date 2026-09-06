"""A sound loud enough to travel is DELIVERED, and it arrives poorer.

`world/spatial_sound_field.py` computed the far field, the finite wall and
the one-beat event channel, and nothing carried any of it to a mind: the
decibels were right and no view ever said so
(`docs/design/DESIGN_SOUND_DECIBELS.md` § 8, `docs/UNBUILT.md` § 1.117).

What is pinned here is the delivery and, more importantly, WHAT IT MAY
CARRY. A body two rooms away gets a direction and what the noise was like.
It does not get the room, the room's name, the thing that made the noise, or
a word anybody said -- a body two streets away who "hears" a line is the
same defect as one who sees through a wall, and the record's key set is
closed by construction so no caller can widen it (§ 3).
"""

from __future__ import annotations

import json
import time

import pytest

from agents.perception import perception_outcome
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

#: A chain, each room measured so the near field exists at all: without
#: geometry there is no composite to hand over FROM, and the boundary case
#: this rests on stops being a boundary.
ROOMS = ("cellar", "stair", "gallery")
DETAIL = "a long grinding collapse"

#: `FAR_FIELD_ENTRY_DB` is 70 and `SOUND_DB["deafening"]` is 61.8, so a
#: sound has to be past the ordinary ladder's top before it travels at all.
#: That is the constant doing its job, not a big number chosen for the test.
LOUD = "catastrophic"


def _scene():
    rooms = {}
    for i, rid in enumerate(ROOMS):
        adjacent = []
        if i:
            adjacent.append({"to": ROOMS[i - 1], "barrier": "open_door",
                             "dir": "w"})
        if i + 1 < len(ROOMS):
            adjacent.append({"to": ROOMS[i + 1], "barrier": "open_door",
                             "dir": "e"})
        rooms[rid] = {"name": rid.title(), "adjacent": adjacent,
                      "light": "lit", "extent": {"w": 6, "d": 6}}
    return {
        "location": "The house", "time": "night", "rooms": rooms,
        "positions": {"The Stranger": ROOMS[0], "Reya": ROOMS[2]},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _ctx(temp_db, *, events=None, omit=False, turn_idx=1):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Distant sound", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(default_character_data("Reya")), "{}",
         time.time(), "char_reya_%d" % chat_id))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", _scene())
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Distant sound", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="", created=time.time()),
        cast=cast, input="")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "speech_volume": "normal",
        "action": None,
        "flow": {"reactors": [], "addressed_to": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    diff = {}
    if not omit:
        diff["sensory_events"] = list(events or ())
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": diff}
    ctx["background_react"] = {
        "fired": False, "name": None, "reactions": [], "selected": [],
        "mode": "background_react",
    }
    return ctx


def _crash(room=ROOMS[0], level=LOUD, detail=DETAIL, **extra):
    return dict({"kind": "sound", "room": room, "level": level,
                 "source": "the cellar stair", "detail": detail}, **extra)


def _views(temp_db, **kw):
    return perception_outcome(_ctx(temp_db, **kw), "n0")["views"]


def _listener(views):
    """The view of the body two rooms from the noise."""
    return next(v for pid, v in views.items() if pid != "player")


# ---------------------------------------------------------------------------
# It arrives
# ---------------------------------------------------------------------------

def test_a_distant_event_reaches_a_listener_two_rooms_away(temp_db):
    view = _listener(_views(temp_db, events=[_crash()]))
    assert DETAIL in view, (
        "the far field graded this at three rooms and no view said so -- "
        "the whole of what was missing")


def test_it_arrives_as_a_direction_and_never_as_a_place(temp_db):
    """THE FIREWALL FLOOR. The flood knows which neighbour the sound came
    through and that room id never leaves `distant_sounds`: it is turned
    into a bearing against this listener's own facing, and a bearing is a
    direction, not a location."""
    view = _listener(_views(temp_db, events=[_crash()]))
    for spelling in (ROOMS[0], ROOMS[0].title(), "the cellar stair"):
        assert spelling not in view, (
            "%r reached a body that cannot see the room it names" % spelling)


def test_no_key_but_the_notes_own_survives_the_normaliser(temp_db):
    """A voice is not a far-field source at any volume, and the event record
    is a CLOSED SET of keys -- so words written into a key nobody reads are
    written into nothing, and neither the room the event happened in nor a
    listener beyond it ever sees them."""
    views = _views(temp_db, events=[
        _crash(quote="open the gate", speaker="The Stranger",
               heard_as="someone shouting open the gate")])
    both = views["player"] + _listener(views)
    assert DETAIL in views["player"] and "open the gate" not in both


def test_the_room_it_happened_in_hears_it_whole(temp_db):
    """The near field's, not the far field's: `distant_sounds` skips the
    listener's own room by construction, so the two never answer the same
    room and nobody is told about one bang twice."""
    view = _views(temp_db, events=[_crash()])["player"]
    assert DETAIL in view
    assert view.count(DETAIL) == 1


# ---------------------------------------------------------------------------
# ...and only when there is something to deliver
# ---------------------------------------------------------------------------

def test_a_beat_with_no_events_composes_exactly_as_it_did(temp_db):
    """The channel may only ADD on evidence it has. An empty list and an
    absent key are the same beat, and both are the beat before any of this
    existed."""
    empty = _views(temp_db, events=[])
    absent = _views(temp_db, omit=True)
    # Keyed by cast row id, which differs between two chats and is not what
    # is being compared: the prose is.
    assert empty["player"] == absent["player"]
    assert _listener(empty) == _listener(absent)
    assert DETAIL not in _listener(empty)


def test_an_event_too_quiet_to_travel_stays_where_it_happened(temp_db):
    """`FAR_FIELD_ENTRY_DB` is the door, and it is the same door for every
    story. WHICH RUNGS REACH IT MOVED 2026-09-06, on the owner's ruling to
    untie the impact ladder from the voice ladder: an `audible` noise -- a
    tool set down, a footfall -- is heard where it is made and nowhere else,
    and a `loud` one (a crowbar on a bulkhead, 72 dB against the old 56) now
    walks the room graph, which is the whole point of the ruling."""
    quiet = _views(temp_db, events=[_crash(level="audible")])
    assert DETAIL in quiet["player"]
    assert DETAIL not in _listener(quiet)
    carried = _views(temp_db, events=[_crash(level="loud")])
    assert DETAIL in _listener(carried), (
        "a hammer blow on steel is heard beyond the room that made it")


def test_an_event_naming_no_room_the_scene_has_reaches_nobody(temp_db):
    """The same normaliser the commit runs, so what a view delivers and what
    the beat stores cannot disagree about which events were real."""
    views = _views(temp_db, events=[_crash(room="a_room_nobody_built")])
    assert DETAIL not in views["player"] + _listener(views)
