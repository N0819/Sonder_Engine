"""Physical conduct written inside a speech element must not travel on the ear.

Found in live play (chat 62, 12 turns): a character model began writing
RP-style stage directions into the `text` of its `{type:'speech'}` elements --

    "*leans in and sets a hand flat on her shoulder* You will want to sit down."

-- instead of emitting a separate `{type:'action'}` element beside the speech.
The sequence contract already supports interleaving, and one live beat declared
a proper action element AND smuggled a second act into the speech in the same
breath, so nothing forced this; the model reached for the convention it was
trained on.

The engine had no opinion about the contents of `text`, so everything in it was
delivered as SOUND. That is a FLOW defect, not a knowledge one: nobody learns
anything they had no business knowing -- the person being touched would feel it
-- but a body movement went through the whole audibility apparatus (distance,
enclosure, muffling, deafness) as though it were a spoken word.

It was not rare noise, and it grew: 52% of that chat's speech elements carried
one against 0.9% across the rest of the corpus, climbing turn over turn because
each span was stored in the speaker's own episodic memory as words she SAID and
read back to her on the next beat. It was also the cause of a second symptom --
`Dropped director-invented dialogue line` fired on 7 of 12 turns there against
7 of 1,715 turns corpus-wide, because the Director (a different model)
re-rendered the stage direction as prose, which no longer matched the
declaration, so the verbatim-speech guard dropped the line as invented.

`norm_sequence` now excises the span before anything downstream sees it and
re-files it as the action element it should have been. The first four tests
below are the four channel consequences, each asserting the outcome the fix
produces; the rest cover the splitter itself.

Language here is deliberately plain; the live material this came from is not.
"""

from __future__ import annotations

from agents.common import (_inject_dialogue, norm_sequence,
                           split_stage_directions)

SMUGGLED = ("*leans in and sets a hand flat on her shoulder* "
            "You will want to sit down for this.")

ACT = "leans in and sets a hand flat on her shoulder"
WORDS = "You will want to sit down for this."


def _normalized(text, **speech):
    """One smuggled speech element, through the seam the engine really uses."""
    out = {"sequence": [dict({"type": "speech", "text": text,
                              "volume": "normal"}, **speech)]}
    warnings = []
    norm_sequence(out, warn=warnings.append)
    return out["sequence"], warnings


def _spoken_line(seq):
    return next((e["text"] for e in seq if e["type"] == "speech"), None)


def _acts(seq):
    return [e["attempt"] for e in seq if e["type"] == "action"]


class TestTheFourChannelConsequences:
    """Each was measured against `_inject_dialogue` before the fix. The speech
    element that reaches it now carries words only, so the act is no longer
    subject to any of them."""

    def test_a_listener_who_cannot_hear_no_longer_loses_the_act(self):
        """`level='none'` is correct for the words and was wrong for the hand:
        a hand on the shoulder is not an audible event, and it was inheriting
        the audibility of the sentence it was parked in."""
        seq, _ = _normalized(SMUGGLED)
        view = _inject_dialogue("The lamp gutters.", "Reya",
                                _spoken_line(seq), "none", "normal", True)

        assert view == "The lamp gutters."       # the words, correctly silent
        assert _acts(seq) == [ACT]               # the act survives elsewhere

    def test_muffling_no_longer_grinds_the_act_into_word_fragments(self):
        """`_muffled_fragment` is an ACOUSTIC filter -- it keeps scattered
        words verbatim so `_scrub_invented_dialogue` can validate them. Applied
        to a body movement it produced fragments of a gesture, asterisks and
        all."""
        seq, _ = _normalized(SMUGGLED)
        view = _inject_dialogue("The lamp gutters.", "Reya",
                                _spoken_line(seq), "fragment", "normal", True)

        assert "A muffled voice:" in view
        assert "*" not in view
        assert "shoulder" not in view

    def test_a_listener_who_cannot_see_is_no_longer_told_the_act_by_ear(self):
        """The sharpest of the four. `can_see=False` is the case this engine
        takes most care over -- a voice through a door, in the dark, from
        inside an enclosure -- and it was handing the listener a description of
        a movement they had no channel to, framed as something they HEARD."""
        seq, _ = _normalized(SMUGGLED)
        view = _inject_dialogue("The lamp gutters.", "Reya",
                                _spoken_line(seq), "full", "normal", False)

        assert "You hear Reya say:" in view
        assert WORDS in view
        assert "shoulder" not in view

    def test_a_visible_speaker_no_longer_leaks_asterisks_into_the_quote(self):
        """Declared speech is preserved verbatim on purpose -- the Director and
        the Narrator must not silently rewrite what a character chose to say --
        so the stage direction reached the reader unedited, inside the
        quotation marks, and rendered as italics in the browser."""
        seq, _ = _normalized(SMUGGLED)
        view = _inject_dialogue("The lamp gutters.", "Reya",
                                _spoken_line(seq), "full", "normal", True)

        assert view == ('The lamp gutters. Reya says: "%s"' % WORDS)


