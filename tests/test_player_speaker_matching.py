"""Regression tests for is_player_speaker: the substring-matching bug that
misattributed an NPC's dialogue to the player whenever the NPC's name
happened to contain the player's name as a substring (e.g. "Alexandra"
matching player persona "Alex")."""

from __future__ import annotations

import json

import scene
from character_schema import default_persona_data


def _make_persona(db, name):
    sheet = default_persona_data(name)
    return db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (name, json.dumps(sheet), "{}"),
    )


def test_npc_with_containing_name_is_not_misattributed(temp_db):
    persona_id = _make_persona(temp_db, "Alex Chen")
    chat = {"persona_id": persona_id}

    assert scene.is_player_speaker("Alexandra", chat) is False
    assert scene.is_player_speaker("Alexander", chat) is False


def test_partial_first_or_last_name_still_matches(temp_db):
    # The whole-word fallback exists precisely so a model attributing a
    # line to just "Alex" or just "Chen" (instead of the full persona
    # name) still resolves to the player.
    persona_id = _make_persona(temp_db, "Alex Chen")
    chat = {"persona_id": persona_id}

    assert scene.is_player_speaker("Alex", chat) is True
    assert scene.is_player_speaker("Chen", chat) is True


def test_exact_full_name_matches(temp_db):
    persona_id = _make_persona(temp_db, "Alex Chen")
    chat = {"persona_id": persona_id}

    assert scene.is_player_speaker("Alex Chen", chat) is True
    assert scene.is_player_speaker("alex chen", chat) is True


def test_generic_placeholder_terms_match(temp_db):
    persona_id = _make_persona(temp_db, "Alex Chen")
    chat = {"persona_id": persona_id}

    assert scene.is_player_speaker("the player", chat) is True
    assert scene.is_player_speaker("You", chat) is True


def test_unrelated_npc_name_does_not_match(temp_db):
    persona_id = _make_persona(temp_db, "Alex Chen")
    chat = {"persona_id": persona_id}

    assert scene.is_player_speaker("Dr. Crusher", chat) is False
    assert scene.is_player_speaker("Vrenak", chat) is False
