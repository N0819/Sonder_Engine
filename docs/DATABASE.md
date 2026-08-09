# Database and State Map

The engine uses SQLite. The schema is defined in `db.py`; access is intentionally lightweight through `q`, `qi`, `qtx`, `transaction`, `wget`, and `wset` (plus the frame-scoped `wget_for_frame`/`wset_for_frame`).

Housekeeping tables not described below: `schema_meta` (the migration version), and `guest_grants` / `host_sessions` (see `guest_access.py` and `auth_routes.py`).

## Resource tables

- `characters`, `personas`: reusable versioned JSON sheets plus original source
  payloads. Their top-level `initial_outfit` is authored starting clothing,
  distinct from stable body appearance in `embodiment.visible` and from the
  mutable story ledger in `world.scene.attire`.
- `lorebooks`, `lore_entries`: canon containers and entries. Two different questions get asked of this table and must not be confused: **ownership** (`chat_id`, what a chat has — what the workspace browser lists via `GET /api/chats/{cid}/lorebooks`) and **reachability** (`memory.chat_lorebook_ids`, what lore retrieval may read — resolved outward from canon plus `chat_lorebooks` attachments through parents/children/links). A chat-owned book with `parent_id` NULL and no attachment row is owned but unreachable: it exists, it is editable, and the pipeline can never read it.
- `lorebook_links`: typed relationships between books.
- `chat_lorebooks`: attachments between chats and reusable or chat-owned books.
- `providers`, `settings`: local model/provider configuration and prompt/runtime settings.
- `lore_gen_jobs`: resumable lorebook-tree generation runs (`importers.generate_lorebook_plan` / `resume_lorebook_plan`). A run is one structure model call plus one call per batch of outlined entries, and each completed unit is written here so an interruption (dropped stream, exhausted provider retries, closed tab, restarted server) costs one unit instead of the whole run. `status` is `running|interrupted|failed|ready|applied|cancelled`; `owner` is a per-process token, so a `running` row from any other process is a crash and reclassifies as an interruption with no staleness timeout. `params` holds the whole request (brief, mode, depth, entry target, flags, and the raised read `timeout`), so a resume reproduces it without the client. Authoring scratch state only — deliberately **not** exported, checkpointed, or branch-remapped, since no lore exists until the plan is applied; rows are pruned to the newest `LORE_GEN_KEEP_PER_BOOK` per book and cascade with the book.

## Runtime fiction tables

- `chats`: root interactive-fiction session.
- `chat_chars`: cast membership, active/dormant status, mutable character
  `state`, and an optional per-story authored `sheet`. A NULL sheet follows the
  reusable `characters.sheet`; a populated sheet overrides it only for that
  story. Never fold the two JSON domains together: card edits may change
  psychology/voice/history/configuration, while current mood, stress, learned
  beliefs, memories, relationships, and bodily condition remain live state.
  `scene.active_cast` is the main effective-sheet read boundary. `state` also
  carries the character's durable spatial memory — `place_graph` (nodes/edges
  with `basis` walked/seen, written by `commit.record_spatial_experience` from
  that character's own position and sight only, bounded by
  `PLACE_GRAPH_NODE_CAP` eviction) beside the windowed `visited_rooms` and the
  legacy `known_exits`/`known_dead_ends` views of it. Deliberate persistence
  decision: no schema, remap, or archive change — checkpoints snapshot/restore
  `state` whole, `chat_archive.py` exports/imports it verbatim, and the branch
  path copies the row; room ids are frame-scoped scene rids preserved as-is by
  all three.
- `chat_char_frames`: per-frame status/state override for a cast member, so one
  character can be dormant in one era and live in another.
- `frames`: the temporal frames themselves. Most `world` keys are frame-scoped
  through this table; cross-frame contracts deliberately are not.
- `chat_personas`, `turn_player_inputs`: multiplayer. Extra personas and their
  per-frame station, and each extra player's per-beat declaration — the primary
  player's declaration lives on `turns`, everyone else's lives here.
- `turns`: the primary player's declaration in sequence, plus the beat's
  `frame_id`.
- `steps`, `variants`: inspectable intermediate pipeline outputs and rerolls.
- `events`: one summarized committed event per turn.
- `memories`, `memory_summaries`: character-owned experience records and
  consolidation. Since **v24**, `memories.valence/arousal` are the resolved
  affect carried into an event and `encoding_valence/encoding_arousal` are the
  resolved post-appraisal affect in which it was encoded; all four follow the
  existing snapshot/archive/portable-bank paths. `memory_summaries` is keyed
  `(chat_id, char_id, scope, end_turn_idx)` since **v23** — one row per
  WINDOW, not one per character. It was `(chat_id, char_id, scope)`, so every
  consolidation overwrote the one row a scope had, which is why the summary
  layer could not be searched: there was nothing to search between. The v23
  migration is a table REBUILD, because SQLite cannot drop a UNIQUE declared
  inline on CREATE TABLE; existing rows copy across unchanged and become each
  character's first window.
