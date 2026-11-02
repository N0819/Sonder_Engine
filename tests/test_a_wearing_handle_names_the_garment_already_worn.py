"""A short handle in a `wearing` restatement is the garment already worn.

The encoder card tells the model "use the wearer's wardrobe handle -- it need
not repeat the full registered name ('robe' finds the one robe she is
wearing)", and `wearing` is one of the ladder channels it names. The commit's
write gate resolved those handles WITH the head-noun tier, as `remove`, `add`
and `replace` do; `apply_flat_change` resolved them WITHOUT it. So
`wearing: ["robe", "leather sandals"]` against "sheer obsidian silk robe that
parts with every movement" read to the gate as nothing omitted, and to the
reconcile as the robe gone and a new "robe" put on: `newly_removed` reported
the worn robe, the commit minted it as an object on the floor, and the body
went on wearing a second one under the shorter name -- the docstring's own
measured case, still open for one-word handles (story_attire_import audit F4;
the lane brief's F1).

The reconcile now matches a handle with the tier the gate uses -- after every
handle that names a garment more exactly has claimed its own, so two listed
garments of one noun stay two.
"""

from __future__ import annotations

from story import attire

ROBE = "sheer obsidian silk robe that parts with every movement"


def _worn(*names):
    return attire.normalize_regions({"wearing": list(names)})


def test_a_one_word_handle_keeps_the_worn_robe():
    before = _worn(ROBE, "leather sandals")
    after = attire.apply_flat_change(before, ["robe", "leather sandals"])
    assert attire.newly_removed(before, after) == []
    assert attire.flat_wearing(after) == [ROBE, "leather sandals"]


def test_the_same_for_a_blouse():
    before = _worn("white silk blouse", "grey skirt")
    after = attire.apply_flat_change(before, ["blouse", "grey skirt"])
    assert attire.newly_removed(before, after) == []
    assert sorted(attire.flat_wearing(after)) == ["grey skirt",
                                                  "white silk blouse"]


def test_two_listed_garments_of_one_noun_stay_two():
    before = _worn("white silk blouse")
    after = attire.apply_flat_change(before,
                                     ["white silk blouse", "cotton blouse"])
    assert attire.newly_removed(before, after) == []
    assert sorted(attire.flat_wearing(after)) == ["cotton blouse",
                                                  "white silk blouse"]


def test_a_garment_left_out_still_comes_off():
    before = _worn(ROBE, "leather sandals")
    after = attire.apply_flat_change(before, ["leather sandals"])
    assert [name for _region, name in attire.newly_removed(before, after)] \
        == [ROBE]


def test_an_ambiguous_handle_still_resolves_to_nothing():
    """Two robes make "robe" ambiguous, and an ambiguous handle must resolve
    to nothing rather than to a coin flip -- here, a new garment."""
    before = _worn("red silk robe", "black wool robe")
    after = attire.apply_flat_change(before, ["robe"])
    assert {name for _r, name in attire.newly_removed(before, after)} == {
        "red silk robe", "black wool robe"}
