"""The ground round a building holds together, or the places that fail are dropped.

Home 10 (chat 173, 2026-10-13): the layout tier laid the mountain path out
of the hall's front door THROUGH the court the hall opens onto -- cutting the
court in two floors -- and stood the storehouse apart, joined to a walk the
solver never laid, so it was written with no doorway at all. No answer the
closed vocabulary allows laid that plan: the fault was in code. The class
was wider -- every chat with recorded layout answers wrote grounds that did
not hold together (Home 6: six breaches, Home 9: one), and the tier's own
farm fixture broke the contract its test claimed. Design A6: generator
rules state where each kind of place stands, a deterministic floor reads
the scene the solve would write through the world's own readers
(`layout_bridge.ground_breaches`), and where the ground still fails only the
places that fail are dropped (the owner's ruling of 2026-10-13). A neutral
court shaped like Home 10's plan, the tier's farm, and a kitchen shaped like
Home 9's; the names are illustrations, not the rule.
"""
from __future__ import annotations

import copy

import pytest

from world import layout_bridge as lb
from world.spatial import _cells_connected

E = "enclosed"
COURT_SPECS = {
    "hall": ("the Hall", {
        "purpose": "a hall with an altar", "structure": "court", "exposure": E,
        "adjacent": [{"to": "court", "dir": "s", "barrier": "open_door"},
                     {"to": "side", "dir": "e", "barrier": "closed_door"},
                     {"to": "loft", "vertical": "up", "way": "ladder"}]}),
    "side": ("the Side Room", {"purpose": "a sleeping room", "structure": "court",
                               "exposure": E,
                               "adjacent": [{"to": "hall", "dir": "w", "barrier": "closed_door"}]}),
    "loft": ("the Loft", {"purpose": "a loft", "structure": "court", "exposure": E,
                          "adjacent": [{"to": "hall", "vertical": "down", "way": "ladder"}]}),
    "court": ("the Court", {"purpose": "a stone court", "structure": "court", "exposure": "open",
                            "adjacent": [{"to": "hall", "dir": "n"}, {"to": "shed", "dir": "w"},
                                         {"to": "lane", "dir": "s"}]}),
    "lane": ("the Lane", {"purpose": "a stair of stone down the hill", "structure": "court",
                          "exposure": "open", "adjacent": [{"to": "court", "dir": "n"}]}),
    "shed": ("the Shed", {"purpose": "a storehouse", "structure": "court",
                          "adjacent": [{"to": "court", "dir": "e"}]}),
}
COURT_SORT = {
    "rooms": [{"id": "hall", "fixtures": [{"id": "altar", "name": "the altar", "mount": "floor"}]},
              {"id": "side", "fixtures": [{"id": "futon", "name": "a futon", "mount": "floor"}]},
              {"id": "loft", "fixtures": []}],
    "stairs": [{"from": "hall", "to": "loft", "enclosed": False}],
    "grounds": [{"id": "court", "is": "open"}, {"id": "lane", "is": "way"},
                {"id": "shed", "is": "outbuilding"}]}
COURT_RELATE = {
    "rooms": [{"id": "hall", "purpose": "hall", "fixtures": [{"id": "altar", "kind": "altar", "at": "n"}]},
              {"id": "side", "purpose": "bedroom", "fixtures": [{"id": "futon", "kind": "bed", "at": "e"}]},
              {"id": "loft", "purpose": "storage", "fixtures": []}],
    "stairs": [{"from": "hall", "to": "loft", "from_at": "n", "to_at": "n", "kind": "ladder"}],
    "grounds": [{"id": "court", "where": "s"},
                {"id": "lane", "from": "entrance", "to": "court"},
                {"id": "shed", "side": "w"}]}
SCENE = {"rooms": {}, "positions": {}, "entities": {}}


