"""A place is a cell; an anchor is a cell with a name; a walk is a path.

Movement was a room a beat: a body arrived "in" a room and stood nowhere,
and a doorway was a place only when the spatial hand wrote a station for
it. The sight and sound fields already lay every room out as cells, one a
pace, so a walk is a path over those cells, through doorways into the next
room's, advanced by a budget of paces (the owner, 2026-09-15: bodies do not
have to land at anchors).
"""
from world.spatial import (blocked_cells, cell_path, door_cell, entry_cell,
                           held_cells, inside_the_door, paces_for, walk)


def _scene():
    return {
        "rooms": {
            "hall": {"name": "hall", "extent": {"w": 8, "d": 6}, "anchors": {
                "long_table": {"desc": "the long table", "dir": "n",
                               "footprint": "run", "height": "waist"},
                "rug": {"desc": "a rug", "footprint": "large", "height": "floor"},
            }, "adjacent": [{"to": "parlour", "barrier": "open_door", "dir": "e"}]},
            "parlour": {"name": "parlour", "extent": {"w": 6, "d": 6}, "anchors": {
                "hearth": {"desc": "the hearth", "dir": "e", "height": "waist"},
            }, "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "w"},
                            {"to": "yard", "barrier": "closed_door", "dir": "s"}]},
            "yard": {"name": "yard", "adjacent": [{"to": "parlour", "barrier": "closed_door", "dir": "n"}]},
        },
        "positions": {"Ada": "hall"},
        "stations": {"Ada": {"at": None, "near": [], "cell": [0, 5]}},
        "entities": {},
    }


def test_a_table_is_walked_round_and_a_rug_is_walked_over():
    sc = _scene()
    blocked = blocked_cells(sc, "hall")
    assert blocked and all(y == 0 or y == 1 for _x, y in blocked)  # the table hugs the north wall
    path = cell_path(sc, "hall", (0, 0), (7, 0))
    assert path and path[0] == (0, 0) and path[-1] == (7, 0)
    assert not any(c in blocked for c in path[1:-1])
    assert cell_path(sc, "hall", (3, 3), (3, 3)) == [(3, 3)]


def test_the_doorway_is_a_cell_and_arriving_puts_you_just_inside_it():
    sc = _scene()
    d = door_cell(sc, "hall", "parlour")
    assert d is not None and d[0] == 7          # on the hall's east wall
    e = entry_cell(sc, "parlour", "hall")
    assert e is not None and e[0] == 0          # on the parlour's west wall
    inside = inside_the_door(sc, "parlour", "hall")
    assert inside == (1, e[1])
    assert door_cell(sc, "yard", "parlour") is None or True  # a room with no extent still answers


def test_a_short_budget_leaves_the_body_mid_room_and_a_long_one_arrives():
    sc = _scene()
    short = walk(sc, "Ada", "parlour", paces=3)
    assert short["room"] == "hall" and not short["arrived"] and short["paces"] == 3
    assert short["cell"] != (0, 5)
    long = walk(sc, "Ada", "parlour", paces=40)
    assert long["room"] == "parlour" and long["arrived"] and long["crossed"] == ["parlour"]
    assert long["cell"] == inside_the_door(sc, "parlour", "hall")


def test_a_destination_anchor_or_cell_ends_the_walk_there():
    sc = _scene()
    at_hearth = walk(sc, "Ada", "parlour", to_anchor="hearth", paces=60)
    assert at_hearth["arrived"] and at_hearth["room"] == "parlour"
    assert at_hearth["cell"] not in blocked_cells(sc, "parlour")
    at_cell = walk(sc, "Ada", "parlour", to_cell=[3, 3], paces=60)
    assert at_cell["cell"] == (3, 3)
    within = walk(sc, "Ada", "hall", to_cell=[5, 5], paces=60)
    assert within["room"] == "hall" and within["cell"] == (5, 5) and within["crossed"] == []


def test_a_shut_door_is_no_route_and_a_budget_spent_at_the_door_waits_there():
    sc = _scene()
    assert walk(sc, "Ada", "yard", paces=60) is None
    just_at_door = walk(sc, "Ada", "parlour", paces=cell_path(sc, "hall", (0, 5), door_cell(sc, "hall", "parlour")).__len__() - 1)
    assert just_at_door["room"] == "hall" and just_at_door["cell"] == door_cell(sc, "hall", "parlour")


