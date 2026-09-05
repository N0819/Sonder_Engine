"""The `cell` field on a station and on an anchor: a place in the room's own
grid, written by the World Browser's map editor and never by the Director.

The owner's ruling, live on the map (2026-09-04): "Why are characters and
personas locked to stations in the editor? ... I have to drag them to
stations." and, of anchors, "I can only place anchors at stations when I
don't wall-attach them, which is quite limiting." The station schema and
the anchor placement had no cell, so a drop could only snap to an anchor or
a wall.

Design: `docs/design/DESIGN_ROOM_FIDELITY.md` §10, `DESIGN_ROOM_GEOMETRY.md`
§2. The contract under test:

  * ABSENT, the derivation is byte for byte what it was, on every shape --
    `FROZEN` below is `body_cell`/`anchor_cells` as computed by the code
    BEFORE the field existed (`artefacts/freeze_cells.py`, run once on
    commit 3fd69a1f, then deleted), so a drift in the reduction is a failing
    test and not a quietly moved body;
  * PRESENT and inside the room, the cell is the body's cell / the anchor's
    origin, `at` and `dir` kept for prose and moving nothing;
  * OUTSIDE the room (the extent or shape moved since), the nearest cell,
    ties to the smaller coordinates -- the fail-open for a shrunk room;
  * JUNK (not two whole numbers) is no cell, and the hygiene drops it;
  * a body that CHANGES ROOM loses its cell in the merge -- a cell in
    another room's coordinates means nothing -- and a re-echo that leaves
    the field out keeps it;
  * a cell is the precise place of the STATION it was pinned with, so an
    incoming `at` naming another anchor takes it down and a re-echo of the
    same anchor, a station that names no `at`, and an `at` cleared to
    nothing all keep it (the owner's ruling of 2026-09-05, F39, reversing
    the half of the 2026-09-04 ruling that let a pin outrank a Director
    `at` that named somewhere else);
  * proximity reads cell distance ONLY when a pin is involved, so every
    anchor-tier answer stands.
"""

from __future__ import annotations

import copy

import pytest

from world.spatial import (
    CELL_NEAR_DIVISOR, CELL_REACH_PACES, _merge_room, anchor_cells, body_cell,
    body_cell_source, body_visibility, invalidate_moved_body_cells,
    measured_proximity_rel, merge_scene_with_diff, normalize_cell,
    normalize_scene_anchor_cells, normalize_scene_stations, proximity_rel,
    room_grid,
)


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

SHAPES = {
    "small": {"size": "small"},
    "large": {"size": "large"},
    "vast": {"size": "vast"},
    "wide": {"extent": {"w": 12, "d": 4}},
    "round": {"extent": {"w": 8, "d": 8}, "shape": "round"},
    "l": {"extent": {"w": 8, "d": 8}, "shape": "l",
          "parts": [{"w": 8, "d": 3, "at": "nw"}, {"w": 3, "d": 8, "at": "ne"}]},
}

