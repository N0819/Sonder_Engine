"""The diversity pass picks the same memories, having stopped re-deriving
what it already knew.

`search_memories` finishes by walking a greedy maximal-marginal-relevance
selection: each round takes the candidate with the best relevance minus its
worst overlap with everything already chosen. The overlap term used to be
rebuilt from scratch every round -- 48,668 `_memory_similarity` evaluations
on chat 117's 401-row bank at k=24, two thirds of the whole retrieval call
(review 2026-09-07, C15). It is now carried forward as a running maximum,
which is 4,308 evaluations for the identical answer.

"Identical" is an algebraic claim -- a max over a set is the max of the
running value and the new member -- so this file tests it as one: the shipped
`_mmr_select` against a reference that rebuilds the term the old way, over
randomised banks with both kinds of similarity in play (real vectors, and the
token-jaccard fallback a bank with no usable vectors falls to). The
byte-for-byte diff of the ranked ids on the real bench bank is the other half
of the evidence and lives in the review, not here.
"""
from __future__ import annotations

import random

import numpy as np

from mind import memory as mr


def _reference_select(memories, fused, k):
    """The pass as it was written: the redundancy term rebuilt every round."""
    ranked = sorted(memories, key=lambda x: fused[x], reverse=True)
    selected = []
    pool = ranked[:max(k * 8, 40)]
    while pool and len(selected) < k:
        best_id, best = None, float("-inf")
        for mid in pool:
            rel = fused[mid]
            red = max((mr._memory_similarity(memories[mid], memories[s])
                       for s in selected), default=0.0)
            mmr = 0.82 * rel - 0.18 * red
            if mmr > best:
                best = mmr
                best_id = mid
        selected.append(best_id)
        pool.remove(best_id)
    return selected


def _bank(rng, n, *, vectors, dims=8):
    """`n` memories, with or without the vectors the cosine branch needs."""
    words = ["lantern", "rope", "salt", "hinge", "smoke", "tide", "coin",
             "ash", "glass", "wire", "bone", "rain"]
    memories, fused = {}, {}
    for i in range(1, n + 1):
        body = " ".join(rng.choice(words) for _ in range(6))
        mem = {"id": i, "gist": body[:20], "content": body,
               "turn_idx": i, "category": "episode"}
        if vectors:
            v = rng.gauss
            arr = np.array([v(0.0, 1.0) for _ in range(dims)], dtype=np.float32)
            arr /= np.linalg.norm(arr) or 1.0
            mem["_vector"] = arr
        else:
            mem["_vector"] = None
        memories[i] = mem
        fused[i] = rng.random()
    return memories, fused


def _ties(rng, n):
    """A bank whose fused scores collide, so tie order is exercised."""
    memories, fused = _bank(rng, n, vectors=False)
    for mid in fused:
        fused[mid] = round(fused[mid], 1)
    return memories, fused


class TestRunningMaximumIsTheSameSelection:
    def test_with_real_vectors(self):
        for seed in range(12):
            rng = random.Random(seed)
            memories, fused = _bank(rng, 60, vectors=True)
            for k in (1, 2, 5, 16, 24):
                assert (mr._mmr_select(memories, fused, k)
                        == _reference_select(memories, fused, k)), (seed, k)

    def test_with_the_token_fallback_no_bank_can_avoid(self):
        """No usable vectors: every comparison falls to the jaccard branch,
        which is also the branch the token memo serves."""
        for seed in range(12):
            rng = random.Random(seed)
            memories, fused = _bank(rng, 60, vectors=False)
            for k in (1, 5, 24):
                assert (mr._mmr_select(memories, fused, k)
                        == _reference_select(memories, fused, k)), (seed, k)

    def test_when_the_scores_tie(self):
        """Ties fall to pool order in both, which is what keeps a bank with a
        flat score distribution from being reordered by this change alone."""
        for seed in range(12):
            rng = random.Random(seed)
            memories, fused = _ties(rng, 50)
            for k in (3, 8, 24):
                assert (mr._mmr_select(memories, fused, k)
                        == _reference_select(memories, fused, k)), (seed, k)

    def test_a_bank_smaller_than_k_still_returns_all_of_it(self):
        rng = random.Random(0)
        memories, fused = _bank(rng, 4, vectors=True)
        assert (sorted(mr._mmr_select(memories, fused, 24))
                == sorted(_reference_select(memories, fused, 24)) == [1, 2, 3, 4])

    def test_the_redundancy_term_remembers_every_round_not_just_the_last(self):
        """The one way a running maximum can be written wrongly: keeping the
        similarity against the LAST selection instead of the largest so far.

        Three memories are chosen before the candidate is judged, and the
        candidate's real overlap is with the FIRST of them.
        """
        def axis(i):
            v = np.zeros(5, dtype=np.float32)
            v[i] = 1.0
            return v

        memories = {
            1: {"id": 1, "_vector": axis(0), "gist": "a", "content": "a"},
            2: {"id": 2, "_vector": axis(1), "gist": "b", "content": "b"},
            3: {"id": 3, "_vector": axis(2), "gist": "c", "content": "c"},
            # 4 is 1 over again; 5 shares nothing with anything.
            4: {"id": 4, "_vector": axis(0), "gist": "d", "content": "d"},
            5: {"id": 5, "_vector": axis(3), "gist": "e", "content": "e"},
        }
        fused = {1: 1.00, 2: 0.90, 3: 0.80, 4: 0.75, 5: 0.70}
        got = mr._mmr_select(memories, fused, 4)
        assert got == _reference_select(memories, fused, 4)
        # 4 is a duplicate of 1, which was chosen first; by the fourth round
        # its penalty must still be 1's, not 3's.
        assert got == [1, 2, 3, 5]


class TestTheTokenMemo:
    def test_two_memories_never_share_a_token_set(self):
        cache = {}
        a = {"id": 1, "gist": "the lantern", "content": "guttered in the wind"}
        b = {"id": 2, "gist": "the rope", "content": "held against the tide"}
        assert mr._memory_tokens(a, cache) != mr._memory_tokens(b, cache)
        assert len(cache) == 2
        assert mr._memory_tokens(a, cache) == mr._memory_tokens(a, None)

    def test_a_row_with_no_id_is_never_cached(self):
        """An idless dict would otherwise share one key with every other."""
        cache = {}
        a = {"gist": "the lantern", "content": "guttered"}
        b = {"gist": "the rope", "content": "held"}
        assert mr._memory_tokens(a, cache) != mr._memory_tokens(b, cache)
        assert cache == {}
