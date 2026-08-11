"""S2a: the opening view-cone.

Sight through an opening used to be whole-room binary: a body pressed against
the wall beside the doorframe was fully seen by anyone looking through -- the
one leak-shaped over-grant in the FOV model. The cone degrades off-axis
bodies from bearings the scene already carries, on BOTH sides of the opening,
and falls back to exactly today's behaviour wherever data is absent.

The final class of test is the subtract-only invariant: the cone is a filter
over what `visual_level_between` already returned, so for EVERY combination
of bearings, sizes, light and distance the post-cone level may be lower than
the pre-cone level and may never be higher. A bearing-comparison bug must be
able to withhold sight, never grant it.
"""
from __future__ import annotations

import itertools

from spatial import (
    _LIGHT_SIGHT,
    _sight_line,
    crossing_visible_from,
    containment_conceals,
    door_anchor_id,
    light_at,
    room_of,
    spatial_rel,
    visual_level_between,
)

_RANK = {"none": 0, "shapes": 1, "full": 2}


def _scene(size="medium", light=None, distance=None, barrier="open_door",
           edge_dir="n", stations=None, crossings=None):
    edge = {"to": "salon", "barrier": barrier}
    if edge_dir:
        edge["dir"] = edge_dir
    if distance:
        edge["distance"] = distance
    salon = {
        "name": "the Salon",
        "anchors": {
            "far_wall": {"desc": "the tall window", "dir": edge_dir or "n"},
            "side_wall": {"desc": "the dresser", "dir": "e"},
            "door_wall": {"desc": "the coat rack", "dir": "s" if edge_dir == "n" else "n"},
        },
        "adjacent": [],
    }
    if size:
        salon["size"] = size
    if light:
        salon["light"] = light
    return {
        "rooms": {"yard": {"name": "the Yard", "adjacent": [edge]},
                  "salon": salon},
        "positions": {"O": "yard", "T": "salon"},
        "entities": {},
        "stations": dict(stations or {}),
        "crossings": dict(crossings or {}),
    }


# ---- defaults are inert -------------------------------------------------------

def test_no_placement_data_keeps_todays_whole_room_grant():
    sc = _scene(size=None)
    assert visual_level_between(sc, "O", "T") == "full"


def test_small_room_stays_whole_room_even_with_an_off_axis_anchor():
    sc = _scene(size="small", stations={"T": {"at": "side_wall"}})
    assert visual_level_between(sc, "O", "T") == "full"


# ---- the cone -------------------------------------------------------------------

def test_body_on_the_opening_axis_is_seen():
    # Edge yard->salon bears n, so from the salon the doorway is south and
    # the visible strip runs toward its north wall.
    sc = _scene(stations={"T": {"at": "far_wall"}})
    assert visual_level_between(sc, "O", "T") == "full"


def test_body_beside_the_doorframe_is_not_seen():
    sc = _scene(stations={"T": {"at": "door_wall"}})
    assert visual_level_between(sc, "O", "T") == "none"


def test_body_off_axis_at_a_side_wall_is_not_seen():
    sc = _scene(stations={"T": {"at": "side_wall"}})
    assert visual_level_between(sc, "O", "T") == "none"


def test_body_in_the_doorway_itself_is_seen():
    sc = _scene(stations={"T": {"at": door_anchor_id("yard")}})
    assert visual_level_between(sc, "O", "T") == "full"


def test_a_crossing_body_is_watched_through_the_opening():
    sc = _scene(crossings={"T": {"from": "yard", "to": "salon", "beats": 2}})
    assert visual_level_between(sc, "O", "T") == "full"


def test_unknown_placement_in_a_large_room_caps_at_shapes():
    sc = _scene(size="large")
    assert visual_level_between(sc, "O", "T") == "shapes"


def test_the_observers_side_is_gated_symmetrically():
    # The observer stands beside their own doorframe (yard's door to the
    # salon bears n; they are at a north-wall anchor that is not the door).
    sc = _scene(stations={"O": {"at": "hook"}, "T": {"at": "far_wall"}})
    sc["rooms"]["yard"]["anchors"] = {"hook": {"desc": "the gate hook",
                                               "dir": "n"}}
    assert visual_level_between(sc, "O", "T") == "none"


def test_a_far_edge_degrades_cross_room_bodies_to_shapes():
    sc = _scene(distance="50m", stations={"T": {"at": "far_wall"}})
    assert visual_level_between(sc, "O", "T") == "shapes"


def test_the_cone_never_outranks_darkness():
    sc = _scene(light="dark", stations={"T": {"at": "far_wall"}})
    assert visual_level_between(sc, "O", "T") == "none"


def test_same_room_sight_is_untouched():
    sc = _scene(stations={"T": {"at": "side_wall"}})
    sc["positions"]["O"] = "salon"
    assert visual_level_between(sc, "O", "T") == "full"


# ---- the subtract-only invariant -------------------------------------------------

def _pre_cone_level(sc, observer, target):
    """visual_level_between exactly as it stood before S2a: sight line +
    light + crossing floor, no cone, no distance cap."""
    o_room = room_of(sc, observer)
    t_room = room_of(sc, target)
    rel = spatial_rel(sc, o_room, t_room)
    crossing = crossing_visible_from(sc, o_room, target)
    if containment_conceals(sc, observer, target):
        return "shapes" if crossing else "none"
    if not _sight_line(rel):
        return "shapes" if crossing else "none"
    level = _LIGHT_SIGHT.get(light_at(sc, target), "full")
    if crossing and level == "none":
        return "shapes"
    return level


def test_the_cone_only_ever_subtracts():
    """The Occluder discipline: the final pass over a sense calculation may
    only remove. Swept across bearings x station placement x size x light x
    distance x barrier, the post-cone grade never exceeds the pre-cone one."""
    anchor_ids = (None, "far_wall", "side_wall", "door_wall",
                  door_anchor_id("yard"))
    sizes = (None, "small", "medium", "large", "vast")
    lights = (None, "dark", "dim", "lit")
    distances = (None, "close", "50m", "200 m")
    edge_dirs = (None, "n", "e", "sw")
    checked = 0
    for at, size, light, distance, edge_dir, crossing in itertools.product(
            anchor_ids, sizes, lights, distances, edge_dirs, (False, True)):
        stations = {"T": {"at": at}} if at else {}
        crossings = ({"T": {"from": "yard", "to": "salon", "beats": 2}}
                     if crossing else {})
        sc = _scene(size=size, light=light, distance=distance,
                    edge_dir=edge_dir, stations=stations, crossings=crossings)
        before = _pre_cone_level(sc, "O", "T")
        after = visual_level_between(sc, "O", "T")
        assert _RANK[after] <= _RANK[before], (
            at, size, light, distance, edge_dir, crossing, before, after)
        checked += 1
    assert checked == len(anchor_ids) * len(sizes) * len(lights) \
        * len(distances) * len(edge_dirs) * 2


def test_a_wall_grants_nothing_no_matter_the_cone_inputs():
    # The cone is a cap, never a grant: a sightless barrier stays sightless
    # even for a body dead on the opening axis.
    sc = _scene(barrier="wall", stations={"T": {"at": "far_wall"}})
    assert visual_level_between(sc, "O", "T") == "none"
