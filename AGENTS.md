# Editing Guide for Coding Agents

This file is the operational map for changing Sonder Engine safely. It is written for both human contributors and AI coding agents.

## First-pass orientation

Before editing behavior:

1. Read `docs/PIPELINE.md` for execution order and ownership boundaries.
2. Search `docs/CODE_MAP.md` for the handler or function involved.
3. Read `docs/DATABASE.md` before changing persistent state, archives, or restore paths.
4. Read the relevant schema in `schemas.py` before changing any model output.
5. Read the corresponding commit function before adding fields that should persist.
6. Read `docs/TESTING.md`, find the nearest regression test, and run the narrow test first.

`docs/CODE_MAP.md` is generated; never hand-edit it. Regenerate and verify it
after moving or adding functions:

```bash
make map
make structure
```

`AGENTS.md`, `docs/PIPELINE.md`, `docs/DATABASE.md`, `docs/TESTING.md`, and
`Design.md` are the maintained guidance set. Dated audits and `*_DESIGN.md`
files are scoped records or proposals, not implementation authority; check
their claims against source and the maintained guides before acting on them.

## Edit routing

| Change | Primary files | Usually inspect too |
|---|---|---|
| Player input interpretation | `agents/director.py` (`director_interpret`) | `schemas.py`, `prompts.py`, pipeline tests |
| Flow planning, resume, or streaming | `agents/runtime.py` (`build_plan`, `_run_pipeline`) | `agents/storage.py`, `checkpoints.py`, pipeline tests |
| Opening scene generation | `agents/director.py`, `agents/perception.py` | `scene.py`, `spatial.py`, `commit.py` |
| Perception or information leakage | `agents/perception.py` (`_source_channels`, `_redact_concealed_from_event`, `_surface_translate_event`, `_touch_only_sources`, `_per_observer_model_views`), `agents/common.py` (`_delivery_ok`, `_AUTONOMY_VERBS`, `bind_sequence_targets`), `agents/loops.py` (`deterministic_micro_perception`), `agents/background.py` (`_present_others`), `agents/narration.py` (`_visible_portal_states`) | `spatial.py` (`scent_level`, `visual_level_between`, `containment_conceals`, `visible_adjacent_rooms`), `scene.py` (`recent_events_for_observer`), `schemas.py`, `memory.py` (`current_turn_idx` cutoff), `commit.py` (S3-A8 copy-forward signal, dialogue-memory recognition gate), perception tests — concealed actions are sentence-level redacted from the resolved event per-perceiver, including pronoun-subject continuations; touch-only sources get surface-translated event text; scent is barrier-gated; per-observer LLM calls create structural information boundaries; the unified `_delivery_ok` gate consolidates containment, awareness, sight (including rear-arc), and hearing (with proximity) checks; background-presence names pass through that presence's OWN recognition ledger (an unregistered presence recognizes nobody); portal states for unseen rooms are withheld; a beat's prose copied forward onto an entity this beat names is reported, not dropped; the events row is concealment-scrubbed on the `recent_events` path that feeds mapping's lore query |
| Character decisions or dialogue | `agents/character.py`, `agents/loops.py` | `memory.py`, `scene.py`, `prompts.py` |
| Character psychology, stress, pain/pleasure, belief learning, or association learning | `character_schema.py`, `psychology_runtime.py`, `affect.py`, `agents/character.py`, `commit.py` | `schemas.py`, `prompts.py`, `importers.py`, character-card UI, `theory_of_mind.py` (`belief_credence`, `absorbed_cap`, `select_active_hypotheses`), `psychology_runtime.py` (`cognitive_absorption`), `memory.py` (`reconcile_inference_confidence`), psychology and information-leak tests — transient state may use only the character's scrubbed current observations, own sheet, own body state, and earned memory |
| Background (unregistered) presence reactions | `agents/background.py`, `commit.py` (`pick_background_reactor`) | `agents/perception.py` (merge into dialogue_log), `prompts.py`, `schemas.py` |
| Objective action resolution | `agents/director.py` (`director_resolve`) | `schemas.py`, `spatial.py`, `commit.py` |
| Narration | `agents/narration.py` (`narrator`) | narrator prompt in `prompts.py`, output validation |
| Persistence or rollback | `commit.py`, `checkpoints.py` | `db.py`, `memory.py`, restore tests |
| Portable chat archive export/import | `chat_archive.py` | `app.py` remap primitives, `checkpoints.py`, `memory.py`, archive fidelity tests |
| Portable pipeline trace export/replay | `pipeline_trace.py`, `tools/pipeline_trace.py` | `agents/storage.py`, `db.py`, `tests/test_pipeline_trace.py`; content-bearing traces are private local artifacts |
| Host authentication and guest access | `auth_routes.py`, `guest_access.py` | `app.py` router registration, auth/guest tests |
| Deterministic mechanics (timed arrivals, expiry, dock edges, zone/carry inference, news latency) | `mechanics.py` (`mechanics_sweep`) | `commit.py` (`commit_transit_sweep`), `spatial.py`, `spatial_frames.py`, `tests/test_mechanics_sweep.py` |
| Going under and waking up (`awareness` conditions) | `agents/director.py` (`_unsupported_player_awareness` for the onset, `_awareness_exits`/`_awareness_view` for the exit), `scene.py` (`awareness_conditions`, `awareness_map`, `NON_AWAKE_GATED`) | `agents/character.py` consciousness gate, `agents/perception.py`, `commit.py` condition INSERT/UPDATE, `tests/test_awareness*.py` — three separate questions, and the exit is the one that was missing: across the author's whole live corpus the Director never once emitted an ending (`active: 0`), and the only conditions that ever stopped gating were born with `expires_at_seconds`. A gated mind runs NO character step, so a stuck sleeper generates no pressure and reads as a quiet one. Waking is the WORLD's decision, never the sleeping mind's: the deterministic exits are the player's own declaration, a deliberate rouse aimed at someone `asleep` (never `sedated`/`unconscious`), and a full sleep on the simulation clock. An ending must re-use the SAME `condition_id` — commit UPDATEs on it, a new id opens a second row |
| Whether a barrier can be seen/heard/smelled/walked through | `spatial.py` (`_SIGHT_BARRIERS`/`_PASSABLE_BARRIERS`/`_AMBIENT_BARRIERS`/`_SCENT_BARRIERS`, `has_visual`, `sight_level`, `scent_level`, `normalize_barrier`) | `visible_adjacent_rooms`, `tests/test_see_through.py`, `tests/test_membrane_barrier.py` — four separate questions; `window` passes sight only, `bars` sight+sound, `membrane` passage only (the inverse of `window`: a curtained doorway, a tent flap). `has_visual`/`sight_level` is where sight is decided; `scent_level` is where scent is decided. `_SOUND_LADDER` is walked by RELATIVE steps — inserting a rung changes what its NEIGHBOURS shift onto, so `membrane` is deliberately off it. `_SCENT_BARRIERS` gates scent the same way `_SIGHT_BARRIERS` gates sight: `membrane` and `closed_door` muffle, `window`/`wall` block, `open`/`bars` pass |
| Containers you can be inside (jar/cage/crate/tent) | entity `enclosure` + `interior_rooms` + `state.hatch`, derived in `spatial.py` (`_closed_enclosure_barrier`, `_open_enclosure_barrier`, dock-edge rewrite) | `tests/test_see_through.py`, `tests/test_membrane_barrier.py` — `enclosure` describes BOTH states: `opaque`/`transparent`/`barred` leave an OPEN interior see-through (right for a lid), `membrane` is opaque open or shut and overrides an authored `open_door`. A closed transparent container yields a `window` edge; `_is_carried_interior` keeps a carried container's inside out of the surrounding room's view. `enclosure`/`light_source` are in `_ENTITY_DEFAULT_FIELDS`, without which they could only be set at entity CREATION |
| A body part-way through an opaque boundary | `spatial_frames.py` (`infer_threshold_crossings`), `spatial.py` (`crossing_of`, `crossing_visible_from`, `spatial_rel_between`, `THRESHOLD_CROSSING_BEATS`) | `commit.py` (called beside `infer_came_from`), `agents/perception.py`, `tests/test_threshold_crossings.py` — a position changes in an instant and a doorway does not; the room LEFT keeps `shapes` sight of the crosser for a couple of beats. A floor on sight, never a bonus, and dropped the moment the body moves again |
| Being carried (pocket/jar/shoulder/hand) | `spatial.py` (`container_of`, `contents_of`, `carrier_chain`, `derive_contained_positions`, `normalize_scene_containment`) | `schemas.py` (`StateDiff.containment`), director prompt, `containment_facts`, `tests/test_containment.py` — a carried body's position is DERIVED from its carrier's, so writing one does nothing; getting out is an explicit release. Not `interior_rooms`, which is for containers you stand inside |
| Body size (shrinking/growing) and what it makes infeasible | `spatial.py` (`scale_of`, `size_relation`, `contacts_broken_by_scale_change`, `normalize_scene_scales`) | `schemas.py` (`StateDiff.scales`), director prompt, `spatial_facts`/`size_facts`, `tests/test_scale.py` — scale lives in `scene.scales`, is NOT pruned by position (a size is not a co-location), and cancels contacts on the resized body BEFORE the beat's own contact ops so a re-established hold survives |
| Body position / contact (who is touching whom, and where) | `spatial.py` (`apply_contact_ops`, `normalize_scene_contacts`, `contacts_of`) | `schemas.py` (`StateDiff.contact_ops`), director prompt, `agents/perception.py` payloads, `spatial_facts`, `tests/test_body_position.py` — a contact is a RELATION stored once in `scene.contacts`, never on either body; positions prune it |
| Authoring edits to live positions (GM relocation) | `app.py` (`GET /api/chats/{cid}/positions`, `PUT /api/chats/{cid}/characters/{ch}/position`) | `scene.get_scene`/`spatial.room_of`, `static/js/settings.js` cast tab, `tests/test_char_relocation.py` — writes only `scene.positions`, requires an idle chat, validates room ids, and queues no narrator beat |
| Room identity/dedup/retirement, destruction (single-book + region cascades) | `commit.py` (room registry + destruction blocks) | `db.py` (`room_registry`), `checkpoints.py`, `app.py` remaps, registry/destruction tests |
| Lore retrieval or hierarchy | `memory.py`, `agents/mapping.py` | `app.py`, lore tests |
| Which lorebooks a chat *has* (browsing/editing) | `app.py` (`GET /api/chats/{cid}/lorebooks`) | `static/js/lorebooks.js` workspace tree, `tests/test_lore_tree_browser.py` — ownership, NOT `chat_lorebook_ids()`: that resolves reachability for retrieval and cannot see a book nothing hangs off |
| Lorebook-tree generation (authoring, not pipeline) | `importers.py` (`generate_lorebook_plan`, `resume_lorebook_plan`, `apply_lorebook_plan`) | `generator_lorebook*` prompts, `db.py` (`lore_gen_jobs`), `app.py` job routes, `static/js/lorebooks.js` generator tab, `tests/test_lore_gen_resume.py` |
| Character/persona format | `character_schema.py` | `importers.py`, generation/import/fill prompts, editor UI, schema and non-destructive-fill tests |
| Initial outfit / live attire | `character_schema.py` (`initial_outfit`), `scene.py` (`seed_initial_attire`) | `agents/director.py`, generator/import prompts, `static/js/editors.js`, attach/promotion routes, `tests/test_initial_outfit.py` — appearance is stable body description; initial outfit is authored starting clothing; `scene.attire` is mutable story state. Seed once and never reset existing attire from a card |
| Per-story character-card edits | `app.py` (`PUT /api/chats/{cid}/characters/{ch}/card`), `chat_chars.sheet`, `scene.active_cast` | `static/js/editors.js`, cast tab in `static/js/settings.js`, `chat_archive.py`, branch copying, `tests/test_chat_character_cards.py` — the override is authored configuration, not live `state`; identity name/uid are locked because scene and knowledge records use them as keys |
| Provider behavior | `providers.py` | `app.py` provider routes, `prompt_cache.py` |
| Per-call request timeout | `providers.py` (`request_timeout`, `clamp_read_timeout`, `_request_timeout`/`_httpx_timeout`) | the caller's own knob (e.g. the lorebook generator's `timeout` param); `REQUEST_TIMEOUT`/`HTTPX_TIMEOUT` stay the pipeline default |
| API behavior | `app.py`, `auth_routes.py`, or `chat_archive.py`, according to route ownership in `docs/CODE_MAP.md` | matching file in `static/js/` |
| Browser UI | `static/index.html`, `static/js/`, CSS | matching API route in `app.py` |
| Test tiers, CI, or dependency support | `Makefile`, `.github/workflows/ci.yml`, `pyproject.toml`, `requirements*.txt`, `constraints.txt` | `docs/TESTING.md`, `tests/conftest.py`, `browser_tests/` |
| Database shape | `db.py` | migrations, snapshot/export/restore code, tests |

