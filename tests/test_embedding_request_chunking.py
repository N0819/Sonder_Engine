"""A batch refused for being too large must be split, not hashed (UNBUILT 1.75).

`_embed_with_retry` sends whatever list it is handed and, on any exception,
replaces the WHOLE batch with crc32 hashes stamped `cheap:crc32:256` -- which
measure 0% paraphrase recall (MEMORY.md section 4). The embeddings provider
caps a request at 120,000 tokens and that ceiling appeared nowhere in this
codebase, so the size of a memory write decided whether its vectors were real.

Turn commit never came close: a beat mints a handful of memories.
`import_character_memories` passes whatever a host's export file holds, and the
three largest banks in the live corpus (657/657/654 rows) each estimate ~127k
request tokens on their own. So the one path a host uses to give a character a
past was the path that silently produced a keyword-only bank behind a
`{"ok": true}`.

The asymmetry in the last two tests is the design, not an oversight: a turn
whose provider is briefly down keeps its memory and has it rebuilt later,
because losing the beat is worse than storing a rebuildable hash. An import is
one host action, retryable in full, and is refused instead.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from mind import memory_write
from mind.memory_snapshot import import_character_memories
from tests.helpers import patch_seam


class _Batch:
    """Stands in for llm.providers.EmbeddingBatch."""

    def __init__(self, vectors, model_key="stub:real", dimensions=8,
                 fallback=False, error=""):
        self.vectors = vectors
        self.model_key = model_key
        self.dimensions = dimensions
        self.fallback = fallback
        self.error = error


def _recording_embedder(calls, *, fallback_on=()):
    """Returns one deterministic vector per text and records request shapes.

    The vector encodes its text's length, so a reordering or a dropped chunk
    is visible in the assertion rather than merely probable.
    """
    def fake(texts, **kw):
        idx = len(calls)
        calls.append(list(texts))
        vecs = [np.full(8, float(len(t)), dtype=np.float32) for t in texts]
        if idx in fallback_on:
            return _Batch(vecs, model_key="cheap:crc32:256", dimensions=256,
                          fallback=True, error="413 payload too large")
        return _Batch(vecs)
    return fake


class TestChunking:
    def test_a_small_batch_is_still_one_request(self, monkeypatch):
        calls = []
        patch_seam(monkeypatch, "mind.memory_write", "embed_texts_meta",
                   _recording_embedder(calls))
        memory_write._embed_in_request_sized_chunks(["short", "texts"])
        assert len(calls) == 1, "small batches must not pay for chunking"

    def test_an_oversized_batch_is_split(self, monkeypatch):
        calls = []
        patch_seam(monkeypatch, "mind.memory_write", "embed_texts_meta",
                   _recording_embedder(calls))
        # Four texts, each ~half the budget in tokens.
        big = "x" * (memory_write._EMBED_REQUEST_TOKENS
                     * memory_write._CHARS_PER_TOKEN // 2)
        memory_write._embed_in_request_sized_chunks([big] * 4)
        assert len(calls) > 1, "the whole point is that this is not one request"
        for chunk in calls:
            est = sum(len(t) for t in chunk) // memory_write._CHARS_PER_TOKEN
            # One text alone may exceed the budget; two must never.
            assert len(chunk) == 1 or est <= memory_write._EMBED_REQUEST_TOKENS

    def test_vector_order_survives_the_split(self, monkeypatch):
        """add_memories_batch indexes by position -- row i reads 2i and 2i+1 --
        so a chunk boundary that reorders anything mislabels every memory after
        it, silently and permanently."""
        calls = []
        patch_seam(monkeypatch, "mind.memory_write", "embed_texts_meta",
                   _recording_embedder(calls))
        unit = memory_write._EMBED_REQUEST_TOKENS * memory_write._CHARS_PER_TOKEN
        texts = ["y" * (unit // 3 + n) for n in range(9)]
        got = memory_write._embed_in_request_sized_chunks(texts)
        assert len(calls) > 1
        assert [int(v[0]) for v in got.vectors] == [len(t) for t in texts]

    def test_one_chunk_falling_back_taints_the_whole_batch(self, monkeypatch):
        """A half-real, half-hash batch is not partially trustworthy: the
        caller's refusal has to fire on it."""
        calls = []
        patch_seam(monkeypatch, "mind.memory_write", "embed_texts_meta",
                   _recording_embedder(calls, fallback_on=(1,)))
        unit = memory_write._EMBED_REQUEST_TOKENS * memory_write._CHARS_PER_TOKEN
        got = memory_write._embed_in_request_sized_chunks(["z" * unit] * 3)
        assert len(calls) >= 2
        assert got.fallback is True
        assert got.error


