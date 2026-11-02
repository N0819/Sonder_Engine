# Persistence consistency audit — schema, migrations, checkpoints, archive, branch

Auditor: persistence lane, 2026-11-01, tree at `84f3de23` (branch `worktree-jev-character-tracking`, clean).
All reproductions ran on scratch databases under the scratchpad (`persist_audit/`), created by `db.init()` with
`ENGINE_DB` set before import; `engine.db` was never opened. Repro scripts: `persist_audit/repro/r1.py` … `r7.py`,
schema dump `persist_audit/schema.json`, world-key inventory `persist_audit/wkeys2.txt`.

## Scope read

Read in full:
- `docs/guides/DATABASE.md` (757 lines).
- `core/db.py` — lines 1-267 (frame keys, era map), 268-1313 (SCHEMA: read every table and comment; skimmed
  the long prose comments in 800-960 and 1070-1313), 1314-2230 (MIGRATIONS: every statement enumerated
  programmatically, comments read for v13-v45), 2231-3148 (LATE_SCHEMA, connection, `transaction`, `q/qi/qtx`,
  guards, `_backfill_resource_uids`, `_migrate_chat_copies_to_overlays`, time-of-day recovery, `init`,
  `wget/wset/wset_if_changed`, read tokens, frame helpers).
- `core/jobs.py` (520), `core/outofband.py` (392), `core/frames.py` (299), `core/updates.py` (399),
  `core/code_version.py` (205), `core/logging_utils.py` (121), `core/paths.py` (32).
- `persist/checkpoints.py` (1937), `persist/chat_archive.py` (1286), `persist/pipeline_trace.py` (635),
  `persist/llm_capture.py` (604), `persist/about_backfill.py` (310), `persist/beat_order.py` (287),
  `persist/steps.py` (150), `persist/chat_delete.py` (42).
- `web/app.py`: 990-1100 (`_clone_snapshot_entries`, rewind gates, `_refresh_rewindable_checkpoints`),
  1171-1700 (`_remap_*`, `_build_world_id_remap`, `_deep_remap_ids`, `_remap_world_values`,
  `_remap_row_json_fields`, `_remap_cp_blob`, `_json_id_list`, `_remap_frame_character_ids`),
  6440-6460 (archive service wiring), 6913-7437 (`turn_branch`), 7840-7900 (`turn_del`), plus 195-245
  (startup reconcile thread), 2515-2530 (debug route), 3021-3033 (compaction route), 3845 (`char_del`),
  4406-4434 (`attach_lore`), 5832-5860 (`world_put`).
Read in part because the persistence paths call into them (not audited as files):
`mind/memory_snapshot.py` 278-520 and 747-1005 (dump/restore of memories, summaries, lorebooks, overlays),
`mind/memory_write.py` 225-260, 640-700, 751-800, `mind/memory_vectors.py` 30-100, 225-300, 740-780,
`mind/memory_lorebooks.py` 260-420, `mind/knowledge_circles.py` 1-80, `story/scene.py` 2560-2750,
`agents/runtime.py` 1590-1650, 2080-2100, `persist/commit_mapping.py` 148-320, 655-690,
`persist/commit_entities.py` 360-500, `persist/commit_skip.py` 40-110, `world/charter_skip.py` 255-290.
Skimmed only: `tests/test_schema_integrity_fresh_vs_migrated.py` (fixture shape), `tests/conftest.py` (redirect).
Tests run: none of the suite (all evidence is scratch-db reproduction, EXPLAIN QUERY PLAN, and code trace).

## Findings

### F1 — `turn_del` nests `restore_checkpoint` inside its own write transaction: deadlock with the startup about-backfill, and a provider call under the global write lock
- **Severity:** CRASH (server-wide write hang). **Confidence:** CONFIRMED (deadlock reproduced with injected timing on the real functions; call order traced).
- **Where:** `web/app.py:7869-7876` (`with transaction(): restore_checkpoint(cid, turn["idx"], carried=_decide)`);
  `persist/checkpoints.py:1298-1318` (after `_restore_checkpoint_body` returns: `start_rebuild_if_needed(chat_id)`,
  `backfill_chat(chat_id)`, `bump_world_epoch()`); `persist/about_backfill.py:225` (`with _chat_lock(chat_id):`)
  and `:285` (`with transaction():` inside it); startup thread `web/app.py:229-233` (`backfill_all()`).
- **Failure:** the startup thread runs `backfill_all` → `backfill_chat(C)` which takes `_chat_lock(C)`, computes
  (seconds per bank) and then wants `_write_lock`. A host deleting a turn of chat C in that window: `turn_del` holds
  `_write_lock` (outer `transaction()`), `restore_checkpoint` reaches `backfill_chat(C)` and blocks on
  `_chat_lock(C)`. Lock-order inversion → both threads wait forever; `_write_lock` is never released, so every
  `qi`/`transaction` in the process blocks → the server cannot write until restart. Repro
  `persist_audit/repro/r5.py`: `turn_del thread alive after 3s: True | startup backfill alive: True`.
  The window recurs on every startup for any chat holding rows `_backfill_chat` `skipped` (no world found,
  `about_backfill.py:259`): skipped rows are never written, so `backfill_all` re-lists those chats every start.
- Same nesting, two more consequences: (a) `start_rebuild_if_needed` → `embedding_bank_status` →
  `embed_texts_meta(["status"], retry=None)` (`mind/memory_vectors.py:64`) is a live provider round trip, made
  here while `turn_del` holds the global write lock — against DATABASE.md "Do not perform provider or embedding
  calls while a write transaction is open" and AGENTS.md "Slow provider work belongs in preparation before the
  outer write transaction"; a legacy (vector-less) blob also re-embeds in `prepare_chat_memory_restore` under
  that lock. (b) `bump_world_epoch()` runs before the OUTER commit; a world row the restore deleted (not
  re-`wset`, so not in `pending_world_bumps`) can be cached by another thread under the new epoch from the
  still-committed pre-restore state and served after the commit (comment at `checkpoints.py:1314-1317`
  "After the commit" is false in this caller).
