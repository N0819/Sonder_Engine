"""A hash vector may not rank a memory against a query.

`cheap_embed` is a crc32 character n-gram sketch. It answers "is this the same
text"; it was standing in for "does this mean the same thing", and it
correlates with real similarity at r = 0.028 over 7,998,000 row pairs. On a
bank the sketch also WROTE, the model keys match, so the compatibility check
that excludes a stranded row never fired and the hash carried 2.15 of the 4.5
RRF weight on pure noise.

Measured over the 10,960-row LongMemEval bank, 470 probes
(`docs/experiments/CRC32_CONTROL.md`): the shipped fallback scored 289 and
switching the vector rankings off entirely scored **338**. The hash was 49
probes WORSE than having no vector channel at all -- not because it added
nothing, but because its noise displaced genuine keyword candidates out of a
fixed-size payload. That is the property these tests defend, and it is why the
interesting assertion is about what comes BACK rather than about a score.

Three boundaries, each of which the obvious version of this change gets wrong:

- **The stamp stays.** `embedding_bank_status`, `_warn_stranded_embeddings`,
  `note_failed_embedding_write` and `rebuild_embeddings` all key on
  `cheap:crc32:256` existing on the row. It is the marker that says "this
  engine failed a write and may finish it later"; deleting it strands exactly
  the rows the repair lane is for.
- **The sketch keeps the job it is good at.** Memory-against-memory
  near-duplicate detection is 99.1% precise against real cosine 0.95. That is
  a different question from memory-against-query, and only the second one is
  refused here.
- **An install that HAS a provider is untouched.** Where one real call fell
  back transiently, the row keys already disagreed and these scores were
  already zero. That path was correct before this change and is unchanged by
  it.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from mind import memory
from mind import memory_retrieval
from mind import memory_write
from tests.helpers import patch_provider_seam
from llm.providers import EmbeddingBatch


REAL = "openrouter:3:perplexity/pplx-embed-v1-4b"
HASH = "cheap:crc32:256"

# One-hot axes, so "which text got which vector" is decidable by eye and a
# rigged cosine is exactly 1.0 or exactly 0.0 rather than nearly so.
_AXIS = {"decoy": 3, "query": 3, "other": 17}


def _axis_for(text):
    t = (text or "").casefold()
    if "mudflat" in t or "brass key" in t:
        # The decoy and the query share an axis. Nothing else does.
        return _AXIS["decoy"]
    return _AXIS["other"]


def _vec_on(axis, dim):
    v = np.zeros(dim, dtype=np.float32)
    v[axis] = 1.0
    return v


def _hash_batch(texts, **_kw):
    """What `embed_texts_meta` returns on an install with no provider.

    `resolve_role("embeddings")` raises, `_embed_with_retry` degrades, and the
    batch comes back stamped `cheap:crc32:256` with `fallback=True`. Rigged so
    the decoy scores a perfect 1.0 against the query -- the sketch does not
    normally do that, but it is the shape of what it does at r = 0.028, and
    making it exact removes the test's dependence on n-gram luck.
    """
    return EmbeddingBatch(
        vectors=[_vec_on(_axis_for(t), 256) for t in texts],
        model_key=HASH, dimensions=256, fallback=True,
        error="no embeddings provider configured")


def _real_batch(texts, **_kw):
    return EmbeddingBatch(
        vectors=[_vec_on(_axis_for(t), 2560) for t in texts],
        model_key=REAL, dimensions=2560, fallback=False)


# The bank the `stocked` fixture builds, minus nothing: every row clears
# `_CONTRAST_MIN_SALIENCE`, and none is in an obligation tier.
_CONTRAST_ROWS_EXPECTED = 20

_VECTOR_REASONS = {"semantic match", "cue-vector match"}


def _has_content(rows, content):
    return any((r.get("content") or "") == content for r in rows)


def _reasons(rows):
    out = set()
    for r in rows:
        out.update(r.get("retrieval_reasons") or [])
    return out


@pytest.fixture
def bank(temp_db, monkeypatch):
    monkeypatch.setattr(memory_write, "_ensure_repair_thread", lambda: None)
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("No provider", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    return chat_id, char_id


def _write(bank, text, turn_idx):
    chat_id, char_id = bank
    return memory.add_memory(chat_id, char_id, None, "episodic", "witnessed",
                             0.6, text, turn_idx=turn_idx)


# The question every probe below asks, and the row that answers it.
QUERY = "where did I leave the brass key"
ANSWER = "I left the brass key on the sill of the scullery window."
# Rigged to cosine 1.0 against the query and to share not one content word
# with it. Under the old code this was semantic rank 1 AND cue rank 1.
DECOY = "The tide came in over the mudflats before anyone had woken."

FILLER = [
    "The baker's cart lost a wheel on the cobbles outside the mill.",
    "Someone had repainted the shutters a colour nobody agreed on.",
    "A dog barked at the weir for most of the afternoon.",
    "The ferryman would not take coin from anyone under twelve.",
    "Frost got into the well housing and split the timber.",
    "Two crows argued over a heel of bread on the chapel step.",
    "The lamplighter came late and blamed the wind for it.",
    "A cart of turnips overturned at the crossroads by the elm.",
    "The miller's daughter sang the same four bars all week.",
    "Nobody claimed the coat left hanging in the porch.",
    "The river ran brown for three days after the rain.",
    "A hawk took a pigeon off the roof of the granary.",
    "The blacksmith shut early on account of the heat.",
    "Someone chalked a rude verse on the back of the toll house.",
    "The orchard wall came down in a section nobody had mended.",
    "A pedlar sold three combs and a length of ribbon by noon.",
    "The bell rope frayed and was spliced rather than replaced.",
    "Rain got under the thatch above the second landing.",
    "A stray cat had kittens behind the tannery vats.",
    "The schoolmaster's bicycle went missing and came back muddy.",
]


@pytest.fixture
def stocked(bank, monkeypatch):
    """A bank written with no provider, so every row carries the hash stamp."""
    patch_provider_seam(monkeypatch, "embed_texts_meta", _hash_batch)
    patch_provider_seam(monkeypatch, "embedding_model_key", lambda: HASH)
    ids = {"answer": _write(bank, ANSWER, 4), "decoy": _write(bank, DECOY, 9)}
    for i, text in enumerate(FILLER):
        _write(bank, text, 20 + i * 3)
    return ids


class TestTheHashDoesNotRank:
    def test_a_fallback_batch_contributes_no_vector_ranking(self, bank,
                                                            stocked):
        chat_id, char_id = bank
        got = memory.search_memories(chat_id, char_id, QUERY, k=5)
        assert got, "the query must still be answered, just not by the hash"
        assert not (_reasons(got) & _VECTOR_REASONS), (
            "a crc32 batch must contribute neither vector ranking")

    def test_the_lexical_answer_comes_back(self, bank, stocked):
        """The point of dropping the hash is that BM25 and exact-cue carry the
        query on their own. `_rrf_add` skips an empty ranking, so nothing
        needed plumbing for this to work."""
        chat_id, char_id = bank
        got = memory.search_memories(chat_id, char_id, QUERY, k=5)
        assert stocked["answer"] in [m["id"] for m in got]
        assert _reasons(got) & {"keyword match",
                                "exact phrase or entity match"}, \
            "the lexical rankings must be what answered it"

    def test_the_hash_no_longer_buys_a_payload_slot(self, bank, stocked):
        """The measured harm, in miniature.

        The decoy shares no content word with the query and is rigged to
        cosine 1.0 against it. Ranked first on both vector lists at a combined
        weight of 2.15, it took a slot in a fixed-size payload from a row that
        had an actual reason to be there. This is the assertion that fails if
        `rank_by_vector` is forced back to True.
        """
        chat_id, char_id = bank
        got = memory.search_memories(chat_id, char_id, QUERY, k=2)
        ids = [m["id"] for m in got]
        assert stocked["decoy"] not in ids, (
            "a row whose only claim is hash similarity must not be recalled")
        assert stocked["answer"] in ids


class TestAConfiguredProviderIsUntouched:
    def test_a_real_batch_still_ranks_by_vector(self, bank, monkeypatch):
        """The scope guard. This change must be invisible to every install
        that has an embeddings provider."""
        patch_provider_seam(monkeypatch, "embed_texts_meta", _real_batch)
        patch_provider_seam(monkeypatch, "embedding_model_key", lambda: REAL)
        chat_id, char_id = bank
        _write(bank, ANSWER, 4)
        _write(bank, DECOY, 9)
        for i, text in enumerate(FILLER):
            _write(bank, text, 20 + i * 3)
        got = memory.search_memories(chat_id, char_id, QUERY, k=5)
        assert _reasons(got) & _VECTOR_REASONS, (
            "with a real provider the vector rankings must still fire")

    def test_a_transient_fallback_against_a_real_bank_was_already_handled(
            self, bank, monkeypatch):
        """Rows real, one query call degraded. The keys disagree, so these
        scores were zero before this change too -- asserted so a later
        simplification cannot quietly widen the refusal into this case and
        call it the same fix."""
        patch_provider_seam(monkeypatch, "embed_texts_meta", _real_batch)
        patch_provider_seam(monkeypatch, "embedding_model_key", lambda: REAL)
        _write(bank, ANSWER, 4)
        for i, text in enumerate(FILLER):
            _write(bank, text, 20 + i * 3)
        patch_provider_seam(monkeypatch, "embed_texts_meta", _hash_batch)
        chat_id, char_id = bank
        got = memory.search_memories(chat_id, char_id, QUERY, k=5)
        assert not (_reasons(got) & _VECTOR_REASONS)
        assert _has_content(got, ANSWER)


class TestTheStampSurvives:
    def test_rows_keep_the_fallback_stamp_for_the_repair_lane(self, bank,
                                                              stocked,
                                                              temp_db):
        """What must NOT be done. Four readers select on this string; without
        it the rows a rebuild exists to find become invisible."""
        chat_id, _char_id = bank
        rows = temp_db.q(
            "SELECT count(*) AS n FROM memories WHERE chat_id=? "
            "AND embedding_model=?", (chat_id, HASH), one=True)
        assert rows["n"] == 2 + len(FILLER), (
            "refusing to RANK on the hash must not stop the engine STORING it")


class TestTheSketchKeepsItsOwnJob:
    def test_memory_against_memory_still_uses_the_vector(self, bank, stocked,
                                                         monkeypatch):
        """Near-duplicate detection is what a character n-gram sketch is for,
        and the diversity pass inside `search_memories` is where it is used.
        Distrusting the hash as a RELEVANCE signal must not cost the engine
        the one comparison it is measured to be good at.
        """
        seen = []
        real = memory_retrieval._memory_similarity

        def _spy(a, b):
            seen.append((a.get("_vector") is not None,
                         b.get("_vector") is not None))
            return real(a, b)

        monkeypatch.setattr(memory_retrieval, "_memory_similarity", _spy)
        chat_id, char_id = bank
        memory.search_memories(chat_id, char_id, QUERY, k=5)
        assert seen, "the diversity pass must have run"
        assert all(a and b for a, b in seen), (
            "both sides of a near-duplicate comparison must still carry the "
            "sketch")


class TestContrastDeclinesTheHashAxis:
    """`contrast_memory` REWARDS distance, which is what makes the hash worse
    here than anywhere else: a sketch scores an unrelated pair at an arbitrary
    distance, so it would not merely fail to find the true contrast, it would
    nominate rows for unbidden recall by coin flip while reporting a semantic
    reason. The function's own docstring records that the semantic half was
    deliberately absent until real vectors existed; this restores that.
    """

    def test_the_semantic_term_is_not_applied_to_a_hash_bank(self, bank,
                                                             stocked,
                                                             monkeypatch):
        """Scored over the WHOLE bank rather than its top three.

        The rigged cosine is 1.0 for exactly two rows, and a row carrying a
        0.7 contrast penalty is not going to be in anyone's top three either
        way -- so a top-k comparison here passes whether the axis is applied
        or not, which is a test that cannot fail. Every row's score is
        compared instead.
        """
        chat_id, char_id = bank
        wide = 2 + len(FILLER)
        before = {m["id"]: m["contrast_score"]
                  for m in memory.contrast_memory(chat_id, char_id, QUERY,
                                                  200, k=wide)}
        assert len(before) >= _CONTRAST_ROWS_EXPECTED, (
            "the structural axis must still score the bank")

        # The same call with the vectors gone from the bank entirely. If the
        # hash were still feeding `_CONTRAST_SEMANTIC`, the two rows rigged to
        # cosine 1.0 would move by 0.7 between these runs.
        from core import db
        db.qi("UPDATE memories SET embedding=NULL, cue_embedding=NULL "
              "WHERE chat_id=?", (chat_id,))
        after = {m["id"]: m["contrast_score"]
                 for m in memory.contrast_memory(chat_id, char_id, QUERY, 200,
                                                 k=wide)}
        assert after == before, (
            "a hash vector must not have moved a single contrast score")
