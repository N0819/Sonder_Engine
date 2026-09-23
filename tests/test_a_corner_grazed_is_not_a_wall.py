"""A line that only touches one fixture's corner is not blocked by it.

`_line` is an exact supercover: where the segment passes exactly through the
corner of four cells it takes both side cells, so two occluders that meet at
a corner leave no gap. `_occluders_on` then stopped the line at EITHER of
them, which makes one fixture's corner a wall. Measured on the playerless
Aldermill round 9 (2026-09-23), idx 12-14: Emory stationed beside the
head-high crown-wheel housing in the grind floor, Sal four paces off, the
line between them touching the housing's corner and nothing else. The
shadowcast had each in the other's view; the straight walk refused it, and
for three beats each was "the unfamiliar person" to the other.
"""

from __future__ import annotations

from world import spatial as fov

HOUSING = {"desc": "Heavy oak framing enclosing the crown wheel overhead.",
           "dir": "n", "footprint": "large", "height": "head",
           "opacity": "opaque", "offset": 0.5}


def _grind_floor(**extra_anchors):
    return {
        "rooms": {"grind_floor": {
            "name": "Grind Floor", "extent": {"w": 6, "d": 6},
            "shape": "rectangle", "adjacent": [],
            "anchors": {"crown_wheel_housing": dict(HOUSING), **extra_anchors}}},
        "positions": {"Emory": "grind_floor", "Sal": "grind_floor"},
        "stations": {"Emory": {"at": "crown_wheel_housing", "cell": [4, 0]},
                     "Sal": {"cell": [3, 3]}},
        "entities": {}, "contacts": [],
    }


def test_the_line_touches_the_housing_only_at_its_corner():
    sc = _grind_floor()
    cells = fov.anchor_cells(sc, "grind_floor")["crown_wheel_housing"]["cells"]
    assert cells == [(2, 0), (2, 1), (3, 0), (3, 1)]
    assert ((3, 1), (4, 2)) in fov._line_steps((4, 0), (3, 3))


def test_two_bodies_beside_one_fixture_see_each_other():
    sc = _grind_floor()
    assert fov.body_visibility(sc, "Sal", "Emory")["visible"] is True
    assert fov.body_visibility(sc, "Emory", "Sal")["visible"] is True


def test_two_fixtures_meeting_at_that_corner_still_close_it():
    post = {"desc": "A head-high oak post.", "cell": [4, 2],
            "footprint": "point", "height": "head", "opacity": "opaque"}
    sc = _grind_floor(post=post)
    view = fov.body_visibility(sc, "Sal", "Emory")
    assert view["visible"] is False


def test_the_flat_line_is_the_steps_flattened():
    for a, b in (((0, 0), (4, 1)), ((0, 0), (2, 2)), ((4, 0), (3, 3)), ((5, 5), (0, 1))):
        assert fov._line(a, b) == [c for step in fov._line_steps(a, b) for c in step]
