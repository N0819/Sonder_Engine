"""A hand-edited narrator step never stops the story being told.

`/api/steps/{sid}/edit` stores whatever the request body holds, so a narrator
variant can hold a JSON string, a list or null (`persist.steps.active_mapping`
says so, and B23 fixed the same read in the Dramaturge). The narrator's own
history readers kept `(json.loads(content) or {}).get("prose")` inside an
`except (TypeError, ValueError)` -- a string or a list raised AttributeError
there, so every narrator (and `narrator_extra`) call whose history window held
that turn failed, for `narrator_history_turns` (12) beats (review 2026-11-01,
agents_narration_planner F6, reproduced by snippet).
"""

from __future__ import annotations

import json

from agents import narration


def _turns(temp_db, key, contents, persona_id=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("N", "", 0.0))
    for idx, content in enumerate(contents, start=1):
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, idx, f"input {idx}", 0.0))
        if persona_id is not None:
            temp_db.qi(
                "INSERT INTO turn_player_inputs(chat_id,turn_idx,persona_id,input,created) "
                "VALUES(?,?,?,?,?)", (chat_id, idx, persona_id, f"extra {idx}", 0.0))
        sid = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
            (tid, key, key, 0))
        temp_db.qi(
            "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
            (sid, content, 0.0))
    return chat_id


def test_the_primary_seat_reads_past_an_edited_step(temp_db):
    chat_id = _turns(temp_db, "narrator", [
        json.dumps("a hand-edited page"), json.dumps([1, 2]), "null",
        json.dumps({"prose": ["not", "text"]}),
        json.dumps({"prose": "The rain kept on."})])
    block, prev = narration._past_narration_block(chat_id, 9, None, 12)
    assert prev == ["The rain kept on."]
    assert "input 1" in block and "The rain kept on." in block


def test_an_extra_seat_reads_past_an_edited_step(temp_db):
    pid = temp_db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)", ("Wren", "{}"))
    seat = str(pid)
    chat_id = _turns(temp_db, "narrator_extra", [
        json.dumps("a hand-edited page"), json.dumps([1, 2]),
        json.dumps({seat: "not a page"}),
        json.dumps({seat: {"prose": "The lamp guttered."}})], persona_id=pid)
    block, prev = narration._past_narration_extra_block(chat_id, 9, None, pid, 12)
    assert prev == ["The lamp guttered."]
    assert "The lamp guttered." in block
