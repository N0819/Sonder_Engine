"""The ground's outline may step, and what stands on it (the fix round's
phase 3, 2026-10-19: the owner's ruling "the house's outline may step -- a
porch, a notch, an L -- rather than rooms leaving the sides the plan asks",
and the visual review of 2026-10-16).

A room of the ground may leave open ground in the slot the arrangement gives
it -- a NOTCH, never a room, never named -- where it would otherwise span a
depth it does not need (`layout_arrange.NOTCH_COST`); every reader of the
layout treats a notch cell as outside the house (`Layout.notches`). A living
room with no outside wall is priced (`HEART_DARK_COST`), so a neighbour
across a cut from it leaves its notch beside it. On the core's path an open
join between two rooms opens at most OPEN_JOIN_MAX cells of their wall, and
an outside door no side is asked of faces where its way leads. A block
stands with its own joined room against the anchor's, and blocks off one
wall slide apart along it. Among rooms opening onto one ground place the
entrance is the house's own door, not the first by id."""
import copy

from world import layout_arrange as A
from world import layout_bridge as lb
from world import layout_solver as S
from world.layout_solver import Layout, Rect, _place_doors, check, room_target

_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


def _room(rid, purpose, joins=(), area=None, windows=(), level=0, block=None):
    r = {"id": rid, "name": rid.replace("_", " ").title(), "purpose": purpose, "level": level,
         "joins": [dict(j) for j in joins], "fixtures": [], "windows": [dict(w) for w in windows],
         "zones": []}
    if area:
        r["area_m2"] = area
    if block:
        r["block"] = block
    return r


def _cells(r):
    return {(r.x + i, r.y + j) for i in range(r.w) for j in range(r.d)}


def _notch_cells(lay):
    out = set()
    for r in lay.notches.get(0, ()):
        out |= _cells(r)
    return out


#: a hall stated large beside a bath the plan leaves unsized: laid as one
#: rectangle wholly floor the bath, alone in its part, ran the house's whole
#: depth at two thirds past its target and the hall came out short of its
#: size (the shrine's washroom, full depth in 18 of 18 layouts)
BATH_BESIDE_A_DEEP_HALL = {
    "name": "bath beside a deep hall", "front": "s", "entrance": {"room": "hall", "kind": "door"},
    "rooms": [_room("hall", "living", [{"to": "bath", "side": "w", "kind": "door"},
                                       {"to": "kitchen", "side": "e", "kind": "door"}], area=40),
              _room("bath", "bath", windows=[{"id": "bath_window", "side": "n", "count": 1}]),
              _room("kitchen", "kitchen", area=22)],
    "stairs": [],
    "grounds": {"areas": [{"id": "garden", "kind": "yard", "name": "The Garden", "where": "around"}]}}


def test_the_outline_steps_where_a_room_would_span_the_depth():
    lay = A.solve_arranged(copy.deepcopy(BATH_BESIDE_A_DEEP_HALL))
    assert check(lay) == []
    o = lay.outlines["main"][0]
    bath = lay.floors[0]["bath"][0]
    hall = lay.floors[0]["hall"][0]
    # the bath no longer spans the depth: it keeps about its target and the
    # rest of its slot is a notch in the outline
    assert lay.notches.get(0)
    assert bath.d < o.d and bath.w < o.w
    target = room_target(next(r for r in BATH_BESIDE_A_DEEP_HALL["rooms"] if r["id"] == "bath"), stated=False)
    assert bath.w * bath.d >= target - A.KEEP_SLACK
    # ...the hall holds its stated size
    stated = 40 / (0.75 * 0.75)
    assert abs(hall.w * hall.d - stated) <= A.STATED_BAND * stated
    # a step or an L, never a ragged edge
    corners, connected = A._steps([r[0] for r in lay.floors[0].values()])
    assert connected and corners <= A.GROUND_STEPS_MAX
    for r in lay.notches[0]:
        assert min(r.w, r.d) >= A.NOTCH_MIN_SIDE


