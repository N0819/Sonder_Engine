"""Every region rebuild carries every region-level flag (review A61).

A region record holds two kinds of thing: the garments on it, and flags that
are facts about the BODY -- `uncovered`, the authored `beneath` surface, the
per-zone `beneath_zones`. Three of the four rebuilds in `story/attire.py`
carried `uncovered`; `dedupe_regions` -- the fork heal that runs inside
`normalize_regions`, which `rederive_entry` runs on EVERY read -- rebuilt
`{garments, beneath}` and dropped it. So a body carrying two spellings of one
garment lost its shed record on the next read while the store still held it,
and `beneath` was withheld from every description afterwards.

`attire.region_record` is now the one region constructor; these tests hold
each rebuild to it.
"""

from story import attire


def _forked_regions():
    """A bared torso, and -- elsewhere -- two spellings of one garment.

    The fork is on the LEGS on purpose: `dedupe_regions` rebuilds every
    region the moment any one of them forks, so a duplicate spelling on the
    trousers is what erased the torso's shed record.
    """
    return {
        "torso": {
            "garments": [],
            "beneath": "a long scar under the collarbone",
            "uncovered": True,
        },
        "legs": {
            "garments": [
                {"name": "canvas work trousers", "state": "worn",
                 "condition": "", "description": ""},
                {"name": "work trousers", "state": "worn",
                 "condition": "", "description": "patched"},
            ],
            "beneath": "",
        },
    }


def test_fork_heal_keeps_the_regions_shed_record():
    healed = attire.dedupe_regions(_forked_regions())
    # The fork itself is healed -- one garment on the legs, not two.
    assert len(healed["legs"]["garments"]) == 1
    assert healed["torso"]["uncovered"] is True
    assert healed["torso"]["beneath"] == "a long scar under the collarbone"


def test_every_read_of_a_forked_wardrobe_keeps_it():
    """`rederive_entry` runs `normalize_regions` on every read path."""
    entry = {"wearing": [], "state": [], "regions": _forked_regions()}
    once = attire.rederive_entry(entry)
    assert once["regions"]["torso"].get("uncovered") is True
    # And it is stable: reading the healed entry again does not lose it.
    twice = attire.rederive_entry(once)
    assert twice["regions"]["torso"].get("uncovered") is True


def test_an_observer_still_sees_the_bared_surface_after_a_fork_heal():
    """`perceptible_region_surfaces` gates `beneath` on `uncovered`."""
    entry = attire.rederive_entry(
        {"wearing": [], "state": [], "regions": _forked_regions()})
    surfaces = attire.perceptible_region_surfaces(
        entry["regions"], beneath_visible=True)
    assert "long scar under the collarbone" in surfaces["torso"]


def test_region_record_is_the_one_constructor():
    """Flags come from the entry, or from the previous region it merges onto."""
    made = attire.region_record(
        "torso", [], {"beneath_zones": {"chest": "freckles"}},
        previous={"uncovered": True, "beneath": "old bruising"})
    assert made["uncovered"] is True
    assert made["beneath"] == "old bruising"
    assert made["beneath_zones"] == {"chest": "freckles"}
    # Nothing to carry means no flag invented.
    assert attire.region_record("torso", [], {}) == {
        "garments": [], "beneath": ""}
