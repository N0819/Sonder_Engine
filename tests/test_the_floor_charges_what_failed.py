"""The grounds floor charges the place that failed, and takes out only that.

A second review of design A6 (2026-10-14) found the floor right about what
failed and wrong about which place to charge, or what to do once charged: a
thing dropped for want of a wall asked for a door of its own and refused the
house; the court an orchard behind the house could not meet was charged
before the orchard, by id; a band of open ground on the entrance's step was
never charged, the court was; a one-sided way the first solve made was taken
back by the next; a place dropped, or the whole ground laid aside, kept the
last solve's site on the plan; a window the solve made was read back as a
way; and the entrance opened onto a lantern because its id sorted first.
And no test failed without the floor's own blame. Each test is the
reviewer's plan, built from the suite's court and farm.
"""
from __future__ import annotations

import copy
import json
import time

from world import layout_bridge as lb

from tests.test_the_grounds_hold_together import (COURT_RELATE, COURT_SORT, COURT_SPECS, SCENE,
                                                  _STEP)


def _court_plan(mutate=None):
    specs, sort, relate = copy.deepcopy(COURT_SPECS), copy.deepcopy(COURT_SORT), \
        copy.deepcopy(COURT_RELATE)
    if mutate:
        mutate(specs, sort, relate)
    return specs, sort, relate


def _building(specs, scene=SCENE, held=()):
    found = lb.plan_buildings(copy.deepcopy(specs), copy.deepcopy(scene), held_open=set(held),
                              grounds=True)
    return max(found, key=lambda x: len(x["rooms"]))


def _answers(sort, relate):
    def call(step, system, payload):
        if step.endswith("_brief"):
            return {"brief": ""}
        return copy.deepcopy(sort if step.endswith("_sort") else relate)
    return call


def _lay(specs, sort, relate, scene=SCENE, held=()):
    from agents import director_layout as dl
    b = _building(specs, scene, held)
    spec, layout, _inv, refused = dl.lay_out(b, _answers(sort, relate), "en")
    return b, spec, layout, refused


def _farm_plan(mutate=None):
    from tests.test_a_building_stands_in_its_grounds import RELATE, SORT, SPECS
    specs, sort, relate = copy.deepcopy(SPECS), copy.deepcopy(SORT), copy.deepcopy(RELATE)
    if mutate:
        mutate(specs, sort, relate)
    return specs, sort, relate


def _lay_farm(mutate=None):
    from tests.test_a_building_stands_in_its_grounds import HELD_OPEN, SCENE as FARM
    specs, sort, relate = _farm_plan(mutate)
    return _lay(specs, sort, relate, FARM, HELD_OPEN)


# --------------------------------------------------------- which place


def test_of_two_open_grounds_the_one_less_hangs_on_gives_way():
    """An orchard behind the house the court cannot meet: the court was
    charged, its id sorting first, and taken out with the lane and the shed
    hung on it. The orchard, with nothing hung on it, gives way."""
    def mutate(specs, sort, relate):
        specs["court"][1]["adjacent"].append({"to": "orchard", "dir": "n"})
        specs["orchard"] = ("the Orchard", {"purpose": "an orchard", "structure": "court",
                                            "exposure": "open", "adjacent": [{"to": "court", "dir": "s"}]})
        sort["grounds"].append({"id": "orchard", "is": "open"})
        relate["grounds"].append({"id": "orchard", "where": "n"})

    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    assert refused == []
    assert spec.get("places_dropped") == ["orchard"]
    assert {"court", "lane", "shed"} <= set(spec["ground_is"])


def test_a_band_on_the_entrances_step_gives_way_to_the_ground_round_the_house():
    """The court lies round the house and a terrace on its south takes the
    entrance's step: the court was charged for the doorway the terrace took,
    and the whole ground was laid aside."""
    def mutate(specs, sort, relate):
        specs["court"][1]["adjacent"].append({"to": "terrace", "dir": "s"})
        specs["terrace"] = ("the Terrace", {"purpose": "a terrace", "structure": "court",
                                            "exposure": "open", "adjacent": [{"to": "court", "dir": "n"}]})
        sort["grounds"].append({"id": "terrace", "is": "open"})
        for g in relate["grounds"]:
            if g["id"] == "court":
                g["where"] = "around"
        relate["grounds"].append({"id": "terrace", "where": "s"})

    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    assert refused == []
    assert spec.get("places_dropped") == ["terrace"]
    assert {"court", "lane", "shed"} <= set(spec["ground_is"])


def test_the_floor_charges_what_stands_on_a_doors_step_and_nothing_it_strands():
    """The floor's own blame, where the solver's aprons are not there to keep
    the step: a lantern standing on the entrance's step costs the court its
    doorway, and the lantern is charged -- the court, and the lane and the
    shed reached through it, refuse the seed and are taken out by nobody."""
    def mutate(specs, sort, relate):
        specs["court"][1]["adjacent"].append({"to": "lantern", "dir": "s"})
        specs["lantern"] = ("the Lantern", {"purpose": "a stone lantern", "structure": "court",
                                            "exposure": "open", "adjacent": [{"to": "court", "dir": "n"}]})
        sort["grounds"].append({"id": "lantern", "is": "feature"})
        relate["grounds"].append({"id": "lantern", "kind": "lantern", "by": "entrance"})

    specs, sort, relate = _court_plan(mutate)
    b = _building(specs)
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    layout, refused = lb.solve_for(b, spec)
    assert refused == []
    door = next(d for d in layout.doors if d["b"] == "entrance")
    sx, sy = _STEP[door["side"]]
    step = (door["cell"][0] + sx, door["cell"][1] + sy)
    from world.layout_solver import Rect
    thing = next(f for f in layout.features if f["id"] == "lantern")
    thing["rect"] = Rect(step[0], step[1], 2, 2)        # where no apron kept it off
    found = lb.ground_breaches(b, spec, layout)
    assert found, "the court's doorway is lost"
    charged = {place for _words, place in found}
    assert "lantern" in charged
    assert not charged & {"court", "lane", "shed"}, found


# ------------------------------------------------------ what a drop costs


def test_things_dropped_at_the_hall_take_no_door_of_their_own():
    """Two things joined to the hall, whose one outside wall holds the
    entrance and one more door: the second found no wall and was dropped,
    and dropped it asked for a door onto the ground the hall had no wall
    for -- the whole building was refused. Its way opens through the
    entrance now; the barrel alone is left out."""
    def mutate(specs, sort, relate):
        for pid, kind in (("zlantern", "lantern"), ("zrainbarrel", "barrel")):
            specs["hall"][1]["adjacent"].append({"to": pid, "dir": "s", "barrier": "closed_door"})
            specs[pid] = (f"the {pid}", {"purpose": f"a {kind}", "structure": "farm", "exposure": "open",
                                         "adjacent": [{"to": "hall", "dir": "n"}]})
            sort["grounds"].append({"id": pid, "is": "feature"})
            relate["grounds"].append({"id": pid, "kind": kind, "by": "hall"})

    _b, spec, _layout, refused = _lay_farm(mutate)
    assert refused == []
    assert spec.get("places_dropped") == ["zrainbarrel"]
    assert {"garden", "gate", "path", "privy", "tree", "well", "zlantern"} <= set(spec["ground_is"])
    assert spec["door_to"]["zrainbarrel"] == "entrance"