class TestTheSplit:

    def test_the_act_becomes_an_action_placed_before_the_speech(self):
        """Ordering is the point: the character wrote the movement first and
        the line second, and that reading survives."""
        seq, _ = _normalized(SMUGGLED)

        assert [e["type"] for e in seq] == ["action", "speech"]
        assert seq[0]["attempt"] == ACT
        assert seq[0]["observable"] == ACT
        assert seq[1]["text"] == WORDS

    def test_it_warns_so_the_drift_is_visible_in_the_turn(self):
        _, warnings = _normalized(SMUGGLED)

        assert len(warnings) == 1
        assert "stage direction" in warnings[0]
        assert "shoulder" in warnings[0]

    def test_single_word_emphasis_stays_spoken(self):
        """Markdown emphasis is not a stage direction. "*feel*" is a word the
        character says with weight on it, and the live chat used both forms."""
        seq, warnings = _normalized("What does it *feel* like I am doing?")

        assert _spoken_line(seq) == "What does it feel like I am doing?"
        assert _acts(seq) == []
        assert warnings == []

    def test_several_spans_in_one_line_all_come_out_in_order(self):
        seq, warnings = _normalized(
            "*sets down the cup* A moment. *turns to the window* Not yet.")

        assert _acts(seq) == ["sets down the cup", "turns to the window"]
        assert _spoken_line(seq) == "A moment. Not yet."
        assert len(warnings) == 2

    def test_a_line_that_is_only_a_stage_direction_leaves_no_empty_speech(self):
        seq, _ = _normalized("*turns away without a word*")

        assert [e["type"] for e in seq] == ["action"]

    def test_the_promoted_act_inherits_the_concealment_of_the_line(self):
        """A stage direction inside a whispered aside was hidden by the words
        around it. Moving it onto its own channel must not make it overt."""
        seq, _ = _normalized("*presses the key into her palm* Keep it.",
                             volume="whisper", visibility="concealed",
                             conceal_from=["Bram"])

        act = seq[0]
        assert act["visibility"] == "concealed"
        assert act["conceal_from"] == ["Bram"]

    def test_a_purely_mental_span_gets_no_outward_surface(self):
        """Routed through the same mental-verb check as any other action, so
        "*thinks better of it*" is an imperceptible beat rather than a visible
        one."""
        seq, _ = _normalized("*thinks better of it* Never mind.")

        assert seq[0]["attempt"] == "thinks better of it"
        assert seq[0]["observable"] == ""

    def test_speech_without_asterisks_is_untouched(self):
        seq, warnings = _normalized("No asterisks at all here.")

        assert _spoken_line(seq) == "No asterisks at all here."
        assert warnings == []

    def test_an_unpaired_asterisk_does_not_swallow_the_line(self):
        spoken, spans = split_stage_directions("Three *stars and no closer")

        assert spoken == "Three *stars and no closer"
        assert spans == []


class TestDeduplication:
    """The live failure narrated one act twice in a single paragraph: once
    through a real action element, once through the copy smuggled into the
    speech beside it."""

    def test_an_act_declared_properly_is_not_promoted_twice(self):
        out = {"sequence": [
            {"type": "action", "attempt": "sets a hand on her shoulder",
             "observable": "sets a hand on her shoulder"},
            {"type": "speech", "volume": "normal",
             "text": "*sets a hand flat on her shoulder* Sit down."},
        ]}
        norm_sequence(out)

        assert _acts(out["sequence"]) == ["sets a hand on her shoulder"]
        assert _spoken_line(out["sequence"]) == "Sit down."

    def test_a_genuinely_different_act_survives_beside_the_declared_one(self):
        """A false match silently drops conduct the character declared, which
        is the failure this path exists to prevent, so the threshold errs
        toward keeping both."""
        out = {"sequence": [
            {"type": "action",
             "attempt": "hooks a finger into the strap and drags it aside",
             "observable": "hooks a finger into the strap and drags it aside"},
            {"type": "speech", "volume": "normal",
             "text": "*takes one slow step back toward the door* Not yet."},
        ]}
        norm_sequence(out)

        assert _acts(out["sequence"]) == [
            "hooks a finger into the strap and drags it aside",
            "takes one slow step back toward the door",
        ]
