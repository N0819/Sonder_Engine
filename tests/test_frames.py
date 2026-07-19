"""Regression tests for frames.py: the diegetic-time axis distinct from
turns.idx (play order). NULL frame_id always means "the present" so an
ordinary chat that never declares a frame must behave identically to
before this feature existed."""

from __future__ import annotations

import time

import db
import frames
from db import q, qi, wget, wset


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, '{}', "{}", time.time()),
    )


def _attach_char(db, chat_id, char_id):
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )


class TestFrameCRUD:
    def test_present_frame_is_implicit_and_always_resolvable(self, temp_db):
        present = frames.get_frame(None)
        assert present["id"] is None
        assert present["ordinal"] == 0
        assert present["kind"] == "present"

    def test_get_frame_returns_none_for_missing_id(self, temp_db):
        assert frames.get_frame(999999) is None

    def test_create_frame_rejects_present_as_a_kind(self, temp_db):
        chat_id = _make_chat(temp_db)
        import pytest
        with pytest.raises(ValueError):
            frames.create_frame(chat_id, label="x", ordinal=1, kind="present")

    def test_create_and_fetch_a_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        fid = frames.create_frame(
            chat_id, label="Far future", ordinal=300000000, kind="future",
            travelers=[alice],
        )
        frame = frames.get_frame(fid)
        assert frame["label"] == "Far future"
        assert frame["ordinal"] == 300000000
        assert frame["kind"] == "future"
        assert frame["travelers"] == [alice]
        assert frame["nonexistent_cast"] == []

    def test_list_frames_always_includes_present_first(self, temp_db):
        chat_id = _make_chat(temp_db)
        frames.create_frame(chat_id, label="Past", ordinal=-5, kind="past")
        listed = frames.list_frames(chat_id)
        assert listed[0]["id"] is None
        assert len(listed) == 2

    def test_ordinal_defaults_present_to_zero(self, temp_db):
        assert frames.frame_ordinal(None) == 0


