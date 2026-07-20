"""Checkpoint audit findings 2 and 4: memory/lore snapshot dumps must
carry their stored embedding vectors, and restore/clone must reuse them
byte-identically instead of re-embedding -- re-embedding on every reroll
is expensive, and any provider hiccup silently downgrades every vector
to the crc32 fallback ('cheap:crc32:256'), which then scores 0.0
forever."""

import json
import time

import numpy as np

import memory
from character_schema import default_character_data
from memory import (
    add_lore, add_memory, dump_chat_memories, dump_lorebook,
    dump_memory_summaries, duplicate_lorebook_tree_for_chat,
    restore_chat_memories, restore_lorebook, restore_memory_summaries,
    save_memory_summary,
)
from providers import EmbeddingBatch

REAL_MODEL = "openai:1:text-embedding-real"
DIM = 8


def _install_stub(monkeypatch, counter, model_key=REAL_MODEL, fill=1.5):
    def fake_meta(texts):
        counter["calls"] += 1
        vecs = [[fill + (i % 3)] * DIM for i, _ in enumerate(texts)]
        return EmbeddingBatch(vectors=vecs, model_key=model_key, dimensions=DIM)

    def fake_plain(texts):
        return fake_meta(texts).vectors

    monkeypatch.setattr(memory, "embed_texts_meta", fake_meta)
    monkeypatch.setattr(memory, "embed_texts", fake_plain)


def _chat_and_character(db):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Alice", json.dumps(default_character_data("Alice")), "{}", time.time(), "char_alice"),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    return chat_id, char_id


def test_memory_restore_reuses_snapshotted_embeddings_verbatim(temp_db, monkeypatch):
    counter = {"calls": 0}
    _install_stub(monkeypatch, counter)
    chat_id, char_id = _chat_and_character(temp_db)

    add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.7,
               "Alice saw the cellar door standing open.", turn_idx=1)
    original = temp_db.q(
        "SELECT embedding,cue_embedding,embedding_model,embedding_dim "
        "FROM memories WHERE chat_id=?", (chat_id,), one=True,
    )
    assert original["embedding_model"] == REAL_MODEL

    dump = dump_chat_memories(chat_id)
    assert isinstance(dump[0]["embedding"], str) and dump[0]["embedding"]
    assert isinstance(dump[0]["cue_embedding"], str) and dump[0]["cue_embedding"]
    assert dump[0]["embedding_model"] == REAL_MODEL
    assert dump[0]["embedding_dim"] == DIM

    # Any embedding call during restore now behaves like a provider
    # hiccup: it would return crc32-fallback vectors under a different
    # model key. The restore must not make that call at all.
    downgraded = {"calls": 0}
    _install_stub(monkeypatch, downgraded, model_key="cheap:crc32:256", fill=9.0)

    restore_chat_memories(chat_id, dump)

    assert downgraded["calls"] == 0, "restore must not re-embed a dump that carries vectors"
    restored = temp_db.q(
        "SELECT id,embedding,cue_embedding,embedding_model,embedding_dim "
        "FROM memories WHERE chat_id=?", (chat_id,), one=True,
    )
    assert bytes(restored["embedding"]) == bytes(original["embedding"])
    assert bytes(restored["cue_embedding"]) == bytes(original["cue_embedding"])
    assert restored["embedding_model"] == REAL_MODEL
    assert restored["embedding_dim"] == DIM
    # The FTS index must be maintained exactly as the normal add path does.
    fts = temp_db.q(
        "SELECT * FROM memory_retrieval_fts WHERE memory_id=?",
        (str(restored["id"]),),
    )
    assert len(fts) == 1


def test_memory_restore_legacy_dump_still_embeds_and_keeps_flags(temp_db, monkeypatch):
    counter = {"calls": 0}
    _install_stub(monkeypatch, counter)
    chat_id, char_id = _chat_and_character(temp_db)

    add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.7,
               "An old memory from before dumps carried vectors.", turn_idx=1)
    dump = dump_chat_memories(chat_id)
    dump[0]["archived"] = True
    for key in ("embedding", "cue_embedding", "embedding_model", "embedding_dim"):
        dump[0].pop(key, None)

    counter["calls"] = 0
    restore_chat_memories(chat_id, dump)

    assert counter["calls"] == 1, "legacy entries are embedded in one batch call"
    row = temp_db.q("SELECT * FROM memories WHERE chat_id=?", (chat_id,), one=True)
    assert row is not None
    assert row["archived"] == 1
    assert row["embedding_model"] == REAL_MODEL
    assert len(temp_db.q(
        "SELECT * FROM memory_retrieval_fts WHERE memory_id=?", (str(row["id"]),)
    )) == 1


