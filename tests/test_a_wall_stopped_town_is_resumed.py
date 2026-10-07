"""A town the Writers' Room drafted and the wall stopped is resumed, not redone.

Measured (scratch story 166, 2026-10-07): a launch failed on "the Writers'
Room did not submit a location plan (14 calls, 6 steps, stopped: wall); it
had 20 room(s) and 2 institution(s) drafted" -- and the failure path cleared
the draft, so a retry would have started from nothing against the same wall.
The owner's rule for a SUBMITTED plan ("you've made it so i have to rerun
every single step instead of recovering from what the writers room sucesfully
planned", chat 150) now holds one step earlier: a failed pass PAUSES its
draft, closed to the draft tools, and a retry of the SAME request resumes it.
"""

import time

import agents.story_planner as story_planner
from story import location_design


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Fen", "", time.time()))


def _with_a_room(cid, digest):
    location_design.open_draft(cid, {"featured_residents": []}, digest)
    row = location_design.draft(cid)
    row["plan"]["rooms"]["quay"] = {"name": "Quay"}
    location_design.save_draft(cid, row)


def test_a_paused_draft_resumes_for_the_same_request_only(temp_db):
    cid = _chat(temp_db)
    _with_a_room(cid, "d1")
    location_design.pause_draft(cid)
    assert not location_design.is_open(cid), "closed to the draft tools"
    assert location_design.resumable_draft(cid, "d2", {}) is None, (
        "an author who changed the brief asked a different question")
    resumed = location_design.resumable_draft(cid, "d1", {"population": 9})
    assert resumed["plan"]["rooms"] == {"quay": {"name": "Quay"}}
    assert resumed["task"] == {"population": 9} and location_design.is_open(cid)


def test_an_empty_draft_is_not_resumed(temp_db):
    cid = _chat(temp_db)
    location_design.open_draft(cid, {}, "d1")
    location_design.pause_draft(cid)
    assert location_design.resumable_draft(cid, "d1", {}) is None


def test_a_retry_hands_the_room_what_it_had_drafted(temp_db, monkeypatch):
    cid = _chat(temp_db)
    tasks = []

    def planner(cid_, frame_id, *, task, regime, base_turn):
        tasks.append(task)
        row = location_design.draft(cid_)
        row["plan"]["rooms"]["quay"] = {"name": "Quay"}
        location_design.save_draft(cid_, row)
        return {"calls": 1, "steps": 1, "stopped": "wall"}

    monkeypatch.setattr(story_planner, "run_planner", planner)
    payload = {"author_brief": "A stilt town.", "lore": ""}
    for attempt in range(2):
        try:
            story_planner.run_location_plan(cid, None, payload=payload)
        except ValueError as exc:
            assert "did not submit" in str(exc)
    assert "resumed_draft" not in tasks[0]
    assert tasks[1]["resumed_draft"]["rooms"] == ["quay"]
    assert not location_design.is_open(cid), "paused again after the retry"
