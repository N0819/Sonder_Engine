"""A one-shot data pass is stamped done only when it is done.

`core.db.init` runs three data passes on the file that crosses their schema
version -- chat copies become overlays (v39), rooms get regions (v36), memory
vectors are filed (v38) -- each gated on the version read BEFORE the chain.
They used to run AFTER `executescript(LATE_SCHEMA)`, which in legacy
transaction mode commits the transaction holding every version stamp. So a
pass that raised, or a first start the host killed during the vector
backfill, left the file stamped at the new version with the pass never run,
and the next start skipped it forever (audit 2026-11-01, persistence F5:
"stamped version after the failed pass: 45").

The rule: the stamps and the passes commit together, so a pass that does not
finish leaves the file at the version that asks for it again.
"""

from __future__ import annotations

import sqlite3

import pytest


def _stamped(db_path):
    c = sqlite3.connect(db_path)
    try:
        return int(c.execute(
            "SELECT value FROM schema_meta WHERE key='version'").fetchone()[0])
    finally:
        c.close()


def _restamp(db_path, version):
    c = sqlite3.connect(db_path)
    try:
        c.execute("UPDATE schema_meta SET value=? WHERE key='version'",
                  (str(version),))
        c.commit()
    finally:
        c.close()


def test_a_failed_overlay_pass_leaves_the_file_asking_for_it(temp_db, monkeypatch):
    from core import db

    _restamp(db.DB, 38)
    real = db._migrate_chat_copies_to_overlays

    def fails(c):
        raise RuntimeError("the pass did not finish")
    monkeypatch.setattr(db, "_migrate_chat_copies_to_overlays", fails)
    with pytest.raises(RuntimeError):
        db.init()
    assert _stamped(db.DB) == 38, "a pass that did not run is not stamped done"

    ran = []

    def runs(c):
        ran.append(True)
        return real(c)
    monkeypatch.setattr(db, "_migrate_chat_copies_to_overlays", runs)
    db.init()
    assert ran == [True], "the next start runs the pass the failed one left"
    assert _stamped(db.DB) == db.SCHEMA_VERSION


def test_a_failed_region_pass_leaves_the_file_asking_for_it(temp_db, monkeypatch):
    from core import db
    from world import regions

    _restamp(db.DB, 35)

    def fails(c):
        raise RuntimeError("killed during the region pass")
    monkeypatch.setattr(regions, "backfill_regions", fails)
    with pytest.raises(RuntimeError):
        db.init()
    assert _stamped(db.DB) == 35

    monkeypatch.undo()
    db.init()
    assert _stamped(db.DB) == db.SCHEMA_VERSION


def test_a_clean_start_on_a_current_file_runs_no_pass(temp_db, monkeypatch):
    from core import db

    def must_not_run(c):
        raise AssertionError("a current file has nothing to convert")
    monkeypatch.setattr(db, "_migrate_chat_copies_to_overlays", must_not_run)
    db.init()
    assert _stamped(db.DB) == db.SCHEMA_VERSION
