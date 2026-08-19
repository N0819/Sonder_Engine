"""A `progress` claim on a beat that repeated itself does not advance a goal.

`progress` is a SELF-REPORT. `affect._advance_intent` has always audited it,
and audited it in exactly one place: the ceiling, where there is nothing left
to gain. That catches a character grinding a finished goal and says nothing
about one grinding UP THE RAMP, where every repeat still buys a real +0.2 and
refreshes the dormancy clock.

Live, chat 80 turns 1-3. A psychologist delivered the same three propositions
on three consecutive beats -- you were sedated, it was not to harm you, the
restraints are for safety -- and her ledger read:

    intent ia1  status=active  progress=0.4  last_progress_turn=3
                barren_attempts=None

Nothing had happened and the ledger recorded steady progress. The engine had
even MEASURED the repetition twice (before the re-ask and after it) and paid
82.2 seconds for a second full character call over it; the intent ledger was
simply never told.

What is deliberately NOT done here: nothing new is demanded of the model. It
emits whatever ops it likes, and every field it left empty stays empty. The
engine only declines to call a repeat an advance -- which is the rule it
already applied at the ceiling, for reasons its own docstring gives.
"""

from __future__ import annotations

from mind import affect

PROGRESS = [{"op": "progress", "id": "ia1", "why": "we are getting somewhere"}]


def _intent(**over):
    base = {"id": "ia1", "intent": "Complete the intake interview",
            "status": "active", "progress": 0.2, "last_progress_turn": 1}
    base.update(over)
    return [base]


def _apply(intents, *, turn=3, barren=False, ops=None):
    return affect.apply_intent_ops(
        intents, ops if ops is not None else PROGRESS, turn,
        lambda op: True, barren_beat=barren)


class TestTheRamp:
    def test_a_barren_beat_does_not_advance_the_goal(self):
        out, _ = _apply(_intent(), barren=True)

        assert out[0]["progress"] == 0.2
        assert out[0]["barren_attempts"] == 1

    def test_a_barren_beat_does_not_refresh_the_dormancy_clock(self):
        """The half that made the old bug self-concealing: `last_progress_turn`
        was refreshed by the very act of grinding, so the sweep that exists to
        catch a stuck goal could only ever fire on a forgotten one."""
        out, _ = _apply(_intent(last_progress_turn=1), barren=True)

        assert out[0]["last_progress_turn"] == 1

    def test_an_ordinary_beat_is_untouched(self):
        """The default path, and the one every existing story is on."""
        out, _ = _apply(_intent())

        assert out[0]["progress"] == 0.4
        assert out[0]["last_progress_turn"] == 3
        assert out[0].get("barren_attempts") is None

    def test_restating_a_goal_on_a_barren_beat_does_not_advance_it_either(self):
        """The same beat, and the answer depended on which op the model chose.

        `apply_intent_ops` folds an `add` that restates an existing goal into
        progress on it -- which is exactly what a character repeating itself
        emits, since a repeated move usually arrives with the goal restated
        rather than with a `progress` op. That fold called `_advance_intent`
        without `barren_beat`, so the rung the flag exists to close was open
        the whole time to anyone who rephrased instead of reporting.
        """
        restate = [{"op": "add", "intent": "Complete the intake interview",
                    "why": "still trying"}]
        out, _ = _apply(_intent(), barren=True, ops=restate)

        assert len(out) == 1, "a restatement is not a second goal"
        assert out[0]["progress"] == 0.2
        assert out[0]["barren_attempts"] == 1
        assert out[0]["last_progress_turn"] == 1

    def test_restating_a_goal_on_an_ordinary_beat_still_advances_it(self):
        restate = [{"op": "add", "intent": "Complete the intake interview",
                    "why": "still trying"}]
        out, _ = _apply(_intent(), ops=restate)

        assert out[0]["progress"] == 0.4
        assert out[0]["last_progress_turn"] == 3

    def test_the_live_three_beat_grind_now_stops_at_the_first_repeat(self):
        """Chat 80 turns 1-3, replayed. Turn 1 advances; turns 2 and 3 repeated
        an earlier move and are refused."""
        intents = _intent(progress=0.0, last_progress_turn=0)
        intents, _ = _apply(intents, turn=1)
        assert intents[0]["progress"] == 0.2

        for turn in (2, 3):
            intents, _ = _apply(intents, turn=turn, barren=True)

        assert intents[0]["progress"] == 0.2
        assert intents[0]["barren_attempts"] == 2
        assert intents[0]["last_progress_turn"] == 1

    def test_a_barren_ramp_beat_warns_without_taking_the_goal_away(self):
        """A slow intention is not a stuck one. Two repeated beats is not
        enough to strip a goal from a character -- that would be the guard
        doing more harm than the grind."""
        intents = _intent()
        for _ in range(4):
            intents, warnings = _apply(intents, barren=True)

        assert intents[0]["status"] == "active"
        assert any("repeated an earlier move" in w for w in warnings)

    def test_the_ceiling_rule_still_stalls(self):
        """The original audit is unchanged: at full progress with nothing left
        to gain, the goal does stop steering."""
        intents = _intent(progress=1.0)
        for _ in range(affect._INTENT_STALL_AFTER):
            intents, warnings = _apply(intents)

        assert intents[0]["status"] == "dormant"
        assert any("stalled" in w for w in warnings)

    def test_a_block_still_clears_the_count(self):
        """The world pushing back IS engagement, and re-opens room above the
        goal -- so a barren run must not survive it."""
        intents, _ = _apply(_intent(), barren=True)
        assert intents[0]["barren_attempts"] == 1

        intents, _ = _apply(intents, ops=[{"op": "block", "id": "ia1",
                                           "why": "she refused"}])

        assert intents[0].get("barren_attempts") is None


