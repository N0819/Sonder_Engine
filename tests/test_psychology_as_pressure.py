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
    """'Derive 2-3 beat wants from your drive' was obeyed 197 times -- the
    deduction was instructed and then measured. The bare card (2026-09-27)
    names a want as what the mind is going for and never derives it; the
    full card's "pressure, not premises" framing and its quoted habit
    ("Given my drive, I would") are not on it (open in
    docs/UNBUILT_CHARACTERS.md §6.17)."""

    def test_the_derivation_instruction_is_gone(self):
        from llm.prompts import bare_character_prompt
        prompt = bare_character_prompt("en")
        assert "Derive 2-3 beat wants from your drive" not in prompt
        assert "`want` is what you are going for" in prompt, (
            "the wants rule itself must survive -- the fix is how wants "
            "arise, not whether they exist")

    def test_what_a_want_serves_is_read_back_not_written(self):
        """`serves` is engine machinery (affect resolves it to the drive or
        an intention id and weights appraisal by it): the decision model
        picks it among this mind's own aims, the drive among them."""
        from mind import character_jev as jev
        held = jev.Holding(name="Wren", language="en", aims=[
            {"kind": "drive", "id": "drive", "text": "keep the family safe"}])
        assert "want:serves" in jev.after_questions(held, {"want": "get the key back"})

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