def test_things_dropped_from_two_rooms_leave_the_house_standing():
    """A stone and a stump each joined to the hall and the side room: once
    they were dropped the court was a band again, each was given a band and
    a door of its own, and the house -- which every seed had stood for --
    was refused."""
    def mutate(specs, sort, relate):
        for pid in ("stone", "stump"):
            specs["hall"][1]["adjacent"].append({"to": pid, "dir": "n", "barrier": "closed_door"})
            specs["side"][1]["adjacent"].append({"to": pid, "dir": "e", "barrier": "closed_door"})
            specs[pid] = (f"the {pid}", {"purpose": f"a {pid}", "structure": "court", "exposure": "open",
                                         "adjacent": [{"to": "hall", "dir": "s"}, {"to": "side", "dir": "w"}]})
            sort["grounds"].append({"id": pid, "is": "feature"})
            relate["grounds"].append({"id": pid, "kind": "stone"})

    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    assert refused == []
    assert set(spec.get("places_dropped") or ()) <= {"stone", "stump"}
    assert {"court", "lane", "shed"} <= set(spec["ground_is"])


def test_the_places_a_drop_takes_with_it_are_named(monkeypatch):
    """A post joined to the lane alone goes with the lane: it was laid by
    nobody and named nowhere."""
    def mutate(specs, sort, relate):
        specs["lane"][1]["adjacent"].append({"to": "post", "dir": "e"})
        specs["post"] = ("the Post", {"purpose": "a waymark post", "structure": "court",
                                      "exposure": "open", "adjacent": [{"to": "lane", "dir": "w"}]})
        sort["grounds"].append({"id": "post", "is": "feature"})
        relate["grounds"].append({"id": "post", "kind": "statue", "by": "lane"})

    real = lb.ground_breaches

    def breaches(building, spec, layout):
        found = real(building, spec, layout)
        if "lane" in (spec.get("ground_is") or {}):
            found = found + [("lane is not one floor", "lane")]
        return found

    monkeypatch.setattr(lb, "ground_breaches", breaches)
    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    assert refused == []
    assert spec.get("places_dropped") == ["lane", "post"]


def test_a_drop_that_would_leave_no_ground_lays_the_house_alone(monkeypatch):
    """The court every other place hangs on fails every seed: taking it out
    takes the whole ground, and the house is laid alone as the tier laid it
    before the grounds -- filed as that, never as one place dropped."""
    real = lb.ground_breaches

    def breaches(building, spec, layout):
        found = real(building, spec, layout)
        if "court" in (spec.get("ground_is") or {}):
            found = found + [("court is not one floor", "court")]
        return found

    monkeypatch.setattr(lb, "ground_breaches", breaches)
    _b, spec, _layout, refused = _lay(*_court_plan())
    assert refused == []
    assert not spec.get("places_dropped")
    assert spec.get("grounds_dropped") and not spec.get("ground_is")


def test_the_floor_never_reads_a_seed_the_house_refused(monkeypatch):
    """A seed refused for the house is never asked of the floor, whose plan
    needs every room laid."""
    from tests.test_the_grounds_hold_together import _court
    b, spec, layout, _refused, _solved, _report = _court()
    asked = []
    monkeypatch.setattr(lb, "ground_breaches", lambda *a: asked.append(a) or [])
    layout.floors[0].pop("hall", None)
    refused = lb.refusals(b, spec, layout)
    assert any("found no floor" in r for r in refused)
    assert asked == []


# ------------------------------------------------------------- the entrance


def test_the_entrance_opens_onto_a_way_before_a_thing():
    """A lantern joined to the hall, whose id sorts before the path's, took
    the entrance: the path lost its door, and the whole building was
    refused. A door opens onto a way or open ground before a thing, which
    stands at a door of its own."""
    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"].append({"to": "lantern", "dir": "s", "barrier": "open_door"})
        specs["lantern"] = ("the lantern", {"purpose": "a stone lantern", "structure": "farm",
                                            "exposure": "open", "adjacent": [{"to": "hall", "dir": "n"}]})
        sort["grounds"].append({"id": "lantern", "is": "feature"})
        relate["grounds"].append({"id": "lantern", "kind": "lantern", "by": "entrance"})

    b, spec, layout, refused = _lay_farm(mutate)
    assert b["entrance"]["to"] == "lantern"             # as the plan alone chose it
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    assert spec["entrance_to"] == "path"
    assert any(d.get("outside") and d["a"] == "hall" and d["b"] == "lantern" for d in layout.doors)


# --------------------------------------------- what an earlier solve wrote


def _court_chat(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Court", "A court.", time.time()))
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def _plant_court(cid, specs, only=None, change=None):
    from world.structure import plant_structure
    rooms = {uid: dict(spec, name=name) for uid, (name, spec) in copy.deepcopy(specs).items()
             if only is None or uid in only}
    for room in rooms.values():
        room.pop("structure", None)
    for uid, fields in (change or {}).items():
        rooms[uid].update(fields)
    plant_structure(cid, {"key": "court", "name": "Court"}, rooms)


def _rows(cid):
    from world.structure import registry_rows
    return {uid: entry["planned"] for uid, entry in registry_rows(cid).items()}


def test_a_way_one_side_alone_declares_holds_through_a_re_solve(temp_db):
    """The court declares its way to the shed, the shed none (two plan ops):
    the first solve wrote the shed's side as its own way; the next read that
    way as the plan's, took it back, and dropped the shed -- every other
    solve."""
    from agents.director_layout import lay_out_buildings
    from tests.test_a_building_stands_in_its_grounds import _grounds_on, _stub_scene
    from world.structure import _planned_specs, apply_solved_plans
    cid = _court_chat(temp_db)
    _plant_court(cid, COURT_SPECS)
    _plant_court(cid, COURT_SPECS, only={"shed"}, change={"shed": {"adjacent": []}})
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid))
    call = _answers(COURT_SORT, COURT_RELATE)
    for turn in range(3):
        _s, laid = lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=call)
        assert "shed" in laid, turn
        rows = _rows(cid)
        assert rows["shed"]["site"]["plan"] == "layout:hall"
        assert rows["shed"]["layout"]["made_edges"] == ["court"]
        # the Room re-plans the house: the next solve lays it again
        _plant_court(cid, COURT_SPECS, only={"hall", "side", "loft"},
                     change={"side": {"purpose": f"a store room {turn}"}})
        apply_solved_plans(cid, scene)


def test_the_house_laid_alone_takes_its_old_ground_off_the_plan(temp_db, monkeypatch):
    """A re-solve that lays the house alone left the ground the first solve
    laid on the plan, under the re-laid house."""
    from agents.director_layout import lay_out_buildings
    from tests.test_a_building_stands_in_its_grounds import _grounds_on, _stub_scene
    from world.structure import _planned_specs, apply_solved_plans
    cid = _court_chat(temp_db)
    _plant_court(cid, COURT_SPECS)
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid))
    call = _answers(COURT_SORT, COURT_RELATE)
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=call)
    apply_solved_plans(cid, scene)
    assert all(_rows(cid)[p].get("site") for p in ("court", "lane", "shed"))
    _plant_court(cid, COURT_SPECS, only={"hall", "side", "loft"},
                 change={"side": {"purpose": "a store room"}})
    real = lb.ground_breaches
    monkeypatch.setattr(lb, "ground_breaches", lambda b, s, l: real(b, s, l) + [
        (f"{p} fails", p) for p in sorted(s.get("ground_is") or ())])
    apply_solved_plans(cid, scene)
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=call)
    rows = _rows(cid)
    assert rows["hall"]["site"]["plan"] == "layout:hall"
    for pid in ("court", "lane", "shed"):
        assert rows[pid].get("site") is None and "layout" not in rows[pid], pid