## Core invariants

These are architectural guarantees, not stylistic preferences.

### Information boundaries

- A character may use only its perception, memory, knowledge configuration, relationships, private history, and explicit inferences.
- Objective world state must not be copied into a character context merely with an instruction to ignore unavailable details.
- Perception of an action onset and perception of its resolved outcome are separate passes.
- The Narrator should render the player-facing view, not an omniscient reconstruction of every private agent result.
- Every perceptual channel is barrier-gated: sight (`_SIGHT_BARRIERS`), sound (`_AMBIENT_BARRIERS` + material), scent (`_SCENT_BARRIERS`), and touch (containment/concealment). Touch-only perception is cause-blind: surface sensations cross, the act producing them does not.
- Per-observer LLM calls (`_per_observer_model_views`) create structural information boundaries: each perceiver gets a separate prompt and response rather than sharing one omniscient call.
- The unified delivery gate `_delivery_ok` in `agents/common.py` consolidates containment, awareness, sight (including rear-arc/`behind_sources`), and hearing (with proximity) checks. Every deterministic delivery site must call it rather than using scattered bare checks.
- **Containment has two forms, and both must be read through
  `spatial.hiding_holders_of`.** A scene expresses one entity inside another
  either as a `contained` ledger record OR as a room carrying `parent_entity`
  whose parent itself holds a position. Reading `scene["contained"]` directly
  sees only the first, which is how a live chat ended up with an occupant of a
  parented interior visible to the very entity enclosing them and delivering no
  touch to it — both halves of "concealed but felt" wrong, in opposite
  directions. The threshold-crossing grace (`crossing_visible_from`) does not
  apply to a parented interior: a doorway is something you stand part-way
  through, an enclosure is not. Hearing from inside a parented interior is
  CONDUCTED (`inside_source` on the relation → `hear_level` returns full): the
  enclosing body is the medium. One-way only, and it grants no sight.