# THE PIN. Per shape: every anchor's cells; P's cell `at` each anchor; P's
# cell `at` each anchor with `cover`; Q's cell `near` P at each anchor.
FROZEN = {
    "small": {
        "anchors": {"bar": [[1, 1], [2, 1]], "screen": [[2, 1], [2, 2]], "hearth": [[2, 3]],
                    "door": [[0, 2]], "urn": [[2, 1]],
                    "table": [[1, 2], [1, 3], [2, 2], [2, 3]], "stool": [[1, 1]],
                    "keg": [[1, 1], [1, 2], [2, 1], [2, 2]], "door:q": [[2, 0]]},
        "at": {"bar": [2, 2], "screen": [1, 2], "hearth": [2, 2], "door": [1, 2], "urn": [1, 2],
               "table": [3, 3], "stool": [2, 1], "keg": [0, 2], "door:q": [2, 1]},
        "cover": {"bar": [2, 0], "screen": [3, 2], "hearth": [2, 2], "door": [1, 2],
                  "urn": [3, 0], "table": [3, 3], "stool": [0, 1], "keg": [0, 2],
                  "door:q": [2, 1]},
        "near": {"bar": [2, 3], "screen": [1, 3], "hearth": [2, 3], "door": [1, 3],
                 "urn": [1, 3], "table": [3, 3], "stool": [2, 2], "keg": [0, 3],
                 "door:q": [2, 2]}},
    "large": {
        "anchors": {"bar": [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1]],
                    "screen": [[6, 1], [6, 2], [6, 3], [6, 4], [6, 5], [6, 6]],
                    "hearth": [[6, 7]], "door": [[0, 6]], "urn": [[6, 1]],
                    "table": [[1, 2], [1, 3], [2, 2], [2, 3]], "stool": [[1, 1]],
                    "keg": [[5, 2], [5, 3], [6, 2], [6, 3]], "door:q": [[6, 0]]},
        "at": {"bar": [6, 2], "screen": [5, 4], "hearth": [6, 6], "door": [1, 6], "urn": [5, 2],
               "table": [3, 3], "stool": [2, 1], "keg": [4, 3], "door:q": [6, 1]},
        "cover": {"bar": [6, 0], "screen": [7, 4], "hearth": [6, 6], "door": [1, 6],
                  "urn": [7, 0], "table": [3, 3], "stool": [0, 1], "keg": [4, 3],
                  "door:q": [6, 1]},
        "near": {"bar": [6, 3], "screen": [5, 5], "hearth": [6, 7], "door": [1, 7],
                 "urn": [5, 3], "table": [3, 4], "stool": [2, 2], "keg": [4, 4],
                 "door:q": [6, 2]}},
    "vast": {
        "anchors": {"bar": [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1], [7, 1], [8, 1],
                            [9, 1], [10, 1]],
                    "screen": [[10, 1], [10, 2], [10, 3], [10, 4], [10, 5], [10, 6], [10, 7],
                               [10, 8], [10, 9], [10, 10]],
                    "hearth": [[6, 11]], "door": [[0, 6]], "urn": [[10, 1]],
                    "table": [[9, 10], [9, 11], [10, 10], [10, 11]], "stool": [[7, 9]],
                    "keg": [[9, 7], [9, 8], [10, 7], [10, 8]], "door:q": [[8, 0]]},
        "at": {"bar": [4, 2], "screen": [9, 8], "hearth": [6, 10], "door": [1, 6], "urn": [9, 2],
               "table": [11, 11], "stool": [6, 9], "keg": [8, 8], "door:q": [8, 1]},
        "cover": {"bar": [4, 0], "screen": [11, 8], "hearth": [6, 10], "door": [1, 6],
                  "urn": [11, 0], "table": [11, 11], "stool": [8, 9], "keg": [8, 8],
                  "door:q": [8, 1]},
        "near": {"bar": [4, 3], "screen": [9, 9], "hearth": [6, 11], "door": [1, 7],
                 "urn": [9, 3], "table": [11, 11], "stool": [6, 10], "keg": [8, 9],
                 "door:q": [8, 2]}},
    "wide": {
        "anchors": {"bar": [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1], [7, 1], [8, 1],
                            [9, 1], [10, 1]],
                    "screen": [[10, 1], [10, 2]], "hearth": [[6, 3]], "door": [[0, 2]],
                    "urn": [[10, 1]], "table": [[9, 2], [9, 3], [10, 2], [10, 3]],
                    "stool": [[7, 1]], "keg": [[9, 1], [9, 2], [10, 1], [10, 2]],
                    "door:q": [[8, 0]]},
        "at": {"bar": [4, 2], "screen": [9, 2], "hearth": [6, 2], "door": [1, 2], "urn": [9, 2],
               "table": [11, 3], "stool": [6, 1], "keg": [8, 2], "door:q": [8, 1]},
        "cover": {"bar": [4, 0], "screen": [11, 2], "hearth": [6, 2], "door": [1, 2],
                  "urn": [11, 0], "table": [11, 3], "stool": [8, 1], "keg": [8, 2],
                  "door:q": [8, 1]},
        "near": {"bar": [4, 3], "screen": [9, 3], "hearth": [6, 3], "door": [1, 3],
                 "urn": [9, 3], "table": [11, 3], "stool": [6, 2], "keg": [8, 3],
                 "door:q": [8, 2]}},
    "round": {
        "anchors": {"bar": [[1, 2], [2, 1], [3, 1], [4, 1], [5, 1], [6, 2]],
                    "screen": [[5, 1], [5, 6], [6, 2], [6, 3], [6, 4], [6, 5]],
                    "hearth": [[6, 6]], "door": [[1, 6]], "urn": [[4, 1]],
                    "table": [[1, 2], [1, 3], [2, 2], [2, 3]], "stool": [[1, 1]],
                    "keg": [[5, 2], [5, 3], [6, 2], [6, 3]], "door:q": [[6, 1]]},
        "at": {"bar": [6, 3], "screen": [5, 3], "hearth": [6, 5], "door": [2, 6], "urn": [3, 2],
               "table": [3, 3], "stool": [2, 1], "keg": [4, 3], "door:q": [6, 2]},
        "cover": {"bar": [6, 1], "screen": [7, 3], "hearth": [6, 5], "door": [2, 6],
                  "urn": [5, 0], "table": [3, 3], "stool": [2, 1], "keg": [4, 3],
                  "door:q": [6, 2]},
        "near": {"bar": [6, 4], "screen": [5, 4], "hearth": [6, 6], "door": [2, 7],
                 "urn": [3, 3], "table": [3, 4], "stool": [2, 2], "keg": [4, 4],
                 "door:q": [6, 3]}},
    "l": {
        "anchors": {"bar": [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1]],
                    "screen": [[6, 1], [6, 2], [6, 3], [6, 4], [6, 5], [6, 6]],
                    "hearth": [[6, 7]], "door": [[5, 6]], "urn": [[6, 1]],
                    "table": [[1, 2], [2, 2]], "stool": [[1, 1]],
                    "keg": [[5, 2], [5, 3], [6, 2], [6, 3]], "door:q": [[6, 0]]},
        "at": {"bar": [6, 2], "screen": [5, 4], "hearth": [6, 6], "door": [6, 6], "urn": [5, 2],
               "table": [3, 2], "stool": [2, 1], "keg": [5, 4], "door:q": [6, 1]},
        "cover": {"bar": [6, 0], "screen": [7, 4], "hearth": [6, 6], "door": [6, 6],
                  "urn": [7, 0], "table": [3, 2], "stool": [0, 1], "keg": [5, 4],
                  "door:q": [6, 1]},
        "near": {"bar": [6, 3], "screen": [5, 5], "hearth": [6, 7], "door": [6, 7],
                 "urn": [5, 3], "table": [3, 2], "stool": [2, 2], "keg": [5, 5],
                 "door:q": [6, 2]}},
}

