"""Unbinding a story's canon by `{"lorebook_id": null}` survives a rewind.

The canon binding is snapshotted with the turn, so a change to it has to be
carried into the checkpoints a rewind can restore, or the next reroll
re-binds what the host unbound. `detach_lore` (`DELETE .../lorebook`) and the
bind path both call `_refresh_rewindable_checkpoints`; the null path of
`bind_lore` ran the same UPDATE and returned without it (audit 2026-11-01,
web_app F9). The UI uses DELETE, so API and extension callers met it.
"""
from __future__ import annotations

import time


def test_a_null_unbind_is_carried_into_the_checkpoint(temp_db):
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app

    db = temp_db
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Story", "", time.time()))
    book = db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("Canon", cid))
    assert app.bind_lore(cid, {"lorebook_id": book}) == {"lorebook_id": book}
    ensure_checkpoint(cid, 0)
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "", time.time()))

    assert app.bind_lore(cid, {"lorebook_id": None}) == {"lorebook_id": None}
    restore_checkpoint(cid, 0)
    assert db.q("SELECT lorebook_id FROM chats WHERE id=?", (cid,),
                one=True)["lorebook_id"] is None
