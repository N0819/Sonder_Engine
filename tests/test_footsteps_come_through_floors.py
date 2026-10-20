"""FOOTSTEPS AND THUDS COME THROUGH FLOORS (DESIGN_SOUND_FIELD.md § 12, wave A,
2026-10-20).

Impact sound travels through a building's structure far better than speech
through the air: on a timber floor a footfall above is plainly heard below,
a stone floor carries less, a soft step carries less again. A body moving on
a storey makes footfalls heard on the storey below and in the rooms beside
it, graded by the floor's material and the gait (sneak, walk, run). The
listener learns that someone moves overhead -- never who.

The scene is chat 177's cottage as its scene holds it: a stone-floored
kitchen under a timber upper storey -- Mellisande's room, a landing and a
second room -- laid out on one site plan, with a stair hall on each storey
and NO room declaring that it lies `over` another. In chat 177 turn 19
Mellisande climbed from the kitchen to the room over it and Hinami, under
the boards, heard nothing: the plan's storeys were never read for a
footfall, and her walk was a `positions` patch with no travel record.
"""

from __future__ import annotations

from agents import composer
from world.spatial import (FLOOR_IMPACT_DB, FOOTFALL_FLANKING_DB,
                           TREAD_RUN_DB, TREAD_SNEAK_DB, footfall_db,
                           normalize_sensory_event, tread_events, tread_gait)

PLAN = "layout:cottage"


def _room(name, level, x, y, w, d, floor, adjacent=()):
    return {"name": name, "level": level, "floor": floor,
            "exposure": "enclosed", "extent": {"w": w, "d": d},
            "site": {"plan": PLAN, "x": x, "y": y, "elev_m": 3.0 * level},
            "anchors": {}, "adjacent": list(adjacent)}


def _cottage(upper_floor="timber"):
    door = {"barrier": "closed_door", "material": "wood"}
    rooms = {
        "kitchen": _room("The Kitchen", 0, 0, 0, 5, 5, "stone",
                         [{"to": "stair_foot", "barrier": "open", "dir": "e"}]),
        "stair_foot": _room("The Stair Foot", 0, 5, 0, 2, 5, None,
                            [{"to": "kitchen", "barrier": "open", "dir": "w"},
                             {"to": "stair_head", "barrier": "open",
                              "vertical": "up", "way": "stair"}]),
        "stair_head": _room("The Stair Head", 1, 5, 0, 2, 5, upper_floor,
                            [{"to": "stair_foot", "barrier": "open",
                              "vertical": "down", "way": "stair"},
                             {"to": "landing", "barrier": "open", "dir": "w"}]),
        "landing": _room("The Landing", 1, 3, 3, 2, 2, upper_floor,
                         [{"to": "bedchamber", "dir": "n", **door},
                          {"to": "spare", "dir": "w", **door},
                          {"to": "stair_head", "barrier": "open", "dir": "e"}]),
        "bedchamber": _room("Mellisande's Room", 1, 0, 0, 5, 3, upper_floor,
                            [{"to": "landing", "dir": "s", **door}]),
        "spare": _room("The Second Room", 1, 0, 3, 3, 2, upper_floor,
                       [{"to": "landing", "dir": "e", **door}]),
    }
    return {"rooms": rooms,
            "positions": {"Mellisande": "bedchamber", "Hinami": "kitchen",
                          "Ivo": "spare"},
            "stations": {"Mellisande": {"cell": [2, 1]},
                         "Hinami": {"cell": [2, 2]}, "Ivo": {"cell": [1, 0]}},
            "entities": {}, "poses": {}, "orientation": {}, "contained": {}}


def _by_room(events):
    return {e["room"]: e for e in events}


