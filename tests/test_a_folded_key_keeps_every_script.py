"""A comparison key keeps the letters of every script.

The engine's slugs were spelled `re.sub(r"[^a-z0-9]+", "_", text.casefold())`
in thirty files (world_spatial_structure_light F2 counted 67 such classes),
and that class deletes every letter outside ASCII: `台所` folded to "", "Café
Rouge" to "caf_rouge", and two owners named in kana folded to the same empty
string -- the shed-garment key `jacket_` was minted once for two different
bodies (persist_scene_entities F2: `two owners -> {'jacket_': 'ヒナミ'}`).

`language_runtime.fold_key` is the one replacement: NFKC, casefold, and
everything that is not a letter, digit or mark dropped (or, with `sep`,
collapsed to one separator). Identical to the old fold for ASCII, so an id
already minted keeps matching; different for every other script, which is the
point.
"""

from __future__ import annotations

import re

import pytest

from language_runtime import fold_key, fold_text, fold_words, script_of


@pytest.mark.parametrize("text, key", [
    ("台所", "台所"),
    ("Café", "café"),
    ("Mirelle's Mouth", "mirellesmouth"),
    ("佐藤・ヒナミ", "佐藤ヒナミ"),
    ("ＬＣＡＲＳ panel", "lcarspanel"),       # NFKC folds the full-width form
    ("ｶﾀｶﾅ", "カタカナ"),                    # and the half-width kana
    ("  ", ""),
    (None, ""),
])
def test_a_key_keeps_letters_of_every_script(text, key):
    assert fold_key(text) == key


def test_two_different_names_stay_different():
    """The case the key ends: two kana owners shedding one garment kind
    minted one object between them."""
    assert fold_key("ヒナミ") != fold_key("レイ")
    assert fold_key("jacket", "_") + "_" + fold_key("ヒナミ", "_") \
        != fold_key("jacket", "_") + "_" + fold_key("レイ", "_")
    assert fold_key("ヒナミ") and fold_key("レイ")


@pytest.mark.parametrize("text", [
    "Back Yard", "Ten-Forward, Deck 10", "the captain's ready room",
    "  __Odd   spacing__ ", "Room #4 (east)", "deck10",
])
def test_a_separated_key_is_the_old_ascii_slug_for_ascii(text):
    """Every id minted by the old fold still matches its own spelling."""
    old = re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")
    assert fold_key(text, "_") == old
    assert fold_key(text, " ") == re.sub(r"[^a-z0-9]+", " ",
                                         text.casefold()).strip()


def test_a_separated_key_keeps_a_japanese_place():
    assert fold_key("裏庭の 物置", "_") == "裏庭の_物置"
    assert fold_key("Café Rouge", "_") == "café_rouge"


def test_fold_text_is_the_normalisation_alone():
    assert fold_text("ＡＢＣ　Café!") == "abc café!"


def test_words_split_at_spaces_punctuation_and_script_changes():
    """An unspaced name is segmented by its scripts -- the parts a family
    name and a given name are written in -- and a spaced word is the old
    `[a-z0-9]+` token for ASCII."""
    assert fold_words("佐藤ヒナミは台所に入った") == [
        "佐藤", "ヒナミ", "は", "台所", "に", "入", "った"]
    for text in ("Deck10 o'clock, the rain-slick lane", "A 3.5m hall"):
        assert fold_words(text) == re.findall(r"[a-z0-9]+", text.casefold())
    assert fold_words("Café Rouge") == ["café", "rouge"]


@pytest.mark.parametrize("char, script", [
    ("あ", "hiragana"), ("ア", "katakana"), ("ｱ", "katakana"),
    ("ー", "katakana"), ("台", "han"), ("々", "han"), ("ヶ", "han"),
    ("한", "hangul"), ("ก", "thai"), ("A", ""), ("1", ""), ("・", ""),
    ("、", ""), ("", ""),
])
def test_the_script_of_a_character(char, script):
    assert script_of(char) == script
