"""A branched or imported story re-emitting its pending event mints nothing.

An authored event's id hashes the chat id with the assertion, and the
"live row absorbs its echo" check looked the row up BY THAT ID. A branch
copies a pending event under a random remapped id (`web/app.py`'s
`_build_world_id_remap` registers every `scheduled_events.event_id`), and an
archive import keeps the id while the new chat's id changes the digest -- so
when the Director re-emits the still-standing assertion, which the module
docstring calls routine, the lookup missed, a second pending row was minted
with a fresh re-queue budget, and both were delivered as due: the
multiplication the id exists to prevent (story_scene_schema audit F3).

The absorption now asks whether THIS chat holds a live row carrying the same
assertion, whatever that row is called.
"""

from __future__ import annotations

import json
import time

from core.db import q
from story.authored_events import (due_authored_events, mint_authored_events,
                                   resolve_authored_events)


def _chat(temp_db, name="t"):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      (name, "", time.time()))


def _pending(cid):
    return q("SELECT event_id FROM scheduled_events WHERE chat_id=? "
             "AND kind='authored_event' AND status='pending'", (cid,))


def _copy_into(temp_db, src_cid, dst_cid, new_id=None):
    for row in q("SELECT * FROM scheduled_events WHERE chat_id=?", (src_cid,)):
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
            "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            (new_id or row["event_id"], dst_cid, row["due_at"], row["kind"],
             row["location_id"], row["payload"], row["seed"], row["status"]))


def test_a_branch_re_emitting_a_remapped_event_mints_nothing(temp_db):
    a, b = _chat(temp_db, "a"), _chat(temp_db, "b")
    assert mint_authored_events(a, 3, [{"summary": "The elevator crashes",
                                        "due_in_turns": 1}]) == 1
    # The branch helper registers every scheduled event id for a random
    # remap; the copy lands under an id no hash of the assertion produces.
    _copy_into(temp_db, a, b, new_id="0123456789abcdef")
    assert mint_authored_events(b, 4, [{"summary": "the elevator  crashes",
                                        "due_in_turns": 1}]) == 0
    assert len(_pending(b)) == 1


def test_an_imported_event_is_still_its_own_echo(temp_db):
    a, b = _chat(temp_db, "a"), _chat(temp_db, "b")
    mint_authored_events(a, 3, [{"summary": "The bell rings at noon",
                                 "due_in_turns": 2}])
    _copy_into(temp_db, a, b)                 # an archive keeps the id
    assert mint_authored_events(b, 4, [{"summary": "The bell rings at noon",
                                        "due_in_turns": 2}]) == 0
    assert len(_pending(b)) == 1


def test_a_finished_event_still_re_arms_in_the_branch(temp_db):
    """Only a LIVE row absorbs its echo: scheduling the same thing again after
    it fired or went stale is a new claim, as it always was."""
    a, b = _chat(temp_db, "a"), _chat(temp_db, "b")
    mint_authored_events(a, 3, [{"summary": "The bell rings at noon",
                                 "due_in_turns": 1}])
    _copy_into(temp_db, a, b, new_id="feedfacefeedface")
    temp_db.qi("UPDATE scheduled_events SET status='fired' WHERE chat_id=?",
               (b,))
    assert mint_authored_events(b, 9, [{"summary": "The bell rings at noon",
                                        "due_in_turns": 1}]) == 1
    assert len(_pending(b)) == 1


def test_a_payload_that_is_not_an_object_is_skipped_not_raised(temp_db):
    cid = _chat(temp_db)
    temp_db.qi(
        "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
        "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
        ("authored:junk", cid, 1.0, "authored_event", None,
         json.dumps(["not", "an", "object"]), "s", "pending"))
    assert mint_authored_events(cid, 1, [{"summary": "x happens"}]) == 1
    assert [e["summary"] for e in due_authored_events(cid, 5)] == ["x happens"]
    resolve_authored_events(cid, 5, "x happens", {"positions": {"x": "here"}})
