"""The dialogue line budget must reach the character agent and mean something.

Reported from live play ("The Doctor — Hinami" and its branches): the dialogue
config is set to `chatty` with `min_lines: 2` and NPCs emit exactly one line.

Two defects, both pinned here.

1. THE FLOOR WAS DISCARDED. `scene.dialogue_budget` read `min_lines` and
   emitted `{style, suggested_lines, hard_max, may_stay_silent}`. The only
   thing derived from the floor was `may_stay_silent`, a boolean that a SINGLE
   line already satisfies -- so an author asking for two lines sent the
   character agent no number it could honour.

2. THE FIELD CARRIED NO MEANING. The character prompt's whole treatment of it
   was "SPEECH BUDGET: speech_budget is pacing guidance. Silence is valid." --
   which describes the budget as optional and blesses the floor. The character
   contract now states the micro-beat bound as elapsed action and causal
   ownership, while line count remains governed explicitly by the authored
   voice and `decision.speech_budget`. (That bound was called MICRO-BEAT
   SCOPE until 2026-08-31 and is now WHERE YOUR TURN ENDS; the rule is the
   same one, named for what it limits rather than for a size.)

Measured across the author's live chats (read-only, structural): line counts do
not track the setting at all. A chat at `min_lines: 2` produced exactly one
speech entry in 28 of 28 declarations, while a chat at `min_lines: 0` produced
two or more in 43% of them.

The fix is prompt + payload shape, so what is asserted here is the plumbing and
the wording contract. Whether characters actually talk more is a model-behavior
change, validated in play, not asserted in a unit test.
"""

from __future__ import annotations

from llm.prompts import character_bare_module

import pytest

from llm.prompts import DEFAULT_PROMPTS
from story.scene import DEFAULT_INTERACTION_CONFIG, dialogue_budget

CHAT = {"id": 1}
TURN = {"idx": 3}


def _budget(cfg, monkeypatch, *, nonce="n1", cid=7):
    merged = dict(DEFAULT_INTERACTION_CONFIG)
    merged.update(cfg)
    monkeypatch.setattr("story.scene.dialogue_config", lambda _cid: merged)
    return dialogue_budget(CHAT, TURN, cid, nonce)


class TestTheFloorSurvives:
    def test_min_lines_reaches_the_payload(self, monkeypatch):
        budget = _budget({"style": "chatty", "min_lines": 2, "max_lines": 4},
                         monkeypatch)
        assert budget["min_lines"] == 2

    @pytest.mark.parametrize("nonce", [f"n{i}" for i in range(24)])
    def test_the_suggestion_never_falls_below_the_floor(self, monkeypatch, nonce):
        budget = _budget({"min_lines": 2, "max_lines": 5}, monkeypatch,
                         nonce=nonce)
        assert budget["min_lines"] <= budget["suggested_lines"] <= budget["hard_max"]

    def test_the_authors_live_setting(self, monkeypatch):
        # chats 40/41/42/43/44 verbatim: chatty, 2..5.
        budget = _budget({"style": "chatty", "min_lines": 2, "max_lines": 5},
                         monkeypatch)
        assert budget["style"] == "chatty"
        assert budget["min_lines"] == 2
        assert budget["may_stay_silent"] is False
        assert budget["suggested_lines"] >= 2

    def test_the_default_still_permits_silence(self, monkeypatch):
        budget = _budget({}, monkeypatch)
        assert budget["min_lines"] == 0
        assert budget["may_stay_silent"] is True

    def test_a_floor_above_the_ceiling_does_not_invert(self, monkeypatch):
        budget = _budget({"min_lines": 6, "max_lines": 2}, monkeypatch)
        assert budget["hard_max"] >= budget["min_lines"]
        assert budget["suggested_lines"] >= budget["min_lines"]


class TestThePromptReadsTheBudget:
    """The budget reaches the bare card as its own gated section
    (`character_bare/speech_budget`), shipped when the payload carries one."""
    SYSTEM = character_bare_module("speech_budget", "en")

    @pytest.mark.parametrize("field", [
        "min_lines", "suggested_lines", "hard_max", "may_stay_silent",
    ])
    def test_every_field_is_named(self, field):
        # The whole budget used to be one sentence naming none of them.
        assert field in self.SYSTEM

    def test_a_line_is_defined_as_a_say_step(self):
        # Without this, "2 lines" is satisfiable by one longer paragraph.
        assert "counts separate `say` steps" in self.SYSTEM

    def test_may_stay_silent_false_is_a_different_instruction(self):
        assert "`may_stay_silent: false` means you speak" in self.SYSTEM

    def test_it_ships_only_with_a_budget(self):
        from agents.character_bare import modules_for
        assert "speech_budget" not in modules_for({})
        assert "speech_budget" in modules_for(
            {"decision": {"speech_budget": {"min_lines": 1}}})


class TestTheTurnBoundDoesNotMinimizeVoice:
    SYSTEM = DEFAULT_PROMPTS["character_bare"]

    def test_the_directive_itself_is_intact(self):
        # The directive still has to SAY what this stage is for, in the
        # first person.
        assert "what you fill in is what {name} does next" in self.SYSTEM

    def test_the_bound_prefers_no_size(self):
        # The turn ends where someone else must answer or the world must
        # decide; the card says in the same breath that it prefers no size.
        head = self.SYSTEM[:self.SYSTEM.index("HOW YOU ACT:")]
        assert "YOUR TURN: act through one stretch" in head
        assert "nothing here prefers a small move to a large one" in head
        assert "Commit as hard as you would" in head


def test_the_character_payload_carries_the_budget():
    """`agents/character.py` puts it at decision.speech_budget; the section
    refers to it by that path."""
    assert "decision.speech_budget" in character_bare_module("speech_budget", "en")
