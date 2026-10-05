"""A lit room shows its own far corners.

`_visible_set` cast its field with a disc sized to the field's Chebyshev
reach while the cast admits cells by Euclidean distance, so a room's far
diagonal fell outside the disc: two lit, pinned bodies at the corners of a
12x12 room graded `none`, and the same pair read `full` once an unrelated
open doorway laid a wider neighbour (survey for distance detail,
2026-10-04). The field's own walls bound the cast.
"""

from __future__ import annotations

from world.spatial import sight_between, visual_level_between


def _room(side, **extra):
    return {"rooms": {"hall": {"name": "Hall", "desc": ".", "extent": {"w": side, "d": side},
                               "adjacent": [], **extra}},
            "positions": {"Ada": "hall", "Ben": "hall"},
            "stations": {"Ada": {"cell": [0, 0]}, "Ben": {"cell": [side - 1, side - 1]}},
            "entities": {}}


def test_corner_to_corner_in_a_lit_room_is_seen():
    """The LINE and the light give a far corner in full; how much of a body
    that far away is made out is the distance's answer (`spatial_range`),
    and never `none`."""
    for side in (8, 12, 24, 50):
        sc = _room(side)
        for a, b in (("Ada", "Ben"), ("Ben", "Ada")):
            assert sight_between(sc, a, b).base == "full", side
            assert visual_level_between(sc, a, b) != "none", side


def test_the_centre_sees_every_corner():
    sc = _room(24)
    sc["stations"]["Ada"] = {"cell": [12, 12]}
    for corner in ([0, 0], [23, 0], [0, 23], [23, 23]):
        sc["stations"]["Ben"] = {"cell": corner}
        assert visual_level_between(sc, "Ada", "Ben") == "full", corner


def test_an_unrelated_doorway_does_not_change_what_a_room_shows_of_itself():
    alone = _room(12)
    alone["stations"] = {"Ada": {"cell": [6, 6]}, "Ben": {"cell": [0, 0]}}
    with_yard = _room(12)
    with_yard["stations"] = {"Ada": {"cell": [6, 6]}, "Ben": {"cell": [0, 0]}}
    with_yard["rooms"]["hall"]["adjacent"] = [{"to": "yard", "barrier": "open", "dir": "e"}]
    with_yard["rooms"]["yard"] = {"name": "Yard", "desc": ".", "extent": {"w": 30, "d": 12},
                                  "adjacent": [{"to": "hall", "barrier": "open", "dir": "w"}]}
    assert visual_level_between(alone, "Ada", "Ben") == visual_level_between(with_yard, "Ada", "Ben") == "full"