- **Spatial belief is belief.** A claim about a PLACE is re-keyed onto that
  place at commit (`theory_of_mind.rekey_place_claims`) so rooms stop competing
  as rival explanations of one subject; within a room, claims still revise each
  other normally. Characters demonstrably build durable cognitive maps this way
  — see [`docs/SPATIAL_LEARNING_EXPERIMENT.md`](docs/SPATIAL_LEARNING_EXPERIMENT.md)
  — but **belief confidence has no outcome feedback**: it tracks restatement and
  recency, never whether acting on the belief worked. Navigation is the one
  place with a success signal (`worked_before`, next bullet); a *belief* still
  accumulates no weight from having been acted on successfully.
- **Outcome feedback exists, narrowly.** An intention reaching `satisfied` is
  the one success signal the engine can observe without trusting a bare
  self-report (`affect.apply_intent_ops` gates satisfy behind evidence). When
  one closes, commit credits the rooms walked while pursuing it into
  `routes_that_worked`, surfaced to the character as `worked_before`. That is
  the ONLY marker anywhere that says something succeeded rather than that it
  happened; everything else revises a belief by contradiction.
- **`schemas.LenientModel`** is the base every schema model inherits. It accepts
  a structured value where a field is declared `str`, reducing it to the prose
  inside. Five separate crashes were this one shape, each discarding an entire
  stage output; ~90 str-typed fields carry the same exposure. It fires ONLY on
  a `str`-typed field receiving a dict/list, so it cannot mask a real type error.
