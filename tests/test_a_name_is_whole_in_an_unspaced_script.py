"""A name is matched whole in an unspaced script, not as a run of letters.

`name_boundary_pattern` used to put NO assertion on an edge written in kana or
kanji, so a Japanese name matched anywhere its letters did (dressing audit F7):

    'ヒナミ' in 'ヒナミコは来た'  -> True   (inside a longer name)
    'ヒナミ' in 'アヒナミ'        -> True
    'レイ'   in 'プレイヤーは'    -> True   ("player")

and the concealment scrub of 角 (horns) rewrote 「角ばった顎」 (an angular jaw)
as 「ばった顎」 in every observer's view. The boundary is now the script's:
an edge is a boundary at the text's edge, at whitespace or punctuation, or
where the script changes (kana <-> kanji <-> Latin <-> digit); within katakana
or hiragana it is not, except that a hiragana edge may meet a particle; a
ONE-character kana/kanji name additionally needs a particle, copula or
honorific (a closed grammatical class), punctuation, another script or the
edge after it. A kanji name of two or more characters keeps an open right
edge on both sides, because Japanese compounds onto a kanji name -- a
title after it (田中部長, 佐藤隊長), a family name before a given name
written without its space (山田花子) -- and the name is in each of them:
closing it would let the identity scrub miss a name it must remove.

Latin behaviour is unchanged: the `\\b`-like refusal of `Hinamis`, case as
the caller's flags say.
"""

from __future__ import annotations

import re

import pytest

import language_runtime
from story import character_schema


CASES = [
    # (form, text, matches, why)
    ("ヒナミ", "ヒナミは棚に向かう。", True, "a particle ends a name"),
    ("ヒナミ", "ヒナミ、こっちへ", True, "punctuation ends a name"),
    ("ヒナミ", "ヒナミコは来た", False, "not inside a longer katakana name"),
    ("ヒナミ", "アヒナミ", False, "not the tail of a longer name"),
    ("レイ", "プレイヤーは笑った", False, "not inside 'player'"),
    ("レイ", "レイも見た", True, "a particle after a short name"),
    ("田中", "田中さんが来た", True, "an honorific after a kanji name"),
    ("田中", "田中部長が来た", True, "a title compounded onto a kanji name"),
    ("花子", "山田花子は笑った", True,
     "a given name inside a full name written without its space"),
    ("角", "角ばった顎の背の高い女性", False, "a one-kanji term needs a particle"),
    ("角", "額に二本の角がある", True, "a one-kanji term before a particle"),
    ("角", "部屋の一角に立つ", False, "not the tail of 一角"),
    ("角", "頭角を現す", False, "not the tail of 頭角"),
    ("凛", "凛は笑った", True, "a one-kanji given name"),
    ("凛", "凛ちゃん", True, "an honorific after a one-kanji name"),
    ("ヒナミ", "佐藤・ヒナミは", True, "a middle dot joins two names"),
    ("ヒナミ", "佐藤ヒナミは", True, "kanji to katakana is a boundary"),
    ("佐藤", "佐藤ヒナミは", True, "kanji to katakana is a boundary"),
    ("さくら", "彼女はさくらを見た", True, "a hiragana name between particles"),
    ("さくら", "あさくらは", False, "not inside a longer hiragana name"),
    ("さくら", "さくらんぼ", False, "not the head of a longer word"),
    ("Hinami", "Hinami reaches for it", True, "Latin, unchanged"),
    ("Hinami", "Hinamis walked away", False, "Latin, unchanged"),
    ("Hinami", "Hinami's arm", True, "Latin possessive, unchanged"),
    ("Hinami", "彼はHinamiに近づく", True, "a Latin name in Japanese prose"),
    ("Reya", "Reyanne entered", False, "Latin prefix, unchanged"),
    ("", "anything", False, "an empty name never matches"),
]


@pytest.mark.parametrize("form, text, matches, why", CASES)
def test_a_name_matches_whole_in_its_own_script(form, text, matches, why):
    pattern = language_runtime.name_boundary_pattern(form)
    assert bool(re.search(pattern, text, re.IGNORECASE)) is matches, why


@pytest.mark.parametrize("form, text, matches, why", CASES)
def test_the_character_schema_spelling_is_the_same_rule(form, text, matches, why):
    """`character_schema.name_boundary_pattern` is the name forty call sites
    import; it delegates, so there is one rule."""
    assert character_schema.name_boundary_pattern(form) \
        == language_runtime.name_boundary_pattern(form)
    assert bool(character_schema.name_boundary_regex(form, re.I).search(text)) \
        is matches, why


def test_latin_patterns_are_byte_identical_to_the_old_rule():
    """Every caller that composes a Latin pattern (`+ "(?:'s|’s)?"`, inside
    `(?-i:...)`, inside a named group) receives exactly what it always did."""
    spaced = r"A-Za-z0-9_À-ɏḀ-ỿͰ-ϿЀ-ӿ"
    for form in ("Hinami", "Dr. Moon", "the navigator", "Sulmirath-house",
                 "R2-D2", "Hinami's"):
        assert language_runtime.name_boundary_pattern(form) == (
            f"(?<![{spaced}])" + re.escape(form) + f"(?![{spaced}])")


def test_the_disguise_scrub_keeps_an_angular_jaw():
    """The over-subtraction the old rule produced in every observer's view."""
    text = "角ばった顎の背の高い女性、額に二本の角がある。"
    out = re.sub(language_runtime.name_boundary_pattern("角"), "", text)
    assert out == "角ばった顎の背の高い女性、額に二本のがある。"


def test_find_names_takes_the_longest_name_and_never_one_inside_another():
    """The set matcher the five "does this text name this place" readers need
    (mind_affect F6): "Great Hall" is not also "Hall", and 「ヒナミコ」 is not
    also 「ヒナミ」."""
    found = language_runtime.find_names(
        "Walk to the Great Hall, then the Hall.", ["Hall", "Great Hall", "Inn"])
    assert [(form, start) for start, _end, form in found] == [
        ("Great Hall", 12), ("Hall", 33)]
    found = language_runtime.find_names("ヒナミコとヒナミは", ["ヒナミ", "ヒナミコ"])
    assert [form for _s, _e, form in found] == ["ヒナミコ", "ヒナミ"]
    assert language_runtime.find_names("the beginning", ["Inn"]) == []
    assert language_runtime.find_names("", ["Inn"]) == []
    assert language_runtime.find_names("Inn", []) == []


def test_find_names_respects_the_callers_case_flags():
    assert language_runtime.find_names("the guard post", ["Guard"], flags=0) == []
    assert language_runtime.find_names("the guard post", ["Guard"])
