"""A bound body does not walk off in the interpret's onset preview either.

The restraint floor (`director._block_restrained_moves`: a body bound, or
held by a holder who is here and awake, cannot relocate itself) is state
only and stage-independent, and it ran only at resolve. The interpret's
positions were previewed unchecked -- into the world the cast's onset views
and the resolve's author read (`onset_state_assertions` ->
`preview_player_state_assertions`) -- and the resolve then popped the
committed position: the cast reacted to a bound player walking out of the
room the commit keeps her in (review 2026-11-01, director core F11).
"""

from __future__ import annotations

import json

import agents.director as director

from tests.director_fakes import _make_ctx, _speech_interp, encoder_event


def _bind(db, chat_id, subject):
    db.qi("INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
          "started_at,expires_at,next_tick,payload,active) "
          "VALUES(?,?,?,?,?,?,?,?,?)",
          ("rope1", chat_id, subject, "restraint", 0.0, None, None,
           json.dumps({"condition_id": "rope1", "subject_id": subject,
                       "kind": "restraint", "active": 1,
                       "state": {"level": "bound", "means": "rope"}}), 1))


def _walk(said):
    def fake(role, step_key, system, payload, **kw):
        if step_key == "director_prose":
            return {"prose": "The Stranger walks up into the lamp room."}
        if step_key == "director_specialist":
            return {"events": [encoder_event(
                "The Stranger walks up into the lamp room.",
                movement={"mover": "self", "to_room": "lamp_room"},
                transforms=[{"item": "The Stranger", "patch": {
                    "positions": {"The Stranger": "lamp_room"}}}])]}
        return {}
    return fake


def test_a_bound_players_walk_is_not_previewed(temp_db, monkeypatch, prose_director):
    said = "I walk up into the lamp room."
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input=said)
    ctx.director_interpret = None
    _bind(temp_db, ctx.chat.id, "The Stranger")
    monkeypatch.setattr(director, "_agent_json", _walk(said))

    out = director.director_interpret(ctx, nonce=0)

    for key in ("state_assertions", "onset_state_assertions"):
        assert "The Stranger" not in ((out.get(key) or {}).get("positions") or {}), key
    assert [w for w in ctx.warnings if "Blocked a move by The Stranger" in w], ctx.warnings


def test_an_unbound_players_walk_is_previewed(temp_db, monkeypatch, prose_director):
    said = "I walk up into the lamp room."
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input=said)
    ctx.director_interpret = None
    monkeypatch.setattr(director, "_agent_json", _walk(said))

    out = director.director_interpret(ctx, nonce=0)

    assert (out.get("onset_state_assertions") or {}).get("positions", {}).get(
        "The Stranger") == "lamp_room"
