"""The way between two rooms is a thing, and it had nowhere to say what.

A room carries `{name, desc}`. The edge between two rooms carried
`{to, barrier, distance, dir, vertical}` -- five values, every one about
topology or passability, not one about what the passage IS.

Measured over every scene blob in the live database: 465 edges, and **not one
carries a `name`, a `to_name` or a `desc`.** Three carry `notes` (0.6%). The
cause is in the prompt, which states the edge contract in exactly those five
keys in both places it defines it -- so the model authors five keys, because
five is what it was asked for.

Live, chat 63: the shrine's two floors are joined by a staircase the lorebook
describes in detail ("a narrow wooden staircase rises from the back of the
first floor"). Every observer got a door. The room above could be rendered
because a room has a name and a desc; the stair between could not, because it
was the tuple `(open_door, near, n, up)`.

`_observer_scene_payload` has ALWAYS carried edge names through to the model,
and its F6 projection has always stripped `to_name`/`name`/`notes`/`desc` from
rooms an observer cannot see -- a reader written against a field nothing ever
wrote. The inverse of the engine's usual defect: consumed, never declared.
"""

from __future__ import annotations

import copy

from dressing.backdrops import room_projection
from llm.prompts import DEFAULT_PROMPTS

STAIR = {"to": "shrine_interior_upstairs", "barrier": "open_door",
         "distance": "near", "dir": "n", "vertical": "up",
         "name": "a narrow wooden staircase"}


def test_both_statements_of_the_edge_contract_ask_for_a_name():
    """Two prompts define the shape of an adjacency edge, and a field named in
    one and omitted from the other is a field authored half the time.
    """
    asked = [key for key, body in DEFAULT_PROMPTS.items()
             if isinstance(body, str) and "adjacent:[{to" in body]
    assert len(asked) >= 2, "the edge contract moved; this test is stale"
    for key in asked:
        body = DEFAULT_PROMPTS[key]
        start = body.index("adjacent:[{to")
        shape = body[start:start + 60]
        assert "name" in shape, (
            "%s states the edge contract without `name`: %r" % (key, shape))


def test_the_occasion_is_named_rather_than_the_field_merely_listed():
    """A bare field in a schema line gets filled when convenient. The standing
    rule is to name the occasion, so the clause carries the cases: a stair, a
    gate, the shoji at the end of a hall.
    """
    body = "".join(v for v in DEFAULT_PROMPTS.values() if isinstance(v, str))
    assert "narrow wooden staircase" in body
    assert "torii gate" in body


def _scene_with(edges):
    return {"rooms": {"hall": {"name": "Main Hall",
                               "desc": "tatami and a low hearth",
                               "adjacent": copy.deepcopy(edges)}}}


def test_a_named_passage_reaches_the_backdrop():
    """The backdrop draws a room from its exits. Given `{barrier, vertical,
    dir}` alone it can put an opening in the north wall and cannot know it is
    a staircase -- so the name rides along as the layout fact it is.
    """
    out = room_projection(_scene_with([STAIR]), "hall")
    exits = out.get("exits") or []
    assert exits and exits[0].get("name") == "a narrow wooden staircase", exits


def test_the_backdrop_still_refuses_the_destination():
    """`name` is layout; `to` is who is through the door. The projection has
    always withheld the destination and must keep withholding it.
    """
    exits = room_projection(_scene_with([STAIR]), "hall").get("exits") or []
    assert "to" not in exits[0]
    assert "shrine_interior_upstairs" not in str(exits)


def test_one_room_can_hold_several_flights_that_stay_distinct():
    """A stairwell: one room whose exits are several flights, each to a
    different level. The engine models this as edges on a single room, so what
    keeps two flights apart is `vertical` plus the name -- the point the user
    raised, and the reason a passage needed to be nameable at all.
    """
    stairwell = _scene_with([
        {"to": "ground_floor", "barrier": "open", "vertical": "down",
         "name": "the flight down to the entrance hall"},
        {"to": "second_floor", "barrier": "open", "vertical": "up",
         "name": "the flight up to the gallery"},
        {"to": "roost", "barrier": "closed_door", "vertical": "up",
         "name": "the narrow ladder to the roost"},
    ])
    exits = room_projection(stairwell, "hall").get("exits") or []
    assert len(exits) == 3
    assert {e["name"] for e in exits} == {
        "the flight down to the entrance hall",
        "the flight up to the gallery",
        "the narrow ladder to the roost"}
    # Two flights going UP out of one room are told apart by their names, not
    # by their level -- `vertical` alone collapses them.
    up = [e for e in exits if e.get("vertical") == "up"]
    assert len(up) == 2 and up[0]["name"] != up[1]["name"]
