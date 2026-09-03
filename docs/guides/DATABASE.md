# Database and State Map

The engine uses SQLite. The schema is defined in `core/db.py`; access is intentionally lightweight through `q`, `qi`, `qtx`, `transaction`, `wget`, and `wset` (plus the frame-scoped `wget_for_frame`/`wset_for_frame`).

Housekeeping tables not described below: `schema_meta` (the migration version), and `guest_grants` / `host_sessions` (see `web/guest_access.py` and `web/auth_routes.py`).

## Resource tables

- `characters`, `personas`: reusable versioned JSON sheets plus original source
  payloads. Their top-level `initial_outfit` is authored starting clothing,
  distinct from stable body appearance in `embodiment.visible` and from the
  mutable story ledger in `world.scene.attire`.
- `lorebooks`, `lore_entries`: canon containers and entries. Two different questions get asked of this table and must not be confused: **ownership** (`chat_id`, what a chat has — what the workspace browser lists via `GET /api/chats/{cid}/lorebooks`) and **reachability** (`memory.chat_lorebook_ids`, what lore retrieval may read — resolved outward from canon plus `chat_lorebooks` attachments through parents/children/links). A chat-owned book with `parent_id` NULL and no attachment row is owned but unreachable: it exists, it is editable, and the pipeline can never read it. A third question is asked of the entries themselves: **who may KNOW one.** `mind.memory_lore_entries.knowledge_for_character` answers it on three orthogonal axes — depth (`knowledge_tag`: `common`/`scholarly`/`esoteric`, matched against the sheet's `knowledge.access_tags`), compartment (`lore_entries.circles`, inheriting `lorebooks.default_circles`, matched against the sheet's `knowledge.circles`) and range (`knowledge_range` + `knowledge_locations`). Reachability is a PROPERTY, not a category: an entry with an explicit depth tag reaches minds whatever it is filed as, and an entry with none is Director-only retrieval material (`agents.common.lore_for`). It was a category until 2026-08-22, which made 25 of 2,671 entries (0.9%) the only ones any mind could hold while 974 tagged entries in other categories reached nobody. `lore_entries.circles` is NULLABLE on purpose — NULL inherits the book, `[]` is a deliberate "this one is public", and a `NOT NULL DEFAULT '[]'` would make the second unwritable. Compartments must survive export/checkpoint/branch or an archive republishes a clandestine organisation's existence to everybody, so both columns ride `dump_lorebook`/`restore_lorebook` and the two `lorebooks` INSERTs in `persist/chat_archive.py`.
- `lorebook_links`: typed relationships between books.
- `chat_lorebooks`: attachments between chats and reusable or chat-owned books.
- `providers`, `settings`: local model/provider configuration and prompt/runtime settings. `settings.ui_language` is the host-wide interface language (absent means `en`), intentionally separate from each chat's `world.story_language`; changing chrome must not rewrite a story's authored language, and changing a story must not relabel the host UI.
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
  `state` whole, `persist/chat_archive.py` exports/imports it verbatim, and the branch
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
  character's first window. Since **v34**, `memories.encoded_at_seconds` is the
  simulation clock's reading, in seconds of fiction time, at the moment the row
  was written — the unit every delivered "how long ago" is named in
  (`mind/memory_time.py`). STORED rather than derived: an age computed as
  `(now_turn - turn_idx) * (now_elapsed / now_turn)` reads off a moving
  denominator, so re-running one turn with a different declared duration
  silently re-ages the whole bank and a branch reads the same memory at two
  ages. A stored reading is local and rolls back with its own row. NULL means
  "no reading" and never zero, because zero is a real opening-of-the-story
  value; rows with a NULL `turn_idx` (prestory seeds, imported banks) stay NULL
  and keep qualitative phrasing. The v34 backfill charges existing rows
  `turn_idx * world.mechanics.UNCLAIMED_BEAT_SECONDS` — the rate the live clock
  already charges a beat that claimed no duration — and is the one estimate in
  the column; `mind/memory_time.window_clock_readings` is the named seam a
  stored per-turn clock history would replace it at.
