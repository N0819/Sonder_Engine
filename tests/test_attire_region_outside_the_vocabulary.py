"""An authored outfit region the engine cannot name keeps its clothes (A89).

`normalize_regions` used to `continue` past any key outside `attire.REGIONS`,
so an extra-parts card writing `initial_outfit.regions = {"tail": {...}}` lost
the garment entirely -- silently, while the coverage path beside it warned.

The rule now: a key naming a body part the card DECLARED re-homes onto the
region that part emerges from, worn AT it (`attaches`, the representation
clothing on an extra part already has); anything else lands on
`DEFAULT_REGION`, where an author can find it, and the card says so.
"""

from story import attire
from story import character_schema as cs


_WRAP = "a beaded tail wrap"


def _outfit():
    return {"regions": {"tail": {"garments": [{"name": _WRAP}]}}}


def test_a_declared_part_rehomes_to_the_region_it_emerges_from():
    regions = attire.normalize_regions(_outfit(), parts={"tail": "waist"})
    assert list(regions) == ["waist"]
    garment = regions["waist"]["garments"][0]
    assert garment["name"] == _WRAP
    # Worn AT the waist: a tail-wrap was never claiming to cover it.
    assert garment["attaches"] is True


def test_an_undeclared_part_lands_on_the_default_region_rather_than_nowhere():
    regions = attire.normalize_regions(_outfit())
    assert list(regions) == [attire.DEFAULT_REGION]
    assert regions[attire.DEFAULT_REGION]["garments"][0]["name"] == _WRAP


def test_a_rehomed_key_joins_the_region_the_card_also_wrote_by_name():
    """Additive, and the region's own record of itself stands."""
    regions = attire.normalize_regions(
        {"regions": {
            "tail": {"garments": [{"name": _WRAP}], "beneath": "russet fur"},
            "waist": {"garments": [{"name": "a sash"}],
                      "beneath": "an old scar"},
        }},
        parts={"tail": "waist"})
    names = [g["name"] for g in regions["waist"]["garments"]]
    assert names == ["a sash", _WRAP]
    assert regions["waist"]["beneath"] == "an old scar"


def test_the_card_carries_the_part_map_into_its_own_outfit():
    sheet = cs.normalize_character_data({
        "identity": {"name": "Kit"},
        "embodiment": {"extra_parts": [{"kind": "tail", "at": "waist"}]},
        "initial_outfit": _outfit(),
    })
    regions = sheet["initial_outfit"]["regions"]
    assert list(regions) == ["waist"]
    assert regions["waist"]["garments"][0]["name"] == _WRAP
    # And the derived flat mirror agrees, which is what the seed path reads.
    assert sheet["initial_outfit"]["wearing"] == [_WRAP]


def test_extra_part_regions_answers_singular_and_plural():
    mapping = cs.extra_part_regions([{"kind": "wings", "at": "torso"}])
    assert mapping["wings"] == "torso"
    assert mapping["wing"] == "torso"


def test_an_undeclared_part_is_named_on_the_card():
    warnings = cs.character_card_warnings({
        "identity": {"name": "Kit"},
        "initial_outfit": _outfit(),
    })
    assert any("initial_outfit places clothing at tail" in w for w in warnings)


def test_a_declared_part_draws_no_warning():
    warnings = cs.character_card_warnings({
        "identity": {"name": "Kit"},
        "embodiment": {"extra_parts": [{"kind": "tail", "at": "waist"}]},
        "initial_outfit": _outfit(),
    })
    assert not any("initial_outfit places clothing" in w for w in warnings)