def test_a_notch_cell_is_open_ground_downstream():
    lay = A.solve_arranged(copy.deepcopy(BATH_BESIDE_A_DEEP_HALL))
    notch = _notch_cells(lay)
    assert notch
    # no room, no store stands on it; the outline still covers it, and the
    # solver's own check reads it as covered
    for rooms in lay.floors.values():
        for rects in rooms.values():
            assert not (_cells(rects[0]) & notch)
    assert notch <= _cells(lay.outlines["main"][0])
    assert check(lay) == []
    assert "notches" in lay.as_dict()
    # every reader of the house's walls reads it as outside: the grounds may
    # take it, and a wall facing it is an outside wall
    assert not (S._ground_house(lay) & notch)
    garden = set(lay.areas.get("garden") or ())
    assert notch <= garden
    win = next(w for w in lay.windows if w["room"] == "bath")
    assert win["side"] == "n"
    dx, dy = _STEP[win["side"]]
    assert (win["cell"][0] + dx, win["cell"][1] + dy) in notch
    # the site plan's grounds take it too
    from tools.site_plan_from_layout import GROUNDS, rooms_from_layout
    d = lay.as_dict()
    d["site"] = lay.site.as_dict() if lay.site else {"x": -6, "y": -6, "w": 40, "d": 40}
    grounds = rooms_from_layout(d, "p")[GROUNDS]
    ox, oy = grounds["site"]["x"], grounds["site"]["y"]
    got = set()
    for part in grounds["parts"]:
        x0, y0 = part["at"][0] + ox, part["at"][1] + oy
        got |= {(x0 + i, y0 + j) for i in range(part["w"]) for j in range(part["d"])}
    assert notch <= got


#: a heart room the plan asks a neighbour on every side of, every join open
#: but the closet's -- the shrine's main hall in a minimal skeleton
HEART_ON_EVERY_SIDE = {
    "name": "heart with a neighbour on every side", "front": "s", "entrance": {"room": "genkan", "kind": "door"},
    "rooms": [_room("genkan", "entryway", [{"to": "main_hall", "side": "n", "kind": "open"}]),
              _room("main_hall", "living", [{"to": "washroom", "side": "w", "kind": "open"},
                                            {"to": "kitchen", "side": "e", "kind": "open"},
                                            {"to": "closet", "side": "n", "kind": "door"}], area=20),
              _room("washroom", "bath"), _room("kitchen", "kitchen", area=10), _room("closet", "closet")],
    "stairs": [], "grounds": {}}


def test_a_heart_room_keeps_an_outside_wall():
    lay = A.solve_arranged(copy.deepcopy(HEART_ON_EVERY_SIDE))
    assert check(lay) == []
    hall = lay.floors[0]["main_hall"][0]
    taken = set()
    for rects in lay.floors[0].values():
        taken |= _cells(rects[0])
    outside = [c for c in _cells(hall) for dx, dy in _STEP.values()
               if (c[0] + dx, c[1] + dy) not in taken]
    assert outside, "the main hall has no wall to the outside"
    # every side the plan asks still holds: the neighbours stand where asked
    rooms = lay.floors[0]
    assert rooms["genkan"][0].y >= hall.y + hall.d
    assert rooms["washroom"][0].x + rooms["washroom"][0].w <= hall.x
    assert rooms["kitchen"][0].x >= hall.x + hall.w
    # ...and the hall is near its stated size, not crushed to give it a wall
    stated = 20 / (0.75 * 0.75)
    assert hall.w * hall.d >= (1 - 0.3) * stated


