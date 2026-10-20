"""Every stair the layout tier's core lays can be climbed, and the floor round
it is floor someone reaches (the fix round's phase 2, 2026-10-19: the unseen
plans and the visual review of 2026-10-16).

A straight flight is climbed from its foot on its lowest storey to its head on
its top one: where the rooms it joins reach the same end on both -- corridors
stacked one over another with the stair at their end -- it turns back on
itself, a U (`layout_arrange._climb`). A stair hall may take a landing past
its cap where a room's stated size needs the band (`LANDING_OVER_COST`),
across its run between the flight and the room it serves, and the storey
above keeps that landing (`KEPT_LANDING_COST`). A landing lies where its
storey reaches it (`_sealed`). A window above a stair keeps the desk the plan
sets by it beneath it (`_window_landing`). No room opens two doorways from one
cell (`layout_solver._place_doors(apart=True)`, the core's path only). A
storey of one room rises sheer over its stair (`_sheer_box`), and an upper
room stands over the rooms its stair climbs from (`OVER_COST`)."""
import copy
import json
from pathlib import Path

from world import layout_arrange as A
from world.layout_solver import Layout, Rect, _place_doors, _shared_wall

_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
_BASELINES = Path(__file__).resolve().parent.parent / "tools" / "layout_lab" / "baselines"


def _room(rid, purpose, level=0, joins=(), windows=(), fixtures=(), area=None):
    r = {"id": rid, "name": rid.replace("_", " ").title(), "purpose": purpose, "level": level,
         "joins": [dict(j) for j in joins], "fixtures": [dict(f) for f in fixtures],
         "windows": [dict(w) for w in windows], "zones": []}
    if area:
        r["area_m2"] = area
    return r


def _stair(sid, a, b, at_a, at_b, kind="straight", enclosed=True, name="stair"):
    return {"id": sid, "name": name, "from": a, "to": b, "from_at": at_a, "to_at": at_b, "kind": kind,
            "enclosed": enclosed, "door": "door"}


def _cells(r):
    return {(r.x + i, r.y + j) for i in range(r.w) for j in range(r.d)}


def _ends(f):
    """The two short ends of a straight flight: (north or west row, south or east row)."""
    if f.w >= f.d:
        return {(f.x, f.y + j) for j in range(f.d)}, {(f.x + f.w - 1, f.y + j) for j in range(f.d)}
    return {(f.x + i, f.y) for i in range(f.w)}, {(f.x + i, f.y + f.d - 1) for i in range(f.w)}


def _door_hall_cells(lay, hid, lv):
    """The cells of hall `hid` each doorway into it opens onto (an open
    stair's whole span)."""
    out = []
    for d in lay.doors:
        if d.get("level") != lv or hid not in (d["a"], d["b"]):
            continue
        dx, dy = _STEP[d["side"]]
        cells = [tuple(c) for c in d.get("span") or [d["cell"]]]
        out.append([c if d["a"] == hid else (c[0] + dx, c[1] + dy) for c in cells])
    return out


def _climbable(lay):
    """The straight stairwells no body can climb foot to head, read as the
    sensible check reads them: on the lowest storey every doorway into the
    hall reaches one end (straight onto it, or across the hall's landing),
    on the top storey every doorway the other."""
    bad = []
    for well in lay.stairwells:
        if well["kind"] != "straight" or len(well["levels"]) < 2:
            continue
        f = Rect(**well["rect"])
        flight = _cells(f)
        low, top = min(well["levels"]), max(well["levels"])

        def reaches(cells, hall, end):
            for c in cells:
                if c in end:
                    return True
                if c in flight:
                    continue
                seen, stack = set(), [c]
                while stack:
                    q = stack.pop()
                    if q in seen or q not in hall or q in flight:
                        continue
                    seen.add(q)
                    stack.extend((q[0] + dx, q[1] + dy) for dx, dy in _STEP.values())
                if any((q[0] + dx, q[1] + dy) in end for q in seen for dx, dy in _STEP.values()):
                    return True
            return False

        a, b = _ends(f)
        ok = False
        for foot, head in ((a, b), (b, a)):
            good = True
            for lv in (low, top):
                hid = well["halls"][str(lv)]
                hall = set()
                for r in lay.floors[lv][hid]:
                    hall |= _cells(r)
                for cells in _door_hall_cells(lay, hid, lv):
                    if not reaches(cells, hall, foot if lv == low else head):
                        good = False
            ok = ok or good
        if not ok:
            bad.append(well["id"])
    return bad


