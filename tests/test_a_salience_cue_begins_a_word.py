"""A salience cue is a word, and a word does not begin inside another one.

`_salience_of` scored every turn memory by its length plus 0.08 for each of
the pack's `_SALIENCE_CUES` found ANYWHERE in the text -- a bare substring
test, so "liar" counted inside "familiar", "promise" inside "compromised",
"love" inside "glove". `mind/memory_summaries` never archives a row at
salience 0.72 or above, and a 320-character memory scores 0.65 on length
alone, so one spurious cue made an ordinary memory permanently
unarchivable. Measured (review 2026-11-01, persist_background_memory F9):
    plain 54 chars                                              0.484
    "A familiar woman glanced at the compromised door ..."     0.657
    "He pulled on a glove at the deadline beside the secretary." 0.726
The sibling `_durable_dialogue_category` was fixed for the same class with
markers that must BEGIN at a word boundary, inflections still matching
("I promised"); the cues now follow the same rule, decided by the cue's own
script: a Japanese cue sits inside its compound as written (the ja pack's
kanji stems), a Latin one begins a word.
"""

from __future__ import annotations

from persist.commit import _salience_of


def _floor(text):
    return round(min(0.45 + min(len(text), 400) / 1600.0, 0.95), 3)


def test_a_cue_inside_another_word_is_not_a_cue():
    text = "A familiar woman glanced at the compromised door and left."
    assert _salience_of(text) == _floor(text)


def test_glove_is_not_love():
    text = "He pulled on a glove and walked into the clover."
    assert _salience_of(text) == _floor(text)


def test_an_inflected_cue_still_counts():
    text = "She was attacked on the stair and later confessed."
    assert _salience_of(text) == round(_floor(text) + 0.16, 3)


def test_the_measured_unarchivable_row_drops_below_the_bar():
    text = "He pulled on a glove at the deadline beside the secretary."
    assert _salience_of(text) < 0.72
