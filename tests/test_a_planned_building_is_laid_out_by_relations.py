"""A planned building of several storeys, laid out by the solver as the
plan's own geometry (`world/layout_bridge.py`, `agents/director_layout.py`).

The owner's choice of 2026-10-08 (survey rank 6, first slice): the model says
what each planned room holds and how its things relate, code places them, and
the designer dresses the rooms when an actor nears them. Hand-made plans and
stand-in answers, never model output; the names are illustrations, not the
rule. Every test names the rule it pins.
"""
from __future__ import annotations

import pytest
import copy
import json

from world import layout_bridge as lb

SPECS = {
    "hall": ("the Hall", {
        "purpose": "a hall with a hearth and a long table", "structure": "town",
        "exposure": "enclosed",
        "adjacent": [{"to": "street", "dir": "s", "barrier": "closed_door"},
                     {"to": "kitchen", "barrier": "open_door"},
                     {"to": "loft", "vertical": "up", "way": "stair"}],
        "anchors": {"hearth": {"desc": "a stone hearth"}}}),
    "kitchen": ("the Kitchen", {
        "purpose": "a kitchen with a range", "structure": "town", "exposure": "enclosed",
        "adjacent": [{"to": "hall", "barrier": "open_door"},
                     {"to": "yard", "barrier": "closed_door"}]}),
    "loft": ("the Loft", {
        "purpose": "a sleeping loft under the roof", "structure": "town",
        "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"}],
        "anchors": {"gable_window": {"desc": "a gable window over the water"}}}),
    "street": ("the Street", {"purpose": "the street", "structure": "town", "exposure": "open",
                              "adjacent": [{"to": "hall", "dir": "n"}]}),
    # exposure unstated: never guessed into the building
    "yard": ("the Yard", {"purpose": "a yard", "structure": "town",
                          "adjacent": [{"to": "kitchen"}]}),
}

SORT = {"rooms": [
    {"id": "hall", "fixtures": [{"id": "hearth", "name": "the hearth", "mount": "floor"},
                                {"id": "long_table", "name": "the long table", "mount": "floor"},
                                {"id": "benches", "name": "a bench", "mount": "floor", "count": 2}]},
    {"id": "kitchen", "fixtures": [{"id": "range", "name": "the range", "mount": "floor"},
                                   {"id": "basin", "name": "the basin", "mount": "floor"}]},
    {"id": "loft", "fixtures": [{"id": "bed", "name": "a bed", "mount": "floor", "implied": True}],
     "windows": [{"id": "gable_window", "name": "the gable window", "faces": "the water"}]},
    {"id": "attic", "fixtures": [{"id": "trunk", "name": "a trunk"}]}],
    "stairs": [{"from": "hall", "to": "loft", "enclosed": False}]}

RELATE = {"front": "e", "rooms": [
    {"id": "hall", "purpose": "hall",
     "joins": [{"to": "kitchen", "side": "e"}, {"to": "cellar", "side": "w"}],
     "fixtures": [{"id": "hearth", "kind": "hearth", "at": "w"},
                  {"id": "long_table", "kind": "table", "at": "middle"},
                  {"id": "benches", "kind": "bench", "near": "long_table"}]},
    {"id": "kitchen", "purpose": "kitchen",
     "fixtures": [{"id": "range", "kind": "stove", "at": "n"},
                  {"id": "basin", "kind": "basin", "at": "e"}]},
    {"id": "loft", "purpose": "a sleeping room", "windows": [{"id": "gable_window", "side": "n"}],
     "fixtures": [{"id": "bed", "kind": "bed", "at": "e"}]}],
    "stairs": [{"from": "hall", "to": "loft", "from_at": "n", "to_at": "n", "kind": "l"}]}


def _scene():
    return {"rooms": {"hall": {"name": "the Hall", "planned": True, "adjacent": []},
                      "street": {"name": "the Street", "desc": "A street.",
                                 "adjacent": [{"to": "hall", "dir": "n"}]}},
            "positions": {}, "entities": {}}


def _building(specs=None, scene=None):
    (b,) = lb.plan_buildings(copy.deepcopy(specs or SPECS), scene or _scene())
    return b


def test_a_building_is_its_stair_joined_rooms_and_the_walled_rooms_beside_them():
    """A stair says two rooms are two storeys of one building; a room the
    plan states `enclosed` beside them is part of it; a room of unstated
    exposure is never guessed in, so the yard is ground the kitchen opens
    onto. The entrance faces the ground whose bearing the plan states."""
    b = _building()
    assert b["refusal"] is None
    assert b["rooms"] == ["hall", "kitchen", "loft"]
    assert b["levels"] == {"hall": 0, "kitchen": 0, "loft": 1}
    assert {(o["room"], o["to"]) for o in b["outside"]} == {("hall", "street"), ("kitchen", "yard")}
    assert b["entrance"]["room"] == "hall" and b["entrance"]["side"] == "s"
    assert b["stairs"] == [{"low": "hall", "high": "loft", "way": "stair"}]


def test_a_room_the_story_has_seen_or_a_plan_already_sited_keeps_the_building_out():
    """A sited room is described, never re-measured: a building one of whose
    rooms the story has described, or whose plan already stands on a site,
    or that waits as a frontier space, is not laid out again."""
    seen = _scene()
    seen["rooms"]["hall"]["desc"] = "A low hall."
    assert "described" in _building(scene=seen)["refusal"]
    sited = copy.deepcopy(SPECS)
    sited["loft"][1]["site"] = {"plan": "p", "x": 0, "y": 0}
    assert "plan already" in _building(specs=sited)["refusal"]
    (held,) = lb.plan_buildings(copy.deepcopy(SPECS), _scene(), held_open={"kitchen"})
    assert "frontier" in held["refusal"]
    one = copy.deepcopy(SPECS)
    one["loft"][1]["adjacent"] = []
    one["hall"][1]["adjacent"] = [e for e in one["hall"][1]["adjacent"] if not e.get("vertical")]
    assert lb.plan_buildings(one, _scene()) == []


def test_the_answers_are_held_to_the_plan_and_to_the_closed_word_sets():
    """The plan's rooms, joins and stairs are the plan's: a room the sort
    invents and a join the relate invents are dropped; a word outside the
    engine's closed sets is no word (a purpose becomes `other`, a stair
    shape the vocabulary does not hold leaves the shape to the rule); a
    side the plan states wins; the sort's things are never lost."""
    b = _building()
    inv = lb.hold_inventory(b, SORT)
    assert [r["id"] for r in inv["rooms"]] == ["hall", "kitchen", "loft"]
    spec = lb.spec_from_answers(b, inv, RELATE)
    rooms = {r["id"]: r for r in spec["rooms"]}
    assert [j["to"] for j in rooms["hall"]["joins"]] == ["kitchen"]
    assert rooms["loft"]["purpose"] == "other"
    assert spec["front"] == "s", "the street's own bearing fixes the front"
    (stair,) = spec["stairs"]
    assert "kind" not in stair and stair["from"] == "hall" and stair["to"] == "loft"
    assert "l" not in lb.vocabulary()["stair_kinds"]
    # a fixture the relate forgot is still placed, at its size
    forgetful = copy.deepcopy(RELATE)
    forgetful["rooms"][1]["fixtures"] = []
    kitchen = {r["id"]: r for r in lb.spec_from_answers(b, inv, forgetful)["rooms"]}["kitchen"]
    assert {f["id"] for f in kitchen["fixtures"]} == {"range", "basin"}
    # a ladder the plan names is a ladder whatever the answer says
    ladder = copy.deepcopy(SPECS)
    for uid in ("hall", "loft"):
        for e in ladder[uid][1]["adjacent"]:
            if e.get("vertical"):
                e["way"] = "ladder"
    lb_ladder = _building(specs=ladder)
    (stair,) = lb.spec_from_answers(lb_ladder, lb.hold_inventory(lb_ladder, SORT), RELATE)["stairs"]
    assert stair["kind"] == "ladder"


def test_a_solved_building_becomes_the_plans_own_geometry():
    """Each room its rectangle on one plan at its storey's height; each
    fixture the solver stood where asked pinned to its whole rectangle, which
    the engine lays on exactly the solver's cells; each doorway's two sides
    meeting across the wall; the stair the plan's own vertical edge, pinned
    where each room meets it."""
    from world.spatial import _door_cells, anchor_cells
    b = _building()
    inv = lb.hold_inventory(b, SORT)
    spec = lb.spec_from_answers(b, inv, RELATE)
    layout = lb.solve_spec(spec)
    assert lb.refusals(b, spec, layout) == []
    solved, report = lb.planned_layout(b, spec, layout, turn=3)
    assert set(solved) == {"hall", "kitchen", "loft"}
    sites = {uid: s["geometry"]["site"] for uid, s in solved.items()}
    assert {s["plan"] for s in sites.values()} == {b["plan"]}
    assert sites["loft"]["elev_m"] == 3.0 and sites["hall"]["elev_m"] == 0.0
    rooms = {}
    for uid, s in solved.items():
        room = {"name": uid, "desc": uid, **s["geometry"],
                "anchors": s["anchors"], "adjacent": []}
        for to, fields in s["edges"].items():
            room["adjacent"].append({"to": to, "barrier": "open_door", **fields})
        rooms[uid] = room
    for uid in ("hall", "loft"):
        for edge in rooms[uid]["adjacent"]:
            if edge["to"] in ("hall", "loft"):
                edge["vertical"] = "up" if uid == "hall" else "down"
                edge["way"] = "stair"
    sc = {"rooms": rooms, "positions": {}, "entities": {}}
    for uid in solved:
        placed = anchor_cells(sc, uid)
        r = layout.floors[b["levels"][uid]][uid][0]
        for f in layout.fixtures.get(uid) or ():
            if f["id"] not in solved[uid]["anchors"] or "cell" not in solved[uid]["anchors"][f["id"]]:
                continue
            want = sorted((x - r.x, y - r.y) for x, y in f["rect"].cells())
            assert placed[f["id"]]["cells"] == want, (uid, f["id"])
    # the hall and the kitchen meet across one wall at their doorway
    (da,), _ = _door_cells(sc, "hall", "kitchen")
    (db,), _ = _door_cells(sc, "kitchen", "hall")
    pa = (da[0] + sites["hall"]["x"], da[1] + sites["hall"]["y"])
    pb = (db[0] + sites["kitchen"]["x"], db[1] + sites["kitchen"]["y"])
    assert abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) == 1
    # the stair: the plan's edge, pinned inside each room it joins
    for uid, other in (("hall", "loft"), ("loft", "hall")):
        cell = tuple(solved[uid]["edges"][other]["cell"])
        ext = solved[uid]["geometry"]["extent"]
        assert 0 <= cell[0] < ext["w"] and 0 <= cell[1] < ext["d"]
    # a window blocks no line, and every record names its plan
    window = solved["loft"]["anchors"]["gable_window"]
    assert window["opacity"] == "see_through" and window["desc"] == "a gable window over the water"
    assert all(s["layout"]["plan"] == b["plan"] for s in solved.values())
    json.dumps(solved)


