"""A VOICE LEAVING A ROOM IS PRICED BY THE OPENING IT LEAVES BY
(`DESIGN_SOUND_FIELD.md` § 20, 2026-10-20; `spatial_sound_field.
room_sound_flood(voice=True)`, `far_field_coupling`, `ring_hold_db`).

Measured on the probe story (a rock lighthouse, all stone, 2026-10-20,
turn idx 5): the keeper spoke in an ordinary voice in the lamp room and the
player, two storeys down in the kitchen behind a shut timber door, was given
every word -- `far_loss_db` 30.2 from the speaker's cell, a voice of 32.8 dB
against a 27 dB floor. The other way her ordinary voice reached him as a
voice and no word (`far_loss_db` 52.5): one path, 22 dB apart by direction.
Two faults. Each open stair cost what the free field's spreading over its
next room happened to be (6-7 dB), where the hearing table charges an
opening its coupling into the room beyond (`ROOM_COUPLING_DB` 10) and a
stair is a duct a doorway wide that climbs a storey; and the bare lamp
room's ring was handed to its openings as its reverberant level over the
far wall's direct level (22.3 dB), at the source alone.

The rules, one test (or more) each:

  1. rooms away, a voice is the hearing table's own budget carried room by
     room: the room's drop, and each opening its transmission and its
     coupling -- whole two openings on, in pieces at three, its voice only
     at four; a SOUND keeps the free field's reach;
  2. a stair, a ladder and a hatch are each a doorway and the way's own
     loss; one flight between two rooms is still one opening, whole;
  3. a ringing room's ring is counted where it stands -- the room a voice is
     made in, the room it is heard in, a room it crosses -- so a path is one
     number both ways;
  4. the ring is Sabine's, measured from one pace, and bounded;
  5. the tower: the keeper's ordinary voice does not reach the kitchen, a
     shout reaches it in pieces at most, and inside the stone the voice
     still carries down the stair.
"""

from __future__ import annotations

import pytest

import math

from world.spatial import (APERTURE_LOSS_DB, DOORWAY_AREA_M2, HATCH_AREA_M2,
                           ROOM_COUPLING_DB, SOUND_DB, SPEECH_DB,
                           VOICE_ROOM_DROP_DB, WAY_LOSS_DB, RING_GAIN_MAX_DB,
                           far_field_coupling, far_path, hear_level,
                           ring_hold_db, room_reverberation, room_sound_flood,
                           spatial_rel_between, spreading_loss_db,
                           voice_carries)

VOLUMES = ("normal", "loud", "shout")
#: The step from a voice's level at its cell to its level a pace off.
ONE_PACE_DB = spreading_loss_db(1.0)


def _run(hops, *, size="medium", surface=None, ways=None):
    """`hops` enclosed rooms in a line past the first, joined by open
    doorways -- or, where `ways` names an edge index, by that vertical way."""
    rooms = {}
    for i in range(hops + 1):
        rooms["r%d" % i] = {"name": "room %d" % i, "exposure": "enclosed",
                            "size": size, "anchors": {}, "adjacent": []}
        if surface:
            rooms["r%d" % i]["surface"] = surface
    for i in range(hops):
        way = (ways or {}).get(i)
        edge = {"to": "r%d" % (i + 1), "barrier": "open_door", "dir": "e"}
        back = {"to": "r%d" % i, "barrier": "open_door", "dir": "w"}
        if way:
            edge.update(barrier="open", vertical="up", way=way)
            back.update(barrier="open", vertical="down", way=way)
        rooms["r%d" % i]["adjacent"].append(edge)
        rooms["r%d" % (i + 1)]["adjacent"].append(back)
    return {"rooms": rooms, "positions": {"L": "r0", "S": "r%d" % hops},
            "stations": {}, "entities": {}, "poses": {}, "orientation": {},
            "contained": {}}


