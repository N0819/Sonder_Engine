"""Review 2026-09-07 A9/A22/A45/A48: the first hop searched the directed
graph backwards, a severance dropped one end of a two-ended doorway, the
watching side of a one-way window heard nothing, and a creature with no
wardrobe was a crate.
"""
import world.spatial as spatial
from world.spatial import _body_interior_holder, merge_scene_with_diff


def _chute():
    return {"rooms": {
        "top": {"adjacent": [{"to": "bottom", "barrier": "open", "passage_from": "top"}]},
        "bottom": {"adjacent": [{"to": "top", "barrier": "open", "passage_from": "top"}]},
    }, "positions": {}}


def test_a_chute_is_walked_from_its_top_only():
    assert spatial.passable_route_next_step(_chute(), "top", "bottom") == "bottom"
    assert spatial.passable_route_next_step(_chute(), "bottom", "top") is None


def test_severing_a_doorway_drops_both_ends_and_its_passage():
    scene = {"rooms": {
        "a": {"adjacent": [{"to": "b", "barrier": "open_door", "passage": "p1"}]},
        "b": {"adjacent": [{"to": "a", "barrier": "open_door", "passage": "p1"}]},
    }, "passages": {"p1": {"rooms": ["a", "b"], "barrier": "open_door"}},
        "positions": {}, "entities": {}}
    merged = merge_scene_with_diff(scene, {"remove_adjacent": [{"room": "a", "to": "b"}]})
    assert merged["rooms"]["a"]["adjacent"] == []
    assert merged["rooms"]["b"]["adjacent"] == []
    assert "p1" not in (merged.get("passages") or {})


def test_the_watching_side_of_a_one_way_window_hears_glass():
    rel = {"same_room": False, "barrier": "one_way_window", "distance": "near"}
    assert spatial.hear_level(rel, "shout") == "fragment"
    assert spatial.hear_level(rel, "normal") == "none"


def test_an_interior_record_over_a_bare_creature_is_a_mass_and_a_car_is_not():
    scene = {"rooms": {"hall": {"adjacent": []}},
             "positions": {"beast": "hall", "Aurel": "hall"},
             "entities": {"beast": {"name": "beast", "kind": "creature"},
                          "lift": {"name": "lift", "kind": "vehicle"}},
             "contained": {"Aurel": {"in": "beast", "mode": "interior"}}}
    assert _body_interior_holder(scene, "Aurel") == "beast"
    scene["contained"]["Aurel"] = {"in": "lift", "mode": "interior"}
    scene["positions"]["lift"] = "hall"
    assert _body_interior_holder(scene, "Aurel") is None
