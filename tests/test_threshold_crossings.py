"""Going through a doorway takes longer than a position field does.

A body's room is a single value that changes between one beat and the next.
Where the boundary is see-through that costs nothing -- the room behind keeps
watching through the opening either way. Where it is OPAQUE, the body blinked
out of the world: the beat it stepped through, every observer behind it lost
it completely, mid-step, with nothing narrated as having happened.

`crossings` is the fix: a body that has just crossed an opaque boundary stays
visible AS A SHAPE to the room it left, for a couple of beats, and then is
gone. Seen going in; not seen once in.
"""

import pytest

from spatial import (
    THRESHOLD_CROSSING_BEATS,
    crossing_of,
    crossing_visible_from,
    has_visual,
    sight_level,
    spatial_rel,
    spatial_rel_between,
    visual_level_between,
)
from spatial_frames import infer_threshold_crossings


def _scene(positions, barrier="membrane", light=None):
    inner = {"name": "Inner", "desc": "A cramped space.",
             "adjacent": [{"to": "camp", "barrier": barrier,
                           "distance": "near"}]}
    if light is not None:
        inner["light"] = light
    return {
        "rooms": {
            "inner": inner,
            "camp": {"name": "Camp", "desc": "A clearing.", "adjacent": []},
            "far_field": {"name": "Far Field", "desc": "Away.",
                          "adjacent": []},
        },
        "positions": dict(positions),
    }


def _step(prev_positions, new_positions, **kw):
    """Run one beat's inference and hand back the resulting scene."""
    prev = _scene(prev_positions, **kw)
    new = _scene(new_positions, **kw)
    new["crossings"] = dict(prev.get("crossings") or {})
    infer_threshold_crossings(None, None, prev, new, ["Ada", "Bo"])
    return new


def _advance(scene, **kw):
    """A further beat in which nobody moves."""
    nxt = _scene(scene["positions"], **kw)
    nxt["crossings"] = dict(scene.get("crossings") or {})
    infer_threshold_crossings(None, None, scene, nxt, ["Ada", "Bo"])
    return nxt


# --- the crossing is recorded, and only for opaque boundaries --------------

def test_stepping_through_an_opaque_boundary_records_a_crossing():
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"})
    rec = crossing_of(sc, "Ada")
    assert rec == {"from": "camp", "to": "inner",
                   "beats": THRESHOLD_CROSSING_BEATS}


def test_stepping_through_a_see_through_boundary_records_nothing():
    """An open doorway needs no special case: the room behind can see through
    it already, before and after the step."""
    sc = _step({"Ada": "camp"}, {"Ada": "inner"}, barrier="open_door")
    assert crossing_of(sc, "Ada") is None


def test_a_non_adjacent_jump_is_not_a_crossing():
    """Nobody watched them go through anything."""
    sc = _step({"Ada": "far_field"}, {"Ada": "inner"})
    assert crossing_of(sc, "Ada") is None


def test_standing_still_records_nothing():
    sc = _step({"Ada": "camp"}, {"Ada": "camp"})
    assert crossing_of(sc, "Ada") is None


# --- what it does to sight -------------------------------------------------

def test_the_room_left_behind_still_sees_them_going_in():
    """The whole point: opaque, and yet not instantly gone."""
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"})

    plain = spatial_rel(sc, "camp", "inner")
    assert has_visual(plain) is False          # the boundary itself is opaque

    rel = spatial_rel_between(sc, "Bo", "Ada")
    assert rel["crossing"] is True
    assert sight_level(rel) == "shapes"
    assert has_visual(rel) is True
    assert visual_level_between(sc, "Bo", "Ada") == "shapes"


def test_they_are_gone_once_the_crossing_lapses():
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"})
    for _ in range(THRESHOLD_CROSSING_BEATS):
        sc = _advance(sc)

    assert crossing_of(sc, "Ada") is None
    assert sight_level(spatial_rel_between(sc, "Bo", "Ada")) == "none"
    assert visual_level_between(sc, "Bo", "Ada") == "none"


