# Tests

Run from the repository root:

```bash
make test-fast     # pure/unit contracts; no database-backed slow tests
make test-full     # every Python regression test
make test-browser  # optional real Chromium behavior tests
make check         # compile, regenerate/verify code map, structure, full suite
```

`make test` is an alias for `make test-full`. See `docs/TESTING.md` for
dependency installation, constraints, and CI policy.

The shared `temp_db` fixture creates a fresh SQLite database, calls
`db.configure`, initializes the schema, closes the thread-local connection, and
removes WAL/SHM files afterward. Tests requesting it are marked `slow` during
collection and run in the full tier. Fast-tier tests must not depend on
`engine.db` or on another test having initialized settings; use pure constants
or stub prompt/settings lookup when the database is outside the invariant under
test.

Test files are organized by invariant or subsystem rather than mirroring every source file. Prefer a focused regression test that captures the earliest broken boundary.

Character-psychology coverage is split deliberately: `test_psychology_runtime`
checks bounded state mechanics, `test_character_psychology_fill` checks
non-destructive legacy-card completion, and the perception/self-knowledge tests
attack the new information paths with hidden-intent and other-body markers.
