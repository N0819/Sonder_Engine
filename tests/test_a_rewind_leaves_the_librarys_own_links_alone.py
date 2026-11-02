"""A story's rewind manages only the links it can put back.

`_restore_books` replaced every link between the books the snapshot mapped,
and the map deliberately includes the LIBRARY books a story reads by
reference. So a link the host drew between two library books -- a
library-wide edit -- was deleted by the next reroll or turn delete of ANY
story reading both, and `restore_lorebook_links` (which refuses a link
outside the story's own books) never put it back (audit 2026-11-01, web F2:
links before `[(1, 2)]`, after `[]`).

The rule: the managed subgraph is the restorable one -- links between the
story's OWN books. A link between library books is the library's, and a
story's checkpoint is not its business, in either direction.
"""

from __future__ import annotations

import time

from mind.memory import add_lorebook_link
from persist.checkpoints import ensure_checkpoint, restore_checkpoint


def _book(db, name, chat_id=None):
    return db.qi("INSERT INTO lorebooks(name,chat_id,book_type,resource_uid) "
                 "VALUES(?,?,?,?)", (name, chat_id, "general", f"uid_{name}"))


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Links", "", time.time()))
    lib_a, lib_b = _book(db, "LibA"), _book(db, "LibB")
    own_c, own_d = _book(db, "OwnC", cid), _book(db, "OwnD", cid)
    for book in (lib_a, lib_b, own_c, own_d):
        db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)",
              (cid, book))
    add_lorebook_link(own_c, own_d)
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "begin", time.time()))
    return cid, lib_a, lib_b, own_c, own_d


def _links(db):
    return sorted((r["source_book_id"], r["target_book_id"])
                  for r in db.q("SELECT source_book_id, target_book_id FROM lorebook_links"))


def test_a_library_link_drawn_after_the_checkpoint_survives_a_reroll(temp_db):
    cid, lib_a, lib_b, own_c, own_d = _story(temp_db)
    ensure_checkpoint(cid, 0)
    add_lorebook_link(lib_a, lib_b)          # the host, in the library

    restore_checkpoint(cid, 0)

    assert _links(temp_db) == sorted([(own_c, own_d), (lib_a, lib_b)])


def test_a_library_link_removed_after_the_checkpoint_stays_removed(temp_db):
    cid, lib_a, lib_b, own_c, own_d = _story(temp_db)
    add_lorebook_link(lib_a, lib_b)
    ensure_checkpoint(cid, 0)
    temp_db.qi("DELETE FROM lorebook_links WHERE source_book_id=? AND target_book_id=?",
               (lib_a, lib_b))

    restore_checkpoint(cid, 0)

    assert _links(temp_db) == [(own_c, own_d)]


def test_the_storys_own_links_still_roll_back(temp_db):
    cid, _lib_a, _lib_b, own_c, own_d = _story(temp_db)
    ensure_checkpoint(cid, 0)
    add_lorebook_link(own_d, own_c, relation_type="contains")   # a discarded beat's

    restore_checkpoint(cid, 0)

    assert _links(temp_db) == [(own_c, own_d)]
