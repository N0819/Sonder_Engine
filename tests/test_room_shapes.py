"""Rooms of different shapes and extents (`world/spatial_fov.room_grid`),
the size word derived from the measurement, and the pin that a room with no
extent is the square it always was.

Design: `docs/design/DESIGN_ROOM_FIDELITY.md` §2. The contract under test is
the same fail-open one the geometry note wrote: THE LAYER MAY ONLY SUBTRACT
ON EVIDENCE IT HAS, and an extent is evidence only when it is a readable
pair of paces.
"""

from __future__ import annotations

import hashlib

import pytest

from llm.schemas import RoomDef
from world.spatial import (
    _ROOM_SILENT_WHEN_EMPTY, _merge_room, EXTENT_MAX_PACES,
    EXTENT_MIN_PACES, GRID_SIDE, ROOM_SIZES, SHAPES, anchor_cells,
    body_cell, effective_room_size, grid_side, normalize_extent,
    observer_field, room_grid, size_from_extent,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ANCHORS = {
    "bar": {"desc": "the long bar", "dir": "n", "footprint": "run",
            "height": "waist"},
    "screen": {"desc": "a folding screen", "dir": "e", "footprint": "run",
               "height": "head"},
    "hearth": {"desc": "the hearth", "dir": "s"},
    "door": {"desc": "the front door", "dir": "w"},
    "urn": {"desc": "an urn", "dir": "ne", "height": "waist"},
    "table": {"desc": "a round table", "footprint": "large", "height": "waist"},
    "stool": {"desc": "a stool"},
    "keg": {"desc": "a keg", "dir": "e", "footprint": "large"},
}


def scene(room, *, positions=None, stations=None, rooms=None):
    rooms = dict(rooms or {})
    rooms["r"] = room
    return {"rooms": rooms, "positions": dict(positions or {"P": "r"}),
            "stations": dict(stations or {}), "orientation": {}, "poses": {},
            "entities": {}}


# ---------------------------------------------------------------------------
# The reference: the square formulas exactly as the geometry note wrote them
# ---------------------------------------------------------------------------

def _seed(*parts):
    joined = "\x1f".join(str(p) for p in parts)
    return int(hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8], 16)


def _square_wall_cells(side, bearing, offset, length):
    last = side - 1
    if bearing in ("ne", "se", "sw", "nw"):
        x = last if bearing in ("ne", "se") else 0
        y = 0 if bearing in ("ne", "nw") else last
        return [(x, y)]
    cells = []
    for i in range(length):
        k = (offset + i) % side
        cells.append({"n": (k, 0), "s": (k, last), "e": (last, k),
                      "w": (0, k)}[bearing])
    return cells


_UNIT = {"n": (0, -1), "ne": (1, -1), "e": (1, 0), "se": (1, 1),
         "s": (0, 1), "sw": (-1, 1), "w": (-1, 0), "nw": (-1, -1)}
_OPP = {"n": "s", "s": "n", "e": "w", "w": "e", "ne": "sw", "sw": "ne",
        "se": "nw", "nw": "se"}