def test_a_dropped_place_goes_back_to_what_the_room_planned(temp_db, monkeypatch):
    """The well, planned six paces square, laid two by two, then dropped on a
    re-solve: it kept the solve's size and pins and lost the record of the
    Room's estimate, so the next solve filed the old two by two as the
    Room's."""
    from agents.director_layout import lay_out_buildings
    from tests.test_a_building_stands_in_its_grounds import (_farm_answers, _farm_chat, _grounds_on,
                                                             _plant_farm, _stub_scene)
    from world.structure import _planned_specs, apply_solved_plans
    cid = _farm_chat(temp_db)
    _plant_farm(cid, change={"well": {"extent": {"w": 6, "d": 6}}})
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid), desc=("pond", "road"))
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=_farm_answers([]))
    apply_solved_plans(cid, scene)
    well = _rows(cid)["well"]
    assert well["layout"]["stated"] == {"w": 6, "d": 6} and well["extent"] != {"w": 6, "d": 6}
    _plant_farm(cid, only={"hall", "kitchen", "washroom", "loft"},
                change={"hall": {"extent": {"w": 8, "d": 4}}})
    real = lb.ground_breaches

    def breaches(building, spec, layout):
        found = real(building, spec, layout)
        if "well" in (spec.get("ground_is") or {}):
            found = found + [("well is not one floor", "well")]
        return found

    monkeypatch.setattr(lb, "ground_breaches", breaches)
    apply_solved_plans(cid, scene)
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=_farm_answers([]))
    well = _rows(cid)["well"]
    assert well.get("site") is None and "layout" not in well
    assert well["extent"] == {"w": 6, "d": 6}
    assert not any(e.get("cell") is not None or e.get("offset") is not None
                   for e in well.get("adjacent") or ())
    monkeypatch.setattr(lb, "ground_breaches", real)
    _plant_farm(cid, only={"hall", "kitchen", "washroom", "loft"},
                change={"hall": {"extent": {"w": 7, "d": 5}}})
    apply_solved_plans(cid, scene)
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=_farm_answers([]))
    well = _rows(cid)["well"]
    assert well["site"]["plan"] == "layout:hall"
    assert well["layout"]["stated"] == {"w": 6, "d": 6}


def test_a_window_the_solve_made_is_never_read_as_the_plans_way(temp_db):
    """The farm with windows onto its garden: re-solved after the Room
    re-planned the house, the garden's window edges -- the first solve's own
    -- were read as the plan's ways, the solver laid a door for each, and
    the kitchen and the loft were each written two windows."""
    from agents.director_layout import lay_out_buildings
    from tests.test_a_building_stands_in_its_grounds import (RELATE, SORT, _farm_chat, _grounds_on,
                                                             _plant_farm, _stub_scene)
    from world.structure import _planned_specs, apply_solved_plans
    sort, relate = copy.deepcopy(SORT), copy.deepcopy(RELATE)
    for rid, side in (("hall", "s"), ("kitchen", "e"), ("loft", "n")):
        next(r for r in sort["rooms"] if r["id"] == rid)["windows"] = [
            {"id": f"{rid}_window", "name": f"the {rid} window", "faces": "the ground outside"}]
        next(r for r in relate["rooms"] if r["id"] == rid)["windows"] = [
            {"id": f"{rid}_window", "side": side}]
    cid = _farm_chat(temp_db)
    _plant_farm(cid)
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid), desc=("pond", "road"))
    call = _answers(sort, relate)
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=call)
    apply_solved_plans(cid, scene)
    _plant_farm(cid, only={"hall", "kitchen", "washroom", "loft"},
                change={"hall": {"extent": {"w": 8, "d": 4}}})
    apply_solved_plans(cid, scene)
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=call)
    rows = _rows(cid)
    for uid in ("kitchen", "loft"):
        edges = [e for e in rows[uid].get("adjacent") or () if e.get("to") == "garden"]
        records = [w for w in rows[uid].get("windows") or () if w.get("id") == f"{uid}_window"]
        assert len(edges) + len(records) == 1, (uid, edges, records)


# ------------------------------------------------ what cut a place in two
#
# The floor's own rules, on a real solve with one place moved where the
# solver's rules would not have put it: each says which place the floor
# charges, whatever the solver does.


def _solved(specs, sort, relate, scene=SCENE, held=()):
    b = _building(specs, scene, held)
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate))
    layout, refused = lb.solve_for(b, spec)
    assert refused == []
    return b, spec, layout


def _charged(found, words):
    return [place for w, place in found if w == words]


