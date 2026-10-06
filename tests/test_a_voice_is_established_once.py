"""A voice is established once per listener; afterwards only a departure
renders (review D2, from Wood: theatre gives a vocal quality once).

Measured before this: "In a flat, hushed monotone voice, she said" on 63-98
of 79 lines in one story and on 6 of 7 lines over three beats of the descent
copy (chat 117, beats 115-117). The speaker's ordinary voice was re-declared
as `tone` on every line, and the composed view had no notion of a voice the
listener already knew, so the narrator copied the tag each time.

Now `speech_percept` takes the speaker's own register and the observer's
standing ledger: the first line renders the register and files a
`voice:<body>` key; later lines render a manner only where the line's own
`tone` names a departure. Tone strings are never compared -- the ledger
decides. The card's half is the character prompt: leave `tone` empty in
your ordinary voice.
"""

from __future__ import annotations

import pathlib

from agents import composer
from agents.composer import Percept, render_view, standing_key, body_key


def _line(tone=""):
    return {"speaker": "Sarah Moon", "text": "Sound transmission is attenuated.",
            "volume": "normal", "tone": tone}


def _rel():
    return {"same_room": True, "tier": "within_reach", "barrier": "open"}


def _percept(tone="", voice="flat, clinical monotone", prev=frozenset()):
    return composer.speech_percept(
        _line(tone), _rel(), "Aurel Voss", display="Sarah Moon", can_see=True,
        voice=voice, prev_standing=prev)


VOICE_KEY = standing_key("voice", (body_key("Sarah Moon"),),
                         ("flat, clinical monotone",))


class TestTheLedgerDecides:
    def test_the_first_line_renders_the_register_and_files_the_key(self):
        p = _percept()
        assert p.data["manner"] == "flat, clinical monotone"
        assert p.data["voice_key"] == VOICE_KEY
        assert p.data["tone"] == ""

    def test_a_later_line_in_the_ordinary_voice_renders_no_manner(self):
        p = _percept(prev=frozenset({VOICE_KEY}))
        assert p.data["manner"] == ""

    def test_a_later_line_that_departs_renders_its_tone(self):
        p = _percept(tone="barely a whisper", prev=frozenset({VOICE_KEY}))
        assert p.data["manner"] == "barely a whisper"
        assert p.data["tone"] == "barely a whisper"

    def test_an_authored_register_is_spliced_in_sentence_case(self):
        p = composer.speech_percept(
            _line(), _rel(), "Aurel Voss", display="Sarah Moon", can_see=True,
            voice="Clinical, deadpan, and strictly monotone.", prev_standing=frozenset())
        assert p.data["manner"] == "clinical, deadpan, and strictly monotone"

    def test_a_speaker_with_no_register_renders_the_declared_tone_every_time(self):
        p = _percept(tone="rough", voice="")
        assert p.data["manner"] == "rough"
        assert "voice_key" not in p.data


