"""Regression tests for memory creation during commit."""

import json
import time

from character_schema import default_character_data
from commit import commit_memories
from pipeline_context import ChatData, PipelineContext, TurnData

def test_episode_does_not_append_dialogue_again(
    temp_db,
    monkeypatch,
):
    import commit

    chat_id = temp_db.qi(
        """
        INSERT INTO chats(name,scenario,created)
        VALUES(?,?,?)
        """,
        ("Test", "", time.time()),
    )

    character_sheet = default_character_data("Alice")
    character_id = temp_db.qi(
        """
        INSERT INTO characters(name,sheet,source,created,resource_uid)
        VALUES(?,?,?,?,?)
        """,
        (
            "Alice",
            json.dumps(character_sheet),
            "{}",
            time.time(),
            "char_alice",
        ),
    )

    temp_db.qi(
        """
        INSERT INTO chat_chars(chat_id,char_id,status,state)
        VALUES(?,?,?,?)
        """,
        (chat_id, character_id, "active", "{}"),
    )

    turn_id = temp_db.qi(
        """
        INSERT INTO turns(chat_id,idx,player_input,created)
        VALUES(?,?,?,?)
        """,
        (chat_id, 1, "test", time.time()),
    )

    temp_db.wset(
        chat_id,
        "scene",
        {
            "rooms": {
                "kitchen": {
                    "name": "Kitchen",
                },
            },
            "positions": {
                "Alice": "kitchen",
            },
            "entities": {},
            "attire": {},
            "overlays": {},
        },
    )

    cast = temp_db.q(
        """
        SELECT ch.*,cc.state AS cstate,cc.status
        FROM chat_chars cc
        JOIN characters ch ON ch.id=cc.char_id
        WHERE cc.chat_id=?
        """,
        (chat_id,),
    )

    context = PipelineContext(
        chat=ChatData(
            id=chat_id,
            name="Test",
            persona_id=None,
            lorebook_id=None,
            scenario="",
            created=time.time(),
        ),
        turn=TurnData(
            id=turn_id,
            chat_id=chat_id,
            idx=1,
            player_input="test",
            created=time.time(),
        ),
        cast=cast,
        input="test",
    )

    quote = '"I promise I will return."'
    context.director_resolve = {
        "summary": "A promise was made.",
        "resolved_event": "Bob made a promise.",
        "dialogue_log": [{
            "speaker": "Bob",
            "exact_quote": quote,
            "volume": "normal",
            "intended_target": "Alice",
            "tone": "",
        }],
    }
    context.perception_outcome = {
        "views": {
            str(character_id): (
                f"Bob says: {quote}"
            ),
        },
    }

    captured = []

    def fake_add_memories_batch(memories=None, *, prepared_batch=None):
        batch = memories if memories is not None else prepared_batch["prepared"]
        captured.extend(batch)
        return list(range(1, len(batch) + 1))

    monkeypatch.setattr(
        commit,
        "add_memories_batch",
        fake_add_memories_batch,
    )
    monkeypatch.setattr(
        commit,
        "maybe_consolidate_character_memory",
        lambda *args, **kwargs: None,
    )

    commit_memories(context, nonce=0)

    episodes = [
        memory
        for memory in captured
        if memory["category"] == "episode"
    ]
    promises = [
        memory
        for memory in captured
        if memory["category"] == "promise"
    ]

    assert len(episodes) == 1
    assert episodes[0]["content"].count(
        "I promise I will return."
    ) == 1

    assert len(promises) == 1
    assert promises[0]["gist"] == "Bob: I promise I will return."