def test_a_way_laid_through_a_building_is_charged_for_its_own_cut():
    """A lane run through a storehouse standing in the band beyond its
    ground: the storehouse was charged for cutting the lane. A way laid over
    a building is the way's own fault."""
    from world.layout_solver import Rect
    b, spec, layout = _solved(*_court_plan())
    rows = layout.ways["lane"]["rows"]
    row = rows[len(rows) // 2]
    xs, y = [c[0] for c in row], row[0][1]
    layout.floors[0]["shed"] = [Rect(min(xs) - 1, y, max(xs) - min(xs) + 3, 2)]
    found = lb.ground_breaches(b, spec, layout)
    assert _charged(found, "lane is not one floor") == ["lane"], found


def test_a_way_cut_by_a_walk_is_charged_to_the_walks_building():
    """The farm's path, crossed by the privy's walk: the walk was laid after
    the path, and the privy whose walk it is gives way."""
    b, spec, layout = _solved(*_farm_plan(), *_farm_scene())
    rows = layout.ways["path"]["rows"]
    row = rows[len(rows) // 2]
    xs, y = [c[0] for c in row], row[0][1]
    # two paces wide, as the world holds a walk
    layout.ways["privy__way"]["cells"] = {(x, y + k) for x in range(min(xs) - 2, max(xs) + 3)
                                          for k in (0, 1)}
    found = lb.ground_breaches(b, spec, layout)
    assert _charged(found, "path is not one floor") == ["privy"], found


def test_a_garden_cut_by_a_walk_is_charged_to_the_walk_never_a_gate_it_touches():
    """The garden round the farm, cut behind the house by the privy's walk
    and before it by the path: the gate across the path's foot touches the
    garden on both sides and was charged. It stands across the path, whose
    cells it gets no credit for; the walk cut the garden."""
    b, spec, layout = _solved(*_farm_plan(), *_farm_scene())
    main = layout.outlines["main"][0]
    things = set().union(*(f["rect"].cells() for f in layout.features))
    for rects in layout.floors[0].values():
        for r in rects:
            things |= r.cells()
    col = next(x for x in range(main.x, main.x + main.w - 1)
               if not {(x + k, y) for y in range(layout.site.y, main.y) for k in (0, 1)} & things)
    # behind the house, from the plot's edge to its wall: the path and the
    # gate at its foot already part the garden before it
    layout.ways["privy__way"]["cells"] = {(col + k, y) for y in range(layout.site.y - 1, main.y)
                                          for k in (0, 1)}
    found = lb.ground_breaches(b, spec, layout)
    charged = _charged(found, "garden is not one floor")
    assert charged and charged != ["gate"], found
    assert charged == ["privy"], found


def test_of_two_places_that_cut_the_garden_alike_the_one_laid_last_is_charged():
    """The garden round the farm cut three ways: before the house by the
    path, behind it by the privy's walk, and on its east side by a band the
    well stands across. Given back, the walk and the well each join one cut
    up; of the two the walk was laid last, and cut the garden the well's
    ground was laid round -- by particularity alone the well was charged."""
    from world.layout_solver import Rect
    b, spec, layout = _solved(*_farm_plan(), *_farm_scene())
    main = layout.outlines["main"][0]
    things = set().union(*(f["rect"].cells() for f in layout.features))
    for rects in layout.floors[0].values():
        for r in rects:
            things |= r.cells()
    col = next(x for x in range(main.x, main.x + main.w - 1)
               if not {(x + k, y) for y in range(layout.site.y, main.y) for k in (0, 1)} & things)
    layout.ways["privy__way"]["cells"] = {(col + k, y) for y in range(layout.site.y - 1, main.y)
                                          for k in (0, 1)}
    east = main.x + main.w
    row = next(y for y in range(main.y, main.y + main.d - 1)
               if not {(x, y + k) for x in range(east, layout.site.x + layout.site.w) for k in (0, 1)} & things)
    well = next(f for f in layout.features if f["id"] == "well")
    well["rect"] = Rect(east, row, layout.site.x + layout.site.w - east, 2)
    found = lb.ground_breaches(b, spec, layout)
    assert _charged(found, "garden is not one floor") == ["privy"], found


def test_a_thing_on_a_ways_mouth_is_charged_for_the_meeting_it_takes():
    """A lantern standing on the court's cells at the lane's mouth: the court
    and the lane no longer touched, and the lane was charged. What stands
    between two places of the ground gives way."""
    from world.layout_solver import Rect, _STEP as STEP

    def mutate(specs, sort, relate):
        specs["court"][1]["adjacent"] = [dict(e, dir="e") if e["to"] == "lane" else e
                                         for e in specs["court"][1]["adjacent"]]
        specs["lane"][1]["adjacent"] = [{"to": "court", "dir": "w"}, {"to": "lantern", "dir": "n"}]
        specs["lantern"] = ("the Lantern", {"purpose": "a stone lantern", "structure": "court",
                                            "exposure": "open", "adjacent": [{"to": "lane", "dir": "s"}]})
        for g in relate["grounds"]:
            if g["id"] == "lane":
                g.pop("from", None)
        sort["grounds"].append({"id": "lantern", "is": "feature"})
        relate["grounds"].append({"id": "lantern", "kind": "lantern", "by": "lane", "side": "n"})

    b, spec, layout = _solved(*_court_plan(mutate))
    way = layout.ways["lane"]
    dx, dy = STEP[way["side"]]
    mouth = {(x - dx, y - dy) for x, y in way["rows"][0]}
    x0, y0 = min(x for x, _ in mouth), min(y for _, y in mouth)
    x1, y1 = max(x for x, _ in mouth), max(y for _, y in mouth)
    thing = next(f for f in layout.features if f["id"] == "lantern")
    thing["rect"] = Rect(x0 - abs(dx), y0 - abs(dy), x1 - x0 + 1 + abs(dx), y1 - y0 + 1 + abs(dy))
    found = lb.ground_breaches(b, spec, layout)
    charged = [place for w, place in found if "court" in w and "lane" in w]
    assert charged and set(charged) == {"lantern"}, found


def _farm_scene():
    from tests.test_a_building_stands_in_its_grounds import HELD_OPEN, SCENE as FARM
    return FARM, HELD_OPEN


def test_a_re_solve_files_no_estimate_the_room_never_stated(temp_db):
    """The oak, planned with no size: every re-solve filed the last solve's
    size as the Room's estimate of it."""
    from agents.director_layout import lay_out_buildings
    from tests.test_a_building_stands_in_its_grounds import (_farm_answers, _farm_chat, _grounds_on,
                                                             _plant_farm, _stub_scene)
    from world.structure import _planned_specs, apply_solved_plans
    cid = _farm_chat(temp_db)
    _plant_farm(cid)
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid), desc=("pond", "road"))
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=_farm_answers([]))
    apply_solved_plans(cid, scene)
    assert "stated" not in _rows(cid)["tree"]["layout"]
    _plant_farm(cid, only={"hall", "kitchen", "washroom", "loft"},
                change={"hall": {"extent": {"w": 8, "d": 4}}})
    apply_solved_plans(cid, scene)
    lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en", call=_farm_answers([]))
    tree = _rows(cid)["tree"]
    assert tree["site"]["plan"] == "layout:hall"
    assert "stated" not in tree["layout"], tree["layout"]


# ------------------------------------------------- the review's random plans
#
# Plans from the second review's own generator (a hall with its rooms, open
# ground, ways, things and outbuildings joined to them, with the two calls'
# answers), on which this round's rules first laid fewer places than the
# round before: each the class, the plan only its witness.

PLAN_2 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"kitchen\",\"dir\":\"n\",\"barrier\":\"open_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"court\",\"dir\":\"s\",\"barrier\":\"open_door\"},{\"to\":\"yard\",\"dir\":\"w\",\"barrier\":\"closed_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\",\"barrier\":\"closed_door\"}]}],\"kitchen\":[\"the Kitchen\",{\"purpose\":\"a kitchen with a stove\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"court\":[\"the Court\",{\"purpose\":\"a stone court\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"yard\":[\"the Yard\",{\"purpose\":\"a back yard\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"e\"}],\"exposure\":\"open\"}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"name\":\"stove\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"court\",\"is\":\"open\"},{\"id\":\"yard\",\"is\":\"open\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"n\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"n\"}]},{\"id\":\"kitchen\",\"purpose\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"kind\":\"stove\",\"at\":\"e\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"court\",\"where\":\"around\"},{\"id\":\"yard\",\"where\":\"e\"}]}}")
PLAN_18 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"kitchen\",\"dir\":\"n\",\"barrier\":\"open_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"court\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"garden\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"kitchen\":[\"the Kitchen\",{\"purpose\":\"a kitchen with a stove\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"s\",\"barrier\":\"open_door\"},{\"to\":\"yard\",\"dir\":\"n\",\"barrier\":\"closed_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"court\":[\"the Court\",{\"purpose\":\"a stone court\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"garden\":[\"the Garden\",{\"purpose\":\"a garden\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"yard\":[\"the Yard\",{\"purpose\":\"a back yard\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"kitchen\",\"dir\":\"s\"},{\"to\":\"shed\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"shed\":[\"the Shed\",{\"purpose\":\"a storehouse\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"yard\",\"dir\":\"n\"}]}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"name\":\"stove\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"court\",\"is\":\"open\"},{\"id\":\"garden\",\"is\":\"open\"},{\"id\":\"yard\",\"is\":\"open\"},{\"id\":\"shed\",\"is\":\"outbuilding\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"e\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"w\"}]},{\"id\":\"kitchen\",\"purpose\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"kind\":\"stove\",\"at\":\"e\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"court\",\"where\":\"around\"},{\"id\":\"garden\",\"where\":\"around\"},{\"id\":\"yard\",\"where\":\"around\"},{\"id\":\"shed\",\"side\":\"e\"}]}}")
PLAN_93 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"kitchen\",\"dir\":\"n\",\"barrier\":\"open_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"path\",\"dir\":\"s\",\"barrier\":\"open_door\"},{\"to\":\"garden\",\"dir\":\"e\",\"barrier\":\"closed_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"privy\",\"dir\":\"n\",\"barrier\":\"closed_door\"}]}],\"kitchen\":[\"the Kitchen\",{\"purpose\":\"a kitchen with a stove\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"path\":[\"the Path\",{\"purpose\":\"a gravel path\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"garden\":[\"the Garden\",{\"purpose\":\"a garden\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\"},{\"to\":\"byre\",\"dir\":\"s\"},{\"to\":\"tree\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"byre\":[\"the Byre\",{\"purpose\":\"a byre\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"n\"}]}],\"privy\":[\"the Privy\",{\"purpose\":\"a privy\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"s\"}]}],\"tree\":[\"the Old Oak\",{\"purpose\":\"an old oak\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"s\"}],\"exposure\":\"open\"}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"name\":\"stove\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"path\",\"is\":\"way\"},{\"id\":\"garden\",\"is\":\"open\"},{\"id\":\"byre\",\"is\":\"outbuilding\"},{\"id\":\"privy\",\"is\":\"outbuilding\"},{\"id\":\"tree\",\"is\":\"feature\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"w\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"n\"}]},{\"id\":\"kitchen\",\"purpose\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"kind\":\"stove\",\"at\":\"e\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"path\",\"from\":\"entrance\"},{\"id\":\"garden\",\"where\":\"e\"},{\"id\":\"byre\",\"side\":\"s\"},{\"id\":\"privy\",\"side\":\"n\"},{\"id\":\"tree\",\"kind\":\"tree\",\"side\":\"s\"}]}}")
PLAN_120 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"kitchen\",\"dir\":\"n\",\"barrier\":\"open_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"path\",\"dir\":\"s\",\"barrier\":\"open_door\"},{\"to\":\"well\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"privy\",\"dir\":\"w\",\"barrier\":\"closed_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\",\"barrier\":\"closed_door\"}]}],\"kitchen\":[\"the Kitchen\",{\"purpose\":\"a kitchen with a stove\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"path\":[\"the Path\",{\"purpose\":\"a gravel path\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"},{\"to\":\"lantern\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"well\":[\"the Well\",{\"purpose\":\"a stone well\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"e\"}],\"exposure\":\"open\"}],\"lantern\":[\"the Lantern\",{\"purpose\":\"a stone lantern\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"path\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"privy\":[\"the Privy\",{\"purpose\":\"a privy\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"e\"}]}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"name\":\"stove\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"path\",\"is\":\"way\"},{\"id\":\"well\",\"is\":\"feature\"},{\"id\":\"lantern\",\"is\":\"feature\"},{\"id\":\"privy\",\"is\":\"outbuilding\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"e\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"w\"}]},{\"id\":\"kitchen\",\"purpose\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"kind\":\"stove\",\"at\":\"e\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"path\",\"from\":\"entrance\"},{\"id\":\"well\",\"kind\":\"well\",\"by\":\"hall\"},{\"id\":\"lantern\",\"kind\":\"lantern\",\"by\":\"entrance\"},{\"id\":\"privy\",\"side\":\"n\"}]}}")

