"""A room behind you is not a room you are looking into.

Live, chat 67 ("Lagunica adventure ⎇0"), turn 9. Hinami stands on Commercial
Lane facing EAST, having walked in from Fountain Plaza — which lies west, and is
therefore at her back. Her view came back reading "Across the street, a
middle-aged man by the fountain watches the foreign notes catch the light": a
person, performing an action, seeing what she held, in a room she was not
looking at. He reappeared the next turn.

The engine had already worked out the right answer and then handed the model
both answers. `spatial.visible_adjacent_rooms` asks a question about the ROOM —
it takes no observer at all — so every open-barrier neighbour is reported in
view however the perceiver is turned. `_behind_rooms` computes the correction,
and its docstring states the rule ("an observer does not receive NEW VISUAL
detail from a room behind them"). Nothing subtracted one from the other, so
`visible_rooms` and `behind_rooms` both named `fountain_plaza` in the same
perceiver payload.

Sight only. Sound and the other channels ride `_source_channels` and are
untouched — she can still hear the fountain.
"""

from __future__ import annotations

import pytest

from agents.perception import _behind_rooms, _visible_rooms_for
from spatial import visible_adjacent_rooms


def _plaza_and_lane(facing="e", came_from="fountain_plaza"):
    """The live geometry: a plaza, a lane east of it, an open mouth between."""
    orientation = {"Hinami": {"came_from": came_from, "focus": None}}
    if facing:
        orientation["Hinami"]["facing"] = facing
    return {
        "positions": {"Hinami": "commercial_lane", "Onlooker": "fountain_plaza"},
        "orientation": orientation,
        "rooms": {
            "fountain_plaza": {
                "name": "Fountain Plaza",
                "desc": "A bustling open plaza. A stone fountain splashes.",
                "adjacent": [{"to": "commercial_lane", "barrier": "open",
                              "distance": "close", "dir": "e"}],
            },
            "commercial_lane": {
                "name": "Commercial Lane",
                "desc": "A cobbled thoroughfare of stalls and shopfronts.",
                "adjacent": [{"to": "fountain_plaza", "barrier": "open",
                              "distance": "close", "dir": "w"}],
            },
        },
    }


def test_the_room_you_walked_out_of_is_not_in_view():
    """The defect, stated as the two lists that contradicted each other."""
    scene = _plaza_and_lane()

    # Both of these named the same room, in the same payload, before the fix.
    assert [r["room_id"] for r in
            visible_adjacent_rooms(scene, "commercial_lane")] == ["fountain_plaza"]
    assert _behind_rooms(scene, "Hinami") == ["fountain_plaza"]

    assert _visible_rooms_for(scene, "Hinami", "commercial_lane") == []


def test_turning_round_gives_it_back():
    """The gate is FACING, not the fact of having moved. Walk in from the west
    and then turn to look back west, and the plaza is in view again — otherwise
    this would forbid looking behind you rather than modelling it."""
    scene = _plaza_and_lane(facing="w")
    assert [r["room_id"] for r in
            _visible_rooms_for(scene, "Hinami", "commercial_lane")] == ["fountain_plaza"]


def test_an_observer_who_has_not_moved_is_never_gated():
    """`_behind_rooms` is empty without movement history, and the wrapper must
    pass that straight through. Gating a mind that has not moved would silently
    blind every character standing where the story started them."""
    scene = _plaza_and_lane(facing=None, came_from=None)
    assert _behind_rooms(scene, "Hinami") == []
    assert [r["room_id"] for r in
            _visible_rooms_for(scene, "Hinami", "commercial_lane")] == ["fountain_plaza"]


def test_the_gate_is_per_observer_not_per_room():
    """The whole reason the room-level function could not answer this: two minds
    in the same room, turned differently, must get different answers."""
    scene = _plaza_and_lane()
    scene["positions"]["Kadomon"] = "commercial_lane"
    scene["orientation"]["Kadomon"] = {"came_from": None, "focus": None,
                                       "facing": "w"}
    assert _visible_rooms_for(scene, "Hinami", "commercial_lane") == []
    assert [r["room_id"] for r in
            _visible_rooms_for(scene, "Kadomon", "commercial_lane")] == ["fountain_plaza"]


@pytest.mark.parametrize("barrier", ["closed_door", "wall"])
def test_a_sight_barrier_still_decides_first(barrier):
    """The wrapper only ever SUBTRACTS. A neighbour that was never in view for
    barrier reasons must not become visible by way of this path.

    Both edges are closed: `visible_adjacent_rooms` reads reverse adjacency too,
    so a one-sided change leaves the room visible through the edge pointing back
    — which is the behaviour, not a bug, and stating it here keeps the next
    reader of this file from "fixing" it."""
    scene = _plaza_and_lane(facing="w")
    scene["rooms"]["commercial_lane"]["adjacent"][0]["barrier"] = barrier
    scene["rooms"]["fountain_plaza"]["adjacent"][0]["barrier"] = barrier
    assert visible_adjacent_rooms(scene, "commercial_lane") == []
    assert _visible_rooms_for(scene, "Hinami", "commercial_lane") == []
