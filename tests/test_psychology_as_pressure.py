"""Psychology as pressure, not as premises (DESIGN_PSYCHOLOGY_AS_PRESSURE).

Measured over 158 beats of one character's full reasoning traces (A11): 299
citations of "his drive", 249 of one value, 197 explicit "Given his X, he
would Y" constructions -- and one "torn between" in the whole log, zero
occasions of acting against a stated value. The character reasoned
deductively FROM his sheet on every beat, because the payload handed him his
psychology as labelled citable data and the prompt told him to derive wants
from it. Conflict was scored and never felt.

These tests pin the two high-confidence fixes: the prompt no longer
instructs the derivation (wants arise from the situation as this person
meets it; the drive is pressure, not premises), and the psychology-fill
guidance prefers values authored as ordered trade-offs, which is also what
lets a value legibly LOSE (motivated violation with no variance -- the
declined alternative, instructed inconsistency, produces noise, and noise
reads as a broken machine).

Database-independent: pure prompt-text contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.prompts import DEFAULT_PROMPTS


class TestWantsAreNotDerivedFromTheSheet:
    def test_the_derivation_instruction_is_gone(self):
        """'Derive 2-3 beat wants from your drive' was obeyed 197 times --
        we instructed the deduction and then measured the character
        performing it. The instruction must not come back under a synonym
        either: wants are not computed from psychology fields."""
        prompt = DEFAULT_PROMPTS["character"]
        assert "Derive 2-3 beat wants from your drive" not in prompt
        assert "WANTS AND GOALS" in prompt, (
            "the wants rule itself must survive -- the fix is how wants "
            "arise, not whether they exist")

    def test_wants_arise_from_the_situation(self):
        """The replacement frames drive and intentions as the reason some
        options feel obvious and others never occur -- salience, not a
        premise in an argument. Without this the sheet is a function the
        character consistently computes, which is exactly what a person is
        not."""
        prompt = DEFAULT_PROMPTS["character"]
        assert "pressure, not premises" in prompt
        assert "never occur to you" in prompt

    def test_the_deduction_is_named_and_forbidden(self):
        """The measured construction is quoted in the prompt so the model
        recognises the habit itself, not merely a banned phrase."""
        assert "Given my drive, I would" in DEFAULT_PROMPTS["character"]

    def test_the_serves_contract_survives(self):
        """`serves` is engine machinery (affect resolves it to the drive or
        an intention id and weights appraisal by it). Softening the
        derivation instruction must not delete the structured contract, or
        appraisal loses its goal grounding."""
        assert "want names what it serves" in DEFAULT_PROMPTS["character"]


class TestValuesArePreferredAsTradeOffs:
    def test_the_fill_prompt_teaches_the_form(self):
        """A flat virtue cannot be traded against anything, so it operates
        as a constraint; a prohibition carries no counterweight inside it,
        which is how 'never breaking stride' inverted into an argument
        against a courier running. The fill prompt is where imported cards
        get their psychology completed, so it is where the authoring habit
        generalises beyond one maze sheet."""
        prompt = DEFAULT_PROMPTS["fill_character_psychology"]
        assert "speed over thoroughness" in prompt
        assert "naming what gives way" in prompt
