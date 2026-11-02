"""One sentence splitter, aware of abbreviations and of every script's stops.

`referring.SENTENCE_END` -- the fourth splitter UNBUILT_PIPELINE 1.69 did not
list, and the one that DOES decide what a mind receives -- was
`(?<=[a-z]{3}[.!?])\\s+|(?<=[。！？])`: it split after any abbreviation of
four or more letters and never after a digit, an acronym or a non-ASCII
letter. Measured (dressing audit F6), the labels an observer is handed:

    'A grizzled former Capt. of the harbour guard, ...' -> 'the grizzled former capt'
                                    (the sentence cut at the title)
    'A stocky dwarf in his 300s. He wears chainmail.'  -> ladder step
                                    'the stocky dwarf in his 300s. he wears chainmail'
    'An elderly man of the RAF. He walks with a cane.' -> ladder step
                                    'the elderly man of the raf. he walks with a cane'

`language_runtime.split_sentences` is the one splitter: ASCII `.!?` followed
by whitespace, never after one of the pack's `_SENTENCE_ABBREVIATIONS`; the
full-width stops with no whitespace needed; a closing bracket or quote stays
with the sentence it closes.
"""

from __future__ import annotations

import pytest

from language_runtime import join_sentences, language_scope, split_sentences


@pytest.mark.parametrize("text, sentences", [
    ("A grizzled former Capt. of the harbour guard, broad and scarred.",
     ["A grizzled former Capt. of the harbour guard, broad and scarred."]),
    ("A stocky dwarf in his 300s. He wears chainmail.",
     ["A stocky dwarf in his 300s.", "He wears chainmail."]),
    ("An elderly man of the RAF. He walks with a cane.",
     ["An elderly man of the RAF.", "He walks with a cane."]),
    ("A woman at the café. She smiles.",
     ["A woman at the café.", "She smiles."]),
    ("Dr. Moon and Mrs. Hale are tall.", ["Dr. Moon and Mrs. Hale are tall."]),
    ("A 3.5 m hall. Lit.", ["A 3.5 m hall.", "Lit."]),
    ('She said "Go." He left.', ['She said "Go."', "He left."]),
    ('"Hi!" she said. Then left.', ['"Hi!" she said.', "Then left."]),
    ("Big. Strong.", ["Big.", "Strong."]),
    ("", []),
    ("   ", []),
])
def test_english_sentences(text, sentences):
    assert split_sentences(text) == sentences


@pytest.mark.parametrize("text, sentences", [
    ("ヒナミは狐耳の背の高い女性。彼女は笑う。",
     ["ヒナミは狐耳の背の高い女性。", "彼女は笑う。"]),
    ("「こんにちは。」彼女は笑った。", ["「こんにちは。」", "彼女は笑った。"]),
    # A quotation closed and carried on by its quotative particle is one
    # sentence: the と belongs to the sentence the quote is inside.
    ("「行こう。」と彼は言った。次の朝。", ["「行こう。」と彼は言った。", "次の朝。"]),
    ("本当に！？嘘でしょう。", ["本当に！？", "嘘でしょう。"]),
])
def test_japanese_sentences(text, sentences):
    with language_scope("ja"):
        assert split_sentences(text) == sentences


def test_maxsplit_keeps_the_remainder_as_written():
    assert split_sentences("One here. Two  here. Three.", 1) == [
        "One here.", "Two  here. Three."]


def test_join_spaces_a_spaced_script_and_not_an_unspaced_one():
    assert join_sentences(["琥珀色の光。", "窓。", "A room.", "Lit."]) == \
        "琥珀色の光。窓。A room. Lit."


def test_the_label_splitter_is_the_one_splitter():
    from agents.common import _SENTENCE_END
    from language_runtime import referring

    assert referring.SENTENCE_END is _SENTENCE_END
    assert _SENTENCE_END.split("Dr. Moon and Mrs. Hale are tall.", 1)[0] == \
        "Dr. Moon and Mrs. Hale are tall."
    assert referring.first_sentence(
        "A grizzled former Capt. of the harbour guard, broad and scarred.") == \
        "A grizzled former Capt. of the harbour guard, broad and scarred."


@pytest.mark.parametrize("summary", [
    "A grizzled former Capt. of the harbour guard, broad and scarred.",
    "A stocky dwarf in his 300s. He wears chainmail.",
    "An elderly man of the RAF. He walks with a cane.",
])
def test_a_stranger_label_never_runs_into_the_next_sentence(summary):
    from agents.common import stranger_label_ladder

    label, ladder = stranger_label_ladder("Pell Varro", summary)
    for step in [label, *ladder]:
        assert ". " not in step, step
        assert not step.endswith((" he", " she")), step


def test_a_title_no_longer_cuts_the_features_off_a_label():
    """Cut at "Capt." the label had no features to widen through; read to its
    end, the summary's own "of the harbour guard" is there for the ladder."""
    from agents.common import stranger_label_ladder

    _label, ladder = stranger_label_ladder(
        "Pell Varro",
        "A grizzled former Capt. of the harbour guard, broad and scarred.")
    assert any("harbour guard" in step for step in ladder), ladder
