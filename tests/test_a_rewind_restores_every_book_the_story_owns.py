"""A rewind restores every book the story OWNS, reachable or not.

The snapshot takes every chat-owned book -- "isolated descendants
intentionally do not inherit/retrieve through their parent, but they are
still chat-owned state that a reroll must restore exactly" -- but the restore
built its working set from owned books INTERSECTED with what retrieval can
reach. An `isolated` child is owned and unreachable, so the id lookup missed
it, the re-create declined (the id is live), and the book was skipped: never
restored, never deleted (audit 2026-11-01, persistence F7: "isolated entries
after restore: 2 (snapshot held 1)"). A book minted after the snapshot in
that shape survived the reroll too.

The rule: ownership, not reachability, is what a restore puts back.
"""

from __future__ import annotations

import time

from mind.memory import add_lore
from persist.checkpoints import ensure_checkpoint, restore_checkpoint


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Books", "", time.time()))
    canon = db.qi("INSERT INTO lorebooks(name,chat_id,book_type,resource_uid) "
                  "VALUES(?,?,?,?)", ("Canon", cid, "general", "uid_canon"))
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, cid))
    secret = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,resource_uid,parent_id,"
        "inheritance_mode) VALUES(?,?,?,?,?,?)",
        ("Secret", cid, "general", "uid_secret", canon, "isolated"))
    add_lore(secret, "vault", "The vault is under the mill.", turn_added=0)
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "begin", time.time()))
    return cid, canon, secret


def _entries(db, book):
    return [r["keys"] for r in db.q(
        "SELECT keys FROM lore_entries WHERE lorebook_id=? ORDER BY id", (book,))]


def test_an_isolated_child_goes_back_to_what_the_snapshot_held(temp_db):
    cid, _canon, secret = _story(temp_db)
    ensure_checkpoint(cid, 0)
    add_lore(secret, "ghost", "A discarded timeline's entry.", turn_added=0)

    restore_checkpoint(cid, 0)

    assert _entries(temp_db, secret) == ["vault"]


def test_an_isolated_book_minted_after_the_snapshot_is_taken_back(temp_db):
    cid, canon, _secret = _story(temp_db)
    ensure_checkpoint(cid, 0)
    later = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,resource_uid,parent_id,"
        "inheritance_mode) VALUES(?,?,?,?,?,?)",
        ("Minted", cid, "general", "uid_minted", canon, "isolated"))

    restore_checkpoint(cid, 0)

    assert temp_db.q("SELECT 1 FROM lorebooks WHERE id=?", (later,), one=True) is None
