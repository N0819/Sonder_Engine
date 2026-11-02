"""A caller that hands the merge copies it owns may say so, and the merge then
skips its own two deep copies -- answering exactly as the copying merge does.

Audit world_spatial_truth E1 (2026-11-01): `copy.deepcopy` was 29% of an empty
merge on chat 172's scene (0.132 s of 0.460 s over 10 merges), and a caller
that already deep-copies its arguments (`director_movement`'s route preview,
`merge_scene_with_diff(copy.deepcopy(sc), copy.deepcopy(sd))`) paid four copies
for one merge.
"""

import copy

from world.spatial import merge_scene_with_diff


def _scene():
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": [{"to": "yard", "barrier": "open_door"}]},
                  "yard": {"name": "Yard", "adjacent": [{"to": "hall", "barrier": "open_door"}]}},
        "positions": {"Ada": "hall", "coin": "hall"},
        "entities": {"coin": {"name": "coin", "kind": "object", "portable": True}},
        "attire": {"Ada": {}}, "contained": {"coin": {"in": "Ada", "mode": "held"}},
        "contacts": [],
    }


def _diff():
    return {"positions": {"Ada": "yard"}, "poses": {"Ada": {"posture": "standing"}}}


def test_owned_and_copied_merges_answer_the_same():
    copied = merge_scene_with_diff(_scene(), _diff())
    owned = merge_scene_with_diff(_scene(), _diff(), _owned=True)
    assert owned == copied
    assert owned["positions"]["coin"] == "yard"


def test_the_default_still_leaves_the_callers_arguments_untouched():
    scene, diff = _scene(), _diff()
    before = (copy.deepcopy(scene), copy.deepcopy(diff))
    merge_scene_with_diff(scene, diff)
    assert (scene, diff) == before


def test_owned_skips_the_copy():
    scene = _scene()
    merged = merge_scene_with_diff(scene, _diff(), _owned=True)
    assert merged is scene
