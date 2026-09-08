"""A one-shot pass runs on a version crossing, not on every start
(review 2026-09-07 A85).

`_migrate_chat_copies_to_overlays` converts the pre-2026-09 "(chat copy)" of a
library book into a reference plus overlays. It sat in `init()` with no gate --
unlike `backfill_regions` (`current < 36`) and `backfill_memory_vectors`
(`current < 38`) beside it -- so it ran on EVERY server start. Its own
re-examination guard was destructive: the `kept_own` branch cleared
`origin_id`, and `origin_id` is not leftover bookkeeping. Four paths still
mint it (`copy_lorebook_tree` behind `attach_lore`'s fork of another story's
book, `turn_branch`, archive import, checkpoint restore) and two readers still
key by it (`attach_lore`'s already-attached check,
`checkpoints._restore_lorebooks`' `by_origin` index), so a fork attached today
was an unrecognisable orphan by tomorrow's start: re-attaching minted a second
fork, and a restore could not find the book it had.

The rule that now holds: the pass is gated on crossing schema v39, and the
fork shape keeps its origin. The clear survives only where `origin_id` really
is a leftover -- an origin that no longer exists, and a copy that IS the
chat's own canon.
"""

from __future__ import annotations

import sqlite3
import time


def _chat(temp_db, name="Story"):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      (name, "", time.time()))


def _book(temp_db, name, chat_id, origin_id=None):
    return temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,origin_id,book_type,summary) "
        "VALUES(?,?,?,?,?)", (name, chat_id, origin_id, "general", ""))


def _run_pass(temp_db):
    from core import db as core_db
    c = sqlite3.connect(core_db.DB)
    c.row_factory = sqlite3.Row
    try:
        report = core_db._migrate_chat_copies_to_overlays(c)
        c.commit()
    finally:
        c.close()
    return report


def test_a_fork_of_another_storys_book_keeps_its_origin(temp_db):
    """`attach_lore` mints exactly this shape whenever a story takes a book
    that belongs to another story: `duplicate_lorebook_for_chat` copies the
    tree with `origin_id` naming the source."""
    source_chat = _chat(temp_db, "The source story")
    source_book = _book(temp_db, "Their canon", source_chat)
    mine = _chat(temp_db, "My story")
    fork = _book(temp_db, "Their canon (chat copy)", mine, source_book)

    report = _run_pass(temp_db)

    assert report["kept_own"] == 1
    kept = temp_db.q("SELECT origin_id FROM lorebooks WHERE id=?", (fork,),
                     one=True)
    assert kept["origin_id"] == source_book


def test_re_attaching_that_book_finds_the_fork_instead_of_minting_a_second(
        temp_db):
    """The reader that the cleared key blinded: `attach_lore` recognises an
    already-attached book by `lorebook_id = src OR lb.origin_id = src`."""
    source_chat = _chat(temp_db, "The source story")
    source_book = _book(temp_db, "Their canon", source_chat)
    mine = _chat(temp_db, "My story")
    fork = _book(temp_db, "Their canon (chat copy)", mine, source_book)
    temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,"
               "enabled) VALUES(?,?,?,1)", (mine, fork, source_book))

    _run_pass(temp_db)

    already = temp_db.q(
        "SELECT cl.lorebook_id FROM chat_lorebooks cl "
        "JOIN lorebooks lb ON lb.id=cl.lorebook_id "
        "WHERE cl.chat_id=? AND (cl.lorebook_id=? OR lb.origin_id=?)",
        (mine, source_book, source_book), one=True)
    assert already is not None and already["lorebook_id"] == fork


def test_a_file_already_at_the_current_version_does_not_run_the_pass(temp_db):
    """The gate itself. `temp_db` is stamped at SCHEMA_VERSION, so a second
    `init()` -- one server restart -- must leave every book exactly as it
    is."""
    source_chat = _chat(temp_db, "The source story")
    source_book = _book(temp_db, "Their canon", source_chat)
    mine = _chat(temp_db, "My story")
    fork = _book(temp_db, "Their canon (chat copy)", mine, source_book)
    library = _book(temp_db, "A library book", None)
    copy = _book(temp_db, "A library book (chat copy)", mine, library)

    temp_db.init()

    assert temp_db.q("SELECT origin_id FROM lorebooks WHERE id=?", (fork,),
                     one=True)["origin_id"] == source_book
    # And the conversion did not run either: the copy is still a book.
    assert temp_db.q("SELECT 1 FROM lorebooks WHERE id=?", (copy,),
                     one=True) is not None


def test_a_copy_whose_origin_is_gone_is_still_cut_loose(temp_db):
    """The half of the clear that was always right: a dangling origin is
    leftover bookkeeping, and the book is the story's own now."""
    mine = _chat(temp_db, "My story")
    orphan = _book(temp_db, "Lost (chat copy)", mine, 424242)

    _run_pass(temp_db)

    assert temp_db.q("SELECT origin_id FROM lorebooks WHERE id=?", (orphan,),
                     one=True)["origin_id"] is None
