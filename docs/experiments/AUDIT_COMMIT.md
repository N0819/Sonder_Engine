# Audit record — the `commit.py` split

Status: EVIDENCE. Written while executing `docs/design/SPLIT_COMMIT.md`
(the 14-module split of `commit.py`), per `DESIGN_MODULE_LAYOUT.md`
§"The split is also the audit" and §"…a documentation reconciliation".

Every `file:line` below is **as of the pre-split revision** (`418ab5b`,
alpha 9.5), because line numbers stop meaning anything after step 1.
The "moved in" column names the split commit that carried the code, so a
finding stays findable afterwards. Findings are **flagged, never fixed** —
nothing in the split commits changes behaviour.

The whole of `commit.py` (8,197 lines) was read start to finish for this
split; the reports in §2 are written from that read, not from the docs.

---

## 1. Audit findings

### 1.1 Confirmed from the split plan's own list

- **`commit.py:3626` — `# ---- Mapping commit ----` labels the wrong block.**
  Confirmed. It heads the address-form/name-roster code (3628–3830), which
  is roster infrastructure used by memory, background, mapping, carriers and
  crowds — not the mapping commit. The real mapping commit (5289–5730) sits
  unlabelled under `# ---- Background-presence tracking ----` (3832). The
  split resolves the ambiguity structurally (the roster block now lives in
  `commit_common.py`, the mapping commit in `commit_mapping.py`), but the
  moved marker was carried **verbatim** per the rules, so `commit_common.py`
  now contains a `# ---- Mapping commit ----` line above the roster block.
  It was wrong before the move and is wrong after it; fix it in a commit of
  its own. Moved in step 1 (`commit_common`).

- **`commit.py:8–20` — seven imported names are dead re-export surface.**
  Confirmed by repo-wide grep: `dump_chat_memories`, `restore_chat_memories`,
  `dump_lorebook`, `restore_lorebook`, `knowledge_for_character`,
  `get_relationships`, `save_relationships` are used nowhere in `commit.py`
  and imported from `commit` by nothing. They stay in the facade import
  block regardless (the whole block is kept byte-for-byte; see the facade
  comment in `commit.py`), so nothing changes — but they are seven names a
  reader will search for the use of and not find.

