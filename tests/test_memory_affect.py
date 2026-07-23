"""Regression: a character's memories must carry the numeric valence/arousal of
its blended surface affect, not just the `emotional_context` text label. The
commit path used to set emotional_context from the mood label but leave
valence/arousal at their 0.0 default, so every stored memory read as
valence=0/arousal=0 (visible as always-zero boxes in the memory editor).

Captured at the batch boundary so no embedding provider is needed.
"""

import json
import time

import commit
from character_schema import default_character_data
from commit import prepare_memory_commit
from pipeline_context import ChatData, PipelineContext, TurnData


def _story(temp_db, name="Vorne"):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Test", "", time.time()))
    sheet = default_character_data(name)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time(), sheet["identity"]["uid"]))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    return chat_id, char_id, cast


def _capture_batch(monkeypatch):
    captured = {}

    def fake_batch(memories):
        captured["memories"] = memories
        return {"prepared": [], "embedded": None}  # skip real embedding

    monkeypatch.setattr(commit, "prepare_memories_batch", fake_batch)
    return captured


def test_memory_carries_surface_valence_and_arousal(temp_db, monkeypatch):
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)

    own_result = {
        "salience": 0.9,
        "sequence": [{"type": "speech", "text": "I won't do it."}],
        "active_state": {
            "mood": "afraid",
            "affect": {"surface": {"label": "afraid", "valence": -0.6, "arousal": 0.7}},
        },
    }
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=99, chat_id=chat_id, idx=3, player_input="well?",
                      created=time.time()),
        cast=cast, input="well?",
        director_resolve={"resolved_event": "The room waits.", "dialogue_log": []},
    )
    ctx.character_results = {char_id: own_result}

    prepare_memory_commit(ctx)

    mems = captured["memories"]
    own = [m for m in mems if m.get("category") == "self"]
    assert own, "expected an own-acts memory"
    m = own[0]
    assert m["emotional_context"] == "afraid"
    assert abs(m["valence"] - (-0.6)) < 1e-9
    assert abs(m["arousal"] - 0.7) < 1e-9


def test_memory_affect_defaults_to_zero_without_surface(temp_db, monkeypatch):
    chat_id, char_id, cast = _story(temp_db)
    captured = _capture_batch(monkeypatch)

    own_result = {
        "salience": 0.9,
        "sequence": [{"type": "speech", "text": "Fine."}],
        "active_state": {"mood": "neutral"},   # no affect block
    }
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=100, chat_id=chat_id, idx=4, player_input="?",
                      created=time.time()),
        cast=cast, input="?",
        director_resolve={"resolved_event": "Nothing.", "dialogue_log": []},
    )
    ctx.character_results = {char_id: own_result}

    prepare_memory_commit(ctx)
    own = [m for m in captured["memories"] if m.get("category") == "self"]
    assert own and own[0]["valence"] == 0.0 and own[0]["arousal"] == 0.0