def test_an_open_join_opens_three_cells_on_the_cores_path():
    def doors(apart):
        layout = Layout(name="open")
        layout.floors = {0: {"hall": [Rect(0, 0, 4, 8)], "parlour": [Rect(4, 0, 5, 8)]}}
        rooms = {"hall": {"id": "hall", "purpose": "living", "joins": [{"to": "parlour", "kind": "open"}]},
                 "parlour": {"id": "parlour", "purpose": "living", "joins": []}}
        _place_doors(layout, rooms, set(), apart=apart)
        return layout.doors
    (core,) = doors(True)
    assert len(core["span"]) == S.OPEN_JOIN_MAX == 3
    assert core["cell"] in core["span"]
    ys = sorted(c[1] for c in core["span"])
    assert ys == list(range(ys[0], ys[0] + 3))
    # the lab's own solve opens the whole wall, as before
    (lab,) = doors(False)
    assert len(lab["span"]) == 8


def test_an_open_stair_keeps_its_whole_wall_open():
    layout = Layout(name="open stair")
    layout.floors = {0: {"hall": [Rect(0, 0, 4, 8)], "stair@0": [Rect(4, 0, 2, 5)]}}
    rooms = {"hall": {"id": "hall", "purpose": "living", "joins": [{"to": "stair@0", "kind": "open"}]},
             "stair@0": {"id": "stair@0", "purpose": "stair", "joins": []}}
    _place_doors(layout, rooms, set(), apart=True)
    (d,) = layout.doors
    assert len(d["span"]) == 5


PORCH_SOUTH_OF_A_ROW = {
    "name": "porchhouse", "front": "s",
    "rooms": [_room("porch", "entryway", [{"to": "hall", "kind": "door", "side": "n"}], block="porch"),
              _room("hall", "hall", [{"to": "parlour", "kind": "door", "side": "e"}]),
              _room("parlour", "living", [{"to": "kitchen", "kind": "door", "side": "e"}]),
              _room("kitchen", "kitchen", [{"to": "dining", "kind": "door", "side": "e"}]),
              _room("dining", "dining")],
    "stairs": [], "blocks": [{"id": "porch", "beside": {"block": "main", "side": "s"}}], "storeys": [],
    "entrance": {"kind": "door", "room": "porch"}}


def test_a_block_stands_with_its_own_joined_room_against_the_anchors():
    # the code review's e04b: the main block was centred on the porch, the
    # porch stood under the parlour, and the hall's wall was shared with none
    lay = A.solve_arranged(copy.deepcopy(PORCH_SOUTH_OF_A_ROW))
    assert check(lay) == [] and lb._standing_breaches(lay) == []
    porch, hall = lay.floors[0]["porch"][0], lay.floors[0]["hall"][0]
    side, cells = __import__("world.layout_solver", fromlist=["_shared_wall"])._shared_wall(porch, hall)
    assert side == "n" and len(cells) >= A.MIN_SHARED
    assert any(d["a"] in ("porch", "hall") and d["b"] in ("porch", "hall") for d in lay.doors)


TWO_CAVERNS_OFF_ONE_WALL = {
    "name": "twocaves2", "front": "s",
    "rooms": [_room("hall", "hall", [{"to": "kitchen", "kind": "door", "side": "n"}]),
              _room("kitchen", "kitchen"),
              _room("basement", "basement", [{"to": "well_cave", "kind": "door", "side": "n", "order": 1},
                                             {"to": "ice_cave", "kind": "door", "side": "n", "order": 2}],
                    level=-1),
              _room("well_cave", "other", level=-1, block="well_cave"),
              _room("ice_cave", "storage", level=-1, block="ice_cave")],
    "stairs": [{"id": "b1", "from": "hall", "to": "basement", "kind": "straight", "name": "cellar stair",
                "enclosed": False, "door": "door", "from_at": "s", "to_at": "s"}],
    "blocks": [{"id": "well_cave", "beside": {"block": "main", "side": "n"}},
               {"id": "ice_cave", "beside": {"block": "main", "side": "n"}}],
    "storeys": [], "entrance": {"kind": "door", "room": "hall"}}


