"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import os
import tempfile

import pytest


def pytest_collection_modifyitems(items):
    """Mark database-backed tests ``slow``.

    Kept for CI's matrix-breadth job (``make test-fast``), NOT as the tier a
    developer should run before considering a change done -- see the fixture
    below for why that split no longer means what it used to.
    """

    for item in items:
        if "temp_db" in item.fixturenames:
            item.add_marker(pytest.mark.slow)


def _fast_tmp_dir():
    """A RAM-backed directory for test databases, where the platform has one.

    ``db.init()`` is fsync-bound, not compute-bound: ``executescript(SCHEMA)``
    auto-commits ~117 DDL statements (53 tables, 64 indexes, FTS5 virtuals,
    triggers) against a brand-new file, and pays a flush for each. That single
    call was the dominant cost of the whole suite -- 159 of 252 test files
    request ``temp_db``, and their test BODIES run in 0.02--0.10s against a
    setup measured at 0.2s idle and 1.2--1.6s on a loaded checkout.

    Measured here, 13 database-backed tests: 2.93s on disk, 0.61s on tmpfs.
    Nothing about the database changes -- same schema, same WAL, same
    isolation, same per-test file. Only the storage backing moves, so a test
    cannot tell the difference; the suite just stops waiting on the platter.

    Returns None where no tmpfs exists (macOS, Windows), which falls back to
    tempfile's own default. Correct everywhere, fast where it can be.
    ``ENGINE_TEST_TMPDIR`` overrides, for a host where /dev/shm is too small.
    """
    override = os.environ.get("ENGINE_TEST_TMPDIR")
    if override:
        return override
    if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK):
        return "/dev/shm"
    return None


_TMP_DIR = _fast_tmp_dir()


@pytest.fixture
def temp_db():
    """Create and configure a temporary test database."""
    fd, db_path = tempfile.mkstemp(
        suffix=".db", dir=_TMP_DIR
    )
    os.close(fd)
    os.remove(db_path)

    import db

    old_path = db.DB
    db.configure(db_path)
    db.init()

    try:
        yield db
    finally:
        db.close_connection()
        db.configure(old_path)

        for path in (
            db_path,
            db_path + "-wal",
            db_path + "-shm",
        ):
            if os.path.exists(path):
                os.remove(path)

@pytest.fixture
def sample_scene():
    """Return a scene with several rooms and characters."""
    return {
        "location": "Old Manor",
        "time": "evening",
        "rooms": {
            "kitchen": {
                "name": "Kitchen",
                "desc": "A rustic kitchen with a heavy oak table.",
                "notes": "Smell of fresh bread. Warm fireplace.",
                "adjacent": [
                    {
                        "to": "hallway",
                        "barrier": "open",
                        "distance": "near",
                    },
                    {
                        "to": "cellar",
                        "barrier": "closed_door",
                        "distance": "near",
                    },
                ],
            },
            "hallway": {
                "name": "Hallway",
                "desc": "A long, dim hallway.",
                "notes": "Cold draft. Dusty portraits.",
                "adjacent": [
                    {
                        "to": "kitchen",
                        "barrier": "open",
                        "distance": "near",
                    },
                    {
                        "to": "study",
                        "barrier": "closed_door",
                        "distance": "near",
                    },
                ],
            },
            "study": {
                "name": "Study",
                "desc": "A cluttered study filled with books.",
                "notes": "Smell of old paper. Flickering candle.",
                "adjacent": [
                    {
                        "to": "hallway",
                        "barrier": "closed_door",
                        "distance": "near",
                    },
                ],
            },
            "cellar": {
                "name": "Cellar",
                "desc": "A dark, damp cellar.",
                "notes": "Cold and musty. Sound of dripping water.",
                "adjacent": [
                    {
                        "to": "kitchen",
                        "barrier": "closed_door",
                        "distance": "near",
                    },
                ],
            },
            "garden": {
                "name": "Garden",
                "desc": "An overgrown garden.",
                "notes": "Night air. Rustling leaves.",
                "adjacent": [],
            },
        },
        "positions": {
            "Alice": "kitchen",
            "Bob": "hallway",
            "Charlie": "study",
            "Diana": "cellar",
        },
        "entities": {},
        "overlays": {},
        "attire": {},
    }
