"""Regression tests for dramatic_irony_feed and promise_ledger: chat-wide
(not per-character, unlike list_memories) queries used by the Insights
tab. Neither function should ever claim to know a belief is false or a
promise was kept/broken -- they only surface the provenance/category
distinctions already tracked per memory."""

from __future__ import annotations

import json
import time

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


def test_dramatic_irony_feed_excludes_witnessed_memories(temp_db):
    chat_id = _make_chat(temp_db)
    char_id = _make_char(temp_db, "Alice")

    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", 0.5,
        "Alice saw the fire herself.", turn_idx=1,
    )
    memory.add_memory(
        chat_id, char_id, None, "episode", "told", 0.5,
        "Alice was told the fire was an accident.", turn_idx=2,
    )

    feed = memory.dramatic_irony_feed(chat_id)
    contents = {m["content"] for m in feed}
    assert "Alice was told the fire was an accident." in contents
    assert "Alice saw the fire herself." not in contents


def test_dramatic_irony_feed_spans_every_character_in_the_chat(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")
    bob = _make_char(temp_db, "Bob")

    memory.add_memory(
        chat_id, alice, None, "episode", "inferred", 0.5,
        "Alice suspects Bob is lying.", turn_idx=1,
    )
    memory.add_memory(
        chat_id, bob, None, "episode", "heard", 0.5,
        "Bob heard a rumor about the mayor.", turn_idx=2,
    )

    feed = memory.dramatic_irony_feed(chat_id)
    names = {m["char_name"] for m in feed}
    assert names == {"Alice", "Bob"}


def test_dramatic_irony_feed_excludes_archived_memories(temp_db):
    chat_id = _make_chat(temp_db)
    char_id = _make_char(temp_db, "Alice")

    memory.add_memory(
        chat_id, char_id, None, "episode", "told", 0.5,
        "A stale rumor.", turn_idx=1,
    )
    temp_db.qi(
        "UPDATE memories SET archived=1 WHERE chat_id=? AND char_id=?",
        (chat_id, char_id),
    )

    assert memory.dramatic_irony_feed(chat_id) == []


def test_dramatic_irony_feed_is_scoped_to_its_own_chat(temp_db):
    chat_a = _make_chat(temp_db)
    chat_b = _make_chat(temp_db)
    char_id = _make_char(temp_db, "Alice")

    memory.add_memory(
        chat_a, char_id, None, "episode", "told", 0.5,
        "Told in chat A.", turn_idx=1,
    )
    memory.add_memory(
        chat_b, char_id, None, "episode", "told", 0.5,
        "Told in chat B.", turn_idx=1,
    )

    feed = memory.dramatic_irony_feed(chat_a)
    assert {m["content"] for m in feed} == {"Told in chat A."}


def test_promise_ledger_only_returns_promise_category(temp_db):
    chat_id = _make_chat(temp_db)
    char_id = _make_char(temp_db, "Alice")

    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", 0.5,
        "Alice will return the sword by dawn.", turn_idx=1, category="promise",
    )
    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", 0.5,
        "Alice walked into town.", turn_idx=2, category="episode",
    )

    ledger = memory.promise_ledger(chat_id)
    contents = {m["content"] for m in ledger}
    assert "Alice will return the sword by dawn." in contents
    assert "Alice walked into town." not in contents


def test_promise_ledger_is_chronological_across_characters(temp_db):
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db, "Alice")
    bob = _make_char(temp_db, "Bob")

    memory.add_memory(
        chat_id, bob, None, "episode", "witnessed", 0.5,
        "Bob promises to guard the gate.", turn_idx=5, category="promise",
    )
    memory.add_memory(
        chat_id, alice, None, "episode", "witnessed", 0.5,
        "Alice promises to bring supplies.", turn_idx=2, category="promise",
    )

    ledger = memory.promise_ledger(chat_id)
    turns = [m["turn_idx"] for m in ledger]
    assert turns == sorted(turns)
    assert turns == [2, 5]


def test_promise_ledger_has_no_kept_or_broken_field(temp_db):
    chat_id = _make_chat(temp_db)
    char_id = _make_char(temp_db, "Alice")
    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", 0.5,
        "Alice promises to write.", turn_idx=1, category="promise",
    )

    ledger = memory.promise_ledger(chat_id)
    assert "kept" not in ledger[0]
    assert "broken" not in ledger[0]
    assert "status" not in ledger[0]