PLAN_169 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"court\",\"dir\":\"s\",\"barrier\":\"open_door\"},{\"to\":\"garden\",\"dir\":\"n\",\"barrier\":\"closed_door\"},{\"to\":\"privy\",\"dir\":\"n\",\"barrier\":\"closed_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"well\",\"dir\":\"n\",\"barrier\":\"closed_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"court\":[\"the Court\",{\"purpose\":\"a stone court\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"},{\"to\":\"lane\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"garden\":[\"the Garden\",{\"purpose\":\"a garden\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"s\"},{\"to\":\"shed\",\"dir\":\"w\"},{\"to\":\"tree\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"lane\":[\"the Lane\",{\"purpose\":\"a lane down the hill\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"court\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"well\":[\"the Well\",{\"purpose\":\"a stone well\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"shed\":[\"the Shed\",{\"purpose\":\"a storehouse\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"e\"}]}],\"privy\":[\"the Privy\",{\"purpose\":\"a privy\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"s\"}]}],\"tree\":[\"the Old Oak\",{\"purpose\":\"an old oak\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"n\"}],\"exposure\":\"open\"}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"court\",\"is\":\"open\"},{\"id\":\"garden\",\"is\":\"open\"},{\"id\":\"lane\",\"is\":\"way\"},{\"id\":\"well\",\"is\":\"feature\"},{\"id\":\"shed\",\"is\":\"outbuilding\"},{\"id\":\"privy\",\"is\":\"outbuilding\"},{\"id\":\"tree\",\"is\":\"feature\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"s\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"n\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"court\",\"where\":\"around\"},{\"id\":\"garden\",\"where\":\"n\"},{\"id\":\"lane\",\"side\":\"s\"},{\"id\":\"well\",\"kind\":\"well\",\"by\":\"side\"},{\"id\":\"shed\",\"side\":\"e\"},{\"id\":\"privy\",\"side\":\"e\"},{\"id\":\"tree\",\"kind\":\"tree\"}]}}")

def _lay_plan(plan, mutate=None):
    specs = {k: (v[0], v[1]) for k, v in copy.deepcopy(plan["specs"]).items()}
    sort, relate = copy.deepcopy(plan["sort"]), copy.deepcopy(plan["relate"])
    if mutate:
        mutate(specs, sort, relate)
    return _lay(specs, sort, relate, {"rooms": {}, "positions": {}, "entities": {}}, ())


def test_the_ground_the_entrance_opens_onto_outweighs_another_as_light():
    """The plan opens the hall west onto a yard; the answer laid the yard as
    a band on the far side of the house, which no door of the hall faces.
    The hall's door onto it opened into the court round the house -- the
    ground the entrance opens onto -- and by what hung on each the court was
    charged for holding its step. The ground the entrance opens onto weighs
    most: the yard gives way, and the court stays."""
    b, spec, _layout, refused = _lay_plan(PLAN_2)
    assert refused == []
    assert spec.get("places_dropped") == ["yard"]
    assert "court" in spec["ground_is"]


def test_ground_answered_round_the_corner_from_its_door_takes_the_strip_between():
    """The same yard answered north, round the corner from the hall's west
    door onto it: the court's strip beside the house on the west reaches the
    yard's band, and is the yard's."""
    def mutate(specs, sort, relate):
        next(g for g in relate["grounds"] if g["id"] == "yard")["where"] = "n"

    b, spec, _layout, refused = _lay_plan(PLAN_2, mutate)
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    assert {"court", "yard"} <= set(spec["ground_is"])


def test_a_charge_its_own_place_answers_is_void():
    """Three grounds all answered round the house: the court the entrance
    opens onto is not one floor, and the garden band holds its step. The
    court was charged for its floor and the garden for the court's step, and
    both were dropped -- though the court's going answered both."""
    b, spec, _layout, refused = _lay_plan(PLAN_18)
    assert refused == []
    assert spec.get("places_dropped") == ["court"]
    assert {"garden", "shed", "yard"} <= set(spec["ground_is"])


def test_a_way_one_door_of_the_house_opens_onto_leaves_from_it():
    """The hall opens onto a garden and a path, and the entrance onto the
    garden, whose id sorted first: the path had nothing to run from or
    between, and was dropped -- a re-pointed entrance laid it once, by moving
    the front the call had answered against (a third review of 2026-10-14).
    The entrance stays; the path leaves from the hall's own door onto it."""
    b, spec, _layout, refused = _lay_plan(PLAN_93)
    assert b["entrance"]["to"] == "garden"        # as the plan alone chose it
    assert "entrance_to" not in spec
    assert next(w for w in spec["grounds"]["ways"] if w["id"] == "path")["from"] == "door"
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    assert {"path", "garden", "byre", "privy", "tree"} <= set(spec["ground_is"])


def test_a_thing_stands_by_what_the_plan_joins_it_to():
    """The plan joins the lantern to the path; the answer stood it by the
    entrance, where it touched no path, and it was dropped. Joined to the
    way the entrance opens onto, it stands by that way at its near end."""
    b, spec, layout, refused = _lay_plan(PLAN_120)
    lantern = next(f for f in spec["grounds"]["features"] if f["id"] == "lantern")
    assert (lantern["by"], lantern.get("end")) == ("path", "near")
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")


