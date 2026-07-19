"""Regression test for GET /api/chats/{cid}/personas: lists only actively
attached extra players, backing the "invite a friend" panel's persona
picker (there was previously only a POST to attach one, no way to list
who's already attached)."""

from __future__ import annotations

import time

import app


def test_lists_only_active_extra_personas(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    active_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Active Guest", "{}", "{}"),
    )
    dormant_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Dormant Guest", "{}", "{}"),
    )
    temp_db.qi(
        "INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')",
        (chat_id, active_id),
    )
    temp_db.qi(
        "INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'dormant')",
        (chat_id, dormant_id),
    )

    result = app.chat_list_extra_personas(chat_id)

    names = [p["name"] for p in result["personas"]]
    assert names == ["Active Guest"]
