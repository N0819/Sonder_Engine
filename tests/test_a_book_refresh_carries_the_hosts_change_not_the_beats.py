"""Refreshing a checkpoint carries the host's book change, never the beat's.

An attach, enable, detach, bind or unbind refreshes the checkpoints a rewind
can restore, so the rewind keeps the host's change. An OLDER checkpoint took
only the book set (`_carry_the_book_set`): it "lies under turns that wrote
lore of their own". The NEWEST one took the lore as it is now, whole -- and
it lies under exactly one turn that writes lore of its own. So a canon claim
that beat ratified was copied into the world BEFORE the beat, and survived
the beat's own reroll (audit 2026-11-01, persistence F6: "turn 0's own canon
entry survives its reroll: True").

The rule: every refresh carries the book set -- which books, enabled or not,
which is canon -- and leaves what a held book contained as it was taken.
"""

from __future__ import annotations

import time

from mind.memory import add_lore
from persist.checkpoints import ensure_checkpoint, refresh_checkpoint, restore_checkpoint


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Canon", "", time.time()))
    canon = db.qi("INSERT INTO lorebooks(name,chat_id,book_type,resource_uid) "
                  "VALUES(?,?,?,?)", ("Canon", cid, "general", "uid_c"))
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, cid))
    add_lore(canon, "mill", "The mill stands by the ford.", turn_added=0)
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "begin", time.time()))
    ensure_checkpoint(cid, 0)
    return cid, canon


def test_the_beats_own_canon_claim_does_not_survive_its_reroll(temp_db):
    cid, canon = _story(temp_db)
    # what turn 0's commit wrote, then an attach/enable route's refresh
    add_lore(canon, "ratified", "A claim the discarded beat ratified.", turn_added=0)
    refresh_checkpoint(cid, 0)

    restore_checkpoint(cid, 0)

    assert [r["keys"] for r in temp_db.q(
        "SELECT keys FROM lore_entries WHERE lorebook_id=?", (canon,))] == ["mill"]


def test_the_hosts_attach_still_survives_it(temp_db):
    cid, _canon = _story(temp_db)
    library = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type,resource_uid) "
                         "VALUES(?,?,?,?)", ("Atlas", None, "general", "uid_atlas"))
    temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)",
               (cid, library))
    refresh_checkpoint(cid, 0)

    restore_checkpoint(cid, 0)

    assert temp_db.q("SELECT 1 FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?",
                     (cid, library), one=True) is not None
