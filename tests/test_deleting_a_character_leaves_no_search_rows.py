"""Deleting a character takes its rows out of the memory search index too.

`memories.char_id` cascades, but `memory_retrieval_fts` is a plain FTS5 table
with no foreign key and no trigger, so the cascade that removed a character's
memories left every one of their index rows behind. Measured on the owner's
database (audit 2026-11-01, mind_memory F8): 18,882 index rows against 17,463
memories, all 1,419 orphans belonging to characters that no longer exist in
chats that still do. Every lexical MATCH paid for them, and a later character
handed the same id (SQLite gives the highest one out again) inherited their
keyword hits. `persist/chat_delete.py` already sweeps the index for a chat.
"""
from __future__ import annotations

import json
import time


def test_a_deleted_characters_memories_leave_the_index(temp_db, monkeypatch):
    from llm.providers import EmbeddingBatch
    from mind.memory import add_memory
    from story.character_schema import default_character_data
    from tests.helpers import patch_provider_seam
    from web import app

    def fake_meta(texts):
        return EmbeddingBatch(vectors=[[1.0] * 8 for _ in texts],
                              model_key="test:1:fake", dimensions=8)

    patch_provider_seam(monkeypatch, "embed_texts_meta", fake_meta)
    patch_provider_seam(monkeypatch, "embed_texts", lambda texts: fake_meta(texts).vectors)

    db = temp_db
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Story", "", time.time()))
    gone = db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                 ("Alice", json.dumps(default_character_data("Alice")), "{}", time.time()))
    kept = db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                 ("Bram", json.dumps(default_character_data("Bram")), "{}", time.time()))
    for ch in (gone, kept):
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
              (cid, ch, "active", "{}"))
        add_memory(cid, ch, None, "episodic", "witnessed", 0.7,
                   "The cellar door stood open.", turn_idx=1)

    def index_rows(ch):
        return db.q("SELECT COUNT(*) AS n FROM memory_retrieval_fts WHERE char_id=?",
                    (str(ch),), one=True)["n"]

    assert index_rows(gone) == 1 and index_rows(kept) == 1
    assert app.char_del(gone) == {"ok": True}
    assert db.q("SELECT COUNT(*) AS n FROM memories WHERE char_id=?", (gone,), one=True)["n"] == 0
    assert index_rows(gone) == 0
    assert index_rows(kept) == 1, "another character's index rows are untouched"
