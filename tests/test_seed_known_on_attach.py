"""Regression test for seeding mutual recognition when attaching a
character with already_known=True: without this, an opening-scene
companion the player is meant to already know renders as "the unfamiliar
person" until an in-story introduction beat happens to fire, since the
'known' map otherwise only grows from validated_introductions during
commit."""

from __future__ import annotations

import json
import time

import app
from character_schema import default_character_data, default_persona_data


def _make_chat_with_persona(db, persona_name):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (persona_name, json.dumps(default_persona_data(persona_name)), "{}"),
    )
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Test", "", time.time(), persona_id),
    )
    return chat_id


def _make_character(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


def test_already_known_seeds_mutual_recognition(temp_db):
    chat_id = _make_chat_with_persona(temp_db, "Sarah Chen")
    char_id = _make_character(temp_db, "Dr. Crusher")

    app.chat_add_char(chat_id, {"char_id": char_id, "already_known": True})

    known = temp_db.wget(chat_id, "known", {})
    assert "Sarah Chen" in known.get("Dr. Crusher", [])
    assert "Dr. Crusher" in known.get("Sarah Chen", [])


def test_without_already_known_no_recognition_is_seeded(temp_db):
    chat_id = _make_chat_with_persona(temp_db, "Sarah Chen")
    char_id = _make_character(temp_db, "Vrenak")

    app.chat_add_char(chat_id, {"char_id": char_id})

    known = temp_db.wget(chat_id, "known", {})
    assert "Sarah Chen" not in known.get("Vrenak", [])


def test_already_known_does_not_duplicate_on_reattach(temp_db):
    chat_id = _make_chat_with_persona(temp_db, "Sarah Chen")
    char_id = _make_character(temp_db, "Dr. Crusher")

    app.chat_add_char(chat_id, {"char_id": char_id, "already_known": True})
    app.chat_add_char(chat_id, {"char_id": char_id, "already_known": True})

    known = temp_db.wget(chat_id, "known", {})
    assert known["Dr. Crusher"].count("Sarah Chen") == 1
    assert known["Sarah Chen"].count("Dr. Crusher") == 1
