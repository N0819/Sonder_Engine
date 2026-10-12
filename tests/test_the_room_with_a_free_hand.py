"""The Writers' Room with a free hand.

The owner, 2026-10-11, after the Saltmarsh run (the Room offered to plant the
foreman its own truths named, the player never asked, and every figure model
named him its own way): "test a mode where the writers room can just do
whatever". `story.mandates.free_hand_row`: a story key, else the host's
setting, OFF unless one says on. On, the Room holds one standing grant for
every capability but `research` -- the web stays the player's to open -- from
the story's first beat; it is part of what `active_mandates` answers and is
never stored.
"""
from __future__ import annotations

from core.db import set_setting, wset
from story import mandates as m
from story.room_conversation import mandates as stored_mandates
from tests.test_story_planner import _story


def test_off_unless_somebody_turns_it_on(temp_db):
    cid, _ = _story(temp_db)
    assert m.free_hand_row(cid) is None
    assert m.coverage(cid, None, {"plan_entity"})["ok"] is False


def test_on_it_covers_planning_people_and_harm_and_not_the_web(temp_db):
    cid, _ = _story(temp_db)
    wset(cid, m.FREE_HAND_STORY_KEY, "on")
    granted = m.coverage(cid, None, {"plan_entity", "create_people", "plan_rooms",
                                     "schedule_harm", "file_lore", "surprise"})
    assert granted["ok"] and granted["cited"] == [m.FREE_HAND_UID]
    assert m.coverage(cid, None, {"research"})["missing"] == ["research"]


def test_it_holds_from_the_first_beat_and_not_before(temp_db):
    """The prelude, the location plan and the opening run before the first
    beat, under the grants the engine gives them."""
    cid, _ = _story(temp_db, turns=1)          # the opening only: idx 0
    wset(cid, m.FREE_HAND_STORY_KEY, "on")
    assert m.free_hand_row(cid) is None
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
               (cid, 1, "", 0.0))
    assert m.free_hand_row(cid)["uid"] == m.FREE_HAND_UID


def test_the_story_says_first_and_the_host_second(temp_db):
    cid, _ = _story(temp_db)
    set_setting(m.FREE_HAND_SETTING, "on")
    try:
        assert m.free_hand_enabled(cid)
        wset(cid, m.FREE_HAND_STORY_KEY, "off")
        assert not m.free_hand_enabled(cid)
    finally:
        set_setting(m.FREE_HAND_SETTING, "")


def test_it_is_never_written_to_the_stored_grants_and_can_be_cited(temp_db):
    cid, _ = _story(temp_db)
    wset(cid, m.FREE_HAND_STORY_KEY, "on")
    m.grant_mandate(cid, None, text="Plan the docks.", capabilities=["plan_rooms"])
    assert m.FREE_HAND_UID not in [r["uid"] for r in stored_mandates(cid, None)]
    assert m.FREE_HAND_UID in [r["uid"] for r in m.active_mandates(cid, None)]
    assert m.FREE_HAND_UID in m.citation(cid, None, [m.FREE_HAND_UID])
    wset(cid, m.FREE_HAND_STORY_KEY, "off")
    assert m.FREE_HAND_UID not in [r["uid"] for r in m.active_mandates(cid, None)]


def test_the_rooms_payload_says_so(temp_db):
    from agents import story_planner as sp
    cid, _ = _story(temp_db)

    def payload():
        return sp._payload(cid, None, text="hi", task=None, transcript=[], step=0,
                           calls_left=10, seconds_left=60, turn_idx=2)
    assert "free_hand" not in payload()
    wset(cid, m.FREE_HAND_STORY_KEY, "on")
    assert payload()["free_hand"] is True
