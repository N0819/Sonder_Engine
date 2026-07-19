"""Integration tests for theory-of-mind revision through the real commit path.

Verifies commit.py's commit_memories persists blended/decayed mind-model
state via theory_of_mind.apply_mind_model_updates (not the old
exact-text-keyed max() accumulation), and that agents/character.py's
payload construction surfaces competing hypotheses.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

def test_commit_memories_reinforces_existing_mind_model(temp_db, monkeypatch):
    import commit

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara"),
    )

    pre_existing_state = {
        "mind_models": {
            "Rowan": {
                "hypotheses": [{
                    "about_entity": "Rowan", "kind": "goal",
                    "claim": "wants to leave the lighthouse",
                    "confidence": 0.3, "evidence": [],
                    "last_updated_turn": 0,
                }],
            }
        }
    }
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(pre_existing_state)),
    )

    temp_db.wset(chat_id, "scene", {
        "rooms": {"lamp_room": {"name": "Lamp Room"}},
        "positions": {"Mara": "lamp_room"},
        "entities": {}, "attire": {}, "overlays": {},
    })

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "test", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="test",
                      created=time.time()),
        cast=cast,
        input="test",
    )
    ctx.director_resolve = {"summary": "", "resolved_event": "", "dialogue_log": []}
    ctx.character_results = {
        char_id: {
            "sequence": [],
            "mind_model_updates": [{
                "about_entity": "Rowan", "kind": "goal",
                "claim": "wants to leave the lighthouse tonight",
                "confidence": 0.9, "evidence": [],
            }],
        }
    }

    monkeypatch.setattr(
        commit, "add_memories_batch",
        lambda memories=None, *, prepared_batch=None: list(
            range(1, len(memories if memories is not None else prepared_batch["prepared"]) + 1)
        ),
    )
    monkeypatch.setattr(
        commit, "maybe_consolidate_character_memory",
        lambda *a, **k: None,
    )

    commit.commit_memories(ctx, nonce=0)

    row = temp_db.q(
        "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
        (chat_id, char_id), one=True,
    )
    hyps = json.loads(row["state"])["mind_models"]["Rowan"]["hypotheses"]

    assert len(hyps) == 1, "reworded restatement should reinforce the existing belief"
    assert 0.3 < hyps[0]["confidence"] < 0.9, (
        "commit path should blend confidence via theory_of_mind, not snap to the "
        "new value the way the old max()-only merge did"
    )

def test_character_payload_surfaces_competing_hypotheses(temp_db):
    import agents.character as character_mod

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    sheet = default_character_data("Mara")
    stored_state = {
        "mind_models": {
            "Rowan": {
                "hypotheses": [
                    {"about_entity": "Rowan", "kind": "goal",
                     "claim": "wants to protect the keeper's logbook",
                     "confidence": 0.3, "evidence": [], "last_updated_turn": 1},
                    {"about_entity": "Rowan", "kind": "goal",
                     "claim": "wants to sabotage the radio tower",
                     "confidence": 0.65, "evidence": [], "last_updated_turn": 1},
                ],
            }
        }
    }
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(stored_state)),
    )

    temp_db.wset(chat_id, "scene", {
        "rooms": {"lamp_room": {"name": "Lamp Room"}},
        "positions": {"Mara": "lamp_room"},
        "entities": {}, "attire": {}, "overlays": {},
    })

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "test", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="test",
                      created=time.time()),
        cast=cast,
        input="test",
    )
    ctx.director_interpret = {}

    row = cast[0]
    stored = json.loads(row["cstate"] or "{}")
    payload_mind_models = character_mod.mind_models_for_payload(
        stored.get("mind_models") or {}, ctx.turn.idx,
    )

    goal_view = payload_mind_models["Rowan"]["goal"]
    assert "sabotage" in goal_view["leading"]["claim"]
    assert len(goal_view["competitors"]) == 1
    assert "logbook" in goal_view["competitors"][0]["claim"]
