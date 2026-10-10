"""A POINTED LIGHT LIGHTS WHAT IT POINTS AT (the owner's ruling, 2026-10-09).

D3 of the Brackwater run (`docs/experiments/PLAY_2026_10_07_brackwater.md`,
F95): a carried light aimed through an opening lights the part of the next
room it reaches, the way it would, and minds see what it shows. Measured,
scratch story 166 turn 4601: from the boat, the player turned her lantern
low and angled the hood "so the beam falls onto the coat" on a stake in the
dark channel. The encoder wrote `state.pointed_at: waterlogged_coat`, the
coat had no measured place, the light field could not read the aim and lit
the lantern all round, and the coat read the channel's median -- dark, sight
`none`.

Over every checkpoint of both databases five distinct aims were ever
written, and three were shapes nothing read: a room, a thing with no
measured place in the next room, a person with no measured place in the
lamp's own room. The rules pinned here, each in the one light model every
reader uses (`world/spatial_light.py`, `world/spatial_light_field.py`):

* an aim names a room, a feature of another room, or a body with no
  measured place, and the cone points there -- through the doorway;
* a body or thing the beam is aimed at is lit where the beam falls, and
  only if the lamp's own rays reach it: a closed door, a curtain and the end
  of the lamp's reach stop it -- and where the lamp's own room is measured,
  its field says how far the beam carries even into a room that is not;
* without geometry, the room-level model lights the body a beam names, in
  its own room or through a doorway, and never the room the beam is sent
  into;
* a dark room a BEAM is pointed into shows what the beam lights through the
  way into it -- named, its lit furniture only, never its notes -- and to
  nobody whose line, or whose opening, the beam is not in. No other light
  admits a dark room: the contrast rule ("a lit room with an unlit way out
  of it has a black doorway in it") stands for a lit room's spill, for a
  lamp burning all round, and for a beam pointed at something in its own
  room;
* a thing with no place that a beam picks out of the dark is seen by those
  in the room with it.
"""

from __future__ import annotations

import copy

import pytest

from agents import perception
from world.spatial import (
    CONE_GAIN, DIM_T, POWER, aim_of, anchor_cells, beam_lit_cells,
    beam_sent_into, door_anchor_id, effective_light, light_at, light_field,
    visible_adjacent_rooms, visual_level_between,
)


# ---------------------------------------------------------------------------
# Fixtures: a dark landing and a dark yard through one open doorway
# ---------------------------------------------------------------------------

RACK = {"rack": {"desc": "a drying rack", "dir": "w", "height": "waist",
                 "footprint": "small"}}

#: The rack stands beside the doorway, where a beam sent in falls; the
#: barrel and the trough stand on the far and the north walls, out of it.
YARD = dict(RACK, **{
    "barrel": {"desc": "a rain barrel", "dir": "e", "height": "waist",
               "footprint": "small"},
    "trough": {"desc": "a stone trough", "dir": "n", "height": "waist",
               "footprint": "small"},
})

YARD_NOTES = "A walled yard of wet cobbles."


def landing_and_yard(aim, *, barrier="open", lamp="lit", p_cell=(4, 3),
                     yard_anchors=None, landing_anchors=None,
                     landing_extent=None, door="e"):
    """P stands in the landing near its east doorway, holding a lantern;
    the yard beyond is dark and holds a coat with no measured place."""
    back = {"e": "w", "n": "s"}[door]
    landing = {"name": "the landing", "desc": "", "light": "dark",
               "exposure": "enclosed", "size": "medium",
               "adjacent": [{"to": "yard", "barrier": barrier, "dir": door}]}
    if landing_extent:
        landing.pop("size")
        landing["extent"] = landing_extent
    if landing_anchors:
        landing["anchors"] = copy.deepcopy(landing_anchors)
    yard = {"name": "the yard", "desc": "", "notes": YARD_NOTES,
            "light": "dark", "exposure": "enclosed", "size": "medium",
            "adjacent": [{"to": "landing", "barrier": barrier, "dir": back}]}
    if yard_anchors:
        yard["anchors"] = copy.deepcopy(yard_anchors)
    lantern = {"name": "the lantern", "light_source": lamp,
               "light_shape": "cone", "portable": True,
               "state": {"pointed_at": aim} if aim is not None else {}}
    coat = {"name": "a wool coat", "kind": "object",
            "description": "A heavy wool coat hung on a nail.",
            "portable": True}
    return {"rooms": {"landing": landing, "yard": yard},
            "positions": {"P": "landing", "lantern": "landing",
                          "coat": "yard"},
            "entities": {"lantern": lantern, "coat": coat},
            "stations": {"P": {"cell": list(p_cell)}},
            "orientation": {},
            "contained": {"lantern": {"in": "P", "mode": "held"}},
            "poses": {}}


