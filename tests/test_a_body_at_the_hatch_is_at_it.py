"""A body standing AT a doorway is in it, whether or not the doorway has a wall.

Playerless Aldermill round 7 (2026-09-23), idx 10: Emory stood on the hatch to
the wheelhouse (`stations: {at: door:mill_wheelhouse}`, pose `on` it), a
vertical edge with no wall bearing to place it on. The walk could not place the
doorway, charged him half the floor's width from its middle, and ruled that he
"covers 9 paces toward 'mill_wheelhouse' and ends the beat in
'mill_flour_floor'" -- a man already on the top rung, left on the floor below.
"""
from world.spatial import FLIGHT_PACES, room_grid, walk


def _mill(station=None):
    scene = {
        "rooms": {
            "mill_floor": {"name": "Milling Floor", "size": "large",
                           "adjacent": [{"to": "wheelhouse", "barrier": "open",
                                         "vertical": "up"}]},
            "wheelhouse": {"name": "Wheelhouse",
                           "adjacent": [{"to": "mill_floor", "barrier": "open",
                                         "vertical": "down"}]},
        },
        "positions": {"Emory Vane": "mill_floor"},
        "entities": {},
    }
    if station:
        scene["stations"] = {"Emory Vane": station}
    return scene


def _short_of_the_door():
    """Enough to climb the flight from the hatch (`FLIGHT_PACES` and the
    doorway's own pace), and not enough to reach an unplaced doorway from
    the middle of the floor first."""
    assert room_grid(_mill(), "mill_floor").side // 2 > 1
    return FLIGHT_PACES + 1


def test_a_body_standing_at_the_hatch_goes_through_it():
    out = walk(_mill({"at": "door:wheelhouse"}), "Emory Vane", "wheelhouse",
               paces=_short_of_the_door())
    assert out["room"] == "wheelhouse"


def test_a_body_mid_floor_still_has_the_floor_to_cross():
    out = walk(_mill(), "Emory Vane", "wheelhouse", paces=_short_of_the_door())
    assert out["room"] == "mill_floor" and not out["arrived"]


def test_standing_at_another_doorway_is_not_standing_at_this_one():
    out = walk(_mill({"at": "door:yard"}), "Emory Vane", "wheelhouse",
               paces=_short_of_the_door())
    assert out["room"] == "mill_floor"
