"""A transformation's parts land on the same menus a card's parts do.

`agents.common.extra_part_phrase` renders "emerges from the {aspect} of the
{at}", and every visibility verdict is keyed by `attire.REGIONS`. A CARD's
parts are coerced on the way in (`character_schema._normalize_extra_parts`); a
`physical_transformation`'s parts are model free text and nothing coerced them,
so both fields arrived as prose and the phrase came out malformed:

    {"kind": "fox ears", "at": "top of the head",
     "aspect": "fluffy, pointed, golden"}
      -> "emerge from the fluffy, pointed, golden of the top of the head"

Live, chat 76: that sentence was delivered to the one observer entitled to it,
Hinami's own self-view, on every beat.

THE OFF-MENU TEXT IS SALVAGED, which is the one place this departs from the
card path. An author who miskeys a card sees it in the editor; a
transformation's stray text is the only description of that anatomy that
exists, and it is exactly the material detail worth delivering.
"""

from __future__ import annotations

from agents.common import extra_part_phrase
from scene import normalize_transformed_parts

LIVE = [
    {"kind": "fox ears", "count": 2, "at": "top of the head",
     "aspect": "fluffy, pointed, golden"},
    {"kind": "tails", "count": 6, "at": "back of the waist",
     "aspect": "golden and fluffy"},
]


def test_the_live_parts_render_grammatically():
    ears, tails = normalize_transformed_parts(LIVE)
    assert extra_part_phrase(ears).startswith(
        "fox ears x2 — emerge from the top of the head")
    assert extra_part_phrase(tails).startswith(
        "tails x6 — emerge from the back of the waist")


def test_the_description_survives_rather_than_being_discarded():
    """The card path throws the off-menu value away. Here it is the only
    description of that anatomy in existence."""
    ears, tails = normalize_transformed_parts(LIVE)
    assert "fluffy, pointed, golden" in extra_part_phrase(ears)
    assert "golden and fluffy" in extra_part_phrase(tails)


def test_a_placement_the_canonical_fields_already_say_is_not_repeated():
    """'top of the head' adds nothing once at=head and aspect=top."""
    ears = normalize_transformed_parts(LIVE)[0]
    assert ears["at"] == "head" and ears["aspect"] == "top"
    assert "top of the head" not in (ears.get("description") or "")


def test_an_existing_description_is_kept_alongside_the_salvage():
    part = dict(LIVE[0], description="twitching at every sound")
    out = normalize_transformed_parts([part])[0]
    assert "twitching at every sound" in out["description"]
    assert "fluffy, pointed, golden" in out["description"]


def test_a_card_shaped_part_passes_through_untouched():
    """The menus already hold, so nothing may move -- byte-identical phrase."""
    card = {"kind": "tail", "count": 1, "at": "waist", "aspect": "back",
            "description": "long and russet-furred"}
    out = normalize_transformed_parts([card])[0]
    assert out["at"] == "waist" and out["aspect"] == "back"
    assert out["description"] == "long and russet-furred"
    assert extra_part_phrase(out) == extra_part_phrase(card)


def test_the_region_is_a_visibility_key_afterwards():
    """The whole point: `at` must be something region_visibility can answer
    for, or the concealment gate has nothing to look up."""
    import attire

    for part in normalize_transformed_parts(LIVE):
        assert part["at"] in attire.REGIONS


def test_unchanged_and_none_stay_distinct():
    """`parts` absent means unchanged; `[]` means none. Collapsing them would
    make it impossible to transform INTO something plain."""
    assert normalize_transformed_parts([]) == []
    assert normalize_transformed_parts(None) == []


def test_junk_is_tolerated_not_crashed_on():
    assert normalize_transformed_parts([None, "tail", {}, {"kind": ""}]) == []
