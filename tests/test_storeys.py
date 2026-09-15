"""Storeys: a room's level, what lies over and under it, and the shaft.

Skerry Light (2026-09-15) was four floors on one stair, and to the engine
it was a chain of edges: nothing knew the tower was a tower. The level is
the number everything vertical hangs on (`world/spatial_levels.py`)."""
from __future__ import annotations

from world.spatial import (FLIGHT_PACES, FLOOR_LOSS_DB, far_path_gain, floor_edges,
                           infer_room_levels, level_span, merge_scene_with_diff,
                           passable_route_exists, room_level, rooms_over, rooms_under,
                           spatial_digest, stack_of, visual_level_between, walk)
from world.spatial_sound_field import far_field_graph


def _tower(levels=False):
    names = ["store", "keepers", "watch", "lamp"]
    rooms = {}
    for i, rid in enumerate(names):
        adj = []
        if i > 0:
            adj.append({"to": names[i - 1], "barrier": "open", "dir": "n", "vertical": "down"})
        if i < 3:
            adj.append({"to": names[i + 1], "barrier": "open", "dir": "n", "vertical": "up"})
        rooms[rid] = {"name": rid.title(), "extent": {"w": 6, "d": 6}, "adjacent": adj,
                      "anchors": {}, "exposure": "enclosed"}
    rooms["yard"] = {"name": "Yard", "extent": {"w": 8, "d": 8}, "anchors": {}, "exposure": "open",
                     "adjacent": [{"to": "store", "barrier": "open_door", "dir": "e"}]}
    rooms["store"]["adjacent"].append({"to": "yard", "barrier": "open_door", "dir": "w"})
    if levels:
        rooms["store"]["level"] = 0
    return {"rooms": rooms, "positions": {"Nell": "store"}, "stations": {"Nell": {"cell": [3, 3]}},
            "entities": {}}


def test_levels_are_inferred_along_the_stairs():
    sc = _tower()
    written = infer_room_levels(sc)
    assert {rid: room_level(sc, rid) for rid in ("store", "keepers", "watch", "lamp", "yard")} == \
        {"store": 0, "keepers": 1, "watch": 2, "lamp": 3, "yard": 0}
    assert "store" not in written or written["store"] == 0
    assert stack_of(sc, "watch") == ["store", "keepers", "watch", "lamp"]
    assert rooms_over(sc, "keepers") == ["watch"] and rooms_under(sc, "keepers") == ["store"]


def test_a_declared_level_is_never_moved_and_the_merge_levels_the_scene():
    sc = _tower()
    sc["rooms"]["lamp"]["level"] = 10
    infer_room_levels(sc)
    assert room_level(sc, "lamp") == 10
    assert room_level(sc, "watch") == 9, "inference runs from the declared storey"
    merged = merge_scene_with_diff(_tower(), {})
    assert room_level(merged, "lamp") == 3


def test_a_flight_costs_the_storeys_between_the_rooms():
    sc = _tower()
    sc["rooms"]["store"]["level"] = 0
    sc["rooms"]["keepers"]["level"] = 2      # a tall flight, two storeys
    assert level_span(sc, "store", "keepers") == 2
    one = walk(_tower(), "Nell", "keepers", paces=FLIGHT_PACES + 8)
    two = walk(sc, "Nell", "keepers", paces=FLIGHT_PACES + 8)
    assert one["arrived"] and not two["arrived"]


def test_a_room_over_another_shares_a_floor_the_far_field_crosses():
    sc = _tower()
    sc["rooms"]["loft"] = {"name": "Loft", "extent": {"w": 8, "d": 8}, "anchors": {},
                           "adjacent": [], "over": ["yard"], "floor": "timber"}
    infer_room_levels(sc)
    assert room_level(sc, "loft") == 1
    edges = floor_edges(sc, "loft")
    assert edges and edges[0]["to"] == "yard" and edges[0]["vertical"] == "down" \
        and edges[0]["loss_db"] == FLOOR_LOSS_DB["timber"]
    assert floor_edges(sc, "yard")[0]["vertical"] == "up"
    graph = far_field_graph(sc)
    assert graph["loft"]["yard"] == FLOOR_LOSS_DB["timber"]
    stone = _tower()
    stone["rooms"]["loft"] = {**sc["rooms"]["loft"], "floor": "stone"}
    assert far_field_graph(stone)["loft"]["yard"] > FLOOR_LOSS_DB["timber"]
    assert not passable_route_exists(sc, "loft", "yard"), "a floor is no way through"
    digest = spatial_digest(sc, "Nell")
    assert digest.get("storey") == 0
    sc["positions"]["Nell"] = "yard"
    assert spatial_digest(sc, "Nell").get("overhead") == ["Loft"]


def test_an_overlook_is_looked_through_and_never_walked_through():
    sc = {"rooms": {
        "hall": {"name": "Hall", "extent": {"w": 10, "d": 10}, "anchors": {}, "exposure": "enclosed",
                 "adjacent": [{"to": "gallery", "barrier": "open", "dir": "n", "vertical": "up", "way": "overlook"},
                              {"to": "stair", "barrier": "open", "dir": "e", "vertical": "up"}]},
        "gallery": {"name": "Gallery", "extent": {"w": 10, "d": 3}, "anchors": {}, "exposure": "enclosed",
                    "adjacent": [{"to": "hall", "barrier": "open", "dir": "s", "vertical": "down", "way": "overlook"}]},
        "stair": {"name": "Stair", "extent": {"w": 3, "d": 3}, "anchors": {}, "exposure": "enclosed",
                  "adjacent": [{"to": "hall", "barrier": "open", "dir": "w", "vertical": "down"}]}},
        "positions": {"Watcher": "gallery", "Speaker": "hall"},
        "stations": {"Watcher": {"cell": [5, 2]}, "Speaker": {"cell": [5, 5]}}, "entities": {}}
    assert not passable_route_exists(sc, "hall", "gallery")
    assert passable_route_exists(sc, "hall", "stair")
    # At the rail (the gallery's south rim, the edge's wall): the whole
    # floor below is in view and the watcher is seen from it.
    assert visual_level_between(sc, "Watcher", "Speaker") == "full"
    assert visual_level_between(sc, "Speaker", "Watcher") == "full"
    # Back from the rail: the floor you stand on is between you and them.
    sc["stations"]["Watcher"] = {"cell": [5, 0]}
    assert visual_level_between(sc, "Speaker", "Watcher") == "none"
    assert visual_level_between(sc, "Watcher", "Speaker") == "none"
