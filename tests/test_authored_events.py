"""Regression tests for player-scheduled (authored) future events (P4).

Live bug (Elevator Adventure, turn 15): the player narrated "(the elevator
crashes next turn)". The future beat was dropped, so the player had to re-narrate
"BOOOM!" by hand on turn 16. Fix: flow.scheduled_assertions are minted into
scheduled_events (kind 'authored_event'), delivered when due, and re-queued --
not dropped -- if the resolution fails to enact them.
"""

from __future__ import annotations

import time

from authored_events import (
    MAX_REQUEUES,
    due_authored_events,
    mint_authored_events,
    resolve_authored_events,
)


def _chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("t", "", time.time()))


def test_mint_and_due(temp_db):
    cid = _chat(temp_db)
    n = mint_authored_events(cid, 15, [{"summary": "the elevator crashes", "due_in_turns": 1}])
    assert n == 1
    # not due yet at turn 15
    assert due_authored_events(cid, 15) == []
    # due at turn 16
    due = due_authored_events(cid, 16)
    assert len(due) == 1 and due[0]["summary"] == "the elevator crashes"


def test_mint_defaults_due_in_one(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 5, [{"summary": "the door bursts open"}])
    assert due_authored_events(cid, 6)


def test_mint_is_idempotent_on_rerun(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 3, [{"summary": "the bridge collapses", "due_in_turns": 2}])
    mint_authored_events(cid, 3, [{"summary": "the bridge collapses", "due_in_turns": 2}])
    assert len(due_authored_events(cid, 5)) == 1  # stable id -> no double


def test_resolve_fires_when_covered(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 15, [{"summary": "the elevator crashes hard", "due_in_turns": 1}])
    fired, requeued, dropped = resolve_authored_events(
        cid, 16, "With a deafening boom the elevator crashes into the shaft floor.")
    assert (fired, requeued, dropped) == (1, 0, 0)
    # fired -> no longer pending/due
    assert due_authored_events(cid, 16) == []


def test_resolve_requeues_when_not_covered(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 15, [{"summary": "the elevator crashes", "due_in_turns": 1}])
    fired, requeued, dropped = resolve_authored_events(
        cid, 16, "Dr. Moon checks her phone. Nothing happens.")
    assert (fired, requeued, dropped) == (0, 1, 0)
    # re-queued to the next turn, still pending
    assert due_authored_events(cid, 16) == []       # bumped past 16
    assert len(due_authored_events(cid, 17)) == 1


def test_resolve_drops_after_requeue_limit(temp_db):
    cid = _chat(temp_db)
    mint_authored_events(cid, 0, [{"summary": "a meteor strikes the tower", "due_in_turns": 1}])
    # never covered: requeue MAX_REQUEUES times, then stale
    t = 1
    for _ in range(MAX_REQUEUES):
        f, r, d = resolve_authored_events(cid, t, "unrelated prose")
        assert (f, r, d) == (0, 1, 0)
        t += 1
    f, r, d = resolve_authored_events(cid, t, "still unrelated")
    assert (f, r, d) == (0, 0, 1)  # dropped/stale
    assert due_authored_events(cid, t + 5) == []
