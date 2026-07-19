"""Regression test for B8 from Fable's audit: FRAME_SCOPED_WORLD_KEYS
named "currently_active_books", but the actual key read/written
everywhere (commit.py, agents/mapping.py) is "active_books" --
"currently_active_books" is only a payload FIELD name (agents/mapping.py's
director/mapping context), never a storage key. Since the set entry
didn't match, active_books was never actually frame-scoped: one frame's
commit could clobber another concurrently-played frame's active book
selection, and mapping in that other frame would then retrieve lore
through the wrong book set.
"""

from __future__ import annotations

import time

import db
from db import active_frame_id, wget, wset
from frames import create_frame


def _make_chat(db_module):
    return db_module.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


class TestActiveBooksIsActuallyFrameScoped:
    def test_active_books_key_is_registered_under_its_real_name(self):
        assert "active_books" in db.FRAME_SCOPED_WORLD_KEYS
        assert "currently_active_books" not in db.FRAME_SCOPED_WORLD_KEYS

    def test_two_frames_hold_independent_active_book_selections(self, temp_db):
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        wset(chat_id, "active_books", [1, 2])

        token = active_frame_id.set(future)
        try:
            wset(chat_id, "active_books", [3])
            future_books = wget(chat_id, "active_books")
        finally:
            active_frame_id.reset(token)

        present_books = wget(chat_id, "active_books")

        assert present_books == [1, 2]
        assert future_books == [3]