def test_paces_follow_the_beats_seconds_at_the_owners_pace():
    assert paces_for(20) == 36
    assert paces_for(None) == paces_for(10) == 18
    assert paces_for(0.1) == 1
    assert paces_for("nonsense") == paces_for(10)


def test_positioned_things_do_not_become_bodies_in_a_doorway():
    sc = _scene()
    door = door_cell(sc, "hall", "parlour")
    for key, kind in (("shelf", "fixture"), ("tin", "object")):
        sc["entities"][key] = {"name": key, "kind": kind}
        sc["positions"][key] = "hall"
        sc["stations"][key] = {"cell": list(door)}
    assert door not in held_cells(sc, "hall", "Ada")
    assert walk(sc, "Ada", "parlour", paces=40)["arrived"]
    # Their existence does not disable the separate fixture footprint floor.
    assert blocked_cells(sc, "hall")


def test_actual_body_and_unpromoted_charter_projection_still_hold_doorways():
    from world.charter_place import scene_with_charter_bodies

    for entity in (None, {"name": "Keeper", "kind": "person"},
                   {"name": "Keeper", "kind": "creature"}):
        sc = _scene()
        door = door_cell(sc, "hall", "parlour")
        if entity:
            sc["entities"]["Keeper"] = entity
        sc["positions"]["Keeper"] = "hall"
        sc["stations"]["Keeper"] = {"cell": list(door)}
        result = walk(sc, "Ada", "parlour", paces=40)
        assert not result["arrived"] and result["held_by"] == "doorway"

    sc = _scene()
    door = door_cell(sc, "hall", "parlour")
    projected = scene_with_charter_bodies(sc, {"charter:watch:keeper": {
        "key": "Keeper", "room": "hall", "station": {"cell": list(door)},
    }})
    assert "Keeper" not in sc["positions"]
    assert door in held_cells(projected, "hall", "Ada")
    assert walk(projected, "Ada", "parlour", paces=40)["held_by"] == "doorway"


def test_juns_causal_arrival_is_not_rewound_by_the_shelfs_standing_cell():
    """Reduced live Jun capture: the final shelf station occupies the door.

    Resolve walks the declared arrival against the composed route world;
    the shelf itself must not be mistaken for a person blocking that walk.
    """
    from copy import deepcopy
    from types import SimpleNamespace

    from agents.director import walk_declared
    from world.causal_program import fold_steps
    from world.spatial import merge_scene_with_diff

    scene = {
        "rooms": {
            "potting": {"size": "small", "adjacent": [
                {"to": "glasshouse", "barrier": "open_door", "dir": "e"}],
                # The shelf is PINNED to the doorway cell, which is what
                # this test is about. It landed there by the seed formula
                # until 2026-09-16, when the wall ring opened up
                # (`spatial_fov.DEFAULT_LANE`) and the seed re-rolled; a
                # test whose subject is "a fixture occupies the door" must
                # say so rather than depend on where a hash puts it.
                "anchors": {"worktop": {"desc": "Stone worktop"},
                            "shelf": {"desc": "Seed shelf", "cell": [3, 2]}}},
            "glasshouse": {"size": "small", "adjacent": [
                {"to": "potting", "barrier": "open_door", "dir": "w"}]},
        },
        "entities": {"shelf": {"kind": "fixture", "name": "Seed shelf"},
                     "worktop": {"kind": "fixture", "name": "Stone worktop"}},
        "positions": {"Ada": "potting", "Jun": "potting",
                      "shelf": "potting", "worktop": "potting"},
        "stations": {name: {"at": "worktop", "near": []}
                     for name in ("Ada", "Jun", "worktop")},
    }
    scene["stations"]["shelf"] = {"at": "shelf", "near": []}
    steps = [
        {"stage": "interpret", "chrono_id": 11, "patch": {"stations": {
            "Jun": {"at": "shelf", "near": ["shelf"]},
            "shelf": {"at": "shelf", "near": ["Jun"]}}}},
        {"stage": "interpret", "chrono_id": 13, "patch": {
            "positions": {"Jun": "glasshouse"},
            "stations": {"Jun": {"at": None, "near": []}}}},
        {"stage": "interpret", "chrono_id": 15, "patch": {"stations": {
            "Ada": {"at": "shelf", "near": []},
            "shelf": {"at": "shelf", "near": ["Ada"]}}}},
    ]
    diff = fold_steps(steps)
    diff["causal_steps"] = deepcopy(steps)
    route_scene = merge_scene_with_diff(scene, diff)
    from world.spatial import body_cell
    assert body_cell(route_scene, "shelf") == door_cell(
        route_scene, "potting", "glasshouse")
    warnings = []
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=warnings.append)
    out = {}
    result = walk_declared(ctx, scene, route_scene, diff, out, "Jun",
                           {"to_room": "glasshouse", "arrives": True}, "potting")
    assert result["arrived"]
    assert diff["positions"]["Jun"] == "glasshouse"
    assert not warnings