class TestTheSignalIsAlreadyMeasured:
    """The flag is carried, not derived a second time.

    The character stage already detects a repeated move and already screens
    the ones the beat genuinely invited. Deriving repetition again in `affect`
    would be a second implementation of a question the engine has answered.
    """

    def test_the_character_stage_marks_the_beat(self):
        import inspect

        import agents.character as character

        source = inspect.getsource(character.character_step) \
            if hasattr(character, "character_step") else inspect.getsource(character)

        assert '_barren_beat = "move_correction" in _corrections' in source
        assert 'out["_barren_beat"] = True' in source

    def test_the_flag_is_set_after_validation(self):
        """`validate_llm_output` drops unknown keys, so a flag set on the draft
        is a flag posted into a dict that is thrown away -- and the ledger goes
        on trusting the self-report."""
        import inspect

        import agents.character as character

        source = inspect.getsource(character)
        validate = source.index('validate_llm_output("character", out)')
        flag = source.index('out["_barren_beat"] = True')

        assert flag > validate

    def test_commit_passes_it_to_the_ledger(self):
        import inspect

        from persist import commit

        # The pass-through lives in prepare_memory_commit (commit_memory
        # since the split); the function source survives the move.
        source = inspect.getsource(commit.prepare_memory_commit)

        assert 'barren_beat=bool(own_result.get("_barren_beat"))' in source

    def test_an_invited_repetition_is_barren_too_and_that_is_deliberate(self):
        """The honest consequence of removing the re-ask.

        A model screen used to judge whether the beat had INVITED the
        repetition, and only an unscreened one counted. That screen existed to
        decide whether to pay for a full re-ask; with the re-ask gone it went
        too. So an insistence, a continuous riff or a deliberate return now
        costs its goal the +0.2 and surfaces `barren_attempts`. For a rule that
        is not working that is the right thing to say; for one that is, it is a
        beat of over-caution. Stated here rather than discovered later.
        """
        import inspect

        import agents.character as character

        source = inspect.getsource(character)

        assert "move_repeat_screen" not in source
        assert '_barren_beat = "move_correction" in _corrections' in source


class TestTheCharacterIsTold:
    """The half that can actually break the loop.

    The appraisal in the live case reported controllability 0.7 after three
    failures, because nothing in the payload had ever said the approach was
    not working. `barren_attempts` needs no new field to fix that: it is a
    stored value, it rides in the intention dict whole, and the character
    prompt already names it.
    """

    def test_the_count_survives_into_the_payload(self):
        from agents.character import _annotate_fading

        annotated = _annotate_fading(
            [{"id": "ia1", "status": "active", "last_progress_turn": 3,
              "barren_attempts": 2}], 4)

        assert annotated[0]["barren_attempts"] == 2

    def test_the_prompt_already_names_it(self):
        """No second vocabulary for the same fact."""
        from llm.prompts import get_prompt

        assert "barren_attempts" in get_prompt("character", "en")
