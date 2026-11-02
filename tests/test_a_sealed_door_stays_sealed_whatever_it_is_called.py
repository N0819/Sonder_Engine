"""A doorway the story SEALS -- welded, bricked up, boarded, sealed -- stays a
wall across merges, whatever its edge is named.

Audit world_spatial_structure_light F4 (2026-11-01, CONFIRMED WRONG-SCENE): the
name floor (`_barrier_against_its_own_name`: "an edge named as an opening
cannot be a wall", chat 74's lift) ran after `normalize_barrier` had folded
`welded_door` to `wall`, and so stored `closed_door` for `welded_door` named
"blast doors", `bricked_up` named "the old cellar door", `sealed` named
"airlock hatch" and `boarded_door` named "back door" -- any hand opened it next
beat. That contradicts `_BARRIER_SEAL_QUALIFIERS`' own rule: "a qualifier must
not quietly promote one back to a door it can be opened through".
"""

import pytest

from world.spatial import merge_scene_with_diff, normalize_scene_barriers


def _scene(barrier, name):
    return {"rooms": {
        "hall": {"name": "Hall", "adjacent": [{"to": "vault", "barrier": barrier,
                                               "name": name}]},
        "vault": {"name": "Vault", "adjacent": [{"to": "hall", "barrier": barrier,
                                                "name": name}]},
    }, "positions": {"Ada": "hall"}, "entities": {}}


def _barriers(scene):
    return {rid: [e["barrier"] for e in room["adjacent"]]
            for rid, room in scene["rooms"].items()}


@pytest.mark.parametrize("barrier, name", [
    ("welded_door", "blast doors"), ("bricked_up", "the old cellar door"),
    ("sealed", "airlock hatch"), ("boarded_door", "back door"),
])
def test_a_sealed_named_door_is_a_wall_across_two_merges(barrier, name):
    once = merge_scene_with_diff(_scene(barrier, name), {})
    assert _barriers(once) == {"hall": ["wall"], "vault": ["wall"]}
    twice = merge_scene_with_diff(once, {})
    assert _barriers(twice) == {"hall": ["wall"], "vault": ["wall"]}


def test_a_bare_wall_named_as_a_door_is_still_a_shut_door():
    """Chat 74's case, unchanged: an edge NAMED as an opening and written
    plain `wall` is a door nobody has opened."""
    sc = normalize_scene_barriers(_scene("wall", "lobby doors"))
    assert _barriers(sc) == {"hall": ["closed_door"], "vault": ["closed_door"]}


def test_unsealing_it_opens_it():
    once = merge_scene_with_diff(_scene("welded_door", "blast doors"), {})
    cut = merge_scene_with_diff(once, {"rooms": {
        "hall": {"adjacent": [{"to": "vault", "barrier": "open_door"}]},
        "vault": {"adjacent": [{"to": "hall", "barrier": "open_door"}]}}})
    assert _barriers(cut) == {"hall": ["open_door"], "vault": ["open_door"]}
    shut = merge_scene_with_diff(cut, {"rooms": {
        "hall": {"adjacent": [{"to": "vault", "barrier": "wall"}]},
        "vault": {"adjacent": [{"to": "hall", "barrier": "wall"}]}}})
    # Written plain `wall` again, a named door is a door nobody has opened.
    assert _barriers(shut) == {"hall": ["closed_door"], "vault": ["closed_door"]}