def test_a_fixture_the_solver_moved_or_could_not_place_is_never_pinned():
    """Never a move made silently (the owner: "capacity goes back to the
    model"). A fixture the solver stood off the wall the model named is
    written on that wall and pinned nowhere -- the engine lays it along that
    wall as every unpinned fixture, and the designer dressing the room sees
    what it crowds -- and one it could not place at all is written the same
    way; both are listed. A window keeps the outside wall the solver found,
    since a window in an inside wall is none, and its move is listed too."""
    from world.layout_solver import Layout, Rect
    b = _building()
    spec = lb.spec_from_answers(b, lb.hold_inventory(b, SORT), RELATE)
    layout = Layout(name="hall")
    layout.floors = {0: {"hall": [Rect(0, 0, 6, 5)], "kitchen": [Rect(6, 0, 3, 5)]},
                     1: {"loft": [Rect(0, 0, 6, 5)]}}
    layout.fixtures = {
        "hall": [{"id": "hearth", "name": "the hearth", "kind": "hearth", "at": "w",
                  "rect": Rect(5, 1, 1, 2), "height": "waist"},
                 {"id": "long_table", "name": "the long table", "kind": "table", "at": "middle",
                  "rect": Rect(2, 0, 2, 2), "height": "waist"}],
        "kitchen": [], "loft": []}
    layout.windows = [{"id": "gable_window", "base": "gable_window", "room": "loft",
                       "level": 1, "side": "e", "cell": [5, 2]}]
    solved, report = lb.planned_layout(b, spec, layout)
    hearth = solved["hall"]["anchors"]["hearth"]
    assert hearth["dir"] == "w" and "cell" not in hearth and "extent" not in hearth
    table = solved["hall"]["anchors"]["long_table"]
    assert "cell" not in table and "dir" not in table, "asked for the middle, stood at a wall"
    moved = {(m["room"], m["anchor"]) for m in report["moved"]}
    assert moved == {("hall", "hearth"), ("hall", "long_table"), ("loft", "gable_window")}
    unplaced = {(u["room"], u["anchor"]) for u in report["unplaced"]}
    assert ("kitchen", "range") in unplaced and ("loft", "bed") in unplaced
    assert solved["kitchen"]["anchors"]["range"]["dir"] == "n"
    assert "cell" not in solved["kitchen"]["anchors"]["range"]
    assert solved["loft"]["anchors"]["gable_window"]["dir"] == "e"
    assert solved["hall"]["layout"]["moved"] and solved["kitchen"]["layout"]["unplaced"]


def test_the_rooms_estimated_size_is_no_target_and_never_a_refusal():
    """The owner's ruling of 2026-10-10, "size from contents, like the lab":
    the plan's `extent` is the Writers' Room's ESTIMATE. Chat 164's Room
    planned Hinami's room at 36 m2 against the lore's six mats, and a solve
    held to a quarter of its estimates was refused room after room. The
    estimate never reaches the solver, a solve far from it is never refused,
    and the record files the two side by side -- the plan's numbers are
    written over by the solve's, and that is where they are still read."""
    specs = copy.deepcopy(SPECS)
    specs["kitchen"][1]["extent"] = {"w": 20, "d": 20}
    b = _building(specs=specs)
    inv = lb.hold_inventory(b, SORT)
    spec = lb.spec_from_answers(b, inv, RELATE)
    assert not any("area_m2" in r for r in spec["rooms"]), "an estimate is no target"
    layout = lb.solve_spec(spec)
    assert not any("was planned" in r for r in lb.refusals(b, spec, layout))
    r = layout.floors[0]["kitchen"][0]
    solved, report = lb.planned_layout(b, spec, layout, inventory=inv)
    assert solved["kitchen"]["geometry"]["extent"] == {"w": r.w, "d": r.d}
    assert solved["kitchen"]["layout"]["stated"] == {"w": 20, "d": 20}
    assert {"room": "kitchen", "stated": {"w": 20, "d": 20},
            "solved": {"w": r.w, "d": r.d}} in report["stated"]


def test_a_size_the_lore_states_is_the_one_size_the_solver_aims_at():
    """The second call reads the story's lore (`description`) and gives a
    room's `area_m2` only where the lore states that room's size, as the
    layout lab's prompt asked; the solver aims at it, never below what the
    room holds (`layout_solver.room_target`), and the record files it
    against the solve. With no description there is no lore to state a
    size, so an area an answer gives is the model's own estimate, dropped."""
    from world.layout_solver import PACE_M, room_target
    b = _building()
    inv = lb.hold_inventory(b, SORT)
    relate = copy.deepcopy(RELATE)
    kitchen = next(r for r in relate["rooms"] if r["id"] == "kitchen")
    told = dict(b, description="The kitchen is thirty square metres of flagstones.")

    def aimed(building):
        spec = lb.spec_from_answers(building, inv, relate)
        return next(r for r in spec["rooms"] if r["id"] == "kitchen").get("area_m2")

    kitchen["area_m2"] = 30
    assert aimed(told) == 30
    assert aimed(b) is None, "no lore, no stated size"
    for junk in (0, -4, "large", True, float("nan"), None):
        kitchen["area_m2"] = junk
        assert aimed(told) is None, junk
    kitchen["area_m2"] = 30
    spec = lb.spec_from_answers(told, inv, relate)
    room = next(r for r in spec["rooms"] if r["id"] == "kitchen")
    assert room_target(room) >= 30 / (PACE_M * PACE_M)
    layout = lb.solve_spec(spec)
    r = layout.floors[0]["kitchen"][0]
    solved, report = lb.planned_layout(told, spec, layout, inventory=inv)
    assert solved["kitchen"]["layout"]["described_m2"] == 30
    assert {"room": "kitchen", "area_m2": 30, "solved": {"w": r.w, "d": r.d}} in report["described"]
    assert "described_m2" not in solved["hall"]["layout"]


# ---------------------------------------------------------------------------
# The plan tier: written by code, carried to the stubs by the commit
# ---------------------------------------------------------------------------

def _chat(db):
    import time
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Layout", "A town.", time.time()))
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def _plant(cid):
    from world.structure import plant_structure
    rooms = {uid: dict(spec, name=name) for uid, (name, spec) in copy.deepcopy(SPECS).items()}
    for room in rooms.values():
        room.pop("structure", None)
    plant_structure(cid, {"key": "town", "name": "Town"}, rooms)


BRIEF = {"brief": "The hall faces the street; the kitchen lies behind it; the stair runs along "
                  "the hall's back wall up to the loft over the hall."}


def _answers(calls):
    def call(step, system, payload):
        calls.append(step)
        if step.endswith("_brief"):
            return copy.deepcopy(BRIEF)
        return copy.deepcopy(SORT if step.endswith("_sort") else RELATE)
    return call


def _registry(cid):
    from world.structure import registry_rows
    return {uid: entry["planned"] for uid, entry in registry_rows(cid).items()}


def test_the_layout_tier_is_on_unless_the_host_turns_it_off(temp_db):
    """On by default since the owner judged the bridge's shrine clean enough
    (2026-10-10: "Bridge lane now, then on"; "It's ok enough now") -- and
    turned off it reads nothing and calls nothing."""
    from agents.director_layout import (LAYOUT_TIER_SETTING, lay_out_buildings,
                                        layout_tier_enabled)
    from core.db import set_setting
    cid = _chat(temp_db)
    _plant(cid)
    calls = []
    scene = _scene()
    before = copy.deepcopy(scene)
    assert layout_tier_enabled(), "on where the host has said nothing"
    for word in ("off", "0", "false", "no"):
        set_setting(LAYOUT_TIER_SETTING, word)
        assert not layout_tier_enabled(), word
    set_setting(LAYOUT_TIER_SETTING, "off")
    got, laid_out = lay_out_buildings(None, cid, scene, ["hall"], "en", call=_answers(calls))
    assert got is scene and laid_out == set()
    assert calls == [] and scene == before
    assert not any((p or {}).get("site") for p in _registry(cid).values())


def test_the_tier_writes_the_plan_never_the_scene_and_the_commit_carries_it(temp_db):
    """The tier writes the building into the PLAN (`write_planned_layout`)
    and brings only its own copy of the scene up to it; the stored scene is
    the commit's, and the next fringe pass carries the solve onto the stubs
    -- onto the anchors the stub was minted with, too."""
    from agents.director_layout import LAYOUT_TIER_SETTING, lay_out_buildings
    from core.db import set_setting, wget, wset
    from world.structure import apply_planned_layout, materialize_planned_fringe
    cid = _chat(temp_db)
    _plant(cid)
    set_setting(LAYOUT_TIER_SETTING, "on")
    stored = _scene()
    stored["rooms"]["hall"]["anchors"] = {"hearth": {"desc": "a stone hearth"}}
    stored["positions"] = {"Walker": "street"}
    wset(cid, "scene", stored)
    calls = []
    scene = copy.deepcopy(stored)
    _scene_back, laid_out = lay_out_buildings(None, cid, scene, ["hall"], "en",
                                              call=_answers(calls))
    assert laid_out == {"hall", "kitchen", "loft"}
    assert calls == ["director_rooms_layout_brief", "director_rooms_layout_sort", "director_rooms_layout_relate"]
    plan = _registry(cid)
    for uid in ("hall", "kitchen", "loft"):
        assert plan[uid]["site"]["plan"] == "layout:hall", uid
    assert plan["hall"]["anchors"]["hearth"]["desc"] == "a stone hearth"
    assert plan["street"].get("site") is None
    # the job's own copy is up to the plan; the stored scene is untouched
    assert scene["rooms"]["hall"]["site"]["plan"] == "layout:hall"
    assert wget(cid, "scene") == stored
    # the commit's fringe pass carries it onto the stub it already made
    committed, _added = materialize_planned_fringe(cid, copy.deepcopy(stored))
    hall = committed["rooms"]["hall"]
    assert hall["site"] == plan["hall"]["site"]
    for key in ("cell", "extent", "dir"):
        assert hall["anchors"]["hearth"].get(key) == plan["hall"]["anchors"]["hearth"].get(key)
    # a described room is the story's: never brought up to the plan
    seen = copy.deepcopy(stored)
    seen["rooms"]["hall"]["desc"] = "A low hall."
    assert apply_planned_layout(seen, {"hall": ("the Hall", plan["hall"])}) == []
    assert "site" not in seen["rooms"]["hall"]


def test_a_refused_building_is_written_nowhere_and_waits_before_trying_again(temp_db):
    """Fails open: an answer that cannot be laid out writes nothing, the
    building's attempt is filed, and it waits as a failed design waits
    (`director_rooms.predevelop_retry_beats`) before costing calls again."""
    from agents.director_layout import (LAYOUT_RUNS_KEY, LAYOUT_TIER_SETTING,
                                        lay_out_buildings)
    from core.db import set_setting, wget
    from core.jobs import Job
    cid = _chat(temp_db)
    _plant(cid)
    set_setting(LAYOUT_TIER_SETTING, "1")
    calls = []

    def broken(step, system, payload):
        calls.append(step)
        raise ValueError("no JSON")

    job = Job(cid, "room_predevelopment", 2)
    lay_out_buildings(job, cid, _scene(), ["hall"], "en", call=broken)
    # the brief fails open; the first call that cannot be read fails the building
    assert calls == ["director_rooms_layout_brief", "director_rooms_layout_sort"]
    assert not any((p or {}).get("site") for p in _registry(cid).values())
    (entry,) = wget(cid, LAYOUT_RUNS_KEY).values()
    assert entry["failed"] == 1 and entry["reasons"]
    lay_out_buildings(job, cid, _scene(), ["hall"], "en", call=broken)
    assert calls == ["director_rooms_layout_brief", "director_rooms_layout_sort"], "a failed building waits"
    later = Job(cid, "room_predevelopment", 2 + 2)
    lay_out_buildings(later, cid, _scene(), ["hall"], "en", call=broken)
    assert calls == ["director_rooms_layout_brief", "director_rooms_layout_sort"] * 2, \
        "and is tried again once its wait is over"


def test_the_plan_is_written_only_onto_the_plan_that_was_solved(temp_db):
    """All or nothing, and only onto the rows the solve read: a building
    whose plan the Room changed underneath the solve is not written."""
    from world.structure import write_planned_layout
    cid = _chat(temp_db)
    _plant(cid)
    plan = _registry(cid)
    solved = {"hall": {"geometry": {"site": {"plan": "p", "x": 0, "y": 0, "elev_m": 0.0}}}}
    stale = {"hall": dict(plan["hall"], purpose="a different hall")}
    assert write_planned_layout(cid, solved, expected=stale) is False
    assert _registry(cid)["hall"].get("site") is None
    assert write_planned_layout(cid, solved, expected={"hall": plan["hall"]}) is True
    assert _registry(cid)["hall"]["site"]["plan"] == "p"