- **Sensation constrains cognition.** `psychology_runtime.cognitive_absorption`
  measures how much of a mind its own body is claiming, 0..1 and deliberately
  **blind to valence** — intense pleasure occupies attention exactly as intense
  pain does. Do NOT read `strain` for this: strain is the aversive component
  specifically, and using it would say a body at the ceiling of a powerful
  pleasant stimulus is free to theorise. `load`/`overloaded` stay strain-only.
  `theory_of_mind` spends the figure three ways: the effortful end of the
  confidence-cap gradient erodes (`absorbed_cap` — observation is untouched, so
  noticing stays sharp while second-order mentalising collapses), a NEW
  hypothesis must clear `formation_floor`, and the hypothesis sheet holds fewer
  entries (`sheet_capacity`, 5 → 1). Absorption gates **formation, not
  reinforcement** — recognising more of what you already think is automatic
  processing and survives; building a theory is controlled and does not. It must
  never ratchet an existing belief down.
- **A model-declared `kind` is not trusted.** Every ceiling in `theory_of_mind`
  keys off `kind`, so `effective_kind` makes the claim's own language vote too
  and takes the **stricter** of declared and inferred. This is text matching and
  must never be relied on as an information boundary — it is confidence
  calibration, deliberately arranged so a misfire can only make a character less
  sure, never more. Both entry points (`cap_mind_model_updates`,
  `apply_mind_model_updates`) must agree on the kind, or a claim is capped under
  one and merged under another.
