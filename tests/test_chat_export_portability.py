"""Regression test: chat_export must embed a portable `resources` bundle
(persona + character sheets keyed by old_id) so an exported story imports
into a DIFFERENT install.

Before the fix, chat_export referenced characters only by local char_id.
chat_import builds old_char_map SOLELY from resources.characters, and drops
every memory/summary whose char_id isn't in that map (app.py ~2360). So a
cross-install import raised "references character N but does not embed it",
and even when participants happened to resolve by raw id, all memories were
lost. The surviving-memory assertion below is the distinguishing check: a
memory can only come through import if resources were embedded.
"""

from __future__ import annotations

import json
import time

import app
import memory
from character_schema import default_character_data


def test_export_embeds_resources_and_memories_survive_import(temp_db):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Ruiz", json.dumps({"identity": {"name": "Ruiz", "uid": "persona_ruiz"}}),
         "{}", "persona_ruiz"),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Story", persona_id, "", time.time()),
    )
    alice = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Alice", json.dumps(default_character_data("Alice")), "{}", time.time(), "char_alice"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, alice, "active", "{}"),
    )
    memory.add_memory(chat_id, alice, None, "episode", "witnessed", 0.5,
                       "A secret only Alice knows.", turn_idx=0)

    exported = app.chat_export(chat_id)

    # the fix: portable resources embedded automatically
    assert exported["resources"]["persona"]["resource_uid"] == "persona_ruiz"
    chars = exported["resources"]["characters"]
    assert any(
        c["old_id"] == alice
        and c["resource_uid"] == "char_alice"
        and c["sheet"]["identity"]["name"] == "Alice"
        for c in chars
    ), chars

    # cross-install round-trip WITHOUT hand-injecting resources
    imported = app.chat_import({"data": exported})
    ncid = imported["id"]

    cast = temp_db.q(
        "SELECT c.name FROM chat_chars cc JOIN characters c ON c.id=cc.char_id WHERE cc.chat_id=?",
        (ncid,),
    )
    assert [r["name"] for r in cast] == ["Alice"]

    # memories survive ONLY because resources were embedded (distinguishing check)
    mem = temp_db.q("SELECT content FROM memories WHERE chat_id=?", (ncid,), one=True)
    assert mem is not None and mem["content"] == "A secret only Alice knows."


def test_export_without_persona_embeds_null_persona(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("No persona", "", time.time()),
    )
    exported = app.chat_export(chat_id)
    assert exported["resources"]["persona"] is None
    assert exported["resources"]["characters"] == []
    # still importable
    imported = app.chat_import({"data": exported})
    assert imported["id"] != chat_id
