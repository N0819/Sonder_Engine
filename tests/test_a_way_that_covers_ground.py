"""A way that covers ground is not a doorway: the sound readers charge it
the ground it covers, and none of them lays the far room beside the near.

The control story (2026-10-20, chat 1 idx 3-5): the room designer joined a
mainland street to a lighthouse's ground floor as `{open, far}`, meaning --
in its own words -- "connected without pretending it is beside the tower".
Every reader of sound read it as next door. The far field charged the way
nothing but the street's own 6-pace span, so a normal voice from the lamp
room reached the street at 54.7 dB over a 17-pace path; the near field laid
the street out through that opening on the tower foot's grid, so the boat's
engine standing in the street was heard there "all through the room, low
enough to talk over"; and the edge model took the pair as neighbours, whose
voices cross an opening whole. The tiers are `normalize_edge_distance`'s;
what each charges is `spatial_sound_field.way_paces`'s comment and
DESIGN_SOUND_FIELD § 19: the word `far` costs a sound what the charter
already charges a body to walk it (`charter_move.WALK_EDGE_PACES`).

The rooms here are left ordinarily furnished, so no room rings: what a bare
room hands its openings is the coupling lane's, and these tests read the
way alone.
"""

from __future__ import annotations

import copy

from world.charter_move import WALK_EDGE_PACES
from world.spatial import (AMBIENT_DB, SPEECH_DB, acoustic_grid,
                           far_field_way_paces, far_path, far_speech_level,
                           room_sound_flood, room_span, sound_passes)


def _rock(distance="far"):
    """The control story's tower, cut to the path a voice takes: the lamp
    room, down the stair landing to the tower's foot, and the street the
    designer joined to the foot -- as written, `far`, unless `distance`
    says otherwise."""
    street_edge = {"to": "tower_foot", "dir": "sw", "barrier": "open",
                   "name": "the quay road"}
    if distance is not None:
        street_edge["distance"] = distance
    return {
        "rooms": {
            "lamp_room": {"name": "The Lamp Room", "size": "small", "exposure": "enclosed",
                          "adjacent": [{"to": "stair_land", "barrier": "open",
                                        "vertical": "down"}]},
            "stair_land": {"name": "The Stair Landing", "size": "tiny",
                           "exposure": "enclosed",
                           "adjacent": [{"to": "tower_foot", "barrier": "open",
                                         "vertical": "down"}]},
            "tower_foot": {"name": "The Tower Foot", "size": "small",
                           "exposure": "enclosed",
                           "adjacent": [{"to": "landing", "dir": "n", "barrier": "open"}]},
            "landing": {"name": "The Landing", "size": "medium", "exposure": "open",
                        "adjacent": []},
            "harrow_street": {"name": "Harrow Street", "size": "medium",
                              "exposure": "open", "adjacent": [street_edge]},
        },
        "positions": {"Elias Thorne": "lamp_room", "Rhona Carrick": "tower_foot"},
        "entities": {},
    }


def _spans(scene, *rooms):
    return sum(room_span(scene, r) for r in rooms)


def test_a_far_way_costs_a_voice_a_streets_length():
    """Across the far way the flood charges a street's length on top of the
    rooms' spans, and the far field -- not the edge model -- answers for the
    pair it joins. A normal voice in the lamp room is no longer heard in the
    street; a shout at the tower's foot still is, because a call carries
    across a street (the owner). The same tower with the way written `near`,
    or with no distance at all, is charged its spans and nothing else, as it
    always was: a doorway covers no ground the rooms do not."""
    rock = _rock()
    path = ("lamp_room", "stair_land", "tower_foot", "harrow_street")
    voice = far_path(rock, "harrow_street", "lamp_room")
    assert voice["length"] == _spans(rock, *path) + WALK_EDGE_PACES["far"]
    assert far_speech_level("normal", voice["loss_db"], AMBIENT_DB["open"]) == "none"
    assert "harrow_street" not in room_sound_flood(rock, "lamp_room", SPEECH_DB["normal"])
    call = far_path(rock, "harrow_street", "tower_foot")
    assert call is not None, "a way across ground is not next door"
    assert far_speech_level("shout", call["loss_db"], AMBIENT_DB["open"]) != "none"
    for distance in ("near", "adjacent", "12 m", None):
        doorway = _rock(distance)
        assert far_field_way_paces(doorway) == {}
        rec = room_sound_flood(doorway, "lamp_room", SPEECH_DB["normal"])["harrow_street"]
        assert rec["length"] == _spans(doorway, *path)
        assert far_path(doorway, "harrow_street", "tower_foot") is None


def test_a_measured_far_way_is_charged_its_measurement():
    """A way written as a measurement keeps its number (DESIGN_METRIC_SPACE:
    "keep the number"): forty metres is forty metres of path, not the band's
    seventy-five, and the shorter of two sides' authored distances wins, as
    the smaller loss does on the graph. A side that says nothing is no
    claim against the other."""
    rock = _rock("40 m")
    assert far_field_way_paces(rock)["tower_foot"]["harrow_street"] == 40 / 0.75
    both = copy.deepcopy(rock)
    both["rooms"]["tower_foot"]["adjacent"].append(
        {"to": "harrow_street", "barrier": "open", "distance": "30m"})
    assert far_field_way_paces(both)["harrow_street"]["tower_foot"] == 30 / 0.75
    silent = copy.deepcopy(rock)
    silent["rooms"]["tower_foot"]["adjacent"].append(
        {"to": "harrow_street", "barrier": "open"})
    assert far_field_way_paces(silent)["harrow_street"]["tower_foot"] == 40 / 0.75


def test_a_far_room_is_not_laid_beside_the_listener():
    """The near field places a neighbour on the listener's grid through any
    opening, as the room just beyond the wall. A far way is not that wall:
    the street stays off the tower foot's grid, so nothing standing in it is
    heard through the quay road as if from the next room -- on the control
    story's checkpoint 5 the boat's engine was, "all through the room". The
    doorway onto the landing is placed as it was."""
    rock = _rock()
    street_edge = rock["rooms"]["harrow_street"]["adjacent"][0]
    assert sound_passes(rock, "harrow_street", street_edge) is None
    assert sound_passes(rock, "tower_foot", rock["rooms"]["tower_foot"]["adjacent"][0])
    placed = set(acoustic_grid(rock, "tower_foot").offsets)
    assert "harrow_street" not in placed
    assert "landing" in placed


def test_a_remote_way_carries_no_air():
    """`remote` is no air (the near field's dead drop): no flood crosses it
    and no voice arrives, whatever its barrier, and the far field says the
    rooms are joined and nothing reaches -- an answer, not a silence."""
    rock = _rock("remote")
    assert "harrow_street" not in room_sound_flood(rock, "tower_foot", SPEECH_DB["shout"])
    assert far_path(rock, "harrow_street", "tower_foot")["loss_db"] == float("inf")
    assert "harrow_street" not in set(acoustic_grid(rock, "tower_foot").offsets)
