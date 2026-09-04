"""An exact match is not ambiguous, and the substring tier made it look like one.

`planned_context` matches loosely on purpose: the Director writes a
destination as a DESCRIPTION rather than an id ("Reeve's Hall interior and
occupants"; 21 of 21 on the Harrowmere replay named a room that way and none
was an id), so a room answers when its own spelling sits INSIDE the query.
But a room id also sits inside another room id, and the function refuses
whenever more than one row matches.

Measured on the live chat 114 register: a room called `parking` is a
substring of `guest_parking_lot`, so a query for the parking lot matched both
and resolved to None. About 30 rooms of that story's Maedomari district
answered nothing at all -- and this is the brief the Director is handed when
a beat walks into a planned room, so those rooms would be furnished with no
purpose, no access and no plan exits.

The tiers are now ranked rather than pooled: a query that names a room
exactly is answered by that room however many others it also brushes, and the
loose tier decides only when nothing matched exactly. A real ambiguity is
still refused in both tiers -- two descriptions matching one query really is
two candidates, and one room's uid equalling another's name is a collision
that cannot be broken by guessing.
"""
import json
import time

import pytest

from world.structure import planned_context


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Harbour", "A harbour.", time.time()))


def _plant(db, cid, uid, name, purpose="A place.", adjacent=()):
    db.qi(
        "INSERT INTO room_registry"
        "(chat_id,room_uid,owning_book_id,parent_entity,name,aliases,payload) "
        "VALUES(?,?,?,?,?,?,?)",
        (cid, uid, None, None, name, json.dumps([name, uid]),
         json.dumps({"planned": {
             "name": name, "purpose": purpose, "structure": "town",
             "access": "",
             "adjacent": [{"to": t} for t in adjacent]}})))


class TestOneIdInsideAnother:
    def test_the_longer_id_resolves_to_itself(self, temp_db):
        """The live shape: `parking` is a substring of `guest_parking_lot`."""
        cid = _chat(temp_db)
        _plant(temp_db, cid, "parking", "Parking Area")
        _plant(temp_db, cid, "guest_parking_lot", "Guest Parking Lot")
        got = planned_context(cid, "guest_parking_lot")
        assert got is not None, "an exact id must not be refused as ambiguous"
        assert got["room_uid"] == "guest_parking_lot"

    def test_the_shorter_id_still_resolves_to_itself(self, temp_db):
        cid = _chat(temp_db)
        _plant(temp_db, cid, "parking", "Parking Area")
        _plant(temp_db, cid, "guest_parking_lot", "Guest Parking Lot")
        got = planned_context(cid, "parking")
        assert got is not None and got["room_uid"] == "parking"

    def test_an_exact_display_name_resolves_too(self, temp_db):
        cid = _chat(temp_db)
        _plant(temp_db, cid, "parking", "Parking Area")
        _plant(temp_db, cid, "guest_parking_lot", "Guest Parking Lot")
        got = planned_context(cid, "Guest Parking Lot")
        assert got is not None and got["room_uid"] == "guest_parking_lot"

    def test_the_brief_survives_intact(self, temp_db):
        """What the refusal was actually costing: the purpose and exits the
        Director furnishes the room from."""
        cid = _chat(temp_db)
        _plant(temp_db, cid, "parking", "Parking Area")
        _plant(temp_db, cid, "guest_parking_lot", "Guest Parking Lot",
               purpose="Paved lot for guests.", adjacent=("parking",))
        got = planned_context(cid, "guest_parking_lot")
        assert got["purpose"] == "Paved lot for guests."
        assert got["adjacent"] == ["Parking Area"]


class TestTheLooseTierIsUntouched:
    def test_a_description_still_finds_its_room(self, temp_db):
        """The reason the match is loose at all: the Director names a room by
        describing it."""
        cid = _chat(temp_db)
        _plant(temp_db, cid, "reeves_hall", "Reeve's Hall")
        got = planned_context(cid, "reeves_hall interior and occupants")
        assert got is not None and got["room_uid"] == "reeves_hall"

    def test_a_query_matching_nothing_still_answers_none(self, temp_db):
        cid = _chat(temp_db)
        _plant(temp_db, cid, "reeves_hall", "Reeve's Hall")
        assert planned_context(cid, "nowhere in particular") is None

    def test_two_loose_matches_are_still_refused(self, temp_db):
        """A real ambiguity: neither room is named exactly and both sit inside
        the query. Guessing here would furnish the wrong room."""
        cid = _chat(temp_db)
        _plant(temp_db, cid, "north_dock", "North Dock")
        _plant(temp_db, cid, "south_dock", "South Dock")
        assert planned_context(cid, "north_dock and south_dock") is None

    def test_a_genuine_exact_collision_is_still_refused(self, temp_db):
        """One room's uid equalling another's display name is a collision the
        exact tier cannot break either."""
        cid = _chat(temp_db)
        _plant(temp_db, cid, "the_vault", "Strongroom")
        _plant(temp_db, cid, "strongroom", "The Vault")
        assert planned_context(cid, "strongroom") is None
