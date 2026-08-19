"""The engine finishes its own failed write, and touches nothing else.

A memory whose embedding call failed is stored anyway under the
`cheap:crc32:256` stamp -- right at write time, because a memory is worth more
than its vector and the turn must not wait. What was wrong was leaving it
there: the only cure on offer walked the whole bank, which is wildly out of
proportion to the four rows that actually failed, and so nobody ran it.

Live provocation (2026-08-11): the configured OpenRouter/Perplexity route
serves a bucket of ~3 requests refilling at 1-2/s while a turn makes several
embedding calls, so chat 70 turn 6 lost all four of its memories inside one
depleted window -- with the retry, pacing and jitter fixes already running.

The property these tests exist to defend is the NARROWNESS. Re-doing a write
the engine failed seconds ago is the engine finishing its job; re-embedding a
corpus is a migration a host chooses and pays for, and this must never quietly
become the second thing.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from mind import memory
from mind import memory_write
from tests.helpers import patch_embedding_seam
from llm.providers import EmbeddingBatch
from story.character_schema import default_character_data


REAL = "openrouter:3:perplexity/pplx-embed-v1-4b"


def _real_batch(texts, **_kw):
    v = np.ones(2560, dtype=np.float32) / np.sqrt(2560)
    return EmbeddingBatch(vectors=[v for _ in texts], model_key=REAL,
                          dimensions=2560, fallback=False)


def _fallen_back(texts, **_kw):
    v = np.ones(256, dtype=np.float32) / np.sqrt(256)
    return EmbeddingBatch(vectors=[v for _ in texts],
                          model_key="cheap:crc32:256", dimensions=256,
                          fallback=True, error="429 rate limited")


@pytest.fixture
def bank(temp_db, monkeypatch):
    """A chat with one character, and no repair THREAD -- the pass is driven
    by hand so the test does not wait 30 seconds to observe a decision."""
    monkeypatch.setattr(memory_write, "_ensure_repair_thread", lambda: None)
    patch_embedding_seam(monkeypatch, "embedding_model_key", lambda: REAL)
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Repair", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Hinami", json.dumps(default_character_data("Hinami")), "{}",
         time.time(), "char_hinami"))
    return {"chat": chat_id, "char": char_id}


def _write(bank, text, turn_idx=0):
    return memory.add_memory(bank["chat"], bank["char"], None, "episodic",
                             "witnessed", 0.6, text, turn_idx=turn_idx)


def _stamp(mid):
    from core.db import q
    return q("SELECT embedding_model FROM memories WHERE id=?", (mid,),
             one=True)["embedding_model"]


def test_a_failed_write_is_queued_and_then_finished(bank, monkeypatch):
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    mid = _write(bank, "She said the tightest route was fine.")
    assert _stamp(mid) == "cheap:crc32:256"
    assert memory._REPAIR_PENDING["memories"] == {mid}

    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    assert memory.repair_pending_embeddings()["memories"] == 1
    assert _stamp(mid) == REAL
    assert memory._REPAIR_PENDING["memories"] == set()


def test_a_successful_write_queues_nothing(bank, monkeypatch):
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    _write(bank, "An ordinary beat.")
    assert memory._REPAIR_PENDING["memories"] == set()


def test_it_touches_only_the_rows_that_failed(bank, monkeypatch):
    """THE POINT. A stranded row from last month is not this pass's business.

    The bank may hold any number of rows on an old stamp — from a model
    change, an import, a restore. Those are a migration the host chooses.
    This pass re-does the write it just fumbled and stops.
    """
    from core.db import q, qi
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    old = _write(bank, "A memory from an earlier era.", turn_idx=1)
    qi("UPDATE memories SET embedding_model='cheap:crc32:256',embedding_dim=256 "
       "WHERE id=?", (old,))

    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    fresh = _write(bank, "The beat that just failed.", turn_idx=2)

    calls = []
    def _counted(texts, **kw):
        calls.append(list(texts))
        return _real_batch(texts, **kw)
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _counted)
    memory.repair_pending_embeddings()

    assert _stamp(fresh) == REAL
    assert _stamp(old) == "cheap:crc32:256", "the corpus was re-embedded"
    assert len(calls) == 1 and len(calls[0]) == 2  # document + cues, one row


def test_a_row_already_fixed_is_not_re_embedded(bank, monkeypatch):
    """A rebuild or a restore may have got there first; spending a request to
    change nothing is the kind of waste this whole change exists to avoid."""
    from core.db import qi
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    mid = _write(bank, "Queued, then fixed by other means.")
    qi("UPDATE memories SET embedding_model=?,embedding_dim=? WHERE id=?",
       (REAL, 2560, mid))

    calls = []
    patch_embedding_seam(monkeypatch, "embed_texts_meta",
                        lambda t, **k: (calls.append(t), _real_batch(t))[1])
    assert memory.repair_pending_embeddings()["memories"] == 0
    assert calls == []


def test_a_still_degraded_provider_leaves_everything_queued(bank, monkeypatch):
    """Never write the hash over the hash and call the row repaired."""
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    mid = _write(bank, "Written during the outage.")
    assert memory.repair_pending_embeddings()["memories"] == 0
    assert memory._REPAIR_PENDING["memories"] == {mid}
    assert _stamp(mid) == "cheap:crc32:256"


def test_no_provider_configured_queues_nothing(bank, monkeypatch):
    """With no embeddings role the hash IS the engine's embedding.

    Queuing here would mean re-hashing the same text on a timer forever.
    """
    patch_embedding_seam(monkeypatch, "embedding_model_key",
                        lambda: "cheap:crc32:256")
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    _write(bank, "No provider, no problem.")
    assert memory._REPAIR_PENDING["memories"] == set()


def test_the_backlog_is_bounded(bank, monkeypatch):
    """A provider down for an hour must not accumulate without limit.

    Past the bound the rows stay stranded and the ordinary rebuild offer is
    the honest remedy — which is the situation that offer was written for.
    """
    patch_embedding_seam(monkeypatch, "embedding_model_key", lambda: REAL)
    memory.note_failed_embedding_write(
        "memories", range(1, memory._REPAIR_MAX_PENDING + 50))
    assert (len(memory._REPAIR_PENDING["memories"])
            <= memory._REPAIR_MAX_PENDING + 50)
    before = len(memory._REPAIR_PENDING["memories"])
    memory.note_failed_embedding_write("memories", [999_999])
    assert len(memory._REPAIR_PENDING["memories"]) == before


def test_summaries_are_finished_too(bank, monkeypatch):
    from core.db import q
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    memory.save_memory_summary(bank["chat"], bank["char"], "She chose a route.",
                               scope="autobiographical", end_turn_idx=3)
    sid = q("SELECT id FROM memory_summaries", one=True)["id"]
    assert memory._REPAIR_PENDING["memory_summaries"] == {sid}

    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    assert memory.repair_pending_embeddings()["memory_summaries"] == 1
    assert q("SELECT embedding_model FROM memory_summaries WHERE id=?", (sid,),
             one=True)["embedding_model"] == REAL


# ---- Waiting a rate limit out, without asking ----

def test_a_still_degraded_pass_comes_back(bank, monkeypatch):
    """ONE PASS WAS NOT ENOUGH, and the first version returned after it.

    A rate limit is a thing you wait OUT. The pass that finds the provider
    still refusing must leave something scheduled to come back, or the rows
    sit queued forever with nobody to finish them -- which is the failure
    this whole queue exists to prevent, reintroduced one level up.
    """
    rounds = []
    monkeypatch.setattr(memory.time, "sleep", lambda s: rounds.append(s))
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    mid = _write(bank, "written during the outage")
    assert memory._REPAIR_PENDING["memories"] == {mid}

    passes = []
    def _still_down():
        passes.append(1)
        return {"memories": 0, "memory_summaries": 0}
    monkeypatch.setattr(memory_write, "repair_pending_embeddings", _still_down)
    memory._repair_loop()
    assert len(passes) == memory._REPAIR_MAX_ROUNDS, "it gave up after one try"
    assert rounds[1] > rounds[0], "it busy-waited instead of backing off"
    assert max(rounds) <= memory._REPAIR_MAX_DELAY


def test_the_loop_stops_once_the_rows_are_done(bank, monkeypatch):
    rounds = []
    monkeypatch.setattr(memory.time, "sleep", lambda s: rounds.append(s))
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    _write(bank, "one bad beat")
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    memory._repair_loop()
    assert len(rounds) == 1
    assert memory._REPAIR_PENDING["memories"] == set()


def test_rows_from_a_previous_process_are_picked_back_up(bank, monkeypatch):
    """The queue dies with the process; the rows do not.

    Without this, a story stranded before a restart had nobody left to finish
    it and could only be OFFERED a rebuild — the question we are removing.
    """
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    mid = _write(bank, "stranded before the restart")
    for queued in memory._REPAIR_PENDING.values():
        queued.clear()  # the restart

    found = memory.queue_fallback_rows_for_repair(bank["chat"])
    assert found["memories"] == 1
    assert memory._REPAIR_PENDING["memories"] == {mid}


def test_a_model_change_is_not_adopted(bank, monkeypatch):
    """The stamp is the whole discriminator.

    A crc32 row under a real provider is a write this engine failed. Another
    model's key is a host who changed embedding model — a migration nobody
    asked this code to start, and the one case the rebuild prompt is for.
    """
    from core.db import qi
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    mid = _write(bank, "embedded by the previous provider")
    qi("UPDATE memories SET embedding_model='openai:1:text-embedding-3-small',"
       "embedding_dim=1536 WHERE id=?", (mid,))

    assert memory.queue_fallback_rows_for_repair(bank["chat"])["memories"] == 0
    assert memory._REPAIR_PENDING["memories"] == set()
    # and it still counts as stranded, so the prompt can still fire for it
    status = memory.embedding_bank_status(chat_id=bank["chat"])
    assert status["memories"]["stranded"] == 1
    assert status["memories"]["fallback_written"] == 0


def test_a_failed_write_is_not_counted_as_a_reason_to_ask(bank, monkeypatch):
    """What the chat-open prompt subtracts.

    The shape of the real moment: the write failed some beats ago, and the
    provider is answering again by the time the chat is opened. While it is
    still down `fallback_written` is 0 by design — with no live model to
    compare against, nothing is separable and nothing is offered either.
    """
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    _write(bank, "a beat the provider refused")
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    status = memory.embedding_bank_status(chat_id=bank["chat"])
    assert status["memories"]["stranded"] == 1
    assert status["memories"]["fallback_written"] == 1


# ---- A comparison needs both sides ----
#
# Live, 2026-08-11: chat 70 held 34 memories, every one correctly stamped
# `openrouter:3:perplexity/pplx-embed-v1-4b`, and every open of that story
# said all 34 were "written with a different embedding model" and told the
# host to go set an embeddings provider they already had. The probe on the
# chat-open path is sent without retries and hit that provider's rate limit;
# its crc32 placeholder was then read as the LIVE MODEL'S IDENTITY, so the
# comparison ran against a model nothing was written by, and stranded the
# bank. The configured role separates the case the probe cannot.

def test_a_rate_limited_probe_does_not_strand_a_healthy_bank(bank,
                                                             monkeypatch):
    """THE REPORTED BUG, exactly: correct rows, silent provider, no claim."""
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    for i in range(3):
        _write(bank, "a correctly embedded beat", turn_idx=i)

    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    status = memory.embedding_bank_status(chat_id=bank["chat"])
    assert status["memories"]["total"] == 3
    assert status["memories"]["stranded"] == 0
    assert status["live_unknown"] is True
    # ...and NOT the flag every consumer reads as "no provider configured".
    assert status["is_fallback"] is False
    # The model reported is the configured one, not the hash placeholder.
    assert status["model"] == REAL
    assert "429" in status["fallback_reason"]


def test_no_provider_configured_still_reports_the_split(bank, monkeypatch):
    """The case the prompt was written for, unchanged.

    With no embeddings provider the hash IS the engine's embedding, so rows
    carrying a real model's stamp genuinely are keyword-only and rebuilding
    onto the hash genuinely is a downgrade. `is_fallback` must still say so.
    """
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    _write(bank, "embedded while a provider was configured")
    patch_embedding_seam(monkeypatch, "embedding_model_key",
                        lambda: "cheap:crc32:256")
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    status = memory.embedding_bank_status(chat_id=bank["chat"])
    assert status["memories"]["stranded"] == 1
    assert status["is_fallback"] is True
    assert status["live_unknown"] is False


def test_a_silent_provider_does_not_start_a_rebuild(bank, monkeypatch):
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    decision = memory.start_rebuild_if_needed(bank["chat"])
    assert decision["started"] is False
    assert decision["reason"] == "embedding provider not answering"


def test_a_rebuild_never_writes_the_hash_over_real_vectors(bank, monkeypatch):
    """The same conflation, where it destroys data rather than nagging.

    `want_fallback` was `live.fallback` — "the probe that opened this run
    failed" — and it is the switch that disables the guard refusing to write
    crc32 over real vectors. So a rebuild started while the provider happened
    to be rate limited would have overwritten an entire real corpus with
    hashes and stamped them migrated. Whether the host has an embeddings
    provider is a settings fact, not a fact about one request.
    """
    from core.db import q
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _real_batch)
    mid = _write(bank, "a real vector worth keeping")
    patch_embedding_seam(monkeypatch, "embed_texts_meta", _fallen_back)

    report = memory.rebuild_embeddings(chat_id=bank["chat"])
    assert report["stopped_early"] is True
    assert report["memories"] == 0
    assert _stamp(mid) == REAL, "a rate limit overwrote a real vector"
    assert q("SELECT embedding_dim FROM memories WHERE id=?", (mid,),
             one=True)["embedding_dim"] == 2560
