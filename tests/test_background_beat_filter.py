"""Regression test for the background-presence perception leak
(AUDIT_FINDINGS #2 HIGH sub-item).

agents/background.py's background_react passed the RAW player declaration
(ctx.input) and the full objective resolved_event to an unregistered bystander
with no perception filtering, so concealed/whispered/private content leaked to
a presence that never legitimately sensed it -- and, worse, naming the presence
while concealing made the deterministic gate MORE likely to pick them.

Fix: the presence now receives a filtered beat -- concealed sequence elements
and the private thought are stripped from the player declaration, and audible
station-room dialogue is preferred over the raw objective outcome (with any
concealed quote body redacted from the fallback prose).
"""

from __future__ import annotations

import json
import time

from pipeline_context import ChatData, PipelineContext, TurnData

import agents.background as background
from agents.background import _beat_for_presence, _filtered_player_declaration


SECRET = "The shipment arrives at midnight."


def _ctx(temp_db, interp):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="", created=time.time()),
        cast=[], input="I lean in and whisper: " + SECRET,
    )
    ctx.director_interpret = interp
    return ctx


def test_filtered_declaration_drops_concealed_speech(temp_db):
    ctx = _ctx(temp_db, {
        "sequence": [
            {"type": "speech", "text": SECRET, "visibility": "concealed",
             "conceal_from": ["Doc"]},
            {"type": "speech", "text": "Evening.", "visibility": "overt"},
        ],
    })
    decl = _filtered_player_declaration(ctx)
    assert "midnight" not in decl
    assert "Evening." in decl


def test_filtered_declaration_withholds_raw_input_when_thought_private(temp_db):
    # No structured sequence, but a private thought exists -> the raw input
    # (which contains the whispered secret) must be withheld entirely.
    ctx = _ctx(temp_db, {"sequence": [], "private_thought": "don't let Doc hear"})
    assert _filtered_player_declaration(ctx) == ""


def test_filtered_declaration_passes_public_raw_input(temp_db):
    ctx = _ctx(temp_db, {"sequence": []})
    ctx.input = "I wave at the crowd."
    assert _filtered_player_declaration(ctx) == "I wave at the crowd."


def test_beat_drops_concealed_dialogue_and_redacts_prose():
    dr = {
        "resolved_event": "A hush falls. The shipment arrives at midnight, or so it seems.",
        "dialogue_log": [
            {"speaker": "Player", "exact_quote": SECRET,
             "visibility": "concealed", "conceal_from": ["Doc"], "volume": "whisper"},
            {"speaker": "Guard", "exact_quote": "Move along.", "visibility": "overt"},
        ],
    }
    beat = _beat_for_presence(dr, None, None, "Doc")
    assert "midnight" not in beat
    # An overt, audible line is preferred and surfaced.
    assert "Move along." in beat


def test_beat_concealed_from_this_presence_only():
    dr = {
        "resolved_event": "Quiet words pass.",
        "dialogue_log": [
            {"speaker": "Player", "exact_quote": SECRET,
             "conceal_from": ["Doc"], "visibility": "overt"},
        ],
    }
    # Concealed FROM Doc (even without a global concealed flag) -> excluded.
    assert "midnight" not in _beat_for_presence(dr, None, None, "Doc")


def test_background_react_payload_is_filtered(temp_db, monkeypatch):
    """End-to-end: the payload handed to the presence's LLM call must not
    contain the concealed line, from either channel."""
    ctx = _ctx(temp_db, {
        "sequence": [{"type": "speech", "text": SECRET, "visibility": "concealed",
                      "conceal_from": ["Doc"]}],
    })
    ctx.director_resolve = {
        "resolved_event": "A tense pause.",
        "dialogue_log": [{"speaker": "Player", "exact_quote": SECRET,
                          "visibility": "concealed", "conceal_from": ["Doc"]}],
    }
    temp_db.wset(ctx.chat.id, "scene", {"rooms": {}, "positions": {}})
    temp_db.wset(ctx.chat.id, "background_presences", {"Doc": {"sketch": {}}})

    monkeypatch.setattr(background, "pick_background_reactors", lambda *a, **k: ["Doc"])

    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"reacts": False}

    monkeypatch.setattr(background, "_agent_json", fake_agent_json)

    background.background_react(ctx, nonce=0)

    blob = json.dumps(captured["payload"], ensure_ascii=False)
    assert "midnight" not in blob, "concealed line leaked into background payload"