def _sealed(lay):
    """Landing cells of straight stair halls no body on their storey reaches
    without crossing the flight (the review's audit: from each doorway's
    cells, and from the end of the flight the storey takes)."""
    n = 0
    for well in lay.stairwells:
        if well["kind"] != "straight":
            continue
        flight = _cells(Rect(**well["rect"]))
        low, top = min(well["levels"]), max(well["levels"])
        foot = {tuple(c) for c in well.get("foot") or ()}
        head = {tuple(c) for c in well.get("head") or ()}
        for lv_s, hid in well["halls"].items():
            lv = int(lv_s)
            hall = set()
            for r in lay.floors[lv][hid]:
                hall |= _cells(r)
            land = hall - flight
            used = foot if lv == low and lv != top else head if lv == top and lv != low else foot | head
            seeds = set()
            for cells in _door_hall_cells(lay, hid, lv):
                for c in cells:
                    if c in land:
                        seeds.add(c)
                    elif c in flight:
                        seeds |= {(c[0] + dx, c[1] + dy) for dx, dy in _STEP.values()} & land
            for c in used:
                seeds |= {(c[0] + dx, c[1] + dy) for dx, dy in _STEP.values()} & land
            seen, stack = set(), list(seeds)
            while stack:
                c = stack.pop()
                if c in seen:
                    continue
                seen.add(c)
                stack.extend(q for q in ((c[0] + dx, c[1] + dy) for dx, dy in _STEP.values()) if q in land)
            n += len(land - seen)
    return n


#: The unseen plans' minimal stacked corridors: a corridor on each storey,
#: rooms on both sides, the stair asked at each corridor's west wall.
STACKED = {
    "name": "stacked", "front": "s", "entrance": {"room": "lobby", "kind": "door"}, "blocks": [], "storeys": [],
    "rooms": [_room("lobby", "entryway", 0, [{"to": "c0", "side": "n", "kind": "door"}], area=9),
              _room("c0", "corridor", 0, [{"to": "r1", "side": "n", "kind": "door", "order": 1},
                                          {"to": "r2", "side": "n", "kind": "door", "order": 2},
                                          {"to": "r3", "side": "s", "kind": "door"}]),
              _room("r1", "office", 0, area=12), _room("r2", "storage", 0, area=10),
              _room("r3", "kitchen", 0, area=14),
              _room("c1", "corridor", 1, [{"to": "u1", "side": "n", "kind": "door", "order": 1},
                                          {"to": "u2", "side": "n", "kind": "door", "order": 2},
                                          {"to": "u3", "side": "s", "kind": "door", "order": 1},
                                          {"to": "u4", "side": "s", "kind": "door", "order": 2}])]
    + [_room(f"u{k}", "bedroom", 1, area=12) for k in (1, 2, 3, 4)],
    "stairs": [_stair("c0__c1", "c0", "c1", "w", "w")]}

#: The unseen farmhouse's byre, minimal: a cross passage, a byre stated at
#: 36 m2 with its hayloft ladder asked on its east wall, the loft over it.
BYRE = {
    "name": "byre", "front": "s", "entrance": {"room": "passage", "kind": "door"}, "blocks": [], "storeys": [],
    "rooms": [_room("passage", "entryway", 0, [{"to": "byre", "side": "e", "kind": "door"},
                                               {"to": "orchard", "side": "n", "kind": "door"}], area=6),
              _room("byre", "other", 0, [{"to": "farmyard", "side": "s", "kind": "door"}], area=36),
              _room("loft", "storage", 1, area=30)],
    "stairs": [_stair("byre__loft", "byre", "loft", "e", "e", kind="ladder", enclosed=False, name="ladder")],
    "grounds": {"areas": [{"id": "farmyard", "name": "Farmyard", "kind": "yard", "where": "s"},
                          {"id": "orchard", "name": "Orchard", "kind": "yard", "where": "n"}]}}

