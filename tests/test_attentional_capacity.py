"""How much a mind holds at once, made authorable.

`_WANT_CAP = 3` and `_INTENT_CAP = 4` were global constants, identical for
every character ever written. Measured over the live corpus
(`tools/fire_rates.py`):

    wants at cap (3)         77.55%   38/49   mean 2.63
    intentions at cap (4)    34.69%   17/49   mean 2.65

A cap that binds three quarters of all minds on the state they persist is not
a safety valve catching an outlier. It is the shape of every character's
attention, authored once, by whoever picked the number 3.

The precedent is `theory_of_mind.sheet_capacity`, which scales the hypothesis
sheet 5 -> 1 with cognitive absorption on exactly this reasoning: not "your
beliefs are worth less" but "you can only keep so much in mind at once". This
extends it from a transient state to an authored disposition, because a
single-minded character and a character who juggles are different people.

Three things this file exists to hold:

**Projects stay off the ladder.** `PROJECT_CAP` is a DRAMATIC limit, not a
cognitive one -- with two slots, a third costs something given up by name. A
"capable" character allowed six projects is not more capable; they have lost
the displacement rule that makes a project mean anything.

**The default is what shipped.** CLAUDE.md records twice that an unset
psychology field fails silently and surfaces fifty beats later as a character
behaving wrongly for no visible reason. This dial cannot do that: unset
resolves to the pair every existing story already ran on.

**Unset is stored as unset.** The first version of this backfilled `ordinary`
into the sheet on normalize, which made "the author chose the middle" and
"nobody has ever seen this field" the same stored value -- and silently killed
the import warning written specifically to stop it being invisible. The
warning was dead on the only path that calls it.
"""

from __future__ import annotations

import affect
import character_schema
import importers
from affect import (CAPACITY_DEFAULT, CAPACITY_LADDER, apply_intent_ops,
                    capacity_caps, normalize_capacity, normalize_wants)


def _want(text, urgency, serves="drive"):
    return {"want": text, "urgency": urgency, "serves": serves}


# Deliberately unrelated to each other: `normalize_wants` and
# `apply_intent_ops` merge near-duplicates at claim_similarity >= 0.4, so
# "thing one"/"thing two" fixtures collapse into one entry and every cap test
# above them passes for the wrong reason.
DISTINCT = [
    "get out of this room alive",
    "find out who sent the letter",
    "keep the child from seeing the body",
    "eat something before the fever returns",
    "reach the harbour by first light",
    "make him admit what he did in Tangier",
]


def _wants(n):
    return [_want(DISTINCT[i], 0.9 - i * 0.05) for i in range(n)]


class TestTheLadder:
    def test_ordinary_is_exactly_what_shipped(self):
        """The whole safety argument for every existing story."""
        assert capacity_caps("ordinary") == (affect._WANT_CAP,
                                             affect._INTENT_CAP)
        assert capacity_caps(None) == (affect._WANT_CAP, affect._INTENT_CAP)
        assert CAPACITY_DEFAULT == "ordinary"

    def test_it_runs_narrow_to_wide_without_a_gap(self):
        pairs = [capacity_caps(rung) for rung in CAPACITY_LADDER]
        assert pairs == sorted(pairs)
        for (w1, i1), (w2, i2) in zip(pairs, pairs[1:]):
            assert w2 == w1 + 1 and i2 == i1 + 1

    def test_a_narrow_mind_holds_one_thing(self):
        assert capacity_caps("narrow") == (1, 2)

    def test_an_unknown_rung_is_the_default_rather_than_an_error(self):
        """A capacity is authored prose in a JSON file. A typo must land the
        character on the middle rung, never raise mid-beat."""
        for junk in ("enormous", "", None, 3, [], "  NARROW  "):
            assert normalize_capacity(junk) in CAPACITY_LADDER
        assert normalize_capacity("  NARROW  ") == "narrow"
        assert normalize_capacity("enormous") == CAPACITY_DEFAULT

    def test_every_rung_says_what_it_is_like_to_be(self):
        """The payload shows the character this string. A rung with no
        description would surface as a bare number and read as a budget."""
        for rung in CAPACITY_LADDER:
            assert affect.CAPACITY_DESCRIPTIONS[rung].strip()


class TestAbsorptionNarrowsIt:
    def test_a_body_at_the_ceiling_takes_one_slot(self):
        assert capacity_caps("wide", 0.9) == (4, 5)
        assert capacity_caps("ordinary", 0.95) == (2, 3)

    def test_it_never_falls_below_one(self):
        """A want cap of zero would mean a character in pain wants nothing,
        which is the opposite of what pain does."""
        assert capacity_caps("narrow", 1.0) == (1, 1)

    def test_ordinary_discomfort_changes_nothing(self):
        assert capacity_caps("ordinary", 0.0) == capacity_caps("ordinary", 0.7)

    def test_a_malformed_absorption_is_treated_as_none(self):
        assert capacity_caps("ordinary", None) == (3, 4)
        assert capacity_caps("ordinary", "very") == (3, 4)