def lantern_source(scene, room="yard"):
    return next(s for s in light_field(scene, room).sources
                if s["id"] == "lantern")


def lamp_light_in(scene, room, lamp="lantern"):
    """The most light `lamp` itself puts on any cell of `room`."""
    lf = light_field(scene, room)
    return max((value for cell, value in lf.per_source[lamp].items()
                if lf.field.inside.get(cell) == room), default=0.0)


def opening_from(scene, observer, room):
    [opening] = perception._visible_openings(scene, observer, room)
    return opening


# ---------------------------------------------------------------------------
# What an aim names
# ---------------------------------------------------------------------------

def test_an_aim_reads_a_body_a_room_a_doorway_and_a_bearing():
    scene = landing_and_yard("coat")
    entity = scene["entities"]["lantern"]

    def read(aim):
        entity["state"]["pointed_at"] = aim
        return aim_of(scene, "lantern", entity)

    assert read("coat") == {"body": "coat", "room": "yard"}
    assert read("yard") == {"room": "yard"}
    assert read("the yard") == {"room": "yard"}
    assert read(door_anchor_id("yard")) == {"anchor": door_anchor_id("yard"),
                                            "room": "landing"}
    assert read("e") == {"degrees": 90.0}
    # A phrase names nothing the scene holds: no aim, the cone all round.
    assert read("toward the far wall of the yard") is None


def test_a_beam_aimed_into_the_next_room_points_through_its_doorway():
    """The aim names a ROOM. The light field read no room and left the cone
    all round; it now points at the first cell of the yard the lamp's rays
    reach -- the far side of the gap -- and concentrates there."""
    aimed = lantern_source(landing_and_yard("yard"))
    assert aimed["axis"] is not None
    goal = aimed["goal"]
    field = light_field(landing_and_yard("yard"), "yard").field
    assert field.inside.get(goal) == "yard"
    # The yard's own doorway cell is where the beam enters.
    yard_door = anchor_cells(landing_and_yard("yard"), "yard",
                             derive=True)[door_anchor_id("landing")]["cells"]
    assert goal == field.cell_of("yard", yard_door[0])
    # And it is brighter there than the same lamp all round.
    lit = light_field(landing_and_yard("yard"), "yard").intensity[goal]
    flat = light_field(landing_and_yard(None), "yard").intensity[goal]
    assert lit > flat


def test_a_thing_with_no_place_that_a_beam_is_aimed_at_is_lit_by_it():
    """The 4601 class: a lamp aimed through a doorway at a thing with no
    measured place. It read its room's median -- dark -- and was unseen."""
    scene = landing_and_yard("coat")
    assert light_at(scene, "coat") != "dark"
    assert visual_level_between(scene, "P", "coat") != "none"
    # Not aimed at it, the same lamp leaves it as dark as its room.
    unaimed = landing_and_yard("yard")
    assert light_at(unaimed, "coat") == "dark"
    assert visual_level_between(unaimed, "P", "coat") == "none"


