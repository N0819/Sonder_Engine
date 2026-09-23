"""What a doorway IS is the doorway's, not one side's.

Playerless Aldermill round 7 (2026-09-23), idx 7-22: the room author renamed
the mill's edge "oak trapdoor hatch" from the milling floor and wrote nothing
of it on the wheelhouse side, so from there it stayed "the open doorway", and
a pose stood Emory "on the open doorway's rung". The barrier was already
mirrored across a doorway; its name was not.
"""
import copy

from world.spatial import merge_scene_with_diff

SCENE = {
    "rooms": {
        "mill_floor": {"name": "Grist Milling Floor",
                       "adjacent": [{"to": "wheelhouse", "barrier": "open"}]},
        "wheelhouse": {"name": "Wheelhouse",
                       "adjacent": [{"to": "mill_floor", "barrier": "open"}]},
    },
    "positions": {"Emory Vane": "wheelhouse"},
    "entities": {},
}


def _edge(scene, room, to):
    return next(e for e in scene["rooms"][room]["adjacent"] if e["to"] == to)


def _merged(rooms):
    return merge_scene_with_diff(copy.deepcopy(SCENE), {"rooms": rooms})


def test_a_name_written_on_one_side_is_the_doorways():
    out = _merged({"mill_floor": {"adjacent": [
        {"to": "wheelhouse", "name": "oak trapdoor hatch"}]}})
    assert _edge(out, "wheelhouse", "mill_floor")["name"] == "oak trapdoor hatch"
    assert _edge(out, "mill_floor", "wheelhouse")["name"] == "oak trapdoor hatch"


def test_the_other_side_keeps_what_the_diff_wrote_there():
    out = _merged({
        "mill_floor": {"adjacent": [{"to": "wheelhouse", "name": "oak trapdoor hatch"}]},
        "wheelhouse": {"adjacent": [{"to": "mill_floor",
                                     "name": "the hatch in the floor"}]}})
    assert _edge(out, "wheelhouse", "mill_floor")["name"] == "the hatch in the floor"


def test_a_one_way_window_keeps_its_two_sides():
    scene = copy.deepcopy(SCENE)
    for room, to in (("mill_floor", "wheelhouse"), ("wheelhouse", "mill_floor")):
        _edge(scene, room, to)["barrier"] = "one_way_window"
    out = merge_scene_with_diff(scene, {"rooms": {"mill_floor": {"adjacent": [
        {"to": "wheelhouse", "name": "the mirror"}]}}})
    assert "name" not in _edge(out, "wheelhouse", "mill_floor")
