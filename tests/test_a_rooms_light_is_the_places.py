"""A room's declared light is what the place does to light, never the hour.

On open ground a room's own `light` meets the sky as the darker of the two
(`world.spatial_light.room_light`), so a declaration can only darken a day.
The shared place vocabulary listed "dusk falls" among the reasons to set it,
and the opening and the room designer wrote the hour they first saw a place
in: chat 44's "rooftops of the city at night" is declared `dark`, chat 58's
"plaza at night" `dim`, both night at noon -- 54 of 172 open rooms in the
owner's corpus (UNBUILT_PIPELINE §1.174, 2026-10-04). The sky is the
engine's: it keeps the hour and the weather.
"""

from __future__ import annotations

import pytest

from llm.prompts import prompt_fragment


def _light_paragraph(language):
    text = prompt_fragment("room_vocabulary", language)
    start = text.index("LIGHT:" if language == "en" else "光：")
    return text[start:text.index("\n", start)]


def test_the_english_vocabulary_gives_the_sky_to_the_engine():
    light = _light_paragraph("en")
    assert "what the PLACE does to the light it is given" in light
    assert "never when it is or what the sky is doing" in light
    assert "dusk falls" not in light


@pytest.mark.parametrize("language", ["en", "ja"])
def test_both_packs_name_the_four_words_the_engine_reads(language):
    """normalize_light reads the protocol words; a Japanese gloss in their
    place (薄暗い) was read as `lit`."""
    from world.spatial import normalize_light
    light = _light_paragraph(language)
    for word in ("dark", "dim", "lit", "bright"):
        assert word in light, (language, word)
        assert normalize_light(word) == word


def test_the_japanese_vocabulary_says_the_same_and_drops_the_dusk():
    light = _light_paragraph("ja")
    assert "時刻と天候はエンジンが持っており" in light
    assert "夕暮れになる" not in light
    assert "視認可能な光源" not in light
    assert "あなたのものではありません" not in light
