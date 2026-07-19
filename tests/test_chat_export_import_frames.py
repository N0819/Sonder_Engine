"""Regression test for chat_export/chat_import learning frames: a
previous version silently had no frames key in the export at all, and
turn_branch (a separate code path) deliberately stripped frame
references as a documented limitation. Both now clone frames properly
with a fresh id remap instead of dropping them.
"""

from __future__ import annotations

import json
import time

import app
import memory
from character_schema import default_character_data


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time(), f"char_{name.lower()}"),
    )


def test_export_then_import_round_trips_frames_and_their_memories(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, alice, "active", "{}"),
    )
    future = app.frames_create(chat_id, {
        "label": "Far future", "ordinal": 300000000, "kind": "future",
        "travelers": [alice],
    })
    memory.add_memory(chat_id, alice, None, "episode", "witnessed", 0.5,
                       "From the future.", turn_idx=0, frame_id=future["id"])

    exported = app.chat_export(chat_id)
    assert len(exported["frames"]) == 1
    assert exported["frames"][0]["label"] == "Far future"

    # chat_import resolves memories' char_id through resources.characters
    # (old_id -> a found-or-created character) -- since this re-imports
    # into the SAME database, resource_uid matches the existing row.
    exported["resources"] = {
        "characters": [{"old_id": alice, "resource_uid": "char_alice",
                        "sheet": default_character_data("Alice"), "source": {}}],
    }

    imported = app.chat_import({"data": exported})
    ncid = imported["id"]

    frames_after = app.frames_list(ncid)["frames"]
    assert len(frames_after) == 2  # implicit present + the cloned one
    cloned = next(f for f in frames_after if f["id"] is not None)
    assert cloned["label"] == "Far future"
    assert cloned["ordinal"] == 300000000
    assert cloned["kind"] == "future"

    mem_row = temp_db.q("SELECT frame_id FROM memories WHERE chat_id=?", (ncid,), one=True)
    assert mem_row["frame_id"] == cloned["id"]