def test_of_two_grounds_the_entrance_does_not_open_onto_the_one_less_hangs_on_gives_way():
    """A garden the side room opens onto, a lane leaving it, and an orchard
    joined to the garden laid on the far side of the house: the two cannot
    meet. By id the garden was charged, and the lane went with it; the
    orchard, with nothing hung on it, gives way."""
    def mutate(specs, sort, relate):
        specs["side"][1]["adjacent"].append({"to": "garden", "dir": "e", "barrier": "closed_door"})
        specs["garden"] = ("the Garden", {"purpose": "a garden", "structure": "court", "exposure": "open",
                                          "adjacent": [{"to": "side", "dir": "w"},
                                                       {"to": "track", "dir": "s"},
                                                       {"to": "orchard", "dir": "e"}]})
        specs["track"] = ("the Track", {"purpose": "a track", "structure": "court", "exposure": "open",
                                        "adjacent": [{"to": "garden", "dir": "n"}]})
        specs["orchard"] = ("the Orchard", {"purpose": "an orchard", "structure": "court",
                                            "exposure": "open", "adjacent": [{"to": "garden", "dir": "w"}]})
        sort["grounds"] += [{"id": "garden", "is": "open"}, {"id": "track", "is": "way"},
                            {"id": "orchard", "is": "open"}]
        relate["grounds"] += [{"id": "garden", "where": "e"}, {"id": "track"},
                              {"id": "orchard", "where": "w"}]

    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    assert refused == []
    assert spec.get("places_dropped") == ["orchard"]
    assert {"court", "garden", "track"} <= set(spec["ground_is"])


def test_ground_whose_room_cannot_face_it_takes_the_strip_beside_the_house():
    """The hall opens north onto a garden, but its back wall is its ladder's
    stair hall: its door onto the garden turned west, into the court round
    the house, and the garden -- with the shed and the oak hung on it -- was
    dropped. The court's strip beside the house on that side reaches the
    garden round the corner, and is the garden's; the court keeps the rest,
    one floor."""
    b, spec, layout, refused = _lay_plan(PLAN_169)
    assert refused == []
    held = {"court", "garden", "shed", "tree"}
    assert held <= set(spec["ground_is"])
    assert not held & set(spec.get("places_dropped") or ()), spec.get("places_dropped")


# ------------------------------------------- the third review's charges


PLAN_41 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"court\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"yard\",\"dir\":\"s\",\"barrier\":\"closed_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"court\":[\"the Court\",{\"purpose\":\"a stone court\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"},{\"to\":\"lantern\",\"dir\":\"s\"},{\"to\":\"byre\",\"dir\":\"w\"}],\"exposure\":\"open\"}],\"yard\":[\"the Yard\",{\"purpose\":\"a back yard\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"n\"},{\"to\":\"tree\",\"dir\":\"w\"}],\"exposure\":\"open\"}],\"lantern\":[\"the Lantern\",{\"purpose\":\"a stone lantern\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"court\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"byre\":[\"the Byre\",{\"purpose\":\"a byre\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"court\",\"dir\":\"e\"}]}],\"tree\":[\"the Old Oak\",{\"purpose\":\"an old oak\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"yard\",\"dir\":\"e\"}],\"exposure\":\"open\"}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"court\",\"is\":\"open\"},{\"id\":\"yard\",\"is\":\"open\"},{\"id\":\"lantern\",\"is\":\"feature\"},{\"id\":\"byre\",\"is\":\"outbuilding\"},{\"id\":\"tree\",\"is\":\"feature\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"w\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"e\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"court\",\"where\":\"around\"},{\"id\":\"yard\",\"where\":\"s\"},{\"id\":\"lantern\",\"kind\":\"lantern\",\"by\":\"court\",\"side\":\"e\"},{\"id\":\"byre\",\"side\":\"s\"},{\"id\":\"tree\",\"kind\":\"tree\",\"side\":\"n\"}]}}")
PLAN_79 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"path\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"garden\",\"dir\":\"n\",\"barrier\":\"closed_door\"},{\"to\":\"yard\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"well\",\"dir\":\"w\",\"barrier\":\"closed_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"path\":[\"the Path\",{\"purpose\":\"a gravel path\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"},{\"to\":\"gate\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"garden\":[\"the Garden\",{\"purpose\":\"a garden\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"s\"},{\"to\":\"lantern\",\"dir\":\"w\"}],\"exposure\":\"open\"}],\"yard\":[\"the Yard\",{\"purpose\":\"a back yard\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"e\"},{\"to\":\"lane\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"lane\":[\"the Lane\",{\"purpose\":\"a lane down the hill\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"yard\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"well\":[\"the Well\",{\"purpose\":\"a stone well\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"e\"}],\"exposure\":\"open\"}],\"lantern\":[\"the Lantern\",{\"purpose\":\"a stone lantern\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"e\"}],\"exposure\":\"open\"}],\"gate\":[\"the Gate\",{\"purpose\":\"a gate\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"path\",\"dir\":\"n\"}],\"exposure\":\"open\"}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"path\",\"is\":\"way\"},{\"id\":\"garden\",\"is\":\"open\"},{\"id\":\"yard\",\"is\":\"open\"},{\"id\":\"lane\",\"is\":\"way\"},{\"id\":\"well\",\"is\":\"feature\"},{\"id\":\"lantern\",\"is\":\"feature\"},{\"id\":\"gate\",\"is\":\"feature\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"e\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"s\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"path\",\"from\":\"entrance\"},{\"id\":\"garden\",\"where\":\"around\"},{\"id\":\"yard\",\"where\":\"w\"},{\"id\":\"lane\",\"side\":\"w\"},{\"id\":\"well\",\"kind\":\"well\",\"by\":\"side\"},{\"id\":\"lantern\",\"kind\":\"lantern\"},{\"id\":\"gate\",\"kind\":\"gate\",\"across\":\"path\",\"end\":\"far\"}]}}")


def test_open_ground_beside_the_house_never_stands_between_two_grounds():
    """An orchard laid behind the house, joined to the court before it, and a
    kailyard the hall's west door opens onto: the kailyard's band touches
    both at the house's corners, was charged as standing between them -- it
    sorted before the orchard -- and its going joined nothing: a round spent,
    and the orchard dropped the round after. A band stands between nothing;
    the orchard gives way, in one round."""
    def mutate(specs, sort, relate):
        specs["court"][1]["adjacent"].append({"to": "orchard", "dir": "n"})
        specs["orchard"] = ("the Orchard", {"purpose": "an orchard", "structure": "court",
                                            "exposure": "open", "adjacent": [{"to": "court", "dir": "s"}]})
        specs["hall"][1]["adjacent"].append({"to": "kailyard", "dir": "w", "barrier": "closed_door"})
        specs["kailyard"] = ("the Kailyard", {"purpose": "a kailyard", "structure": "court",
                                              "exposure": "open", "adjacent": [{"to": "hall", "dir": "e"}]})
        sort["grounds"] += [{"id": "orchard", "is": "open"}, {"id": "kailyard", "is": "open"}]
        relate["grounds"] += [{"id": "orchard", "where": "n"}, {"id": "kailyard", "where": "w"}]

    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    assert refused == []
    assert spec.get("places_dropped") == ["orchard"]
    assert {"court", "kailyard", "lane", "shed"} <= set(spec["ground_is"])


def _farm_yard(mutate=None):
    def with_yard(specs, sort, relate):
        specs["washroom"][1]["adjacent"].append({"to": "yard", "dir": "w", "barrier": "closed_door"})
        specs["yard"] = ("the Yard", {"purpose": "a yard", "structure": "farm", "exposure": "open",
                                      "adjacent": [{"to": "washroom", "dir": "e"}]})
        sort["grounds"].append({"id": "yard", "is": "open"})
        relate["grounds"].append({"id": "yard", "where": "w"})
        if mutate:
            mutate(specs, sort, relate)
    return with_yard


