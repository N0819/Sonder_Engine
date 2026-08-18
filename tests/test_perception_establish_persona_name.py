"""Regression test for perception_establish: it used pers.get("name")/
pers.get("appearance") -- flat keys that don't exist on persona_of's
normalized (identity.name / embodiment.visible.summary) return shape -- so
the opening turn of every chat with a real persona configured silently
described the player as "the player" with no real appearance."""

from __future__ import annotations

import json
import time

from agents.perception import perception_establish
from story.character_schema import default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


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

    # There is no model payload to inspect. The same values are computed in
    # the same place and handed to the composer, so the capture moved there.
    def capture(ctx_, sc, perceivers, known, p_name, p_appearance, *a, **kw):
        captured.update(
            {"p_name": p_name, "p_appearance": p_appearance,
             "perceivers": perceivers})
        return {"views": {}, "observations": {}, "composer_ledger": {}}

    monkeypatch.setattr("agents.perception._composer_establish", capture)

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

    assert captured["p_name"] == "Sarah Chen"
    assert "gold uniform" in captured["p_appearance"]

    player_perceiver = next(
        p for p in captured["perceivers"] if p["id"] == "player"
    )
    assert player_perceiver["name"] == "Sarah Chen"