class TestAVoiceThatIsAClause:
    """Kirinoura (scratch chat 167, 2026-10-05): the slot is "in a {tone}
    voice", and a register can be a clause -- "says in a bright, informal,
    theatrical, and highly articulate, shifting into grave authority without
    warning voice". It is said once, after the line, whole."""

    CLAUSE = ("Bright, informal, theatrical, and highly articulate, shifting "
              "into grave authority without warning.")

    def test_a_register_with_a_clause_is_its_own_sentence(self):
        p = composer.speech_percept(
            _line(), _rel(), "Aurel Voss", display="Sarah Moon", can_see=True,
            voice=self.CLAUSE, prev_standing=frozenset())
        text = render_view([p], mode="player", language="en").text
        assert ' voice:' not in text and 'says: "Sound transmission' in text
        assert text.endswith("The voice is bright, informal, theatrical, and highly "
                             "articulate, shifting into grave authority without warning.")

    def test_a_register_of_adjectives_stays_in_the_slot(self):
        p = composer.speech_percept(
            _line(), _rel(), "Aurel Voss", display="Sarah Moon", can_see=True,
            voice="Clinical, deadpan, and strictly monotone.", prev_standing=frozenset())
        text = render_view([p], mode="player", language="en").text
        assert "in a clinical, deadpan, and strictly monotone voice" in text
        assert "The voice is" not in text

    def test_a_line_said_in_the_room_ends_on_its_quote_before_the_voice(self):
        """Review round 3 (2026-10-05): ending the line before the voice put
        a stop after the closing quote: 'says: "...". The voice is'."""
        p = composer.speech_percept(
            _line(), _rel(), "Aurel Voss", display="Sarah Moon", can_see=True,
            voice=self.CLAUSE, prev_standing=frozenset())
        text = render_view([p], mode="player", language="en").text
        assert text == ('Sarah Moon says: "Sound transmission is attenuated." The voice '
                        "is bright, informal, theatrical, and highly articulate, "
                        "shifting into grave authority without warning.")

    def test_conduct_keeps_its_slot_however_long(self):
        p = _percept(tone="with a smirk, eyes narrowing at the corners and lips pressed thin",
                     prev=frozenset({VOICE_KEY}))
        text = render_view([p], mode="player", language="en").text
        assert "The voice is" not in text and "with a smirk" in text

    def test_a_new_voice_is_said_once_however_many_lines_it_says(self):
        """The review (2026-10-05): every line a newly heard speaker said in
        one beat said the voice again -- `speech_percept` asks the ledger of
        earlier beats."""
        lines = [composer.speech_percept(
            dict(_line(), text=f"Line {n}."), _rel(), "Aurel Voss",
            display="Sarah Moon", can_see=True, voice=self.CLAUSE,
            prev_standing=frozenset(), order_key=n) for n in range(3)]
        text = render_view(lines, mode="player", language="en").text
        assert text.count("The voice is") == 1
        assert text.index("The voice is") < text.index("Line 1.")

    def test_the_voice_is_said_by_the_first_line_that_can_say_it(self):
        """Review round 2 (2026-10-05): a first line that arrives as a
        fragment cannot say the voice, and keeping it there left the voice
        filed as known and never said."""
        far = composer.Percept(kind="speech", channel="hearing", source_label="Sarah Moon",
                               fidelity="fragment", order_key=0, salience=0.5,
                               dedupe_key="speech:far",
                               data={"fragment": "...attenuated...", "attributed": True,
                                     "voice_key": "voice:sarah", "tone": "",
                                     **composer._voice_fields(self.CLAUSE.rstrip("."), "", False)})
        near = composer.Percept(kind="speech", channel="hearing", source_label="Sarah Moon",
                                fidelity="full", order_key=1, salience=0.5,
                                dedupe_key="speech:near",
                                data={"body": "Line two.", "level": "full", "volume": "normal",
                                      "can_see": True, "voice_key": "voice:sarah", "tone": "",
                                      **composer._voice_fields(self.CLAUSE.rstrip("."), "", False)})
        text = render_view([far, near], mode="player", language="en").text
        assert text.count("The voice is") == 1 and "Line two." in text

    def test_over_the_radio_the_line_ends_before_the_voice_is_said(self):
        p = composer.Percept(kind="speech", channel="hearing", source_label="Sarah Moon",
                             fidelity="full", order_key=0, salience=0.5,
                             data={"body": "Copy.", "level": "full", "volume": "normal",
                                   "can_see": False, "via": "the radio", "tone": "",
                                   **composer._voice_fields("dry, clipped, and certain, never "
                                                            "rising whatever the news", "", False)})
        text = render_view([p], mode="player", language="en").text
        assert "over the radio. The voice is dry" in text

    def test_a_register_said_apart_keeps_one_stop(self):
        fields = composer._voice_fields(
            "Barely above a whisper, dropping to nothing at the end of every line.", "", False)
        assert fields["said_apart"] == ("barely above a whisper, dropping to nothing "
                                        "at the end of every line")

    def test_a_lines_own_tone_stays_in_its_slot(self):
        """A register describes a voice, always; a line's own tone stays in
        its slot as it always has (review rounds 1-3, 2026-10-05: classifying
        tones as conduct or voice in two scripts cost more than it fixed)."""
        fields = composer._voice_fields("", "barely a whisper, dropping to nothing at the end", True)
        assert "said_apart" not in fields

    def test_japanese_conduct_keeps_its_slot_and_memory_keeps_no_voice(self):
        from language_runtime import language_scope
        with language_scope("ja"):
            conduct = composer._voice_fields(
                "", "にやりと笑みを浮かべ、目を細めて肩をすくめながら", True)
        assert "said_apart" not in conduct
        p = composer.speech_percept(
            _line(), _rel(), "Aurel Voss", display="Sarah Moon", can_see=True,
            voice="明るく、くだけた、芝居がかった、警告もなく重々しい威厳に変わる",
            prev_standing=frozenset())
        memory = composer.render_episode([p], language="ja")[0]
        assert "その声は" not in memory

    def test_the_japanese_view_says_a_clause_voice_apart_in_its_own_words(self):
        p = composer.speech_percept(
            _line(), _rel(), "Aurel Voss", display="Sarah Moon", can_see=True,
            voice="明るく、くだけた、芝居がかった、警告もなく重々しい威厳に変わる",
            prev_standing=frozenset())
        text = render_view([p], mode="player", language="ja").text
        assert "その声は、明るく、くだけた" in text and "声ににじませ" not in text


