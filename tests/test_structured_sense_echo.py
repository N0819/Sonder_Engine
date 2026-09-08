"""A structured echo of a sense may not exceed the sense (A79).

Review 2026-09-07 finding A79: four fields of the character payload are sight
and nothing else -- `perception.here_affords` (what the room visibly
affords), `perception.corridor_sight` (what looking straight down each
passage shows), the `in_sight` recall cue handed to the memory context (the
rooms currently in view), and the onward counts and bearings
`_annotate_known_exits` writes onto `perception.spatial_frame` out of
`visible_adjacent_rooms` (what looking THROUGH each doorway shows) -- and
each was computed from the world alone. `composer._sense_graded` grades every
admission the composed VIEW makes through the card
(`spatial.sense_adjusted`, G4), so an authored-blind card correctly received
no sight in its view and then received four structured statements of what it
could see beside it.

The gate is the engine's own and it subtracts: a card whose sight channel is
ABSENT cannot be reached by the best sight the world has, so the echo goes
with it. A dulled or keen card is untouched -- these fields carry no ladder
to shift, and dulled sight is still sight.

The exits frame is withheld by ABSENCE rather than by a zero, because that is
what its own reader already means: "absent means cannot tell from here --
never none", and `_verdict` reads a missing `visibly_no_way_through` as
untried, which is the conservative answer.
"""

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data


def _sheet(name, sight_acuity):
    sheet = default_character_data(name)
    sheet.setdefault("embodiment", {})["senses"] = [
        {"channel": "sight", "acuity": sight_acuity, "range": "ordinary",
         "notes": ""},
        {"channel": "hearing", "acuity": "ordinary", "range": "ordinary",
         "notes": ""},
    ]
    return sheet


def _scene():
    """A lit room with a bed in it, a straight lit run of two more rooms
    north of it, and a body standing in the first. The run has to be longer
    than one room: a corridor sight is what the line meets BEYOND the room
    the view already delivers, so a single neighbour reports nothing."""
    return {
        "location": "Room A", "time": "day",
        "rooms": {
            "room_a": {
                "name": "Room A", "desc": "A plain room.", "light": "lit",
                "anchors": {"bed": {"desc": "a low bed"}},
                "adjacent": [{"to": "room_b", "dir": "north",
                              "barrier": "open"}],
            },
            "room_b": {
                "name": "Room B", "desc": "Another room.", "light": "lit",
                "adjacent": [{"to": "room_a", "dir": "south",
                              "barrier": "open"},
                             {"to": "room_c", "dir": "north",
                              "barrier": "open"}],
            },
            "room_c": {
                "name": "Room C", "desc": "The end of the run.",
                "light": "lit",
                "adjacent": [{"to": "room_b", "dir": "south",
                              "barrier": "open"}],
            },
        },
        "positions": {"Kestrel": "room_a"},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _payload(temp_db, monkeypatch, sight_acuity):
    """Run one character step and hand back its payload and the memory
    context's own cue keywords."""
    import agents.character as character_module

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Echo", "", time.time()))
    temp_db.wset(cid, "scene", _scene())
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Kestrel", json.dumps(_sheet("Kestrel", sight_acuity)), "{}",
         time.time(), "char_kestrel"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Echo", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx.director_interpret = {"flow": {"reactors": [char_id],
                                       "tom_triggers": []}}

    seen = {}

    def _fake_memory_context(**kwargs):
        seen["in_sight"] = kwargs.get("in_sight")
        return {}

    def _fake_agent_json(role, step_key, system, payload, **kwargs):
        seen["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "build_character_memory_context",
                        _fake_memory_context)
    monkeypatch.setattr(character_module, "_agent_json", _fake_agent_json)
    character_module.character_step(ctx, char_id, nonce=0)
    return seen


_SIGHT_EXIT_KEYS = ("onward_exits_visible", "onward_bearings",
                    "visibly_no_way_through")


def _exit_sight_keys(spatial_frame):
    """Every sight-derived key present on any exit of the frame.

    `spatial_frame` buckets its exits egocentrically, so the three keys live
    one level down, inside whichever bucket the doorway landed in.
    """
    found = set()
    for bucket in (spatial_frame or {}).values():
        for entry in (bucket if isinstance(bucket, list) else []):
            if isinstance(entry, dict):
                found.update(k for k in _SIGHT_EXIT_KEYS if k in entry)
    return found


def test_an_ordinary_card_still_receives_every_sight_echo(temp_db,
                                                          monkeypatch):
    """The fixture has to be able to produce all four, or the blind half
    below proves nothing."""
    seen = _payload(temp_db, monkeypatch, "ordinary")
    perception = seen["payload"]["perception"]

    assert perception.get("here_affords"), perception
    assert perception.get("corridor_sight"), perception
    assert seen["in_sight"] == ["Room B"], seen["in_sight"]
    assert _exit_sight_keys(perception.get("spatial_frame")) == {
        "onward_exits_visible", "onward_bearings"}, perception


def test_a_sightless_card_receives_none_of_them(temp_db, monkeypatch):
    """The defect: a card authored blind was handed the bed it cannot see,
    the passage it cannot look down, the room in view as a recall cue, and
    -- the fourth echo in the same payload -- what looking through the
    doorway shows, written onto its own exits frame."""
    seen = _payload(temp_db, monkeypatch, "absent")
    perception = seen["payload"]["perception"]

    assert not perception.get("here_affords"), perception
    assert perception.get("corridor_sight") == [], perception
    assert not seen["in_sight"], seen["in_sight"]
    # ABSENT, not zeroed: the frame's own reader takes a missing key as
    # "cannot tell from here", and `_verdict` reads a missing
    # `visibly_no_way_through` as untried -- the conservative answer.
    assert _exit_sight_keys(perception.get("spatial_frame")) == set(), \
        perception.get("spatial_frame")
    assert perception.get("spatial_frame"), "the frame itself still stands"


@pytest.mark.parametrize("acuity", ["dulled", "keen"])
def test_a_shifted_channel_is_not_a_cut_channel(temp_db, monkeypatch,
                                                acuity):
    """The gate is `sense_adjusted`'s own distinction: an offset moves a
    grade along a ladder, and only an ABSENT channel cuts. These fields have
    no ladder, so anything short of absent keeps them."""
    seen = _payload(temp_db, monkeypatch, acuity)
    perception = seen["payload"]["perception"]

    assert perception.get("here_affords"), perception
    assert perception.get("corridor_sight"), perception
    assert seen["in_sight"] == ["Room B"], seen["in_sight"]
    assert _exit_sight_keys(perception.get("spatial_frame")) == {
        "onward_exits_visible", "onward_bearings"}, perception
