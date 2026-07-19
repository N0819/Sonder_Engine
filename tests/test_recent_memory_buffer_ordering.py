"""Regression test for recent_memory_buffer's truncation direction.

Found live during the Doctor Who playtest: a character (the Doctor) doing
a memory-dense arc kept repeating a stale routine ("cutting the relay
panel") for many turns after the story had already moved him elsewhere
(escaping aboard a ship). Root cause -- recent_memory_buffer's query used
`ORDER BY turn_idx, id LIMIT ?` (oldest-first), so once a short turn
window accumulated more memory rows than `limit`, the LIMIT clause cut
off the NEWEST rows, not the oldest -- exactly backwards for a buffer
whose entire purpose is keeping a character's next decision grounded in
what most recently happened.
"""

from __future__ import annotations

import json
import time

from memory import recent_memory_buffer


def _insert_memory(temp_db, chat_id, char_id, turn_idx, content):
    temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,provenance,"
        "salience,content,gist,key_phrases,entities,location,emotional_context,"
        "valence,arousal,confidence,access_count,archived,event_key,embedding_model)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (chat_id, char_id, turn_idx, "episodic", "episode", "witnessed",
         0.5, content, content, "[]", "[]", "", "", 0.0, 0.0, 1.0, 0,
         0, "", ""),
    )


def _make_chat_and_char(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Doctor", json.dumps({}), "{}", time.time(), "char_doctor"),
    )
    return chat_id, char_id


def test_newest_memories_survive_truncation_in_a_dense_window(temp_db):
    chat_id, char_id = _make_chat_and_char(temp_db)

    # 15 memories, all within the last 4 turns (turns 8-11), exceeding the
    # default limit of 12 -- the exact "memory-dense window" scenario.
    for i in range(15):
        turn_idx = 8 + (i // 4)  # spreads across turns 8, 9, 10, 11
        _insert_memory(temp_db, chat_id, char_id, turn_idx, f"memory number {i}")

    result = recent_memory_buffer(chat_id, char_id, current_turn_idx=11, turns=4, limit=12)

    contents = [m["content"] for m in result]
    assert len(contents) == 12
    # The 3 OLDEST memories (0, 1, 2) must be the ones dropped -- the
    # newest 12 (3 through 14) must all survive.
    assert "memory number 14" in contents, "newest memory was dropped"
    assert "memory number 3" in contents
    assert "memory number 0" not in contents
    assert "memory number 2" not in contents


def test_result_stays_in_chronological_order(temp_db):
    chat_id, char_id = _make_chat_and_char(temp_db)
    for i in range(5):
        _insert_memory(temp_db, chat_id, char_id, 10 + i, f"memory number {i}")

    result = recent_memory_buffer(chat_id, char_id, current_turn_idx=14, turns=4, limit=12)

    turn_indices = [m["turn_idx"] for m in result]
    assert turn_indices == sorted(turn_indices), "buffer must read oldest-to-newest"
