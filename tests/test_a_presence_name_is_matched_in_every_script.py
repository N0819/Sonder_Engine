"""A tracked presence's name is found in a line whatever script it is
written in -- and a description is narrowed by its words in every script.

The presence matchers wrapped a name in `\\b`, which is a rule about where an
English word ends: there is no word boundary between ハンナ and the
honorific or particle written onto it, so in a Japanese story the gate's
`named_exactly`/`mentioned` triggers, the writer's `mention_turns` (and with
them the mention promotion bar) and the player-precise reply debt never
fired for the ordinary spelling. `_word_stems` took `[a-z0-9]+`, so a
Japanese description had no words and PB6's narrowing never narrowed.
Measured (review 2026-11-01, persist_background_memory F15):
    named_exactly JA: False   ('ハンナ', 'ハンナさん、エールを一杯')
    mentioned JA:     False   ('ハンナ', 'ハンナは頷いた')
    named_exactly EN: True
`language_runtime.name_boundary_pattern` decides each edge by the NAME's
script; `fold_words` splits words by script.
"""

from __future__ import annotations

from persist.commit import (_background_name_mentioned,
                            _background_name_named_exactly,
                            _bodies_the_description_could_be_true_of,
                            _presence_addressed_match, _word_stems)


def test_a_japanese_name_with_an_honorific_is_named_exactly():
    assert _background_name_named_exactly("ハンナ", "ハンナさん、エールを一杯")


def test_a_japanese_name_with_a_particle_is_mentioned():
    assert _background_name_mentioned("ハンナ", "ハンナは頷いた")


def test_a_japanese_name_inside_a_longer_name_is_not_it():
    assert not _background_name_mentioned("ハンナ", "ハンナコは頷いた")
    assert not _background_name_named_exactly("ハンナ", "アハンナが来た")


def test_a_structured_address_with_an_honorific_names_its_body():
    assert _presence_addressed_match("ハンナ", "ハンナさん")


def test_the_english_readings_are_unchanged():
    assert _background_name_named_exactly("Trader Tate", "Trader Tate, a word")
    assert not _background_name_named_exactly("Tate", "Tates of the hill")
    assert _background_name_mentioned("Dr. Crusher", "Crusher nodded")
    assert _presence_addressed_match("Trader Tate", "Tate")
    assert _presence_addressed_match("Trader Tate", "Captain Trader Tate")


def test_a_japanese_description_has_words():
    words = _word_stems("エプロンの男")
    assert "エプロン" in words and "男" in words
    assert _word_stems("the men with aprons") >= {"men", "apron"}


def test_a_japanese_description_narrows_the_cohort():
    cohort = [
        ("給仕", {"sketch": {"appearance": "エプロンを着けた若い男"}}),
        ("番人", {"sketch": {"appearance": "鎧を着けた年配の男"}}),
    ]
    kept = _bodies_the_description_could_be_true_of(cohort, "エプロンの男")
    assert [name for name, _ in kept] == ["給仕"]