- `world`: JSON key/value state for the chat, including the current scene and pipeline caches. The chat-global `story_language` key is an author setting naming an installed, story-capable language pack; absent means `en`. It is exported and branched with the world and preserved across checkpoint restore, because rerolling a beat must not undo the reader's language selection. Inside the frame-scoped `scene` blob, `positions` is which room each person is in, `stations` their within-room position, and `following` the voluntary durable follower → target travel relations. Following is intention rather than containment: it may persist while separated and never derives a position by itself; Director movement carries it only across ordinary passable travel. `scales` records each body's size relative to its own baseline (absent = normal; not pruned by position, since a size is not a co-location), `contained` says who is being carried by what (a contained body's position is derived from its carrier's, transitively), and `contacts` is a flat list of who is in physical contact with whom and by which body parts — a relation stored once rather than on either body, pruned at every merge by `spatial.normalize_scene_contacts` (contact between two people not in the same room cannot survive, so movement ends a hold deterministically). Each contact has independent `relation: surface|interior` topology and `motion: settled|moving` kinematics; old rows derive both from `manner` and `detail`, and an interior relation must be explicitly removed before the same endpoints become surface contact. Interior records may also carry `target_interior`, the enclosing passage/chamber/material, separately from `target_part`, the exact boundary or endpoint currently touched. An `op:cross` is validated against a standing `crossed_target_part`; it persists only the downstream `target_interior` and current `target_part`, not the crossed boundary. `attire` is the live per-story clothing state: a card's `initial_outfit` may seed a missing entry at scene creation or first attachment/promotion, but must never reset an entry already changed by story events. Each attire region contains ordered `garments` and optional authored `beneath`; torso additionally permits `beneath_zones:{chest,midriff}`. A garment's optional `covered_zones:{torso:[...]}` is an override listing the zones it still covers while worn; absence means full coverage. An empty torso list means the garment remains worn at the torso but covers neither torso zone. `wearing`, derived `state`, region garment state and zone coverage must be reconciled only through `attire.rederive_entry`/the commit path.

  character's first window.
- `world`: JSON key/value state for the chat, including the current scene and pipeline caches. The chat-global `story_language` key is an author setting naming an installed, story-capable language pack; absent means `en`. It is exported and branched with the world and preserved across checkpoint restore, because rerolling a beat must not undo the reader's language selection. Inside the frame-scoped `scene` blob, `time_of_day` is the story's STANDING time of day (a free-text label — "dusk", "08:42:15 AM" — written by the opening or by a beat that explicitly declares a new one, and restated on `simulation_clock.display` so the two cannot drift; a beat's PASSAGE PHRASE is never written to either, and `db.init` recovers the field for stories written before it existed from their own persisted `director_establish` variant; since the day cycle landed the label is also DERIVED: the clock record carries `anchor_hour` (the hour of the day at elapsed zero, set from the first readable label), `day_length_hours` (the author's `style_guide.day_length_hours` dial, default 24), and the derived `hour_of_day` and `phase`; the scene carries `day_phase`; and `time_of_day` becomes the phase's own name once the clock has left the phase the last declared label named. All of it rides the `world` row, so archive, checkpoint, branch and frame split/merge carry it without their own handling; a story whose opening named no readable time has no anchor and none of these keys), `positions` is which room each person is in, `stations` their within-room position, and `following` the voluntary durable follower → target travel relations. Following is intention rather than containment: it may persist while separated and never derives a position by itself; Director movement carries it only across ordinary passable travel. `scales` records each body's size relative to its own baseline (absent = normal; not pruned by position, since a size is not a co-location), `contained` says who is being carried by what (a contained body's position is derived from its carrier's, transitively), and `contacts` is a flat list of who is in physical contact with whom and by which body parts — a relation stored once rather than on either body, pruned at every merge by `spatial.normalize_scene_contacts` (contact between two people not in the same room cannot survive, so movement ends a hold deterministically). Each contact has independent `relation: surface|interior` topology and `motion: settled|moving` kinematics; old rows derive both from `manner` and `detail`, and an interior relation must be explicitly removed before the same endpoints become surface contact. Interior records may also carry `target_interior`, the enclosing passage/chamber/material, separately from `target_part`, the exact boundary or endpoint currently touched. An `op:cross` is validated against a standing `crossed_target_part`; it persists only the downstream `target_interior` and current `target_part`, not the crossed boundary. `attire` is the live per-story clothing state: a card's `initial_outfit` may seed a missing entry at scene creation or first attachment/promotion, but must never reset an entry already changed by story events. Each attire region contains ordered `garments` and optional authored `beneath`; torso additionally permits `beneath_zones:{chest,midriff}`. A garment's optional `covered_zones:{torso:[...]}` is an override listing the zones it still covers while worn; absence means full coverage. An empty torso list means the garment remains worn at the torso but covers neither torso zone. `wearing`, derived `state`, region garment state and zone coverage must be reconciled only through `attire.rederive_entry`/the commit path.
- `scene.poses`: frame-scoped complete body-arrangement snapshots keyed by
  subject. `posture` is the body's own pose, `support` its anchor/entity/body,
  `relative_to` plus `relation` its arrangement against another body, and
  `constraint` a standing restriction; `detail` carries only what those axes
  cannot. Touched snapshots replace whole. Room separation clears the relative
  and constraint axes while retaining a still-valid own posture. Open strings
  keep fictional bodies genre-neutral.
