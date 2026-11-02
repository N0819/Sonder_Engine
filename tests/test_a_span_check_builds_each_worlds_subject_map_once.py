"""One span's receipts fold each world's subject spellings once, not once per
comparison.

world_misc_causal E1 (audit 2026-11-01): `causal_verification._same` asked
`canonical_subject` for both sides of every comparison, and each ask rebuilt
the whole `canonical_subject_map` (O(names x aliases)). `_record` compares
once per key of a channel table and the stations check nests it, so one
`verify_patch` of positions and stations over 30 entities with aliases took
624 ms (904 map rebuilds), 7.6 s at 100 -- on a path every
`merge_scene_with_diff(..., causal_worlds=...)` runs per step. The worlds a
span is checked against are fixed for the call, so each is folded once.
"""

from copy import deepcopy

import world.spatial_identity as spatial_identity
from world import causal_verification


def _world(n):
    entities, positions, stations = {}, {}, {}
    for i in range(n):
        name = "Person %d" % i
        entities["p%d" % i] = {"name": name, "kind": "person",
                               "aliases": ["P%d" % i, "the %dth" % i]}
        positions[name] = "hall"
        stations[name] = {"near": ["Person %d" % ((i + 1) % n)]}
    return {"rooms": {"hall": {"name": "Hall"}}, "entities": entities,
            "positions": positions, "stations": stations,
            "attire": {"Person 0": {"wearing": []}}}


def test_each_world_is_folded_once_per_span(monkeypatch):
    before = _world(12)
    after = deepcopy(before)
    after["positions"]["Person 3"] = "hall"
    after["stations"]["Person 3"] = {"near": ["Person 4"]}
    patch = {"positions": {"Person 3": "hall"},
             "stations": {"Person 3": {"near": ["Person 4"]}}}
    builds = []
    real = spatial_identity._live_subject_spellings

    def counting(scene):
        builds.append(id(scene))
        return real(scene)

    monkeypatch.setattr(spatial_identity, "_live_subject_spellings", counting)
    receipts = causal_verification.verify_patch(before, after, patch)
    assert receipts
    assert len(builds) <= 2, len(builds)
    assert set(builds) <= {id(before), id(after)}


def test_the_receipts_are_the_ones_the_unfolded_reading_gave(monkeypatch):
    before = _world(6)
    after = deepcopy(before)
    after["stations"]["Person 2"] = {"near": ["Person 3", "Person 1"]}
    patch = {"stations": {"Person 2": {"near": ["Person 3", "Person 1"]}},
             "positions": {"P2": "hall"}}
    folded = causal_verification.verify_patch(before, after, patch)
    # The same call with no memo: every comparison folds the scene afresh.
    monkeypatch.setattr(causal_verification, "_subject_map",
                        causal_verification._build_subject_map)
    plain = causal_verification.verify_patch(before, after, patch)
    assert folded == plain


def test_nothing_is_kept_once_the_call_returns():
    before = _world(3)
    causal_verification.verify_patch(before, deepcopy(before),
                                     {"positions": {"Person 1": "hall"}})
    assert getattr(causal_verification._SUBJECT_MAPS, "maps", None) is None
