"""Hard mode: `PlayerAuthorityMode`, enforced.

The enum has named this ladder since the vocabulary was written and was
consumed nowhere -- one site in the whole tree, the definition. `Design.md`
§ Hard mode and `UNBUILT.md` §2.4 settled what each rung grants and the two
design notes that had to hold before it could be built:

  1. a refused assertion must not silently vanish -- the player wrote it for a
     reason, and dropping player text is the one thing this engine's authority
     contract has never done;
  2. the mode is per-chat and a mid-story change is recorded, because changing
     it changes what the earlier turns meant.

Both are pinned here. So is the property that matters most for everyone who
does not want hard mode: `world_author` is today's behaviour exactly, so an
existing story means the same thing tomorrow as it did yesterday.
"""

from __future__ import annotations

import copy

import pytest

from agents.common import apply_player_authority
from scene import (PLAYER_AUTHORITY_GRANTS, PLAYER_AUTHORITY_MODES,
                   normalize_player_authority, player_authority,
                   set_player_authority)

PLAYER = "Sam"


def _beat(*, own_body=False, own_effect=False, world=False):
    """One interpreted beat carrying whichever kinds of claim were asked for.

    Claim ids follow `_extract_authority_claims`' own spelling -- the index is
    the sequence position and the `:event` suffix marks an actor-less world
    assertion -- because that spelling is what the downgrade reads to find the
    element behind a claim.
    """
    sequence, claims = [], []
    if own_body:
        sequence.append({"type": "action", "attempt": "raise my hand",
                         "targets": [], "commitment": "asserted",
                         "asserted_effects": [{"description": "my hand is up"}]})
        claims.append({"claim_id": f"claim:{len(sequence) - 1}:0",
                       "scope": "effect", "subject_id": PLAYER,
                       "predicate": "my hand is up",
                       "source_text": "I raise my hand"})
    if own_effect:
        sequence.append({"type": "action", "attempt": "pick the lock",
                         "targets": ["the door"], "commitment": "asserted",
                         "asserted_effects": [{"description": "the lock opens"}]})
        claims.append({"claim_id": f"claim:{len(sequence) - 1}:0",
                       "scope": "effect", "subject_id": "the door",
                       "predicate": "the lock is open",
                       "source_text": "I pick the lock and it opens"})
    if world:
        sequence.append({"type": "event",
                         "description": "two guards come around the corner"})
        claims.append({"claim_id": f"claim:{len(sequence) - 1}:event",
                       "scope": "effect", "subject_id": "guards",
                       "predicate": "two guards come around the corner",
                       "source_text": "two guards come around the corner"})
    return {"sequence": sequence, "flow": {"authority_claims": claims}}


def _scopes(out):
    return [c["scope"] for c in out["flow"]["authority_claims"]]


def _commitments(out):
    return [e.get("commitment") for e in out["sequence"]
            if e["type"] == "action"]


# --------------------------------------------------------------- the ladder


class TestTheLadder:
    """Each rung grants exactly what `Design.md`'s table says it does."""

    def test_world_author_grants_everything(self):
        out = _beat(own_body=True, own_effect=True, world=True)
        assert apply_player_authority(out, "world_author", PLAYER) == []
        assert _scopes(out) == ["effect", "effect", "effect"]

    def test_explicit_outcomes_refuses_world_authorship_only(self):
        out = _beat(own_body=True, own_effect=True, world=True)
        records = apply_player_authority(out, "explicit_outcomes", PLAYER)

        assert [r["kind"] for r in records] == ["world"]
        assert _scopes(out) == ["effect", "effect", "intent"]

    def test_actor_only_refuses_every_outcome_beyond_the_players_body(self):
        out = _beat(own_body=True, own_effect=True, world=True)
        records = apply_player_authority(out, "actor_only", PLAYER)

        assert [r["kind"] for r in records] == ["own_effect", "world"]
        assert _scopes(out) == ["effect", "intent", "intent"]

    def test_the_players_own_body_is_the_floor_under_every_mode(self):
        """"Attempts, speech, and immediate bodily conduct" is not a grant.

        No mode takes it, so the strictest one still lets a player raise their
        own hand without asking the Director's permission.
        """
        for mode in PLAYER_AUTHORITY_MODES:
            out = _beat(own_body=True)
            assert apply_player_authority(out, mode, PLAYER) == []
            assert _scopes(out) == ["effect"]

    def test_an_intent_claim_is_untouched_by_any_mode(self):
        """A contestable intent was already the Director's to resolve, so
        there is nothing for a mode to take away."""
        out = _beat(own_effect=True)
        out["flow"]["authority_claims"][0]["scope"] = "intent"

        for mode in PLAYER_AUTHORITY_MODES:
            assert apply_player_authority(copy.deepcopy(out), mode, PLAYER) == []