def test_caverns_off_one_wall_slide_apart_along_it():
    # the code review's e32b: both caverns were centred on the basement and
    # laid on the same nine cells
    lay = A.solve_arranged(copy.deepcopy(TWO_CAVERNS_OFF_ONE_WALL))
    assert lb._standing_breaches(lay) == []
    well, ice = lay.floors[-1]["well_cave"][0], lay.floors[-1]["ice_cave"][0]
    assert not (_cells(well) & _cells(ice))
    from world.layout_solver import _shared_wall
    base = lay.floors[-1]["basement"][0]
    for cave in (well, ice):
        side, cells = _shared_wall(base, cave)
        assert side == "n" and len(cells) >= A.MIN_SHARED
    # in the plan's order along the wall: the well cave west of the ice cave
    assert well.x < ice.x


def test_the_entrance_is_the_house_door_among_rooms_opening_onto_one_ground():
    # the unseen farmhouse: its byre and its cross passage both open south
    # onto the farmyard, and the byre, first by id, took the front door
    def room(name, purpose, adjacent, exposure="enclosed"):
        return (name, {"name": name, "purpose": purpose, "structure": "farm", "exposure": exposure,
                       "adjacent": adjacent, "shape": "rectangle"})
    specs = {
        "a_byre": room("Byre", "the cow byre under the same roof",
                       [{"to": "passage", "dir": "w", "barrier": "wood"},
                        {"to": "yard", "dir": "s", "barrier": "wood"}]),
        "passage": room("Cross Passage", "the flagged passage across the house",
                        [{"to": "house_place", "dir": "w", "barrier": "wood"},
                         {"to": "a_byre", "dir": "e", "barrier": "wood"},
                         {"to": "yard", "dir": "s", "barrier": "wood"}]),
        "house_place": room("House Place", "the great farm kitchen",
                            [{"to": "passage", "dir": "e", "barrier": "wood"},
                             {"to": "chamber", "vertical": "up", "way": "stair"}]),
        # a storey above: the tier lays buildings of two storeys or more
        "chamber": room("Chamber", "the chamber under the eaves",
                        [{"to": "house_place", "vertical": "down", "way": "stair"}]),
        "yard": room("Farmyard", "the farmyard", [{"to": "passage", "dir": "n"}, {"to": "a_byre", "dir": "n"}],
                     exposure="open"),
    }
    found = lb.plan_buildings(copy.deepcopy(specs), {"rooms": {}, "positions": {}, "entities": {}},
                              held_open=set())
    b = next(x for x in found if "passage" in x["rooms"])
    assert b["entrance"]["room"] == "passage"
    assert b["entrance"]["to"] == "yard"


def test_a_door_no_side_is_asked_of_faces_where_its_way_leads():
    # the review's visual 6: a latrine north-west of the house, its door onto
    # the way to the washroom's back door faced north, away from the house
    def doors(apart):
        layout = Layout(name="latrine")
        layout.floors = {0: {"washroom": [Rect(0, 0, 4, 4)], "latrine": [Rect(-8, -8, 3, 3)]}}
        layout.outlines = {"main": {0: Rect(0, 0, 4, 4)}, "latrine": {0: Rect(-8, -8, 3, 3)}}
        rooms = {"washroom": {"id": "washroom", "purpose": "bath", "level": 0,
                              "joins": [{"to": "latrine_way", "side": "n", "kind": "door"}]},
                 "latrine": {"id": "latrine", "purpose": "latrine", "level": 0,
                             "joins": [{"to": "latrine_way", "kind": "door"}]}}
        _place_doors(layout, rooms, {"latrine_way"}, apart=apart)
        return next(d for d in layout.doors if d["a"] == "latrine")
    assert doors(True)["side"] in ("e", "s")
    # the lab's own solve keeps its order, north first
    assert doors(False)["side"] == "n"


def test_the_stair_head_two_paces_are_a_price_not_a_rule():
    # one pace of wall where two are wanted costs HEAD_SHARED_COST; less
    # than one is no join at all
    chk = [(0, 0, 1, 0, False, None, A.MIN_SHARED)]
    assert A._chk_cost(chk, ((0, 5),), ((4, 9),)) == A.HEAD_SHARED_COST
    assert A._chk_cost(chk, ((0, 5),), ((3, 9),)) == 0.0
    assert A._chk_cost(chk, ((0, 5),), ((5, 9),)) == A.INF


