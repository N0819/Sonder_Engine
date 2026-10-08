"""A NARRATOR FIDELITY CHECK MUST NOT FIRE ON A PAGE THAT IS RIGHT.

The owner's standing ruling (2026-09-06): a check that fires on valid output
is fixed or dies, because a warning channel that lies stops being read. The
Brackwater run (scratch story 166, 2026-10-07) stored three classes of it, on
its three short-trace pages, and each is fixed at its cause:

* QUOTES ARE PAIRED BY THEIR MARKS (turn 4614). `_QUOTE_BODY_RE` held a
  four-character floor in its pattern, so "No." never matched and its two
  marks paired with their neighbours: every span after it was narration.
  The narrator was handed no `dialogue_lines` and the check reported four
  real lines missing and four stretches of narration as invented.
* THE SUBJECT OF THE INTRODUCING SENTENCE OPENS IT (turns 4607, 4609, 4610).
  The attribution check took the first body named anywhere, skipping
  possessives, so "Hester's voice came from behind ... without following
  Tamsin" gave Hester's line to Tamsin.
* A VOICE IS COUNTED BY SENTENCE (turn 4611). One impersonal "you" simile is
  two tokens in one sentence, and two tokens crossed the person margin.

The page texts below are the stored ones, cut to the passage that matters.
"""

from __future__ import annotations

import pytest

from agents.common import (_check_narration_person_match,
                           _check_narrator_fidelity, _check_quote_attribution,
                           _dialogue_tokens, quoted_lines)


VIEW_4614 = (
    'Abel Gale says under their breath in a flat, low, almost quiet — the '
    'word dropped like a stone, then nothing for a beat voice: "No." Abel '
    'Gale the lantern flame gutters in a draft through the floorboards, '
    'throwing shadows of hooks and nets across the wall. Abel Gale says in a '
    'steady, each sentence bitten off clean, eyes on her face now voice: "I '
    "came ashore at dawn. I came here. I haven't left this house since. Ask "
    "the neighbours. Ask anyone on the walk. I haven't been out to that "
    "stake. I haven't been out anywhere.\" Abel Gale shifts weight forward "
    'off the table. Abel Gale says in a harder now, the protective edge '
    'breaking through the flatness — leaning forward off the table voice: '
    '"Hester went out to that wreck because you hired her to take you there. '
    "That's her work. She cuts reed, she marks the channel, she shows the "
    'assessor where the hull lies. If she cut reed round that stake, she was '
    "doing what you paid her to do. Don't make it into something else.\" Abel "
    'Gale says under their breath in a voice dropping again, the rawness '
    'back, turning it back on her because he needs to know what she saw '
    "voice: \"You came here asking if I did something to that coat. I didn't. "
    "Now I'm asking you — what did you find out there that makes you think "
    'somebody did?" ')

PROSE_4614 = (
    'The word landed and the room held still around it. "No." Flat, low — a '
    'stone dropped into a dry well, then nothing for a beat.\n\n'
    'The lantern flame guttered. A draught came up through the floorboards '
    'where the piles let the river breathe, and shadows of hooks and dried '
    'nets swung once across the tarred wall behind him and settled.\n\n'
    "\"I came ashore at dawn. I came here. I haven't left this house since.\" "
    'Each sentence bitten off clean, his eyes on her face now — not on the '
    "receipt, not on the door. \"Ask the neighbours. Ask anyone on the walk. I "
    "haven't been out to that stake. I haven't been out anywhere.\"\n\n"
    'He shifted his weight forward off the table, and the protective edge '
    'broke through the flatness — harder, leaning toward her. "Hester went '
    "out to that wreck because you hired her to take you there. That's her "
    'work. She cuts reed, she marks the channel, she shows the assessor where '
    'the hull lies. If she cut reed round that stake, she was doing what you '
    "paid her to do. Don't make it into something else.\"\n\n"
    'His voice dropped again, the rawness back in it, turning the question '
    "on her. \"You came here asking if I did something to that coat. I "
    "didn't. Now I'm asking you — what did you find out there that makes you "
    'think somebody did?"')


