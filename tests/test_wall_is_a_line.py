"""The wall between two rooms is a line, and a doorway is a gap in it.

`world/spatial_fov.py` lays a neighbour's grid beyond an open doorway and
asks whether a straight line from an observer reaches a thing in it. Until
2026-09-04 that question was answered by which CELLS the line touched, with
the wall a cell thick and a rasteriser that over-covered every shallow step,
so a one-pace doorway admitted a third of the lines a real one does, and the
fix of the same day routed the line through the door in two legs -- which
let an observer beside the doorframe see round the corner. Both were the
cell model standing in for the geometry. These tests pin the geometry:

  * `_line` is an exact supercover -- the cells the segment touches, no more,
    and both cells at a corner it passes through;
  * a line into the next room is judged where it crosses the wall's LINE
    (`_wall_verdict`): through the gap or into the wall, at any angle;
  * the answer is symmetric, because a segment has no direction;
  * bodies and furniture beyond a doorway are graded by that one line.

The private names come through the `world.spatial` facade, which re-exports
them for exactly this: pinning the geometry rather than the callers' contract.
"""

from world.spatial import (
    _door_cells,
    _line,
    _occluders_on,
    _wall_verdict,
    body_cell,
    body_visibility,
    neighbour_feature_visibility,
    observer_field,
)


def _scene(rooms, positions, stations=None):
    return {"rooms": rooms, "positions": dict(positions),
            "stations": dict(stations or {}), "poses": {}}


def _pair(a_size="medium", b_size="medium", bearing="e", b_anchors=None):
    from world.spatial import opposite_bearing
    return _scene({
        "hall": {"name": "the Hall", "size": a_size,
                 "adjacent": [{"to": "yard", "barrier": "open_door",
                               "dir": bearing}],
                 "anchors": {}},
        "yard": {"name": "the Yard", "size": b_size,
                 "adjacent": [{"to": "hall", "barrier": "open_door",
                               "dir": opposite_bearing(bearing)}],
                 "anchors": dict(b_anchors or {})},
    }, {"P": "hall", "Q": "yard"})


def _cells_of(field, room):
    return sorted(c for c, r in field.inside.items() if r == room)


# ---------------------------------------------------------------------------
# The rasteriser
# ---------------------------------------------------------------------------

def test_the_supercover_is_exact():
    """(0,0)->(4,1) runs y = x/4: it is in row 0 until x = 2 and in row 1
    after, so it touches (1,0) (2,0) (2,1) (3,1) and nothing else. The old
    walk also produced (3,0), a cell the segment passes under."""
    assert _line((0, 0), (4, 1)) == [(1, 0), (2, 0), (2, 1), (3, 1)]
    assert _line((0, 0), (1, 0)) == []
    assert _line((0, 0), (0, 0)) == []


def test_a_corner_the_segment_passes_through_yields_both_cells():
    """The one thing a supercover adds to Bresenham, kept exactly: through
    the corner of four cells, both side cells count, so two occluders that
    meet at a corner still stop the line."""
    # (0,0)->(2,2) passes through the corner at (0.5,0.5) and again at
    # (1.5,1.5): both cells at each corner, and the diagonal cell between.
    cells = _line((0, 0), (2, 2))
    assert set(cells) == {(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)}
    assert set(_line((0, 0), (1, 1))) == {(1, 0), (0, 1)}
    field = observer_field(_pair(), "P")
    for cell in ((1, 0), (0, 1)):
        field.height[cell] = 3.0
        field.occluder[cell] = "screen"
    blocker, _t, _tid = _occluders_on(field, (0, 0), (2, 2), 2.0, 2.0)
    assert blocker == "screen"


def test_the_supercover_is_symmetric():
    for a, b in (((0, 0), (5, 2)), ((1, 4), (6, 0)), ((0, 0), (3, 3))):
        assert set(_line(a, b)) == set(_line(b, a))


# ---------------------------------------------------------------------------
# The wall as a line
# ---------------------------------------------------------------------------

def test_the_field_records_the_wall_as_a_line_with_the_doorway_as_a_gap():
    sc = _pair()
    field = observer_field(sc, "P")
    (wall,) = field.walls
    door, bearing = _door_cells(sc, "hall", "yard")
    assert bearing == "e" and wall["axis"] == 0
    assert wall["coord"] == door[0][0] + 1            # the band beyond the door
    assert wall["aperture"] == (door[0][1] - 0.5, door[0][1] + 0.5)
    assert wall["to"] == "yard"


def test_the_verdict_is_where_the_segment_crosses_the_wall():
    """Brute force against the geometry itself: for every pair of cells
    across the wall, the verdict equals whether the continuous segment
    crosses the wall's line inside the gap."""
    sc = _pair()
    field = observer_field(sc, "P")
    (wall,) = field.walls
    lo, hi = wall["aperture"]
    for o in _cells_of(field, "hall"):
        for t in _cells_of(field, "yard"):
            k = (wall["coord"] - o[0]) / float(t[0] - o[0])
            y = o[1] + k * (t[1] - o[1])
            assert _wall_verdict(field, o, t) == (lo <= y <= hi), (o, t)


def test_a_doorway_admits_the_lines_that_thread_it_and_the_answer_is_symmetric():
    sc = _pair()
    field = observer_field(sc, "P")
    hall, yard = _cells_of(field, "hall"), _cells_of(field, "yard")
    admitted = [(o, t) for o in hall for t in yard if _wall_verdict(field, o, t)]
    # More than a line dead through the centre, and less than the whole room.
    assert 0.2 < len(admitted) / float(len(hall) * len(yard)) < 0.4
    for o, t in admitted:
        assert _wall_verdict(field, t, o)
    # An empty pair of rooms: the walk agrees with the wall, cell for cell.
    for o in hall:
        for t in yard:
            blocker, _t, _tid = _occluders_on(field, o, t, 2.0, 2.0)
            assert (blocker is None) == _wall_verdict(field, o, t), (o, t)


