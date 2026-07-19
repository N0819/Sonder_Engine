"""Regression tests for B15 from Fable's audit: db.init()'s migration
loop indexed MIGRATIONS[i-1] for i starting at `current` (0 for a
genuinely fresh database) -- Python's negative indexing turned i-1=-1
into MIGRATIONS[-1], the LAST (most recent) migration, running it FIRST
on every fresh install rather than skipping the whole migration chain
entirely. Harmless today only because every existing migration statement
happens to be an idempotent ALTER TABLE ADD COLUMN / CREATE INDEX IF NOT
EXISTS that no-ops via the "duplicate column" swallow against the
already-current freshly-created schema -- a future migration doing
anything non-idempotent (a data backfill, an UPDATE, a DROP) would
silently corrupt every new install.

Fixed by detecting a genuinely fresh database (no schema_meta table
before executescript(SCHEMA) runs) and stamping it straight to
SCHEMA_VERSION, skipping the incremental migration loop entirely --
that loop exists only to bring an OLDER, already-populated database up
to date.
"""

from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture
def fresh_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    yield path
    for p in (path, path + "-wal", path + "-shm"):
        if os.path.exists(p):
            os.remove(p)


class TestFreshDatabaseSkipsMigrations:
    def test_a_fresh_database_never_executes_the_last_migration_list(self, fresh_db_path, monkeypatch):
        import db

        old_path = db.DB
        db.configure(fresh_db_path)
        try:
            # A distinguishing, observable, deliberately NON-idempotent
            # side effect as the LAST migration list -- if the old
            # i-1 == -1 wraparound bug were still present, a fresh
            # database would run this FIRST instead of skipping the
            # whole migration chain.
            monkeypatch.setattr(db, "MIGRATIONS", [
                ["CREATE TABLE IF NOT EXISTS _t1(x INTEGER)"],
                ["INSERT INTO settings(key,value) VALUES('poison_marker','1')"],
            ])
            db.init()

            marker = db.q("SELECT value FROM settings WHERE key='poison_marker'", one=True)
            assert marker is None

            version = db.q("SELECT value FROM schema_meta WHERE key='version'", one=True)
            assert int(version["value"]) == db.SCHEMA_VERSION
        finally:
            db.close_connection()
            db.configure(old_path)

    def test_a_fresh_database_still_has_the_current_schema(self, fresh_db_path):
        import db

        old_path = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            row = db.q(
                "SELECT frame_id FROM chat_personas WHERE 0=1", one=False,
            )
            assert row == []  # the column exists (query didn't raise)
        finally:
            db.close_connection()
            db.configure(old_path)


class TestExistingDatabaseStillMigratesInOrder:
    def test_an_older_databases_migrations_run_in_ascending_order(self, fresh_db_path, monkeypatch):
        import db

        old_path = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()  # brand new -> stamped straight to SCHEMA_VERSION

            # Simulate an OLDER, already-populated database that has not
            # yet run the next two migrations.
            db.qi(
                "INSERT INTO schema_meta(key,value) VALUES('version',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(db.SCHEMA_VERSION - 2),),
            )

            order = []

            def make_migration(name):
                return [f"INSERT INTO settings(key,value) VALUES('order_{name}','{name}')"]

            # MIGRATIONS[k] represents the vk+1 -> vk+2 transition --
            # build a list long enough to cover SCHEMA_VERSION-1 entries,
            # with the LAST TWO distinguishable so ordering is observable.
            patched = [[f"-- noop {i} --"] for i in range(db.SCHEMA_VERSION - 3)]
            patched.append(make_migration("second_to_last"))
            patched.append(make_migration("last"))
            monkeypatch.setattr(db, "MIGRATIONS", patched)

            db.init()

            first = db.q("SELECT value FROM settings WHERE key='order_second_to_last'", one=True)
            second = db.q("SELECT value FROM settings WHERE key='order_last'", one=True)
            assert first is not None
            assert second is not None

            version = db.q("SELECT value FROM schema_meta WHERE key='version'", one=True)
            assert int(version["value"]) == db.SCHEMA_VERSION
        finally:
            db.close_connection()
            db.configure(old_path)
