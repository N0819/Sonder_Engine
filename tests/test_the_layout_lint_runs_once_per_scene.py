"""The World Browser lints a scene's layout once per distinct scene, not once
per request.

Audit 2026-11-01 (web_routes_extensions Efficiency 1): `_lint_rows` re-ran
the whole-scene `room_layout_lint` on every index, slice, grid and map read
and on every write's response. Measured read-only on real scenes: 58 ms on
chat 172 (22 rooms), 40 ms on chat 175, 22 ms on chat 63 -- against 0.4-0.8
ms to parse the scene -- and one map edit is a write plus the client's
index/grid/map refetch, four passes over the same scene. Keyed on the
scene's CONTENT, not the row's read token: `get_scene` lays the layout
tier's solved plans over the stored blob (`structure.apply_solved_plans`),
so the scene a reader lints can change while its row does not. A digest
costs about 1 ms on those scenes.
"""

from __future__ import annotations

import copy

import pytest

from web import world_routes


@pytest.fixture(autouse=True)
def _fresh_memo():
    """Each test starts with nothing remembered: the memo is the process's."""
    memo = getattr(world_routes, "_LINT_MEMO", None)
    if memo is not None:
        memo.clear()
    yield


def _scene():
    return {"rooms": {
        "hall": {"name": "Hall", "size": "small", "extent": {"w": 30, "d": 30},
                 "adjacent": [{"to": "yard", "barrier": "open", "dir": "n"}]},
        "yard": {"name": "Yard",
                 "adjacent": [{"to": "hall", "barrier": "open", "dir": "n"}]},
    }}


def test_the_same_scene_is_linted_once(monkeypatch):
    calls = []
    real = world_routes.room_layout_lint

    def counting(scene, *args, **kwargs):
        calls.append(1)
        return real(scene, *args, **kwargs)

    monkeypatch.setattr(world_routes, "room_layout_lint", counting)
    scene = _scene()

    first = world_routes._lint_rows(scene)
    second = world_routes._lint_rows(copy.deepcopy(scene))

    assert first == second
    assert first, "the fixture scene should carry layout rows"
    assert len(calls) == 1


def test_a_changed_scene_is_linted_again(monkeypatch):
    calls = []
    real = world_routes.room_layout_lint
    monkeypatch.setattr(world_routes, "room_layout_lint",
                        lambda scene, *a, **k: calls.append(1) or real(scene, *a, **k))
    scene = _scene()
    world_routes._lint_rows(scene)
    scene["rooms"]["yard"]["adjacent"][0]["dir"] = "s"

    rows = world_routes._lint_rows(scene)

    assert len(calls) == 2
    assert not any(r["kind"] == "reciprocal_bearing_disagrees" for r in rows)


def test_a_caller_cannot_edit_the_remembered_rows(monkeypatch):
    scene = _scene()
    rows = world_routes._lint_rows(scene)
    rows[0]["text"] = "scribbled on"
    rows.clear()

    again = world_routes._lint_rows(scene)
    assert again and again[0]["text"] != "scribbled on"
