"""The layout prototype keeps what its design promises (world/layout_solver.py).

Hand-made buildings, never model output: each test names one promise of the
design -- rooms are whole rectangles filling their block's outline, stairs
line up and have floor before them, an enclosed stair is walled with a
door, a zone is floor in its room, the grounds are open ground with things
standing in them by plain relations.
"""

from world.layout_solver import Rect, check, solve

HOUSE = {
    "name": "test house", "front": "s",
    "entrance": {"room": "hall", "zone": "step", "kind": "door"},
    "storeys": [{"level": 2, "smaller": True}],
    "rooms": [
        {"id": "hall", "name": "Hall", "level": 0, "purpose": "living",
         "joins": [{"to": "kitchen", "side": "w"}, {"to": "store", "side": "e"}],
         "zones": [{"id": "step", "name": "Entry step", "by": "entrance", "size": "medium"},
                   {"id": "sitting", "name": "Sitting area", "at": "middle", "size": "large"}],
         "fixtures": [{"id": "rack", "name": "Shoe rack", "kind": "shelf", "in": "step"},
                      {"id": "table", "name": "Low table", "kind": "low_table", "in": "sitting"},
                      {"id": "alcove", "name": "Alcove", "kind": "tokonoma", "at": "n"}]},
        {"id": "kitchen", "name": "Kitchen", "level": 0, "purpose": "kitchen",
         "fixtures": [{"id": "stove", "name": "Stove", "kind": "stove", "at": "w"},
                      {"id": "basin", "name": "Basin", "kind": "basin"}]},
        {"id": "store", "name": "Store", "level": 0, "purpose": "storage",
         "fixtures": [{"id": "shelf", "name": "Shelf", "kind": "shelf"}]},
        {"id": "corridor", "name": "Corridor", "level": 1, "purpose": "hallway",
         "joins": [{"to": "bed_a", "side": "e", "order": 1}, {"to": "bed_b", "side": "e", "order": 2}]},
        {"id": "bed_a", "name": "Bedroom A", "level": 1, "purpose": "bedroom",
         "fixtures": [{"id": "bed1", "name": "Bed", "kind": "futon"}]},
        {"id": "bed_b", "name": "Bedroom B", "level": 1, "purpose": "bedroom",
         "fixtures": [{"id": "bed2", "name": "Bed", "kind": "futon"}, {"id": "chest", "name": "Chest", "kind": "chest"}]},
        {"id": "loft", "name": "Loft", "level": 2, "purpose": "attic",
         "fixtures": [{"id": "nest", "name": "Nest", "kind": "futon", "at": "middle"}]},
    ],
    "stairs": [
        {"id": "up", "name": "Stair up", "from": "hall", "to": "corridor", "enclosed": False,
         "from_at": "n", "to_at": "s"},
        {"id": "loft_stair", "name": "Loft stair", "from": "corridor", "to": "loft", "enclosed": True,
         "door": "shoji", "from_at": "n"},
    ],
    "grounds": {
        "areas": [{"id": "garden", "name": "Garden", "kind": "garden", "where": "around"}],
        "ways": [{"id": "approach", "name": "Approach", "from": "entrance"}],
        "features": [
            {"id": "gate", "name": "Gate", "kind": "gate", "across": "approach", "end": "far"},
            {"id": "guard", "name": "Guardian", "kind": "statue", "flank": "approach", "end": "far", "count": 2},
            {"id": "lamp", "name": "Lantern", "kind": "lantern", "along": "approach", "count": 4},
            {"id": "well", "name": "Well", "kind": "well", "by": "entrance"},
            {"id": "tree", "name": "Tree", "kind": "tree", "side": "n"},
        ],
    },
    "elsewhere": [{"name": "The far valley", "why": "seen from the gate"}],
}

