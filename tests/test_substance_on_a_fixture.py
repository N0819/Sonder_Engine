"""A room's own fixture is a destination for matter, as it is for touch."""
from world.spatial import _substance_target_exists


def _scene():
    return {"rooms": {"mill_race": {"name": "Mill and Race",
                                    "anchors": {"lower_bearing": {"kind": "fixture"}}},
                      "mill_yard": {"name": "Mill Yard", "anchors": {}}},
            "positions": {"Emory Vane": "mill_race"}}


def test_a_fixture_takes_tallow():
    """Playerless Aldermill round 3 (2026-09-23): six substance adds on the
    wheel's bearing were discarded as "target is not present"."""
    assert _substance_target_exists(_scene(), "lower_bearing")


def test_nothing_the_scene_holds_is_still_absent():
    assert not _substance_target_exists(_scene(), "staging_post")
