"""Regression test for perception_establish: it used pers.get("name")/
pers.get("appearance") -- flat keys that don't exist on persona_of's
normalized (identity.name / embodiment.visible.summary) return shape -- so
the opening turn of every chat with a real persona configured silently
described the player as "the player" with no real appearance."""

from __future__ import annotations

import json
import time

from agents.perception import perception_establish
from character_schema import default_persona_data
from pipeline_context import ChatData, PipelineContext, TurnData


def test_opening_turn_uses_real_persona_name_and_appearance(
    temp_db, monkeypatch,
):
    sheet = default_persona_data("Sarah Chen")
    sheet["embodiment"]["visible"]["summary"] = "A tall woman in a gold uniform."
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Sarah Chen", json.dumps(sheet), "{}"),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Test", "", time.time(), persona_id),
    )

    captured = {}

    def fake_agent_json(role, step_key, prompt, payload, **kwargs):
        captured["payload"] = payload
        return {"views": {}}

    monkeypatch.setattr(
        "agents.perception._agent_json", fake_agent_json,
    )

    ctx = PipelineContext(
        chat=ChatData(
            id=chat_id, name="Test", persona_id=persona_id,
            lorebook_id=None, scenario="", created=time.time(),
        ),
        turn=TurnData(
            id=1, chat_id=chat_id, idx=0, player_input="",
            created=time.time(),
        ),
        cast=[],
        input="",
        director_establish={},
    )

    perception_establish(ctx, nonce=0)

    payload = captured["payload"]
    assert payload["declared_act"]["actor_name"] == "Sarah Chen"
    assert "gold uniform" in payload["declared_act"]["actor_present_appearance"]

    player_perceiver = next(
        p for p in payload["perceivers"] if p["id"] == "player"
    )
    assert player_perceiver["name"] == "Sarah Chen"
