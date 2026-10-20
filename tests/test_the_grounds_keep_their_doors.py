"""The ground keeps every door it is given, and lays nothing on another's.

A second review of design A6 (2026-10-14, 28 findings confirmed) found the
grounds giving way where the plan held together: a large round thing whose
own door shared a wall stood on a corner its circle leaves out; a lantern by
a lane stood on the lane's mouth; a walk laid two wide left the entrance's
step a sliver; a lane ran through a storehouse, and another through the
court beyond the garden it left; two outbuildings stood one pace apart; a
privy's walk ran round the house because the answer stood it on the side
the plan's way did not face; a lantern joined to a garden alone stood where
no garden was. Each test is the reviewer's plan, built from the suite's own
court and farm; the names are illustrations, not the rule.
"""
from __future__ import annotations

import copy

import pytest

from world import layout_bridge as lb
from world.layout_solver import SEED, solve

from tests.test_the_grounds_hold_together import (COURT_RELATE, COURT_SORT, COURT_SPECS, SCENE,
                                                  _STEP)

_OPP = {"n": "s", "s": "n", "e": "w", "w": "e"}


def _court(mutate):
    specs, sort, relate = copy.deepcopy(COURT_SPECS), copy.deepcopy(COURT_SORT), \
        copy.deepcopy(COURT_RELATE)
    mutate(specs, sort, relate)
    return specs, copy.deepcopy(SCENE), set(), sort, relate


def _farm(mutate):
    from tests.test_a_building_stands_in_its_grounds import HELD_OPEN, RELATE, SCENE as FARM, SORT, SPECS
    specs, sort, relate = copy.deepcopy(SPECS), copy.deepcopy(SORT), copy.deepcopy(RELATE)
    mutate(specs, sort, relate)
    return specs, copy.deepcopy(FARM), set(HELD_OPEN), sort, relate


def _building(plan):
    specs, scene, held, _sort, _relate = plan
    found = lb.plan_buildings(copy.deepcopy(specs), copy.deepcopy(scene), held_open=held,
                              grounds=True)
    return max(found, key=lambda x: len(x["rooms"]))


def _spec(plan):
    b = _building(plan)
    inv = lb.hold_inventory(b, copy.deepcopy(plan[3]))
    return b, lb.spec_from_answers(b, inv, copy.deepcopy(plan[4]))


def _lay(plan):
    """`(spec, layout, refused)` from `director_layout.lay_out`, no model."""
    from agents import director_layout as dl
    b = _building(plan)

    def call(step, system, payload):
        if step.endswith("_brief"):
            return {"brief": ""}
        return copy.deepcopy(plan[3] if step.endswith("_sort") else plan[4])

    spec, layout, _inv, refused = dl.lay_out(b, call, "en")
    return spec, layout, refused


def _add(specs, uid, name, purpose, edges, **fields):
    specs[uid] = (name, dict({"purpose": purpose, "structure": next(iter(specs.values()))[1]["structure"],
                              "adjacent": edges}, **fields))


def _laid_all(spec, refused, places):
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    assert set(places) <= set(spec.get("ground_is") or {}), spec.get("ground_is")


# ---------------------------------------------------------------- doors


@pytest.mark.parametrize("size", ["large", "huge"])
def test_a_large_round_thing_at_a_door_stands_whole(size):
    """A yew joined to the hall, whose one outside wall carries the entrance:
    its own door shared that wall, its step fell on a corner of its box the
    circle leaves out, and it was dropped on every seed. The step is a cell
    the thing holds as the world reads it, and the door turns where nothing
    else fits."""
    from world.spatial import room_grid

    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"].append({"to": "yew", "dir": "s", "barrier": "closed_door"})
        _add(specs, "yew", "the Yew", "an old yew", [{"to": "hall", "dir": "n"}],
             exposure="open", shape="round")
        sort["grounds"].append({"id": "yew", "is": "feature"})
        relate["grounds"].append({"id": "yew", "kind": "tree", "size": size, "by": "hall"})

    plan = _court(mutate)
    spec, layout, refused = _lay(plan)
    _laid_all(spec, refused, ["court", "lane", "shed", "yew"])
    rect = next(f["rect"] for f in layout.features if f["id"] == "yew")
    door = next(d for d in layout.doors if d.get("outside") and d["b"] == "yew")
    sx, sy = _STEP[door["side"]]
    step = (door["cell"][0] + sx, door["cell"][1] + sy)
    circle = room_grid({"rooms": {"_": {"name": "_", "shape": "round",
                                        "extent": {"w": rect.w, "d": rect.d}}}}, "_").cells
    assert (step[0] - rect.x, step[1] - rect.y) in circle