def test_a_closed_door_and_a_curtain_stop_the_beam():
    for barrier in ("closed_door", "curtain"):
        scene = landing_and_yard("coat", barrier=barrier)
        assert light_at(scene, "coat") == "dark", barrier
        # The beam is aimed at the way into the yard, and lights the door.
        source = lantern_source(scene, "landing")
        door = anchor_cells(scene, "landing", derive=True)[
            door_anchor_id("yard")]["cells"]
        field = light_field(scene, "landing").field
        assert source["goal"] == field.cell_of("landing", door[0]), barrier


def test_a_beam_lights_only_as_far_as_it_carries():
    """The lamp at the far end of a long room: its rays end before the
    doorway, so the coat it is aimed at stays in the dark."""
    scene = landing_and_yard("coat", landing_extent={"w": 4, "d": 24},
                             p_cell=(2, 23), door="n")
    assert light_at(scene, "coat") == "dark"
    near = landing_and_yard("coat", landing_extent={"w": 4, "d": 24},
                            p_cell=(2, 1), door="n")
    assert light_at(near, "coat") != "dark"


def test_a_body_with_no_place_in_the_lamps_own_room_is_lit_where_it_stands():
    """Murren in the chapel (scratch story 166, idx 10-13): the lantern aimed
    at a person with no measured place in its own room. An unmeasured body
    stands at its room's centre, where an unstationed lamp stands too; the
    beam is aimed there and lights it."""
    scene = landing_and_yard("Q", p_cell=(0, 0))
    scene["positions"]["Q"] = "landing"
    source = lantern_source(scene, "landing")
    field = light_field(scene, "landing").field
    assert source["goal"] == field.cell_of("landing", (3, 3))
    assert source["axis"] is not None
    assert light_at(scene, "Q") != "dark"
    # Turned to the wall behind the lamp, the room stays dark for Q.
    scene["entities"]["lantern"]["state"]["pointed_at"] = "n"
    assert light_at(scene, "Q") == "dark"


def test_a_beam_is_concentrated_where_it_is_cast_not_on_the_hands_holding_it():
    """The lamp's own cell is its holder's, behind the beam: it takes the
    lamp's power as an all-round lamp's does. With `CONE_GAIN` there too, the
    4601 replay -- the aim at the coat readable at last -- put the lantern
    turned low at `bright` on Tamsin's own hands, and her view said "You are
    in a glare of light"."""
    scene = landing_and_yard("e")
    source = lantern_source(scene, "landing")
    assert source["axis"] == 90.0
    beam = light_field(scene, "landing").per_source["lantern"]
    assert beam[source["cell"]] == pytest.approx(POWER["lit"])
    ahead = (source["cell"][0] + 1, source["cell"][1])
    assert beam[ahead] == pytest.approx(POWER["lit"] / 2.0 * CONE_GAIN)
    assert light_at(scene, "P") == "lit"


def held_lamp_at_night(exposure, lamp, shape="cone"):
    """A dark place with nothing lit but the lamp P holds, pointed south: Q
    stands a pace to P's east, outside the beam; W two paces to P's west."""
    return {"rooms": {"r": {"name": "the strand", "desc": "", "light": "dark",
                            "exposure": exposure, "size": "large",
                            "adjacent": []}},
            "positions": {"P": "r", "Q": "r", "W": "r", "lamp": "r"},
            "entities": {"lamp": {"name": "the lamp", "light_source": lamp,
                                  "portable": True, "light_shape": shape,
                                  "state": ({"pointed_at": "s"}
                                            if shape == "cone" else {})}},
            "contained": {"lamp": {"in": "P", "mode": "held"}},
            "stations": {"P": {"cell": [6, 6]}, "Q": {"cell": [7, 6]},
                         "W": {"cell": [4, 6]}},
            "orientation": {}, "poses": {}}


