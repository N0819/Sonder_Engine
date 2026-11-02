"""An imported book's `origin_id` names a book of THIS install, or nothing.

`origin_id` is an integer row id. A fork of another story's book carries the
source book's id (`attach_lore`), and the archive import copied it verbatim
into a different install, where the same integer can be an unrelated LIBRARY
book. `attach_lore` reads `lb.origin_id = src` as "already attached", so the
host could never attach that library book to the imported story (audit
2026-11-01, persistence F8: `{'lorebook_id': 2, 'already': True}`); and a
restore of an imported checkpoint read a book's foreign origin as a library
reference and attached that stranger instead of re-creating the book.

The rule: an origin survives an import only through the archive's own book
map -- when the origin came in the same archive -- and is NULL otherwise, in
the live rows and in every checkpoint the archive carried.
"""

from __future__ import annotations

import json
import time

from tests.helpers import remove_scratch_db, scratch_db_path


def _chat(db, name):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def _source(db):
    """Install A: story X forks story W's book, a checkpoint is taken, and
    the fork is then detached -- so only the checkpoint still holds it."""
    from mind.memory import add_lore
    from persist.checkpoints import ensure_checkpoint
    from web import app

    w = _chat(db, "W")
    wbook = db.qi("INSERT INTO lorebooks(name,chat_id,book_type,resource_uid) "
                  "VALUES(?,?,?,?)", ("W's notes", w, "general", "uid_wbook"))
    add_lore(wbook, "ford", "The ford floods in spring.", turn_added=0)
    x = _chat(db, "X")
    fork = app.attach_lore(x, {"lorebook_id": wbook})["lorebook_id"]
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (x, 0, "begin", time.time()))
    ensure_checkpoint(x, 0)
    return x, wbook, fork


def _into_another_install(db, archive, wbook):
    """Install B, whose library book `wbook` is an unrelated stranger."""
    from web import app

    lib = None
    for i in range(wbook):
        lib = db.qi("INSERT INTO lorebooks(name,chat_id,book_type,resource_uid) "
                    "VALUES(?,?,?,?)", (f"Library {i}", None, "general", f"uid_lib{i}"))
    assert lib == wbook, "the fixture must make the integer collide"
    return app.chat_import({"data": archive})["id"], lib


def test_the_imported_fork_does_not_block_attaching_an_unrelated_library_book(temp_db):
    from core import db
    from web import app

    x, wbook, _fork = _source(temp_db)
    archive = json.loads(json.dumps(app.chat_export(x)))
    other = scratch_db_path()
    try:
        db.configure(other)
        db.init()
        nx, lib = _into_another_install(db, archive, wbook)

        origins = [r["origin_id"] for r in db.q(
            "SELECT origin_id FROM lorebooks WHERE chat_id=?", (nx,))]
        assert origins == [None]
        attached = app.attach_lore(nx, {"lorebook_id": lib})
        assert attached == {"lorebook_id": lib}
    finally:
        db.close_connection()
        remove_scratch_db(other)


def test_a_restore_of_an_imported_checkpoint_recreates_the_book_rather_than_borrowing_a_stranger(temp_db):
    from core import db
    from persist.checkpoints import restore_checkpoint
    from web import app

    x, wbook, fork = _source(temp_db)
    # A later beat lost the fork; no refresh ran, so only the checkpoint
    # still holds it (the route would have refreshed it away).
    temp_db.qi("DELETE FROM lorebooks WHERE id=?", (fork,))
    archive = json.loads(json.dumps(app.chat_export(x)))
    other = scratch_db_path()
    try:
        db.configure(other)
        db.init()
        nx, lib = _into_another_install(db, archive, wbook)

        restore_checkpoint(nx, 0)

        attached = {r["lorebook_id"]: r["chat_id"] for r in db.q(
            "SELECT cl.lorebook_id, lb.chat_id FROM chat_lorebooks cl "
            "JOIN lorebooks lb ON lb.id=cl.lorebook_id WHERE cl.chat_id=?", (nx,))}
        assert lib not in attached, "a stranger's library book is not the fork"
        assert list(attached.values()) == [nx], "the fork comes back as the story's own"
    finally:
        db.close_connection()
        remove_scratch_db(other)
