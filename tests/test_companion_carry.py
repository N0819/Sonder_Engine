"""A companion who declared nothing stays where they stood.

`spatial_frames.infer_companion_carry` was a backstop from the causal
Director's era: when the player boarded a vehicle, every registered cast
member left in the player's old room was copied aboard, on the strength of
"people in the room walk aboard with you" and nothing the companion
declared. Measured 2026-10-07 over every stored beat (the scratch play db
and engine.db): 30 boardings, two firings, both wrong --

  * chat 20 turn 384: a lieutenant put aboard the shuttle he was at the
    station's override panel trying to stop;
  * scratch story 166 turn 4597: a pilot put in the boat while she stood
    mid-span on the bridge behind it, so the page had her "within arm's
    reach" and her own line torn apart by the fog.

The case it was built for does not occur any more: every TARDIS boarding in
both dbs carried the companion's own position, written by the encoder. And
the owner's ruling of the same day is that a mind goes only where its own
declaration takes it (`director_prose.a_walk_is_its_owners`).
"""

from __future__ import annotations

import json
import time

from world import spatial_frames
from world.mechanics import mechanics_sweep


def _scenes():
    prev_scene = {
        "rooms": {
            "room_a": {"name": "Room A", "adjacent": []},
            "ship_cockpit": {"name": "Cockpit", "adjacent": [],
                             "parent_entity": "ship"},
        },
        "entities": {"ship": {"kind": "vehicle", "name": "Ship",
                              "interior_rooms": ["ship_cockpit"]}},
        "positions": {"The Stranger": "room_a", "Reya": "room_a",
                      "ship": "room_a"},
        "attire": {}, "overlays": {},
    }
    new_scene = json.loads(json.dumps(prev_scene))
    new_scene["positions"]["The Stranger"] = "ship_cockpit"
    return prev_scene, new_scene


def test_the_sweep_puts_nobody_aboard_who_did_not_go(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    prev_scene, scene = _scenes()
    mechanics_sweep(scene, {"elapsed_seconds": 6}, None, [],
                    prev_scene=prev_scene, chat_id=chat_id)
    assert scene["positions"]["Reya"] == "room_a"
    assert scene["positions"]["The Stranger"] == "ship_cockpit"


def test_there_is_no_carry_to_call():
    assert not hasattr(spatial_frames, "infer_companion_carry")
