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


def test_both_packs_tell_the_character_tone_is_a_departure():
    for pack, marker in (("en", "YOUR VOICE IS ALREADY KNOWN"),
                         ("ja", "あなたの声はすでに知られている")):
        text = pathlib.Path("language_packs", pack, "cards", "system_prompts",
                            "prompts", "character.txt").read_text(encoding="utf-8")
        assert marker in text, pack
