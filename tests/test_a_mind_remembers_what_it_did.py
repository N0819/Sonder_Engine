"""A character's own conduct is the one thing only it can record.

Deterministic perception structurally excludes a mind's own speech and acts
from its own view -- that is the firewall working, not a gap -- so the `self`
memory row in `persist/commit_memory.py` is the ONLY durable record that a
character did anything. It was gated on the character's own `salience`
self-report reaching 0.7, and that gate never opened: `salience` reaches the
character prompt only as the literal `0.5` inside the required JSON shape,
nothing says what it means, and `KERNEL_FILL_QUIETLY` fills an absent one with
0.5 and reports nowhere.

Measured, two_lives v5 (2026-09-19): 60 beats, two autonomous characters, no
player. ONE self row -- on the single beat anybody spoke. Emory Vane spent
twenty of those beats diagnosing a rotten bearing in a mill sluice and the
memories he came away with are "I was in a deep crouch" and "I feel the sluice
framing against my right palm". The engine kept his posture and discarded his
work.
"""

from __future__ import annotations

from persist.commit import _own_sequence_memory


def _act(attempt):
    return {"type": "action", "attempt": attempt, "observable": ""}


class TestTheRowSaysWhatTheMindDid:
    def test_an_act_is_rendered_as_an_attempt(self):
        content, gist = _own_sequence_memory(
            [_act("roll the wet grit between thumb and forefinger to feel "
                  "whether it shears")])
        assert content.startswith("I tried to roll the wet grit")
        assert gist

    def test_speech_and_act_keep_their_order(self):
        content, _ = _own_sequence_memory([
            {"type": "speech", "text": "She's shuddering every fifth turn."},
            _act("walk out to the race")])
        assert content.index("I said") < content.index("I tried to")

    def test_a_beat_with_no_conduct_renders_nothing(self):
        assert _own_sequence_memory([]) == ("", "")
        assert _own_sequence_memory([{"type": "action", "attempt": "  "}]) \
            == ("", "")


class TestTheBoundIsConductNotSelfRating:
    """The gate's own predicate, stated here so a later edit cannot quietly
    put a self-reported number back in front of a mind's memory."""

    @staticmethod
    def _stores(seq):
        return any(
            isinstance(event, dict)
            and (event.get("type") in ("speech", "communication")
                 or str(event.get("attempt") or "").strip())
            for event in seq)

    def test_a_silent_act_is_remembered(self):
        """v5's whole failure in one line: nobody spoke, so nobody
        remembered anything they had done."""
        assert self._stores([_act("sight down the revolving main shaft")])

    def test_speech_is_remembered(self):
        assert self._stores([{"type": "speech", "text": "Right away."}])

    def test_a_beat_with_nothing_in_it_is_not(self):
        assert not self._stores([])
        assert not self._stores([{"type": "action", "attempt": ""}])


class TestTheRowReadsAsOneSentence:
    """A declared `attempt` is authored standalone and arrives capitalised;
    the row folds it into the middle of a sentence the character reads back
    ("I tried to Crouch beside the wheel shroud" -- two_lives v7, turn 5)."""

    def test_a_capitalised_attempt_is_folded_in(self):
        content, _ = _own_sequence_memory([_act("Crouch beside the shroud")])
        assert content == "I tried to crouch beside the shroud."

    def test_an_acronym_keeps_its_capitals(self):
        content, _ = _own_sequence_memory([_act("SOS the mill with a horn")])
        assert content.startswith("I tried to SOS")

    def test_an_already_lowercase_attempt_is_untouched(self):
        content, _ = _own_sequence_memory([_act("sight down the main shaft")])
        assert content == "I tried to sight down the main shaft."
