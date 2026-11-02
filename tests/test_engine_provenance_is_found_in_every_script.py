"""The provenance floor cuts the engine's note out, never the place.

`split_engine_provenance` judges a description sentence by sentence, and a
sentence ended only at ASCII `.!?`. A Japanese description has none: `。` was
not a boundary, so「港の事務所。机が並ぶ。」followed by an engine note was ONE
sentence, matched, and filed WHOLE as provenance -- the view, and the
persisted description, got nothing (story_scene_schema audit F7). The same
splitter broke "3.5 metres" into "3." and "5 metres", and rejoined them with
a space.

Sentences are now the engine's one splitter's (`language_runtime.
split_sentences`), joined back the way their script joins them; and the
parenthetical shape is recognised in full-width brackets too.
"""

from __future__ import annotations

from story.provenance_text import split_engine_provenance, strip_engine_provenance


NOTE = "generated because no candidate described this location."


def test_a_japanese_description_keeps_its_own_sentences():
    prose, note = split_engine_provenance("港の事務所。机が並ぶ。" + NOTE)
    assert prose == "港の事務所。机が並ぶ。"
    assert note == NOTE


def test_a_note_in_full_width_brackets_is_filed_not_delivered():
    text = "狭い踊り場（generated because no candidate described this floor）。"
    prose, note = split_engine_provenance(text)
    assert prose == "狭い踊り場。"
    assert "no candidate" in note


def test_a_decimal_is_not_a_sentence_break():
    prose, _note = split_engine_provenance(
        "The room is 3.5 metres wide. " + NOTE)
    assert prose == "The room is 3.5 metres wide."


def test_a_line_break_still_ends_a_note():
    prose, note = split_engine_provenance(
        "A cramped office\ngenerated because no candidate described it")
    assert prose == "A cramped office"
    assert note.startswith("generated because")


def test_text_without_a_note_is_returned_exactly():
    text = "港の事務所。机が並ぶ。\n窓は北を向く。"
    assert strip_engine_provenance(text) == text
