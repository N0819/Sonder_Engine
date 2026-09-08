"""ONE ANSWER TO "WHICH ROOMS DOES THIS OPERATION NAME" (REVIEW_2026-09-07
B20).

Two sites asked it and answered differently, each over its own hand-written
key list: `plot_packages._rooms_named_by` read `room|where|to|place` for the
reach warning, `room_slice._op_rooms` read `room|where|place` for the Room's
per-room slice -- so an errand named a room to one and no room to the other.
And NEITHER read `plan_creature.lair`/`hunts`, so a package whose rooms were
a creature's lair and the range it hunts named no room at all: the reach
check could not warn that the thing was planted where the story cannot go,
and the room it lairs in listed no operation.

The rule now: `plot_packages.ROOM_FIELDS` declares the room-valued fields of
each operation kind, beside `OPERATION_FIELDS` which documents them, and
`plot_packages.operation_rooms` is the only reader. A field documented as
holding a room id and not declared is a drift the last test here catches.
"""
from __future__ import annotations

import re
import time

from story.plot_packages import (
    OPERATION_FIELDS, ROOM_FIELDS, _reach_warning, _world_snapshot,
    draft_operation, new_package, operation_rooms)
from story.room_slice import room_slice

#: No persona on the chat, so the player carries the default name.
PLAYER = "The Stranger"


def _scene():
    """A chain: the player stands in the lobby, the den is three hops out --
    one past `room_frontier.FRONTIER_DEPTH_HOPS`."""
    return {"location": "Warren", "rooms": {
        "lobby": {"name": "Lobby", "desc": "Dust.",
                  "adjacent": [{"to": "corridor", "barrier": "open_door"}]},
        "corridor": {"name": "Corridor", "desc": "Concrete.",
                     "adjacent": [{"to": "lobby", "barrier": "open_door"},
                                  {"to": "hall", "barrier": "open_door"}]},
        "hall": {"name": "Hall", "desc": "Long.",
                 "adjacent": [{"to": "corridor", "barrier": "open_door"},
                              {"to": "den", "barrier": "open_door"}]},
        "den": {"name": "Den", "desc": "Bones.",
                "adjacent": [{"to": "hall", "barrier": "open_door"}]},
    }, "entities": {}, "positions": {PLAYER: "lobby"}}


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Warren", "Underground.", time.time()))
    db.wset(cid, "scene", _scene())
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "", time.time()))
    return cid


def _creature_package(cid, **fields):
    pkg = new_package(cid, title="The Thing")
    return draft_operation(cid, pkg["uid"],
                           {"op": "plan_creature", "name": "the thing", **fields})


class TestOperationRooms:
    def test_a_creatures_lair_and_range_are_rooms_it_names(self):
        op = {"op": "plan_creature", "name": "the thing", "lair": "den",
              "hunts": ["hall", "corridor"]}
        assert operation_rooms(op) == {"den", "hall", "corridor"}

    def test_every_declared_shape_is_read(self):
        assert operation_rooms({"op": "errand", "charter": "keep",
                                "body": "runner", "to": "hall"}) == {"hall"}
        assert operation_rooms({"op": "plan_rooms",
                                "rooms": {"cellar": {}, "stair": {}}}) \
            == {"cellar", "stair"}
        assert operation_rooms({"op": "plan_entity", "name": "a lamp",
                                "brief": {"where": "hall"}}) == {"hall"}
        assert operation_rooms({"op": "region_event", "label": "flood",
                                "footprint": {"rooms": ["hall", "den"],
                                              "epicentre": "corridor"}}) \
            == {"hall", "den", "corridor"}
        assert operation_rooms({"op": "director_note", "text": "x",
                                "rooms": ["hall"]}) == {"hall"}
        # A kind with no room-valued field names no room, and a missing or
        # empty field is not a room called "".
        assert operation_rooms({"op": "presimulate", "hours": 2}) == set()
        assert operation_rooms({"op": "post_artifact", "room": ""}) == set()
        assert operation_rooms({"op": "post_artifact"}) == set()


class TestBothReadersAgree:
    def test_the_reach_warning_sees_where_a_creature_is_planted(self, temp_db):
        """The den is 3 hops from the occupied lobby and the frontier reaches
        2, so a creature lairing there is out of the story's reach. Before
        B20 the check read no room off a `plan_creature` at all and stayed
        silent whatever the package planted."""
        cid = _story(temp_db)
        pkg = _creature_package(cid, lair="den")
        world = _world_snapshot(cid)
        warning = _reach_warning(cid, world, pkg)
        assert warning and "'den'" in warning

        # The range it hunts is reach too: a lair out past the frontier that
        # ranges into a room beside the cast is reachable.
        near = _creature_package(cid, lair="den", hunts=["corridor"])
        assert _reach_warning(cid, _world_snapshot(cid), near) is None

    def test_the_room_slice_lists_the_operation_under_every_room_it_names(
            self, temp_db):
        cid = _story(temp_db)
        pkg = _creature_package(cid, lair="den", hunts=["hall"])
        for rid in ("den", "hall"):
            ops = room_slice(cid, None, rid)["plan_here"]["package_ops"]
            assert [(o["package"], o["op"]) for o in ops] \
                == [(pkg["uid"], "plan_creature")]
        assert room_slice(cid, None, "lobby")["plan_here"]["package_ops"] == []

    def test_an_errand_names_its_destination_to_the_slice_too(self, temp_db):
        """`_op_rooms` read `room|where|place` and not `to`, so the reach
        check and the slice disagreed about an errand."""
        cid = _story(temp_db)
        pkg = new_package(cid, title="Send him")
        draft_operation(cid, pkg["uid"], {"op": "errand", "charter": "keep",
                                          "body": "runner", "to": "hall"})
        ops = room_slice(cid, None, "hall")["plan_here"]["package_ops"]
        assert [o["op"] for o in ops] == ["errand"]


class TestTheDeclarationMatchesTheDocumentation:
    """`ROOM_FIELDS` and `OPERATION_FIELDS` are two records of one fact, so
    they are checked against each other: this is what would have caught
    `plan_creature.lair` when the kind was added."""

    #: A field whose documentation says "room id" and whose value is NOT a
    #: room id alone -- read as one, it would name rooms that do not exist.
    EXEMPT = {("file_lore", "subject_id"):
              "a room id OR a plan uid OR a charter key OR a slug"}

    ROOM_ID_TEXT = re.compile(r"room[_ ]ids?\b", re.I)

    def test_every_field_documented_as_a_room_id_is_declared(self):
        missing = []
        for kind, fields in OPERATION_FIELDS.items():
            declared = {p.split(".")[0] for p in ROOM_FIELDS.get(kind, ())}
            for field, description in fields.items():
                name = field.rstrip("?")
                if (kind, name) in self.EXEMPT or name in declared:
                    continue
                if self.ROOM_ID_TEXT.search(str(description or "")):
                    missing.append("%s.%s" % (kind, name))
        assert missing == []

    def test_every_declared_path_is_a_field_of_that_kind(self):
        for kind, paths in ROOM_FIELDS.items():
            fields = OPERATION_FIELDS[kind]
            documented = {name.rstrip("?") for name in fields}
            for path in paths:
                assert path.split(".")[0] in documented, \
                    "%s declares %r, which is no field of it" % (kind, path)