class TestTheRenderFilesTheVoice:
    def test_the_english_view_files_the_voice_key_as_standing(self):
        view = render_view([_percept()], mode="player", language="en")
        assert VOICE_KEY in view.standing_keys
        assert "flat, clinical monotone" in view.text

    def test_the_second_view_says_the_line_without_the_tag(self):
        view = render_view([_percept(prev=frozenset({VOICE_KEY}))],
                           mode="player", prev_standing=frozenset({VOICE_KEY}),
                           language="en")
        assert "monotone" not in view.text
        assert "Sound transmission is attenuated." in view.text

    def test_the_japanese_view_files_the_same_key(self):
        view = render_view([_percept()], mode="player", language="ja")
        assert VOICE_KEY in view.standing_keys
        assert "flat, clinical monotone" in view.text
        later = render_view([_percept(prev=frozenset({VOICE_KEY}))],
                            mode="player", prev_standing=frozenset({VOICE_KEY}),
                            language="ja")
        assert "monotone" not in later.text


class TestAKnownVoiceSurvivesSilence:
    """The ledger is rolled forward a turn at a time; a key not re-filed is
    gone. A voice key was re-filed only on a beat the speaker spoke, so one
    silent beat made the next line a first hearing again (descent copy,
    beats 120-121)."""

    def test_the_english_view_carries_the_voice_through_a_silent_beat(self):
        presence = Percept(kind="presence", channel="sight", source_label="Sarah Moon",
                           data={"tier": "close", "body": body_key("Sarah Moon")},
                           salience=0.3, dedupe_key="presence:x")
        view = render_view([presence], mode="player",
                           prev_standing=frozenset({VOICE_KEY}), language="en")
        assert VOICE_KEY in view.standing_keys

    def test_the_japanese_view_carries_it_too(self):
        presence = Percept(kind="presence", channel="sight", source_label="Sarah Moon",
                           data={"tier": "close", "body": body_key("Sarah Moon")},
                           salience=0.3, dedupe_key="presence:x")
        view = render_view([presence], mode="player",
                           prev_standing=frozenset({VOICE_KEY}), language="ja")
        assert VOICE_KEY in view.standing_keys


# The card's half -- "leave `tone` empty in your ordinary voice" -- went with
# the full card (2026-09-27): the bare card asks for `how` on a `say` and
# `compile_bare` files it as the line's `tone`, which this ledger reads as a
# departure. Recorded as open in docs/UNBUILT_CHARACTERS.md §6.17.



def test_a_register_said_apart_needs_the_speaker_seen():
    """Review round 4 (2026-10-05): the manner slot says a voice only of a
    line SEEN and not conducted (`_inject_dialogue`), and a long register
    said apart reached a listener in the dark -- sheet text that can name
    the body it belongs to. Unseen, the line says no register at all."""
    from agents import composer
    fields = composer._voice_fields(
        "bright, informal, theatrical, and highly articulate, shifting into "
        "grave authority without warning", "", False, can_say=False)
    assert "said_apart" not in fields


def test_a_voice_first_heard_unseen_is_said_once_it_is_seen():
    """Review round 5 (2026-10-05): every rendered line filed its voice as
    established, said or not -- a voice heard round a corner was "known"
    before its register was ever said, and the line seen next said none."""
    unseen = composer.speech_percept(
        _line(), _rel(), "Aurel Voss", display="a voice", can_see=False,
        voice=TestAVoiceThatIsAClause.CLAUSE, prev_standing=frozenset())
    filed = render_view([unseen], mode="player", language="en").standing_keys
    seen = composer.speech_percept(
        _line(), _rel(), "Aurel Voss", display="Sarah Moon", can_see=True,
        voice=TestAVoiceThatIsAClause.CLAUSE, prev_standing=frozenset(filed))
    assert "The voice is" in render_view([seen], mode="player", language="en").text
