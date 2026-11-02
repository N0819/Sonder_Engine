# Audit — persist commit core: scene, registry, entities, attire, ledgers

Auditor scope: `persist/commit.py`, `commit_scene_state.py`, `commit_attire.py`,
`commit_entities.py`, `commit_mapping.py`, `commit_common.py`,
`commit_room_registry.py`, `commit_ledgers.py`, `commit_mechanics.py`,
`commit_destruction.py`, `commit_place_graph.py` (working tree at 84f3de23,
2026-11-01). Read-only; no repo file touched. Evidence scripts and their scratch
databases live in `.../scratchpad/persist_audit/` (`half_order.py`,
`checks.py`, `shed_ja.py`); every scratch DB was deleted after its run. The
owner's `engine.db` was only ever opened `mode=ro`. No pytest run was needed:
every CONFIRMED item below was reproduced with a snippet whose output is quoted.

## Scope read

Read in full (every line, comments included unless noted):

- `persist/commit.py` 1–947.
- `persist/commit_scene_state.py` 1–3092 (compose 1663–2436 and prepare
  2439–2971 line by line; helper blocks 43–1660 and the commit tail 2974–3092).
- `persist/commit_room_registry.py` 1–620.
- `persist/commit_entities.py` 1–644.
- `persist/commit_common.py` 1–738.
- `persist/commit_destruction.py` 1–414.
- `persist/commit_place_graph.py` 1–336.
- `persist/commit_attire.py` 1–260, 931–1797 in full; 260–930 read code-only
  (long comment blocks skimmed).
- `persist/commit_mapping.py` 1–420 in full; 420–860 code-only (comment
  blocks skimmed).
- `persist/commit_ledgers.py`, `persist/commit_mechanics.py` code-only with
  the docstrings (inline comment blocks skimmed).

Read for context (the parts named, not audited): `docs/experiments/AUDIT_COMMIT.md`
(all), `docs/guides/DATABASE.md` 1–140, 338–470, 565–640, `docs/guides/PIPELINE.md`
142–300, 1140–1160, 1281–1395, `core/db.py` (frame-scoped keys, `wget`/`wset`,
schemas of `world_entities`/`room_registry`), `world/charter_runtime.py` 680–1000,
3983–4002, `world/charter_ops.py` 351–384, `world/spatial_frames.py` 160–330,
`world/spatial_identity.py` 800–825, `world/paradox.py` 150–700 (scene writers),
`web/world_routes.py` 1680–1915, 2270–2350, `web/app.py` scene writers and
`world_put`, `story/plot_packages.py` 2140–2400, 4065–4150, `agents/director_lots.py`
297–420, `story/attire.py` 1120–1290, 2140–2310, 3132–3225, `story/scene.py`
238–310, 717–815, `persist/checkpoints.py` 740–830.

Not audited: `commit_background.py`, `commit_memory*.py`, `commit_skip.py`
(outside the assignment; touched only where a scene writer lives there).

## Findings

Severity counts: CORRUPTION 5, WRONG-SCENE 5, LEAK 1, SILENT-NOOP 3,
STALE-DOC 5, DEAD 1 (20 findings). PERF items are in `## Efficiency`.

### F1 — A refused charter order half-lands inside the commit, and the Director is told nothing was dispatched