TOWER = {
    "name": "test light", "front": "s",
    "entrance": {"room": "kitchen"},
    "blocks": [{"id": "tower", "beside": {"block": "cottage", "side": "w"}}],
    "rooms": [
        {"id": "kitchen", "name": "Kitchen", "level": 0, "block": "cottage", "purpose": "kitchen",
         "joins": [{"to": "bedroom", "side": "n"}, {"to": "base", "side": "w"}],
         "fixtures": [{"id": "range", "name": "Range", "kind": "stove"}, {"id": "t", "name": "Table", "kind": "table"}]},
        {"id": "bedroom", "name": "Bedroom", "level": 0, "block": "cottage", "purpose": "bedroom",
         "fixtures": [{"id": "b", "name": "Bed", "kind": "bed"}]},
        {"id": "base", "name": "Store", "level": 0, "block": "tower", "purpose": "storage"},
        {"id": "mid", "name": "Watch room", "level": 1, "block": "tower", "purpose": "study",
         "fixtures": [{"id": "desk", "name": "Desk", "kind": "desk"}]},
        {"id": "top", "name": "Lamp room", "level": 2, "block": "tower", "purpose": "other",
         "fixtures": [{"id": "lamp", "name": "Lamp", "kind": "lamp", "at": "middle"}]},
    ],
    "stairs": [
        {"id": "s1", "name": "Tower stair", "from": "base", "to": "mid", "kind": "spiral"},
        {"id": "s2", "name": "Tower stair", "from": "mid", "to": "top", "kind": "spiral"},
    ],
}


def _house():
    return solve(HOUSE)


def test_every_room_is_one_rectangle_filling_its_outline():
    assert check(_house()) == []
    assert check(solve(TOWER)) == []


def test_a_storey_under_the_roof_is_inset_in_the_outline():
    lay = _house()
    full, roof = lay.outlines["main"][1], lay.outlines["main"][2]
    assert full.contains(roof) and roof.w * roof.d < full.w * full.d


def test_every_join_between_rooms_has_a_doorway():
    lay = _house()
    pairs = {tuple(sorted((d["a"], d["b"]))) for d in lay.doors}
    for a, b in (("hall", "kitchen"), ("hall", "store"), ("corridor", "bed_a"), ("corridor", "bed_b")):
        assert (a, b) in pairs or (b, a) in pairs


def test_the_entrance_opens_on_the_front_and_its_zone_holds_the_door():
    lay = _house()
    door = next(d for d in lay.doors if d["b"] == "entrance")
    assert door["a"] == "hall" and door["side"] == "s"
    step = next(z for z in lay.zones["hall"] if z["id"] == "step")
    assert tuple(door["cell"]) in step["rect"].cells()
    rack = next(f for f in lay.fixtures["hall"] if f["id"] == "rack")
    assert step["rect"].contains(rack["rect"])


def test_the_approach_runs_out_of_the_front_with_its_gate_at_the_far_end():
    lay = _house()
    house = lay.outlines["main"][0]
    way = lay.ways["approach"]
    assert way["side"] == "s" and min(c[1] for c in way["cells"]) >= house.y + house.d
    gate = next(f for f in lay.features if f["id"] == "gate")
    xs = {c[0] for c in way["cells"]}
    assert gate["rect"].w >= len(xs)                       # spans the way
    assert gate["rect"].y == max(c[1] for c in way["cells"])  # at its far end
    guards = [f for f in lay.features if f["id"].startswith("guard")]
    assert len(guards) == 2 and all(not (g["rect"].cells() & way["cells"]) for g in guards)


def test_features_stand_by_what_they_name_and_behind_when_asked():
    lay = _house()
    house = lay.outlines["main"][0]
    tree = next(f for f in lay.features if f["id"] == "tree")
    assert tree["rect"].y + tree["rect"].d <= house.y      # behind: the front is south
    well = next(f for f in lay.features if f["id"] == "well")
    door = next(d for d in lay.doors if d["b"] == "entrance")
    assert abs(well["rect"].x - door["cell"][0]) + abs(well["rect"].y - door["cell"][1]) <= 6
    for f in lay.features:
        assert not (f["rect"].cells() & house.cells())


def test_the_layout_is_the_same_every_time():
    assert _house().as_dict() == _house().as_dict()


