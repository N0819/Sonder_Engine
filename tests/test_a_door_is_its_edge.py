"""A door is its edge: what it is made of and what it is like are the
edge's, and nothing is minted on top of it.

Chat 168 (2026-10-12): the layout tier minted a "shoji door" anchor on the
cell of every doorway, the only description of each door lived on that copy,
and the copy a body stood at stayed shut when the door was opened. A door's
`desc` now lives on its edge: the implicit door anchor every edge already
derives (`door:<to>`) takes it, the mirror carries it to the other side, and
perception lists a described door with its bearing.
"""
from __future__ import annotations

from world.spatial import door_anchor_id, effective_anchors, merge_scene_with_diff

DESC = "a shoji door of cedar and paper, its frame dark with handling"


def _house(desc=None):
    edge = {"to": "bedroom", "barrier": "closed_door", "name": "a shoji door", "dir": "e"}
    if desc:
        edge["desc"] = desc
    return {"rooms": {
        "hall": {"name": "Hall", "adjacent": [edge]},
        "bedroom": {"name": "Bedroom", "adjacent": [{"to": "hall", "barrier": "closed_door",
                                                     "name": "a shoji door", "dir": "w"}]}},
        "positions": {}}


def test_the_doors_own_words_are_its_anchors():
    door = effective_anchors(_house(DESC), "hall")[door_anchor_id("bedroom")]
    assert door["desc"] == DESC and door.get("described") is True and door["implicit"]
    plain = effective_anchors(_house(), "hall")[door_anchor_id("bedroom")]
    assert plain["desc"] == "the shut door" and "described" not in plain


def test_what_a_door_is_like_is_the_doorways_from_either_side():
    scene = merge_scene_with_diff(_house(), {"rooms": {"hall": {"adjacent": [
        {"to": "bedroom", "barrier": "closed_door", "desc": DESC}]}}})
    far = next(e for e in scene["rooms"]["bedroom"]["adjacent"] if e["to"] == "hall")
    assert far.get("desc") == DESC
    assert effective_anchors(scene, "bedroom")[door_anchor_id("hall")]["desc"] == DESC
