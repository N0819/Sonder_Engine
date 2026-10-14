"""A way between two rooms of one storey is a doorway, even into a stair hall.

Home 11 (chat 174, reviewed 2026-10-13): the opening wrote `vertical` and
`way: stair` on the doorway from each room into the stair hall beside it, on
the same storey, and the bearing normalizer mirrored the tag onto the hall's
side. Every reader then took a doorway for a flight: the storey plan drew no
door into any hall on three storeys, five of the six halls read as climbing
both ways, the far view stood the shrine 21 m tall, and the walk into a hall
cost a flight of six paces. Only a DECIDED site says what storey a room
stands on (`site_plan.one_storey`): an elevator whose rooms carry one level
and no site (chats 160/161) keeps its shaft. Hand-made rooms; the names are
illustrations, not the rule.
"""
from __future__ import annotations

import copy

import pytest

PLAN = "layout:house"


def _room(name, level, x, elev, w=4, d=3, adjacent=(), **extra):
    room = {"name": name, "desc": f"{name}.", "level": level, "exposure": "enclosed",
            "extent": {"w": w, "d": d}, "site": {"plan": PLAN, "x": x, "y": 0, "elev_m": elev},
            "adjacent": [dict(e) for e in adjacent]}
    room.update(extra)
    return room


def _house():
    """A main room and its cellar, the stair between them a hall on each
    storey; the opening tagged the main room's doorway into its hall."""
    return {"rooms": {
        "main": _room("the main room", 0, 0, 0.0, adjacent=[
            {"to": "hall_0", "dir": "e", "barrier": "open_door", "offset": 0.5,
             "vertical": "down", "way": "stair"}]),
        "hall_0": _room("the stair", 0, 4, 0.0, w=2, made_by_layout=True, adjacent=[
            {"to": "main", "dir": "w", "barrier": "open_door", "offset": 0.5},
            {"to": "hall_b", "barrier": "open", "vertical": "down", "way": "stair"}]),
        "hall_b": _room("the stair", -1, 4, -3.0, w=2, made_by_layout=True, adjacent=[
            {"to": "hall_0", "barrier": "open", "vertical": "up", "way": "stair"},
            {"to": "cellar", "dir": "w", "barrier": "open_door", "offset": 0.5}]),
        "cellar": _room("the cellar", -1, 0, -3.0, adjacent=[
            {"to": "hall_b", "dir": "e", "barrier": "open_door", "offset": 0.5}])},
        "positions": {}, "stations": {}, "entities": {}}


def _edge(scene, a, b):
    return next(e for e in scene["rooms"][a]["adjacent"] if e["to"] == b)


def test_the_merge_takes_the_tag_off_a_doorway_between_two_rooms_of_one_storey():
    from world.spatial import merge_scene_with_diff
    merged = merge_scene_with_diff(_house(), {})
    for a, b in (("main", "hall_0"), ("hall_0", "main")):
        edge = _edge(merged, a, b)
        assert "vertical" not in edge and "way" not in edge, edge
    assert (_edge(merged, "main", "hall_0")["dir"], _edge(merged, "hall_0", "main")["dir"]) == ("e", "w")
    # the flight between the two halls climbs, as it always did
    assert _edge(merged, "hall_0", "hall_b")["vertical"] == "down"
    assert _edge(merged, "hall_b", "hall_0")["vertical"] == "up"
    # and a beat that writes the tag again is taken back the same way
    again = merge_scene_with_diff(merged, {"rooms": {"main": {"adjacent": [
        {"to": "hall_0", "vertical": "down", "way": "stair"}]}}})
    assert "vertical" not in _edge(again, "main", "hall_0")
    assert "vertical" not in _edge(again, "hall_0", "main")


@pytest.mark.parametrize("how", ["unsited", "derived", "other_plan"])
def test_a_shaft_no_decided_site_puts_on_one_storey_keeps_its_way(how):
    """An elevator's car, its crash site and the shaft above all carried
    level -1 and no site (chats 160/161): only a decided site says two rooms
    stand on one storey."""
    from world.spatial import merge_scene_with_diff
    sc = _house()
    for rid in ("main", "hall_0"):
        if how == "unsited":
            sc["rooms"][rid].pop("site")
        elif how == "derived":
            sc["rooms"][rid]["site"]["derived"] = True
    if how == "other_plan":
        sc["rooms"]["hall_0"]["site"]["plan"] = "layout:elsewhere"
    merged = merge_scene_with_diff(sc, {})
    assert _edge(merged, "main", "hall_0").get("vertical") == "down"
    assert _edge(merged, "hall_0", "main").get("vertical") == "up"


def test_the_plan_draws_the_door_and_each_hall_climbs_only_its_own_flight():
    from web.storey_plan import room_look, storey_plan
    from world.spatial import merge_scene_with_diff
    sc = merge_scene_with_diff(_house(), {})
    ground = storey_plan(sc, PLAN, 0)
    assert frozenset(("main", "hall_0")) in {frozenset((d["a"], d["b"])) for d in ground["doors"]}
    spec = {"made_by_layout": True, "stair_kind": "straight"}
    assert room_look(sc, "hall_0", spec)["stair"] == {"kind": "straight", "up": False, "down": True}
    assert room_look(sc, "hall_b", spec)["stair"] == {"kind": "straight", "up": True, "down": False}


def test_a_stored_scene_reads_healed_before_its_next_commit(temp_db):
    """`apply_solved_plans` is how every beat reads the scene: Home 11's
    stored scene carried the tags until its next merge."""
    import time
    from world.structure import apply_solved_plans
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("House", "A house.", time.time()))
    sc = _house()
    _edge(sc, "hall_0", "main")["vertical"] = "up"
    apply_solved_plans(cid, sc)
    assert "vertical" not in _edge(sc, "main", "hall_0")
    assert "vertical" not in _edge(sc, "hall_0", "main")
    assert _edge(sc, "hall_0", "hall_b")["vertical"] == "down"


def test_the_passage_record_and_the_host_cannot_put_the_tag_back():
    from fastapi import HTTPException
    from web.world_routes import _apply_doorway_fields
    from world.spatial import merge_scene_with_diff, sync_scene_passages
    sc = merge_scene_with_diff(_house(), {})
    sc["passages"] = {"main|hall_0": {"rooms": ["main", "hall_0"], "vertical": "down"}}
    _edge(sc, "main", "hall_0")["passage"] = "main|hall_0"
    _edge(sc, "hall_0", "main")["passage"] = "main|hall_0"
    sync_scene_passages(sc)
    assert "vertical" not in sc["passages"]["main|hall_0"]
    assert "vertical" not in _edge(sc, "main", "hall_0")
    record = {"rooms": ["main", "hall_0"]}
    ea, eb = copy.deepcopy(_edge(sc, "main", "hall_0")), copy.deepcopy(_edge(sc, "hall_0", "main"))
    with pytest.raises(HTTPException) as refused:
        _apply_doorway_fields(sc, "main", "hall_0", record, ea, eb, {"vertical": "down"})
    assert refused.value.status_code == 400 and "one storey" in refused.value.detail
    # between the two halls, a storey apart, the host still may
    record = {"rooms": ["hall_0", "hall_b"]}
    ea, eb = copy.deepcopy(_edge(sc, "hall_0", "hall_b")), copy.deepcopy(_edge(sc, "hall_b", "hall_0"))
    _apply_doorway_fields(sc, "hall_0", "hall_b", record, ea, eb, {"vertical": "down"})
    assert record["vertical"] == "down"
