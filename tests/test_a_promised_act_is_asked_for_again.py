"""A figure who promised to do something is asked for it again on the
default path too.

`still_owes` writes the figure's aged `pending_act` ("re-asked until
`hands_over` lands", Design.md:280), and the scene manager's gate re-asks it
(`agents/background._demanded_presences`' `owes_act`). The default gate --
`pick_voice_demand`, the only one that runs under `scene_life: off` -- had no
such trigger: its `owed` is a reply debt only. So the tapster who said "In
good time" was never picked again unless re-addressed, and the ale was never
poured (review 2026-11-01, persist_background_memory F13). The trigger is
the manager path's, with its channel rule: an unaimed demand is judged on the
same-room bar, and it ranks below every address.
"""

from __future__ import annotations

import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import pick_voice_demand

KEEPER = "Tapster Ben"


def _ctx(temp_db, keeper_room="taproom", expires=9):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    temp_db.wset(chat_id, "scene", {
        "location": "inn",
        "rooms": {"taproom": {"name": "Taproom"}, "yard": {"name": "Yard"}},
        "positions": {"The Stranger": "taproom", KEEPER: keeper_room},
        "entities": {}, "attire": {}})
    temp_db.wset(chat_id, "background_presences", {KEEPER: {
        "first_turn": 1, "last_turn": 6,
        "pending_act": {"what": "a small ale", "to": "the stranger",
                        "turn": 6, "expires_turn": expires}}})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 7, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=7, player_input="",
                      created=time.time()),
        cast=[], input="",
        director_resolve={"resolved_event": "The taproom hums.",
                          "dialogue_log": []})


def test_an_unkept_promise_is_a_demand(temp_db):
    ctx = _ctx(temp_db)
    out = pick_voice_demand(ctx, ctx.director_resolve, cap=1)
    assert out["picks"] == [KEEPER], out
    assert "owes_act" in out["meta"][KEEPER]["why"]


def test_a_lapsed_promise_is_not(temp_db):
    ctx = _ctx(temp_db, expires=6)
    assert pick_voice_demand(ctx, ctx.director_resolve, cap=1)["picks"] == []


def test_a_promise_does_not_cross_a_closed_distance(temp_db):
    """The manager path's channel: an unaimed demand needs the same room."""
    ctx = _ctx(temp_db, keeper_room="yard")
    assert pick_voice_demand(ctx, ctx.director_resolve, cap=1)["picks"] == []
