"""A question is a question in Japanese too, and a line's `to` names the
person it is said to whatever honorific or particle follows the name.

Measured (review 2026-11-01, agents_character_background F12): four
readers in `agents/character.py` tested `"?" in line`, and
`'?' in 'どこへ行くの？'` is False -- so in a Japanese story the player's
questions never became `awaiting_your_answer`, `recent_self_moves.asked`
stayed empty and the repeated-ask screen never fired. The engine's other
readers already include `？` (`director_floors`, `impossible_knowledge`, the
pack's `_QUESTION_MARKS`). And `character_bare._named_here` bounded a name
with `(?<!\\w)...(?!\\w)`: `_named_here('田中さん', ['田中'])` was None while
`_named_here('Mr. Tanaka', ['Tanaka'])` was 'Tanaka', so a Japanese line
whose `to` carried an honorific went to nobody when it was not read back.
"""

from __future__ import annotations

import json
import time

from agents.character import _this_beat_self_record, _unanswered_question_note
from agents.character_bare import _named_here


def test_a_japanese_question_is_recorded_as_asked():
    _lines, move = _this_beat_self_record(
        {"sequence": [{"type": "speech", "text": "誰が建てたと思う？"}],
         "interaction": {"expects_response": True}}, 9)
    assert move.get("asked") == ["誰が建てたと思う？"]


def test_a_japanese_question_from_the_player_is_owed(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", 0.0))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
        ("The Doctor", json.dumps({"identity": {"name": "The Doctor"}}), 0.0))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    tid = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 145, "", time.time()))
    speech = "その箱は本当は何なの？"
    for key, content in (
            ("director_interpret", {"speech": speech, "flow": {"addressed_to": [char_id]}}),
            ("perception_act", {"views": {str(char_id): speech}})):
        sid = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
            (tid, key, key, 0))
        temp_db.qi(
            "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
            (sid, json.dumps(content), time.time()))
    owed = _unanswered_question_note(chat_id, "The Doctor", char_id, 146, None)
    assert owed.get("awaiting_your_answer", {}).get("asked") == speech


def test_a_full_width_question_mark_is_a_question():
    from agents.character import _is_question
    assert _is_question("どこへ行くの？")
    assert _is_question("Where are you going?")
    assert not _is_question("ここで待つ。")
    assert not _is_question("Wait here.")


def test_a_name_with_an_honorific_or_particle_is_the_person_it_names():
    assert _named_here("田中さん", ["田中", "佐藤"]) == "田中"
    assert _named_here("ヒナミに", ["ヒナミ", "田中"]) == "ヒナミ"
    assert _named_here("Mr. Tanaka", ["Tanaka"]) == "Tanaka"
    assert _named_here("the tall man", ["the tall man", "the man"]) == "the tall man"
    # Still whole: a name inside another word names nobody.
    assert _named_here("ヒナミコ", ["ヒナミ"]) is None
    assert _named_here("Hinamis", ["Hinami"]) is None
