"""Regression tests for memory creation during commit."""

import json
import time

from story.character_schema import default_character_data
from persist.commit import commit_memories
from core.pipeline_context import ChatData, PipelineContext, TurnData

def test_episode_does_not_append_dialogue_again(
    temp_db,
    monkeypatch,
):
    from persist import commit

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

    # commit_memories resolves both names in commit_memory_write's
    # globals since the split; patching the commit facade would be inert.
    from persist import commit_memory_write
    monkeypatch.setattr(
        commit_memory_write,
        "add_memories_batch",
        fake_add_memories_batch,
    )
    monkeypatch.setattr(
        commit_memory_write,
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
    assert promises[0]["gist"] == "a voice: I promise I will return."
    assert promises[0]["content"].startswith("I heard a voice say ")

def test_embedding_fallback_is_surfaced_as_a_warning(temp_db):
    """A missing embeddings provider silently downgrades every stored vector
    to the local character-trigram hash. The downgrade was recorded on the
    EmbeddingBatch and read by nobody -- an audited live corpus had 100% of
    rows on the fallback with no signal anywhere. prepare_memory_commit must
    say so through the same warning channel every other turn anomaly uses."""
    from persist import commit

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    sheet = default_character_data("Alice")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Alice", json.dumps(sheet), "{}", time.time(), "char_alice"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", {
        "rooms": {"kitchen": {"name": "Kitchen"}},
        "positions": {"Alice": "kitchen"},
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
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="test", created=time.time()),
        cast=cast,
        input="test",
    )
    ctx.director_resolve = {
        "summary": "", "resolved_event": "", "dialogue_log": []}
    ctx.perception_outcome = {
        "views": {str(char_id): "The kettle boils over on the stove."}}

    # No embeddings provider is configured in a temp DB, so the batch embeds
    # through the deterministic local fallback.
    prepared = commit.prepare_memory_commit(ctx)

    assert prepared["memory_batch"]["prepared"], "a view must mint a memory"
    assert getattr(prepared["memory_batch"]["embedded"], "fallback", False)
    assert any("embeddings" in w for w in ctx.warnings), ctx.warnings