@pytest.mark.parametrize("exposure, lamp, holder, beside", [
    ("open", "dim", "dim", "dark"),
    ("open", "lit", "lit", "dark"),
    ("open", "bright", "bright", "dim"),
    ("enclosed", "dim", "dim", "dark"),
    ("enclosed", "lit", "lit", "dim"),
    ("enclosed", "bright", "bright", "lit"),
])
def test_a_lamp_lights_its_holder_at_its_power_and_scatters_round_itself(
        exposure, lamp, holder, beside):
    """The hands holding a coned lamp read the lamp's own power, as an
    all-round lamp's holder does -- the gain lands where the beam is cast.
    What the gain would have put on the lamp's own cell still scatters from
    it and reaches what stands beside the lamp, so a body a pace off, outside
    the beam, keeps the light it had. Measured on the owner's chat 122: the
    Doctor a pace from the TARDIS's `bright` cone pointed south, on a clear
    night, read `dim`, and Hinami, standing at the lamp, saw him `full`;
    taking the scatter out with the gain read him `dark`, unseen at arm's
    length beside a lit lamp."""
    scene = held_lamp_at_night(exposure, lamp)
    assert light_at(scene, "P") == holder
    assert light_at(scene, "Q") == beside
    if beside != "dark":
        assert visual_level_between(scene, "P", "Q") == "full"


def test_a_dim_hand_lamp_shows_its_holder_no_more_than_an_all_round_one():
    """A `dim` lamp held in the dark lights the hands holding it `dim`
    whatever its shape, so W, two paces off, makes out what the holder
    does and not their face -- as an all-round dim lamp always gave. With
    the gain on the lamp's own cell a dim cone read `bright` there and
    showed its holder in full: the reading this change takes away, and the
    one it makes consistent."""
    cone = held_lamp_at_night("enclosed", "dim")
    pool = held_lamp_at_night("enclosed", "dim", shape="all_round")
    assert light_at(cone, "P") == light_at(pool, "P") == "dim"
    assert visual_level_between(cone, "W", "P") \
        == visual_level_between(pool, "W", "P") == "conduct"


def test_a_lamp_with_no_aim_lights_exactly_as_it_did():
    """No aim written: no goal, and the cone follows its holder's facing or
    stays all round, byte for byte."""
    scene = landing_and_yard(None)
    source = lantern_source(scene)
    assert source["aim"] is None and source["goal"] is None
    assert source["axis"] is None
    scene["orientation"] = {"P": {"facing": "e"}}
    assert lantern_source(scene)["axis"] == 90.0


# ---------------------------------------------------------------------------
# What minds see through a doorway: a beam pointed in, and nothing else
# ---------------------------------------------------------------------------

def test_a_cone_aimed_into_a_dark_room_names_it_with_only_its_lit_furniture():
    """The beam falls by the doorway, on the rack: the yard is named, the
    rack is listed, the barrel and the trough out of the beam are not, and
    the yard's notes -- what the room as a whole looks like -- are not seen,
    for the room as a whole is still dark."""
    scene = landing_and_yard("yard", yard_anchors=YARD)
    assert effective_light(scene, "yard") == "dark"
    opening = opening_from(scene, "P", "landing")
    assert opening["state"] == "seen"
    assert opening["room_name"] == "the yard"
    assert opening["room_notes"] == ""
    assert [f["anchor"] for f in opening["features"]] == ["rack"]
    # The same yard lit: its notes, and the furniture the line reaches.
    lit = landing_and_yard("yard", yard_anchors=YARD)
    lit["rooms"]["yard"]["light"] = "lit"
    shown = opening_from(lit, "P", "landing")
    assert shown["room_notes"] == YARD_NOTES
    assert {f["anchor"] for f in shown["features"]} >= {"rack", "barrel"}