def test_a_door_moved_onto_its_ground_keeps_clear_of_a_things_door():
    """The review's house 218: the kitchen's door onto an orchard behind the
    house was moved to a pace from the well's own door, the well's step fell
    in its ground, and the well found no room. A cell two paces off would
    do, and is taken."""
    spec = {"name": "fuzz", "front": "e", "entrance": {"room": "hall", "kind": "door"}, "rooms": [
        {"id": "hall", "name": "Hall", "level": 0, "purpose": "entryway",
         "joins": [{"to": "kitchen", "side": "n"}, {"to": "store", "side": "e"},
                   {"to": "garden", "side": "n"}],
         "fixtures": [{"id": "h0", "name": "H0", "kind": "bench"}]},
        {"id": "kitchen", "name": "Kitchen", "level": 0, "purpose": "kitchen",
         "joins": [{"to": "orchard", "side": "s"}, {"to": "well", "side": "s"}],
         "fixtures": [{"id": "k0", "name": "K0", "kind": "chest", "at": "w"},
                      {"id": "k1", "name": "K1", "kind": "counter"}], "windows": []},
        {"id": "store", "name": "Store", "level": 0, "purpose": "storage", "joins": [],
         "fixtures": [{"id": "s0", "name": "S0", "kind": "shelf"}]},
        {"id": "bath", "name": "Bath", "level": 0, "purpose": "bath",
         "joins": [{"to": "kitchen", "side": "n"}], "fixtures": [{"id": "b0", "name": "Tub", "kind": "tub"}]}],
        "grounds": {"areas": [{"id": "orchard", "name": "Orchard", "kind": "garden", "where": "w"},
                              {"id": "garden", "name": "Garden", "kind": "garden", "where": "around"}],
                    "ways": [{"id": "approach", "name": "Approach", "from": "entrance"}],
                    "features": [{"id": "well", "name": "Well", "kind": "statue",
                                  "at_door": {"room": "kitchen", "onto": "garden"}}],
                    "narrowest": 2}}
    for k in range(4):
        layout = solve(copy.deepcopy(spec), seed=SEED + k)
        assert any(f["id"] == "well" for f in layout.features), layout.warnings
        doors = {d["b"]: d for d in layout.doors if d.get("outside") and d["a"] == "kitchen"}
        a, b = doors["orchard"]["cell"], doors["well"]["cell"]
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) >= 2
        # the well kept the door it was given, never turned off its wall
        assert doors["well"]["side"] == "w", doors["well"]


def test_a_door_whose_wall_faces_another_room_opens_onto_its_ground():
    """The hall's whole back wall was its ladder's stair hall: its door onto
    the yard behind the house turned to its west wall, onto ground beside the
    house no area held, and the yard was dropped with its track."""
    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"].append({"to": "yard", "dir": "n", "barrier": "closed_door"})
        _add(specs, "yard", "the Yard", "a back yard",
             [{"to": "hall", "dir": "s"}, {"to": "track", "dir": "n"}], exposure="open")
        _add(specs, "track", "the Track", "a cart track", [{"to": "yard"}], exposure="open")
        sort["grounds"] += [{"id": "yard", "is": "open"}, {"id": "track", "is": "way"}]
        relate["grounds"] += [{"id": "yard", "where": "n"}, {"id": "track"}]

    spec, layout, refused = _lay(_court(mutate))
    _laid_all(spec, refused, ["court", "lane", "shed", "yard", "track"])
    door = next(d for d in layout.doors if d.get("outside") and d["a"] == "hall" and d["b"] == "yard")
    sx, sy = _STEP[door["side"]]
    assert (door["cell"][0] + sx, door["cell"][1] + sy) in layout.areas["yard"]


# ------------------------------------------------- the ground at a door


