"""Regression tests for spatial.apply_transit_dock_edges: the derived
dock/portal edge rewrite that makes moving rooms first-class.

The interior<->exterior doorway of a parent_entity-linked room is a DERIVED
fact -- f(entity position, entity.state.transit) -- not an authored edge.
The historical static edge went stale the moment a vehicle moved or sealed
(the live elevator bug: doors narrated sealed + descending while the room
kept an open_door edge onto the departure hallway). The rewrite is a pure,
idempotent function of the scene, run from merge_scene_with_diff so commit
preparation and perception's mid-turn merges all see the same doorways.
"""

from __future__ import annotations

import copy

from spatial import (
    apply_transit_dock_edges,
    merge_scene_with_diff,
    spatial_rel,
    visible_adjacent_rooms,
)


def _elevator_scene(transit=None, exterior="floor1_hall"):
    scene = {
        "rooms": {
            "elevator_car": {
                "name": "Service Elevator", "desc": "A cramped car.",
                "adjacent": [{"to": "floor1_hall", "barrier": "open_door",
                              "distance": "near"}],
                "parent_entity": "service_elevator",
            },
            "floor1_hall": {"name": "Floor One Hall",
                            "desc": "A smoky hallway.", "adjacent": []},
            "sub4_shelter": {"name": "Sub-level 4 Shelter",
                             "desc": "A concrete shelter.", "adjacent": []},
            "elevator_shaft": {"name": "Elevator Shaft",
                               "desc": "A dark shaft.", "adjacent": []},
        },
        "entities": {"service_elevator": {
            "name": "Service Elevator", "kind": "vehicle",
            "state": ({"transit": transit} if transit else {}),
        }},
        "positions": {"service_elevator": exterior,
                      "The Stranger": "elevator_car",
                      "Mara": "elevator_car"},
    }
    return scene


def test_full_elevator_lifecycle_derives_each_phase():
    """docked@floor1 doors-open -> sealed -> in_transit -> arriving ->
    docked@sub4 opening onto a DIFFERENT adjacency than it departed --
    asserting the derived edges via spatial_rel/visible_adjacent_rooms at
    every phase, with occupants' positions never touched."""
    sc = _elevator_scene()

    # Phase: docked, hatch open (no transit state = the historical default).
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "elevator_car", "floor1_hall")["barrier"] == "open_door"
    visible = {r["room_id"] for r in visible_adjacent_rooms(sc, "elevator_car")}
    assert "floor1_hall" in visible

    # Phase: doors sealed (hatch closed, still docked).
    sc["entities"]["service_elevator"]["state"]["transit"] = {
        "phase": "docked", "hatch": "closed"}
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "elevator_car", "floor1_hall")["barrier"] == "closed_door"
    assert not visible_adjacent_rooms(sc, "elevator_car")

    # Phase: in transit -- no exterior doorway at all; "step out" is blocked
    # by the same passable-route vocabulary director_resolve already checks.
    sc["entities"]["service_elevator"]["state"]["transit"] = {
        "phase": "in_transit", "hatch": "closed"}
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "elevator_car", "floor1_hall")["barrier"] == "separated"
    assert not visible_adjacent_rooms(sc, "elevator_car")

    # Phase: arriving -- hatch still shut against the destination.
    sc["entities"]["service_elevator"]["state"]["transit"] = {
        "phase": "arriving", "hatch": "closed",
        "destination_room": "sub4_shelter"}
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "elevator_car", "sub4_shelter")["barrier"] == "closed_door"
    assert spatial_rel(sc, "elevator_car", "floor1_hall")["barrier"] == "separated"

    # Phase: docked at the NEW exterior, doors open onto the shelter.
    sc["entities"]["service_elevator"]["state"]["transit"] = {
        "phase": "docked", "hatch": "open"}
    sc["positions"]["service_elevator"] = "sub4_shelter"
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "elevator_car", "sub4_shelter")["barrier"] == "open_door"
    assert spatial_rel(sc, "elevator_car", "floor1_hall")["barrier"] == "separated"
    visible = {r["room_id"] for r in visible_adjacent_rooms(sc, "elevator_car")}
    assert visible == {"sub4_shelter"}

    # Occupants rode along without a single position change.
    assert sc["positions"]["The Stranger"] == "elevator_car"
    assert sc["positions"]["Mara"] == "elevator_car"


