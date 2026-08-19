"""Regression tests for PUT /api/turns/{tid}/prose: letting a player
hand-edit a turn's displayed narration without disturbing anything the
pipeline already committed from it."""

from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException

from web import app
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


def test_a_failed_insert_leaves_the_step_with_its_active_variant(temp_db,
                                                                 monkeypatch):
    """Deactivate-then-insert is one operation, not two.

    "Exactly one active variant per materialized step" is a named invariant,
    and a crash between these two statements leaves the narrator step with
    ZERO -- a turn that renders as blank prose forever, with no error anywhere
    to say why. Both siblings that write this same pair (`step_edit`,
    `turn_narration_select`) already wrap it.
    """
    chat_id = _make_chat(temp_db)
    turn_id = _make_turn(temp_db, chat_id)
    save_step(turn_id, "narrator", "Narrator \u00b7 render", 6,
              {"prose": "The original line."})

    real_qi = app.qi

    def failing_qi(sql, args=()):
        if sql.lstrip().startswith("INSERT INTO variants"):
            raise RuntimeError("the process died here")
        return real_qi(sql, args)

    monkeypatch.setattr(app, "qi", failing_qi)
    with pytest.raises(RuntimeError):
        app.edit_prose(turn_id, {"prose": "Never written."})
    monkeypatch.undo()

    active = temp_db.q(
        "SELECT v.content FROM steps s JOIN variants v "
        "ON v.step_id=s.id AND v.active=1 "
        "WHERE s.turn_id=? AND s.key='narrator'", (turn_id,))
    assert len(active) == 1
    assert json.loads(active[0]["content"])["prose"] == "The original line."


def test_a_prose_edit_is_refused_while_that_chat_has_a_live_pipeline(temp_db):
    """WEB-18. This route WRITES a variant, so an edit issued during a reroll
    of the same turn races the pipeline's own write to that step: whichever
    `UPDATE variants SET active=0` lands second wins, and either the edit
    vanishes or it silences the beat the pipeline just produced.

    Not marking anything stale is what makes the route safe to run on an OLD
    turn; it was never an argument for running it against a LIVE one, and its
    sibling `edit_input` has taken the same guard all along.
    """
    chat_id = _make_chat(temp_db)
    turn_id = _make_turn(temp_db, chat_id)
    save_step(turn_id, "narrator", "Narrator · render", 6, {"prose": "As written."})

    app.ABORTS[(chat_id, None)] = object()
    try:
        with pytest.raises(HTTPException) as caught:
            app.edit_prose(turn_id, {"prose": "As edited."})
        assert caught.value.status_code == 409
    finally:
        app.ABORTS.pop((chat_id, None), None)

    assert app.active_content(turn_id, "narrator")["prose"] == "As written."

    # ...and the moment the pipeline is done, the same edit lands.
    assert app.edit_prose(turn_id, {"prose": "As edited."})["prose"] == "As edited."
