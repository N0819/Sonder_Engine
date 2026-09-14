"""A sound the player's declaration makes is graded in the ACT pass.

A world-author declaration that throws a sluice puts a `sensory_events` row
in the beat's onset assertions; the act pass graded none of them, so the
cast declared into a silent world and the bargee begged for the sluice she
had just thrown (scratch play 2026-09-14, chat 5 turn 3).
"""
import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data
from story.character_schema import default_persona_data

PLAYER = "Nan Corrie"
CAST = "Silas Penhale"


def _ctx(temp_db, *, level="loud"):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}", "persona_nan"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Lock", "", time.time(), persona_id))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (CAST, json.dumps(default_character_data(CAST)), "{}", time.time(),
         "char_silas"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "the lock", "time": "night",
        "rooms": {"lock_side": {"name": "Lock-side", "adjacent": []}},
        "positions": {PLAYER: "lock_side", CAST: "lock_side"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {CAST: [PLAYER], PLAYER: [CAST]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Lock", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "lock_side"
    ctx.director_interpret = {
        "action": {"attempt": "winds the paddle up", "visibility": "overt",
                   "conceal_from": [], "targets": [], "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "winds the paddle up",
            "observable": "winds the ground paddle up a foot",
            "visibility": "overt", "conceal_from": [], "targets": [],
            "commitment": "asserted", "verb": "wind", "stage": "immediate",
            "event_id": "turn:1:player:0:action",
        }],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [cast[0]["id"]]},
        "state_assertions": {"sensory_events": [{
            "kind": "sound", "room": "lock_side", "level": level,
            "source": "by-wash",
            "detail": "water rushing through the by-wash with a roar"}]},
    }
    return ctx, cast[0]["id"]


def test_the_players_own_sound_is_in_the_casts_act_view(temp_db):
    import agents.perception as perception
    ctx, reactor_id = _ctx(temp_db)
    out = perception.perception_act(ctx, nonce="n")
    view = out["views"][str(reactor_id)] or ""
    assert "roar" in view, view


def test_no_asserted_sound_adds_nothing(temp_db):
    import agents.perception as perception
    ctx, reactor_id = _ctx(temp_db)
    ctx.director_interpret["state_assertions"] = {}
    out = perception.perception_act(ctx, nonce="n")
    assert "roar" not in (out["views"][str(reactor_id)] or "")


def test_an_act_made_before_she_left_the_room_is_seen_by_the_one_left_behind(temp_db):
    """Chat 5 turn 8: Nan took the lamp off the kitchen table and went out;
    the bargee at that table was refused all four acts "cannot see", because
    sight was graded with her already outside. The lamp is on the table
    where the beat found her, so that act is graded in the kitchen."""
    import agents.perception as perception
    ctx, reactor_id = _ctx(temp_db)
    ctx.director_interpret["state_assertions"] = {"positions": {PLAYER: "yard"}}
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["rooms"] = {
        "lock_side": {"name": "Kitchen", "light": "lit",
                      "adjacent": [{"to": "yard", "barrier": "closed_door"}]},
        "yard": {"name": "Yard", "light": "dark",
                 "adjacent": [{"to": "lock_side", "barrier": "closed_door"}]}}
    sc["entities"] = {"kitchen_lamp": {"name": "the lamp", "kind": "thing"}}
    sc["positions"]["kitchen_lamp"] = "lock_side"
    temp_db.wset(ctx.chat.id, "scene", sc)
    ctx.director_interpret["sequence"] = [
        {"type": "action", "attempt": "takes the lamp off the table",
         "observable": "takes the lamp off the table",
         "visibility": "overt", "conceal_from": [], "targets": ["kitchen_lamp"],
         "commitment": "asserted", "stage": "immediate",
         "event_id": "turn:1:player:0:action"},
        {"type": "action", "attempt": "goes out into the yard",
         "observable": "goes out into the yard and shuts the door",
         "visibility": "overt", "conceal_from": [], "targets": [],
         "commitment": "asserted", "stage": "immediate",
         "event_id": "turn:1:player:1:action",
         "movement": {"to_room": "yard", "mover": PLAYER, "arrives": True}}]
    ctx.director_interpret["movement"] = {"to_room": "yard", "mover": PLAYER,
                                          "arrives": True}
    from core.pipeline_context import current_decision_sink
    decisions = []
    token = current_decision_sink.set(
        lambda kind, subject, verdict, reason: decisions.append(
            (kind, subject, verdict, reason)))
    try:
        out = perception.perception_act(ctx, nonce="n")
    finally:
        current_decision_sink.reset(token)
    view = out["views"][str(reactor_id)] or ""
    assert "lamp" in view, (view, decisions)
