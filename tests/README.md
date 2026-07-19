# Tests

Run from the repository root:

```bash
pytest -q
```

The shared `temp_db` fixture creates a fresh SQLite database, calls `db.configure`, initializes the schema, closes the thread-local connection, and removes WAL/SHM files afterward.

Test files are organized by invariant or subsystem rather than mirroring every source file. Prefer a focused regression test that captures the earliest broken boundary.
