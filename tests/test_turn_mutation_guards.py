"""Regression tests for consistent idle-chat guarding and clean 404s across
turn/step mutation routes. turn_new previously had no _require_chat_idle
check at all -- the most-hit route of all, submit-a-new-turn -- and several
step routes crashed with a raw TypeError/500 on a bad id instead of a 404."""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

import app
from agents.runtime import ABORTS


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def test_turn_new_rejects_when_chat_has_active_pipeline(temp_db):
    chat_id = _make_chat(temp_db)
    ABORTS[(chat_id, None)] = object()
    try:
        with pytest.raises(HTTPException) as exc_info:
            app.turn_new(chat_id, {"input": "hello"})
        assert exc_info.value.status_code == 409
    finally:
        ABORTS.pop((chat_id, None), None)


def test_turn_reroll_404s_for_missing_turn(temp_db):
    with pytest.raises(HTTPException) as exc_info:
        app.turn_reroll(999999)
    assert exc_info.value.status_code == 404


def test_step_edit_404s_for_missing_step(temp_db):
    with pytest.raises(HTTPException) as exc_info:
        app.step_edit(999999, {"content": {}})
    assert exc_info.value.status_code == 404


def test_step_activate_404s_for_missing_step(temp_db):
    with pytest.raises(HTTPException) as exc_info:
        app.step_activate(999999, {"variant_id": 1})
    assert exc_info.value.status_code == 404


def test_edit_input_404s_for_missing_turn(temp_db):
    with pytest.raises(HTTPException) as exc_info:
        app.edit_input(999999, {"input": "x"})
    assert exc_info.value.status_code == 404
