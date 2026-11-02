"""Lore search never ranks on a crc32 hash query, as memory search never does.

When the embedding call falls back, the query vector is a crc32 sketch
(`cheap:crc32:256`, `fallback=True`). Every memory ranking refuses it --
`search_memories`, `contrast_memory`, `recall_confidence`, `memory_net` -- on
CRC32_CONTROL §8's measurement: ranking on the hash scored 289/470 against 338
with no vector at all. `search_lore` compared on model key and width only, and
a row stamped with the same hash key is "compatible", so its 0.65 term was
hash cosine (review 2026-11-01, mind_memory F10). That is every install with
no embeddings provider, and every lore row written during a rate-limit window
on one that has one -- the outage that strands those rows is the outage that
makes the query fall back, so the two arrive together. Each such call also
logged "Re-embed to restore them" for rows that were not the problem.
"""

from __future__ import annotations

import time

import numpy as np

from llm.providers import EmbeddingBatch
from mind import memory
from mind import memory_lore_entries


def test_a_hash_query_ranks_by_keyword_alone(temp_db, monkeypatch):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))
    book = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type,summary) "
                      "VALUES(?,?,?,?)", ("B", chat, "general", ""))
    granary = memory.add_lore(book, "granary", "The granary is kept by the miller.",
                              knowledge_tag="common", title="Granary")
    chapel = memory.add_lore(book, "chapel", "The chapel bell rings for the dead at dusk.",
                             knowledge_tag="common", title="Chapel")
    row = temp_db.q("SELECT embedding, embedding_model, embedding_dim FROM lore_entries "
                    "WHERE id=?", (chapel,), one=True)
    chapel_vec = np.frombuffer(row["embedding"], dtype=np.float32)

    def hashed(texts, **_kw):
        # The query "falls back" to a vector that IS the chapel row's: on the
        # hash it is a perfect match, though the words share nothing.
        return EmbeddingBatch(vectors=[chapel_vec.copy() for _ in texts],
                              model_key=row["embedding_model"],
                              dimensions=int(row["embedding_dim"] or len(chapel_vec)),
                              fallback=True, error="rate limited")

    monkeypatch.setattr(memory_lore_entries, "embed_texts_meta", hashed)
    ranked = [r["id"] for r in memory.search_lore([book], "Who keeps the granary?", k=2)]
    assert ranked[0] == granary, "the keyword match leads; the hash adds nothing"


def test_a_real_query_still_ranks_by_meaning(temp_db, monkeypatch):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))
    book = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type,summary) "
                      "VALUES(?,?,?,?)", ("B", chat, "general", ""))
    near, far = np.zeros(8, dtype=np.float32), np.zeros(8, dtype=np.float32)
    near[0], far[1] = 1.0, 1.0
    a = memory.add_lore(book, "orchard", "Apples ripen late here.", knowledge_tag="common",
                        embedding=near, embedding_model="test:model", embedding_dim=8)
    memory.add_lore(book, "quarry", "Stone is cut by the river.", knowledge_tag="common",
                    embedding=far, embedding_model="test:model", embedding_dim=8)
    monkeypatch.setattr(memory_lore_entries, "embed_texts_meta",
                        lambda texts, **_kw: EmbeddingBatch(
                            vectors=[near.copy() for _ in texts], model_key="test:model",
                            dimensions=8, fallback=False))
    assert memory.search_lore([book], "when is the harvest?", k=1)[0]["id"] == a