def test_a_one_pace_thing_by_the_entrance_is_laid_two_deep_clear_of_its_step():
    """A bench a pace deep by the entrance, a lantern against it: the writer
    widened the bench onto the ground the solver kept at the entrance, and
    the bench and the lantern were dropped. Where the world asks it, a thing
    is laid at least two paces each way, as it is written."""
    def mutate(specs, sort, relate):
        specs["court"][1]["adjacent"].append({"to": "bench", "dir": "s"})
        _add(specs, "bench", "the Bench", "a stone bench",
             [{"to": "court", "dir": "n"}, {"to": "lamp", "dir": "s"}], exposure="open")
        _add(specs, "lamp", "the Lamp", "a stone lamp", [{"to": "bench", "dir": "n"}],
             exposure="open")
        sort["grounds"] += [{"id": "bench", "is": "feature"}, {"id": "lamp", "is": "feature"}]
        relate["grounds"] += [{"id": "bench", "kind": "bench", "by": "entrance"},
                              {"id": "lamp", "kind": "lantern", "size": "large", "by": "bench"}]

    spec, layout, refused = _lay(_court(mutate))
    _laid_all(spec, refused, ["court", "bench", "lamp"])
    bench = next(f["rect"] for f in layout.features if f["id"] == "bench")
    assert min(bench.w, bench.d) >= 2
    # at the entrance -- read as by the court, it stood ten paces off, and
    # never came near the ground it was laid clear of (a review of
    # 2026-10-14) -- and never on its step or the pace past it
    door = next(d for d in layout.doors if d.get("b") == "entrance")
    sx, sy = _STEP[door["side"]]
    kept = {(door["cell"][0] + sx * k + (1 - abs(sx)) * m, door["cell"][1] + sy * k + (1 - abs(sy)) * m)
            for k in (1, 2) for m in (-1, 0, 1)}
    near = min(abs(x - door["cell"][0]) + abs(y - door["cell"][1]) for x, y in bench.cells())
    assert near <= 4, (bench, door)
    assert not bench.cells() & kept, (bench, door)


def test_a_thing_by_a_way_leaving_the_ground_never_takes_its_mouth():
    """The lane leaves the court eastward; a thing by it stood on the court's
    cells at its mouth, the court and the lane no longer touched, and the
    thing -- once the lane too -- was dropped."""
    def mutate(specs, sort, relate):
        specs["court"][1]["adjacent"] = [dict(e, dir="e") if e["to"] == "lane" else e
                                         for e in specs["court"][1]["adjacent"]]
        specs["lane"][1]["adjacent"] = [{"to": "court", "dir": "w"}, {"to": "bench", "dir": "n"}]
        _add(specs, "bench", "the Bench", "a stone bench", [{"to": "lane", "dir": "s"}],
             exposure="open")
        for g in relate["grounds"]:
            if g["id"] == "lane":
                g.pop("from", None)
        sort["grounds"].append({"id": "bench", "is": "feature"})
        relate["grounds"].append({"id": "bench", "kind": "bench", "by": "lane"})

    spec, _layout, refused = _lay(_court(mutate))
    _laid_all(spec, refused, ["court", "lane", "bench", "shed"])


