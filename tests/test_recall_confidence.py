"""The recall abstention floor (recall_confidence).

A deterministic, per-query-calibrated emptiness signal read from the score
DISTRIBUTION against the bank's own baseline (NQC/WIG shape) -- never an
absolute cosine floor, which drops everything or nothing depending on the
embedding model. Fails OPEN: too small a bank, low model coverage, or a
degenerate distribution all mean "no signal", never "empty".
"""

import hashlib
import json
import time

import numpy as np
import pytest

from mind import memory
from llm import providers
from story.character_schema import default_character_data
from tests.helpers import patch_provider_seam

_DIM = 16


def _unit(vec):
    return vec / np.linalg.norm(vec)


def _noise(text):
    """Deterministic pseudo-random unit vector from the text (hashlib, not
    hash(): the builtin is salted per process)."""
    digest = hashlib.sha256(str(text).encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    return _unit(rng.standard_normal(_DIM).astype(np.float32))


def _vector_for(text):
    text = str(text)
    if "SPECIAL" in text:
        base = np.zeros(_DIM, dtype=np.float32)
        base[1] = 1.0
        return _unit(base + 0.05 * _noise(text))
    if "QUERY-DIFFUSE" in text:
        base = np.zeros(_DIM, dtype=np.float32)
        base[2] = 1.0
        return _unit(base)
    base = np.zeros(_DIM, dtype=np.float32)
    base[0] = 1.0
    return _unit(base + 0.6 * _noise(text))


def _fake_embedder(model_key="test:model:x"):
    def fake(texts):
        return providers.EmbeddingBatch(
            vectors=[_vector_for(t) for t in texts], model_key=model_key,
            dimensions=_DIM, fallback=False)
    return fake


@pytest.fixture
def bank(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Floor", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}", time.time(),
         "char_mara"))
    return {"chat": chat_id, "char": char_id}


def _seed(bank, n, prefix="filler"):
    for i in range(n):
        memory.add_memory(bank["chat"], bank["char"], None, "episodic",
                          "witnessed", 0.6, f"{prefix} event number {i}",
                          turn_idx=i)


def _confidence(bank, query, **kw):
    return memory.recall_confidence(
        bank["chat"], bank["char"], query, current_turn_idx=10**6,
        viewer_frame_id=None, **kw)


def test_a_small_bank_gives_no_signal(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    _seed(bank, 10)

    out = _confidence(bank, "anything")

    assert out["available"] is False
    assert out["abstain"] is False


def test_low_model_coverage_gives_no_signal(bank, monkeypatch):
    # A bank mid-rebuild must never read as empty: stranded vectors are an
    # infrastructure fact, not an absence of memory.
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    _seed(bank, 60)
    from core.db import qi
    qi("UPDATE memories SET embedding_model='ancient:model' "
       "WHERE id IN (SELECT id FROM memories LIMIT 40)")

    out = _confidence(bank, "anything")

    assert out["available"] is False


def test_a_strong_match_clears_the_floor(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    _seed(bank, 60)
    _seed(bank, 16, prefix="SPECIAL")

    out = _confidence(bank, "SPECIAL")

    assert out["available"] is True
    assert out["lift_sigma"] > memory._RECALL_ABSTAIN_LIFT
    assert out["abstain"] is False


def test_a_query_the_bank_does_not_answer_abstains(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    _seed(bank, 100)

    out = _confidence(bank, "QUERY-DIFFUSE")

    assert out["available"] is True
    assert out["abstain"] is True


def test_a_supplied_batch_means_no_provider_call(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    _seed(bank, 60)
    _seed(bank, 16, prefix="SPECIAL")
    supplied = _fake_embedder()(["SPECIAL"])

    def explode(texts):  # pragma: no cover - the assertion is that it never runs
        raise AssertionError("recall_confidence must reuse the caller's batch")
    patch_provider_seam(monkeypatch, "embed_texts_meta", explode)

    out = _confidence(bank, "SPECIAL", embedded=supplied)

    assert out["available"] is True
    assert out["abstain"] is False


def test_a_fallback_query_vector_gives_no_signal(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    _seed(bank, 60)

    fallback = providers.EmbeddingBatch(
        vectors=[np.zeros(_DIM, dtype=np.float32)],
        model_key="cheap:crc32:256", dimensions=_DIM, fallback=True)
    out = _confidence(bank, "anything", embedded=fallback)

    assert out["available"] is False
