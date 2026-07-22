"""_recent_self_lines feeds a character agent its own recent verbatim lines so
it can avoid repeating itself unawares (the 'Dr. Moon says keep moving three
turns running' loop) and vary/escalate instead."""

from __future__ import annotations

import json

from agents.character import _recent_self_lines


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("T", "", 0.0))


def _turn_with_dialogue(db, chat_id, idx, dialogue_log):
    tid = db.qi("INSERT INTO turns(chat_id,idx,created) VALUES(?,?,?)",
                (chat_id, idx, 0.0))
    sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                (tid, "director_resolve", "", 0))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps({"dialogue_log": dialogue_log}), 0.0))


def test_recent_self_lines_returns_own_lines_oldest_first(temp_db):
    chat_id = _chat(temp_db)
    _turn_with_dialogue(temp_db, chat_id, 0, [
        {"speaker": "Dr. Moon", "exact_quote": "Keep walking."},
        {"speaker": "Hinami", "exact_quote": "Where are we going?"},
    ])
    _turn_with_dialogue(temp_db, chat_id, 1, [
        {"speaker": "Dr. Moon", "exact_quote": "Keep moving."},
    ])

    lines = _recent_self_lines(chat_id, "Dr. Moon", current_turn_idx=2)
    assert [x["said"] for x in lines] == ["Keep walking.", "Keep moving."]
    # Another speaker's lines are never attributed to this character.
    assert all("Where are we going?" != x["said"] for x in lines)


def test_recent_self_lines_excludes_current_and_future_turns(temp_db):
    chat_id = _chat(temp_db)
    _turn_with_dialogue(temp_db, chat_id, 5, [
        {"speaker": "Dr. Moon", "exact_quote": "Earlier line."},
    ])
    _turn_with_dialogue(temp_db, chat_id, 6, [
        {"speaker": "Dr. Moon", "exact_quote": "This beat's line."},
    ])
    # Deciding turn 6: its own not-yet-committed line must not appear.
    lines = _recent_self_lines(chat_id, "Dr. Moon", current_turn_idx=6)
    assert [x["said"] for x in lines] == ["Earlier line."]


def test_recent_self_lines_empty_when_none(temp_db):
    chat_id = _chat(temp_db)
    assert _recent_self_lines(chat_id, "Dr. Moon", current_turn_idx=0) == []
    assert _recent_self_lines(chat_id, "Dr. Moon", current_turn_idx=None) == []
