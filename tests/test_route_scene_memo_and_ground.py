"""Review 2026-09-07 C6/C17: the route scene is merged once per diff content
per turn, and a dry beat skips the per-room ground walk.
"""
import world.weather as weather
from agents.director import route_scene_for
from persist.commit import _advance_ground


def test_the_route_scene_is_shared_until_the_diff_changes():
    ctx = {}
    scene = {"rooms": {"a": {"adjacent": []}}, "positions": {}, "entities": {}}
    sd = {"positions": {"Aurel": "a"}}
    first = route_scene_for(ctx, scene, sd)
    assert route_scene_for(ctx, scene, sd) is first
    sd["positions"]["Aurel"] = "b"
    assert route_scene_for(ctx, scene, sd) is not first
    assert route_scene_for(None, scene, sd) is not None, "no context, no memo"


def test_a_dry_beat_with_nothing_on_the_floor_skips_the_walk(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no exposure walk on a dry beat")
    monkeypatch.setattr(weather, "room_exposure", boom)
    sc = {"rooms": {"a": {}, "b": {}}, "weather": {"precipitation": "none"},
          "ground": {}}
    _advance_ground(1, sc)
    assert "ground" not in sc
