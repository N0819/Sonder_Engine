"""The embedding repair finishes a backlog at its own pace, and never writes a
vector over a row that changed while it was embedding.

Two defects in one lane (review 2026-11-01, mind_memory F11 and the F4
addendum):

* THE BACKOFF PUNISHED SUCCESS. `_repair_loop` doubled its delay after every
  round whatever the round did, and gave up after `_REPAIR_MAX_ROUNDS` rounds
  of any kind. Measured with a healthy provider fixing 32 rows a round: a
  200-row backlog took 7 rounds and 1,350 s; a 500-row backlog (the chat-open
  adoption limit) used all 12 rounds over 2,850 s and left 116 rows queued
  with no thread. The rounds bound exists for a provider that keeps REFUSING
  ("not busy, it is gone"); a round that fixed rows is not that.
* THE WRITE WAS NOT COMPARE-AND-SET. The repair read a row, spent a provider
  round trip embedding its text, then wrote `WHERE id=?`. A host edit
  (`update_memory`) landing inside that window -- re-embedding the row with
  its NEW text and the live stamp -- was overwritten with vectors of the OLD
  text, stamped live, and nothing ever revisited it.
"""

from __future__ import annotations

import time as _real_time

import numpy as np
import pytest

from llm.providers import EmbeddingBatch
from mind import memory, memory_write


class _Clock:
    """`time` as `memory_write` sees it, with `sleep` recorded, not slept."""

    def __init__(self):
        self.slept = []

    def sleep(self, seconds):
        self.slept.append(seconds)

    def __getattr__(self, name):
        return getattr(_real_time, name)


