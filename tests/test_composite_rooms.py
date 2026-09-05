"""`composite`: a room that is not one rectangle is the union of rectangles
placed within its bounding box (`world/spatial_fov.py`, 2026-09-05).

The owner, trying the map editor: "the room editor doesn't cover the multi
room shape design." The `l` of the 2026-09-04 prototype was two corner parts;
this widens `parts` to ANY number of rectangles, each placed by a corner word
(as before) or by a room-local origin cell `at: [x, y]` (the `cell`
convention stations and anchors use), so a T, a U, a cross or a room with a
bay can be authored. The contract under test:

  * an `l` of two corner parts reads EXACTLY as it did -- `part_box` is the
    prototype's arithmetic, pinned here against a copy of it;
  * a composite's cells are the union of its parts; the notch is not the
    room; `rim` includes the inner walls a notch makes; a doorway on a
    composite's rim places exactly as on an L's;
  * parts that do not touch are a LINT row (`parts_disconnected`), never a
    refusal, and the cell-level `shape_disconnected` row is not repeated
    for the same room;
  * a room without parts, or with junk parts, is byte-identical to before
    on every tier -- `tests/test_room_shapes.py`'s pin stands beside this.
"""

from __future__ import annotations

import pytest

from llm.schemas import RoomDef
from world.spatial import (
    LAYOUT_LINT_KINDS, SHAPES, anchor_cells, layout_warning, normalize_part_at,
    normalize_parts, part_box, parts_box, room_field, room_grid,
    room_layout_lint,
)


def scene(room, rooms=None):
    rooms = dict(rooms or {})
    rooms["r"] = room
    return {"rooms": rooms, "positions": {}, "stations": {}, "orientation": {},
            "poses": {}, "entities": {}}


# ---------------------------------------------------------------------------
# The parts vocabulary
# ---------------------------------------------------------------------------

def test_composite_is_a_shape_and_a_part_sits_at_a_corner_or_a_cell():
    assert "composite" in SHAPES and "l" in SHAPES
    assert normalize_part_at("ne") == "ne"
    assert normalize_part_at("NW") == "nw"
    assert normalize_part_at([2, 3]) == [2, 3]
    assert normalize_part_at((0, 0)) == [0, 0]
    assert normalize_part_at([2.0, 3.0]) == [2, 3]
    # Not a corner, not a cell: a straight bearing, prose, one number, a
    # boolean pair, three numbers.
    for junk in ("n", "east corner", [2], [True, False], [1, 2, 3], None, "", 7):
        assert normalize_part_at(junk) is None, junk
    parts = normalize_parts([
        {"w": 4, "d": 2, "at": "nw"},
        {"w": 2, "d": 4, "at": [3, 0]},
        {"w": 2, "d": 2, "at": "middle"},        # dropped: no place
        {"w": "wide", "d": 2, "at": [0, 0]},     # dropped: no extent
        "not a part",
    ])
    assert parts == [{"w": 4, "d": 2, "at": "nw"}, {"w": 2, "d": 4, "at": [3, 0]}]


def test_part_box_is_the_l_prototypes_arithmetic_for_a_corner_and_clips_a_cell_part():
    """The reference is the corner formula copied from the prototype, so a
    drift in `part_box` is a failing test and not a quietly moved notch."""
    w, d = 8, 6
    for part in ({"w": 5, "d": 2, "at": "nw"}, {"w": 3, "d": 6, "at": "ne"},
                 {"w": 8, "d": 3, "at": "sw"}, {"w": 2, "d": 2, "at": "se"},
                 {"w": 20, "d": 20, "at": "se"}):
        pw, pd = min(part["w"], w), min(part["d"], d)
        x0 = w - pw if part["at"] in ("ne", "se") else 0
        y0 = d - pd if part["at"] in ("se", "sw") else 0
        assert part_box(part, w, d) == (x0, y0, x0 + pw, y0 + pd), part
    # A cell part is laid east and south from its origin, clipped to the box.
    assert part_box({"w": 3, "d": 2, "at": [2, 1]}, w, d) == (2, 1, 5, 3)
    assert part_box({"w": 3, "d": 2, "at": [7, 5]}, w, d) == (7, 5, 8, 6)
    # A part the box holds nothing of is an empty rectangle, not an error.
    x0, y0, x1, y1 = part_box({"w": 3, "d": 2, "at": [9, 9]}, w, d)
    assert x1 <= x0 or y1 <= y0
    x0, y0, x1, y1 = part_box({"w": 3, "d": 2, "at": [-4, 0]}, w, d)
    assert (x0, y0, x1, y1) == (0, 0, 0, 2)


