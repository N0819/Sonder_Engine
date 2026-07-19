"""Tests for actor-specific ability lookup."""

import json
from types import SimpleNamespace

from character_schema import default_character_data, default_persona_data
from scene import _ability_mod

def test_actor_cannot_borrow_another_characters_ability(monkeypatch):
    monkeypatch.setattr(
        "scene.persona_of",
        lambda chat: default_persona_data("Player"),
    )

    alice_sheet = default_character_data("Alice")
    alice_sheet["competence"]["abilities"] = [
        {
            "name": "Swordplay",
            "level": "novice",
            "scope": "",
            "limits": "",
            "notes": "",
        },
    ]

    bob_sheet = default_character_data("Bob")
    bob_sheet["competence"]["abilities"] = [
        {
            "name": "Swordplay",
            "level": "master",
            "scope": "",
            "limits": "",
            "notes": "",
        },
    ]

    ctx = SimpleNamespace(
        chat={},
        cast=[
            {"id": 1, "sheet": json.dumps(alice_sheet)},
            {"id": 2, "sheet": json.dumps(bob_sheet)},
        ],
    )

    assert _ability_mod("Alice", "Swordplay", ctx) == 0
    assert _ability_mod("Bob", "Swordplay", ctx) == 6
    assert _ability_mod("Player", "Swordplay", ctx) == 0
    assert _ability_mod("Unknown", "Swordplay", ctx) == 0