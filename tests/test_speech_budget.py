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
   voice and `decision.speech_budget`.

Measured across the author's live chats (read-only, structural): line counts do
not track the setting at all. A chat at `min_lines: 2` produced exactly one
speech entry in 28 of 28 declarations, while a chat at `min_lines: 0` produced
two or more in 43% of them.

The fix is prompt + payload shape, so what is asserted here is the plumbing and
the wording contract. Whether characters actually talk more is a model-behavior
change, validated in play, not asserted in a unit test.
"""

from __future__ import annotations

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
    SYSTEM = DEFAULT_PROMPTS["character"]

    @pytest.mark.parametrize("field", [
        "min_lines", "suggested_lines", "hard_max", "may_stay_silent",
    ])
    def test_every_field_is_named(self, field):
        # The whole budget used to be one sentence naming none of them.
        assert field in self.SYSTEM

    def test_the_floor_is_stated_as_a_floor(self):
        assert "FLOOR" in self.SYSTEM

    def test_a_line_is_defined_as_a_speech_entry(self):
        # Without this, "2 lines" is satisfiable by one longer paragraph.
        assert "one {type:'speech'} entry" in self.SYSTEM

    def test_silence_is_no_longer_blessed_unconditionally(self):
        assert "speech_budget is pacing guidance. Silence is valid." not in self.SYSTEM

    def test_may_stay_silent_false_is_a_different_instruction(self):
        assert "may_stay_silent:false" in self.SYSTEM
        assert "may_stay_silent:true" in self.SYSTEM


class TestTheMicroBeatScopeDoesNotMinimizeVoice:
    SYSTEM = DEFAULT_PROMPTS["character"]

    def test_the_directive_itself_is_intact(self):
        assert "Predict this character's next behavior" in self.SYSTEM

    def test_it_is_scoped_where_it_is_stated(self):
        # The qualification sits beside the scope directive, before any
        # epistemic rules can make it read as a personality preference.
        head = self.SYSTEM[:self.SYSTEM.index("EPISTEMIC FIREWALL")]
        assert "MICRO-BEAT SCOPE limits elapsed action and causal ownership" in head
        assert "not personality or intensity" in head
        assert "no preference for caution" in head

    def test_the_voice_scoping_still_stands(self):
        # The distant voice anchor independently states the same boundary.
        assert "constrains elapsed action and causal ownership, NOT " in self.SYSTEM
        assert "word count" in self.SYSTEM


def test_the_character_payload_carries_the_budget():
    """`agents/character.py` puts it at decision.speech_budget; the prompt now
    refers to it by that path."""
    assert "decision.speech_budget" in DEFAULT_PROMPTS["character"]