def test_a_planned_room_carries_its_site_onto_its_stub_and_an_unreadable_one_is_none():
    """`site` travels with the plan's geometry (`structure.GEOMETRY_FIELDS`),
    read through `site_plan.normalize_site`: a site that is not a place on
    a plan is no site at all."""
    from world.structure import GEOMETRY_FIELDS, planned_geometry
    assert "site" in GEOMETRY_FIELDS
    got = planned_geometry({"extent": {"w": 4, "d": 3}, "site": {"plan": "p", "x": 2.0, "y": 5}})
    assert got["site"] == {"plan": "p", "x": 2, "y": 5, "elev_m": None}
    assert "site" not in planned_geometry({"site": {"x": 1, "y": 2}})
    assert "site" not in planned_geometry({"site": "behind the church"})


def test_a_side_the_room_planned_is_a_wish_the_solve_may_turn():
    """The owner's ruling of 2026-10-10, "sides are wishes, like the lab":
    before any room is described a side the Room planned is weighed as the
    lab weighed every side, and the solve may turn it -- never refused, the
    turn filed beside the solve and marked `planned`, the plan's own doorway
    written on the wall the solve chose. Held as a fact it refused all three
    of the owner's refined shrine's answer sets. A side the MODEL chose is
    filed the same way, unmarked."""
    from world.layout_solver import Layout, Rect
    specs = copy.deepcopy(SPECS)
    specs["hall"][1]["adjacent"][1]["dir"] = "e"          # the plan: the kitchen lies east
    b = _building(specs=specs)
    spec = lb.spec_from_answers(b, lb.hold_inventory(b, SORT), RELATE)
    layout = Layout(name="hall")
    layout.floors = {0: {"hall": [Rect(0, 3, 6, 5)], "kitchen": [Rect(0, 0, 6, 3)]},
                     1: {"loft": [Rect(0, 3, 6, 5)]}}
    layout.doors = [{"a": "hall", "b": "kitchen", "level": 0, "side": "n", "cell": [2, 3]},
                    {"a": "hall", "b": "entrance", "level": 0, "side": "w", "cell": [0, 5],
                     "outside": True},
                    {"a": "kitchen", "b": "yard", "level": 0, "side": "n", "cell": [3, 0],
                     "outside": True}]
    reasons = lb.refusals(b, spec, layout)
    assert not any("was planned through" in r or "was planned to open onto" in r for r in reasons), reasons
    solved, report = lb.planned_layout(b, spec, layout)
    assert {"room": "hall", "to": "kitchen", "asked": "e", "solved": "n", "planned": True} in report["sides"]
    assert solved["hall"]["edges"]["kitchen"]["dir"] == "n", "the plan's doorway moves with the solve"
    assert solved["kitchen"]["edges"]["hall"]["dir"] == "s"
    # a side only the model chose is listed, never refused, and unmarked
    model_side = copy.deepcopy(RELATE)
    model_side["rooms"][1]["joins"] = [{"to": "yard", "side": "e"}]
    b2 = _building()
    spec2 = lb.spec_from_answers(b2, lb.hold_inventory(b2, SORT), model_side)
    assert not any("yard" in r for r in lb.refusals(b2, spec2, layout))
    _solved, report = lb.planned_layout(b2, spec2, layout)
    assert {"room": "kitchen", "to": "yard", "asked": "e", "solved": "n"} in report["sides"]
    assert _solved["kitchen"]["layout"]["sides"]


def test_a_zone_the_sort_named_is_never_lost():
    """What the first call sorted a room to hold reaches the solver even when
    the second call forgets it -- a fixture at its size, a zone where it fits."""
    sort = copy.deepcopy(SORT)
    sort["rooms"][0]["zones"] = [{"id": "sitting", "name": "the sitting end"}]
    b = _building()
    inv = lb.hold_inventory(b, sort)
    hall = {r["id"]: r for r in lb.spec_from_answers(b, inv, RELATE)["rooms"]}["hall"]
    assert [z["id"] for z in hall["zones"]] == ["sitting"]


# ---------------------------------------------------------------------------
# The room in view of the beat that follows the solve
# ---------------------------------------------------------------------------

STREET = {"name": "the Street", "desc": "A street of shut shops.",
          "adjacent": [{"to": "hall", "dir": "n", "barrier": "open_door"}]}


def _story_on_the_street(temp_db):
    """A chat whose stored scene is the street with the hall's stub in view
    through an open door, the plan planted, a canon book for the registry,
    and the player and Mara on the street -- the scene commit N leaves."""
    from tests.director_fakes import _action_interp, _make_ctx
    from world.structure import materialize_planned_fringe
    scene = {"location": "the Street", "rooms": {"street": copy.deepcopy(STREET)},
             "positions": {"The Stranger": "street", "Mara": "street"},
             "entities": {}, "attire": {}, "overlays": {}}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    canon = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
                       ("Canon", ctx.chat.id, "general"))
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, ctx.chat.id))
    ctx.chat.lorebook_id = canon
    _plant(ctx.chat.id)
    stored, _ = materialize_planned_fringe(ctx.chat.id, temp_db.wget(ctx.chat.id, "scene"))
    temp_db.wset(ctx.chat.id, "scene", stored)
    assert stored["rooms"]["hall"].get("planned") and not stored["rooms"]["hall"].get("site")
    return ctx


HALL_DESIGN = {"name": "the Hall", "desc": "A low hall, a stone hearth on its west wall."}


def _job_answers(calls):
    """The room role between turns: the layout tier's three answers, and a
    designer that drafts the hall it owes and submits."""
    def answer(role, step_key, system, payload, **kw):
        calls.append(step_key)
        if step_key.endswith("_layout_brief"):
            return copy.deepcopy(BRIEF)
        if step_key.endswith("_layout_sort"):
            return copy.deepcopy(SORT)
        if step_key.endswith("_layout_relate"):
            return copy.deepcopy(RELATE)
        owed = list(payload.get("develop") or {})
        drafts = [{"tool": "draft_room", "args": {"room_id": rid, "room": copy.deepcopy(HALL_DESIGN)}}
                  for rid in owed if rid == "hall"]
        return {"calls": drafts + [{"tool": "submit", "args": {}}]}
    return answer


def _wait(job):
    import time
    deadline = time.monotonic() + 30.0
    while job.state in ("pending", "running") and time.monotonic() < deadline:
        time.sleep(0.02)
    assert job.state == "done", job.as_dict()
    return job


def test_the_room_in_view_of_the_next_beat_stands_on_its_solved_site(temp_db, monkeypatch):
    """THE BEAT AFTER THE SOLVE OPENS ON THE PLAN. The job between turns lays
    the building out, writes the plan and designs the hall in view on the
    plan's geometry; the next beat opens on the stored scene, where the hall
    is still the stub commit N minted. That scene is brought up to the solved
    plan before anything reads it -- the install, the Director, perception --
    and so is the scene the commit merges the beat onto, so the hall the beat
    builds in stands where the solver put it, its fixtures on the solver's
    cells, and the rest of the building is laid out on the same plan.
    (Review of 2026-10-08, F1: the hall was committed off the plan, its
    hearth unpinned, and the fringe skipped it for good.)"""
    import agents.common as common
    import agents.director as director
    from agents import director_rooms, perception
    from agents.director_layout import LAYOUT_TIER_SETTING
    from core.db import set_setting
    from llm import decisions
    from persist import commit
    from tests.director_fakes import _fake_agent
    from tests.test_a_room_in_view_is_built_before_anyone_walks_in import _decide, _next_beat

    ctx = _story_on_the_street(temp_db)
    cid = ctx.chat.id
    set_setting(LAYOUT_TIER_SETTING, "on")
    calls = []
    monkeypatch.setattr(common, "_agent_json", _job_answers(calls))
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert calls[:3] == ["director_rooms_layout_brief", "director_rooms_layout_sort",
                         "director_rooms_layout_relate"], calls
    plan = _registry(cid)
    assert plan["hall"]["site"]["plan"] == "layout:hall"
    filed = temp_db.wget(cid, director_rooms.PREPARED_KEY)["hall"]
    assert filed["clean"] is True, filed

    beat = _next_beat(temp_db, ctx)
    # THE SCENE THE BEAT READS, before anything of it is committed: the hall
    # stands on its solved site with its fixtures on the solver's cells,
    # while the stored scene still holds the stub commit N minted.
    from story.scene import get_scene
    assert not temp_db.wget(cid, "scene")["rooms"]["hall"].get("site")
    opened = get_scene(cid)["rooms"]["hall"]
    assert opened.get("site") == plan["hall"]["site"], opened.get("site")
    for aid, anchor in plan["hall"]["anchors"].items():
        if "cell" in anchor:
            assert opened["anchors"][aid]["cell"] == anchor["cell"], aid
            assert opened["anchors"][aid].get("extent") == anchor.get("extent"), aid
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    beat_calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(beat_calls, {
        "director_prose": {"prose": "Mara looks through the door at the hall."},
        "director_specialist": {"events": [
            {"source_entity_id": "character:1", "event": "Mara looks.",
             "item_names": ["Mara"], "transforms": []}]},
        "director_rooms": {"calls": [{"tool": "submit", "args": {}}]}}))
    beat.director_interpret = director.director_interpret(beat, nonce=0)
    assert beat.director_interpret["orchestration"]["installed_rooms"] == ["hall"]
    beat["perception_act"] = perception.perception_act(beat, 0)
    beat.director_resolve = director.director_resolve(beat, nonce=0)
    beat["perception_outcome"] = perception.perception_outcome(beat, 0)
    commit.commit_scene(beat, nonce=0, prepared=commit.prepare_scene_commit(beat))

    stored = temp_db.wget(cid, "scene")
    hall = stored["rooms"]["hall"]
    assert hall["desc"] == HALL_DESIGN["desc"]
    assert hall.get("site") == plan["hall"]["site"], hall.get("site")
    assert hall["extent"] == plan["hall"]["extent"]
    pinned = {aid: a for aid, a in plan["hall"]["anchors"].items() if "cell" in a}
    assert pinned, plan["hall"]["anchors"]
    for aid, anchor in pinned.items():
        assert hall["anchors"][aid]["cell"] == anchor["cell"], aid
        assert hall["anchors"][aid].get("extent") == anchor.get("extent"), aid
    # The walker steps in: the next commit's fringe mints the rest of the
    # building on the same plan, and the hall meets its stair where the plan
    # pinned it -- one building, not half of one.
    from world.structure import materialize_planned_fringe
    inside = copy.deepcopy(stored)
    inside["positions"]["The Stranger"] = "hall"
    inside, _added = materialize_planned_fringe(cid, inside)
    for uid in ("kitchen", "loft"):
        assert inside["rooms"][uid]["site"] == plan[uid]["site"], uid
    stair = next(e for e in inside["rooms"]["hall"]["adjacent"] if e.get("to") == "loft")
    assert stair.get("cell") == next(e for e in plan["hall"]["adjacent"]
                                     if e.get("to") == "loft").get("cell")


