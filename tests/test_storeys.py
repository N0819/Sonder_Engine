"""Storeys: a room's level, what lies over and under it, and the shaft.

Skerry Light (2026-09-15) was four floors on one stair, and to the engine
it was a chain of edges: nothing knew the tower was a tower. The level is
the number everything vertical hangs on (`world/spatial_levels.py`)."""
from __future__ import annotations

from world.spatial import (FLIGHT_PACES, FLOOR_LOSS_DB, far_path_gain, floor_edges,
                           infer_room_levels, level_span, merge_scene_with_diff,
                           passable_route_exists, room_level, rooms_over, rooms_under,
                           spatial_digest, stack_of, visual_level_between, walk)
from world.spatial import far_field_graph


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


def test_a_stair_and_an_overlook_on_one_wall_both_keep_it():
    """Hollin Mill, 2026-09-15: the stair in the wheel floor's north wall
    and the gallery rail above it, both `up` on `n`, were dropped as a
    collision, and their far sides with them."""
    from world.spatial import normalize_scene_bearings
    sc = {"rooms": {
        "wheel": {"adjacent": [{"to": "stones", "barrier": "open", "dir": "n", "vertical": "up", "way": "stair"},
                               {"to": "gallery", "barrier": "open", "dir": "n", "vertical": "up", "way": "overlook"}]},
        "stones": {"adjacent": [{"to": "wheel", "barrier": "open", "dir": "n", "vertical": "down", "way": "stair"}]},
        "gallery": {"adjacent": [{"to": "wheel", "barrier": "open", "dir": "s", "vertical": "down", "way": "overlook"}]}}}
    normalize_scene_bearings(sc)
    e = lambda a, b: next(x for x in sc["rooms"][a]["adjacent"] if x["to"] == b)
    assert e("wheel", "stones")["dir"] == "n" and e("wheel", "gallery")["dir"] == "n"
    assert e("stones", "wheel")["dir"] == "n" and e("gallery", "wheel")["dir"] == "s"


def test_a_hatch_shows_its_own_two_ends_and_nothing_beyond():
    """Hollin Mill turn 4, 2026-09-15: through a ladder hatch the surveyor
    below saw the man in the loft's far corner, and he saw her by the
    millstones. A passage shows the body at its end, not the room."""
    sc = {"rooms": {
        "stones": {"name": "Stones", "extent": {"w": 12, "d": 10}, "anchors": {}, "exposure": "enclosed",
                   "adjacent": [{"to": "loft", "barrier": "open", "dir": "e", "vertical": "up", "way": "ladder"}]},
        "loft": {"name": "Loft", "extent": {"w": 12, "d": 8}, "anchors": {}, "exposure": "enclosed",
                 "adjacent": [{"to": "stones", "barrier": "open", "dir": "e", "vertical": "down", "way": "ladder"}]}},
        "positions": {"Ada": "stones", "Cal": "loft"},
        "stations": {"Ada": {"cell": [6, 5]}, "Cal": {"cell": [1, 4]}}, "entities": {}}
    assert visual_level_between(sc, "Ada", "Cal") == "none"
    assert visual_level_between(sc, "Cal", "Ada") == "none"
    from world.spatial import _door_cells
    lip_loft = _door_cells(sc, "loft", "stones")[0][0]
    lip_stones = _door_cells(sc, "stones", "loft")[0][0]
    sc["stations"]["Cal"] = {"cell": list(lip_loft)}
    sc["stations"]["Ada"] = {"cell": list(lip_stones)}
    assert visual_level_between(sc, "Ada", "Cal") == "full"
    assert visual_level_between(sc, "Cal", "Ada") == "full"


def test_looks_apply_in_order_and_the_last_the_room_can_place_wins():
    """Hollin Mill turn 5, 2026-09-15: a look down over the rail (south),
    then a look at a hatch in another room; only the last was kept, it
    placed nothing, and she faced north with her back to the drop."""
    from world.spatial_frames import infer_facing
    rooms = {"gallery": {"extent": {"w": 12, "d": 3}, "anchors": {},
                         "adjacent": [{"to": "stones", "barrier": "open", "dir": "s"},
                                      {"to": "wheel", "barrier": "open", "dir": "s", "vertical": "down", "way": "overlook"}]},
             "stones": {"adjacent": [{"to": "gallery", "barrier": "open", "dir": "n"}]},
             "wheel": {"adjacent": [{"to": "gallery", "barrier": "open", "dir": "n", "vertical": "up", "way": "overlook"}]}}
    prev = {"rooms": rooms, "positions": {"Ada": "stones"}, "orientation": {"Ada": {"facing": "n"}}}
    new = {"rooms": rooms, "positions": {"Ada": "gallery"}, "stations": {"Ada": {"cell": [1, 1]}},
           "orientation": {"Ada": {"came_from": "stones", "facing": "n"}}}
    infer_facing(1, None, prev, new, [], looks={"Ada": ["wheel", "loft_hatch"]}, turn_idx=5)
    assert new["orientation"]["Ada"]["facing"] == "s"


def test_standing_on_the_destinations_door_cell_is_arriving():
    """Hollin Mill turn 8, 2026-09-15: a climb ended on the loft's hatch
    cell with its paces spent and was left "under way" to the pace inside
    the door, so every silent beat after would have walked it."""
    from world.spatial import FLIGHT_PACES
    sc = {"rooms": {
        "stones": {"name": "Stones", "extent": {"w": 12, "d": 10}, "anchors": {}, "exposure": "enclosed",
                   "adjacent": [{"to": "loft", "barrier": "open", "dir": "e", "vertical": "up", "way": "ladder"}]},
        "loft": {"name": "Loft", "extent": {"w": 12, "d": 8}, "anchors": {}, "exposure": "enclosed",
                 "adjacent": [{"to": "stones", "barrier": "open", "dir": "e", "vertical": "down", "way": "ladder"}]}},
        "positions": {"Ada": "stones"}, "stations": {"Ada": {"cell": [2, 6]}}, "entities": {}}
    # Exactly enough paces to reach the hatch cell and cross: the door,
    # the flight, and the entry -- none for the pace inside.
    from world.spatial import walk as _walk
    probe = _walk(sc, "Ada", "loft", paces=200)
    short = _walk(sc, "Ada", "loft", paces=probe["paces"] - 1)
    assert short["room"] == "loft" and short["arrived"], short


