"""A follow follows where its target ends the beat, and boarding is an ending.

Hollowmere turn 4661 (scratch chat 196, 2026-10-11): the brakeman declared
his own follow of the inspector, the beat seated both of them in the
funicular car, and the follow carry -- which read room changes alone -- wrote
him the inspector's walk room on top of it. The merge read that as stepping
back out: the car climbed without its brakeman, and he was split into a scene
of his own.
"""
from __future__ import annotations

import pytest

from tests.director_fakes import prose_resolve_agent
from tests.test_director_movement import (_following_scene, _make_ctx,
                                          _quiet_character_result)

pytestmark = pytest.mark.usefixtures("prose_director")


def _scene():
    scene = _following_scene()
    scene["entities"]["cart"] = {"name": "covered cart", "kind": "vehicle",
                                 "interior_rooms": []}
    scene["positions"]["cart"] = "trail_b"
    return scene


def _resolve(temp_db, monkeypatch, diff, *, follows=True):
    import agents.director as director
    ctx = _make_ctx(temp_db, "trail_b")
    scene = _scene()
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"].update({"mover": "self", "arrives": True})
    if follows:
        ctx.character_results[ctx.cast[0]["id"]] = _quiet_character_result(
            {"op": "start", "target": "The Stranger", "reason": "go together"})
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent({"state_diff": diff}))
    return director.director_resolve(ctx, nonce=0)["state_diff"], scene


def test_the_follower_boards_where_the_one_followed_boards(temp_db, monkeypatch):
    diff, scene = _resolve(temp_db, monkeypatch, {
        "positions": {"The Stranger": "trail_b"},
        "containment": {"The Stranger": {"in": "cart", "mode": "inside"}}})
    assert diff["containment"]["Mara"] == {"in": "cart", "mode": "inside"}
    assert diff["positions"].get("Mara") in (None, "trail_a"), "no room of her own to undo it"
    from world.spatial import merge_scene_with_diff, room_of
    merged = merge_scene_with_diff(scene, diff)
    assert room_of(merged, "Mara") == room_of(merged, "The Stranger")


def test_a_follower_the_beat_already_seats_is_left_seated(temp_db, monkeypatch):
    diff, _scene_ = _resolve(temp_db, monkeypatch, {
        "positions": {"The Stranger": "trail_b"},
        "containment": {"The Stranger": {"in": "cart", "mode": "inside"},
                        "Mara": {"in": "cart", "mode": "inside"}}})
    seat = diff["containment"]["Mara"]
    assert (seat["in"], seat["mode"]) == ("cart", "inside")
    assert "Mara" not in diff["positions"] or diff["positions"]["Mara"] != "trail_b"


def test_a_ride_on_someone_is_not_a_boarding_to_follow(temp_db, monkeypatch):
    """Upon, not inside: the one followed rides a carrier in view, and the
    follower walks after them as before."""
    diff, _ = _resolve(temp_db, monkeypatch, {
        "positions": {"The Stranger": "trail_b"},
        "containment": {"The Stranger": {"in": "cart", "mode": "riding"}}})
    assert "Mara" not in (diff.get("containment") or {})
    assert diff["positions"]["Mara"] == "trail_b"
