"""Regression tests for per-character memory export/import: unlike
restore_chat_memories (destructive, only ever used for checkpoint
restore), import_character_memories is additive -- a user carrying a
character's memory bank into a chat, possibly a different one than it
was exported from, must never lose existing memories in the process."""

from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException

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
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


def test_dump_character_memories_is_scoped_to_one_character(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")
    bob = _make_char(temp_db, "Bob")

    memory.add_memory(chat_id, alice, None, "episode", "witnessed", 0.5,
                       "Alice's memory.", turn_idx=1)
    memory.add_memory(chat_id, bob, None, "episode", "witnessed", 0.5,
                       "Bob's memory.", turn_idx=1)

    dumped = memory.dump_character_memories(chat_id, alice)
    assert {m["content"] for m in dumped} == {"Alice's memory."}
    # No char_id/turn_id/chat_id leak into the export -- irrelevant to a
    # portable per-character memory bank and would misleadingly imply
    # they still mean something after being carried elsewhere.
    assert "char_id" not in dumped[0]
    assert "turn_id" not in dumped[0]
    assert "chat_id" not in dumped[0]


def test_import_is_additive_not_destructive(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")
    memory.add_memory(chat_id, alice, None, "episode", "witnessed", 0.5,
                       "Existing memory.", turn_idx=1)

    imported = memory.import_character_memories(chat_id, alice, [
        {"content": "Imported memory one.", "provenance": "told"},
        {"content": "Imported memory two.", "provenance": "heard"},
    ])

    assert imported == 2
    contents = {m["content"] for m in memory.dump_character_memories(chat_id, alice)}
    assert contents == {"Existing memory.", "Imported memory one.", "Imported memory two."}


def test_import_strips_turn_references(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")

    memory.import_character_memories(chat_id, alice, [
        {"content": "From another story.", "turn_idx": 99, "turn_id": 12345},
    ])

    row = temp_db.q(
        "SELECT turn_id, turn_idx FROM memories WHERE chat_id=? AND char_id=?",
        (chat_id, alice), one=True,
    )
    assert row["turn_id"] is None
    assert row["turn_idx"] is None


def test_import_skips_blank_content(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")

    imported = memory.import_character_memories(chat_id, alice, [
        {"content": "   "},
        {"content": ""},
        {"content": "Real one."},
    ])

    assert imported == 1


def test_import_into_a_different_chat_than_it_was_exported_from(temp_db):
    source_chat = _make_chat(temp_db)
    target_chat = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")

    memory.add_memory(source_chat, alice, None, "episode", "witnessed", 0.5,
                       "From the original story.", turn_idx=3)
    exported = memory.dump_character_memories(source_chat, alice)

    imported = memory.import_character_memories(target_chat, alice, exported)

    assert imported == 1
    assert memory.dump_character_memories(target_chat, alice)[0]["content"] == "From the original story."
    # The source chat's own memories are untouched.
    assert len(memory.dump_character_memories(source_chat, alice)) == 1


def test_export_endpoint_returns_expected_envelope(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")
    memory.add_memory(chat_id, alice, None, "episode", "witnessed", 0.5,
                       "Hello.", turn_idx=1)

    result = app.mem_export(chat_id, alice)
    assert result["format"] == "fiction_engine.character_memories.v1"
    assert result["char_name"] == "Alice"
    assert len(result["memories"]) == 1


def test_export_endpoint_404s_for_missing_character(temp_db):
    chat_id = _make_chat(temp_db)
    with pytest.raises(HTTPException) as exc_info:
        app.mem_export(chat_id, 999999)
    assert exc_info.value.status_code == 404


def test_import_endpoint_rejects_missing_memories_list(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")
    with pytest.raises(HTTPException) as exc_info:
        app.mem_import(chat_id, alice, {})
    assert exc_info.value.status_code == 400


def test_import_endpoint_404s_for_missing_character(temp_db):
    chat_id = _make_chat(temp_db)
    with pytest.raises(HTTPException) as exc_info:
        app.mem_import(chat_id, 999999, {"memories": []})
    assert exc_info.value.status_code == 404


def test_import_endpoint_round_trips_export(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")
    memory.add_memory(chat_id, alice, None, "episode", "witnessed", 0.5,
                       "Round trip me.", turn_idx=1, category="promise")

    exported = app.mem_export(chat_id, alice)
    result = app.mem_import(chat_id, alice, {"memories": exported["memories"]})

    assert result == {"ok": True, "imported": 1}
    contents = [m["content"] for m in memory.dump_character_memories(chat_id, alice)]
    assert contents.count("Round trip me.") == 2