def test_an_open_stair_up_and_an_enclosed_stair_down_are_two_stairs():
    spec = {
        "name": "two stairs", "front": "s", "entrance": {"room": "hall"},
        "rooms": [
            {"id": "hall", "level": 0, "purpose": "common room", "joins": [{"to": "back", "side": "n"}]},
            {"id": "back", "level": 0, "purpose": "kitchen", "fixtures": [{"id": "r", "kind": "stove"}]},
            {"id": "up", "level": 1, "purpose": "hallway", "joins": [{"to": "bed", "side": "s"}]},
            {"id": "bed", "level": 1, "purpose": "bedroom", "fixtures": [{"id": "b", "kind": "bed"}]},
            {"id": "cellar", "level": -1, "purpose": "cellar"},
        ],
        "stairs": [
            {"id": "s_up", "from": "hall", "to": "up", "enclosed": False},
            {"id": "s_down", "from": "hall", "to": "cellar", "enclosed": True, "door": "low door"},
        ],
    }
    lay = solve(spec)
    wells = {s["id"]: Rect(**s["rect"]) for s in lay.stairwells}
    assert set(wells) == {"s_up", "s_down"}
    assert not wells["s_up"].overlaps(wells["s_down"])


def test_a_storey_of_one_room_never_decides_where_stairs_stand():
    """The cellar is one room: it takes the stair wherever the floor above
    puts it, so the floor above keeps the kitchen behind the hall."""
    spec = {
        "name": "cellar last", "front": "s", "entrance": {"room": "hall"},
        "rooms": [
            {"id": "hall", "level": 0, "purpose": "common room", "joins": [{"to": "kitchen", "side": "n"}]},
            {"id": "kitchen", "level": 0, "purpose": "kitchen", "fixtures": [{"id": "r", "kind": "stove"}]},
            {"id": "cellar", "level": -1, "purpose": "cellar"},
        ],
        "stairs": [{"id": "down", "from": "hall", "to": "cellar", "enclosed": True, "from_at": "n", "to_at": "n"}],
    }
    lay = solve(spec)
    hall, kitchen = lay.floors[0]["hall"][0], lay.floors[0]["kitchen"][0]
    assert kitchen.y + kitchen.d == hall.y                 # the kitchen is behind the hall
    assert not [w for w in lay.warnings if "Kitchen" in w or "kitchen" in w and "side" in w]


def test_a_storey_that_holds_less_covers_part_of_the_building():
    spec = {
        "name": "part storey", "front": "s", "entrance": {"room": "hall"},
        "rooms": [
            {"id": "hall", "level": 0, "purpose": "hall", "size": "huge", "joins": [{"to": "k", "side": "n"}],
             "fixtures": [{"id": f"t{i}", "kind": "table"} for i in range(6)]},
            {"id": "k", "level": 0, "purpose": "kitchen", "fixtures": [{"id": "s", "kind": "stove"}]},
            {"id": "loft", "level": 1, "purpose": "bedroom", "fixtures": [{"id": "b", "kind": "bed"}]},
        ],
        "stairs": [{"id": "up", "from": "hall", "to": "loft", "enclosed": False}],
    }
    lay = solve(spec)
    ground, upper = lay.outlines["main"][0], lay.outlines["main"][1]
    assert ground.contains(upper) and upper.w * upper.d < 0.7 * ground.w * ground.d
    assert check(lay) == [] and {s["id"] for s in lay.stairwells} == {"up"}


def test_an_upper_storey_stands_within_the_one_below():
    for spec in (HOUSE, TOWER):
        lay = solve(spec)
        for b, levels in lay.outlines.items():
            for lv, o in levels.items():
                if lv > 0 and lv - 1 in levels:
                    assert levels[lv - 1].contains(o), (b, lv)


ROOMY = {
    "name": "furnishing", "front": "s", "entrance": {"room": "hall"},
    "rooms": [
        {"id": "hall", "level": 0, "purpose": "living", "joins": [{"to": "bath", "side": "e"}],
         "windows": [{"id": "hw", "side": "s"}, {"id": "inner", "side": "e"}],
         "fixtures": [
             {"id": "alcove", "kind": "tokonoma", "at": "n"},
             {"id": "vase", "kind": "vase", "mount": "in alcove"},
             {"id": "scroll", "kind": "scroll", "mount": "hung"},
             {"id": "bar", "kind": "bar", "mount": "wall", "at": "w"},
             {"id": "lamps", "kind": "lantern", "mount": "ceiling", "count": 3},
             {"id": "pools", "kind": "pond", "count": 4, "at": "walls"},
             {"id": "seat", "kind": "cushion", "near": "hw"}]},
        {"id": "bath", "level": 0, "purpose": "washroom",
         "fixtures": [{"id": "tub", "kind": "tub", "size": "large"}]},
    ],
}


