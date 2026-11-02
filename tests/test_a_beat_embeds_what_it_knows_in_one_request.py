"""A beat's memory context embeds every text it already knows in one request.

`build_character_memory_context` embedded the beat's query and its aspects in
one batch, then made a request of its own for the mind's ponder question, one
for a question it was asked, and one for an unbidden subject -- all three
known before the first request went out (review 2026-11-01, mind_memory E2:
up to seven serial round trips a character a beat, against a provider bucket
of about three requests whose 429s are what strand rows on the crc32 hash).
The vectors are the same either way; only the round trips differ.
"""

from __future__ import annotations

import time

import numpy as np

from llm.providers import EmbeddingBatch
from mind import memory
from tests.helpers import patch_provider_seam

DIM = 16


def _vector(text):
    v = np.zeros(DIM, dtype=np.float32)
    for word in str(text or "").lower().split():
        v[sum(map(ord, word)) % DIM] += 1.0
    return v / (float(np.linalg.norm(v)) or 1.0)


def test_ponder_asked_and_resurfaced_ride_with_the_beat(temp_db, monkeypatch):
    requests = []

    def embed(texts, **_kw):
        requests.append(list(texts))
        return EmbeddingBatch(vectors=[_vector(t) for t in texts],
                              model_key="test:words", dimensions=DIM)
    patch_provider_seam(monkeypatch, "embed_texts_meta", embed)
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))
    mara = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                      ("Mara", "{}", "{}", time.time()))
    for t in range(1, 25):
        memory.add_memory(chat, mara, None, "episodic", "witnessed", 0.6,
                          f"At the ferry on day {t} the rope frayed.", turn_idx=t,
                          event_key=f"ferry:{t}")
    requests.clear()
    ctx = memory.build_character_memory_context(
        chat, mara, 30, "The ferry rocks at the landing.", {"goal": "cross the river"},
        ponder_query="when did the rope first fray?", asked_query="who cut the rope?",
        resurfaced_subject="the frayed rope")
    assert len(requests) == 1, requests
    asked = requests[0]
    for text in ("when did the rope first fray?", "who cut the rope?", "the frayed rope"):
        assert text in asked
    # Each lane still ran on its own question.
    assert ctx.get("deliberate_recall") is not None
