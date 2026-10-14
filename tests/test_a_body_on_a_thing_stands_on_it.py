"""A body ON a fixture stands on it; a cell code chooses for any other body
keeps out of every fixture it is not on, and out of every doorway.

The owner, 2026-10-13, reading Home 11's map: "being on the same tile space
as something like a futon or any other input that implies standing or laying
atop a furniture of any kind should... work but it doesn't. A character
overlapping furniture makes sense in some circumstances." The engine already
recorded being on a thing -- a station AT it and a pose whose `support` names
it -- and no reader placed a body by it: measured that day on a copy of the
play database, 55 of the 57 bodies resting on a fixture were drawn a pace off
it, Home 11's Hinami in the trunk beside her futon, Home 7's in the hallway
door. Hand-made rooms; the names are illustrations, not the rule.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

from world.spatial import (
    anchor_cells, body_cell, body_cell_source, body_visibility, feature_visibility,
    merge_scene_with_diff, resting_on,
)

BED = {"desc": "a low bed", "cell": [3, 1], "extent": {"w": 2, "d": 3},
       "footprint": "large", "height": "waist"}


def _scene(anchors, positions, *, stations=None, poses=None, w=8, d=6, adjacent=()):
    room = {"name": "the Room", "desc": "A room.", "exposure": "enclosed", "light": "lit",
            "extent": {"w": w, "d": d}, "anchors": copy.deepcopy(anchors),
            "adjacent": [dict(e) for e in adjacent]}
    rooms = {"r": room}
    for edge in adjacent:
        rooms[edge["to"]] = {"name": edge["to"], "desc": "Beyond.", "exposure": "enclosed",
                             "light": "lit", "extent": {"w": 4, "d": 4}, "anchors": {},
                             "adjacent": []}
    return {"rooms": rooms, "positions": dict(positions), "entities": {},
            "stations": copy.deepcopy(stations or {}), "poses": copy.deepcopy(poses or {}),
            "orientation": {}, "contained": {}}


def _cells(sc, aid, room="r"):
    return {tuple(c) for c in anchor_cells(sc, room)[aid]["cells"]}


LYING = {"posture": "lying on her back", "support": "bed"}


def test_three_records_agreeing_put_a_body_on_a_thing():
    sc = _scene({"bed": BED, "chair": {"desc": "a chair", "cell": [6, 4]}},
                {"Hinami": "r"}, stations={"Hinami": {"at": "bed"}},
                poses={"Hinami": dict(LYING)})
    assert resting_on(sc, "Hinami") == "bed"
    assert tuple(body_cell(sc, "Hinami")) in _cells(sc, "bed")
    assert body_cell_source(sc, "Hinami") == "anchor"
    # at the bed with no pose bearing her on it: beside it, never in it
    sc["poses"] = {}
    assert resting_on(sc, "Hinami") is None
    assert tuple(body_cell(sc, "Hinami")) not in _cells(sc, "bed")
    # a support her station does not stand at says nothing about where she is
    sc["poses"] = {"Hinami": dict(LYING)}
    sc["stations"]["Hinami"] = {"at": "chair"}
    assert resting_on(sc, "Hinami") is None
    # a doorway bears nobody's weight
    sc = _scene({}, {"Hinami": "r"}, stations={"Hinami": {"at": "door:hall"}},
                poses={"Hinami": {"posture": "standing", "support": "door:hall"}},
                adjacent=[{"to": "hall", "barrier": "open_door", "dir": "s"}])
    assert resting_on(sc, "Hinami") is None


def test_two_in_one_bed_take_two_of_its_cells():
    sc = _scene({"bed": BED}, {"Hinami": "r", "Tamamo": "r"},
                stations={"Hinami": {"at": "bed"}, "Tamamo": {"at": "bed"}},
                poses={"Hinami": dict(LYING), "Tamamo": dict(LYING)})
    a, b = tuple(body_cell(sc, "Hinami")), tuple(body_cell(sc, "Tamamo"))
    assert a != b and {a, b} <= _cells(sc, "bed")


def test_a_pin_on_the_bed_stands_and_a_pin_beside_it_gives_way():
    """A host's drop on the bed is a cell of it ("this end of the bed") and
    stands. A pin beside it while her pose and station both put her on it
    is a walk's arrival cell, and is no answer: read, she is drawn on the
    bed; merged, the pin is dropped (F39's reasoning)."""
    sc = _scene({"bed": BED}, {"Hinami": "r"},
                stations={"Hinami": {"at": "bed", "cell": [4, 3]}},
                poses={"Hinami": dict(LYING)})
    assert tuple(body_cell(sc, "Hinami")) == (4, 3)
    assert body_cell_source(sc, "Hinami") == "cell"
    merged = merge_scene_with_diff(sc, {"poses": {"Hinami": dict(LYING)}})
    assert merged["stations"]["Hinami"]["cell"] == [4, 3]

    sc["stations"]["Hinami"]["cell"] = [6, 2]
    assert tuple(body_cell(sc, "Hinami")) in _cells(sc, "bed")
    assert body_cell_source(sc, "Hinami") == "anchor"
    merged = merge_scene_with_diff(sc, {"poses": {"Hinami": dict(LYING)}})
    assert "cell" not in merged["stations"]["Hinami"]
    assert tuple(body_cell(merged, "Hinami")) in _cells(merged, "bed")


def test_a_walk_that_ends_beside_the_bed_she_then_lies_on_leaves_her_on_it():
    """The arrival pin is beside the fixture (`anchor_stand_cell`); the same
    beat lays her down on it."""
    sc = _scene({"bed": BED}, {"Hinami": "r"}, stations={"Hinami": {"at": None, "cell": [0, 5]}})
    merged = merge_scene_with_diff(sc, {
        "stations": {"Hinami": {"at": "bed", "cell": [5, 2]}},
        "poses": {"Hinami": dict(LYING)}})
    assert "cell" not in merged["stations"]["Hinami"]
    assert tuple(body_cell(merged, "Hinami")) in _cells(merged, "bed")


def test_a_body_stepping_off_its_fixture_never_lands_in_another():
    """Home 11's shape: a futon against the west wall, a waist-high trunk
    pinned against its foot. Whatever cell of the futon a body at it is
    dealt, it steps off onto the floor, never into the trunk."""
    anchors = {"futon": {"desc": "a futon", "dir": "w", "cell": [0, 1],
                         "extent": {"w": 2, "d": 2}, "height": "floor"},
               "trunk": {"desc": "a trunk", "cell": [0, 3], "extent": {"w": 3, "d": 2},
                         "height": "waist"}}
    names = [f"Body{i}" for i in range(40)]
    sc = _scene(anchors, {n: "r" for n in names}, stations={n: {"at": "futon"} for n in names})
    held = _cells(sc, "futon") | _cells(sc, "trunk")
    for name in names:
        assert tuple(body_cell(sc, name)) not in held, name


def test_a_body_at_a_chair_by_the_door_stands_in_neither_the_table_nor_the_door():
    anchors = {"chair": {"desc": "a chair", "dir": "s", "cell": [3, 4], "footprint": "point",
                         "height": "waist"},
               "table": {"desc": "a table", "cell": [3, 3], "footprint": "point",
                         "height": "waist"}}
    sc = _scene(anchors, {"Ada": "r"}, stations={"Ada": {"at": "chair"}}, w=6, d=5,
                adjacent=[{"to": "hall", "barrier": "open_door", "dir": "s", "offset": 0.4}])
    door = _cells(sc, "door:hall")
    assert door == {(2, 4)}, door
    cell = tuple(body_cell(sc, "Ada"))
    assert cell not in _cells(sc, "table") | door | _cells(sc, "chair"), cell


def test_a_body_placed_beside_another_never_lands_in_a_thing_or_a_doorway():
    """P stands one pace inside the west door; a crate is east of them and a
    rug south. Whichever way the seed would step, Q stands clear."""
    anchors = {"crate": {"desc": "a crate", "cell": [2, 2], "footprint": "point",
                         "height": "waist"},
               "rug": {"desc": "a rug", "cell": [1, 3], "footprint": "point", "height": "floor"}}
    for i in range(24):
        q = f"Q{i}"
        sc = _scene(anchors, {"P": "r", q: "r"}, w=5, d=5,
                    stations={"P": {"cell": [1, 2]}, q: {"near": ["P"]}},
                    adjacent=[{"to": "hall", "barrier": "open_door", "dir": "w", "offset": 0.5}])
        assert _cells(sc, "door:hall") == {(0, 2)}
        cell = tuple(body_cell(sc, q))
        assert cell != (1, 2) and cell not in {(2, 2), (1, 3), (0, 2)}, (q, cell)


def test_a_body_on_a_bed_is_seen_across_it_and_sees_past_it():
    """Lying, a body's eye and top are low, and a waist-high bed between
    two bodies hides one from the other -- but not the bed she lies ON: she
    is on it. The bed still hides a body lying on the floor behind it, and
    from the bed the room beyond it is in view."""
    sc = _scene({"bed": BED}, {"Hinami": "r"}, stations={"Hinami": {"at": "bed"}},
                poses={"Hinami": dict(LYING)})
    hx, hy = body_cell(sc, "Hinami")
    near_x, far_x, beyond_x = (6, 7, 0) if hx == 3 else (1, 0, 6)
    across = 4 if hx == 3 else 3                  # the bed's other column
    assert (across, hy) in _cells(sc, "bed")
    sc["positions"].update({"Ojo": "r", "Low": "r"})
    sc["stations"]["Ojo"] = {"cell": [near_x, hy]}
    sc["stations"]["Low"] = {"cell": [beyond_x, hy]}
    sc["poses"]["Low"] = {"posture": "lying"}
    sc["rooms"]["r"]["anchors"]["chest"] = {"desc": "a chest", "cell": [far_x, hy],
                                           "footprint": "point", "height": "floor"}
    assert body_visibility(sc, "Ojo", "Hinami")["visible"] is True
    assert body_visibility(sc, "Hinami", "Ojo")["visible"] is True
    assert body_visibility(sc, "Ojo", "Low")["visible"] is False, "the bed hides who is behind it"
    rows = {r["anchor"]: r for r in feature_visibility(sc, "Hinami", sweep=True)}
    assert rows["chest"]["visible"] is True, rows["chest"]


def _doorways_room():
    """A narrow room entered from the hall through its south door, a table
    one pace inside it, the yard's doorway beside that pace."""
    anchors = {"table": {"desc": "a table", "cell": [1, 2], "footprint": "point",
                         "height": "waist"}}
    for offset in (0.5, 0.6, 0.67, 0.7, 0.75):
        sc = _scene(anchors, {"Ada": "hall"}, w=3, d=4,
                    adjacent=[{"to": "hall", "barrier": "open_door", "dir": "s", "offset": 0.5},
                              {"to": "yard", "barrier": "open_door", "dir": "w", "offset": offset}])
        sc["rooms"]["hall"]["adjacent"] = [{"to": "r", "barrier": "open_door", "dir": "n"}]
        sc["rooms"]["yard"]["adjacent"] = [{"to": "r", "barrier": "open_door", "dir": "e"}]
        if _cells(sc, "door:yard") == {(0, 2)} and _cells(sc, "door:hall") == {(1, 3)}:
            return sc
    raise AssertionError("no offset lays the yard's doorway beside the pace")


def test_an_arrival_seated_inside_its_door_never_stands_in_another_doorway():
    sc = _doorways_room()
    merged = merge_scene_with_diff(sc, {"positions": {"Ada": "r"}})
    cell = tuple(merged["stations"]["Ada"]["cell"])
    assert cell not in {(0, 2), (1, 3), (1, 2)}, cell


def test_a_walk_in_ends_in_neither_a_doorway_nor_a_thing():
    from world.spatial import walk
    sc = _doorways_room()
    landed = walk(sc, "Ada", "r", paces=40, from_room="hall")
    assert landed["arrived"] and tuple(landed["cell"]) not in {(0, 2), (1, 3), (1, 2)}, landed


def test_a_walk_across_the_room_stands_where_it_landed_not_where_it_started():
    """A station's cell written beside a new `at` is often the body's OLD
    cell echoed; read first, it drew the body back where it started. The
    echo is dropped and the station places the body -- unless the cell is ON
    the fixture the body lies on, the hand's own answer."""
    from agents.director import walk_within_room
    anchors = {"stove": {"desc": "a stove", "dir": "e", "cell": [7, 2], "footprint": "point",
                         "height": "waist"},
               "bed": BED}
    sc = _scene(anchors, {"Ada": "r"}, stations={"Ada": {"at": None, "cell": [0, 0]}})
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    sd = {"stations": {"Ada": {"at": "stove", "near": [], "cell": [0, 0]}}}
    walk_within_room(ctx, sc, sd, {})
    # the echo is dropped: the station's `at` places her, beside the stove
    assert "cell" not in sd["stations"]["Ada"]
    merged = merge_scene_with_diff(sc, sd)
    here = tuple(body_cell(merged, "Ada"))
    assert here != (0, 0) and here not in _cells(merged, "stove")
    sd = {"stations": {"Ada": {"at": "bed", "near": [], "cell": [4, 2]}},
          "poses": {"Ada": dict(LYING)}}
    walk_within_room(ctx, sc, sd, {})
    assert sd["stations"]["Ada"]["cell"] == [4, 2], "on the bed she lies on: the hand's answer"


# ---------------------------------------------------------------------------
# What the review of 2026-10-13 found, each pinned as its reproduction
# ---------------------------------------------------------------------------

def test_a_body_in_cover_stays_behind_its_counter_whatever_lies_in_its_lane():
    """Graded over every side, a rug in a counter's lane stood a crouching
    thief on the customers' side, in full view. The side a station declares
    holds; a floor-height thing there is stood on."""
    anchors = {"counter": {"desc": "the shop counter", "dir": "n", "footprint": "run",
                           "height": "waist", "lane": True},
               "rug": {"desc": "a rug", "dir": "n", "footprint": "run", "height": "floor"}}
    sc = _scene(anchors, {"Thief": "r", "Guard": "r"},
                stations={"Thief": {"at": "counter", "cover": "counter"}, "Guard": {"cell": [4, 5]}},
                poses={"Thief": {"posture": "crouching"}})
    counter = _cells(sc, "counter")
    assert all(y == 1 for _x, y in counter)
    assert body_cell(sc, "Thief")[1] == 0, "behind the counter, on the rug"
    assert body_visibility(sc, "Guard", "Thief")["visible"] is False


def test_a_body_with_no_cover_is_never_stood_in_a_counters_lane():
    """The mirror: stools on the customers' side stood a patron in the
    bartender's lane, hidden behind the bar."""
    anchors = {"bar": {"desc": "the bar", "dir": "n", "footprint": "run", "height": "waist",
                       "lane": True}}
    for i, x in enumerate(range(1, 7)):
        anchors[f"stool_{i + 1}"] = {"desc": "a bar stool", "cell": [x, 2], "footprint": "point",
                                     "height": "waist"}
    sc = _scene(anchors, {"Patron": "r"}, stations={"Patron": {"at": "bar"}},
                poses={"Patron": {"posture": "sitting"}})
    assert body_cell(sc, "Patron")[1] >= 1, "never in the lane behind the bar"


def test_drawn_curtains_on_a_bed_still_hide_the_body_in_it():
    """The bed a body lies on is passable to lines to and from it; what else
    stands or hangs on its cells is not."""
    curtains = {"desc": "the bed's drawn curtains", "cell": [3, 1], "extent": {"w": 2, "d": 3},
                "footprint": "large", "height": "full", "opacity": "opaque", "mount": "on bed"}
    sc = _scene({"bed": BED, "curtains": curtains}, {"Hinami": "r", "Maid": "r"},
                stations={"Hinami": {"at": "bed", "cell": [4, 2]}, "Maid": {"cell": [1, 2]}},
                poses={"Hinami": dict(LYING)})
    assert body_visibility(sc, "Maid", "Hinami")["visible"] is False
    assert body_visibility(sc, "Hinami", "Maid")["visible"] is False


def test_a_body_dragged_or_stepped_off_its_bed_stands_where_it_was_put():
    """With the encoder's three records -- station, contact, pose -- a host's
    drop on open floor was overridden at once and deleted at the next merge,
    and a beat's own `{at: null, cell}` the same; the standing contact
    re-derived the station. The step-off lets the pose go of the bed."""
    def lying():
        sc = _scene({"bed": BED}, {"Hinami": "r"}, stations={"Hinami": {"at": "bed"}},
                    poses={"Hinami": dict(LYING)})
        sc["contacts"] = [{"actor": "Hinami", "target": "bed", "relation": "surface",
                           "manner": "rest", "motion": "settled"}]
        return sc
    sc = lying()
    sc["stations"]["Hinami"] = {"at": None, "near": [], "cell": [6, 2]}      # the host's drop
    assert tuple(body_cell(sc, "Hinami")) == (6, 2)
    merged = merge_scene_with_diff(sc, {"positions": {}})
    assert tuple(body_cell(merged, "Hinami")) == (6, 2)
    assert not merged["poses"]["Hinami"].get("support")
    merged = merge_scene_with_diff(lying(), {"stations": {"Hinami": {"at": None, "cell": [6, 2]}}})
    assert tuple(body_cell(merged, "Hinami")) == (6, 2)


def test_a_body_on_a_thing_laid_across_a_doorway_is_never_dealt_the_door():
    """A body in a doorway is the door: one resting on a futon a story laid
    across the doorway was dealt the door's cell, and nobody could leave."""
    for fx in ([1, 4], [2, 4], [3, 4]):
        for i in range(10):
            name = f"Sleeper{i}"
            sc = _scene({"futon": {"desc": "a futon", "cell": fx, "extent": {"w": 3, "d": 1},
                                   "footprint": "small", "height": "floor"}},
                        {name: "r"}, stations={name: {"at": "futon"}}, w=6, d=5,
                        poses={name: {"posture": "lying", "support": "futon"}},
                        adjacent=[{"to": "hall", "barrier": "open_door", "dir": "s", "offset": 0.5}])
            door = _cells(sc, "door:hall")
            assert tuple(body_cell(sc, name)) not in door, (fx, name)


def test_beside_someone_on_a_rug_is_a_pace_off_not_two():
    """A clear cell two paces off was taken before a rug one pace off, and a
    pair stationed together fell out of each other's reach."""
    from world.spatial import proximity_rel
    rug = {"desc": "a wide rug", "cell": [2, 1], "extent": {"w": 4, "d": 3},
           "footprint": "large", "height": "floor"}
    for i in range(12):
        q = f"Q{i}"
        sc = _scene({"rug": rug}, {"P": "r", q: "r"},
                    stations={"P": {"at": None, "cell": [3, 2]}, q: {"at": None, "near": ["P"]}})
        assert proximity_rel(sc, "P", q) == "within_reach", (q, body_cell(sc, q))


def test_a_body_pinned_on_a_bed_keeps_its_cell_from_the_one_dealt_beside_it():
    for x, y in [(3, 1), (4, 1), (3, 2), (4, 2), (3, 3), (4, 3)]:
        for pinned, free in (("Ada", "Bea"), ("Bea", "Ada")):
            sc = _scene({"bed": BED}, {pinned: "r", free: "r"},
                        stations={pinned: {"at": "bed", "cell": [x, y]}, free: {"at": "bed"}},
                        poses={pinned: dict(LYING), free: dict(LYING)})
            assert body_cell(sc, pinned) != body_cell(sc, free), (pinned, (x, y))


def test_a_walk_keeps_a_cell_the_beat_declared_beside_its_fixture():
    """Only the body's OLD cell echoed back is replaced by the landing; a
    cell the beat itself declared beside its `at` is the beat's place."""
    from agents.director import walk_within_room
    anchors = {"stove": {"desc": "a stove", "dir": "e", "cell": [7, 2], "footprint": "point",
                         "height": "waist"}}
    sc = _scene(anchors, {"Ada": "r"}, stations={"Ada": {"at": None, "cell": [0, 0]}})
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    sd = {"stations": {"Ada": {"at": "stove", "near": [], "cell": [6, 3]}}}
    walk_within_room(ctx, sc, sd, {})
    assert sd["stations"]["Ada"]["cell"] == [6, 3]


# ---------------------------------------------------------------------------
# What the second review of 2026-10-13 found: a floor height hides nobody,
# and is not ground to stand on
# ---------------------------------------------------------------------------

def test_a_body_beside_a_floor_thing_stands_clear_of_it_where_it_can():
    """925 of the play database's 1,373 anchors carry no height, so are
    floor height: ponds, stands, low tables, futons. A body at the bench
    was stood in the pond before it, at the hearth on the low table, at the
    wardrobe on the futon a body lay on."""
    pond = {"desc": "a koi pond", "cell": [2, 1], "extent": {"w": 4, "d": 1}}
    bench = {"desc": "a bench", "dir": "n", "cell": [2, 0], "extent": {"w": 4, "d": 1},
             "height": "waist"}
    sc = _scene({"bench": bench, "pond": pond}, {"Ada": "r"}, stations={"Ada": {"at": "bench"}})
    assert tuple(body_cell(sc, "Ada")) not in _cells(sc, "pond") | _cells(sc, "bench")
    futon = {"desc": "a futon", "cell": [2, 1], "extent": {"w": 3, "d": 2}, "height": "floor"}
    wardrobe = {"desc": "a wardrobe", "dir": "n", "cell": [2, 0], "extent": {"w": 3, "d": 1},
                "height": "full"}
    for i in range(40):
        maid = f"Maid{i}"
        sc = _scene({"wardrobe": wardrobe, "futon": futon}, {maid: "r", "Hinami": "r"},
                    stations={maid: {"at": "wardrobe"}, "Hinami": {"at": "futon"}},
                    poses={"Hinami": {"posture": "lying", "support": "futon"}})
        assert body_cell(sc, maid) != body_cell(sc, "Hinami"), maid


def test_beside_someone_is_beside_them_never_in_a_pond_of_their_own():
    """A floor-height cell is taken before a clear one only when it is the
    thing the other body stands on: beside someone on a bench is never in
    the koi pond before it -- by the near step or by an arrival's seat
    (second review of 2026-10-13, its garden)."""
    garden = {"bench": {"desc": "a stone bench", "cell": [2, 0], "extent": {"w": 3, "d": 1},
                        "height": "waist"},
              "pond": {"desc": "a koi pond", "cell": [1, 1], "extent": {"w": 5, "d": 3},
                       "height": "floor"}}
    for i in range(12):
        q = f"Q{i}"
        sc = _scene(garden, {"P": "r", q: "r"},
                    stations={"P": {"at": "bench", "cell": [3, 0]}, q: {"near": ["P"]}},
                    poses={"P": {"posture": "sitting", "support": "bench"}})
        assert tuple(body_cell(sc, q)) not in _cells(sc, "pond"), q
    sc = _scene(garden, {"P": "r", "Q": "lane"},
                stations={"P": {"at": "bench", "cell": [3, 0]}},
                poses={"P": {"posture": "sitting", "support": "bench"}},
                adjacent=[{"to": "lane", "barrier": "open", "dir": "s"}])
    sc["rooms"]["lane"]["adjacent"] = [{"to": "r", "barrier": "open", "dir": "n"}]
    merged = merge_scene_with_diff(sc, {"positions": {"Q": "r"}, "stations": {"Q": {"near": ["P"]}}})
    assert tuple(merged["stations"]["Q"]["cell"]) not in _cells(merged, "pond")


def test_a_body_in_cover_stays_behind_its_counter_whatever_stands_in_its_lane():
    """The first review's second case: a head-high back shelf in a lane
    counter's lane stood the keeper beside the counter, in full view."""
    anchors = {"bar": {"desc": "the bar", "dir": "n", "footprint": "run", "height": "waist",
                       "lane": True},
               "shelf": {"desc": "the bottle shelf", "dir": "n", "footprint": "run",
                         "height": "head"}}
    sc = _scene(anchors, {"Keeper": "r", "Guest": "r"},
                stations={"Keeper": {"at": "bar", "cover": True}, "Guest": {"cell": [3, 5]}},
                poses={"Keeper": {"posture": "crouching"}})
    assert body_cell(sc, "Keeper")[1] == 0
    assert body_visibility(sc, "Guest", "Keeper")["visible"] is False


def test_bodies_beside_a_blocked_fixture_go_to_its_nearer_end():
    """Beside the anchor is nearest the cell a body was dealt: every body
    went to one end and stacked there."""
    anchors = {"bar": {"desc": "the bar", "dir": "n", "cell": [1, 0], "extent": {"w": 6, "d": 1},
                       "height": "waist"}}
    for i, x in enumerate(range(1, 7)):
        anchors[f"stool_{i}"] = {"desc": "a stool", "cell": [x, 1], "footprint": "point",
                                 "height": "waist"}
    ends = set()
    for i in range(40):
        name = f"P{i}"
        sc = _scene(anchors, {name: "r"}, stations={name: {"at": "bar"}})
        ends.add(body_cell(sc, name)[0])
    assert ends == {0, 7}, ends


def test_a_body_at_a_corner_thing_steps_along_its_walls_never_into_another():
    anchors = {"stove": {"desc": "a stove", "dir": "ne", "footprint": "point", "height": "waist"},
               "crate": {"desc": "a crate", "cell": [6, 1], "footprint": "point", "height": "waist"}}
    sc = _scene(anchors, {"Cook": "r"}, stations={"Cook": {"at": "stove"}})
    assert _cells(sc, "stove") == {(7, 0)}
    assert tuple(body_cell(sc, "Cook")) in {(6, 0), (7, 1)}


def test_two_in_one_curtained_bed_see_each_other_and_a_dais_hides_nobody_on_it():
    curtains = {"desc": "drawn curtains", "cell": [3, 1], "extent": {"w": 2, "d": 3},
                "footprint": "large", "height": "full", "opacity": "opaque", "mount": "on bed"}
    sc = _scene({"bed": BED, "curtains": curtains}, {"Ada": "r", "Bea": "r", "Maid": "r"},
                stations={"Ada": {"at": "bed", "cell": [4, 1]}, "Bea": {"at": "bed", "cell": [4, 3]},
                          "Maid": {"cell": [1, 1]}},
                poses={"Ada": dict(LYING), "Bea": dict(LYING)})
    assert body_visibility(sc, "Ada", "Bea")["visible"] is True
    assert body_visibility(sc, "Maid", "Ada")["visible"] is False
    dais = {"desc": "a stone dais", "cell": [3, 1], "extent": {"w": 3, "d": 3}, "height": "waist"}
    throne = {"desc": "a throne", "cell": [4, 2], "footprint": "point", "height": "waist",
              "mount": "on dais"}
    sc = _scene({"dais": dais, "throne": throne}, {"Queen": "r", "Page": "r"},
                stations={"Queen": {"at": "throne"}, "Page": {"cell": [0, 2]}},
                poses={"Queen": {"posture": "sitting", "support": "throne"}})
    assert body_visibility(sc, "Page", "Queen")["visible"] is True


def test_a_beat_that_lays_a_body_down_by_pose_alone_puts_it_on_the_bed():
    """A body that walks in and lies down by its pose alone -- no station,
    no contact -- was seated at the door, and the step-off rule then erased
    the pose the beat had just stated; one that had stepped off earlier kept
    its old pin. A pose resting a body on a thing of its room stations it
    there (second review of 2026-10-13)."""
    sc = _scene({"bed": BED}, {"Hinami": "hall"}, w=8, d=6,
                adjacent=[{"to": "hall", "barrier": "open_door", "dir": "s", "offset": 0.5}])
    sc["rooms"]["hall"]["adjacent"] = [{"to": "r", "barrier": "open_door", "dir": "n"}]
    merged = merge_scene_with_diff(sc, {"positions": {"Hinami": "r"},
                                        "poses": {"Hinami": dict(LYING)}})
    assert merged["poses"]["Hinami"]["support"] == "bed"
    assert tuple(body_cell(merged, "Hinami")) in _cells(merged, "bed")
    # a body already in the room that lies down on it by its pose alone is
    # put on it too -- the support is new this beat -- and it stays there the
    # beat after (fourth review of 2026-10-13: an arrivals-only rule left her
    # by the door, and the next beat erased her pose)
    sc = _scene({"bed": BED}, {"Hinami": "r", "Maid": "r"},
                stations={"Hinami": {"at": None, "cell": [1, 1]}})
    merged = merge_scene_with_diff(sc, {"poses": {"Hinami": dict(LYING)}})
    assert tuple(body_cell(merged, "Hinami")) in _cells(merged, "bed")
    merged = merge_scene_with_diff(merged, {"poses": {"Maid": {"posture": "standing"}}})
    assert merged["poses"]["Hinami"]["support"] == "bed"
    assert tuple(body_cell(merged, "Hinami")) in _cells(merged, "bed")


def test_an_at_the_hygiene_blanked_is_no_step_off():
    """The station hygiene writes null over an `at` that names no anchor
    exactly; the body lying down by pose and contact stays on the bed."""
    sc = _scene({"bed": BED}, {"Hinami": "r"})
    merged = merge_scene_with_diff(sc, {
        "stations": {"Hinami": {"at": "Bed"}},
        "poses": {"Hinami": dict(LYING)},
        "contact_ops": [{"op": "add", "actor": "Hinami", "target": "bed", "manner": "rest",
                         "relation": "surface", "motion": "settled"}]})
    assert tuple(body_cell(merged, "Hinami")) in _cells(merged, "bed")


def test_a_beats_step_off_with_no_cell_lets_go_of_the_bed():
    """The encoder card's step-off, `{at: null}` with no cell: the contact
    left standing re-derived the station and put the body back on the bed."""
    sc = _scene({"bed": BED}, {"Hinami": "r"}, stations={"Hinami": {"at": "bed"}},
                poses={"Hinami": dict(LYING)})
    sc["contacts"] = [{"actor": "Hinami", "target": "bed", "relation": "surface",
                       "manner": "rest", "motion": "settled"}]
    merged = merge_scene_with_diff(sc, {"stations": {"Hinami": {"at": None}}})
    assert not merged["poses"]["Hinami"].get("support")
    merged = merge_scene_with_diff(merged, {"positions": {}})
    assert tuple(body_cell(merged, "Hinami")) not in _cells(merged, "bed")


def test_a_walk_behind_a_counter_keeps_its_cover():
    """The echoed old cell is dropped, never replaced by the landing beside
    the counter, which outranked the cover behind it."""
    from agents.director import walk_within_room
    anchors = {"counter": {"desc": "the counter", "dir": "n", "footprint": "run", "height": "waist",
                           "lane": True}}
    sc = _scene(anchors, {"Ada": "r"}, stations={"Ada": {"at": None, "cell": [0, 5]}})
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    sd = {"stations": {"Ada": {"at": "counter", "cover": "counter", "near": [], "cell": [0, 5]}}}
    walk_within_room(ctx, sc, sd, {})
    assert "cell" not in sd["stations"]["Ada"]
    merged = merge_scene_with_diff(sc, sd)
    assert body_cell(merged, "Ada")[1] == 0, "behind the counter"


def test_the_directors_sight_digest_asks_where_each_body_rests_once(monkeypatch):
    from world import spatial_fov
    from world.spatial import sight_digest
    calls = []
    real = spatial_fov._resting_on
    monkeypatch.setattr(spatial_fov, "_resting_on",
                        lambda scene, name: calls.append(name) or real(scene, name))
    names = [f"B{i}" for i in range(6)]
    sc = _scene({"bed": BED}, {n: "r" for n in names},
                stations={n: {"at": "bed"} for n in names},
                poses={n: dict(LYING) for n in names})
    sight_digest(sc, names)
    assert len(calls) <= len(names), len(calls)


def test_a_host_who_drags_a_body_off_its_bed_and_back_finds_it_lying_there(temp_db):
    """The map's own route: a drag off and back, or an Undo, restores the
    body to its bed; the route never erased its pose (second review of
    2026-10-13). Only a merge lets go of a support."""
    import time
    from fastapi.testclient import TestClient
    from web import app as app_module
    from web import guest_access as guest
    sc = _scene({"bed": BED}, {"Hinami": "r"}, stations={"Hinami": {"at": "bed", "cell": [4, 2]}},
                poses={"Hinami": dict(LYING)})
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Bed", "", time.time()))
    temp_db.wset(cid, "scene", sc)
    guest.reset_host_account()
    client = TestClient(app_module.app)
    client.__enter__()
    try:
        assert client.post("/api/auth/setup", json={"username": "host",
                                                    "password": "pw12345"}).status_code == 200
        for body in ({"at": None, "near": [], "cell": [6, 2]},
                     {"at": "bed", "near": [], "cell": [4, 2]}):
            out = client.put(f"/api/chats/{cid}/bodies/Hinami/station", json=body)
            assert out.status_code == 200, out.text
    finally:
        client.__exit__(None, None, None)
        guest.reset_host_account()
    stored = temp_db.wget(cid, "scene", {})
    assert stored["poses"]["Hinami"]["support"] == "bed"
    assert resting_on(stored, "Hinami") == "bed"


# ---------------------------------------------------------------------------
# The third review of 2026-10-13
# ---------------------------------------------------------------------------

def test_two_on_one_support_are_divided_by_what_stands_on_part_of_it():
    """Inside what encloses the whole support they see each other; a shed on
    a lawn, a screen on a platform, still divides them."""
    lawn = {"desc": "the lawn", "cell": [0, 0], "extent": {"w": 10, "d": 6}, "height": "floor"}
    shed = {"desc": "a tool shed", "cell": [4, 2], "extent": {"w": 2, "d": 2}, "height": "full",
            "opacity": "opaque"}
    sc = _scene({"lawn": lawn, "shed": shed}, {"Ada": "r", "Bea": "r"}, w=10, d=6,
                stations={"Ada": {"at": "lawn", "cell": [1, 3]}, "Bea": {"at": "lawn", "cell": [8, 3]}},
                poses={"Ada": {"posture": "standing", "support": "lawn"},
                       "Bea": {"posture": "standing", "support": "lawn"}})
    assert body_visibility(sc, "Ada", "Bea")["visible"] is False
    platform = {"desc": "a sleeping platform", "cell": [1, 1], "extent": {"w": 6, "d": 3},
                "height": "floor"}
    screen = {"desc": "a folding screen", "cell": [4, 1], "extent": {"w": 1, "d": 3},
              "height": "full", "opacity": "opaque", "mount": "on platform"}
    sc = _scene({"platform": platform, "screen": screen}, {"Ada": "r", "Bea": "r"},
                stations={"Ada": {"at": "platform", "cell": [2, 2]},
                          "Bea": {"at": "platform", "cell": [6, 2]}},
                poses={"Ada": {"posture": "sitting", "support": "platform"},
                       "Bea": {"posture": "sitting", "support": "platform"}})
    assert body_visibility(sc, "Ada", "Bea")["visible"] is False


def test_a_futon_in_a_box_bed_is_hidden_inside_it():
    """`in` an enclosure is not `on` a dais: the box bed hides who lies in it."""
    box = {"desc": "a box bed", "cell": [3, 1], "extent": {"w": 2, "d": 3}, "height": "full",
           "opacity": "opaque"}
    futon = {"desc": "a futon", "cell": [3, 1], "extent": {"w": 2, "d": 3}, "height": "floor",
             "mount": "in box"}
    sc = _scene({"box": box, "futon": futon}, {"Hinami": "r", "Maid": "r"},
                stations={"Hinami": {"at": "futon", "cell": [4, 2]}, "Maid": {"cell": [1, 2]}},
                poses={"Hinami": {"posture": "lying", "support": "futon"}})
    assert body_visibility(sc, "Maid", "Hinami")["visible"] is False


def test_several_on_a_one_cell_thing_never_stand_on_one_another():
    ledge = {"desc": "a sand shelf", "cell": [4, 4], "footprint": "point", "height": "floor"}
    sc = _scene({"ledge": ledge}, {"Hinami": "r", "Doctor": "r"},
                stations={"Hinami": {"at": "ledge"}, "Doctor": {"at": "ledge"}},
                poses={"Hinami": {"posture": "standing", "support": "ledge"},
                       "Doctor": {"posture": "standing", "support": "ledge"}})
    assert body_cell(sc, "Hinami") != body_cell(sc, "Doctor")


def test_a_body_in_cover_is_never_stood_in_a_doorway():
    """Its declared side only a doorway: beside its anchor, where it holds
    no door against every walk."""
    anchors = {"crate": {"desc": "a crate", "dir": "s", "cell": [2, 3], "footprint": "point",
                         "height": "waist"}}
    sc = _scene(anchors, {"Thief": "r"}, w=6, d=5,
                stations={"Thief": {"at": "crate", "cover": "crate"}},
                adjacent=[{"to": "hall", "barrier": "open_door", "dir": "s", "offset": 0.4}])
    door = _cells(sc, "door:hall")
    assert door == {(2, 4)}, door
    assert tuple(body_cell(sc, "Thief")) not in door


def test_a_body_already_in_the_room_keeps_its_station_when_its_pose_is_restated():
    """A support restated is no news: a body pinned on a rug keeps its pin,
    and one whose pose already leant on the desk is not stood on it (the
    stored beats' nine misfires, all a restated support -- third and fourth
    reviews of 2026-10-13)."""
    rug = {"desc": "a rug", "cell": [1, 1], "extent": {"w": 7, "d": 5}, "height": "floor"}
    sc = _scene({"rug": rug}, {"Ada": "r"}, w=10, d=8, stations={"Ada": {"at": None, "cell": [6, 4]}})
    merged = merge_scene_with_diff(sc, {"poses": {"Ada": {"posture": "standing", "support": "rug"}}})
    assert tuple(body_cell(merged, "Ada")) == (6, 4)
    desk = {"desc": "the reception desk", "dir": "n", "cell": [0, 1], "footprint": "point",
            "height": "waist"}
    sc = _scene({"desk": desk}, {"Doctor": "r"}, stations={"Doctor": {"near": []}},
                poses={"Doctor": {"posture": "leaning", "support": "desk"}})
    merged = merge_scene_with_diff(sc, {"poses": {"Doctor": {
        "posture": "leaning, both hands lightly on the reception desk", "support": "desk"}}})
    assert body_cell(merged, "Doctor") is None or tuple(body_cell(merged, "Doctor")) != (0, 1)


def test_a_walk_to_someone_ends_beside_them_not_at_its_old_cell():
    """A `near` station has no `at` to take its old pin down: the echoed
    cell gives way to the landing, and the one walked to is not dragged to
    the walker's old cell."""
    from agents.director import walk_within_room
    anchors = {"stove": {"desc": "a stove", "dir": "e", "cell": [9, 2], "footprint": "point",
                         "height": "waist"}}
    sc = _scene(anchors, {"Ada": "r", "Tamamo": "r"}, w=10, d=6,
                stations={"Ada": {"at": None, "cell": [1, 2]}, "Tamamo": {"at": "stove"}})
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    sd = {"stations": {"Ada": {"at": None, "near": ["Tamamo"], "cell": [1, 2]}}}
    walk_within_room(ctx, sc, sd, {})
    merged = merge_scene_with_diff(sc, sd)
    ada, tamamo = body_cell(merged, "Ada"), body_cell(merged, "Tamamo")
    assert max(abs(ada[0] - tamamo[0]), abs(ada[1] - tamamo[1])) <= 1
    assert ada[0] >= 6, ("she crossed the room", ada)


def test_a_station_restated_beside_the_one_it_names_keeps_its_cell():
    """A body already beside the one it would walk to, its own cell
    restated, stands where it stood: walked to that one's fixed side, a body
    at an elevator's gate went round to her far side every beat while the
    prose kept her at the gate (chat 160, turns 10 and 11; fourth review of
    2026-10-13)."""
    from agents.director import walk_within_room
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    for cell in ([6, 3], [5, 3], [4, 3], [6, 2], [4, 1], [6, 1]):
        sc = _scene({}, {"Ada": "r", "Tamamo": "r"}, w=8, d=6,
                    stations={"Ada": {"at": None, "cell": list(cell)},
                              "Tamamo": {"at": None, "cell": [5, 2]}})
        sd = {"stations": {"Ada": {"at": None, "near": ["Tamamo"], "cell": list(cell)}}}
        walk_within_room(ctx, sc, sd, {})
        merged = merge_scene_with_diff(sc, sd)
        assert tuple(body_cell(merged, "Ada")) == tuple(cell), (cell, body_cell(merged, "Ada"))
        assert tuple(body_cell(merged, "Tamamo")) == (5, 2)
    # and with no cell written at all: beside her already, nothing moves
    sc = _scene({}, {"Ada": "r", "Tamamo": "r"}, w=8, d=6,
                stations={"Ada": {"at": None, "cell": [6, 3]},
                          "Tamamo": {"at": None, "cell": [5, 2]}})
    sd = {"stations": {"Ada": {"at": None, "near": ["Tamamo"]}}}
    walk_within_room(ctx, sc, sd, {})
    assert "cell" not in sd["stations"]["Ada"], sd


def test_a_body_getting_up_beside_someone_steps_off_the_thing():
    """Getting up off the bed to stand by the maid, one pace off it: read as
    a restatement, the body was left standing on the bed's cell (fifth
    review of 2026-10-13)."""
    from agents.director import walk_within_room
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    sc = _scene({"bed": BED}, {"Hinami": "r", "Maid": "r"},
                stations={"Hinami": {"at": "bed"}, "Maid": {"at": None, "cell": [5, 4]}},
                poses={"Hinami": dict(LYING)})
    assert resting_on(sc, "Hinami") == "bed"
    drawn = list(body_cell(sc, "Hinami"))
    assert tuple(drawn) in _cells(sc, "bed")
    sd = {"stations": {"Hinami": {"at": None, "near": ["Maid"], "cell": drawn}},
          "poses": {"Hinami": {"posture": "standing", "support": ""}}}
    walk_within_room(ctx, sc, sd, {})
    merged = merge_scene_with_diff(sc, sd)
    assert tuple(body_cell(merged, "Hinami")) not in _cells(merged, "bed"), body_cell(merged, "Hinami")


def test_a_pinned_body_walked_to_someone_with_no_cell_written_stands_where_it_landed():
    """No cell written and no `at`: the stored pin outlived the walk at the
    merge, so a body pinned on its bed got up beside the maid and was drawn
    standing on the bed (fifth review of 2026-10-13; 6 of the 398 stored
    near-walks with no cell carried a pin)."""
    from agents.director import walk_within_room
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    sc = _scene({"bed": BED}, {"Hinami": "r", "Maid": "r"},
                stations={"Hinami": {"at": "bed", "cell": [4, 3]},
                          "Maid": {"at": None, "cell": [5, 4]}},
                poses={"Hinami": dict(LYING)})
    assert resting_on(sc, "Hinami") == "bed" and tuple(body_cell(sc, "Hinami")) == (4, 3)
    sd = {"stations": {"Hinami": {"at": None, "near": ["Maid"]}},
          "poses": {"Hinami": {"posture": "standing", "support": ""}}}
    walk_within_room(ctx, sc, sd, {})
    merged = merge_scene_with_diff(sc, sd)
    cell = tuple(body_cell(merged, "Hinami"))
    assert cell not in _cells(merged, "bed"), cell
    assert max(abs(cell[0] - 5), abs(cell[1] - 4)) <= 1, cell


def test_two_bodies_walked_to_one_person_in_one_beat_land_on_two_cells():
    """Each walk was planned against the scene before the beat, so two
    bodies walked to the same one both landed on the cell beside him (chat
    122's turn 5; fifth review of 2026-10-13)."""
    from agents.director import walk_within_room
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    sc = _scene({}, {"Ada": "r", "Bea": "r", "Tamamo": "r"}, w=10, d=6,
                stations={"Ada": {"at": None, "cell": [0, 0]},
                          "Bea": {"at": None, "cell": [0, 5]},
                          "Tamamo": {"at": None, "cell": [8, 2]}})
    sd = {"stations": {"Ada": {"at": None, "near": ["Tamamo"]},
                       "Bea": {"at": None, "near": ["Tamamo"]}}}
    walk_within_room(ctx, sc, sd, {})
    merged = merge_scene_with_diff(sc, sd)
    ada, bea = tuple(body_cell(merged, "Ada")), tuple(body_cell(merged, "Bea"))
    assert ada != bea, (ada, bea)
    for cell in (ada, bea):
        assert max(abs(cell[0] - 8), abs(cell[1] - 2)) <= 2, cell


def test_a_walk_to_a_thing_that_is_no_body_ends_beside_it_never_in_it():
    """A thing named that is no body holds no cell the walk knows of: a walk
    to the TARDIS, written where it landed, stood the Doctor in its own cell
    (chat 122's turn 5; fifth review of 2026-10-13)."""
    from agents.director import walk_within_room
    ctx = SimpleNamespace(chat={"id": 0}, add_warning=lambda *_: None)
    sc = _scene({}, {"Ada": "r", "the box": "r"}, w=10, d=6,
                stations={"Ada": {"at": None, "cell": [0, 0]},
                          "the box": {"at": None, "cell": [7, 3]}})
    sc["entities"]["the box"] = {"name": "the box", "kind": "vehicle", "portable": False}
    sd = {"stations": {"Ada": {"at": None, "near": ["the box"]}}}
    walk_within_room(ctx, sc, sd, {})
    merged = merge_scene_with_diff(sc, sd)
    cell = tuple(body_cell(merged, "Ada"))
    assert cell != (7, 3), cell
    assert max(abs(cell[0] - 7), abs(cell[1] - 3)) <= 1, cell
