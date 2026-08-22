"""A clothing STATE is not another garment, and an overlay is not either.

`scene.appearance_of` composes three clauses and labels each one:

    <base>; wearing: A, B, C; clothing state: X; currently: Y

`_appearance_as_prose` then rewrites those labels for prose, and the English
pack rewrote two of the three to a bare comma — so the state and the overlay
were absorbed into the garment list as members of it. The `wearing` clause kept
its word; the other two lost theirs.

Live, chat 82 t1. The player's view of the interviewer read

    ...wearing black button-up shirt, white lab coat, pencil skirt, black
    leggings, loafers, black leggings displaced off the groin.

and the narrator reproduced it faithfully, because from the sentence it was
handed there is nothing to tell the sixth item from the first five. The ledger
was right the whole way: `attire["Sarah Moon"]["state"]` holds exactly one
entry and it is a state.

The Japanese pack never had this — it renders the same three labels as
「、服装は」「、衣服の状態は」「、現在は」, keeping all three distinct. English
was the outlier.
"""

from __future__ import annotations

from agents.common import _appearance_as_prose
from story.scene import appearance_of

#: Exactly what `scene.appearance_of` composes: three labelled clauses. Fed to
#: the prose renderer directly, because that renderer is the unit that lost
#: two of the three labels -- and because `appearance_of` re-derives `state`
#: from `regions`, which would make this fixture a test of the attire model
#: instead of a test of the rewrite.
LABELLED = ("A tall woman.; wearing: white lab coat, black leggings"
            "; clothing state: black leggings displaced off the groin"
            "; currently: one finger resting on the talk plate")


def _prose():
    return _appearance_as_prose(LABELLED)


def test_the_state_does_not_join_the_garment_list():
    prose = _prose()
    garments, _, rest = prose.partition("black leggings displaced")
    assert rest, prose
    assert not garments.rstrip().endswith(","), (
        "the clothing state is separated from the wearing list by a bare "
        "comma, so it reads as one more garment: " + prose)


def test_every_clause_is_still_delivered():
    prose = _prose()
    for fragment in ("white lab coat", "black leggings displaced off the groin",
                     "one finger resting on the talk plate"):
        assert fragment in prose, (fragment, prose)


def test_the_overlay_does_not_join_the_garment_list_either():
    prose = _prose()
    garments, _, rest = prose.partition("one finger resting")
    assert rest, prose
    assert not garments.rstrip().endswith(","), prose


def test_a_body_with_only_garments_reads_as_one_clause():
    assert _appearance_as_prose("A tall woman.; wearing: white lab coat") \
        == "a tall woman, wearing white lab coat"


def test_the_japanese_pack_kept_all_three_labels():
    """It never had this defect -- the English rewrite was the outlier, and
    the fix is English catching up rather than a new idea."""
    import json

    labels = json.load(open(
        "language_packs/ja/cards/linguistics.json", encoding="utf-8"
    ))[
        "agents.common"]["_APPEARANCE_LABELS"]["items"]
    # FIRST match wins: the rewrite is a sequential `.replace`, so the
    # Japanese rows fire and the English fallback rows below them then find
    # nothing left to match.
    replacements = {}
    for row in labels:
        replacements.setdefault(row["items"][0], row["items"][1])
    assert replacements["; clothing state:"] != ","
    assert replacements["; currently:"] != ","
    # ...and its English fallback rows, which a Japanese story reaches only
    # for English-labelled text, must not reintroduce the flattening.
    assert not any(row["items"][1] == "," for row in labels)
