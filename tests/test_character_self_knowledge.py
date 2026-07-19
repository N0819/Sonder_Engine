"""A character must know its own established public biography.

character_public_history is fed to the Director and Mapping stages (for
scene-building) and to other characters' perception of this one, but was
never included in the character's own decision payload -- meaning the
character had no way to stay consistent with facts already established
about itself (e.g. how long it has held a role), and could contradict its
own sheet's public_history purely because that information was never in
its own context.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

def test_character_payload_includes_own_public_history(temp_db, monkeypatch):
    import agents.character as character_module

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    sheet = default_character_data("Dr. Elena Voss")
    sheet["knowledge"]["public_history"] = (
        "Resident psychiatrist at Blackwood Sanatorium for eleven years."
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Dr. Elena Voss", json.dumps(sheet), "{}", time.time(), "char_voss"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )

    temp_db.wset(
        chat_id,
        "scene",
        {
            "location": "Blackwood Sanatorium", "time": "day",
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Dr. Elena Voss": "hall"},
            "entities": {}, "attire": {}, "overlays": {},
        },
    )

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "how long have you worked here?", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="how long have you worked here?",
                      created=time.time()),
        cast=cast,
        input="how long have you worked here?",
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

    assert captured["payload"]["self"]["public_history"] == (
        "Resident psychiatrist at Blackwood Sanatorium for eleven years."
    )