# ------------------------------------------------- the fix round's phase 3, second pass

def test_an_unsided_door_opens_where_its_way_is_shortest():
    # fuzz plan 125's privy, east of a side room whose own door onto the
    # privy's way is in its north wall: turned to face the side room's
    # centre it opened west into the garden between them, the way cut the
    # garden and the privy was dropped. Its north door's step lies 9 steps
    # from the side room's, its west door's 10
    layout = Layout(name="privy")
    layout.floors = {0: {"side": [Rect(3, 0, 5, 9)], "privy": [Rect(11, 2, 3, 4)]}}
    layout.outlines = {"main": {0: Rect(3, 0, 5, 9)}, "privy": {0: Rect(11, 2, 3, 4)}}
    rooms = {"side": {"id": "side", "purpose": "bedroom", "level": 0,
                      "joins": [{"to": "privy_way", "side": "n", "kind": "door"}]},
             "privy": {"id": "privy", "purpose": "latrine", "level": 0,
                       "joins": [{"to": "privy_way", "kind": "door"}]}}
    _place_doors(layout, rooms, {"privy_way"}, apart=True)
    assert next(d for d in layout.doors if d["a"] == "privy")["side"] == "n"
    # ...and with `face` off, the lab's order, north first, as well
    layout.doors = []
    _place_doors(layout, rooms, {"privy_way"}, apart=True, face=False)
    assert next(d for d in layout.doors if d["a"] == "privy")["side"] == "n"


def _building_of(spec):
    return A._Building(S._prepare(copy.deepcopy(spec), own_outlines=True))


