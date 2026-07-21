"""Regression test for audit finding #30 (scene.py note): persona private
knowledge was labeled with pers.get("name"), which is always None for a
normalized persona -- the name lives under identity.name. It must use the
persona-name accessor so the "about" label is the actual player name.
"""

from __future__ import annotations

import json
import time

import pytest

import scene
from character_schema import default_persona_data


def test_persona_private_knowledge_is_labeled_with_the_persona_name(temp_db):
    sheet = default_persona_data("Robin")
    sheet["knowledge"]["private_history"] = [
        {"content": "Robin once smuggled contraband.",
         "about": "self", "known_by": ["Alice"]},
    ]
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Robin", json.dumps(sheet), "{}"),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,persona_id,created) VALUES(?,?,?,?)",
        ("Test", "", persona_id, time.time()),
    )

    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True))
    out = scene.private_knowledge_for(chat, "Alice")

    persona_items = [o for o in out if "privately know about them" in o["source"]]
    assert persona_items, "persona private knowledge was not surfaced"
    for item in persona_items:
        assert item["about"] == "Robin"
        assert item["about"] is not None
