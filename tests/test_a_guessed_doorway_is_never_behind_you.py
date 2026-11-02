"""A doorway nobody gave a bearing to is never culled by the facing cone,
whichever room declared it.

Audit world_spatial_movement_sight F9 (2026-11-01, CONFIRMED WRONG-SCENE):
UNBUILT_PERCEPTION 1.147 (fixed 2026-09-06) rules that the cone may not hide a
doorway whose bearing nobody declared, "on either side of the edge" -- but
`_unbeared_doorways` read the OBSERVER room's own edges only. A doorway
declared only by the far room (31.3% of room pairs are one-sided) still got a
hash-placed anchor and never entered the carve-out: facing s, sw or w,
`door:y` was culled with basis 'cone' and handed a hash `side`.
"""

import pytest

from world.spatial import feature_visibility


def _scene(facing, *, declared_from="y"):
    rooms = {
        "x": {"name": "X", "extent": {"w": 6, "d": 6}, "anchors": {}, "adjacent": []},
        "y": {"name": "Y", "extent": {"w": 6, "d": 6}, "anchors": {}, "adjacent": []},
    }
    if declared_from == "y":
        rooms["y"]["adjacent"].append({"to": "x", "barrier": "open_door"})
    else:
        rooms["x"]["adjacent"].append({"to": "y", "barrier": "open_door"})
    return {"rooms": rooms, "positions": {"Ada": "x"},
            "stations": {"Ada": {"at": None, "near": [], "cell": [3, 3]}},
            "orientation": {"Ada": {"facing": facing}}, "entities": {},
            "attire": {"Ada": {}}}


@pytest.mark.parametrize("facing", ["n", "ne", "e", "se", "s", "sw", "w", "nw"])
@pytest.mark.parametrize("declared_from", ["x", "y"])
def test_an_unbeared_doorway_is_seen_and_claims_no_side(facing, declared_from):
    rows = {r["anchor"]: r for r in feature_visibility(
        _scene(facing, declared_from=declared_from), "Ada")}
    door = rows["door:y"]
    assert door["visible"] is True, (facing, declared_from, door)
    assert door["side"] is None and door["sector"] is None
