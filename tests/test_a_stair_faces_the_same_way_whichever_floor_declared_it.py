"""A stair's bearing is the wall its own end sits on, per floor -- so a stair
declared from one floor only reads the same as one declared from both.

Audit world_spatial_movement_sight F11 (2026-11-01, CONFIRMED WRONG-SCENE):
`normalize_scene_bearings` rules "A STAIR IS ONE SHAFT ... a floor that names
none takes the other's ... never its opposite", but reconciles only pairs
declared from BOTH sides. For a stair declared upstairs only (`{to: hall, dir:
n, vertical: down}`), `travel_bearing(hall, up)` reversed it to `s` (declared
from both sides, `n`), and `effective_adjacent(hall)` derived the stair foot on
the `s` wall -- after a climb `infer_facing` faced the body the opposite way
and every left/right in the next view was mirrored, by an accident of which
side wrote the edge.
"""

from world.spatial import effective_adjacent, merge_scene_with_diff, travel_bearing


def _one_sided():
    return {"rooms": {
        "hall": {"name": "Hall", "adjacent": []},
        "up": {"name": "Landing", "adjacent": [
            {"to": "hall", "dir": "n", "vertical": "down", "barrier": "open"}]},
    }}


def _two_sided():
    sc = _one_sided()
    sc["rooms"]["hall"]["adjacent"].append(
        {"to": "up", "dir": "n", "vertical": "up", "barrier": "open"})
    return sc


def test_one_and_two_sided_declarations_give_one_travel_bearing():
    for sc in (_one_sided(), _two_sided()):
        assert travel_bearing(sc, "hall", "up") == "n"
        assert travel_bearing(sc, "up", "hall") == "n"


def test_the_derived_stair_foot_sits_on_the_shaft_s_own_wall():
    derived = [e for e in effective_adjacent(_one_sided(), "hall") if e["to"] == "up"]
    assert derived and derived[0]["dir"] == "n"
    assert derived[0].get("vertical") == "up"


def test_a_doorway_declared_from_one_side_still_reverses():
    sc = {"rooms": {"a": {"name": "A", "adjacent": []},
                    "b": {"name": "B", "adjacent": [
                        {"to": "a", "dir": "w", "barrier": "open_door"}]}}}
    assert travel_bearing(sc, "a", "b") == "e"
    assert [e["dir"] for e in effective_adjacent(sc, "a") if e["to"] == "b"] == ["e"]