class TestTheCapsActuallyBind:
    def test_wants_are_culled_to_the_authored_number(self):
        kept, _e, _s = normalize_wants(_wants(5), set(), want_cap=1)
        assert len(kept) == 1

    def test_the_most_urgent_want_is_the_one_kept(self):
        """Culling by anything else would make a narrow character arbitrary
        rather than single-minded."""
        wants = [_want("idle curiosity", 0.2), _want("get out alive", 0.95)]
        kept, _e, _s = normalize_wants(wants, set(), want_cap=1)
        assert kept[0]["want"] == "get out alive"

    def test_omitting_the_cap_is_the_ordinary_rung(self):
        assert len(normalize_wants(_wants(6), set())[0]) == affect._WANT_CAP

    def test_a_wide_mind_keeps_more(self):
        kept, _e, _s = normalize_wants(_wants(6), set(), want_cap=5)
        assert len(kept) == 5

    def test_intentions_are_capped_and_the_rejection_names_the_number(self):
        ops = [{"op": "add", "intent": t} for t in DISTINCT[:4]]
        result, warnings = apply_intent_ops([], ops, 1, lambda op: True,
                                            intent_cap=2)
        assert sum(1 for i in result if i["status"] == "active") == 2
        assert any("cap 2 active" in w for w in warnings)

    def test_omitting_the_intent_cap_is_the_ordinary_rung(self):
        ops = [{"op": "add", "intent": t} for t in DISTINCT]
        result, _w = apply_intent_ops([], ops, 1, lambda op: True)
        assert sum(1 for i in result
                   if i["status"] == "active") == affect._INTENT_CAP


class TestProjectsAreNotOnTheLadder:
    def test_the_project_cap_is_still_a_single_constant(self):
        assert affect.PROJECT_CAP == 2
        assert "PROJECT_CAP" not in str(affect._CAPACITY_CAPS)

    def test_capacity_caps_returns_only_two_numbers(self):
        """If a third ever appears here, the displacement rule that makes a
        project cost something has been quietly put on a dial."""
        assert len(capacity_caps("wide")) == 2

    def test_adopting_a_third_project_is_still_refused_at_every_rung(self):
        live = [{"id": "p1", "project": "a", "status": "active"},
                {"id": "p2", "project": "b", "status": "active"}]
        _p, _f, warnings = affect.apply_project_ops(
            live, [], [{"op": "adopt", "project": "keep the village alive",
                        "about": "world",
                        "satisfied_when": "spring comes and it still stands"}],
            5)
        assert any("both slots full" in w for w in warnings)


class TestUnsetIsStoredAsUnset:
    def test_normalize_does_not_backfill_a_rung(self):
        """The bug this class exists for. Backfilling `ordinary` made an
        unauthored capacity indistinguishable from an authored middle, and the
        import warning below never fired on any card in existence."""
        sheet = character_schema.normalize_character_data(
            {"name": "X", "psychology": {}})
        assert sheet["psychology"]["capacity"] == ""

    def test_an_authored_rung_survives_normalize(self):
        sheet = character_schema.normalize_character_data(
            {"name": "X", "psychology": {"capacity": "NARROW"}})
        assert sheet["psychology"]["capacity"] == "narrow"

    def test_a_junk_rung_normalises_to_unset_rather_than_to_the_middle(self):
        """So the author is warned about it instead of silently landed on a
        rung they did not pick."""
        sheet = character_schema.normalize_character_data(
            {"name": "X", "psychology": {"capacity": "enormous"}})
        assert sheet["psychology"]["capacity"] == ""

    def test_unset_still_behaves_exactly_as_before(self):
        sheet = character_schema.normalize_character_data(
            {"name": "X", "psychology": {}})
        assert capacity_caps(sheet["psychology"]["capacity"]) == (3, 4)


class TestTheAuthorIsTold:
    def _warnings(self, psychology):
        base = {"name": "X", "initial_state": {"goals": [{"goal": "g"}]},
                "psychology": dict({"drive": {"essence": "to know"}},
                                   **psychology)}
        return importers.character_import_warnings(
            character_schema.normalize_character_data(base))

    def test_an_unset_capacity_is_named_at_import(self):
        """Not a defect -- the default is correct. It is named because nobody
        looks for a field they do not know exists, and a character who should
        be single-minded is otherwise authored at the middle rung forever by
        omission."""
        assert any("capacity" in w for w in self._warnings({}))

    def test_an_authored_capacity_is_not_warned_about(self):
        assert not any("capacity" in w for w in
                       self._warnings({"capacity": "narrow"}))

    def test_the_warning_names_the_rungs_the_author_can_choose(self):
        warning = next(w for w in self._warnings({}) if "capacity" in w)
        for rung in CAPACITY_LADDER:
            assert rung in warning


def test_the_character_is_told_its_own_ceiling():
    """Commit culls past the cap deterministically either way. A character
    asked for three wants whose third is then dropped has had a decision taken
    from it without being told the decision existed."""
    import inspect

    from agents import character
    src = inspect.getsource(character)
    assert '"attention": {' in src
    assert '"wants": _want_cap' in src
    assert '"intentions": _intent_cap' in src

    import prompts
    block = prompts.DEFAULT_PROMPTS["character"]
    assert "self.attention" in block
    assert "self.attention.wants beat wants" in block


def test_commit_reads_the_same_pair_the_payload_showed():
    """Two computations of one number is how they drift. Both sides resolve it
    through `affect.capacity_caps` from the sheet plus absorption."""
    import inspect

    import commit
    src = inspect.getsource(commit)
    assert "affect.capacity_caps(" in src
    assert "want_cap=_want_cap" in src
    assert "intent_cap=_intent_cap" in src
