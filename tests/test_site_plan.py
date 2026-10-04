"""A site plan: rooms standing where a plan put them, at their floors' heights.

The owner, 2026-10-03, on the layout lab's grounds -- "outdoor areas like
that would be cool" -- and on a garden below a third-storey window: "I
suppose the easiest solution is to add something akin to a 3rd dimension."
Step 1 of three: positions and elevations, the map drawing them, and a lab
layout written in the engine's own vocabulary. Hand-made scenes; the names
are illustrations, not the rule.
"""

from __future__ import annotations

import copy

from tools.site_plan_from_layout import GROUNDS, rooms_from_layout
from web.world_routes import map_view
from world.site_plan import (STOREY_M, normalize_site, room_elevation_m,
                             site_overlaps, site_plans)
from world.spatial import (_door_cells, merge_scene_with_diff, room_grid,
                           room_layout_lint)


def _room(name, x, y, w, d, level=0, plan="manor", **extra):
    room = {"name": name, "desc": f"{name}.", "level": level,
            "extent": {"w": w, "d": d}, "adjacent": [],
            "site": {"plan": plan, "x": x, "y": y}}
    room.update(extra)
    return room


def _garden_round_a_house():
    """A 4 x 3 hall in the middle of a 10 x 9 garden, the garden a ring of
    four parts round it, and a bedroom over the hall."""
    garden = _room("Garden", 0, 0, 10, 9, exposure="open", shape="composite",
                   parts=[{"w": 10, "d": 3, "at": [0, 0]}, {"w": 3, "d": 3, "at": [0, 3]},
                          {"w": 3, "d": 3, "at": [7, 3]}, {"w": 10, "d": 3, "at": [0, 6]}])
    hall = _room("Hall", 3, 3, 4, 3)
    bedroom = _room("Bedroom", 3, 3, 4, 3, level=1)
    # the hall's front door, south, onto the garden -- pinned on the ring
    hall["adjacent"].append({"to": "garden", "barrier": "open_door", "dir": "s", "offset": 0.0})
    garden["adjacent"].append({"to": "hall", "barrier": "open_door", "dir": "n", "cell": [3, 6]})
    hall["adjacent"].append({"to": "bedroom", "barrier": "open", "vertical": "up", "way": "stair"})
    return {"rooms": {"garden": garden, "hall": hall, "bedroom": bedroom},
            "entities": {}, "positions": {}}


def test_a_site_is_a_plan_and_a_corner_and_the_height_is_optional():
    assert normalize_site({"plan": "manor", "x": 3.4, "y": -2}) == {
        "plan": "manor", "x": 3, "y": -2, "elev_m": None}
    assert normalize_site({"plan": "manor", "x": 0, "y": 0, "elev_m": 8.5})["elev_m"] == 8.5
    for bad in (None, {}, {"x": 1, "y": 1}, {"plan": "", "x": 1, "y": 1},
                {"plan": "m", "x": "east", "y": 1}, {"plan": "m", "x": True, "y": 1}):
        assert normalize_site(bad) is None, bad


def test_a_floors_height_is_stated_or_its_storey_times_a_storey():
    sc = _garden_round_a_house()
    assert room_elevation_m(sc, "garden") == 0.0
    assert room_elevation_m(sc, "bedroom") == STOREY_M
    sc["rooms"]["bedroom"]["site"]["elev_m"] = 4.2
    assert room_elevation_m(sc, "bedroom") == 4.2
    assert room_elevation_m({"rooms": {"x": {"level": -1}}}, "x") == -STOREY_M


def test_a_house_in_the_hole_of_its_garden_is_no_overlap_and_a_real_one_is():
    sc = _garden_round_a_house()
    assert site_overlaps(sc) == []
    assert site_plans(sc) == {"manor": {0: ["garden", "hall"], 1: ["bedroom"]}}
    sc["rooms"]["hall"]["site"]["x"] = 1            # into the ring
    assert site_overlaps(sc) and site_overlaps(sc)[0][:2] == ("manor", 0)
    kinds = [r["kind"] for r in room_layout_lint(sc)]
    assert "site_plan_overlap" in kinds


def test_the_bearing_walk_does_not_call_a_plan_a_contradiction():
    kinds = [r["kind"] for r in room_layout_lint(_garden_round_a_house())]
    assert "rooms_overlap_when_placed" not in kinds


def test_a_doorway_pinned_to_its_cell_stands_there_on_a_ring():
    sc = _garden_round_a_house()
    cells, bearing = _door_cells(sc, "garden", "hall")
    assert cells == [(3, 6)] and bearing == "n"
    hall_cells, _ = _door_cells(sc, "hall", "garden")
    # the two sides of the doorway meet across the wall, on the plan
    gx, gy = cells[0]
    hx, hy = hall_cells[0][0] + 3, hall_cells[0][1] + 3
    assert abs(gx - hx) + abs(gy - hy) == 1


