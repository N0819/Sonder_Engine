"""The stock repair of junk retrieval-cue material (repair_memory_cues).

Legacy extraction stamped stopword-grade key phrases and entities onto most
of the live corpus, and those items fire the highest-weighted exact-match
ranking by bare substring (docs/experiments/AUDIT_MEMORY.md 1.3). The repair
is subtractive -- it removes what `_junk_cue` condemns and never rewrites a
clean model-supplied cue -- and refills from content only when subtraction
emptied a list.
"""

import json
import time

import numpy as np
import pytest

from mind import memory
from llm import providers
from story.character_schema import default_character_data
from tests.helpers import patch_provider_seam


@pytest.fixture
def bank(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("CueRepair", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}", time.time(),
         "char_mara"))
    return {"chat": chat_id, "char": char_id}


def _fake_embedder(dim=8):
    def fake(texts):
        vectors = []
        for text in texts:
            seed = (hash(str(text)) % 997) + 1
            vec = np.arange(1, dim + 1, dtype=np.float32) * seed
            vectors.append(vec / np.linalg.norm(vec))
        return providers.EmbeddingBatch(
            vectors=vectors, model_key="test:model:x", dimensions=dim,
            fallback=False)
    return fake


def _fallback_embedder(dim=8):
    def fake(texts):
        return providers.EmbeddingBatch(
            vectors=[np.zeros(dim, dtype=np.float32) for _ in texts],
            model_key="cheap:crc32:256", dimensions=dim, fallback=True)
    return fake


def _seed(bank, *, key_phrases, entities,
          content="Mara crossed the old stone bridge at dusk."):
    return memory.add_memory(
        bank["chat"], bank["char"], None, "episodic", "witnessed", 0.6,
        content, turn_idx=1, gist=content,
        key_phrases=key_phrases, entities=entities, location="bridge")


def _row(mid):
    from core.db import q
    return q("SELECT * FROM memories WHERE id=?", (mid,), one=True)


def test_junk_items_are_removed_and_clean_ones_kept(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    mid = _seed(bank, key_phrases=["the", "stone bridge", "'; said '"],
                entities=["She", "Mara"])

    report = memory.repair_memory_cues(bank["chat"], bank["char"],
                                       dry_run=False)

    assert report["repaired"] == 1
    assert report["items_removed"] == 3
    row = _row(mid)
    assert json.loads(row["key_phrases"]) == ["stone bridge"]
    assert json.loads(row["entities"]) == ["Mara"]
    assert row["embedding_model"] == "test:model:x"


def test_a_clean_row_is_not_touched(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    mid = _seed(bank, key_phrases=["stone bridge"], entities=["Mara"])
    before = _row(mid)

    report = memory.repair_memory_cues(bank["chat"], bank["char"],
                                       dry_run=False)

    assert report["repaired"] == 0
    after = _row(mid)
    assert after["embedding"] == before["embedding"]
    assert after["key_phrases"] == before["key_phrases"]


def test_an_emptied_list_is_refilled_from_content(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    mid = _seed(bank, key_phrases=["the", "her"], entities=["Mara"])

    report = memory.repair_memory_cues(bank["chat"], bank["char"],
                                       dry_run=False)

    assert report["key_phrases_refilled"] == 1
    refilled = json.loads(_row(mid)["key_phrases"])
    assert refilled, "an emptied list must be refilled from content"
    assert all(p for p in refilled)
    assert "the" not in refilled


def test_dry_run_reports_and_writes_nothing(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    mid = _seed(bank, key_phrases=["the", "stone bridge"], entities=["Mara"])
    before = _row(mid)

    report = memory.repair_memory_cues(bank["chat"], bank["char"],
                                       dry_run=True)

    assert report["dry_run"] is True
    assert report["repaired"] == 1
    after = _row(mid)
    assert after["key_phrases"] == before["key_phrases"]
    assert after["embedding"] == before["embedding"]


def test_a_fallback_batch_aborts_instead_of_downgrading(bank, monkeypatch):
    mid = _seed(bank, key_phrases=["the", "stone bridge"], entities=["Mara"])
    before = _row(mid)
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fallback_embedder())

    report = memory.repair_memory_cues(bank["chat"], bank["char"],
                                       dry_run=False)

    assert report["stopped_early"] is True
    assert "fallback" in report["error"]
    after = _row(mid)
    assert after["key_phrases"] == before["key_phrases"]
    assert after["embedding"] == before["embedding"]


def test_the_repair_is_idempotent(bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fake_embedder())
    _seed(bank, key_phrases=["the", "stone bridge"], entities=["She", "Mara"])

    first = memory.repair_memory_cues(bank["chat"], bank["char"],
                                      dry_run=False)
    second = memory.repair_memory_cues(bank["chat"], bank["char"],
                                       dry_run=False)

    assert first["repaired"] == 1
    assert second["repaired"] == 0