#: The code review's e26: a hall asking a room and a straight stair both on
#: its north wall.
ONE_WALL = {
    "name": "onewall", "front": "s", "entrance": {"room": "hall", "kind": "door"}, "blocks": [], "storeys": [],
    "rooms": [_room("hall", "hall", 0, [{"to": "a", "side": "n", "kind": "door"}]), _room("a", "bedroom", 0),
              _room("up", "bedroom", 1)],
    "stairs": [_stair("s", "hall", "up", "n", "n", enclosed=False)]}

#: Two stacked corridors with rooms both sides and the stair asked off both
#: corridors' north sides -- the unseen hospital's wing at a size searched
#: wide: the ground's hall shares the north row's depth.
WARD = {
    "name": "ward", "front": "s", "entrance": {"room": "hall", "kind": "door"}, "blocks": [], "storeys": [],
    "rooms": [_room("hall", "entryway", 0, [{"to": "c0", "side": "n", "kind": "door"}], area=9),
              _room("c0", "corridor", 0, [{"to": "k1", "side": "n", "kind": "door", "order": 1},
                                          {"to": "k2", "side": "n", "kind": "door", "order": 3},
                                          {"to": "s1", "side": "s", "kind": "door", "order": 1},
                                          {"to": "hall", "side": "s", "kind": "door", "order": 2}]),
              _room("k1", "office", 0, area=14), _room("k2", "office", 0, area=14),
              _room("s1", "kitchen", 0, area=16),
              _room("c1", "corridor", 1, [{"to": "u1", "side": "n", "kind": "door", "order": 1},
                                          {"to": "u2", "side": "n", "kind": "door", "order": 3},
                                          {"to": "v1", "side": "s", "kind": "door", "order": 1},
                                          {"to": "v2", "side": "s", "kind": "door", "order": 2}])]
    + [_room(r, "bedroom", 1, area=14) for r in ("u1", "u2", "v1", "v2")],
    "stairs": [_stair("main", "c0", "c1", "n", "n")]}

#: The visual review's shrine skeleton (its repro r2): six rooms, a stair up
#: from the hall's north wall and a cellar stair down from it.
SKELETON = {
    "name": "skeleton", "front": "s", "entrance": {"room": "genkan", "kind": "door"}, "blocks": [], "storeys": [],
    "rooms": [_room("genkan", "entryway", 0, [{"to": "hall", "kind": "open", "side": "n"}]),
              _room("hall", "living", 0, [{"to": "washroom", "kind": "open", "side": "w"}], area=19.8),
              _room("kitchen", "kitchen", 0, [{"to": "hall", "kind": "open", "side": "w"}], area=9.9),
              _room("washroom", "bath", 0), _room("cellar", "cellar", -1), _room("upper", "bedroom", 1)],
    "stairs": [_stair("up", "hall", "upper", "n", "n", name="up stair"),
               _stair("down", "cellar", "hall", "s", "n", name="cellar stair")]}

#: The visual review's roost: a roof room's south gable window above the
#: stair that climbs to that same wall, a writing desk set by the window, the
#: storey below a hallway with a meditation room and a bedroom off it (the
#: shrine's own rooms).
ROOST = {
    "name": "roost", "front": "s", "entrance": {"room": "hall", "kind": "door"}, "blocks": [],
    "storeys": [{"level": 2, "smaller": True}],
    "rooms": [_room("hall", "living", 0, area=45),
              _room("landing", "hallway", 1, [{"to": "meditation", "kind": "door", "side": "e", "order": 1},
                                              {"to": "bedroom", "kind": "door", "side": "e", "order": 2}]),
              _room("meditation", "meditation", 1, windows=[{"id": "w_m", "side": "e", "count": 1}], area=7.4),
              _room("bedroom", "bedroom", 1, windows=[{"id": "w_b", "side": "e", "count": 1}], area=9.9),
              _room("roost", "attic", 2, windows=[{"id": "gable", "side": "s", "count": 1}], area=16,
                    fixtures=[{"id": "writing_desk", "name": "Low writing desk", "kind": "writing_desk", "at": "s",
                               "near": "gable"}])],
    "stairs": [_stair("up", "hall", "landing", "n", "n"), _stair("roof", "landing", "roost", "s", "s", name="roof stair")]}