def test_a_beat_describes_a_room_on_a_plan_and_never_re_measures_it():
    sc = _garden_round_a_house()
    merged = merge_scene_with_diff(sc, {"rooms": {"hall": {
        "name": "Hall", "desc": "Dust on every surface.",
        "extent": {"w": 9, "d": 9}, "level": 2, "site": {"plan": "manor", "x": 0, "y": 0}}}})
    hall = merged["rooms"]["hall"]
    assert hall["desc"] == "Dust on every surface."
    assert hall["extent"] == {"w": 4, "d": 3} and hall["level"] == 0
    assert hall["site"]["x"] == 3 and hall["site"]["y"] == 3


def test_the_map_draws_a_plan_where_it_stands_storey_by_storey():
    sc = _garden_round_a_house()
    sc["rooms"]["lane"] = {"name": "Lane", "desc": "A lane.", "adjacent": [
        {"to": "garden", "barrier": "open", "dir": "n"}]}
    comps = map_view(sc, [])["components"]
    plan = [c for c in comps if c.get("plan") == "manor"]
    assert [c["level"] for c in plan] == [0, 1]        # ground first, then up
    ground = {r["id"]: r for r in plan[0]["rooms"]}
    assert ground["garden"]["offset"] == [0, 0] and ground["hall"]["offset"] == [3, 3]
    assert plan[0]["collisions"] == []
    # a room on no plan is laid out by bearing as before, and never draws a
    # plan's room a second time
    drawn = [r["id"] for c in comps for r in c["rooms"]]
    assert drawn.count("garden") == 1 and "lane" in drawn


LAYOUT = {
    "name": "Cottage",
    "floors": {"0": {"parlour": [{"x": 2, "y": 2, "w": 4, "d": 3}],
                     "stair@0": [{"x": 6, "y": 2, "w": 2, "d": 3}]},
               "1": {"loft": [{"x": 2, "y": 2, "w": 4, "d": 3}],
                     "stair@1": [{"x": 6, "y": 2, "w": 2, "d": 3}]}},
    "outlines": {"main": {"0": {"x": 2, "y": 2, "w": 6, "d": 3},
                          "1": {"x": 2, "y": 2, "w": 6, "d": 3}}},
    "site": {"x": 0, "y": 0, "w": 10, "d": 8},
    "names": {"parlour": "Parlour", "loft": "Loft", "stair@0": "Stair", "stair@1": "Stair"},
    "purposes": {"parlour": "living", "loft": "bedroom"},
    "doors": [{"a": "parlour", "b": "stair@0", "level": 0, "side": "e", "cell": [5, 3], "kind": "door"},
              {"a": "loft", "b": "stair@1", "level": 1, "side": "e", "cell": [5, 3], "kind": "door"},
              {"a": "parlour", "b": "entrance", "level": 0, "side": "s", "cell": [3, 4],
               "kind": "front door", "outside": True}],
    "stairwells": [{"id": "stair", "kind": "straight", "levels": [0, 1],
                    "halls": {"0": "stair@0", "1": "stair@1"}}],
    "fixtures": {"parlour": [{"id": "hearth", "name": "Hearth", "kind": "hearth",
                              "rect": {"x": 2, "y": 2, "w": 2, "d": 1}, "height": "waist"}]},
    "features": [{"id": "well", "name": "Well", "kind": "well",
                  "rect": {"x": 8, "y": 6, "w": 1, "d": 1}, "height": "waist"}],
    "windows": [{"id": "loft_w1", "room": "loft", "level": 1, "side": "n", "cell": [3, 2]}],
}


def test_a_lab_layout_becomes_rooms_on_one_plan_that_hold_together():
    rooms = rooms_from_layout(copy.deepcopy(LAYOUT), "cottage")
    sc = {"rooms": rooms, "entities": {}, "positions": {}}
    assert set(rooms) == {"parlour", "stair_0", "loft", "stair_1", GROUNDS}
    assert site_overlaps(sc) == []
    # the grounds are the site less the cottage's footprint
    g = rooms[GROUNDS]
    cells = {(x + g["site"]["x"], y + g["site"]["y"]) for x, y in room_grid(sc, GROUNDS).cells}
    assert len(cells) == 10 * 8 - 6 * 3 and (3, 3) not in cells and (0, 0) in cells
    assert g["exposure"] == "open" and "well" in g["anchors"]
    # every doorway's two sides meet across the wall on the plan
    for a, room in rooms.items():
        for edge in room["adjacent"]:
            if edge.get("vertical"):
                continue
            b = edge["to"]
            (da,), _ = _door_cells(sc, a, b)
            (db,), _ = _door_cells(sc, b, a)
            pa = (da[0] + rooms[a]["site"]["x"], da[1] + rooms[a]["site"]["y"])
            pb = (db[0] + rooms[b]["site"]["x"], db[1] + rooms[b]["site"]["y"])
            assert abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) == 1, (a, b, pa, pb)
    # the stair climbs between its halls, and the loft is a storey up
    assert {"to": "stair_1", "barrier": "open", "vertical": "up", "way": "stair"} \
        in rooms["stair_0"]["adjacent"]
    assert room_elevation_m(sc, "loft") == STOREY_M
    assert rooms["parlour"]["anchors"]["hearth"]["cell"] == [0, 0]
    assert rooms["loft"]["anchors"]["loft_w1"]["dir"] == "n"