- `scene.contact_actions`: frame-scoped ongoing tactile effects attached to a
  stable `contact_id`. The id is derived symmetrically from a contact's two
  owned endpoints rather than from list order. Records keep the participating
  actor, a noun-like effect, and optional qualitative intensity/rhythm. They
  persist through model silence and are removed when their parent contact
  ends; only contact participants receive their cause-blind percepts.
- `scene.substances`: frame-scoped flat records for non-discrete matter that
  remains at a destination. Each record has a stable id plus source/source
  part, fiction-authored material name, target, `placement:surface|interior|contained|room`,
  optional enclosing interior/endpoint, free-text amount, optional explicit
  `amount_band`, and detail. Partial transfers name `source_substance_id` and
  a qualitative `portion`; these transient selector fields are consumed during
  merge. A unique standing
  interior contact may supply omitted destination topology before that beat's
  contact removals. Records persist until a bounded remove/clear operation;
  elapsed time and model silence do not alter them without world-specific law,
  they are neither inventory nor body contact. Because this is inside the
  scene blob, checkpoints, branches, and portable archives carry it without a
  normalized-table migration.
- `checkpoints`: whole-state restoration blobs keyed by chat and turn index.

Sequence causality adds no world table and no persistent scene ledger.
`DirectorResolve.sequence_dispositions` is retained with the step result for
author diagnostics and replay inspection. `StateDiff.phase_sources` is a
transient source map consumed by the deterministic causal floor before the
scene is committed; neither it nor compatibility `source_event_id` annotations
belong in the stored scene blob.

## Structured world tables

