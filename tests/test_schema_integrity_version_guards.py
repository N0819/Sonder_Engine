"""MASTER-007 / MASTER-006 / MASTER-008(a): what ``db.init()`` does with a
database it should not silently accept.

- A file stamped NEWER than SCHEMA_VERSION used to open without a word: the
  migration loop is ``range(current, SCHEMA_VERSION)``, empty when current is
  ahead, and nothing else compared them. Precedent for the harm is in-repo:
  v13->v14 repartitioned world_entities/world_conditions onto (chat_id, id),
  so an older binary writing a newer file uses the wrong key space.
- A file with tables but NO schema_meta at all used to be adopted:
  executescript(SCHEMA) is all IF NOT EXISTS, so the foreign tables survived
  as-is, and the unconditional stamp then asserted -- falsely, permanently --
  that the file was fully migrated.
- ADD COLUMN idempotence in the migration loop used to ride on matching
  "duplicate column" in the error message; it is now answered by
  introspection (PRAGMA table_xinfo), with re-runnability preserved (the
  crash-recovery property tests/test_fable_audit_migrations.py pins).
"""

from __future__ import annotations

import sqlite3

import pytest

from tests.helpers import remove_scratch_db, scratch_db_path

pytestmark = pytest.mark.slow


@pytest.fixture
def fresh_db_path():
    path = scratch_db_path()
    yield path
    remove_scratch_db(path)


class TestTooNewDatabaseRefusesToOpen:
    def test_a_newer_stamp_raises_a_named_error(self, fresh_db_path):
        from core import db

        old = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            db.qi(
                "UPDATE schema_meta SET value=? WHERE key='version'",
                (str(db.SCHEMA_VERSION + 69),),
            )
            db.close_connection()

            with pytest.raises(db.SchemaVersionTooNew) as exc:
                db.init()
            # The message must name both versions, or the user cannot tell
            # which side to update.
            assert str(db.SCHEMA_VERSION + 69) in str(exc.value)
            assert str(db.SCHEMA_VERSION) in str(exc.value)
        finally:
            db.close_connection()
            db.configure(old)

        # The refused database keeps its stamp: refusal must not "repair".
        c = sqlite3.connect(f"file:{fresh_db_path}?mode=ro", uri=True)
        try:
            row = c.execute(
                "SELECT value FROM schema_meta WHERE key='version'"
            ).fetchone()
            assert int(row[0]) == db.SCHEMA_VERSION + 69
        finally:
            c.close()


class TestUnstampedForeignFileRefusesToOpen:
    def _make_foreign_file(self, path):
        c = sqlite3.connect(path)
        c.execute("CREATE TABLE chats(id INTEGER PRIMARY KEY, oldcol TEXT)")
        c.execute("INSERT INTO chats(oldcol) VALUES('not ours')")
        c.commit()
        c.close()

    def test_tables_without_schema_meta_raise_a_named_error(
        self, fresh_db_path
    ):
        from core import db

        self._make_foreign_file(fresh_db_path)
        old = db.DB
        db.configure(fresh_db_path)
        try:
            with pytest.raises(db.UnstampedDatabaseError) as exc:
                db.init()
            assert "chats" in str(exc.value)
        finally:
            db.close_connection()
            db.configure(old)

    def test_the_refused_file_is_not_touched(self, fresh_db_path):
        from core import db

        self._make_foreign_file(fresh_db_path)
        old = db.DB
        db.configure(fresh_db_path)
        try:
            with pytest.raises(db.UnstampedDatabaseError):
                db.init()
        finally:
            db.close_connection()
            db.configure(old)

        c = sqlite3.connect(f"file:{fresh_db_path}?mode=ro", uri=True)
        try:
            tables = [
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            # No adoption: the engine created nothing, stamped nothing.
            assert tables == ["chats"]
            # Not even the WAL header switch: a refused file comes out as
            # it went in.
            mode = c.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() != "wal"
        finally:
            c.close()

    def test_a_genuinely_empty_file_still_initializes(self, fresh_db_path):
        from core import db

        old = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            row = db.q(
                "SELECT value FROM schema_meta WHERE key='version'", one=True
            )
            assert int(row["value"]) == db.SCHEMA_VERSION
        finally:
            db.close_connection()
            db.configure(old)


class TestAddColumnIdempotenceIsIntrospective:
    def test_the_predicate_reads_the_schema_not_the_error(self, fresh_db_path):
        from core import db

        old = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            c = sqlite3.connect(fresh_db_path)
            c.row_factory = sqlite3.Row
            try:
                assert db._column_addition_already_applied(
                    c, "ALTER TABLE chats ADD COLUMN scenario TEXT"
                )
                assert not db._column_addition_already_applied(
                    c, "ALTER TABLE chats ADD COLUMN never_seen_before TEXT"
                )
                # Non-ADD-COLUMN statements are none of its business.
                assert not db._column_addition_already_applied(
                    c, "CREATE INDEX IF NOT EXISTS idx_x ON chats(name)"
                )
                # A missing table is not "already applied" -- let the real
                # execution produce the real error.
                assert not db._column_addition_already_applied(
                    c, "ALTER TABLE no_such_table ADD COLUMN x TEXT"
                )
            finally:
                c.close()
        finally:
            db.close_connection()
            db.configure(old)

    def test_a_rerun_add_column_is_skipped_and_the_version_advances(
        self, fresh_db_path, monkeypatch
    ):
        from core import db

        old = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            db.qi(
                "UPDATE schema_meta SET value=? WHERE key='version'",
                (str(db.SCHEMA_VERSION - 1),),
            )
            db.close_connection()

            # Only the LAST migration list runs from SCHEMA_VERSION-1; its
            # sole statement targets a column that already exists -- the
            # exact state a crash between the ALTER and the version bump
            # leaves behind.
            patched = [["SELECT 1"]] * (db.SCHEMA_VERSION - 2)
            patched.append(
                ["ALTER TABLE chats ADD COLUMN scenario TEXT NOT NULL DEFAULT ''"]
            )
            monkeypatch.setattr(db, "MIGRATIONS", patched)

            db.init()

            row = db.q(
                "SELECT value FROM schema_meta WHERE key='version'", one=True
            )
            assert int(row["value"]) == db.SCHEMA_VERSION
        finally:
            db.close_connection()
            db.configure(old)

    def test_a_genuinely_failing_statement_still_raises(
        self, fresh_db_path, monkeypatch
    ):
        from core import db

        old = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            db.qi(
                "UPDATE schema_meta SET value=? WHERE key='version'",
                (str(db.SCHEMA_VERSION - 1),),
            )
            db.close_connection()

            patched = [["SELECT 1"]] * (db.SCHEMA_VERSION - 2)
            patched.append(["ALTER TABLE no_such_table ADD COLUMN x TEXT"])
            monkeypatch.setattr(db, "MIGRATIONS", patched)

            with pytest.raises(sqlite3.OperationalError):
                db.init()
        finally:
            db.close_connection()
            db.configure(old)
