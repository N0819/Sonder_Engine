"""Regression tests for audit finding #26: spatial split must fail CLOSED.

Two independent leaks, both grant memory visibility across an active,
unmerged spatial separation:

(a) spatial_frames.detect_merge merged on TWO empty zone sets -- i.e. neither
    party standing in any zoned room -- which fires for two parties in
    newly-created, not-yet-zoned rooms that are light-years apart. Merge is
    one-way and unrecoverable (perform_merge sets merged_turn_idx, restoring
    permanent bidirectional visibility), so it must require positive evidence
    of reunion: a shared zone, or a shared room id.

(b) frames.is_memory_visible returned True for a parent-side memory with a
    NULL turn_idx when viewed from inside an unmerged child split, leaking the
    parent's post-split memories across the split.
"""

from __future__ import annotations

import time

import pytest

import app
import spatial_frames
from db import wget_for_frame, wset, wset_for_frame
from frames import create_frame, is_memory_visible


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_persona(db, name):
    import json
    return db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        (name, json.dumps({"identity": {"name": name}})),
    )


def _make_char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, "{}", "{}", time.time()),
    )


class TestDetectMergeFailsClosedOnEmptyZones:
    def test_does_not_merge_two_empty_zone_sets_in_different_rooms(self, temp_db):
        # Both parties are in unzoned rooms -- but DIFFERENT rooms (e.g. two
        # freshly-created, not-yet-zoned locales light-years apart). The old
        # `not parent_zones and not child_zones` branch merged here, leaking
        # permanent bidirectional memory across the split.
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=5)
        temp_db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
            "VALUES(?,?,'active',?)",
            (chat_id, bob, child),
        )

        # Parent side: primary player "The Stranger" alone in an unzoned room.
        wset(chat_id, "scene", {
            "rooms": {"attic": {"name": "Attic", "adjacent": []}},
            "positions": {"The Stranger": "attic"},
            "entities": {}, "attire": {}, "overlays": {},
        })
        # Child side: Bob alone in a DIFFERENT unzoned room.
        wset_for_frame(chat_id, "scene", {
            "rooms": {"basement": {"name": "Basement", "adjacent": []}},
            "positions": {"Bob": "basement"},
            "entities": {}, "attire": {}, "overlays": {},
        }, child)

        assert spatial_frames.detect_merge(chat_id, None) is None

    def test_still_merges_when_parties_share_the_same_unzoned_room(self, temp_db):
        # The legitimate reunion-in-an-unzoned-room case must still merge:
        # a shared room id is positive proof of co-location.
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=5)
        temp_db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
            "VALUES(?,?,'active',?)",
            (chat_id, bob, child),
        )

        shared_room = {"name": "Lobby", "adjacent": []}
        wset(chat_id, "scene", {
            "rooms": {"lobby": shared_room},
            "positions": {"The Stranger": "lobby"},
            "entities": {}, "attire": {}, "overlays": {},
        })
        wset_for_frame(chat_id, "scene", {
            "rooms": {"lobby": shared_room},
            "positions": {"Bob": "lobby"},
            "entities": {}, "attire": {}, "overlays": {},
        }, child)

        assert spatial_frames.detect_merge(chat_id, None) == (None, child)

    def test_still_merges_on_a_shared_declared_zone(self, temp_db):
        # And the ordinary shared-zone reunion still works.
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=5)
        temp_db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
            "VALUES(?,?,'active',?)",
            (chat_id, bob, child),
        )
        room = {"name": "Docking Bay", "adjacent": [], "zone": "rendezvous"}
        wset(chat_id, "scene", {
            "rooms": {"bay_a": room},
            "positions": {"The Stranger": "bay_a"},
            "entities": {}, "attire": {}, "overlays": {},
        })
        wset_for_frame(chat_id, "scene", {
            "rooms": {"bay_b": room},
            "positions": {"Bob": "bay_b"},
            "entities": {}, "attire": {}, "overlays": {},
        }, child)

        assert spatial_frames.detect_merge(chat_id, None) == (None, child)


class TestNullTurnIdxParentMemoryFailsClosed:
    def test_null_turn_idx_parent_memory_is_invisible_from_child(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=10)

        # A parent-side memory with no recorded turn_idx: with no proof it
        # predates the split, the child must NOT see it. (Was True -> leak.)
        assert is_memory_visible(alice, None, child, memory_turn_idx=None) is False

    def test_dated_pre_and_post_split_visibility_still_holds(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=10)

        # Pre-split shared history stays visible; post-split parent memory hidden.
        assert is_memory_visible(alice, None, child, memory_turn_idx=5) is True
        assert is_memory_visible(alice, None, child, memory_turn_idx=15) is False
