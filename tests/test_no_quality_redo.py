"""A redo fires only when output is broken, never when it is merely weak.

The owner's rule, and the measurements agree with it. A repeated move, a
reissued line and a spent intention steering a choice are all WEAK output --
usable, committable, in-character-arguable. None of them justified what they
cost: a full second character call on the character's own model, measured live
at 36.3s, 58.0s and 155.6s, kept unchanged 48 times across stored variants, and
on the 155.6s beat producing a "corrected" answer that restated the same three
propositions in different words.

The deeper reason it could never work is written one screen above the seam in
`agents/character.py`: `recent_self_lines`, the refrain skeleton and the
verbatim rewrite "all say NOT THAT". A negative constraint helps a mind that
has another move and does nothing for one that does not -- so the retry
rephrased, because rephrasing was the only move left.

What replaces it is the mechanism that says HERE IS SOMETHING ELSE YOU OWN.
"""

from __future__ import annotations

import inspect

import agents.character as character


class TestNoQualityRedo:
    def test_the_character_stage_makes_no_second_model_call(self):
        """The whole point. `_agent_json` appears once: the draft."""
        source = inspect.getsource(character.character_step) \
            if hasattr(character, "character_step") else ""
        if not source:
            source = inspect.getsource(character)
            source = source[source.index("    out = _agent_json("):]
            source = source[:source.index("\ndef ")]

        assert source.count("_agent_json(") == 1

    def test_the_screen_that_gated_the_redo_is_gone_with_it(self):
        """It existed only to decide whether to pay for the re-ask, and it
        answered `redo` whenever it could not tell -- an uncertain screen
        buying the exact call it was built to avoid."""
        from llm import llm_quality

        assert not hasattr(llm_quality, "move_repeat_screen")

    def test_its_prompt_is_gone_from_every_pack(self):
        """A prompt with no caller is a prompt every language pack has to keep
        translating."""
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for pack in ("en", "ja"):
            card = json.loads(
                (root / f"language_packs/{pack}/cards/system_prompts.json")
                .read_text(encoding="utf-8"))
            assert "move_repeat_screen" not in card["prompts"], pack

    def test_the_corrections_are_still_recorded(self):
        """Not silently dropped: a beat that repeated itself still says so on
        the step, because the next reader of that turn needs to know."""
        source = inspect.getsource(character)

        assert "(recorded; the beat stands)" in source


class TestWhatStillFires:
    """A redo is right when the output cannot be used. Those paths stay."""

    def test_a_schema_failure_still_repairs(self):
        """`complete_validated_json` owns repair/fallback/raise, and unusable
        JSON is the definition of broken."""
        from llm import llm_quality

        assert hasattr(llm_quality, "complete_validated_json")

    def test_the_director_still_refuses_invented_player_conduct(self):
        """The line the rule draws. Repetition is weak; a resolve that gives
        the player acts they never declared is a contract violation, and its
        retry is kept only when it reduces the violation count."""
        source = inspect.getsource(__import__("agents.director",
                                              fromlist=["director"]))

        assert "_check_player_act_authority" in source
        assert "correction_notes" in source


class TestTheReplacement:
    """The positive mechanism, armed with the signal that caught the live case."""

    def test_a_barren_goal_now_triggers_unbidden_recall(self):
        """`_unbidden_trigger` is the one mechanism that offers an alternative
        rather than forbidding a repeat. Its three existing signals all missed
        the live loop: the lines were not verbatim repeats, their shapes
        varied, and the goal was neither held nor at its ceiling -- it was
        grinding UP the ramp, which nothing measured until that floor existed.
        """
        state = {"interior": {"intentions": [
            {"id": "ia1", "status": "active", "barren_attempts": 1}]},
            "unbidden": {}}

        assert character._unbidden_trigger(state, {}, None, 5, 0.3) \
            == ("barren_goal", True)

    def test_an_ordinary_goal_does_not(self):
        state = {"interior": {"intentions": [
            {"id": "ia1", "status": "active"}]}, "unbidden": {}}

        assert character._unbidden_trigger(state, {}, None, 5, 0.3) \
            == (None, False)

    def test_only_a_live_intention_counts(self):
        """A dormant goal carrying an old barren count is not a mind stuck on
        it now -- it is a mind that already let it go."""
        state = {"interior": {"intentions": [
            {"id": "ia1", "status": "dormant", "barren_attempts": 3}]},
            "unbidden": {}}

        assert character._barren_intent(state) is False

    def test_the_existing_suppressions_still_outrank_it(self):
        """A barren goal must not force reminiscence on a mind the engine has
        already decided has no room for it."""
        state = {"interior": {"intentions": [
            {"id": "ia1", "status": "active", "barren_attempts": 1}]},
            "unbidden": {}}

        assert character._unbidden_trigger(state, {}, None, 5, 0.99) \
            == ("barren_goal", False)
