"""The layout tier's arrangement-first core (`world.layout_arrange`) is never
worse than the lab's own search, and its work is bounded (the fix round's
phase 1, 2026-10-19: the code review of 2026-10-16 and the unseen plans).

A plan the lab's search lays is never refused by the core: where the core
raises, passes its work budget, or lays what the bridge refuses, the bridge
lays the building as before the core -- four seeds of the lab's search, the
best that stands -- and says so (`layout_bridge.solve_for`). And the review's
plans the core raised on or refused are laid by the core itself: doors
outdoors on three sides, a top-heavy house, a storey skipped, eleven rooms
whose hall is spelled first, a room and a stair asked on one end of a
corridor. Two blocks laid on the same ground are refused, never written."""
import copy

import pytest

from world import layout_arrange as A
from world import layout_bridge as lb
from world.layout_solver import Rect, SEED, check


def _building(spec):
    """The bridge's building for a bare spec: its rooms, storeys, room joins
    and the entrance's own door."""
    levels = {r["id"]: int(r.get("level") or 0) for r in spec["rooms"]}
    joins, seen = [], set()
    for r in spec["rooms"]:
        for j in r.get("joins") or ():
            if j["to"] in levels and frozenset((r["id"], j["to"])) not in seen:
                seen.add(frozenset((r["id"], j["to"])))
                joins.append({"a": r["id"], "b": j["to"], "side": j.get("side"), "barrier": None})
    ent = spec["entrance"]["room"]
    return {"rooms": list(levels), "levels": levels, "joins": joins,
            "outside": [{"room": ent, "to": "__front__", "side": None}],
            "entrance": {"room": ent, "to": "__front__"}}


def _room(rid, purpose, level=0, joins=(), windows=()):
    return {"id": rid, "name": rid.replace("_", " ").title(), "purpose": purpose, "level": level,
            "joins": [dict(j) for j in joins], "fixtures": [], "windows": [dict(w) for w in windows], "zones": []}


#: The code review's e31c: a hall (the entrance, front south) with doors north
#: onto the garden and east onto the yard, and a kitchen with a door east
#: onto the same yard -- no rectangle holds every door's side.
THROUGH_HALL = {
    "name": "throughhall", "front": "s", "stairs": [], "blocks": [], "storeys": [],
    "entrance": {"kind": "door", "room": "hall"},
    "rooms": [_room("hall", "hall", joins=[{"to": "kitchen", "kind": "door"},
                                           {"to": "garden", "kind": "door", "side": "n"},
                                           {"to": "yard", "kind": "door", "side": "e"}]),
              _room("kitchen", "kitchen", joins=[{"to": "yard", "kind": "door", "side": "e"}])],
    "grounds": {"areas": [{"id": "front_yard", "kind": "yard", "name": "Front Yard", "where": "s"},
                          {"id": "garden", "kind": "garden", "name": "Garden", "where": "n"},
                          {"id": "yard", "kind": "yard", "name": "Yard", "where": "e"}],
                "features": [], "ways": [], "narrowest": 2}}

#: The code review's e36d: an entry and a kitchen on the ground under a
#: landing with five bedrooms -- an upper floor no ground the size its own
#: rooms need can carry.
TOP_HEAVY = {
    "name": "topheavy_sided", "front": "s", "blocks": [], "storeys": [],
    "entrance": {"kind": "door", "room": "hall"},
    "stairs": [{"id": "s", "from": "hall", "to": "landing", "kind": "straight", "name": "stair",
                "enclosed": False, "door": "door", "from_at": "n", "to_at": "n"}],
    "rooms": [_room("hall", "entryway", joins=[{"to": "kitchen", "kind": "door", "side": "e"}]),
              _room("kitchen", "kitchen"),
              _room("landing", "hallway", 1, joins=[{"to": f"bed_{c}", "kind": "door", "side": s}
                                                    for c, s in zip("abcde", "wewew")])]
    + [_room(f"bed_{c}", "bedroom", 1) for c in "abcde"]}


def _grid(sided):
    """Six rooms in a two-by-three grid, each joined to its neighbours: the
    code review's g_2x3, with the sides asked or not."""
    def j(to, side):
        return {"to": to, "kind": "door", **({"side": side} if sided else {})}
    return {"name": "grid", "front": "s", "stairs": [], "blocks": [], "storeys": [],
            "entrance": {"kind": "door", "room": "hall"},
            "rooms": [_room("r00", "study", joins=[j("r01", "e"), j("r10", "s")]),
                      _room("r01", "bedroom", joins=[j("r02", "e"), j("hall", "s")]),
                      _room("r02", "storage", joins=[j("r12", "s")]),
                      _room("r10", "kitchen", joins=[j("hall", "e")]),
                      _room("hall", "hall", joins=[j("r12", "e")]),
                      _room("r12", "bedroom")]}


def _door(layout, a, b):
    return next((d for d in layout.doors if {d["a"], d["b"]} == {a, b}), None)


# ------------------------------------------------------------------ the fallback

