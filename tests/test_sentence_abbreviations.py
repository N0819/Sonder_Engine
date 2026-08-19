"""A title's period does not end a sentence.

Live, chat 82 "Sarah Moon — Hinami attempt 2", t0 and t1. The observation
annex's room note read "From this side the mirror is transparent glass. The
observation chair is occupied by Dr. Sarah Moon." Sarah Moon's own view of her
own room came out ending "...is occupied by Dr."

Nothing in the guard chain was wrong on its own. `_SENTENCE_SPLIT` breaks on a
period followed by whitespace, and a title is a period followed by whitespace,
so the note arrived as two sentences: one ending "by Dr." and a fragment that
is nothing but the perceiver's name. `_strip_self_narration` drops whole
sentences whose subject is the perceiver, the fragment IS the perceiver, and it
went — correctly, by its own rule, applied to a sentence that was never one.

Written without the title the same note is untouched, because then her name
sits inside a real sentence and no whole sentence is only her. That is the
signature of the class: the defect needs an abbreviation immediately before a
NAME, which is exactly where titles live.
"""

from __future__ import annotations

from agents.common import split_sentences
from agents.perception import _strip_self_narration_quote_safe


def test_the_title_keeps_its_name():
    assert split_sentences(
        "Mrs. Hudson brought tea to Dr. Watson. Then she left.") == [
        "Mrs. Hudson brought tea to Dr. Watson.", "Then she left."]


def test_an_ordinary_full_stop_still_splits():
    assert split_sentences("He arrived. She left.") == [
        "He arrived.", "She left."]


def test_a_sentence_final_abbreviation_is_left_alone():
    """`etc.` and `Ph.D.` genuinely end sentences, so they are not in the set:
    rejoining there would weld two real sentences into one."""
    assert split_sentences("Rope, lamp oil, bombs, etc. Then we left.") == [
        "Rope, lamp oil, bombs, etc.", "Then we left."]


def test_the_view_keeps_the_name_the_split_used_to_amputate():
    note = ("From this side the mirror is transparent glass. The observation "
            "chair is occupied by Dr. Sarah Moon.")
    view, dropped, refused = _strip_self_narration_quote_safe(
        note, "Sarah Moon", ["Sarah Moon", "Hinami"])
    assert view == note
    assert dropped == [] and refused == []


def test_third_person_narration_of_the_perceiver_is_still_cut():
    """The repair widens what counts as one sentence; it must not soften the
    guard that decides about them.

    Before it, "Dr. Watson ..." reached that guard already broken in half, so
    the second piece opened with the bare name and the cut fired BY ACCIDENT,
    leaving the dangling "Dr." behind. Handing the sentence back whole would
    have lost the catch and turned a visible defect into a silent one -- so
    `_subject_opener` now admits a title standing immediately before the name.
    A title used INSTEAD of a name ("the captain") is still refused: that one
    can tell two bodies apart, and this one cannot.
    """
    view, dropped, _refused = _strip_self_narration_quote_safe(
        "The lamp gutters. Dr. Watson's jaw tightens.", "Watson", ["Watson"])
    assert view == "The lamp gutters."
    assert dropped == ["Dr. Watson's jaw tightens."]


def test_a_bare_title_still_does_not_open_a_subject():
    """`_NAME_LEADERS` may lead a name, never stand in for one."""
    view, dropped, _refused = _strip_self_narration_quote_safe(
        "The lamp gutters. The doctor's jaw tightens.", "Watson", ["Watson"])
    assert view == "The lamp gutters. The doctor's jaw tightens."
    assert dropped == []
