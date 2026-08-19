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

import pytest

from tests.helpers import remove_scratch_db, scratch_db_path

#: Every test here calls the real `db.init()`, which is fsync-bound. It builds
#: its own databases rather than taking `temp_db`, so the marker the conftest
#: applies by fixture name never reached it: these ran in the FAST tier, which
#: is documented as database-independent, and on the platter rather than the
#: tmpfs every other database test uses.
pytestmark = pytest.mark.slow


@pytest.fixture
def fresh_db_path():
    path = scratch_db_path()
    yield path
    remove_scratch_db(path)


class TestFreshDatabaseSkipsMigrations:
    def test_a_fresh_database_never_executes_the_last_migration_list(self, fresh_db_path, monkeypatch):
        from core import db

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
        from core import db

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
        from core import db

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


class TestARebuildMigrationSurvivesACrashedRebuild:
    """PERSISTENCE-F14. Three of the four recreate-copy-swap migrations drop
    their scratch table first, and say why in the same breath: a crash between
    the CREATE and the RENAME leaves a half-populated `*_new`, and
    `CREATE TABLE IF NOT EXISTS` then adopts it instead of building a fresh
    one. The fourth, `memory_summaries_v23`, did not -- so the copy landed on
    top of the wreckage and the migration died on the id it had already
    written, leaving the database at the OLD version with no way forward.
    """

    def _scratch_ddl(self, db, table):
        for steps in db.MIGRATIONS:
            for stmt in steps:
                if stmt.startswith("CREATE TABLE") and table in stmt.split("(")[0]:
                    return stmt
        raise AssertionError(f"no rebuild migration creates {table}")

    def test_a_leftover_scratch_table_does_not_wedge_the_upgrade(
            self, fresh_db_path):
        from core import db

        old_path = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                        ("Crashed", "", 0.0))
            char_id = db.qi(
                "INSERT INTO characters(name,sheet,source,created) "
                "VALUES(?,?,?,?)", ("Alice", "{}", "{}", 0.0))
            row_id = db.qi(
                "INSERT INTO memory_summaries(chat_id,char_id,scope,summary,"
                "updated) VALUES(?,?,?,?,?)",
                (cid, char_id, "autobiographical", "the real window", 0.0))

            # The wreckage a crash mid-copy leaves: the scratch table exists
            # and already holds the first row the copy wrote.
            db.qi(self._scratch_ddl(db, "memory_summaries_v23"))
            db.qi("INSERT INTO memory_summaries_v23(id,chat_id,char_id,scope,"
                  "summary,updated) VALUES(?,?,?,?,?,?)",
                  (row_id, cid, char_id, "autobiographical", "half-written", 0.0))

            db.qi("INSERT INTO schema_meta(key,value) VALUES('version','22') "
                  "ON CONFLICT(key) DO UPDATE SET value='22'")
            db.close_connection()

            db.init()

            kept = db.q("SELECT summary FROM memory_summaries WHERE id=?",
                        (row_id,), one=True)
            assert kept["summary"] == "the real window"
            leftover = db.q(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='memory_summaries_v23'", one=True)
            assert leftover is None
            version = db.q("SELECT value FROM schema_meta WHERE key='version'",
                           one=True)
            assert int(version["value"]) == db.SCHEMA_VERSION
        finally:
            db.close_connection()
            db.configure(old_path)

    def test_every_rebuild_migration_clears_its_scratch_table(self):
        """The class, not the instance: any future recreate-copy-swap step is
        held to the same rule by this test rather than by memory."""
        from core import db

        for steps in db.MIGRATIONS:
            created = [s.split("(")[0].split()[-1] for s in steps
                       if s.startswith("CREATE TABLE")]
            swapped = {s.split()[2] for s in steps
                       if s.startswith("ALTER TABLE") and " RENAME TO " in s}
            dropped = {s.split()[-1] for s in steps
                       if s.startswith("DROP TABLE IF EXISTS")}
            for table in created:
                if table in swapped:
                    assert table in dropped, (
                        f"{table} is rebuilt and renamed but never dropped "
                        "first; a crash mid-copy wedges the upgrade")
