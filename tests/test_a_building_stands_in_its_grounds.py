"""A planned building is laid out with the ground it stands in.

The owner's shrine (chat 167, "Home 5", 2026-10-11): the layout tier laid
out the house and left every outdoor place where the Writers' Room's own
estimates put it -- a 60 by 60 garden, a 20 by 20 camphor tree and a lantern
path forty long, each a box beside a house a fraction their size -- where the
layout lab's liked shrine stood in its garden, its approach running from the
front door to the torii. The owner chose "Tier lays out the grounds": the
places stay the plan's rooms, a first call says what each IS on the ground
(open ground, a way, a feature, an outbuilding), a second where, and the
solver lays them round the house (`layout_bridge._grounds_of`,
`_ground_plan`, `_ground_geometry`). Hand-made plans and stand-in answers;
the names are illustrations, not the rule.
"""
from __future__ import annotations

import copy

from world import layout_bridge as lb

E = "enclosed"
SPECS = {
    "hall": ("the Hall", {
        "purpose": "a hall with a hearth", "structure": "farm", "exposure": E,
        "adjacent": [{"to": "path", "dir": "s", "barrier": "open_door"},
                     {"to": "kitchen", "dir": "e", "barrier": "open_door"},
                     {"to": "washroom", "dir": "w", "barrier": "open_door"},
                     {"to": "loft", "vertical": "up", "way": "stair"}]}),
    "kitchen": ("the Kitchen", {
        "purpose": "a kitchen with a range", "structure": "farm", "exposure": E,
        "adjacent": [{"to": "hall", "dir": "w", "barrier": "open_door"},
                     {"to": "well", "dir": "s", "barrier": "closed_door"}]}),
    "washroom": ("the Washroom", {
        "purpose": "a washroom with a tub", "structure": "farm", "exposure": E,
        "adjacent": [{"to": "hall", "dir": "e", "barrier": "open_door"},
                     {"to": "privy", "dir": "n", "barrier": "closed_door"}]}),
    "loft": ("the Loft", {"purpose": "a sleeping loft", "structure": "farm",
                          "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"}]}),
    "path": ("the Path", {"purpose": "a gravel path to the gate", "structure": "farm",
                          "exposure": "open",
                          "adjacent": [{"to": "hall", "dir": "n"}, {"to": "gate", "dir": "s"},
                                       {"to": "garden", "dir": "w"}]}),
    "gate": ("the Gate", {"purpose": "a wooden gate", "structure": "farm", "exposure": "open",
                          "adjacent": [{"to": "path", "dir": "n"}, {"to": "road", "dir": "s"}]}),
    "road": ("the Road", {"purpose": "the road", "structure": "farm", "exposure": "open",
                          "adjacent": [{"to": "gate", "dir": "n"}]}),
    "garden": ("the Garden", {"purpose": "a kitchen garden", "structure": "farm",
                              "exposure": "open", "shape": "composite",
                              "adjacent": [{"to": "path", "dir": "e"}, {"to": "tree", "dir": "n"},
                                           {"to": "pond", "dir": "w"}]}),
    "tree": ("the Old Oak", {"purpose": "an old oak", "structure": "farm", "exposure": "open",
                             "shape": "round", "adjacent": [{"to": "garden", "dir": "s"}]}),
    "pond": ("the Pond", {"purpose": "a duck pond", "structure": "farm", "exposure": "open",
                          "adjacent": [{"to": "garden", "dir": "e"}]}),
    "well": ("the Well", {"purpose": "a stone well", "structure": "farm", "exposure": "open",
                          "shape": "round", "adjacent": [{"to": "kitchen", "dir": "n"}]}),
    "privy": ("the Privy", {"purpose": "a privy", "structure": "farm",
                            "adjacent": [{"to": "washroom", "dir": "s"}]}),
}
#: the pond the story has described, and the road a frontier space
SCENE = {"rooms": {"pond": {"name": "the Pond", "desc": "A green duck pond."}},
         "positions": {}, "entities": {}}
HELD_OPEN = {"road"}

