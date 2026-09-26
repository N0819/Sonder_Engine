"""A body that walks into a room TO someone ends beside them, not at the door.

The owner's rule (2026-09-15) is that an arrival's place is its door, and a
declared walk already ends at the fixture the spatial hand named instead
(`walk_declared`, Skerry Light turn 1). A BODY named is the same kind of
destination, and `walk_within_room` already treats it so inside one room.
Only the arrival ignored it. Measured on the opera test story (2026-09-26):
"sets the proof on the music rest in front of her" crossed onto the stage
with the hand's station `near: [Isolde]`, the walk ended one pace inside the
door 4.5 paces off, and the stage's ring smeared every word she said to him
for three beats while the narrator sat them on one bench."""
from __future__ import annotations

from types import SimpleNamespace

from world.spatial import inside_the_door, merge_scene_with_diff

ISOLDE = (5, 2)


def _theatre():
    return {
        "rooms": {
            "practice": {"extent": {"w": 6, "d": 5}, "anchors": {}, "exposure": "enclosed",
                         "adjacent": [{"to": "stage", "barrier": "open_door", "dir": "n"}]},
            "stage": {"extent": {"w": 10, "d": 8}, "anchors": {}, "exposure": "enclosed",
                      "adjacent": [{"to": "practice", "barrier": "open_door", "dir": "s"}]},
        },
        "entities": {},
        "positions": {"Tomas": "practice", "Isolde": "stage"},
        "stations": {"Tomas": {"at": None, "near": [], "cell": [3, 1]},
                     "Isolde": {"at": None, "near": [], "cell": list(ISOLDE)}},
    }


def _beside(cell, other=ISOLDE):
    return max(abs(int(cell[0]) - other[0]), abs(int(cell[1]) - other[1])) == 1


def test_a_walk_to_someone_ends_beside_them():
    from agents.director import walk_declared

    scene = _theatre()
    diff = {"positions": {"Tomas": "stage"},
            "stations": {"Tomas": {"at": None, "near": ["Isolde"]}}}
    route_scene = merge_scene_with_diff(scene, diff)
    warnings = []
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=warnings.append)
    result = walk_declared(ctx, scene, route_scene, diff, {}, "Tomas",
                           {"to_room": "stage", "arrives": True}, "practice")
    assert result["arrived"], result
    assert _beside(diff["stations"]["Tomas"]["cell"]), diff["stations"]["Tomas"]


def test_an_arrival_seated_by_the_merge_stands_beside_who_it_came_to():
    merged = merge_scene_with_diff(_theatre(), {"positions": {"Tomas": "stage"},
                                                "stations": {"Tomas": {"near": ["Isolde"]}}})
    assert _beside(merged["stations"]["Tomas"]["cell"]), merged["stations"]["Tomas"]


def test_an_arrival_that_names_nobody_there_still_stands_inside_the_door():
    # Near a body in ANOTHER room is no place in this one: the door stands.
    scene = _theatre()
    scene["positions"]["Celestine"] = "practice"
    scene["stations"]["Celestine"] = {"at": None, "near": [], "cell": [1, 1]}
    for stations in ({}, {"Tomas": {"near": ["Celestine"]}}):
        merged = merge_scene_with_diff(scene, {"positions": {"Tomas": "stage"},
                                               "stations": stations})
        assert merged["stations"]["Tomas"]["cell"] == list(
            inside_the_door(merged, "stage", "practice")), stations