def test_things_on_walls_ceilings_or_in_other_fixtures_take_no_floor():
    lay = solve(ROOMY)
    placed = {f["id"] for f in lay.fixtures["hall"]}
    assert not placed & {"vase", "scroll", "lamps", "lamps_1"}
    assert {d["id"] for d in lay.details["hall"]} == {"scroll", "lamps"}
    assert "bar" in placed                                   # against a wall is on the floor
    assert [c["id"] for c in lay.contents["hall"]["alcove"]] == ["vase"]


def test_several_alike_along_the_walls_go_round_the_walls():
    lay = solve(ROOMY)
    pools = [f for f in lay.fixtures["hall"] if f["id"].startswith("pools_")]
    assert len(pools) == 4
    assert len({f["at"] for f in pools}) >= 3


def test_a_size_word_scales_a_known_kind():
    lay = solve(ROOMY)
    tub = next(f for f in lay.fixtures["bath"] if f["id"] == "tub")
    assert tub["rect"].w * tub["rect"].d > 4                 # larger than a plain 2x2 tub


def test_a_window_is_on_an_outside_wall():
    lay = solve(ROOMY)
    wins = {w["id"]: w for w in lay.windows}
    assert wins["hw"]["side"] == "s"
    assert wins["inner"]["side"] != "e"                      # the east wall is the bath's
    hall = lay.floors[0]["hall"][0]
    outline = lay.outlines["main"][0]
    for w in wins.values():
        x, y = w["cell"]
        dx, dy = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}[w["side"]]
        assert (x, y) in hall.cells() and (x + dx, y + dy) not in outline.cells()


def test_a_zone_is_big_enough_for_what_stands_in_it():
    spec = {"name": "z", "front": "s", "entrance": {"room": "hall"},
            "rooms": [{"id": "hall", "level": 0, "purpose": "living",
                       "zones": [{"id": "sit", "at": "middle", "size": "small"}],
                       "fixtures": [{"id": "t", "kind": "chabudai", "in": "sit"},
                                    {"id": "c", "kind": "cushion", "in": "sit", "count": 4},
                                    {"id": "b", "kind": "basin", "in": "sit"}]}]}
    lay = solve(spec)
    assert not lay.unplaced
    zone = lay.zones["hall"][0]["rect"]
    assert all(zone.contains(f["rect"]) for f in lay.fixtures["hall"])


def test_every_stair_is_a_hall_at_the_same_cells_on_each_storey_it_joins():
    lay = _house()
    assert {s["id"] for s in lay.stairwells} == {"up", "loft_stair"}
    for s in lay.stairwells:
        rect = Rect(**s["rect"])
        for lv in s["levels"]:
            assert lay.floors[lv][s["halls"][str(lv)]][0].contains(rect)
    # each hall opens onto the rooms its flight serves
    pairs = {(d["a"], d["b"]) for d in lay.doors} | {(d["b"], d["a"]) for d in lay.doors}
    assert ("up@0", "hall") in pairs and ("up@1", "corridor") in pairs
    assert ("loft_stair@1", "corridor") in pairs and ("loft_stair@2", "loft") in pairs


def test_an_enclosed_stair_has_its_door_and_an_open_one_is_open_to_its_room():
    lay = _house()
    loft = [d for d in lay.doors if "loft_stair@" in d["a"] + d["b"]]
    assert loft and all(d["kind"] == "shoji" for d in loft)
    up = [d for d in lay.doors if "up@" in d["a"] + d["b"]]
    assert up and all(d["kind"] == "open" and len(d["span"]) >= 1 for d in up)


def test_fixtures_never_cut_a_rooms_doorways_off_from_each_other():
    lay = _house()
    for lv, parts in lay.floors.items():
        for rid, rects in parts.items():
            cells = rects[0].cells()
            for f in lay.fixtures.get(rid, ()):
                cells -= f["rect"].cells()
            own = [tuple(d["cell"]) for d in lay.doors if d["level"] == lv and d["a"] == rid]
            own = [c for c in own if c in cells]
            seen, stack = set(), own[:1]
            while stack:
                c = stack.pop()
                if c in seen or c not in cells:
                    continue
                seen.add(c)
                stack += [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]
            assert all(c in seen for c in own), rid


