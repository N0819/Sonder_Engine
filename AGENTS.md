# Editing Guide for Coding Agents

This file is the operational map for changing Sonder Engine safely. It is written for both human contributors and AI coding agents.

## First-pass orientation

Before editing behavior:

1. Read `Design.md` § Genre-agnostic substrate, world-specific law before adding
   or specializing a mechanic.
2. Read `docs/guides/PIPELINE.md` for execution order and ownership boundaries.
3. Search `docs/CODE_MAP.md` for the handler or function involved.
4. Read `docs/guides/DATABASE.md` before changing persistent state, archives, or restore paths.
5. Read the relevant schema in `llm/schemas.py` before changing any model output.
6. Read the corresponding commit function before adding fields that should persist.
7. Read `docs/guides/TESTING.md`, find the nearest regression test, and run the narrow test first.

`docs/CODE_MAP.md` is generated; never hand-edit it. Regenerate and verify it
after moving or adding functions:

```bash
make map
make structure
```

`AGENTS.md`, `Design.md` and everything in `docs/guides/` are the maintained
guidance set — current implementation authority, changed in the same commit as
the behaviour. `docs/design/`, `docs/experiments/` and `docs/archive/` are
context rather than authority: a design note argues for one subsystem, an
experiment record reports one unrepeatable run, and an archived document has
been superseded. Check any of their claims against source and the maintained
guides before acting on them. [`docs/README.md`](docs/README.md) is the index
and says which is which.

## Edit routing

