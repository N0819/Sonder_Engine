"""Objective event spine: writer and every persistence boundary.

This table was intentionally dormant until checkpoint, archive, and branch
behavior could land with its first writer. These tests are the gate.
"""

from __future__ import annotations

import json
import time
import types

import app
from checkpoints import ensure_checkpoint, restore_checkpoint, snapshot_state


def _story(db):
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Event story", "", time.time()),
    )
    frame_id = db.qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,created) "
        "VALUES(?,?,?,?,?)", (cid, "Present", 0, "present", time.time()),
    )
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (cid, 0, "wait", time.time(), frame_id),
    )
    db.qi(
        "INSERT INTO world_entities(entity_id,chat_id,kind,name,payload) "
        "VALUES(?,?,?,?,?)", ("gate", cid, "object", "Gate", "{}"),
    )
    return cid, frame_id, turn_id


def _insert_event(db, cid, frame_id, turn_id, event_id="evt_world"):
    db.qi(
        "INSERT INTO world_events(event_id,chat_id,turn_id,frame_id,"
        "occurred_at,duration_seconds,kind,location_id,payload,seed,committed) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, cid, turn_id, frame_id, 120.0, 0.0, "consequence",
         "courtyard", json.dumps({"entity_id": "gate", "what": "closed"}),
         "seed", time.time()),
    )


def _events(db, cid):
    return [dict(row) for row in db.q(
        "SELECT * FROM world_events WHERE chat_id=? ORDER BY event_id", (cid,))]


def test_fired_mechanics_event_is_promoted_once(temp_db):
    from commit import commit_world_event_spine
    from db import transaction

    cid, frame_id, turn_id = _story(temp_db)
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=turn_id, frame_id=frame_id),
    )
    transit = {"fired_events": [{
        "event_id": "scheduled_gate", "kind": "consequence",
        "location_id": "courtyard", "occurred_at": 120.0,
        "payload": json.dumps({"what": "the gate closed", "entity_id": "gate"}),
        "seed": "seed",
    }]}
    with transaction():
        first = commit_world_event_spine(ctx, transit)
        second = commit_world_event_spine(ctx, transit)
    assert first["written"] == 1 and second["written"] == 0
    row = _events(temp_db, cid)[0]
    assert row["frame_id"] == frame_id and row["turn_id"] == turn_id
    payload = json.loads(row["payload"])
    assert payload["source_event_id"] == "scheduled_gate"
    assert payload["entity_id"] == "gate"


def test_checkpoint_restore_rewinds_objective_history(temp_db):
    cid, frame_id, turn_id = _story(temp_db)
    _insert_event(temp_db, cid, frame_id, turn_id)
    before = _events(temp_db, cid)
    assert snapshot_state(cid)["world_events"][0]["event_id"] == "evt_world"
    ensure_checkpoint(cid, 1)
    temp_db.qi("DELETE FROM world_events WHERE chat_id=?", (cid,))
    _insert_event(temp_db, cid, frame_id, turn_id, "discarded_timeline")
    restore_checkpoint(cid, 1)
    assert _events(temp_db, cid) == before


def test_portable_archive_remaps_turn_and_frame_and_keeps_source(temp_db):
    cid, frame_id, turn_id = _story(temp_db)
    _insert_event(temp_db, cid, frame_id, turn_id)
    exported = app.chat_export(cid)
    assert exported["world_events"][0]["event_id"] == "evt_world"

    imported = app.chat_import({"data": exported})
    ncid = imported["id"]
    source = _events(temp_db, cid)[0]
    copied = _events(temp_db, ncid)[0]
    assert copied["event_id"] == source["event_id"]  # composite chat key
    assert copied["turn_id"] != source["turn_id"]
    assert copied["frame_id"] != source["frame_id"]
    assert temp_db.q("SELECT COUNT(*) AS n FROM world_events WHERE event_id=?",
                     ("evt_world",), one=True)["n"] == 2


def test_branch_mints_event_id_and_remaps_payload_and_foreign_keys(temp_db):
    cid, frame_id, turn_id = _story(temp_db)
    _insert_event(temp_db, cid, frame_id, turn_id)
    branched = app.turn_branch(turn_id)
    ncid = branched["id"]
    copied = _events(temp_db, ncid)[0]
    assert copied["event_id"] != "evt_world"
    assert copied["turn_id"] != turn_id
    assert copied["frame_id"] != frame_id
    new_entity = temp_db.q(
        "SELECT entity_id FROM world_entities WHERE chat_id=?", (ncid,), one=True)
    assert json.loads(copied["payload"])["entity_id"] == new_entity["entity_id"]
    for checkpoint in temp_db.q(
            "SELECT blob FROM checkpoints WHERE chat_id=?", (ncid,)):
        for event in json.loads(checkpoint["blob"]).get("world_events") or []:
            assert event["event_id"] != "evt_world"
            assert event["turn_id"] != turn_id
            assert event["frame_id"] != frame_id


def test_v26_migration_adds_frame_scope_and_chat_partition(temp_db):
    cid, _, turn_id = _story(temp_db)
    temp_db.qi("DROP TABLE world_events")
    temp_db.qi(
        "CREATE TABLE world_events(event_id TEXT PRIMARY KEY,chat_id INTEGER "
        "NOT NULL REFERENCES chats(id) ON DELETE CASCADE,turn_id INTEGER "
        "REFERENCES turns(id) ON DELETE SET NULL,occurred_at REAL NOT NULL,"
        "duration_seconds REAL NOT NULL DEFAULT 0,kind TEXT NOT NULL,"
        "location_id TEXT,payload TEXT NOT NULL,seed TEXT,committed REAL NOT NULL)")
    temp_db.qi(
        "INSERT INTO world_events VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("legacy", cid, turn_id, 12.0, 0.0, "news_arrival", "square", "{}",
         "seed", time.time()))
    temp_db.qi("UPDATE schema_meta SET value='26' WHERE key='version'")
    temp_db.close_connection()
    temp_db.init()

    columns = {row["name"] for row in temp_db.q("PRAGMA table_info(world_events)")}
    assert "frame_id" in columns
    row = temp_db.q("SELECT * FROM world_events WHERE chat_id=?", (cid,), one=True)
    assert row["event_id"] == "legacy" and row["frame_id"] is None
    pk = [row["name"] for row in temp_db.q("PRAGMA table_info(world_events)")
          if row["pk"]]
    assert pk == ["event_id", "chat_id"] or pk == ["chat_id", "event_id"]
