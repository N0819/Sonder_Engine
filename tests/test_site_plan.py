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


# ---------------------------------------------------------------------------
# Step 2: sight with height (2026-10-04)
# ---------------------------------------------------------------------------

def _window_over_the_garden(hinami_cell=(3, 1), visitor_cell=(9, 4), posture=None):
    """The bedroom (a storey up, over the hall) has a window in its east wall
    at plan cell (6, 4), looking over the garden's east strip; Hinami is in
    the bedroom and a visitor in the garden."""
    sc = _garden_round_a_house()
    bedroom, garden = sc["rooms"]["bedroom"], sc["rooms"]["garden"]
    bedroom["adjacent"].append({"to": "garden", "barrier": "window", "dir": "e", "offset": 0.5})
    garden["adjacent"].append({"to": "bedroom", "barrier": "window", "dir": "w", "cell": [7, 4]})
    sc["positions"] = {"Hinami": "bedroom", "Visitor": "garden"}
    sc["stations"] = {"Visitor": {"cell": list(visitor_cell)}}
    if hinami_cell is not None:
        sc["stations"]["Hinami"] = {"cell": list(hinami_cell)}
    if posture:
        sc["poses"] = {"Hinami": {"posture": posture}}
    return sc


def test_a_body_at_a_window_a_storey_up_is_seen_from_the_garden_above_the_sill():
    from world.spatial import body_visibility
    sc = _window_over_the_garden()
    up = body_visibility(sc, "Visitor", "Hinami")
    assert up["basis"] == "plan" and up["visible"] and up["through"] == "bedroom"
    assert up["hidden_below"] == "waist"          # head and shoulders over the sill
    down = body_visibility(sc, "Hinami", "Visitor")
    assert down["visible"]


def test_a_body_deep_in_the_room_is_hidden_by_the_sill_and_so_is_one_with_no_station():
    from world.spatial import body_visibility, visual_level_between
    deep = _window_over_the_garden(hinami_cell=(0, 1))
    assert not body_visibility(deep, "Visitor", "Hinami")["visible"]
    assert body_visibility(deep, "Visitor", "Hinami")["occluded_by"] == "the sill"
    assert visual_level_between(deep, "Visitor", "Hinami") == "none"
    # no station: the room's centre, never the open default that read the
    # bedroom as a pace from the lawn
    unplaced = _window_over_the_garden(hinami_cell=None)
    assert body_visibility(unplaced, "Visitor", "Hinami")["basis"] == "plan"


def test_lying_down_by_the_window_drops_below_the_sill():
    from world.spatial import body_visibility
    sc = _window_over_the_garden(posture="lying")
    assert not body_visibility(sc, "Visitor", "Hinami")["visible"]


def test_from_below_the_window_shows_who_is_at_it_never_the_room_behind():
    from world.spatial import observer_field, visible_adjacent_rooms
    sc = _window_over_the_garden()
    assert "bedroom" not in [r["room_id"] for r in visible_adjacent_rooms(sc, "garden")]
    assert "garden" in [r["room_id"] for r in visible_adjacent_rooms(sc, "bedroom")]
    # and the garden's field never lays the bedroom flat beside it
    assert "bedroom" not in observer_field(sc, "Visitor").offsets


def test_rooms_on_one_level_are_seen_between_as_they_always_were():
    from world.spatial import body_visibility
    sc = _garden_round_a_house()
    sc["positions"] = {"A": "hall", "B": "garden"}
    sc["stations"] = {"A": {"cell": [1, 2]}, "B": {"cell": [4, 7]}}
    assert body_visibility(sc, "A", "B")["basis"] != "plan"


# ---------------------------------------------------------------------------
# Step 3: drops as facts (2026-10-04)
# ---------------------------------------------------------------------------

def test_a_window_over_the_garden_is_a_drop_and_a_stair_never_is():
    from world.site_plan import drop_m, drops_from
    sc = _window_over_the_garden()
    assert drop_m(sc, "bedroom", "garden") == STOREY_M
    assert drop_m(sc, "garden", "bedroom") is None          # up is not a fall
    assert drop_m(sc, "bedroom", "hall") is None             # the stair down
    assert drops_from(sc, "bedroom") == {"garden": STOREY_M}


def test_the_director_is_shown_the_drop_before_it_writes():
    from agents.director import causal_world_index
    rooms = causal_world_index(_window_over_the_garden())["rooms"]
    assert rooms["bedroom"]["drops"] == {"garden": STOREY_M}
    assert "drops" not in rooms["garden"] and "drops" not in rooms["hall"]


def _moved(sc, who, to):
    after = copy.deepcopy(sc)
    after["positions"][who] = to
    return after


def test_a_body_out_of_an_open_window_is_reported_as_a_fall_and_a_shut_one_is_passed_by_nobody():
    from world.site_plan import report_drops
    shut = _window_over_the_garden()
    assert report_drops(shut, _moved(shut, "Hinami", "garden")) == []
    opened = _window_over_the_garden()
    for edge in opened["rooms"]["bedroom"]["adjacent"] + opened["rooms"]["garden"]["adjacent"]:
        if edge.get("barrier") == "window":
            edge["barrier"] = "open"
    notes = []
    assert report_drops(opened, _moved(opened, "Hinami", "garden"), notes) == [
        ("Hinami", "bedroom", "garden", STOREY_M)]
    assert "drop of 3 m" in notes[0]