def test_a_beam_sent_in_by_name_by_doorway_or_by_compass_word_shows_one_room():
    """Where the beam goes is what it shows, not how its aim is spelled: the
    room, the doorway onto it, a thing in it, and a compass word whose beam
    falls through the doorway all give one answer. A compass word that
    points the beam away from the doorway shows nothing."""
    answers = [opening_from(landing_and_yard(aim, yard_anchors=YARD),
                            "P", "landing")
               for aim in ("yard", door_anchor_id("yard"), "coat", "e")]
    assert all(answer == answers[0] for answer in answers), answers
    assert answers[0]["state"] == "seen"
    away = opening_from(landing_and_yard("n", yard_anchors=YARD), "P",
                        "landing")
    assert away["state"] != "seen" and "room_name" not in away


def test_one_hall_gives_one_answer_whether_its_light_is_a_word_or_a_fixture():
    """A hall beside a dark storeroom, a shelf on the storeroom's wall by
    the doorway. Declared `bright`, the hall's floor spills through the gap
    and lights both cells of the shelf `dim`; declared dark under a `bright`
    chandelier, the fixture casts on one of them directly. One hall, two
    ways of writing its light, and no beam in either: the doorway is black
    both times, as a lit room's way into a dark one is. (Counting every
    source's direct light, as a first build of this did, named the
    storeroom and its shelf under the chandelier and showed only darkness
    under the word -- the shelf in less light seen, the shelf in more light
    not.)"""
    def hall(light, fixture=None):
        scene = {
            "rooms": {
                "hall": {"name": "the hall", "desc": "", "light": light,
                         "exposure": "enclosed", "size": "medium",
                         "anchors": {"sconce_bracket": {
                             "desc": "an iron bracket by the door", "dir": "e",
                             "height": "head", "footprint": "small",
                             "offset": 3}},
                         "adjacent": [{"to": "store", "barrier": "open",
                                       "dir": "e"}]},
                "store": {"name": "the storeroom", "desc": "",
                          "notes": "Shelves of preserves.", "light": "dark",
                          "exposure": "enclosed", "size": "medium",
                          "anchors": {"shelf": {
                              "desc": "a shelf of jars", "dir": "w",
                              "height": "head", "footprint": "small"}},
                          "adjacent": [{"to": "hall", "barrier": "open",
                                        "dir": "w"}]}},
            "positions": {"P": "hall"}, "entities": {},
            "stations": {"P": {"cell": [2, 3]}},
            "orientation": {}, "contained": {}, "poses": {}}
        if fixture:
            scene["entities"]["chandelier"] = {
                "name": "the chandelier", "light_source": fixture,
                "portable": False}
            scene["positions"]["chandelier"] = "hall"
        return scene

    word, fixture = hall("bright"), hall("dark", fixture="bright")
    shelf = anchor_cells(word, "store", derive=True)["shelf"]["cells"]
    spilled = light_field(word, "store")
    assert [spilled.level(spilled.field.cell_of("store", tuple(c)))
            for c in shelf] == ["dim", "dim"]
    cast = light_field(fixture, "store")
    assert max(cast.per_source["chandelier"].get(
        cast.field.cell_of("store", tuple(c)), 0.0) for c in shelf) >= DIM_T
    by_word = perception._visible_openings(word, "P", "hall")
    by_fixture = perception._visible_openings(fixture, "P", "hall")
    assert by_word == by_fixture
    assert by_word[0]["state"] == "dark" and "room_name" not in by_word[0]


def test_a_lamp_burning_all_round_by_a_doorway_names_nothing_beyond_it():
    """A torch held in the doorway lights the threshold of the dark yard
    beyond -- its own light, well over dim -- and is pointed at nothing:
    whether it is all round, or a cone with no aim following no facing. The
    doorway stays black."""
    for shape in ("all_round", "cone"):
        scene = landing_and_yard(None, yard_anchors=YARD, p_cell=(5, 2))
        scene["entities"]["lantern"]["light_shape"] = shape
        assert lamp_light_in(scene, "yard") >= DIM_T, shape
        assert beam_lit_cells(scene, "yard") == set(), shape
        opening = opening_from(scene, "P", "landing")
        assert opening["state"] == "dark", shape
        assert "room_name" not in opening, shape


