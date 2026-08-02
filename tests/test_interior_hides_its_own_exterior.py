"""You cannot see the outside of what you are standing inside.

An entity's `description` is its EXTERIOR — what a body in the room around it
takes in. Handed to its own occupant it reads as a thing across the way.

Live, chat 58 "Run! ⎇10 ⎇20" t38. The player stood in the TARDIS console room
and her view read: "Through the doorway the rain-slicked plaza glitters under
dim streetlights … while a blue police box — its paint darkened by rain —
settles with a heavy thud on the cobbles." The plaza is correct: the doors were
open and the city is genuinely through them. The police box is the box she was
standing in, landing, seen from inside itself.

The engine already knew the relationship — `_body_interior_holder` resolves a
room-parented interior, and `spatial_rel_between` sets `inside_source` from it
— but that flag only ever conducted SOUND. Nothing withheld the exterior from
the occupant.

Only the outward appearance goes. The entity itself stays: presence is not the
leak, and the room's own `parent_entity` already says what you are inside.
"""

from __future__ import annotations

import pytest

from agents.common import _perceptible_entities

SCENE = {
    "rooms": {
        "plaza": {"name": "Northern Plaza", "adjacent": []},
        "console": {"name": "Console Room", "parent_entity": "tardis",
                    "adjacent": [{"to": "plaza", "barrier": "open_door",
                                  "distance": "near"}]},
    },
    "positions": {"Hinami": "console", "The Doctor": "plaza",
                  "tardis": "plaza"},
    "entities": {
        "tardis": {"name": "The TARDIS", "interior_rooms": ["console"],
                   "description": "A blue police box, paint darkened by rain."},
        "dumpster": {"name": "A dumpster",
                     "description": "Rust-streaked, lid ajar."},
    },
}


def _tardis_for(who):
    ents = _perceptible_entities(SCENE, [who])
    return next(v for v in ents.values() if v.get("name") == "The TARDIS")


def test_the_occupant_is_not_shown_the_exterior():
    assert _tardis_for("Hinami").get("description") in (None, "")


def test_someone_standing_outside_still_sees_it():
    assert "blue police box" in _tardis_for("The Doctor")["description"]


def test_the_entity_itself_is_not_removed():
    """Presence is not the leak — and the room's `parent_entity` already tells
    the occupant what they are inside."""
    assert _tardis_for("Hinami")["name"] == "The TARDIS"


def test_other_entities_are_untouched_for_the_occupant():
    ents = _perceptible_entities(SCENE, ["Hinami"])
    dump = next(v for v in ents.values() if v.get("name") == "A dumpster")
    assert "Rust-streaked" in dump["description"]


def test_a_scene_with_no_interiors_is_unaffected():
    flat = {
        "rooms": {"plaza": {"name": "Plaza", "adjacent": []}},
        "positions": {"Hinami": "plaza", "dumpster": "plaza"},
        "entities": {"dumpster": {"name": "A dumpster",
                                  "description": "Rust-streaked, lid ajar."}},
    }
    ents = _perceptible_entities(flat, ["Hinami"])
    dump = next(v for v in ents.values() if v.get("name") == "A dumpster")
    assert "Rust-streaked" in dump["description"]


def test_no_perceiver_named_keeps_the_whole_table():
    ents = _perceptible_entities(SCENE, None)
    t = next(v for v in ents.values() if v.get("name") == "The TARDIS")
    assert "blue police box" in t["description"]
