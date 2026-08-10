"""Player-declared standing contact reaches the other party in perception 1.

Chat 68 turn 15 supplied the failure: the player explicitly felt a standing
cock-to-cervix relation, interpret retained only the visible squirm, and pass 1
reused the older coarse cock-to-groin record. The other participant therefore
decided before receiving the contact declaration their own body should feel.
"""

from __future__ import annotations

import json
import time

from agents.director import (
    _merge_player_contact_assertions,
    _validated_player_contact_assertions,
)
from character_schema import default_character_data, default_persona_data
from pipeline_context import ChatData, PipelineContext, TurnData
from prompts import DEFAULT_PROMPTS
from schemas import validate_llm_output


def _scene():
    return {
        "rooms": {"room": {"name": "Room", "desc": "", "adjacent": []}},
        "positions": {"Hinami": "room", "Elyra Voss": "room"},
        "entities": {},
        "contacts": [{
            "actor": "Elyra Voss", "actor_part": "cock",
            "target": "Hinami", "target_interior": "vaginal canal",
            "target_part": "groin",
            "manner": "insert", "detail": "standing interior contact",
        }],
    }


def _assertion(target_part="cervix"):
    return {
        "actor": "Elyra Voss", "actor_part": "cock",
        "target": "Hinami", "target_interior": "vaginal canal",
        "target_part": target_part,
        "manner": "insert", "detail": "head pressing firmly",
    }


def test_interpret_schema_and_prompt_carry_exact_contact_assertions():
    parsed, warnings = validate_llm_output(
        "director_interpret", {"contact_assertions": [_assertion()]})

    assert not warnings
    assert parsed["contact_assertions"][0]["target_part"] == "cervix"
    prompt = DEFAULT_PROMPTS["director_interpret"]
    assert "contact_assertions" in prompt
    assert "'cervix', not the coarse visibility region 'groin'" in prompt
    assert "relation is surface|interior" in prompt
    assert "motion is settled|moving" in prompt
    assert "target_interior names the passage, chamber, material" in prompt
    assert "use op:'cross'" in prompt


def test_felt_contact_can_refine_standing_relation_but_not_mint_npc_act():
    scene = _scene()

    kept = _validated_player_contact_assertions(
        scene, [_assertion()], "Hinami")
    rejected = _validated_player_contact_assertions(scene, [{
        "actor": "Elyra Voss", "actor_part": "hand",
        "target": "Hinami", "target_part": "throat", "manner": "grip",
    }], "Hinami")

    assert kept[0]["target_part"] == "cervix"
    assert kept[0]["relation"] == "interior"
    assert kept[0]["motion"] == "settled"
    assert rejected == []

    subpart = _validated_player_contact_assertions(scene, [{
        **_assertion(), "actor_part": "head",
    }], "Hinami")
    assert subpart[0]["actor_part"] == "cock"


def test_resolve_cannot_silently_coarsen_asserted_contact_endpoint():
    assertion = {"op": "add", **_assertion()}
    coarse = {"op": "add", **_assertion("groin")}

    merged = _merge_player_contact_assertions([assertion], [coarse])
    assert [op["target_part"] for op in merged if op.get("op") == "add"] == [
        "cervix"]

    # A real later transition is expressible, but it must end the asserted
    # relation explicitly rather than overwriting its endpoint by re-description.
    moved = _merge_player_contact_assertions([assertion], [
        {"op": "remove", "actor": "Elyra Voss", "actor_part": "cock",
         "target": "Hinami", "target_part": "cervix"},
        coarse,
    ])
    assert moved[-1]["target_part"] == "groin"


def test_explicit_crossing_can_advance_a_player_declared_endpoint():
    assertion = {"op": "add", **_assertion()}
    crossing = {
        "op": "cross", "actor": "Elyra Voss", "actor_part": "cock",
        "target": "Hinami", "crossed_target_part": "cervix",
        "target_interior": "downstream chamber", "target_part": "far wall",
        "manner": "push", "relation": "interior", "motion": "moving",
    }

    validated = _validated_player_contact_assertions(
        {**_scene(), "contacts": [assertion]}, [crossing], "Hinami")
    merged = _merge_player_contact_assertions([assertion], validated)

    assert validated[0]["op"] == "cross"
    assert validated[0]["crossed_target_part"] == "cervix"
    assert merged[-1]["op"] == "cross"


def test_crossing_cannot_bypass_a_different_declared_endpoint():
    invalid = {
        "op": "cross", **_assertion("far wall"),
        "crossed_target_part": "groin",
        "target_interior": "downstream chamber",
    }

    assert _validated_player_contact_assertions(
        {**_scene(), "contacts": [{"op": "add", **_assertion()}]},
        [invalid], "Hinami") == []


def _ctx(temp_db):
    persona = default_persona_data("Hinami")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Contact onset", "", time.time(), persona_id))
    sheet = default_character_data("Elyra Voss")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Elyra Voss", json.dumps(sheet), "{}", time.time(), "char_elyra"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", _scene())
    temp_db.wset(chat_id, "known", {
        "Elyra Voss": ["Hinami"], "Hinami": ["Elyra Voss"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "I feel the exact contact.", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Contact onset", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="I feel the exact contact.",
                      created=time.time()),
        cast=cast, input="I feel the exact contact.")
    ctx["_player_room"] = "room"
    ctx.director_interpret = {
        "sequence": [{
            "type": "action", "attempt": "reacts to the exact contact",
            "observable": "body tenses", "visibility": "overt",
            "targets": [], "commitment": "asserted",
        }],
        "action": {"attempt": "reacts to the exact contact"},
        "contact_assertions": [{"op": "add", **_assertion()}],
        "flow": {"reactors": [char_id], "resolution_flags": {}},
    }
    return ctx, char_id


def test_other_participant_feels_exact_contact_in_perception_pass_one(
        temp_db, monkeypatch):
    import agents.perception as perception

    ctx, char_id = _ctx(temp_db)
    seen = {}

    def capture(role, key, system, payload, **kwargs):
        seen["contact"] = payload["scene"]["contacts"][0]
        return {"views": {str(char_id): "You are in the Room."}}

    monkeypatch.setattr(perception, "_agent_json", capture)
    view = perception.perception_act(ctx, nonce=0)["views"][str(char_id)]

    assert seen["contact"]["target_part"] == "cervix"
    assert "your cock registers hinami's vaginal canal enclosing it" in view.casefold()
    assert "contact at hinami's cervix" in view.casefold()
    assert "hinami's groin" not in view.casefold()