def test_the_crossing_counts_down_rather_than_ending_at_once():
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"})
    assert crossing_of(sc, "Ada")["beats"] == 2

    sc = _advance(sc)
    assert crossing_of(sc, "Ada")["beats"] == 1
    assert sight_level(spatial_rel_between(sc, "Bo", "Ada")) == "shapes"

    sc = _advance(sc)
    assert crossing_of(sc, "Ada") is None


def test_only_the_room_they_left_sees_the_crossing():
    """Someone standing somewhere else entirely gains nothing from it."""
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"})
    sc["positions"]["Cass"] = "far_field"

    assert crossing_visible_from(sc, "camp", "Ada") is True
    assert crossing_visible_from(sc, "far_field", "Ada") is False
    assert sight_level(spatial_rel_between(sc, "Cass", "Ada")) == "none"


def test_a_crossing_is_only_ever_a_floor_never_a_bonus():
    """It refuses to let a body vanish mid-step. It does not hand out detail
    the light never offered -- `shapes` is the ceiling it lifts to, not
    `full`."""
    rel = {"same_room": False, "barrier": "membrane", "distance": "near",
           "light": "lit", "crossing": True}
    assert sight_level(rel) == "shapes"

    # ...and where sight was already better, the crossing changes nothing.
    open_rel = {"same_room": False, "barrier": "open_door", "distance": "near",
                "light": "lit", "crossing": True}
    assert sight_level(open_rel) == "full"


def test_a_crossing_into_the_dark_is_still_a_shape():
    """Unlit on the far side: they are a shape in the doorway on the way
    through, and nothing at all afterwards."""
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"},
               light="dark")
    assert visual_level_between(sc, "Bo", "Ada") == "shapes"

    for _ in range(THRESHOLD_CROSSING_BEATS):
        sc = _advance(sc, light="dark")
    assert visual_level_between(sc, "Bo", "Ada") == "none"


# --- the record cannot outlive what it describes ---------------------------

def test_moving_on_clears_a_crossing_that_no_longer_describes_anything():
    """The record says "part-way from camp into inner". Once they are not in
    `inner` any more it describes nothing, and must not linger and keep them
    visible to a room they are no longer stepping out of. (Stepping back the
    way they came is a NEW crossing -- see the round-trip test below.)"""
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"})
    assert crossing_of(sc, "Ada")

    moved = _scene({"Ada": "far_field", "Bo": "camp"})
    moved["crossings"] = dict(sc["crossings"])
    infer_threshold_crossings(None, None, sc, moved, ["Ada", "Bo"])
    assert crossing_of(moved, "Ada") is None


def test_leaving_the_scene_prunes_the_crossing():
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"})

    gone = _scene({"Bo": "camp"})
    gone["crossings"] = dict(sc["crossings"])
    infer_threshold_crossings(None, None, sc, gone, ["Ada", "Bo"])
    assert crossing_of(gone, "Ada") is None


def test_crossing_back_out_is_watched_too():
    """Symmetric: emerging is as visible as going in, from the side left."""
    sc = _step({"Ada": "camp", "Bo": "camp"}, {"Ada": "inner", "Bo": "camp"})
    out = _scene({"Ada": "camp", "Bo": "camp"})
    out["crossings"] = dict(sc["crossings"])
    infer_threshold_crossings(None, None, sc, out, ["Ada", "Bo"])

    assert crossing_of(out, "Ada") == {"from": "inner", "to": "camp",
                                       "beats": THRESHOLD_CROSSING_BEATS}


def test_a_malformed_record_is_treated_as_no_crossing():
    sc = _scene({"Ada": "inner", "Bo": "camp"})
    for junk in ({"from": "camp", "to": "inner", "beats": "many"},
                 {"from": "camp", "to": "inner", "beats": 0},
                 "not a record"):
        sc["crossings"] = {"Ada": junk}
        assert crossing_of(sc, "Ada") is None


@pytest.mark.parametrize("key", ["crossings"])
def test_absent_state_is_simply_no_crossing(key):
    sc = _scene({"Ada": "inner", "Bo": "camp"})
    sc.pop(key, None)
    assert crossing_of(sc, "Ada") is None
    assert sight_level(spatial_rel_between(sc, "Bo", "Ada")) == "none"