def test_a_beam_aimed_at_something_in_its_own_room_names_nothing_beyond_it():
    """The lantern held on the bench beside the doorway: the cone brushes
    through the gap and lights the yard's threshold, where R, standing
    beside P with a clear line through the doorway, could see it -- but it
    is pointed at the bench. Only a beam pointed INTO a room admits it."""
    bench = {"bench": {"desc": "a bench", "dir": "e", "height": "waist",
                       "footprint": "small"}}
    scene = landing_and_yard("bench", yard_anchors=YARD,
                             landing_anchors=bench)
    scene["positions"]["R"] = "landing"
    scene["stations"]["R"] = {"cell": [3, 2]}
    assert lamp_light_in(scene, "yard") >= DIM_T
    assert beam_lit_cells(scene, "yard") == set()
    opening = opening_from(scene, "R", "landing")
    assert opening["state"] != "seen" and "room_name" not in opening
    # Pointed into the yard from the same hands, the threshold is R's to see.
    scene["entities"]["lantern"]["state"]["pointed_at"] = "yard"
    assert opening_from(scene, "R", "landing")["room_name"] == "the yard"


def test_a_dark_room_that_only_the_doorways_own_glow_reaches_stays_dark():
    """The lit landing's floor spills through the doorway onto the yard's
    threshold (`FLOOR_SPILL`, the owner's tuning: the threshold dim, the
    room dark). That is the observer's own room's light on the threshold, not
    a light in the yard: the doorway still shows only darkness."""
    scene = landing_and_yard(None, yard_anchors=RACK)
    scene["entities"].pop("lantern")
    scene["contained"] = {}
    scene["positions"].pop("lantern")
    scene["rooms"]["landing"]["light"] = "lit"
    assert beam_lit_cells(scene, "yard") == set()
    assert opening_from(scene, "P", "landing")["state"] == "dark"


def test_a_thing_with_no_place_a_beam_picks_out_is_seen_by_those_beside_it():
    scene = landing_and_yard("coat")
    scene["positions"]["R"] = "yard"
    scene["stations"]["R"] = {"cell": [3, 3]}
    rows = perception._visible_things(scene, "R", "yard", bodies=["R"])
    assert [row["uid"] for row in rows] == ["coat"]
    scene["entities"]["lantern"]["state"]["pointed_at"] = "yard"
    assert perception._visible_things(scene, "R", "yard", bodies=["R"]) == []


# ---------------------------------------------------------------------------
# Three rooms in a row: the lamp's holder, the room it is aimed into, and a
# bystander beyond it -- with no geometry, and laid out
# ---------------------------------------------------------------------------

VAULT_NOTES = ("Strongboxes line the far wall; one stands open, stacked with "
               "ledgers.")


def landing_vault_stair(aim, *, laid_out=False):
    """P in the landing holds a lit torch; the vault beyond is dark and
    holds Q and R; S stands in the back stair, which opens onto the vault
    from its far side and does not adjoin the landing."""
    scene = {
        "rooms": {
            "a": {"name": "the landing", "desc": "A landing.",
                  "light": "dark",
                  "adjacent": [{"to": "b", "barrier": "open",
                                "distance": "near"}]},
            "b": {"name": "the vault", "desc": "", "light": "dark",
                  "notes": VAULT_NOTES,
                  "adjacent": [{"to": "c", "barrier": "open",
                                "distance": "near"}]},
            "c": {"name": "the back stair", "desc": "A stair.",
                  "light": "dark", "adjacent": []},
        },
        "positions": {"P": "a", "torch": "a", "Q": "b", "R": "b", "S": "c"},
        "entities": {"torch": {"name": "the torch", "light_source": "lit",
                               "portable": True, "light_shape": "cone",
                               "state": {"pointed_at": aim} if aim else {}}},
        "contained": {"torch": {"in": "P", "mode": "held"}},
    }
    if laid_out:
        for room in scene["rooms"].values():
            room["size"] = "medium"
            room["exposure"] = "enclosed"
        scene["rooms"]["a"]["adjacent"] = [
            {"to": "b", "barrier": "open", "dir": "e"}]
        scene["rooms"]["b"]["adjacent"] = [
            {"to": "a", "barrier": "open", "dir": "w"},
            {"to": "c", "barrier": "open", "dir": "e"}]
        scene["rooms"]["c"]["adjacent"] = [
            {"to": "b", "barrier": "open", "dir": "w"}]
        scene.update(stations={"P": {"cell": [4, 3]}, "S": {"cell": [1, 3]}},
                     orientation={}, poses={})
    return scene


