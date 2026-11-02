"""Every foreign key onto a turn or an era has an index that leads with it.

Deleting a `turns` row makes SQLite find every child row naming it -- to set
it NULL or to cascade -- and a child column with no index whose LEADING
column it is turns each of those lookups into a scan of the whole table,
every chat's rows included. Measured (audit 2026-11-01, persistence P1):
deleting a 1,000-turn story while another held 60k world_events, 20k
entities and 5k rooms took 17.6 s inside the global write lock, 0.035 s with
the columns indexed; it is paid by story deletion, `turn_del`, a take-back
and every discarded stepless turn. `frames` is the same: one era deleted,
nine tables scanned.

The class: a key onto `turns(id)` or `frames(id)` is not added without its
index. `LATE_SCHEMA` holds them (it runs on every open, after the migration
chain, so an older file gets them without a migration).
"""

from __future__ import annotations

import sqlite3

import pytest

PARENTS = ("turns", "frames")


def _unindexed(path):
    c = sqlite3.connect(path)
    try:
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        missing = []
        for table in tables:
            leads = set()
            for index in c.execute(f'PRAGMA index_list("{table}")'):
                cols = [r[2] for r in c.execute(f'PRAGMA index_info("{index[1]}")')]
                if cols:
                    leads.add(cols[0])
            for fk in c.execute(f'PRAGMA foreign_key_list("{table}")'):
                if fk[2] in PARENTS and fk[3] not in leads:
                    missing.append(f"{table}.{fk[3]} -> {fk[2]}")
        return sorted(missing)
    finally:
        c.close()


def test_a_fresh_file_indexes_every_key_onto_a_turn_or_an_era(temp_db):
    assert _unindexed(temp_db.DB) == []


def test_deleting_a_turn_uses_the_index_not_a_scan(temp_db):
    """The plan SQLite makes for the FK action's own lookup."""
    c = sqlite3.connect(temp_db.DB)
    try:
        for table, column in (("world_events", "turn_id"),
                              ("world_entities", "created_turn_id"),
                              ("room_registry", "retired_turn_id"),
                              ("lorebooks", "retired_turn_id"),
                              ("memories", "frame_id")):
            plan = " ".join(r[3] for r in c.execute(
                f"EXPLAIN QUERY PLAN UPDATE {table} SET {column}=NULL WHERE {column}=?",
                (1,)))
            assert "USING" in plan and "INDEX" in plan, (table, column, plan)
    finally:
        c.close()
