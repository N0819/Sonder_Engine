"""MASTER-046 / MASTER-020: a database built fresh by ``db.init()`` must be
structurally identical to one brought up through the migration chain.

``init()`` stamps a fresh file straight to SCHEMA_VERSION (deliberate — see
tests/test_fable_audit_migrations.py), which means anything that exists ONLY
inside MIGRATIONS never reaches a fresh install. Measured before the fix:
a fresh database had ZERO triggers while the owner's migrated engine.db had
all six FTS triggers (lore_ai/ad/au, memories_ai/ad/au, v4->v5) plus
idx_lorebooks_anchor (v9->v10). The live consequence was that
``mind/memory.py``'s ``_kw_scores("lore_fts", ...)`` — the 0.35 keyword term
of search_lore — returned {} forever on every database created since the
fresh-path change: lore ranked on the vector term alone, silently.

The equality test here is the guard that matters: it holds the CLASS (any
future migration-only object), not the instance.
"""

from __future__ import annotations

import re
import sqlite3

import pytest

from tests.helpers import remove_scratch_db, scratch_db_path

#: Builds real databases via db.init(); fsync-bound like the other
#: migration tests, so it belongs to the slow marker with them.
pytestmark = pytest.mark.slow


@pytest.fixture
def fresh_db_path():
    path = scratch_db_path()
    yield path
    remove_scratch_db(path)


@pytest.fixture
def second_db_path():
    path = scratch_db_path()
    yield path
    remove_scratch_db(path)


def _build_fresh(db, path):
    old = db.DB
    db.configure(path)
    try:
        db.init()
    finally:
        db.close_connection()
        db.configure(old)


def _build_migrated(db, path):
    """A database that takes the MIGRATION path: current SCHEMA on disk,
    version stamped to 1, then init() walks every migration list. All the
    rebuild/backfill statements no-op on empty tables — this is exactly what
    the pre-fix init() did for every fresh install, so it is a faithful stand-
    in for 'a database that has run the whole chain'."""
    c = sqlite3.connect(path)
    c.executescript(db.SCHEMA)
    c.execute(
        "INSERT INTO schema_meta(key,value) VALUES('version','1') "
        "ON CONFLICT(key) DO UPDATE SET value='1'"
    )
    c.commit()
    c.close()
    old = db.DB
    db.configure(path)
    try:
        db.init()
    finally:
        db.close_connection()
        db.configure(old)


def _norm_sql(sql):
    """Whitespace-insensitive, IF NOT EXISTS-insensitive DDL comparison."""
    if sql is None:
        return None
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"\s+", " ", sql).strip()
    sql = re.sub(r"(?i)\bIF NOT EXISTS\b ?", "", sql)
    return sql