def test_memory_summary_restore_reuses_snapshotted_embedding(temp_db, monkeypatch):
    counter = {"calls": 0}
    _install_stub(monkeypatch, counter)
    chat_id, char_id = _chat_and_character(temp_db)

    save_memory_summary(chat_id, char_id, "Alice explored the manor.",
                        key_phrases=["manor"], unresolved_threads=["the cellar"])
    original = temp_db.q(
        "SELECT embedding,embedding_model FROM memory_summaries WHERE chat_id=?",
        (chat_id,), one=True,
    )
    dump = dump_memory_summaries(chat_id)
    assert isinstance(dump[0]["embedding"], str) and dump[0]["embedding"]

    downgraded = {"calls": 0}
    _install_stub(monkeypatch, downgraded, model_key="cheap:crc32:256", fill=9.0)
    restore_memory_summaries(chat_id, dump)

    assert downgraded["calls"] == 0
    restored = temp_db.q(
        "SELECT embedding,embedding_model FROM memory_summaries WHERE chat_id=?",
        (chat_id,), one=True,
    )
    assert bytes(restored["embedding"]) == bytes(original["embedding"])
    assert restored["embedding_model"] == REAL_MODEL


def test_lorebook_restore_reuses_snapshotted_embeddings(temp_db, monkeypatch):
    counter = {"calls": 0}
    _install_stub(monkeypatch, counter)

    book_id = temp_db.qi("INSERT INTO lorebooks(name) VALUES(?)", ("Canon",))
    add_lore(book_id, "cellar, door", "The cellar door is always locked at night.")
    original = temp_db.q(
        "SELECT embedding FROM lore_entries WHERE lorebook_id=?", (book_id,), one=True,
    )

    dump = dump_lorebook(book_id)
    assert isinstance(dump[0]["embedding"], str) and dump[0]["embedding"]

    # Update path: restoring the same book must not embed.
    counter["calls"] = 0
    restore_lorebook(book_id, dump)
    assert counter["calls"] == 0, "restore of unchanged entries must not re-embed"
    after = temp_db.q(
        "SELECT embedding FROM lore_entries WHERE lorebook_id=?", (book_id,), one=True,
    )
    assert bytes(after["embedding"]) == bytes(original["embedding"])

    # Insert path: restoring into a fresh book must reuse the vector too.
    other_id = temp_db.qi("INSERT INTO lorebooks(name) VALUES(?)", ("Canon copy",))
    counter["calls"] = 0
    restore_lorebook(other_id, dump)
    assert counter["calls"] == 0
    added = temp_db.q(
        "SELECT embedding FROM lore_entries WHERE lorebook_id=?", (other_id,), one=True,
    )
    assert bytes(added["embedding"]) == bytes(original["embedding"])

    # Legacy dumps without vectors still embed (single batch).
    legacy = [dict(e) for e in dump]
    for e in legacy:
        e.pop("embedding", None)
    counter["calls"] = 0
    restore_lorebook(book_id, legacy)
    assert counter["calls"] == 1


def test_duplicate_lorebook_tree_reuses_source_embeddings(temp_db, monkeypatch):
    counter = {"calls": 0}
    _install_stub(monkeypatch, counter)

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    root_id = temp_db.qi("INSERT INTO lorebooks(name) VALUES(?)", ("World",))
    add_lore(root_id, "harbor", "The harbor floods every spring tide.")
    source = temp_db.q(
        "SELECT embedding FROM lore_entries WHERE lorebook_id=?", (root_id,), one=True,
    )

    counter["calls"] = 0
    mapping = duplicate_lorebook_tree_for_chat(root_id, chat_id)
    assert counter["calls"] == 0, "cloning identical entries must not re-embed"

    clone_book = mapping[root_id]
    clone = temp_db.q(
        "SELECT embedding FROM lore_entries WHERE lorebook_id=?", (clone_book,), one=True,
    )
    assert bytes(clone["embedding"]) == bytes(source["embedding"])
