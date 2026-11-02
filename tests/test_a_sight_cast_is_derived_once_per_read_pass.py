"""The shadowcast a line of sight is decided over depends on the observer's
cell, the two heights and what the bodies lie on -- not on the pair -- so a
read pass casts it once per distinct question.

Audit world_spatial_movement_sight E1 (2026-11-01): `body_visibility` ran a
full-field shadowcast per call, unmemoised; the Director's digest asks n^2
pairs, and 8 bodies (56 pairs) in a 64x64 room took 409 ms, 96% of it in
`_visible_set`.
"""

import world.spatial_fov as fov
from world.scene_memo import scene_read_pass
from world.spatial import body_visibility


def _room():
    return {
        "rooms": {"hall": {"name": "hall", "extent": {"w": 12, "d": 12},
                           "anchors": {"pillar": {"desc": "a pillar", "cell": [6, 6],
                                                  "height": "full"}},
                           "adjacent": []}},
        "positions": {"A": "hall", "B": "hall", "C": "hall"},
        "stations": {"A": {"at": None, "near": [], "cell": [1, 1]},
                     "B": {"at": None, "near": [], "cell": [10, 10]},
                     "C": {"at": None, "near": [], "cell": [10, 2]}},
        "entities": {}, "orientation": {}, "poses": {},
        "attire": {"A": {}, "B": {}, "C": {}},
    }


def _counting(monkeypatch):
    calls = []
    real = fov._visible_set

    def counted(*args, **kwargs):
        calls.append(args[1])
        return real(*args, **kwargs)

    monkeypatch.setattr(fov, "_visible_set", counted)
    return calls


def test_one_cast_serves_every_target_of_one_observer_in_a_pass(monkeypatch):
    sc = _room()
    calls = _counting(monkeypatch)
    with scene_read_pass(sc):
        first = [body_visibility(sc, "A", t)["visible"] for t in ("B", "C")]
    assert len(calls) == 1
    calls.clear()
    second = [body_visibility(sc, "A", t)["visible"] for t in ("B", "C")]
    assert len(calls) == 2
    assert first == second