@pytest.mark.parametrize("laid_out", [False, True])
@pytest.mark.parametrize("aim", ["b", door_anchor_id("b"), "Q"])
def test_a_beam_shows_the_room_it_is_sent_into_only_through_its_own_opening(
        aim, laid_out):
    """Without geometry a beam has no cells to light and no line to test:
    it lights only what it names, never the room, and the room is named --
    without its notes -- to whoever looks through the opening the beam is
    sent through. The bystander on the vault's far side, carrying no light,
    is shown what the vault shows them with no beam at all, and neither
    neighbour's visible rooms admit the vault's record. Laid out, the same
    three rooms give the same answers. (Lifting the vault's own light to dim
    instead, as a first build of this did, handed its notes and its record
    to both minds beside it.)"""
    scene = landing_vault_stair(aim, laid_out=laid_out)
    unlit = landing_vault_stair(None, laid_out=laid_out)
    assert effective_light(scene, "b") == "dark"
    seen = opening_from(scene, "P", "a")
    assert seen["state"] == "seen"
    assert seen["room_name"] == "the vault"
    assert seen["room_notes"] == ""
    assert perception._visible_openings(scene, "S", "c") \
        == perception._visible_openings(unlit, "S", "c")
    assert "room_name" not in opening_from(scene, "S", "c")
    for room in ("a", "c"):
        assert "b" not in [v["room_id"]
                           for v in visible_adjacent_rooms(scene, room)]


@pytest.mark.parametrize("laid_out", [False, True])
def test_a_beam_lights_the_body_it_names_and_not_the_one_beside_it(laid_out):
    scene = landing_vault_stair("Q", laid_out=laid_out)
    assert light_at(scene, "Q") == "lit"
    assert visual_level_between(scene, "P", "Q") != "none"
    assert light_at(scene, "R") == "dark"
    # Aimed at the room, it singles out nobody in it.
    room = landing_vault_stair("b", laid_out=laid_out)
    assert light_at(room, "Q") == "dark"


def test_without_geometry_a_shut_door_stops_the_beam_an_open_one_lets_through():
    opened = landing_vault_stair("Q")
    shut = landing_vault_stair("Q")
    shut["rooms"]["a"]["adjacent"][0]["barrier"] = "closed_door"
    assert light_at(opened, "Q") == "lit"
    assert light_at(shut, "Q") == "dark"
    assert effective_light(shut, "b") == "dark"
    assert not beam_sent_into(shut, "b", "a")


# ---------------------------------------------------------------------------
# A measured lamp, an unmeasured room: the lamp's own field says how far
# ---------------------------------------------------------------------------

def long_hall_and_cell(p_cell, *, measured, aim="Q"):
    """A hall laid out four paces by twenty-four, its doorway at the north
    end; P holds a lit torch aimed at Q, who stands in a cell off that
    doorway -- the cell given a size, or none."""
    cell = {"name": "the cell", "desc": "A cramped cell.", "light": "dark",
            "exposure": "enclosed",
            "adjacent": [{"to": "hall", "barrier": "open", "dir": "s",
                          "distance": "near"}]}
    if measured:
        cell["size"] = "small"
    return {
        "rooms": {
            "hall": {"name": "the long hall", "desc": "", "light": "dark",
                     "exposure": "enclosed", "extent": {"w": 4, "d": 24},
                     "adjacent": [{"to": "cell", "barrier": "open",
                                   "dir": "n", "distance": "near"}]},
            "cell": cell},
        "positions": {"P": "hall", "torch": "hall", "Q": "cell"},
        "entities": {"torch": {"name": "the torch", "light_source": "lit",
                               "portable": True, "light_shape": "cone",
                               "state": {"pointed_at": aim}}},
        "contained": {"torch": {"in": "P", "mode": "held"}},
        "stations": {"P": {"cell": list(p_cell)}},
        "orientation": {}, "poses": {}}