#: Not a cell: a boolean, prose, one number, three, a mapping, a fraction.
JUNK = (None, True, "3,2", 3, [3], [3, 2, 1], {"x": 3, "y": 2}, [1.5, 2], [True, 1],
        ["3", "2"], (), "")


def scene(room, stations=None, anchors=None, positions=None):
    return {"rooms": {"r": {"name": "R", **room,
                            "anchors": copy.deepcopy(anchors if anchors is not None else ANCHORS),
                            "adjacent": [{"to": "q", "barrier": "open", "dir": "n"}]},
                      "q": {"name": "Q", "size": "small"}},
            "positions": dict(positions or {"P": "r", "Q": "r"}),
            "stations": copy.deepcopy(stations or {}), "orientation": {},
            "poses": {}, "entities": {}}


# ---------------------------------------------------------------------------
# The pin: absent, byte for byte what it was
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_without_a_cell_every_body_and_anchor_stands_where_it_did(shape):
    room = SHAPES[shape]
    frozen = FROZEN[shape]
    placed = {aid: [list(c) for c in rec["cells"]]
              for aid, rec in anchor_cells(scene(room), "r").items()}
    assert placed == frozen["anchors"]
    for rec in anchor_cells(scene(room), "r").values():
        assert rec["cell"] is None
        assert rec["source"] in ("seed", "offset")
    for aid in list(ANCHORS) + ["door:q"]:
        assert list(body_cell(scene(room, {"P": {"at": aid}}), "P")) == frozen["at"][aid]
        assert list(body_cell(scene(room, {"P": {"at": aid, "cover": True}}), "P")) \
            == frozen["cover"][aid]
        assert list(body_cell(scene(room, {"P": {"at": aid}, "Q": {"near": ["P"]}}), "Q")) \
            == frozen["near"][aid]
        assert body_cell_source(scene(room, {"P": {"at": aid}}), "P") == "anchor"
    assert body_cell(scene(room), "P") is None
    assert body_cell_source(scene(room), "P") == "none"


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("junk", JUNK)
def test_a_cell_that_does_not_read_is_no_cell(shape, junk):
    """A junk `cell` on a station or an anchor places exactly as no cell."""
    room = SHAPES[shape]
    for aid in ANCHORS:
        assert body_cell(scene(room, {"P": {"at": aid, "cell": junk}}), "P") \
            == body_cell(scene(room, {"P": {"at": aid}}), "P")
    assert body_cell(scene(room, {"P": {"cell": junk}}), "P") is None
    anchors = {aid: {**a, "cell": junk} for aid, a in ANCHORS.items()}
    assert {aid: rec["cells"] for aid, rec in anchor_cells(scene(room, anchors=anchors), "r").items()} \
        == {aid: rec["cells"] for aid, rec in anchor_cells(scene(room), "r").items()}
    assert normalize_cell(junk) is None