SORT = {"rooms": [
    {"id": "hall", "fixtures": [{"id": "hearth", "name": "the hearth", "mount": "floor"}]},
    {"id": "kitchen", "fixtures": [{"id": "range", "name": "the range", "mount": "floor"}]},
    {"id": "washroom", "fixtures": [{"id": "tub", "name": "the tub", "mount": "floor"}]},
    {"id": "loft", "fixtures": [{"id": "bed", "name": "a bed", "mount": "floor"}]}],
    "stairs": [{"from": "hall", "to": "loft", "enclosed": False}],
    "grounds": [{"id": "path", "is": "way"}, {"id": "gate", "is": "feature"},
                {"id": "garden", "is": "open"}, {"id": "tree", "is": "feature"},
                {"id": "well", "is": "feature"}, {"id": "privy", "is": "outbuilding"}]}
RELATE = {"rooms": [
    {"id": "hall", "purpose": "hall", "fixtures": [{"id": "hearth", "kind": "hearth", "at": "n"}]},
    {"id": "kitchen", "purpose": "kitchen", "fixtures": [{"id": "range", "kind": "stove", "at": "e"}]},
    {"id": "washroom", "purpose": "other", "fixtures": [{"id": "tub", "kind": "bath", "at": "w"}]},
    {"id": "loft", "purpose": "bedroom", "fixtures": [{"id": "bed", "kind": "bed", "at": "e"}]}],
    "stairs": [{"from": "hall", "to": "loft", "from_at": "n", "to_at": "n"}],
    "grounds": [{"id": "path", "from": "entrance", "to": "gate"}, {"id": "gate", "kind": "gate"},
                {"id": "garden", "where": "around"}, {"id": "tree", "kind": "tree", "side": "n"},
                {"id": "well", "kind": "well", "by": "kitchen"}, {"id": "privy", "side": "w"}]}


def _building(grounds=True):
    found = lb.plan_buildings(copy.deepcopy(SPECS), copy.deepcopy(SCENE),
                              held_open=HELD_OPEN, grounds=grounds)
    return max(found, key=lambda b: len(b["rooms"]))


def _laid(sort=SORT, relate=RELATE):
    b = _building()
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    layout, refused = lb.solve_for(b, spec)
    solved, report = lb.planned_layout(b, spec, layout)
    return b, spec, layout, refused, solved, report


def _cells(geometry):
    site, extent = geometry["site"], geometry["extent"]
    parts = geometry.get("parts") or [{"w": extent["w"], "d": extent["d"], "at": [0, 0]}]
    return {(site["x"] + p["at"][0] + i, site["y"] + p["at"][1] + j)
            for p in parts for i in range(p["w"]) for j in range(p["d"])}


def test_the_grounds_are_the_outdoor_places_its_doors_reach_and_nothing_decided():
    b = _building()
    assert b["refusal"] is None
    assert [g["id"] for g in b["grounds"]] == ["path", "well", "privy", "garden", "gate", "tree"]
    assert {g["id"]: g["hop"] for g in b["grounds"]}["tree"] == 3
    # a frontier space and a place the story has described are not ground
    assert not {"road", "pond"} & {g["id"] for g in b["grounds"]}
    assert set(b["ground_specs"]) == {g["id"] for g in b["grounds"]}
    # off, the building is what it always was
    assert "grounds" not in _building(grounds=False)


def test_each_place_is_what_the_first_call_sorted_it_to_be_and_nothing_else():
    b = _building()
    held = lb.hold_grounds(b, [{"id": "path", "is": "way"}, {"id": "path", "is": "open"},
                               {"id": "gate", "is": "a gate"}, {"id": "hall", "is": "open"},
                               {"id": "road", "is": "way"}, "nonsense"])
    assert held == [{"id": "path", "name": "the Path", "is": "way"}]