def _court(relate=COURT_RELATE, specs=COURT_SPECS):
    found = lb.plan_buildings(copy.deepcopy(specs), copy.deepcopy(SCENE), grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(COURT_SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    layout, refused = lb.solve_for(b, spec)
    solved, report = lb.planned_layout(b, spec, layout)
    return b, spec, layout, refused, solved, report


def _world(b, solved, pid):
    return lb._world_cells(b, pid, solved[pid]["geometry"])


_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


@pytest.mark.parametrize("said_from", ["entrance", None])
def test_a_way_the_plan_joins_to_open_ground_leaves_it_and_never_splits_it(said_from):
    """Whatever an answer says, the approach is the way the entrance opens
    onto; a way the plan joins only to open ground leaves that ground past
    its far edge, on the side the plan states -- never through it."""
    relate = copy.deepcopy(COURT_RELATE)
    for g in relate["grounds"]:
        if g["id"] == "lane" and said_from is None:
            g.pop("from")
    b, spec, layout, refused, solved, _report = _court(relate)
    assert refused == []
    lane = next(w for w in spec["grounds"]["ways"] if w["id"] == "lane")
    assert lane["from"] == "court" and lane.get("side") == "s"
    court = _world(b, solved, "court")
    assert _cells_connected(court), "the court is one floor"
    door = next(d for d in layout.doors if d["b"] == "entrance")
    threshold = (door["cell"][0] + _STEP[door["side"]][0], door["cell"][1] + _STEP[door["side"]][1])
    assert threshold in court, "the hall opens onto the court"
    lane_cells = _world(b, solved, "lane")
    assert min(y for _x, y in lane_cells) > max(y for _x, y in court)
    assert any((x, y - 1) in court for x, y in lane_cells), "the lane leaves the court's south edge"


def test_the_same_court_is_laid_whatever_the_answer_said_the_lane_runs_from():
    relate = copy.deepcopy(COURT_RELATE)
    for g in relate["grounds"]:
        if g["id"] == "lane":
            g.pop("from")
    said = _court()[4]
    unsaid = _court(relate)[4]
    for pid in ("court", "lane", "shed", "hall"):
        assert said[pid]["geometry"] == unsaid[pid]["geometry"], pid


def test_an_outbuilding_stands_on_the_open_ground_the_plan_joins_it_to():
    """Joined to open ground and to no room, the shed stands in that ground,
    toward the end the plan bears it to, and opens onto it -- never apart
    on a walk nobody lays."""
    b, spec, layout, refused, solved, _report = _court()
    assert refused == []
    shed = next(r for r in spec["rooms"] if r["id"] == "shed")
    assert [j["to"] for j in shed["joins"]] == ["court"]
    assert "shed__way" not in {w["id"] for w in spec["grounds"]["ways"]}
    block = next(x for x in spec["blocks"] if x["id"] == "shed")
    assert block.get("toward") == "w"
    assert "court" in solved["shed"]["edges"] and "shed" in solved["court"]["edges"]
    assert lb.ground_breaches(b, spec, layout) == []


def test_ground_that_does_not_hold_together_is_refused():
    """The court laid with its lane run out of the hall's front door through
    it, as the tier laid Home 10's: the floor names what breaks."""
    b, spec, _layout, _refused, _solved, _report = _court()
    from world.layout_solver import solve
    for w in spec["grounds"]["ways"]:
        if w["id"] == "lane":
            w["from"] = "entrance"
            w.pop("side", None)
    layout = solve(spec)
    words = [w for w, _place in lb.ground_breaches(b, spec, layout)]
    assert words and any("court" in w for w in words), words
    assert set(words) <= set(lb.refusals(b, spec, layout))


def test_only_the_places_that_fail_are_dropped(monkeypatch):
    """Where the ground still fails, the places that fail are taken out and
    the rest laid -- the owner's ruling of 2026-10-13 -- with no call beyond
    the brief, the sort and the relate."""
    from agents import director_layout as dl
    real = lb.ground_breaches

    def breaches(building, spec, layout):
        found = real(building, spec, layout)
        if "shed" in (spec.get("ground_is") or {}):
            found = found + [("shed is not one floor", "shed")]
        return found

    monkeypatch.setattr(lb, "ground_breaches", breaches)
    calls = []

    def call(step, system, payload):
        calls.append(step)
        if step.endswith("_brief"):
            return {"brief": ""}
        return copy.deepcopy(COURT_SORT if step.endswith("_sort") else COURT_RELATE)

    found = lb.plan_buildings(copy.deepcopy(COURT_SPECS), copy.deepcopy(SCENE), grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    spec, _layout, _inventory, refused = dl.lay_out(b, call, "en")
    assert refused == []
    assert spec["places_dropped"] == ["shed"]
    assert spec["grounds_dropped"] == ["shed is not one floor"]
    assert set(spec["ground_is"]) == {"court", "lane"}
    assert len(calls) == 3


def test_a_way_with_no_start_is_no_approach():
    """A way nothing opens onto and nothing leads from has nothing to run
    from; it was laid as a second approach out of the front door."""
    from tests.test_layout_solver import HOUSE
    from world.layout_solver import solve
    spec = copy.deepcopy(HOUSE)
    spec.setdefault("grounds", {}).setdefault("ways", []).append({"id": "lane", "name": "the lane"})
    lay = solve(spec)
    assert "lane" not in lay.ways
    assert any("has nothing to run from" in w for w in lay.warnings)


# ---- the farm (`tests/test_a_building_stands_in_its_grounds.py`) ---------

def test_a_thing_the_plan_joins_to_a_room_stands_at_its_door():
    """The plan joins the well to the kitchen: it stands across the
    kitchen's door, its doorway onto the kitchen the cell across the
    threshold -- it stood a pace off (the farm), or eighteen paces (Home 11)."""
    from tests.test_a_building_stands_in_its_grounds import _laid
    b, spec, layout, refused, solved, _report = _laid()
    assert refused == []
    well = next(f for f in spec["grounds"]["features"] if f["id"] == "well")
    assert well["at_door"] == {"room": "kitchen", "onto": "garden"}
    assert not {"by", "side"} & set(well)
    door = next(d for d in layout.doors if d.get("outside") and d["a"] == "kitchen")
    threshold = (door["cell"][0] + _STEP[door["side"]][0], door["cell"][1] + _STEP[door["side"]][1])
    rect = next(f["rect"] for f in layout.features if f["id"] == "well")
    assert threshold in rect.cells()
    assert threshold in _world(b, solved, "well")
    edge = solved["well"]["edges"]["kitchen"]
    assert edge["dir"] == {"n": "s", "s": "n", "e": "w", "w": "e"}[door["side"]]


def test_an_outbuilding_reached_from_a_room_owns_its_walk():
    """The privy's walk to the washroom is its own floor: the washroom's
    door opens onto the privy, its doorway pinned across the threshold."""
    from tests.test_a_building_stands_in_its_grounds import _laid
    b, spec, layout, refused, solved, _report = _laid()
    assert refused == []
    privy = _world(b, solved, "privy")
    assert _cells_connected(privy)
    block = next(r for r in layout.floors[0]["privy"])
    assert len(privy) > block.w * block.d, "the walk is part of it"
    door = next(d for d in layout.doors if d.get("outside") and d["a"] == "washroom")
    threshold = (door["cell"][0] + _STEP[door["side"]][0], door["cell"][1] + _STEP[door["side"]][1])
    assert threshold in privy
    edge = solved["privy"]["edges"]["washroom"]
    assert edge["dir"] == {"n": "s", "s": "n", "e": "w", "w": "e"}[door["side"]]
    house = set()
    for uid in b["rooms"]:
        if solved[uid]["geometry"]["level"] == 0:
            house |= _world(b, solved, uid) if uid in (b.get("ground_specs") or {}) else \
                lb._world_cells({"ground_specs": {}}, uid, solved[uid]["geometry"])
    assert not privy & house


def test_a_place_is_one_thing():
    """A gate answered `along` the path is one place standing by it, never
    a row of parts that do not touch."""
    from tests.test_a_building_stands_in_its_grounds import RELATE, _laid
    relate = copy.deepcopy(RELATE)
    for g in relate["grounds"]:
        if g["id"] == "gate":
            g.clear()
            g.update({"id": "gate", "kind": "gate", "along": "path"})
    b, spec, _layout, refused, solved, _report = _laid(relate=relate)
    gate = next(f for f in spec["grounds"]["features"] if f["id"] == "gate")
    assert gate.get("by") == "path" and "along" not in gate
    assert _cells_connected(_world(b, solved, "gate"))


def test_a_round_place_meets_at_a_cell_the_world_reads():
    """The farm's round oak: its doorway onto the garden is pinned on a cell
    its circle holds, never on a corner of the box round it."""
    from tests.test_a_building_stands_in_its_grounds import _laid
    from world.spatial import room_grid
    b, _spec, _layout, refused, solved, _report = _laid()
    assert refused == []
    geometry = solved["tree"]["geometry"]
    edge = solved["tree"]["edges"].get("garden")
    assert edge is not None
    stub = {"name": "tree", "shape": "round", **{k: v for k, v in geometry.items() if v is not None}}
    grid = room_grid({"rooms": {"tree": stub}}, "tree")
    if edge.get("cell") is not None:
        assert tuple(edge["cell"]) in grid.cells
    assert lb.ground_breaches(b, _spec, _layout) == []


def test_a_round_place_is_never_pinned_on_a_corner_its_circle_leaves_out():
    """A round thing six paces across holds 32 of its box's 36 cells. A place
    touching it only at a box corner meets it nowhere the world reads and
    gets no doorway there -- read off the box, it was pinned on that corner.
    The farm's oak is three paces across and holds all nine of its cells, so
    the test above passes either way (a review of 2026-10-14). A place along
    its side is pinned on a cell the circle holds."""
    from types import SimpleNamespace
    from world.spatial import room_grid
    plan = "layout:t"

    def geo(x, y, w, d, shape=None):
        g = {"extent": {"w": w, "d": d}, "level": 0,
             "site": {"plan": plan, "x": x, "y": y, "elev_m": 0.0}, "parts": None}
        if shape:
            g["shape"] = shape
        return g

    tree = geo(0, 0, 6, 6, "round")
    circle = room_grid({"rooms": {"tree": {"name": "tree", **{k: v for k, v in tree.items()
                                                                if v is not None}}}}, "tree").cells
    assert len(circle) < 36 and (0, 0) not in circle
    for yard, touches in ((geo(-2, -1, 2, 2), False), (geo(-2, 0, 2, 6), True)):
        building = {"rooms": [], "outside": [], "entrance": {}, "plan": plan,
                    "grounds": [{"id": "tree", "joins": ["yard"]}, {"id": "yard", "joins": ["tree"]}],
                    "ground_specs": {"tree": {"shape": "round",
                                              "adjacent": [{"to": "yard", "dir": "w"}]},
                                     "yard": {"adjacent": [{"to": "tree", "dir": "e"}]}}}
        laid = {"tree": copy.deepcopy(tree), "yard": yard}
        out = {pid: {"edges": {}} for pid in laid}
        lb._ground_doorways(building, {}, SimpleNamespace(doors=[]), laid, out)
        pin = out["tree"]["edges"].get("yard")
        if touches:
            assert pin is not None and tuple(pin["cell"]) in circle, pin
        else:
            assert pin is None, pin


def test_a_thing_by_a_way_stands_beside_it_on_its_side():
    """`by` a way is beside it, on the side the answer gives -- read as the
    way's far end, Home 11's well stood across the path's foot, and the
    lab's fresh runs stood their wells in the torii."""
    from tests.test_a_building_stands_in_its_grounds import RELATE, SPECS, SCENE as FARM, HELD_OPEN, SORT
    specs = copy.deepcopy(SPECS)
    specs["kitchen"][1]["adjacent"] = [e for e in specs["kitchen"][1]["adjacent"] if e["to"] != "well"]
    specs["well"][1]["adjacent"] = [{"to": "path", "dir": "w"}]
    specs["path"][1]["adjacent"].append({"to": "well", "dir": "e"})
    relate = copy.deepcopy(RELATE)
    for g in relate["grounds"]:
        if g["id"] == "well":
            g.clear()
            g.update({"id": "well", "kind": "well", "by": "path", "side": "e"})
    found = lb.plan_buildings(specs, copy.deepcopy(FARM), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    layout, _refused = lb.solve_for(b, spec)
    well = next(f["rect"] for f in layout.features if f["id"] == "well")
    path = layout.ways["path"]
    xs = [x for x, _y in path["cells"]]
    assert well.x > max(xs), "east of the path"
    ys = [y for _x, y in path["cells"]]
    assert min(ys) - 1 <= well.y <= max(ys), "beside it, not past its end"


def test_a_way_that_gives_up_its_end_gives_up_its_rows():
    """Where the thing a way leads to has no room past its end, the way gives
    up its last rows to it -- and its rows go with its cells, so a thing laid
    across its far end stands on the way's real last row: Home 11's torii
    stood on a row the path had given up, off its line and half outside the
    plot."""
    from world.layout_solver import solve
    from tests.test_layout_solver import HOUSE
    spec = copy.deepcopy(HOUSE)
    spec["grounds"]["ways"] = [{"id": "approach", "name": "Approach", "from": "entrance",
                                "to": "camphor"}]
    spec["grounds"]["features"] = [
        {"id": "camphor", "name": "Camphor", "kind": "tree", "size": "huge"},
        {"id": "gate", "name": "Gate", "kind": "gate", "across": "approach", "end": "far"}]
    lay = solve(spec)
    way = lay.ways["approach"]
    assert way["rows"], "the approach is laid"
    for row in way["rows"]:
        assert set(map(tuple, row)) <= set(map(tuple, way["cells"])), "a given-up row stayed"
    gate = next(f["rect"] for f in lay.features if f["id"] == "gate")
    last = way["rows"][-1]
    assert any(abs(gate.y - c[1]) <= 0 and gate.x <= c[0] < gate.x + gate.w for c in last) or \
        any(abs(gate.x - c[0]) <= 0 and gate.y <= c[1] < gate.y + gate.d for c in last), \
        "the gate stands across the way's real last row"


# ---- a kitchen shaped like Home 9's (chat 172) ----------------------------

NINE_SPECS = {
    "genkan": ("the Genkan", {
        "purpose": "an entry hall", "structure": "nine", "exposure": E,
        "adjacent": [{"to": "path", "dir": "s", "barrier": "open_door"},
                     {"to": "kitchen", "dir": "e", "barrier": "open_door"},
                     {"to": "loft", "vertical": "up", "way": "stair"}]}),
    "loft": ("the Loft", {"purpose": "a sleeping loft", "structure": "nine", "exposure": E,
                          "adjacent": [{"to": "genkan", "vertical": "down", "way": "stair"}]}),
    "kitchen": ("the Kitchen", {
        "purpose": "a kitchen with a hearth", "structure": "nine", "exposure": E,
        "adjacent": [{"to": "genkan", "dir": "w", "barrier": "open_door"},
                     {"to": "well", "dir": "e", "barrier": "closed_door"}]}),
    "path": ("the Path", {"purpose": "a lantern path", "structure": "nine", "exposure": "open",
                          "adjacent": [{"to": "genkan", "dir": "n"}, {"to": "well", "dir": "e"},
                                       {"to": "garden", "dir": "w"}]}),
    "well": ("the Well", {"purpose": "a stone well", "structure": "nine", "exposure": "open",
                          "adjacent": [{"to": "kitchen", "dir": "w"}, {"to": "path", "dir": "w"}]}),
    "garden": ("the Garden", {"purpose": "a garden of moss", "structure": "nine", "exposure": "open",
                              "shape": "composite", "adjacent": [{"to": "path", "dir": "e"}]}),
}
NINE_SORT = {
    "rooms": [{"id": "genkan", "fixtures": []}, {"id": "loft", "fixtures": []},
              {"id": "kitchen", "fixtures": [{"id": "hearth", "name": "the hearth", "mount": "floor"}]}],
    "stairs": [{"from": "genkan", "to": "loft", "enclosed": False}],
    "grounds": [{"id": "path", "is": "way"}, {"id": "well", "is": "feature"},
                {"id": "garden", "is": "open"}]}
NINE_RELATE = {
    "rooms": [{"id": "genkan", "purpose": "hall", "fixtures": []},
              {"id": "loft", "purpose": "bedroom", "fixtures": []},
              {"id": "kitchen", "purpose": "kitchen", "fixtures": [{"id": "hearth", "kind": "hearth", "at": "n"}]}],
    "stairs": [{"from": "genkan", "to": "loft", "from_at": "n", "to_at": "n"}],
    "grounds": [{"id": "path", "from": "entrance"}, {"id": "well", "kind": "well", "by": "kitchen"},
                {"id": "garden", "where": "around"}]}


def test_a_door_onto_a_thing_also_joined_to_a_way_turns_to_reach_it():
    """The plan joins the well to the kitchen and to the path; the kitchen's
    door to it, asked on the wall away from the path, stands where the well
    reaches the path -- Home 9's well and path did not meet."""
    found = lb.plan_buildings(copy.deepcopy(NINE_SPECS), copy.deepcopy(SCENE), grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(NINE_SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(NINE_RELATE))
    well = next(f for f in spec["grounds"]["features"] if f["id"] == "well")
    assert well.get("reach") == ["path"]
    layout, refused = lb.solve_for(b, spec)
    assert refused == []
    from world.layout_solver import REACH_MAX
    door = next(d for d in layout.doors if d.get("outside") and d["a"] == "kitchen")
    threshold = (door["cell"][0] + _STEP[door["side"]][0], door["cell"][1] + _STEP[door["side"]][1])
    cells = set().union(*(f["rect"].cells() for f in layout.features if f["id"] == "well"))
    assert threshold in cells
    path = layout.ways["path"]["cells"]
    gap = min(abs(a - c) + abs(b_ - e) for a, b_ in cells for c, e in path) - 1
    assert gap <= 0 or gap <= REACH_MAX
    solved, report = lb.planned_layout(b, spec, layout)
    assert lb.ground_breaches(b, spec, layout) == []


def test_no_ground_is_left_to_no_place():
    """A garden answered on one side, with a thing standing at a door: the
    open ground the plan joins to the most places lies round the building,
    never ground no row is written for."""
    from tests.test_a_building_stands_in_its_grounds import RELATE, SORT, _building
    relate = copy.deepcopy(RELATE)
    for g in relate["grounds"]:
        if g["id"] == "garden":
            g["where"] = "w"
    b = _building()
    inv = lb.hold_inventory(b, copy.deepcopy(SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    areas = {a["id"]: a["where"] for a in spec["grounds"]["areas"]}
    assert lb.GROUND_ID not in areas
    assert areas["garden"] == "around"


def test_every_way_between_laid_places_meets_across_one_wall(temp_db):
    """End to end: the tier lays the farm, and on the scene the next beat
    reads every pair of laid ground-storey places joined by a way stands on
    one plan, their doorways on opposite walls, and every place is one floor."""
    from agents.director_layout import lay_out_buildings
    from world.site_plan import plan_offset, room_level, room_site
    from world.spatial import _door_cells, opposite_bearing, room_grid
    from world.structure import _planned_specs, apply_solved_plans
    from tests.test_a_building_stands_in_its_grounds import (_farm_answers, _farm_chat,
                                                             _grounds_on, _plant_farm, _stub_scene)
    cid = _farm_chat(temp_db)
    _plant_farm(cid)
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid), desc=("pond", "road"))
    scene, laid_out = lay_out_buildings(None, cid, scene, ["hall"], "en", call=_farm_answers([]))
    apply_solved_plans(cid, scene)
    rooms = scene["rooms"]
    laid = {uid for uid in laid_out if uid in rooms and (room_site(scene, uid) or {}).get("plan")}
    ground = laid & {"path", "well", "privy", "garden", "gate", "tree"}
    assert ground
    for pid in ground:
        assert _cells_connected(room_grid(scene, pid).cells), pid
    checked = 0
    for a in sorted(laid):
        for edge in rooms[a].get("adjacent") or ():
            b = str(edge.get("to") or "")
            if b not in laid or edge.get("vertical") or edge.get("barrier") == "window" \
                    or not {a, b} & ground or room_level(scene, a) != room_level(scene, b):
                continue
            assert plan_offset(scene, a, b) is not None, (a, b)
            _da, wa = _door_cells(scene, a, b)
            _db, wb = _door_cells(scene, b, a)
            assert wa and wb == opposite_bearing(wa), (a, b, wa, wb)
            checked += 1
    assert checked >= 4


def test_the_owners_liked_shrine_re_solves_cell_for_cell():
    """The layout lab's preferred shrine (`tools/layout_lab/baselines`, the
    owner's: compare before publishing) solves exactly as it did when this
    was pinned. A change that moves it is a change to put to the owner, with
    its before and after, never a digest quietly updated."""
    import hashlib
    import json
    from pathlib import Path
    from world.layout_solver import solve
    root = Path(__file__).resolve().parent.parent / "tools" / "layout_lab" / "baselines"
    spec = json.loads((root / "shrine_rewritten.json").read_text())["spec"]
    laid = json.dumps(solve(spec).as_dict(), sort_keys=True, ensure_ascii=False, default=str)
    assert hashlib.sha1(laid.encode()).hexdigest()[:16] == "f538dba9624c129e"


def test_a_place_left_joined_to_nothing_goes_with_the_place_it_hung_on():
    """Home 6's torii was joined to the lantern path alone: with the path
    taken out it was laid in the plot's far corner, reached by nothing. A
    place left joined to no room and no other place of the ground goes with
    the places taken out, in the same round."""
    b = lb.plan_buildings(copy.deepcopy(COURT_SPECS), copy.deepcopy(SCENE), grounds=True)
    b = max(b, key=lambda x: len(x["rooms"]))
    b = dict(b, grounds=[dict(g) for g in b["grounds"]])
    b["grounds"].append({"id": "post", "name": "the post", "joins": ["lane"], "hop": 2})
    left = lb.without_places(b, ["lane"])
    assert {g["id"] for g in left["grounds"]} == {"court", "shed"}
    assert "post" not in left["ground_specs"]


def test_a_place_nothing_reaches_is_refused():
    """A place whose every way fails or leads only to what is not laid is
    reached from no room of the building, and the floor names it."""
    b, spec, layout, _refused, _solved, _report = _court()
    real = lb.planned_layout

    def cut(building, spec_, layout_, **kw):
        solved, report = real(building, spec_, layout_, **kw)
        for pid in ("court",):
            solved[pid]["edges"] = {}
        for uid in solved:
            solved[uid].get("edges", {}).pop("court", None)
        return solved, report

    import world.layout_bridge as bridge
    try:
        bridge.planned_layout = cut
        words = [w for w, _p in bridge.ground_breaches(b, spec, layout)]
    finally:
        bridge.planned_layout = real
    assert any("reached from no room" in w or "no placed doorway" in w for w in words), words


def test_a_place_an_earlier_solve_laid_comes_off_the_plan_when_it_is_dropped(temp_db, monkeypatch):
    """The house re-planned is laid again with the ground an earlier solve
    laid round it; a place of that ground that fails now is taken off the
    plan in the same write -- left on its old site, the re-solve laid the
    rest of the ground over it (a review of 2026-10-14)."""
    from agents.director_layout import lay_out_buildings
    from world.structure import _planned_specs, apply_solved_plans, registry_rows
    from tests.test_a_building_stands_in_its_grounds import (_farm_answers, _farm_chat, _grounds_on,
                                                             _plant_farm, _stub_scene)
    cid = _farm_chat(temp_db)
    _plant_farm(cid)
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid), desc=("pond", "road"))
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=_farm_answers([]))
    apply_solved_plans(cid, scene)
    plan = {uid: e["planned"] for uid, e in registry_rows(cid).items()}
    assert plan["tree"]["site"]["plan"] == "layout:hall"
    _plant_farm(cid, only={"hall", "kitchen", "washroom", "loft"},
                change={"hall": {"extent": {"w": 8, "d": 4}}})
    real = lb.ground_breaches

    def breaches(building, spec, layout):
        found = real(building, spec, layout)
        if "tree" in (spec.get("ground_is") or {}):
            found = found + [("tree is not one floor", "tree")]
        return found

    monkeypatch.setattr(lb, "ground_breaches", breaches)
    apply_solved_plans(cid, scene)
    _scene, laid_out = lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en",
                                         call=_farm_answers([]))
    plan = {uid: e["planned"] for uid, e in registry_rows(cid).items()}
    assert plan["hall"]["site"]["plan"] == "layout:hall"
    assert plan["garden"]["site"]["plan"] == "layout:hall"
    assert plan["tree"].get("site") is None and "layout" not in plan["tree"]


# ---- the review of 2026-10-14 ---------------------------------------------

def _court_with(extra_ground, relate_extra, joins):
    """The court plus places the review added: `extra_ground` specs, their
    answers, and the plan joins back to them (`{uid: [edge]}`)."""
    specs = copy.deepcopy(COURT_SPECS)
    for uid, spec in extra_ground.items():
        specs[uid] = spec
    for uid, edges in joins.items():
        specs[uid][1]["adjacent"].extend(edges)
    sort = copy.deepcopy(COURT_SORT)
    relate = copy.deepcopy(COURT_RELATE)
    for answer in relate_extra:
        sort["grounds"].append({"id": answer["id"], "is": answer.pop("is")})
        relate["grounds"].append(answer)
    found = lb.plan_buildings(specs, copy.deepcopy(SCENE), grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    return b, sort, relate


def _lay(b, sort, relate):
    from agents import director_layout as dl

    def call(step, system, payload):
        if step.endswith("_brief"):
            return {"brief": ""}
        return copy.deepcopy(sort if step.endswith("_sort") else relate)

    return dl.lay_out(b, call, "en")


def test_a_thing_by_a_way_that_leaves_the_ground_stands_by_it():
    """The way that leaves the court is laid before every thing, so a post
    the answers stand by it has it to stand by -- laid last, the post stood
    with nothing to stand by and was dropped on every seed."""
    post = ("the Post", {"purpose": "a waymark post", "structure": "court", "exposure": "open",
                         "adjacent": [{"to": "lane", "dir": "w"}]})
    b, sort, relate = _court_with({"post": post},
                                  [{"id": "post", "is": "feature", "kind": "statue", "by": "lane",
                                    "side": "e"}],
                                  {"lane": [{"to": "post", "dir": "e"}]})
    spec, layout, _inv, refused = _lay(b, sort, relate)
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")


def test_a_lantern_by_the_entrance_never_costs_the_court_its_doorway():
    """A lantern by the entrance stood one pace below the threshold and left
    it a sliver no two-pace block held: the court lost its doorway, and the
    house was laid with no ground at all. The ground at a door is no thing's."""
    lantern = ("the Lantern", {"purpose": "a stone lantern", "structure": "court",
                               "exposure": "open", "adjacent": [{"to": "court", "dir": "n"}]})
    b, sort, relate = _court_with({"lantern": lantern},
                                  [{"id": "lantern", "is": "feature", "kind": "lantern",
                                    "by": "entrance"}],
                                  {"court": [{"to": "lantern", "dir": "s"}]})
    spec, layout, _inv, refused = _lay(b, sort, relate)
    assert refused == []
    assert "court" in (spec.get("ground_is") or {}), "the court is laid"
    assert "court" not in (spec.get("places_dropped") or [])
    # and the lantern stands at the entrance, clear of its ground: read as by
    # the court, it stood nineteen paces off, and the ground at the door was
    # never asked to keep it clear (a review of 2026-10-14)
    assert "lantern" not in (spec.get("places_dropped") or [])
    door = next(d for d in layout.doors if d.get("b") == "entrance")
    rect = next(f["rect"] for f in layout.features if f["id"] == "lantern")
    sx, sy = _STEP[door["side"]]
    step = (door["cell"][0] + sx, door["cell"][1] + sy)
    assert min(abs(x - step[0]) + abs(y - step[1]) for x, y in rect.cells()) <= 3, (rect, step)
    assert step not in rect.cells()


def test_a_thing_at_a_door_never_costs_the_open_ground():
    """The farm's kitchen opens onto the garden as well as onto its well:
    the well on the one door's threshold cost the garden its doorway, and the
    garden was dropped with the privy and the tree. The well stands at a door
    of its own, and nothing is dropped."""
    from tests.test_a_building_stands_in_its_grounds import RELATE, SCENE as FARM, SORT, SPECS, HELD_OPEN
    specs = copy.deepcopy(SPECS)
    specs["kitchen"][1]["adjacent"].append({"to": "garden", "dir": "s", "barrier": "open_door"})
    specs["garden"][1]["adjacent"].append({"to": "kitchen", "dir": "n"})
    found = lb.plan_buildings(specs, copy.deepcopy(FARM), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    spec, layout, _inv, refused = _lay(b, SORT, RELATE)
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    doors = {(d["a"], d["b"]) for d in layout.doors if d.get("outside")}
    assert {("kitchen", "garden"), ("kitchen", "well")} <= doors


def test_two_things_joined_to_one_room_never_fight_over_its_door():
    """A woodpile joined to the kitchen beside its well: the second moved the
    one door off the first, and the well was dropped. Each stands at a door
    of its own, and nothing is dropped."""
    from tests.test_a_building_stands_in_its_grounds import RELATE, SCENE as FARM, SORT, SPECS, HELD_OPEN
    specs = copy.deepcopy(SPECS)
    specs["woodpile"] = ("the Woodpile", {"purpose": "a stack of firewood", "structure": "farm",
                                          "exposure": "open",
                                          "adjacent": [{"to": "kitchen", "dir": "w"}]})
    specs["kitchen"][1]["adjacent"].append({"to": "woodpile", "dir": "e", "barrier": "closed_door"})
    sort, relate = copy.deepcopy(SORT), copy.deepcopy(RELATE)
    sort["grounds"].append({"id": "woodpile", "is": "feature"})
    relate["grounds"].append({"id": "woodpile", "kind": "barrel", "by": "kitchen", "side": "e"})
    found = lb.plan_buildings(specs, copy.deepcopy(FARM), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    at = sorted(f["id"] for f in spec["grounds"]["features"] if f.get("at_door"))
    assert at == ["well", "woodpile"], at
    spec2, layout, _inv, refused = _lay(b, sort, relate)
    assert refused == []
    assert not spec2.get("places_dropped"), spec2.get("places_dropped")
    doors = [d for d in layout.doors if d.get("outside") and d["a"] == "kitchen"]
    assert sorted(d["b"] for d in doors) == ["well", "woodpile"]
    steps = {}
    for d in doors:
        sx, sy = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}[d["side"]]
        steps[d["b"]] = (d["cell"][0] + sx, d["cell"][1] + sy)
    for f in layout.features:
        if f["id"] in steps:
            assert steps[f["id"]] in f["rect"].cells(), f


def test_the_places_dropped_are_those_of_the_seed_that_fails_on_fewest():
    """Every seed refused, each carrying the floor's findings as the search
    made them (`solve_for`'s attempts): a seed refused for the house is never
    read for places, even where its ground fails on fewer, and of the rest
    the one failing on the fewest places is taken."""
    b, spec, _layout, _refused, _solved, _report = _court()
    seeds = [object() for _ in range(4)]
    attempts = [
        # refused for the house: its ground's findings, fewest of all, are
        # never the drop
        (seeds[0], ["hall and side were to join and share no doorway", "lane does not meet"],
         [("lane does not meet", "lane")]),
        (seeds[1], ["lane does not meet", "shed does not meet"],
         [("lane does not meet", "lane"), ("shed does not meet", "shed")]),
        (seeds[2], ["shed does not meet"], [("shed does not meet", "shed")]),
        (seeds[3], ["court is not one floor", "lane is reached from no room of the building"],
         [("court is not one floor", "court"),
          ("lane is reached from no room of the building", None)])]
    places, words = lb.places_to_drop(b, spec, attempts)
    assert places == ["shed"] and words == ["shed does not meet"]
    # a breach charged to nobody refuses the seed and drops nothing
    places, words = lb.places_to_drop(b, spec, attempts[3:])
    assert places == ["court"] and "lane is reached from no room of the building" in words


def test_a_house_refused_is_never_read_for_its_ground(monkeypatch):
    """The floor reads a plan that needs every room laid; asked of a seed
    whose house is refused, it raised and aborted the seed search."""
    b, spec, layout, _refused, _solved, _report = _court()

    def boom(*a):
        raise KeyError("hall")

    monkeypatch.setattr(lb, "ground_breaches", boom)
    layout.floors[0].pop("hall", None)
    refused = lb.refusals(b, spec, layout)
    assert any("found no floor" in r for r in refused)
    b2, spec2, layout2, _r, _s, _p = _court()
    assert any("could not be read" in r for r in lb.refusals(b2, spec2, layout2))


def test_a_way_one_side_alone_declares_meets_from_both():
    """The court declares its way to the shed, the shed none back (two plan
    ops): the solve's place for the shed's side was thrown away, and the
    shed stood with a bare doorway that met nothing."""
    specs = copy.deepcopy(COURT_SPECS)
    specs["shed"][1]["adjacent"] = []
    found = lb.plan_buildings(specs, copy.deepcopy(SCENE), grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(COURT_SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(COURT_RELATE))
    layout, refused = lb.solve_for(b, spec)
    solved, _report = lb.planned_layout(b, spec, layout)
    assert "court" in (solved["shed"].get("made_edges") or {}), solved["shed"]
    assert solved["shed"]["made_edges"]["court"].get("dir") in ("n", "e", "s", "w")
    assert lb.ground_breaches(b, spec, layout) == []


def test_a_place_that_is_no_ground_keeps_its_own_door():
    """The rule that opens a dropped place's door onto the ground fired for
    every outside place that is no ground -- a described room among them --
    and folded its door into the room's door onto the garden."""
    from tests.test_a_building_stands_in_its_grounds import RELATE, SCENE as FARM, SORT, SPECS, HELD_OPEN
    specs = copy.deepcopy(SPECS)
    specs["washroom"][1]["adjacent"].append({"to": "pond", "dir": "w", "barrier": "open_door"})
    specs["pond"][1]["adjacent"].append({"to": "washroom", "dir": "e"})
    found = lb.plan_buildings(specs, copy.deepcopy(FARM), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    assert "pond" not in {g["id"] for g in b["grounds"]}
    inv = lb.hold_inventory(b, copy.deepcopy(SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(RELATE))
    assert "pond" not in (spec.get("door_to") or {})


def test_ground_cut_in_two_is_charged_to_what_cut_it(monkeypatch):
    """A way laid across the court splits it: the court is not one floor,
    and the way that cut it gives way -- the court was charged, and dropped
    with every place reached through it."""
    b, spec, layout, _refused, solved, report = _court()
    real = lb.planned_layout

    def cut(building, spec_, layout_, **kw):
        out, rep = real(building, spec_, layout_, **kw)
        court = out["court"]["geometry"]
        site = court["site"]
        cells = lb._world_cells(building, "court", court)
        xs = sorted({x for x, _y in cells})
        mid = xs[len(xs) // 2]
        ys = sorted({y for _x, y in cells})
        lane = out["lane"]["geometry"]
        lane["site"] = dict(site, x=mid, y=ys[0])
        lane["extent"] = {"w": 1, "d": ys[-1] - ys[0] + 1}
        lane["parts"] = None
        parts = [{"w": mid - site["x"], "d": ys[-1] - ys[0] + 1, "at": [0, 0]},
                 {"w": site["x"] + court["extent"]["w"] - mid - 1, "d": ys[-1] - ys[0] + 1,
                  "at": [mid - site["x"] + 1, 0]}]
        court["shape"], court["parts"] = "composite", parts
        return out, rep

    monkeypatch.setattr(lb, "planned_layout", cut)
    found = lb.ground_breaches(b, spec, layout)
    floor = [(w, p) for w, p in found if "court is not one floor" in w]
    assert floor and floor[0][1] == "lane", found


# The review's fuzz houses (2026-10-14), each as the bridge now writes it: the
# room's way to the thing at its door is its own join (a door of its own)
FUZZ_POCKET = {"name": "fuzz", "front": "w", "entrance": {"room": "hall", "kind": "door"}, "rooms": [
    {"id": "hall", "name": "Hall", "level": 0, "purpose": "living",
     "joins": [{"to": "kitchen", "side": "n"}, {"to": "store", "side": "e"},
               {"to": "garden", "side": "n"}],
     "fixtures": [{"id": "h0", "name": "H0", "kind": "sink"}]},
    {"id": "kitchen", "name": "Kitchen", "level": 0, "purpose": "kitchen",
     "joins": [{"to": "well", "side": "n"}],
     "fixtures": [{"id": "k0", "name": "K0", "kind": "table", "at": "s"},
                  {"id": "k1", "name": "K1", "kind": "table"},
                  {"id": "k2", "name": "K2", "kind": "counter"},
                  {"id": "k3", "name": "K3", "kind": "cabinet", "at": "w"},
                  {"id": "k4", "name": "K4", "kind": "sink"}],
     "windows": [{"id": "kw", "side": "e", "count": 1}]},
    {"id": "store", "name": "Store", "level": 0, "purpose": "storage", "joins": [],
     "fixtures": [{"id": "s0", "name": "S0", "kind": "shelf"}]}],
    "grounds": {"areas": [{"id": "garden", "name": "Garden", "kind": "garden", "where": "around"}],
                "ways": [{"id": "approach", "name": "Approach", "from": "entrance"}],
                "features": [{"id": "well", "name": "Well", "kind": "well",
                              "at_door": {"room": "kitchen", "onto": "garden"},
                              "reach": ["approach"]}]}}
FUZZ_RUN = {"name": "fuzz", "front": "s", "entrance": {"room": "hall", "kind": "door"}, "rooms": [
    {"id": "hall", "name": "Hall", "level": 0, "purpose": "entryway",
     "joins": [{"to": "kitchen", "side": "e"}, {"to": "store", "side": "e"}],
     "fixtures": [{"id": "h0", "name": "H0", "kind": "stove"}]},
    {"id": "kitchen", "name": "Kitchen", "level": 0, "purpose": "kitchen",
     "joins": [{"to": "well", "side": "n"}],
     "fixtures": [{"id": "k0", "name": "K0", "kind": "shelf", "at": "w"},
                  {"id": "k1", "name": "K1", "kind": "shelf"}], "windows": []},
    {"id": "store", "name": "Store", "level": 0, "purpose": "storage",
     "joins": [{"to": "garden", "side": "s"}],
     "fixtures": [{"id": "s0", "name": "S0", "kind": "shelf"}]}],
    "grounds": {"areas": [{"id": "garden", "name": "Garden", "kind": "garden", "where": "around"}],
                "ways": [{"id": "approach", "name": "Approach", "from": "entrance"}],
                "features": [{"id": "well", "name": "Well", "kind": "tree",
                              "at_door": {"room": "kitchen", "onto": "garden"},
                              "reach": ["approach"]}]}}


def _doorways_of(layout, rid, lv=0):
    """The cells of room `rid` its doorways open from, each on its own side."""
    out = []
    for d in layout.doors:
        if d.get("level", lv) != lv or d["side"] not in _STEP:
            continue
        if d["a"] == rid:
            out.append(tuple(d["cell"]))
        elif d["b"] == rid:
            out.append((d["cell"][0] + _STEP[d["side"]][0], d["cell"][1] + _STEP[d["side"]][1]))
    return out


@pytest.mark.parametrize("k", range(4))
def test_a_door_moved_for_a_thing_never_opens_into_a_pocket(k):
    """Fuzz house 182: the kitchen's door turned to reach the approach, into
    two cells its tables and counter wall off from the hall's doorway. A
    moved door joins the room's other doorways through its floor."""
    from world.layout_solver import SEED, solve
    layout = solve(copy.deepcopy(FUZZ_POCKET), seed=SEED + k)
    for rid, rects in layout.floors[0].items():
        floor = set(rects[0].cells())
        for fx in layout.fixtures.get(rid) or ():
            floor -= fx["rect"].cells()
        doors = [c for c in _doorways_of(layout, rid) if c in rects[0].cells()]
        if len(doors) > 1:
            reached = _reach_from(floor, doors[0])
            assert all(c in reached for c in doors), (rid, doors)


def _reach_from(cells, start):
    seen, stack = set(), [start]
    while stack:
        c = stack.pop()
        if c in seen or c not in cells:
            continue
        seen.add(c)
        stack.extend((c[0] + dx, c[1] + dy) for dx, dy in _STEP.values())
    return seen


@pytest.mark.parametrize("k", range(4))
def test_a_thing_within_reach_of_its_way_reaches_it(k):
    """Fuzz house 1142: the tree stood two paces from the approach and its
    run of ground to it ran x first, through the house, so none was laid. A
    thing scored within reach has its ground laid to the way."""
    from world.layout_solver import REACH_MAX, SEED, solve
    layout = solve(copy.deepcopy(FUZZ_RUN), seed=SEED + k)
    mine = [f["rect"] for f in layout.features if f["id"] == "well"]
    way = layout.ways["approach"]["cells"]
    assert mine
    gap = min(abs(a - c) + abs(b - d) for a, b in mine[0].cells() for c, d in way) - 1
    held = set().union(*(r.cells() for r in mine))
    touch = min(abs(a - c) + abs(b - d) for a, b in held for c, d in way) - 1
    assert gap > REACH_MAX or touch == 0, (gap, touch)


def test_a_door_never_turns_onto_a_cell_another_doorway_arrives_at():
    """The hall's doorway, written by the hall, arrives a pace into the
    kitchen at its corner; the kitchen's door turned for its well read the
    hall's own cell for it, and opened on that same corner (fuzz house
    5274)."""
    from world.layout_solver import Layout, Rect, _things_at_doors
    layout = Layout(name="t")
    layout.floors = {0: {"hall": [Rect(0, 0, 5, 4)], "kitchen": [Rect(0, 4, 5, 3)]}}
    layout.outlines = {"main": {0: Rect(0, 0, 5, 7)}}
    layout.doors = [{"a": "hall", "b": "kitchen", "level": 0, "side": "s", "cell": [4, 3],
                     "kind": "door"},
                    {"a": "kitchen", "b": "well", "level": 0, "side": "s", "cell": [2, 6],
                     "kind": "door", "outside": True}]
    layout.ways = {"approach": {"cells": {(x, y) for x in range(6, 9) for y in range(1, 4)},
                                "side": "e", "rows": []}}
    layout.names = {"well": "Well", "kitchen": "Kitchen", "hall": "Hall"}
    house = Rect(0, 0, 5, 7).cells()
    plot = {(x, y) for x in range(-4, 12) for y in range(-4, 12)} - house
    taken = set(layout.ways["approach"]["cells"])

    def free(rc, door=None):
        return rc.cells() <= plot and not rc.cells() & taken

    def place(f, rect):
        layout.features.append({"id": f["id"], "rect": rect})
        taken.update(rect.cells())

    feats = [{"id": "well", "name": "Well", "kind": "well",
              "at_door": {"room": "kitchen", "onto": "garden"}, "reach": ["approach"]}]
    _things_at_doors(layout, {"hall": {"level": 0}, "kitchen": {"level": 0}}, feats, free, place)
    door = layout.doors[1]
    assert door["side"] == "e", "turned toward the approach"
    assert tuple(door["cell"]) != (4, 4), "never onto the hall doorway's cell"
    assert len(set(_doorways_of(layout, "kitchen"))) == len(_doorways_of(layout, "kitchen"))


def _farm_plus(extra_specs, extra_sort, extra_relate, joins):
    from tests.test_a_building_stands_in_its_grounds import HELD_OPEN, RELATE, SCENE as FARM, SORT, SPECS
    specs = copy.deepcopy(SPECS)
    specs.update(copy.deepcopy(extra_specs))
    for uid, edges in joins.items():
        specs[uid][1]["adjacent"].extend(edges)
    sort, relate = copy.deepcopy(SORT), copy.deepcopy(RELATE)
    sort["grounds"] += extra_sort
    relate["grounds"] += extra_relate
    found = lb.plan_buildings(specs, copy.deepcopy(FARM), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    return b, lb.spec_from_answers(b, inv, copy.deepcopy(relate))


@pytest.mark.parametrize("k", range(4))
def test_a_branch_way_is_laid_two_paces_wide_and_written(k):
    """A spur off the approach to a wayside shrine was laid a pace wide, and
    the world reads no place narrower than two: it was written as nothing,
    and dropped with the shrine. Laid two wide, it is written on every seed."""
    from world.layout_solver import SEED, solve
    b, spec = _farm_plus(
        {"spur": ("the Spur", {"purpose": "a footpath to the shrine", "structure": "farm",
                               "exposure": "open", "adjacent": [{"to": "path", "dir": "w"},
                                                                {"to": "shrine", "dir": "e"}]}),
         "shrine": ("the Shrine", {"purpose": "a wayside shrine", "structure": "farm",
                                   "exposure": "open", "adjacent": [{"to": "spur", "dir": "w"}]})},
        [{"id": "spur", "is": "way"}, {"id": "shrine", "is": "feature"}],
        [{"id": "spur", "from": "path", "to": "shrine"}, {"id": "shrine", "kind": "statue", "side": "e"}],
        {"path": [{"to": "spur", "dir": "e"}]})
    assert spec["grounds"]["narrowest"] == 2
    layout = solve(spec, seed=SEED + k)
    assert lb.refusals(b, spec, layout) == []
    solved, report = lb.planned_layout(b, spec, layout)
    assert "spur" not in report["grounds_unplaced"]
    assert len(_world(b, solved, "spur")) >= 4


@pytest.mark.parametrize("k", range(4))
def test_an_outbuildings_walk_holds_on_every_seed(k):
    """The farm's privy walk ran a pace wide between the washroom's wall and
    the oak; the world reads no place narrower than two, so the walk's end at
    the washroom's door was cut off and the privy failed on three of four
    seeds. The ground at a door is no thing's, and the walk is laid two
    wide."""
    from tests.test_a_building_stands_in_its_grounds import _building, RELATE, SORT
    from world.layout_solver import SEED, solve
    b = _building()
    inv = lb.hold_inventory(b, copy.deepcopy(SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(RELATE))
    layout = solve(spec, seed=SEED + k)
    assert lb.refusals(b, spec, layout) == []


def test_two_outbuildings_on_one_bearing_stand_apart():
    """A storehouse and a byre at one end of the court: both stood on one
    rectangle, and one was always dropped."""
    byre = ("the Byre", {"purpose": "a byre", "structure": "court",
                         "adjacent": [{"to": "court", "dir": "e"}]})
    b, sort, relate = _court_with({"byre": byre},
                                  [{"id": "byre", "is": "outbuilding", "side": "e"}],
                                  {"court": [{"to": "byre", "dir": "w"}]})
    spec, layout, _inv, refused = _lay(b, sort, relate)
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    shed, byre_r = (layout.floors[0][k][0] for k in ("shed", "byre"))
    assert not shed.cells() & byre_r.cells()


def test_a_way_leaving_ground_behind_the_house_leaves_on_its_side():
    """The hall also opens north onto a yard, and a lane joined to the yard
    alone states no side: it left toward the front, through the house, and
    was dropped. Unsaid, it leaves on the side its ground lies."""
    # the yard's way to the track states no side either: the side the track
    # leaves on is unsaid
    yard = ("the Yard", {"purpose": "a back yard", "structure": "court", "exposure": "open",
                         "adjacent": [{"to": "hall", "dir": "s"}, {"to": "track"}]})
    track = ("the Track", {"purpose": "a cart track", "structure": "court", "exposure": "open",
                           "adjacent": [{"to": "yard"}]})
    b, sort, relate = _court_with({"yard": yard, "track": track},
                                  [{"id": "yard", "is": "open", "where": "n"},
                                   {"id": "track", "is": "way"}],
                                  {"hall": [{"to": "yard", "dir": "n", "barrier": "closed_door"}]})
    spec, layout, _inv, refused = _lay(b, sort, relate)
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    house = set().union(*(r.cells() for rects in layout.floors[0].values() for r in rects))
    track_cells = layout.ways["track"]["cells"]
    assert not track_cells & house
    assert max(y for _x, y in track_cells) < min(y for _x, y in house)
    assert layout.ways["track"]["side"] == "n", "it leaves on the side its ground lies"


def test_a_gate_across_the_way_that_leaves_the_ground_stands_across_its_end():
    """The leaving way laid after every thing: a gate across its far end had
    no way to stand across, stood in the plot's corner, and was dropped."""
    gate = ("the Gate", {"purpose": "a gate at the foot of the stair", "structure": "court",
                         "exposure": "open", "adjacent": [{"to": "lane", "dir": "n"}]})
    b, sort, relate = _court_with({"gate": gate},
                                  [{"id": "gate", "is": "feature", "kind": "gate", "across": "lane",
                                    "end": "far"}],
                                  {"lane": [{"to": "gate", "dir": "s"}]})
    spec, layout, _inv, refused = _lay(b, sort, relate)
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    lane = layout.ways["lane"]["cells"]
    rect = next(f["rect"] for f in layout.features if f["id"] == "gate")
    far = max(y for _x, y in lane)
    assert any(abs(y - far) <= 1 for _x, y in rect.cells())