def test_normalize_cell_reads_two_whole_numbers_and_nothing_else():
    assert normalize_cell([3, 2]) == (3, 2)
    assert normalize_cell((3, 2)) == (3, 2)
    assert normalize_cell([3.0, 2.0]) == (3, 2)      # JSON round-trips may float
    assert normalize_cell([-1, 0]) == (-1, 0)        # outside is the reader's question
    for junk in JUNK:
        assert normalize_cell(junk) is None


# ---------------------------------------------------------------------------
# Present: the body's cell, the anchor's origin
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_a_pinned_body_stands_on_its_cell_and_keeps_at_for_prose(shape):
    room = SHAPES[shape]
    grid = room_grid(scene(room), "r")
    for cell in sorted(grid.cells):
        sc = scene(room, {"P": {"at": "hearth", "cell": list(cell)}})
        assert body_cell(sc, "P") == cell
        assert body_cell_source(sc, "P") == "cell"
        # `at` is untouched: the effective station still says "at the hearth".
        from world.spatial import effective_station
        assert effective_station(sc, "P")["at"] == "hearth"
        # A cell with no `at` at all places too.
        assert body_cell(scene(room, {"P": {"cell": list(cell)}}), "P") == cell


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_a_pinned_anchor_lays_its_footprint_from_its_origin(shape):
    """The origin is the west-most, north-most cell; the footprint runs east
    (and, for `large`, south) from it, clipped to the room; `dir` moves
    nothing -- no inset, no wall cells -- and `offset` yields to the cell."""
    room = SHAPES[shape]
    grid = room_grid(scene(room), "r")
    for cell in sorted(grid.cells):
        x, y = cell
        anchors = {
            "point": {"desc": "p", "dir": "n", "offset": 0.9, "cell": [x, y]},
            "small": {"desc": "s", "footprint": "small", "cell": [x, y]},
            "run": {"desc": "r", "footprint": "run", "dir": "e", "cell": [x, y]},
            "large": {"desc": "l", "footprint": "large", "height": "waist", "dir": "s",
                      "cell": [x, y]},
            "corner": {"desc": "c", "dir": "ne", "cell": [x, y]},
        }
        placed = anchor_cells(scene(room, anchors=anchors), "r")
        expect_pair = [c for c in [(x, y), (x + 1, y)] if grid.contains(c)]
        expect_large = [c for c in [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
                        if grid.contains(c)]
        assert placed["point"]["cells"] == [(x, y)]
        assert placed["small"]["cells"] == sorted(expect_pair)
        assert placed["run"]["cells"] == sorted(expect_pair)
        assert placed["large"]["cells"] == sorted(expect_large)
        assert placed["corner"]["cells"] == [(x, y)]
        for aid in anchors:
            rec = placed[aid]
            assert rec["source"] == "cell" and rec["cell"] == [x, y]
            assert min(rec["cells"]) == (x, y)          # the origin is the first cell
        assert placed["door:q"]["source"] == "seed"     # the edge's door, unpinned
        # `dir` rides through for prose; `offset` is read but outranked.
        assert placed["point"]["dir"] == "n" and placed["point"]["offset"] == 0.9


# ---------------------------------------------------------------------------
# Outside: the nearest cell the room still holds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_a_cell_the_room_no_longer_holds_snaps_to_the_nearest(shape):
    room = SHAPES[shape]
    grid = room_grid(scene(room), "r")
    for cell in ((grid.w + 3, grid.d + 3), (-2, -2), (grid.w, 0), (0, grid.d), (-1, grid.d // 2)):
        expected = grid.nearest(cell)
        assert expected in grid.cells
        assert body_cell(scene(room, {"P": {"cell": list(cell)}}), "P") == expected
        placed = anchor_cells(scene(room, anchors={"a": {"desc": "a", "cell": list(cell)}}), "r")
        assert placed["a"]["cells"] == [expected]
        assert placed["a"]["source"] == "cell"


def test_the_snap_breaks_ties_to_the_smaller_coordinates():
    """A round room's notch: (0, 0) is outside an 8x8 round room and equally
    far from two cells; the smaller pair wins, so a reroll agrees."""
    grid = room_grid(scene(SHAPES["round"]), "r")
    assert (0, 0) not in grid.cells
    nearest = grid.nearest((0, 0))
    ties = [c for c in grid.cells
            if (c[0] ** 2 + c[1] ** 2) == (nearest[0] ** 2 + nearest[1] ** 2)]
    assert nearest == min(ties)
    assert body_cell(scene(SHAPES["round"], {"P": {"cell": [0, 0]}}), "P") == nearest


def test_the_l_notch_is_not_a_cell_a_body_can_hold():
    """An L's notch is inside the box and outside the room; a body pinned
    there snaps into the room, exactly as a shrunk extent would."""
    sc = scene(SHAPES["l"], {"P": {"cell": [1, 6]}})
    grid = room_grid(sc, "r")
    assert (1, 6) not in grid.cells
    assert body_cell(sc, "P") == grid.nearest((1, 6))
    assert body_cell(sc, "P") in grid.cells


# ---------------------------------------------------------------------------
# Durability: hygiene, the merge, a change of room
# ---------------------------------------------------------------------------

def test_station_hygiene_keeps_a_cell_and_drops_junk():
    sc = scene(SHAPES["large"], {"P": {"at": "bar", "near": [], "cell": [3, 2]},
                                 "Q": {"at": None, "near": [], "cell": "3,2"}})
    normalize_scene_stations(sc)
    assert sc["stations"]["P"]["cell"] == [3, 2]
    assert "cell" not in sc["stations"]["Q"]
    # A tuple or a float pair is written back as two ints.
    sc = scene(SHAPES["large"], {"P": {"cell": (3.0, 2.0)}})
    normalize_scene_stations(sc)
    assert sc["stations"]["P"]["cell"] == [3, 2]


def test_anchor_hygiene_keeps_a_cell_and_drops_junk():
    sc = scene(SHAPES["large"], anchors={"bar": {"desc": "b", "cell": [3, 2]},
                                          "keg": {"desc": "k", "cell": [3]},
                                          "urn": {"desc": "u"}})
    dropped = normalize_scene_anchor_cells(sc)
    assert dropped == [("r", "keg")]
    assert sc["rooms"]["r"]["anchors"]["bar"]["cell"] == [3, 2]
    assert "cell" not in sc["rooms"]["r"]["anchors"]["keg"]
    assert "cell" not in sc["rooms"]["r"]["anchors"]["urn"]


def test_the_merge_keeps_a_station_cell_a_re_echo_left_out():
    """A re-echo of the SAME anchor keeps the pin, and so does silence.

    This is the half of the 2026-09-04 ruling that survives: the Director
    hands back a station it never thought about (`_coerce_station_table`
    keeps only `at`/`near`, so it can never write a cell), and a host's
    "at the bar, this end of it" must not be flattened by it.
    """
    sc = scene(SHAPES["large"], {"P": {"at": "bar", "near": [], "cell": [3, 2]}})
    merged = merge_scene_with_diff(sc, {"stations": {"P": {"at": "bar"}}})
    assert merged["stations"]["P"] == {"at": "bar", "near": [], "cell": [3, 2]}
    assert body_cell(merged, "P") == (3, 2)
    # Silence about the anchor is not a statement about where the body
    # stands: a diff touching only `near` leaves the pin alone.
    merged = merge_scene_with_diff(sc, {"stations": {"P": {"near": ["Q"]}}})
    assert merged["stations"]["P"]["cell"] == [3, 2]
    assert body_cell(merged, "P") == (3, 2)


def test_the_merge_drops_a_station_cell_when_the_at_names_another_anchor():
    """A cell is the precise place of the station it was pinned with, so a
    changed `at` takes it down (the owner's ruling of 2026-09-05, F39 of
    `docs/experiments/DEBUG_RUN_2026_09_05.md`, reversing the 2026-09-04
    ruling that the map's pin outranked a Director `at` on exactly this
    shape).

    Chat 115, turn 4: the resolve moved a body from the north control panel
    to the east threshold, the merge kept the map's `cell: [0, 1]` on the
    west wall, and `body_cell` reads the cell FIRST -- so every field drew
    her at the west wall while every ledger said the east sill, and turn 6
    moved her again with the pin still on her. A changed `at` is all the
    Director can say, and a body drawn where no record puts her is worse
    than a host having to pin again.
    """
    sc = scene(SHAPES["large"], {"P": {"at": "bar", "near": [], "cell": [3, 2]}})
    merged = merge_scene_with_diff(sc, {"stations": {"P": {"at": "hearth"}}})
    assert merged["stations"]["P"] == {"at": "hearth", "near": []}
    assert body_cell(merged, "P") == tuple(FROZEN["large"]["at"]["hearth"])
    # The same in the other direction: an anchor named over a FREE pin (a
    # cell with no `at`, what the map writes for a body dropped on open
    # floor) is the story putting the body somewhere, and it wins too.
    free = scene(SHAPES["large"], {"P": {"at": None, "near": [], "cell": [3, 2]}})
    merged = merge_scene_with_diff(free, {"stations": {"P": {"at": "bar"}}})
    assert "cell" not in merged["stations"]["P"]
    # A cell the diff itself carries is written with the new anchor, so it
    # lands rather than being taken down with the old one.
    merged = merge_scene_with_diff(
        sc, {"stations": {"P": {"at": "hearth", "cell": [5, 5]}}})
    assert merged["stations"]["P"]["cell"] == [5, 5]


def test_an_at_cleared_to_nothing_is_not_a_move_and_keeps_the_cell():
    """The adjacent case, decided with F39 (2026-09-05): leaving an anchor
    is not arriving anywhere.

    `at: null` says the body no longer stands AT the thing; it names no
    other place, so nothing contradicts the pin and the body stands where
    it stood. A cell with no `at` is a supported record everywhere else --
    it is what a drop on open floor writes -- so keeping it invents no
    state, where dropping it would move a body nothing asked to move.
    """
    sc = scene(SHAPES["large"], {"P": {"at": "bar", "near": [], "cell": [3, 2]}})
    merged = merge_scene_with_diff(sc, {"stations": {"P": {"at": None}}})
    assert merged["stations"]["P"] == {"at": None, "near": [], "cell": [3, 2]}
    assert body_cell(merged, "P") == (3, 2)


def test_the_merge_keeps_an_anchor_cell_a_re_echo_left_out():
    existing = {"name": "R", "anchors": {"bar": {"desc": "the bar", "dir": "n",
                                                 "height": "waist", "cell": [3, 2]}}}
    merged = _merge_room(existing, {"name": "R", "anchors": {
        "bar": {"desc": "the long bar", "dir": "n"}}}, "r")
    assert merged["anchors"]["bar"] == {"desc": "the long bar", "dir": "n",
                                        "height": "waist", "cell": [3, 2]}
    # And through the whole merge, junk written over it is dropped again.
    sc = scene(SHAPES["large"], anchors={"bar": {"desc": "b", "dir": "n", "cell": [3, 2]}})
    merged = merge_scene_with_diff(sc, {"rooms": {"r": {"anchors": {
        "bar": {"desc": "b", "cell": "nowhere"}}}}})
    assert "cell" not in merged["rooms"]["r"]["anchors"]["bar"]


def test_a_body_that_changes_room_loses_its_cell_in_the_merge():
    sc = scene(SHAPES["large"], {"P": {"at": "bar", "near": [], "cell": [3, 2]},
                                 "Q": {"at": None, "near": [], "cell": [1, 1]}})
    merged = merge_scene_with_diff(sc, {"positions": {"P": "q"}})
    assert merged["positions"]["P"] == "q"
    assert "cell" not in merged["stations"]["P"]
    assert merged["stations"]["P"]["at"] is None          # the old hygiene, unchanged
    assert merged["stations"]["Q"]["cell"] == [1, 1]     # the body that stayed keeps it


def test_invalidate_moved_body_cells_compares_against_where_the_body_was():
    sc = scene(SHAPES["large"], {"P": {"cell": [3, 2]}, "Q": {"cell": [1, 1]},
                                 "N": {"cell": [0, 0]}},
               positions={"P": "q", "Q": "r", "N": "r"})
    moved = invalidate_moved_body_cells(sc, {"P": "r", "Q": "r"})
    assert moved == [("P", "r", "q")]
    assert "cell" not in sc["stations"]["P"]
    assert sc["stations"]["Q"]["cell"] == [1, 1]
    assert sc["stations"]["N"]["cell"] == [0, 0]          # newly placed, not moved
    assert invalidate_moved_body_cells(sc, None) == []
    assert invalidate_moved_body_cells({"stations": {}, "positions": {}}, {}) == []


# ---------------------------------------------------------------------------
# What a pin measures: sight and proximity
# ---------------------------------------------------------------------------

def test_a_pinned_body_is_measured_for_sight():
    """Two pinned bodies with the head-high screen between them: the line
    subtracts. Without pins the same pair is open, as before."""
    room = {"extent": {"w": 8, "d": 8}}
    anchors = {"screen": {"desc": "a folding screen", "footprint": "run",
                          "height": "full", "cell": [3, 3]}}
    pinned = scene(room, {"P": {"cell": [3, 1]}, "Q": {"cell": [3, 6]}}, anchors=anchors)
    seen = body_visibility(pinned, "P", "Q")
    assert seen["basis"] == "line"
    assert seen["visible"] is False
    assert seen["occluded_by"] == "a folding screen"
    assert body_visibility(scene(room, anchors=anchors), "P", "Q")["basis"] == "open"


def test_proximity_reads_cell_distance_only_when_a_pin_is_involved():
    room = {"extent": {"w": 12, "d": 12}}
    # Both pinned: reach at one pace (a diagonal counts), near under a third
    # of the longer side, across beyond.
    assert CELL_REACH_PACES == 1 and CELL_NEAR_DIVISOR == 3
    close = scene(room, {"P": {"cell": [2, 2]}, "Q": {"cell": [3, 3]}})
    assert proximity_rel(close, "P", "Q") == "within_reach"
    assert measured_proximity_rel(close, "P", "Q") == "within_reach"
    apart = scene(room, {"P": {"cell": [2, 2]}, "Q": {"cell": [5, 2]}})
    assert proximity_rel(apart, "P", "Q") == "near"
    assert measured_proximity_rel(apart, "P", "Q") == "near"    # a measurement, not the default
    far = scene(room, {"P": {"cell": [0, 0]}, "Q": {"cell": [11, 11]}})
    assert proximity_rel(far, "P", "Q") == "across"
    # One pinned, the other at an anchor: the anchor's derived cell is the
    # other end of the measurement.
    mixed = scene(room, {"P": {"at": "hearth"}, "Q": {"cell": [0, 0]}})
    hearth = body_cell(mixed, "P")
    assert hearth is not None
    assert proximity_rel(mixed, "P", "Q") == "across"
    beside = scene(room, {"P": {"at": "hearth"}, "Q": {"cell": [hearth[0], hearth[1] - 1]}})
    assert proximity_rel(beside, "P", "Q") == "within_reach"
    # One pinned, the other unmeasured: no second cell, so the tier rule.
    lone = scene(room, {"P": {"cell": [0, 0]}})
    assert proximity_rel(lone, "P", "Q") == "near"
    assert measured_proximity_rel(lone, "P", "Q") is None


def test_the_anchor_tier_rule_is_untouched_where_nothing_is_pinned():
    """Two anchors in a medium room are `near`; in a large room `across`;
    one anchor `within_reach` -- the rule `tests/test_stations.py` pins,
    restated here beside the cell rule so a later widening has to face it.
    Both bodies DERIVE cells here, and the cell rule must not fire."""
    medium = scene({"size": "medium"}, {"P": {"at": "bar"}, "Q": {"at": "hearth"}})
    assert body_cell(medium, "P") and body_cell(medium, "Q")
    assert proximity_rel(medium, "P", "Q") == "near"
    large = scene({"size": "large"}, {"P": {"at": "bar"}, "Q": {"at": "hearth"}})
    assert proximity_rel(large, "P", "Q") == "across"
    same = scene({"size": "large"}, {"P": {"at": "bar"}, "Q": {"at": "bar"}})
    assert proximity_rel(same, "P", "Q") == "within_reach"
    assert proximity_rel(scene({"size": "large"}), "P", "Q") == "near"