def test_a_walk_two_paces_wide_never_leaves_a_step_a_sliver():
    """A privy before the entrance, its walk from the hall's west door: laid
    two wide it took the two rows by the privy, left the row under the
    entrance a pace wide, and the court lost its doorway."""
    def mutate(specs, sort, relate):
        specs.pop("shed")
        specs["court"][1]["adjacent"] = [e for e in specs["court"][1]["adjacent"] if e["to"] != "shed"]
        sort["grounds"] = [g for g in sort["grounds"] if g["id"] != "shed"]
        relate["grounds"] = [g for g in relate["grounds"] if g["id"] != "shed"]
        specs["hall"][1]["adjacent"].append({"to": "privy", "dir": "s", "barrier": "closed_door"})
        _add(specs, "privy", "the Privy", "a privy", [{"to": "hall", "dir": "n"}])
        sort["grounds"].append({"id": "privy", "is": "outbuilding"})
        relate["grounds"].append({"id": "privy", "side": "s"})

    spec, _layout, refused = _lay(_court(mutate))
    _laid_all(spec, refused, ["court", "lane", "privy"])
    # the solver's own rule, where a privy does stand before the entrance --
    # a spec that names no end of its side: its walk keeps off the ground at
    # the entrance's step, every seed
    b, spec = _spec(_court(mutate))
    for block in spec["blocks"]:
        if block["id"] == "privy":
            block.pop("toward", None)
    for k in range(4):
        layout = solve(copy.deepcopy(spec), seed=SEED + k)
        door = next(d for d in layout.doors if d.get("b") == "entrance")
        sx, sy = _STEP[door["side"]]
        lx, ly = (1, 0) if door["side"] in "ns" else (0, 1)
        kept = {(door["cell"][0] + sx * (1 + j) + lx * m, door["cell"][1] + sy * (1 + j) + ly * m)
                for j in (0, 1) for m in (-1, 0, 1)}
        assert not layout.ways["privy__way"]["cells"] & kept, k
        assert not [w for w, _p in lb.ground_breaches(b, spec, layout) if "court's doorway" in w], k


def test_a_walkway_between_two_doors_is_laid_two_paces_wide_and_written():
    """A covered walkway the washroom and the kitchen both open onto, no
    start of its own: laid a pace wide it was written as nothing -- the world
    reads no place narrower than two paces, and a way is never widened on
    writing -- and dropped. Where the world asks it, it is laid two wide."""
    def mutate(specs, sort, relate):
        for room, d in (("washroom", "s"), ("kitchen", "s")):
            specs[room][1]["adjacent"].append({"to": "walkway", "dir": d, "barrier": "open_door"})
        _add(specs, "walkway", "the Walkway", "a covered walkway",
             [{"to": "washroom", "dir": "n"}, {"to": "kitchen", "dir": "n"}], exposure="sheltered")
        sort["grounds"].append({"id": "walkway", "is": "way"})
        relate["grounds"].append({"id": "walkway"})

    b, spec = _spec(_farm(mutate))
    assert spec["grounds"]["narrowest"] == 2
    for k in range(4):
        layout = solve(copy.deepcopy(spec), seed=SEED + k)
        solved, report = lb.planned_layout(b, spec, layout)
        assert "walkway" not in report["grounds_unplaced"], k
        walk = layout.ways["walkway"]["cells"]
        assert any({(x + 1, y), (x, y + 1), (x + 1, y + 1)} <= walk for x, y in walk)


def test_an_outbuilding_on_the_front_stands_toward_its_rooms_end():
    """The plan puts the farm's privy south of the washroom -- the front of
    the house: centred on that side it stood before the entrance, across the
    path, and the gate at the path's foot was dropped. It stands toward the
    washroom's end of the front."""
    def mutate(specs, sort, relate):
        specs["washroom"][1]["adjacent"] = [e for e in specs["washroom"][1]["adjacent"]
                                            if e["to"] != "privy"]
        specs["washroom"][1]["adjacent"].append({"to": "privy", "dir": "s", "barrier": "closed_door"})
        specs["privy"][1]["adjacent"] = [{"to": "washroom", "dir": "n"}]
        # answered on the plan's own side, which names no end: the plan's
        # bearings alone say which
        next(g for g in relate["grounds"] if g["id"] == "privy")["side"] = "s"

    plan = _farm(mutate)
    _b, spec = _spec(plan)
    block = next(x for x in spec["blocks"] if x["id"] == "privy")
    assert block["beside"]["side"] == "s" and block.get("toward") == "w"
    spec2, _layout, refused = _lay(plan)
    _laid_all(spec2, refused, ["garden", "gate", "path", "privy", "tree", "well"])


# ------------------------------------------------------------- ways


