"""A walk under way ends where it was going, or when something ends it.

`director_movement._travel_continues` carries a declared walk across a
silent beat and `_travel_in_flight_view` tells the Director it is under way.
Both read "the body is in its destination ROOM" as arrived -- true of a walk
to a room, false of a walk to a place IN the room. Two writers leave such a
leg under way: `walk_within_room` (`from == to == destination`, a `to_cell`,
the warning "silence carries the walk on") and `walk_declared` when the paces
run out after the destination's door but short of its `to_anchor` or
`to_cell`. Audit of 2026-11-01 (`agents_director_prose_movement_rooms` F3),
reproduced: the next beat retired the leg as arrived without a step walked,
the body left mid-square with its `at` and `near` cleared and an on-the-way
pose, and the Director told nothing.

And a leg whose walker is in no room was held "no passable route" every
beat, forever (F11): kept silently, and walked again, undeclared, the beat
the body was placed anywhere.
"""

from __future__ import annotations

import copy

from agents.director_movement import _travel_continues, _travel_in_flight_view


class _Ctx(dict):
    language = "en"

    def __init__(self, chat_id):
        super().__init__()
        self.chat = {"id": chat_id}
        self.cast = []
        self.turn = {"idx": 5}
        self.warnings = []

    def add_warning(self, text):
        self.warnings.append(text)


SQUARE = {
    "rooms": {"square": {"name": "The Square", "extent": {"w": 40, "d": 20},
                         "anchors": {"well": {"desc": "the well", "dir": "e",
                                              "height": "waist", "footprint": "small"}},
                         "adjacent": [{"to": "lane", "barrier": "open"}]},
              "lane": {"name": "The Lane", "adjacent": [{"to": "square", "barrier": "open"}]}},
    "positions": {"Hester": "square"},
    "stations": {"Hester": {"cell": [0, 10]}},
    "entities": {}, "poses": {},
    "approach": {"Hester": {"to_room": "square", "to_cell": [30, 10], "turn": 4}},
}


def _continue(scene, temp_db):
    ctx = _Ctx(temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES('t','',0)"))
    out, sd = {}, {}
    _travel_continues(ctx, out, copy.deepcopy(scene), sd, {}, "Tamsin")
    return out.get("travel") or {}, sd, ctx.warnings


def test_a_walk_across_its_own_room_is_walked_on_not_retired(temp_db):
    record, sd, warnings = _continue(SQUARE, temp_db)
    assert "Hester" not in record.get("arrived", [])
    (leg,) = record["advanced"]
    assert (leg["subject"], leg["from"], leg["to"], leg["destination"]) == (
        "Hester", "square", "square", "square")
    assert leg["to_cell"] == [30, 10] and leg["underway"] is True
    assert sd["stations"]["Hester"]["cell"] == [18, 10]
    assert warnings and "Hester" in warnings[0]


def test_the_last_stretch_arrives_where_it_was_going(temp_db):
    scene = copy.deepcopy(SQUARE)
    scene["stations"]["Hester"]["cell"] = [18, 10]
    record, sd, _w = _continue(scene, temp_db)
    assert record["arrived"] == ["Hester"]
    assert sd["stations"]["Hester"]["cell"] == [30, 10]


def test_a_walk_to_a_fixture_in_its_room_is_walked_to_the_fixture(temp_db):
    scene = copy.deepcopy(SQUARE)
    scene["approach"] = {"Hester": {"to_room": "square", "to_anchor": "well", "turn": 4}}
    record, sd, _w = _continue(scene, temp_db)
    assert record.get("advanced") and record["advanced"][0]["to_anchor"] == "well"
    assert sd["stations"]["Hester"]["cell"] != [0, 10]


def test_a_walk_to_a_room_is_over_in_the_room(temp_db):
    scene = copy.deepcopy(SQUARE)
    scene["approach"] = {"Hester": {"to_room": "square", "turn": 4}}
    record, sd, _w = _continue(scene, temp_db)
    assert record["arrived"] == ["Hester"] and not record.get("advanced")
    assert sd == {}


def test_the_director_is_told_a_walk_across_the_room_is_under_way():
    (entry,) = _travel_in_flight_view(copy.deepcopy(SQUARE), {}, "Tamsin")
    assert entry["subject"] == "Hester" and entry["within_room"] is True
    assert entry["from_room"] == entry["destination"] == "square"


def test_a_walker_in_no_room_ends_the_walk_and_says_why(temp_db):
    """F11: the record never retired. A body the world places nowhere has no
    walk to carry on; ended out loud, it is not walked again -- undeclared --
    the beat it is placed somewhere."""
    scene = copy.deepcopy(SQUARE)
    scene["approach"] = {"Coyle": {"to_room": "lane", "turn": 3}}
    record, sd, _w = _continue(scene, temp_db)
    assert [row["subject"] for row in record["interrupted"]] == ["Coyle"]
    assert not record.get("held")
    assert sd == {}