def _tower(kitchen_door="closed_door"):
    """The probe story's lighthouse at turn idx 5, as its checkpoint holds
    it: small rooms of bare stone on one stair -- the lamp room at the top,
    a landing, the tower's foot -- and off the foot a furnished kitchen and
    a store behind timber doors, the street through an open way, and a
    ladder down to the landing stage. Each room three or four paces square;
    no site plan."""
    def room(name, side, surface, level, adjacent, exposure="enclosed"):
        return {"name": name, "extent": {"w": side, "d": side},
                "exposure": exposure, "surface": surface, "floor": "stone",
                "level": level, "anchors": {}, "adjacent": adjacent}

    def stair(to, vertical, direction):
        return {"to": to, "barrier": "open", "material": "stone",
                "vertical": vertical, "way": "stair", "dir": direction}
    door = {"barrier": kitchen_door, "material": "wood"}
    shut = {"barrier": "closed_door", "material": "wood"}
    rooms = {
        "lamp_room": room("The Lamp Room", 4, "bare", 2,
                          [stair("stair_land", "down", "s")]),
        "stair_land": room("The Stair Landing", 3, "bare", 1,
                           [stair("lamp_room", "up", "n"),
                            stair("tower_foot", "down", "w")]),
        "tower_foot": room("The Tower Foot", 4, "bare", 0,
                           [stair("stair_land", "up", "e"),
                            dict(door, to="kitchen", dir="n"),
                            dict(shut, to="store", dir="w"),
                            {"to": "street", "barrier": "open",
                             "material": "stone", "dir": "sw"},
                            {"to": "landing_stage", "barrier": "open",
                             "material": "metal", "vertical": "down",
                             "way": "ladder", "dir": "s"}]),
        "kitchen": room("The Kitchen", 4, "furnished", 0,
                        [dict(door, to="tower_foot", dir="s")]),
        "store": room("The Store", 3, "bare", 0,
                      [dict(shut, to="tower_foot", dir="e")]),
        "street": room("Harrow Street", 6, "bare", 0, [], exposure="open"),
        "landing_stage": room("The Landing", 9, "bare", -1, [],
                              exposure="open"),
    }
    return {"rooms": rooms,
            "positions": {"Elias": "lamp_room", "Rhona": "kitchen"},
            "stations": {"Elias": {"cell": [2, 2]}, "Rhona": {"cell": [2, 2]}},
            "entities": {}, "poses": {}, "orientation": {}, "contained": {}}


def _heard(sc, listener, speaker):
    rel = spatial_rel_between(sc, listener, speaker)
    return {v: hear_level(rel, v) for v in VOLUMES}, rel


# --- 1. the hearing table carried room by room --------------------------------

def test_rooms_away_a_voice_pays_each_opening_the_tables_coupling():
    """Two open doorways on, the way costs exactly what the hearing table
    charges: the one-pace step, the room's drop, and each doorway its
    transmission and its coupling into the room beyond. Before, the free
    field's spreading over 18 paces stood in for both couplings, and a run
    of rooms cost less a room the further it went."""
    sc = _run(2)
    table = (ONE_PACE_DB + VOICE_ROOM_DROP_DB
             + 2 * (APERTURE_LOSS_DB["open_door"] + ROOM_COUPLING_DB))
    assert far_path(sc, "r0", "r2")["loss_db"] == pytest.approx(table)
    # A SOUND keeps the free field's reach: the coupling is the speech
    # band's, and a boom's low end crosses an opening with a fraction of it.
    deafening = SOUND_DB["deafening"]
    heard = room_sound_flood(sc, "r2", deafening)["r0"]["db"]
    assert heard == pytest.approx(deafening - 2 * APERTURE_LOSS_DB["open_door"]
                                  - spreading_loss_db(18.0))


def test_down_a_run_of_doorways_a_voice_is_whole_two_on_and_its_voice_at_four():
    """The table's arithmetic, a normal voice against a quiet room's floor:
    +3 dB two openings on (followed), -9 at three (pieces), -21 at four
    (no word; its voice is still there), gone at five. It was whole three
    rooms on, in pieces to seven.

    A shout keeps its pieces where it falls under the room's floor: five
    openings on it stands 11 dB under it, and a voiced line is caught to 12
    under. The flood used to stop at the floor itself -- the gate for a
    SOUND -- so the far field could say a shout was whole or nothing."""
    words = {}
    for hops in (2, 3, 4, 5):
        rel = spatial_rel_between(_run(hops), "L", "S")
        words[hops] = (hear_level(rel, "normal"), voice_carries(rel, "normal"),
                       hear_level(rel, "shout"))
    assert words == {2: ("full", True, "full"), 3: ("fragment", True, "full"),
                     4: ("none", True, "full"),
                     5: ("none", False, "fragment")}