- **Belief provenance belongs to the belief.** `first_seen_turn`, `formed_under`
  and `reappraised_turn` are carried across reinforcement; the merged hypothesis
  is rebuilt from the incoming update, so anything not explicitly carried is
  silently lost. `due_for_reappraisal` must be asked with the character's
  CURRENT absorption — passing 0.0 flags every extremity-formed belief
  unconditionally, including for a character still in the grip of it.
- **The stable hypothesis sheet.** `select_active_hypotheses` keeps 1–5 open
  questions on `chat_chars.state.active_hypotheses`, each keyed `i_suspect` so
  the field itself carries the epistemic status — a mind reading its own
  conjecture back as settled fact is the same information-layer collapse the
  engine polices between minds, happening inside one. Selection has hysteresis
  (`_SHEET_INCUMBENT_MARGIN`); without it the sheet churns each turn and stops
  being "what I am actively wondering about". Selected at commit (where the
  reconciled beliefs and settled end-of-beat body state both exist), read by
  `agents/character.py`. A hypothesis formed under absorption carries
  `formed_under`, and `due_for_reappraisal` re-opens it once the character is
  calmer — neither standing as though reached calmly nor discounted forever.
- **Recall follows belief.** An inference memory's `confidence` is not a mint-time
  constant: `memory.reconcile_inference_confidence` re-weights it at commit to the
  character's current credence, read from their own `mind_models` via
  `theory_of_mind.belief_credence`, and `search_memories` ranks on it. A belief
  they have since explained away is pushed toward a floor rather than erased --
  they can still recall having held it, it just no longer outranks what replaced
  it. **Aged out is not explained away.** `mind_models` is a small working set
  (per-kind half-lives, per-entity capacity, pruning at the floor) while the
  memory bank is an archive, so "no surviving hypothesis carries this claim"
  is usually expiry, not revision -- the demotion is therefore a ONE-SHOT,
  idempotent re-anchoring to a fraction of the mint-time confidence
  (recovered from `salience = 0.45 + 0.3*confidence`), never a compounding
  per-turn decay; a still-stored hypothesis's credence is floored at that same
  resting place so held >= abandoned always. A compounding decay was measured
  (2026-07-29) crushing 76-80% of a long chat's entire inference bank to the
  floor within 7-18 played turns, removing inferences from recall wholesale.
  Reconciliation reads ONLY that character's own memory rows and own
  mind_models: it must never consult the objective record or ask whether a belief
  was TRUE, because a character revises from what they later perceived, and
  grading beliefs against reality collapses the belief layer into the truth
  layer. `salience` is deliberately untouched (how much it mattered when formed,
  which drives consolidation) as distinct from `confidence` (how much they credit
  it now) -- and it is also what makes the mint confidence reconstructible.
- **Unbidden recall says "here is something else you own."** The repetition
  mechanisms (refrain skeleton, verbatim-repeat rewrite, plateau habituation)
  all say "not that"; `memory.contrast_memory` +
  `agents/character.py` (`_unbidden_trigger`) surface at most ONE
  high-salience memory DISSIMILAR to the current beat into a measurably stuck
  character's memory context, keyed `surfaces_unbidden.it_comes_back_to_me`
  so the field itself says it arrived on its own. Same epistemic envelope as
  ordinary recall (own rows, turn cutoff, frame filter), deliberately
  confidence-blind, a pure read (never `access_count`), substituting for one
  of the ordinary recall slots so the payload budget is constant.
  Deterministically edge-triggered with cooldown and two-strikes suppression;
  commit is the sole writer of the `cstate.unbidden` ledger. Absorption at
  the place-recall-zero tier, an open drive-rupture window, or a gated mind
  suppress it outright -- engine-crisis machinery outranks texture.
