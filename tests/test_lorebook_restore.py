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


def test_dump_and_restore_carry_the_embedding_stamp(temp_db, monkeypatch):
    """A restored vector keeps its provenance, or no reader can trust it.

    `dump_lorebook` carried the vector BYTES and not the two columns that say
    what produced them, so `add_lore`/`update_lore` had nothing to record and
    deliberately stored NULL -- correctly, since inventing a model name would
    be a guess written down as a fact. The result is that a restore, an import
    or a branch converts every entry in the bank into one judged on width
    alone, forever.
    """
    import memory

    monkeypatch.setattr(
        memory, "embed_texts", lambda values: [[0.25] * 256 for _ in values])

    source = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type,summary,resource_uid) "
        "VALUES(?,?,?,?)", ("Source", "general", "", "book_stamp_src"))
    add_lore(source, "door", "A wooden door.", entry_uid="entry_stamped")
    temp_db.qi(
        "UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
        "WHERE entry_uid=?", ("test:embedder:256", 256, "entry_stamped"))

    dumped = memory.dump_lorebook(source)
    assert dumped[0]["embedding_model"] == "test:embedder:256"
    assert dumped[0]["embedding_dim"] == 256

    target = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type,summary,resource_uid) "
        "VALUES(?,?,?,?)", ("Target", "general", "", "book_stamp_dst"))
    memory.restore_lorebook(target, dumped)

    restored = temp_db.q(
        "SELECT embedding,embedding_model,embedding_dim FROM lore_entries "
        "WHERE lorebook_id=?", (target,), one=True)
    assert restored["embedding_model"] == "test:embedder:256"
    assert restored["embedding_dim"] == 256

    # ...and a restore over an EXISTING row goes through update_lore.
    memory.restore_lorebook(target, dumped)
    again = temp_db.q(
        "SELECT embedding_model,embedding_dim FROM lore_entries "
        "WHERE lorebook_id=?", (target,), one=True)
    assert again["embedding_model"] == "test:embedder:256"
    assert again["embedding_dim"] == 256


def test_a_legacy_dump_with_no_stamp_still_restores_unstamped(
        temp_db, monkeypatch):
    """The stamp is a fact about the bytes, never a default: an older snapshot
    carries a vector and no provenance, and guessing one would record a guess
    as a measurement."""
    import memory

    monkeypatch.setattr(
        memory, "embed_texts", lambda values: [[0.25] * 256 for _ in values])

    book = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type,summary,resource_uid) "
        "VALUES(?,?,?,?)", ("Legacy", "general", "", "book_legacy_stamp"))
    memory.restore_lorebook(book, [{
        "entry_uid": "entry_legacy",
        "keys": "door",
        "content": "A wooden door.",
        "category": "other",
        "embedding": memory._blob_to_b64(memory._blob([0.5] * 256)),
    }])

    row = temp_db.q(
        "SELECT embedding_model,embedding_dim FROM lore_entries "
        "WHERE lorebook_id=?", (book,), one=True)
    assert row["embedding_model"] is None
    assert row["embedding_dim"] == 256


def test_cloning_a_book_for_a_chat_keeps_the_stamp(temp_db, monkeypatch):
    """Same defect, same file, a different verbatim reuse: the clone copies
    the source row's bytes and used to leave the two provenance columns
    behind."""
    import memory

    monkeypatch.setattr(
        memory, "embed_texts", lambda values: [[0.25] * 256 for _ in values])

    root = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type,summary,resource_uid) "
        "VALUES(?,?,?,?)", ("Root", "general", "", "book_clone_src"))
    add_lore(root, "door", "A wooden door.", entry_uid="entry_cloned")
    temp_db.qi(
        "UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
        "WHERE entry_uid=?", ("test:embedder:256", 256, "entry_cloned"))

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("C", "", 0.0))
    mapping = memory.duplicate_lorebook_tree_for_chat(root, chat_id)

    cloned = temp_db.q(
        "SELECT embedding_model,embedding_dim FROM lore_entries "
        "WHERE lorebook_id=?", (mapping[root],), one=True)
    assert cloned["embedding_model"] == "test:embedder:256"
    assert cloned["embedding_dim"] == 256
