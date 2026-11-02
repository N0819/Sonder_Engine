"""A retold claim loses its count, its place and its name in whatever script
it is written in, and never loses a word that was not a count.

world_misc_causal F2/F3 (audit 2026-11-01, CONFIRMED):
* In a Japanese claim nothing was ever redacted. The caller-supplied name
  and place were matched with `\\b`, which never falls between two
  characters of an unspaced script, so 「ミラ・ホルトが門の通路で衛兵を三人殺した」
  travelled word for word until `is_exhausted` stopped it -- the module's own
  rule is that hop 3 loses the NAME.
* In English the count list held idioms and vague quantities, and any digit
  run was a count: "settled the score" became "settled the several", "a
  couple of the guards" "a several of the guards", "at 10:30" "at
  several:several".

The words a language counts with, and the vaguer words that replace them,
are the language pack's (`linguistics.world.degradation`); a pack that does
not carry them degrades with the English defaults.
"""

import re

import pytest

import language_runtime
from world import degradation

JA_CLAIM = "ミラ・ホルトが門の通路で衛兵を三人殺した"


def test_a_name_and_a_place_in_an_unspaced_script_are_lost_in_order():
    names, places = ["ミラ・ホルト"], ["門の通路"]
    second = degradation.degrade(JA_CLAIM, degradation.TIER_PLACES,
                                 names=names, places=places)
    assert "門の通路" not in second and "ミラ・ホルト" in second
    third = degradation.degrade(JA_CLAIM, degradation.TIER_NAMES,
                                names=names, places=places)
    assert "ミラ・ホルト" not in third and "門の通路" not in third


def test_a_name_is_still_matched_only_whole():
    """「ミラ」 is not a name inside 「ミラーボール」, as "Mora" is not one
    inside "Morality"."""
    out = degradation.degrade("ミラーボールが回る", degradation.TIER_NAMES,
                              names=["ミラ"])
    assert out == "ミラーボールが回る"
    out = degradation.degrade("Morality left town", degradation.TIER_NAMES,
                              names=["Mora"])
    assert out == "Morality left town"


@pytest.mark.parametrize("claim", [
    "Mira settled the score with the miller",
    "a couple of the guards saw a handful of riders",
    "a few of them went home",
    "They met at 10:30 by the well",
])
def test_an_idiom_or_a_time_is_not_a_count(claim):
    assert degradation.degrade(claim, degradation.TIER_COUNTS) == claim


def test_an_article_before_a_count_goes_with_it():
    assert degradation.degrade("a dozen guards fell", degradation.TIER_COUNTS) \
        == "several guards fell"


def test_a_language_pack_supplies_its_own_counts_and_vague_words(monkeypatch):
    table = {
        "COUNT": re.compile(r"[二三四五六七八九十百千万]+(?=[人匹頭本])"),
        "ARTICLE": "",
        "VAGUE_COUNT": "数",
        "VAGUE_PLACE": "どこか",
        "VAGUE_PERSON": "見知らぬ誰か",
    }
    real = language_runtime.linguistic

    def fake(module, name, language_id=None):
        selected = language_runtime.current_language_id.get() \
            if language_id is None else language_id
        if module == "world.degradation" and selected == "ja":
            return table[name]
        return real(module, name, language_id)

    monkeypatch.setattr(language_runtime, "linguistic", fake)
    with language_runtime.language_scope("ja"):
        first = degradation.degrade(JA_CLAIM, degradation.TIER_COUNTS)
        third = degradation.degrade(JA_CLAIM, degradation.TIER_NAMES,
                                    names=["ミラ・ホルト"], places=["門の通路"])
    assert first == "ミラ・ホルトが門の通路で衛兵を数人殺した"
    assert third == "見知らぬ誰かがどこかで衛兵を数人殺した"
    # ...and an English story is untouched by the Japanese table.
    assert degradation.degrade("Mora killed three raiders", 3,
                               names=["Mora"]) == \
        "a stranger killed several raiders"
