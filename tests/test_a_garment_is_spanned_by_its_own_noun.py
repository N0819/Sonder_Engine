"""What a garment covers is decided by the noun it IS, not a word describing it.

`regions_covered` spanned a garment by ANY spanning cue anywhere in its name,
while `region_of` (the anchor) reads the last cue and `attaches_only` the head
before a placement preposition -- three readers of "what is this thing",
three rules. So a modifier noun spanned the garment like the garment it
names: a "dress belt" covered torso, groin and legs, a "kimono sash" the
whole body, "dress shoes" everything from the shoulders down -- the very
"body in only a sash reads as dressed" failure the waist/groin split in
AGENTS.md exists to prevent (story_attire_import audit F10).

And `\\b` cannot fire inside a closed compound, so "overcoat", "raincoat" and
"petticoat" matched nothing and fell to the torso default, while the
comment claimed "overcoat" was a coat. A closed compound is its own word and
the table now holds it as one; the last letters of a word are not evidence of
what it is ("headdress" is not a dress).
"""

from __future__ import annotations

import pytest

from story import attire


@pytest.mark.parametrize("garment,covers", [
    ("dress belt", ("waist",)),
    ("kimono sash", ("waist",)),
    ("trouser belt", ("waist",)),
    ("dress shoes", ("feet",)),
    ("jeans jacket", ("torso", "arms", "waist")),
    ("silk kimono", ("torso", "arms", "waist", "groin", "legs")),
    ("long wool skirt", ("legs", "groin")),
])
def test_the_span_is_the_head_nouns(garment, covers):
    assert attire.regions_covered(garment) == covers


def test_a_garment_described_by_where_it_sits_is_not_spanned_by_the_place():
    assert "groin" not in attire.regions_covered("apron over the dress")
    assert "legs" not in attire.regions_covered("sash over a kimono")


def test_a_phrase_with_a_trailing_clause_still_finds_its_noun():
    covered = attire.regions_covered(
        "sheer obsidian silk robe that parts with every movement")
    assert covered == ("torso", "waist", "groin", "legs")


@pytest.mark.parametrize("compound", ["overcoat", "raincoat", "trenchcoat",
                                      "greatcoat"])
def test_a_closed_coat_compound_is_a_coat(compound):
    assert attire.regions_covered(compound) == attire.regions_covered("coat")
    assert attire.span_is_a_guess(compound) is False


def test_a_petticoat_is_worn_below_the_waist():
    assert attire.region_of("petticoat") == "legs"
    assert attire.regions_covered("petticoat") == \
        attire.regions_covered("skirt")
    assert attire.span_is_a_guess("lace petticoat") is False