- `world_entities`: normalized projection of the scene's entities, derived at commit (`commit_world_entities(prepared=...)`). Read at runtime only for fixed-point existence checks (`paradox._entity_exists`) and book-anchor alias resolution (`commit._entity_alias_map`). **Which** entities a beat touched comes from the post-dedup diff; **what** they now are comes from the merged scene, and taking the second from the diff too is how this projection drifted: `spatial._merge_entity` sits between the diff and the blob, reading a schema default as silence and refusing a name `schemas._fill_entity_names` derived from the dict key. Writing the raw diff skipped all of it, so a pose-only beat left the blob saying "Blue Police Box"/vehicle and the row saying "Tardis 001"/object — 15 of 480 live rows named literally `Object`, 19 disagreeing with the blob about `name`, 24 about `kind`. A row heals the next time a beat touches that entity; `tools/reproject_world_entities.py` sweeps the ones nothing will touch again (read-only without `--apply`, and it skips an entity whose frames disagree, since `scene` is frame-scoped and this table is not).
- `world_placements`: DECOMMISSIONED (Phase 3a) — nothing inserts or reads it; kept only so old snapshots/exports restore. The two surviving runtime writers are deletes (legacy cleanup in `commit_world_entities`, and `world/paradox.py`). Positions live solely in the frame-scoped `scene.positions`.
- `world_events`, `world_conditions`, `scheduled_events`: objective event timeline, active conditions, and future events (`transit_arrival`, `news_arrival`, `consequence`). `scheduled_events` is the due queue; `commit_world_event_spine` promotes only mechanically fired rows into `world_events`. Both event tables are keyed `(chat_id,event_id)`; `world_events.frame_id` is an explicit FK and its `turn_id` names the commit that observed the occurrence. The payload retains `source_event_id`, so readers can suppress the legacy queue row rather than report one occurrence twice.
  `world_conditions.next_tick` is written by the mechanics sweep's pass (c1) and by nothing else — not read by anything else, and not WRITTEN by anything else, which is the load-bearing half: a condition whose payload declares a `tick_interval_seconds` gets its cadence scheduled from the clock the sweep first sees it on, then advanced on every beat a tick comes due (`idx_world_conditions_due` is the index over it). `commit_world_entities` binds it NULL on insert and does not name it on update, so a model re-emitting a live condition cannot move it; a writer-set value past any reachable clock would freeze that row's cadence forever, since `_tick_conditions` loops `while t <= elapsed` and no view surfaces the column to a reader who could repair it. The column is NULL for every row that declares no cadence, which is most of them. `expires_at` is the only thing that closes a row on the clock, and it IS the writer's: a re-emission that authors one now reaches the column through a COALESCE on the UPDATE (it used to be discarded silently). Every write also stamps `last_asserted_turn_idx` into the payload — one stamp, in turns, because `director_floors._conditions_view` is its only reader and reports `last_asserted_turns_ago`.
- `room_registry`: the sole cross-frame ledger of room identity/existence-over-time/retirement, keyed `(chat_id, room_uid)` and scoped to an owning lorebook. It is a deterministic projection of every scene write: `commit_scene` maintains it in the same commit domain, and the manual world editor (`world_put`) reconciles it through `commit.sync_room_registry_with_scene`. Rooms and lorebooks are retired (`retired_turn_id`), never deleted, on removal/destruction.
- `fiction_worlds`, `fiction_locations`, `transit_edges`: DEPRECATED dead macro schema — nothing in the runtime pipeline reads or writes them. Only the first two are kept so old imports restore: they are in `chat_archive.WORLD_TABLES` and in the checkpoint blob. `transit_edges` is named in exactly one place outside `core/db.py` — the chat-deletion sweep in `web/app.py` — so nothing snapshots, exports, imports or restores it, and an old archive carrying rows loses them on import. Do not repeat the three-table phrasing without that split; it is the reason a deprecated table can be dropped and nobody notices. Removal of all three is planned.

Authority model (Phase 3a): the frame-scoped `world.scene` blob is the single runtime source of truth for LIVE rooms/adjacency/positions/entity state — every spatial reader reads it and nothing else. The normalized tables are derived projections of scene commits and must never be treated as a second authority over live state; `room_registry` alone answers the cross-frame question "which rooms have ever existed here, and which are retired" (what multi-book destruction cascades mutate). A room retired in one frame's commit may legitimately still be live in a sibling (e.g. past-era) frame's blob; that frame's next commit re-registers it (upsert revives).

## Write helpers