def _square_reference(room_id, side, anchors):
    """`_place_anchors` as it stood before extents existed, verbatim in its
    arithmetic. The claim under test is that the new form REDUCES to this
    for a square, not that it resembles it."""
    out = {}
    for aid, anchor in anchors.items():
        fp = anchor.get("footprint") or "point"
        height = anchor.get("height") or "floor"
        bearing = anchor.get("dir")
        seed = _seed(room_id, aid)
        if bearing:
            length = {"point": 1, "small": 2, "large": 2,
                      "run": max(2, side - 2)}[fp]
            offset = 1 + seed % max(1, side - 2 - (length - 1)) \
                if side > 2 else 0
            cells = _square_wall_cells(side, bearing, offset, length)
            standing = height != "floor" or fp in ("run", "large")
            if standing and side > 3:
                dx, dy = _UNIT[_OPP[bearing]]
                cells = [(x + dx, y + dy) for x, y in cells]
            if fp == "large" and cells:
                dx, dy = _UNIT[_OPP[bearing]]
                cells = cells + [(x + dx, y + dy) for x, y in cells
                                 if 0 <= x + dx < side and 0 <= y + dy < side]
        else:
            inner = max(1, side - 2)
            x = 1 + seed % inner
            y = 1 + (seed // 7) % inner
            cells = [(x, y)]
            if fp in ("small", "run"):
                cells.append((min(side - 1, x + 1), y))
            elif fp == "large":
                cells += [(min(side - 1, x + 1), y), (x, min(side - 1, y + 1)),
                          (min(side - 1, x + 1), min(side - 1, y + 1))]
        out[aid] = sorted(set(cells))
    return out


@pytest.mark.parametrize("tier", ROOM_SIZES)
def test_a_room_without_extent_composes_byte_identically(tier):
    """THE FAIL-OPEN PIN. Every anchor kind the engine places -- wall runs,
    points, corners, large footprints, interior things -- lands on exactly
    the cells the square formulas gave it, for every size tier, when the
    room carries no `extent`. The reference is the pre-extent arithmetic
    copied into this test, so a drift in the reduction is a failing test
    and not a quietly moved bar."""
    sc = scene({"name": "R", "size": tier, "anchors": dict(ANCHORS)})
    grid = room_grid(sc, "r")
    side = GRID_SIDE[tier]
    assert (grid.w, grid.d, grid.shape) == (side, side, "rectangle")
    assert not grid.measured
    assert grid.cells == frozenset((x, y) for x in range(side)
                                   for y in range(side))
    assert grid_side(sc, "r") == side
    placed = {aid: rec["cells"] for aid, rec in anchor_cells(sc, "r").items()}
    assert placed == _square_reference("r", side, ANCHORS)


def test_a_body_in_a_square_room_stands_where_it_did():
    """`body_cell` for a station at each anchor: inward of the anchor, never
    in it, within the square -- the geometry tests' own claims, restated
    against the grid form for a room with no extent."""
    for tier in ("small", "large", "vast"):
        for aid in ANCHORS:
            sc = scene({"name": "R", "size": tier, "anchors": dict(ANCHORS)},
                       stations={"P": {"at": aid}})
            cell = body_cell(sc, "P")
            side = GRID_SIDE[tier]
            assert cell is not None
            assert 0 <= cell[0] < side and 0 <= cell[1] < side
            assert cell not in anchor_cells(sc, "r")[aid]["cells"]


# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------

def test_the_closed_sets_and_the_clamp():
    # `composite` joined the set 2026-09-05 (the owner: "the room editor
    # doesn't cover the multi room shape design"); `l` stays, the two-part
    # case, readable exactly as it was.
    assert SHAPES == ("rectangle", "round", "l", "composite")
    assert (EXTENT_MIN_PACES, EXTENT_MAX_PACES) == (2, 24)
    assert normalize_extent({"w": 100, "d": 1}) == {"w": 24, "d": 2}
    assert normalize_extent({"width": 3.4, "depth": 11.6}) == {"w": 3, "d": 12}


@pytest.mark.parametrize("value", [
    None, "big", 12, {"w": 3}, {"d": 3}, {"w": "about ten", "d": 3},
    {"w": -3, "d": 3}, {"w": 0, "d": 4}, {"w": True, "d": 3}, [3, 4],
])
def test_an_unreadable_extent_is_no_extent(value):
    """A room is two-dimensional; one side is not an extent, prose is not a
    number, and a negative is not a room. None, never a guess."""
    assert normalize_extent(value) is None
    sc = scene({"name": "R", "size": "large", "extent": value})
    grid = room_grid(sc, "r")
    assert (grid.w, grid.d) == (GRID_SIDE["large"], GRID_SIDE["large"])


def test_an_unknown_shape_is_a_rectangle_and_parts_off_an_l_are_ignored():
    sc = scene({"name": "R", "extent": {"w": 6, "d": 4}, "shape": "hexagon",
                "parts": [{"w": 2, "d": 2, "at": "nw"}]})
    grid = room_grid(sc, "r")
    assert grid.shape == "rectangle" and len(grid.cells) == 24
    assert grid.parts == []


# ---------------------------------------------------------------------------
# Size is derived from the measurement
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("extent, tier", [
    ({"w": 2, "d": 2}, "tiny"),
    ({"w": 4, "d": 4}, "small"),
    ({"w": 3, "d": 12}, "medium"),      # a corridor is medium FLOOR, long
    ({"w": 6, "d": 6}, "medium"),
    ({"w": 8, "d": 8}, "large"),
    ({"w": 10, "d": 10}, "huge"),
    ({"w": 12, "d": 12}, "vast"),
    ({"w": 24, "d": 24}, "vast"),
])
def test_size_is_the_tier_of_the_equal_area_square(extent, tier):
    assert size_from_extent(extent) == tier


def test_the_extent_decides_the_size_word_so_the_two_never_disagree():
    """An authored `size` beside a disagreeing extent yields to the
    measurement (the lint reports the disagreement; nothing here fixes it
    silently)."""
    sc = scene({"name": "R", "size": "vast", "extent": {"w": 3, "d": 3}})
    assert effective_room_size(sc, "r") == "tiny"
    sc = scene({"name": "R", "size": "vast"})
    assert effective_room_size(sc, "r") == "vast"
    assert size_from_extent(None) is None


# ---------------------------------------------------------------------------
# Each shape's cells and boundary
# ---------------------------------------------------------------------------

def test_a_rectangle_has_every_cell_and_walls_of_two_lengths():
    grid = room_grid(scene({"name": "R", "extent": {"w": 8, "d": 4}}), "r")
    assert grid.measured and len(grid.cells) == 32
    assert grid.rim("n") == [(x, 0) for x in range(8)]
    assert grid.rim("s") == [(x, 3) for x in range(8)]
    assert grid.rim("e") == [(7, y) for y in range(4)]
    assert grid.rim("w") == [(0, y) for y in range(4)]
    assert grid.corner("ne") == (7, 0) and grid.corner("sw") == (0, 3)
    assert grid.centre() == (4, 2) and grid.side == 8


def test_a_round_room_has_no_corners_and_its_walls_are_arcs():
    grid = room_grid(scene({"name": "R", "extent": {"w": 8, "d": 8},
                            "shape": "round"}), "r")
    for corner in ((0, 0), (7, 0), (0, 7), (7, 7)):
        assert corner not in grid.cells
    assert (3, 3) in grid.cells and (4, 0) in grid.cells
    assert 0 < len(grid.cells) < 64
    rim = grid.rim("n")
    # The north arc: every rim cell has the outside above it, and the arc
    # curves -- its cells are not all on one row.
    assert all((x, y - 1) not in grid.cells for x, y in rim)
    assert len({y for _x, y in rim}) > 1
    assert grid.corner("ne")[0] > 4 and grid.corner("ne")[1] < 4
    assert grid.centre() in grid.cells


def test_an_l_is_the_union_of_its_parts_and_the_notch_is_not_the_room():
    grid = room_grid(scene({
        "name": "R", "extent": {"w": 8, "d": 8}, "shape": "l",
        "parts": [{"w": 8, "d": 3, "at": "nw"}, {"w": 3, "d": 8, "at": "ne"}],
    }), "r")
    assert (0, 0) in grid.cells and (7, 7) in grid.cells
    assert (0, 7) not in grid.cells and (2, 5) not in grid.cells   # the notch
    assert len(grid.cells) == 8 * 3 + 3 * 8 - 3 * 3
    # The inner wall of the notch faces south and west too.
    assert (4, 2) in grid.rim("s") and (5, 5) in grid.rim("w")
    assert grid.centre() in grid.cells


def test_an_l_with_no_extent_is_the_box_its_parts_need():
    grid = room_grid(scene({
        "name": "R", "shape": "l",
        "parts": [{"w": 6, "d": 2, "at": "nw"}, {"w": 2, "d": 6, "at": "sw"}],
    }), "r")
    assert (grid.w, grid.d) == (6, 6) and grid.measured
    assert (5, 5) not in grid.cells and (0, 5) in grid.cells


# ---------------------------------------------------------------------------
# Anchors on the right wall, doors on the boundary, walls' extents
# ---------------------------------------------------------------------------

def test_anchors_sit_on_the_wall_their_bearing_names_along_its_own_length():
    """A wide room: the north anchor has the long wall to sit on and the east
    anchor the short one. A `run` on the north wall runs most of twelve
    paces; a `run` on the east wall runs most of four."""
    sc = scene({"name": "R", "extent": {"w": 12, "d": 4}, "anchors": {
        "bar": {"desc": "the bar", "dir": "n", "footprint": "run",
                "height": "waist"},
        "rack": {"desc": "a rack", "dir": "e", "footprint": "run",
                 "height": "head"},
        "hearth": {"desc": "the hearth", "dir": "s"},
        "urn": {"desc": "an urn", "dir": "sw"},
    }})
    placed = anchor_cells(sc, "r")
    assert all(y == 1 for _x, y in placed["bar"]["cells"])       # inset of north
    assert len(placed["bar"]["cells"]) == 10
    assert all(x == 10 for x, _y in placed["rack"]["cells"])     # inset of east
    assert len(placed["rack"]["cells"]) == 2
    assert all(y == 3 and 0 <= x < 12 for x, y in placed["hearth"]["cells"])
    assert placed["urn"]["cells"] == [(0, 3)]


def test_a_round_rooms_anchors_and_doorway_sit_on_the_arc():
    sc = scene({"name": "R", "extent": {"w": 10, "d": 10}, "shape": "round",
                "anchors": {"altar": {"desc": "the altar", "dir": "n"}},
                "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "e"}]},
               rooms={"hall": {"name": "Hall", "size": "small"}})
    grid = room_grid(sc, "r")
    placed = anchor_cells(sc, "r")
    assert all(c in grid.rim("n") for c in placed["altar"]["cells"])
    door = placed["door:hall"]
    assert door["implicit"] and all(c in grid.rim("e") for c in door["cells"])
    assert all(c in grid.cells for c in door["cells"])


def test_an_interior_anchor_of_a_round_room_is_inside_the_room():
    sc = scene({"name": "R", "extent": {"w": 6, "d": 6}, "shape": "round",
                "anchors": {"stool%d" % i: {"desc": "a stool"}
                            for i in range(12)}})
    grid = room_grid(sc, "r")
    for rec in anchor_cells(sc, "r").values():
        assert all(c in grid.cells for c in rec["cells"])


def test_a_body_in_a_shaped_room_never_stands_outside_it():
    sc = scene({"name": "R", "extent": {"w": 8, "d": 8}, "shape": "l",
                "parts": [{"w": 8, "d": 3, "at": "nw"},
                          {"w": 3, "d": 8, "at": "ne"}],
                "anchors": {"desk": {"desc": "a desk", "dir": "w",
                                     "height": "waist"},
                            "lamp": {"desc": "a lamp"}}},
               positions={"P": "r", "Q": "r"},
               stations={"P": {"at": "desk"}, "Q": {"near": ["P"]}})
    grid = room_grid(sc, "r")
    assert body_cell(sc, "P") in grid.cells
    assert body_cell(sc, "Q") in grid.cells


def test_the_walls_extents_follow_the_two_boxes_sides():
    """A wide room with a small room to its north: the wall line between
    them spans both boxes ALONG the wall -- twelve paces of this room and
    four of the neighbour, wherever the doorway put it -- not two equal
    sides."""
    sc = scene({"name": "R", "extent": {"w": 12, "d": 4},
                "adjacent": [{"to": "n_room", "barrier": "open_door", "dir": "n"}]},
               rooms={"n_room": {"name": "N", "extent": {"w": 4, "d": 4}}})
    field = observer_field(sc, "P")
    assert "n_room" in field.offsets
    off = field.offsets["n_room"]
    (wall,) = [w for w in field.walls if w["to"] == "n_room"]
    assert wall["axis"] == 1 and wall["coord"] == -1
    assert wall["extent"] == (min(0, off[0]) - 0.5, max(12, off[0] + 4) - 0.5)
    assert wall["aperture"][1] - wall["aperture"][0] == 1.0
    # The field holds exactly the two shapes' cells.
    assert sum(1 for r in field.inside.values() if r == "r") == 48
    assert sum(1 for r in field.inside.values() if r == "n_room") == 16


def test_two_small_rooms_off_one_long_wall_both_cast_when_they_fit():
    """The geometry note's residual, half answered: with squares of one
    tier, the second neighbour on a wall always overlapped the first; with
    extents, two rooms fit side by side exactly when their placed cells do
    not meet."""
    sc = scene({"name": "R", "extent": {"w": 24, "d": 4},
                "adjacent": [{"to": "a", "barrier": "open_door", "dir": "n"},
                             {"to": "b", "barrier": "open_door", "dir": "n"}]},
               rooms={"a": {"name": "A", "extent": {"w": 2, "d": 2}},
                      "b": {"name": "B", "extent": {"w": 2, "d": 2}}})
    placed = anchor_cells(sc, "r")
    ax = placed["door:a"]["cells"][0][0]
    bx = placed["door:b"]["cells"][0][0]
    field = observer_field(sc, "P")
    fit = abs(ax - bx) >= 2
    assert ("b" in field.offsets and "a" in field.offsets) == fit or \
        ("a" in field.offsets) != ("b" in field.offsets)


# ---------------------------------------------------------------------------
# The record survives the schema and the merge
# ---------------------------------------------------------------------------

def test_the_schema_keeps_a_readable_extent_and_heals_prose_to_none():
    room = RoomDef(name="R", extent={"w": 3, "d": 12}, shape="l",
                   parts=[{"w": 3, "d": 12, "at": "nw"}])
    assert room.extent == {"w": 3.0, "d": 12.0}
    assert room.shape == "l" and room.parts == [{"w": 3.0, "d": 12.0, "at": "nw"}]
    healed = RoomDef(name="R", extent={"w": "about ten paces", "d": 3},
                     parts=[{"w": 2, "d": 2}, "north corner"])
    assert healed.extent is None and healed.parts is None


def test_the_merge_keeps_an_extent_a_re_echo_left_out():
    assert {"extent", "shape", "parts"} <= set(_ROOM_SILENT_WHEN_EMPTY)
    existing = {"name": "R", "extent": {"w": 3, "d": 12}, "shape": "rectangle",
                "adjacent": []}
    merged = _merge_room(existing, {"name": "R", "desc": "Long.",
                                    "extent": None, "shape": ""}, "r")
    assert merged["extent"] == {"w": 3, "d": 12}
    assert merged["shape"] == "rectangle"
    merged = _merge_room(existing, {"extent": {"w": 4, "d": 4}}, "r")
    assert merged["extent"] == {"w": 4, "d": 4}
