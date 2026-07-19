"""Regression test for interaction_loop's reactor queue ordering.

Bug: interaction_loop built its reactor queue directly from flow.reactors'
own list order, which in practice just reflects cast-registration order, not
who the player actually addressed. A player line explicitly addressed to a
newly-promoted character still let an earlier-ordered character go first,
which mattered because whichever character goes first can trigger
_requires_director_resolution and break the loop before the addressed
character's turn is ever reached -- direct address gave them zero priority.

Fix: flow.addressed_to (populated by director_interpret) is used to
stable-sort the initial reactor queue so addressed characters go first,
without changing who is eligible to react or the break semantics.
"""

from __future__ import annotations

import json
import time

from agents.loops import interaction_loop
from character_schema import default_character_data
from db import wset
from pipeline_context import ChatData, PipelineContext, TurnData


def _cast_row(char_id, name):
    return {
        "id": char_id,
        "sheet": json.dumps(default_character_data(name)),
    }


def _make_ctx(chat_id, reactors, addressed_to):
    cast = [_cast_row(rid, f"Character {rid}") for rid in reactors]

    # Co-locate every reactor in the same room so deterministic_micro_perception
    # treats each speech beat as fully heard by the others -- otherwise
    # interaction_loop's own "no eligible respondent" check (unrelated to the
    # bug under test) would stop the loop after the first speaker regardless
    # of who else is still queued.
    wset(chat_id, "scene", {
        "location": "test",
        "time": "now",
        "description": "",
        "rooms": {"room_a": {"name": "Room A", "adjacent": []}},
        "entities": {},
        "positions": {f"Character {rid}": "room_a" for rid in reactors},
        "overlays": {},
        "attire": {},
    })

    return PipelineContext(
        chat=ChatData(
            id=chat_id, name="Test", persona_id=None, lorebook_id=None,
            scenario="", created=time.time(),
        ),
        turn=TurnData(
            id=1, chat_id=chat_id, idx=1, player_input="test",
            created=time.time(),
        ),
        cast=cast,
        input="test",
        director_interpret={
            "flow": {
                "reactors": reactors,
                "addressed_to": addressed_to,
            },
        },
        perception_act={
            "views": {str(rid): f"view for {rid}" for rid in reactors},
        },
    )


def _fake_character_step(calls_made):
    def fake(ctx, char_id, nonce):
        calls_made.append(char_id)
        return {"sequence": [{"type": "speech", "text": "Hi there."}]}
    return fake


def test_addressed_character_is_queued_before_earlier_ordered_reactor(
    temp_db, monkeypatch,
):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    # flow.reactors lists 12 before 14 (cast-registration order), but the
    # player's line was addressed to 14.
    ctx = _make_ctx(chat_id, reactors=[12, 14], addressed_to=[14])

    calls_made = []
    monkeypatch.setattr(
        "agents.loops.character_step", _fake_character_step(calls_made),
    )

    result = interaction_loop(ctx, nonce=0)

    assert calls_made[0] == 14, (
        f"expected addressed character 14 to go first, got {calls_made}"
    )
    assert calls_made[:2] == [14, 12]
    assert [r["speaker_id"] for r in result["rounds"]][:2] == [14, 12]


def test_no_addressed_to_keeps_original_reactor_order(temp_db, monkeypatch):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    ctx = _make_ctx(chat_id, reactors=[12, 14], addressed_to=[])

    calls_made = []
    monkeypatch.setattr(
        "agents.loops.character_step", _fake_character_step(calls_made),
    )

    interaction_loop(ctx, nonce=0)

    assert calls_made[:2] == [12, 14]
