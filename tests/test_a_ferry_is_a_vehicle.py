"""A thing that carries bodies between places is a vehicle, never a room
between them.

Saltmarsh Crossing (2026-10-11, scratch chat 170): the opening laid the chain
ferry as a room joined to both slips, so it never docked -- its edge to the
north slip stayed `closed_door` after it arrived, and a hand at the rail
reached the player "in fragments". The opening card now says so; a rerun of
that opening minted `chain_ferry_entity` (kind vehicle, interior_rooms
["chain_ferry"]) and left the deck itself unclaimed, and the dock rewrite
reads the ROOM's claim. `sync_entity_interior_rooms` now fills it in for the
engine's own moving kinds (`MOVING_KINDS`), never for a building.
"""
from __future__ import annotations

from world.spatial import merge_scene_with_diff
from world.spatial_transit import MOVING_KINDS, sync_entity_interior_rooms


def _diff(kind="vehicle", claimed_by=None):
    deck = {"name": "Ferry deck", "adjacent": []}
    if claimed_by:
        deck["parent_entity"] = claimed_by
    return {
        "rooms": {"south_slip": {"name": "South slip", "adjacent": []},
                  "north_slip": {"name": "North slip", "adjacent": []},
                  "chain_ferry": deck},
        "entities": {"ferry": {"name": "chain ferry", "kind": kind,
                               "interior_rooms": ["chain_ferry"]}},
        "positions": {"ferry": "south_slip", "Bethan Marsh": "chain_ferry"},
    }


def test_a_ferry_owns_the_deck_it_lists_and_docks_where_it_stands():
    scene = merge_scene_with_diff({}, _diff())
    deck = scene["rooms"]["chain_ferry"]
    assert deck["parent_entity"] == "ferry"
    assert [e["to"] for e in deck["adjacent"]] == ["south_slip"]


def test_a_building_listing_its_rooms_is_left_as_it_was():
    scene = _diff(kind="building")
    sync_entity_interior_rooms(scene)
    assert "parent_entity" not in scene["rooms"]["chain_ferry"]


def test_a_room_another_holder_claims_is_never_taken():
    scene = _diff(claimed_by="pontoon")
    sync_entity_interior_rooms(scene)
    assert scene["rooms"]["chain_ferry"]["parent_entity"] == "pontoon"


def test_the_moving_kinds_are_the_engines_own_words():
    assert MOVING_KINDS == {"vehicle", "ship", "boat"}