def test_touching_cells_see_each_other_and_a_fixture_is_still_cover():
    """Hollin Mill turn 13, 2026-09-15: a head-high stair post beside a
    one-step diagonal hid the man at the stair foot from the woman at
    the pit, one pace away, and her from him."""
    from world.spatial import anchor_cells, body_visibility
    sc = {"rooms": {"wheel": {"name": "Wheel", "extent": {"w": 12, "d": 10}, "exposure": "enclosed",
                              "adjacent": [], "anchors": {
                                  "stair": {"desc": "the stair foot", "dir": "n", "height": "head", "footprint": "small"}}}},
          "positions": {"Ada": "wheel", "Cal": "wheel"},
          "stations": {"Ada": {"cell": [8, 1]}, "Cal": {"at": "stair", "cell": [9, 2]}},
          "orientation": {"Ada": {"facing": "e"}, "Cal": {"facing": "s"}}, "entities": {}}
    assert body_visibility(sc, "Ada", "Cal")["visible"]
    assert body_visibility(sc, "Cal", "Ada")["visible"]
    # Three paces off, with the post's cell squarely on the line, the post
    # is cover: standing at a fixture does not make it transparent.
    post = anchor_cells(sc, "wheel")["stair"]["cells"][0]
    sc["stations"]["Cal"] = {"at": "stair", "cell": [post[0], post[1] - 1]}
    sc["stations"]["Ada"] = {"cell": [post[0], post[1] + 3]}
    sc["orientation"]["Ada"] = {"facing": "n"}
    assert not body_visibility(sc, "Ada", "Cal")["visible"]


def test_a_thing_that_says_who_carries_it_is_carried(temp_db):
    """Hollin Mill, 2026-09-15: the establish stood the surveyor's lantern
    and key loose in the lane; setting the lantern down was refused as not
    hers. `held_by` on the thing is the bearing record's evidence."""
    from persist.commit import derive_borne_containment
    sc = {"rooms": {"lane": {"name": "Lane", "adjacent": []}},
          "positions": {"Ada": "lane", "lamp": "lane"},
          "entities": {"char_ada": {"name": "Ada", "kind": "person", "aliases": []},
                       "lamp": {"name": "a lantern", "kind": "item", "portable": True,
                                "held_by": "Ada"}},
          "contained": {}, "contacts": [], "poses": {}}
    minted = derive_borne_containment(sc)
    assert any(subject == "lamp" and bearer == "Ada" for subject, bearer, _e in minted), minted
    assert sc["contained"]["lamp"]["in"] == "Ada" and sc["contained"]["lamp"]["mode"] == "carried"


def test_a_planned_measurement_survives_the_establish():
    """Coldharbour Fair, 2026-09-15: the plan laid a 20 by 16 square and the
    establish re-measured it 30 by 30. A stub carrying the plan's geometry
    keeps it; the establish's description is welcome, its measuring is not."""
    from world.spatial import merge_scene_with_diff
    sc = {"rooms": {"square": {"name": "Square", "planned": True, "extent": {"w": 20, "d": 16},
                               "exposure": "open", "level": 0, "adjacent": []}},
          "positions": {}, "entities": {}}
    merged = merge_scene_with_diff(sc, {"rooms": {"square": {
        "name": "Market Square", "desc": "cobbles and stalls", "extent": {"w": 30, "d": 30},
        "exposure": "sheltered", "level": 2}}})
    room = merged["rooms"]["square"]
    assert room["extent"] == {"w": 20, "d": 16} and room["exposure"] == "open" and room["level"] == 0
    assert room["desc"] == "cobbles and stalls"


def test_steps_under_the_sky_are_an_overlook_for_sight():
    """Coldharbour Fair turn 6, 2026-09-15: the clerk at the porch rail, a
    storey above the square up a flight of steps, saw nothing of the fair.
    Between two rooms neither of which is enclosed there is air, not a
    floor: the porch sees the square from its lip and is seen from it."""
    sc = {"rooms": {
        "square": {"name": "Square", "extent": {"w": 20, "d": 16}, "anchors": {}, "exposure": "open",
                   "adjacent": [{"to": "porch", "barrier": "open", "dir": "e", "vertical": "up", "way": "stair"}]},
        "porch": {"name": "Porch", "extent": {"w": 6, "d": 4}, "anchors": {}, "exposure": "sheltered",
                  "adjacent": [{"to": "square", "barrier": "open", "dir": "w", "vertical": "down", "way": "stair"}]}},
        "positions": {"Isla": "porch", "Wick": "square"},
        "stations": {"Isla": {"cell": [1, 1]}, "Wick": {"cell": [10, 8]}}, "entities": {}}
    assert visual_level_between(sc, "Isla", "Wick") == "full"
    assert visual_level_between(sc, "Wick", "Isla") == "full"
    sc["stations"]["Isla"] = {"cell": [5, 2]}          # back from the rail: still open air
    assert visual_level_between(sc, "Isla", "Wick") == "full"
    from world.spatial import anchor_cells
    assert len(anchor_cells(sc, "square")["door:porch"]["cells"]) > 1, "the steps' side is the whole side"