def test_the_design_job_designs_on_the_plan_an_earlier_run_solved(temp_db, monkeypatch):
    """An earlier run solved the building and wrote the plan; no commit has
    run since, so the stored scene still holds the hall's unsited stub. The
    next run designs the hall on the scene the next beat will open on -- the
    stub on its solved site, its fixtures on the solver's cells -- never on
    the stored stub (the job reads the scene through the plan, as `get_scene`
    does for every reader of a beat)."""
    import agents.common as common
    from agents import director_layout, director_rooms
    from agents.director_layout import LAYOUT_TIER_SETTING
    from core.db import set_setting
    ctx = _story_on_the_street(temp_db)
    cid = ctx.chat.id
    set_setting(LAYOUT_TIER_SETTING, "on")
    stored = temp_db.wget(cid, "scene")
    _scene, laid = director_layout.lay_out_buildings(None, cid, copy.deepcopy(stored), ["hall"],
                                                     "en", call=_answers([]))
    assert laid == {"hall", "kitchen", "loft"}
    plan = _registry(cid)
    assert not temp_db.wget(cid, "scene")["rooms"]["hall"].get("site")
    seen = []
    design = director_rooms.design_rooms

    def watching(ctx_, scene, *args, **kwargs):
        seen.append(copy.deepcopy((scene.get("rooms") or {}).get("hall")))
        return design(ctx_, scene, *args, **kwargs)

    monkeypatch.setattr(director_rooms, "design_rooms", watching)
    calls = []
    monkeypatch.setattr(common, "_agent_json", _job_answers(calls))
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert "director_rooms_layout_sort" not in calls, "the building stands on its plan already"
    assert seen, calls
    hall = seen[0]
    assert hall.get("site") == plan["hall"]["site"], hall.get("site")
    for aid, anchor in plan["hall"]["anchors"].items():
        if "cell" in anchor:
            assert hall["anchors"][aid]["cell"] == anchor["cell"], aid


def test_a_design_filed_before_its_building_was_laid_out_is_made_again_on_the_plan(
        temp_db, monkeypatch):
    """A design made before the solve was made on another room -- its own
    measurements, its fixtures where its designer put them -- and its brief
    reads only names, purposes and exits, so where the plan stated every
    side the solve keeps, its fingerprint still matches. The run that lays
    the building out drops it, and the room is designed again on the plan."""
    import agents.common as common
    from agents import director_rooms
    from agents.director_layout import LAYOUT_TIER_SETTING
    from core.db import set_setting
    from world.structure import plant_structure

    ctx = _story_on_the_street(temp_db)
    cid = ctx.chat.id
    # every side of the hall stated, so the solve changes no brief
    rooms = {uid: dict(spec, name=name) for uid, (name, spec) in copy.deepcopy(SPECS).items()}
    for room in rooms.values():
        room.pop("structure", None)
    rooms["hall"]["adjacent"][1]["dir"] = "e"
    plant_structure(cid, {"key": "town", "name": "Town"}, rooms)
    calls = []
    monkeypatch.setattr(common, "_agent_json", _job_answers(calls))
    set_setting(LAYOUT_TIER_SETTING, "off")                      # the tier is off
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert "director_rooms_layout_sort" not in calls
    before = temp_db.wget(cid, director_rooms.PREPARED_KEY)["hall"]
    assert before["clean"] is True
    assert calls.count("director_rooms") == 1

    set_setting(LAYOUT_TIER_SETTING, "on")
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert _registry(cid)["hall"]["site"]["plan"] == "layout:hall"
    after = temp_db.wget(cid, director_rooms.PREPARED_KEY)["hall"]
    assert after["brief"] == before["brief"], "the solve left the hall's brief as it was"
    assert calls.count("director_rooms") == 2, "designed again, on the plan"


# ---------------------------------------------------------------------------
# What the plan states is held: its proportions, its shapes, its fixtures,
# its open ground (review of 2026-10-08, F2-F4)
# ---------------------------------------------------------------------------