def test_a_room_laid_short_of_its_size_wants_no_notch():
    # a notch gives back floor a room does not need, and never gives one
    # more: the unseen inn's taproom laid 70 of a stated 85 cells set the
    # inn laying its ground twice for the same layout
    B = _building_of(BATH_BESIDE_A_DEEP_HALL)
    bath = next(r for r in BATH_BESIDE_A_DEEP_HALL["rooms"] if r["id"] == "bath")
    k = room_target(bath, stated=False)
    w = int(2 * k // 8) + 1                              # twice its target, eight deep
    laid = A._Laid(0, Rect(0, 0, 5 + w + 5, 8),
                   {"hall": Rect(0, 0, 5, 8), "bath": Rect(5, 0, w, 8), "kitchen": Rect(5 + w, 0, 5, 8)}, [], 0.0)
    # the hall, stated 71 cells, laid 40; the kitchen at its size; the bath past its band
    assert B._notch_wanted(laid) == {"bath"}


#: the bath beside a deep hall with a bedroom over the hall, up a straight
#: stair: one flight, laid each way round it
BATH_UNDER_A_STOREY = copy.deepcopy(BATH_BESIDE_A_DEEP_HALL)
BATH_UNDER_A_STOREY["rooms"].append(_room("upper", "bedroom", level=1, area=12))
BATH_UNDER_A_STOREY["stairs"] = [{"id": "s", "name": "stair", "from": "hall", "to": "upper", "from_at": "n",
                                  "to_at": "n", "kind": "straight", "enclosed": True, "door": "door"}]


def _notched_lays(monkeypatch):
    calls = []
    lay_free = A._Building.lay_free

    def counted(self, *a, **k):
        if k.get("notch"):
            calls.append(sorted(k["notch"]))
        return lay_free(self, *a, **k)
    monkeypatch.setattr(A._Building, "lay_free", counted)
    return calls


def test_the_notched_pass_runs_once_and_only_where_a_notch_can_stand(monkeypatch):
    # laid with notches in the slots of the rooms that want one, for the ends
    # of the flights the best plain chain's ground was laid for alone (the
    # shrine's s1: four ways round two flights, 1.9 s to find no notch)
    calls = _notched_lays(monkeypatch)
    lay = A.solve_arranged(copy.deepcopy(BATH_UNDER_A_STOREY))
    assert calls == [["bath"]]
    assert lay.notches.get(0)
    p = S._prepare(copy.deepcopy(BATH_UNDER_A_STOREY), own_outlines=True)
    B = A._Building(p)
    kinds = {sh.id: sh.kind for sh in p.shafts}
    assert len(B._end_combos(B.home, 0, kinds, set())) == 2
    # ...and not at all where the rooms that want one lie wholly under the
    # storey beside the ground: a notch there leaves an upper room over open
    # ground (the unseen inn and its hospital laid their grounds twice for it)
    calls.clear()
    monkeypatch.setattr(A._Building, "_wholly_under", staticmethod(lambda state, first, rooms: True))
    lay = A.solve_arranged(copy.deepcopy(BATH_UNDER_A_STOREY))
    assert calls == [] and not lay.notches.get(0)


def test_a_room_wholly_under_the_storey_above_is_read_so():
    B = _building_of(BATH_UNDER_A_STOREY)
    g = A._Laid(0, Rect(0, 0, 8, 6), {"hall": Rect(0, 0, 5, 6), "bath": Rect(5, 0, 3, 6)}, [], 0.0)
    over_all = A._Laid(1, Rect(0, 0, 8, 6), {"upper": Rect(0, 0, 8, 6)}, [], 0.0)
    over_hall = A._Laid(1, Rect(0, 0, 5, 6), {"upper": Rect(0, 0, 5, 6)}, [Rect(5, 0, 3, 6)], 0.0)
    assert B._wholly_under(A._State(0.0, {0: g, 1: over_all}, {}, {}), 0, {"bath"})
    assert not B._wholly_under(A._State(0.0, {0: g, 1: over_hall}, {}, {}), 0, {"bath"})


def test_the_ground_grows_for_a_crushed_room_only_on_a_crowded_storey():
    # the shrine's clone 168 #2 and its s1: Hinami's room laid at half its
    # size on a first floor needing half the ground's floor -- crushed by how
    # it is arranged; the ground grown for 4.5 s and 3.6 s, and kept
    B = _building_of(BATH_UNDER_A_STOREY)
    g = A._Laid(0, Rect(0, 0, 8, 6), {"hall": Rect(0, 0, 5, 6), "bath": Rect(5, 0, 3, 6)}, [], 0.0)
    up = A._Laid(1, Rect(0, 0, 4, 3), {"upper": Rect(0, 0, 4, 3)}, [], 0.0)
    st = A._State(0.0, {0: g, 1: up}, {}, {})
    floor = 48
    B.rooms["upper"]["area_m2"] = 0.5 * floor * 0.75 * 0.75          # needs half the ground's floor
    assert not B._crowded(st, 0, ["upper"])
    B.rooms["upper"]["area_m2"] = 0.95 * floor * 0.75 * 0.75         # the unseen inn's 95%
    assert B._crowded(st, 0, ["upper"])


def test_a_notch_never_leaves_a_landing_nobody_reaches(monkeypatch):
    # the shrine skeleton laid with notches in every room's slot and for every
    # way round its two flights: one notched ground -- a 3 x 2 genkan beside
    # a porch -- ran its stair halls the whole north row, and the up flight,
    # kept along the hall's wall, sealed the two cells past its head. No
    # ground with notches that seals a landing is carried, nor any storey
    # laid on one (`_settle`); the plain ground seals none
    from tests.test_a_stair_is_climbed_and_its_landing_reached import SKELETON, _climbable, _sealed
    monkeypatch.setattr(A._Building, "_notch_wanted", lambda self, laid: frozenset(
        r for r in laid.rects if r in self.rooms and r not in self.hall_ids))
    init = A._Laid.__init__

    def every_way_round(self, *a, **k):
        k.pop("ends", None)
        init(self, *a, **k)
    monkeypatch.setattr(A._Laid, "__init__", every_way_round)
    lay = A.solve_arranged(copy.deepcopy(SKELETON))
    assert _sealed(lay) == 0
    assert _climbable(lay) == []