`persist.chat_delete.delete_chat_data` is the complete story-owned deletion
boundary. The ordinary delete route checks that the pipeline is idle before
calling it; greeting Quick Start may also call it for the chat it just minted
when lived-location generation fails before turn 0. Keep the table inventory
there rather than adding another partial sweep at a caller.

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

`offscreen_epoch`, `offscreen_plans`, `offscreen_log`, and `charters` are
frame-scoped world keys. The epoch, reactive plans, and Charter registry are
primary diegetic state; the log is
provisional diegetic history. All four therefore
ride the existing whole-`world` checkpoint/archive/branch path and roll back
together. A plan stores its current stage and bounded history, so restore never
replays a discarded plan advance. Background jobs carry an epoch id in addition to `base_turn`: the
turn check catches rollback behind the producer, while the epoch check catches
a restore/branch at the same numeric turn but on a different world edge. Stable
epoch+rung batch identity makes landing idempotent.

`planned_entities` (`world/planned_entities.py`) and `planning_needs`
(`world/planning_needs.py`) are frame-scoped world keys beside `charters`: the authored plans no charter
simulates (`{uid: {kind, name, aliases, role, brief:{purpose, truths, where},
surface?, rendered?}}`) and the typed needs a surface-only Director mint files
(`[{uid, kind: person|thing|room, status: open|filled|closed, surface:{name,
room, description, did, role}, identity, fill?}]`). Both ride the whole-`world`
checkpoint/archive/branch path with no handling of their own; a charter body
enrolled to answer a need lives in `charters` like any other body, with
`guest`, `guest_until` and `departed` as the only fields enrolment adds to a
body's shape.

`plot_packages` (`story/plot_packages.py`) is the Writers' Room's package
store, a frame-scoped world key like the two above: `{uid: {title, premise,
status, revision, spoiler_policy, scope, authority, base:{turn_idx,
registry_revision}, truths[], questions[], participants[], evidence[],
pressures[], clocks[], opportunities[], constraints[], planner_requests[],
operations[], validation, provenance:{history[]}, published_turn?,
activated_turn?}}`. It rides the whole-`world` path with no handling of its
own; what a published package PLACED (planned rooms in `room_registry`,
plans in `planned_entities`, bills in `artifacts`, rows in
`scheduled_events` and `lore_entries`) lives in those ledgers and is
restored with them, so a checkpoint restore past a publish takes back both
the package's status and what it placed.

`charters` stores `{version, items}`. Each item separates its
normalized pure `state` from runtime markers (`last_elapsed_seconds`,
`last_epoch_id`, `window_hours`). Directed regard keys are JSON strings
(`listener->speaker`), never tuple keys. Charter jobs write this blob and their
stable scheduled consequences in one transaction after checking the epoch,
base turn, and source-registry revision under that same write lock; do not
persist a Charter
event list in the blob or a second table. Incidents live only on the existing
`scheduled_events` -> `world_events` spine.

`structures` is the authoring grammar/extent ledger for planned locations.
Individual planned rooms use ordinary `room_registry` rows; their free-form
`payload.planned` contains only structure key, purpose, access, adjacency and
frontier labels. A planned row becomes resolved only when the live scene room
has mapped prose. The full skeleton never lives in the scene blob: Charter
composes it for pathing, while commit materializes only planned neighbours of
occupied rooms as small scene stubs.

Lived-location generation is additive. A second generated structure receives
a deterministic suffix when its structure, room or Charter keys would collide;
the existing `charters`, `structures`, and `room_registry` records remain
standing. `room_registry.owning_book_id` records the selected lorebook that
grounded the skeleton. Presim advances only the new Charter items before
merging them into the existing frame-scoped registry.

Generation lore is retrieved from the author-selected book subtree with the
same hybrid relevance ranker Mapping uses; insertion order is never relevance.
Setting-law entries (`rules` categories or `<rules>` content) remain a bounded
mandatory prefix. The resulting Charter `history.architecture.generation_lore`
records the exact query, source book, and entry ids so an author can audit what
shaped a location without exposing that host-facing manifest to any mind.