def _solve(specs=None, sort=None, relate=None):
    b = _building(specs=specs)
    inv = lb.hold_inventory(b, copy.deepcopy(sort or SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(relate or RELATE))
    layout = lb.solve_spec(spec)
    return b, inv, spec, layout


def test_every_estimate_is_filed_against_the_solve_and_none_is_refused():
    """A long hall, a near-square one, a small one. Until the owner's ruling
    of 2026-10-10 a stated extent was a measurement and its proportion too:
    the review of 2026-10-08 (F2) measured a hall planned twelve by three
    solved six by five and refused it. Whatever the solver now makes of each
    estimate from what the hall holds, the building is never refused for
    it, and the record files the estimate against the solved size either
    way."""
    for stated in ((12, 3), (6, 5), (4, 4)):
        specs = copy.deepcopy(SPECS)
        specs["hall"][1]["extent"] = {"w": stated[0], "d": stated[1]}
        b, inv, spec, layout = _solve(specs=specs)
        r = layout.floors[0]["hall"][0]
        assert not any("hall was planned" in x for x in lb.refusals(b, spec, layout)), stated
        solved, report = lb.planned_layout(b, spec, layout, inventory=inv)
        assert solved["hall"]["layout"]["stated"] == {"w": stated[0], "d": stated[1]}
        assert {"room": "hall", "stated": {"w": stated[0], "d": stated[1]},
                "solved": {"w": r.w, "d": r.d}} in report["stated"]


def test_a_room_the_plan_states_is_not_a_rectangle_keeps_its_building_out():
    """The solver lays rectangles; written back, a round tower room would be
    squared for good. Refused before any call is made."""
    rounded = copy.deepcopy(SPECS)
    rounded["loft"][1]["shape"] = "round"
    refusal = _building(specs=rounded)["refusal"]
    assert refusal and "loft is planned round" in refusal
    squared = copy.deepcopy(SPECS)
    squared["loft"][1]["shape"] = "rectangle"
    assert _building(specs=squared)["refusal"] is None


def test_a_fixture_the_plan_lists_is_never_lost_to_the_answer():
    """The plan's fixtures are the plan's, as its rooms are: one the answer
    leaves out is kept as the plan holds it and counted -- never handed to
    the solver as a thing of a size code chose -- and one whose id the answer
    gave to a zone is still the plan's record, the zone taking an id of its
    own."""
    dropped = copy.deepcopy(SORT)
    hall = dropped["rooms"][0]
    hall["fixtures"] = [f for f in hall["fixtures"] if f["id"] != "hearth"]
    hall["zones"] = [{"id": "hearth", "name": "the hearth side"}]
    b = _building()
    inv = lb.hold_inventory(b, dropped)
    held = {r["id"]: r for r in inv["rooms"]}["hall"]
    assert held["restored"] == [{"id": "hearth", "name": "a stone hearth"}]
    assert "hearth" not in {f["id"] for f in held["fixtures"]}
    assert [z["id"] for z in held["zones"]] != ["hearth"], held["zones"]
    relate = copy.deepcopy(RELATE)
    relate["rooms"][0]["fixtures"] = [f for f in relate["rooms"][0]["fixtures"]
                                      if f["id"] != "hearth"]
    spec = lb.spec_from_answers(b, inv, relate)
    assert "hearth" not in {f["id"] for f in {r["id"]: r for r in spec["rooms"]}["hall"]["fixtures"]}
    layout = lb.solve_spec(spec)
    solved, report = lb.planned_layout(b, spec, layout, inventory=inv)
    assert "hearth" not in solved["hall"]["anchors"], "nothing written: the plan's record stands"
    # and said: an answer that gave the plan's hearth a new id shows as two
    assert {"room": "hall", "anchor": "hearth", "name": "a stone hearth"} in report["restored"]
    assert solved["hall"]["layout"]["restored"] == [
        {"room": "hall", "anchor": "hearth", "name": "a stone hearth"}]


def test_a_plan_anchor_the_answer_leaves_out_or_files_as_a_zone_stays_as_the_plan_holds_it(
        temp_db):
    """WHAT A THING IS STAYS THE MODEL'S TO SAY. A window the plan lists that
    the first call leaves out, and a place the plan lists that the first call
    files as a zone -- an area, not a thing -- are kept as the plan holds
    them: no cell, no rectangle, nothing the solver placed, so the engine
    reads each as the plan's bare record and the room's designer meets it as
    the plan named it. Both are listed as restored. (Review of 2026-10-08,
    R2-2: each was restored as a middling floor thing and pinned, an opaque
    waist-high obstacle whose nature code had decided.)"""
    from world.spatial import anchor_cells
    from world.structure import (_planned_specs, materialize_planned_fringe,
                                 write_planned_layout)
    specs = copy.deepcopy(SPECS)
    specs["hall"][1]["anchors"]["stair_foot"] = {"desc": "the foot of the stair, where people wait"}
    sort = copy.deepcopy(SORT)
    sort["rooms"][2]["windows"] = []                    # the loft's plan window, left out
    sort["rooms"][0]["zones"] = [{"id": "stair_foot", "name": "the foot of the stair",
                                  "why": "where people wait"}]
    relate = copy.deepcopy(RELATE)
    relate["rooms"][2]["windows"] = []
    b, inv, spec, layout = _solve(specs=specs, sort=sort, relate=relate)
    held = {r["id"]: r for r in inv["rooms"]}
    assert {f["id"] for f in held["loft"]["restored"]} == {"gable_window"}
    assert {f["id"] for f in held["hall"]["restored"]} == {"stair_foot"}
    assert [z["id"] for z in held["hall"]["zones"]] != ["stair_foot"], "the zone has its own id"
    assert lb.refusals(b, spec, layout) == []
    solved, report = lb.planned_layout(b, spec, layout, inventory=inv)
    assert {(r["room"], r["anchor"]) for r in report["restored"]} == {
        ("loft", "gable_window"), ("hall", "stair_foot")}
    # through the plan's own write and onto the stubs the commit stores
    cid = _chat(temp_db)
    rooms = {uid: dict(sp, name=name) for uid, (name, sp) in copy.deepcopy(specs).items()}
    for room in rooms.values():
        room.pop("structure", None)
    from world.structure import plant_structure
    plant_structure(cid, {"key": "town", "name": "Town"}, rooms)
    assert write_planned_layout(cid, solved, expected={uid: _planned_specs(cid)[uid][1]
                                                      for uid in b["rooms"]})
    plan = _registry(cid)
    assert plan["loft"]["anchors"]["gable_window"] == {"desc": "a gable window over the water"}
    assert plan["hall"]["anchors"]["stair_foot"] == {"desc": "the foot of the stair, where people wait"}
    street = {"name": "the Street", "desc": "A street.",
              "adjacent": [{"to": "hall", "dir": "n", "barrier": "open_door"}]}
    sc, _ = materialize_planned_fringe(cid, {"rooms": {"street": street},
                                             "positions": {"Walker": "street", "Mara": "hall"},
                                             "entities": {}})
    for uid, aid in (("loft", "gable_window"), ("hall", "stair_foot")):
        anchor = sc["rooms"][uid]["anchors"][aid]
        assert "cell" not in anchor and "extent" not in anchor, (uid, anchor)
        assert anchor_cells(sc, uid)[aid]["source"] != "cell", (uid, aid)


def test_several_alike_the_plan_named_are_written_first_under_its_own_id(temp_db):
    """The plan named "three box beds along the wall" under one id; the
    solver lays three. The first is written under the plan's id, so the plan
    holds three beds and no fourth record standing beside its copies (the
    live inn: four box-bed anchors for three beds) -- and the plan's words
    for the GROUP go to the solve's record, never onto one copy: every copy
    carries the first call's name for one of them, on the plan and on the
    stub the commit minted with the group's words before the solve (review of
    2026-10-08, R2-6: a mind saw three box beds in one place and two more
    beside them)."""
    from world.structure import (_planned_specs, apply_planned_layout,
                                 materialize_planned_fringe, plant_structure,
                                 write_planned_layout)
    group = "three box beds along the wall"
    beds = copy.deepcopy(SPECS)
    beds["loft"][1]["anchors"]["bed_boxes"] = {"desc": group}
    sort = copy.deepcopy(SORT)
    sort["rooms"][2]["fixtures"] = [{"id": "bed_boxes", "name": "a box bed",
                                     "mount": "floor", "count": 3}]
    relate = copy.deepcopy(RELATE)
    relate["rooms"][2]["fixtures"] = [{"id": "bed_boxes", "kind": "bed", "at": "walls"}]
    b, inv, spec, layout = _solve(specs=beds, sort=sort, relate=relate)
    solved, report = lb.planned_layout(b, spec, layout, inventory=inv)
    ids = {aid for aid in solved["loft"]["anchors"] if aid.startswith("bed_boxes")}
    assert ids == {"bed_boxes", "bed_boxes_2", "bed_boxes_3"}, ids
    assert {solved["loft"]["anchors"][aid]["desc"] for aid in ids} == {"a box bed"}
    (split,) = report["split"]
    assert (split["room"], split["anchor"], split["desc"]) == ("loft", "bed_boxes", group)
    assert sorted(split["copies"]) == sorted(ids)
    assert solved["loft"]["layout"]["split"] == [
        {"anchor": "bed_boxes", "desc": group, "copies": split["copies"]}]
    # the commit minted the loft's stub from the plan before the solve...
    cid = _chat(temp_db)
    rooms = {uid: dict(sp, name=name) for uid, (name, sp) in copy.deepcopy(beds).items()}
    for room in rooms.values():
        room.pop("structure", None)
    plant_structure(cid, {"key": "town", "name": "Town"}, rooms)
    street = {"name": "the Street", "desc": "A street.",
              "adjacent": [{"to": "hall", "dir": "n", "barrier": "open_door"}]}
    sc, _ = materialize_planned_fringe(cid, {"rooms": {"street": street},
                                             "positions": {"Walker": "street", "Mara": "hall"},
                                             "entities": {}})
    assert sc["rooms"]["loft"]["anchors"]["bed_boxes"]["desc"] == group
    # ...the plan takes the solve, the group's words kept in its record...
    assert write_planned_layout(cid, solved, expected={uid: _planned_specs(cid)[uid][1]
                                                      for uid in b["rooms"]})
    plan = _registry(cid)["loft"]
    assert {plan["anchors"][aid]["desc"] for aid in ids} == {"a box bed"}
    assert plan["layout"]["split"][0]["desc"] == group
    # ...and the stub is laid on it: three box beds, none of them the group
    apply_planned_layout(sc, _planned_specs(cid))
    stub = sc["rooms"]["loft"]["anchors"]
    assert sorted(a["desc"] for aid, a in stub.items() if aid.startswith("bed_boxes")) == \
        ["a box bed"] * 3
    assert not any(a.get("desc") == group for a in stub.values())


def test_several_windows_the_plan_named_under_one_record_are_one_each():
    """The same class for windows: the solver names several alike
    `<id>_1`, `<id>_2`, and each copy was handed the plan's words for the
    group while the plan's own record stood beside them -- three windows,
    each "two gable windows". Now the first is written under the plan's id,
    each is named as one of them, and the group's words go to the solve's
    record."""
    specs = copy.deepcopy(SPECS)
    specs["loft"][1]["anchors"] = {"gable_windows": {"desc": "two gable windows over the water"}}
    sort = copy.deepcopy(SORT)
    sort["rooms"][2]["windows"] = [{"id": "gable_windows", "name": "a gable window",
                                    "faces": "the water", "count": 2}]
    relate = copy.deepcopy(RELATE)
    relate["rooms"][2]["windows"] = [{"id": "gable_windows", "side": "n", "count": 2}]
    b, inv, spec, layout = _solve(specs=specs, sort=sort, relate=relate)
    solved, report = lb.planned_layout(b, spec, layout, inventory=inv)
    loft = solved["loft"]["anchors"]
    ids = {aid for aid in loft if aid.startswith("gable_windows")}
    assert ids == {"gable_windows", "gable_windows_2"}, ids
    assert {loft[aid]["desc"] for aid in ids} == {"a gable window"}
    assert all(loft[aid]["opacity"] == "see_through" for aid in ids)
    assert [(s["room"], s["anchor"], s["desc"]) for s in report["split"]] == [
        ("loft", "gable_windows", "two gable windows over the water")]


def test_a_fixture_that_marks_where_a_way_meets_the_room_is_pinned_there():
    """A fixture the plan lists that is no thing in the room but the place
    where a stair or a doorway meets it -- given with `marks` -- is pinned
    where that way meets the room, blocking no line (the live inn: the foot
    of the stair pinned four paces from the stair)."""
    marked = copy.deepcopy(SPECS)
    marked["hall"][1]["anchors"]["stair_foot"] = {"desc": "the foot of the stair"}
    marked["hall"][1]["anchors"]["kitchen_door"] = {"desc": "the door through to the kitchen"}
    sort = copy.deepcopy(SORT)
    sort["rooms"][0]["fixtures"] += [
        {"id": "stair_foot", "name": "the foot of the stair", "marks": "loft"},
        {"id": "kitchen_door", "name": "the kitchen door", "marks": "kitchen"},
        {"id": "nowhere", "name": "a mark on no way", "marks": "attic"}]
    b, inv, spec, layout = _solve(specs=marked, sort=sort)
    held = {r["id"]: r for r in inv["rooms"]}["hall"]
    assert {m["id"] for m in held["marks"]} == {"stair_foot", "kitchen_door"}
    assert "stair_foot" not in {f["id"] for f in {r["id"]: r for r in spec["rooms"]}["hall"]["fixtures"]}
    assert "nowhere" in {f["id"] for f in held["fixtures"]}, "no such way: an ordinary fixture"
    assert lb.refusals(b, spec, layout) == []
    solved, report = lb.planned_layout(b, spec, layout, inventory=inv)
    foot = solved["hall"]["anchors"]["stair_foot"]
    assert foot["cell"] == solved["hall"]["edges"]["loft"]["cell"]
    assert foot["opacity"] == "see_through" and foot["footprint"] == "point"
    door = solved["hall"]["anchors"]["kitchen_door"]
    edge = solved["hall"]["edges"]["kitchen"]
    assert door["dir"] == edge["dir"]
    # the doorway's own cell, by the engine's reading of the edge
    from world.spatial import _door_cells
    room = {"name": "hall", "desc": "hall", **solved["hall"]["geometry"],
            "adjacent": [{"to": "kitchen", "barrier": "open_door", **edge}]}
    sc = {"rooms": {"hall": room, "kitchen": {"name": "k", "desc": "k",
                                               "extent": solved["kitchen"]["geometry"]["extent"],
                                               "adjacent": [{"to": "hall", "barrier": "open_door",
                                                             **solved["kitchen"]["edges"]["hall"]}]}},
          "positions": {}, "entities": {}}
    (cell,), _bearing = _door_cells(sc, "hall", "kitchen")
    assert tuple(door["cell"]) == tuple(cell)
    assert {m["anchor"] for m in report["marks"]} == {"stair_foot", "kitchen_door"}


OPEN_WALKS = {
    "low_walk": ("the Low Walk", {
        "purpose": "a plank walk over the mud", "structure": "town", "exposure": "open",
        "adjacent": [{"to": "high_walk", "vertical": "up", "way": "stair"},
                     {"to": "quay", "dir": "s"}]}),
    "high_walk": ("the High Walk", {
        "purpose": "a raised walk between the houses", "structure": "town", "exposure": "open",
        "adjacent": [{"to": "low_walk", "vertical": "down", "way": "stair"},
                     {"to": "gale_house", "dir": "e"}]}),
    "quay": ("the Quay", {"purpose": "a quay", "structure": "town", "exposure": "open",
                          "adjacent": [{"to": "low_walk", "dir": "n"}]}),
    "gale_house": ("the Gale House", {
        "purpose": "a pile house", "structure": "town", "exposure": "enclosed",
        "adjacent": [{"to": "high_walk", "dir": "w"}]}),
}


def test_open_ground_up_a_flight_of_steps_is_no_building():
    """A room stated open or sheltered has no walls round it and is never a
    storey: a plank walk up a flight of steps to another walk is ground on
    two heights, not a house (the review's pile-town case, the brief's own
    Gale house)."""
    scene = {"rooms": {"quay": {"name": "the Quay", "desc": "A quay.",
                                "adjacent": [{"to": "low_walk", "dir": "n"}]}},
             "positions": {}, "entities": {}}
    assert lb.plan_buildings(copy.deepcopy(OPEN_WALKS), scene) == []
    sheltered = copy.deepcopy(OPEN_WALKS)
    sheltered["high_walk"][1]["exposure"] = "sheltered"
    assert lb.plan_buildings(sheltered, scene) == []


def test_a_stair_from_a_storey_down_to_open_ground_is_a_way_out_of_the_building():
    """A stair from a storey to a room with no walls round it is an outside
    stair: the open room is ground the building opens onto, laid as an
    outside door of the storey it leaves from, never a storey of it."""
    specs = copy.deepcopy(SPECS)
    specs["loft"][1]["adjacent"].append({"to": "yard_steps", "vertical": "down", "way": "stair"})
    specs["yard_steps"] = ("the Yard Steps", {
        "purpose": "steps down the gable to the yard", "structure": "town", "exposure": "open",
        "adjacent": [{"to": "loft", "vertical": "up", "way": "stair"}]})
    b = _building(specs=specs)
    assert b["refusal"] is None and b["rooms"] == ["hall", "kitchen", "loft"]
    way_out = [o for o in b["outside"] if o["to"] == "yard_steps"]
    assert way_out and way_out[0]["room"] == "loft" and way_out[0]["vertical"] == "down"
    assert b["entrance"]["room"] == "hall", "the entrance is a door at the foot, not a stair"
    inv = lb.hold_inventory(b, SORT)
    spec = lb.spec_from_answers(b, inv, RELATE)
    loft = {r["id"]: r for r in spec["rooms"]}["loft"]
    assert "yard_steps" in {j["to"] for j in loft["joins"]}


def test_a_plan_written_while_a_commit_prepares_is_never_written_back_over(temp_db):
    """The commit's registry projection is prepared before the write lock and
    applied inside it; the layout tier writes the plan out of band, at any
    moment between the two. What the projection owns -- whether a planned
    room is described yet, and its region -- is applied onto the row as it
    stands inside the lock; it never writes back the whole payload it read
    before (review of 2026-10-08, F5: the kitchen and the loft lost their
    site to a commit that had prepared before the solve, and the building
    was refused for good)."""
    from core.db import transaction, wset
    from persist.commit import _apply_room_registry, _prepare_room_registry
    from world.structure import materialize_planned_fringe, write_planned_layout
    cid = _chat(temp_db)
    book = temp_db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("canon", cid))
    turns = [r["id"] for r in temp_db.q("SELECT id FROM turns WHERE chat_id=? ORDER BY idx", (cid,))]
    _plant(cid)
    street = {"name": "the Street", "desc": "A street.",
              "adjacent": [{"to": "hall", "dir": "n", "barrier": "open_door"}]}
    sc_n, _ = materialize_planned_fringe(cid, {"rooms": {"street": street},
                                               "positions": {"Walker": "street"}, "entities": {}})
    with transaction():
        wset(cid, "scene", sc_n)
        _apply_room_registry(cid, turns[1], _prepare_room_registry(cid, book, {}, sc_n))
    # commit N+1 prepares: the walker in the hall, the fringe mints the rest
    moved = copy.deepcopy(sc_n)
    moved["positions"]["Walker"] = "hall"
    sc_n1, _ = materialize_planned_fringe(cid, moved)
    prepared = _prepare_room_registry(cid, book, sc_n, sc_n1)
    assert {"kitchen", "loft"} <= {u["room_uid"] for u in prepared["upserts"]}
    # ...the tier writes the plan meanwhile...
    from world.structure import _planned_specs
    b = _building(specs=_planned_specs(cid), scene=sc_n)
    inv = lb.hold_inventory(b, SORT)
    spec = lb.spec_from_answers(b, inv, RELATE)
    layout = lb.solve_spec(spec)
    assert lb.refusals(b, spec, layout) == []
    solved, _report = lb.planned_layout(b, spec, layout, inventory=inv)
    assert write_planned_layout(cid, solved, expected=b["specs"])
    # ...and the commit applies what it prepared, inside the lock
    with transaction():
        wset(cid, "scene", sc_n1)
        _apply_room_registry(cid, turns[2], prepared)
    plan = _registry(cid)
    for uid in ("hall", "kitchen", "loft"):
        assert plan[uid].get("site", {}).get("plan") == "layout:hall", uid
    assert plan["kitchen"]["resolved"] is False, "the projection's own field still lands"


