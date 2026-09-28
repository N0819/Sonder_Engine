"""Evidence ids around the character call (`agents/character_evidence.py`).

The wire carries short handles in place of database- and observer-sized ids;
the bare reply cites nothing, so they are never read back. At commit, what
the read-back cited from this beat is re-keyed onto the episode memory minted
from the same witnessed beat. Moved here from the full card's kernel tests
when the kernel was deleted (2026-09-27).
"""

import json
import time

from agents.character_evidence import (
    bind_current_evidence_to_memory,
    compact_character_evidence,
)
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import prepare_memory_commit
from story.character_schema import default_character_data


def test_evidence_handles_are_short_and_one_per_id():
    payload = {
        "perception": {
            "observations": [
                {"observation_id": "current:77:0", "observed": {"text": "a bell"}},
            ],
            # A cue's pointer AT an observation takes that observation's handle.
            "impossible_knowledge": [{"line_ref": "current:77:0"}],
        },
        "memory": {
            "recent_episodes": [
                {"memory_ref": "event:very-long-hash", "gist": "old bell"},
            ],
            "recalled_old_memories": [
                {"memory_ref": "event:very-long-hash", "gist": "same bell"},
            ],
            "where_i_came_from": {
                "summary_id": "summary:long-hash", "summary": "a tower"},
        },
    }

    compacted, handles = compact_character_evidence(payload)

    assert compacted["perception"]["observations"][0]["observation_id"] == "o1"
    assert compacted["perception"]["impossible_knowledge"][0]["line_ref"] == "o1"
    assert compacted["memory"]["recent_episodes"][0]["memory_ref"] == "m1"
    assert compacted["memory"]["recalled_old_memories"][0]["memory_ref"] == "m1"
    assert compacted["memory"]["where_i_came_from"]["summary_id"] == "s1"
    assert handles == {"o1": "current:77:0", "m1": "event:very-long-hash",
                       "s1": "summary:long-hash"}
    # The prose beside each id is untouched, and so is the caller's payload.
    assert compacted["memory"]["recent_episodes"][0]["gist"] == "old bell"
    assert payload["perception"]["observations"][0]["observation_id"] == "current:77:0"


def test_commit_binds_current_evidence_to_the_episode_memory_in_place():
    result = {
        "appraisal": {
            "present_evidence": [{"event_id": "current:7:0"}],
            "memory_modulation": {"evidence": [{"event_id": "event:past"}]},
        },
        "belief_updates": [{
            "belief": "the bell is near",
            "evidence": [{"event_id": "current:7:1"}],
        }],
        "relationship_updates": [{
            "target_entity": "keeper",
            "trigger_event_ids": ["current:7:0", "event:past"],
        }],
        "sequence": [{"type": "action", "event_id": "current:phase:0"}],
    }

    returned = bind_current_evidence_to_memory(result, "event:this-episode")

    assert returned is result
    assert result["appraisal"]["present_evidence"][0]["event_id"] == "event:this-episode"
    assert result["appraisal"]["memory_modulation"]["evidence"][0]["event_id"] == "event:past"
    assert result["belief_updates"][0]["evidence"][0]["event_id"] == "event:this-episode"
    assert result["relationship_updates"][0]["trigger_event_ids"] == [
        "event:this-episode", "event:past"]
    assert result["sequence"][0]["event_id"] == "current:phase:0"


def test_commit_keeps_current_ids_when_no_episode_was_minted():
    result = {"belief_updates": [{
        "belief": "the bell is near", "evidence": [{"event_id": "current:7:1"}],
    }]}

    bind_current_evidence_to_memory(result, "")

    assert result["belief_updates"][0]["evidence"][0]["event_id"] == "current:7:1"


def test_the_episode_rekey_reaches_every_evidence_spelling():
    """A belief citing this beat must point at the episode minted for it,
    whichever way the citation was spelled."""
    for row, expected in (
            ({"evidence": "current:77:7"}, "event:MINTED"),
            ({"evidence": ["current:77:5", "event:old"]},
             ["event:MINTED", "event:old"]),
            ({"evidence": [{"event_id": "current:77:7"}]},
             [{"event_id": "event:MINTED"}]),
    ):
        out = bind_current_evidence_to_memory(
            {"belief_updates": [dict(row)]}, "event:MINTED")
        assert out["belief_updates"][0]["evidence"] == expected


def test_memory_commit_persists_current_evidence_as_the_episode_key(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Evidence", "", time.time()))
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(),
         sheet["identity"]["uid"]))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "ring the bell", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Evidence", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="ring the bell", created=time.time()),
        cast=cast,
        input="ring the bell",
    )
    ctx.director_resolve = {"dialogue_log": []}
    ctx.perception_outcome = {
        "views": {str(char_id): "A brass bell rings beside you."},
        "episodes": {str(char_id): "The brass bell rang beside me."},
        "episode_meta": {},
    }
    ctx.character_results = {char_id: {
        "active_state": {"mood": "alert", "wants": []},
        "appraisal": {},
        "sequence": [],
        "belief_updates": [{
            "belief": "the bell is within reach",
            "confidence": 0.8,
            "evidence": [{"event_id": f"current:{char_id}:0",
                          "fact": "the bell rang beside me"}],
        }],
    }}
    scene = {
        "location": "Belfry", "time": "now",
        "rooms": {"belfry": {"name": "Belfry", "adjacent": []}},
        "positions": {"Mara": "belfry"},
        "entities": {}, "attire": {}, "overlays": {},
    }

    prepared = prepare_memory_commit(ctx, scene=scene)

    episode = next(row for row in prepared["memory_batch"]["prepared"]
                   if row.get("char_id") == char_id
                   and row.get("category") == "episode")
    state = json.loads(next(row[2] for row in prepared["state_updates"]
                            if row[1] == char_id))
    belief = next(item for item in state["interior"]["beliefs"]
                  if item["belief"] == "the bell is within reach")
    assert belief["last_evidence"][0]["event_id"] == episode["event_key"]