def test_the_core_lays_a_building_it_can_once_and_alone(monkeypatch):
    """Where the core's layout stands, it is the solve: the lab's search is
    never run, and `attempts` holds the one solve."""
    def no_lab(*_a, **_k):
        raise AssertionError("the lab's search ran for a building the core laid")
    monkeypatch.setattr(lb, "solve", no_lab)
    spec = copy.deepcopy(THROUGH_HALL)
    attempts = []
    layout, refused = lb.solve_for(_building(spec), spec, attempts=attempts)
    assert refused == [] and len(attempts) == 1 and attempts[0][0] is layout
    assert not any("arrangement core" in w for w in layout.warnings)


@pytest.mark.parametrize("failure", ["raises", "budget"])
def test_a_building_the_core_cannot_lay_is_laid_by_the_lab_and_says_so(monkeypatch, failure):
    """The core raising, or passing its work budget (a count, never a
    clock), hands the building to the lab's four seeds -- the old path --
    and the layout names what happened."""
    spec = copy.deepcopy(THROUGH_HALL)
    if failure == "raises":
        def broken(_spec, seed=SEED):
            raise ValueError("block main: storey 0 could not be laid")
        monkeypatch.setattr(lb, "solve_arranged", broken)
    else:
        monkeypatch.setattr(A, "ARRANGE_WORK_BUDGET", 50)
    layout, refused = lb.solve_for(_building(spec), spec)
    assert refused == []
    said = [w for w in layout.warnings if "arrangement core" in w]
    assert len(said) == 1 and "lab's search (seed" in said[0]
    assert ("work budget" in said[0]) == (failure == "budget")


def test_a_building_both_refuse_is_refused_as_the_core_laid_it(monkeypatch):
    """Where the lab refuses every seed too, the building is refused as it
    was before the fallback: the core's solve and its refusals, and the
    attempts hold that solve alone."""
    calls = []
    real = lb.refusals

    def refusing(building, spec, layout, breaches=None):
        calls.append(layout)
        return real(building, spec, layout, breaches=breaches) + ["refused for the test"]
    monkeypatch.setattr(lb, "refusals", refusing)
    spec = copy.deepcopy(_grid(sided=True))
    attempts = []
    layout, refused = lb.solve_for(_building(spec), spec, attempts=attempts)
    assert refused[-1] == "refused for the test"
    assert len(calls) == 1 + lb.LAYOUT_SOLVE_SEEDS
    assert layout is calls[0] and [a[0] for a in attempts] == [layout]


def test_two_blocks_on_the_same_ground_are_refused():
    """The lab's `check` judges each block alone; the bridge refuses two
    blocks' outlines on one storey standing on the same ground (the code
    review's two caverns off one basement wall, laid on the same nine cells
    and written)."""
    spec = copy.deepcopy(_grid(sided=True))
    layout = lb.solve_spec(spec)
    assert lb.refusals(_building(spec), spec, layout) == []
    o = layout.outlines["main"][0]
    layout.outlines["shed"] = {0: Rect(o.x + 1, o.y + 1, 2, 2)}
    assert any("stand on the same ground" in r for r in lb.refusals(_building(spec), spec, layout))


# ------------------------------------------------------------------ the core itself

def test_doors_outdoors_that_cannot_all_hold_turn_one_at_a_time():
    """Doors outdoors on three sides of the entrance hall and a kitchen's
    door onto the same yard: the core gives way the lowest door side --
    never the entrance's front -- and the lab's doors name the turn."""
    spec = copy.deepcopy(THROUGH_HALL)
    layout = A.solve_arranged(spec)
    assert check(layout) == []
    turned = [w for w in layout.warnings if "opens to" in w and "not the" in w]
    assert len(turned) == 1
    front = next(d for d in layout.doors if d.get("outside") and d["b"] == "entrance")
    assert front["side"] == "s"


def test_a_top_heavy_house_grows_its_ground_and_says_so():
    """An upper floor no ground the size of its own rooms can carry: the
    block is laid again on larger grounds -- the owner's rule that no ground
    room grows for the storey above yields only here -- and the layout says
    the ground was laid larger than its rooms need."""
    spec = copy.deepcopy(TOP_HEAVY)
    layout = A.solve_arranged(spec)
    assert check(layout) == [] and lb._standing_breaches(layout) == []
    assert any("laid larger than its own rooms need" in w for w in layout.warnings)
    for bed in "abcde":
        assert _door(layout, "landing", f"bed_{bed}") is not None


def test_a_storey_skipped_is_laid_on_the_nearest_below():
    """A belfry at storey 2 over nothing at storey 1 (the code review's e19,
    a KeyError): it stands on the ground storey."""
    spec = {"name": "gap", "front": "s", "stairs": [], "blocks": [], "storeys": [],
            "entrance": {"kind": "door", "room": "hall"},
            "rooms": [_room("hall", "hall", joins=[{"to": "kitchen", "kind": "door", "side": "n"}]),
                      _room("kitchen", "kitchen"), _room("belfry", "other", 2)]}
    layout = A.solve_arranged(spec)
    assert check(layout) == [] and "belfry" in layout.floors[2]