def _frontier_on_the_hall(temp_db):
    """The plan with a frontier axis on the hall, and the walker standing in
    the hall's undescribed stub -- the holder a frontier expansion rewrites."""
    from world.structure import materialize_planned_fringe, plant_structure
    cid = _chat(temp_db)
    turns = [r["id"] for r in temp_db.q("SELECT id FROM turns WHERE chat_id=? ORDER BY idx", (cid,))]
    rooms = {uid: dict(spec, name=name) for uid, (name, spec) in copy.deepcopy(SPECS).items()}
    for room in rooms.values():
        room.pop("structure", None)
    rooms["hall"]["frontier"] = ["a lane going east"]
    plant_structure(cid, {"key": "town", "name": "Town"}, rooms)
    street = {"name": "the Street", "desc": "A street.",
              "adjacent": [{"to": "hall", "dir": "n", "barrier": "open_door"}]}
    sc, _ = materialize_planned_fringe(cid, {"rooms": {"street": street},
                                             "positions": {"Walker": "street"}, "entities": {}})
    sc["positions"]["Walker"] = "hall"
    return cid, turns, sc


def test_a_plan_written_while_a_frontier_expansion_prepares_is_never_written_back_over(temp_db):
    """The frontier expansion prepares the holder's row before the write lock
    and writes it inside; the layout tier writes the plan out of band, at any
    moment between the two. Only what the expansion owns -- the edge it drew,
    the axis it spent, what now stands in it -- is laid onto the holder's row
    as it stands inside the lock (review of 2026-10-08, R2-4: the hall lost
    its solved site while the kitchen and the loft kept theirs, and the
    building was refused for good)."""
    from agents.director_layout import LAYOUT_TIER_SETTING, lay_out_buildings
    from core.db import set_setting, transaction
    from world.structure import apply_frontier_mutations, prepare_frontier_expansion
    cid, turns, sc = _frontier_on_the_hall(temp_db)
    set_setting(LAYOUT_TIER_SETTING, "on")
    # the commit prepares its expansion before the lock...
    _sc, mutations = prepare_frontier_expansion(cid, copy.deepcopy(sc))
    minted = next(m["room_uid"] for m in mutations if m["room_uid"] != "hall")
    # ...the tier lays the building out meanwhile...
    _scene, laid = lay_out_buildings(None, cid, copy.deepcopy(sc), ["hall"], "en",
                                     call=_answers([]))
    assert laid == {"hall", "kitchen", "loft"}
    solved = _registry(cid)
    # ...and the commit writes what it prepared, inside the lock
    with transaction():
        apply_frontier_mutations(cid, turns[2], mutations)
    plan = _registry(cid)
    for uid in ("hall", "kitchen", "loft"):
        assert plan[uid].get("site") == solved[uid]["site"], uid
    hall = plan["hall"]
    assert hall["anchors"] == solved["hall"]["anchors"]
    assert hall["frontier"] == [] and hall["frontier_standing"] == {"a lane going east": minted}
    assert [e["to"] for e in hall["adjacent"]] == \
        [e["to"] for e in solved["hall"]["adjacent"]] + [minted]
    assert plan[minted]["frontier_of"]["room"] == "hall"


def test_a_frontier_expansion_nobody_raced_writes_exactly_what_it_prepared(temp_db):
    """On a row nobody wrote between the expansion's preparation and its
    write, laying what the expansion owns onto the row as it stands is the
    payload the expansion prepared, byte for byte."""
    from core.db import transaction
    from world.structure import apply_frontier_mutations, prepare_frontier_expansion
    cid, turns, sc = _frontier_on_the_hall(temp_db)
    _sc, mutations = prepare_frontier_expansion(cid, copy.deepcopy(sc))
    prepared = next(m["payload"] for m in mutations if m["room_uid"] == "hall")
    with transaction():
        apply_frontier_mutations(cid, turns[2], mutations)
    row = temp_db.q("SELECT payload FROM room_registry WHERE chat_id=? AND room_uid='hall'",
                    (cid,), one=True)
    assert json.loads(row["payload"]) == json.loads(json.dumps(prepared))


def test_a_building_re_planned_after_its_solve_gives_the_solve_back_and_may_be_laid_out_again(temp_db):
    """A re-plan replaces a planned row whole, so the solve is gone from the
    plan while the stubs still stand on it. The stub gives back what the
    solve put there -- its site, any rectangle the plan no longer states, its
    fixtures' placed pins, its doorways' places -- and takes the new plan's
    measurements, so the building is a stub on no plan again and may be laid
    out afresh where nothing else stands on its plan, as here, where the
    street was never placed (review of 2026-10-08, F6: the stub kept its old
    site under the new twelve by three, and the building was refused for
    good). Where the street does stand on the old plan, the next tests."""
    from agents.director_layout import LAYOUT_TIER_SETTING, lay_out_buildings
    from core.db import set_setting
    from world.structure import (_planned_specs, apply_solved_plans,
                                 materialize_planned_fringe, plant_structure,
                                 provisional_room_ids)
    cid = _chat(temp_db)
    _plant(cid)
    set_setting(LAYOUT_TIER_SETTING, "on")
    street = {"name": "the Street", "desc": "A street.",
              "adjacent": [{"to": "hall", "dir": "n", "barrier": "open_door"}]}
    sc, _ = materialize_planned_fringe(cid, {"rooms": {"street": street},
                                             "positions": {"Walker": "street"}, "entities": {}})
    lay_out_buildings(None, cid, copy.deepcopy(sc), ["hall"], "en", call=_answers([]))
    sc, _ = materialize_planned_fringe(cid, sc)
    hall = sc["rooms"]["hall"]
    assert hall["site"]["plan"] == "layout:hall"
    assert any("cell" in a and "extent" in a for a in hall["anchors"].values())
    # the Room re-plans the building: the hall is a long hall now
    rooms = {uid: dict(spec, name=name) for uid, (name, spec) in copy.deepcopy(SPECS).items()}
    for room in rooms.values():
        room.pop("structure", None)
    rooms["hall"]["extent"] = {"w": 12, "d": 3}
    plant_structure(cid, {"key": "town", "name": "Town"}, rooms)
    assert _registry(cid)["hall"].get("site") is None
    # every reader of the next beat already reads it as the plan has it...
    read = apply_solved_plans(cid, copy.deepcopy(sc))
    assert "hall" in read
    # ...and the next commit's fringe stores it so
    sc, _ = materialize_planned_fringe(cid, sc)
    hall = sc["rooms"]["hall"]
    assert "site" not in hall and hall["extent"] == {"w": 12, "d": 3}
    assert "laid_out" not in hall, "the record of the solve goes with it"
    assert not any("extent" in a for a in (hall.get("anchors") or {}).values())
    assert not any("offset" in e or "cell" in e for e in hall["adjacent"])
    (b,) = lb.plan_buildings(_planned_specs(cid), sc, held_open=provisional_room_ids(cid))
    assert b["refusal"] is None, b["refusal"]


def _commit_like(cid, prev, diff=None):
    """One commit's scene work, in its order: the merge base read through the
    plan (`compose_beat_scene`), the beat's diff merged onto it -- the merge
    ends in the engine's site derivation -- then the fringe pass."""
    from world.spatial import merge_scene_with_diff
    from world.structure import apply_solved_plans, materialize_planned_fringe
    base = copy.deepcopy(prev)
    apply_solved_plans(cid, base)
    merged = merge_scene_with_diff(base, copy.deepcopy(diff or {}))
    stored, _ = materialize_planned_fringe(cid, merged)
    return stored


def _laid_out_and_walked(temp_db):
    """The building laid out from the street, then a walker into the hall and
    on into the kitchen, a commit at each step, and one more while the walker
    stays: the fringe mints the yard in the kitchen's commit, after that
    commit's merge, so the derivation places it in the next one."""
    from agents.director_layout import LAYOUT_TIER_SETTING, lay_out_buildings
    from core.db import set_setting
    from world.structure import materialize_planned_fringe
    cid = _chat(temp_db)
    _plant(cid)
    set_setting(LAYOUT_TIER_SETTING, "on")
    street = {"name": "the Street", "desc": "A street.",
              "adjacent": [{"to": "hall", "dir": "n", "barrier": "open_door"}]}
    sc, _ = materialize_planned_fringe(cid, {"rooms": {"street": street},
                                             "positions": {"Walker": "street"}, "entities": {}})
    lay_out_buildings(None, cid, copy.deepcopy(sc), ["hall"], "en", call=_answers([]))
    for room in ("hall", "kitchen", "kitchen"):
        sc["positions"]["Walker"] = room
        sc = _commit_like(cid, sc)
    return cid, sc


def test_a_neighbour_the_engine_placed_beside_a_solved_building_keeps_what_it_holds(temp_db):
    """ONLY WHAT A SOLVE LAID IS TAKEN BACK. The engine's derivation places a
    planned yard behind the solved kitchen on the building's own plan; the
    yard was never solved, so it keeps standing on that plan commit after
    commit, and a beat that measures it and places its gate -- without
    describing it -- keeps both (review of 2026-10-08, R2-1: read off the
    plan's name, the re-plan rule took all three off the yard every commit).

    WHERE IT STANDS FOLLOWS WHAT IT IS (2026-10-09). The yard's site is the
    derivation's reading of its doorways (`site_plan.DERIVED_KEY`), so once
    the beat has measured it and moved its gate, the next merge lays it out
    again where that gate now meets the kitchen's door -- never left at the
    corner its unmeasured square was given."""
    from world.site_plan import plan_offset, site_is_derived, site_overlaps
    from world.structure import apply_solved_plans
    cid, sc = _laid_out_and_walked(temp_db)
    yard = sc["rooms"]["yard"]
    assert not yard.get("desc") and yard.get("planned")
    assert yard["site"]["plan"] == "layout:hall", yard.get("site")
    assert site_is_derived(yard["site"]) and "laid_out" not in yard
    assert sc["rooms"]["kitchen"]["laid_out"]["plan"] == "layout:hall"
    placed = yard["site"]
    sc = _commit_like(cid, sc)
    assert sc["rooms"]["yard"]["site"] == placed, "and the next commit keeps it"
    gate = {"rooms": {"yard": {"extent": {"w": 3, "d": 3},
                               "adjacent": [{"to": "kitchen", "offset": 0.5}]}}}
    moved = None
    for diff in (gate, None):
        sc = _commit_like(cid, sc, diff)
        yard = sc["rooms"]["yard"]
        assert yard["extent"] == {"w": 3, "d": 3}
        assert next(e for e in yard["adjacent"] if e["to"] == "kitchen")["offset"] == 0.5
        assert yard["site"]["plan"] == "layout:hall" and site_is_derived(yard["site"])
        assert plan_offset(sc, "kitchen", "yard") is not None, "its gate meets the kitchen"
        assert site_overlaps(sc) == []
        moved = moved or yard["site"]
        assert yard["site"] == moved, "and stands there commit after commit"
    assert moved != placed, "laid out again where its measured gate puts it"
    read = copy.deepcopy(sc)
    apply_solved_plans(cid, read)
    assert read["rooms"]["yard"] == sc["rooms"]["yard"], "nor does any reader of a beat"


