"""A dice roll's actor is an identity HANDLE, and the handle finds its sheet.

The Director builds `flow.dice` from causal-ledger rows whose
`source_entity_id` `normalize_causal_ledger` has already turned into an
identity handle -- `persona:7`, `persona:primary`, `character:58`. And
`_ability_mod` compared that handle against the persona's NAME and each
cast sheet's name, so every production roll read a modifier of 0: an
authored mechanic with no effect on any outcome. `tests/test_ability_
isolation.py` passed because it pinned display names, which production
never sends (story_scene_schema audit F11; agents_director_core audit F6,
second half -- whether the encoder is asked for `ability`/`difficulty` at
all is that report's owner decision, and not this fix).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from story.character_schema import default_character_data, default_persona_data
from story.scene import _ability_mod


def _ability(name, level):
    return {"name": name, "level": level, "scope": "", "limits": "",
            "notes": ""}


def _ctx(monkeypatch):
    player = default_persona_data("Kai Rowan")
    player["competence"]["abilities"] = [_ability("Lockpicking", "expert")]
    monkeypatch.setattr("story.scene.persona_of", lambda chat: player)
    co_player = default_persona_data("Mira Vale")
    co_player["competence"]["abilities"] = [_ability("Climbing", "master")]

    alice = default_character_data("Alice")
    alice["competence"]["abilities"] = [_ability("Swordplay", "novice")]
    bob = default_character_data("Bob")
    bob["competence"]["abilities"] = [_ability("Swordplay", "master")]
    return SimpleNamespace(
        chat={"persona_id": 7},
        cast=[{"id": 1, "sheet": json.dumps(alice)},
              {"id": 2, "sheet": json.dumps(bob)}],
        extra_players=[{"persona_id": 9, "persona": co_player,
                        "name": "Mira Vale"}],
    )


def test_a_character_handle_reads_that_characters_sheet(monkeypatch):
    ctx = _ctx(monkeypatch)
    assert _ability_mod("character:2", "Swordplay", ctx) == 6
    assert _ability_mod("character:1", "Swordplay", ctx) == 0
    assert _ability_mod("character:99", "Swordplay", ctx) == 0


def test_the_players_handles_read_the_players_sheet(monkeypatch):
    ctx = _ctx(monkeypatch)
    assert _ability_mod("persona:7", "lockpicking", ctx) == 4
    assert _ability_mod("persona:primary", "lockpicking", ctx) == 4


def test_a_co_players_handle_reads_their_own_sheet(monkeypatch):
    ctx = _ctx(monkeypatch)
    assert _ability_mod("persona:9", "climbing", ctx) == 6
    assert _ability_mod("persona:9", "lockpicking", ctx) == 0
    assert _ability_mod("persona:4", "lockpicking", ctx) == 0


def test_display_names_still_resolve(monkeypatch):
    ctx = _ctx(monkeypatch)
    assert _ability_mod("Bob", "Swordplay", ctx) == 6
    assert _ability_mod("Kai Rowan", "lockpicking", ctx) == 4
    assert _ability_mod("Mira Vale", "climbing", ctx) == 6
