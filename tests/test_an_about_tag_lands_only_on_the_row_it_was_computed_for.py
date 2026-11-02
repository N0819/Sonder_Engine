"""An `about` tag lands only on the memory it was computed for.

`persist/about_backfill.py` reads a story's untagged rows, computes who each
moment had in it, then writes `UPDATE memories SET about=? WHERE id=?`. A
checkpoint restore is delete-and-reinsert and re-mints every id of the chat
(`memories.id` has no AUTOINCREMENT; the dump orders rows so ids swap on the
first restore -- audit 2026-11-01, persistence F4, reproduced: id 1 held the
seed before and the turn memory after). A restore landing between the
computation and the write -- a reroll while the startup backfill works --
put one mind's tag on another mind's memory: a moment the mind spent alone
named a body it never saw, which the `about` recall lane then hands back to a
question about that person.

The rule: the write is compare-and-set on the row's identity -- its mind and
its text -- so a row that moved under the computation is left for the next
pass rather than mis-tagged.
"""

from __future__ import annotations

import contextlib
import json
import time

from core.db import q, wset
from persist import about_backfill


def _char(db, name):
    return db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                 (name, json.dumps({"identity": {"name": name}}), "{}", time.time()))


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Mill", "", time.time()))
    ada, bob, cara = _char(db, "Ada"), _char(db, "Bob"), _char(db, "Cara")
    for char_id in (ada, bob, cara):
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,'active','{}')", (cid, char_id))
    turn = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                 (cid, 0, "begin", time.time()))
    wset(cid, "scene", {"rooms": {"hall": {}, "cellar": {}},
                        "positions": {"Ada": "hall", "Bob": "hall", "Cara": "cellar"}})
    for char_id, content in ((ada, "Ada stood in the hall."),
                             (cara, "Cara waited alone in the cellar.")):
        db.qi("INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,content,event_key) "
              "VALUES(?,?,?,?,?,?,?)",
              (cid, char_id, turn, 0, "episodic", content, f"ev:{char_id}"))
    return cid


def _a_restore_reinserts_them_swapped(cid):
    rows = [dict(r) for r in q("SELECT * FROM memories WHERE chat_id=? ORDER BY id", (cid,))]
    ids = [r["id"] for r in rows]
    from core.db import qi
    qi("DELETE FROM memories WHERE chat_id=?", (cid,))
    for new_id, row in zip(ids, reversed(rows)):
        qi("INSERT INTO memories(id,chat_id,char_id,turn_id,turn_idx,kind,content,event_key) "
           "VALUES(?,?,?,?,?,?,?,?)",
           (new_id, cid, row["char_id"], row["turn_id"], row["turn_idx"], row["kind"],
            row["content"], row["event_key"]))


def _about(cid):
    return {r["content"]: r["about"] for r in q(
        "SELECT content, about FROM memories WHERE chat_id=?", (cid,))}


def test_a_restore_between_the_reading_and_the_writing_mis_tags_nothing(temp_db, monkeypatch):
    cid = _story(temp_db)
    real = about_backfill.transaction

    @contextlib.contextmanager
    def the_restore_lands_first():
        _a_restore_reinserts_them_swapped(cid)
        with real() as c:
            yield c
    monkeypatch.setattr(about_backfill, "transaction", the_restore_lands_first)

    about_backfill.backfill_chat(cid)

    assert _about(cid)["Cara waited alone in the cellar."] in ("", None), (
        "Cara's lone moment must not name a body she never saw")

    monkeypatch.undo()
    about_backfill.backfill_chat(cid)
    tags = _about(cid)
    assert json.loads(tags["Ada stood in the hall."]) == ["Bob"]
    assert json.loads(tags["Cara waited alone in the cellar."]) == []