#: The unseen farmhouse's hayloft, minimal: a cross passage between the
#: house place and the byre, a loft reached only by the ladder from the byre.
HAYLOFT = {
    "name": "hayloft", "front": "s", "entrance": {"room": "passage", "kind": "door"}, "blocks": [], "storeys": [],
    "rooms": [_room("passage", "entryway", 0, [{"to": "house", "side": "w", "kind": "door"},
                                               {"to": "byre", "side": "e", "kind": "door"}], area=6),
              _room("house", "living", 0, area=24), _room("byre", "other", 0, area=24),
              _room("loft", "storage", 1, area=20)],
    "stairs": [_stair("ladder", "byre", "loft", None, None, kind="ladder", enclosed=False, name="ladder")]}

#: The unseen watchtower, minimal: a tower foot and a guardroom beside it, a
#: chamber and a watch room above, a spiral stair asked on each north wall.
TOWER = {
    "name": "tower", "front": "s", "entrance": {"room": "guardroom", "kind": "door"}, "blocks": [], "storeys": [],
    "rooms": [_room("foot", "storage", 0, [{"to": "guardroom", "side": "e", "kind": "door"}], area=12),
              _room("guardroom", "living", 0, area=24),
              _room("chamber", "bedroom", 1, windows=[{"id": "slit_n", "side": "n", "count": 1}], area=12),
              _room("watch", "other", 2, windows=[{"id": "watch_n", "side": "n", "count": 1}], area=12)],
    "stairs": [_stair("t1", "foot", "chamber", "n", "n", kind="spiral", enclosed=False, name="tower stair"),
               _stair("t2", "chamber", "watch", "n", "n", kind="spiral", enclosed=False, name="tower stair")]}


def test_corridors_stacked_with_the_stair_at_their_end_turn_it_back_on_itself():
    # both corridors meet a straight flight at one end wherever it stands:
    # it turns to a U, and the layout says why
    lay = A.solve_arranged(copy.deepcopy(STACKED))
    assert _climbable(lay) == []
    well = next(w for w in lay.stairwells if w["id"] == "c0__c1")
    assert well["kind"] == "u"
    assert any("could not be climbed" in w and "u stair" in w for w in lay.warnings)


def test_a_flight_the_rooms_can_climb_stays_straight():
    # the minimal plan with the stair asked on the corridors' north walls:
    # the flight runs along them, climbed from one end below and the other
    # above -- no turn
    spec = copy.deepcopy(STACKED)
    spec["stairs"] = [_stair("c0__c1", "c0", "c1", "n", "n")]
    lay = A.solve_arranged(spec)
    assert _climbable(lay) == []
    assert next(w for w in lay.stairwells if w["id"] == "c0__c1")["kind"] == "straight"


def test_a_room_beside_a_stair_hall_keeps_its_stated_size():
    # the byre's band is the ladder hall's: the hall takes a landing past its
    # cap rather than cut the byre to its own depth (8.4 m2 of a stated 36)
    lay = A.solve_arranged(copy.deepcopy(BYRE))
    byre = lay.floors[0]["byre"][0]
    stated = 36 / 0.75 ** 2
    assert byre.w * byre.d >= 0.8 * stated
    hall = lay.floors[0]["byre__loft@0"][0]
    assert hall.w * hall.d > 6                     # past the cap, and the layout's own reading says so


