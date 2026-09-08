"""A quick start that fails keeps the model calls it already paid for.

Reported from play (2026-09-08): "you just get several console messages that
generations succeed until errors and then deletes everything". Starting a
story from a greeting with a lived location makes two model calls to plan the
town, saves them as a resumable artifact on the chat's job -- the generator's
own comment calls that boundary "exactly what is worth not paying for twice"
-- and then, on any later failure, `start_story` deleted the chat. The delete
took the job with it, so the engine threw away the one thing it had gone out
of its way to keep, and the retry paid for both calls again.

The plan is now saved against WHAT WAS ASKED FOR rather than against the chat
it was made for, because the chat is the thing that does not survive. A start
that asks the same question adopts it and goes straight to the writes.
"""
from __future__ import annotations

import json

import pytest

from core.db import get_setting, set_setting
from world import charter_runtime as cr


REQUEST = {"brief": "a shuttered spa town under ash", "scale": "hamlet"}


def _job_with_plan(temp_db, cid, town=None):
    """A chat whose job holds a finished plan, as the boundary leaves it."""
    cr._save_job(cid, {
        "version": 1, "job_id": "j1", "owner": cr._GEN_OWNER,
        "status": "running", "stage": "planned",
        "digest": cr._request_digest(cid, REQUEST, None),
        "artifact": {"town": town or {"name": "Ashfall"},
                     "required_rooms_added": [], "lore_manifest": {},
                     "source_book": None, "owning_book": None,
                     "horizon": 0, "wants_history": False},
    })


def _chat(temp_db, name="start"):
    import time
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      (name, "", time.time()))


@pytest.fixture(autouse=True)
def _clean_salvage(temp_db):
    set_setting(cr.SALVAGED_PLAN_KEY, "")
    yield
    set_setting(cr.SALVAGED_PLAN_KEY, "")


def test_the_plan_survives_the_story_it_was_made_for(temp_db):
    cid = _chat(temp_db)
    _job_with_plan(temp_db, cid, town={"name": "Ashfall"})

    assert cr.salvage_plan(cid, REQUEST) is True
    # The chat goes; the plan does not.
    from persist.chat_delete import delete_chat_data
    delete_chat_data(cid)

    adopted = cr.take_salvaged_plan(REQUEST)
    assert adopted is not None
    assert adopted["town"]["name"] == "Ashfall"


def test_a_plan_is_adopted_only_by_the_question_it_answers(temp_db):
    cid = _chat(temp_db)
    _job_with_plan(temp_db, cid)
    cr.salvage_plan(cid, REQUEST)

    assert cr.take_salvaged_plan({"brief": "somewhere else entirely"}) is None
    # ...and refusing it does not consume it, so the right request still gets it.
    assert cr.take_salvaged_plan(REQUEST) is not None


def test_a_plan_is_taken_once(temp_db):
    """Adopted by ONE story: a plan left lying about would be picked up by a
    later unrelated start, which would then be playing in a town the author
    had abandoned."""
    cid = _chat(temp_db)
    _job_with_plan(temp_db, cid)
    cr.salvage_plan(cid, REQUEST)

    assert cr.take_salvaged_plan(REQUEST) is not None
    assert cr.take_salvaged_plan(REQUEST) is None


def test_there_is_nothing_to_keep_before_the_boundary(temp_db):
    """A failure BEFORE the two calls finished has bought nothing, and saying
    so is the difference between a retry that is free and one that is not."""
    cid = _chat(temp_db)
    cr._save_job(cid, {"version": 1, "job_id": "j1", "owner": cr._GEN_OWNER,
                       "status": "running", "stage": "planning",
                       "digest": "x", "artifact": None})
    assert cr.salvage_plan(cid, REQUEST) is False
    assert cr.take_salvaged_plan(REQUEST) is None


def test_a_corrupt_store_is_dropped_rather_than_raised(temp_db):
    """The store is read on a path whose whole point is recovering from a
    failure; it may not become a second one."""
    set_setting(cr.SALVAGED_PLAN_KEY, "{not json")
    assert cr.take_salvaged_plan(REQUEST) is None
    assert get_setting(cr.SALVAGED_PLAN_KEY, "") == ""


def test_only_the_most_recent_plan_is_kept(temp_db):
    """`SALVAGED_PLANS_KEPT` is one, and this is what that costs: two failed
    starts in a row keep the second plan."""
    assert cr.SALVAGED_PLANS_KEPT == 1
    first, second = _chat(temp_db, "a"), _chat(temp_db, "b")
    _job_with_plan(temp_db, first, town={"name": "First"})
    _job_with_plan(temp_db, second, town={"name": "Second"})
    cr.salvage_plan(first, REQUEST)
    cr.salvage_plan(second, REQUEST)

    adopted = cr.take_salvaged_plan(REQUEST)
    assert adopted["town"]["name"] == "Second"


def test_the_fingerprint_does_not_name_the_chat(temp_db):
    """The point of the whole mechanism: the same request made in a story that
    does not exist yet is the same question."""
    assert (cr._plan_fingerprint(REQUEST, None)
            == cr._plan_fingerprint(dict(REQUEST), None))
    assert (cr._request_digest(1, REQUEST, None)
            != cr._request_digest(2, REQUEST, None))


def test_the_stored_record_says_why_it_was_kept(temp_db):
    """A salvaged plan is also the only surviving evidence of the failure that
    produced it, so it carries the reason and the stage."""
    cid = _chat(temp_db)
    _job_with_plan(temp_db, cid)
    cr.salvage_plan(cid, REQUEST, reason="Unterminated string at line 130")

    stored = json.loads(get_setting(cr.SALVAGED_PLAN_KEY, "{}"))
    assert "Unterminated string" in stored["reason"]
    assert stored["stage"] == "planned"
