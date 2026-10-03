"""Two doors in one wall are two places along it (2026-10-03).

The owner: "whenever I try to place multiple doors on one cardinal direction
such as east they both disappear". `normalize_scene_bearings` read two
horizontal doorways with one bearing as a contradiction and stripped the
bearing from both, so neither had a wall to stand in.
"""

import copy

from world.spatial import normalize_scene_bearings, sound_field


def _scene(offsets=(None, None)):
    hall = {"name": "Hall", "extent": {"w": 12, "d": 8}, "anchors": {}, "adjacent": []}
    for to, off in zip(("study", "pantry"), offsets):
        edge = {"to": to, "barrier": "open_door", "dir": "e"}
        if off is not None:
            edge["offset"] = off
        hall["adjacent"].append(edge)
    return {"rooms": {"hall": hall,
                      "study": {"name": "Study", "extent": {"w": 3, "d": 3}, "anchors": {}, "adjacent": []},
                      "pantry": {"name": "Pantry", "extent": {"w": 3, "d": 3}, "anchors": {}, "adjacent": []}},
            "positions": {"A": "hall"}, "stations": {"A": {"cell": [6, 4]}}, "entities": {}}


def test_both_doors_keep_their_wall_and_get_places_of_their_own():
    sc = normalize_scene_bearings(_scene())
    edges = sc["rooms"]["hall"]["adjacent"]
    assert [e.get("dir") for e in edges] == ["e", "e"]
    offsets = [e.get("offset") for e in edges]
    assert None not in offsets and offsets[0] != offsets[1]


def test_a_place_already_given_is_kept_and_a_shared_one_is_moved():
    sc = normalize_scene_bearings(_scene((0.2, 0.2)))
    offsets = [e.get("offset") for e in sc["rooms"]["hall"]["adjacent"]]
    assert offsets[0] == 0.2 and offsets[1] not in (None, 0.2)
    kept = normalize_scene_bearings(_scene((0.2, 0.8)))
    assert [e.get("offset") for e in kept["rooms"]["hall"]["adjacent"]] == [0.2, 0.8]


def test_both_rooms_beyond_the_wall_are_laid_out():
    sc = normalize_scene_bearings(_scene())
    field = sound_field(sc, "A", room="hall")
    assert field is not None and {"study", "pantry"} <= set(field.grid.offsets)


def test_two_stairs_up_one_wall_are_still_the_ambiguity():
    sc = _scene()
    for edge in sc["rooms"]["hall"]["adjacent"]:
        edge["vertical"] = "up"
        edge["way"] = "stair"
    sc = normalize_scene_bearings(copy.deepcopy(sc))
    assert [e.get("dir") for e in sc["rooms"]["hall"]["adjacent"]] == [None, None]
