"""A body or thing CONTAINED in a vessel goes where the vessel goes -- into no
room, when the vessel goes into none.

Audit world_spatial_movement_sight F6 (2026-11-01, CONFIRMED WRONG-SCENE): two
representations of one fact, `contained[Ada] = {in: skiff}` and
`positions[Ada]`. A skiff on the quay with Ada contained in it, written
`in_transit` toward the harbour with no route, stood in no room (the 2026-09-25
rule) while Ada stayed `positions: quay` with her containment intact, in view
of everyone on the quay: `derive_contained_positions` skipped a holder with no
room and left the contents wherever they were last derived. UNBUILT_WORLD
1.194's class one level down, for the vessel's CONTENTS.
"""

from world.spatial import merge_scene_with_diff


def _quay():
    return {
        "rooms": {"quay": {"name": "Quay", "adjacent": []},
                  "harbour": {"name": "Harbour", "adjacent": []}},
        "positions": {"skiff": "quay", "Ada": "quay", "Bo": "quay"},
        "entities": {"skiff": {"name": "skiff", "kind": "boat",
                               "state": {"transit": {"phase": "docked"}}}},
        "attire": {"Ada": {}, "Bo": {}},
        "contained": {"Ada": {"in": "skiff", "mode": "riding"}},
        "contacts": [],
    }


def _leave():
    return {"entities": {"skiff": {"state": {"transit": {
        "phase": "in_transit", "destination_room": "harbour"}}}}}


def test_the_rider_leaves_the_quay_with_the_skiff():
    moved = merge_scene_with_diff(_quay(), _leave())
    assert "skiff" not in moved["positions"]
    assert moved["positions"].get("Ada") != "quay"
    assert moved["contained"]["Ada"]["in"] == "skiff"      # still aboard
    assert moved["positions"]["Bo"] == "quay"


def test_the_rider_arrives_with_it():
    moved = merge_scene_with_diff(_quay(), _leave())
    landed = merge_scene_with_diff(moved, {
        "positions": {"skiff": "harbour"},
        "entities": {"skiff": {"state": {"transit": {"phase": "docked"}}}}})
    assert landed["positions"].get("skiff") == "harbour"
    assert landed["positions"].get("Ada") == "harbour"
