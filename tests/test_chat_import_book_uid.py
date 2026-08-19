"""Regression test: same-install chat import must not abort on lorebook
resource_uid collisions.

chat_import used to reuse an archived lorebook's resource_uid verbatim.
Characters/personas dedupe by uid onto the existing row
(_import_or_match_*), but lorebooks are per-chat COPIES inserted fresh --
so re-importing an archive into the very install that exported it hit
uq_lorebooks_resource_uid and the UNIQUE violation aborted the entire
import. The imported copy is a distinct book in a distinct chat: when the
uid is already taken locally, a fresh one is minted (_import_book_uid);
when it is free (cross-install import), it is kept for portability.
"""

import time

from web import app


def _make_chat_with_books(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Story", "", time.time()),
    )
    canon = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,resource_uid) VALUES(?,?,?)",
        ("Canon", chat_id, "book_canon_orig"),
    )
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, chat_id))
    extra = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,resource_uid) "
        "VALUES(?,?,?,?)",
        ("Harbor lore", chat_id, "general", "book_extra_orig"),
    )
    temp_db.qi(
        "INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)",
        (chat_id, extra),
    )
    temp_db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content,category) "
        "VALUES(?,?,?,?)",
        (canon, "lighthouse", "The lamp never goes out.", "layout"),
    )
    return chat_id, canon, extra


def test_same_install_import_survives_book_uid_collision(temp_db):
    chat_id, canon, extra = _make_chat_with_books(temp_db)

    exported = app.chat_export(chat_id)
    exported_uids = {b["book"]["resource_uid"] for b in exported["lorebooks"]}
    assert exported_uids == {"book_canon_orig", "book_extra_orig"}

    # Import back into the SAME install: the original books still hold
    # those uids. Pre-fix this raised sqlite3.IntegrityError (UNIQUE
    # constraint on lorebooks.resource_uid) and aborted the whole import.
    imported = app.chat_import({"data": exported})
    ncid = imported["id"]

    new_books = temp_db.q(
        "SELECT id,name,resource_uid FROM lorebooks WHERE chat_id=?",
        (ncid,),
    )
    assert len(new_books) == 2
    new_uids = {b["resource_uid"] for b in new_books}
    # Distinct books: fresh, non-null, non-colliding uids.
    assert all(u for u in new_uids)
    assert len(new_uids) == 2
    assert not new_uids & {"book_canon_orig", "book_extra_orig"}

    # The originals are untouched and the imported chat has its own canon.
    assert temp_db.q(
        "SELECT resource_uid FROM lorebooks WHERE id=?", (canon,), one=True
    )["resource_uid"] == "book_canon_orig"
    new_canon = temp_db.q(
        "SELECT lorebook_id FROM chats WHERE id=?", (ncid,), one=True
    )["lorebook_id"]
    assert new_canon in {b["id"] for b in new_books}
    # Entries came through under the new book.
    entry = temp_db.q(
        "SELECT content FROM lore_entries WHERE lorebook_id=?",
        (new_canon,), one=True,
    )
    assert entry and entry["content"] == "The lamp never goes out."


def test_cross_install_import_keeps_free_book_uid(temp_db):
    """Portability contract preserved: when the uid is NOT taken locally
    (the cross-install case), the imported book keeps the archive's uid."""
    chat_id, canon, extra = _make_chat_with_books(temp_db)
    exported = app.chat_export(chat_id)

    # Simulate the other-install side: free the uids locally.
    temp_db.qi("DELETE FROM chats WHERE id=?", (chat_id,))
    assert not temp_db.q(
        "SELECT id FROM lorebooks WHERE resource_uid IN (?,?)",
        ("book_canon_orig", "book_extra_orig"),
    )

    imported = app.chat_import({"data": exported})
    new_uids = {
        b["resource_uid"]
        for b in temp_db.q(
            "SELECT resource_uid FROM lorebooks WHERE chat_id=?",
            (imported["id"],),
        )
    }
    assert new_uids == {"book_canon_orig", "book_extra_orig"}


class TestARewoundBookIsTheSameBook:
    """PERSISTENCE-F15's restore-side writer.

    `_recreate_snapshot_book` brings back a book the chat owned at snapshot
    time and has since deleted -- the ordinary way to reach it is rolling back
    past the turn that minted one. It inserted no `resource_uid` at all, so
    the book came back as a resource with no identity and `db.init()`'s
    `_backfill_resource_uids` stamped a stranger's uid onto it at the next
    open. That is the wrong answer twice over: the book already HAD an
    identity, and the backfill is a repair pass that should have nothing left
    to repair.
    """

    def _snapshot(self, db, chat_id):
        from persist.checkpoints import snapshot_state

        return snapshot_state(chat_id)["lorebooks"]

    def test_the_recreated_book_keeps_the_uid_it_had(self, temp_db):
        from persist.checkpoints import _restore_books

        chat_id, canon, extra = _make_chat_with_books(temp_db)
        books = self._snapshot(temp_db, chat_id)
        temp_db.qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (chat_id,))
        temp_db.qi("DELETE FROM lorebooks WHERE chat_id=?", (chat_id,))

        _restore_books(chat_id, books, [])

        uids = {row["resource_uid"] for row in temp_db.q(
            "SELECT resource_uid FROM lorebooks WHERE chat_id=?", (chat_id,))}
        assert uids == {"book_canon_orig", "book_extra_orig"}

    def test_a_taken_uid_mints_a_fresh_one_rather_than_none(self, temp_db):
        """The uid is UNIQUE where not null. A restore must not abort because
        some other row holds the name, and must not fall back to leaving the
        column empty -- which is the state the backfill exists to clean up."""
        from persist.checkpoints import _restore_books

        chat_id, canon, extra = _make_chat_with_books(temp_db)
        books = self._snapshot(temp_db, chat_id)
        temp_db.qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (chat_id,))
        temp_db.qi("DELETE FROM lorebooks WHERE chat_id=?", (chat_id,))
        # A library book on this install already answers to that name. Given
        # an id of its own, well clear of the deleted rows': SQLite reuses the
        # low rowids of an emptied table, and a library book that landed on
        # the snapshot's own id would make `_recreate_snapshot_book` decline
        # for the unrelated reason it declines for a still-live row.
        temp_db.qi("INSERT INTO lorebooks(id,name,resource_uid) VALUES(?,?,?)",
                   (9999, "Someone else's Canon", "book_canon_orig"))

        _restore_books(chat_id, books, [])

        uids = {row["resource_uid"] for row in temp_db.q(
            "SELECT resource_uid FROM lorebooks WHERE chat_id=?", (chat_id,))}
        assert None not in uids and "" not in uids
        assert "book_extra_orig" in uids
        assert len(uids) == 2