def test_a_re_plan_takes_back_only_the_doorways_the_solve_placed():
    """The stub's record lists the doorways and stairs the solve placed, and
    a re-plan takes back exactly those -- taking the new plan's measurements
    where it states them. A doorway the solve never placed keeps whatever a
    beat or a host gave it."""
    from world.structure import LAID_OUT_KEY, apply_planned_layout
    site = {"plan": "layout:hall", "x": 0, "y": 2, "elev_m": 0.0}
    hall = {"name": "the Hall", "planned": True, "site": dict(site),
            "extent": {"w": 6, "d": 5}, "shape": "rectangle", "level": 0,
            LAID_OUT_KEY: {"plan": "layout:hall", "edges": ["kitchen", "loft"]},
            "anchors": {"hearth": {"desc": "a stone hearth", "cell": [0, 0],
                                   "extent": {"w": 1, "d": 2}, "dir": "w"}},
            "adjacent": [{"to": "kitchen", "dir": "e", "offset": 0.5},
                         {"to": "loft", "vertical": "up", "cell": [2, 0]},
                         {"to": "garden", "dir": "n", "offset": 0.25}]}
    replanned = {"purpose": "a hall", "extent": {"w": 12, "d": 3},
                 "adjacent": [{"to": "kitchen", "dir": "e", "offset": 0.75},
                              {"to": "loft", "vertical": "up"}],
                 "anchors": {"hearth": {"desc": "a stone hearth"}}}
    scene = {"rooms": {"hall": hall}}
    assert apply_planned_layout(scene, {"hall": ("the Hall", replanned)}) == ["hall"]
    edges = {e["to"]: e for e in hall["adjacent"]}
    assert edges["kitchen"]["offset"] == 0.75, "the new plan's own measurement"
    assert "cell" not in edges["loft"]
    assert edges["garden"]["offset"] == 0.25, "never the solve's: kept"
    assert "site" not in hall and LAID_OUT_KEY not in hall
    assert hall["extent"] == {"w": 12, "d": 3} and "level" not in hall
    assert hall["anchors"]["hearth"] == {"desc": "a stone hearth", "dir": "w"}


def test_a_re_planned_building_is_laid_out_again_and_its_ground_with_it(temp_db):
    """A solve is written only onto a plan nothing else stands on, and the
    ground the derivation laid beside an old solve is not something: once the
    Room re-plans the building, its stubs give the solve back, and the street
    the engine placed beside it is read again from the rooms
    (`structure.apply_solved_plans` recomputes the derived plan wherever it
    lays or takes back a solve; `site_plan.DERIVED_KEY`). Until 2026-10-09
    the street kept the OLD solve's coordinates, the tier read it as a room
    standing on the plan, and the re-planned building was left to the
    designer for good. Now it is laid out again, and the commit that follows
    stores the new solve with the street beside it, its door meeting the
    hall's. A re-plan the answers cannot solve is attempted too, and waits as
    every refused solve does (the test below)."""
    from agents.director_layout import lay_out_buildings
    from world.site_plan import plan_offset, site_is_derived, site_overlaps
    from world.structure import (_planned_specs, apply_solved_plans, plant_structure,
                                 provisional_room_ids)
    cid, sc = _laid_out_and_walked(temp_db)
    assert sc["rooms"]["street"]["site"]["plan"] == "layout:hall"
    assert site_is_derived(sc["rooms"]["street"]["site"])
    rooms = {uid: dict(spec, name=name) for uid, (name, spec) in copy.deepcopy(SPECS).items()}
    for room in rooms.values():
        room.pop("structure", None)
    rooms["hall"]["purpose"] = "a hall with a hearth, a long table and a settle"
    plant_structure(cid, {"key": "town", "name": "Town"}, rooms)
    # the job between turns reads the scene through the plan, as it does
    job_copy = copy.deepcopy(sc)
    apply_solved_plans(cid, job_copy)
    for uid in ("hall", "kitchen", "loft"):
        room = job_copy["rooms"][uid]
        assert "laid_out" not in room, uid
        assert (room.get("site") or {}).get("plan") != "layout:hall", uid
        assert not any("extent" in a for a in (room.get("anchors") or {}).values()), uid
    assert (job_copy["rooms"]["street"].get("site") or {}).get("plan") != "layout:hall", \
        "the ground beside the old solve is read again from the rooms"
    (b,) = lb.plan_buildings(_planned_specs(cid), job_copy,
                             held_open=provisional_room_ids(cid))
    assert b["refusal"] is None, b["refusal"]
    calls = []
    _scene, laid = lay_out_buildings(None, cid, job_copy, ["hall"], "en", call=_answers(calls))
    assert calls and laid == {"hall", "kitchen", "loft"}, (calls, laid)
    # and the commit that follows stores the new solve, the street beside it
    sc = _commit_like(cid, sc)
    for uid in ("hall", "kitchen", "loft"):
        assert sc["rooms"][uid]["laid_out"]["plan"] == "layout:hall", uid
    street = sc["rooms"]["street"]
    assert street["site"]["plan"] == "layout:hall" and site_is_derived(street["site"])
    assert plan_offset(sc, "hall", "street") is not None, "the street's door meets the hall's"
    assert site_overlaps(sc) == []



def test_a_re_plan_the_answers_cannot_solve_costs_one_attempt_then_waits(temp_db, monkeypatch):
    """A re-planned building the derivation no longer keeps out (above) is
    attempted even where the answers cannot solve it -- here the bridge's
    refusal is forced, every seed refused, since what is under test is what
    the tier does with a refusal and not which plans earn one -- and the
    bridge refuses the solve after its three calls -- where, until
    2026-10-09, the street's stale site refused it before any call. The
    refusal is filed, the building waits as every refused solve waits
    (`director_rooms.predevelop_retry_beats`: 2 beats, then 4, 8 and every
    16 while it keeps failing on the same plan), and no stub keeps anything
    the old solve laid: the designer builds the rooms as it always has."""
    import types
    from agents.director_layout import LAYOUT_RUNS_KEY, lay_out_buildings
    from agents.director_rooms import predevelop_retry_beats
    from core.db import wget
    from world.structure import (_planned_specs, apply_solved_plans, plant_structure,
                                 provisional_room_ids)
    cid, sc = _laid_out_and_walked(temp_db)
    rooms = {uid: dict(spec, name=name) for uid, (name, spec) in copy.deepcopy(SPECS).items()}
    for room in rooms.values():
        room.pop("structure", None)
    plant_structure(cid, {"key": "town", "name": "Town"}, rooms)
    monkeypatch.setattr(lb, "refusals", lambda building, spec, layout: ["a refusal the test forces"])
    job_copy = copy.deepcopy(sc)
    apply_solved_plans(cid, job_copy)
    (b,) = lb.plan_buildings(_planned_specs(cid), job_copy,
                             held_open=provisional_room_ids(cid))
    assert b["refusal"] is None, b["refusal"]
    calls = []
    job = types.SimpleNamespace(base_turn=1)
    _scene, laid = lay_out_buildings(job, cid, job_copy, ["hall"], "en", call=_answers(calls))
    assert len(calls) == 3 and laid == set(), (calls, laid)
    run = wget(cid, LAYOUT_RUNS_KEY)[b["key"]]
    assert run["failed"] == 1 and run["reasons"], run
    # within the wait, no call at all
    for turn in range(1, 1 + predevelop_retry_beats(1)):
        lay_out_buildings(types.SimpleNamespace(base_turn=turn), cid, copy.deepcopy(job_copy),
                          ["hall"], "en", call=_answers(calls))
    assert len(calls) == 3, calls
    # once the wait is over it is tried again -- three calls -- and fails again,
    # and the next wait is twice as long: the cost of a building nobody can
    # solve, the same for every building the tier attempts
    lay_out_buildings(types.SimpleNamespace(base_turn=1 + predevelop_retry_beats(1)), cid,
                      copy.deepcopy(job_copy), ["hall"], "en", call=_answers(calls))
    assert len(calls) == 6, calls
    assert wget(cid, LAYOUT_RUNS_KEY)[b["key"]]["failed"] == 2
    # and the commit that follows stores no stub with the old solve on it
    sc = _commit_like(cid, sc)
    for uid in ("hall", "kitchen", "loft"):
        room = sc["rooms"][uid]
        assert "laid_out" not in room, uid
        assert not any("extent" in a for a in (room.get("anchors") or {}).values()), uid
    # the stub is the re-plan's: the old solve's measurement went with it,
    # and the only site it has is the one the engine derives every merge
    hall = sc["rooms"]["hall"]
    assert "extent" not in hall, hall["extent"]
    assert (hall.get("site") or {}).get("plan") != "layout:hall", hall["site"]


def test_the_tier_can_be_turned_on_for_one_story_and_a_rewind_keeps_the_dial(temp_db):
    """The owner compares the tier in a story before it publishes to any: the
    story's own switch is read before the host's, on in one chat while every
    other stays off, or off in one while the host has it on -- and it is a
    dial the author set, so a reroll's restore does not turn it back (review
    of 2026-10-08, F8: one global switch could not be turned on "for a
    story")."""
    from agents.director_layout import (LAYOUT_TIER_SETTING, LAYOUT_TIER_STORY_KEY,
                                        lay_out_buildings, layout_tier_enabled)
    from core.db import set_setting, wset
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    one, other = _chat(temp_db), _chat(temp_db)
    # the host turned it off, so a story's own switch is what turns it on
    set_setting(LAYOUT_TIER_SETTING, "off")
    assert not layout_tier_enabled(one) and not layout_tier_enabled(other)
    # a checkpoint of the story as it stood before the dial was turned...
    _plant(one)
    wset(one, "scene", _scene())
    ensure_checkpoint(one, 1)
    wset(one, LAYOUT_TIER_STORY_KEY, "on")
    assert layout_tier_enabled(one) and not layout_tier_enabled(other)
    # ...the tier lays a building out in that story...
    _scene_back, laid = lay_out_buildings(None, one, _scene(), ["hall"], "en", call=_answers([]))
    assert laid == {"hall", "kitchen", "loft"}
    # ...and a reroll restores the checkpoint: the plan it solved rolls back
    # with the story, and the dial stays where the author turned it
    restore_checkpoint(one, 1)
    assert not any((p or {}).get("site") for p in _registry(one).values())
    assert temp_db.wget(one, LAYOUT_TIER_STORY_KEY) == "on"
    assert layout_tier_enabled(one)
    set_setting(LAYOUT_TIER_SETTING, "on")
    wset(other, LAYOUT_TIER_STORY_KEY, "off")
    assert layout_tier_enabled(one) and not layout_tier_enabled(other)
    third = _chat(temp_db)
    assert layout_tier_enabled(third), "the host's switch where a story states none"



def test_the_building_the_opening_stands_in_is_laid_out_before_anything_is_described(temp_db):
    """A story that OPENS inside a planned building had it refused forever:
    the tier ran only in the job after a beat, the opening had described the
    room the player woke in by then, and the tier never re-measures a room
    the story has seen -- the owner's shrine (chat 164, 2026-10-10) was built
    with no solve at all. The opening plan lays out the building its bodies
    stand in before turn 0 describes any of it."""
    from agents.director_layout import lay_out_opening_ground
    from core.db import wset
    from story.opening_plan import record_placement
    from agents.director_layout import LAYOUT_TIER_SETTING
    from core.db import set_setting
    cid = _chat(temp_db)
    _plant(cid)
    set_setting(LAYOUT_TIER_SETTING, "on")
    wset(cid, "scene", _scene())
    record_placement(cid, None, "Nia", "hall")
    calls = []
    laid = lay_out_opening_ground(cid, None, call=_answers(calls))
    assert laid == {"hall", "kitchen", "loft"}
    assert calls, "the three calls were made"
    assert all((p or {}).get("site") for uid, p in _registry(cid).items()
               if uid in laid), "the plan holds the solve the opening reads"


def test_an_opening_placed_nowhere_lays_nothing_out_and_never_raises(temp_db):
    from agents.director_layout import lay_out_opening_ground
    cid = _chat(temp_db)
    _plant(cid)
    assert lay_out_opening_ground(cid, None, call=_answers([])) == set()


def test_the_opening_plan_lays_out_its_ground_after_the_room_has_placed_it():
    import inspect
    from agents import story_planner
    source = inspect.getsource(story_planner.run_opening_plan)
    assert "lay_out_opening_ground(" in source
    assert source.index("run_planner(") < source.index("lay_out_opening_ground(")
    assert source.index("lay_out_opening_ground(") < source.index("record_opening_plan(cid")


def _book(temp_db, cid, entries):
    book = temp_db.qi("INSERT INTO lorebooks(name) VALUES(?)", ("Town lore",))
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book, cid))
    for keys, content in entries:
        temp_db.qi("INSERT INTO lore_entries(lorebook_id,keys,content) VALUES(?,?,?)",
                   (book, keys, content))
    return book


