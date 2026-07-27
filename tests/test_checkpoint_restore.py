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


def _book_snapshot(book_id, name):
    return {
        "lorebook_id": book_id,
        "name": name,
        "book_type": "general",
        "summary": "",
        "parent_id": None,
        "scope_world_id": None,
        "scope_location_id": None,
        "inheritance_mode": "inherit",
        "sort_order": 0,
        "anchor_entity_id": None,
        "retired_turn_id": None,
        "canon": False,
        "enabled": 1,
        "entries": [],
    }


def _chat_with_two_books(db):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Books", "", time.time()),
    )
    first = db.qi(
        "INSERT INTO lorebooks(chat_id,name,book_type) VALUES(?,?,?)",
        (chat_id, "First", "general"),
    )
    second = db.qi(
        "INSERT INTO lorebooks(chat_id,name,book_type) VALUES(?,?,?)",
        (chat_id, "Second", "general"),
    )
    for book_id in (first, second):
        db.qi(
            "INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) "
            "VALUES(?,?,1)",
            (chat_id, book_id),
        )
    return chat_id, first, second


def test_restore_books_removes_managed_links_when_snapshot_is_empty(temp_db):
    from checkpoints import _restore_books
    from memory import add_lorebook_link

    chat_id, first, second = _chat_with_two_books(temp_db)
    add_lorebook_link(first, second, "related", label="later timeline")
    library_first = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type) VALUES(?,?)",
        ("Library First", "general"),
    )
    library_second = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type) VALUES(?,?)",
        ("Library Second", "general"),
    )
    unrelated_link = add_lorebook_link(
        library_first,
        library_second,
        "related",
        label="unrelated library link",
    )

    _restore_books(
        chat_id,
        [_book_snapshot(first, "First"), _book_snapshot(second, "Second")],
        [],
    )

    assert temp_db.q(
        "SELECT * FROM lorebook_links "
        "WHERE source_book_id=? AND target_book_id=?",
        (first, second),
    ) == []
    assert temp_db.q(
        "SELECT label FROM lorebook_links WHERE id=?",
        (unrelated_link,),
        one=True,
    )["label"] == "unrelated library link"


def test_restore_books_replaces_existing_link_metadata(temp_db):
    from checkpoints import _restore_books
    from memory import add_lorebook_link

    chat_id, first, second = _chat_with_two_books(temp_db)
    add_lorebook_link(
        first,
        second,
        "related",
        label="later",
        notes="not in checkpoint",
        bidirectional=True,
        follow_for_retrieval=True,
        weight=0.9,
        sort_order=8,
    )
    snapshot_link = {
        "source_book_id": first,
        "target_book_id": second,
        "relation_type": "related",
        "label": "saved",
        "notes": "checkpoint metadata",
        "bidirectional": 0,
        "follow_for_retrieval": 0,
        "weight": 0.25,
        "sort_order": 3,
    }

    _restore_books(
        chat_id,
        [_book_snapshot(first, "First"), _book_snapshot(second, "Second")],
        [snapshot_link],
    )

    row = temp_db.q(
        "SELECT relation_type,label,notes,bidirectional,"
        "follow_for_retrieval,weight,sort_order "
        "FROM lorebook_links WHERE source_book_id=? AND target_book_id=?",
        (first, second),
        one=True,
    )
    assert dict(row) == {
        "relation_type": "related",
        "label": "saved",
        "notes": "checkpoint metadata",
        "bidirectional": 0,
        "follow_for_retrieval": 0,
        "weight": 0.25,
        "sort_order": 3,
    }

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
