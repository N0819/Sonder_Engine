# Database and State Map

The engine uses SQLite. The schema is defined in `db.py`; access is intentionally lightweight through `q`, `qi`, `qtx`, `transaction`, `wget`, and `wset`.

## Resource tables

- `characters`, `personas`: reusable versioned JSON sheets plus original source payloads.
- `lorebooks`, `lore_entries`: canon containers and entries.
- `lorebook_links`: typed relationships between books.
- `chat_lorebooks`: attachments between chats and reusable or chat-owned books.
- `providers`, `settings`: local model/provider configuration and prompt/runtime settings.

## Runtime fiction tables

- `chats`: root interactive-fiction session.
- `chat_chars`: cast membership, active/dormant status, and mutable character state.
- `turns`: player declarations in sequence.
- `steps`, `variants`: inspectable intermediate pipeline outputs and rerolls.
- `events`: one summarized committed event per turn.
- `memories`, `memory_summaries`: character-owned experience records and consolidation.
- `world`: JSON key/value state for the chat, including the current scene and pipeline caches.
- `checkpoints`: whole-state restoration blobs keyed by chat and turn index.

## Structured world tables

- `fiction_worlds`, `fiction_locations`, `transit_edges`: world and location hierarchy.
- `world_entities`, `world_placements`: persistent entities and containment/placement.
- `world_events`, `world_conditions`, `scheduled_events`: objective event timeline, active conditions, and future events.

The structured-world model is only partially integrated. Some physical truth still lives in JSON under the `world` table. Treat the scene dictionary and normalized tables as overlapping representations until the architecture is consolidated.

## Write helpers

- `q(sql, args, one=False)`: read rows.
- `qi(sql, args)`: write and commit immediately unless already inside a transaction.
- `transaction()`: outer `BEGIN IMMEDIATE`; nested calls use savepoints.
- `qtx(sql, args)`: write only inside `transaction()`.
- `wget(chat_id, key, default)`: decode a JSON value from `world`.
- `wset(chat_id, key, value)`: JSON upsert into `world`.

Use `qtx` for a multi-statement invariant that must roll back together. Nested domain transactions become savepoints. `commit_all` supplies one outer transaction for all primary turn effects, so any exception rolls the complete turn back. Do not perform provider or embedding calls while a write transaction is open.

## Schema-change checklist

A durable field or table change is incomplete until all applicable paths are updated:

1. `SCHEMA` and `SCHEMA_VERSION`/migration logic in `db.py`.
2. Creation/default behavior.
3. Read and commit code.
4. Export/import payloads.
5. Checkpoint snapshot and restore.
6. Branch/clone ID remapping in `app.py` when IDs are embedded.
7. Cleanup behavior under foreign keys.
8. Regression tests using the temporary database fixture.

## Runtime database selection

`DB` defaults to `engine.db` and can be overridden with `ENGINE_DB` before importing `db.py`. Tests use `db.configure(path)` to switch connections safely.
