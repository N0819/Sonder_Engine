"""A checkpoint outlives the characters it names, and a rewind must not.

`chat_char_frames.char_id` is `REFERENCES characters(id)`. Deleting a
character from the library cascades its live override rows away, but a
checkpoint keeps its own copy inside a JSON blob where no foreign key reaches
it. Replaying that copy raised `IntegrityError: FOREIGN KEY constraint
failed` and rolled the whole restore back -- every reroll, rerun and delete of
the story's latest turn returned 500, and so did every branch from a turn
whose checkpoint held the row (audit 2026-11-01, persistence F2, web F3;
reproduced as `restore FAILED: IntegrityError FOREIGN KEY constraint failed`).

The memories, summaries and persona rosters already drop such an orphan
(`memory_common.surviving_character_ids`, `_restore_chat_personas`); the era
override is the sibling that did not. The rule is the cascade the schema
already ran, applied to the copy that missed it.
"""

from __future__ import annotations

import json
import time

from persist.checkpoints import restore_checkpoint, snapshot_blob


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Eras", "", time.time()))


def _char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps({"identity": {"name": name}}), "{}", time.time()))


def _story(db):
    """A story with an era, two cast members and an override for each."""
    cid = _chat(db)
    ada, bram = _char(db, "Ada"), _char(db, "Bram")
    for char_id in (ada, bram):
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,'active','{}')", (cid, char_id))
    era = db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) "
                "VALUES(?,?,?,?,?)", (cid, "Past", 1, "past", time.time()))
    for char_id, mood in ((ada, "calm"), (bram, "wary")):
        db.qi("INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) "
              "VALUES(?,?,?,?,?)",
              (cid, char_id, era, "dormant", json.dumps({"mood": mood})))
    turn = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, 0, "begin", time.time()))
    db.qi("INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
          (cid, 1, snapshot_blob(cid), time.time()))
    return cid, turn, era, ada, bram


def _delete_from_the_library(db, char_id):
    # what `web.app.char_del` does
    db.qi("DELETE FROM characters WHERE id=?", (char_id,))
    db.qi("DELETE FROM chat_chars WHERE char_id=?", (char_id,))


def test_a_restore_drops_the_override_of_a_deleted_character(temp_db):
    cid, _turn, era, ada, bram = _story(temp_db)
    _delete_from_the_library(temp_db, bram)

    restore_checkpoint(cid, 1)

    rows = {r["char_id"]: json.loads(r["state"]) for r in temp_db.q(
        "SELECT char_id, state FROM chat_char_frames WHERE chat_id=? AND frame_id=?",
        (cid, era))}
    assert rows == {ada: {"mood": "calm"}}, (
        "the surviving character's era override comes back; the deleted "
        "one's is the cascade's to drop")


def test_a_branch_from_that_turn_drops_it_too(temp_db):
    from web import app

    cid, turn, _era, ada, bram = _story(temp_db)
    _delete_from_the_library(temp_db, bram)

    ncid = app.turn_branch(turn)["id"]

    rows = temp_db.q("SELECT char_id FROM chat_char_frames WHERE chat_id=?", (ncid,))
    assert [r["char_id"] for r in rows] == [ada]
