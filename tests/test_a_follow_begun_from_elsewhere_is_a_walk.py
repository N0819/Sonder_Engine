"""A follow begun from another room is an approach, and an approach moves.

Following carries a follower only from beside the target, which is right for
travel together. A start op across rooms declares that a body has decided
to go to somebody elsewhere, and left as a relation alone it moved nobody:
"Captain Hale's approach continues toward Clara" was filed as a following
op and ticked fifteen beats running while he sat two rooms away (scratch
play 2026-09-14, chat 9). A pressure about where a body is going advances by
the body moving, and a tick without movement is now reported.
"""
import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist import commit
from story.character_schema import default_character_data
from tests.helpers import fanout_resolve_agent
from tests.test_director_movement import (_following_scene, _make_ctx,
                                          _quiet_character_result)


def test_a_start_op_across_rooms_puts_the_follower_with_the_target(
        temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, "trail_b")
    scene = _following_scene(player_room="trail_b", mara_room="trail_a")
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"] = None
    mara_id = ctx.cast[0]["id"]
    ctx.character_results[mara_id] = _quiet_character_result(
        {"op": "start", "target": "The Stranger", "reason": "go to him"})
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent({
        "state_diff": {"positions": {}},
    }))

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"]["positions"]["Mara"] == "trail_b"
    assert any("Approach: Mara started following The Stranger" in w
               for w in ctx.warnings)


def test_no_open_route_leaves_the_follower_and_the_relation(
        temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, "trail_b")
    scene = _following_scene(player_room="trail_b", mara_room="trail_a")
    for room in scene["rooms"].values():
        for edge in room["adjacent"]:
            edge["barrier"] = "locked_door"
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"] = None
    mara_id = ctx.cast[0]["id"]
    ctx.character_results[mara_id] = _quiet_character_result(
        {"op": "start", "target": "The Stranger", "reason": "go to him"})
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent({
        "state_diff": {"positions": {}},
    }))

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"].get("positions", {}).get("Mara") in (None, "trail_a")
    assert any("no open route" in w for w in ctx.warnings)


def _pressure_ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    temp_db.wset(chat_id, "scene", {
        "rooms": {"card_room": {"name": "card room", "adjacent": []},
                  "supper_room": {"name": "supper room", "adjacent": []}},
        "positions": {"Captain Edmund Hale": "card_room",
                      "Clara Penrose": "supper_room"},
        "entities": {}})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 5, "wait", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=5,
                      player_input="wait", created=time.time()),
        cast=[], input="wait")
    temp_db.wset(chat_id, "world_pressures", [{
        "id": "wp:0:1", "subject": "Captain Hale's approach",
        "note": "Captain Hale's approach continues toward Clara.",
        "level": 2, "opened_turn": 0, "last_tick_turn": 4, "held_streak": 0}])
    return ctx


def test_a_tick_on_a_bodys_approach_without_movement_is_reported(temp_db):
    ctx = _pressure_ctx(temp_db)
    ctx.director_resolve = {
        "world_pressure": [{"op": "tick", "id": "wp:0:1",
                            "subject": "Captain Hale's approach"}],
        "state_diff": {"positions": {}}}
    commit.commit_world_pressure(ctx, nonce=0)
    assert any("ticked without movement" in w and "Captain Edmund Hale" in w
               for w in ctx.warnings)
    # Report-only: the tick still lands.
    assert temp_db.wget(ctx.chat.id, "world_pressures", [])[0]["level"] == 3


def test_a_tick_with_the_body_moving_is_not_reported(temp_db):
    ctx = _pressure_ctx(temp_db)
    ctx.director_resolve = {
        "world_pressure": [{"op": "tick", "id": "wp:0:1",
                            "subject": "Captain Hale's approach"}],
        "state_diff": {"positions": {"Captain Edmund Hale": "supper_room"}}}
    commit.commit_world_pressure(ctx, nonce=0)
    assert not any("ticked without movement" in w for w in ctx.warnings)


def test_the_causal_sheet_says_where_a_walk_ends():
    from llm.prompts import get_prompt_body
    sheet = get_prompt_body("director_interpret", "en")
    assert "never the row's own source" in sheet
    assert "where the walk was declared to END" in sheet
    assert "carries a body out of its room is a positions row" in sheet