Within each Charter, `judgments` is holder → subject → independent social axes
plus bounded evidence identities; `commitments` holds locally recognised
undertakings and their explicit lifecycle; `economy` holds abstract lots,
targets, flows and markets; `decisions` holds bounded agendas and typed orders.
All are part of the one frame-scoped Charter JSON state and therefore use the
existing checkpoint/archive/branch path—do not create parallel tables for
them. `history` is author diagnostics and must never be projected into a mind.
The presim historian may cite synthetic `presim:service:*` evidence rows
derived from each selected resident's bounded `stood`/`travelled` aggregates.
Those rows are historian input, not another persisted event ledger: they let a
quiet competent career be summarized without writing one event per watch.
`economy.supply_points` is the temporary upstream-chain abstraction: each
names a physical boundary place and receiving holder, with bounded delivery
rates, reliability and route burden. It is explicit external dependence, not
local production and not a broadcast timer; future caravans may replace it
without changing the local stock/target model.

Within a Charter state, `bodies.<key>.name` is the scene-facing display name;
the dict key remains the durable institutional identity. An authored `naming`
profile supplies bounded cultural name pools/parts, formatting, rank titles
and post titles. Normalization deterministically generates an unnamed body's
name from `{profile seed, charter key, body key}` and materializes it into the
body exactly once: changing the profile or inserting another body never
renames an existing person. Titles are presentation aliases, not identity.
`dialogue_color`, when authored, is a normalized override; otherwise rendering
derives it from `charter:<charter>:<body>`, so renames, title changes and
promotion cannot repaint that speaker. `bindings.<body>` is
written once at background-to-character promotion and carries `char_id`,
character/entity identity, display name and promotion turn. A bound body is an
institutional projection only: scene position is copied into it before a tick,
while Charter-held `minds`, `needs`, `feel` and `heard_blame` for that body are
removed. Do not delete the body itself—rosters, watches, standing and service
history still refer to its durable key, and the character may continue to hold
office. `background_presences[].charter_refs` contains only stable
`{charter,body}` references; the Charter registry remains the identity and
state authority.

A generated authored resident additionally carries `resident_seed_id` on its
body. It is placement identity only, never cognition and never a card payload;
for greeting launch its value is `character:<id>`. The private
`charter_resident_histories` world record makes the one-time handoff auditable:
exact Charter/body binding, historian citations, recent-life overview, minted
memory event keys, per-episode chronology/location/entities, grounding drops
and any generation failure. It contains no private card context. The actual
pre-story career, recent-life summary and 10–16 episode rows use
`turn_id=NULL`, `turn_idx=NULL`, stable `prestory:charter:*` event keys, and the
episode's remembered provenance. Episode keys derive from grounded content
rather than database row ids, so branch/import identity survives; re-running
the same handoff updates rather than duplicates identical episodes.

`character_history_routes` is the frame-scoped author routing record: closed
topology/authority fields, confidence, cited reasons, optional author guidance
and handoff status. It is not a mind payload. `character_journey_histories`
stores the separate itinerary ledger: ordered event ids, places, named
participants, citations (or an explicit generated flag), grounding drops and
compiled memory keys. Both use ordinary world JSON storage, so checkpoint,
branch and portable archive paths need no schema migration.

Within a Charter, `experiences.<body>` is capped participant-owned evidence,
not another objective event ledger. Social rows are copied only to
participants; private-habit rows only to self. A generated featured-resident
episode adds one compact `shared_prestory` row to each named participant while
the featured character receives the detailed autobiographical memory. The
reciprocal row survives that character's handoff and becomes promotion-safe
history for its owner. `habit_runs` updates a habit's
last occurrence and repetition count without appending a diary row per window.
These stores and `bodies.<body>.private_habits` are removed when a full
character claims cognition. `posts.<post>.purpose` supplies human meaning for
career narration; `serves` remains the mechanical upkeep edge.

