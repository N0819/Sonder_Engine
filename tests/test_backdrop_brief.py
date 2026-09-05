"""The backdrop brief (`dressing/backdrops.room_brief`): the picture is drawn
from the same room record the composer and the geometry read -- walls,
openings, proportion, camera, look -- and the signature follows it, while an
occupant still cannot reach either.

Design: `docs/design/DESIGN_ROOM_FIDELITY.md` §4.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dressing import backdrops
from dressing.backdrops import (
    CAMERA_WALL_ORDER, compose_prompt, room_brief, room_projection,
    visual_signature,
)

ROOT = Path(__file__).resolve().parents[1]


def _scene():
    return {
        "time_of_day": "night",
        "rooms": {
            "hall": {
                "name": "Great Hall", "desc": "Flagstones and soot.",
                "size": "large", "region": "keep",
                "anchors": {
                    "table": {"desc": "the long table", "dir": "n",
                              "footprint": "run", "height": "waist"},
                    "hearth": {"desc": "the hearth", "dir": "s"},
                    "brazier": {"desc": "an iron brazier"},
                    "dais": {"desc": "the dais where the lord sits", "dir": "e"},
                },
                "adjacent": [
                    {"to": "yard", "barrier": "closed_door", "dir": "n",
                     "name": "the great door"},
                    {"to": "stair", "barrier": "open_door", "dir": "e",
                     "vertical": "up", "name": "a stair"},
                    {"to": "vault", "barrier": "wall", "dir": "s"},
                ],
            },
            "yard": {"name": "Yard"},
            "stair": {"name": "Stair"},
            "vault": {"name": "Vault"},
            "kitchen": {"name": "Kitchen",
                        "adjacent": [{"to": "hall", "barrier": "open",
                                      "dir": "e"}]},
        },
        "positions": {"Hinami": "hall", "Guard": "hall"},
        "entities": {"Guard": {"name": "Guard", "kind": "person"}},
        "attire": {"Hinami": {"wearing": ["a red coat"]}},
    }


REGIONS = {"keep": {"name": "The Keep", "brief": "",
                    "look": "black stone, iron and tallow light"}}


# ---------------------------------------------------------------------------
# Walls, openings, proportion, camera, look
# ---------------------------------------------------------------------------

def test_walls_group_the_anchors_by_bearing_and_carry_geometry_words():
    brief = room_brief(_scene(), "hall")
    walls = brief["walls"]
    assert walls["n"] == [{"desc": "the long table", "footprint": "run",
                           "height": "waist"}]
    assert walls["s"] == [{"desc": "the hearth"}]
    assert walls["free"] == [{"desc": "an iron brazier"}]
    # A description that names a person is dropped whole: the picture is of
    # an empty room, and "where the lord sits" puts a lord in it.
    assert "e" not in walls
    assert "door:" not in repr(walls)


def test_openings_are_the_exits_by_wall_with_state_and_never_a_destination():
    brief = room_brief(_scene(), "hall")
    openings = brief["openings"]
    assert openings["n"] == [{"barrier": "closed_door", "name": "the great door"}]
    assert openings["e"] == [{"barrier": "open_door", "name": "a stair",
                              "vertical": "up"}]
    # A wall is not an opening; a doorway declared only from the kitchen's
    # side is still a doorway in this room's west wall.
    assert "s" not in openings
    assert openings["w"] == [{"barrier": "open"}]
    assert "to" not in repr(openings) and "kitchen" not in repr(openings)


def test_proportion_says_only_what_was_authored_or_measured():
    sc = _scene()
    assert room_brief(sc, "hall")["proportion"] == "a large room"
    sc["rooms"]["hall"]["extent"] = {"w": 3, "d": 12}
    sentence = room_brief(sc, "hall")["proportion"]
    assert sentence == ("a medium room, about 3 paces east to west and 12 "
                        "north to south, long and narrow")
    sc["rooms"]["hall"]["shape"] = "round"
    sc["rooms"]["hall"]["extent"] = {"w": 8, "d": 8}
    assert room_brief(sc, "hall")["proportion"] == (
        "a large round room, about 8 paces east to west and 8 north to "
        "south, roughly square")
    # A size the engine only guessed is not asserted to the picture.
    assert "proportion" not in room_brief(sc, "yard")


def test_the_camera_is_the_main_entrance_looking_in():
    """The first passable, NON-VERTICAL doorway in compass order: the north
    door is shut and the east way is a stair, so the picture is taken from
    the west opening looking east.

    The vertical exclusion is PR14 (`PLAY_2026_09_05C_rush.md`, 2026-09-05):
    a camera stands in a doorway and looks level across the room, and a
    stair, ladder, hatch or shaft is a way up or down with no level, wide
    shot to be taken from inside it. Live, the brief for a landing put the
    camera in "the north doorway" looking south -- the north doorway being
    the stair going down into a flashover.
    """
    assert CAMERA_WALL_ORDER == ("n", "e", "s", "w")
    brief = room_brief(_scene(), "hall")
    assert brief["camera"] == {"from": "the west doorway", "looking": "east",
                               "framing": "level, wide"}
    sc = _scene()
    sc["rooms"]["hall"]["adjacent"][0]["barrier"] = "open_door"
    assert room_brief(sc, "hall")["camera"]["from"] == "the north doorway"
    for edge in sc["rooms"]["hall"]["adjacent"]:
        edge["barrier"] = "closed_door"
    sc["rooms"]["kitchen"]["adjacent"][0]["barrier"] = "window"
    assert "camera" not in room_brief(sc, "hall")


def test_the_viewer_camera_is_behind_the_setting_and_needs_a_cell_and_a_facing():
    sc = _scene()
    sc["stations"] = {"Hinami": {"at": "hearth"}}
    sc["orientation"] = {"Hinami": {"facing": "n"}}
    entrance = room_brief(sc, "hall", "Hinami")["camera"]
    assert entrance["from"] == "the west doorway"
    turned = room_brief(sc, "hall", "Hinami", viewer_camera=True)["camera"]
    assert turned["looking"] == "north" and turned["framing"] == "eye level, wide"
    assert "south" in turned["from"] and "part of the room" in turned["from"] \
        or "south side" in turned["from"]
    # No facing: the entrance camera, even with the switch on.
    sc["orientation"] = {}
    assert room_brief(sc, "hall", "Hinami", viewer_camera=True)["camera"] \
        == entrance
    # Not in the room: the entrance camera.
    sc["orientation"] = {"Hinami": {"facing": "n"}}
    sc["positions"]["Hinami"] = "yard"
    assert room_brief(sc, "hall", "Hinami", viewer_camera=True)["camera"] \
        == entrance


def test_the_look_is_the_regions_and_a_person_in_it_is_dropped():
    assert "look" not in room_brief(_scene(), "hall")
    assert room_brief(_scene(), "hall", regions=REGIONS)["look"] == \
        "black stone, iron and tallow light"
    peopled = {"keep": {"name": "The Keep", "brief": "",
                        "look": "Crowds jostle under the lamps."}}
    assert "look" not in room_brief(_scene(), "hall", regions=peopled)
    assert "look" not in room_brief(_scene(), "yard", regions=REGIONS)


# ---------------------------------------------------------------------------
# The projection and the signature
# ---------------------------------------------------------------------------

def test_the_projection_carries_the_brief_and_still_no_occupant():
    out = room_projection(_scene(), "hall", "Hinami", regions=REGIONS)
    for key in ("walls", "openings", "proportion", "camera", "look"):
        assert key in out, key
    blob = repr(out).lower()
    for leak in ("hinami", "guard", "red coat", "lord", "kitchen", "yard"):
        assert leak not in blob, leak
    assert "lighting" not in out          # the light field's slot, reserved


def test_a_moved_fixture_an_opened_door_and_a_look_are_new_pictures():
    sc = _scene()
    base = visual_signature(sc, "hall")
    moved = _scene()
    moved["rooms"]["hall"]["anchors"]["hearth"]["dir"] = "w"
    assert visual_signature(moved, "hall") != base
    opened = _scene()
    opened["rooms"]["hall"]["adjacent"][0]["barrier"] = "open_door"
    assert visual_signature(opened, "hall") != base
    assert visual_signature(sc, "hall", regions=REGIONS) != base
    shaped = _scene()
    shaped["rooms"]["hall"]["extent"] = {"w": 3, "d": 12}
    assert visual_signature(shaped, "hall") != base


def test_a_bystander_is_still_not_a_new_picture():
    sc = _scene()
    base = visual_signature(sc, "hall", viewer="Hinami")
    sc["positions"]["Stranger"] = "hall"
    sc["entities"]["Stranger"] = {"name": "Stranger", "kind": "person"}
    sc["stations"] = {"Stranger": {"at": "table"}}
    sc["orientation"] = {"Stranger": {"facing": "s"}}
    assert visual_signature(sc, "hall", viewer="Hinami") == base
    # The viewer turning is not a new picture either -- unless the owner
    # switched the viewer camera on, which is the cost the setting names.
    sc["stations"]["Hinami"] = {"at": "hearth"}
    sc["orientation"]["Hinami"] = {"facing": "n"}
    assert visual_signature(sc, "hall", viewer="Hinami") == base
    assert visual_signature(sc, "hall", viewer="Hinami", viewer_camera=True) \
        != base


def test_a_room_with_nothing_to_brief_hashes_as_it_did():
    sc = {"rooms": {"cell": {"name": "Cell", "desc": "Bare."}}, "positions": {}}
    assert room_brief(sc, "cell") == {}
    material_keys = set(room_projection(sc, "cell"))
    assert not material_keys & {"walls", "openings", "proportion", "camera",
                                "look"}


# ---------------------------------------------------------------------------
# The draft and the card
# ---------------------------------------------------------------------------

def test_the_draft_is_composed_from_the_walls_outward():
    place = room_projection(_scene(), "hall", regions=REGIONS)
    draft = compose_prompt(place, None, "")
    assert "north wall: the long table (waist-high, running the length of the wall), the great door" in draft
    assert "east wall: a stair leading up" in draft
    assert "south wall: the hearth" in draft
    assert "standing free of the walls: an iron brazier" in draft
    assert "west wall: an opening" in draft
    assert "seen from the west doorway looking east, level, wide, the middle of the floor empty" in draft
    assert "a large room" in draft
    assert "in the manner of the district: black stone, iron and tallow light" in draft
    assert draft.index("a large room") < draft.index("north wall")


def test_the_lighting_slot_replaces_the_level_word_when_present():
    place = {"name": "Cellar", "light": "dark"}
    assert "near-total darkness" in compose_prompt(place, None, "")
    place["lighting"] = "one lantern on the far wall, the rest in shadow"
    out = compose_prompt(place, None, "")
    assert "one lantern on the far wall" in out
    assert "near-total darkness" not in out


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_hard_rules_paragraph_is_unchanged(language):
    """One clause changed -- the paragraph naming what the agent receives.
    The HARD RULES paragraph is byte-identical to the pre-split reference
    in both packs."""
    reference = json.loads((ROOT / "tests" / "data" / "prompt_cards_presplit"
                            / f"{language}.json").read_text(encoding="utf-8"))
    before = reference["prompts"]["backdrop_prompt"].split("\n\n")
    after = (ROOT / "language_packs" / language / "cards" / "system_prompts"
             / "prompts" / "backdrop_prompt.txt").read_text(
                 encoding="utf-8").split("\n\n")
    assert len(before) == len(after)
    assert before[0] == after[0]                  # the role
    assert before[1] == after[1]                  # HARD RULES
    assert before[2] != after[2]                  # the brief clause
    assert before[3].strip() == after[3].strip()  # the output shape
    for token in ("walls", "openings", "camera", "look", "proportion"):
        assert token in after[2], token


def test_the_agent_receives_the_brief_not_a_concatenation():
    """`refine_prompt` hands the agent `place`, which IS the brief."""
    import inspect
    src = inspect.getsource(backdrops.refine_prompt)
    assert '{"place": place, "draft": draft}' in src


# ---------------------------------------------------------------------------
# The region's look: the seam that writes it
# ---------------------------------------------------------------------------

def test_a_regions_look_is_written_once_and_read_by_the_registry(temp_db):
    """`set_region_look` is the writer the brief reads through
    (`region_registry`); an entry with no look keeps the shape the regions
    tests pin, and an empty look removes the field."""
    import time
    from world.regions import (normalize_regions, region_registry,
                               set_region_look)
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Keep", "", time.time()))
    assert region_registry(cid, None) == {}
    entry = set_region_look(cid, None, "The Keep", "black stone and tallow light")
    assert entry == {"name": "The Keep", "brief": "",
                     "look": "black stone and tallow light"}
    registry = region_registry(cid, None)
    assert registry["the_keep"]["look"] == "black stone and tallow light"
    assert set_region_look(cid, None, "the_keep", "  ") == {"name": "The Keep",
                                                             "brief": ""}
    assert "look" not in region_registry(cid, None)["the_keep"]
    assert normalize_regions({"items": {"x": {"name": "X"}}})["items"]["x"] \
        == {"name": "X", "brief": ""}
    assert set_region_look(cid, None, "", "anything") is None


# ---------------------------------------------------------------------------
# PD12: a brief describes what the room IS
#
# `room_brief(scene, "bare_hilltop")` on the road run's committed scene --
# `exposure: open`, overcast with rain, morning -- answered "a vast round
# room, about 15 paces east to west and 20 north to south", bucketed the
# scrub and turf under "walls", and put the camera at "the north doorway".
# An image made from that brief is an interior, and none of exposure, weather
# or day phase appeared in it at all.
# ---------------------------------------------------------------------------

def _hilltop():
    return {
        "time_of_day": "morning",
        "weather": {"sky": "overcast", "precipitation": "rain",
                    "intensity": "light", "wind": "breeze",
                    "temperature": "cold"},
        "rooms": {
            "bare_hilltop": {
                "name": "Bare Hilltop", "exposure": "open",
                "shape": "round", "extent": {"w": 15, "d": 20},
                "anchors": {
                    "scrub": {"desc": "patches of low scrub and coarse turf",
                              "dir": "n", "height": "waist",
                              "footprint": "run"},
                    "cairn": {"desc": "a heap of grey stones"},
                },
                "adjacent": [{"to": "north_slope", "dir": "n"},
                             {"to": "south_slope", "dir": "s"}],
            },
            "north_slope": {"name": "North Slope", "exposure": "open"},
            "south_slope": {"name": "South Slope", "exposure": "open"},
        },
        "positions": {}, "entities": {},
    }


def test_an_open_room_is_briefed_as_ground_and_horizon_and_not_as_a_room():
    brief = room_brief(_hilltop(), "bare_hilltop")
    blob = json.dumps(brief).casefold()
    for interior in ("room", "wall", "doorway", "ceiling", "floor"):
        assert interior not in blob, interior
    assert set(brief["ground"]) == {"n", "free"}
    assert set(brief["ways"]) == {"n", "s"}
    assert "walls" not in brief and "openings" not in brief


def test_an_open_rooms_brief_names_the_sky_the_hour_and_the_weather():
    brief = room_brief(_hilltop(), "bare_hilltop")
    assert brief["sky"]["exposure"] == "open"
    assert brief["sky"]["time"] == "morning"
    assert brief["sky"]["weather"]
    assert brief["proportion"] == (
        "a vast roughly circular stretch of open ground, about 15 paces east "
        "to west and 20 north to south, deeper than it is wide")
    assert brief["camera"]["from"] == "the north edge of the stretch of open ground"


def test_the_open_draft_reads_as_outdoors():
    place = room_projection(_hilltop(), "bare_hilltop")
    draft = compose_prompt(place, None, "")
    assert ("to the north: patches of low scrub and coarse turf (waist-high, "
            "running right across the ground), the ground carries on") in draft
    assert "standing out in the open: a heap of grey stones" in draft
    assert "in the open air, the horizon past the edges of the ground" in draft
    assert "the middle of the ground empty" in draft
    assert "wall" not in draft and "doorway" not in draft


def test_an_enclosed_room_is_briefed_and_hashed_exactly_as_it_was():
    """Byte-identity where a scene carries none of this: an enclosed room's
    brief keeps its keys, its text and its cache key."""
    sc = _scene()
    brief = room_brief(sc, "hall")
    assert set(brief) == {"walls", "openings", "proportion", "camera"}
    assert "sky" not in brief and "ground" not in brief and "ways" not in brief
    assert brief["proportion"] == "a large room"
    assert brief["camera"]["from"] == "the west doorway"