def _schema_inventory(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = c.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        objects = {(t, n): (tbl, _norm_sql(sql)) for t, n, tbl, sql in rows}
        columns = {}
        for t, n in objects:
            if t == "table":
                cols = c.execute(f'PRAGMA table_xinfo("{n}")').fetchall()
                columns[n] = {col[1] for col in cols}
        return objects, columns
    finally:
        c.close()


class TestFreshEqualsMigrated:
    def test_fresh_and_migrated_schemas_are_identical(
        self, fresh_db_path, second_db_path
    ):
        from core import db

        _build_fresh(db, fresh_db_path)
        _build_migrated(db, second_db_path)

        fresh_objects, fresh_columns = _schema_inventory(fresh_db_path)
        migrated_objects, migrated_columns = _schema_inventory(second_db_path)

        only_migrated = sorted(set(migrated_objects) - set(fresh_objects))
        only_fresh = sorted(set(fresh_objects) - set(migrated_objects))
        assert only_migrated == [], (
            "objects the migration chain creates but a fresh init() never "
            f"does: {only_migrated}"
        )
        assert only_fresh == [], (
            "objects a fresh init() creates but the migration chain loses: "
            f"{only_fresh}"
        )

        # Same column set per table (catches an ADD COLUMN missing from
        # SCHEMA or vice versa without being fragile about column order).
        for table in sorted(fresh_columns):
            assert fresh_columns[table] == migrated_columns[table], (
                f"table {table} differs: fresh-only "
                f"{fresh_columns[table] - migrated_columns[table]}, "
                f"migrated-only {migrated_columns[table] - fresh_columns[table]}"
            )

        # Indexes and triggers must agree on their actual DDL, not just
        # exist under the same name.
        for key, (tbl, sql) in sorted(fresh_objects.items()):
            if key[0] in ("index", "trigger") and sql is not None:
                m_tbl, m_sql = migrated_objects[key]
                assert (tbl, sql) == (m_tbl, m_sql), (
                    f"{key[0]} {key[1]} differs between fresh and migrated"
                )


class TestFreshDatabaseFtsIsLive:
    TRIGGERS = ("lore_ai", "lore_ad", "lore_au",
                "memories_ai", "memories_ad", "memories_au")

    def test_a_fresh_database_has_the_six_fts_triggers(self, fresh_db_path):
        from core import db

        _build_fresh(db, fresh_db_path)
        c = sqlite3.connect(f"file:{fresh_db_path}?mode=ro", uri=True)
        try:
            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'"
                )
            }
        finally:
            c.close()
        missing = [t for t in self.TRIGGERS if t not in names]
        assert missing == [], f"fresh database is missing triggers: {missing}"

    def test_lore_fts_indexes_new_lore_on_a_fresh_database(self, fresh_db_path):
        """The real reader: mind/memory.py's _kw_scores('lore_fts', query)
        supplies the 0.35 keyword term of search_lore. Without the insert
        trigger this MATCH returns nothing, forever, for every entry."""
        from core import db

        old = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            book = db.qi(
                "INSERT INTO lorebooks(name) VALUES(?)",
                ("Bestiary",),
            )
            db.qi(
                "INSERT INTO lore_entries(lorebook_id,keys,content) "
                "VALUES(?,?,?)",
                (book, "dragon", "A dragon sleeps under the mountain."),
            )
            hits = db.q(
                "SELECT rowid FROM lore_fts WHERE lore_fts MATCH ?",
                ("dragon",),
            )
            assert hits, (
                "lore_fts saw nothing: the insert trigger is missing, so "
                "search_lore's keyword term scores 0.0 for every entry"
            )
        finally:
            db.close_connection()
            db.configure(old)

    def test_an_existing_triggerless_database_is_rebuilt_on_upgrade(
        self, fresh_db_path
    ):
        """A database created by the broken fresh path has no triggers and an
        empty lore_fts despite populated lore_entries. Opening it again must
        both re-create the triggers (SCHEMA, IF NOT EXISTS) and rebuild the
        FTS content so pre-existing entries become searchable."""
        from core import db

        old = db.DB
        db.configure(fresh_db_path)
        try:
            db.init()
            book = db.qi(
                "INSERT INTO lorebooks(name) VALUES(?)",
                ("Bestiary",),
            )
            db.qi(
                "INSERT INTO lore_entries(lorebook_id,keys,content) "
                "VALUES(?,?,?)",
                (book, "dragon", "A dragon sleeps under the mountain."),
            )
            # Recreate the broken-era state: no triggers, index never
            # populated, and the version stamped so the REPAIR MIGRATION runs.
            #
            # 30 literally, not `SCHEMA_VERSION - 1`. The repair is the
            # v30 -> v31 step, and deriving the stamp from whatever is newest
            # only worked while that step WAS the newest. The first migration
            # added after it silently stopped this test from running the
            # repair at all -- and the symptom was not a clear assertion
            # failure but `database disk image is malformed`, thrown later and
            # somewhere else, because a live trigger over a deleted
            # external-content index corrupts it on the next UPDATE. Found
            # when v31 -> v32 was added.
            _PRE_REPAIR_VERSION = 30
            assert db.SCHEMA_VERSION > _PRE_REPAIR_VERSION
            for trig in self.TRIGGERS:
                db.qi(f"DROP TRIGGER IF EXISTS {trig}")
            db.qi("INSERT INTO lore_fts(lore_fts) VALUES('delete-all')")
            db.qi(
                "UPDATE schema_meta SET value=? WHERE key='version'",
                (str(_PRE_REPAIR_VERSION),),
            )
            db.close_connection()

            db.init()

            hits = db.q(
                "SELECT rowid FROM lore_fts WHERE lore_fts MATCH ?",
                ("dragon",),
            )
            assert hits, (
                "reopening a triggerless database did not rebuild lore_fts; "
                "entries written during the broken era stay unsearchable"
            )
        finally:
            db.close_connection()
            db.configure(old)


class TestFreshDatabaseIndexes:
    #: idx_lorebooks_anchor is MASTER-046's index half (v9->v10, deliberately
    #: kept out of SCHEMA because SCHEMA runs before migrations); the two
    #: guest_grants hash indexes are MASTER-020 (guest auth was a full table
    #: scan per request without them).
    EXPECTED = (
        "idx_lorebooks_anchor",
        "idx_guest_grants_code_hash",
        "idx_guest_grants_token_hash",
    )

    def test_a_fresh_database_has_every_expected_index(self, fresh_db_path):
        from core import db

        _build_fresh(db, fresh_db_path)
        c = sqlite3.connect(f"file:{fresh_db_path}?mode=ro", uri=True)
        try:
            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
        finally:
            c.close()
        missing = [i for i in self.EXPECTED if i not in names]
        assert missing == [], f"fresh database is missing indexes: {missing}"

    def test_a_migrated_database_has_every_expected_index(
        self, fresh_db_path
    ):
        from core import db

        _build_migrated(db, fresh_db_path)
        c = sqlite3.connect(f"file:{fresh_db_path}?mode=ro", uri=True)
        try:
            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
        finally:
            c.close()
        missing = [i for i in self.EXPECTED if i not in names]
        assert missing == [], f"migrated database is missing indexes: {missing}"
