"""A door the player cannot see has no open-or-shut on the page.

`_visible_portal_states` gates a room EDGE's door on whether its far room is
in view, which consults that room's light; the entity branches -- a
door-like entity, a lift hatch, a portal link -- were gated only on standing
in a "visible" room, and the player's own room is always counted visible.
So a player sitting in a pitch-dark storeroom was handed `"cabinet door":
"open"` for a cabinet another body opened silently, under a sheet rule that
says the prose "MUST match it" and calls these states the player "can
currently see" (review 2026-11-01, agents_narration_planner F18). Each
entity branch now asks whether the player sees the thing
(`_player_sees_character`, the gate `co_present_positions` already uses).
"""

from __future__ import annotations

from agents.narration import _player_sees_character, _visible_portal_states


def _scene(light):
    room = {"name": "Storeroom", "adjacent": []}
    if light:
        room["light"] = light
    return {"rooms": {"store": room},
            "positions": {"Tamsin": "store", "cabinet": "store"},
            "entities": {"cabinet": {"name": "cabinet door", "kind": "door",
                                     "state": {"open": True}}}}


def _states(light):
    sc = _scene(light)
    return _visible_portal_states(
        sc, "store", {"store"},
        sees=lambda key, room: _player_sees_character(sc, "Tamsin", "store", key, room))


def test_a_cabinet_opened_in_the_dark_is_not_reported():
    assert "cabinet door" not in _states("dark")


def test_in_a_lit_room_the_cabinet_is_seen_open():
    assert _states("lit").get("cabinet door") == "open"


def test_without_a_sight_gate_the_old_reading_stands():
    sc = _scene("dark")
    assert _visible_portal_states(sc, "store", {"store"}).get("cabinet door") == "open"