def test_the_tier_reads_what_the_storys_lore_says_of_the_building(temp_db):
    """The plan holds a room's one-line purpose; the lore holds what the room
    IS, and a solver sizes a room by what it holds. The owner's shrine (chat
    164) was replicated with nothing described and laid out from the plan
    alone: every room came back a third of its planned size. The tier's
    calls now read every entry whose OWN keys name the building or one of its
    rooms -- the building's own first -- and nothing the keys do not name."""
    from agents.director_layout import building_description
    cid = _chat(temp_db)
    _book(temp_db, cid, [
        ("the realm beyond,the dimensional seal", "Past the seal lies another world."),
        ("kitchen,hearth", "The kitchen keeps a deep stone hearth on its north wall."),
        ("town,market town", "The town is an old market town on a ford."),
        ("loft", "The loft holds two straw beds under the eaves."),
    ])
    (building,) = lb.plan_buildings(copy.deepcopy(SPECS), _scene())
    building = dict(building, structure="town")
    text = building_description(cid, building)
    assert text.startswith("The town is an old market town"), "the building's own entry first"
    assert "stone hearth" in text and "straw beds" in text
    assert "another world" not in text
    assert lb.sort_payload(dict(building, description=text))["building"]["description"] == text
    assert "description" not in lb.sort_payload(building)["building"]


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_the_relate_card_asks_for_a_size_only_where_the_lore_states_one(lang):
    from llm.prompts import layout_prompt
    card = layout_prompt("relate", lang)
    assert '"area_m2"' in card and "`area_m2`" in card


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_both_layout_cards_say_what_the_description_is(lang):
    from llm.prompts import layout_prompt
    assert "`description`" in layout_prompt("sort", lang)
    assert "`description`" in layout_prompt("relate", lang)


def test_a_room_of_another_shape_off_one_doorway_stands_in_a_block_of_its_own():
    """The owner's shrine (chat 164) planned its Seal Cavern `composite`, off
    the basement's north wall through one warded door, and the whole building
    was refused for it. The layout lab's liked shrine stood the cavern in a
    block of its own beside the main block -- a hand edit the engine now
    makes: the building stands, the block sits on the side the plan states,
    and the solve says where the room stands and how large; its shape stays
    the plan's, never squared."""
    specs = copy.deepcopy(SPECS)
    specs["store"] = ("the Store", {"shape": "composite", "extent": {"w": 9, "d": 6},
                                    "exposure": "enclosed",
                                    "structure": specs["kitchen"][1].get("structure"),
                                    "adjacent": [{"to": "kitchen", "dir": "s",
                                                  "barrier": "closed_door"}]})
    specs["kitchen"][1]["adjacent"].append({"to": "store", "dir": "n", "barrier": "closed_door"})
    b = _building(specs=specs)
    assert b["refusal"] is None
    assert b["own_blocks"] == {"store": {"beside": "kitchen", "side": "n"}}
    inv = lb.hold_inventory(b, copy.deepcopy(SORT))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(RELATE))
    assert {"id": "store", "apart": False, "beside": {"block": "main", "side": "n"}} in spec["blocks"]
    store_room = next(r for r in spec["rooms"] if r["id"] == "store")
    assert store_room["block"] == "store"
    # its doorway is written from its own side, as the lab wrote the cavern's
    assert {"to": "kitchen", "kind": "door", "side": "s"} in store_room["joins"]
    assert not any(j["to"] == "store" for r in spec["rooms"] if r["id"] == "kitchen"
                   for j in r["joins"])
    layout = lb.solve_spec(spec)
    solved, _report = lb.planned_layout(b, spec, layout)
    store = solved["store"]["geometry"]
    rect = next(rects[0] for floor in layout.floors.values()
                for rid, rects in floor.items() if rid == "store")
    assert "shape" not in store, "never squared: the plan's shape stands"
    assert store["extent"] == {"w": rect.w, "d": rect.d}, "sized from what it holds"
    assert store["site"]["plan"] == b["plan"]
    assert not [r for r in lb.refusals(b, spec, layout) if r.startswith("store was planned")]
    # built from parts the plan places inside its box, it cannot be re-boxed
    parted = copy.deepcopy(specs)
    parted["store"][1]["parts"] = [{"w": 4, "d": 6, "at": "nw"}, {"w": 9, "d": 2, "at": "sw"}]
    refusal = _building(specs=parted)["refusal"]
    assert refusal and "store is planned composite" in refusal


def test_the_plans_own_sides_reach_the_solver_as_asked_sides():
    """A side the plan states reaches the solver as a side asked, weighed
    as the lab weighed every side -- no heavier than one the model chose
    (the owner's ruling of 2026-10-10, sides are wishes)."""
    def hall_kitchen(specs):
        b = _building(specs=specs)
        spec = lb.spec_from_answers(b, lb.hold_inventory(b, copy.deepcopy(SORT)), copy.deepcopy(RELATE))
        return next(j for r in spec["rooms"] for j in r["joins"]
                    if {r["id"], j["to"]} == {"hall", "kitchen"})
    planned = copy.deepcopy(SPECS)
    next(a for a in planned["hall"][1]["adjacent"] if a["to"] == "kitchen")["dir"] = "w"
    entry = hall_kitchen(planned)
    assert entry["side"] == "w" and "held" not in entry


def test_a_building_the_search_missed_on_one_seed_is_tried_on_the_next(monkeypatch):
    """`solve_for` takes the solver's own seed first and the next ones only
    where it fell short: a solve with every stair landed at once, else the
    first the bridge does not refuse, else the first seed's refusal. On the
    owner's shrine (chat 164, 2026-10-10) one answer set stood on 13 of 20
    seeds, the solver's own among the failures."""
    from world.layout_solver import SEED
    seen, plans = [], {}

    def fake_solve(spec, seed=0):
        seen.append(seed)
        return f"layout{seed}"

    monkeypatch.setattr(lb, "solve", fake_solve)
    monkeypatch.setattr(lb, "refusals", lambda building, spec, layout: plans[layout][0])
    monkeypatch.setattr(lb, "unlanded", lambda spec, layout: plans[layout][1])

    def run(*table):
        plans.clear()
        seen.clear()
        for k, outcome in enumerate(table):
            plans[f"layout{SEED + k}"] = outcome
        return lb.solve_for({}, {})

    clean, standing, refused = ([], []), ([], [("stair", "hall")]), (["no doorway"], [])
    assert lb.LAYOUT_SOLVE_SEEDS == 4
    assert run(clean, refused, refused, refused) == (f"layout{SEED}", [])
    assert seen == [SEED], "a seed after the first only where it fell short"
    assert run(refused, standing, clean, refused) == (f"layout{SEED + 2}", [])
    assert seen == [SEED, SEED + 1, SEED + 2]
    assert run(refused, standing, refused, standing) == (f"layout{SEED + 1}", [])
    assert len(seen) == 4
    assert run(refused, (["other"], []), refused, refused) == (f"layout{SEED}", ["no doorway"])


def test_a_stair_whose_hall_opens_on_no_room_it_joins_is_unlanded():
    """Read off the layout's doors: a stair hall with no doorway onto a room
    its stair joins leaves the plan's stair no landing in that room."""
    b, inv, spec, layout = _solve()
    assert lb.unlanded(spec, layout) == []
    (st,) = spec["stairs"]
    halls = {h for well in layout.stairwells for h in (well.get("halls") or {}).values()}
    layout.doors = [d for d in layout.doors
                    if not ({d["a"], d["b"]} & halls and st["from"] in (d["a"], d["b"]))]
    assert lb.unlanded(spec, layout) == [(st["id"], st["from"])]


def test_a_shape_built_from_parts_that_names_none_is_laid_as_its_box():
    """A part-less `l` or `composite` covers its whole extent
    (`spatial_fov._shape_cells`): joined by a stair it is solved as the
    rectangle it already is, its shape word kept. The Room planned the
    owner's refined shrine (scratch chat 169, 2026-10-10) with its basement
    `composite` and its roof room an `l`, neither with a part, and the whole
    building was refused. One that names parts, or a round room joined any
    other way than one doorway, still keeps its building out."""
    boxed = copy.deepcopy(SPECS)
    boxed["loft"][1]["shape"] = "composite"
    b = _building(specs=boxed)
    assert b["refusal"] is None and b["boxed"] == ["loft"]
    spec = lb.spec_from_answers(b, lb.hold_inventory(b, copy.deepcopy(SORT)), copy.deepcopy(RELATE))
    layout = lb.solve_spec(spec)
    solved, _report = lb.planned_layout(b, spec, layout)
    geometry = solved["loft"]["geometry"]
    rect = layout.floors[1]["loft"][0]
    assert "shape" not in geometry and geometry["extent"] == {"w": rect.w, "d": rect.d}
    parted = copy.deepcopy(boxed)
    parted["loft"][1]["parts"] = [{"w": 3, "d": 3, "at": "nw"}, {"w": 6, "d": 2, "at": "sw"}]
    assert "loft is planned composite" in (_building(specs=parted)["refusal"] or "")
    rounded = copy.deepcopy(SPECS)
    rounded["loft"][1]["shape"] = "round"
    assert "loft is planned round" in (_building(specs=rounded)["refusal"] or "")


def test_the_architects_brief_is_written_first_and_both_calls_follow_it():
    """The owner's choice of 2026-10-10 ("the brief is a good idea too"):
    one call writes how the building stands as a whole -- from the plan, the
    sides it fixes and the story's lore, never from a brief already written --
    and both layout calls read it as `brief`, beside the lore. The spec keeps
    it for the record."""
    from agents.director_layout import BRIEF_STEP, RELATE_STEP, SORT_STEP, lay_out
    b = dict(_building(), description="The hall is the front room of the house.")
    seen = []

    def call(step, system, payload):
        seen.append((step, copy.deepcopy(payload)))
        if step == BRIEF_STEP:
            return copy.deepcopy(BRIEF)
        return copy.deepcopy(SORT if step == SORT_STEP else RELATE)

    spec, _layout, _inv, _refused = lay_out(b, call, "en")
    assert [step for step, _p in seen] == [BRIEF_STEP, SORT_STEP, RELATE_STEP]
    brief_payload = seen[0][1]
    assert "fixed" in brief_payload and "brief" not in brief_payload["building"]
    assert brief_payload["building"]["description"] == "The hall is the front room of the house."
    for _step, payload in seen[1:]:
        assert payload["building"]["brief"] == BRIEF["brief"]
        assert payload["building"]["description"] == "The hall is the front room of the house."
    assert spec["brief"] == BRIEF["brief"]


@pytest.mark.parametrize("answer", ["raises", {}, {"brief": "  "}, "not a dict"])
def test_a_brief_that_fails_or_says_nothing_leaves_the_two_calls_the_lore_alone(answer):
    """Fails open: the brief call raising, or writing nothing, costs nothing
    but its own call -- the two layout calls read the lore alone."""
    from agents.director_layout import BRIEF_STEP, SORT_STEP, lay_out
    seen = []

    def call(step, system, payload):
        seen.append((step, copy.deepcopy(payload)))
        if step == BRIEF_STEP:
            if answer == "raises":
                raise ValueError("no JSON")
            return answer
        return copy.deepcopy(SORT if step == SORT_STEP else RELATE)

    spec, layout, _inv, _refused = lay_out(_building(), call, "en")
    assert all("brief" not in payload["building"] for _step, payload in seen[1:])
    assert "brief" not in spec and layout is not None


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_every_layout_card_says_what_the_brief_is(lang):
    from llm.prompts import layout_prompt
    brief = layout_prompt("brief", lang)
    assert "`fixed`" in brief and "`description`" in brief and '{"brief":' in brief
    assert "`brief`" in layout_prompt("sort", lang)
    assert "`brief`" in layout_prompt("relate", lang)

