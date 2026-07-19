"""Regression test for spatial_frames.infer_companion_carry.

Bug: when the player's own declared action narrates OTHER present
characters moving/boarding a vehicle alongside them (e.g. "I climb into
the ship, the Doctor and Reya right behind me"), director_resolve's
state_diff.positions reliably updates the PLAYER's own position but not
the companions'. Confirmed 3 times live (a ship, then a TARDIS, twice).

Fix: infer_companion_carry is a deterministic backstop, mirroring
infer_vehicle_zones' role -- narrow and specific (vehicle-interior or
pre-diff gap-crossing only), not a general "figure out who else moved"
solver.
"""

from __future__ import annotations

import json
import time

import spatial_frames


def _base_scene():
    return {
        "rooms": {
            "room_a": {"name": "Room A", "adjacent": []},
            "room_b": {"name": "Room B", "adjacent": []},
            "ship_cockpit": {
                "name": "Cockpit", "adjacent": [], "parent_entity": "ship",
            },
        },
        "entities": {
            "ship": {
                "kind": "vehicle", "name": "Ship",
                "interior_rooms": ["ship_cockpit"],
            },
        },
        "positions": {
            "The Stranger": "room_a",
            "Reya": "room_a",
            "ship": "room_a",
        },
        "attire": {}, "overlays": {},
    }


class TestInferCompanionCarry:
    def test_companion_co_located_with_player_is_carried_into_vehicle_interior(
        self, temp_db,
    ):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        prev_scene = _base_scene()
        new_scene = json.loads(json.dumps(prev_scene))
        # Diff only moves the player -- Reya's position is left untouched,
        # exactly like the live bug: the Director moved the player into
        # the vehicle interior but never wrote Reya's matching entry.
        new_scene["positions"]["The Stranger"] = "ship_cockpit"

        changed = spatial_frames.infer_companion_carry(
            chat_id, None, prev_scene, new_scene, ["Reya"], [],
        )

        assert changed is True
        assert new_scene["positions"]["Reya"] == "ship_cockpit"

    def test_companion_not_co_located_is_not_carried(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        prev_scene = _base_scene()
        prev_scene["positions"]["Reya"] = "room_b"  # not with the player

        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["positions"]["The Stranger"] = "ship_cockpit"

        changed = spatial_frames.infer_companion_carry(
            chat_id, None, prev_scene, new_scene, ["Reya"], [],
        )

        assert changed is False
        assert new_scene["positions"]["Reya"] == "room_b"

    def test_companion_explicitly_departed_this_beat_is_not_carried(
        self, temp_db,
    ):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        prev_scene = _base_scene()
        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["positions"]["The Stranger"] = "ship_cockpit"

        cast_changes = [
            {"who": "Reya", "status": "departed", "reason": "stayed behind"},
        ]

        changed = spatial_frames.infer_companion_carry(
            chat_id, None, prev_scene, new_scene, ["Reya"], cast_changes,
        )

        assert changed is False
        assert new_scene["positions"]["Reya"] == "room_a"

    def test_companion_already_explicitly_moved_by_diff_is_not_overridden(
        self, temp_db,
    ):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        prev_scene = _base_scene()
        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["positions"]["The Stranger"] = "ship_cockpit"
        # The diff DID explicitly place Reya somewhere else this beat.
        new_scene["positions"]["Reya"] = "room_b"

        changed = spatial_frames.infer_companion_carry(
            chat_id, None, prev_scene, new_scene, ["Reya"], [],
        )

        assert changed is False
        assert new_scene["positions"]["Reya"] == "room_b"

    def test_ordinary_movement_with_no_vehicle_or_gap_does_not_trigger(
        self, temp_db,
    ):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        prev_scene = _base_scene()
        # room_a and room_b are adjacent -- ordinary movement, not a gap
        # crossing, and room_b is not a vehicle interior.
        prev_scene["rooms"]["room_a"]["adjacent"] = [
            {"to": "room_b", "barrier": "open", "distance": "near"},
        ]
        prev_scene["rooms"]["room_b"]["adjacent"] = [
            {"to": "room_a", "barrier": "open", "distance": "near"},
        ]
        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["positions"]["The Stranger"] = "room_b"

        changed = spatial_frames.infer_companion_carry(
            chat_id, None, prev_scene, new_scene, ["Reya"], [],
        )

        assert changed is False
        assert new_scene["positions"]["Reya"] == "room_a"