def test_the_grounds_are_laid_round_the_house_and_written_onto_its_plan():
    b, spec, _layout, refused, solved, report = _laid()
    assert not refused and report["grounds_unplaced"] == []
    house = set()
    for uid in b["rooms"]:
        if solved[uid]["geometry"]["level"] == 0:
            house |= _cells(solved[uid]["geometry"])
    garden = solved["garden"]["geometry"]
    # open ground is a composite round the house: the house stands in its hole
    assert garden["shape"] == "composite" and len(garden["parts"]) > 1
    assert not _cells(garden) & house
    for pid in ("path", "well", "privy", "garden", "gate", "tree"):
        geometry = solved[pid]["geometry"]
        assert geometry["site"]["plan"] == b["plan"] and geometry["level"] == 0
        assert solved[pid]["layout"]["grounds"] == spec["ground_is"][pid]
    # the approach runs from the front door, south, and the gate stands at its end
    path, gate, hall = (solved[k]["geometry"] for k in ("path", "gate", "hall"))
    assert path["site"]["y"] >= hall["site"]["y"] + hall["extent"]["d"]
    assert gate["site"]["y"] >= path["site"]["y"] + path["extent"]["d"] - 1
    # a feature is the size of the thing, and one planned round stays round
    assert solved["tree"]["geometry"]["extent"] == {"w": 3, "d": 3}
    assert "shape" not in solved["tree"]["geometry"]
    tree = solved["tree"]["geometry"]
    assert tree["site"]["y"] + tree["extent"]["d"] <= min(y for _x, y in house)
    # the outbuilding stands apart, with its own doorway to the room it joins
    assert not _cells(solved["privy"]["geometry"]) & house
    assert "washroom" in solved["privy"]["edges"]


def test_a_door_onto_a_feature_is_still_the_doorway_to_the_place_the_plan_names():
    """The kitchen's back door opens onto the ground the well stands in, and
    is written as the kitchen's doorway to the well, on the wall the solve
    found."""
    b, spec, layout, _refused, solved, _report = _laid()
    assert spec["door_to"]["well"] == "garden"
    assert any(d.get("outside") and d["a"] == "kitchen" and d["b"] == "garden"
               for d in layout.doors)
    assert set(solved["kitchen"]["edges"]["well"]) == {"dir", "offset"}
    assert "garden" not in solved["kitchen"]["edges"]


def test_a_place_the_first_call_left_unsaid_is_laid_as_the_tier_always_laid_it():
    """Unsaid, a place the house opens straight onto is open ground on the
    side its doorway states -- as before the grounds -- and one further out
    is not laid at all."""
    sort = dict(SORT, grounds=[g for g in SORT["grounds"] if g["id"] not in ("path", "tree")])
    relate = dict(RELATE, grounds=[g for g in RELATE["grounds"] if g["id"] not in ("path", "tree")])
    _b, spec, _layout, refused, solved, _report = _laid(sort, relate)
    assert not refused
    assert spec["ground_is"]["path"] == "open"
    assert "tree" not in spec["ground_is"] and "tree" not in solved


def test_the_grounds_are_on_unless_turned_off(temp_db):
    """On since the owner saw the comparison: "I would like layout grounds
    on" (2026-10-11). The host's setting turns them off; the story's own key
    reads first, either way."""
    from agents import director_layout as dl
    from core.db import set_setting, wset
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES('g','',0)")
    assert dl.layout_grounds_enabled(cid) is True
    for word in ("off", "0", "false", "no"):
        set_setting(dl.LAYOUT_GROUNDS_SETTING, word)
        assert dl.layout_grounds_enabled(cid) is False, word
    wset(cid, dl.LAYOUT_GROUNDS_STORY_KEY, "on")
    assert dl.layout_grounds_enabled(cid) is True
    set_setting(dl.LAYOUT_GROUNDS_SETTING, "on")
    wset(cid, dl.LAYOUT_GROUNDS_STORY_KEY, "off")
    assert dl.layout_grounds_enabled(cid) is False


def test_a_composites_parts_go_onto_its_stub_and_come_off_with_the_solve():
    from world import structure
    spec = {"extent": {"w": 6, "d": 5}, "shape": "composite",
            "parts": [{"w": 6, "d": 2, "at": [0, 0]}, {"w": 2, "d": 3, "at": [0, 2]}],
            "site": {"plan": "layout:hall", "x": 0, "y": 0}}
    assert structure.planned_geometry(spec)["parts"] == spec["parts"]
    # a part the world cannot place is no part
    assert "parts" not in structure.planned_geometry(dict(spec, parts="a ring"))
    room = {"name": "the Garden"}
    structure._lay_stub_on_its_plan(room, spec)
    assert room["parts"] == spec["parts"]
    structure._take_the_solve_off(room, {"shape": "composite"}, room[structure.LAID_OUT_KEY])
    assert "parts" not in room and "site" not in room


