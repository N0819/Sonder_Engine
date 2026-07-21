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

- `world_entities`: normalized projection of the scene's entities, derived at commit from the same post-dedup diff that builds the scene blob (`commit_world_entities(prepared=...)`). Read at runtime only for fixed-point existence checks (`paradox._entity_exists`) and book-anchor alias resolution (`commit._entity_alias_map`).
- `world_placements`: DECOMMISSIONED (Phase 3a) — no runtime writer or reader; kept only so old snapshots/exports restore. Positions live solely in the frame-scoped `scene.positions`.
- `world_events`, `world_conditions`, `scheduled_events`: objective event timeline, active conditions, and future events (`transit_arrival`, `news_arrival`). `scheduled_events` is keyed `(chat_id, event_id)` since v16 (same repartition v14 applied to entities/conditions).
- `room_registry`: the sole cross-frame ledger of room identity/existence-over-time/retirement, keyed `(chat_id, room_uid)` and scoped to an owning lorebook. It is a deterministic projection of every scene write: `commit_scene` maintains it in the same commit domain, and the manual world editor (`world_put`) reconciles it through `commit.sync_room_registry_with_scene`. Rooms and lorebooks are retired (`retired_turn_id`), never deleted, on removal/destruction.
- `fiction_worlds`, `fiction_locations`, `transit_edges`: DEPRECATED dead macro schema (nothing in the runtime pipeline reads or writes them; kept only so old imports restore — removal is planned).

Authority model (Phase 3a): the frame-scoped `world.scene` blob is the single runtime source of truth for LIVE rooms/adjacency/positions/entity state — every spatial reader reads it and nothing else. The normalized tables are derived projections of scene commits and must never be treated as a second authority over live state; `room_registry` alone answers the cross-frame question "which rooms have ever existed here, and which are retired" (what multi-book destruction cascades mutate). A room retired in one frame's commit may legitimately still be live in a sibling (e.g. past-era) frame's blob; that frame's next commit re-registers it (upsert revives).

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
