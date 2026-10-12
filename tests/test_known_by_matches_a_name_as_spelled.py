"""A private entry reaches the person its `known_by` spells.

Hollowmere (scratch chat 196, 2026-10-12): the generated companion card wrote
`known_by: ["mattias_brenn", "agathe_brenn"]`, matched against display names
exactly, so those entries reached nobody, forever -- the card warning said so
and nothing fixed it. `story.scene._shares_with` matches by name, case aside,
or as an identifier spells the name; a class of people written that way
still names no one.
"""
from __future__ import annotations

from story.scene import _shares_with, _spelled


def test_a_name_written_as_an_identifier_reaches_its_person():
    assert _shares_with("agathe brenn", ["mattias_brenn", "agathe_brenn"])
    assert _shares_with("agathe brenn", ["Agathe  Brenn"])
    assert _shares_with("dr. sarah moon", ["dr_sarah_moon"])


def test_a_name_that_is_not_theirs_does_not():
    assert not _shares_with("agathe brenn", ["all_staff", "the town"])
    assert not _shares_with("agathe brenn", [])


def test_a_name_in_any_script_is_spelled_by_its_own_letters():
    assert _spelled("アガーテ・ブレン") == "アガーテ_ブレン"
    assert _shares_with("アガーテ・ブレン", ["アガーテ_ブレン"])