| Change | Primary files | Usually inspect too |
|---|---|---|
| Player input interpretation | `agents/director.py` (`director_interpret`) | `llm/schemas.py`, `llm/prompts.py`, pipeline tests |
| Director orchestration (specialist scopes/gates, the six specialists, the fan-out and its `director_fanout_mode` concurrency choice, the prose author's scoped sheet, the owner-routed reconciliation repair) | `agents/director_scopes.py` (`SPECIALISTS`, `_CHANNEL_GATES`, `_dispatch_specialists`, `_PROSE_DUTY_SHIPPED`, `_gate_facts` — the sole writer of the specialist registries), `agents/director_fanout.py` (`fanout_is_parallel`, the beat views and scoped payload assembly, `_orchestration_scope_backstop`), `agents/director_reconcile.py` (`_route_repair_omissions`, `_verify_already_true`, `_acquit_addressed_events`), `agents/director.py` (`_run_specialists`, `_PROSE_DUTY_GATES`, `_prose_author_scope`, `_specialist_repairs`, `_reconcile_resolution` and the stage bodies), `llm/prompts.py` (`SPECIALIST_PROMPT_SPECS`, `specialist_prompt`, `PROSE_AUTHOR_SHEET`, `prose_author_prompt`, the `_RESOLVE_*`/`RESOLVE_*` segments — each belongs to exactly one specialist or to the prose author's sheet; there is no monolithic sheet and no registry entry for one, and `test_every_delegated_block_has_exactly_one_owner` holds each block to a single owner) | `llm/schemas.py` (`SPECIALIST_CHANNELS`, the `Director*Specialist` models, `orchestration` on both Director outputs), `llm/providers.py` (the `director_*` specialist roles; `ROLE_FALLBACKS` is deliberately EMPTY — an unconfigured specialist follows `default` like every other blank row, and MUST NOT be given `director` as a hidden parent again: a host who leaves the six blank is parking them somewhere cheap, and inheriting `director` moved all six onto the writing model the moment that row was set, which is the opposite of the reason the rows were left alone; per-specialist spend stays separable through the ROLE STRING in `_log_usage`, never through the fallback), `tools/project_check.py` (`check_specialist_prompt_chunks`, `check_prose_author_chunks`), design note 19, `tests/test_director_orchestration.py` — scope gates key on scene state and FAIL OPEN per channel and per prose duty; a channel or prose duty shipping content outside every served scope must reach `tell_director`, never silence; KNOWLEDGE FIREWALL, CHANGES MANIFEST, PLAYER-ASSERTED FACTS, DIALOGUE LOG and the authority contract are never gateable; the specialists are SHARED between interpret and resolve (one definition, two callers — interpret is not a lesser authority); specialists never stream, run PARALLEL by default with `director_fanout_mode: sequential` available for a provider that will not take concurrent requests (same hands, same scopes, same canonical assembly — NOT a fallback to the dead monolith), and assembly is in canonical order with failure isolated per specialist; the movement backstop and every cross-channel judgment stay with the orchestrator on the MERGED diff; the offscreen specialist is an ops surface only (no simulator); one step per Director stage, no new runtime keys; the reconciliation seam repairs an omission in a delegated channel at that channel's OWNING specialist (one scoped call, additive merge, fail-open) and only player claims and undelegated categories still buy the full-core `resolve_repair` call; a repair call's own `resolved_events` echo is read back, so a hand asked to encode something it can see is already carried can say `already_true` instead of shipping a staleness warning against a change it just certified (measured cause: chat 71 turn 10's 105.5s resolve, where the full-core repair re-ran the prose author to encode a change the body specialist owned); the seam's evidence classes must accept EVERY spelling of a change the diff legitimately encodes — garment as well as wearer for attire, structured endpoints over the free-text subject for contacts, a `cross` op's ended endpoint, a station for a within-room drop — because the manifest's `subject` is model-worded and a wording gate turns coverage into a coin flip per reroll (measured: 5 of 11 live manifest items read as omissions against diffs that encoded them); and `channels_replaced` counts author content that LOST to ownership, so it is `[]` on every healthy beat — read `channels_filled` for what a specialist contributed; and the beat's changes are NUMBERED by the engine in `_manifest_items` (1..N, emission order = narrated chronology, never a model-authored id), carried into each specialist's manifest slice by the one filter that also records which ids it is answerable for, and echoed back on `resolved_events` -- an event its OWNER settled (`encoded`/`already_true`) buys no second LLM call, while a verdict on an id the specialist was never handed is discarded, a FAILED specialist acquits nothing, and `not_mine` reports scope under-grant rather than closing the gap (design note 21; detection is untouched and the echo is evidence, not authority -- `encoded` is still checked against the merged diff); an `already_true` verdict is additionally verified against STANDING state (`_verify_already_true`) -- a defect detector, never a truth prover, because change DIRECTION lives only in manifest prose and prose matching stays out of bounds: a provably incoherent ledger (removed-yet-resident attire, wearing/regions drift, a position naming a non-room, a contained body with its own disagreeing position) refuses the acquittal as a NAMED defect and the gap still escalates, while anything undecidable falls through to trust; diff application is order-independent by construction and `test_diff_application_is_order_independent_by_construction` is the tripwire that forces a future sequential channel to be classified consciously; and any fan-out thread must receive a context COPIED IN THE PARENT, one copy per job (narration.py's `narrator_extra` is the worked example) -- ThreadPoolExecutor workers inherit no contextvars, so a copy made inside the worker is a copy of nothing, and `cancel_event`, the ledger/warning sinks and `active_frame_id` all silently read None (measured: five specialist calls, zero ledger entries, live variant v26648) |
| Flow planning, resume, or streaming | `agents/runtime.py` (`build_plan`, `_run_pipeline`) | `agents/storage.py`, `persist/checkpoints.py`, pipeline tests |
| Opening scene generation | `agents/director.py`, `agents/perception.py` | `story/scene.py`, `world/spatial_merge.py`, `persist/commit_scene_state.py` |
| Perception or information leakage | `agents/composer.py` (the percept builders that DECIDE admission — `presence_percepts`, `speech_percept`, `act_percept`, `contact_percepts`, `body_region_percepts`, `residue_percepts` — and `render_view`/`render_episode`, which realise them from percepts alone), `agents/perception.py` (`_source_channels`, `_redact_concealed_from_event`, `_composer_outcome`), `agents/common.py` (`_delivery_ok`, `_AUTONOMY_VERBS`, `bind_sequence_targets`), `agents/loops.py` (`deterministic_micro_perception`), `agents/background.py` (`_present_others`), `agents/narration.py` (`_visible_portal_states`) | `world/spatial_senses.py` (`scent_level`, `visual_level_between`), `world/spatial_containment.py` (`containment_conceals`), `world/spatial_routing.py` (`visible_adjacent_rooms`), `story/scene.py` (`recent_events_for_observer`), `llm/schemas.py`, `mind/memory.py` (`current_turn_idx` cutoff), `persist/commit_entities.py` (S3-A8 copy-forward signal), `persist/commit_memory.py` (dialogue-memory recognition gate), perception tests — concealed actions are sentence-level redacted from the resolved event per-perceiver, including pronoun-subject continuations; touch-only sources get surface-translated event text; scent is barrier-gated; per-observer boundaries are STRUCTURAL — perception makes no model call, so admission is decided on typed data one observer at a time and a rendering path cannot ADD information; `_delivery_ok` consolidates containment, awareness, sight (including rear-arc) and hearing (with proximity) on ONE of the two delivery paths -- its only callers are `agents/loops.py`'s two micro-round deliveries, and perception and the composer answer the same four questions from the same primitives without routing through it, which is the drift risk `docs/UNBUILT.md` 3.8 holds; background-presence names pass through that presence's OWN recognition ledger (an unregistered presence recognizes nobody); portal states for unseen rooms are withheld; **every payload that hands a mind prose somebody else wrote needs the identity floor too** — `observer_label_fn` gates one name, `observer_name_scrub`+`scrub_names_deep` gate a paragraph, and both read the same `known` map. **The floor runs in the other direction too**: `common.self_reference_forms` + `perception._composer_self_forms` rewrite a mind's OWN minted epithet (not just its name) into second person before delivery, guarded by the labels that observer already uses for other bodies — see design note 20 and `tests/test_observer_epithet_floor.py`. Lore is the known case (it is objective record, written during play with canonical names, and `knowledge_for_character` gates which entries arrive but never who they may name); `spatial_frame.ahead_entity` was the case before it. Assume there are more; a beat's prose copied forward onto an entity this beat names is reported, not dropped; the events row is concealment-scrubbed on the `recent_events` path that feeds mapping's lore query |
| Character decisions or dialogue | `agents/character.py` (`character_step`, `_recent_self_lines`, `_recent_self_moves`, `_first_repeated_move`), `agents/loops.py` | `mind/affect.py` (`steering_intent_ids`), `persist/commit_memory.py` (settled want normalization), `mind/memory.py`, `story/scene.py`, `llm/prompts.py`, `tests/test_character_self_lines.py` — exact-line repetition and repeated conversational jobs are separate checks. Semantic similarity is a review TRIGGER, not proof of bad repetition — and since `e629d60` it opens no call: the findings are recorded on the step as `repeat_correction`/`move_correction`/`intention_correction`, read by `affect._advance_intent` and `_unbidden_trigger`'s `barren_goal` reason, and the beat stands. Repetition is weak output, not broken output. Preserve invited continuations, deliberate emphasis, callbacks, lists, and in-character riffs/rants. Target only an unmotivated reset that repeats an offer/question/handoff as though the prior turn was unheard. A dormant/blocked/satisfied/abandoned intention stays visible as history but cannot authorize a fresh want. **`interaction_loop`'s early exits end the BEAT, not the round** — so anything that changes ordering changes who is simulated at all, and a character who never ran has no appraisal, no `goal_impacts`, no drive strain, and no memory of having stayed quiet. **`initial_parallel_reactors` defaults to 1**, so by default there is no wave and the beat opens with one speaker (`Design.md`'s conformance row has the argument). Raised, the first wave is simultaneous in the FICTION: members declare blind, micro-perception is delivered only after every member is done, and exits are evaluated for the wave as a whole. Do not deliver mid-wave and do not thread it — `character_step` writes through `ctx`. `tests/test_interaction_first_wave.py`, `tests/test_interaction_focus_call.py` |
| Character psychology, stress, pain/pleasure, belief learning, or association learning | `story/character_schema.py`, `mind/psychology_runtime.py`, `mind/affect.py`, `agents/character.py`, `persist/commit_memory.py` | `llm/schemas.py`, `llm/prompts.py`, `story/importers.py`, character-card UI, `mind/theory_of_mind.py` (`belief_credence`, `absorbed_cap`, `select_active_hypotheses`), `mind/psychology_runtime.py` (`cognitive_absorption`), `mind/memory.py` (`reconcile_inference_confidence`), psychology and information-leak tests — transient state may use only the character's scrubbed current observations, own sheet, own body state, and earned memory; surface-affect SATURATION has a cost when `affect_habituation` is on (default off, byte-identical): `affect.resolve_surface_habituation`/`_compress_top_slice` compress only the ceiling-slice above the character's own baseline (sustained ordinary warmth is a trait and pays nothing), the hedonic RELEASE pierces (refunds the cost, waives compression on its beat — shock and novelty were both measured failing as peak discriminators), and `tools/affect_replay.py` replays any character's stored appraisals through both resolver arms against checkpoint ground truth before any tuning change ships |
| Background (unregistered) presence reactions | `agents/background.py` (`background_react` per-presence path, `scene_life` manager path), `persist/commit_background.py` (`pick_background_reactors`; `pick_background_reactor` is the single-winner wrapper) | `agents/perception.py` (merge into dialogue_log), `llm/prompts.py`, `llm/schemas.py`, `story/scene.py` (`background_config` — `max_reactors` default 1, hard ceiling 3; `scene_life` default `off`) — a directly-addressed or `routed_to_background` presence is forced past the cap, and a presence MINTED THIS BEAT is seeded into the gate rather than looked up, since `track_background_presences` writes its record at commit and the forced hand-off could otherwise never see the one class of presence that most needs it. AT POST IS SCOPED BY EARSHOT, not by `station_room == player_room`: `_at_post_within_earshot` asks `hear_level` at the heard-in-FULL bar `_character_address_of` already sets, so a clerk one open doorway from a ringing bell can answer it and a shut door still means nobody comes. Perception always modelled this (`_beat_for_presence` runs the same check before handing a presence a word of the beat) — the gate withheld the agency while granting the hearing, which is why the Director kept walking such figures into the room so they could speak. A presence placed by `state_diff.positions` alone is tracked from that ledger, keyed on the positions name rather than `cast_changes.who`, which is a description the model wrote rather than an identity anything else keys on |
| Lore a background presence INVENTS (claims, ratification, contradiction) | `world/background_claims.py` (`record_claims`, `unratified_claims`, `settle_claims`, `write_canon`) | `agents/background.py` (`_claimed_refs`), `agents/director_views.py` (`_unratified_background_claims`), `llm/schemas.py` (`StateDiff.ratified_claims`/`contradicted_claims`), `persist/commit_background.py` (`prepare_background_claims`, `track_background_presences`), `mind/memory.py` (`ensure_chat_canon_book`), `tests/test_background_claims.py` — **ratifying is a WRITE, not a status flag.** "It becomes canon" means a row in `lore_entries` in the chat's own canon book, because that is the only durable store of play-established facts and the only one anything reads back; setting `status = "ratified"` and stopping made a claim true and unreachable in the same instant. Contradiction is EXPLICIT ONLY while adoption may also be inferred from the objective record — prose naming a subject is evidence the fiction took it up, but prose cannot announce a rejection. **Inferred adoption requires a LATER beat**: `background_react` runs after `director_resolve`, so a reference standing in the resolved event of the beat a claim was made in is the presence echoing the Director's own prose, and reading that as adoption has the causality backwards. Explicit ratification still lands on the claim's own beat, because naming a claim in `state_diff.ratified_claims` is a decision whenever it arrives. Named in both lists settles as contradicted and writes nothing: canon is a one-way door, and the disagreement is recorded rather than averaged. Embeddings are prepared before the outer transaction (`prepare_background_claims`); do not let a canon write pay for a provider round-trip under the write lock. `CLAIM_TTL_TURNS` is deliberately uniform — the claims ride EVERY resolve payload, so expiry is eight declines rather than a missed window. Measured on the live corpus 2026-08-18: **7 claims, all 7 ratified, 0 contradicted, 0 expired**, in one chat. That is not a tuning baseline — until `5ab591e` the gate settled every claim on the beat that produced it, so contradiction and expiry had no chance to fire and the numbers describe the defect rather than the design. Re-measure after a run under the repaired gate; the seven existing rows stay as they are, because canon is write-once |
| What the cast may do off screen | `story/scene.py` (`OFFSCREEN_LIFE_LADDER`, `normalize_offscreen_life`, `offscreen_life_allows`), `world/offscreen.py` (`apply_plan_ops`, `advance_epoch`, `advance_reactive_plans`, tick/profile producers), `persist/commit.py` (`offscreen_plans` then `offscreen_epoch` domains) | `web/app.py` (`dlg_get`/`dlg_put`), `static/js/settings.js` dialogue panel, `director_resolve` prompt, `docs/design/OFFSCREEN_LIFE_DESIGN.md`, `tests/test_offscreen_life.py`, `tests/test_offscreen_reactive.py` — the rungs are `schemas.BehaviorController`'s and must stay so; a second friendlier vocabulary would diverge and then disagree. A CEILING, never an instruction: nothing is obliged to act at any level, because cost must keep scaling with dramatic density rather than story length. `reactive` is built but deliberately narrow: only a present character's same-beat declaration may open/cancel a typed plan, and firing may enact only the pre-adjudicated effect. Gate payload and commit; a model may volunteer fields. An unreadable level falls to the DEFAULT, never to the floor. Do not give `character_agent` behaviour without carrier C and the knowledge firewall: a ticking character advances on its OWN delivered knowledge, never the player's position or recent acts |
| How off-screen information reaches a mind | `world_events` (objective truth), `story/carriers.py` (`advance_carriers`, `reports_for_state`), `story/couriers.py` (`run_couriers`; a `stops` list makes the body a caravan — dwell on the clock, two-way exchange at stops), `story/artifacts.py` (`run_artifacts`; a posted claim acquired only by reading, stopped by tearing down), `persist/commit_mechanics.py` (`world_events`, then post-memory `information_carriers` domains), `agents/character.py` (`carried_reports`) | Truth is not knowledge. Only a non-empty public `witnessed` surface may enter a carrier, and only that holder's private payload reads it. **Who may acquire has widened three times and the rule has not**: a registered character standing at that location was the whole of it, and acquisition now also reaches the PLAYER (`carriers.persona_entry`, a persona has no `chat_chars` row so its envelope is a frame-scoped world key), a body arriving LATER at a surface that landed earlier and is still standing (`ARRIVAL_SURFACES` — consequences fire off-screen on a clock in rooms chosen because nobody is in them, so a witness-on-the-beat rule meant one live drive emitted a public surface, took zero acquisitions, and had a character walk in the next turn and look directly at a barred gate while learning nothing forever), and a standing CROWD trading news both ways with a caravan at its stop (`_crowds_acquire`). What has not widened is the physics: each of the three is a body in a place, and none of them is a broadcast. The envelope moves with the holder's actual scene position. Co-location never copies knowledge; a listener learns through on-page speech → perception → memory. Never hand a full agent the objective event ledger. Crowd/message copies and degradation must extend this envelope, not add a broadcast timer — `story/couriers.py` is the worked example: a dispatched report is a BODY with a position on a `passable_path` route, advanced on the simulation clock, described for perception (`agents/common.couriers_for_room`), and stoppable (`question`/`silence` ops; a silenced rider's message never arrives). The perception half is connected as of 2026-08-18: `couriers_for_room` (with its twins `crowds_for_room` and `artifacts_for_room`) is assembled into every perceiver record in `agents/perception.py`, and `composer.room_content_percepts` mints each as an `ambient` percept — a standing feature of the room, not an event, not a body. The subtraction stays where it was computed: the courier's figure and which door he makes for and NEVER his message, that a bill hangs there and never its wording. A `due_seconds` fuse wearing a courier's name is the forbidden shape. An artifact is the carrier that does not move: reading is a COPY, not a mouth (verbatim, provenance `read`, retellings unchanged), so degradation happens only at mouths; a torn-down bill refuses reads, leaves perception, and teaches a passing caravan nothing — destruction is the artifact's silencing. The wording ceiling (`schedule_artifact_wording`) is presentation, never information: readers acquire the CLAIM, and the minted text lands out of band only while the bill still stands |
| Who may receive a paid off-screen character tick | `story/character_schema.py` (`character_offscreen_agent`), card editor `simulation.offscreen_agent`, `offscreen.full_agent_candidates` | Three gates compose: explicit card opt-in (default false), chat `offscreen_life=character_agent`, and living-world `antagonist_ladder=ceiling`. Selection also needs a private reason: that mind's active authored plan or carried evidence newer than its own last tick. Importance may rank spend but may never auto-opt in. The selector must not read player state, objective event payloads, or omniscient scene content |
| What the WORLD does on its own (living-world floors: routine residue, scheduled consequences, place obligations) | `world/living_world.py` (`LIVING_WORLD_BUILT` is the declared/built authority; `mint_consequences`, `record_obligations`, `attach_owed_history`), `world/routines.py` (pure; writes nothing), `world/mechanics.py` (`_fire_due_events` consequence branch), `persist/commit_mechanics.py` (`commit_transit_sweep` mint + obligation feed) | `agents/director.py` (`destination_residue`), `agents/mapping.py` (owed-history seam — the obligation ledger's ONLY reader; a second reader is an epistemic leak, pinned by `tests/test_living_world.py`), `llm/schemas.py` (`StateDiff.consequences`), `llm/prompts.py` (CONSEQUENCES ON THE CLOCK / DESTINATION RESIDUE / OWED HISTORY), `web/app.py` living_world routes, `static/js/settings.js`, `docs/design/DESIGN_LIVING_WORLD.md` §9 — the author's verbatim phase-2 constraints: information travels by carriers along routes, never by timer; nothing may privilege the player as a subject; a fired fuse is fact, but knowledge of it moves only by route. Everything defaults OFF; a fuse firing emits a notice ONLY when the player stands at its location |
| Objective action resolution | `agents/director.py` (`director_resolve`), `agents/director_movement.py` (the deterministic movement backstops: `_travel_continues`, `_travel_in_flight_view`, `_guard_approach_is_not_arrival`, `_reconcile_near_group_positions`, `_unreachable_position_writes`) | `llm/schemas.py`, `world/spatial_routing.py`, `persist/commit_scene_state.py` — `state_diff.positions` for the PLAYER has two guards and they cover different beats: the passable-route backstop runs only when interpret declared a movement, and `_guard_approach_is_not_arrival` covers the case where it declared none but staged the action `approach`. Approaching, arriving and entering are three beats; resolve only the ones declared. But a walk already DECLARED continues without being re-declared: `_travel_continues` advances one edge per beat (two on a `far`/`remote` edge) from the per-mover `scene.approach` ledger, writing the leg into `positions` BEFORE both guards above so it is judged exactly as a declared move is; `_travel_in_flight_view` hands the leg to the prose author as `travel_in_flight` BEFORE the resolve call, so the scenery changes on the page rather than behind it. Silence continues and an INTERRUPTION is what must be established — the Director asserts it in `travel_interrupted`, under a deterministic floor (no passable route, carried, arrived) it cannot argue with — because continuing executes the player's declaration while stopping them without being told overrides it. `out['travel']` is the one answer `persist/commit_scene_state.py` retires or keeps each approach record from. AND A STATION IS NOT A MOVER: `stations.at` resolves to the anchor's owning room, so a threshold anchor read as room membership and `_reconcile_near_group_positions` carried everyone near that body across with them; where nobody is travelling it may now only settle which ALREADY-OCCUPIED room wins, the player's above all |
| Narration | `agents/narration.py` (`narrator`, `_ENFORCEABLE_PREFIXES`, `_ordered_beat_events`), `agents/common.py` (`_check_narrator_fidelity`, `_check_player_person`, `_check_narration_person_match`) | narrator prompt in `llm/prompts.py`, output validation, `tests/test_merged_speakers.py`, `tests/test_observer_epithet_floor.py` — `event_order` is a SECOND delivery of this beat's prose to the player, so it carries the identity floor (`player_forms`) rather than inheriting one. Person is asked for AND verified: `_narration_person_counts` chooses it from the player's input and `_check_narration_person_match` re-runs the same detector over the output (warning-only, measured at 0.52% over 2,303 stored drafts). **fidelity has two separate questions and they are easy to conflate**: did the line survive (each view quote present verbatim), and did it land in the right mouth. Two speakers welded into one quoted span passes the first while failing the second, so the merge check is its own pass. Read `event_order` rather than the raw dialogue log for anything player-facing — it is already gated to lines that reached the player's view. An enforceable warning costs a rewrite, so only add one whose false-positive rate you have measured against the stored corpus |
| Whether a mechanism actually fires | `tools/fire_rates.py` | `tools/salience_replay.py`, `tools/remember_lines.py`, `tests/test_fire_rates.py` — **measure the fire rate before enriching anything.** Five mechanisms here were built, documented, tested and never ran once, and none looked dead from reading the code. Always state the DENOMINATOR: `memory_disputes` against every memory row reads 0 of 6,480 and means nothing (the field did not exist for most of that corpus); against the beats that could have carried one it reads 0 of 181, beside a sibling from the same commit at 78%, and that pair is a diagnosis. A mechanism with no opportunities reports `no chances`, never 0%. These tools open the database `mode=ro`; `salience_replay` copies it first, because `search_memories` writes `access_count` |
| How much a mind holds at once | `mind/affect.py` (`CAPACITY_LADDER`, `normalize_capacity`, `capacity_caps`), `story/character_schema.py` (`psychology.capacity`) | `persist/commit_memory.py` (both cap sites), `agents/character.py` (`self.attention`), `llm/prompts.py`, `importers.character_import_warnings`, `static/js/editors.js`, `tests/test_attentional_capacity.py` — scales the want and intention caps only. **Projects are NOT on this ladder**: `PROJECT_CAP` is a dramatic limit, and six slots lose the displacement rule that makes a project cost anything. Unset is stored as `""`, never backfilled to `ordinary` — backfilling makes "the author chose the middle" and "nobody has seen this field" the same value and silently kills the import warning. Tell the character its own ceiling; a want culled without the mind knowing the decision existed is a decision taken from it |
| Persistence or rollback | `persist/commit.py` (orchestrator, per-turn lock, tail domains, facade) and the thirteen `commit_*` domain modules (`commit_common`, `commit_place_graph`, `commit_destruction`, `commit_room_registry`, `commit_attire`, `commit_entities`, `commit_ledgers`, `commit_mapping`, `commit_background`, `commit_scene_state`, `commit_mechanics`, `commit_memory`, `commit_memory_write`), `persist/checkpoints.py` | `core/db.py`, `mind/memory.py`, restore tests — `from commit import X` still reaches every name (the facade re-exports them all, private names included), but a monkeypatch must target the module that DEFINES the function whose reader you want intercepted: a moved function resolves names in its own module's globals, and a patch on the `commit` facade whose reader moved is silently inert (`docs/experiments/AUDIT_COMMIT.md`) |
| The normalized projection of an entity (`world_entities`) | `persist/commit_entities.py` (`commit_world_entities`) | `world/spatial_merge.py` (`_merge_entity`), `llm/schemas.py` (`_fill_entity_names`, `is_derived_entity_name`), `tools/reproject_world_entities.py`, `tests/test_scene_entity_merge.py` — **a projection is derived from the MERGED scene, never from the diff that scene was merged from.** WHICH entities a beat touched is the diff's to say; WHAT they now are is the blob's. `_merge_entity` sits between the two, reading a schema default as silence and refusing a name the validator derived from the dict key, and writing the raw diff here skipped all of it: one pose-only beat left the blob saying "Blue Police Box"/vehicle and the durable row saying "Tardis 001"/object. Measured live at 15 of 480 rows named literally `Object`, 19 disagreeing with the blob about `name` and 24 about `kind` — a repair that had already landed in the blob and been left standing one layer down. Do not restate the derived-name refusal here; a second copy of that policy has to be extended by hand for every field the merge learns next |
| Portable chat archive export/import | `persist/chat_archive.py` | `web/app.py` remap primitives, `persist/checkpoints.py`, `mind/memory.py`, archive fidelity tests |
| Portable pipeline trace export/replay | `persist/pipeline_trace.py`, `tools/pipeline_trace.py` | `agents/storage.py`, `core/db.py`, `tests/test_pipeline_trace.py`; content-bearing traces are private local artifacts |
| Host authentication and guest access | `web/auth_routes.py`, `web/guest_access.py` | `web/app.py` router registration, auth/guest tests |
| Deterministic mechanics (timed arrivals, expiry, dock edges, zone/carry inference, news latency) | `world/mechanics.py` (`mechanics_sweep`) | `persist/commit_mechanics.py` (`commit_transit_sweep`), `world/spatial_transit.py`, `world/spatial_frames.py`, `tests/test_mechanics_sweep.py` |
| Weather, and how much of it a room gets | `world/weather.py` (`normalize_weather`, `room_exposure`, `weather_for_room`, `weather_words`, `advance_weather`) | `llm/schemas.py` (`StateDiff.weather`, `RoomDef.exposure`), director prompts, `persist/commit_scene_state.py` (declared-wins-then-drift block after the clock), `dressing/backdrops.py`/`dressing/ambience.py` consumers, `tests/test_weather.py` — ONE sky per scene; how much reaches a room is the ROOM's `exposure`, never per-room weather. `weather_words` takes a CHANNEL because sight and sound cross a wall differently: a cellar sees nothing of a downpour and hears it clearly, and a single undifferentiated list put audible-only phrases into an image prompt and repainted a cached backdrop for weather that room could not see. Exposure falls back to a keyword pass over room prose when unauthored — a convenience for presentation only, never an authority a mind may act on, and it defaults to `enclosed` so an unrecognised room stays dry. Drift is seeded and idempotent (same chat + same elapsed = same sky) so a reroll cannot change the weather. A declaration is written OVER the sky already blowing (`normalize_weather(value, base)`) and never in place of it, because a beat reports what it noticed rather than restating the whole sky — and because every default in this vocabulary is the MILDEST reading of its field, so a term the enum cannot read must keep what was there instead of clearing it. Extend `_SYNONYMS` rather than widening an enum when a model writes a word this cannot read; a silent fall to the default inverts the meaning of the beat |
| Going under and waking up (`awareness` conditions) | `agents/director_floors.py` (`_unsupported_player_awareness` for the onset, `_awareness_exits`/`_awareness_view` for the exit), `story/scene.py` (`awareness_conditions`, `awareness_map`, `NON_AWAKE_GATED`) | `agents/character.py` consciousness gate, `agents/perception.py`, `persist/commit_entities.py` condition INSERT/UPDATE, `tests/test_awareness*.py` — three separate questions, and the exit is the one that was missing: across the author's whole live corpus the Director never once emitted an ending (`active: 0`), and the only conditions that ever stopped gating were born with `expires_at_seconds`. A gated mind runs NO character step, so a stuck sleeper generates no pressure and reads as a quiet one. Waking is the WORLD's decision, never the sleeping mind's: the deterministic exits are the player's own declaration, a deliberate rouse aimed at someone `asleep` (never `sedated`/`unconscious`), and a full sleep on the simulation clock. An ending must re-use the SAME `condition_id` — commit UPDATEs on it, a new id opens a second row |
| Whether a barrier can be seen/heard/smelled/walked through | `world/spatial_barriers.py` (`_SIGHT_BARRIERS`/`_PASSABLE_BARRIERS`/`_AMBIENT_BARRIERS`/`_SCENT_BARRIER_LEVELS`, `normalize_barrier`), `world/spatial_senses.py` (`has_visual`, `sight_level`, `scent_level`) | `visible_adjacent_rooms`, `tests/test_see_through.py`, `tests/test_membrane_barrier.py` — four separate questions; `window` passes sight only, `bars` sight+sound, `membrane` passage only (the inverse of `window`: a curtained doorway, a tent flap). `has_visual`/`sight_level` is where sight is decided; `scent_level` is where scent is decided. `_SOUND_LADDER` is walked by RELATIVE steps — inserting a rung changes what its NEIGHBOURS shift onto, so `membrane` is deliberately off it. scent is the GRADED one, so its vocabulary is a table (`_SCENT_BARRIER_LEVELS`: `membrane`/`closed_door` muffle, `open`/`open_door`/`bars` pass, absent means blocked) and `scent_level` is its only reader — change the table, not the function. What the grade is a grade OF lives in three ledgers and one percept (`docs/design/DESIGN_SCENT.md`) |
| Containers you can be inside (jar/cage/crate/tent) | entity `enclosure` + `interior_rooms` + `state.hatch`, derived in `world/spatial_transit.py` (`_closed_enclosure_barrier`, `_open_enclosure_barrier`, dock-edge rewrite) | `tests/test_see_through.py`, `tests/test_membrane_barrier.py` — `enclosure` describes BOTH states: `opaque`/`transparent`/`barred` leave an OPEN interior see-through (right for a lid), `membrane` is opaque open or shut and overrides an authored `open_door`. A closed transparent container yields a `window` edge; `_is_carried_interior` keeps a carried container's inside out of the surrounding room's view. `enclosure`/`light_source` are in `_ENTITY_DEFAULT_FIELDS`, without which they could only be set at entity CREATION |
| A body part-way through an opaque boundary | `world/spatial_frames.py` (`infer_threshold_crossings`), `world/spatial_geometry.py` (`crossing_of`, `THRESHOLD_CROSSING_BEATS`), `world/spatial_senses.py` (`crossing_visible_from`, `spatial_rel_between`) | `persist/commit_scene_state.py` (called beside `infer_came_from`), `agents/perception.py`, `tests/test_threshold_crossings.py` — a position changes in an instant and a doorway does not; the room LEFT keeps `shapes` sight of the crosser for a couple of beats. A floor on sight, never a bonus, and dropped the moment the body moves again |
| A body sealed INSIDE another body | `world/spatial_containment.py` (`_body_interior_holder`), `world/spatial_identity.py` (`same_subject`, `_position_of`), `world/spatial_senses.py` (`scent_level`, `hear_level`), `world/spatial_merge.py` (`repair_entity_positions`), `agents/composer.py` (`contact_percepts` — a touch admitted without the act that produced it), `agents/perception.py` (`_composer_outcome`) | `tests/test_body_enclosure_channels.py`, `tests/test_touch_only_identity.py`, `tests/test_self_surface_when_enclosed.py` — **one being, one name.** (`_self_cannot_see_own_surface` used to be named here as the guard for an enclosed actor's own act surface; its only caller is the dead `_inject_onset_sequence`, and the composer enforces the property more bluntly instead — an actor never receives their own act surface in their own view at all, because `_composer_act` builds no perceiver for the acting player and `_composer_outcome`'s act loop skips the observer's own act.) A being routinely carries two at once (a cast display name and a scene entity id); five separate defects here were a single `==` between them, including a firewall that failed OPEN and delivered another mind's interoceptive state. `spatial_identity.normalize_scene_subjects` folds every subject-keyed ledger at merge so plain equality is correct on STORED data; `same_subject` remains the floor for raw model output that never went through a merge. Fold only where the canonical name is already live as a subject spelling elsewhere in the scene — `positions` legitimately keys objects and unregistered presences by entity id, and renaming those strands carried lights, derived stations and destruction cascades. Three directions, not one symmetric `concealed` flag: `inside_source` (perceiver within this source — maximal), `enclosed_from_source` (perceiver within something else — the room beyond is gone), `source_enclosed` (source within something the perceiver is outside — muffled outward). A perceiver is never sealed from themselves and co-occupants perceive each other normally. Scoped to BODIES via `_is_body_entity`: a crate is not a mass, and opaque is not soundproof. A `positions` value must name a ROOM — an entity id there is a category error that every spatial query answers as `unknown`, which looks exactly like distance |
| Being carried (pocket/jar/shoulder/hand) | `world/spatial_containment.py` (`container_of`, `contents_of`, `carrier_chain`, `derive_contained_positions`, `normalize_scene_containment`) | `llm/schemas.py` (`StateDiff.containment`), director prompt, `containment_facts`, `tests/test_containment.py` — a carried body's position is DERIVED from its carrier's, so writing one does nothing; getting out is an explicit release. Not `interior_rooms`, which is for containers you stand inside |
| Body size (shrinking/growing) and what it makes infeasible | `world/spatial_containment.py` (`scale_of`, `size_relation`, `normalize_scene_scales`), `world/spatial_contacts.py` (`contacts_broken_by_scale_change`) | `llm/schemas.py` (`StateDiff.scales`), director prompt, `spatial_facts`/`size_facts`, `tests/test_scale.py` — scale lives in `scene.scales`, is NOT pruned by position (a size is not a co-location), and cancels contacts on the resized body BEFORE the beat's own contact ops so a re-established hold survives |
| Body position / contact (who is touching whom, and where) | `world/spatial_contacts.py` (`apply_contact_ops`, `normalize_scene_contacts`, `contacts_of`, `_part_identity`, `_same_appendage`, `_displaces`), `world/spatial_contact_migration.py` (`contacts_from_entity_state`) | `llm/schemas.py` (`StateDiff.contact_ops`), director prompt, `agents/perception.py` payloads, `spatial_facts`, `tests/test_body_position.py` — a contact is a RELATION stored once in `scene.contacts`, never on either body; positions prune it. **An unqualified part noun is a definite description**: re-asserting the same limb on a new spot MOVES it, because the Director re-describes a standing hold rather than repeating it (`thumb→ear` then `thumb→ear_base` is one thumb). Two carve-outs must survive any change here — anything asserted in the SAME beat stands, and a bare noun never displaces a qualified limb nor the reverse. Do not add a synonym table for body parts: `tail_spade` is a nameable place on a tail, not `tail` blurred, and the structural rule (a refinement repeats the limb's own word) is what keeps that expressible. `detail` is excluded from the identity key exactly as `manner` is. **Contact must have one record**: anything that puts it back into an entity's `state` re-creates a copy nothing ages |
| Where in a room a body is | `world/spatial_geometry.py` (`derive_scene_stations`, `normalize_scene_stations`, `_station`, `proximity_rel`, `entity_side`, `entity_arc`) | `llm/schemas.py` (`StateDiff.stations`, `ScenePatch.stations`, `RoomDef.anchors`/`size`), `persist/commit_scene_state.py` (mapping fold), `world/comfort.py`, director + mapping prompts, `tests/test_stations.py` — `scene.stations` {name:{at,near:[]}} against per-room `anchors`. **Any new field on a scene-blob diff must be DECLARED on its Pydantic model**: `stations` was asked for by the prompts and merged by `merge_scene_with_diff` for two releases while `extra="ignore"` deleted it, and 0 of 45 live scenes ever got one. Keep `stations` a plain `dict[str, dict]`, never a typed sub-model — the merge is a PARTIAL per-entity update, so a default-filled `near: []` would clobber the standing roster, and `_dump`'s `exclude_none` would delete the explicit `{at: null}` that means "stepped away". Derivation from contact is additive and must never override a station the beat stated; a derived station outlives its contact but not a room change. "On the bed" is a station AT it + a contact WITH it + `state.posture` — do not add a fourth ledger for surfaces |
| Authoring edits to live positions (GM relocation) | `web/app.py` (`GET /api/chats/{cid}/positions`, `PUT /api/chats/{cid}/characters/{ch}/position`) | `scene.get_scene`/`spatial.room_of`, `static/js/settings.js` cast tab, `tests/test_char_relocation.py` — writes only `scene.positions`, requires an idle chat, validates room ids, and queues no narrator beat |
| Room identity/dedup/retirement, destruction (single-book + region cascades) | `persist/commit_room_registry.py` + `persist/commit_destruction.py` | `core/db.py` (`room_registry`), `persist/checkpoints.py`, `web/app.py` remaps, registry/destruction tests |
| Lore retrieval or hierarchy | `mind/memory.py`, `agents/mapping.py` | `web/app.py`, lore tests |
| Which lorebooks a chat *has* (browsing/editing) | `web/app.py` (`GET /api/chats/{cid}/lorebooks`) | `static/js/lorebooks.js` workspace tree, `tests/test_lore_tree_browser.py` — ownership, NOT `chat_lorebook_ids()`: that resolves reachability for retrieval and cannot see a book nothing hangs off |
| Lorebook-tree generation (authoring, not pipeline) | `story/importers.py` (`generate_lorebook_plan`, `resume_lorebook_plan`, `apply_lorebook_plan`) | `generator_lorebook*` prompts, `core/db.py` (`lore_gen_jobs`), `web/app.py` job routes, `static/js/lorebooks.js` generator tab, `tests/test_lore_gen_resume.py` |
| Character/persona format | `story/character_schema.py` | `story/importers.py`, generation/import/fill prompts, editor UI, schema and non-destructive-fill tests |
| Initial outfit / live attire | `story/character_schema.py` (`initial_outfit`), `story/scene.py` (`seed_initial_attire`) | `agents/director.py`, generator/import prompts, `static/js/editors.js`, attach/promotion routes, `tests/test_initial_outfit.py` — appearance is stable body description; initial outfit is authored starting clothing; `scene.attire` is mutable story state. Seed once and never reset existing attire from a card |
| Clothing regions and undressing | `story/attire.py` | `persist/commit_attire.py` (`apply_flat_change`, `_mint_shed_garments`), `agents/common.py` (`attire_view`), `story/character_schema.py`, `story/scene.py`, `director_resolve`/`fill_appearance` prompts, `static/js/components.js` (`fAttireGarments`), `tests/test_attire_regions.py`, `tests/test_attire_authoring.py` — `story/attire.py` is pure functions over dicts and must stay database-free. `waist` (belt line) and `groin` (private parts) are SEPARATE regions and must stay so — conflated, a body in only a sash reports its groin covered. A garment spans every region it covers (`regions_covered`); `_sync_spanning_garments` must run after any change that rebuilds garment dicts, or a kimono's sleeves stay fastened while its torso opens. Regions are the only authoring surface; `initial_outfit.wearing` is an INPUT format (older cards, imports, generators) migrated into regions on read and written back DERIVED, so the two cannot disagree and a `region_of` guess is visible where an author can fix it. `initial_outfit.state` is NOT retired, though this line said so: it is a live INPUT field with two readers — `character_schema._normalize_initial_outfit` keeps it through normalization, and `scene.seed_initial_attire` passes it to `attire.authored_entry`, so an authored "torn"/"open" note on a starting outfit reaches the ledger at seeding. What is retired is state as an ONGOING record: once the story starts, what happened to a garment is that garment's `condition`, and nothing writes back to `initial_outfit.state`. A loosened or open garment is STILL in `wearing`. `attire.decisive_targets` attributes a decisive act per body (garment, then first person in the player's own input, then a sole name) — the actor is not the target. **A garment name is not an identity**: every incoming handle goes through `attire.resolve_garment` against what the body already wears, or a redescription forks the garment into two. Resolution is tiered on purpose — `dedupe_regions` (which MERGES, destroying a garment if wrong) never uses the bare head noun, while note routing (which only mis-files a sentence) may. `dedupe_regions` runs on read and must stay idempotent, since a checkpoint restore replays it. **An unrecognised attire-diff key is read, not dropped** (`attire.coerce_diff_shape` + `commit_attire.interpret_attire_notes`); `coerce_diff_shape` must be run at commit as well as at validation, because rerunning a stage replays diffs stored before the schema knew the shape. Any writer of `scene.attire` outside commit — `app.attire_put` is the one — must re-derive all three representations (`attire.rederive_entry`), or `wearing`, `state` and `regions` drift apart and the next beat reconciles a body against itself |
| Extra body parts (tails, wings, horns — structured, not prose) | `story/character_schema.py` (`EXTRA_PART_ASPECTS`, `_normalize_extra_parts`, `character_extra_parts`, `persona_extra_parts`), `agents/common.py` (`extra_part_phrase`, `scene_extra_parts`, `observer_body_regions`) | `agents/perception.py` (`_observer_scene_payload` threading), `agents/character.py` (`body_parts` in the self payload), `agents/director.py` payloads, `story/scene.py` (`cast_scene_context`), `static/js/components.js` (`fExtraParts`), perception/resolve prompts, `tests/test_extra_body_parts.py`, `design_notes/11-extra-body-parts.md` — a part is BODY: card-level `embodiment.extra_parts`, read live like senses, never attire and never scene state, so persistence/archive/branch come free with the sheet and defaults stay byte-inert. `at` reuses `attire.REGIONS` (the seam that makes "does the skirt cover the tail's root" answerable); visibility rides the SAME `region_visibility` verdicts clothing uses, with `through_clothing` (default true) deciding whether garment coverage hides the part; a body is never concealed from itself. Part nouns stay free text and are already valid contact endpoints — `_part_identity`/`_same_appendage` are structural, so add no synonym table and no schema change for them |
| Per-story character-card edits | `web/app.py` (`PUT /api/chats/{cid}/characters/{ch}/card`), `chat_chars.sheet`, `scene.active_cast` | `static/js/editors.js`, cast tab in `static/js/settings.js`, `persist/chat_archive.py`, branch copying, `tests/test_chat_character_cards.py` — the override is authored configuration, not live `state`; identity name/uid are locked because scene and knowledge records use them as keys |
| Provider behavior | `llm/providers.py` | `web/app.py` provider routes, `llm/prompt_cache.py` |
| Whether a call is cached, and whether it lands on the replica holding the prefix | `llm/providers.py` (`prompt_cache_enabled_for`, `_cache_denied`, `_cache_passthrough_allowed`, `cache_affinity_allowed`/`_apply_cache_affinity`) | `web/app.py` (`_provider_public`, `PUT /api/providers/{pid}/prompt_cache`), the `cache` checkbox in `static/js/settings.js`, `tests/test_prompt_cache_toggle.py` — there are TWO request paths, native Anthropic (`_anthropic_system`) and aggregator passthrough (`_openai_system_message`), and both must ask the same predicate. They did not: the native one read only `FICTION_ENGINE_PROMPT_CACHE` and ignored `prompt_cache_deny` entirely, so the host switch reported off while every call went on caching. The UI must never re-derive the rule — it is a three-way interaction (built-in kinds, an allowlist, a deny list that outranks both) and two copies drift. It stays an ALLOWLIST: a provider that *rejects* an unrecognized `cache_control` key fails the turn, which is worse than not caching |
| Per-call request timeout | `llm/providers.py` (`request_timeout`, `clamp_read_timeout`, `_request_timeout`/`_httpx_timeout`) | the caller's own knob (e.g. the lorebook generator's `timeout` param); `REQUEST_TIMEOUT`/`HTTPX_TIMEOUT` stay the pipeline default |
| API behavior | `web/app.py`, `web/auth_routes.py`, or `persist/chat_archive.py`, according to route ownership in `docs/CODE_MAP.md` | matching file in `static/js/` |
| Browser UI | `static/index.html`, `static/js/`, CSS | matching API route in `web/app.py` |
| Language packs, story language, prompt language, or compositor grammar | `language_runtime/`, `language_packs/`, `agents/composer.py` Layer B | `core/pipeline_context.py`, `agents/runtime.py`, `llm/prompts.py`, `web/app.py`, `persist/checkpoints.py`, `static/js/app.js`, `static/js/settings.js`, `tests/test_language_packs.py` — protocol keys/enums remain canonical; a story-capable pack must cover deterministic recognition and rendering, never silently fall back to English guards |
| Inspecting a turn: per-perceiver views, engine repairs, concurrency, per-call cost | `static/js/chat.js` (`openPipeline`, `perceiverViews`, `perceiverSlice`, `renderEngineNotes`, `liveStep`), `web/app.py` (`pipeline_get`, `_perceiver_names`), `agents/runtime.py` (`_run_parallel_group`, `_with_engine_notes`), `agents/storage.py` (`ENGINE_NOTES_KEY`), `core/pipeline_context.py` (`StepTaggedWarnings`, `current_step_key`, `note_llm_call`), `llm/providers.py` (`call_ledger_sink`, `record_llm_call`) | `tests/test_pipeline_perspectives.py`, `tests/test_engine_notes.py`, `tests/test_llm_call_ledger.py` — three things a JSON blob cannot show: which mind a view belongs to, that a view is missing an entire sensory channel, and that two steps ran at once. Warning attribution is by contextvar, never by list position — the parallel groups run siblings on their own threads; the per-call ledger (`_engine_notes.llm_calls`: `{step_key, role, requested, served, in, out, cached, duration, kind}`) is attributed the same way, fed by `providers._log_usage` through `call_ledger_sink`, and must stay counts and identifiers, never content. `_engine_notes` is stripped by `active_content` so a rerun cannot carry the engine's own repair log into a prompt; anything added to it must stay diagnostic, since it rides every archive, branch and trace as opaque content |
| Extensions: the loader, the developer facade, or what an extension may reach | `extension_runtime/__init__.py` (discovery, trust classes, the enable set, `apply_plan_splices`, `notify_step_saved`, `dispatch_turn_committed`, install/remove), `extension_runtime/api.py` (`SonderExtensionAPI`, `ExtState`, `StepView`, `CommittedTurn`, `CharacterHandle`) | `agents/runtime.py` (`_extension_splices`, `_extension_step_saved`, `register_step`), `persist/commit.py` (the `dispatch_turn_committed` call in the commit tail), `web/app.py` (the `/api/extensions` routes), `static/js/extensions.js`, `static/js/settings.js` (the 🧩 menu), `extensions/cohesion-demo/`, `tests/test_extensions.py`, `tests/test_extension_install.py`, `docs/guides/EXTENSIONS.md` — three properties are load-bearing and none are obvious: plan splices must be a PURE function of durable settings and manifests or `resume_key_for_turn` breaks; every dispatch helper the core calls must be TOTAL, so a broken extension costs a turn nothing; and the four `ext:<id>` state homes exist so an extension inherits checkpoint/archive/branch coverage without a schema change. Manifest `capabilities` are DISCLOSURE for the consent dialog, never enforcement — do not add a guard there and call it a boundary |
| Test tiers, CI, or dependency support | `Makefile`, `.github/workflows/ci.yml`, `pyproject.toml`, `requirements*.txt`, `constraints.txt` | `docs/guides/TESTING.md`, `tests/conftest.py`, `browser_tests/` |
| Database shape | `core/db.py` | migrations, snapshot/export/restore code, tests |

## Core invariants

These are architectural guarantees, not stylistic preferences.

### Genre boundary and quality bar

- The engine core owns universal representation and enforcement: identity,
  space, time, contact, motion, containment, visibility, perception, knowledge,
  authority, conditions, causality and persistence.
- Genre-specific mechanics and interpretations belong in lorebooks. Where canon
  is silent, the Director may infer a local rule from the fiction model,
  established story facts and current circumstances. The priority is explicit
  canon, then established facts, then inference; inference never overrides
  lorebook canon.
- Do not hard-code one story's meaning of a wound, spell, transformation,
  technology, anatomy, social custom or supernatural effect into the shared
  substrate merely because that story exposed a missing representation. Model
  the reusable physical/causal fact and leave its world-specific consequence to
  lore and Director adjudication.
- The benchmark is higher-quality long-form fiction than a raw LLM call, not
  feature count. A new layer must justify its seams through measurable gains in
  continuity, causality, agency, epistemic integrity, memory or world-specific
  coherence; plausible prose alone is not evidence that orchestration helped.

### Information boundaries

**READ THIS BEFORE CHANGING ANY GUARD BELOW.** The firewall is not a
restriction on knowledge. It is a restriction on the FLOW of knowledge. A mind
may know anything it has a channel to; what it may not do is acquire a fact
that reached it through no channel at all. Every rule in this section is that
one rule, applied to a different pathway.

Five consequences, each of which has been got wrong at least once:

1. **Inference is the product, not the risk.** A character reasoning from what
   they legitimately perceived to a new conclusion is the thing this engine
   exists to produce — hence inference memories, `mind_model_updates` with
   confidence, belief revision, `i_suspect`. Never "harden" a guard by making
   minds conclude less. A character who remembers a green-glass lantern at the
   cellar stair and decides its owner is lying has done exactly the right
   thing; a character who knows a stranger's NAME has not, because no chain of
   perception yields a name. The test is never how far the reasoning went. It
   is whether every input it ran on reached that mind.

2. **A leak is a failure of the ENGINE, never of the model.** The deterministic
   floor must not depend on any model cooperating. If something crossed a gap,
   the code that was supposed to make it impossible did not run — and no model
   behaviour excuses that. Fix the seam; do not add a prompt clause and call it
   closed.

3. **A warning is not a leak.** A scrub firing (`scrubbed unearned identity`,
   `dropped a body with no sensory channel`) is the system WORKING: nothing
   crossed. Do not count warnings as model quality or as near-misses. They
   scale with cast size — five bodies produce far more identity scrubs than
   one — so comparing warning rates across stories of different sizes measures
   the story, not the model.

4. **Real leaks fail open and silent**, because the thing that would have
   announced them is the thing that did not run. Every leak found so far was
   discovered by measurement, never by an error: an identity comparison that
   returned False, a ledger form a resolver could not see, a lore field nothing
   scrubbed. When auditing, look for guards that CANNOT fire rather than guards
   that fired wrongly.

5. **Firewall integrity is therefore not a model-selection criterion.** It is
   an invariant. Choose models on latency, contract compliance, problem
   solving, creation depth and prose. If a model choice could move firewall
   integrity, that is a defect in the firewall.

And the reason the gap is worth protecting is not safety — it is that the gap
is GENERATIVE. Dramatic irony, deception, misidentification, a mind acting
confidently on a false belief, `record_dispute` existing at all: every one
requires the distance between minds to be real. Collapse it and the result is
not a freer story, it is one in which nobody can be surprised, deceived, or
wrong.

**The firewall is for MINDS, not for developers or tooling.** It constrains
what reaches a fictional mind. It says nothing about what the engine, its
instruments, or a third party may OBSERVE: the pipeline drawer, persisted
traces, `chat_archive` and `pipeline_trace` all read every mind's state at
once, and that is correct — reading a mind puts nothing in anyone's head. The
only place a breach can occur is the WRITE side, giving a mind a fact it had
no channel to.

That distinction is easy to lose, and losing it costs real capability. Read
access is not a security question, and an API narrowed "for firewall reasons"
on the read side protects nothing while making the engine less useful. Sonder's
firewall guarantee describes SONDER'S pipeline; an extension that reroutes
information owns whatever guarantee it then makes, and security is a question
for the extension registry, not for this boundary.

- A character may use only its perception, memory, knowledge configuration, relationships, private history, and explicit inferences.
- Objective world state must not be copied into a character context merely with an instruction to ignore unavailable details.
- Perception of an action onset and perception of its resolved outcome are separate passes.
- The Narrator should render the player-facing view, not an omniscient reconstruction of every private agent result.
- Every perceptual channel is barrier-gated: sight (`_SIGHT_BARRIERS`), sound (`_AMBIENT_BARRIERS` + material), scent (`_SCENT_BARRIER_LEVELS`), and touch (containment/concealment). Touch-only perception is cause-blind: surface sensations cross, the act producing them does not. Scent is attribution-blind in the same way and for the same kind of reason: the material crosses, and WHOSE it is crosses only when the observer also has sight of the body — so a muffled smell, and a smell from a body in the dark, arrive with no source at all. A scent therefore never defeats a disguise: it carries a material, never a name, and the label on it is the one `observer_display_map` already earned (`docs/design/DESIGN_SCENT.md`).
- **Per-observer boundaries are STRUCTURAL, not prompted.** Perception makes no
  model call at all: `agents/composer.py`'s percept builders decide admission
  on typed data, one observer at a time (`presence_percepts`, `speech_percept`,
  `act_percept`, `contact_percepts`, `body_region_percepts`, …), and
  `render_view`/`render_episode` realise them from percepts alone, taking no
  scene and no database. A rendering path structurally cannot ADD information.
  This replaced an earlier design in which each perceiver got its own LLM call
  (`_per_observer_model_views`, long gone) — the boundary is now the admission
  gate rather than a separate prompt, which is why there is no `perception`
  entry in `providers.ROLES`, `prompts`, or `schemas.SCHEMA_MAP`.
- The delivery gate `_delivery_ok` in `agents/common.py` consolidates containment, awareness, sight (including rear-arc/`behind_sources`), and hearing (with proximity) checks. **It is not universal, and this line used to claim it was.** Its only callers are the two micro-round deliveries in `agents/loops.py`; `agents/perception.py` and `agents/composer.py` re-derive the same four questions themselves (`hear_level`, `_in_plain_view`, `spatial_rel_between`, `composer._sense_graded`). Two families of delivery gate exist and can drift apart — registered as a structural risk in `docs/UNBUILT.md` §3.8, which is the entry to fix, not this row. Consolidating them is still the right change; asserting it has happened is what let the drift go unmeasured.
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
  — see [`docs/experiments/SPATIAL_LEARNING_EXPERIMENT.md`](docs/experiments/SPATIAL_LEARNING_EXPERIMENT.md)
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
- The stored events row is omniscient (for the author/audit trail). `recent_events`/`recent_events_for_observer` in `story/scene.py` scrub concealed content off the path that feeds mapping's lore query, and `director_context(entitled=False)` scrubs the path that feeds `mapping_stage` (X18 closed). The Director stays entitled to omniscience — it owns objective causality and cannot resolve a beat it may not see; mapping is not, because it emits lore and `scene_patch` room notes that reach every perceiver.
- Entity state blobs referencing concealed actors are withheld at commit time — the entity's state is only updated when overtly perceived.
- Portal states for rooms the player cannot see are withheld from the narrator payload.
- Background-presence co-located character names pass through that presence's OWN `known` ledger entry, not the player's. An unregistered presence has no entry and therefore recognizes nobody; the shared scene-manager payload uses the intersection across its managed cast.
- A character deciding turn N never retrieves memories stamped turn N or later; `search_memories` hard-filters on `current_turn_idx` before ranking. Author-facing search routes deliberately omit it.
- Dialogue memories store appearance labels for unrecognized speakers, not canonical names.

### Authority boundaries

- The player owns the declaration of player speech, thought, and attempted action.
- The Director interprets and resolves declarations; it must not silently replace the player’s declared content.
- **`director_interpret` is not a lesser authority than `director_resolve`; it is the same authority scoped to the player's input.** What the player's declaration asserts as already true is written to `state_assertions` — a full `StateDiff`, the same channels resolve uses, no subset — and previewed onto the scene before `perception_act` builds a single view, so nobody reacts to a world one beat stale. What bounds interpret is its SOURCE (the player's declaration alone), never a channel whitelist: an unfinished attempt, and anything acting on another character, is held back by being classified `contestable` and routed to the reaction phase. Resolve receives the same previewed world, may re-resolve any of it, and wins wherever it speaks about the same subject; silence does not revoke an assertion. Persistence is unchanged — the preview is a copy, the assertion merges into resolve's own diff, and commit writes the beat once (`agents/common.py`, `preview_player_state_assertions`).
- Every element of the player's `sequence` is attributed to the player: perception prepends the actor label to its `observable` surface, and the narrator renders it as the player's own conduct. An interior or autonomous outcome the player authors FOR a character therefore must not stay in that sequence — `agents/director_views.py` (`_route_authorial_npc_beat`) rerouts it to an offer that character's own agent decides on. A player act that merely *causes* such an outcome stays the player's; the target's response is resolved through the reaction phase.
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

Physical-world authority (Phase 3a consolidation): the frame-scoped `world.scene` blob is the sole runtime authority for live rooms/positions/entity state; `room_registry` is the sole cross-frame ledger of room identity/retirement; `world_entities` is a derived projection of the scene commit (built from the prepared post-dedup diff); `world_placements` is decommissioned. Every scene writer must keep the registry projection in sync (`commit_scene` does; `world_put` calls `commit.sync_room_registry_with_scene`). See `docs/guides/DATABASE.md`.

## Safe change workflow

1. Reproduce the problem with a focused test or saved payload.
2. Identify the earliest stage where the data first becomes wrong.
3. Fix that stage rather than compensating in the Narrator or UI.
4. Validate the structured output in `llm/schemas.py` when possible.
5. Keep persistence deterministic in `persist/commit.py` and its `commit_*` domain modules.
6. Run the focused tests, then `make check`.

Avoid broad rewrites of `agents/runtime.py`, `web/app.py`, or `mind/memory.py` unless the change has dedicated tests. These files contain orchestration seams; seemingly local edits can affect reruns, variants, streaming, and commits.

Never add runtime artifacts to source control. `engine.db*`, `*.sqlite*`,
`backdrops/`, `__pycache__/`, `*.py[cod]`, and content-bearing `*.trace.json`
files are local state or private diagnostics and are ignored deliberately.

## Large-file landmarks

### `agents/`

- `director.py`: scene establishment, interpretation, and resolution — the
  stage bodies and every model-calling function, plus the facade re-exporting
  its split-out family: `director_lingua.py` (language-pack access),
  `director_contact.py` (contact/material validate+merge),
  `director_views.py` (payload views and output audits),
  `director_movement.py` (spatial backstops), `director_floors.py`
  (prose-vs-diff floors), `director_evidence.py` (the seams' detection
  substrate), `director_scopes.py` (specialist registry/gates/dispatch —
  sole writer of `SPECIALISTS`, `_CHANNEL_GATES`, `_CHANNEL_SPECIALISTS`),
  `director_fanout.py` (beat views, payload assembly, scope backstop) and
  `director_reconcile.py` (repair routing and acquittal). Import direction
  is an invariant: nothing outside `agents/director*.py` may import an
  `agents/director_*` submodule, and no `director_*` module may import
  `agents.director` (that is the cycle the facade exists to prevent).
- `mapping.py`: lore routing and retrieval
- `perception.py`: opening, action-onset, and outcome views
- `character.py`: one character decision
- `background.py`: two paths. The scene-manager (`scene_life`, one batched call voicing every managed presence in a room, config `off`/`ambient`/`full`) runs when enabled; otherwise the original one-beat, stateless reaction for a single named background presence with no character sheet (deterministically gated by `persist/commit_background.py`'s `pick_background_reactor`)
- `loops.py`: deterministic micro-perception, reactions, and dialogue rounds
- `narration.py`: player-facing prose
- `common.py`: shared normalization and delivery helpers
- `storage.py`: steps and variants
- `runtime.py`: dispatch, plans, streaming, resume, and reruns
- `__init__.py`: compatibility exports for `from agents import ...`

### `web/app.py`

- Application assembly and shared remap primitives
- Bootstrap/settings
- Lorebook tree and links
- Providers
- Characters and personas
- Lorebooks
- Chats and branches (`persist/chat_archive.py` owns portable export/import)
- Memories
- Turns, rerolls, checkpoints, resume, and async streaming

### Supporting boundaries

- `web/auth_routes.py`: typed host authentication routes and cookie transport
- `persist/chat_archive.py`: typed, atomic portable chat export/import service and routes
- `persist/pipeline_trace.py`: privacy-conscious export, validation, and offline replay
  of persisted step/variant history
- `world/spatial.py`: a pure re-export facade over fourteen `spatial_*` modules
  (identity, barriers, transit, containment, contacts, contact_migration,
  substance, geometry, light, routing, senses, prose, merge, orientation --
  split plan in `docs/design/SPLIT_SPATIAL.md`, findings in
  `docs/experiments/AUDIT_SPATIAL.md`); every name, private ones included,
  still imports as `from world.spatial import X`, **and that is the only
  spelling a caller may use.** `tools/project_check.py` covers this family
  alongside `agents.director` and `persist.commit`: reaching past the facade to
  a sibling is an error, and the one exception is a test that PATCHES or
  introspects a sibling, because a monkeypatch must name the module that
  DEFINES the function it intercepts. `world/spatial_frames.py` matches the
  filename prefix and is NOT behind the facade — the family is read off the
  facade's own import block, never off a glob.
- `world/spatial_orientation.py`: bearing math and reciprocal edge
  normalization. One of the fourteen, named here because three documents used
  to present it as a directly-importable seam of its own

### `mind/memory.py`

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
Tests that request `temp_db` are collected into the slow/full tier. The old
rule here — that a `make test-fast` test must not depend on another test having
initialized `engine.db` — describes a hazard `tests/conftest.py` has since
removed at the root: `_redirect_default_database()` runs at conftest IMPORT,
before any test module is imported, pointing `db.DB` at a scratch file and
calling `db.init()` on it. So no test, fast or full, can reach the developer's
`engine.db`, and none has to arrange its own initialization. What survives of
the rule is the part that was always about the test rather than the database:
prefer pure constants or an explicit stub to a runtime settings/prompt lookup
when settings behaviour is not what the test covers.