- The stored events row is omniscient (for the author/audit trail). `recent_events`/`recent_events_for_observer` in `scene.py` scrub concealed content off the path that feeds mapping's lore query, and `director_context(entitled=False)` scrubs the path that feeds `mapping_stage` (X18 closed). The Director stays entitled to omniscience — it owns objective causality and cannot resolve a beat it may not see; mapping is not, because it emits lore and `scene_patch` room notes that reach every perceiver.
- Entity state blobs referencing concealed actors are withheld at commit time — the entity's state is only updated when overtly perceived.
- Portal states for rooms the player cannot see are withheld from the narrator payload.
- Background-presence co-located character names pass through that presence's OWN `known` ledger entry, not the player's. An unregistered presence has no entry and therefore recognizes nobody; the shared scene-manager payload uses the intersection across its managed cast.
- A character deciding turn N never retrieves memories stamped turn N or later; `search_memories` hard-filters on `current_turn_idx` before ranking. Author-facing search routes deliberately omit it.
- Dialogue memories store appearance labels for unrecognized speakers, not canonical names.

### Authority boundaries

- The player owns the declaration of player speech, thought, and attempted action.
- The Director interprets and resolves declarations; it must not silently replace the player’s declared content.
- Every element of the player's `sequence` is attributed to the player: perception prepends the actor label to its `observable` surface, and the narrator renders it as the player's own conduct. An interior or autonomous outcome the player authors FOR a character therefore must not stay in that sequence — `agents/director.py` (`_route_authorial_npc_beat`) rerouts it to an offer that character's own agent decides on. A player act that merely *causes* such an outcome stays the player's; the target's response is resolved through the reaction phase.
- An act that lands on another character must carry that character in `targets` — the reaction-phase gate, claim subject binding, and perception's targeted-observer check all read it, so an unbound act is invisible to every one of them (`agents/common.py`, `bind_sequence_targets`).
- Character agents declare behavior but do not author objective success.
- Model output is provisional until deterministic commit code validates and persists it.

### Persistence boundaries

- `steps` and `variants` preserve inspectable intermediate outputs; exactly one active variant should exist per materialized step.
- A checkpoint is established before a pipeline run mutates durable state.
- Stable event identifiers should prevent duplicate memories and duplicate persistence on reruns.
- Primary turn effects are atomic: a commit-domain failure must roll back every durable effect from that turn. Slow provider work belongs in preparation before the outer write transaction.
- New persistent fields require an explicit owner, snapshot/export behavior, restore behavior, and a regression test.

## Source-of-truth order

When several representations disagree, resolve the conflict deliberately rather than updating all copies blindly.

1. **SQLite rows and `world` keys** are the durable runtime state.
2. **Active step variants** are the inspectable result of the current turn.
3. **`PipelineContext`** is the in-memory working state for one execution.
4. **Pydantic schemas** define accepted structured model output.
5. **Prompts** describe desired behavior but do not override deterministic validation.
6. **`Design.md`** describes intended architecture and carries a verified status table; code still wins a disagreement, and the losing row should be corrected rather than left standing.

Physical-world authority (Phase 3a consolidation): the frame-scoped `world.scene` blob is the sole runtime authority for live rooms/positions/entity state; `room_registry` is the sole cross-frame ledger of room identity/retirement; `world_entities` is a derived projection of the scene commit (built from the prepared post-dedup diff); `world_placements` is decommissioned. Every scene writer must keep the registry projection in sync (`commit_scene` does; `world_put` calls `commit.sync_room_registry_with_scene`). See `docs/DATABASE.md`.

## Safe change workflow

1. Reproduce the problem with a focused test or saved payload.
2. Identify the earliest stage where the data first becomes wrong.
3. Fix that stage rather than compensating in the Narrator or UI.
4. Validate the structured output in `schemas.py` when possible.
5. Keep persistence deterministic in `commit.py`.
6. Run the focused tests, then `make check`.

Avoid broad rewrites of `agents/runtime.py`, `app.py`, or `memory.py` unless the change has dedicated tests. These files contain orchestration seams; seemingly local edits can affect reruns, variants, streaming, and commits.

Never add runtime artifacts to source control. `engine.db*`, `*.sqlite*`,
`backdrops/`, `__pycache__/`, `*.py[cod]`, and content-bearing `*.trace.json`
files are local state or private diagnostics and are ignored deliberately.

## Large-file landmarks

### `agents/`