- **Fix:** run `restore_checkpoint`'s tail (rebuild kick, about backfill, epoch bump) only when its transaction is
  outermost — e.g. return a "post-commit" callback list that `turn_del` runs after its `with transaction()` —
  or restructure `turn_del` so the restore is the outermost transaction and the deletes ride inside it
  (`restore_checkpoint` already takes `carried`). Test: a thread holding `_chat_lock(C)` waiting on
  `transaction()` while `turn_del` runs must finish (join with timeout).

### F2 — Restore and branch crash when a character with a frame override was deleted from the library after the snapshot
- **Severity:** CRASH (story permanently un-rerollable/un-rewindable/un-branchable at every checkpoint taken while the override existed). **Confidence:** CONFIRMED (`repro/r2.py`).
- **Where:** `persist/checkpoints.py:1215-1220` (`DELETE FROM chat_char_frames …; INSERT INTO chat_char_frames(…)
  VALUES(?,?,?,?,?)` for every `b["char_frames"]` row, no check that `cf["char_id"]` still exists);
  `web/app.py:7134-7144` (branch inserts the blob's `char_frames` the same way). `char_del`
  (`web/app.py:3845-3848`) deletes the `characters` row; `chat_char_frames.char_id` is `REFERENCES characters(id)`.
- **Failure:** chat with a frame, character B with a `chat_char_frames` row, checkpoint 1 written; host deletes B
  from the library; `restore_checkpoint(cid, 1)` → `IntegrityError FOREIGN KEY constraint failed`; the whole
  restore rolls back. The memories path (`prepare_chat_memory_restore` → `surviving_character_ids`), summaries
  (`prepare_memory_summary_restore`) and `chat_personas` (`_restore_chat_personas`) already filter the deleted
  row — `char_frames` is the one sibling that does not (the same orphan class
  `memory_snapshot.py:777-780` says it "found by fixing memories first and watching the identical
  IntegrityError reappear one table along").
- **Fix:** skip `char_frames` rows whose `char_id` is not in `surviving_character_ids()` in both the restore and
  `turn_branch`. Test: the r2 shape — delete the character, restore succeeds, the surviving override remains.

### F3 — Archive import does not rekey integer character ids held inside `world`: `relationships:<char_id>` is lost or lands on the wrong person
- **Severity:** CORRUPTION. **Confidence:** CONFIRMED for `relationships:` (`repro/r1.py`); PLAUSIBLE for the siblings.
- **Where:** `persist/chat_archive.py:1063-1081` remaps only the frame suffix of world keys, `active_books`,
  fixed-point frames and couple maps; `web/app.py:1459-1481` (`_remap_cp_blob`) the same for checkpoint blobs.
  Writers keyed by the integer: `mind/memory_relationships.py:60-72` (`f"relationships:{char_id}"`),
  `world/spatial_frames.py:1324-1326, 1853-1856`.
- **Failure (reproduced):** source character id 1 with a stance toward "Hal"; import into an install already holding
  five characters → character becomes id 6, the world row stays `relationships:1`;
  `get_relationships(new_cid, 6).get("Hal")` → `None`, while `relationship_events` (remapped, `chat_archive.py:1105-1115`)
  still holds the reason — the ledger and the graph now disagree. If the importing install later attaches its own
  character 1 to that story, it inherits Mora's stances — exactly the "hanging a grudge on whoever inherited the
  number" the `relationship_events` import was written to prevent. Imported checkpoints carry the old key too.
- **Same class (not executed):** Charter `bindings.<body>.char_id` and `bodies.<body>.resident_seed_id =
  "character:<id>"` (`world/charter_model.py:801-810`, `world/charter_skip.py:269-283` asks bindings by id first
  and returns None on a mismatch, so a promoted person is no longer found as bound and the body can be simulated
  beside the character); couple maps keep an unmapped id verbatim (`web/app.py:1253-1256`,
  `char_idmap.get(int(c), int(c))`). Contrast: `knowledge_circles` is keyed by the portable identity
  (`mind/knowledge_circles.py:47-56`) and survives import.
- **Fix (class):** key per-character world state by the portable identity (as knowledge_circles does), or have the
  import and `_remap_cp_blob` rewrite every char-id-bearing key/value through `old_char_map` (and drop, not keep,
  an unmapped id). Test: export, import into a db with pre-existing characters, assert the graph is read back.

### F4 — Background memory writers address rows by id across a restore that re-mints every id of the chat
- **Severity:** CORRUPTION (wrong vector / wrong `about` tag on a memory, permanent). **Confidence:** id re-mint CONFIRMED (`repro/r7.py`); the race PLAUSIBLE (traced, not timed).
- **Where:** restore is delete-and-reinsert (`mind/memory_snapshot.py:491-517`; `memories.id` has no AUTOINCREMENT,
  `core/db.py:793-794`). Writers that SELECT rows, do a remote/long step, then UPDATE `WHERE id=?` with no
  content check: `mind/memory_vectors.py:262-279` (`rebuild_embeddings`), `mind/memory_write.py:676-688`
  (fallback-vector repair), `persist/about_backfill.py:284-288` (guarded only by `about=''`). The restore cancels
  consolidation, promotion, room design, skip memories and Room jobs (`checkpoints.py:554-638`) but not the
  embedding rebuild or repair, and the about-backfill holds no lock the restore takes.
- **Failure:** r7: before restore `{1: 'A prestory seed…', 2: 'Turn 0: Ada opened…'}`, after
  `{1: 'Turn 0: Ada opened…', 2: 'A prestory seed…'}` — the dump orders NULL-`turn_idx` rows last
  (`memory_snapshot.py:308-309`), so ids swap on the first restore. A rebuild batch that read id 1 (seed) and is
  inside its embed call when the player rerolls writes the seed's vectors (and `vkey`) onto the turn memory;
  `embedding_model` then equals the live key, so the rebuild never revisits it — semantic recall surfaces the wrong
  memory for good. The repo already states the rule this breaks: `record_memory_look` is "addressed by the stable
  `memory_ref` … never by row id -- checkpoint restore is delete-and-reinsert" (`mind/memory_read.py:400-406`).
- **Fix:** write by `(chat_id, char_id, event_key)` and `content` (compare-and-set: `WHERE id=? AND content=?`), or
  stamp a per-chat restore epoch that these writers re-check inside their write transaction; also cancel the
  rebuild/repair in `_cancel_jobs_the_restore_discards`. Test: monkeypatch the embed call to run a restore
  mid-batch; assert no row's vector is another row's.

### F5 — One-shot data migrations run after the version stamp has committed; a failure or kill skips them forever
- **Severity:** CORRUPTION (silent, permanent). **Confidence:** CONFIRMED (injected failure; stamped version read back).
- **Where:** `core/db.py:2947` `c.executescript(LATE_SCHEMA)` (legacy-mode `executescript` COMMITs the open
  transaction that holds every `_set_schema_version` stamp) runs BEFORE `:2955 _migrate_chat_copies_to_overlays`
  (gate `current < 39`), `:2969 backfill_regions` (`< 36`), `:2978 backfill_memory_vectors` (`< 38`), whose writes
  commit only at `:2979`.
- **Failure:** scratch db stamped 38, `_migrate_chat_copies_to_overlays` made to raise → `init raised: …` and
  `stamped version after the failed pass: 45`. The next start sees `current == 45` and never runs the pass. A host
  killing a slow first start (the vector backfill hashes every bank) gets the same result: chat copies never become
  overlays, rooms never get regions, old vectors are never filed (so every reroll of an old bank re-embeds it in the
  prepare phase). The comment at `core/db.py:2475-2486` promises the stamps and later lists "roll back together";
  the data passes are outside that.
- **Fix:** run the gated data passes before `executescript(LATE_SCHEMA)` inside the stamping transaction, or give
  each pass its own completion marker in `schema_meta` and gate on the marker, not on `current`. Test: the injected
  failure above, then a clean `init()` must run the pass.

### F6 — Refreshing the newest checkpoint copies that turn's own lore writes into the world before it
- **Severity:** CORRUPTION (a discarded beat's lore survives its reroll). **Confidence:** CONFIRMED (`repro/r3.py`).
- **Where:** `web/app.py:1053` `refresh_checkpoint(cid, last["idx"])` (called by attach/enable/detach/bind/unbind
  routes, `web/app.py:4432-4510`); `persist/checkpoints.py:1931-1933` replaces `lore`, `lorebooks`,
  `lorebook_links`, `lore_overlays` with the CURRENT lore. Only older checkpoints get `_carry_the_book_set`
  (`checkpoints.py:1809-1859`), whose docstring is the argument: a checkpoint "lies under turns that wrote lore of
  their own -- … ratifying a claim into canon, a destruction retiring a book …".
- **Failure:** canon at turn 0's checkpoint; turn 0's commit writes a canon entry (in play: `settle_claims` →
  `write_canon`, `world/background_claims.py:557-569`; destruction sets `lorebooks.retired_turn_id`,
  `persist/commit_destruction.py:388`; the opening premise); the host attaches a book; reroll turn 0 →
  `turn 0's own canon entry survives its reroll: True`. The newest checkpoint lies under exactly one turn that can
  write lore, so the older-checkpoint argument applies to it too.
- **Fix:** use the book-set carry for the newest checkpoint as well (or diff only the book set). Test: r3's sequence.

### F7 — Checkpoint restore skips chat-owned books retrieval cannot reach, though the snapshot holds them
- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (`repro/r2.py`).
- **Where:** snapshot takes every owned book (`checkpoints.py:122-138`, comment: isolated descendants "are still
  chat-owned state that a reroll must restore exactly"); restore builds `current` from owned books ∩
  `chat_lorebook_ids` (`checkpoints.py:386-392`), so an `isolated` child or an owned, unattached, parentless book is
  not in it; the id lookup then fails, `_recreate_snapshot_book` declines because the id is live
  (`checkpoints.py:352-355`), and the book is `continue`d — never restored and never deleted.
- **Failure:** isolated child holding 1 entry at the snapshot gains an entry after it; restore → still 2
  (`isolated entries after restore: 2 (snapshot held 1)`). A book minted after the snapshot in that shape survives
  too. Turn-time producer: `_apply_mapping_book_ops` accepts `inheritance_mode: "isolated"`
  (`persist/commit_mapping.py:230-238`, reached through the authoring package's prepared dict).
- **Fix:** build `current` from `SELECT * FROM lorebooks WHERE chat_id=?` (ownership), keeping reachability only for
  what library books to touch. Test: r2's H4.

### F8 — Import carries source-install `origin_id` verbatim; the integer then blocks attaching an unrelated book
- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (`repro/r6.py`).
- **Where:** `persist/chat_archive.py:917` and `:954` (`book.get("origin_id")` into `lorebooks` and
  `chat_lorebooks` unchanged); `web/app.py:4417` (`attach_lore` treats `lb.origin_id = src` as already attached);
  `persist/checkpoints.py:420-425` (restore treats a snapshot book whose `origin_id` names a live LIBRARY book as a
  library reference).
- **Failure:** install A: story X forks story W's book (origin 1). Import X into install B where id 1 is library book
  "Library 0": imported fork has `origin_id 1`; `attach_lore(nx, {"lorebook_id": 1})` →
  `{'lorebook_id': 2, 'already': True}` — the host can never attach that book to the imported story. On restore, a
  snapshot book absent from `current` whose foreign origin names a library row is attached by reference instead of
  being re-created.
- **Fix:** NULL `origin_id` on import unless the origin is itself in the archive (then map through `bookmap`).
  Test: r6.

### F9 — `fiction_worlds` / `fiction_locations` have GLOBAL primary keys: importing a story holding rows into an install that still has its source fails
- **Severity:** CRASH (import refused with HTTP 500). **Confidence:** CONFIRMED (`repro/r1.py` H2:
  `IntegrityError UNIQUE constraint failed: fiction_worlds.world_id`).
- **Where:** schema `fiction_worlds(world_id TEXT PRIMARY KEY …)`, `fiction_locations(location_id TEXT PRIMARY KEY …)`
  (every other world table is `(chat_id, id)` since v14/v16/v27); `persist/chat_archive.py:1129` passes the rows
  unremapped to `insert_world_tables` (`checkpoints.py:832-842`). Branch remaps them (`_build_world_id_remap`), but
  only from the branch-point blob, so a branch's OLDER checkpoint holding a row the branch point lost restores with
  the source id and collides the same way. Also: both paths drop `created_turn_id`/`retired_turn_id` of
  `fiction_worlds` (snapshot `checkpoints.py:277-281`, insert `:832`).
- Not new as a removal: UNBUILT_PARKED "Remove the deprecated macro schema" / UNBUILT_PLATFORM PERSISTENCE-F5's
  drop half would cure it; the crash itself is not in either entry.
- **Fix:** until the drop, import should mint fresh ids for these two tables (reuse `_build_world_id_remap` limited
  to them). Test: export + import into the same db with one `fiction_worlds` row.

### F10 — The branch's world-id remap rewrites every exact string equal to an entity/condition/event id, anywhere in the world
- **Severity:** CORRUPTION (WRONG-SCENE on the branch). **Confidence:** mechanism CONFIRMED (`repro/r4.py`); a
  colliding id in a live story PLAUSIBLE.
- **Where:** `web/app.py:1307-1341` (`_build_world_id_remap` mints a hex id for every world_entities /
  world_conditions / scheduled / world_events id), `:1344-1374` (`_deep_remap_ids` rewrites any exact string and any
  dict key, sparing only values under `"name"`), applied to the live world (`:7326`), every copied checkpoint
  (`:7408-7417`) and the world tables (`:7345-7348`).
- **Failure:** an entity keyed `door` → every `barrier: "door"` (a real stored alias, `world/spatial_barriers.py:31`)
  becomes `6f6bd862658d41d6`; an entity `lantern` → a garment string `"lantern"` becomes hex. The docstring records
  one instance already (entity names turned to hex on chat 123) and patches only the `name` key.
  The remap's original reason — global PKs — no longer exists for these four tables (all `(chat_id, id)`; anchor
  lookups are chat-scoped, `persist/commit_destruction.py:36-41`); the archive import keeps the same ids and works.
- **Fix (class):** stop remapping chat-partitioned ids on branch (keep fresh ids only for the two global-PK
  deprecated tables), or remap only at schema-known id positions. Test: r4's world through `turn_branch`.

### F11 — Checkpoint blobs carry no schema version; restoring or branching an old blob re-introduces pre-migration shapes
- **Severity:** CORRUPTION (low likelihood: needs a checkpoint from before a data migration). **Confidence:** PLAUSIBLE (by reading).
- **Where:** `snapshot_blob` writes no version (`checkpoints.py:51-104`); `_restore_checkpoint_body` has no upgrade
  step; data migrations touch live rows only: v30 re-keys `persona_carrier_state` per era (`core/db.py:1926-1966`),
  v36 `backfill_regions`, v33 `knowledge_tag='common'`, v15 layout entries → `room_registry`. Also
  `insert_world_tables(delete_first=True)` deletes all nine tables unconditionally (`checkpoints.py:752-838`), unlike
  `chars`/`frames`/`chat_personas`/`memories`/`lorebooks`/`lore_overlays`, which the restore guards by presence.
- **Failure:** a pre-v30 checkpoint of a framed story restores the bare `persona_carrier_state` holding every era's
  reports (the defect v30 fixed), and v30 never re-runs; a pre-v36 checkpoint restores rooms without `region`, which
  `backfill_regions` (gated `current < 36`) never revisits.
- **Fix:** stamp `SCHEMA_VERSION` into the blob and run the same version-gated data upgrades on a blob before
  restoring it; guard the world-table deletes by key presence. Test: restore a hand-built pre-v30 blob.

### F12 — A restore that deletes a frame moves that era's Writers' Room thread into the present
- **Severity:** CORRUPTION (low). **Confidence:** PLAUSIBLE (schema + code read).
- **Where:** `_restore_frames` deletes frames the snapshot lacks (`checkpoints.py:720-723`);
  `room_messages.frame_id REFERENCES frames(id) ON DELETE SET NULL` and the thread is not snapshotted (by design).
- **Failure:** a bubble split by the beat being rerolled, in which the player spoke to the Room → on reroll those
  lines get `frame_id NULL`, i.e. join the present's thread. Import and branch DROP a line whose frame did not come
  across (`story/room_conversation.py:547-575`); the restore re-homes it instead.
- **Fix:** delete (or keep with the era's asks via `_keep_room_briefs`' rule) the lines of frames the restore removes.

### F13 — Archive import flattens a library book hierarchy
- **Severity:** CORRUPTION (low). **Confidence:** CONFIRMED by reading.
- **Where:** `persist/chat_archive.py:875-893` inserts a newly created library book with `parent_id` None; the
  parent pass skips library books (`:961-962`).
- **Failure:** a library parent and child both bundled in an archive arrive in a new install as two unrelated
  library books, each attached directly at `enabled=1` (`:900-904`) — `inheritance_mode` weights and the tree are
  lost for every later story in that install.
- **Fix:** resolve library `parent_id` through `bookmap` in the second pass when the parent was created here.

### F14 — Restore's `lore_cache` sweep reaches only the present's row
- **Severity:** WRONG-SCENE (low). **Confidence:** PLAUSIBLE.
- **Where:** `checkpoints.py:1254-1272` run under `active_frame_id = None` (`:679`), so `wget/wset("lore_cache")` touch
  the bare key; `lore_cache` is frame-scoped (`core/db.py:110`).
- **Failure:** after a detach carried into the checkpoint by `refresh_checkpoint`, a framed story's era rows keep
  entries from the detached book; `agents/mapping.py:514-515` merges them into the Director's world context. (The
  sweep also caps at 24 while `commit_mapping` writes 12.)
- **Fix:** iterate every stored `lore_cache` key (`parse_scoped_world_key`) in the sweep.

### F15 — Capture retention never runs: `prune` and `vacuum_blobs` have no callers
- **Severity:** SILENT-NOOP (and a deleted story's captured text persists). **Confidence:** CONFIRMED (repo-wide grep:
  `prune` has no caller, `vacuum_blobs` only in `tests/test_llm_capture.py`).
- **Where:** `persist/llm_capture.py:60` `RETAIN_TURNS = 200`, `:357-371` `prune`, `:418-440` `vacuum_blobs`;
  DATABASE.md:78 says capture is "pruned to `RETAIN_TURNS` per chat".
- **Failure:** with capture on (the owner runs it with full bodies) `llm_capture` grows with every turn of every
  chat and `llm_blobs` never shrinks; `delete_chat_data` cascades the capture rows but the bodies — prompts,
  payloads, reasoning, i.e. the story text — stay in `llm_blobs` after the story is deleted.
- **Fix:** call `prune(chat_id)` from the commit tail when capture is on and `vacuum_blobs()` after chat deletion
  (or on a maintenance button); a cap is the owner's to confirm.

### F16 — Compaction and summary propagation write checkpoint blobs read outside the write lock
- **Severity:** CORRUPTION (low). **Confidence:** PLAUSIBLE.
- **Where:** `compact_checkpoints` reads at `checkpoints.py:1520` and writes `UPDATE … WHERE id=?` at `:1571`
  (background thread, no idle requirement: `web/app.py:3021-3032`); `propagate_memory_summaries_to_checkpoints`
  reads at `:1737`, writes at `:1769`. `refresh_checkpoint` and `carry_memories_forward` read-modify-write inside
  the lock; these two do not.
- **Failure:** a refresh or a skip-memory carry landing between the read and the write is overwritten (the carry
  exists so a reroll does not delete those rows); `checkpoints.id` has no AUTOINCREMENT, so a checkpoint deleted and
  re-created meanwhile can be the row the stale blob is written onto.
- **Fix:** compare-and-set (`WHERE id=? AND blob=?`, or re-read inside the transaction).

### F17 — `reaction_config` is a hand-set dial a restore rolls back
- **Severity:** SILENT-NOOP (low). **Confidence:** CONFIRMED by reading.
- **Where:** `story/scene.py:2570-2574` reads `reaction_config`; no route writes it (only the whole-world editor
  `world_put`, `web/app.py:5832-5856`); it is absent from `SETTING_PROVENANCE` (`checkpoints.py:872-985`), so every
  reroll restores the checkpoint's value. Sibling of the registered `promotion_thresholds` (UNBUILT_IDENTITY §4,
  line 961); the register names only that key.
- **Fix:** add it to `SETTING_PROVENANCE` as `SET_BY_HAND` (the class fix: a list of hand-set world keys checked
  against every route that writes one).

### F18 — A database older than v7 cannot be opened; the "any older version" promise is false
- **Severity:** DEAD (migrations v1-v7 unreachable) / STALE-DOC. **Confidence:** CONFIRMED (scratch db stamped 6 →
  `OperationalError no such column: resource_uid`).
- **Where:** `core/db.py:1` docstring; `executescript(SCHEMA)` (`:2899`) runs before the chain, and SCHEMA creates
  indexes on columns added by v2/v4/v7/v8 (`uq_characters_resource_uid`, `idx_memories_chronology`,
  `idx_lorebooks_parent` …). SCHEMA's own comment at `:342-350` explains this hazard for `idx_lorebooks_anchor`
  alone and moved only that one to LATE_SCHEMA. The integrity test builds the CURRENT schema and stamps 1
  (`tests/test_schema_integrity_fresh_vs_migrated.py:56-75`), so it cannot see it.
- **Fix:** move migration-dependent indexes to LATE_SCHEMA, or state the oldest supported version and refuse below
  it with a named error.

### F19 — Dead carriers and parameters
- **Severity:** DEAD (low). **Confidence:** CONFIRMED by grep.
- `world_entities.retired_turn_id` has no writer (the AUDIT_COMMIT §1.3 reader was removed —
  `persist/commit_common.py:576`), yet export, import (`chat_archive.py:1096-1101`), snapshot (`checkpoints.py:213-218`),
  `_remap_cp_blob` (`web/app.py:1597-1601`) and branch (`:7349-7351`) all carry and remap it.
- `_recover_scene_time_of_day(..., only_pre_split=...)` (`core/db.py:2771, 2832`): no caller passes it.

### F20 — DATABASE.md states four things the code does not do
- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- `:15` "`origin_id` is a legacy column, NULL on every new row" — `attach_lore` mints it for forks
  (`web/app.py:4429-4430`), `turn_branch` writes `origin_id or old_id` on every clone (`web/app.py:7227, 7259`),
  import copies it (F8); `core/db.py:2546-2551` itself says the shape is live.
- `:78` capture "pruned to `RETAIN_TURNS` per chat" — F15.
- `:146-150` "The v34 backfill charges existing rows `turn_idx * UNCLAIMED_BEAT_SECONDS`" — the v33→v34 migration
  is one ALTER and its comment says "EXISTING ROWS ARE LEFT NULL, DELIBERATELY" (`core/db.py:2027-2049`);
  `mind/memory_time.py:317` repeats the phantom backfill, and `core/db.py:2048` names
  `mind/memory_time.turn_clock_reading`, which does not exist (the function is `window_clock_readings`, `:320`).
- `:184-187` the `world` paragraph appears twice (the first copy lacks the time-of-day text) with a stray
  "character's first window." between them.

### F21 — Debug-capture docs still describe the deleted five-specialist Director, and the "safe" skeleton carries story text
- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- "five specialist(s)" as the live reason for the design: `persist/llm_capture.py:11, 205`,
  `persist/pipeline_trace.py:451, 459, 577`, `core/db.py:728` (the causal Director and its specialists were deleted
  2026-09-27 per CLAUDE.md).
- `web/app.py:2522` "`content=0` returns the hash-only skeleton, which is safe to paste into an issue … without
  carrying the story": `export_turn_debug` emits `warnings` and `decisions` verbatim regardless of
  `include_content` (`pipeline_trace.py:565-567`), and commit warnings carry names, drive text and interior quotes
  (`persist/commit_memory.py:1929` "interior leak -- {w}", `:2155` "DRIVE SHIFTED -> {essence}").
- **Fix:** update the prose; hash or drop `warnings`/`decisions` when `include_content` is false.

### F22 — "It costs one COUNT" — every restore makes a live embedding call
- **Severity:** STALE-DOC (and PERF, see P3). **Confidence:** CONFIRMED by reading.
- `persist/checkpoints.py:1297` and `start_rebuild_if_needed`'s docstring (`mind/memory_vectors.py:744-746`) promise
  one COUNT; `embedding_bank_status` first calls `embed_texts_meta(["status"], retry=None)` (`:64`), which with
  `retry=None` bypasses coalescing and memory (`llm/providers.py:5836-5846`). The startup comment
  (`web/app.py:206-208`) states the round trip correctly.

## Efficiency

**P1 — Unindexed foreign-key child columns make every turn deletion scan whole tables.** `world_events.turn_id`,
`world_entities.created_turn_id/retired_turn_id`, `room_registry.created_turn_id/retired_turn_id`,
`lorebooks.retired_turn_id`, `fiction_worlds.created/retired_turn_id` reference `turns(id) ON DELETE SET NULL` with
no index whose leading column is the FK (EXPLAIN: `SCAN world_events`, `SCAN world_entities`, `SCAN room_registry`,
`SCAN lorebooks`). Where: chat deletion (`persist/chat_delete.py:25-33`, one delete per turn row), `turn_del`,
`take_back`, stepless-turn discard. Measured on a scratch db: deleting a 1,000-turn chat while another chat holds
60k world_events / 20k entities / 5k rooms took **17.62 s** (inside the global write lock); with those columns
indexed **0.035 s**. The same holds for `frames(id)` children (`turns.frame_id`, `memories.frame_id`,
`room_messages.frame_id`, …) on frame deletion. Fix: `CREATE INDEX IF NOT EXISTS` (partial `WHERE col IS NOT NULL`)
in LATE_SCHEMA — no migration needed since LATE_SCHEMA runs on every open.

**P2 — Each checkpoint stores the canon book twice and every lore/summary vector inline.** `_snapshot_lore` dumps
the canon into `lore` AND into its `lorebooks` entry (`checkpoints.py:178, 182`); `lore` is read only for legacy
blobs without `lorebooks` (`web/app.py:7186-7194`). `dump_lorebook` and `dump_memory_summaries` inline base64
vectors (`mind/memory_snapshot.py:829, 760`) — memory vectors were moved to the content-addressed store for
exactly this cost; lore and summaries were not. Measured (`repro/r3.py`): a 200-entry canon at the 256-dim fallback
is 372 KB per copy, both copies in every checkpoint (one per turn); a real 1024+-dim model multiplies it. Fix: drop
the `lore` section from new snapshots (keep reading it), and address lore/summary vectors by content hash as
memories are.

**P3 — Every reroll pays a provider round trip.** `restore_checkpoint` → `start_rebuild_if_needed` →
`embedding_bank_status` probes the live model (F22) on every restore, ahead of the rerun's first stage; under
`turn_del` it is inside the write lock (F1). Fix: cache the probe's answer per process for a short TTL, or decide
staleness from the stored model key without a call.

**P4 — `turn_branch` holds the global write lock while parsing, deep-remapping and re-dumping every checkpoint up to
the branch point** (`web/app.py:6963` … `7408-7417`). Each blob is the whole world (DATABASE.md: a story's `charters`
row reached 41 MB), `_deep_remap_ids` walks every node, and nothing else in the process can write meanwhile
(`_write_lock` is a process-wide RLock with no timeout). Estimated minutes for a long, large story. Fix: compute the
remapped blobs outside the transaction (they depend only on id maps), or copy older checkpoints in a second,
bounded transaction.

**P5 — `_restore_books` rewrites a whole book when any entry differs** (`checkpoints.py:463-465`: compares the full
dump, embeddings included, then `restore_lorebook` updates every entry, each firing the FTS trigger). On the reroll
path a beat that ratified one canon claim rewrites the whole canon. Fix: restore only entries whose dump differs.

**P6 — Startup parses every scene row in the database** (`_recover_scene_time_of_day`, `core/db.py:2791-2830`, run
unconditionally by `init`): its gate is the key's presence, which it can only learn by `json.loads` of each scene.
Fix: filter in SQL (`json_type(value,'$.time_of_day') IS NULL`).

**P7 — Redundant indexes add a b-tree write per insert:** `idx_checkpoints_chat`, `idx_turns_chat_idx`,
`idx_memory_summaries_window` duplicate their tables' UNIQUE autoindexes; `idx_variants_step` is a prefix of
`idx_variants_active`; `idx_memories_chat_char` a prefix of three memory indexes; `idx_lorebook_links_source` a
prefix of `uq_lorebook_link`. Small per write; a drop is a migration (owner's call).

**P8 — A reroll discards out-of-band LLM work a spared job finished after the snapshot.** Only Room proposals have a
keep-spared path (`_keep_spared_room_work`); the room designer's cache `prose_contract_prepared_rooms`
(`agents/director_rooms.py:2119, 2656-2666`) and layout/lot run rows are restored from the snapshot, so a design that
landed between checkpoint N and N's reroll is paid for again. PLAUSIBLE cost leak on the most common action.

**P9 — `_file_pending` opens an empty write transaction per captured call** while any story holds pending capture
rows (`llm_capture.py:243-264`: the fast path tests the whole table, then `with transaction()` for a chat with none).

**P10 — `delete_chat_data` deletes variants one step at a time** (`chat_delete.py:18-23`); one
`DELETE … WHERE step_id IN (SELECT …)` does it.

**P11 — The about-backfill retries `skipped` rows on every startup** (`about_backfill.py:259-261` writes nothing for
them, `_untagged` lists them again) — and keeps the F1 window open each start. The module note says a row "is
computed once"; skipped rows are not.

## Already registered

- `memory_retrieval_fts` full scans by UNINDEXED `memory_id` on every memory write and twice per row in every
  restore — **UNBUILT_PLATFORM §1.172**. My scratch measurement agrees: 13.9 ms per lookup at 20k rows
  (`EXPLAIN: SCAN memory_retrieval_fts VIRTUAL TABLE INDEX 0`).
- `memories_fts` has no reader but is maintained by three triggers — **UNBUILT_PLATFORM §1.35**.
- `shadow_profile` and `standing_intentions` (both in `FRAME_SCOPED_WORLD_KEYS`) have no writer —
  **UNBUILT_PLANNING (line 638)**.
- `promotion_thresholds` absent from `SETTING_PROVENANCE` — **UNBUILT_IDENTITY §4 (line 961)** (F17 is its sibling).
- Deprecated `fiction_worlds` / `fiction_locations` / `transit_edges` removal — **UNBUILT_PARKED** and
  **UNBUILT_PLATFORM PERSISTENCE-F5 drop half** (F9's crash is a consequence the entries do not state).
- `_backfill_resource_uids` runs on every open, ungated — **UNBUILT_PLATFORM PERSISTENCE-F15 gate half**.
- `world_conditions` has no `frame_id` — **UNBUILT_PLATFORM RUNTIME-11**.
- Retired settings rows never pruned (§1.51b) — DATABASE.md's moved section / UNBUILT_PLATFORM.
- `transit_edges` in no archive/checkpoint/restore path — DATABASE.md and CLAUDE.md state it.

## Structure notes

- **Seam:** `persist/checkpoints.py` is four modules in one file: snapshot (`_world_rows`…`_snapshot_without_world`),
  restore (`_restore_*`, `insert_world_tables`, `_restore_checkpoint_body`, the setting/room keep-lists), compaction
  (`checkpoint_storage_status`…`start_compaction`, with module state `_COMPACT_STATE`), and blob patching
  (`ensure_checkpoint`, `propagate_*`, `carry_memories_forward`, `_carry_the_book_set`, `refresh_checkpoint`). The
  patchers are where the lock discipline differs (F16).
- **Monoliths in miniature:** `turn_branch` (`web/app.py:6913-7437`, ~520 lines, one transaction), `import_chat`
  (`persist/chat_archive.py:585-1205`, ~620 lines, one transaction), `_restore_checkpoint_body` (~190 lines),
  `_restore_books` (~150 lines).
- **Two remap implementations of one archive:** the live-row remap in `import_chat`/`turn_branch` and the blob remap
  in `_remap_cp_blob` must agree field by field; they have drifted before (`_remap_world_values` docstring, review
  A17) and F3 is a field both miss. A single "remap a snapshot dict" used for live rows too would hold them together.
- **Three restore policies for a removed era's rows:** import/branch drop a Room line whose frame did not come
  across; restore re-homes it to the present by FK (F12); overlays are filtered by held frames (`checkpoints.py:1239`).
- **Module-level mutable state:** `core/db.py` `_ERA_OF_FRAME` (era_of_frame / forget_frame_eras), `_world_epoch` +
  `_world_write_gen` (bump_world_epoch, `_wset_encoded`, `transaction` exit), `_local` (thread connection, depth,
  pending bumps), `_write_lock` (process RLock, no timeout), `DB` (rebound by `configure`; only read as `db.DB`
  elsewhere — no stale import found); `core/jobs.py` `_ACTIVE`/`_HISTORY` (per-chat history never pruned on chat
  delete); `core/outofband.py` `_QUEUES`; `core/code_version.py` `_snapshot`/`_status`/`_failures`;
  `persist/checkpoints.py` `_COMPACT_STATE`; `persist/about_backfill.py` `_CHAT_LOCKS` (a `defaultdict(Lock)`, never
  pruned, and the lock that inverts with `_write_lock` in F1).
- **Lock ordering is undocumented:** `_write_lock` (process) vs per-chat `_chat_lock` (about_backfill) vs `_REBUILD_LOCK`
  (memory_vectors) vs job cancellation. F1 is the first inversion found; a rule ("never take a per-chat lock while
  holding `_write_lock`") would make the next one findable by grep.
- `transaction()` catches `Exception` only: a `BaseException` (KeyboardInterrupt, GeneratorExit) raised inside the
  body releases `_write_lock` but neither commits nor rolls back, leaving the thread's connection in an open
  `BEGIN IMMEDIATE`. No `yield`/`await` inside a `with transaction()` was found (AST scan), so this is latent.

## Docs checked

- DATABASE.md "`transaction()`: outer BEGIN IMMEDIATE; nested calls use savepoints" — HOLDS (`core/db.py:2349-2391`).
- DATABASE.md "`qi`: write and commit immediately unless already inside a transaction" — HOLDS.
- DATABASE.md "`transit_edges` is named in exactly one place outside `core/db.py`" — HOLDS (`chat_delete.py:31`; column
  scan: zero mentions of its columns elsewhere).
- DATABASE.md `world_events` "Same-chat restore preserves ids…; import may preserve ids…; branching mints new event
  ids" — HOLDS.
- DATABASE.md "Checkpoints snapshot … `lore_overlays` and a library book as a reference, never its entries" — HOLDS.
- DATABASE.md `memory_vectors` rules (never GC'd; archive carries referenced vectors; `vkey` trigger) — HOLD.
- DATABASE.md `room_messages` "the turn checkpoint deliberately does NOT snapshot or restore it" — HOLDS, but see F12.
- DATABASE.md "Per-story card overrides … intentionally not rolled back by turn checkpoints" — HOLDS (`chars` snapshot
  carries state+status only; restore keeps a row with a sheet).
- DATABASE.md `chat_lorebooks.origin_id` "NULL on every new row" — FAILS (F20/F8).
- DATABASE.md capture "pruned to RETAIN_TURNS" — FAILS (F15).
- DATABASE.md "The v34 backfill charges existing rows…" — FAILS (F20).
- DATABASE.md `world` paragraph — duplicated (F20).
- DATABASE.md schema-change checklist item 6 (branch/clone remap when ids are embedded) — not met for
  `relationships:<char_id>` and charter bindings on import (F3), nor `origin_id` (F8).
- CLAUDE.md "checkpoint N is the world BEFORE turn N" (memory note, settled 2026-10-11) — HOLDS:
  `restore_checkpoint` docstring, `ensure_checkpoint` callers, `turn_branch` using `idx+1` as the world after `idx`,
  `carry_memories_forward` and `about_backfill` all agree; DATABASE.md does not state it either way.
- CLAUDE.md / memory note "a rerun deletes every later checkpoint" — HOLDS (`sweep_later=True` from
  `agents/runtime.py:1636`; `turn_del` deletes past the newest remaining turn, `web/app.py:7891-7898`).
- AGENTS.md "A checkpoint is established before a pipeline run mutates durable state" — HOLDS.
- AGENTS.md "Slow provider work belongs in preparation before the outer write transaction" — FAILS in `turn_del` (F1).
- `core/db.py:1` "migrations run in order from any older version" — FAILS below v7 (F18).
- `core/db.py` SCHEMA comment "`lorebooks.retired_turn_id` … does NOT mirror world_entities.retired_turn_id" — HOLDS
  (AUDIT_COMMIT §1.3's inert filter was removed; the column itself is still dead, F19).
- `core/outofband.py` "jobs.py has LANDED — offscreen, artifacts, checkpoints, commit_memory_write import it" — HOLDS.
- `persist/checkpoints.py:122-124` "isolated descendants … a reroll must restore exactly" — FAILS (F7).
- `persist/checkpoints.py:1297` "one COUNT" — FAILS (F22).
- `persist/about_backfill.py` "a row … is computed once" — FAILS for skipped rows (P11).
- `persist/llm_capture.py` / `pipeline_trace.py` five-specialist rationale — STALE (F21).

## Appendix — the carriage matrix

(a) archive export, (b) archive import, (c) checkpoint snapshot, (d) checkpoint restore, (e) branch/clone remap.
"by design" = documented deliberate exclusion.

| Table | a | b | c | d | e | Notes |
|---|---|---|---|---|---|---|
| chats | row | name/persona/scenario; lorebook via books; `branched_from` dropped (by design) | lorebook_id via lore | canon rebind | new row + lineage | |
| frames | ✓ | ✓ (parent 2nd pass) | ✓ | ✓ (update/insert/delete) | ✓ (ended-mark from snapshot) | |
| turns | ✓ | ✓ (frame remapped; commit_seq, offscreen verbatim) | — | carried beats deleted | idx≤branch; commit_seq cleared past held | |
| steps / variants | ✓ (variants without `reasoning`, by design) | ✓ | — | — | ✓ (with reasoning) | |
| events | ✓ | ✓ | — | deleted with turn | per copied turn | |
| world | ✓ minus `presence_id_namespace` | frame suffix, active_books, fixed_points, couples | ✓ (spliced text) | ✓ minus preserved settings + room briefs | ✓ + world-id deep remap (F10) | `relationships:<char_id>`, charter char ids not remapped on import (F3) |
| chat_chars | ✓ | ✓ | state+status | state+status; promoted rows swept | ✓ (membership from snapshot) | sheet/dialogue_color not rolled back (by design) |
| chat_char_frames | ✓ | ✓ | ✓ | ✓ — FK crash on deleted char (F2) | ✓ — same (F2) | |
| chat_personas | ✓ | ✓ (persona remap) | ✓ | ✓ | ✓ | |
| turn_player_inputs | ✓ | ✓ | — | — | idx≤branch | |
| memories | ✓ inline vectors | ✓ | ✓ vkey | ✓ delete+reinsert (ids re-minted, F4) | ✓ | |
| memory_summaries | ✓ | ✓ | ✓ (inline vectors, P2) | ✓ | ✓ | |
| memory_vectors | referenced set | ✓ | address only | resolved | same db | never GC'd (by design) |
| lorebooks / lore_entries | owned+attached+reachable; library bundled | ✓ — library parent lost (F13), origin_id foreign (F8) | owned+attached+reachable (canon twice, P2) | reachable only (F7) | owned cloned, fresh uids; library re-attached | |
| lorebook_links | ✓ | ✓ | ✓ | managed subgraph | ✓ | |
| lore_overlays | ✓ by entry_uid | ✓ | ✓ | ✓ (held frames) | ✓ | |
| chat_lorebooks | via books | ✓ | via books | ✓ | ✓ | |
| room_messages | ✓ | ✓ | — (by design) | — (frame SET NULL, F12) | up to branch turn | |
| world_events | ✓ | ✓ | ✓ | ✓ | new ids | |
| relationship_events | ✓ | ✓ (unmapped char dropped) | ✓ | ✓ | ✓ | |
| world_entities | ✓ | ✓ | ✓ | ✓ | new ids | `retired_turn_id` dead (F19) |
| world_placements | ✓ | ✓ | ✓ | ✓ | ✓ | decommissioned |
| world_conditions | ✓ | ✓ | ✓ | ✓ | new ids | |
| scheduled_events | ✓ | ✓ (payload frame) | ✓ | ✓ | new ids | |
| room_registry | ✓ | ✓ (turn/book remap) | ✓ | ✓ (book map) | ✓ | |
| fiction_worlds / fiction_locations | ✓ | ✓ — global PK crash (F9); turn ids dropped | ✓ minus turn ids | ✓ | new ids | deprecated (registered) |
| transit_edges | — | — | — | — | — | registered |
| checkpoints | ✓ | ✓ remapped | — | — | ≤branch remapped + final | |
| llm_capture / _pending / llm_blobs | — | — | — | — | — | by design; retention dead (F15) |
| guest_grants, lore_gen_jobs | — | — | — | — | — | by design |

World keys: all 31 `FRAME_SCOPED_WORLD_KEYS` and every non-frame key found by AST scan of `wget/wset` callers
(`persist_audit/wkeys2.txt`, ~95 keys) ride the `world` row on paths (a)-(d); exceptions are the two keep-lists above.
(e) remaps only the frame suffix, `active_books`, `fixed_points[].frame_id`, `couple:*` maps and scheduled-event
payload frames; integer ids inside any other value travel verbatim (F3).
