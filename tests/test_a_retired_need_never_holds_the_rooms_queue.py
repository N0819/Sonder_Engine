"""A need of a retired channel is closed as it is read, so it never holds the
Writers' Room's queue.

`setting_fact` was retired on 2026-09-26 (`persist/commit_mapping`'s
docstring): nothing raises it and nothing answers it, but nothing closed the
needs already stored under it either, and `open_planning_needs` serves the
oldest first. Measured on the owner's database (audit of 2026-11-01,
world_misc_causal F11): in 19 of the 20 chats with open needs, the three
oldest open needs were `setting_fact` needs filed at turn 0, so the fill job's
three slots (`story_planner.FILL_NEEDS_PER_JOB`) were spent on them for good,
and chats 154, 157 and 158 held real room needs behind them.
"""

from __future__ import annotations

import time

from core.db import wset
from world.planning_needs import (PLANNING_NEEDS_KEY, RETIRED_NEED_REASONS,
                                  open_planning_needs, planning_needs)


def _stored(reason, subject, kind="thing", status="open", turn=0):
    return {"uid": "need_%s" % abs(hash((reason, subject))), "kind": kind,
            "reason": reason, "subject": subject,
            "identity": "%s:%s" % (kind, subject.casefold()),
            "surface": {}, "status": status, "filed_turn": turn,
            "filed_at": 1.0 + turn}


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Queue", "", time.time()))


def test_setting_fact_is_a_retired_reason():
    assert "setting_fact" in RETIRED_NEED_REASONS


def test_the_rooms_slice_reaches_the_needs_behind_the_retired_ones(temp_db):
    cid = _chat(temp_db)
    wset(cid, PLANNING_NEEDS_KEY, [
        _stored("setting_fact", "The cable car runs once a day."),
        _stored("setting_fact", "Iron burns the fae."),
        _stored("setting_fact", "The guild keeps the only maps."),
        _stored("declared_destination_unplanned", "the sail loft",
                kind="room", turn=23),
    ])
    opened = open_planning_needs(cid)
    assert [(n["reason"], n["subject"]) for n in opened[:3]] == [
        ("declared_destination_unplanned", "the sail loft")]


def test_a_retired_need_is_closed_with_its_reason_and_kept(temp_db):
    cid = _chat(temp_db)
    wset(cid, PLANNING_NEEDS_KEY, [
        _stored("setting_fact", "Iron burns the fae."),
        _stored("setting_fact", "The tide tables are wrong.", status="filled"),
    ])
    by_subject = {n["subject"]: n for n in planning_needs(cid)}
    open_one = by_subject["Iron burns the fae."]
    assert open_one["status"] == "closed"
    assert open_one["closed_reason"]
    # a need the Room already answered keeps its answer
    assert by_subject["The tide tables are wrong."]["status"] == "filled"