def test_walking_down_the_stair_is_no_fall():
    from world.site_plan import report_drops
    sc = _window_over_the_garden()
    assert report_drops(sc, _moved(sc, "Hinami", "hall")) == []


def test_a_beat_that_drops_a_body_tells_the_director():
    sc = _window_over_the_garden()
    for edge in sc["rooms"]["bedroom"]["adjacent"]:
        if edge.get("barrier") == "window":
            edge["barrier"] = "open"
    report = []
    merge_scene_with_diff(sc, {"positions": {"Hinami": "garden"}},
                          clock_seconds=100.0, crossing_report=report)
    assert any("Hinami" in note and "drop" in note for note in report)
    # outside a beat (no clock) nothing is reported
    quiet = []
    merge_scene_with_diff(sc, {"positions": {"Hinami": "garden"}}, crossing_report=quiet)
    assert not any("drop" in note for note in quiet)


# ---------------------------------------------------------------------------
# Flight (2026-10-04)
# ---------------------------------------------------------------------------

def test_altitude_is_kept_under_an_indoor_ceiling_and_unbounded_outdoors():
    from world.site_plan import body_altitude_m
    from world.spatial import normalize_scene_stations
    sc = _garden_round_a_house()
    sc["positions"] = {"Bird": "garden", "Moth": "hall", "Cat": "hall"}
    sc["stations"] = {"Bird": {"altitude_m": 40}, "Moth": {"altitude_m": 9},
                      "Cat": {"altitude_m": 0}}
    normalize_scene_stations(sc)
    assert body_altitude_m(sc, "Bird") == 40.0
    assert body_altitude_m(sc, "Moth") == STOREY_M - 1.7      # under the ceiling
    assert "altitude_m" not in sc["stations"]["Cat"]


def test_a_body_aloft_sees_over_what_the_room_holds_and_is_out_of_reach():
    from world.spatial import body_visibility, proximity_rel
    sc = {"rooms": {"yard": {"name": "Yard", "desc": "A yard.", "exposure": "open",
                             "extent": {"w": 9, "d": 3}, "adjacent": [], "anchors": {
                                 "wall": {"desc": "a wall", "cell": [4, 0], "footprint": "run",
                                          "height": "full", "opacity": "opaque"}}}},
          "entities": {}, "positions": {"A": "yard", "B": "yard"},
          "stations": {"A": {"cell": [1, 1]}, "B": {"cell": [7, 1]}}}
    for c in range(3):
        sc["rooms"]["yard"]["anchors"][f"w{c}"] = {"desc": "a wall", "cell": [4, c],
                                                   "footprint": "point", "height": "full",
                                                   "opacity": "opaque"}
    assert not body_visibility(sc, "A", "B")["visible"]
    sc["stations"]["A"]["altitude_m"] = 6
    assert body_visibility(sc, "A", "B")["visible"]
    sc["stations"]["B"]["cell"] = [2, 1]
    assert proximity_rel(sc, "A", "B") != "within_reach"


def test_a_flier_in_the_garden_looks_straight_into_the_upper_window():
    from world.spatial import body_visibility
    sc = _window_over_the_garden(hinami_cell=(0, 1))      # deep in the room
    assert not body_visibility(sc, "Visitor", "Hinami")["visible"]
    sc["stations"]["Visitor"]["altitude_m"] = 3.0          # level with her floor
    assert body_visibility(sc, "Visitor", "Hinami")["visible"]


def test_the_director_sees_who_is_aloft():
    from agents.director import causal_world_index
    sc = _garden_round_a_house()
    sc["positions"] = {"Bird": "garden"}
    sc["stations"] = {"Bird": {"altitude_m": 12}}
    holds = causal_world_index(sc)["rooms"]["garden"]["holds"]
    assert holds[0]["aloft_m"] == 12.0


def test_a_low_flier_still_loses_the_body_pressed_behind_the_wall():
    from world.spatial import body_visibility
    sc = {"rooms": {"yard": {"name": "Yard", "desc": "A yard.", "exposure": "open",
                             "extent": {"w": 9, "d": 3}, "adjacent": [], "anchors": {}}},
          "entities": {}, "positions": {"A": "yard", "B": "yard"},
          "stations": {"A": {"cell": [1, 1], "altitude_m": 1.2}, "B": {"cell": [5, 1]}}}
    for c in range(3):
        sc["rooms"]["yard"]["anchors"][f"w{c}"] = {"desc": "a wall", "cell": [4, c],
                                                   "footprint": "point", "height": "full",
                                                   "opacity": "opaque"}
    assert not body_visibility(sc, "A", "B")["visible"]
    sc["stations"]["A"]["altitude_m"] = 8
    assert body_visibility(sc, "A", "B")["visible"]