def _stub_scene(specs, desc=()):
    """Every planned room as a prose-free stub, the ones named in `desc`
    described."""
    rooms = {}
    for uid, (name, spec) in specs.items():
        rooms[uid] = {"name": name, "planned": True,
                      "adjacent": [dict(e) for e in spec.get("adjacent") or ()]}
        if uid in desc:
            rooms[uid]["desc"] = f"{name}, as the story has it."
    return {"rooms": rooms, "positions": {}, "entities": {}}


def test_every_cell_is_one_places_and_the_world_reads_each_as_solved():
    """The solver's open ground is the ground its ways and features stand
    on; as rooms of their own they are taken out of it, so the garden, the
    path, the gate, the well, the oak, the privy and the house share no
    cell -- and the world's own grid reads each place as exactly the cells
    the solve gave it, though it reads no side or part narrower than two
    paces (`EXTENT_MIN_PACES`)."""
    from world.spatial import room_grid
    b, _spec, _layout, _refused, solved, _report = _laid()
    ground = [pid for pid in ("path", "well", "privy", "garden", "gate", "tree")]
    level0 = [uid for uid in b["rooms"] if solved[uid]["geometry"]["level"] == 0] + ground
    cells = {uid: _cells(solved[uid]["geometry"]) for uid in level0}
    for i, a in enumerate(level0):
        for other in level0[i + 1:]:
            assert not cells[a] & cells[other], (a, other)
    for pid in ground:
        geometry = solved[pid]["geometry"]
        stub = {"name": pid, **{k: v for k, v in geometry.items() if v is not None}}
        if "shape" not in stub:
            stub["shape"] = SPECS[pid][1].get("shape") or "rectangle"
        grid = room_grid({"rooms": {pid: stub}}, pid)
        site = geometry["site"]
        read = {(site["x"] + x, site["y"] + y) for x, y in grid.cells}
        if stub["shape"] in ("rectangle", "composite"):
            assert read == cells[pid], pid
        else:
            assert read <= cells[pid], pid      # a round thing inside its box
        for part in geometry.get("parts") or ():
            assert part["w"] >= 2 and part["d"] >= 2, (pid, part)
        assert geometry["extent"]["w"] >= 2 and geometry["extent"]["d"] >= 2, pid


def test_a_thing_a_pace_across_is_a_place_two_paces_across():
    """The solver lays a gate a pace deep across the way's far end; as a
    place a body stands at it is two, over the ground no other place
    holds -- never over the path."""
    _b, _spec, _layout, _refused, solved, _report = _laid()
    gate, path = solved["gate"]["geometry"], solved["path"]["geometry"]
    assert gate["extent"] == {"w": 3, "d": 2}
    assert not _cells(gate) & _cells(path)


