"""A stair is a room of its own on every storey it joins.

The owner's choice of 2026-10-12, asked between a stair standing in its room
and the layout lab's own model: "Its own stairwell room per storey". The
owner's shrine (chat 168): "there are no genned stairs as far as i can
tell" -- the solver laid a hall for every stair and the bridge left each off
the plan, writing the stair as one vertical edge between two rooms with a
landing cell. A hall is now a planned room the layout tier makes
(`structure.LAYOUT_MADE_KEY`): planted by the tier's one write, joined to
the room it serves and to the hall above or below, replacing the plan's own
stair -- and no plan once its building is re-planned or a re-solve no longer
makes it. How the bridge lays the halls out is pinned beside the rest of the
solve (`tests/test_a_planned_building_is_laid_out_by_relations.py`).
"""
from __future__ import annotations

import copy
import time

from world.structure import (LAYOUT_MADE_KEY, plant_structure, registry_rows,
                             write_planned_layout)

PLAN = "layout:hall"


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Stairs", "A house.", time.time()))


def _plant(cid):
    plant_structure(cid, {"key": "town", "name": "Town"}, {
        "hall": {"name": "the Hall", "purpose": "a hall", "exposure": "enclosed",
                 "adjacent": [{"to": "loft", "vertical": "up", "way": "stair"},
                              {"to": "street", "barrier": "open_door", "dir": "s"}]},
        "loft": {"name": "the Loft", "purpose": "a loft",
                 "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"}]},
        "street": {"name": "the Street", "purpose": "the street", "exposure": "open",
                   "adjacent": [{"to": "hall", "dir": "n"}]}})


def _site(x, y, level):
    return {"plan": PLAN, "x": x, "y": y, "elev_m": 3.0 * level}


def _hall(uid, serves, level, ways):
    return {"room": {"name": "the stair", "purpose": "the stair", "structure": "town",
                     LAYOUT_MADE_KEY: True, "stair_of": [serves]},
            "geometry": {"extent": {"w": 2, "d": 3}, "shape": "rectangle", "level": level,
                         "exposure": "enclosed", "site": _site(0, 0, level)},
            "anchors": {}, "edges": {}, "made_edges": ways,
            "layout": {"plan": PLAN, "made_edges": sorted(ways)}}


def _solve(halls=("hall__loft_stair_0", "hall__loft_stair_1")):
    low, high = halls
    return {
        "hall": {"geometry": {"extent": {"w": 6, "d": 5}, "level": 0, "site": _site(2, 0, 0)},
                 "anchors": {}, "edges": {},
                 "made_edges": {low: {"barrier": "open", "dir": "w", "offset": 0.5, "width": 3}},
                 "layout": {"plan": PLAN, "made_edges": [low], "replaced": ["loft"]}},
        "loft": {"geometry": {"extent": {"w": 6, "d": 5}, "level": 1, "site": _site(2, 0, 1)},
                 "anchors": {}, "edges": {},
                 "made_edges": {high: {"barrier": "open", "dir": "w", "offset": 0.5, "width": 3}},
                 "layout": {"plan": PLAN, "made_edges": [high], "replaced": ["hall"]}},
        low: _hall(low, "hall", 0, {
            "hall": {"barrier": "open", "dir": "e", "offset": 0.5, "width": 3},
            high: {"barrier": "open", "vertical": "up", "way": "stair"}}),
        high: _hall(high, "loft", 1, {
            "loft": {"barrier": "open", "dir": "e", "offset": 0.5, "width": 3},
            low: {"barrier": "open", "vertical": "down", "way": "stair"}}),
    }


def _plans(cid):
    return {uid: entry["planned"] for uid, entry in registry_rows(cid).items()}


def _expected(cid):
    return {uid: plan for uid, plan in _plans(cid).items() if uid in ("hall", "loft")}


def test_the_solve_plants_each_hall_and_its_ways_replace_the_plans_stair(temp_db):
    cid = _chat(temp_db)
    _plant(cid)
    assert write_planned_layout(cid, _solve(), expected=_expected(cid))
    plans = _plans(cid)
    low, high = plans["hall__loft_stair_0"], plans["hall__loft_stair_1"]
    assert low[LAYOUT_MADE_KEY] and low["stair_of"] == ["hall"] and low["level"] == 0
    assert {e["to"]: e.get("vertical") for e in low["adjacent"]} == {
        "hall": None, "hall__loft_stair_1": "up"}
    ways = {e["to"] for e in plans["hall"]["adjacent"]}
    assert ways == {"hall__loft_stair_0", "street"}, "the plan's own stair is replaced"
    assert {e["to"] for e in plans["loft"]["adjacent"]} == {"hall__loft_stair_1"}
    # and a second write of the same solve changes nothing
    before = copy.deepcopy(plans)
    assert write_planned_layout(cid, _solve(), expected=_expected(cid))
    assert _plans(cid) == before


def test_a_hall_is_no_plan_once_its_building_is_re_planned(temp_db):
    cid = _chat(temp_db)
    _plant(cid)
    assert write_planned_layout(cid, _solve(), expected=_expected(cid))
    _plant(cid)                                # the Room plans the house again
    plans = _plans(cid)
    assert plans["hall__loft_stair_0"] is None and plans["hall__loft_stair_1"] is None
    assert {e["to"] for e in plans["hall"]["adjacent"]} == {"loft", "street"}
    # the row itself stays: every registry identity does
    assert "hall__loft_stair_0" in registry_rows(cid)


def test_a_re_solve_withdraws_a_hall_it_no_longer_makes(temp_db):
    cid = _chat(temp_db)
    _plant(cid)
    assert write_planned_layout(cid, _solve(), expected=_expected(cid))
    moved = ("hall__loft_stair_b0", "hall__loft_stair_b1")
    assert write_planned_layout(cid, _solve(moved), expected=_expected(cid))
    plans = _plans(cid)
    assert plans["hall__loft_stair_0"] is None and plans["hall__loft_stair_1"] is None
    assert plans["hall__loft_stair_b0"][LAYOUT_MADE_KEY]
    assert {e["to"] for e in plans["hall"]["adjacent"]} == {"hall__loft_stair_b0", "street"}


def test_a_made_room_is_never_planted_over_a_room_somebody_planned(temp_db):
    cid = _chat(temp_db)
    _plant(cid)
    solve = _solve(("street", "hall__loft_stair_1"))
    before = _plans(cid)
    assert write_planned_layout(cid, solve, expected=_expected(cid)) is False
    assert _plans(cid) == before


def test_a_building_is_its_planned_rooms_and_never_the_halls_a_solve_made(temp_db):
    from world import layout_bridge as lb
    from world.structure import _planned_specs
    cid = _chat(temp_db)
    _plant(cid)
    assert write_planned_layout(cid, _solve(), expected=_expected(cid))
    _plant(cid)
    specs = _planned_specs(cid)
    assert "hall__loft_stair_0" not in specs, "a hall of a re-planned building is no plan"
    # and a sited hall the specs still hold is never a room of the building
    made = copy.deepcopy(_solve()["hall__loft_stair_0"])
    specs["hall__loft_stair_0"] = ("the stair", dict(made["room"], **made["geometry"]))
    scene = {"rooms": {"street": {"name": "the Street", "desc": "A street."}},
             "positions": {}, "entities": {}}
    (b,) = lb.plan_buildings(specs, scene)
    assert b["rooms"] == ["hall", "loft"] and b["refusal"] is None
