"""Whether two rooms are under the sky is the ONE reading of exposure the
rest of the engine uses (`weather.room_exposure`), not a second one.

Audit world_spatial_sound F11 (2026-11-01, CONFIRMED divergence, latent): the
vertical-edge sight rule's `_under_the_sky` read the raw `exposure` field --
any declared word but `enclosed` was sky, an absent field was `enclosed` --
while `weather.room_exposure` derives it (a `parent_entity` is enclosed; the
declared word; the keyword fallback). Measured: 118 live rooms with no declared
exposure that `room_exposure` calls open or sheltered read as enclosed here,
and 3 declared `indoor`/`interior` read as UNDER THE SKY, which the sight cap
answers "full ... no wall, no floor".
"""

from world.spatial import _under_the_sky
from world.weather import room_exposure


def _pair(lower, upper):
    return {"rooms": {"lower": lower, "upper": upper}}


def test_it_agrees_with_room_exposure_on_every_case():
    cases = [
        {"name": "The Market Square", "desc": "An open square under the sky."},
        {"name": "Porch", "exposure": "sheltered"},
        {"name": "Back Room", "exposure": "indoor"},
        {"name": "Cabin", "exposure": "interior"},
        {"name": "Hall", "exposure": "enclosed"},
        {"name": "Plain Room"},
        {"name": "Hold", "exposure": "open", "parent_entity": "ship"},
    ]
    for a in cases:
        for b in cases:
            sc = _pair(dict(a), dict(b))
            expected = (room_exposure(sc, "lower") != "enclosed"
                        and room_exposure(sc, "upper") != "enclosed")
            assert _under_the_sky(sc, "lower", "upper") is expected, (a, b)


def test_a_room_declared_indoor_is_not_under_the_sky():
    sc = _pair({"name": "Yard", "exposure": "open"},
               {"name": "Back Room", "exposure": "indoor"})
    assert _under_the_sky(sc, "lower", "upper") is False
