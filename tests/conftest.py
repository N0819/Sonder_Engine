"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import json
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


def _redirect_default_database():
    """Point `db.DB` at a scratch file NOW -- at conftest import, before any
    test module is imported.

    A session-scoped autouse fixture is too late, and that is not a nicety.
    pytest imports every test module during COLLECTION, and a module-level
    import can reach the database before any fixture has run: `importers`
    resolves `REINT_CHAR_SYS` through `__getattr__` -> `get_prompt()` ->
    `active_preset()` -> `get_setting()` -> `db.q()`. On a fresh checkout with
    no `engine.db` that raises `no such table: settings` and collection dies
    (`test_character_import_drives.py`, `test_extra_parts_authoring.py`,
    `test_initial_outfit.py`); on a developer's machine it does something
    worse, and quietly -- it OPENS the live `engine.db`, which is the one
    outcome the redirect exists to prevent.

    The fixture below still runs, and still owns teardown. This only moves the
    moment the default stops being `engine.db` to the earliest one available.
    """
    import db

    fd, path = tempfile.mkstemp(suffix=".db", dir=_TMP_DIR)
    os.close(fd)
    os.remove(path)
    db.configure(path)
    db.init()
    return path


#: Done at import, not at fixture time. See above.
_SESSION_DB = _redirect_default_database()


@pytest.fixture(scope="session", autouse=True)
def _never_the_real_database():
    """Own the scratch database `_redirect_default_database` already installed.

    The redirect itself happens at import (a fixture runs after collection,
    which is already too late -- see that function). What remains here is the
    part a fixture is actually for: keeping it configured for the session and
    removing it afterwards.

    A test that asks for `temp_db` was always isolated. A test that never asks
    for one and still reaches `db.q` was not: `db.DB` defaults to `engine.db`,
    so it read -- and could write -- the developer's live stories, provider
    rows and API keys.

    This is not hypothetical. Three prompt-cache tests passed or failed
    depending on whether a checkbox in API Connections happened to be ticked,
    because they read a real provider row out of the working copy's own
    database. The failure looked exactly like a code regression and was a
    setting; the suite is documented as offline with no network and no model,
    and it was reading live state.

    Session-scoped and initialized once, so a stray write lands somewhere
    disposable instead of in a story someone is playing. `temp_db` still
    swaps in its own file per test and restores this one afterwards.
    """
    import db

    path = _SESSION_DB
    # A module imported during collection may have opened it already; keep the
    # same file rather than swapping underneath anything that did.
    if db.DB != path:
        db.configure(path)
        db.init()
    try:
        yield path
    finally:
        db.close_connection()
        for leftover in (path, path + "-wal", path + "-shm"):
            if os.path.exists(leftover):
                os.remove(leftover)


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

def fanout_resolve_agent(output, *, per_step=None, calls=None):
    """A fake `agents.director._agent_json` that serves a whole-beat resolve
    output THROUGH the specialist fan-out.

    The Director's delegated channels are answered by their owners: a
    specialist's reply owns the channels it was granted, so a fixture that
    hands the prose author a complete `state_diff` has those channels
    replaced by whatever each specialist said -- which, for a fake that
    returns one shape to every call, is nothing. Position diffs vanished,
    room edits vanished, and a test about the movement backstop failed on a
    KeyError that had nothing to do with movement.

    So this slices the output the way the engine does. The prose author gets
    it verbatim; each specialist gets its own channels lifted out of
    `state_diff` to the TOP level, which is the shape a specialist emits.
    That keeps a fixture free to say "the Director decided X" without also
    having to say which hand carries it.

    `per_step` overrides any step key outright; `calls` collects
    (step_key, payload) when a test wants to count.
    """
    from agents.director import SPECIALISTS

    diff = (output or {}).get("state_diff") or {}
    sliced = {}
    for spec in SPECIALISTS.values():
        patch = {ch: diff[ch] for ch in spec["channels"] if ch in diff}
        if patch:
            sliced[spec["step_key"]] = patch
    canned = {**sliced, **(per_step or {})}

    def fake(role, step_key, system, payload, **kw):
        if calls is not None:
            calls.append((step_key, payload))
        if step_key in canned:
            return json.loads(json.dumps(canned[step_key]))
        if step_key == "director_resolve":
            return json.loads(json.dumps(output or {}))
        return {}
    return fake


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


@pytest.fixture(autouse=True)
def _no_learned_rate_limit_between_tests():
    """Reset the adaptive embedding pacer around every test.

    `providers._EMBED_PACE` is process-global on purpose — it is one engine
    learning one provider's ceiling, and it must outlive any single call. In a
    test suite that makes it a leak with teeth: a test that scripts a 429 to
    check the retry teaches the pacer a two-second interval, the pacer is
    still holding it when the NEXT test runs, and every later test that
    reaches a real `time.sleep` pays for a rate limit that was fictional.
    Measured before this fixture existed: the full suite went from 65 seconds
    to over ten minutes, sleeping, with nothing failing.

    Reset on the way IN as well as out, so a test is protected from whatever
    ran before it even if that test predates this file.
    """
    import providers
    import memory
    providers._EMBED_PACE.update({"interval": 0.0, "next_at": 0.0})
    providers._COALESCE_QUEUE[:] = []
    providers._COALESCE_INFLIGHT = False
    for queued in memory._REPAIR_PENDING.values():
        queued.clear()
    yield
    providers._EMBED_PACE.update({"interval": 0.0, "next_at": 0.0})
    for queued in memory._REPAIR_PENDING.values():
        queued.clear()