- `director.py`: scene establishment, interpretation, and resolution
- `mapping.py`: lore routing and retrieval
- `perception.py`: opening, action-onset, and outcome views
- `character.py`: one character decision
- `background.py`: two paths. The scene-manager (`scene_life`, one batched call voicing every managed presence in a room, config `off`/`ambient`/`full`) runs when enabled; otherwise the original one-beat, stateless reaction for a single named background presence with no character sheet (deterministically gated by `commit.py`'s `pick_background_reactor`)
- `loops.py`: deterministic micro-perception, reactions, and dialogue rounds
- `narration.py`: player-facing prose
- `common.py`: shared normalization and delivery helpers
- `storage.py`: steps and variants
- `runtime.py`: dispatch, plans, streaming, resume, and reruns
- `__init__.py`: compatibility exports for `from agents import ...`

### `app.py`

- Application assembly and shared remap primitives
- Bootstrap/settings
- Lorebook tree and links
- Providers
- Characters and personas
- Lorebooks
- Chats and branches (`chat_archive.py` owns portable export/import)
- Memories
- Turns, rerolls, checkpoints, resume, and async streaming

### Supporting boundaries

- `auth_routes.py`: typed host authentication routes and cookie transport
- `chat_archive.py`: typed, atomic portable chat export/import service and routes
- `pipeline_trace.py`: privacy-conscious export, validation, and offline replay
  of persisted step/variant history
- `spatial_orientation.py`: bearing math and reciprocal edge normalization,
  re-exported through `spatial.py` for compatibility

### `memory.py`

- Lorebook hierarchy and graph resolution
- Chat lorebook attachment resolution
- Memory normalization and hybrid retrieval
- Summaries and consolidation
- Snapshot/restore
- Lore entries
- Relationships
- Vector index

### Frontend

The UI uses browser globals rather than ES modules. `theme-init.js` loads in
the document head before rendering. The remaining script order at the end of
`static/index.html` matters:

`utils.js → components.js → editors.js → lorebooks.js → backdrops.js → chat.js → settings.js → themes.js → app.js`

Do not rename a shared function without searching every JavaScript file.

## Test organization

- `test_pipeline_safety.py`: materialization, recent-event, and commit failure behavior.
- `test_spatial.py`: room/barrier/hearing/visibility and scene-diff behavior.
- `test_memory_*`: retrieval, deduplication, commit, and restore.
- `test_lore*`: lorebook graph, stability, and restore.
- `test_archive_fidelity.py`, `test_chat_archive_service.py`: portable archive
  completeness, remapping, and service boundaries.
- `test_pipeline_trace.py`: trace privacy defaults, integrity, and replay.
- `test_frontend_state_guards.py`: static frontend ownership and race guards.
- `browser_tests/`: real Chromium behavior; optional locally, required in CI.
- `test_character_schema.py` and importer tests: resource formats.
- `test_psychology_runtime.py`, `test_character_psychology_fill.py`, and
  `test_character_card_psychology_ui.py`: live psychology, non-destructive
  old-card completion, and editor/prompt coverage.
- `test_theory_of_mind.py`, `test_tom_normalization.py`, and `test_ability_isolation.py`: private cognition boundaries.
- `test_perception_intent_leak.py` and `test_character_self_knowledge.py`:
  adversarial checks for structured-observation smuggling and cross-character
  private/body-state leakage.
- `test_authorial_channel.py` and `test_authored_outcome_attribution.py`: who an
  authored outcome belongs to — reroute of puppeted cognition/response, target
  binding, the reaction gate, and claim subject binding.
- `test_observation_derivation.py`: whether the structured observations
  perception derives are *true*, as distinct from leak-free.
- `test_pipeline_audit_leak_gaps.py`: information-leak gaps from the pipeline
  audit — rear-arc action injection, `co_present_positions` destination leak,
  string-line concealment erosion, reroll memory turn cutoff, dialogue memory
  recognition gate, entity-state concealed-actor gate, omniscient event
  re-entry, surgical concealed redaction, portal-state visibility gating,
  background-presence recognition gate.
- `test_reroll_restore_integrity.py`: checkpoint restore refreshes cast cache
  and rolls back cast membership.

Add a test next to the subsystem it protects. A bug involving leaked dialogue or private knowledge belongs in a perception/cognition test, not only in a narrator snapshot.
Tests that request `temp_db` are collected into the slow/full tier. A test
intended for `make test-fast` must not depend on another test having initialized
`engine.db`; use pure constants or explicitly stub settings/prompt lookup.
