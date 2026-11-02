"""A card's player macro is resolved before a mind reads it, on every path.

`{{user}}` and `<USER>` become the neutral `{{PLAYER}}` token on the
heuristic import, and `start_story` resolves that token in the greeting --
but nothing else did (story_attire_import audit F11):

  * the AI-reinterpret import (the dialog's default) sent the card raw and
    stored whatever the model copied, so a sheet kept `{{user}}`,
    `<USER>` and `{{char}}` verbatim -- not even the canonical token;
  * a card's private history reached its own mind as "{{PLAYER}} owes me
    money": engine vocabulary inside a fictional mind, the class
    `greetings._PLAYER_SLOT` was written for.

The token is resolved for a mind through the identity floor the greeting
launch already uses: the persona's NAME when this mind knows it, a
description of the player's body when it does not -- never the name to a
stranger, and never "the player".
"""

from __future__ import annotations

import json
import time

from story import importers, scene
from story.character_schema import default_character_data, default_persona_data


def test_a_reinterpreted_card_stores_no_raw_macro(temp_db, monkeypatch):
    sheet = default_character_data("Aria")
    sheet["knowledge"]["public_history"] = (
        "Aria grew up next door to {{user}}; <USER> owes her money.")
    sheet["knowledge"]["private_history"] = [
        "{{char}} has loved {{ user }} for years"]
    monkeypatch.setattr(importers, "chat_complete",
                        lambda *a, **k: json.dumps(sheet))
    _cid, stored = importers.import_character(
        {"name": "Aria", "description": "A mage."}, reinterpret=True)
    text = json.dumps(stored)
    for macro in ("{{user}}", "<USER>", "{{char}}", "{{ user }}"):
        assert macro not in text
    assert stored["knowledge"]["public_history"] == (
        "Aria grew up next door to {{PLAYER}}; {{PLAYER}} owes her money.")
    assert stored["knowledge"]["private_history"][0]["content"] == (
        "Aria has loved {{PLAYER}} for years")


def _story(temp_db, *, knows_player):
    persona = default_persona_data("Dana Reyes")
    persona["embodiment"]["visible"]["summary"] = (
        "A wiry woman in a courier's oilskin.")
    pid = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                     ("Dana Reyes", json.dumps(persona), "{}"))
    cid = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("t", pid, "", time.time()))
    card = default_character_data("Aria")
    card["knowledge"]["private_history"] = [
        {"content": "{{PLAYER}} still owes me forty crowns.", "about": "",
         "known_by": []}]
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Aria", json.dumps(card), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,?)",
               (cid, char_id, "active"))
    if knows_player:
        temp_db.wset(cid, "known", {"Aria": ["Dana Reyes"]})
    return {"id": cid, "persona_id": pid}


def _private(chat):
    return [e["content"] for e in scene.private_knowledge_for(chat, "Aria")]


def test_a_mind_that_knows_the_player_reads_their_name(temp_db):
    contents = _private(_story(temp_db, knows_player=True))
    assert "Dana Reyes still owes me forty crowns." in contents


def test_a_mind_that_does_not_reads_no_name_and_no_token(temp_db):
    contents = _private(_story(temp_db, knows_player=False))
    owed = next(c for c in contents if "forty crowns" in c)
    assert "{{PLAYER}}" not in owed
    assert "Dana" not in owed
    assert "player" not in owed.casefold()
