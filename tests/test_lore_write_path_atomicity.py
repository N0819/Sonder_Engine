"""The lore write paths that deleted or inserted row-by-row, outside any
transaction, with an embedding round-trip inside the loop.

`reinterpret_lorebook` deleted every unlocked row and then re-inserted the
rewritten set one entry at a time. Reproduced before the fix: three entries
in, a failure on the third insert left two rows behind and the third gone
permanently, while the route returned a 502. Worse, even a fully successful
run read each source row as a bare `(keys, content)` pair, so `title`,
`importance`, `aliases` and every knowledge field were silently reset on
every reinterpretation (measured: title 'T0' -> None, importance 0.9 -> 0.5,
aliases ['a0'] -> []) -- and the knowledge fields are not cosmetic, they
decide who can retrieve the entry.

`generate_lore_entries` had the same shape: a bare insert loop, no
transaction, an embedding call per entry. A failure on entry 3 of 4 left two
committed while the route reported failure.

Pinned here: both paths prepare their embeddings BEFORE the write
transaction, commit atomically (a failure anywhere loses nothing), and a
reinterpretation carries the source row's full metadata into the new row.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import q
from story import importers


def _book(db, name="Book"):
    return db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) VALUES(?,?,?,?)",
        (name, None, "general", ""),
    )


def _full_entry(db, book_id, i):
    return db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content,canon_locked,"
        "title,importance,aliases,knowledge_tag,knowledge_range,"
        "knowledge_locations,scope,relations,source_notes) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (book_id, f"key{i}", f"Content number {i} about the delta.", 0,
         f"T{i}", 0.9, json.dumps([f"a{i}"]), "secret", "local",
         json.dumps(["delta"]), json.dumps({"w": i}), json.dumps({}),
         f"note {i}"),
    )


def _fail_on_nth(monkeypatch, name, n, wrapped):
    calls = {"n": 0}

    def wrapper(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == n:
            raise RuntimeError("simulated mid-write failure")
        return wrapped(*args, **kwargs)

    monkeypatch.setattr(importers, name, wrapper)
    return calls


class TestReinterpretLorebook:
    def test_a_failed_insert_loses_nothing(self, temp_db, monkeypatch):
        lid = _book(temp_db)
        for i in range(3):
            _full_entry(temp_db, lid, i)

        monkeypatch.setattr(
            importers, "_reinterpret_entries",
            lambda entries: [
                {"keys": k, "content": c + " (rewritten)",
                 "category": "other", "locked": 0}
                for k, c, _ in entries
            ],
        )
        _fail_on_nth(monkeypatch, "add_lore", 2, importers.add_lore)

        with pytest.raises(RuntimeError):
            importers.reinterpret_lorebook(lid)

        rows = q("SELECT content FROM lore_entries WHERE lorebook_id=? "
                 "ORDER BY id", (lid,))
        assert [r["content"] for r in rows] == [
            f"Content number {i} about the delta." for i in range(3)
        ]

    def test_metadata_survives_a_reinterpretation(self, temp_db, monkeypatch):
        lid = _book(temp_db)
        _full_entry(temp_db, lid, 0)

        # The model rewrites the tail of the content; the opening survives,
        # which is exactly what _structure_key was built to match on.
        monkeypatch.setattr(
            importers, "_reinterpret_entries",
            lambda entries: [
                {"keys": k, "content": c + " Rewritten for clarity.",
                 "category": "location", "locked": 0}
                for k, c, _ in entries
            ],
        )

        assert importers.reinterpret_lorebook(lid) == 1

        row = q("SELECT * FROM lore_entries WHERE lorebook_id=?", (lid,),
                one=True)
        assert row["title"] == "T0"
        assert row["importance"] == pytest.approx(0.9)
        assert json.loads(row["aliases"]) == ["a0"]
        assert row["knowledge_tag"] == "secret"
        assert row["knowledge_range"] == "local"
        assert json.loads(row["knowledge_locations"]) == ["delta"]
        assert row["source_notes"] == "note 0"

    def test_a_failed_embedding_deletes_nothing(self, temp_db, monkeypatch):
        lid = _book(temp_db)
        for i in range(2):
            _full_entry(temp_db, lid, i)

        monkeypatch.setattr(
            importers, "_reinterpret_entries",
            lambda entries: [
                {"keys": k, "content": c, "category": "other", "locked": 0}
                for k, c, _ in entries
            ],
        )

        def boom(*args, **kwargs):
            raise RuntimeError("provider down")

        monkeypatch.setattr(importers, "embed_texts_meta", boom)

        with pytest.raises(RuntimeError):
            importers.reinterpret_lorebook(lid)

        assert q("SELECT COUNT(*) AS c FROM lore_entries WHERE lorebook_id=?",
                 (lid,), one=True)["c"] == 2

    def test_locked_entries_are_never_touched(self, temp_db, monkeypatch):
        lid = _book(temp_db)
        temp_db.qi(
            "INSERT INTO lore_entries(lorebook_id,keys,content,canon_locked) "
            "VALUES(?,?,?,?)", (lid, "locked", "Canon text.", 1),
        )
        _full_entry(temp_db, lid, 0)

        monkeypatch.setattr(
            importers, "_reinterpret_entries",
            lambda entries: [
                {"keys": k, "content": "New " + c, "category": "other",
                 "locked": 0}
                for k, c, _ in entries
            ],
        )

        importers.reinterpret_lorebook(lid)
        locked = q("SELECT content FROM lore_entries WHERE canon_locked=1",
                   one=True)
        assert locked["content"] == "Canon text."


class TestGenerateLoreEntries:
    RESPONSE = {
        "entry_ops": [
            {"op": "create", "keys": f"k{i}", "content": f"Entry {i}.",
             "category": "other"}
            for i in range(4)
        ]
    }

    def test_a_partial_failure_commits_nothing(self, temp_db, monkeypatch):
        lid = _book(temp_db)
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda *a, **k: json.dumps(self.RESPONSE),
        )
        _fail_on_nth(monkeypatch, "add_lore", 3, importers.add_lore)

        with pytest.raises(RuntimeError):
            importers.generate_lore_entries(lid, "some lore")

        assert q("SELECT COUNT(*) AS c FROM lore_entries WHERE lorebook_id=?",
                 (lid,), one=True)["c"] == 0

    def test_a_clean_run_still_writes_everything(self, temp_db, monkeypatch):
        lid = _book(temp_db)
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda *a, **k: json.dumps(self.RESPONSE),
        )
        ids = importers.generate_lore_entries(lid, "some lore")
        assert len(ids) == 4
        assert q("SELECT COUNT(*) AS c FROM lore_entries WHERE lorebook_id=?",
                 (lid,), one=True)["c"] == 4