def test_a_landing_past_the_cap_is_never_slack():
    # a hall alone in a storey wholly floor has nothing to buy: within its cap
    assert A._hall_past(5, 2, 7, 2) == 0
    assert A._hall_past(5, 2, 5, 3) == 5          # a row across the run past the cap
    assert A._hall_past(5, 2, 5, 9) is None       # past LANDING_OVER_CEILING times the least hall
    lone = {"name": "lone", "front": "s", "entrance": {"room": "hall", "kind": "door"}, "blocks": [], "storeys": [],
            "rooms": [_room("hall", "living", 0, area=30), _room("up", "bedroom", 1, area=12)],
            "stairs": [_stair("s", "hall", "up", "n", "n")]}
    lay = A.solve_arranged(lone)
    hall = lay.floors[0]["s@0"][0]
    assert hall.w * hall.d <= 10 + 5               # the sensible check's one landing


def test_the_storey_above_keeps_the_landing_in_front_of_its_flight():
    # the ground's hall takes a landing past its cap to share the north
    # row's depth; the corridor above meets the flight only across that
    # landing, which its storey keeps: the stair stands off both corridors'
    # north sides as asked, climbable, no wall given way
    lay = A.solve_arranged(copy.deepcopy(WARD))
    assert not [w for w in lay.warnings if "main" in w.lower() or "stair" in w.lower()]
    assert _climbable(lay) == []
    assert lay.floors[1]["main@1"][0] == lay.floors[0]["main@0"][0]
    c0, c1 = lay.floors[0]["c0"][0], lay.floors[1]["c1"][0]
    hall = lay.floors[0]["main@0"][0]
    assert hall.y + hall.d == c0.y and hall.y + hall.d == c1.y   # north of both corridors


def test_a_room_and_a_straight_stair_share_the_wall_they_are_asked_on():
    # the code review's e26: the flight runs along the hall's north wall
    # beside the room, its landing between the flight and the hall -- not
    # end-on, not sealed behind the flight
    lay = A.solve_arranged(copy.deepcopy(ONE_WALL))
    f = Rect(**next(w for w in lay.stairwells if w["id"] == "s")["rect"])
    assert f.w > f.d                                   # along the north wall
    a, hall = lay.floors[0]["a"][0], lay.floors[0]["hall"][0]
    assert a.y + a.d == hall.y                         # the room still north of the hall
    assert _climbable(lay) == []
    assert _sealed(lay) == 0


def test_a_landing_lies_where_its_storey_reaches_it():
    # the visual review's shrine skeleton: the cellar stair's landing lay
    # past the flight's foot on the ground, where no doorway reaches it
    lay = A.solve_arranged(copy.deepcopy(SKELETON))
    assert _sealed(lay) == 0
    assert _climbable(lay) == []


def test_the_desk_set_by_a_window_stands_beneath_it():
    # the window over the stair's landing below, past the flight's end: the
    # landing is the window's cell and the desk's width, and the roost runs
    # that far past the flight -- one cell put the window beside the arrival
    # door and the desk elsewhere
    lay = A.solve_arranged(copy.deepcopy(ROOST))
    win = next(w for w in lay.windows if w["room"] == "roost" and w["side"] == "s")
    desk = next(f for f in lay.fixtures["roost"] if f["id"] == "writing_desk")
    assert tuple(win["cell"]) in _cells(desk["rect"])


def _doubled(lay):
    """{(level, room, cell): [doorways]} for every cell of a room two doorways
    open from."""
    seen = {}
    for d in lay.doors:
        if d.get("outside"):
            continue
        dx, dy = _STEP[d["side"]]
        c = tuple(d["cell"])
        for room, cell in ((d["a"], c), (d["b"], (c[0] + dx, c[1] + dy))):
            seen.setdefault((d["level"], room, cell), []).append(d)
    return {k: v for k, v in seen.items() if len(v) > 1}