def test_an_off_axis_glance_through_the_door_reaches_the_far_diagonal():
    """One pace in from the door and one to the side, looking at a thing
    beyond the door on the OTHER side: the line crosses the wall inside the
    gap, so it gets through. The cell-thick wall refused this."""
    sc = _pair()
    field = observer_field(sc, "P")
    (door,), _b = _door_cells(sc, "hall", "yard")
    wall_x = door[0] + 1
    o = (door[0] - 1, door[1] + 1)
    t = (wall_x + 1, door[1] - 1)
    assert _wall_verdict(field, o, t)
    assert _occluders_on(field, o, t, 2.0, 2.0)[0] is None


def test_beside_the_doorframe_you_cannot_see_your_own_side_of_the_next_room():
    """Standing against the wall right beside the door, a thing in the next
    room on YOUR side of the doorway is behind the wall: the line runs almost
    parallel to it and crosses outside the gap. The two-leg routing said
    yes here (you see the door, the door sees the thing), which is seeing
    round a corner."""
    sc = _pair()
    field = observer_field(sc, "P")
    (door,), _b = _door_cells(sc, "hall", "yard")
    o = (door[0], door[1] + 1)                        # beside the doorframe
    t = (door[0] + 5, door[1] + 2)                    # beyond, on my side
    assert not _wall_verdict(field, o, t)
    assert _occluders_on(field, o, t, 2.0, 2.0)[0] == "__wall__"


def test_rooms_of_different_sizes_share_one_wall_over_both_their_reaches():
    sc = _pair(a_size="large", b_size="small")
    field = observer_field(sc, "P")
    (wall,) = field.walls
    lo, hi = wall["extent"]
    ys = [c[1] for c in field.inside]
    assert lo == min(ys) - 0.5 and hi == max(ys) + 0.5
    hall, yard = _cells_of(field, "hall"), _cells_of(field, "yard")
    for o in hall:
        for t in yard:
            assert _wall_verdict(field, o, t) == _wall_verdict(field, t, o)


def test_a_corner_doorway_is_a_gap_in_both_walls_that_meet_there():
    sc = _pair(bearing="ne")
    field = observer_field(sc, "P")
    assert "yard" in field.offsets
    assert sorted(w["axis"] for w in field.walls) == [0, 1]
    hall, yard = _cells_of(field, "hall"), _cells_of(field, "yard")
    admitted = [(o, t) for o in hall for t in yard if _wall_verdict(field, o, t)]
    assert admitted
    for o, t in admitted:
        assert _wall_verdict(field, t, o)
        assert _occluders_on(field, o, t, 2.0, 2.0)[0] is None


# ---------------------------------------------------------------------------
# What the callers get from it
# ---------------------------------------------------------------------------

def test_a_body_beyond_the_doorway_is_graded_by_the_one_straight_line():
    sc = _pair(b_anchors={"well": {"desc": "the well", "dir": "e",
                                   "height": "waist"}})
    sc["stations"] = {"P": {"at": "door:yard"}, "Q": {"at": "well"}}
    field = observer_field(sc, "P")
    o = field.cell_of("hall", body_cell(sc, "P"))
    t = field.cell_of("yard", body_cell(sc, "Q"))
    rec = body_visibility(sc, "P", "Q")
    assert rec["basis"] == "line" and rec["through"] == "yard"
    assert rec["visible"] == (_occluders_on(field, o, t, 2.0, 2.0)[0] is None)
    assert rec["visible"] == _wall_verdict(field, o, t)


def test_a_wall_struck_beside_the_door_is_named_as_the_wall():
    """`occluded_by` for a line into the wall is None: no furniture did it,
    and the view says nothing rather than inventing a thing in the way."""
    sc = _pair(b_anchors={"well": {"desc": "the well", "dir": "e",
                                   "height": "waist"}})
    field = observer_field(sc, "P")
    (door,), _b = _door_cells(sc, "hall", "yard")
    # Find a hall cell whose line to the well misses the gap, if one exists.
    ox, oy = field.offsets["yard"]
    well = [(x + ox, y + oy) for x, y in field.anchors["yard"]["well"]["cells"]][0]
    miss = [o for o in _cells_of(field, "hall") if not _wall_verdict(field, o, well)]
    assert miss
    blocker, _t, _tid = _occluders_on(field, miss[0], well, 2.0, 1.0)
    assert blocker == "__wall__"


def test_furniture_beyond_the_door_comes_and_goes_with_the_line():
    """`neighbour_feature_visibility` uses the same single line: a far
    anchor is in the rows exactly when the line to it threads the gap and
    meets nothing tall on the way."""
    sc = _pair(b_anchors={"well": {"desc": "the well", "dir": "e",
                                   "height": "waist"}})
    sc["stations"] = {"P": {"at": "door:yard"}}
    field = observer_field(sc, "P")
    o = field.cell_of("hall", body_cell(sc, "P"))
    ox, oy = field.offsets["yard"]
    cells = [(x + ox, y + oy) for x, y in field.anchors["yard"]["well"]["cells"]]
    t = min(cells, key=lambda c: (c[0] - o[0]) ** 2 + (c[1] - o[1]) ** 2)
    expected = _occluders_on(field, o, t, 2.0, 1.0)[0] is None
    rows = neighbour_feature_visibility(sc, "P", "yard", sweep=True)
    assert ("well" in {r["anchor"] for r in rows}) == expected