# --- 2. a way between storeys --------------------------------------------------

def test_a_stair_is_a_doorway_and_its_flight():
    """A stair, a ladder and a hatch are each an opening -- coupled into the
    room beyond by their area -- and a stair's flight its own loss besides:
    a flight is a passage a doorway wide that climbs a storey, a hatch a
    hole in a floor smaller than a door."""
    level = far_path(_run(2), "r0", "r2")["loss_db"]
    for way in ("stair", "ladder", "hatch"):
        sc = _run(2, ways={1: way})
        couple = far_field_coupling(sc)["r1"]["r2"]
        climbed = far_path(sc, "r0", "r2")["loss_db"]
        # The way's barrier is `open` against the doorway's `open_door`.
        assert climbed == pytest.approx(level - APERTURE_LOSS_DB["open_door"]
                                        + couple - ROOM_COUPLING_DB), way
    stair = far_field_coupling(_run(2, ways={1: "stair"}))["r1"]["r2"]
    assert stair == pytest.approx(ROOM_COUPLING_DB + WAY_LOSS_DB["stair"])
    # A flight in all -- its doorway and its climb -- is the world's 10-15 dB,
    # and more than the doorway alone.
    assert ROOM_COUPLING_DB < stair <= 15.0
    for way in ("ladder", "hatch"):
        hatch = far_field_coupling(_run(2, ways={1: way}))["r1"]["r2"]
        assert hatch == pytest.approx(
            ROOM_COUPLING_DB + 10.0 * math.log10(DOORWAY_AREA_M2 / HATCH_AREA_M2))
    # ONE flight between two rooms is one opening, and a voice through one
    # opening is whole (the owner's ruling): the table answers, not the way.
    one = spatial_rel_between(_run(1, ways={0: "stair"}), "L", "S")
    assert "far_loss_db" not in one
    assert hear_level(one, "normal") == "full"


def test_an_opening_couples_by_its_width_and_never_gives_back_more():
    """An opening that declares its width couples as that many doorways: a
    five-pace opening 7 dB better than a door (the layout tier writes such
    widths -- a kitchen open on its stair foot, chat 177's cottage). And
    however wide it is, a voice never stands louder in a room than in the
    room that feeds it, a ringing room included: the opening is part of
    that room's absorption, so what the room holds is never more than the
    opening's coupling."""
    narrow = far_path(_run(2, size="small"), "r0", "r2")["loss_db"]
    wide = _run(2, size="small")
    for edge in wide["rooms"]["r1"]["adjacent"] + wide["rooms"]["r2"]["adjacent"]:
        if {edge["to"]} <= {"r1", "r2"}:
            edge["width"] = 5
    assert far_path(wide, "r0", "r2")["loss_db"] == pytest.approx(
        narrow - 10.0 * math.log10(5.0))
    ringing = _run(3, size="small", surface="bare")
    for room in ringing["rooms"].values():
        for edge in room["adjacent"]:
            edge["width"] = 2
    for rid in ringing["rooms"]:
        for other, couple in far_field_coupling(ringing)[rid].items():
            assert ring_hold_db(ringing, other) <= couple + 1e-9, (rid, other)
    flood = room_sound_flood(ringing, "r0", SPEECH_DB["shout"], voice=True)
    levels = [flood["r%d" % i]["db"] for i in range(4)]
    assert levels == sorted(levels, reverse=True), levels


# --- 3. one path, one number ---------------------------------------------------

def test_a_path_from_a_ringing_room_is_one_number_both_ways():
    """An airborne path is reciprocal: a voice made in the bare room and
    heard in the furnished one arrives as the same voice made in the
    furnished one arrives in the bare one. The bare room's ring is counted
    at its end of the path, whichever end that is -- as the room the voice
    fills, or the room that holds what arrives."""
    sc = _run(2)
    sc["rooms"]["r2"]["surface"] = "bare"
    sc["rooms"]["r2"]["size"] = "small"
    there = far_path(sc, "r0", "r2")["loss_db"]
    back = far_path(sc, "r2", "r0")["loss_db"]
    assert there == pytest.approx(back)
    plain = far_path(_run(2), "r0", "r2")["loss_db"]
    assert there < plain, "a ringing room should hold a voice up"