- **`commit.py:3854–3871` — two title lists with a correctness-critical
  comment and no enforcement.** Confirmed. The comment above
  `_NAME_TITLE_PREFIXES` states that merging it into
  `_BACKGROUND_NAME_TITLE_WORDS` "would silently make mention-detection
  stricter for short names". No test asserts the two sets are disjoint or
  separately sourced (grepped `tests/` for both names: only a passing
  docstring mention in `tests/test_background_presence_tracking.py:353`).
  The failure it warns about would be exactly as silent as described. Both
  lists stay in `commit_background.py` per the plan (resistance #4). Moved
  in step 9.

- **`tools/project_check.py:878` matches deep imports on the first dotted
  component only.** Confirmed (`head = name.split(".")[0]` against
  `EXTENSION_DEEP_IMPORTS`, line 647). Correct while `commit` was one
  module; a hole the moment `commit_*` siblings exist. Closed in step 14 by
  listing all 14 new module names.

- **`tests/test_commit_tail_producers.py:113–119` asserts by absence.**
  Confirmed: the test installs a raising stub as
  `commit._consolidate_committed_memories` and passes if it never runs.
  After step 13 the reader of that name is `commit_memory_write.commit_memories`,
  which resolves it in **its own** globals — the facade patch would be
  inert and the test green and blind. Repointed deliberately in step 13's
  commit (`tests/test_commit_tail_producers.py:118` →
  `commit_memory_write`).

### 1.2 Plan corrections found during execution

The plan's boundaries, tiers and transaction lines all held exactly as
tabulated. What it under-counted was the **test surface pinned to
`commit.py` as a module or file** rather than to function objects:

- **Five more silent-miss monkeypatch sites at step 13.** The plan's table
  lists four repoints; a sweep of every `setattr` naming
  `add_memories_batch` / `maybe_consolidate_character_memory` /
  `_consolidate_committed_memories` (including multi-line calls, which a
  single-line grep misses) found five more whose reader moved to
  `commit_memory_write`: `tests/test_commit_mind_models.py:84,90`,
  `tests/test_memory_commit.py:130,135`,
  `tests/test_memory_consolidation_parallel.py:71,88`, and
  `tests/test_consolidation_out_of_band.py:154` (a fourth site in a file
  the plan counted three in). Every one fails **silently** when missed —
  the facade patch is inert, the fake never runs, and several would have
  made real database writes through the unpatched functions while green.
  All repointed in step 13's commit.

- **Source-inspection tests are a repoint class the plan does not mention
  at all.** Nine tests assert substrings of `inspect.getsource(commit)` —
  the *module* — whose pinned text moved out of `commit.py`:
  `test_carriers.py:363,374` (step 1), `test_attentional_capacity.py:250`,
  `test_project_tier_reachable.py:180`, `test_dispute_reachability.py:245`,
  `test_pipeline_audit_leak_gaps.py:399`, `test_barren_progress.py:156`,
  `test_reaction_interior_commits.py:83` (step 12), and
  `test_relationship_events.py:121` (step 13). Each was repointed to
  `inspect.getsource(<function object>)`, which survives this and any
  future move because the facade re-exports the same objects. Two more pin
  by **file**: `tests/test_disguise_supersede.py:110` reads `commit.py`
  by path (→ `commit_entities.py`, step 6) and
  `tests/test_room_size_coverage.py:95` AST-parses `commit.__file__`
  (→ `commit_scene_state.__file__`, step 10). These fail loudly, unlike
  the monkeypatch class, but they are the same lesson: a split's blast
  radius includes every test that treats a module's source text as the
  contract.

### 1.3 New findings from the read (flagged, not fixed)

- **`commit.py:5325–5326` — a guard that cannot fire: `_entity_alias_map`
  filters `world_entities` on `retired_turn_id IS NULL`, and nothing ever
  sets `world_entities.retired_turn_id`.** The column exists (added by the
  `db.py:1092` migration), `db.py:151`'s comment on `room_registry` says it
  "mirrors world_entities.retired_turn_id", and destruction retires
  lorebooks and registry rooms — but the entity removal path
  (`commit.py:3533–3537`) **deletes** `world_entities` rows outright, and no
  code path anywhere writes the column (verified by repo-wide grep: the only
  `UPDATE world_entities` statements set kind/subtype/name/payload). The
  filter is inert, and the `db.py` comment describes retirement semantics
  the table has never had. Either the delete should become a retire (making
  the filter live) or the column and comment are describing something
  built-adjacent and quietly never wired. Code moved in steps 1
  (`_entity_alias_map` → `commit_common`) and 6 (removal path →
  `commit_entities`).

- **`commit.py:5205–5213` + `3842–3852` — the `auto_dialogue` promotion
  threshold is configurable, clamped, tested, and enforced nowhere.**
  `promotion_thresholds` (and `scene.promotion_config`, which the per-chat
  editor and `tests/test_scene_integrity_and_promotion_config.py:99–106`
  exercise) plumb an `auto_dialogue` value whose documented meaning is
  "lines before hands-off auto-promotion fires". No code reads it:
  `auto_promote_background_characters` (5216–5287) gates on the
  `promotable` flag and on `addressed_turns >= _promote_after_addressed`,
  and never compares `dialogue_turns` against `auto_dialogue` /
  `AUTO_PROMOTE_DIALOGUE_THRESHOLD` — its own docstring ("AND at least
  AUTO_PROMOTE_DIALOGUE_THRESHOLD dialogue turns") describes a gate the
  code does not have. A host who raises `auto_dialogue` to slow hands-off
  promotion changes nothing, silently. Moved in step 9
  (`commit_background`).

- **`commit.py:3118–3138` — `commit_cast_changes` silently ignores every
  status except `active`/`dormant`, and nothing tells the model those are
  the only two words.** The prompt shape is bare
  (`cast_changes:[{who,status,reason}]`, no vocabulary), `StateDiff.
  cast_changes` is `list[dict]` (untyped inner shape), and `schemas.py:4613`'s
  own worked example writes `"status": "departed"` — which this function
  drops without a warning, leaving the character `active`. Departure still
  *works* through the other readers of `cast_changes` (the stranded-occupant
  guard, destruction vacate, presence tracking key off the entry's
  existence), which is exactly why the dropped status write is invisible.
  Same silent-tolerance shape as the weather-enum lesson already recorded in
  AGENTS.md. Moved in step 11 (`commit_mechanics`).

- **`commit.py:5477–5482` — `proposed_specifics` is a permanently empty
  payload field.** `prepare_mapping_commit` initializes `specifics = []`,
  never appends to it, then ships `"proposed_specifics": specifics` to the
  mapping model and uses `" ".join(map(str, specifics)) or …summary` as the
  lore-search query (the join is always `""`, so the fallback always wins).
  Vestige of a removed narrator-specifics channel; the field teaches every
  mapping call about an input that cannot occur. Moved in step 8
  (`commit_mapping`).

- **`commit.py:8125–8137` — `commit_all`'s result carries a hardcoded
  `"errors": []`.** No code path can ever populate it (failures raise and
  roll back instead), and nothing reads it (grepped `agents/runtime.py`,
  `app.py`, `static/js/`). A field that is always empty is indistinguishable
  from a field that is never checked. Retained in `commit.py` (not moved).

- **`commit.py:6184–6191` + `6032–6054` — the salience and durable-quote
  word lists are hardcoded English in a language-pack engine.**
  `_salience_of` boosts on English words ("attack", "blood", …);
  `_durable_dialogue_category` matches English markers ("promise",
  "my name is", …). The engine otherwise routes language-dependent
  recognizers through `language_runtime` (see `_form_in`, which fetches
  `_COMMON_WORD_NAMES` through `linguistic(...)`, in this very file). In a
  Japanese story every memory scores the flat length-based salience and no
  quote is ever kept verbatim — silently. `tools/remember_lines.py` inlines
  the same English rule. Moved in step 12 (`commit_memory`).

- **`commit.py:79–135` — `update_place_graph` documents a `"told"` basis
  with no writer.** The docstring is honest about it ("no code path writes
  it yet"), so this is a register entry rather than a lie: a
  testimony-derived place-graph writer is designed, accepted by the data
  model, and unbuilt. Belongs in `docs/UNBUILT.md`'s residuals once the
  parallel agents' work on that file settles. Moved in step 2
  (`commit_place_graph`).

- **Near-duplicate pair, accepted:** `_find_obligation` (5766) and
  `_find_pressure` (5889) are the same fuzzy-match shape on different
  fields, and the file says so ("the same convention as _find_obligation").
  Both stay side by side in `commit_ledgers.py`, where the duplication is
  at least visible in one screenful. Not a defect; recorded so the next
  reader doesn't re-discover it as one.

---

## 2. What the code actually does, per module — checked against the docs

Sources checked: `Design.md` (conformance table + § scene/persistence),
`docs/guides/DATABASE.md`, `docs/guides/PIPELINE.md` (§ commit),
`AGENTS.md` (routing table + invariants), `CLAUDE.md` (§ Architecture),
and the design notes each module cites.

**The headline claims all hold.** Verified directly against
`_prepare_turn_commit` / `_commit_all_locked` while splitting them:

- Preparation (scene, mapping, memory, background-claim embeddings) runs
  before the outer transaction; every provider round-trip is outside the
  write lock. The three `prepared or prepare_*(ctx)` fallbacks
  (`commit_scene:2765`, `commit_transit_sweep:2828`, `commit_memories:7628`)
  each run their fallback **before** their own `with transaction():`, so
  even standalone callers keep preparation outside — the split moved none
  of them across that line.
- The in-transaction domain order is exactly the order CLAUDE.md and
  PIPELINE.md state (transit → world_events → scene → entities → cast →
  paradox → spatial → mapping → offscreen_plans → crowds → offscreen_epoch
  → memories → information_carriers → background_presences →
  narration_person → obligations → world_pressure → authored_events →
  pending → extension domains).
- Out-of-band tail: consolidation job, auto-promotion, offscreen ticks,
  agent ticks, artifact wording, extension dispatch — all after the
  transaction, all warn-never-rollback, as PIPELINE.md:563 describes.
- The only mutable module state is `_COMMIT_LOCKS`/`_COMMIT_LOCKS_GUARD`,
  written only by `_commit_lock`, called only by `commit_all`. All three
  stayed in `commit.py`.

Per module:

- **`commit_common`** — scalar helpers (`_clamp`, `_keys_str`, the
  `_stable_event_key` alias re-exporting `mechanics.stable_event_key`),
  the monotonic story clock (`_monotonic_elapsed` — shared by scene and
  memory so a backwards beat is refused identically in both),
  `_normalize_character_output`, `_player_name_or_none`, `_room_of`
  (script-aware position lookup), `_normalized_fact`, the address-form /
  name-roster block (`_address_forms`, `_names_heard_in`,
  `_known_name_roster` vs `_registered_name_roster` — presence vs
  existence, deliberately two functions), and entity-id canonicalisation
  (`_entity_alias_map`, `_canonical_anchor`). Docs: AGENTS.md's
  name-learning row (`_names_heard_in`) and the roster-discipline notes
  are accurate to the code, including the "membership only, never
  iterate" rule on the wide roster.

- **`commit_place_graph`** — `update_place_graph` folds one committed beat
  into a per-mind `{nodes, edges}` graph on `chat_chars.state`, with
  walked/seen bases, disproven edges corrected only from the standing
  room, and eviction by `(last_turn, visits)` at 400 nodes;
  `record_spatial_experience` reconstructs sprint-crossed rooms
  deterministically via `passable_path` and bounds the legacy
  `known_exits`/`known_dead_ends` keys by the graph's memory rather than
  the recency window. Matches `DESIGN_RUNNING.md` and the firewall
  discipline in AGENTS.md (§ own traversal only). The `"told"` basis is
  documented-unbuilt (finding above).

- **`commit_destruction`** — validates `state_diff.destruction`
  (vehicle/building = one book, region = a BFS cascade over
  parent-containment plus physically-inside `currently_within` members),
  folds removals into the ordinary diff (no second removal path), retires
  books and registry rooms (never deletes), and mints latency-gated
  `news_arrival` scheduled events with hop-distance-derived latency.
  DATABASE.md:85/88 and the AGENTS.md routing row describe this
  accurately.

- **`commit_room_registry`** — mint-time dedup (rekey on cross-owner key
  collisions, redirect on same-scope alias re-mints), the prepare/apply
  registry projection pair, `sync_room_registry_with_scene` for the manual
  world editor, DW-1/TR-3 location-label refresh, and dangling-exit
  pruning. Docs right; the docstrings themselves carry the measured cases.

- **`commit_attire`** — the single attire projection (`apply_attire_diff`)
  shared by the perception preview and durable commit, exactly as
  AGENTS.md's attire row demands: alias-key healing, note interpretation
  (`interpret_attire_notes`, prose-gated garment introduction), the
  decisive/process ladder, coverage escalations, steal guard, held-removal
  and dropped-condition feedback, unconditional derived-note rebuild, and
  shed-garment adopt-or-mint with worn/shed entity folding. AGENTS.md:79's
  long attire row was checked clause by clause against this code and is
  accurate — including "coerce_diff_shape must run at commit as well as at
  validation", which `apply_attire_diff` does.

- **`commit_entities`** — the `world_entities` projection from the
  **merged** scene (never the raw diff), S3-A8 copy-forward detection,
  deterministic vehicle-lorebook creation, the sleep/speech awareness gate
  (moved-this-beat vs targeted-this-beat), and disguise/transformation
  supersession with `known_to` inheritance. DATABASE.md:82 and the
  AGENTS.md `world_entities` row match the code precisely. One divergence
  recorded as finding 1.3 (delete vs retire).

- **`commit_ledgers`** — pending obligations and world pressures: open /
  discharge (or tick / hold / resolve) ops with fuzzy id fallback, silence
  counted as implicit hold and warned, overdue/stall flags surfaced into
  the next resolve payload, caps at 12/8. Matches the DW-2 "significance
  floor" description in the F5 comment and the Director routing row.

- **`commit_mapping`** — `prepare_mapping_commit` (the mapping_commit LLM
  call + batch embeddings, all pre-lock) and `commit_mapping` (book ops
  via `_apply_mapping_book_ops` with alias dedup and a 3-book/turn cap,
  lore ops with canon-locking at 20 turns, validated introductions with
  both-present + frame-recognition gates, shadow profile and standing
  intentions), plus `normalize_offscreen_events`, which now exists only to
  count-and-refuse volunteered ticks. PIPELINE.md's mapping-commit section
  is accurate. `proposed_specifics` is a dead input (finding 1.3).

- **`commit_background`** — presence tracking from structured fields only
  (dialogue speakers, non-inert entity defs, placed positions, the
  backstop's own line), id/article identity folding gated by
  `_bodies_answering_to`, the speech verdict ladder (frozen `nature`
  answer > ubiquitous > inert > animate-kind > undecided), the
  deterministic reactor gate with forced routing and at-post-within-
  earshot, owed-reply debts, claims record/settle, promotion (manual and
  auto) with name-collision refusal and mutual-recognition seeding.
  AGENTS.md:46's row and `BACKGROUND_LIFE_DESIGN.md` §3.8/§3.11 match the
  code. `auto_dialogue` is plumbed-but-unenforced (finding 1.3).

- **`commit_scene_state`** — `prepare_scene_commit` builds the exact
  post-turn scene pure: destruction plan, mint dedup, stranded-occupant
  guard, mapping map-detail/station folds, the contested merge, declared
  destinations always existing, advisory remove_rooms with protections,
  approach/travel ledger, attire, weather-declared-then-drift, ground
  advance, the spatial-frames inference chain in its stated order, and the
  prepared bundle (`scene`/`diff`/`prev_scene`/`prev_clock`/registry/
  destruction) whose `prev_scene` exists precisely so in-transaction
  guards can see "before". `commit_scene` persists it with the registry
  and destruction applies and the last-seen ledger. PIPELINE.md § commit
  and the AGENTS.md travel/weather/stations rows are accurate to this
  code.

- **`commit_mechanics`** — the transit-sweep domain (fires/schedules/
  expires through `mechanics.mechanics_sweep`, mints living-world
  consequences, feeds the obligation ledger, publishes engine notices),
  the world-event spine (fired rows promoted to checkpointed objective
  history, stable ids, never invents), information carriers (acquire →
  tell → couriers → artifacts, all one domain so a telling can never
  outlive a rolled-back acquisition), and cast status writes. Docs right;
  the cast-status vocabulary gap is finding 1.3.

- **`commit_memory`** — `prepare_memory_commit`, 1,264 lines, the file's
  monolith-in-miniature (the plan's resistance #2 is real: nothing under
  the verbatim rule could divide it). Per character: merged
  interaction+reaction results, the recognition-gated dialogue memories
  with in-play name learning, the empty-view floor, IR-minted episodes,
  own-conduct rows (the alpha-9.5 regression fix — the d290ca4/3a82657
  history in the comment matches git), inference memories keyed to
  rekeyed place claims, the interior-depth block (capacity caps,
  intentions, projects with probation/service ledger and boundary review,
  appraisal with memory modulation, affect/hedonic/stress resolution,
  drive strain and rupture windows), tell ledgers, stance clamps, spatial
  experience, place purpose, mind-model merge and hypothesis selection,
  relationship/dispute/importance deferrals, and the embeddings batch with
  the local-hash downgrade warning. `DESIGN_LONG_TERM_GOALS.md` and
  `DESIGN_PSYCHOLOGY_AS_PRESSURE.md` describe this code accurately,
  including the parts CLAUDE.md's psychology section warns about. The
  English-only word lists are finding 1.3.

- **`commit_memory_write`** — `commit_memories` (names learned, turn
  memory replace, relationship ops, state writes, belief reconciles,
  disputes, importance bumps, the events-row upsert — one transaction),
  `schedule_memory_consolidation` (the out-of-band job with frame pinning
  and cooperative cancellation) and `_consolidate_committed_memories`
  (the blocking twin for standalone/test paths, with the contextvars-copy
  fix for story language). PIPELINE.md:563's description is accurate,
  including the 29.5s measurement and the restore-mid-LLM residual it
  says is recorded in UNBUILT.md.

- **`commit.py` (retained)** — the per-turn commit lock, four thin tail
  domains (narration person; authored events; offscreen epoch + plans;
  crowds — the crowd-advance-before-ops ordering comment matches
  `tools/crowd_drive.py`'s finding), `commit_all` /
  `_prepare_turn_commit` / `_commit_domain` / `_commit_all_locked`, and
  the facade. The full pre-split import block is kept byte-for-byte:
  `_is_empty_view` is reachable only through it, and tests monkeypatch
  `commit.<imported-name>` (`prepare_memories_batch`, `get_scene`,
  `persona_name`, `add_memories_batch`,
  `maybe_consolidate_character_memory`, `commit.affect.*`). The hardcoded
  `"errors": []` is finding 1.3.

**Documentation verdicts, in the three categories the layout note asks
for:**

- *Right*: DATABASE.md §world_entities/§room_registry/§world_placements;
  PIPELINE.md § commit (order, preparation, out-of-band tail, both
  background paths); CLAUDE.md § architecture's commit paragraph;
  AGENTS.md's routing rows touching commit (attire, background,
  world_entities, weather, travel, obligations) — checked clause by
  clause during the read, no stale clause found.
- *Stale*: `db.py:151`'s "mirrors world_entities.retired_turn_id" comment
  describes a mirror with no writer (finding 1.3);
  `auto_promote_background_characters`' docstring claims a dialogue-count
  gate the code lost (finding 1.3). Both are code-comment/docstring
  staleness, not guide staleness; correcting them is behaviour-adjacent
  and deferred with their findings.
- *Described but not built / quietly lost*: the `"told"` place-graph
  basis (self-declared unbuilt); the `auto_dialogue` threshold (built as
  configuration, never as behaviour). Nothing in the split's territory
  matched the worst category (documented behaviour silently lost) beyond
  those two — the own-conduct memory regression that category is named
  for was already fixed and its history is accurately recorded in the
  code comment at 6693–6707.

---

## 3. Execution record

Split executed leaf-first, one module per commit, `make check` green at
every step (compile + map + structure + full suite). Verbatim moves —
`git diff` on each step shows pure deletion-from-`commit.py` /
addition-to-new-module plus the facade import; no moved line was edited.

| step | module | commit |
| --- | --- | --- |
| 1 | `commit_common.py` (+ repoint `tests/test_carriers.py:363,374` to function sources) | `f358891` |
| 2 | `commit_place_graph.py` | `876208f` |
| 3 | `commit_destruction.py` | `7273082` |
| 4 | `commit_room_registry.py` (+ repoint `tests/test_dw_audit_scene.py:55`) | `13ed2c7` |
| 5 | `commit_attire.py` | `9ca5b00` |
| 6 | `commit_entities.py` (+ repoint `tests/test_awareness_not_from_speech.py:66,103`, `tests/test_disguise_supersede.py:110`) | `edbe375` |
| 7 | `commit_ledgers.py` | `2a88513` |
| 8 | `commit_mapping.py` | `13879c7` |
| 9 | `commit_background.py` | `aec177f` |
| 10 | `commit_scene_state.py` (+ repoint `tests/test_room_size_coverage.py:95`) | `106341f` |
| 11 | `commit_mechanics.py` | `5870bed` |
| 12 | `commit_memory.py` (+ repoint three `prepare_memories_batch` patch sites and six module-source tests) | `23bda52` |
| 13 | `commit_memory_write.py` (+ repoint the plan's four sites, the five extra found in §1.2, and `tests/test_relationship_events.py:121`) | `daa37b8` |
| 14 | tooling + docs (`EXTENSION_DEEP_IMPORTS`, `MODULE_PURPOSES`, AGENTS.md, CLAUDE.md, this file) | the commit carrying this file |

Final line counts: `commit.py` 575 (from 8,197); `commit_common` 384,
`commit_place_graph` 274, `commit_destruction` 413, `commit_room_registry`
444, `commit_attire` 862, `commit_entities` 499, `commit_ledgers` 302,
`commit_mapping` 490, `commit_background` 1,476, `commit_scene_state` 709,
`commit_mechanics` 348, `commit_memory` 1,486, `commit_memory_write` 230 —
each within a few header lines of the plan's estimate. Every name
`commit.py` exported before the split, all 22 private crossers included,
remains importable as `from commit import X`.
