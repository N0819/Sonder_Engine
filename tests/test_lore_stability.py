import json
from memory import add_lore, restore_lorebook
from db import q

def test_restore_lorebook_preserves_entry_id(temp_db, monkeypatch):
    import memory

    # Mock embeddings to avoid needing an API key
    monkeypatch.setattr(
        memory,
        "embed_texts",
        lambda values: [[0.0] * 256 for _ in values]
    )

    book_id = temp_db.qi(
        "INSERT INTO lorebooks(name, book_type, summary, resource_uid) VALUES(?,?,?,?)",
        ("Test", "general", "", "book_test")
    )

    entry_id = add_lore(
        book_id,
        "door",
        "A wooden door.",
        entry_uid="entry_test"
    )

    # Restore with updated content for the same UID
    restore_lorebook(book_id, [{
        "entry_uid": "entry_test",
        "keys": "door",
        "content": "A wooden door with a brass handle.",
        "category": "other",
    }])

    row = temp_db.q(
        "SELECT * FROM lore_entries WHERE entry_uid='entry_test'",
        one=True
    )

    assert row is not None
    assert row["id"] == entry_id  # ID should be preserved, not recreated
    assert "brass handle" in row["content"]

    # Ensure no duplicates were created
    count = temp_db.q(
        "SELECT COUNT(*) as c FROM lore_entries WHERE lorebook_id=?",
        (book_id,),
        one=True
    )["c"]
    assert count == 1