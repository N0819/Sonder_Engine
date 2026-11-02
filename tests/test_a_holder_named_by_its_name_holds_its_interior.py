"""A room's `parent_entity` names its holder by the entity's KEY, whatever
spelling the writer reached for.

Audit world_spatial_truth F1 (2026-11-01, CONFIRMED LEAK): the room author /
encoder wrote `parent_entity: "Mirelle"` (the display name) for an entity keyed
`mirelle_01`. The structural readers compare the KEY exactly
(`_interior_rooms_of`, `apply_transit_dock_edges`, the frame zone stamp), so the
interior index stayed empty, `infer_body_enclosures` never defaulted the way in
to `membrane`, the dock rewrite never replaced the authored `open` edge, and a
body inside a body was visible from the room outside it: `visual_level_between`
answered `conduct` where the id spelling answers `none`.

The class is the `inside`/`interior` one: canonicalise at ingest, against the
holder. Names, aliases and case are folded onto the unique entity key; an
ambiguous or unknown spelling is left as written.
"""

from world.spatial import (containment_conceals, merge_scene_with_diff,
                           visual_level_between)

HOLDER_ID = "mirelle_01"


def _scene(parent):
    return {
        "rooms": {
            "hall": {"name": "Hall", "desc": "A hall.", "adjacent": []},
            "stomach": {"name": "Mirelle's Stomach", "desc": "Close and dark.",
                        "parent_entity": parent,
                        "adjacent": [{"to": "hall", "barrier": "open"}]},
        },
        "positions": {"Mirelle": "hall", "Bo": "hall", "Hinami": "stomach"},
        "entities": {HOLDER_ID: {"name": "Mirelle", "kind": "person",
                                 "aliases": ["the dragon"]}},
        "attire": {"Mirelle": {}, "Bo": {}, "Hinami": {}},
        "contained": {}, "contacts": [],
    }


def _edge_to_hall(scene):
    return [e for e in scene["rooms"]["stomach"]["adjacent"]
            if e.get("to") == "hall"]


def test_the_display_name_is_folded_onto_the_entity_key():
    merged = merge_scene_with_diff(_scene("Mirelle"), {})
    assert merged["rooms"]["stomach"]["parent_entity"] == HOLDER_ID


def test_an_alias_and_a_case_variant_fold_too():
    for spelling in ("the dragon", "MIRELLE_01", "mirelle"):
        merged = merge_scene_with_diff(_scene(spelling), {})
        assert merged["rooms"]["stomach"]["parent_entity"] == HOLDER_ID, spelling


def test_the_body_interior_is_shut_and_the_occupant_is_not_seen_from_outside():
    merged = merge_scene_with_diff(_scene("Mirelle"), {})
    edges = _edge_to_hall(merged)
    assert edges and edges[0]["barrier"] == "membrane"
    assert containment_conceals(merged, "Bo", "Hinami") is True
    assert visual_level_between(merged, "Bo", "Hinami") == "none"


def test_the_name_spelling_now_answers_exactly_as_the_key_spelling():
    by_name = merge_scene_with_diff(_scene("Mirelle"), {})
    by_key = merge_scene_with_diff(_scene(HOLDER_ID), {})
    assert by_name["rooms"] == by_key["rooms"]
    assert visual_level_between(by_name, "Bo", "Hinami") \
        == visual_level_between(by_key, "Bo", "Hinami")


def test_an_unknown_or_ambiguous_holder_is_left_as_written():
    sc = _scene("Nobody In Particular")
    merged = merge_scene_with_diff(sc, {})
    assert merged["rooms"]["stomach"]["parent_entity"] == "Nobody In Particular"
    sc = _scene("the twin")
    sc["entities"]["twin_a"] = {"name": "Ana", "kind": "person", "aliases": ["the twin"]}
    sc["entities"]["twin_b"] = {"name": "Bea", "kind": "person", "aliases": ["the twin"]}
    merged = merge_scene_with_diff(sc, {})
    assert merged["rooms"]["stomach"]["parent_entity"] == "the twin"


def test_a_new_room_minted_with_the_holders_name_is_folded_at_ingest():
    sc = _scene(HOLDER_ID)
    sc["rooms"].pop("stomach")
    sc["positions"]["Hinami"] = "hall"
    merged = merge_scene_with_diff(sc, {"rooms": {"maw": {
        "name": "Maw", "parent_entity": "Mirelle",
        "adjacent": [{"to": "hall", "barrier": "open"}]}}})
    assert merged["rooms"]["maw"]["parent_entity"] == HOLDER_ID
    assert "maw" in (merged["entities"][HOLDER_ID].get("interior_rooms") or [])