- **Where:** `persist/commit_scene_state.py:3021-3066` (`_apply_charter_orders`,
  called at 3004 inside `commit_scene`'s transaction); mechanism in
  `world/charter_runtime.py:810-825` (`registry_for_update`) and
  `world/charter_ops.py:351-379` (`apply_charter_ops`).
- **Code:**
  ```python
  # commit_scene_state.py
  try:
      landed = author_charter_ops(ctx.chat.id, ctx.turn.frame_id, ops, by="director", ...)
  except Exception as exc:
      ctx.add_warning("charter ops not landed: %s" % exc)
      ctx.tell_director("The institution refused this beat's order and nothing was "
                        "dispatched (%s). ..." % exc)
  # charter_runtime.registry_for_update
  entry = _session_entry(cid, frame_id, create=True)
  if entry is not None:
      return entry["registry"]          # the SESSION's shared copy
  ```
  `apply_charter_ops` mutates its registry argument op by op and raises at the
  first refusal ("ALL OR NOTHING at the caller's level ... the caller never
  saves").
- **Failure:** every commit runs inside `registry_session()` (commit.py:556).
  There `registry_for_update` hands back the session's shared parsed copy, not a
  private one, so ops 0..k-1 of a refused event are already applied to the copy
  that `flush_registry_session()` (commit.py:681) writes. The flush writes any
  entry marked dirty — and `_apply_charter_placements` (3003, one line earlier)
  marks it dirty on every beat that moved a townsperson, as does any later
  carrier/observation writer. Result: half an authored event lands (the very
  "town whose ledgers disagree with the sentence that made them" the docstring
  forbids), while the Director is told "nothing was dispatched".
- **Verified:** CONFIRMED. `half_order.py` builds the caravanserai fixture from
  `tests/test_charter_ops.py`, opens `transaction()` + `registry_session()`,
  dirties the entry the way `apply_scene_placements` does, calls
  `author_charter_ops` with `[vacate_post cook, errand body:"nobody"]`, flushes:
  ```
  refused as documented: op 1 (errand): charter 'caravanserai' holds no body 'nobody'
  watch['cook'] before: yusra | after the REFUSED event: None
  ```
  `tests/test_charter_ops.py::test_a_refused_event_writes_nothing` passes only
  because it runs outside a session.
- **Class:** `registry_for_update`'s docstring promises mutations "are discarded
  with the object when the caller abandons them, which several writers (carrier
  ingest, caravan trade, public evidence) rely on" — false for every one of them
  inside a commit.
- **Severity:** CORRUPTION. Not registered (UNBUILT_LIVING_WORLD.md:2194-2203
  describes the landing as all-or-nothing).
- **Fix:** inside a session, `registry_for_update` should return a deep copy and
  `save_registry` should swap it into the session entry (or `author_charter_ops`
  applies to `copy.deepcopy` and assigns back on success). Test: in
  `registry_session()`, dirty the entry, call `author_charter_ops([valid,
  invalid])`, flush, assert the registry unchanged.

### F2 — A garment with a non-Latin name vanishes when taken off; two non-Latin owners share one shed object

- **Where:** `persist/commit_attire.py:768-772` (`_mint_shed_garments`), then
  `1794-1796` (`release_removed_garments`).
- **Code:**
  ```python
  key = re.sub(r"[^a-z0-9]+", "_", str(garment).casefold()).strip("_")
  if not key:
      continue
  key = "%s_%s" % (key, re.sub(r"[^a-z0-9]+", "_",
                               str(owner).casefold()).strip("_"))[:60]
  ```
- **Failure:** in a Japanese story a garment named 上着 folds to `""`, so no
  floor object is minted; the removed seat is then deleted by
  `release_removed_garments` ("AFTER the mint, never before ... the seat is a
  duplicate"). The garment leaves the world entirely — the exact failure the
  function's docstring exists to prevent ("Clothes that vanish when removed
  cannot be picked up"). With an ASCII garment name and kana owner names, every
  owner folds to `""` and the keys collide: the second body's jacket is stamped
  onto the first body's object (`worn_by` stays the first owner).
- **Verified:** CONFIRMED, `shed_ja.py`:
  ```
  'Hinami' 'jacket' -> ['jacket_hinami']
  'ヒナミ' '上着' -> [] | diff: []
  two owners -> {'jacket_': 'ヒナミ'}
  ```
  Japanese is a shipped, protocol-parity language pack.
- **Severity:** CORRUPTION (+ language-pack hazard). Not registered.
- **Fix:** mint the key with a script-aware fold (`fold_identity_key`, which
  returns `上着` unchanged) or `new_uid`, and never let an empty owner fold
  collapse two owners. Test: `_mint_shed_garments(sc, [("ヒナミ","上着","")], {})`
  mints one positioned entity; two kana owners shedding "jacket" mint two.

### F3 — The world editor writes scene entities and never re-projects `world_entities`

- **Where:** `web/world_routes.py:1723-1746` (`_write_scene`), used by
  `room_entity_create` (2270-2304), `room_entity_patch` (1819-1914, `kind`,
  `description`, sources, `room`) and `room_entity_delete` (2306-2348);
  `web/app.py:5833-5869` (`world_put`, the raw JSON editor).
- **Code:**
  ```python
  with transaction():
      wset(cid, "scene", scene)
      sync_room_registry_with_scene(cid, chat.get("lorebook_id"), before, scene)
  ```
- **Failure:** the registry projection is reconciled; the entity projection is
  not. Delete a thing in the browser and its `world_entities` row stays;
  create one and it has no row until some beat names it in a diff; change its
  `kind` and the row keeps the old one. `world_entities` is read for
  `paradox._entity_exists` (fixed points, `world/paradox.py:184-192`) and
  `_entity_alias_map`. A host who deletes an entity a fixed point requires
  absent never trips the paradox; one who creates an entity a fixed point
  requires present trips a paradox on the next commit for a thing standing in
  the room. `world/paradox.py:375-380` calls the pair "every scene writer owes".
- **Verified:** CONFIRMED by reading all three routes and `world_put`; measured
  read-only on `engine.db`: 85 of 1,208 scene entities (25 chats) have no row.
- **Severity:** CORRUPTION. Not registered (AGENTS.md:880 and DATABASE.md:344
  only name the registry for the editor).
- **Fix:** a `sync_world_entities_with_scene(cid, before, after)` sibling of
  `sync_room_registry_with_scene`, called from `_write_scene` and `world_put`
  (insert/update rows for added/changed entities of this frame, delete rows only
  for entities this write removed). Test: POST then DELETE
  `/rooms/{room}/entities` and assert the row appears and disappears.

### F4 — The commit's own scene-only mints and folds bypass the entity projection

- **Where:** mints into the scene only: `materialize_plans_in_sight`
  (`persist/commit_scene_state.py:2786-2789` → `world/planned_entities.py` writes
  `entities[key] = record`), `ensure_cast_entities` (1857). Folds that pop scene
  entities without a `remove_entities` entry: `_fold_duplicate_shed_garments`
  (`persist/commit_attire.py:444-447`), `_fold_worn_garment_entities` (531-533),
  `_reclaim_worn_shed_garments` (1003-1005). And the merge's own fold:
  `_dedup_duplicate_entity_keys` re-keys an id-keyed record onto its display
  name, after which `commit_world_entities._projected`
  (`persist/commit_entities.py:376-391`) falls back and UPSERTs a row for the
  folded-away id (429-447).
- **Code:** `commit_world_entities` projects `diff["entities"]` and deletes only
  `diff["remove_entities"]` (`commit_entities.py:409-498`). `_mint_shed_garments`'
  own docstring states the rule the others break (commit_attire.py:730-733):
  "an entity minted only here would live in the runtime scene and be absent from
  the normalized table -- the one divergence Phase 3a exists to prevent."
- **Failure:** a planned thing stood up by the commit, or a cast record created
  by the heal, exists in the scene with no row (paradox reads it as absent); a
  shed garment folded or reclaimed keeps its row forever (`tools/reproject_
  world_entities.py` deliberately leaves rows absent from the blob alone); a
  beat that writes `entities: {"char_9f13": {"name": "Bramwell"}}` against a
  scene keyed `Bramwell` gets a phantom `char_9f13` row.
- **Verified:** CONFIRMED (mechanism). `checks.py` §4: merging that diff into a
  scene keyed `Bramwell` yields `merged entity keys: ['Bramwell']`, so
  `_merged_entities.get("char_9f13")` is None and the fallback writes the row.
  Read-only corpus: 11 of 1,069 rows (9 chats) name no entity any scene of their
  chat holds, one of them a folded twin; 0 are garments today, so the attire
  half is unmeasured in the corpus.
- **Severity:** CORRUPTION (low incidence). Not registered.
- **Fix (class):** every pass that adds or removes a scene entity after the diff
  writes the same change to `diff["entities"]` / `diff["remove_entities"]` (the
  `_mint_shed_garments` rule), and `_projected` skips an id the merged scene
  does not hold instead of minting it. Test: a commit whose
  `materialize_plans_in_sight` stands a plan up produces a row; reclaiming a shed
  garment deletes its row.

### F5 — The duplicate-mint fold runs after the beat was perceived and narrated

- **Where:** `persist/commit_scene_state.py:2908` (`_fold_duplicate_mints`, in
  `prepare_scene_commit`); absent from `compose_beat_scene` (1663-2436), which is
  what `perception_outcome` composes (`agents/perception.py:4139-4142`).
- **Code:**
  ```python
  _record_failed_sources(ctx, cid, sc, _turn_idx)
  _fold_duplicate_mints(ctx, cid, sc, prev_scene, diff)
  _place_orphan_mints(ctx, cid, sc, diff)
  ```
- **Failure:** the composition the narrator and every memory episode read holds
  the mint beside the thing it duplicates (Flat 4B's `door_buzzer` +
  `intercom_buzzer`); the commit folds it afterwards. Every view of the beat
  shows two buzzers and the world keeps one; memories cite a thing that no
  longer exists. PIPELINE.md:1144-1156 says the composition is "the Director's
  diff deduped and guarded ... the two sides cannot disagree by construction".
  REVIEW_2026-09-07 A67's rule was "fold on the DIFF before the merge"; the
  `_apply_entity_renames` half landed, the timing did not. Its sibling
  `_place_orphan_mints` was moved forward for exactly this "WHEN" reason (B15,
  `agents/director_floors.py:1484-1495`).
- **Verified:** CONFIRMED by trace (compose has no fold; no Director floor folds
  alias mints — grep for the fold or its label helpers outside this file finds
  none).
- **Severity:** WRONG-SCENE. Not registered.
- **Fix:** run the fold in `compose_beat_scene` against `prev_scene` and the
  diff before `merge_scene_with_diff`, keeping `_apply_entity_renames`. Test:
  compose a beat minting a key that a standing entity carries as an alias; assert
  the composed scene (perception's stash) already holds one entity.

### F6 — A redirected room key survives in every channel `_apply_room_renames` does not list

- **Where:** `persist/commit_room_registry.py:78-133`.
- **Code:** rewrites `causal_steps` patches, `rooms`, `adjacent[].to`,
  `positions`, `remove_rooms`, `remove_adjacent`, `interior_rooms`,
  `state.transit` — nothing else.
- **Failure:** when `dedup_minted_rooms` redirects `deck_three` onto `deck_3`,
  the same beat's `sensory_events[].room`, `inventory_ops[].to_id`,
  `substance_ops` room targets, `movement_refused[].to_room`, `poses[].support`
  (a room-valued support), `charter_ops`/`crowd_ops` rooms keep `deck_three`.
  `_record_sensory_events` then drops the event as naming "a room this scene does
  not hold" (and perception's normaliser does the same), so the beat's noise is
  heard nowhere; a set-down "onto deck three" resolves nowhere and stays in the
  hand.
- **Verified:** CONFIRMED, `checks.py` §1: after
  `_apply_room_renames(diff, {"deck_three": "deck_3"})` only `positions` and
  `rooms` moved; `sensory_events`, `inventory_ops`, `movement_refused`, `poses`
  still say `deck_three`.
- **Severity:** WRONG-SCENE. Not registered. The entity sibling states the class
  (`commit_scene_state.py:793-799`: "A per-channel rewrite would have to be
  extended by hand ... which is how the room sibling's own list grew").
- **Fix:** rewrite room keys by the same any-string walk `_apply_entity_renames`
  uses, restricted to room-valued positions of the walk (values, not entity-keyed
  dict keys). Test: redirect a minted room in a diff carrying a sensory event and
  a transfer to it; assert both land in the surviving room.

### F7 — Room identity by name is ASCII-only, so a room named in kana/kanji never dedups

- **Where:** `world/spatial_identity.py:800-825` (`room_spellings`, folding with
  `normalize_room_id` = `re.sub(r"[^a-z0-9]+", "_", ...)`), consumed by
  `persist/commit_room_registry.py:196-213` (`dedup_minted_rooms`), 47-53
  (`_room_display_slug`), 55-76 (`_registry_alias_index`).
- **Failure:** a room whose name is 古い蔵 answers only to its ASCII id. A beat
  that re-mints it under another id (`kura` vs `old_storehouse`) is not
  redirected, so a Japanese story accumulates duplicate rooms the B2 rule
  ("ONE identity per room: a room answers to its name and to its id") was built
  to stop; the registry alias index likewise drops every non-Latin name.
- **Verified:** CONFIRMED: `room_spellings('kura', {'name': '古い蔵'}) ==
  ('kura',)`; `normalize_room_id('上着') == ''`.
- **Severity:** WRONG-SCENE (language-pack hazard). Not registered.
- **Fix:** add a script-aware folded name (`fold_identity_key`) to
  `room_spellings` only — not to `normalize_room_id`, which mints ids. Test: two
  mints with different ids and the same Japanese name redirect onto one.

### F8 — The commit records the PRESENT era's creature noises into any frame's scene

- **Where:** `persist/commit_scene_state.py:1377-1381`.
- **Code:** `incoming.extend(charter_noises(registry_for(cid)))` — no frame,
  so `registry_for` reads the present era's town; perception reads the beat's
  own (`agents/perception.py:7899-7903`:
  `registry_for(ctx.chat.id, getattr(ctx.turn, "frame_id", None))`).
- **Failure:** in a frame of another era (a flashback with its own town), the
  stored `scene.sensory_events` carry present-era creature noises wherever room
  ids coincide (same house, two eras), and `world/charter_runtime.py:3781-3786`
  feeds the stored record to that era's creatures (`hearing_for_creatures`).
  Two readers of one fact disagree by frame. Bubbles of the present era are
  unaffected (same era).
- **Verified:** CONFIRMED by reading both call sites and `registry_for`'s
  default.
- **Severity:** WRONG-SCENE (narrow). Not registered.
- **Fix:** pass `getattr(ctx.turn, "frame_id", None)`. Test: two-era registry,
  commit in the non-present era, assert only that era's noises are stored.

### F9 — Typed introductions teach a name to a mind that is asleep, and fail open on unplaced bodies

- **Where:** `persist/commit_mapping.py:802-853`.
- **Failure:** the floor checks roster membership, on-stage membership and "same
  room when both can be placed" (`if who_room and learns_room and who_room !=
  learns_room: continue` — an unplaced body passes). It never asks whether `who`
  is awake (`_is_gated_awareness` / `story.scene.awareness_map`), so an encoder
  row `{who: <asleep or unconscious>, learns: X}` writes a recognition edge into
  `known` that perception will honour from then on. The hearing path
  (`_names_heard_in`) is perception-gated; this path is model-gated only.
- **Verified:** PLAUSIBLE (read the gate; not reproduced against a live encoder
  output).
- **Severity:** LEAK (a channel-less fact if the model writes the row). Not
  registered.
- **Fix:** refuse an introduction whose `who` holds a gated awareness condition
  this beat, and warn. Test: asleep `who` + introduction row → `known` unchanged.

### F10 — `known_to` is inherited from one of the two shapes its reader accepts

- **Where:** `persist/commit_entities.py:193-206` (`_inherit_known_to`) vs
  `story/scene.py:771-799` (`disguises_from_rows`).
- **Code:** writer: `state = payload.get("state"); if not isinstance(state, dict)
  or state.get("known_to"): return`, and priors read only
  `prior["state"]["known_to"]`. Reader: `pick = lambda k: state.get(k) or
  payload.get(k)`.
- **Failure:** a superseding disguise written flat (fields at the payload's top
  level, which the reader accepts) inherits nothing; supersession deactivates the
  old rows; the observer who had been told is fooled again — the chat 74 defect
  the inheritance exists for (a mind concluding less than it knows).
- **Verified:** CONFIRMED mechanism, `checks.py` §3: state-shaped row inherits
  `['The Doctor']`; flat row inherits nothing; `disguises_from_rows` then reports
  `known_to: []`. Incidence: 0 of 30 disguise/transformation rows in `engine.db`
  are flat (read-only count).
- **Severity:** WRONG-SCENE (rare). Not registered.
- **Fix:** read with the reader's `pick` rule on both sides and write into
  `state` (creating it). Test: the two-row supersession above with a flat new row.

### F11 — The living-world consequence block swallows a failure inside the turn's transaction without a savepoint

- **Where:** `persist/commit_mechanics.py:286-320` (inside
  `commit_transit_sweep`'s `with transaction():`).
- **Failure:** `mint_consequences`, the per-row `qtx` INSERT loop and
  `record_obligations` share one `try/except Exception → add_warning`. An
  exception after some INSERTs (or inside `record_obligations` after a partial
  write) leaves those writes in the outer transaction and the turn commits —
  the one place in the transit domain where "any domain failure rolls the whole
  turn back" becomes "half of this block lands".
- **Verified:** PLAUSIBLE (structure read; no failing input constructed).
- **Severity:** CORRUPTION (partial write, low likelihood). Not registered.
- **Fix:** `with transaction():` (a savepoint) inside the `try`, so a failure
  rolls back the block it warns about. Test: patch `record_obligations` to raise
  after a mint; assert no consequence row survives and the turn commits.

### F12 — The twenty-beat canon lock runs only on beats the mapping commit does not skip

- **Where:** `persist/commit_mapping.py:645-660` (skip branch returns) vs
  `730-738` (the lock).
- **Code:** `UPDATE lore_entries SET canon_locked=1 WHERE lorebook_id=? AND
  turn_added IS NOT NULL AND turn_added<=?` is reached only when
  `prepare_mapping_commit` found introductions, planning needs or the opening
  premise.
- **Failure:** since 2026-09-03 no lore is filed here, so "nothing new to
  commit" is the ordinary beat; the lock then waits for the next beat that
  happens to carry an introduction or a need. AGENTS.md:540 ("the twenty-beat
  canon lock on the story's own book") and Design.md:540 ("chat-canon entries
  auto-lock after 20 turns") describe a per-beat rule. `canon_locked` is honoured
  by `story/importers.py:2026,3104` and the Room tools.
- **Verified:** CONFIRMED by reading the early return.
- **Severity:** SILENT-NOOP (a lag, not a loss). Not registered (UNBUILT_PLATFORM
  §2.5 registers the unbuilt repeated-reference rule, not this).
- **Fix:** run the idempotent UPDATE in the skip branch too. Test: a skipped
  mapping commit at turn 25 locks an entry added at turn 1.

### F13 — DATABASE.md says a sibling frame's commit revives a retired room; since B8 it never does

- **Where:** `docs/guides/DATABASE.md:347` vs
  `persist/commit_room_registry.py:341-359`.
- **Code:** `revive = not row_retired or rid not in prev_rooms`.
- **Failure:** the doc: "A room retired in one frame's commit may legitimately
  still be live in a sibling frame's blob; that frame's next commit re-registers
  it (upsert revives)". The code revives only where the room's live existence
  BEGINS this beat, so a sibling frame that still holds the room keeps a retired
  row for it forever (and the planned/alias readers that filter retired rows stop
  seeing it there).
- **Verified:** CONFIRMED, `checks.py` §2: a retired `hall` live in both
  pre- and post-scene yields no upsert, and a rename yields an upsert with
  `'revive': False`.
- **Severity:** STALE-DOC (and an unruled semantic: is retirement global across
  frames? — the owner's call). Not registered.
- **Fix:** correct the DATABASE.md sentence to the B8 rule, or scope the B8 rule
  to the frame that retired the row. Test: pin whichever rule is chosen.

### F14 — Domain, scheduler and module counts are stale: `skip_lives` is in no list

- **Where:** `docs/guides/PIPELINE.md:1334-1384` ("twenty durable domains",
  numbered 1-20), `PIPELINE.md:1395` ("Eleven schedulers live there today, in
  order: ..."), `CLAUDE.md:103` ("twenty domains", "thirteen `commit_*`
  modules"), `Design.md:725` ("twenty domains").
- **Code:** `persist/commit.py:575-583` runs `skip_lives` between scene and
  entities (21 domains); the tail (`commit.py:700-921`) runs fourteen schedulers
  — consolidation, skip memories, offscreen beats, memory tension, planning
  needs, room work, room predevelopment, plot packages, promotion, charter ticks,
  profile ticks, agent ticks, artifact wording, extension hooks; `persist/` holds
  fourteen `commit_*` modules (`commit_skip.py`).
- **Verified:** CONFIRMED by reading.
- **Severity:** STALE-DOC. Fix: add `skip_lives` as domain 4 (AGENTS.md:490 already
  routes it), recount, list the three missing schedulers in code order.

### F15 — PIPELINE.md's S3-A8 trigger describes the reverted concealed-actor reading

- **Where:** `docs/guides/PIPELINE.md:1351-1355` vs
  `persist/commit_entities.py:332-345, 393-417`.
- **Failure:** the doc: "an entity state blob referencing a concealed actor
  raises a 'possible stale clause (S3-A8)' warning". The code's comment says that
  reading was the reverted one; the live check warns when the beat's prose names
  the entity AND its `posture`/`description` came through byte-identical.
- **Verified:** CONFIRMED. **Severity:** STALE-DOC. Fix: restate the trigger.

### F16 — `_entity_alias_map` documents an insertion-order tiebreak its query does not have

- **Where:** `persist/commit_common.py:567-571` (comment), `580-583` (query, no
  `ORDER BY`).
- **Failure:** union semantics make the first row registered the canonical id
  for a shared key ("Row order is the deterministic tiebreak (world_entities
  first, insertion order)"). SQLite answers in index order: `EXPLAIN QUERY PLAN`
  on `engine.db` shows `idx_world_entities_chat_kind`, and on the largest chat
  the returned order differs from rowid order. Which vehicle id a book anchors to
  on a collision is decided by the plan, not by age.
- **Verified:** CONFIRMED (read-only EXPLAIN). **Severity:** STALE-DOC. Fix:
  `ORDER BY rowid`.

### F17 — `attire.decisive_intent` is test-only, and `_DECISIVE`'s comment describes the pre-inversion ladder

- **Where:** `story/attire.py:1282-1285` (`decisive_intent`), `1137-1140`
  (comment: "the one thing that lifts the one-step-per-beat rule").
- **Failure:** no production caller (grep over the tree incl. `tools/`,
  `extension_runtime/`, `extensions/`: only `tests/test_attire_displacement.py`
  and `tests/test_attire_regions.py`). Since the clamp was inverted (removals
  land unless `_PROCESS` fires), `decisive` lifts only a process reading in the
  same beat (`apply_flat_change(..., decisive=name in _decisive_names)`,
  `persist/commit_attire.py:1594-1598`).
- **Verified:** CONFIRMED. **Severity:** DEAD. Fix: delete the wrapper or move it
  to the tests; reword the comment.

### F18 — Planning-need relevance tests are ASCII- and space-based

- **Where:** `persist/commit_mapping.py:421-427` (`_need_words`:
  `re.findall(r"[a-z0-9]+", ...)`), `430-444` (`_reads_as_prose`: punctuation
  followed by whitespace, `len(text.split()) > 12`).
- **Failure:** a Japanese subject yields no words, so the beat's own bodies never
  answer it, and a Japanese sentence (no spaces; 、。 not followed by whitespace)
  is never read as prose — so a ja beat files sentence-shaped needs for the
  Writers' Room. Fails toward filing (the module's chosen safe direction): noise,
  not loss.
- **Verified:** PLAUSIBLE (read; not run on a ja beat). **Severity:** SILENT-NOOP
  (language-pack). Fix: tokenise with the script-aware boundary the attire gate
  uses (`attire._named_pattern`'s `_UNSEGMENTED` rule).

### F19 — The overlay-condition guard reads one of the overlay channel's shapes

- **Where:** `persist/commit_attire.py:1025-1042` (`_overlay_texts_by_subject`).
- **Failure:** it keys by the record's `subject` and reads only `description`,
  while overlays are written as bare lines, under `name`/`desc`/`text`, and keyed
  by the body without a `subject` (`commit_scene_state.py:431-461` names all of
  these). A garment condition that duplicates such an overlay is kept, which is
  the chat 82 defect `_drop_overlay_conditions` exists for.
- **Verified:** PLAUSIBLE (read). **Severity:** SILENT-NOOP. Fix: build the set
  with `_overlay_handles` per map key.

### F20 — The cast-change warning names two words the reader no longer limits itself to

- **Where:** `persist/commit_mechanics.py:499-502` ("expected 'active' or
  'dormant'") vs `story/scene.py:250-272` (twenty accepted protocol words).
- **Verified:** CONFIRMED. **Severity:** STALE-DOC (diagnostic text). Fix: name the
  two meanings and that synonyms are accepted.

## Efficiency

Measured on `engine.db` (read-only): scene rows median 16.7 KB, p90 42.7 KB, max
56.2 KB; at the max, `json.loads` 0.90 ms, `copy.deepcopy` 2.40 ms, `json.dumps`
0.71 ms. `room_registry` max 22 rows / 27.5 KB per chat. So nothing here is hot
on the owner's stories; ordering is by cost-to-fix over gain.

1. **The scene is re-parsed inside the write lock on every beat** (Q6). Per
   ordinary beat, in-lock parses: transit sweep `prev_scene`
   (`commit_mechanics.py:129`), world pressure (`commit_ledgers.py:537`, parsed
   unconditionally and used only for `tick` ops), background presences
   (`commit_background.py:2229`), plus one per other live frame of the era
   (`town_for_sweep`, `commit_mechanics.py:63`), plus needs/introductions
   (`commit_mapping.py:537, 794`) when present, plus paradox/spatial
   reconciliation when active. Serialisations: `commit_scene` once, and
   `track_background_presences` up to twice more (departures then handovers, two
   whole-scene `wset`s, `commit_background.py:2685, 2698`). Pre-lock: one parse
   at composition (in `perception_outcome`, reused by the commit when
   `compose_beat_key` holds). Gain ≈ 3-5 ms of lock time per beat at 56 KB;
   cheapest first: make `commit_world_pressure` parse lazily (or read
   `prepared["scene"]["scene"]`), and merge the two background writes into one.
2. **Deep copies of the scene per beat:** the diff copy (`commit_scene_state.py:1700`),
   the merge's copy, perception's two (`agents/perception.py:4156-4158`), and —
   when a diff carries k ≥ 2 inventory ops — k whole-scene re-merges in
   `_refuse_unheld_transfers` (`commit_scene_state.py:1166-1173`), O(ops ×
   scene) at ~2.4 ms each. Merging only the moved subject's records would do.
3. **Registry projection reads the chat's whole registry with payloads** every
   beat (`commit_room_registry.py:287-290`, `SELECT *`), parsing aliases and
   payload JSON per live room, and `_anchored_book_ids` runs twice per beat
   (dedup 161, prepare 271); `_apply_room_registry` costs two SELECTs per upsert
   (404-421). Negligible at 22 rows; scales with planted towns whose payloads
   carry `planned` layouts. Select only `room_uid, owning_book_id, parent_entity,
   name, aliases, retired_turn_id` plus `payload` for live ids.
4. **`_beats_open` issues a COUNT per ledger entry** (`commit_ledgers.py:113-117`),
   from `pending_obligation_view` (≤12 per Director payload) and twice over the
   ledger in `commit_obligations` (overdue, evictions). One query for the other
   frames' turn indices in (min opened, now] answers all of them.
5. **N+1 in `commit_world_entities`:** a SELECT per diff entity (418-419) and per
   condition (577-579); one `IN (...)` each.
6. **`update_place_graph` scans every room's adjacency per character per beat**
   to find doorways into the standing room (`commit_place_graph.py:154-164`):
   O(rooms × edges × cast). A reverse-adjacency index built once per commit.
7. **`_chat_book_graph` reads every chat's `currently_within` links**
   (`commit_destruction.py:72-80`) — destruction beats only; join on the chat.
8. **`sync_anchored_books` runs two queries per anchored book per beat**
   (`commit_scene_state.py:262-306`); fold into one join. Small.

## Already registered

- `world_pressures` is chat-wide while `pending_obligations` is frame-scoped —
  UNBUILT_PLATFORM §1.58 (PERSISTENCE-F17). That row also lists `engine_notices`,
  which `core/db.py` has since frame-scoped (the 2026-09-23 comment in
  `FRAME_SCOPED_WORLD_KEYS`): the register row is half stale.
- The world-pressure channel has no owning hand and the must-tick retry is
  inert — UNBUILT_PIPELINE §1.164 ("This is the 'world acts' floor, and it is
  off").
- `world_conditions` has no frame column — UNBUILT_PLATFORM §1.58 (RUNTIME-11).
- Attire prose readers (Q4): `_DECISIVE`, `_DECISIVE_GAP_OFF`, `_REMOVAL_PHRASE`,
  `_PROCESS`, `_CLOTHING_CONTEXT`, `_DISPLACEMENT_ANCHORS` (`story/attire.py:1141-1243,
  2148-2160`) are still English word tables over free prose. The clamp is
  inverted, so a missing COMPLETION word now fails safe (the removal lands unless
  process language fires), and a ja beat gets the mildest reading (both tables
  fail open; `tests/test_attire_write_gate.py:378-387` states it). The surviving
  class — a process word and a garment co-occurring in one sentence about
  different acts — is UNBUILT_PIPELINE §1.112; prose matching as a boundary is
  §3.1. Only the dead wrapper (F17) is new.
- The place graph's `told` basis is a recorded decision — UNBUILT_WORLD §6.5
  (`commit_place_graph.py:74-85`).
- S3-A8 (entity `state` never ages; copy-forward) — UNBUILT_WORLD §1.10.
- Canon lock's repeated-reference rule — UNBUILT_PLATFORM §2.5.

## Structure notes

**Q1 — every scene writer and its two projections** (`room_registry` /
`world_entities`):

| Writer | registry | entities | Note |
| --- | --- | --- | --- |
| `commit_scene` (`commit_scene_state.py:2974-3006`) | yes, same domain (`_apply_room_registry`) | yes, `entities` domain from the prepared diff | but see F4 (scene-only mints/folds) |
| checkpoint restore (`persist/checkpoints.py:740-830`) | snapshot rows restored | snapshot rows restored | consistent with the restored blob |
| World Browser `_write_scene` (`web/world_routes.py:1723-1746`) | yes (`sync_room_registry_with_scene`) | **no** | F3 |
| `world_put` raw editor (`web/app.py:5833-5869`) | yes, per scene key | **no** | F3 |
| `chat_edit` / `chat_add_char` / `chat_add_persona` / `attire_put` / `survival_put` / `chat_char_position_put` (`web/app.py`) | n/a (attire, vitals, positions) | n/a | `chat_add_char` persists `get_scene`'s read-time overlays |
| `world/paradox.py` warden and force-restore | n/a (no rooms) | yes (`_project_entity_row`, DELETE) | |
| `world/spatial_frames.py` split/merge/fuse | chat-wide table, rooms already registered | chat-wide table | |
| `story/plot_packages.py` `set_vistas` / `set_far_looks` (2172-2190, 2344-2392) | n/a (no identity fields) | n/a | publish runs out of band without the commit lock (`story/room_tools.py:1395`); a publish between a turn's prepare and its `commit_scene` is overwritten by the commit's whole-blob `wset` — the lost-update hazard PIPELINE.md:1395 itself names for promotion (PLAUSIBLE; outside this audit's files) |
| `persist/commit_background.py` departures/handovers (2685, 2698), promotion (5213-5216) | n/a | payload drift only (rows not re-projected) | not audited |
| `world/structure.plant_structure` / `director_lots.expand_lot` | writes registry rows (planned); scene gets stubs at the next commit's fringe | n/a | `deal_berths` (`director_lots.py:306-332`) saves the charter registry out of band with no epoch/base-turn guard |
| `director_rooms` predevelopment | never writes the scene (cache only; installed in band at interpret) | via commit | |

**Monoliths in miniature:** `compose_beat_scene` (~774 lines,
`commit_scene_state.py:1663-2436`); `prepare_scene_commit` (~533, 2439-2971);
`apply_attire_diff` (~706, `commit_attire.py:1091-1797`); `commit_world_entities`
(~360, `commit_entities.py:282-644`).

**Natural seams.** `commit_scene_state.py` grew from 709 lines at the split to
3,092: an overlay ledger (431-679), a mint block (`_minted_this_beat`,
`_apply_entity_renames`, `_fold_duplicate_mints`, `_place_orphan_mints`), a
carriage block (`derive_borne_containment`, `_refuse_unheld_transfers`), a sound
block (`_record_failed_sources`, `_record_dulled_hearing`, `_record_sensory_events`,
`_report_started_sources`), the composition (`ComposedBeat` … `compose_beat_scene`),
the tick (`_advance_day_cycle`, `_advance_ground`, `prepare_scene_commit`) and the
write (`commit_scene`, charter apply, last seen). `apply_attire_diff` splits at its
own "doors": write gate (1179-1329), omission guard (1330-1423), channel
application (1424-1520), coverage/steal guard (1527-1592), ladder feedback
(1593-1669), notes rebuild and shed bookkeeping (1670-1797).

**Module-level mutable state:** only `persist/commit.py:207-208`
(`_COMMIT_LOCKS`, a `WeakValueDictionary`, and its guard), written only by
`_commit_lock`. No `global` rebinds in any audited file.

**Two functions doing nearly the same thing:** `_apply_room_renames` vs
`_apply_entity_renames` (F6); `_find_obligation` vs `_find_pressure` (accepted in
AUDIT_COMMIT §1.3); `registry_for_update`'s two behaviours in and out of a
session (F1).

## Docs checked

**AUDIT_COMMIT.md findings in this scope — status:**

| Finding | Status |
| --- | --- |
| `# ---- Mapping commit ----` marker on the roster block | FIXED (`commit_common.py:126-132`) |
| Seven dead re-exports in the facade import block | Kept deliberately as published surface, now documented (`commit.py:74-82`) |
| `_entity_alias_map` filters on `retired_turn_id` nothing writes | FIXED (filter removed, `commit_common.py:576-579`; column documented vestigial, `core/db.py:1179-1186`; pinned by `test_the_entity_projection_never_retires_a_row`) |
| `commit_cast_changes` drops `departed` | FIXED (`story.scene.cast_change_status` vocabulary, warns on unknown; `_cast_changes_leaving` reads it) — residual F20 |
| `proposed_specifics` permanently empty | FIXED (gone with the mapping model; `prepare_mapping_commit` has no model) |
| `commit_all` hardcoded `"errors": []` | FIXED (`commit.py:934-939`) |
| `"told"` place-graph basis unbuilt | Registered as a decision, UNBUILT_WORLD §6.5 |
| `_find_obligation`/`_find_pressure` near-duplicates | Unchanged, accepted |

**Q2 — transaction boundary.** Every model-facing preparation runs before
`transaction()` (`_prepare_turn_commit`, `commit.py:468-479`): the composed scene,
the opening premise's embedding (`commit_mapping.py:357`), memory embeddings,
background-claim embeddings. No mapping LLM call exists any more. Inside the
lock the only "embedding" is `cheap_embed` (local CPU) on a failed premise. A66
holds: no prepare-phase helper writes (checked `seed_scene_from_plan`,
`apply_solved_plans`, `lay_held_open_marks`, `far_end_scene`,
`prepare_frontier_expansion`, `materialize_planned_fringe`,
`materialize_plans_in_sight`, `assign_regions`; notices are staged on the context
and the told-flags ride `world_flags`). Every engine domain is wrapped by
`_commit_domain`, which re-raises. Sub-steps caught and not re-raised inside the
transaction: `_apply_charter_orders` (F1, partial landing), the living-world block
(F11), `_record_subject_last_seen` (one `wset`, documented), `sync_anchored_books`
(`add_lorebook_link` ValueError swallowed silently), `charter_speaker_records` in
`commit_information_carriers` (silent), extension domains (by registration).

**Q3 — `prepare_scene_commit` ordering.** PIPELINE.md § commit states only the
domain order, never this order, so there is no guide to contradict. Actual
order: compose — base overlays → beat-end clock → destruction plan → mint dedup →
stranded-occupant guard → legacy mapping folds → cast-entity heal → interior
parentage → charter routing → unheld-transfer refusal → merge → borne containment
→ destruction vacate → charter lease → declared destination (refused-walk
guard) → remove_rooms protections → overlays → approach/travel ledger → attire →
spatial-frames inference (zones, came_from, crossings, focus, facing) → beat
events → planned exits; then prepare — time/day cycle → weather → ground →
destruction news → frontier/fringe/emissions/scents/plans in sight → dangling
exits → regions → sight contradictions → failed sources, duplicate-mint fold,
orphan mints, started sources, sensory events, hearing → layout lint → registry
projection. AUDIT_COMMIT §2 (an evidence snapshot predating A26's split) puts
weather and ground before the inference chain; nothing in the chain reads
weather, so no functional consequence. The one placement that is a defect is the
duplicate-mint fold after perception (F5).

**Q5 — entities.** Delete, not retire: consistent with the documented vestigial
column and `scene_lint`. `known_to` inheritance: works for the `state` shape only
(F10). S3-A8: detected and warned, never skipped — matches the code comment, not
PIPELINE's description (F15).

**Other claims checked:**

- CLAUDE.md § commit ("Any domain failure rolls the entire turn back") — held,
  with the sub-step exceptions above.
- DATABASE.md:340 (`world_entities` derived from the merged scene; read only for
  `_entity_exists` and alias resolution) — held for readers; "derived from the
  prepared diff" misses scene-only mints/folds (F4).
- DATABASE.md:344 (registry maintained by `commit_scene` and `world_put`) — held,
  and the World Browser's `_write_scene` also reconciles it.
- DATABASE.md:347 (sibling frame revives) — stale (F13).
- PIPELINE.md:1144-1156 (composition "cannot disagree by construction") — fails
  for duplicate mints (F5).
- PIPELINE.md:1334-1395 (counts, domain 4) — stale (F14, F15).
- AGENTS.md:540 / Design.md:540 (twenty-beat canon lock) — conditional (F12).
- AGENTS.md:880 (every scene writer keeps the registry in sync) — held for the
  registry; silent on the entity projection, which `world/paradox.py:375-380`
  says AGENTS.md requires.
- Design.md:455 (engine notices: one writer, one composer, notices survive the
  sweep's rewrite) — held (`add_engine_notice` stages before the rewrite and
  appends durably after it; the sweep composes from the staged list).
- `commit_scene_state.prepare_scene_commit` docstring ("NOTHING HERE WRITES") —
  held.