@pytest.fixture
def queue(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(memory_write, "time", clock)
    saved = {t: set(ids) for t, ids in memory_write._REPAIR_PENDING.items()}
    for ids in memory_write._REPAIR_PENDING.values():
        ids.clear()
    yield clock
    for table, ids in memory_write._REPAIR_PENDING.items():
        ids.clear()
        ids.update(saved[table])


def _draining(per_round, refuse_after=None):
    """A stand-in repair pass: fixes `per_round` rows a round, or none once
    `refuse_after` rounds have run (the provider refusing)."""
    calls = {"n": 0}

    def repair(batch=32):
        calls["n"] += 1
        fixed = {t: 0 for t in memory_write._REPAIR_PENDING}
        if refuse_after is not None and calls["n"] > refuse_after:
            return fixed
        with memory_write._REPAIR_LOCK:
            ids = sorted(memory_write._REPAIR_PENDING["memories"])[:per_round]
            memory_write._REPAIR_PENDING["memories"].difference_update(ids)
        fixed["memories"] = len(ids)
        return fixed
    return repair, calls


def test_a_productive_round_never_lengthens_the_wait(queue, monkeypatch):
    repair, calls = _draining(32)
    monkeypatch.setattr(memory_write, "repair_pending_embeddings", repair)
    memory_write._REPAIR_PENDING["memories"].update(range(1, 501))
    memory_write._repair_loop()
    assert not memory_write._REPAIR_PENDING["memories"], "the whole backlog is finished"
    assert calls["n"] == 16
    assert set(queue.slept) == {memory_write._REPAIR_DELAY}


def test_a_refusing_provider_still_backs_off_and_is_given_up_on(queue, monkeypatch):
    repair, calls = _draining(32, refuse_after=2)
    monkeypatch.setattr(memory_write, "repair_pending_embeddings", repair)
    memory_write._REPAIR_PENDING["memories"].update(range(1, 201))
    memory_write._repair_loop()
    refused = calls["n"] - 2
    assert refused == memory_write._REPAIR_MAX_ROUNDS
    assert queue.slept[:3] == [memory_write._REPAIR_DELAY] * 3
    assert queue.slept[3] == 2 * memory_write._REPAIR_DELAY, "backs off once refused"
    assert max(queue.slept) == memory_write._REPAIR_MAX_DELAY
    assert len(memory_write._REPAIR_PENDING["memories"]) == 200 - 64


def test_a_pass_that_raises_is_a_refused_round_not_the_end(queue, monkeypatch):
    """`database is locked` is transient; the thread used to exit on it and
    leave the queue with nobody coming back for it."""
    repair, _calls = _draining(50)
    raised = {"n": 0}

    def flaky(batch=32):
        if raised["n"] == 0:
            raised["n"] += 1
            raise RuntimeError("database is locked")
        return repair(batch)
    monkeypatch.setattr(memory_write, "repair_pending_embeddings", flaky)
    memory_write._REPAIR_PENDING["memories"].update(range(1, 101))
    memory_write._repair_loop()
    assert not memory_write._REPAIR_PENDING["memories"]


@pytest.fixture
def stranded(temp_db, queue):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", _real_time.time()))
    mara = temp_db.qi("INSERT INTO characters(name,sheet,source,created) "
                      "VALUES(?,?,?,?)", ("Mara", "{}", "{}", _real_time.time()))
    mid = memory.add_memory(chat, mara, None, "episodic", "witnessed", 0.7,
                            "The ferry left without us.", turn_idx=1)
    row = temp_db.q("SELECT embedding_model FROM memories WHERE id=?", (mid,), one=True)
    assert row["embedding_model"] == "cheap:crc32:256", "written on the fallback"
    memory_write._REPAIR_PENDING["memories"].add(mid)
    return mid


def _host_edit_during_the_embed(temp_db, mid, monkeypatch, *, stamp):
    host_vec = np.full(4, 0.5, dtype=np.float32).tobytes()

    def embed(texts, **_kw):
        # The host's edit lands while the repair waits on the provider.
        temp_db.qi("UPDATE memories SET content=?, gist=?, embedding=?, cue_embedding=?, "
                   "embedding_model=?, embedding_dim=? WHERE id=?",
                   ("The ferry left WITH us aboard.", "aboard", host_vec, host_vec,
                    stamp, 4 if stamp != "cheap:crc32:256" else 256, mid))
        return EmbeddingBatch(vectors=[np.ones(4, dtype=np.float32) for _ in texts],
                              model_key="test:live", dimensions=4, fallback=False)
    monkeypatch.setattr(memory_write, "embed_texts_meta", embed)
    return host_vec


def test_a_host_edit_inside_the_embed_window_keeps_its_vector(temp_db, stranded, monkeypatch):
    host_vec = _host_edit_during_the_embed(temp_db, stranded, monkeypatch, stamp="test:live")
    memory_write.repair_pending_embeddings()
    row = temp_db.q("SELECT content, embedding, embedding_model FROM memories WHERE id=?",
                    (stranded,), one=True)
    assert row["content"] == "The ferry left WITH us aboard."
    assert bytes(row["embedding"]) == host_vec, "the repair wrote the OLD text's vector"


def test_an_edit_that_also_fell_back_is_not_stamped_with_the_old_text(temp_db, stranded,
                                                                       monkeypatch):
    """Still on the hash, but with different words: the repair's vector is of
    words the row no longer holds, so it must not land -- the row stays queued
    material for a later pass rather than carrying a wrong live vector."""
    _host_edit_during_the_embed(temp_db, stranded, monkeypatch, stamp="cheap:crc32:256")
    memory_write.repair_pending_embeddings()
    row = temp_db.q("SELECT embedding_model FROM memories WHERE id=?", (stranded,), one=True)
    assert row["embedding_model"] == "cheap:crc32:256"


def test_an_untouched_row_is_finished(temp_db, stranded, monkeypatch):
    monkeypatch.setattr(memory_write, "embed_texts_meta",
                        lambda texts, **_kw: EmbeddingBatch(
                            vectors=[np.ones(4, dtype=np.float32) for _ in texts],
                            model_key="test:live", dimensions=4, fallback=False))
    assert memory_write.repair_pending_embeddings()["memories"] == 1
    row = temp_db.q("SELECT embedding_model FROM memories WHERE id=?", (stranded,), one=True)
    assert row["embedding_model"] == "test:live"
