"""Regression test for consolidate_character_memory's payload scope: it
used to resend every memory since turn 0 (including ones already archived
or already folded into a previous summary) on every consolidation pass,
even though the previous summary is already in the payload as context.
This bounds the query to memories since the last summary's end_turn_idx
and excludes archived rows."""

from __future__ import annotations

import json
import time

import memory
from character_schema import default_character_data


def _make_chat_and_char(db):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Alice", json.dumps(default_character_data("Alice")), "{}", time.time()),
    )
    return chat_id, char_id


def test_second_consolidation_only_sends_memories_since_last_summary(
    temp_db, monkeypatch,
):
    chat_id, char_id = _make_chat_and_char(temp_db)

    for idx in range(1, 6):
        memory.add_memory(
            chat_id, char_id, None, "episode", "witnessed", 0.5,
            f"Something happened at turn {idx}.", turn_idx=idx,
        )

    captured = {}

    def fake_chat_complete(role, system, user, **kwargs):
        captured["payload"] = json.loads(user)
        return json.dumps({"summary": "first summary", "key_phrases": [], "stable_facts": []})

    monkeypatch.setattr(memory, "chat_complete", fake_chat_complete)

    memory.consolidate_character_memory(chat_id, char_id)
    first_turns = {m["turn_idx"] for m in captured["payload"]["memories_chronological"]}
    assert first_turns == {1, 2, 3, 4, 5}

    # Now add a second, later batch and consolidate again -- the second
    # call must only see the NEW memories, not turns 1-5 again, since
    # those are already folded into the previous_summary field.
    for idx in range(6, 9):
        memory.add_memory(
            chat_id, char_id, None, "episode", "witnessed", 0.5,
            f"Something happened at turn {idx}.", turn_idx=idx,
        )

    memory.consolidate_character_memory(chat_id, char_id)
    second_turns = {m["turn_idx"] for m in captured["payload"]["memories_chronological"]}
    assert second_turns == {6, 7, 8}
    assert captured["payload"]["previous_summary"]["summary"] == "first summary"


def test_archived_memories_are_excluded_from_the_payload(temp_db, monkeypatch):
    chat_id, char_id = _make_chat_and_char(temp_db)

    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", 0.1,
        "A minor, forgettable moment.", turn_idx=1,
    )
    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", 0.5,
        "A more notable moment.", turn_idx=2,
    )

    temp_db.qi(
        "UPDATE memories SET archived=1 WHERE chat_id=? AND char_id=? AND turn_idx=1",
        (chat_id, char_id),
    )

    captured = {}

    def fake_chat_complete(role, system, user, **kwargs):
        captured["payload"] = json.loads(user)
        return json.dumps({"summary": "s", "key_phrases": [], "stable_facts": []})

    monkeypatch.setattr(memory, "chat_complete", fake_chat_complete)

    memory.consolidate_character_memory(chat_id, char_id)
    turns = {m["turn_idx"] for m in captured["payload"]["memories_chronological"]}
    assert turns == {2}
