"""A disguise hides authored extra parts, not just the appearance summary.

Reported live (chat 72). A kitsune persona declared a glamour, the Director
encoded it correctly as a `physical_disguise` with
`presented_appearance: "ordinary human ears on the sides of her head"`, and
every observer's view still read:

    Six tails emerge from the back of Hinami's waist, golden and fluffy.
    Two fox ears emerge from the top of Hinami's head, fluffy pointed.

Nothing was broken in the disguise itself. `disguised_visible_appearance`
rewrites one string -- the appearance SUMMARY -- and authored extra parts are
a separate typed ledger that the composer renders straight from structured
data (`body_part_percepts` -> `_render_body_part`). The scrub never saw them,
because by the time there was prose to scrub the barrier was already behind
it.

The rule went through two versions and the second one is the point. A part
first survived if `presented_appearance` NAMED it -- reasonable, and wrong one
turn later: the Director wrote "...; no tails are visible", the word `tails`
was present, and six tails came back. A negation reads as a mention, and so do
"without", "hidden" and every other way prose says absence.

So prose may only CONCEAL. A part is shown through a disguise only via
`visible_parts`, a typed list with nothing to parse and nothing to negate --
which is also the seam an additive transformation wants, since granting a body
a part its card never declared is the same mechanism read the other way.
"""

import pytest

from scene import conceal_disguised_parts


TAILS = {"kind": "tail", "count": 6, "at": "waist", "aspect": "back"}
EARS = {"kind": "fox ear", "count": 2, "at": "head", "aspect": "top"}
WINGS = {"kind": "wing", "count": 2, "at": "back", "aspect": "back"}

GLAMOUR = {
    "presented_appearance": "ordinary human ears on the sides of her head",
    "concealed_terms": ["fox ears", "six golden tails", "tails", "kitsune"],
}


def test_the_reported_case():
    out = conceal_disguised_parts({"Hinami": [TAILS, EARS]},
                                  {"hinami": GLAMOUR})
    assert "Hinami" not in out


def test_an_undisguised_body_keeps_everything():
    """The overwhelmingly common case, and the one that must not regress: a
    cast with no disguise anywhere passes through untouched."""
    parts = {"Bryn": [WINGS]}
    assert conceal_disguised_parts(parts, {}) == parts
    assert conceal_disguised_parts(parts, {"hinami": GLAMOUR}) == parts


def test_a_typed_grant_shows_a_part_through_the_disguise():
    """Concealment, not deletion -- and the additive seam. A disguise that
    declares wings visible still has wings to show."""
    out = conceal_disguised_parts(
        {"Bryn": [WINGS]},
        {"bryn": {"presented_appearance": "a traveller",
                  "visible_parts": ["wing"]}})
    assert out["Bryn"] == [WINGS]


def test_a_negation_does_not_grant_a_part():
    """THE ONE THAT SHIPPED BROKEN. Measured live: the disguise said "no
    tails are visible", a name match found `tails`, and the glamour dropped
    on the very next turn. Prose cannot grant."""
    out = conceal_disguised_parts(
        {"Hinami": [TAILS]},
        {"hinami": {"presented_appearance": "normal human ears on the sides "
                                            "of her head; no tails are "
                                            "visible."}})
    assert "Hinami" not in out


def test_naming_a_part_in_prose_is_not_enough():
    """The generalisation of the above: any mention, negated or not, is
    ignored. Only the typed field is authority."""
    out = conceal_disguised_parts(
        {"Bryn": [WINGS]},
        {"bryn": {"presented_appearance": "a traveller with two great "
                                          "feathered wings"}})
    assert "Bryn" not in out


@pytest.mark.parametrize("kind,granted", [
    ("tail", ["tails"]),        # part singular, grant plural
    ("tails", ["tail"]),        # the other way round
    ("fox ear", ["fox ears"]),
])
def test_singular_and_plural_are_the_same_feature(kind, granted):
    """A near-miss on the grant hides a part that was meant to show, which is
    the harmless direction -- but the fold makes it behave anyway."""
    out = conceal_disguised_parts(
        {"X": [{"kind": kind, "count": 1}]},
        {"x": {"visible_parts": granted}})
    assert out["X"]


def test_a_legacy_disguise_hides_everything():
    """An information barrier fails toward concealment. A condition carrying
    only freeform prose says nothing reliable about which parts are covered,
    and guessing in the permissive direction undoes the disguise."""
    out = conceal_disguised_parts({"Hinami": [TAILS, EARS]},
                                  {"hinami": {"description": "a glamour"}})
    assert "Hinami" not in out


def test_only_the_disguised_body_is_touched():
    out = conceal_disguised_parts(
        {"Hinami": [TAILS], "Bryn": [WINGS]}, {"hinami": GLAMOUR})
    assert out == {"Bryn": [WINGS]}


def test_a_partless_cast_stays_empty_rather_than_growing_keys():
    """`scene_extra_parts` yields {} for a cast with no declarations, and
    every payload key hanging off it stays absent."""
    assert conceal_disguised_parts({}, {"hinami": GLAMOUR}) == {}


def test_the_gate_sits_where_names_are_still_true_names():
    """Filtering later -- at the percept build -- would have to match on
    observer-facing DISPLAY labels, and two bodies can both be "someone".
    This runs on `scene_extra_parts` output, whose keys are true body names."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "agents"
           / "perception.py").read_text(encoding="utf-8")
    block = src[src.index("def _composer_extra_parts"):]
    block = block[:block.index("\n\n\n")]
    assert "conceal_disguised_parts(cached" in block
    assert block.index("scene_extra_parts(") < block.index(
        "conceal_disguised_parts(")
