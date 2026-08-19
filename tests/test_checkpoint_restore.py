"""Tests for memory checkpoint restoration."""

import json
import time

from story.character_schema import default_character_data
from mind.memory import restore_chat_memories
from tests.helpers import patch_provider_seam


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
    from persist.checkpoints import _restore_books
    from mind.memory import add_lorebook_link

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
    from persist.checkpoints import _restore_books
    from mind.memory import add_lorebook_link

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

def test_restore_books_recreates_a_book_deleted_since_the_snapshot(
    temp_db, monkeypatch,
):
    """A book the chat owned at snapshot time comes back.

    Deleting one is not a special case: the general one is a snapshot book
    with no counterpart in this database, which the id -> origin -> name
    matching already has to answer. Rolling back past the turn that minted a
    book is the ordinary way to reach it -- a restore deletes the books no
    snapshot book maps onto, so the next restore forward found nothing to
    match and the lore, the canon binding and the links between those books
    were all gone.
    """
    from persist import checkpoints
    from persist.checkpoints import _restore_books
    from mind import memory as memory_mod
    from mind.memory import add_lorebook_link

    patch_provider_seam(
        monkeypatch, "embed_texts", lambda texts: [[0.5, 0.5] for _ in texts]
    )

    chat_id, first, second = _chat_with_two_books(temp_db)
    temp_db.qi(
        "UPDATE chats SET lorebook_id=? WHERE id=?", (first, chat_id)
    )
    add_lorebook_link(first, second, "related", label="saved link")
    temp_db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content,category,entry_uid) "
        "VALUES(?,?,?,?,?)",
        (second, "harbor", "The harbor freezes in winter.", "place",
         "harbor_entry"),
    )
    snapshot = [
        {**_book_snapshot(first, "First"), "canon": True},
        {
            **_book_snapshot(second, "Second"),
            "entries": [{
                "keys": "harbor",
                "content": "The harbor freezes in winter.",
                "category": "place",
                "entry_uid": "harbor_entry",
            }],
        },
    ]
    links = [{
        "source_book_id": first,
        "target_book_id": second,
        "relation_type": "related",
        "label": "saved link",
        "notes": "",
        "bidirectional": 1,
        "follow_for_retrieval": 1,
        "weight": 0.75,
        "sort_order": 0,
    }]

    temp_db.qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (chat_id,))
    temp_db.qi("DELETE FROM lorebooks WHERE chat_id=?", (chat_id,))
    assert temp_db.q(
        "SELECT id FROM lorebooks WHERE chat_id=?", (chat_id,)
    ) == []

    old_to_new = _restore_books(chat_id, snapshot, links)

    names = {
        row["name"]: row["id"]
        for row in temp_db.q(
            "SELECT id,name FROM lorebooks WHERE chat_id=?", (chat_id,)
        )
    }
    assert set(names) == {"First", "Second"}
    assert old_to_new == {first: names["First"], second: names["Second"]}
    assert temp_db.q(
        "SELECT content FROM lore_entries WHERE lorebook_id=?",
        (names["Second"],),
        one=True,
    )["content"] == "The harbor freezes in winter."
    assert temp_db.q(
        "SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True
    )["lorebook_id"] == names["First"]
    assert temp_db.q(
        "SELECT label FROM lorebook_links "
        "WHERE source_book_id=? AND target_book_id=?",
        (names["First"], names["Second"]),
        one=True,
    )["label"] == "saved link"


def test_restore_preserves_archived_without_event_key(
    temp_db,
    monkeypatch,
):
    from mind import memory
    from llm.providers import EmbeddingBatch

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
    from mind import memory
    from llm.providers import EmbeddingBatch

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


class TestASnapshotBuiltOutsideTheLockIsStillCurrent:
    """`turn_new` serialises the checkpoint snapshot BEFORE taking the write
    lock -- it is the most expensive read in the app and holding the global
    write lock for it blocked every other writer. That is only safe if
    something detects a write landing in the window between building the blob
    and acquiring the lock.

    The first version compared the latest turn id, on the reasoning that the
    only writer that could slip in was another frame's pipeline committing a
    turn. That is not true: lorebook edits, character-sheet saves, memory
    edits and background world writes all change checkpointed state without
    inserting a turn row, and a turn-id check misses every one of them.
    `db.data_version` is the exact test instead.
    """

    def test_it_moves_when_another_connection_commits(self, temp_db):
        import sqlite3
        from core import db

        before = db.data_version()
        other = sqlite3.connect(db.DB)
        other.execute("INSERT INTO settings(key,value) VALUES(?,?)",
                      ("cpu_probe", "1"))
        other.commit()
        other.close()
        assert db.data_version() != before, (
            "a write from another connection must be detectable")

    def test_it_does_not_move_for_this_connections_own_writes(self, temp_db):
        """Or every snapshot would be treated as stale and rebuilt, which is
        the cost this avoids."""
        from core import db

        db.qi("INSERT INTO settings(key,value) VALUES(?,?)", ("own_probe", "1"))
        before = db.data_version()
        db.qi("INSERT INTO settings(key,value) VALUES(?,?)", ("own_probe2", "1"))
        assert db.data_version() == before

    def test_a_lorebook_edit_is_caught_where_a_turn_id_check_would_miss_it(
            self, temp_db):
        """The concrete case the turn-id guard was blind to."""
        import sqlite3
        from core import db

        cid = db.qi("INSERT INTO chats(name,created) VALUES(?,?)", ("S", 0.0))
        latest_before = db.q(
            "SELECT id FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
            (cid,), one=True)
        before = db.data_version()

        other = sqlite3.connect(db.DB)
        other.execute(
            "INSERT INTO lorebooks(name,book_type,summary) VALUES(?,?,?)",
            ("Edited elsewhere", "general", ""))
        other.commit()
        other.close()

        latest_after = db.q(
            "SELECT id FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
            (cid,), one=True)
        # No turn row was inserted, so the old guard sees nothing...
        assert (latest_before["id"] if latest_before else None) == (
            latest_after["id"] if latest_after else None)
        # ...and the real one sees it.
        assert db.data_version() != before
