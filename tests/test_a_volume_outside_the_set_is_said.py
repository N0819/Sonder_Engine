"""A volume word outside the closed set is read as normal, and SAID.

`normalize_speech_volume` turned any word it did not know into "normal"
without a word: raw captures held `muttered`, `low` x8, "pitched low, only
for Hinami" x2 and `projected` x3 (2026-09-08..24), each graded as an
ordinary voice -- a line the speaker kept low heard by the whole room, and
nothing on the step to say so (review 2026-11-01, llm_schemas_prompts F2).
The default stays normal (UNBUILT_CHARACTERS §6.19 leaves the quiet fallback
to the owner); the fold is now a step warning naming the word.

And the alias table disagreed with the card. `encoder/core.txt`: volume "is
how far the speaker means the words to carry, never how they sound: a soft,
breathy, shaky, murmured or moaned line ... carries as any voice does, at
normal unless something says how far it was meant to go". The table folded
`soft`/`softly` to mutter and `excited`/`enthusiastic` -- how a voice
sounds -- to loud. The card is followed: they are normal, as are the card's
own breathy, shaky, murmured and moaned, which are named there and so are not
"outside the set" to warn about.
"""
from __future__ import annotations

import pytest

from core.pipeline_context import current_warning_sink
from llm.schemas import normalize_speech_volume


@pytest.fixture
def said():
    seen = []
    token = current_warning_sink.set(seen.append)
    yield seen
    current_warning_sink.reset(token)


@pytest.mark.parametrize("word", ["whispered", "low", "projected",
                                  "pitched low, only for Hinami"])
def test_an_unknown_word_is_normal_and_said(said, word):
    assert normalize_speech_volume(word) == "normal"
    assert any(repr(word) in w and "normal" in w for w in said), said


@pytest.mark.parametrize("word", ["soft", "softly", "breathy", "shaky",
                                  "murmured", "moaned", "excited",
                                  "enthusiastic"])
def test_how_a_voice_sounds_is_not_how_far_it_carries(said, word):
    assert normalize_speech_volume(word) == "normal"
    assert said == [], "the card names these: no warning"


@pytest.mark.parametrize("word,member", [
    ("whisper", "whisper"), (" Ear ", "ear"), ("quietly", "mutter"),
    ("raised voice", "loud"), ("yelling", "shout"), ("pitched", "pitched"),
    ("", "normal"), (None, "normal")])
def test_the_closed_set_and_its_aliases_are_unchanged_and_silent(said, word, member):
    assert normalize_speech_volume(word) == member
    assert said == []
