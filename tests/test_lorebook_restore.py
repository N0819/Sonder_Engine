"""Tests for lorebook snapshot restoration."""

from memory import add_lore, restore_lorebook

def test_restore_lorebook_preserves_entry_id(temp_db, monkeypatch):
    import memory

    monkeypatch.setattr(
        memory,
        "embed_texts",
        lambda values: [[0.0] * 256 for _ in values],
    )

    book_id = temp_db.qi(
        """
        INSERT INTO lorebooks(name,book_type,summary,resource_uid)
        VALUES(?,?,?,?)
        """,
        ("Test", "general", "", "book_test"),
    )

    entry_id = add_lore(
        book_id,
        "door",
        "A wooden door.",
        entry_uid="entry_test",
    )

    restore_lorebook(book_id, [{
        "entry_uid": "entry_test",
        "keys": "door",
        "content": "A wooden door with a brass handle.",
        "category": "other",
    }])

    row = temp_db.q(
        """
        SELECT *
        FROM lore_entries
        WHERE lorebook_id=? AND entry_uid=?
        """,
        (book_id, "entry_test"),
        one=True,
    )

    assert row is not None
    assert row["id"] == entry_id
    assert "brass handle" in row["content"]

    count = temp_db.q(
        """
        SELECT COUNT(*) AS c
        FROM lore_entries
        WHERE lorebook_id=?
        """,
        (book_id,),
        one=True,
    )["c"]

    assert count == 1

def test_restore_lorebook_deletes_entries_missing_from_snapshot(
    temp_db,
    monkeypatch,
):
    import memory

    monkeypatch.setattr(
        memory,
        "embed_texts",
        lambda values: [[0.0] * 256 for _ in values],
    )

    book_id = temp_db.qi(
        "INSERT INTO lorebooks(name) VALUES(?)",
        ("Test",),
    )

    add_lore(
        book_id,
        "keep",
        "Keep this entry.",
        entry_uid="entry_keep",
    )
    add_lore(
        book_id,
        "remove",
        "Remove this entry.",
        entry_uid="entry_remove",
    )

    restore_lorebook(book_id, [{
        "entry_uid": "entry_keep",
        "keys": "keep",
        "content": "Keep this entry.",
        "category": "other",
    }])

    rows = temp_db.q(
        """
        SELECT entry_uid
        FROM lore_entries
        WHERE lorebook_id=?
        ORDER BY entry_uid
        """,
        (book_id,),
    )

    assert [row["entry_uid"] for row in rows] == ["entry_keep"]