def test_a_way_leaving_its_ground_never_runs_through_a_building():
    """A lane joined to the garden round the house, leaving it southward:
    the garden's far south edge lay beside the house, the court band beyond
    it, and the lane ran straight over the storehouse standing in the court
    -- which was then charged for cutting the lane, and dropped."""
    def mutate(specs, sort, relate):
        specs["side"][1]["adjacent"].append({"to": "garden", "dir": "e", "barrier": "closed_door"})
        _add(specs, "garden", "the Garden", "a garden",
             [{"to": "side", "dir": "w"}, {"to": "lane", "dir": "s"}], exposure="open")
        specs["lane"] = ("the Lane", {"purpose": "a lane down the hill", "structure": "court",
                                      "exposure": "open", "adjacent": [{"to": "garden", "dir": "n"}]})
        specs["court"][1]["adjacent"] = [e for e in specs["court"][1]["adjacent"] if e["to"] != "lane"]
        sort["grounds"].append({"id": "garden", "is": "open"})
        relate["grounds"] = [g for g in relate["grounds"] if g["id"] != "lane"]
        relate["grounds"] += [{"id": "lane"}, {"id": "garden", "where": "around"}]

    spec, layout, refused = _lay(_court(mutate))
    _laid_all(spec, refused, ["court", "garden", "lane", "shed"])
    lane = layout.ways["lane"]["cells"]
    assert not lane & layout.areas["court"]
    for rects in layout.floors[0].values():
        for r in rects:
            assert not lane & r.cells()


def test_a_way_leaving_the_garden_never_runs_on_from_the_approach():
    """The entrance opens onto the path, whose cells are the garden's too: a
    lane joined to the garden alone was laid in line with the entrance, on
    from the path's foot, and the gate there and the lane were dropped."""
    def mutate(specs, sort, relate):
        _add(specs, "lane", "the Lane", "a lane to the fields", [{"to": "garden", "dir": "n"}],
             exposure="open")
        specs["garden"][1]["adjacent"].append({"to": "lane", "dir": "s"})
        sort["grounds"].append({"id": "lane", "is": "way"})
        relate["grounds"].append({"id": "lane"})

    spec, layout, refused = _lay(_farm(mutate))
    _laid_all(spec, refused, ["garden", "gate", "lane", "path", "privy", "tree", "well"])
    path_foot = {x for x, _y in layout.ways["path"]["rows"][-1]}
    lane_head = {x for x, _y in layout.ways["lane"]["rows"][0]}
    assert lane_head != path_foot, "laid on in line from the path's foot"


# ------------------------------------------------------ outbuildings


def test_two_outbuildings_never_stand_one_pace_apart():
    """A byre the plan bears along the court's own axis stood centred, one
    pace from the storehouse borne west: the storehouse's door opened into
    the one-pace gap, onto ground no place is read to hold, and it was
    dropped."""
    def mutate(specs, sort, relate):
        specs.pop("side")
        specs["hall"][1]["adjacent"] = [e for e in specs["hall"][1]["adjacent"] if e["to"] != "side"]
        sort["rooms"] = [r for r in sort["rooms"] if r["id"] != "side"]
        relate["rooms"] = [r for r in relate["rooms"] if r["id"] != "side"]
        _add(specs, "byre", "the Byre", "a byre", [{"to": "court", "dir": "n"}])
        specs["court"][1]["adjacent"].append({"to": "byre", "dir": "s"})
        sort["grounds"].append({"id": "byre", "is": "outbuilding"})
        relate["grounds"].append({"id": "byre", "side": "s"})

    spec, layout, refused = _lay(_court(mutate))
    _laid_all(spec, refused, ["byre", "court", "lane", "shed"])
    shed, byre = layout.floors[0]["shed"][0], layout.floors[0]["byre"][0]
    gx = max(byre.x - (shed.x + shed.w), shed.x - (byre.x + byre.w))
    gy = max(byre.y - (shed.y + shed.d), shed.y - (byre.y + byre.d))
    assert not ((gx == 1 and gy < 0) or (gy == 1 and gx < 0))


def test_an_outbuilding_stands_on_the_side_the_plans_way_to_it_faces():
    """The plan joins the hall's west wall to the privy; the answer stood
    the privy east. Its walk ran round the house from the west door and cut
    the ground. The plan's way is the fact."""
    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"].append({"to": "privy", "dir": "w", "barrier": "closed_door"})
        _add(specs, "privy", "the Privy", "a privy", [{"to": "hall", "dir": "e"}])
        sort["grounds"].append({"id": "privy", "is": "outbuilding"})
        relate["grounds"].append({"id": "privy", "side": "e"})

    b, spec = _spec(_court(mutate))
    block = next(x for x in spec["blocks"] if x["id"] == "privy")
    assert block["beside"]["side"] == "w"


