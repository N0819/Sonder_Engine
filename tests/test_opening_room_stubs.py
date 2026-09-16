"""A room the opening does not see is a stub, not a description; and the
place vocabulary is one text (owner, 2026-09-16).

Measured on the owner's chat 126 ("Attempt two", turns 0-9). The opening
Director wrote the parlor's back room, which nobody had seen, as a described
room: desc "A back room behind a paneled door -- not currently visible from
the reception parlor", a guessed `light: dim`, no anchors, no entities. The
engine could not tell that placeholder from a description --
`structure.is_planned_stub` reads a non-empty desc as developed, the spatial
hand's own contract says "a room you were not handed is not a stub and needs
nothing", and the compiler files a planning need only for a room no plan
holds -- so when the door opened (turn 8) and the player walked in (turn 9)
the hand was handed moves and nothing else, the placeholder sentence rendered
verbatim into every view, the guessed light told the narrator sight was
"degraded: dim light -- shapes, not detail", and the narrator invented a
table the room did not hold.

The same opening wrote every anchor without a height, because the establish
sheet had drifted 23 rule headings behind the spatial hand's. Both are one
class: the opening contract was a copy, and copies drift.

What holds now: `director_establish` and the spatial hand's rooms chunk embed
one `room_vocabulary` fragment by reference; `RoomDef` declares `planned`,
`purpose` and `access`, so an opening can write a neighbour it has not seen
in the same shape the registry's planted stubs use, and the first beat that
enters or looks into it is handed a brief and furnishes it.
"""

from __future__ import annotations

import copy

from llm.prompts import get_prompt, prompt_fragment, specialist_prompt
from llm.schemas import validate_llm_output
from world.spatial import merge_scene_with_diff
from world.structure import (
    is_planned_stub, planned_room_brief, rooms_to_develop,
)

VOCABULARY_HEADINGS = (
    "HOW BIG IT IS", "WHAT SHAPE IT IS", "LIGHT: every room carries",
    "QUIET: a room may carry", "WHICH WALL A WAY OUT IS IN",
    "AN INSIDE IS A PLACE", "ANCHORS ARE PLACES A BODY CAN BE",
    "AN ANCHOR IS A THING WITH A HEIGHT", "STOREYS:",
    "WHAT THE WALLS GIVE BACK",
)


# ---------------------------------------------------------------------------
# One text, two readers
# ---------------------------------------------------------------------------

def test_the_place_vocabulary_reaches_both_sheets_from_one_fragment():
    fragment = prompt_fragment("room_vocabulary")
    establish = get_prompt("director_establish")
    spatial = specialist_prompt("spatial", ["rooms"])
    for heading in VOCABULARY_HEADINGS:
        assert heading in fragment, heading
        assert heading in establish, heading
        assert heading in spatial, heading
    # Resolved at card load, so the bytes are identical in both readers.
    assert fragment.strip() in establish
    assert fragment.strip() in spatial
    # And nowhere else does a copy live: a hand not granted `rooms` does not
    # carry the vocabulary, which is what proves it rides the chunk.
    assert "ANCHORS ARE PLACES A BODY CAN BE" not in specialist_prompt(
        "spatial", ["positions"])


def test_the_fragment_speaks_to_no_particular_hand():
    """The paragraphs were the spatial hand's, and three sentences named the
    hand's own world -- `state_diff.rooms`, "the objects hand's channel".
    The establish stage has no state_diff and no other hands, so the shared
    text may name neither."""
    fragment = prompt_fragment("room_vocabulary")
    assert "state_diff" not in fragment
    assert "hand's channel" not in fragment
    assert "not yours" not in fragment


def test_the_establish_sheet_carries_the_stub_rule_and_the_page_rule():
    establish = get_prompt("director_establish")
    assert "A ROOM THE OPENING DOES NOT SEE IS A STUB" in establish
    assert "THE PASSAGE MAY ALREADY BE ON THE PAGE" in establish
    # The paragraph the vocabulary superseded is gone, not doubled.
    assert "MEASURE A ROOM WHERE THE FICTION LETS YOU" not in establish
    # The output shape teaches the stub's keys.
    assert "planned OPTIONAL" in establish and "purpose OPTIONAL" in establish


# ---------------------------------------------------------------------------
# The stub survives the round trip and is briefed
# ---------------------------------------------------------------------------

def _opening():
    return {
        "location": "The Velvet Passage",
        "time": "evening",
        "scene_description": "A reception parlor.",
        "rooms": {
            "parlor": {
                "name": "Reception Parlor",
                "desc": "Silk hangings, a bench, a lamp on the west wall.",
                "adjacent": [
                    {"to": "back_room", "barrier": "closed_door", "dir": "n",
                     "name": "a paneled door"},
                ],
                "light": "lit", "exposure": "enclosed", "size": "small",
                "anchors": {"bench": {"desc": "a plum silk bench",
                                      "dir": "w", "height": "waist",
                                      "footprint": "run"}},
            },
            "back_room": {
                "name": "Treatment Room",
                "planned": True,
                "purpose": "where the proprietor works on a client",
                "adjacent": [
                    {"to": "parlor", "barrier": "closed_door", "dir": "s"},
                ],
            },
        },
        "positions": {"Mirelle": "parlor"},
        "stations": {"Mirelle": {"at": "bench", "near": []}},
    }