def _tower():
    """Three storeys joined by one stair, its foot and head on the walls the
    Larch Hill lookout put them on: kitchen (0) -> sleeping room (1) -> watch
    cabin (2)."""
    def room(level, w, d, edges):
        return {"name": None, "level": level, "extent": {"w": w, "d": d},
                "adjacent": edges}
    return {
        "rooms": {
            "kitchen": room(0, 5, 4, [{"to": "sleeping_room", "vertical": "up", "way": "stair",
                                        "barrier": "open", "dir": "n"}]),
            "sleeping_room": room(1, 5, 4, [
                {"to": "kitchen", "vertical": "down", "way": "stair", "barrier": "open", "dir": "s"},
                {"to": "watch_cabin", "vertical": "up", "way": "stair", "barrier": "open", "dir": "n"}]),
            "watch_cabin": room(2, 4, 4, [{"to": "sleeping_room", "vertical": "down", "way": "stair",
                                            "barrier": "open", "dir": "s"}]),
        },
        "positions": {"Ren": "kitchen", "Doctor": "kitchen"},
        "stations": {"Ren": {"cell": [0, 3]}, "Doctor": {"cell": [2, 2]}},
        "entities": {},
    }


def test_a_body_that_climbs_behind_you_does_not_bar_the_stair_it_arrives_by():
    """Live, Larch Hill turn 3 (chat 165, 2026-10-04): Ren climbed for the
    watch cabin with the Doctor on the stair behind her. The beat's diff
    ended him at the cabin's stairhead, and the walk -- which reads the room
    graph from the scene as the beat leaves it -- took that end-of-beat cell
    for a body standing in the doorway all beat: "Walk stopped: Ren Aoki's
    way toward 'watch_cabin' is held at 'sleeping_room' -- a body stands in
    the doorway", 18 of 99 paces, a floor short. Then she, stopped in the
    sleeping room's doorway, stopped him. A body the beat carries from one
    room to another is passing through, not standing in a door."""
    from world.spatial import door_cell as _door
    sc = _tower()
    route = {**sc, "positions": {"Ren": "watch_cabin", "Doctor": "watch_cabin"},
             "stations": {"Ren": {"cell": [0, 3]},
                          "Doctor": {"cell": list(_door(sc, "watch_cabin", "sleeping_room"))}}}
    barred = walk(route, "Ren", "watch_cabin", paces=99, from_room="kitchen", from_cell=[0, 3])
    assert barred["held_by"] == "doorway"           # what the engine did
    walked = walk(route, "Ren", "watch_cabin", paces=99, from_room="kitchen",
                  from_cell=[0, 3], passing={"Doctor"})
    assert walked["arrived"] and walked["room"] == "watch_cabin"
    # ...and arriving, nobody stands on anybody: the cell he ends on is his
    assert walked["cell"] != tuple(route["stations"]["Doctor"]["cell"])


def test_a_keeper_who_keeps_her_room_still_holds_the_stairhead():
    """The rule the passing set must not undo (Skerry Light turn 8,
    2026-09-15): a body planted in the stairhead all beat is the door."""
    from world.spatial import door_cell as _door
    sc = _tower()
    sc["positions"]["Keeper"] = "watch_cabin"
    sc["stations"]["Keeper"] = {"cell": list(_door(sc, "watch_cabin", "sleeping_room"))}
    result = walk(sc, "Ren", "watch_cabin", paces=99, passing={"Doctor"})
    assert not result["arrived"] and result["held_by"] == "doorway"


def test_who_is_passing_is_who_the_beat_moved_between_rooms():
    from agents.director import in_transit
    sc = _tower()
    route = {**sc, "positions": {"Ren": "watch_cabin", "Doctor": "kitchen", "New": "kitchen"}}
    assert in_transit(sc, route) == {"Ren"}
