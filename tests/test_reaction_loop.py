"""Regression test for reaction_loop: max_reaction_rounds used to break the
loop after only 2 reactors had reacted regardless of max_reactors, silently
dropping the tail of an eligible reactor list even though the function's own
docstring promises "each eligible reactor" gets to react."""

from __future__ import annotations

import json
import time

from agents.loops import reaction_loop
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _cast_row(char_id, name):
    return {
        "id": char_id,
        "sheet": json.dumps(default_character_data(name)),
    }


def _make_ctx(chat_id, reactor_ids):
    cast = [_cast_row(rid, f"Character {rid}") for rid in reactor_ids]
    return PipelineContext(
        chat=ChatData(
            id=chat_id, name="Test", persona_id=None, lorebook_id=None,
            scenario="", created=time.time(),
        ),
        turn=TurnData(
            id=1, chat_id=chat_id, idx=0, player_input="test",
            created=time.time(),
        ),
        cast=cast,
        input="test",
        director_interpret={
            "flow": {
                "resolution_flags": {"possible_reactors": True},
                "reactors": reactor_ids,
            },
        },
        perception_act={
            "views": {str(rid): f"view for {rid}" for rid in reactor_ids},
        },
    )


def test_every_eligible_reactor_up_to_max_reactors_gets_to_react(
    temp_db, monkeypatch,
):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    temp_db.qi(
        "INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
        (chat_id, "reaction_config", json.dumps({
            "enabled": True, "max_reactors": 6,
            "allow_emergency_reactions": True, "use_seeded_checks": True,
        })),
    )

    reactor_ids = [1, 2, 3, 4, 5, 6]
    ctx = _make_ctx(chat_id, reactor_ids)

    calls_made = []

    def fake_character_step(ctx, char_id, nonce):
        calls_made.append(char_id)
        return {"sequence": []}

    monkeypatch.setattr(
        "agents.loops.character_step", fake_character_step,
    )

    result = reaction_loop(ctx, nonce=0)

    # Before the fix, this stopped at 2 reactors (the old
    # max_reaction_rounds default) no matter how many were eligible.
    assert calls_made == reactor_ids
    assert result["calls"] == 6
    assert len(result["rounds"]) == 6


def test_max_reactors_still_truncates_the_reactor_list(temp_db, monkeypatch):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    temp_db.qi(
        "INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
        (chat_id, "reaction_config", json.dumps({
            "enabled": True, "max_reactors": 2,
            "allow_emergency_reactions": True, "use_seeded_checks": True,
        })),
    )

    reactor_ids = [1, 2, 3, 4]
    ctx = _make_ctx(chat_id, reactor_ids)

    calls_made = []

    def fake_character_step(ctx, char_id, nonce):
        calls_made.append(char_id)
        return {"sequence": []}

    monkeypatch.setattr(
        "agents.loops.character_step", fake_character_step,
    )

    result = reaction_loop(ctx, nonce=0)

    assert calls_made == [1, 2]
    assert result["calls"] == 2