# ------------------------------------------------------- both representations


class TestBothRepresentations:
    """The claim and the sequence element must move together.

    They are two representations of one declaration. Move the claim alone and
    the downgrade is invisible where it counts: the claim stops being
    non-rejectable while the element still says the effect already happened,
    and the beat is resolved from the element.
    """

    def test_the_sequence_element_becomes_contestable_with_its_claim(self):
        out = _beat(own_effect=True)
        apply_player_authority(out, "actor_only", PLAYER)

        assert _commitments(out) == ["contestable"]

    def test_an_element_whose_claim_survived_stays_asserted(self):
        out = _beat(own_body=True, own_effect=True)
        apply_player_authority(out, "actor_only", PLAYER)

        assert _commitments(out) == ["asserted", "contestable"]

    def test_contestable_is_what_lets_the_cast_contest_it(self):
        """Not a bookkeeping detail: `_requires_reaction_phase` reads exactly
        this field, so hard mode without it is hard mode the cast cannot
        participate in -- the character it was done to never gets a reaction,
        which is most of what "the Director may refuse" is supposed to buy."""
        from agents.common import _requires_reaction_phase

        out = _beat(own_effect=True)
        out["sequence"][0]["targets"] = [7]
        assert not _requires_reaction_phase(out["sequence"][0], {7}, set())

        apply_player_authority(out, "actor_only", PLAYER)
        assert _requires_reaction_phase(out["sequence"][0], {7}, set())


# ------------------------------------------------------- nothing disappears


class TestNothingDisappears:
    """Design note 1. The player wrote it; they are owed an answer, not a gap."""

    def test_a_refused_assertion_is_still_in_the_sequence(self):
        out = _beat(world=True)
        before = copy.deepcopy(out["sequence"])
        apply_player_authority(out, "actor_only", PLAYER)

        assert out["sequence"] == before

    def test_a_refused_claim_is_downgraded_rather_than_dropped(self):
        out = _beat(world=True)
        apply_player_authority(out, "actor_only", PLAYER)

        claims = out["flow"]["authority_claims"]
        assert len(claims) == 1
        assert claims[0]["predicate"] == "two guards come around the corner"

    def test_the_record_carries_the_players_own_words(self):
        """What the Director is asked to answer has to be answerable. A record
        naming a claim id and nothing else describes a refusal nobody can act
        on -- least of all the reader, who never sees claim ids."""
        out = _beat(world=True)
        record = apply_player_authority(out, "actor_only", PLAYER)[0]

        assert record["source_text"] == "two guards come around the corner"
        assert record["predicate"] == "two guards come around the corner"
        assert record["mode"] == "actor_only"
        assert record["kind"] == "world"


# ------------------------------------------------------------ the resolve seam


class TestTheResolveSeam:
    """A downgraded claim stops being non-rejectable, which is the point.

    `_player_claim_findings` is what makes an asserted effect claim binding:
    it must be encoded in the diff, and a resolve that marks it rejected or
    failed is a contract violation. Hard mode is that rule ceasing to apply.
    """

    def test_an_asserted_claim_may_not_be_rejected(self):
        from agents.director import _player_claim_findings

        interp = _beat(world=True)
        out = {"claim_dispositions": [
            {"claim_id": "claim:0:event", "status": "rejected"}]}
        _, _, contract = _player_claim_findings(
            out, {}, interp, [], {}, player_input="two guards")

        assert any("may not be rejected" in w for w in contract)

    def test_a_downgraded_claim_may_be_rejected_freely(self):
        from agents.director import _player_claim_findings

        interp = _beat(world=True)
        apply_player_authority(interp, "actor_only", PLAYER)
        out = {"claim_dispositions": [
            {"claim_id": "claim:0:event", "status": "rejected"}]}
        omissions, _, contract = _player_claim_findings(
            out, {}, interp, [], {}, player_input="two guards")

        assert contract == []
        assert omissions == []


# ---------------------------------------------------------------- the setting