def test_a_tower_beside_a_cottage_climbs_by_one_spiral_through_its_storeys():
    lay = solve(TOWER)
    tower, cottage = lay.outlines["tower"][0], lay.outlines["cottage"][0]
    assert tower.x + tower.w == cottage.x
    assert tower.w * tower.d < cottage.w * cottage.d
    assert len(lay.stairwells) == 1
    shaft = lay.stairwells[0]
    assert shaft["kind"] == "spiral" and shaft["levels"] == [0, 1, 2] and shaft["flights"] == ["s1", "s2"]


def test_the_stair_shape_follows_the_building_unless_the_spec_names_one():
    def stair_kind(spec):
        return {s["id"]: s["kind"] for s in solve(spec).stairwells}

    three = {"name": "three", "front": "s", "entrance": {"room": "a0"},
             "rooms": [{"id": f"{n}{lv}", "level": lv, "purpose": "bedroom",
                        "fixtures": [{"id": f"b{n}{lv}", "kind": "bed"}],
                        "joins": [{"to": f"b{lv}", "side": "e"}] if n == "a" else []}
                       for lv in (0, 1, 2) for n in ("a", "b")],
             "stairs": [{"id": "s1", "from": "a0", "to": "a1"}, {"id": "s2", "from": "a1", "to": "a2"}]}
    assert stair_kind(three) == {"s1": "u"}                   # stacked through three storeys
    named = dict(three, stairs=[dict(st, kind="spiral") for st in three["stairs"]])
    assert stair_kind(named) == {"s1": "spiral"}


def test_floor_beyond_every_room_s_ceiling_is_a_store_not_a_bigger_room():
    spec = {"name": "spare", "front": "s", "entrance": {"room": "hall"},
            "rooms": [{"id": "hall", "level": 0, "purpose": "hall", "size": "huge",
                       "fixtures": [{"id": f"t{i}", "kind": "table"} for i in range(10)]},
                      {"id": "up", "level": 1, "purpose": "bedroom", "joins": [{"to": "closet", "side": "e"}],
                       "fixtures": [{"id": "b", "kind": "bed"}]},
                      {"id": "closet", "level": 1, "purpose": "closet"}],
            "storeys": [],
            "stairs": [{"id": "s", "from": "hall", "to": "up"}]}
    lay = solve(spec)
    assert check(lay) == []
    bed = lay.floors[1]["up"][0]
    assert bed.w * bed.d <= 36 * 1.4 + 1


def test_rooms_are_near_square():
    # the cutter's own test: no roof storey pinning a stair mid-building
    roomy = dict(HOUSE, storeys=[], stairs=[st for st in HOUSE["stairs"] if st["id"] != "loft_stair"],
                 rooms=[dict(r, fixtures=list(r.get("fixtures", [])) +
                             [{"id": f"x_{r['id']}_{i}", "kind": "chest"} for i in range(3)])
                        if r["purpose"] == "bedroom" else r for r in HOUSE["rooms"] if r["id"] != "loft"])
    for spec in (roomy, TOWER):
        lay = solve(spec)
        for lv, parts in lay.floors.items():
            for rid, rects in parts.items():
                r = rects[0]
                if lay.purposes.get(rid) in ("hallway", "corridor", "stair") or rid.startswith("store_"):
                    continue
                # the review's strips ran 3.7:1 (a 3 x 11 cellar); a narrow
                # room beside a stair the roof pins mid-building is allowed
                assert max(r.w, r.d) / min(r.w, r.d) <= 2.7, (rid, r)



TAVERN = {"name": "taproom", "front": "s", "entrance": {"room": "tap"},
          "rooms": [{"id": "tap", "level": 0, "purpose": "common room",
                     "fixtures": [{"id": "bar", "kind": "bar", "at": "n"},
                                  {"id": "table", "kind": "table", "at": "middle"},
                                  {"id": "chairs", "kind": "chair", "near": "table", "count": 4},
                                  {"id": "hearth", "kind": "hearth", "at": "w"}]}]}


def test_a_bar_has_its_server_s_aisle_behind_it():
    lay = solve(TAVERN)
    room = lay.floors[0]["tap"][0]
    bar = next(f for f in lay.fixtures["tap"] if f["id"] == "bar")["rect"]
    assert bar.y > room.y                                   # off the wall it stands along
    behind = {(x, y) for x in range(bar.x, bar.x + bar.w) for y in range(room.y, bar.y)}
    taken = set().union(*(f["rect"].cells() for f in lay.fixtures["tap"]))
    assert behind and not (behind & taken)


