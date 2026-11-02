"""A room is a medium because of what the room IS, not because a vessel under
way happens to stand in it.

Audit world_spatial_movement_sight F5 (2026-11-01, CONFIRMED WRONG-SCENE):
under the owner's D2 ruling (2026-10-09) a journey that names no other space
keeps `route_room = departed_from` -- the room it set off from. `medium_rooms`
(2026-10-21) read EVERY under-way route room as "a room a body does not walk
into, across or out of", so a TARDIS written `{phase: in_transit, hatch:
closed}` on a beach made the beach water: `medium_rooms == {'beach'}` and the
skip's walk graph had no edge into or out of it. 18 stored TARDIS writes have
this shape (UNBUILT_WORLD 1.194).

Kept: a room whose own `floor` says water is a medium, and the SPACE a vessel
moves through on its way elsewhere (a route that is not the room it left) is
one.
"""

from world.spatial import medium_rooms, merge_scene_with_diff


def _beach():
    return {
        "rooms": {
            "beach": {"name": "Beach", "adjacent": [{"to": "village", "barrier": "open"}]},
            "village": {"name": "Village", "adjacent": [{"to": "beach", "barrier": "open"}]},
            "console": {"name": "Console Room", "parent_entity": "tardis",
                        "adjacent": [{"to": "beach", "barrier": "open_door"}]},
        },
        "positions": {"Rose": "beach", "tardis": "beach", "Doctor": "console"},
        "entities": {"tardis": {"name": "TARDIS", "kind": "vehicle",
                                "interior_rooms": ["console"],
                                "state": {"transit": {"phase": "docked",
                                                      "hatch": "open"}}}},
        "attire": {"Rose": {}, "Doctor": {}},
        "contained": {}, "contacts": [],
    }


def test_a_journey_naming_no_other_space_leaves_its_room_walkable():
    moved = merge_scene_with_diff(_beach(), {"entities": {"tardis": {"state": {
        "transit": {"phase": "in_transit", "hatch": "closed"}}}}})
    transit = moved["entities"]["tardis"]["state"]["transit"]
    assert transit.get("route_room") == "beach"          # D2 stands
    assert medium_rooms(moved) == set()


def test_the_space_a_vessel_moves_through_elsewhere_is_still_a_medium():
    sc = _beach()
    sc["rooms"]["vortex"] = {"name": "The Vortex", "adjacent": []}
    sc["entities"]["tardis"]["state"]["transit"] = {
        "phase": "in_transit", "hatch": "closed", "route_room": "vortex",
        "departed_from": "beach"}
    sc["positions"]["tardis"] = "vortex"
    assert medium_rooms(sc) == {"vortex"}


def test_a_room_whose_floor_is_water_is_a_medium_whatever_floats_in_it():
    sc = _beach()
    sc["rooms"]["beach"]["floor"] = "water"
    assert medium_rooms(sc) == {"beach"}
