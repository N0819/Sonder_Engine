"""The salience term in ranking, and the fix that was nearly a weight increase.

`search_memories` adds `0.08 * effective_importance(mem)` to every fused score.
The fire-rate harness showed that number is compressed -- mean 0.674, p10-p90
spread 0.27, 70% of the corpus between 0.6 and 0.8 -- and the plan was to
spread it out so the term could discriminate again.

Replaying 270 real recalls over the live corpus (tools/salience_replay.py)
refuted both halves of that plan:

    the term deleted entirely             35.2% of top-16s change membership
    percentile-normalised to [0,1]        59.6%
    stretched 3x about the mean           47.0%
    respaced inside the bank's own range  15.2%

So the term was never silent -- deleting it moves a third of all results --
and the two obvious ways to "fix the compression" move retrieval MORE than
deleting it does. Values occupy a 0.27-wide band, so mapping them onto [0,1]
multiplies this one term's influence by ~3.7 without reordering a single
memory. That is a weight change disguised as a normalisation, and it would let
salience out-argue semantic match.

`_rank_normalized_importance` is what survives: rank-normalise inside the
bank's OWN p10-p90, so ordering and influence budget are both untouched and
only the spacing moves. The defect it actually fixes is that this term's
discrimination currently depends on how the minting model happened to
distribute its numbers -- a bank minted at 0.70 +/- 0.03 has a silent salience
term and a bank spanning 0.4-0.9 has a loud one, for a reason with nothing to
do with the story.

These tests pin the three properties that make it safe: same order, same
budget, and silence where there is nothing to say.
"""

from __future__ import annotations

import pytest

from memory import _rank_normalized_importance


def _bank(*values):
    return {i: {"id": i, "importance": v, "salience": v}
            for i, v in enumerate(values)}


def _out(*values):
    return _rank_normalized_importance(_bank(*values))


class TestOrderIsPreserved:
    """The whole safety argument. Respacing must not promote anything past
    anything -- if it reorders, it is not a respacing, it is a different
    ranking signal wearing the name."""

    def test_a_typical_compressed_bank_keeps_its_order(self):
        raw = [0.62, 0.71, 0.68, 0.75, 0.59, 0.70, 0.66]
        out = _out(*raw)
        by_raw = sorted(range(len(raw)), key=lambda i: raw[i])
        by_new = sorted(range(len(raw)), key=lambda i: out[i])
        assert by_raw == by_new

    def test_a_revised_importance_still_outranks_its_neighbours(self):
        """`effective_importance` prefers revised importance over minted
        salience, and respacing reads it through that same function rather
        than the raw column."""
        bank = {1: {"id": 1, "importance": None, "salience": 0.90},
                2: {"id": 2, "importance": 0.95, "salience": 0.20}}
        out = _rank_normalized_importance(bank)
        assert out[2] > out[1]


class TestTheBudgetIsUnchanged:
    """The measured trap. Percentile-normalising to [0,1] leaves every rank
    identical and still moves retrieval more than deleting the term, because
    it silently triples what the term is worth."""

    def test_output_stays_inside_the_banks_own_range(self):
        raw = [0.55, 0.60, 0.65, 0.70, 0.72, 0.75, 0.78, 0.80, 0.82, 0.85]
        out = _out(*raw)
        ordered = sorted(raw)
        lo = ordered[int(len(ordered) * 0.10)]
        hi = ordered[int(len(ordered) * 0.90)]
        assert min(out.values()) == pytest.approx(lo)
        assert max(out.values()) == pytest.approx(hi)

    def test_it_does_not_reach_zero_or_one(self):
        """Which is exactly what the rejected `spread` arm did, and why it
        moved 59.6% of top-16s."""
        out = _out(*[0.60 + i * 0.01 for i in range(20)])
        assert min(out.values()) > 0.5
        assert max(out.values()) < 0.9

    def test_a_wide_bank_keeps_its_width(self):
        """Respacing must not COMPRESS an already well-spread bank either --
        the budget is pinned to whatever range the bank occupies, in both
        directions."""
        out = _out(*[0.10 * i for i in range(11)])
        assert max(out.values()) - min(out.values()) > 0.7


class TestSilenceWhereThereIsNothingToSay:
    def test_a_flat_bank_stays_flat(self):
        """If the minting model gave no discrimination there is none to
        recover, and inventing an ordering by row id would be worse than the
        compression this fixes."""
        out = _out(0.7, 0.7, 0.7, 0.7, 0.7)
        assert set(out.values()) == {0.7}

    def test_near_flat_does_not_get_stretched_to_the_horizon(self):
        out = _out(*([0.70] * 9 + [0.71]))
        assert max(out.values()) - min(out.values()) <= 0.01 + 1e-9

    def test_ties_share_a_rank(self):
        """Two memories minted at the same salience are not distinguishable
        by this term, and must not become so."""
        out = _out(0.5, 0.8, 0.8, 0.9)
        assert out[1] == out[2]

    def test_a_single_memory_is_returned_untouched(self):
        assert _out(0.63) == {0: 0.63}

    def test_an_empty_bank_does_not_raise(self):
        assert _rank_normalized_importance({}) == {}


class TestItActuallySpreadsTheCompressedCase:
    def test_the_live_shape_gains_discrimination(self):
        """The corpus shape: 70% of rows inside a 0.2-wide band. Before, two
        adjacent memories in that band differ by hundredths; after, the band
        occupies the bank's full range and the term can tell them apart --
        without the term as a whole being worth any more than it was."""
        raw = ([0.45] * 5 + [0.62, 0.64, 0.66, 0.68, 0.70, 0.72, 0.74]
               + [0.88] * 3)
        out = _out(*raw)
        middle = [out[i] for i in range(5, 12)]
        assert max(middle) - min(middle) > (max(raw[5:12]) - min(raw[5:12]))

    def test_two_banks_minted_differently_end_up_comparable(self):
        """The defect in one assertion. A cautious minting model and a
        generous one produce the same discrimination after respacing, where
        before one of them had almost none."""
        tight = _out(*[0.69 + i * 0.005 for i in range(10)])
        loose = _out(*[0.30 + i * 0.06 for i in range(10)])
        tight_steps = sorted(tight.values())
        loose_steps = sorted(loose.values())
        def normalised_gaps(values):
            span = values[-1] - values[0]
            return [(b - a) / span for a, b in zip(values, values[1:])]
        assert normalised_gaps(tight_steps) == pytest.approx(
            normalised_gaps(loose_steps))


def test_ranking_reads_the_respaced_value_not_the_raw_one():
    """A regression guard on the wiring rather than the maths: the fused loop
    must consume `_rank_normalized_importance`, or all of the above is a
    well-tested function nothing calls."""
    import inspect

    import memory
    src = inspect.getsource(memory.search_memories)
    assert "ranked_importance = _rank_normalized_importance(memories)" in src
    assert "fused[mid] += 0.08 * ranked_importance[mid]" in src
    assert "0.08 * effective_importance(mem)" not in src
