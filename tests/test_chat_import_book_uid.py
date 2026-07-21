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

import app


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