# ---------------------------------------------------------- things


def test_a_thing_joined_to_open_ground_alone_stands_in_it():
    """A lantern joined to the court alone, no relation answered: it stood
    as far from everything as the plot allowed, touching no court, and was
    dropped."""
    def mutate(specs, sort, relate):
        specs["court"][1]["adjacent"].append({"to": "lantern", "dir": "e"})
        _add(specs, "lantern", "the Lantern", "a stone lantern", [{"to": "court", "dir": "w"}],
             exposure="open")
        sort["grounds"].append({"id": "lantern", "is": "feature"})
        relate["grounds"].append({"id": "lantern", "kind": "lantern"})

    b, spec = _spec(_court(mutate))
    assert next(f for f in spec["grounds"]["features"] if f["id"] == "lantern")["by"] == "court"
    spec2, layout, refused = _lay(_court(mutate))
    _laid_all(spec2, refused, ["court", "lane", "lantern", "shed"])
    rect = next(f["rect"] for f in layout.features if f["id"] == "lantern")
    assert any((x + dx, y + dy) in layout.areas["court"] for x, y in rect.cells()
               for dx, dy in _STEP.values())


# ------------------------------------------------- the whole building


PLAN_106 = {
    "hall": ("the Hall", {"purpose": "a hall with a hearth", "structure": "h", "exposure": "enclosed",
                          "adjacent": [{"to": "side", "dir": "e", "barrier": "closed_door"},
                                       {"to": "kitchen", "dir": "n", "barrier": "open_door"},
                                       {"to": "loft", "vertical": "up", "way": "ladder"},
                                       {"to": "path", "dir": "s", "barrier": "open_door"}]}),
    "side": ("the Side Room", {"purpose": "a sleeping room", "structure": "h", "exposure": "enclosed",
                               "adjacent": [{"to": "hall", "dir": "w", "barrier": "closed_door"},
                                            {"to": "garden", "dir": "s", "barrier": "open_door"},
                                            {"to": "woodpile", "dir": "e", "barrier": "closed_door"}]}),
    "kitchen": ("the Kitchen", {"purpose": "a kitchen with a stove", "structure": "h",
                                "exposure": "enclosed",
                                "adjacent": [{"to": "hall", "dir": "s", "barrier": "open_door"}]}),
    "loft": ("the Loft", {"purpose": "a loft", "structure": "h", "exposure": "enclosed",
                          "adjacent": [{"to": "hall", "vertical": "down", "way": "ladder"}]}),
    "path": ("the Path", {"purpose": "a gravel path", "structure": "h", "exposure": "open",
                          "adjacent": [{"to": "hall", "dir": "n"}, {"to": "lantern", "dir": "s"},
                                       {"to": "gate", "dir": "s"}]}),
    "garden": ("the Garden", {"purpose": "a garden", "structure": "h", "exposure": "open",
                              "adjacent": [{"to": "side", "dir": "n"}, {"to": "shed", "dir": "e"},
                                           {"to": "byre", "dir": "s"}]}),
    "woodpile": ("the Woodpile", {"purpose": "a stack of firewood", "structure": "h",
                                  "exposure": "open", "adjacent": [{"to": "side", "dir": "w"}]}),
    "lantern": ("the Lantern", {"purpose": "a stone lantern", "structure": "h", "exposure": "open",
                                "adjacent": [{"to": "path", "dir": "n"}]}),
    "gate": ("the Gate", {"purpose": "a gate", "structure": "h", "exposure": "open",
                          "adjacent": [{"to": "path", "dir": "n"}]}),
    "shed": ("the Shed", {"purpose": "a storehouse", "structure": "h",
                          "adjacent": [{"to": "garden", "dir": "w"}]}),
    "byre": ("the Byre", {"purpose": "a byre", "structure": "h",
                          "adjacent": [{"to": "garden", "dir": "n"}]}),
}
SORT_106 = {"rooms": [{"id": "hall", "fixtures": [{"id": "hearth", "name": "hearth", "mount": "floor"}]},
                      {"id": "side", "fixtures": [{"id": "bed", "name": "bed", "mount": "floor"}]},
                      {"id": "kitchen", "fixtures": [{"id": "stove", "name": "stove", "mount": "floor"}]},
                      {"id": "loft", "fixtures": []}],
            "stairs": [{"from": "hall", "to": "loft", "enclosed": False}],
            "grounds": [{"id": "path", "is": "way"}, {"id": "garden", "is": "open"},
                        {"id": "woodpile", "is": "feature"}, {"id": "lantern", "is": "feature"},
                        {"id": "gate", "is": "feature"}, {"id": "shed", "is": "outbuilding"},
                        {"id": "byre", "is": "outbuilding"}]}
