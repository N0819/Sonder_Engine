"""Durable following is travel intent, not a physical tether."""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData
from spatial import apply_following_ops, merge_scene_with_diff


def _scene():
    return {
        "rooms": {"road": {"name": "Road", "adjacent": []}},
        "positions": {"A": "road", "B": "road", "C": "road"},
        "entities": {}, "stations": {},
    }


def test_following_start_and_stop_round_trip_through_scene_merge():
    scene = _scene()
    started = merge_scene_with_diff(scene, {"following_ops": [
        {"op": "start", "follower": "A", "target": "B", "turn": 4,
         "reason": "travelling together"},
    ]})
    assert started["following"]["A"] == {
        "target": "B", "since_turn": 4, "reason": "travelling together",
    }

    stopped = merge_scene_with_diff(started, {"following_ops": [
        {"op": "stop", "follower": "A", "reason": "staying here"},
    ]})
    assert stopped["following"] == {}


def test_following_rejects_self_and_cycles():
    scene = _scene()
    apply_following_ops(scene, [
        {"op": "start", "follower": "A", "target": "A"},
        {"op": "start", "follower": "A", "target": "B"},
        {"op": "start", "follower": "B", "target": "A"},
    ])
    assert scene["following"] == {
        "A": {"target": "B", "since_turn": None, "reason": ""},
    }


def test_separation_does_not_erase_intent_to_follow():
    scene = _scene()
    scene["following"] = {
        "A": {"target": "B", "since_turn": 2, "reason": "catch up"},
    }
    scene["rooms"]["elsewhere"] = {"name": "Elsewhere", "adjacent": []}
    separated = merge_scene_with_diff(
        scene, {"positions": {"B": "elsewhere"}})
    assert separated["following"]["A"]["target"] == "B"


def test_departed_target_prunes_following_relation():
    scene = _scene()
    scene["following"] = {
        "A": {"target": "B", "since_turn": 2, "reason": "catch up"},
    }
    gone = merge_scene_with_diff(scene, {"remove_entities": ["B"]})
    # remove_entities only removes a position when B is an entity key; model
    # the ordinary post-departure scene directly for ledger hygiene.
    gone["positions"].pop("B", None)
    apply_following_ops(gone, [])
    assert gone["following"] == {}


def test_following_fields_survive_schema_validation():
    from schemas import validate_llm_output_strict

    interpreted = validate_llm_output_strict("director_interpret", {
        "follow_op": {"op": "start", "target": "B", "reason": "go together"},
    })
    character = validate_llm_output_strict("character", {
        "follow_op": {"op": "stop", "reason": "stay behind"},
    })
    assert interpreted.output["follow_op"]["target"] == "B"
    assert character.output["follow_op"]["op"] == "stop"


def test_character_knows_its_own_following_state(temp_db, monkeypatch):
    import agents.character as character_module

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Following", "", time.time()),
    )
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara_follow"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    scene = _scene()
    scene["positions"] = {"Mara": "road", "The Stranger": "road"}
    scene["following"] = {
        "Mara": {"target": "The Stranger", "since_turn": 3,
                 "reason": "travelling together"},
    }
    temp_db.wset(chat_id, "scene", scene)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 4, "Continue.", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Following", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=4,
                      player_input="Continue.", created=time.time()),
        cast=cast, input="Continue.",
    )
    ctx.director_interpret = {
        "flow": {"reactors": [char_id], "tom_triggers": []},
    }
    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    character_module.character_step(ctx, char_id, nonce=0)

    assert captured["payload"]["self"]["following"] == {
        "target": "The Stranger", "since_turn": 3,
        "reason": "travelling together", "target_room": "road",
        "same_room": True,
    }


def test_prompts_define_following_as_voluntary_and_speed_bounded():
    from prompts import DEFAULT_PROMPTS

    assert "player.following" in DEFAULT_PROMPTS["director_interpret"]
    character_prompt = DEFAULT_PROMPTS["character"]
    assert "self.following" in character_prompt
    assert "grants no speed" in character_prompt
