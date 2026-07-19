"""Regression tests for identity masking in perception_outcome.

Deterministic dialogue/action injection must not reveal a source's real
name to a perceiver who has never been introduced to them -- it should
fall back to an appearance description or a generic unknown-actor label,
exactly like the existing action-onset masking in perception_act does for
NPCs observing the player.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

def _make_chat_and_cast(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    def add_character(name):
        sheet = default_character_data(name)
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), f"char_{name.lower()}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
        return char_id

    mara_id = add_character("Mara")
    elden_id = add_character("Elden")

    temp_db.wset(
        chat_id,
        "scene",
        {
            "location": "Blackthorn Lighthouse",
            "time": "night",
            "rooms": {
                "keeper_room": {
                    "name": "Keeper's Room",
                    "adjacent": [
                        {"to": "lamp_room", "barrier": "open", "distance": "near"},
                        {"to": "cellar", "barrier": "closed_door", "distance": "near"},
                    ],
                },
                "lamp_room": {"name": "Lamp Room", "adjacent": []},
                "cellar": {"name": "Cellar", "adjacent": []},
            },
            "positions": {"Mara": "lamp_room", "Elden": "cellar"},
            "entities": {},
            "attire": {},
            "overlays": {},
        },
    )

    # The player has met Mara but has never encountered Elden, who is
    # hiding in the cellar.
    temp_db.wset(chat_id, "known", {"The Stranger": ["Mara"]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "listen", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="listen",
                      created=time.time()),
        cast=cast,
        input="listen",
    )
    ctx["_player_room"] = "keeper_room"
    return ctx, mara_id, elden_id

def test_unrecognized_speaker_name_is_masked_in_player_view(temp_db, monkeypatch):
    import agents.perception as perception

    ctx, mara_id, elden_id = _make_chat_and_cast(temp_db)

    ctx.director_resolve = {
        "resolved_event": "Voices carry through the lighthouse.",
        "dialogue_log": [
            {"speaker": "Mara", "exact_quote": '"Mind the steps."',
             "volume": "normal", "intended_target": None, "tone": ""},
            {"speaker": "Elden", "exact_quote": '"Please, help me."',
             "volume": "shout", "intended_target": None, "tone": ""},
        ],
    }
    ctx.director_interpret = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        views = {"player": "You stand in the keeper's room, rain on the shutters."}
        for p in payload["perceivers"]:
            views[str(p["id"])] = f"You are in {p['room_name']}."
        return {"views": views}

    monkeypatch.setattr(perception, "_agent_json", fake_agent_json)

    result = perception.perception_outcome(ctx, nonce=0)
    player_view = result["views"]["player"]

    assert "Mind the steps" in player_view
    assert "Mara" in player_view, "recognized speaker should be named"

    assert "Elden" not in player_view, (
        "unrecognized speaker's real name leaked into the player's view"
    )
    assert "Please, help me" in player_view, (
        "the (unattributed) quote should still be delivered"
    )