RELATE_106 = {"rooms": [{"id": "hall", "purpose": "hall", "fixtures": [{"id": "hearth", "kind": "hearth", "at": "w"}]},
                        {"id": "side", "purpose": "bedroom", "fixtures": [{"id": "bed", "kind": "bed", "at": "w"}]},
                        {"id": "kitchen", "purpose": "kitchen", "fixtures": [{"id": "stove", "kind": "stove", "at": "s"}]},
                        {"id": "loft", "purpose": "storage", "fixtures": []}],
              "stairs": [{"from": "hall", "to": "loft", "from_at": "n", "to_at": "n", "kind": "ladder"}],
              "grounds": [{"id": "path", "from": "entrance"}, {"id": "garden", "where": "w"},
                          {"id": "woodpile", "kind": "barrel", "by": "side", "side": "e"},
                          {"id": "lantern", "kind": "lantern", "by": "path", "side": "w"},
                          {"id": "gate", "kind": "gate", "across": "path", "end": "far"},
                          {"id": "shed", "side": "w"}, {"id": "byre", "side": "n"}]}


def test_a_thing_with_no_wall_for_its_door_costs_only_itself():
    """The review's plan 106: the side room's one outside wall holds its door
    onto the garden and no other a pace clear of it, so its woodpile found no
    door and was dropped -- and dropped, it asked for a band and a door of
    its own, and the whole building was refused. Its way now opens through
    the room's door onto the garden; the woodpile alone may be left out, and
    nothing else. (The tier's arrangement-first core gives that room a
    second outside wall, and lays the woodpile too: 2026-10-15.)"""
    plan = (copy.deepcopy(PLAN_106), {"rooms": {}, "positions": {}, "entities": {}}, set(),
            copy.deepcopy(SORT_106), copy.deepcopy(RELATE_106))
    spec, _layout, refused = _lay(plan)
    assert refused == []
    assert spec.get("places_dropped") in (None, ["woodpile"])
    assert {"garden", "path", "lantern", "gate", "shed", "byre"} <= set(spec["ground_is"])


# --------------------------------------------- the third review's geometry


def _without_the_shed(specs, sort, relate):
    specs.pop("shed")
    specs["court"][1]["adjacent"] = [e for e in specs["court"][1]["adjacent"] if e["to"] != "shed"]
    sort["grounds"] = [g for g in sort["grounds"] if g["id"] != "shed"]
    relate["grounds"] = [g for g in relate["grounds"] if g["id"] != "shed"]


def test_a_thing_whose_door_turns_has_plot_past_the_wall_it_turns_to():
    """A yew six paces across, round, the plan joins to the hall's south
    wall beside the entrance: no box at that door held its step clear of the
    entrance's ground, so its door turned to the hall's west wall -- which
    the plot reached five paces past, and the yew was dropped on every seed.
    The plot reaches past every wall its door may turn to."""
    def mutate(specs, sort, relate):
        _without_the_shed(specs, sort, relate)
        specs["hall"][1]["adjacent"].append({"to": "yew", "dir": "s", "barrier": "closed_door"})
        _add(specs, "yew", "the Yew", "an old yew", [{"to": "hall", "dir": "n"}], exposure="open",
             shape="round")
        sort["grounds"].append({"id": "yew", "is": "feature"})
        relate["grounds"].append({"id": "yew", "kind": "tree", "size": "huge", "by": "hall"})

    spec, _layout, refused = _lay(_court(mutate))
    _laid_all(spec, refused, ["court", "lane", "yew"])