def test_route_room_gives_forced_door_somewhere_to_open():
    """Mid-transit with a route_room set (the shaft): the derived edge
    targets the shaft, closed -- so a door forced open mid-transit has a
    real, dangerous place on the other side rather than nothing."""
    sc = _elevator_scene(transit={"phase": "in_transit", "hatch": "closed",
                                  "route_room": "elevator_shaft"})
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "elevator_car", "elevator_shaft")["barrier"] == "closed_door"
    assert spatial_rel(sc, "elevator_car", "floor1_hall")["barrier"] == "separated"


def test_rewrite_is_idempotent():
    sc = _elevator_scene(transit={"phase": "sealed", "hatch": "closed"})
    apply_transit_dock_edges(sc)
    snapshot = copy.deepcopy(sc)
    changed = apply_transit_dock_edges(sc)
    assert sc == snapshot
    assert changed is False


def test_stale_edge_retro_fix_without_transit_state():
    """A vehicle that moved with NO transit state authored (every
    pre-existing vehicle in live chats): the stale interior edge to the
    departure room is re-pointed to the current exterior, preserving the
    authored barrier -- the retro-fix for the whole existing fleet."""
    sc = _elevator_scene(exterior="sub4_shelter")  # moved; edge still floor1
    # A stale reverse edge from the old hall into the car, too.
    sc["rooms"]["floor1_hall"]["adjacent"] = [
        {"to": "elevator_car", "barrier": "open_door", "distance": "near"}]
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "elevator_car", "sub4_shelter")["barrier"] == "open_door"
    assert spatial_rel(sc, "elevator_car", "floor1_hall")["barrier"] == "separated"
    # The stale reverse edge from the plain world room was stripped.
    assert sc["rooms"]["floor1_hall"]["adjacent"] == []


def test_entity_without_position_is_left_alone():
    """No recorded exterior position and no closed phase: there is nothing
    to derive the doorway from, so the authored edge must survive -- the
    rewrite never severs on missing data."""
    sc = _elevator_scene()
    del sc["positions"]["service_elevator"]
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "elevator_car", "floor1_hall")["barrier"] == "open_door"


def test_nested_mover_composes():
    """A car parked on a ferry's vehicle deck (a moving room inside a moving
    room): the car's dock edge targets the deck; the ferry's dock edge
    targets the pier; sealing the FERRY severs deck<->pier while the car's
    own doorway onto the deck survives (another entity's interior rooms are
    exempt from reverse-stripping)."""
    sc = {
        "rooms": {
            "car_interior": {"name": "Car Interior", "desc": "Cramped.",
                             "adjacent": [{"to": "vehicle_deck",
                                           "barrier": "closed_door",
                                           "distance": "near"}],
                             "parent_entity": "the_car"},
            "vehicle_deck": {"name": "Vehicle Deck", "desc": "Steel deck.",
                             "adjacent": [{"to": "pier", "barrier": "open",
                                           "distance": "near"}],
                             "parent_entity": "the_ferry"},
            "pier": {"name": "Pier", "desc": "A wooden pier.",
                     "adjacent": []},
        },
        "entities": {
            "the_car": {"name": "The Car", "kind": "vehicle", "state": {}},
            "the_ferry": {"name": "The Ferry", "kind": "vehicle",
                          "state": {}},
        },
        "positions": {"the_car": "vehicle_deck", "the_ferry": "pier",
                      "The Stranger": "car_interior"},
    }
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "car_interior", "vehicle_deck")["barrier"] == "closed_door"
    assert spatial_rel(sc, "vehicle_deck", "pier")["barrier"] == "open"

    # Ferry departs: deck loses the pier, car keeps its deck doorway.
    sc["entities"]["the_ferry"]["state"]["transit"] = {
        "phase": "in_transit", "hatch": "closed", "route_room": ""}
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "vehicle_deck", "pier")["barrier"] == "separated"
    assert spatial_rel(sc, "car_interior", "vehicle_deck")["barrier"] == "closed_door"