class TestMemoryVisibility:
    def test_native_cannot_see_a_future_frames_memory(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        future = frames.create_frame(chat_id, label="Future", ordinal=10, kind="future")
        assert not frames.is_memory_visible(alice, future, None)

    def test_native_can_see_a_present_or_past_frames_memory(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        past = frames.create_frame(chat_id, label="Past", ordinal=-10, kind="past")
        assert frames.is_memory_visible(alice, past, None)
        assert frames.is_memory_visible(alice, None, None)

    def test_traveler_keeps_continuity_across_frames(self, temp_db):
        chat_id = _make_chat(temp_db)
        hinami = _make_char(temp_db, "Hinami")
        future = frames.create_frame(
            chat_id, label="Far future", ordinal=300000000, kind="future",
            travelers=[hinami],
        )
        # Hinami, standing in the far-future frame, can see a memory that
        # (from the future frame's perspective) was formed in the present.
        assert frames.is_memory_visible(hinami, None, future)

    def test_non_traveler_still_bound_by_native_cutoff_in_the_same_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        hinami = _make_char(temp_db, "Hinami")
        future = frames.create_frame(
            chat_id, label="Far future", ordinal=300000000, kind="future",
            travelers=[hinami],
        )
        # A memory formed IN the far-future frame is visible to anyone
        # standing in that same frame or later -- ordinal cutoff, not
        # traveler status, is what's doing the work here.
        assert frames.is_memory_visible(alice, future, future)


class TestExistenceMasking:
    def test_native_frame_with_no_mask_recognizes_everyone(self, temp_db):
        chat_id = _make_chat(temp_db)
        hinami = _make_char(temp_db, "Hinami")
        assert frames.is_recognized_in_frame(hinami, None)

    def test_masked_character_is_not_recognized_in_that_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        hinami = _make_char(temp_db, "Hinami")
        past = frames.create_frame(
            chat_id, label="Before Hinami existed", ordinal=-300000000, kind="past",
            travelers=[hinami], nonexistent_cast=[hinami],
        )
        # Hinami is physically present (she's a traveler) but not yet
        # recognized/known by natives of this era -- she doesn't exist
        # to them yet, even though she's standing right there.
        assert not frames.is_recognized_in_frame(hinami, past)

    def test_unmasked_character_in_a_declared_frame_is_still_recognized(self, temp_db):
        chat_id = _make_chat(temp_db)
        tamamo = _make_char(temp_db, "Tamamo")
        past = frames.create_frame(chat_id, label="Before Hinami existed", ordinal=-1, kind="past")
        assert frames.is_recognized_in_frame(tamamo, past)


class TestConcurrentFrameStorage:
    """Frame state is no longer swapped in and out of shared rows (that
    model couldn't support two frames being simultaneously live) -- it
    lives natively at frame-scoped storage keys, redirected transparently
    by db.py's active_frame_id contextvar. These tests exercise that
    mechanism directly; agents/runtime.py sets/resets it once per
    pipeline run (see tests/test_concurrent_frames.py for that wiring)."""

    def test_present_and_a_frame_have_independent_scene_rows(self, temp_db):
        chat_id = _make_chat(temp_db)
        future = frames.create_frame(chat_id, label="Future", ordinal=10, kind="future")

        wset(chat_id, "scene", {"location": "Earth"})
        token = db.active_frame_id.set(future)
        try:
            assert wget(chat_id, "scene", None) is None  # never-visited frame starts blank
            wset(chat_id, "scene", {"location": "Alien planet"})
        finally:
            db.active_frame_id.reset(token)

        # Present's own row is untouched by what happened while "in" the future.
        assert wget(chat_id, "scene") == {"location": "Earth"}

    def test_returning_to_the_same_frame_sees_its_own_prior_writes(self, temp_db):
        chat_id = _make_chat(temp_db)
        future = frames.create_frame(chat_id, label="Future", ordinal=10, kind="future")

        token = db.active_frame_id.set(future)
        try:
            wset(chat_id, "scene", {"location": "Alien planet"})
        finally:
            db.active_frame_id.reset(token)

        token = db.active_frame_id.set(future)
        try:
            assert wget(chat_id, "scene") == {"location": "Alien planet"}
        finally:
            db.active_frame_id.reset(token)

    def test_relationship_keys_are_frame_scoped(self, temp_db):
        chat_id = _make_chat(temp_db)
        future = frames.create_frame(chat_id, label="Future", ordinal=10, kind="future")

        wset(chat_id, "relationships:1", {"2": {"trust": 0.9}})

        token = db.active_frame_id.set(future)
        try:
            assert wget(chat_id, "relationships:1", None) is None
            wset(chat_id, "relationships:1", {"2": {"trust": 0.1}})
        finally:
            db.active_frame_id.reset(token)

        assert wget(chat_id, "relationships:1") == {"2": {"trust": 0.9}}

    def test_chat_global_keys_are_never_frame_scoped(self, temp_db):
        """fixed_points/paradox/paradox_policy/fiction_model etc. are
        cross-frame contracts, not per-era state -- they must resolve to
        the SAME row regardless of which frame is active."""
        chat_id = _make_chat(temp_db)
        future = frames.create_frame(chat_id, label="Future", ordinal=10, kind="future")

        wset(chat_id, "fiction_model", {"genre": "noir"})
        token = db.active_frame_id.set(future)
        try:
            assert wget(chat_id, "fiction_model") == {"genre": "noir"}
        finally:
            db.active_frame_id.reset(token)

    def test_frameless_chats_are_completely_unaffected(self, temp_db):
        """The contextvar defaults to None everywhere outside a pipeline
        run that explicitly sets it -- an ordinary chat that never
        touches frames must behave exactly as before this feature."""
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {"location": "Earth"})
        assert wget(chat_id, "scene") == {"location": "Earth"}