def _without(*gone):
    def mutate(specs, sort, relate):
        for pid in gone:
            specs.pop(pid)
            for _uid, (_name, spec) in specs.items():
                spec["adjacent"] = [e for e in spec.get("adjacent") or () if e.get("to") != pid]
            sort["grounds"] = [g for g in sort["grounds"] if g["id"] != pid]
            relate["grounds"] = [g for g in relate["grounds"] if g["id"] != pid]
            for g in relate["grounds"]:
                if g.get("to") == pid:
                    g.pop("to")
    return mutate


def test_a_place_cut_by_the_only_way_that_reaches_it_is_charged_itself():
    """A yard band west of the farm leaves the garden no ring, and the path
    cuts a pocket off it. The path was charged for the cut -- and the garden
    and the oak, reached through the path alone, went with it. Charging what
    a place hangs on takes the place too; the garden gives way itself."""
    _b, spec, _layout, refused = _lay_farm(_farm_yard(_without("gate", "privy")))
    assert refused == []
    assert spec.get("places_dropped") == ["garden", "tree"]
    assert {"path", "well", "yard"} <= set(spec["ground_is"])


def test_a_thing_on_a_ways_line_takes_no_credit_for_the_ways_cut():
    """The gate across the path's foot stands on the path's own line: given
    back, its cells rejoined the garden the path cut, so it was charged
    before the path -- a round spent, and with the gate joined to the garden
    as well, the gate dropped beside the path. The path gives way alone."""
    def gate_by_the_garden(specs, sort, relate):
        specs["gate"][1]["adjacent"].append({"to": "garden", "dir": "e"})
        specs["garden"][1]["adjacent"].append({"to": "gate", "dir": "w"})

    _b, spec, _layout, refused = _lay_plan(PLAN_79, gate_by_the_garden)
    assert refused == []
    assert spec.get("places_dropped") == ["path"]
    _b, spec, _layout, refused = _lay_farm(_farm_yard())
    assert refused == []
    assert {"gate", "path", "well", "yard"} <= set(spec["ground_is"])


def test_a_building_apart_goes_with_the_charged_ground_on_its_step():
    """A yard band before the house holds the entrance's step and the byre's
    doorstep: the yard was charged for the court's doorway, and the byre for
    its own -- both dropped, and the oak with the yard, where the yard's
    going alone answered both."""
    _b, spec, _layout, refused = _lay_plan(PLAN_41)
    assert refused == []
    assert spec.get("places_dropped") == ["tree", "yard"]
    assert {"byre", "court", "lantern"} <= set(spec["ground_is"])


# --------------------------------------------------- doorway pins on the stub


def _two_solves(db, one_sided=False):
    """The court with no shed, laid round the house (a composite, its
    doorways pinned by cell), the house re-planned, and the court laid again
    as a band before it (one rectangle, pinned by offset): `(cid, scene,
    laid)`, each solve applied to one stub scene as the commit applies it."""
    from agents.director_layout import lay_out_buildings
    from tests.test_a_building_stands_in_its_grounds import _grounds_on, _stub_scene
    from world.structure import _planned_specs, apply_solved_plans
    specs, sort, relate = _court_plan(_without("shed"))
    cid = _court_chat(db)
    _plant_court(cid, specs)
    if one_sided:
        # a second plan op plants the court bare: each of its ways is
        # declared by the other side alone
        _plant_court(cid, specs, only={"court"}, change={"court": {"adjacent": []}})
    _grounds_on(cid)
    scene = _stub_scene(_planned_specs(cid))
    laid = []
    for k, where in enumerate(("around", "s")):
        if k:
            _plant_court(cid, specs, only={"hall", "side", "loft"},
                         change={"side": {"purpose": "a store room"}})
            apply_solved_plans(cid, scene)
        answered = copy.deepcopy(relate)
        next(g for g in answered["grounds"] if g["id"] == "court")["where"] = where
        _s, got = lay_out_buildings(None, cid, copy.deepcopy(scene), ["hall"], "en",
                                    call=_answers(sort, answered))
        laid.append(set(got))
        apply_solved_plans(cid, scene)
    return cid, scene, laid


def test_a_doorway_a_re_solve_pins_the_other_way_keeps_no_old_pin_on_the_stub(temp_db):
    """Laid round the house, the court's doorway onto the hall is pinned by
    cell; laid again as a band, by offset. The plan row took the cell off --
    and the beat's stub, which takes only the fields the row holds, kept it;
    a cell outranks an offset, and the court's doorway stood on its far row,
    eleven paces from the hall's."""
    from world.spatial import _door_cells
    from world.structure import _planned_specs, solved_scene
    cid, scene, laid = _two_solves(temp_db)
    assert {"court", "lane"} <= laid[1]
    preview = solved_scene(_planned_specs(cid))
    for a, b in (("court", "hall"), ("hall", "court"), ("court", "lane"), ("lane", "court")):
        assert _door_cells(scene, a, b) == _door_cells(preview, a, b), (a, b)
    edge = next(e for e in scene["rooms"]["court"]["adjacent"] if e.get("to") == "hall")
    assert edge.get("cell") is None, edge


def test_a_way_one_side_declares_made_again_replaces_its_old_pin(temp_db):
    """The court planted bare, its ways to the hall and the lane declared
    from the other side: the solve writes the court's side of each. Laid
    round the house they were pinned by cell; made again on a band, the old
    cell stayed beside the new offset and outranked it, the court and the
    hall no longer met, and the whole ground was dropped."""
    from agents.director_layout import LAYOUT_RUNS_KEY
    from core.db import wget
    cid, _scene, laid = _two_solves(temp_db, one_sided=True)
    assert {"court", "lane"} <= laid[1], laid
    run = next(iter((wget(cid, LAYOUT_RUNS_KEY) or {}).values()))
    assert not run.get("grounds_dropped"), run.get("grounds_dropped")
    court = _rows(cid)["court"]
    for edge in court.get("adjacent") or ():
        assert not (edge.get("cell") is not None and edge.get("offset") is not None), edge


# ---------------------------------- the third round's own fixes, fuzzed
#
# Plans of the same generator on which the third round's first fixes laid
# fewer places than the tree they were fixing -- each the class, the plan
# only its witness.