def test_every_doorway_onto_the_ground_meets_its_other_side():
    """The lab converter's measure of a plan that holds together: a house
    door's other side is the cell across its threshold on the place it
    opens onto, or the nearest cell of the thing standing by it; two places
    of the ground the plan joins meet where they touch, on opposite sides of
    one line."""
    from world.layout_bridge import _UNIT
    b, _spec, layout, _refused, solved, _report = _laid()

    def at(pid, edge):
        geometry = solved[pid]["geometry"]
        site = geometry["site"]
        if edge.get("cell") is not None:
            return (site["x"] + edge["cell"][0], site["y"] + edge["cell"][1])
        x0, y0, w, d = site["x"], site["y"], geometry["extent"]["w"], geometry["extent"]["d"]
        along = round(edge["offset"] * ((w if edge["dir"] in "ns" else d) - 1))
        return {"n": (x0 + along, y0), "s": (x0 + along, y0 + d - 1),
                "w": (x0, y0 + along), "e": (x0 + w - 1, y0 + along)}[edge["dir"]]

    # the front door: the path's doorway is the cell across the hall's threshold
    hall_door = at("hall", solved["hall"]["edges"]["path"])
    path_door = at("path", solved["path"]["edges"]["hall"])
    ux, uy = _UNIT[solved["hall"]["edges"]["path"]["dir"]]
    assert path_door == (hall_door[0] + ux, hall_door[1] + uy)
    assert solved["path"]["edges"]["hall"]["dir"] == "n"
    # the well stands by the kitchen door: its doorway faces the threshold
    kitchen_door = at("kitchen", solved["kitchen"]["edges"]["well"])
    kx, ky = _UNIT[solved["kitchen"]["edges"]["well"]["dir"]]
    threshold = (kitchen_door[0] + kx, kitchen_door[1] + ky)
    well_door = at("well", solved["well"]["edges"]["kitchen"])
    assert abs(well_door[0] - threshold[0]) + abs(well_door[1] - threshold[1]) == 1
    # two places of the ground meet across one line, facing each other
    for a, other in (("garden", "path"), ("path", "gate"), ("garden", "tree")):
        ea, eb = solved[a]["edges"][other], solved[other]["edges"][a]
        ax, ay = at(a, ea)
        dx, dy = _UNIT[ea["dir"]]
        assert at(other, eb) == (ax + dx, ay + dy), (a, other)
        assert eb["dir"] == {"n": "s", "s": "n", "e": "w", "w": "e"}[ea["dir"]]
        assert (ax, ay) in _cells(solved[a]["geometry"])
        assert at(other, eb) in _cells(solved[other]["geometry"])


def test_a_side_asked_toward_the_ground_is_read_off_the_door_onto_it():
    """A door onto a feature opens onto the ground it stands in; the side
    the plan asked for that door is still checked against the wall the
    solve put it on, under the place the plan names."""
    b, spec, layout, _refused, _solved, report = _laid()
    asked = {(r["id"], j["to"]): j.get("side") for r in spec["rooms"] for j in r.get("joins") or ()}
    assert asked[("kitchen", "garden")] == "s"
    assert all(entry["to"] in {o["to"] for o in b["outside"]} | set(b["rooms"])
               for entry in report["sides"])


def test_the_rooms_estimate_of_a_place_is_filed_against_its_solve():
    planned = copy.deepcopy(SPECS)
    planned["garden"][1]["extent"] = {"w": 60, "d": 60}
    found = lb.plan_buildings(planned, copy.deepcopy(SCENE), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(RELATE))
    layout, _refused = lb.solve_for(b, spec)
    solved, report = lb.planned_layout(b, spec, layout)
    assert solved["garden"]["layout"]["stated"] == {"w": 60, "d": 60}
    entry = next(e for e in report["stated"] if e["room"] == "garden")
    assert entry["solved"] == solved["garden"]["geometry"]["extent"]


def test_the_grounds_never_cost_the_house_its_layout(monkeypatch):
    """Where the ground laid round a building leaves every seed refused, the
    building is solved again from the same two answers as the tier laid it
    before the grounds -- no further call -- and says why."""
    from agents import director_layout as dl
    real = lb.solve_for

    def solve_for(building, spec):
        layout, refused = real(building, spec)
        return (layout, ["the ground would not stand"]) if spec.get("ground_is") \
            else (layout, refused)

    monkeypatch.setattr(lb, "solve_for", solve_for)
    calls = []

    def call(step, system, payload):
        calls.append(step)
        if step.endswith("_brief"):
            return {"brief": ""}
        return copy.deepcopy(SORT if step.endswith("_sort") else RELATE)

    spec, _layout, _inventory, refused = dl.lay_out(_building(), call, "en")
    assert refused == []
    assert spec["grounds_dropped"] == ["the ground would not stand"]
    assert "ground_is" not in spec and "door_to" not in spec
    assert len(calls) == 3, "no call beyond the brief, the sort and the relate"


def _farm_chat(db):
    import time
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Farm", "A farm.", time.time()))
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def _plant_farm(cid, only=None, change=None):
    from world.structure import plant_structure
    rooms = {uid: dict(spec, name=name) for uid, (name, spec) in copy.deepcopy(SPECS).items()
             if only is None or uid in only}
    for room in rooms.values():
        room.pop("structure", None)
    for uid, fields in (change or {}).items():
        rooms[uid].update(fields)
    plant_structure(cid, {"key": "farm", "name": "Farm"}, rooms)