def test_parts_box_is_the_box_the_parts_need():
    assert parts_box([{"w": 8, "d": 3, "at": "nw"}, {"w": 3, "d": 8, "at": "ne"}]) == (8, 8)
    assert parts_box([{"w": 4, "d": 2, "at": [0, 0]}, {"w": 2, "d": 5, "at": [1, 2]}]) == (4, 7)
    # Clamped to the extent range like every measurement.
    assert parts_box([{"w": 24, "d": 2, "at": [10, 0]}]) == (24, 2)
    assert parts_box([{"w": 2, "d": 2, "at": [0, 0]}])[0] >= 2


# ---------------------------------------------------------------------------
# An L is byte-identical; a composite is the union
# ---------------------------------------------------------------------------

L_PARTS = [{"w": 8, "d": 3, "at": "nw"}, {"w": 3, "d": 8, "at": "ne"}]


def test_an_l_reads_exactly_as_it_did():
    sc = scene({"name": "R", "extent": {"w": 8, "d": 8}, "shape": "l", "parts": L_PARTS,
                "anchors": {"bar": {"desc": "the bar", "dir": "n", "footprint": "run",
                                    "height": "waist"},
                            "urn": {"desc": "an urn", "dir": "se"}}})
    grid = room_grid(sc, "r")
    expected = {(x, y) for x in range(8) for y in range(3)} | \
               {(x, y) for x in range(5, 8) for y in range(8)}
    assert grid.cells == frozenset(expected)
    assert grid.shape == "l" and grid.parts == L_PARTS
    # The same room written as a two-part composite is the same floor.
    sc2 = scene({"name": "R", "extent": {"w": 8, "d": 8}, "shape": "composite",
                 "parts": L_PARTS, "anchors": sc["rooms"]["r"]["anchors"]})
    grid2 = room_grid(sc2, "r")
    assert grid2.cells == grid.cells
    assert {a: r["cells"] for a, r in anchor_cells(sc2, "r").items()} == \
           {a: r["cells"] for a, r in anchor_cells(sc, "r").items()}
    # And an `l` written with a cell part reads as the union too.
    sc3 = scene({"name": "R", "extent": {"w": 8, "d": 8}, "shape": "l",
                 "parts": [{"w": 8, "d": 3, "at": [0, 0]}, {"w": 3, "d": 8, "at": [5, 0]}]})
    assert room_grid(sc3, "r").cells == grid.cells


def test_a_t_a_u_and_a_room_with_a_bay_are_unions_and_the_notch_is_not_the_room():
    tee = scene({"name": "T", "extent": {"w": 9, "d": 6}, "shape": "composite",
                 "parts": [{"w": 9, "d": 2, "at": "nw"}, {"w": 3, "d": 6, "at": [3, 0]}]})
    grid = room_grid(tee, "r")
    assert (grid.w, grid.d, grid.shape) == (9, 6, "composite")
    assert (0, 0) in grid.cells and (4, 5) in grid.cells
    assert (0, 3) not in grid.cells and (8, 5) not in grid.cells
    assert len(grid.cells) == 9 * 2 + 3 * 4
    # The T's stem has two inner walls facing east and west: the rim of a
    # bearing includes them, in wall order.
    east = grid.rim("e")
    assert (8, 0) in east and (8, 1) in east and (5, 2) in east and (5, 5) in east
    assert east == sorted(east, key=lambda c: (c[1], c[0]))
    # Its south rim is the stem's foot AND the underside of the bar.
    south = grid.rim("s")
    assert {(3, 5), (4, 5), (5, 5)} <= set(south) and (0, 1) in south and (8, 1) in south

    cup = scene({"name": "U", "extent": {"w": 7, "d": 5}, "shape": "composite",
                 "parts": [{"w": 2, "d": 5, "at": "nw"}, {"w": 2, "d": 5, "at": "ne"},
                           {"w": 7, "d": 2, "at": "sw"}]})
    grid = room_grid(cup, "r")
    assert (3, 0) not in grid.cells and (3, 4) in grid.cells
    assert grid.corner("ne") == (6, 0) and grid.corner("sw") == (0, 4)

    bay = scene({"name": "Bay", "extent": {"w": 6, "d": 6}, "shape": "composite",
                 "parts": [{"w": 6, "d": 4, "at": "nw"}, {"w": 2, "d": 2, "at": [2, 4]}]})
    grid = room_grid(bay, "r")
    assert len(grid.cells) == 24 + 4
    assert grid.nearest((0, 5)) == (2, 5) or grid.nearest((0, 5)) == (0, 3)


