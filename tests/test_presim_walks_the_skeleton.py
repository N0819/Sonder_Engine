"""Prehistory walks the planted skeleton instead of teleporting over it.

`presim_registry` ran with no scene, so every one of a generated town's 720
prehistory hours was a teleport move (Harrowmere, 2026-09-02: `travelled` = 1
per body over a month), while the same registry's first in-play catch-up
composed `charter["scene"]` from the same planted skeleton and walked it.
`plant_structure` precedes presim, so the fix is one argument: the skeleton
in scene shape (`skeleton_scene`), stamped on every institution that does not
already carry one.

Measured on the Harrowmere plan closed at 100 residents, 720h at 4h windows,
seed 3: no scene 5.7s, 55 walked edges, 52 bodies with a walk record;
skeleton 6.5s, 8,193 walked edges over 91 bodies, replay byte-identical.
"""

from __future__ import annotations

import copy
import json
import os

import pytest

from world.charter_generate import close_plan
from world.charter_runtime import (
    normalize_registry, presim_registry, skeleton_scene)

_HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="module")
def town():
    with open(os.path.join(_HERE, "data", "harrowmere_plan.json")) as fh:
        return close_plan(json.load(fh), population=40)


def _registry(town):
    return normalize_registry({"items": {
        key: {"state": copy.deepcopy(state), "window_hours": 4.0}
        for key, state in town["charters"].items()}})


def _walked(registry):
    edges = []
    for item in registry["items"].values():
        for body, routes in (item["state"].get("walked") or {}).items():
            for frm, tos in routes.items():
                for to, n in tos.items():
                    edges.append((body, frm, to, int(n)))
    return edges


def test_the_skeleton_is_the_planted_rooms_in_scene_shape(town):
    scene = skeleton_scene(town["rooms"])
    assert set(scene["rooms"]) == set(town["rooms"])
    for uid, room in scene["rooms"].items():
        assert room["planned"] is True
        assert room["name"] == town["rooms"][uid]["name"]
        assert [e["to"] for e in room["adjacent"]] == \
            [e["to"] for e in town["rooms"][uid]["adjacent"]]


def test_with_the_skeleton_bodies_walk_and_every_walk_is_a_planned_edge(town):
    scene = skeleton_scene(town["rooms"])
    before, _e = presim_registry(
        _registry(town), horizon_hours=48.0, active_tail_hours=8.0, seed=3)
    after, _e = presim_registry(
        _registry(town), horizon_hours=48.0, active_tail_hours=8.0, seed=3,
        scene=scene)
    walked_before = sum(n for *_x, n in _walked(before))
    walked_after = sum(n for *_x, n in _walked(after))
    assert walked_after > walked_before
    adjacent = {(uid, e["to"]) for uid, room in scene["rooms"].items()
                for e in room["adjacent"]}
    for _body, frm, to, _n in _walked(after):
        # The pathfinder walks a declared edge from either side.
        assert (frm, to) in adjacent or (to, frm) in adjacent, (frm, to)
    assert all(item["state"].get("scene") for item in after["items"].values())


def test_an_institution_that_already_carries_a_scene_keeps_it(town):
    registry = _registry(town)
    own = {"rooms": {"only": {"name": "Only", "adjacent": []}}}
    first = sorted(registry["items"])[0]
    registry["items"][first]["state"]["scene"] = copy.deepcopy(own)
    out, _e = presim_registry(
        registry, horizon_hours=8.0, active_tail_hours=4.0, seed=1,
        scene=skeleton_scene(town["rooms"]))
    assert out["items"][first]["state"]["scene"]["rooms"].keys() == {"only"}


def test_no_scene_is_exactly_the_old_behaviour(town):
    a, ea = presim_registry(
        _registry(town), horizon_hours=24.0, active_tail_hours=4.0, seed=2)
    b, eb = presim_registry(
        _registry(town), horizon_hours=24.0, active_tail_hours=4.0, seed=2,
        scene=None)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert ea == eb


def test_the_walked_prehistory_replays_identically(town):
    scene = skeleton_scene(town["rooms"])
    a, ea = presim_registry(
        _registry(town), horizon_hours=48.0, active_tail_hours=8.0, seed=3,
        scene=scene)
    b, eb = presim_registry(
        _registry(town), horizon_hours=48.0, active_tail_hours=8.0, seed=3,
        scene=scene)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert ea == eb
