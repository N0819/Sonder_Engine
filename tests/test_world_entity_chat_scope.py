"""Regression tests for chat-scoped world_entities / world_conditions.

Before schema v14 both tables had a bare GLOBAL primary key on the id the
model coins (entity_id / condition_id). Those ids ("rifle", "tardis") are
only unique within a chat, so a second chat reusing a name would either
collide on the global PK (INSERT failure) or, via commit's unscoped
SELECT/UPDATE, silently mutate the FIRST chat's row -- a cross-story leak.
v14 repartitions both tables on the composite key (chat_id, id).
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time

import pytest


def _new_chat(db, name="C"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def test_same_entity_id_isolated_across_chats(temp_db):
    a = _new_chat(temp_db, "A")
    b = _new_chat(temp_db, "B")
    for cid, tag in ((a, "A-rifle"), (b, "B-rifle")):
        temp_db.qi(
            "INSERT INTO world_entities(entity_id,chat_id,kind,name,payload) "
            "VALUES('rifle',?,?,?,?)",
            (cid, "object", "A rifle", json.dumps({"tag": tag})),
        )
    ra = temp_db.q("SELECT payload FROM world_entities WHERE entity_id='rifle' AND chat_id=?",
                   (a,), one=True)
    rb = temp_db.q("SELECT payload FROM world_entities WHERE entity_id='rifle' AND chat_id=?",
                   (b,), one=True)
    assert json.loads(ra["payload"])["tag"] == "A-rifle"
    assert json.loads(rb["payload"])["tag"] == "B-rifle"
    total = temp_db.q("SELECT COUNT(*) n FROM world_entities WHERE entity_id='rifle'",
                      one=True)["n"]
    assert total == 2


def test_same_condition_id_isolated_across_chats(temp_db):
    a = _new_chat(temp_db, "A")
    b = _new_chat(temp_db, "B")
    for cid, tag in ((a, "A"), (b, "B")):
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
            "started_at,payload,active) VALUES('poisoned',?,?,?,?,?,1)",
            (cid, "npc", "status", 1.0, json.dumps({"tag": tag})),
        )
    ra = temp_db.q("SELECT payload FROM world_conditions WHERE condition_id='poisoned' AND chat_id=?",
                   (a,), one=True)
    assert json.loads(ra["payload"])["tag"] == "A"
    assert temp_db.q("SELECT COUNT(*) n FROM world_conditions WHERE condition_id='poisoned'",
                     one=True)["n"] == 2


def test_duplicate_entity_within_one_chat_still_rejected(temp_db):
    a = _new_chat(temp_db, "A")
    temp_db.qi("INSERT INTO world_entities(entity_id,chat_id,kind,name,payload) "
               "VALUES('rifle',?,?,?,'{}')", (a, "object", "A rifle"))
    with pytest.raises(sqlite3.IntegrityError):
        temp_db.qi("INSERT INTO world_entities(entity_id,chat_id,kind,name,payload) "
                   "VALUES('rifle',?,?,?,'{}')", (a, "object", "Dup"))


def test_v13_to_v14_migration_preserves_data_and_repartitions_pk():
    """A populated pre-v14 database (bare global PK) must upgrade in place,
    keeping every row and switching to the composite (chat_id, id) key."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)

    import db

    old = db.DB
    try:
        db.configure(path)
        db.init()
        db.qi("INSERT INTO chats(id,name,scenario,created) VALUES(1,'Old','',0)")
        db.close_connection()

        # Recreate the two tables in their pre-v14 (global-PK) shape, populate
        # legacy rows, and roll the recorded version back to 13.
        raw = sqlite3.connect(path)
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.executescript(
            "DROP TABLE world_entities;"
            "DROP TABLE world_conditions;"
            "CREATE TABLE world_entities("
            "entity_id TEXT PRIMARY KEY,"
            "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
            "kind TEXT NOT NULL, subtype TEXT NOT NULL DEFAULT '',"
            "name TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL,"
            "created_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,"
            "retired_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL);"
            "CREATE TABLE world_conditions("
            "condition_id TEXT PRIMARY KEY,"
            "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,"
            "subject_id TEXT NOT NULL, kind TEXT NOT NULL, started_at REAL NOT NULL,"
            "expires_at REAL, next_tick REAL, payload TEXT NOT NULL,"
            "active INTEGER NOT NULL DEFAULT 1);"
        )
        raw.execute("INSERT INTO world_entities(entity_id,chat_id,kind,name,payload) "
                    "VALUES('tardis',1,'vehicle','The TARDIS',?)",
                    (json.dumps({"n": "legacy"}),))
        raw.execute("INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
                    "started_at,payload,active) VALUES('poisoned',1,'npc1','status',5.0,?,1)",
                    (json.dumps({"sev": "mild"}),))
        raw.execute("UPDATE schema_meta SET value='13' WHERE key='version'")
        raw.commit()
        raw.close()

        # Re-init runs only the v13 -> v14 migration.
        db.configure(path)
        db.init()

        raw = sqlite3.connect(path)
        ver = raw.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()[0]
        pk_e = [r[1] for r in raw.execute("PRAGMA table_info(world_entities)") if r[5]]
        pk_c = [r[1] for r in raw.execute("PRAGMA table_info(world_conditions)") if r[5]]
        raw.close()
        assert ver == "14"
        assert pk_e == ["entity_id", "chat_id"]
        assert pk_c == ["condition_id", "chat_id"]

        ent = db.q("SELECT * FROM world_entities WHERE entity_id='tardis' AND chat_id=1",
                   one=True)
        cond = db.q("SELECT * FROM world_conditions WHERE condition_id='poisoned' AND chat_id=1",
                    one=True)
        assert ent["name"] == "The TARDIS"
        assert json.loads(ent["payload"])["n"] == "legacy"
        assert cond["started_at"] == 5.0
        assert json.loads(cond["payload"])["sev"] == "mild"

        # Composite key now admits the same id under a different chat.
        db.qi("INSERT INTO chats(id,name,scenario,created) VALUES(2,'New','',0)")
        db.qi("INSERT INTO world_entities(entity_id,chat_id,kind,name,payload) "
              "VALUES('tardis',2,'vehicle','Other','{}')")
        assert db.q("SELECT COUNT(*) n FROM world_entities WHERE entity_id='tardis'",
                    one=True)["n"] == 2
    finally:
        db.close_connection()
        db.configure(old)
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(path + suffix):
                os.remove(path + suffix)