def test_a_composite_with_no_extent_is_the_box_its_parts_need():
    sc = scene({"name": "R", "shape": "composite",
                "parts": [{"w": 4, "d": 2, "at": [0, 0]}, {"w": 2, "d": 5, "at": [1, 2]}]})
    grid = room_grid(sc, "r")
    assert (grid.w, grid.d) == (4, 7) and grid.measured
    assert len(grid.cells) == 8 + 10


def test_a_doorway_on_a_composite_rim_places_as_on_an_l():
    """The notch's inner wall is a wall: a neighbour hung off it is laid
    beyond it with the door cells aligned, exactly as an L's would be."""
    def build(shape):
        return scene(
            {"name": "R", "extent": {"w": 8, "d": 8}, "shape": shape, "parts": L_PARTS,
             "adjacent": [{"to": "q", "barrier": "open", "dir": "s", "offset": 0.0}]},
            rooms={"q": {"name": "Q", "size": "small",
                         "adjacent": [{"to": "r", "barrier": "open", "dir": "n"}]}})
    ell, comp = build("l"), build("composite")
    door_l = anchor_cells(ell, "r")["door:q"]
    door_c = anchor_cells(comp, "r")["door:q"]
    assert door_l["cells"] == door_c["cells"]
    # Offset 0 on the south rim: the FIRST south-facing cell in wall order --
    # the underside of the west arm, (0, 2) -- not the box's bottom row.
    assert door_c["cells"] == [(0, 2)]
    field_l, field_c = room_field(ell, "r"), room_field(comp, "r")
    assert field_c.offsets == field_l.offsets and "q" in field_c.offsets
    assert field_c.walls == field_l.walls
    # The wall line stands where the neighbour meets the arm's underside.
    wall = field_c.walls[0]
    assert wall["axis"] == 1 and wall["coord"] == 3


# ---------------------------------------------------------------------------
# The lint
# ---------------------------------------------------------------------------

def test_parts_that_do_not_touch_are_a_row_not_a_refusal_and_not_two_rows():
    sc = scene({"name": "R", "extent": {"w": 8, "d": 8}, "shape": "composite",
                "parts": [{"w": 3, "d": 3, "at": "nw"}, {"w": 3, "d": 3, "at": "se"}]})
    rows = room_layout_lint(sc)
    kinds = [r["kind"] for r in rows]
    assert kinds == ["parts_disconnected"], rows
    assert rows[0]["pieces"] == [["nw"], ["se"]]
    assert "parts_disconnected" in LAYOUT_LINT_KINDS
    sentence = layout_warning(rows[0])
    assert "nw" in sentence and "se" in sentence and "touch" in sentence
    # The grid still exists -- the row is advice, not a refusal.
    assert len(room_grid(sc, "r").cells) == 18
    # Touching along an edge is one floor; a corner touch alone is not.
    joined = scene({"name": "R", "extent": {"w": 8, "d": 8}, "shape": "composite",
                    "parts": [{"w": 3, "d": 3, "at": "nw"}, {"w": 3, "d": 3, "at": [3, 0]},
                              {"w": 2, "d": 2, "at": [6, 3]}]})
    rows = room_layout_lint(joined)
    assert [r["kind"] for r in rows] == ["parts_disconnected"]
    assert rows[0]["pieces"] == [["nw", "3,0"], ["6,3"]]
    corner = scene({"name": "R", "extent": {"w": 6, "d": 6}, "shape": "composite",
                    "parts": [{"w": 3, "d": 3, "at": "nw"}, {"w": 3, "d": 3, "at": "se"}]})
    assert [r["kind"] for r in room_layout_lint(corner)] == ["parts_disconnected"]
    whole = scene({"name": "R", "extent": {"w": 9, "d": 6}, "shape": "composite",
                   "parts": [{"w": 9, "d": 2, "at": "nw"}, {"w": 3, "d": 6, "at": [3, 0]}]})
    assert room_layout_lint(whole) == []