def test_a_room_and_a_stair_on_one_end_of_a_corridor_the_room_gives_way():
    """A corridor's two-pace end holds its stair or a room, not both: the
    room's side gives way before laying, with a note, and the stair keeps
    the end (the unseen merchant's gallery: the maids' room and the gallery
    stair both asked on its west end, and the upper floor written
    unreachable after 255 s)."""
    from world.layout_solver import _prepare
    spec = {"name": "gallery", "front": "s", "blocks": [], "storeys": [],
            "entrance": {"kind": "door", "room": "hall"},
            "stairs": [{"id": "g", "from": "hall", "to": "gallery", "kind": "straight", "name": "gallery stair",
                        "enclosed": False, "door": "door", "from_at": "w", "to_at": "w"}],
            "rooms": [_room("hall", "hall"),
                      _room("gallery", "hallway", 1, joins=[{"to": "maids", "kind": "door", "side": "w"},
                                                             {"to": "chamber", "kind": "door", "side": "n"},
                                                             {"to": "nursery", "kind": "door", "side": "n"},
                                                             {"to": "guest", "kind": "door", "side": "s"},
                                                             {"to": "solar", "kind": "door", "side": "e"}]),
                      _room("maids", "bedroom", 1), _room("chamber", "bedroom", 1), _room("nursery", "bedroom", 1),
                      _room("guest", "bedroom", 1), _room("solar", "living", 1)]}
    b = A._Building(_prepare(spec, own_outlines=True))
    ids = b.leaves_of("main", 1)
    out = b.storey("main", 1, ids, {}, frozenset(), {}, {"g": "straight"})
    notes, held = out[9], out[-1]
    assert frozenset(("gallery", "maids")) in held
    assert frozenset(("g@1", "gallery")) not in held
    assert ("side", "gallery", "maids", 8, "gallery stair") in notes
    # a room alone on that end keeps it
    spec["stairs"][0]["to_at"] = "n"
    b = A._Building(_prepare(spec, own_outlines=True))
    out = b.storey("main", 1, ids, {}, frozenset(), {}, {"g": "straight"})
    assert frozenset(("gallery", "maids")) not in out[-1]


def test_joins_asked_no_side_are_laid_within_a_bounded_count(monkeypatch):
    """Six rooms joined to their neighbours with no side asked (the code
    review: 46 s and 1 GB one try, eight rooms past 1.6 GB): the storey is
    searched narrowly past NARROW_WORK_OPEN entries, every join keeps a
    wall, and the whole building is counted well inside the budget."""
    seen = {}
    real = A._Building.division

    def counted(self):
        try:
            return real(self)
        finally:
            seen["work"] = self.meter.total
    monkeypatch.setattr(A._Building, "division", counted)
    spec = _grid(sided=False)
    layout = A.solve_arranged(copy.deepcopy(spec))
    assert check(layout) == []
    assert seen["work"] < A.ARRANGE_WORK_BUDGET // 4
    for r in spec["rooms"]:
        for j in r["joins"]:
            assert _door(layout, r["id"], j["to"]) is not None


def test_a_window_never_gives_way_with_a_join():
    """Four rooms all joined to each other, three asking a window: the join
    that has to give way takes no window with it (the code review's e29:
    all three windows were turned with it)."""
    spec = {"name": "k4", "front": "s", "stairs": [], "blocks": [], "storeys": [],
            "entrance": {"kind": "door", "room": "hall"},
            "rooms": [_room("hall", "hall", joins=[{"to": x, "kind": "door"} for x in "abc"]),
                      _room("a", "study", joins=[{"to": "b", "kind": "door"}, {"to": "c", "kind": "door"}],
                            windows=[{"side": "n"}]),
                      _room("b", "bedroom", joins=[{"to": "c", "kind": "door"}], windows=[{"side": "e"}]),
                      _room("c", "kitchen", windows=[{"side": "w"}])]}
    layout = A.solve_arranged(spec)
    assert not any("a window could not keep its side" in w for w in layout.warnings)
    turned = [w for w in layout.warnings if "its window could not face" in w]
    assert len(turned) <= 1


def test_a_join_said_lost_shares_no_wall():
    """A join given way is said lost only where its two rooms share no wall
    as laid (the code review: 'Aa Pantry and Hall could not share a wall' of
    two rooms that did)."""
    spec = {"name": "k4", "front": "s", "stairs": [], "blocks": [], "storeys": [],
            "entrance": {"kind": "door", "room": "hall"},
            "rooms": [_room("hall", "hall", joins=[{"to": x, "kind": "door"} for x in "abc"]),
                      _room("a", "study", joins=[{"to": "b", "kind": "door"}, {"to": "c", "kind": "door"}]),
                      _room("b", "bedroom", joins=[{"to": "c", "kind": "door"}]),
                      _room("c", "kitchen")]}
    layout = A.solve_arranged(spec)
    names = {v: k for k, v in layout.names.items()}
    for w in layout.warnings:
        if w.endswith("could not share a wall: the storey cannot hold every join the plan asks"):
            a, b = w.split(" could not share")[0].split(" and ")
            assert _door(layout, names[a], names[b]) is None, w