class TestQuotesArePairedByTheirMarks:
    def test_a_short_line_does_not_take_the_next_with_it(self):
        view = ('Picard says in a flat voice: "No." '
                'Riker says in a quiet voice: "Then we wait for the relief."')
        assert [body for _at, body in quoted_lines(view)] == [
            "Then we wait for the relief."]

    def test_turn_4614_hands_the_narrator_every_long_line(self):
        """It was handed none: every span it was offered was an
        attribution, and each was dropped as one."""
        assert [line[:24] for line in _dialogue_tokens(VIEW_4614, [])] == [
            "I came ashore at dawn. I",
            "Hester went out to that ",
            "You came here asking if ",
        ]

    def test_turn_4614_page_raises_no_paired_narration(self):
        """Seven warnings, none true. What is left is the one finding the
        mis-pairing had hidden: the narrator, given no placeholders, split
        "I came ashore ..." around a beat of narration."""
        warnings = _check_narrator_fidelity({"prose": PROSE_4614}, VIEW_4614)
        assert not any("invented quoted dialogue" in w for w in warnings), \
            warnings
        missing = [w for w in warnings if "missing or altered" in w]
        assert len(missing) == 1 and "I came ashore at dawn" in missing[0], \
            warnings

    def test_the_four_character_floor_still_holds_after_pairing(self):
        """The floor is the pack's (`_QUOTE_BODY_RE`), asked of each PAIRED
        span: a line under four characters is still not scored."""
        assert [b for _a, b in quoted_lines(
            'She shakes her head. "No." Then: "Not the north road."')] == [
            "Not the north road."]


def _speech(actor, quote):
    return {"actor": actor, "kind": "speech", "quote": f'"{quote}"'}


class TestTheSubjectOpensTheSentence:
    EVENTS = [
        _speech("Tamsin Coyle", "Mr Gale. Tamsin Coyle, River Underwriters."),
        _speech("Hester Gale", "I'm on the walk, Abel. Say it as it lies "
                               "and it goes easier on you."),
        _speech("Abel Gale", "There was no other man aboard."),
    ]

    def test_turn_4609_a_possessive_subject_names_the_speaker(self):
        prose = ("Hester's voice came from behind, flat and low, pitched to "
                 "carry through the open door without following Tamsin across "
                 "the threshold. \"I'm on the walk, Abel. Say it as it lies "
                 "and it goes easier on you.\"")
        assert _check_quote_attribution(prose, self.EVENTS) == []

    def test_turn_4610_a_fragment_names_no_subject(self):
        prose = ("His gaze cut toward the stair where Hester stood, then back. "
                 "Not to Tamsin. \"Hester. Go wait on—\" He stopped the name "
                 "short and didn't finish.")
        events = self.EVENTS + [_speech("Abel Gale", "Hester. Go wait on—")]
        assert _check_quote_attribution(prose, events) == []

    def test_turn_4607_a_body_inside_a_modifier_is_not_the_subject(self):
        prose = ("A man Tamsin didn't know leaned against the nearest mooring "
                 "post. \"Mind the second tread — it's split.\" He didn't "
                 "look up.")
        events = self.EVENTS + [_speech("the unfamiliar person",
                                        "Mind the second tread — it's split.")]
        assert _check_quote_attribution(prose, events) == []

    def test_a_named_subject_that_did_not_speak_still_fires(self):
        """The case the check exists for: the sentence that introduces the
        line opens on a different body, by name."""
        prose = ("Tamsin Coyle turns the receipt to the light. \"There was no "
                 "other man aboard.\"")
        found = _check_quote_attribution(prose, self.EVENTS)
        assert found and "Abel Gale" in found[0] and "Tamsin Coyle" in found[0]

    def test_an_article_before_a_described_subject_still_opens_it(self):
        prose = ("The unfamiliar woman pulls her hands back from the console. "
                 "\"Don't say I didn't warn you.\"")
        events = [_speech("Vorne", "Don't say I didn't warn you."),
                  _speech("the unfamiliar woman", "I second that.")]
        found = _check_quote_attribution(prose, events)
        assert found and "Vorne" in found[0]


PROSE_4611 = (
    "He braced both hands on the table edge opposite her, the lantern between "
    "them throwing his shadow up the tarred wall behind. His knuckles went "
    "white against the scarred pine.\n\n"
    "The words came under his breath, pushed out one at a time the way you'd "
    "shift cargo you weren't sure would hold. His eyes were down on the grain "
    "of the table -- the knife-marks, the ring-stains -- and then they came "
    "up.")


class TestAVoiceIsCountedBySentence:
    def test_turn_4611_an_impersonal_you_is_not_second_person(self):
        assert _check_narration_person_match(
            PROSE_4611, "third", "Tamsin Coyle") == []
        assert not any(
            w.startswith("Narrator prose reads as")
            for w in _check_narrator_fidelity(
                {"prose": PROSE_4611}, "", narration_person="third",
                player_name="Tamsin Coyle"))

    @pytest.mark.parametrize("prose", [
        "You set the lantern down. Your hands stay off the table, and you "
        "wait for him to answer.",
        "You turn the receipt toward the lamp. He reads it. You do not let "
        "go of it.",
    ])
    def test_a_page_written_in_the_second_person_still_reads_as_one(
            self, prose):
        found = _check_narration_person_match(prose, "third", "Tamsin Coyle")
        assert found and "second person" in found[0]
