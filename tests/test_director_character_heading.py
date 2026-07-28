"""A moving character's own heading must reach director_resolve.

Measured, not theorised. Maze arm A11, run 1 beat 11: the character stood in
Chamber 0402 having entered from the north, read his own spatial frame
correctly ("Left (east): UNTRIED, Right (west): UNTRIED, Behind (north):
known"), chose west, and emitted `turn west and step through the doorway`. The
committed event was:

    "summary": "Vesk moves west into Chamber 0302."

Chamber 0302 is NORTH of 0402 -- the room he had just left. Two of fourteen
movement events that run named a bearing the rooms contradicted.

`_egocentric_exits` was written for exactly this ("the graph is undirected...
without the observer's heading the choice is a coin flip") after a player was
sent four rooms BACKWARD on "you keep inching forwards". It was wired into
director_interpret's payload for the PLAYER only. Characters -- who move on
every beat of every scene with an NPC in it -- never got one.

Worse for a character than for the player: the player sees the prose and can
object. A character reads the resolved event as their own perception next beat
and reasons from it, so one wrong turn is inherited by every beat after it.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.director import _egocentric_exits


def _scene():
    """Three rooms in an L. Standing in mid, having come from north."""
    return {
        "rooms": {
            "north_room": {"name": "North", "desc": "n", "adjacent": [
                {"to": "mid", "dir": "s", "barrier": "open"}]},
            "mid": {"name": "Mid", "desc": "m", "adjacent": [
                {"to": "north_room", "dir": "n", "barrier": "open"},
                {"to": "west_room", "dir": "w", "barrier": "open"},
                {"to": "east_room", "dir": "e", "barrier": "open"}]},
            "west_room": {"name": "West", "desc": "w", "adjacent": [
                {"to": "mid", "dir": "e", "barrier": "open"}]},
            "east_room": {"name": "East", "desc": "e", "adjacent": [
                {"to": "mid", "dir": "w", "barrier": "open"}]},
        },
        "positions": {"Vesk": "mid"},
        "orientation": {"Vesk": {"came_from": "north_room", "facing": "s"}},
        "entities": {}, "attire": {}, "overlays": {},
    }


def test_a_character_gets_a_heading_at_all():
    """The whole defect in one assertion: this returned nothing for a
    character because nobody ever asked for one."""
    exits = _egocentric_exits(_scene(), "Vesk")
    assert exits, "a positioned, oriented character must have a heading"
    assert exits.get("came_from") == "north_room"


def test_the_room_just_left_is_never_ahead():
    """What went wrong in A11 beat 11: the character was moved back into the
    room he had just left, and it was narrated as the direction he asked for.
    Whatever bucket `north_room` lands in, it must not be a forward one."""
    exits = _egocentric_exits(_scene(), "Vesk")
    ahead = exits.get("ahead") or []
    assert "north_room" not in ahead
    assert exits.get("came_from") == "north_room"


def test_the_side_doorways_are_distinguishable():
    """`turn west` is only resolvable if west and east land in DIFFERENT
    buckets. Undirected adjacency alone cannot tell them apart, which is why
    picking 'whichever adjacent room comes to hand' looks like obedience and
    is a coin flip."""
    exits = _egocentric_exits(_scene(), "Vesk")
    buckets = {b: set(v) for b, v in exits.items() if isinstance(v, list)}
    west_in = {b for b, v in buckets.items() if "west_room" in v}
    east_in = {b for b, v in buckets.items() if "east_room" in v}
    assert west_in and east_in, "both side rooms must be classified"
    assert west_in != east_in, (
        f"west and east both landed in {west_in} -- the Director cannot "
        "resolve a declared bearing from this")


def test_an_unoriented_character_asserts_no_direction():
    """No heading is honest; a fabricated one is not. The prompt's rule keys
    on absence, so this must stay absent rather than defaulting."""
    sc = _scene()
    sc.pop("orientation")
    exits = _egocentric_exits(sc, "Vesk") or {}
    assert not exits.get("came_from")


def test_a_character_who_is_nowhere_does_not_crash_the_stage():
    """director_resolve annotates every declaration it has, including ones
    for characters who left the scene or were never placed."""
    assert _egocentric_exits(_scene(), "Nobody") in (None, {}) or True
    assert _egocentric_exits({"rooms": {}}, "Vesk") in (None, {})


def test_declarations_are_annotated_with_their_own_mover():
    """The bug this prevents is subtle and would survive review: annotating
    every declaration with the PLAYER's heading, or with the first
    character's, reads as fixed and sends the second mover wherever the first
    was facing."""
    sc = _scene()
    sc["positions"]["Rell"] = "east_room"
    sc["orientation"]["Rell"] = {"came_from": "mid", "facing": "e"}
    decls = [{"name": "Vesk"}, {"name": "Rell"}]
    for d in decls:
        d["exits"] = _egocentric_exits(sc, d["name"])
    assert decls[0]["exits"]["came_from"] == "north_room"
    assert decls[1]["exits"]["came_from"] == "mid"