- `world`: JSON key/value state for the chat, including the current scene and pipeline caches. Inside the frame-scoped `scene` blob, `positions` is which room each person is in, `stations` their within-room position, and `following` the voluntary durable follower → target travel relations. Following is intention rather than containment: it may persist while separated and never derives a position by itself; Director movement carries it only across ordinary passable travel. `scales` records each body's size relative to its own baseline (absent = normal; not pruned by position, since a size is not a co-location), `contained` says who is being carried by what (a contained body's position is derived from its carrier's, transitively), and `contacts` is a flat list of who is in physical contact with whom and by which body parts — a relation stored once rather than on either body, pruned at every merge by `spatial.normalize_scene_contacts` (contact between two people not in the same room cannot survive, so movement ends a hold deterministically). `attire` is the live per-story clothing state: a card's `initial_outfit` may seed a missing entry at scene creation or first attachment/promotion, but must never reset an entry already changed by story events. Each attire region contains ordered `garments` and optional authored `beneath`; torso additionally permits `beneath_zones:{chest,midriff}`. A garment's optional `covered_zones:{torso:[...]}` is an override listing the zones it still covers while worn; absence means full coverage. An empty torso list means the garment remains worn at the torso but covers neither torso zone. `wearing`, derived `state`, region garment state and zone coverage must be reconciled only through `attire.rederive_entry`/the commit path.
- `checkpoints`: whole-state restoration blobs keyed by chat and turn index.

## Structured world tables

- `world_entities`: normalized projection of the scene's entities, derived at commit (`commit_world_entities(prepared=...)`). Read at runtime only for fixed-point existence checks (`paradox._entity_exists`) and book-anchor alias resolution (`commit._entity_alias_map`). **Which** entities a beat touched comes from the post-dedup diff; **what** they now are comes from the merged scene, and taking the second from the diff too is how this projection drifted: `spatial._merge_entity` sits between the diff and the blob, reading a schema default as silence and refusing a name `schemas._fill_entity_names` derived from the dict key. Writing the raw diff skipped all of it, so a pose-only beat left the blob saying "Blue Police Box"/vehicle and the row saying "Tardis 001"/object — 15 of 480 live rows named literally `Object`, 19 disagreeing with the blob about `name`, 24 about `kind`. A row heals the next time a beat touches that entity; `tools/reproject_world_entities.py` sweeps the ones nothing will touch again (read-only without `--apply`, and it skips an entity whose frames disagree, since `scene` is frame-scoped and this table is not).
- `world_placements`: DECOMMISSIONED (Phase 3a) — nothing inserts or reads it; kept only so old snapshots/exports restore. The two surviving runtime writers are deletes (legacy cleanup in `commit_world_entities`, and `paradox.py`). Positions live solely in the frame-scoped `scene.positions`.
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
- `wget_for_frame(chat_id, key, frame_id, default)` / `wset_for_frame(...)`: the
  same, addressed to one temporal frame. Most `world` keys are frame-scoped —
  use these when the era matters, which for live world state it almost always
  does.

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

### `memory_vectors` — the one table that is append-only

Embedding vectors are stored once, addressed by `sha1(char_id, normalised
content)` (`memory.vector_address`). Checkpoints reference that address rather
than carrying the payload, which is what keeps them small: a checkpoint is a
full pre-turn snapshot, so an inline vector was re-stored on every turn for the
life of the story.

Two rules follow, and neither is optional:

* **Never garbage-collect it.** A checkpoint written before a memory was
  deleted still references that memory's vector, and a rollback that cannot
  restore one is a worse failure than a few kilobytes of orphaned rows.
* **A portable archive must carry the vectors its checkpoints reference.**
  `chat_archive` exports the deduped set under `memory_vectors` and restores it
  before the checkpoints that point at it; the archive's own top-level
  `memories` keep their vectors INLINE, because the importing database has no
  store to resolve against. `dump_chat_memories(inline_vectors=...)` is that
  distinction.

`tools`-free conversion of an existing database lives in
`checkpoints.compact_checkpoints`, exposed in the UI under Software updates. It
verifies each story against its original before writing anything and refuses
any story it cannot prove lossless.

Per-story card overrides are preserved by portable chat archives and branches.
They are intentionally not rolled back by turn checkpoints: like other explicit
authoring configuration, editing a card is not an event inside the beat being
rerolled.

## Runtime database selection

`DB` defaults to `engine.db` and can be overridden with `ENGINE_DB` before importing `db.py`. Tests use `db.configure(path)` to switch connections safely.