def test_a_walk_over_the_kitchen_is_heard_in_the_kitchen():
    """No room declares `over`: the plan says the upper room lies over the
    kitchen, and the timber floor carries a walk into it."""
    sc = _cottage()
    events = _by_room(tread_events(sc, {"Mellisande": "walk"}))
    assert "kitchen" in events
    below = events["kitchen"]
    assert below["db"] == FLOOR_IMPACT_DB["timber"]
    assert below["detail"] == "footsteps overhead"
    kept = normalize_sensory_event(below, sc["rooms"])
    heard = composer.ambient_percepts([dict(kept, desc=kept["detail"])],
                                      "kitchen", order_key=0)
    assert heard and heard[0].data["desc"] == "footsteps overhead"
    # It names nobody: the listener learns that someone moves overhead.
    for event in events.values():
        assert "Mellisande" not in event["detail"]
    # The complement: the stair head lies over the stair foot, and a stair
    # joins them -- the tread goes down it through the air (the near
    # field), never as a footfall through a floor nobody walks under.
    sc["positions"]["Mellisande"] = "stair_head"
    sc["stations"]["Mellisande"] = {"cell": [0, 2]}
    events = _by_room(tread_events(sc, {"Mellisande": "walk"}))
    assert "stair_foot" not in events
    assert "landing" not in events            # an opening: the air's


def test_a_floor_carries_a_footfall_into_the_room_beside():
    """A walk on the timber of Mellisande's room reaches the room beside it
    through the floor and the wall it shares, and the landing's through its
    shut door -- some fifteen decibels under what falls straight down."""
    sc = _cottage()
    events = _by_room(tread_events(sc, {"Mellisande": "walk"}))
    assert events["spare"]["detail"] == "footsteps beyond the wall"
    assert events["spare"]["db"] == FLOOR_IMPACT_DB["timber"] - FOOTFALL_FLANKING_DB
    assert events["landing"]["detail"] == "footsteps through the door"


def test_the_gait_and_the_floor_grade_the_footfall():
    sc = _cottage()
    assert tread_gait("sneak") == "sneak" and tread_gait("stroll") == "walk"
    run = _by_room(tread_events(sc, {"Mellisande": "run"}))
    assert run["kitchen"]["db"] == FLOOR_IMPACT_DB["timber"] + TREAD_RUN_DB
    assert run["kitchen"]["detail"] == "running footsteps overhead"
    # A sneak on timber still creaks through to the kitchen, softly; it
    # makes no tread in its own room, and none reaches the room beside.
    sneak = tread_events(sc, {"Mellisande": "sneak"})
    by = _by_room(sneak)
    assert by["kitchen"]["db"] == FLOOR_IMPACT_DB["timber"] - TREAD_SNEAK_DB
    assert by["kitchen"]["detail"] == "careful footsteps overhead"
    assert "bedchamber" not in by and "spare" not in by
    # Stone upstairs: a walk is heard below, a sneak is not, and nothing
    # reaches the room beside.
    stone = _cottage("stone")
    assert footfall_db(stone, "bedchamber", "walk") == FLOOR_IMPACT_DB["stone"]
    by = _by_room(tread_events(stone, {"Mellisande": "walk"}))
    assert "kitchen" in by and "spare" not in by
    assert "kitchen" not in _by_room(tread_events(stone, {"Mellisande": "sneak"}))


def test_a_walk_with_no_travel_record_still_makes_footfalls():
    """Chat 177 turn 19: the beat moved Mellisande to the room over the
    kitchen by a `positions` patch and no walk; her footfalls are read off
    the beat's room change. A carried body does not walk."""
    from agents.perception import _beat_movers

    class Ctx(dict):
        pass

    before = _cottage()
    before["positions"]["Mellisande"] = "kitchen"
    after = _cottage()
    ctx = Ctx(director_resolve={"travel": {"advanced": []}})
    movers = _beat_movers(ctx, before, after, bodies=["Mellisande", "Hinami"])
    assert movers == {"Mellisande": "walk"}
    assert "kitchen" in _by_room(tread_events(after, movers))
    carried = _cottage()
    carried["contained"] = {"Mellisande": "Hinami"}
    ctx = Ctx(director_resolve={"travel": {"advanced": []}})
    assert _beat_movers(ctx, before, carried, bodies=["Mellisande"]) == {}