def test_dock_exit_marker_restores_door_to_the_same_room():
    """A two-room vehicle: only the airlock has an exterior edge. Sealing
    severs it; re-docking restores the doorway to the AIRLOCK (dock_exit
    memory), never to the bridge."""
    sc = {
        "rooms": {
            "bridge": {"name": "Bridge", "desc": "Consoles.",
                       "adjacent": [{"to": "airlock", "barrier": "open_door",
                                     "distance": "near"}],
                       "parent_entity": "ship"},
            "airlock": {"name": "Airlock", "desc": "Twin hatches.",
                        "adjacent": [
                            {"to": "bridge", "barrier": "open_door",
                             "distance": "near"},
                            {"to": "hangar", "barrier": "open_door",
                             "distance": "near"},
                        ],
                        "parent_entity": "ship"},
            "hangar": {"name": "Hangar", "desc": "A vast bay.",
                       "adjacent": []},
            "landing_pad": {"name": "Landing Pad", "desc": "Open pad.",
                            "adjacent": []},
        },
        "entities": {"ship": {"name": "The Ship", "kind": "vehicle",
                              "state": {}}},
        "positions": {"ship": "hangar", "The Stranger": "bridge"},
    }
    sc["entities"]["ship"]["state"]["transit"] = {
        "phase": "in_transit", "hatch": "closed"}
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "airlock", "hangar")["barrier"] == "separated"
    # Interior edges survive sealing.
    assert spatial_rel(sc, "bridge", "airlock")["barrier"] == "open_door"

    sc["entities"]["ship"]["state"]["transit"] = {
        "phase": "docked", "hatch": "open"}
    sc["positions"]["ship"] = "landing_pad"
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "airlock", "landing_pad")["barrier"] == "open_door"
    # The bridge never grows its own exterior doorway.
    assert spatial_rel(sc, "bridge", "landing_pad")["barrier"] == "separated"


def test_portal_link_open_and_closed():
    """A traversable link entity derives an edge between two arbitrary
    rooms when open and severs it (only its own tagged edge) when closed."""
    sc = {
        "rooms": {
            "study": {"name": "Study", "desc": "Bookshelves.",
                      "adjacent": [{"to": "hallway", "barrier": "open",
                                    "distance": "near"}]},
            "hallway": {"name": "Hallway", "desc": "Long.", "adjacent": []},
            "sanctum": {"name": "Sanctum", "desc": "Candles.",
                        "adjacent": []},
        },
        "entities": {"arcane_gate": {
            "name": "Arcane Gate", "kind": "portal",
            "state": {"link": {"rooms": ["study", "sanctum"],
                               "phase": "open"}},
        }},
        "positions": {},
    }
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "study", "sanctum")["barrier"] == "open_door"
    # The hand-authored study<->hallway edge is untouched.
    assert spatial_rel(sc, "study", "hallway")["barrier"] == "open"

    sc["entities"]["arcane_gate"]["state"]["link"]["phase"] = "closed"
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "study", "sanctum")["barrier"] == "separated"
    assert spatial_rel(sc, "study", "hallway")["barrier"] == "open"


def test_merge_scene_with_diff_applies_the_rewrite():
    """The one-enum repair path end to end: a diff that only sets
    hatch:'closed' on the entity leaves the merged scene with the doorway
    actually closed -- no adjacency surgery authored anywhere."""
    prev = _elevator_scene()
    diff = {"entities": {"service_elevator": {
        "name": "Service Elevator", "kind": "vehicle",
        "state": {"transit": {"phase": "docked", "hatch": "closed"}}}}}
    merged = merge_scene_with_diff(prev, diff)
    assert spatial_rel(merged, "elevator_car", "floor1_hall")["barrier"] == "closed_door"

    # And an arrival: position change + docked/open = new adjacency.
    diff2 = {
        "positions": {"service_elevator": "sub4_shelter"},
        "entities": {"service_elevator": {
            "name": "Service Elevator", "kind": "vehicle",
            "state": {"transit": {"phase": "docked", "hatch": "open"}}}},
    }
    merged2 = merge_scene_with_diff(merged, diff2)
    assert spatial_rel(merged2, "elevator_car", "sub4_shelter")["barrier"] == "open_door"
    assert spatial_rel(merged2, "elevator_car", "floor1_hall")["barrier"] == "separated"
