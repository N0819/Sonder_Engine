"""Review 2026-09-07 A15/A16/A18: the Writers' Room reads the frame it was
asked about, a restored Planner line keeps its own ceiling, and an attire
PUT writes the entries it names.
"""
import time

from core.db import wset, wset_for_frame
from story.room_conversation import (ROLE_MESSAGE_CHARS, dump_room_messages,
                                     restore_room_messages)
from story.room_slice import read_scene


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Room", "", time.time()))


def test_read_scene_pins_the_frame_it_is_given(temp_db):
    cid = _chat(temp_db)
    wset(cid, "scene", {"rooms": {"present_hall": {}}, "positions": {}})
    wset_for_frame(cid, "scene", {"rooms": {"flashback_hall": {}}, "positions": {}}, 7)
    assert "present_hall" in read_scene(cid)["rooms"]
    assert "flashback_hall" in read_scene(cid, 7)["rooms"]


def test_a_restored_planner_line_keeps_the_planners_ceiling(temp_db):
    cid = _chat(temp_db)
    long = "x" * 10_000
    with temp_db.transaction():
        restore_room_messages(cid, [{"role": "planner", "text": long,
                                     "turn_idx": 1, "frame_id": None}])
    kept = dump_room_messages(cid)
    assert ROLE_MESSAGE_CHARS["planner"] >= 10_000
    assert len(kept[0]["text"]) == 10_000


def test_an_attire_put_writes_only_the_entries_it_names(temp_db):
    from web.app import attire_put
    cid = _chat(temp_db)
    wset(cid, "scene", {"rooms": {"hall": {}}, "positions": {"A": "hall", "B": "hall"},
                        "attire": {"A": {"wearing": ["coat"]}, "B": {"wearing": ["hat"]}}})
    attire_put(cid, {"A": {"wearing": ["cloak"]}})
    ledger = temp_db.wget(cid, "scene")["attire"]
    assert ledger["B"]["wearing"] == ["hat"], "a body not named is untouched"
    assert "cloak" in str(ledger["A"])
    attire_put(cid, {"B": None})
    assert "B" not in temp_db.wget(cid, "scene")["attire"]
