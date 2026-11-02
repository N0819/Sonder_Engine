"""The narrator's tic list never bans Japanese grammar, and never spells a
Japanese phrase one character at a time.

`_overused_phrases` reads an unspaced script one character per unit, and its
"must carry a content word" rule is `_TIC_STOPWORDS`, which is the same
English set in both packs -- so any three characters recurring across two
drafts were a tic, inflection included, and the narrator was handed the
progressive -ている, spaced out: `['っ て い る']` (agents_common audit F10). A
run of hiragana alone is grammar (particles, inflection), the caseless
script's analogue of a function-word run, and a phrase written without
spaces is listed without them.
"""

from __future__ import annotations

from language_runtime import language_scope

from agents.common import _already_established_phrases, _overused_phrases


def test_recurring_inflection_is_not_a_tic():
    with language_scope("ja"):
        tics = _overused_phrases(
            ["彼女はゆっくりと扉を開けている。外では雨が降っている。"],
            "彼は窓の外を見ている。誰かが笑っている。")
    assert tics == [], tics


def test_a_recurring_japanese_phrase_is_listed_as_written():
    with language_scope("ja"):
        tics = _overused_phrases(
            ["時計の針が静かに進む。", "暖炉の火が揺れる。時計の針が止まる。"],
            "時計の針が光る。")
        shared = _already_established_phrases(
            "窓の外を見つめている。", ["彼は窓の外を見つめていた。"])
    assert tics and all(" " not in t for t in tics), tics
    assert any("時計の針" in t for t in tics), tics
    assert shared and all(" " not in s for s in shared), shared


def test_english_tics_are_unchanged():
    tics = _overused_phrases(["The clock ticks on the wall."],
                             "Again the clock ticks somewhere.")
    assert tics == ["the clock ticks"], tics