def test_a_ringing_room_holds_what_crosses_it():
    """A bare room between two others holds the voice that crosses it, as
    much as one at either end: a run of bare rooms carries further than a
    run of furnished ones, and the abandoned building's long reach is the
    rooms', not the speaker's alone."""
    plain = far_path(_run(3, size="small"), "r0", "r3")["loss_db"]
    bare = far_path(_run(3, size="small", surface="bare"), "r0", "r3")["loss_db"]
    middle = _run(3, size="small")
    middle["rooms"]["r1"]["surface"] = "bare"
    held = far_path(middle, "r0", "r3")["loss_db"]
    assert bare < held < plain
    assert plain - held == pytest.approx(ring_hold_db(middle, "r1"))


def test_a_ringing_room_open_to_a_stairwell_holds_less_than_a_sealed_one():
    """REALISTIC ABSORPTION. Sabine's box is sealed, and a small stone room
    a voice crosses is not: its open stair lets out what reaches it, and in
    four paces of stone an open stairwell is most of what absorbs. The lamp
    room holds less with its stair open than with a hatch shut over it, and
    a room with two ways open less than one with one."""
    sc = _tower()
    open_stair = ring_hold_db(sc, "lamp_room")
    shut = _tower()
    for room in ("lamp_room", "stair_land"):
        for edge in shut["rooms"][room]["adjacent"]:
            if edge["to"] in ("lamp_room", "stair_land"):
                edge["barrier"] = "closed_door"
    assert ring_hold_db(shut, "lamp_room") > open_stair > 0.0
    # The landing, a stair down and a stair up, three paces of stone.
    assert ring_hold_db(sc, "stair_land") < ring_hold_db(shut, "stair_land")


# --- 4. the ring itself --------------------------------------------------------

def test_the_ring_is_bounded_and_measured_from_one_pace():
    """Sabine's gain has no ceiling as a bare room shrinks -- a closet two
    paces square, the smallest room the grid lays, read 13.8 dB over a
    voice at a pace -- where a small bare masonry room stands 8-13 dB over
    it in the world. And the far field
    started a ringing room from the voice's level at its CELL, three
    decibels over the one-pace level the ring is stated against: the
    near field's echo had the same defect, mended 2026-09-23."""
    cell = {"rooms": {"cell": {"name": "cell", "extent": {"w": 1, "d": 1},
                               "surface": "bare", "anchors": {},
                               "adjacent": []}}}
    assert room_reverberation(cell, "cell")["gain_db"] <= RING_GAIN_MAX_DB
    sc = _tower()
    ring = room_reverberation(sc, "lamp_room")
    level = SOUND_DB["deafening"]
    own = room_sound_flood(sc, "lamp_room", level)["lamp_room"]["db"]
    assert own == pytest.approx(level - ONE_PACE_DB + ring["gain_db"],
                                abs=0.05)
    # What a ringing room holds over the room the coupling is written for
    # is never more than that coupling, nor less than nothing.
    for room in sc["rooms"]:
        assert 0.0 <= ring_hold_db(sc, room) <= ROOM_COUPLING_DB
    assert ring_hold_db(sc, "kitchen") == 0.0


# --- 5. the tower --------------------------------------------------------------

def test_two_storeys_and_a_shut_door_keep_an_ordinary_voice():
    """THE PROBE STORY. The keeper's ordinary voice in the lamp room does not
    reach the kitchen two flights down behind its shut door; a shout reaches
    it in pieces at most; and the path is one number, whichever of the two
    speaks.

    The complement, in the same tower: its own rooms ring, and two flights
    of open stair with no door on them still carry his ordinary voice to
    the tower's foot whole -- as a call down a stone stairwell carries."""
    sc = _tower()
    down, rel = _heard(sc, "Rhona", "Elias")
    assert down["normal"] == "none", rel.get("far_loss_db")
    assert down["shout"] in ("none", "fragment"), rel.get("far_loss_db")
    up, back = _heard(sc, "Elias", "Rhona")
    assert back["far_loss_db"] == pytest.approx(rel["far_loss_db"])
    assert up == down
    sc["positions"]["Rhona"] = "tower_foot"
    inside, rel = _heard(sc, "Rhona", "Elias")
    assert rel.get("far_loss_db") is not None
    assert inside["normal"] == "full"