def test_no_room_opens_two_doorways_from_one_cell_save_where_two_paces_cost_a_stated_size(monkeypatch):
    # the lab's fresh run 2: the hallway's corner cell held the arrival door
    # of the stair and the meditation room's door. Since the fix round's
    # phase 3 the stair head's second pace is a price (HEAD_SHARED_COST),
    # not a rule: a room meets the corridor at the stair's head by one pace,
    # its doorway sharing that cell with the stair's arrival, only where two
    # paces cost a size the plan states. On run 2 they do -- held as a rule,
    # the main hall is laid 10 x 5, 50 cells against a stated 35.6; on the
    # ground the price lays, two paces cost Hinami's room a row (15 cells
    # against a stated 17.8, past its band) and more roof
    spec = json.loads((_BASELINES / "fresh_runs" / "run2.json").read_text())["spec"]
    stated = {r["id"]: r["area_m2"] / (0.75 * 0.75) for r in spec["rooms"] if r.get("area_m2")}

    def within(lay, rid):
        r = lay.floors[0][rid][0]
        return abs(r.w * r.d - stated[rid]) <= max(A.STATED_BAND * stated[rid], A.STATED_SLACK)

    lay = A.solve_arranged(copy.deepcopy(spec))
    assert within(lay, "main_hall")
    # a cell two doorways open from is one a room meets at a single pace of
    # wall: no free second cell to spread to (wherever there is one, they
    # spread -- test_the_labs_own_doors_spread_as_before_and_the_cores_stand_apart)
    for (lv, _room, _cell), doors in _doubled(lay).items():
        assert any(len(_shared_wall(lay.floors[lv][d["a"]][0], lay.floors[lv][d["b"]][0])[1]) == 1
                   for d in doors), doors
    # ...and held as a rule, no cell holds two doorways, and the stated main
    # hall is laid past its band
    monkeypatch.setattr(A, "HEAD_SHARED_COST", A.INF)
    hard = A.solve_arranged(copy.deepcopy(spec))
    assert _doubled(hard) == {}
    assert not within(hard, "main_hall")


def test_the_labs_own_doors_spread_as_before_and_the_cores_stand_apart():
    # a hallway whose corner cell is the only cell it shares with the room
    # south of it, and one of two it shares with the room west: the lab's
    # spread (`apart` off, `layout_solver.solve`) opens both doorways from
    # that cell, as it always has; the core's path opens the second from the
    # wall's other cell
    def doors(apart):
        layout = Layout(name="corner")
        layout.floors = {0: {"hall": [Rect(0, 0, 2, 4)], "west": [Rect(-3, 2, 3, 2)],
                             "south": [Rect(-2, 4, 3, 3)]}}
        rooms = {"hall": {"id": "hall", "purpose": "hallway",
                          "joins": [{"to": "south", "kind": "door"}, {"to": "west", "kind": "door"}]},
                 "west": {"id": "west", "purpose": "bedroom", "joins": []},
                 "south": {"id": "south", "purpose": "bedroom", "joins": []}}
        _place_doors(layout, rooms, set(), apart=apart)
        return {d["b"]: tuple(d["cell"]) for d in layout.doors if d["a"] == "hall"}

    lab = doors(False)
    assert lab["south"] == lab["west"] == (0, 3)
    core = doors(True)
    assert core["south"] == (0, 3) and core["west"] == (0, 2)


def test_a_tower_rises_sheer_over_its_stair():
    # the spiral's landing below is kept on every storey above: no notch of
    # roof beside the stair, storey over storey
    lay = A.solve_arranged(copy.deepcopy(TOWER))
    assert all(not lay.roofs.get(lv) for lv in (1, 2))
    hall0 = lay.floors[0]["t1@0"][0]
    for lv in (1, 2):
        assert lay.floors[lv]["t1@%d" % lv][0] == hall0


def test_a_loft_stands_over_the_room_its_ladder_climbs_from():
    # the unseen farmhouse: a loft "over the byre, reached only by the ladder
    # from the byre" stood over the house place
    lay = A.solve_arranged(copy.deepcopy(HAYLOFT))
    loft, byre = lay.floors[1]["loft"][0], lay.floors[0]["byre"][0]
    assert len(_cells(loft) & _cells(byre)) * 2 > len(_cells(loft))
