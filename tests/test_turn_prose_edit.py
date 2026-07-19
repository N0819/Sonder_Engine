"""Regression tests for PUT /api/turns/{tid}/prose: letting a player
hand-edit a turn's displayed narration without disturbing anything the
pipeline already committed from it."""

from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException

import app
from agents.storage import save_step


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_turn(db, chat_id, idx=0):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "look around", time.time()),
    )


def test_edit_prose_updates_only_prose_field(temp_db):
    chat_id = _make_chat(temp_db)
    turn_id = _make_turn(temp_db, chat_id)
    save_step(turn_id, "narrator", "Narrator · render", 6, {
        "prose": "The original line.",
        "new_specifics": ["a lantern on the table"],
    })
    save_step(turn_id, "commit", "Mapping & memory · commit-up", 7, {"ok": True})

    result = app.edit_prose(turn_id, {"prose": "The corrected line."})

    assert result == {"ok": True, "prose": "The corrected line."}

    row = temp_db.q(
        "SELECT v.content FROM steps s JOIN variants v "
        "ON v.step_id=s.id AND v.active=1 "
        "WHERE s.turn_id=? AND s.key='narrator'",
        (turn_id,), one=True,
    )
    content = json.loads(row["content"])
    assert content["prose"] == "The corrected line."
    # Everything else in the narrator step's content survives untouched.
    assert content["new_specifics"] == ["a lantern on the table"]


def test_edit_prose_does_not_mark_downstream_steps_stale(temp_db):
    # commit already applied its memory/world-state side effects and isn't
    # idempotent -- a cosmetic prose fix must never make it reroll/rerun
    # -eligible the way editing an earlier mechanical step would.
    chat_id = _make_chat(temp_db)
    turn_id = _make_turn(temp_db, chat_id)
    save_step(turn_id, "narrator", "Narrator · render", 6, {"prose": "Before."})
    save_step(turn_id, "commit", "Mapping & memory · commit-up", 7, {"ok": True})

    app.edit_prose(turn_id, {"prose": "After."})

    commit_step = temp_db.q(
        "SELECT stale FROM steps WHERE turn_id=? AND key='commit'",
        (turn_id,), one=True,
    )
    assert commit_step["stale"] == 0


def test_edit_prose_creates_new_variant_not_overwrite(temp_db):
    chat_id = _make_chat(temp_db)
    turn_id = _make_turn(temp_db, chat_id)
    save_step(turn_id, "narrator", "Narrator · render", 6, {"prose": "First."})

    app.edit_prose(turn_id, {"prose": "Second."})

    step = temp_db.q(
        "SELECT id FROM steps WHERE turn_id=? AND key='narrator'",
        (turn_id,), one=True,
    )
    variants = temp_db.q(
        "SELECT content, active FROM variants WHERE step_id=? ORDER BY id",
        (step["id"],),
    )
    assert len(variants) == 2
    assert variants[0]["active"] == 0
    assert variants[1]["active"] == 1
    assert json.loads(variants[1]["content"])["prose"] == "Second."


def test_edit_prose_404s_for_missing_turn(temp_db):
    with pytest.raises(HTTPException) as exc_info:
        app.edit_prose(999999, {"prose": "x"})
    assert exc_info.value.status_code == 404


def test_edit_prose_404s_when_turn_has_no_narrator_step(temp_db):
    chat_id = _make_chat(temp_db)
    turn_id = _make_turn(temp_db, chat_id)
    save_step(turn_id, "director_interpret", "Director · interpret", 0, {})

    with pytest.raises(HTTPException) as exc_info:
        app.edit_prose(turn_id, {"prose": "x"})
    assert exc_info.value.status_code == 404
