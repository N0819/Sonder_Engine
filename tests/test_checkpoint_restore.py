"""Tests for memory checkpoint restoration."""

import json
import time

from character_schema import default_character_data
from memory import restore_chat_memories

def _chat_and_character(db):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    sheet = default_character_data("Alice")
    character_id = db.qi(
        """
        INSERT INTO characters(
            name,sheet,source,created,resource_uid
        )
        VALUES(?,?,?,?,?)
        """,
        (
            "Alice",
            json.dumps(sheet),
            "{}",
            time.time(),
            "char_alice",
        ),
    )

    db.qi(
        """
        INSERT INTO chat_chars(chat_id,char_id,status,state)
        VALUES(?,?,?,?)
        """,
        (chat_id, character_id, "active", "{}"),
    )

    return chat_id, character_id

def test_restore_preserves_archived_without_event_key(
    temp_db,
    monkeypatch,
):
    import memory
    from providers import EmbeddingBatch

    chat_id, character_id = _chat_and_character(temp_db)

    monkeypatch.setattr(
        memory,
        "embed_texts_meta",
        lambda texts: EmbeddingBatch(
            vectors=[[0.0] * 256 for _ in texts],
            model_key="test",
            dimensions=256,
        ),
    )

    restore_chat_memories(chat_id, [{
        "char_id": character_id,
        "turn_id": None,
        "turn_idx": 1,
        "kind": "episodic",
        "category": "episode",
        "provenance": "witnessed",
        "salience": 0.5,
        "content": "An archived memory.",
        "archived": True,
        "event_key": "",
    }])

    row = temp_db.q(
        """
        SELECT archived,event_key
        FROM memories
        WHERE chat_id=? AND char_id=?
        """,
        (chat_id, character_id),
        one=True,
    )

    assert row is not None
    assert row["archived"] == 1
    assert row["event_key"] == ""

def test_restore_replaces_existing_chat_memories(
    temp_db,
    monkeypatch,
):
    import memory
    from providers import EmbeddingBatch

    chat_id, character_id = _chat_and_character(temp_db)

    monkeypatch.setattr(
        memory,
        "embed_texts_meta",
        lambda texts: EmbeddingBatch(
            vectors=[[0.0] * 256 for _ in texts],
            model_key="test",
            dimensions=256,
        ),
    )

    restore_chat_memories(chat_id, [{
        "char_id": character_id,
        "turn_id": None,
        "content": "Old restored memory.",
    }])

    restore_chat_memories(chat_id, [{
        "char_id": character_id,
        "turn_id": None,
        "content": "New restored memory.",
    }])

    rows = temp_db.q(
        """
        SELECT content
        FROM memories
        WHERE chat_id=? AND char_id=?
        """,
        (chat_id, character_id),
    )

    assert [row["content"] for row in rows] == [
        "New restored memory.",
    ]