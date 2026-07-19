"""Regression test for commit_memories' per-character consolidation loop:
each character's maybe_consolidate_character_memory call now runs in a
thread pool rather than one after another. Every character must still be
attempted, a failure for one must not affect another's result or note, and
successful notes must all land in the returned committed list."""

from __future__ import annotations

import json
import time

import commit
from character_schema import default_character_data
from commit import commit_memories
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_character(db, name):
    sheet = default_character_data(name)
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time(), f"char_{name}"),
    )


def test_all_characters_are_attempted_and_one_failure_does_not_block_others(
    temp_db, monkeypatch,
):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    names = ["Alice", "Bob", "Cara"]
    char_ids = {name: _make_character(temp_db, name) for name in names}
    for name, cid in char_ids.items():
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, cid, "active", "{}"),
        )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "test", time.time()),
    )
    temp_db.wset(chat_id, "scene", {
        "rooms": {}, "positions": {}, "entities": {}, "attire": {}, "overlays": {},
    })

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    context = PipelineContext(
        chat=ChatData(
            id=chat_id, name="Test", persona_id=None, lorebook_id=None,
            scenario="", created=time.time(),
        ),
        turn=TurnData(
            id=turn_id, chat_id=chat_id, idx=1, player_input="test",
            created=time.time(),
        ),
        cast=cast, input="test",
    )
    context.director_resolve = {"summary": "", "resolved_event": "", "dialogue_log": []}
    context.perception_outcome = {"views": {}}

    monkeypatch.setattr(
        commit, "add_memories_batch",
        lambda memories=None, *, prepared_batch=None: [],
    )

    id_to_name = {v: k for k, v in char_ids.items()}
    called = []

    def fake_maybe_consolidate(cid, char_id, turn_idx, *, frame_id=None):
        name = id_to_name[char_id]
        called.append(name)
        if name == "Bob":
            raise RuntimeError("simulated consolidation failure")
        if name == "Alice":
            return {"summary": "updated"}
        return None

    monkeypatch.setattr(
        commit, "maybe_consolidate_character_memory", fake_maybe_consolidate,
    )

    result = commit_memories(context, nonce=0)

    assert sorted(called) == ["Alice", "Bob", "Cara"]
    assert "Alice: autobiographical summary updated" in result["committed"]
    assert not any("Bob" in note for note in result["committed"])
    assert not any("Cara" in note for note in result["committed"])
    assert any(
        "Memory consolidation failed for character" in w
        for w in context.warnings
    )