def test_a_thing_by_a_way_on_a_side_of_it_stands_beside_it_never_past_its_end():
    """A lantern by the lane's far end, east of it, and a gate across that
    end: a box just past the end, half a pace east of the lane's line,
    scored as well as one beside it, the lantern stood there, and the gate
    across the end was dropped. On a side of a way is beside it."""
    def mutate(specs, sort, relate):
        specs["lane"][1]["adjacent"] += [{"to": "gate", "dir": "s"}, {"to": "lantern", "dir": "e"}]
        _add(specs, "gate", "the Gate", "a gate", [{"to": "lane", "dir": "n"}], exposure="open")
        _add(specs, "lantern", "the Lantern", "a stone lantern", [{"to": "lane", "dir": "w"}],
             exposure="open")
        sort["grounds"] += [{"id": "gate", "is": "feature"}, {"id": "lantern", "is": "feature"}]
        relate["grounds"] += [{"id": "gate", "kind": "gate", "across": "lane", "end": "far"},
                              {"id": "lantern", "kind": "lantern", "by": "lane", "end": "far",
                               "side": "e"}]

    spec, _layout, refused = _lay(_court(mutate))
    _laid_all(spec, refused, ["court", "lane", "gate", "lantern", "shed"])
    for k in range(4):
        layout = solve(copy.deepcopy(spec), seed=SEED + k)
        lane = layout.ways["lane"]["cells"]
        rect = next(f["rect"] for f in layout.features if f["id"] == "lantern")
        ys = {y for _x, y in lane}
        assert min(x for x, _y in rect.cells()) > max(x for x, _y in lane), (k, rect)
        assert {y for _x, y in rect.cells()} & ys, (k, rect)


def test_a_block_below_ground_never_moves_a_building_above_it():
    """A privy north of the hall, over the footprint of a cavern cut north of
    the basement: the cavern's block stands below ground alone, yet the
    privy was pushed five paces east off it, and the lab's shrine moved its
    latrine by the order its rooms were listed in. What crowds a building
    stands at the ground."""
    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"] += [{"to": "basement", "vertical": "down", "way": "stair"},
                                         {"to": "privy", "dir": "n", "barrier": "closed_door"}]
        specs["basement"] = ("the Basement", {
            "purpose": "a storage basement", "structure": "court", "exposure": "enclosed",
            "adjacent": [{"to": "hall", "vertical": "up", "way": "stair"},
                         {"to": "cavern", "dir": "n", "barrier": "closed_door"}]})
        specs["cavern"] = ("the Seal Cavern", {
            "purpose": "a sealed cavern", "structure": "court", "exposure": "enclosed", "shape": "round",
            "adjacent": [{"to": "basement", "dir": "s", "barrier": "closed_door"}]})
        _add(specs, "privy", "the Privy", "a privy", [{"to": "hall", "dir": "s"}])
        sort["rooms"] += [{"id": "basement", "fixtures": [{"id": "crates", "name": "crates", "mount": "floor"}]},
                          {"id": "cavern", "fixtures": [{"id": "seal", "name": "the seal stone",
                                                         "mount": "floor"}]}]
        sort["stairs"].append({"from": "hall", "to": "basement", "enclosed": False})
        sort["grounds"].append({"id": "privy", "is": "outbuilding"})
        relate["rooms"] += [{"id": "basement", "purpose": "storage",
                             "fixtures": [{"id": "crates", "kind": "crate", "at": "e"}]},
                            {"id": "cavern", "purpose": "other",
                             "fixtures": [{"id": "seal", "kind": "boulder", "at": "middle"}]}]
        relate["stairs"].append({"from": "hall", "to": "basement", "from_at": "n", "to_at": "n"})
        relate["grounds"].append({"id": "privy", "side": "n"})

    _b, spec = _spec(_court(mutate))
    for k in range(4):
        layout = solve(copy.deepcopy(spec), seed=SEED + k)
        main, privy = layout.outlines["main"][0], layout.outlines["privy"][0]
        assert 0 not in layout.outlines["cavern"], k
        assert privy.cells() & {(x, y) for x, y in layout.outlines["cavern"][-1].cells()}, k
        assert privy.x == main.x + (main.w - privy.w) // 2, (k, privy, main)
