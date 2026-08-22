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
from story.scene import (PLAYER_AUTHORITY_GRANTS, PLAYER_AUTHORITY_MODES,
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


# ------------------------------------------------------- what a played beat found


class TestTheInferredSubject:
    """The hole that the first hard-mode story ever played walked straight into.

    `_extract_authority_claims` resolves an asserted effect to the DECLARING
    ACTOR when the action named no targets. That fallback is right for its own
    purpose -- a wave or going rigid stops tripping the resolve seam's 'no
    resolvable subject' note -- and it is not evidence about whose body an
    effect is on. "Named no target" is equally what a world assertion looks
    like once the interpret stage has typed it as an action.

    Both fixtures below are verbatim from that story (2026-08-18, the empty
    house, `actor_only` throughout), and between them they rule out the
    obvious wrong fix: the first has no first person and the second has
    plenty, so any test on the WORDING grants exactly the wrong one.
    """

    GUARDS = {
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": PLAYER, "subject_inferred": True,
        "predicate": "Two guards come around the corner from the stair "
                     "into the front hall",
        "source_text": "Two guards come around the corner from the stair "
                       "into the front hall, boots loud on the stone floor.",
    }
    DOOR = {
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": PLAYER, "subject_inferred": True,
        "predicate": "west door opens, revealing a vault",
        "source_text": "Sam takes the west door's handle and forces the lock, "
                       "causing the vault door to swing open.",
    }

    def test_a_world_assertion_typed_as_an_action_is_not_the_players_body(self):
        """Turn 1. Two guards walked into the world unchallenged: the mode was
        `actor_only`, the claim read subject_id=the player, and the engine
        granted it as bodily conduct."""
        beat = {"sequence": [{"type": "action", "targets": [],
                              "commitment": "asserted"}],
                "flow": {"authority_claims": [dict(self.GUARDS)]}}

        records = apply_player_authority(beat, "actor_only", PLAYER)

        assert [r["kind"] for r in records] == ["own_effect"]
        assert beat["flow"]["authority_claims"][0]["scope"] == "intent"

    def test_an_effect_on_a_door_is_not_the_players_body_either(self):
        """Turn 2, the same fallback, and the reason prose cannot decide it:
        this one is written in the first person and is still about a door."""
        beat = {"sequence": [{"type": "action", "targets": [],
                              "commitment": "asserted"}],
                "flow": {"authority_claims": [dict(self.DOOR)]}}

        records = apply_player_authority(beat, "actor_only", PLAYER)

        assert [r["kind"] for r in records] == ["own_effect"]

    def test_a_subject_the_model_actually_named_is_still_the_players_body(self):
        """The fix withholds a GUESS, not the grant. When the model names the
        player as the effect's target, that is an answer rather than a
        fallback, and `actor_only` still grants it."""
        claim = dict(self.GUARDS, subject_inferred=False)
        beat = {"sequence": [], "flow": {"authority_claims": [claim]}}

        assert apply_player_authority(beat, "actor_only", PLAYER) == []

    def test_the_looser_rungs_are_unchanged_by_it(self):
        """Only `actor_only` tightens. `own_effect` is granted above it, so a
        story on the default reads exactly as it did."""
        for mode in ("explicit_outcomes", "world_author"):
            beat = {"sequence": [], "flow": {
                "authority_claims": [dict(self.DOOR)]}}
            assert apply_player_authority(beat, mode, PLAYER) == [], mode

    def test_the_extractor_marks_what_it_guessed(self):
        """The flag has to be minted where the guess is made, or the claim
        layer is back to inferring from prose."""
        from agents.common import _extract_authority_claims

        sequence = [{
            "type": "action", "attempt": "force the lock", "targets": [],
            "commitment": "asserted",
            "asserted_effects": [{"target_id": None, "kind": "the door opens"},
                                 {"target_id": "vault_door",
                                  "kind": "the vault is open"}],
        }]
        claims = _extract_authority_claims(sequence, "I force the lock",
                                           actor_name=PLAYER)

        assert claims[0]["subject_id"] == PLAYER
        assert claims[0]["subject_inferred"] is True
        assert claims[1]["subject_id"] == "vault_door"
        assert claims[1]["subject_inferred"] is False


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
        from core.db import wset

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
        from llm.schemas import PlayerAuthorityMode

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


class TestTheHostControl:
    """The menu the mode is actually chosen in.

    It sits in **Genre & style**, beside genre, tone and weather severity,
    because it decides what a DECLARATION MEANS in this story -- a question
    about the fiction, not about how much happens off screen. The panel reads
    the ladder from the engine rather than carrying its own copy, so a rung
    added later cannot go missing from the menu.
    """

    def test_the_route_serves_the_ladder_and_records_a_change(self, temp_db):
        from fastapi.testclient import TestClient

        from web import app as app_module
        from web import guest_access as guest

        from tests.test_extensions import _chat

        chat_id = _chat(temp_db)
        guest.reset_host_account()
        try:
            with TestClient(app_module.app) as client:
                assert client.post(
                    "/api/auth/setup",
                    json={"username": "host", "password": "pw12345"}
                ).status_code == 200

                got = client.get(f"/api/chats/{chat_id}/player_authority").json()
                assert got["mode"] == "world_author"
                assert [m["value"] for m in got["modes"]] == list(
                    PLAYER_AUTHORITY_MODES)

                put = client.put(f"/api/chats/{chat_id}/player_authority",
                                 json={"mode": "actor_only", "turn_idx": 4})
                assert put.status_code == 200
                assert put.json()["changes"] == [
                    {"turn_idx": 4, "mode": "actor_only"}]

                # Refused rather than normalized: the setter falls back to the
                # default on an unreadable value, and a typo landing on
                # `world_author` is the one failure this feature exists to
                # prevent.
                bad = client.put(f"/api/chats/{chat_id}/player_authority",
                                 json={"mode": "hard"})
                assert bad.status_code == 400
                assert client.get(
                    f"/api/chats/{chat_id}/player_authority"
                ).json()["mode"] == "actor_only"
        finally:
            guest.reset_host_account()

    def test_the_menu_reads_the_ladder_from_the_engine(self):
        """A mode list maintained in two places is one that disagrees with
        itself the first time a rung moves."""
        from pathlib import Path

        settings = (Path(__file__).resolve().parents[1]
                    / "static/js/ui-next/story-tools/style.js").read_text(encoding="utf-8")
        assert "/player_authority`" in settings
        assert "player_authority?.modes" in settings

    def test_the_enforcer_reads_the_ladder_through_its_one_normalizer(self):
        """`apply_player_authority` had its own second copy of the rule --
        `str(mode or "world_author")` and a dict `.get` with the top rung as
        the fallback -- so a stored mode in any other case or with stray
        whitespace missed the table and silently granted the WHOLE ladder.

        `normalize_player_authority` (story/scene.py) owns this vocabulary;
        it is what `player_authority` runs on the stored mode and on every
        history entry. One home, so tightening a story cannot be undone by a
        spelling.
        """
        for spelling in ("Actor_Only", "ACTOR_ONLY", "  actor_only  "):
            beat = _beat(own_effect=True)
            records = apply_player_authority(beat, spelling, PLAYER)
            assert [r["kind"] for r in records] == ["own_effect"], spelling

    def test_an_unreadable_mode_still_falls_to_the_default(self):
        """The fallback itself is unchanged and deliberate: an unreadable
        level falls to the DEFAULT, never to the floor."""
        beat = _beat(world=True)
        assert apply_player_authority(beat, "hard mode", PLAYER) == []
        assert apply_player_authority(_beat(world=True), None, PLAYER) == []

    def test_every_rung_has_a_label_in_the_menu(self):
        """A rung the engine serves and the menu cannot name renders as its raw
        storage key in a dropdown a player is meant to choose from."""
        from pathlib import Path

        settings = (Path(__file__).resolve().parents[1]
                    / "static/js/ui-next/story-tools/style.js").read_text(encoding="utf-8")
        assert "mode.label || String(mode.value" in settings
        assert "player_authority?.modes" in settings