Witnessed player/major-character conduct is not a second event table. A
grounded `scene:<turn_id>:<source_id>` claim lives in the receiving body's
existing `minds` map as `kind: news`, with `public_evidence` carrying the exact
licensed action/quote and speech-act direction only for a firsthand witness.
The source id deduplicates a replayed commit; the mind cap and ordinary news
decay bound it. Body-to-body retelling replaces that firsthand packet with a
secondhand act-kind summary and degrades `claim_text`, so no listener stores a
pristine transcript it did not hear. Because the claim remains ordinary
Charter state, checkpoint/archive/branch/restore and promotion need no new
durable store.

`world_events` joined `snapshot_state`/`insert_world_tables`, portable
export/import, branch remapping, deletion, and fidelity tests with its first
runtime writer (schema v27). Same-chat checkpoint restore preserves ids and
removes discarded-timeline rows; portable import may preserve ids because the
primary key is chat-partitioned; branching mints new event ids and remaps
payload references plus turn/frame FKs. Do not add a second event ledger.

Physical information envelopes use the bounded `carried_reports` member of a
character's existing `chat_chars.state` / `chat_char_frames.state`, not another
global truth table. Each row cites a `world_events` id and stores only its
public witnessed surface plus acquisition/current locations and route. It
therefore inherits character-state checkpoint, frame, branch, and archive
behavior. The objective payload is never copied into this private state.

`character.simulation.offscreen_agent` is author-owned configuration on the
card (and story-card override), default false. It is not runtime state and does
not itself schedule work. Runtime `state.offscreen_agent.last_turn` is the
character/frame-owned landing marker used to reject repeated spend on the same
carried evidence; it must continue to travel through the existing character
state checkpoint/archive/branch paths.

Use `qtx` for a multi-statement invariant that must roll back together. Nested domain transactions become savepoints. `commit_all` supplies one outer transaction for all primary turn effects, so any exception rolls the complete turn back. Do not perform provider or embedding calls while a write transaction is open.

## Schema-change checklist

A durable field or table change is incomplete until all applicable paths are updated:

1. `SCHEMA` and `SCHEMA_VERSION`/migration logic in `core/db.py`.
2. Creation/default behavior.
3. Read and commit code.
4. Export/import payloads.
5. Checkpoint snapshot and restore.
6. Branch/clone ID remapping in `web/app.py` when IDs are embedded.
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

`DB` defaults to `engine.db` and can be overridden with `ENGINE_DB` before importing `core/db.py`. Tests use `db.configure(path)` to switch connections safely.

## A retired setting's row outlives its feature

*(Moved out of `docs/UNBUILT.md` §1.51b on 2026-08-19. The entry's own verdict
was "this is tidiness, not a defect"; what is worth keeping is the CLASS.)*

Nothing prunes `settings` when a feature is deleted, so a retired key stays
forever, and the only symptom is that a later reader greps the tree, finds
nothing, greps the database, and finds a row. Measured on the owner's live
install 2026-08-18, read-only: **four of 29 keys have no reader anywhere in the
engine** — `director_orchestration` (the flag the orchestrated Director shipped
behind), `character_reflection` (a feature built and then decided against; the
work is intact on branch `character-cognition`), and `host_secret` /
`host_secret_hash` (the auth scheme that preceded `host_pw_hash` /
`host_pw_salt`). Checked because two of them are credentials: nothing sensitive
is at rest — `host_secret` is empty and `host_secret_hash` is a 64-character
digest, so `tests/test_host_secret_hashing.py`'s standing claim holds.

**The class: a settings key is the one kind of configuration the engine cannot
check.** `tools/project_check.py` reads the tree, and the tree is exactly where
a retired key is absent. Anything that enforces this has to compare a list of
live keys against a database, which means **the list has to exist first** — so
adding a key means adding it to that list too, or the check can never be built.

The repair is not free either: a migration deleting retired keys runs on the
owner's database at next launch, which is their call to make, not a
housekeeping commit's.