PLAN_66 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"court\",\"dir\":\"s\",\"barrier\":\"open_door\"},{\"to\":\"garden\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"yard\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"well\",\"dir\":\"n\",\"barrier\":\"closed_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"e\",\"barrier\":\"closed_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"court\":[\"the Court\",{\"purpose\":\"a stone court\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"garden\":[\"the Garden\",{\"purpose\":\"a garden\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\"}],\"exposure\":\"open\"}],\"yard\":[\"the Yard\",{\"purpose\":\"a back yard\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\"}],\"exposure\":\"open\"}],\"well\":[\"the Well\",{\"purpose\":\"a stone well\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"s\"}],\"exposure\":\"open\"}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"court\",\"is\":\"open\"},{\"id\":\"garden\",\"is\":\"open\"},{\"id\":\"yard\",\"is\":\"open\"},{\"id\":\"well\",\"is\":\"feature\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"n\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"w\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"court\",\"where\":\"s\"},{\"id\":\"garden\",\"where\":\"w\"},{\"id\":\"yard\",\"where\":\"e\"},{\"id\":\"well\",\"kind\":\"well\",\"by\":\"hall\"}]}}")
PLAN_125 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"path\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"garden\",\"dir\":\"e\",\"barrier\":\"closed_door\"},{\"to\":\"privy\",\"dir\":\"e\",\"barrier\":\"closed_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"path\":[\"the Path\",{\"purpose\":\"a gravel path\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"garden\":[\"the Garden\",{\"purpose\":\"a garden\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"w\"},{\"to\":\"lane\",\"dir\":\"n\"},{\"to\":\"shed\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"lane\":[\"the Lane\",{\"purpose\":\"a lane down the hill\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"shed\":[\"the Shed\",{\"purpose\":\"a storehouse\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"s\"}]}],\"privy\":[\"the Privy\",{\"purpose\":\"a privy\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"w\"}]}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"path\",\"is\":\"way\"},{\"id\":\"garden\",\"is\":\"open\"},{\"id\":\"lane\",\"is\":\"way\"},{\"id\":\"shed\",\"is\":\"outbuilding\"},{\"id\":\"privy\",\"is\":\"outbuilding\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"e\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"s\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"path\",\"from\":\"entrance\"},{\"id\":\"garden\",\"where\":\"n\"},{\"id\":\"lane\",\"side\":\"w\"},{\"id\":\"shed\",\"side\":\"e\"},{\"id\":\"privy\",\"side\":\"n\"}]}}")
PLAN_135 = json.loads("{\"specs\":{\"hall\":[\"the Hall\",{\"purpose\":\"a hall with a hearth\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"side\",\"dir\":\"w\",\"barrier\":\"closed_door\"},{\"to\":\"kitchen\",\"dir\":\"n\",\"barrier\":\"open_door\"},{\"to\":\"loft\",\"vertical\":\"up\",\"way\":\"ladder\"},{\"to\":\"court\",\"dir\":\"s\",\"barrier\":\"open_door\"},{\"to\":\"garden\",\"dir\":\"e\",\"barrier\":\"open_door\"},{\"to\":\"privy\",\"dir\":\"e\",\"barrier\":\"closed_door\"}]}],\"side\":[\"the Side Room\",{\"purpose\":\"a sleeping room\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"e\",\"barrier\":\"closed_door\"}]}],\"kitchen\":[\"the Kitchen\",{\"purpose\":\"a kitchen with a stove\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"s\",\"barrier\":\"open_door\"}]}],\"loft\":[\"the Loft\",{\"purpose\":\"a loft\",\"structure\":\"h\",\"exposure\":\"enclosed\",\"adjacent\":[{\"to\":\"hall\",\"vertical\":\"down\",\"way\":\"ladder\"}]}],\"court\":[\"the Court\",{\"purpose\":\"a stone court\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"n\"},{\"to\":\"shed\",\"dir\":\"w\"}],\"exposure\":\"open\"}],\"garden\":[\"the Garden\",{\"purpose\":\"a garden\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\"},{\"to\":\"lane\",\"dir\":\"s\"},{\"to\":\"lantern\",\"dir\":\"s\"},{\"to\":\"byre\",\"dir\":\"w\"}],\"exposure\":\"open\"}],\"lane\":[\"the Lane\",{\"purpose\":\"a lane down the hill\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"n\"},{\"to\":\"gate\",\"dir\":\"s\"}],\"exposure\":\"open\"}],\"lantern\":[\"the Lantern\",{\"purpose\":\"a stone lantern\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"gate\":[\"the Gate\",{\"purpose\":\"a gate\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"lane\",\"dir\":\"n\"}],\"exposure\":\"open\"}],\"shed\":[\"the Shed\",{\"purpose\":\"a storehouse\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"court\",\"dir\":\"e\"}]}],\"byre\":[\"the Byre\",{\"purpose\":\"a byre\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"garden\",\"dir\":\"e\"}]}],\"privy\":[\"the Privy\",{\"purpose\":\"a privy\",\"structure\":\"h\",\"adjacent\":[{\"to\":\"hall\",\"dir\":\"w\"}]}]},\"sort\":{\"rooms\":[{\"id\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"name\":\"hearth\",\"mount\":\"floor\"}]},{\"id\":\"side\",\"fixtures\":[{\"id\":\"bed\",\"name\":\"bed\",\"mount\":\"floor\"}]},{\"id\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"name\":\"stove\",\"mount\":\"floor\"}]},{\"id\":\"loft\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"enclosed\":false}],\"grounds\":[{\"id\":\"court\",\"is\":\"open\"},{\"id\":\"garden\",\"is\":\"open\"},{\"id\":\"lane\",\"is\":\"way\"},{\"id\":\"lantern\",\"is\":\"feature\"},{\"id\":\"gate\",\"is\":\"feature\"},{\"id\":\"shed\",\"is\":\"outbuilding\"},{\"id\":\"byre\",\"is\":\"outbuilding\"},{\"id\":\"privy\",\"is\":\"outbuilding\"}]},\"relate\":{\"rooms\":[{\"id\":\"hall\",\"purpose\":\"hall\",\"fixtures\":[{\"id\":\"hearth\",\"kind\":\"hearth\",\"at\":\"s\"}]},{\"id\":\"side\",\"purpose\":\"bedroom\",\"fixtures\":[{\"id\":\"bed\",\"kind\":\"bed\",\"at\":\"w\"}]},{\"id\":\"kitchen\",\"purpose\":\"kitchen\",\"fixtures\":[{\"id\":\"stove\",\"kind\":\"stove\",\"at\":\"n\"}]},{\"id\":\"loft\",\"purpose\":\"storage\",\"fixtures\":[]}],\"stairs\":[{\"from\":\"hall\",\"to\":\"loft\",\"from_at\":\"n\",\"to_at\":\"n\",\"kind\":\"ladder\"}],\"grounds\":[{\"id\":\"court\",\"where\":\"s\"},{\"id\":\"garden\",\"where\":\"e\"},{\"id\":\"lane\",\"from\":\"entrance\",\"side\":\"s\"},{\"id\":\"lantern\",\"kind\":\"lantern\",\"by\":\"entrance\"},{\"id\":\"gate\",\"kind\":\"gate\",\"across\":\"lane\",\"end\":\"far\"},{\"id\":\"shed\",\"side\":\"n\"},{\"id\":\"byre\",\"side\":\"s\"},{\"id\":\"privy\",\"side\":\"e\"}]}}")


def test_a_place_taken_out_keeps_the_entrance_and_the_house_stands():
    """The court the entrance opens onto is taken out of the ground. Moved
    onto the garden beside it, the entrance faced east while the garden lay
    west; the garden was dropped the next round, the house alone was refused
    for want of walls, and nothing was laid at all."""
    _b, spec, _layout, refused = _lay_plan(PLAN_66)
    assert refused == []
    assert "garden" in spec["ground_is"]
    assert "garden" not in (spec.get("places_dropped") or ())


def test_by_the_entrance_holds_only_where_its_step_can_lie_in_the_things_ground():
    """A lantern joined to a garden east of the house, answered by the
    entrance, which opens south onto the court: kept, the answer pulled the
    lantern to the garden's corner nearest a door it could never stand by,
    and it was dropped. It stands in its garden."""
    _b, spec, _layout, refused = _lay_plan(PLAN_135)
    assert refused == []
    lantern = next(f for f in spec["grounds"]["features"] if f["id"] == "lantern")
    assert lantern.get("by") != "entrance" and lantern["in"] == "garden"
    assert "lantern" in spec["ground_is"]
    assert "lantern" not in (spec.get("places_dropped") or ())


def test_an_outbuilding_off_the_entrances_side_stands_centred_on_its_side():
    """A privy east of the side room, answered north: stood toward that end,
    it crowded the shed at the garden's corner, and the garden was cut. Off
    the entrance's side an outbuilding stands centred on its side, as it
    always has; only on the entrance's side does an end matter."""
    _b, spec, _layout, refused = _lay_plan(PLAN_125)
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    block = next(x for x in spec["blocks"] if x["id"] == "privy")
    assert block["beside"]["side"] != spec["front"] and "toward" not in block