def _chat_and_char(db):
    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("T", "", time.time()))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    return chat_id, char_id


class TestImportRefusesAHashedBank:
    def test_an_install_with_no_provider_imports_normally(self, temp_db,
                                                          monkeypatch):
        """The discriminator, pinned first because getting it wrong broke six
        existing tests: running with no embeddings provider is SUPPORTED, and
        there the crc32 hash is what this install embeds onto rather than a
        failure. `embedding_model_key` returns the hash key in that case, which
        is the same rule `rebuild_embeddings` states as `want_fallback`."""
        chat_id, char_id = _chat_and_char(temp_db)
        calls = []
        patch_seam(monkeypatch, "mind.memory_write", "embed_texts_meta",
                   _recording_embedder(calls, fallback_on=(0,)))
        patch_seam(monkeypatch, "mind.memory_snapshot", "embedding_model_key",
                   lambda: "cheap:crc32:256")
        assert import_character_memories(
            chat_id, char_id, [{"content": "She crossed the yard."}]) == 1

    def test_import_raises_rather_than_storing_hash_vectors(
            self, temp_db, monkeypatch):
        chat_id, char_id = _chat_and_char(temp_db)
        calls = []
        patch_seam(monkeypatch, "mind.memory_write", "embed_texts_meta",
                   _recording_embedder(calls, fallback_on=(0,)))
        patch_seam(monkeypatch, "mind.memory_snapshot", "embedding_model_key",
                   lambda: "openrouter:3:perplexity/pplx-embed-v1-4b")
        with pytest.raises(ValueError, match="crc32"):
            import_character_memories(
                chat_id, char_id,
                [{"content": "She crossed the yard."},
                 {"content": "The gate was open."}])
        assert not temp_db.q(
            "SELECT 1 FROM memories WHERE chat_id=? AND char_id=?",
            (chat_id, char_id)), "a refused import must leave nothing behind"

    def test_a_real_import_still_lands(self, temp_db, monkeypatch):
        chat_id, char_id = _chat_and_char(temp_db)
        calls = []
        patch_seam(monkeypatch, "mind.memory_write", "embed_texts_meta",
                   _recording_embedder(calls))
        n = import_character_memories(
            chat_id, char_id,
            [{"content": "She crossed the yard."},
             {"content": "The gate was open."}])
        assert n == 2
        rows = temp_db.q("SELECT turn_idx FROM memories WHERE chat_id=? AND char_id=?",
                         (chat_id, char_id))
        assert len(rows) == 2
        # The turn-less tier this path already writes into -- see UNBUILT 2.20.
        assert all(r["turn_idx"] is None for r in rows)

    def test_the_turn_path_deliberately_keeps_a_fallback(self, temp_db,
                                                         monkeypatch):
        """The asymmetry, pinned. A beat that cannot embed must not lose its
        memory: the row is stored and `rebuild_embeddings` can repair it. Only
        the bulk import refuses."""
        chat_id, char_id = _chat_and_char(temp_db)
        calls = []
        patch_seam(monkeypatch, "mind.memory_write", "embed_texts_meta",
                   _recording_embedder(calls, fallback_on=(0,)))
        ids = memory_write.add_memories_batch([{
            "chat_id": chat_id, "char_id": char_id, "turn_id": None,
            "kind": "episodic", "provenance": "witnessed", "salience": 0.5,
            "content": "The bell rang twice.", "turn_idx": 3,
        }])
        assert len(ids) == 1