def _farm_answers(calls):
    def call(step, system, payload):
        calls.append(step)
        if step.endswith("_brief"):
            return {"brief": ""}
        return copy.deepcopy(SORT if step.endswith("_sort") else RELATE)
    return call


def _grounds_on(cid):
    from agents.director_layout import LAYOUT_GROUNDS_SETTING, LAYOUT_TIER_SETTING
    from core.db import set_setting
    set_setting(LAYOUT_TIER_SETTING, "on")
    set_setting(LAYOUT_GROUNDS_SETTING, "on")


def test_the_tier_writes_the_grounds_onto_the_plan_and_the_stubs_take_them(temp_db):
    from agents.director_layout import LAYOUT_RUNS_KEY, lay_out_buildings
    from core.db import wget
    from world.structure import _planned_specs, apply_planned_layout, registry_rows
    cid = _farm_chat(temp_db)
    _plant_farm(cid)
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid), desc=("pond", "road"))
    _scene, laid_out = lay_out_buildings(None, cid, scene, ["hall"], "en",
                                         call=_farm_answers([]))
    ground = {"path", "well", "privy", "garden", "gate", "tree"}
    assert laid_out == {"hall", "kitchen", "washroom", "loft"} | ground
    plan = {uid: e["planned"] for uid, e in registry_rows(cid).items()}
    for pid in ground:
        assert plan[pid]["site"]["plan"] == "layout:hall", pid
        assert plan[pid]["layout"]["grounds"], pid
    assert plan["garden"]["shape"] == "composite" and len(plan["garden"]["parts"]) > 1
    assert "parts" not in plan["path"]
    assert plan["tree"]["shape"] == "round", "a planned round thing stays round"
    assert plan["pond"].get("site") is None and plan["road"].get("site") is None
    run = next(iter(wget(cid, LAYOUT_RUNS_KEY).values()))
    assert run["grounds"] == len(ground) and run["grounds_unplaced"] == []
    # the stubs this job holds stand on the plan, the garden with its parts
    assert scene["rooms"]["garden"]["parts"] == plan["garden"]["parts"]
    assert scene["rooms"]["garden"]["site"] == plan["garden"]["site"]
    # a stub a rectangle's solve lays keeps no parts an earlier one gave it
    stale = copy.deepcopy(scene)
    stale["rooms"]["path"]["parts"] = [{"w": 2, "d": 2, "at": [0, 0]}]
    apply_planned_layout(stale, _planned_specs(cid), {"path"})
    assert "parts" not in stale["rooms"]["path"]


def test_a_house_re_planned_after_its_grounds_were_laid_is_laid_out_again_with_them(temp_db):
    """A re-plan of the house's rooms gives their solve back; the ground the
    solve laid round them still stands on the building's plan, and is laid
    again with the house rather than keeping it off its own plan. With the
    grounds switched off it does keep it off -- a new solve beside the old
    ground would read two frames as one -- and the house is left as planned."""
    from agents.director_layout import lay_out_buildings
    from world.structure import (_planned_specs, apply_solved_plans, provisional_room_ids,
                                 registry_rows)
    cid = _farm_chat(temp_db)
    _plant_farm(cid)
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid), desc=("pond", "road"))
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=_farm_answers([]))
    apply_solved_plans(cid, scene)
    assert scene["rooms"]["garden"]["site"]["plan"] == "layout:hall"
    # the Room re-plans the house alone: the hall is a long hall now
    _plant_farm(cid, only={"hall", "kitchen", "washroom", "loft"},
                change={"hall": {"extent": {"w": 8, "d": 4}}})
    plan = {uid: e["planned"] for uid, e in registry_rows(cid).items()}
    assert plan["hall"].get("site") is None and plan["garden"]["site"]["plan"] == "layout:hall"
    apply_solved_plans(cid, scene)
    assert "site" not in scene["rooms"]["hall"] or scene["rooms"]["hall"]["site"].get("derived")
    (b,) = [x for x in lb.plan_buildings(_planned_specs(cid), scene,
                                         held_open=provisional_room_ids(cid), grounds=True)
            if "hall" in x["rooms"]]
    assert b["refusal"] is None, b["refusal"]
    assert {g["id"] for g in b["grounds"]} == {"path", "well", "privy", "garden", "gate", "tree"}
    (off,) = [x for x in lb.plan_buildings(_planned_specs(cid), scene,
                                           held_open=provisional_room_ids(cid))
              if "hall" in x["rooms"]]
    assert off["refusal"] is not None
    _scene, laid_out = lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en",
                                         call=_farm_answers([]))
    assert {"hall", "garden"} <= laid_out
    plan = {uid: e["planned"] for uid, e in registry_rows(cid).items()}
    assert plan["hall"]["site"]["plan"] == "layout:hall"