def test_seats_stand_round_their_table_and_nothing_else_in_any_use_space():
    lay = solve(TAVERN)
    fx = {f["id"]: f for f in lay.fixtures["tap"]}
    table = fx["table"]["rect"]
    ring = {(x + dx, y + dy) for x, y in table.cells() for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
    seats = [f for k, f in fx.items() if k.startswith("chairs_")]
    assert len(seats) == 4 and all(f["rect"].cells() <= ring for f in seats)
    for f in fx.values():
        for g in fx.values():
            if f is g or (g["id"] == "table" and f["id"].startswith("chairs_")):
                continue
            assert not (f["rect"].cells() & set(map(tuple, g["use"]))), (f["id"], g["id"])


def test_stairs_with_different_names_are_different_stairs():
    """A box staircase up and stone stairs down from one room are two stairs
    in two places, even of one kind; a tower's flights of one name stack."""
    spec = {"name": "two", "front": "s", "entrance": {"room": "hall"},
            "rooms": [{"id": "hall", "level": 0, "purpose": "living",
                       "fixtures": [{"id": "t", "kind": "table", "at": "middle"}]},
                      {"id": "up", "level": 1, "purpose": "hallway", "joins": [{"to": "bed", "side": "e"}]},
                      {"id": "bed", "level": 1, "purpose": "bedroom", "fixtures": [{"id": "b", "kind": "bed"}]},
                      {"id": "down", "level": -1, "purpose": "cellar"}],
            "stairs": [{"id": "box", "name": "box staircase", "from": "hall", "to": "up", "enclosed": True,
                        "kind": "straight"},
                       {"id": "stone", "name": "stone stairs", "from": "hall", "to": "down", "enclosed": True,
                        "kind": "straight"}]}
    lay = solve(spec)
    assert {s["id"] for s in lay.stairwells} == {"box", "stone"}
    assert all(len(s["levels"]) == 2 for s in lay.stairwells)


def test_upper_floor_no_room_takes_at_the_edge_is_roof_and_a_window_may_face_it():
    import copy
    spec = copy.deepcopy(HOUSE)
    for r in spec["rooms"]:
        if r["id"] == "corridor":
            r["windows"] = [{"side": "w", "count": 2}]
        if r["id"] in ("bed_a", "bed_b"):
            r["area_m2"] = 7
    lay = solve(spec)
    assert not check(lay)
    assert lay.roofs.get(1), "the floor the stated rooms leave is roof over the storey below"
    o = lay.outlines["main"][1]
    roof = set().union(*(r.cells() for r in lay.roofs[1]))
    for rf in lay.roofs[1]:
        assert rf.x == o.x or rf.y == o.y or rf.x + rf.w == o.x + o.w or rf.y + rf.d == o.y + o.d
    win = [w for w in lay.windows if w["level"] == 1]
    assert win
    for w in win:
        x, y = w["cell"]
        dx, dy = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}[w["side"]]
        assert (x + dx, y + dy) in roof or (x + dx, y + dy) not in o.cells()
    assert len({(w["room"], tuple(w["cell"]), w["side"]) for w in win}) == len(win), "never two windows in one cell"


def test_a_towers_walls_rise_sheer_so_no_storey_of_it_has_roof():
    lay = solve(TOWER)
    assert not any(lay.roofs.values())


TAPROOM = {"name": "tap", "front": "s", "entrance": {"room": "tap"},
           "rooms": [{"id": "tap", "level": 0, "purpose": "common room", "joins": [{"to": "kitchen", "side": "n"}],
                      "fixtures": [{"id": "bar", "kind": "bar", "at": "n"}, {"id": "t1", "kind": "table"},
                                   {"id": "t2", "kind": "table"}]},
                     {"id": "kitchen", "level": 0, "purpose": "kitchen",
                      "fixtures": [{"id": "range", "kind": "stove", "at": "n"}]},
                     {"id": "landing", "level": 1, "purpose": "corridor",
                      "joins": [{"to": "r1", "side": "s"}, {"to": "r2", "side": "n"}]},
                     {"id": "r1", "level": 1, "purpose": "guest room", "fixtures": [{"id": "b1", "kind": "bed"}]},
                     {"id": "r2", "level": 1, "purpose": "guest room", "fixtures": [{"id": "b2", "kind": "bed"}]}],
           "stairs": [{"id": "up", "name": "narrow stair", "from": "tap", "to": "landing", "enclosed": False}]}


