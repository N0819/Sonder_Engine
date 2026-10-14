"""A straight stair is entered at the foot of its flight and left at its head.

Home 11 (chat 174, reviewed 2026-10-13): the solver spread every doorway
evenly along the wall a room shares with a stair hall, so a doorway opened
onto the middle of a flight -- over the lab's four baselines, Home 11 and
the solver's own test house, 12 of 29 enclosed stair doorways did -- and the
plan drew the treads over the whole hall, which takes the landing beside
the flight too (Home 11's basement hall was ten by five round a two by five
flight). The solver now opens each doorway of an enclosed straight stair's
hall at the end of the flight its storey takes, the bridge writes the flight
into the hall, and the plan draws the treads on it. Hand-made specs and the
lab's own baselines; the names are illustrations, not the rule.
"""
from __future__ import annotations

import json
from pathlib import Path

from world.layout_solver import Rect, solve

_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


def _hall_side(door, halls):
    if door["a"] in halls:
        return door["a"], tuple(door["cell"])
    if door["b"] in halls:
        dx, dy = _STEP[door["side"]]
        return door["b"], (door["cell"][0] + dx, door["cell"][1] + dy)
    return None, None


def _ends_hold(lay):
    """Every doorway of every enclosed straight stair's halls, judged: off
    the flight, or on it at the end its storey takes."""
    judged = 0
    for well in lay.stairwells:
        if well["kind"] != "straight" or not well["enclosed"]:
            continue
        foot, head = {tuple(c) for c in well["foot"]}, {tuple(c) for c in well["head"]}
        flight = Rect(**well["rect"]).cells()
        assert foot | head <= flight and not foot & head
        halls = set(well["halls"].values())
        low, top = min(well["levels"]), max(well["levels"])
        for door in lay.doors:
            hall, cell = _hall_side(door, halls)
            if hall is None or door.get("kind") == "open":
                continue
            lv = door["level"]
            end = foot if lv == low else head if lv == top else foot | head
            if cell in flight and cell not in end:
                assert any("could not open at the end of the flight" in w for w in lay.warnings), \
                    (well["id"], door)
                continue
            judged += 1
    return judged


def test_a_straight_stair_is_entered_at_its_foot_and_left_at_its_head():
    from tests.test_layout_solver import HOUSE
    lay = solve(HOUSE)
    (well,) = [s for s in lay.stairwells if s["id"] == "loft_stair"]
    assert well["kind"] == "straight" and well["enclosed"]
    assert _ends_hold(lay) == 2


def test_the_labs_baselines_open_no_stair_doorway_onto_the_middle_of_a_flight():
    """The owner's preferred shrine and the three fresh runs of its brief:
    one roof stair of fresh run 2 is met by both its rooms at one end, and
    keeps its doorway with a warning; every other doorway holds."""
    root = Path(__file__).resolve().parent.parent / "tools" / "layout_lab" / "baselines"
    paths = [root / "shrine_rewritten.json", *sorted((root / "fresh_runs").glob("*.json"))]
    assert len(paths) == 4
    for path in paths:
        lay = solve(json.loads(path.read_text())["spec"])
        assert _ends_hold(lay) >= 4, path.name


def _laid():
    from tests.test_a_planned_building_is_laid_out_by_relations import HALLS, _solve
    from world import layout_bridge as lb
    b, inv, spec, layout = _solve()
    solved, _report = lb.planned_layout(b, spec, layout, inventory=inv)
    return solved, HALLS


def test_each_hall_carries_its_flight_the_same_cells_on_every_storey():
    solved, halls = _laid()
    on_plan = set()
    for uid in halls:
        room, geo = solved[uid]["room"], solved[uid]["geometry"]
        flight = room["flight"]
        assert 0 <= flight["x"] and flight["x"] + flight["w"] <= geo["extent"]["w"]
        assert 0 <= flight["y"] and flight["y"] + flight["d"] <= geo["extent"]["d"]
        site = geo["site"]
        on_plan.add((site["x"] + flight["x"], site["y"] + flight["y"], flight["w"], flight["d"]))
    assert len(on_plan) == 1, on_plan


def test_the_plan_draws_the_treads_on_the_flight_and_an_old_plan_as_it_was():
    from tests.test_a_storey_is_drawn_as_the_lab_draws_it import PLAN, SPECS, _scene
    from web.storey_plan import room_look, storey_plan
    specs = dict(SPECS)
    name, spec = specs["stair_0"]
    specs["stair_0"] = (name, dict(spec, flight={"x": 0, "y": 1, "w": 2, "d": 2}))
    (stair,) = storey_plan(_scene(), PLAN, 0, specs)["stairs"]
    assert stair["rects"] == [{"x": 4, "y": 1, "w": 2, "d": 2}]
    assert "flight" not in stair
    assert room_look(_scene(), "stair_0", specs["stair_0"][1])["stair"]["flight"] == \
        {"x": 0, "y": 1, "w": 2, "d": 2}
    (stair,) = storey_plan(_scene(), PLAN, 0, SPECS)["stairs"]
    assert stair["rects"] == [{"x": 4, "y": 0, "w": 2, "d": 3}]
    assert "flight" not in room_look(_scene(), "stair_0", SPECS["stair_0"][1])["stair"]


#: A stair through three storeys whose middle storey's hall has a doorway
#: where the storey below holds one (the review's reproduction, seed 3).
TALL = {"name": "t", "front": "s", "entrance": {"room": "r0", "kind": "door"},
        "rooms": [{"id": "r0", "name": "Room 0", "level": 0, "purpose": "living"},
                  {"id": "r1", "name": "Room 1", "level": 1, "purpose": "bedroom",
                   "joins": [{"to": "o1_0"}]},
                  {"id": "o1_0", "name": "Other 1", "level": 1, "purpose": "storage"},
                  {"id": "r2", "name": "Room 2", "level": 2, "purpose": "bedroom",
                   "joins": [{"to": "o2_0"}, {"to": "o2_1"}]},
                  {"id": "o2_0", "name": "Other 2a", "level": 2, "purpose": "storage"},
                  {"id": "o2_1", "name": "Other 2b", "level": 2, "purpose": "storage"}],
        "stairs": [{"id": "s0", "name": "Main stair", "from": "r0", "to": "r1",
                    "enclosed": True, "door": "door", "kind": "straight"},
                   {"id": "s1", "name": "Main stair", "from": "r1", "to": "r2",
                    "enclosed": True, "door": "door", "kind": "straight"}]}


def test_a_stair_through_three_storeys_opens_at_its_ends_on_every_storey():
    """Each storey's hall is a place of its own: a doorway taken on one
    storey held the same cell on every other, and a middle storey's doorway
    was pushed onto the middle of the flight (review of 2026-10-13)."""
    for seed in range(1, 9):
        lay = solve(TALL, seed=seed)
        assert not [w for w in lay.warnings if "could not open at the end" in w], seed
        _ends_hold(lay)