def test_a_beam_carries_as_far_as_the_lamps_own_field_says_into_any_room():
    """Twenty-four paces from the doorway the hall's own field has the cone
    dead about seven cells out. Whether or not the cell beyond is measured,
    Q stays dark and unseen from there, and is lit and seen with the torch
    beside the doorway: the lamp's own reach decides, never whether the far
    room happens to have a size. (Answering by the name alone wherever the
    target's room had no field lit Q `lit` from 24 paces, seen at
    `conduct`, while the measured cell read `dark` and `none`.)"""
    for measured in (True, False):
        near = long_hall_and_cell((2, 1), measured=measured)
        far = long_hall_and_cell((2, 23), measured=measured)
        assert light_at(near, "Q") == "lit", measured
        assert visual_level_between(near, "P", "Q") != "none", measured
        assert light_at(far, "Q") == "dark", measured
        assert visual_level_between(far, "P", "Q") == "none", measured


def test_an_unmeasured_room_is_named_only_while_the_beam_reaches_it():
    near = long_hall_and_cell((2, 1), measured=False, aim="cell")
    far = long_hall_and_cell((2, 23), measured=False, aim="cell")
    assert beam_sent_into(near, "cell", "hall")
    assert not beam_sent_into(far, "cell", "hall")
    seen = opening_from(near, "P", "hall")
    assert seen["state"] == "seen" and seen["room_notes"] == ""
    assert "room_name" not in opening_from(far, "P", "hall")


# ---------------------------------------------------------------------------
# The measured case, compact: a boat's deck in a dark channel
# ---------------------------------------------------------------------------

def deck_and_channel(light):
    """Turn 4601's shape: a deck inside a vessel standing in a vast dark
    channel, joined by an open way with no bearing; the player at the deck's
    middle, a lantern in her hands aimed at a coat with no measured place."""
    deck = {"name": "the deck", "parent_entity": "boat", "exposure": "open",
            "size": "tiny",
            "adjacent": [{"to": "channel", "barrier": "open_door",
                          "distance": "near"}],
            "anchors": {"thwart": {"desc": "a thwart", "dir": "n",
                                   "height": "waist", "footprint": "small"}}}
    channel = {"name": "the channel", "light": "dark", "exposure": "open",
               "extent": {"w": 6, "d": 30}, "adjacent": []}
    return {
        "rooms": {"deck": deck, "channel": channel},
        "positions": {"T": "deck", "lantern": "deck", "boat": "channel",
                      "coat": "channel"},
        "entities": {
            "boat": {"name": "the boat", "kind": "vehicle", "container": True,
                     "interior_rooms": ["deck"]},
            "lantern": {"name": "the lantern", "light_source": light,
                        "light_shape": "cone", "portable": True,
                        "state": {"pointed_at": "coat"}},
            "coat": {"name": "a coat", "kind": "object", "portable": True,
                     "description": "A wet coat caught on a stake."}},
        "stations": {"T": {"cell": [1, 1]}},
        "contained": {"lantern": {"in": "T", "mode": "held"}},
    }


def test_the_lantern_aimed_from_the_boat_lights_the_coat_on_the_stake():
    scene = deck_and_channel("dim")
    assert light_at(scene, "coat") == "dim"
    assert visual_level_between(scene, "T", "coat") == "conduct"
    opening = opening_from(scene, "T", "deck")
    assert opening["state"] == "seen" and opening["room_notes"] == ""
