"""Familiarity is ONE scale, read through one function.

Review 2026-09-07 finding B17. "How well do these two know each other" was
answered twice: `charter_social.familiarity` divided the holder's own
`served_beside` tally by `TIE_SATURATION = 200` for the tie label, the
`close` formation gate and the promotion payload, while
`charter_practice._between` divided windows-plus-occasions by its own
`FAMILIAR_SATURATION = 250.0` for every affordance's utility. Same pair, two
numbers, and the tie constant's own comment already said why that is a
defect -- it was hoisted out of `charter_promote` precisely because "two
copies of a tuned constant is how they drift".

The rule these tests hold: the practice layer has no scale of its own. It
calls `familiarity()` with its occasion rows folded in as the `occasions`
term, so a pair reads the same familiarity to an affordance as it does to a
tie.
"""

from __future__ import annotations

from world import charter_practice
from world.charter import TIE_SATURATION, entanglement, familiarity


def _charter(*, shared=0, occasions=0):
    """Two bodies, a co-presence tally and a diary, and nothing else.

    Nothing else matters: with no judgments, no commitments and no claims,
    `entanglement` is `familiar + |affect| + debt + owed + grievances` with
    every term but the first at zero, so it reports the practice layer's
    familiarity exactly.
    """
    rows = [{"kind": "acquaintance", "other": "bo", "at_hours": float(i)}
            for i in range(int(occasions))]
    return {
        "bodies": {"ada": {"name": "Ada", "place": "galley"},
                   "bo": {"name": "Bo", "place": "galley"}},
        "minds": {}, "needs": {}, "figures": {}, "clock_hours": 100.0,
        "experiences": {"ada": rows},
        "served_beside": {"ada": {"bo": int(shared)}},
        "judgments": {}, "commitments": {},
    }


class TestOneScale:

    def test_practice_reads_the_tie_layer_number(self):
        """Half the saturation is half the familiarity on BOTH sides.

        Before B17 this pair read 0.5 to a tie and 0.4 to an affordance.
        """
        shared = TIE_SATURATION // 2
        expected = familiarity({"ada": {"bo": shared}}, "ada", "bo")
        assert expected == 0.5
        assert entanglement(_charter(shared=shared), "ada", ["bo"]) == expected

    def test_occasions_fold_into_the_same_scale(self):
        """A diary occasion and a window stood beside are one unit.

        The practice layer's claim, kept -- it now lives in `familiarity`'s
        `occasions` term rather than in a second constant.
        """
        half = TIE_SATURATION // 2
        by_windows = entanglement(_charter(shared=half), "ada", ["bo"])
        by_rows = entanglement(_charter(occasions=half), "ada", ["bo"])
        split = entanglement(
            _charter(shared=half // 2, occasions=half - half // 2),
            "ada", ["bo"])
        assert by_windows == by_rows == split
        assert familiarity({}, "ada", "bo", occasions=half) == by_rows

    def test_a_life_together_saturates_on_both_sides(self):
        """At `TIE_SATURATION` of anything, familiarity is 1.0 everywhere."""
        assert familiarity({"ada": {"bo": TIE_SATURATION}}, "ada", "bo") == 1.0
        assert entanglement(
            _charter(shared=TIE_SATURATION), "ada", ["bo"]) == 1.0
        assert entanglement(
            _charter(shared=TIE_SATURATION * 9), "ada", ["bo"]) == 1.0
        assert entanglement(
            _charter(occasions=TIE_SATURATION + 1), "ada", ["bo"]) == 1.0

    def test_the_practice_layer_owns_no_saturation_of_its_own(self):
        """The class, not the instance: a second scale cannot come back by
        being spelled differently. `charter_practice` may name a saturation
        only by calling the function that holds one."""
        assert [n for n in dir(charter_practice) if "SATURATION" in n] == []

    def test_a_stranger_is_zero_to_everybody(self):
        assert familiarity({}, "ada", "bo") == 0.0
        assert entanglement(_charter(), "ada", ["bo"]) == 0.0