class TestTheSetting:
    """Design note 2: per chat, and a mid-story change is recorded."""

    def test_the_default_is_todays_behaviour(self, temp_db):
        from tests.test_extensions import _chat

        assert player_authority(_chat(temp_db))["mode"] == "world_author"

    def test_the_mode_is_scoped_to_one_story(self, temp_db):
        from tests.test_extensions import _chat

        first, second = _chat(temp_db), _chat(temp_db)
        set_player_authority(first, "actor_only")

        assert player_authority(first)["mode"] == "actor_only"
        assert player_authority(second)["mode"] == "world_author"

    def test_a_change_is_recorded_with_the_turn_it_happened_on(self, temp_db):
        """Changing the dial changes what the earlier turns MEANT. A beat where
        the player asserted a world fact and got it reads as a defect once the
        story is in `actor_only`, and this record is the only thing that can
        explain it."""
        from tests.test_extensions import _chat

        chat_id = _chat(temp_db)
        set_player_authority(chat_id, "explicit_outcomes", turn_idx=12)
        set_player_authority(chat_id, "actor_only", turn_idx=40)

        assert player_authority(chat_id)["changes"] == [
            {"turn_idx": 12, "mode": "explicit_outcomes"},
            {"turn_idx": 40, "mode": "actor_only"},
        ]

    def test_reselecting_the_same_mode_records_nothing(self, temp_db):
        """A host panel that saves on every render must not turn the history
        into noise."""
        from tests.test_extensions import _chat

        chat_id = _chat(temp_db)
        set_player_authority(chat_id, "actor_only", turn_idx=3)
        set_player_authority(chat_id, "actor_only", turn_idx=4)

        assert len(player_authority(chat_id)["changes"]) == 1

    def test_an_unreadable_stored_value_falls_back_rather_than_raising(
            self, temp_db):
        from db import wset

        from tests.test_extensions import _chat

        chat_id = _chat(temp_db)
        wset(chat_id, "player_authority", {"mode": "hard"})

        assert player_authority(chat_id)["mode"] == "world_author"

    def test_normalization_accepts_only_the_named_rungs(self):
        assert normalize_player_authority("actor_only") == "actor_only"
        assert normalize_player_authority("ACTOR_ONLY") == "actor_only"
        assert normalize_player_authority("hard") == "world_author"
        assert normalize_player_authority(None) == "world_author"

    def test_the_enum_and_the_config_name_the_same_rungs(self):
        """Two lists of modes is one list that disagrees with itself."""
        from schemas import PlayerAuthorityMode

        assert (sorted(m.value for m in PlayerAuthorityMode)
                == sorted(PLAYER_AUTHORITY_MODES)
                == sorted(PLAYER_AUTHORITY_GRANTS))


# ------------------------------------------------------------------- wiring


class TestWiring:
    def test_director_interpret_consumes_the_mode(self):
        """The enum was consumed NOWHERE for the whole life of the vocabulary.
        This is the test that says it is consumed now."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_interpret)
        assert 'player_authority(chat["id"])["mode"]' in source
        assert "apply_player_authority(out, _authority_mode, p_name)" in source

    def test_the_downgrades_reach_the_same_beats_resolve(self):
        """`tell_director` reaches the NEXT beat, which is a beat too late for
        the player reading this one -- and under a restricted mode it would
        repeat every beat as past-tense feedback about a settled one. So the
        refusal rides the resolve payload, and this stage does not also use
        that channel."""
        import inspect

        import agents.director as director

        assert '"downgraded_assertions": interp.get("authority_downgrades")' \
            in inspect.getsource(director.director_resolve)

        interpret = inspect.getsource(director.director_interpret)
        block = interpret[interpret.index("_downgrades = apply_player_authority"):]
        # The CALL, not the word: the comment there explains why the channel is
        # the wrong one, and a test that cannot tell an explanation from a use
        # would fail the moment somebody wrote the reason down.
        assert "ctx.tell_director(" not in block[:block.index("# Detect contested")]

    def test_the_declaration_stays_absolute_in_every_mode(self):
        """What the player SAID and ATTEMPTED is fixed under hard mode too.
        The mode moves what they asserted about OUTCOMES, and nothing else --
        a hard mode that let the Director rewrite the player's words would be
        a worse violation than the one it set out to fix."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)
        assert '"ABSOLUTE": True' in source