def test_a_quarter_turn_stair_stands_only_where_a_spec_names_one():
    """The owner withdrew L stairs on 2026-10-03 ("I was wrong recommending
    l shaped stairs"), and the fallback went on offering one right after a
    straight flight, so the solver chose an L nobody asked for: this
    taproom's stair was an L, as were both of the lab inn's. A spec that
    names an L by its own word still gets one."""
    from world.layout_solver import STAIR_FALLBACK

    assert "l" not in STAIR_FALLBACK
    unasked = {s["id"]: s["kind"] for s in solve(TAPROOM).stairwells}
    assert unasked == {"up": "straight"}
    asked = dict(TAPROOM, stairs=[dict(TAPROOM["stairs"][0], kind="l")])
    assert {s["id"]: s["kind"] for s in solve(asked).stairwells} == {"up": "l"}


def test_a_storey_under_the_roof_never_sizes_its_block():
    """The owner's shrine (chat 164, 2026-10-10): its roof room's nest was
    asked huge, and the roof storey -- smaller by the roofline -- sized the
    whole building, 20 by 14, its ground floor's spare handed to a stair hall
    20 by 5. A storey under the roof fits itself to the floor below, so what
    it holds never moves the building's outline."""
    import copy
    small, huge = copy.deepcopy(HOUSE), copy.deepcopy(HOUSE)
    loft = next(r for r in huge["rooms"] if r["id"] == "loft")
    loft["fixtures"] = [{"id": "nest", "name": "Nest", "kind": "nest", "size": "huge", "at": "middle"},
                        {"id": "desk", "name": "Desk", "kind": "writing_desk"},
                        {"id": "chest", "name": "Chest", "kind": "chest"},
                        {"id": "screen", "name": "Screen", "kind": "screen", "size": "large"}]
    a, b = solve(small).outlines["main"], solve(huge).outlines["main"]
    assert (a[0], a[1]) == (b[0], b[1])
    assert check(solve(huge)) == []


def test_a_block_of_none_but_storeys_under_the_roof_still_has_an_outline():
    """The one block the rule above leaves nothing to size from -- every
    storey of it under the roof -- is sized from those storeys, as before."""
    import copy
    spec = copy.deepcopy(HOUSE)
    spec["storeys"] = [{"level": 1, "smaller": True}, {"level": 2, "smaller": True}]
    spec["blocks"] = [{"id": "oriel", "beside": {"block": "main", "side": "e"}}]
    spec["rooms"].append({"id": "oriel_room", "name": "Oriel", "level": 1, "block": "oriel",
                          "purpose": "study", "joins": [{"to": "bed_b", "side": "w"}],
                          "fixtures": [{"id": "seat", "name": "Window seat", "kind": "window_seat"}]})
    lay = solve(spec)
    oriel = lay.outlines["oriel"][1]
    assert oriel.w * oriel.d > 0 and "oriel_room" in lay.floors[1]


def test_a_side_a_plan_holds_costs_what_a_missing_doorway_costs():
    """`held` marks a side the PLAN states (`layout_bridge.spec_from_answers`):
    turned, it refuses the plan's building as a missing doorway does, and the
    scoring weighs it so. At the 20 a model's asked side costs, the owner's
    shrine (chat 164, 2026-10-10) traded two held sides for a better-scoring
    stair and was refused for it. Read from whichever room wrote the join."""
    from world.layout_solver import _score
    rooms = {"a": {"id": "a", "purpose": "living", "level": 0, "joins": [{"to": "b", "side": "e"}]},
             "b": {"id": "b", "purpose": "living", "level": 0, "joins": []}}
    parts = {"a": Rect(4, 0, 4, 4), "b": Rect(0, 0, 4, 4)}       # b stands west of a, asked east

    def score():
        return _score(parts, ["a", "b"], rooms, {"a": 16, "b": 16}, Rect(0, 0, 8, 4),
                      {}, {"_front": "s"}, {}, 0)

    asked = score()
    rooms["a"]["joins"][0]["held"] = True
    held_here = score()
    del rooms["a"]["joins"][0]["held"]
    rooms["b"]["joins"].append({"to": "a", "held": True})
    held_there = score()
    assert held_here - asked == 40 == held_there - asked
