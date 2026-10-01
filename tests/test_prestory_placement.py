"""A seeded past sits BEFORE the story, never in it (2026-09-30).

Journey histories, a greeting's knowledge, an inherited charter life and an
imported bank were written at turn 0 or with no turn. The recent window counts
turn 0 as recent, so for a character's first eight turns its whole seeded past
was delivered as "recent" and recall never ran on it -- measured on the concept
lab's planted 240-memory bank: over 262k characters of "recent" per character
call, the recalled lane empty -- and every seeded row read "at a time you cannot
place against now". At `PRESTORY_TURN_IDX` (-1) a row is visible from the
opening, never recent, and dated by its clock reading when the writer has one
(negative: before the story's clock began).
"""

import json
import time

from mind.memory import (
    PRESTORY_TURN_IDX,
    WHEN_BEFORE_RECORD,
    MemoryClock,
    memory_line,
    recent_memory_buffer,
    visible_memory_rows,
)


def _story(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", time.time()))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                         ("A", json.dumps({}), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    return chat_id, char_id


def _row(temp_db, chat_id, char_id, *, turn_idx, seconds, content, key):
    return temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,frame_id,kind,category,provenance,salience,content,"
        "gist,key_phrases,entities,location,emotional_context,valence,arousal,confidence,archived,event_key,"
        "embedding_model,encoded_at_seconds) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (chat_id, char_id, turn_idx, None, "episodic", "episode", "remembered", 0.6, content, content,
         "[]", "[]", "", "", 0.0, 0.0, 1.0, 0, key, "", seconds))


def test_a_seeded_memory_is_visible_from_the_opening_and_never_recent(temp_db):
    chat_id, char_id = _story(temp_db)
    _row(temp_db, chat_id, char_id, turn_idx=PRESTORY_TURN_IDX, seconds=None,
         content="I crossed the pass in the snow.", key="prestory:a")
    _row(temp_db, chat_id, char_id, turn_idx=1, seconds=60.0, content="A knock at the door.", key="lived:1")
    seen = visible_memory_rows(chat_id, char_id, before_turn_idx=0, viewer_frame_id=None,
                               include_archived=False, require_turn_idx=True)
    assert [r["event_key"] for r in seen] == ["prestory:a"]  # the opening can read it
    for current in range(1, 10):
        recent = recent_memory_buffer(chat_id, char_id, current, turns=8, limit=None)
        assert "prestory:a" not in {m.get("event_key") for m in recent}, current


def test_a_seeded_memory_is_dated_when_its_writer_knows_when(temp_db):
    chat_id, char_id = _story(temp_db)
    clock = MemoryClock(chat_id, char_id, 3)
    undated = {"turn_idx": PRESTORY_TURN_IDX, "encoded_at_seconds": None, "frame_id": None}
    assert clock.of_memory(undated) == WHEN_BEFORE_RECORD
    nine_days = {"turn_idx": PRESTORY_TURN_IDX, "encoded_at_seconds": clock.now_seconds - 9 * 86400.0,
                 "frame_id": None}
    assert "week" in clock.of_memory(nine_days) or "day" in clock.of_memory(nine_days)


def test_the_decision_models_memory_line_never_counts_beats_into_a_seeded_past():
    line = memory_line({"content": "I crossed the pass.", "turn_idx": PRESTORY_TURN_IDX}, 5)
    assert line.startswith("MEMORY (before this story") and "beats" not in line


def test_a_seeded_past_is_felt_once_when_it_is_planted(temp_db, monkeypatch):
    """Each seeded row that keeps nothing is asked once what it makes the mind
    feel, and keeps the answer as its moment -- dated in psych minutes when
    the row is dated -- so recall never asks again. A lived row, and a seeded
    one that already keeps a feeling, are not asked."""
    from llm import decisions
    from mind.affect_pass import feel_seeded, why_read
    chat_id, char_id = _story(temp_db)
    dated = _row(temp_db, chat_id, char_id, turn_idx=PRESTORY_TURN_IDX, seconds=-9 * 86400.0,
                 content="I sat with my brother's coat across my knees.", key="prestory:dated")
    undated = _row(temp_db, chat_id, char_id, turn_idx=PRESTORY_TURN_IDX, seconds=None,
                   content="The pass road in winter.", key="prestory:undated")
    _row(temp_db, chat_id, char_id, turn_idx=2, seconds=120.0, content="A knock.", key="lived:2")
    felt = _row(temp_db, chat_id, char_id, turn_idx=PRESTORY_TURN_IDX, seconds=None,
                content="Already kept.", key="prestory:felt")
    temp_db.qi("UPDATE memories SET feelings=? WHERE id=?",
               (json.dumps({"moment": {"felt": {}, "strength": 0.0, "turn": -1, "key": "x"}}), felt))
    asked = []

    def answer(state, questions):
        asked.extend(questions)
        out = {}
        for key in questions:
            if key.endswith(":strength"):
                out[key] = {"type": "choice", "probabilities": {"strong": 1.0}}
            elif key.endswith(":tone"):
                out[key] = {"type": "choice", "probabilities": {"very_unpleasant": 1.0}}
            else:
                out[key] = {"type": "choice", "probabilities": {"grief": 1.0}}
        return out

    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    assert feel_seeded(chat_id, char_id) == 2
    asked_rows = {k.split(":")[1] for k in asked}
    assert asked_rows == {str(dated), str(undated)}
    rows = {r["event_key"]: json.loads(r["feelings"]) for r in temp_db.q(
        "SELECT event_key, feelings FROM memories WHERE chat_id=? AND turn_idx<0", (chat_id,))}
    moment = rows["prestory:dated"]["moment"]
    assert moment["turn"] == PRESTORY_TURN_IDX and moment["strength"] > 0.5 and moment["felt"]
    assert moment["at"] == -9 * 24 * 60.0
    assert "at" not in rows["prestory:undated"]["moment"]
    assert why_read({"ref": "r", "feelings": rows["prestory:dated"]}) is None  # recall will not ask
    assert feel_seeded(chat_id, char_id) == 0  # nothing left to ask


def test_a_greetings_knowledge_seeds_are_planted_before_the_story_and_felt(temp_db, monkeypatch):
    """The greeting launch writes what the character knows going in at
    PRESTORY_TURN_IDX, and asks once what it makes the character feel."""
    from story import greetings
    chat_id, char_id = _story(temp_db)
    written, felt = [], []
    monkeypatch.setattr(greetings, "add_memories_batch", lambda rows: written.extend(rows))
    monkeypatch.setattr(greetings, "feel_seeded_quietly", lambda c, ch: felt.append((c, ch)))
    n = greetings._route_mind_memories(chat_id, char_id, [{"content": "The well at the camp is fouled."}], "you")
    assert n == 1 and written[0]["turn_idx"] == PRESTORY_TURN_IDX
    assert felt == [(chat_id, char_id)]