def test_an_l_keeps_its_redundant_part_row_and_a_composite_does_not_borrow_it():
    parts = [{"w": 8, "d": 8, "at": "nw"}, {"w": 3, "d": 3, "at": "ne"}]
    ell = scene({"name": "R", "extent": {"w": 8, "d": 8}, "shape": "l", "parts": parts})
    assert [r["kind"] for r in room_layout_lint(ell)] == ["l_part_redundant"]
    comp = scene({"name": "R", "extent": {"w": 8, "d": 8}, "shape": "composite", "parts": parts})
    assert room_layout_lint(comp) == []


# ---------------------------------------------------------------------------
# Byte-identity without parts, and the schema
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("room", [
    {"size": "small"}, {"size": "large"}, {"extent": {"w": 12, "d": 4}},
    {"extent": {"w": 8, "d": 8}, "shape": "round"},
    {"extent": {"w": 8, "d": 8}, "shape": "l", "parts": L_PARTS},
])
def test_a_room_without_composite_parts_is_unchanged_and_junk_parts_are_no_parts(room):
    anchors = {"bar": {"desc": "the bar", "dir": "n", "footprint": "run", "height": "waist"},
               "stool": {"desc": "a stool"}, "urn": {"desc": "an urn", "dir": "ne"}}
    base = scene({"name": "R", **room, "anchors": anchors})
    grid = room_grid(base, "r")
    placed = {a: r["cells"] for a, r in anchor_cells(base, "r").items()}
    # Parts on a rectangle or a round room are ignored by the grid, as before.
    if room.get("shape") != "l":
        junk = scene({"name": "R", **room, "anchors": anchors,
                      "parts": [{"w": 2, "d": 2, "at": [0, 0]}]})
        assert room_grid(junk, "r").cells == grid.cells
        assert {a: r["cells"] for a, r in anchor_cells(junk, "r").items()} == placed
    # A composite whose parts are all junk is the bounding box, cell for cell.
    comp = scene({"name": "R", **{k: v for k, v in room.items() if k != "parts"},
                  "shape": "composite", "anchors": anchors,
                  "parts": ["x", {"w": 2, "d": 2, "at": "middle"}, {"at": [1, 1]}]})
    cgrid = room_grid(comp, "r")
    if room.get("extent"):
        assert cgrid.cells == frozenset((x, y) for x in range(cgrid.w) for y in range(cgrid.d))
        assert (cgrid.w, cgrid.d) == (room["extent"]["w"], room["extent"]["d"])
    else:
        assert (cgrid.w, cgrid.d) == (grid.w, grid.d)


def test_the_schema_keeps_a_corner_or_a_cell_part_and_heals_junk_to_none():
    room = RoomDef.model_validate({
        "name": "R", "shape": "composite",
        "parts": [{"w": 4, "d": 2, "at": "nw"}, {"w": 2, "d": 4, "at": [3, 0]},
                  {"w": 2, "d": 2, "at": [1.0, 2.0]}, {"w": 2, "d": 2, "at": [True, 1]},
                  {"w": "wide", "d": 2, "at": "ne"}, {"w": 2, "d": 2}]})
    assert room.shape == "composite"
    assert room.parts == [{"w": 4.0, "d": 2.0, "at": "nw"}, {"w": 2.0, "d": 4.0, "at": [3, 0]},
                          {"w": 2.0, "d": 2.0, "at": [1, 2]}]
    assert RoomDef.model_validate({"name": "R", "parts": "two bits"}).parts is None
    assert RoomDef.model_validate({"name": "R", "parts": [{"w": 2, "d": 2}]}).parts is None