def test_a_stub_survives_the_establish_schema():
    out, warnings = validate_llm_output("director_establish", _opening())
    assert not [w for w in warnings if "Schema validation" in w], warnings
    stub = out["rooms"]["back_room"]
    assert stub["planned"] is True
    assert stub["purpose"] == "where the proprietor works on a client"
    assert not stub.get("desc")
    # Silence stays silence: a described room carries no `planned` key.
    assert "planned" not in out["rooms"]["parlor"]


def test_a_scene_stub_is_a_stub_and_a_placeholder_desc_is_not(temp_db):
    out, _ = validate_llm_output("director_establish", _opening())
    scene = {"rooms": out["rooms"], "positions": dict(out["positions"]),
             "stations": dict(out["stations"])}
    assert is_planned_stub(scene, "back_room")
    assert not is_planned_stub(scene, "parlor")
    # Chat 126's opening, for contrast: the same room with a desc written
    # from outside is developed as far as the engine can tell, whatever the
    # desc says -- which is the whole reason the flag exists.
    placeholder = copy.deepcopy(scene)
    placeholder["rooms"]["back_room"].pop("planned")
    placeholder["rooms"]["back_room"]["desc"] = (
        "A back room behind a paneled door -- not currently visible.")
    assert not is_planned_stub(placeholder, "back_room")


def test_the_stub_is_briefed_from_the_scene_alone(temp_db):
    """No registry row, no plan: the brief comes from what the opening
    wrote -- the name, the purpose and the exits -- so the first beat that
    opens the door or walks in is handed the seed."""
    out, _ = validate_llm_output("director_establish", _opening())
    scene = {"rooms": out["rooms"], "positions": dict(out["positions"])}
    # A shut door beside the focus room is a room the beat may open.
    reach = rooms_to_develop(scene, "parlor")
    assert "back_room" in reach
    brief = planned_room_brief(1, scene, reach)
    assert list(brief) == ["back_room"]
    assert brief["back_room"]["name"] == "Treatment Room"
    assert brief["back_room"]["purpose"] == "where the proprietor works on a client"
    assert [e["to"] for e in brief["back_room"]["exits"]] == ["parlor"]


def test_a_furnished_stub_stops_being_one(temp_db):
    out, _ = validate_llm_output("director_establish", _opening())
    scene = {"rooms": out["rooms"], "positions": dict(out["positions"]),
             "stations": {}, "entities": {}}
    furnished = merge_scene_with_diff(scene, {"rooms": {"back_room": {
        "desc": "A padded table under a low amber lamp.",
        "light": "lit",
        "anchors": {"table": {"desc": "a padded treatment table",
                              "dir": "c", "height": "waist",
                              "footprint": "large"}},
    }}})
    room = furnished["rooms"]["back_room"]
    assert room["desc"].startswith("A padded table")
    assert room["purpose"] == "where the proprietor works on a client"
    assert [e["to"] for e in room["adjacent"]] == ["parlor"]
    assert not is_planned_stub(furnished, "back_room")
    assert "back_room" not in planned_room_brief(
        1, furnished, rooms_to_develop(furnished, "parlor"))


# ---------------------------------------------------------------------------
# A channel written one level too deep
# ---------------------------------------------------------------------------

def test_a_sibling_channel_written_inside_entities_is_lifted_out():
    """Chat 132's opening (2026-09-16) died with `entities.contact_ops.name:
    Field required` three times over: the model had written three top-level
    channels INSIDE `entities`, each was then validated as an entity record,
    and the whole opening was thrown away with a complaint about a missing
    name rather than about the misplacement. Same failure the envelope
    unwrapper repairs, one level in."""
    raw = dict(_opening())
    raw["entities"] = {
        "wall_lamp": {"name": "Wall Lamp", "kind": "fixture"},
        "contact_ops": [], "contact_action_ops": [], "substance_ops": [],
    }
    out, warnings = validate_llm_output("director_establish", raw)
    assert not [w for w in warnings if "Schema validation" in w], warnings
    assert sorted(out["entities"]) == ["wall_lamp"]
    for channel in ("contact_ops", "contact_action_ops", "substance_ops"):
        assert out.get(channel) == []


def test_only_an_unambiguous_misplacement_is_lifted():
    """Three tests, all of which must hold: the key names a field this
    schema declares, its value is a LIST where a record would be an object,
    and the top-level field is not already answered. Anything else is a real
    disagreement and stays one."""
    # A thing legitimately keyed by a field name, written as a record, stays.
    raw = dict(_opening())
    raw["entities"] = {"world_facts": {"name": "The Ledger", "kind": "object"}}
    out, _ = validate_llm_output("director_establish", raw)
    assert "world_facts" in out["entities"]
    # A real top-level answer is never overwritten by a stray one.
    raw = dict(_opening())
    raw["world_facts"] = ["Mirelle rose from the bench."]
    raw["entities"] = {"world_facts": ["something else"]}
    out, _ = validate_llm_output("director_establish", raw)
    assert out["world_facts"] == ["Mirelle rose from the bench."]