def test_a_thing_by_something_on_a_side_of_it_stands_on_that_side():
    """The owner's lore puts the shrine's well "east of the path near the
    entryway", and all three answers said so: by the entrance, side e. The
    solver read the first and dropped the second, and laid the well west of
    the path in three runs of three (replicas of Home 5, 2026-10-11); it now
    takes ground on the side of the thing it stands by wherever that side
    has any. The layout lab's liked shrine and its three fresh runs, none of
    which asks for both, re-solve cell for cell."""
    for side, west in (("w", True), ("e", False)):
        relate = copy.deepcopy(RELATE)
        for g in relate["grounds"]:
            if g["id"] == "well":
                g.clear()
                g.update({"id": "well", "kind": "well", "by": "entrance", "side": side})
        _b, spec, layout, _refused, solved, _report = _laid(relate=relate)
        well = next(f for f in spec["grounds"]["features"] if f["id"] == "well")
        assert (well["by"], well["side"]) == ("entrance", side)
        door = next(d for d in layout.doors if d["b"] == "entrance")
        xs = [x for x, _y in _cells(solved["well"]["geometry"])]
        assert (max(xs) < door["cell"][0]) if west else (min(xs) > door["cell"][0]), side


def test_a_place_left_unsaid_never_takes_the_ground_round_the_house():
    """A place the first call left unsaid is laid as the tier always laid
    it; one the answers said lies round the house keeps that ground, though
    the unsaid one comes first on the walk from the doors."""
    specs = copy.deepcopy(SPECS)
    for edge in specs["kitchen"][1]["adjacent"]:
        if edge["to"] == "well":
            edge.pop("dir")
    for edge in specs["well"][1]["adjacent"]:
        edge.pop("dir")
    sort = dict(SORT, grounds=[g for g in SORT["grounds"] if g["id"] != "well"])
    relate = dict(RELATE, grounds=[g for g in RELATE["grounds"] if g["id"] != "well"])
    found = lb.plan_buildings(specs, copy.deepcopy(SCENE), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    assert [g["id"] for g in b["grounds"]].index("well") < [g["id"] for g in b["grounds"]].index("garden")
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    areas = {a["id"]: a["where"] for a in spec["grounds"]["areas"]}
    assert areas["garden"] == "around"
    assert spec["ground_is"]["well"] == "open"


def test_a_door_of_the_house_always_opens_onto_something():
    """An outbuilding the answers give no side to stand apart on, and the
    plan none either, is open ground on its doorway's side -- never a door
    onto nothing, which would refuse every seed and cost the house its
    grounds."""
    specs = copy.deepcopy(SPECS)
    for uid, to in (("washroom", "privy"), ("privy", "washroom")):
        for edge in specs[uid][1]["adjacent"]:
            if edge["to"] == to:
                edge.pop("dir")
    relate = copy.deepcopy(RELATE)
    for g in relate["grounds"]:
        if g["id"] == "privy":
            g.pop("side")
    found = lb.plan_buildings(specs, copy.deepcopy(SCENE), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    assert spec["ground_is"]["privy"] == "open"
    assert "privy" in {a["id"] for a in spec["grounds"]["areas"]}
    _layout, refused = lb.solve_for(b, spec)
    assert refused == []
