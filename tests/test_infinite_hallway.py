"""Walking forward must not walk you backward.

Found live auditing chat "Elevator Adventure branch 41", turns 73-89. The
player leaned on Dr. Moon and pressed west down a condemned passage every
single beat. The committed room per turn:

    west_chamber, west_descent, west_chamber, west_descent, west_chamber,
    west_descent, lower_descent, lower_descent, west_chamber(!), ...
    ... deep_passage, lower_descent, deep_passage, functional_chamber,
    lower_descent, west_chamber(!)

Twenty turns of oscillation, ending with "You keep inching forwards with
her" committing a jump four rooms BACKWARD into a chamber they had left
fifteen turns earlier. The player noticed before the engine did, in
character: "Does this corridor go on forever?", "How long is this
hallway............".

Two gaps are covered here:
  * the room graph is undirected and director_interpret was never shown
    the mover's heading, so "keep going" and "turn back" named the same
    two doorways  -> _egocentric_exits
  * one room offered two different neighbors on the same bearing, so
    "ahead" was ambiguous even when a bearing existed
    -> normalize_scene_bearings

Deliberately NOT fixed by blocking: the deterministic backstop validates
reachability only, and in an all-open corridor every room is reachable --
but requiring the resolve diff to corroborate a multi-room walk breaks the
contract test_director_movement_routes.py pins (a legitimate three-hop walk
through open doorways must commit, or the narrator describes arriving while
the position never moves). Direction is therefore enforced by giving the
Director the heading, not by rejecting reachable destinations.
"""

from __future__ import annotations

import copy

from agents.director import _egocentric_exits
from world.spatial import normalize_scene_bearings


def _corridor():
    """The live west-leg topology: a chain of open doorways."""
    return {
        "rooms": {
            "west_chamber": {"adjacent": [
                {"to": "west_passage", "barrier": "open", "dir": "e"},
                {"to": "west_descent", "barrier": "open", "dir": "w"}]},
            "west_passage": {"adjacent": [
                {"to": "west_chamber", "barrier": "open", "dir": "w"}]},
            "west_descent": {"adjacent": [
                {"to": "west_chamber", "barrier": "open", "dir": "e"},
                {"to": "lower_descent", "barrier": "open", "dir": "w"}]},
            "lower_descent": {"adjacent": [
                {"to": "west_descent", "barrier": "open", "dir": "e"}]},
        },
        "positions": {"Hinami": "west_descent"},
        "orientation": {"Hinami": {"came_from": "west_chamber", "facing": "w"}},
    }


def test_the_director_is_told_which_way_is_forward():
    exits = _egocentric_exits(_corridor(), "Hinami")
    # The room deeper into the passage is ahead...
    assert exits["ahead"] == ["lower_descent"]
    # ...and the one they just left is behind, by name.
    assert exits["behind"] == ["west_chamber"]
    assert exits["came_from"] == "west_chamber"


def test_an_unoriented_mover_asserts_no_direction():
    """Scene open or fresh teleport: no heading, so no forward/back claim."""
    scene = _corridor()
    scene["orientation"] = {}
    exits = _egocentric_exits(scene, "Hinami")
    assert "ahead" not in exits and "behind" not in exits
    assert exits.get("unclassified")


def test_two_neighbors_on_one_bearing_lose_the_bearing():
    """west_deep_passage claimed both lower_descent and functional_chamber
    due west, so egocentric_frame offered two different rooms as 'ahead'."""
    scene = {"rooms": {
        "deep_passage": {"adjacent": [
            {"to": "descent", "dir": "e"},
            {"to": "lower_descent", "dir": "w"},
            {"to": "functional_chamber", "dir": "w"}]},
        "descent": {"adjacent": [{"to": "deep_passage", "dir": "w"}]},
        "lower_descent": {"adjacent": [{"to": "deep_passage", "dir": "e"}]},
        "functional_chamber": {"adjacent": [{"to": "deep_passage", "dir": "e"}]},
    }}
    out = normalize_scene_bearings(copy.deepcopy(scene))
    edges = {e["to"]: e for e in out["rooms"]["deep_passage"]["adjacent"]}
    # The colliding pair keeps its doorways but loses the false bearing...
    assert "dir" not in edges["lower_descent"]
    assert "dir" not in edges["functional_chamber"]
    # ...and so do their reciprocals, so the next pass cannot re-derive it.
    assert "dir" not in out["rooms"]["lower_descent"]["adjacent"][0]
    assert "dir" not in out["rooms"]["functional_chamber"]["adjacent"][0]
    # An uncontested bearing is untouched.
    assert edges["descent"]["dir"] == "e"
    # Stable: running it again changes nothing.
    assert normalize_scene_bearings(copy.deepcopy(out)) == out
