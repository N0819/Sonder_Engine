# Audit: agents runtime, loops, mapping, storage, skip stage/work, off-screen beat, layout/lots tiers, impossible knowledge, pipeline context

Auditor scope (2026-11-01, working tree at 84f3de23, clean). Read-only in the repo. Verification
scripts live in `<review scratch>/rt_audit/`
(`registries.py`, `plans.py`, `runs.py`, `reaction.py`, `offscreen0.py`, `badkey.py`, `skipabort.py`,
`pure.py`, `planned.py`); every DB-backed one ran against a scratch SQLite file in that folder
(`ENGINE_DB` pointed there before import, `db.configure` + `db.init`), never `engine.db`. Live-data
counts came from `engine.db` opened `mode=ro`. One focused test file was run
(`tests/test_turn_is_a_beat_that_happened.py`, 8 passed).

## Scope read

Read IN FULL, every line:
- `agents/runtime.py` 1-2180
- `agents/loops.py` 1-1985
- `agents/mapping.py` 1-713
- `agents/storage.py` 1-103
- `agents/skip_stage.py` 1-1224
- `agents/skip_work.py` 1-793
- `agents/offscreen_beat.py` 1-490
- `agents/director_layout.py` 1-746
- `agents/director_lots.py` 1-450
- `agents/impossible_knowledge.py` 1-232
- `agents/__init__.py` 1-101
- `core/pipeline_context.py` 1-625
- `agents/README.md` (whole), `docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md` (whole)

Read in part, only as far as a finding needed (NOT audited):
- `web/app.py` 846-1000 (stream/detach), 1135-1166 (`_require_turn_resolved`), 4855-4872, 5380-5393 (`pending` writers), 7655-7780 (rerun/resume/reroll routes)
- `persist/commit.py` 200-215, 455-560, 670-745; `persist/steps.py` 1-80; `persist/commit_scene_state.py` 1137-1215 (`_refuse_unheld_transfers`)
- `world/structure.py` 2562-2636 (`planned_context`), plant_structure's transaction lines; `world/spatial_identity.py` 790-870; `world/spatial_transit.py` 1000-1003, 1100-1135, 1180-1250, 1490-1500, 1550-1570; `world/mechanics.py` 810-860; `world/lots.py` 30-80; `world/charter_runtime.py` 670-830, 964-1024; `world/skip_itinerary.py` 424-455, 1410-1450
- `mind/skip_memories.py` 380-420; `mind/memory_lore_entries.py` search_lore head
- `core/jobs.py` 110-260; `core/db.py` transaction/_execute_retry heads; `tools/project_check.py` 2517-2620
- `extension_runtime/__init__.py` 883-940; `extension_runtime/api.py` 1540-1560, 1750-1790
- `story/scene.py` 464-560 (`get_scene`), 2492-2552 (`interaction_limits`, `dialogue_config`)
- `agents/common.py` (`_assert_plan_materialized`, `_merge_character_results`, `_next_speaker_candidates`, `_requires_director_resolution`, `acts_awaiting_resolution`); `agents/character.py` 1040-1135, 3590-3680; `agents/director_prose.py` 1195-1235, 3893-3935, 4560-4625; `agents/director_rooms.py` 2820-2880; `agents/director.py` 1920-1932, 2405-2425, 2738-2750, 5558-5572
- `docs/guides/PIPELINE.md` 301-362, 674-680, 1397-1446; `docs/guides/EXTENSIONS.md` 340-380, 1140-1190; `docs/guides/DATABASE.md` 55-70, 228-245; `docs/design/DESIGN_BUILDING_LOTS.md` 55-90, 130-144; `static/js/chat.js` 859-900, 2470-2505

## Findings

### F1 — A refused rerun has already rewound the turn: restore, checkpoint sweep, commit marked stale, then the refusal
- **Where.** `agents/runtime.py:1790-1799` runs before every refusal of the `from_key` paths:
  ```python
  if has_existing_steps:
      _restore_and_refresh()
      yield from _restored_notice
      ...
      _mark_the_commit_stale(turn_id)
      _claim_the_rerun(turn_id)
  ```
  and the refusals come after it: `runtime.py:1957-1964` (`raise RuntimeError(f"step '{from_key}' is not in this turn's plan")`, whose own comment says "Refuse before deleting orphans or marking anything stale"), `1884-1888` (stale `director_interpret` -> `StaleStepError`), and the opening's `1808-1813` (`not in the establishment plan`) and `1842-1845`. The `only_key` path gets the order right (its `not found` and stale-upstream checks, `1688-1716`, precede its restore).
- **Failure.** `POST /api/turns/{tid}/rerun` passes the body's `from_key` unvalidated (`web/app.py:7682-7705`), and the drawer's "Run from here" button is drawn on every step row (`static/js/chat.js:2490-2497`) -- including orphaned steps kept because they had >1 variant (`runtime.py:1967-1971`), and `ext:` steps of a since-disabled extension. Any such click: the pre-turn checkpoint is restored (this turn's commit taken back), later checkpoints are swept (`restore_checkpoint(..., sweep_later=True)`), unseen off-screen beats are taken back and their running jobs stopped (`stop_off_screen_beats`), the turn is claimed (`offscreen=0`), the commit is marked stale -- and the run then raises.
- **Verified.** `rt_audit/badkey.py` on a scratch DB: two committed turns, then `_run_pipeline(cid, t1, from_key="narrator_typo")`:
  ```
  before: checkpoints [1, 2]  world marker 2  stale t1 []
  refused: RuntimeError step 'narrator_typo' is not in this turn's plan
  after:  checkpoints [1]  world marker None  stale t1 ['commit']
  ```
  (The route's `_require_latest` limits the web path to the latest turn, so via HTTP only that turn's commit and the unseen off-screen beats go back; Resume re-runs the commit.) **CONFIRMED.**
- **Severity.** CORRUPTION (durable state rolled back, later checkpoints deleted and off-screen beats discarded by a request that is refused).
- **Fix.** Decide every refusal before `_restore_and_refresh`: check the key against the stored interpret's plan (the plan `resume_key_for_turn` builds) and the stale flags first; keep the post-restore check only as a backstop. Test: a stubbed `_run_pipeline` rerun with an unknown `from_key` (and one over a stale interpret) leaves checkpoints, world rows and stale flags byte-identical.

### F2 — The skip stage swallows the user's Stop, and the step built from the aborted calls is saved as fresh
- **Where.** `Aborted` is a `RuntimeError` (`llm/providers.py:517`). `agents/skip_stage.py` catches it as an ordinary failure at every model seam: `ask` (`:354`, `:372` `except Exception as exc: ... return None, f"no answer (...)"`), the futures loop (`:698-699`), `resolve_mind`'s decision request (`:555-556`), `judge_what_was_missing` (`:595-596`), and the wrappers at `:753-760` and `:777-786`. Only `skip_work` re-raises (`skip_work.py:423`, `:465`). The runtime then saves whatever the handler returned without re-checking the flag (`runtime.py:789-803`; `compute_step` checks only on entry, `:485`).
- **Failure.** Stop pressed while the cast are being asked: every in-flight `ask` returns `None`; every mind gets `itin.default_day` (empty `doing`, so `skip_work.told_rows` tells nothing, no encoder call is made and nothing re-raises); `skip_lives` returns normally and is saved `stale=0`; the abort surfaces at the next `compute_step`. Resume (`resume_key_for_turn`) treats `skip_lives` as complete, so the beat proceeds -- and the commit makes canon -- with every asked mind having slept/idled in place through the whole skip, and the out-of-band memory job writes memories from that log.
- **Verified.** `rt_audit/skipabort.py`: `_agent_json` raising `Aborted` -> `ask()` returns `None | no answer (Aborted: generation aborted by user)`; `issubclass(Aborted, Exception)` is True. The save path is traced (`_step_stream` -> `_save_or_reuse_variant` -> `save_step`, which sets `stale=0`). **CONFIRMED** (ask behaviour reproduced; save path traced, not executed end-to-end).
- **Severity.** CORRUPTION.
- **Fix.** The class, not the instance: `_step_stream` and `_run_parallel_group` call `_check_cancel()` after the handler returns and before `save_step`, so no step finished under a set flag is persisted; and the skip stage re-raises `Aborted` at its seams the way `director`, `background`, `llm_quality` and `skip_work` already do. Tests: (a) runtime -- a handler that sets the abort event then returns content leaves no variant; (b) skip -- `_agent_json` raising `Aborted` makes `skip_lives` raise.

### F3 — Any failed run wipes the cast arrival/departure notices the next beat must hear
- **Where.** `agents/runtime.py:2159-2169`:
  ```python
  except Exception:
      try:
          from persist.beat_order import RewindRefused
          if (not isinstance(sys.exc_info()[1], RewindRefused)
                  and q("SELECT 1 FROM turns WHERE id=?", (turn_id,), one=True)):
              wset(chat_id, "pending", [])
  ```
  `pending` is filled by the cast routes (`web/app.py:4866-4868` arrival, `5389-5391` departure), read by the interpret (`agents/director.py:1929`, `:2744` forces mapping) and cleared by the commit's own `pending` domain once consumed (`persist/commit.py:671-674`).
- **Failure.** Host adds a character (pending: arrival). The next beat dies at `director_interpret` on a provider error (HTTP 402 is the measured PQ10 case): the wipe runs, then `_discard_stepless_turn` deletes the row. The retry's interpret is never told the character arrived. A user Stop (the `except Aborted` branch) does not wipe, so the two failures disagree. The wipe dates to the first upload (eba771fb) with no stated reason; the commit already clears the list when it consumes it.
- **Verified.** Traced writers/readers above. **CONFIRMED** (by trace; not executed).
- **Severity.** CORRUPTION (queued state lost).
- **Fix.** Delete the wipe; the commit domain is the consumer. Test: queue an arrival, make `director_interpret` raise, assert `wget(cid, "pending")` still holds it.

### F4 — `deal_berths` read-modify-writes the charter registry from a background job with no lock and no transaction
- **Where.** `agents/director_lots.py:317` `registry = registry_for_update(cid, frame_id)` ... `:331` `save_registry(cid, registry, frame_id)`, called from `expand_lot` in the rooms-in-view job (`director_rooms.py:2839-2843`). `save_registry` outside a session goes straight to `wset_for_frame` (`world/charter_runtime.py:964-1022`). The commit writes the same row once, at `flush_registry_session()` inside `with transaction(), registry_session():` (`persist/commit.py:556`, `:681`), and `transaction()` is `BEGIN IMMEDIATE` (`core/db.py:2358`).
- **Failure.** The job reads the registry while a commit's transaction is open (WAL: it sees the pre-commit row), then its write blocks on the commit's lock (`_execute_retry`, up to 30 s) and lands after it -- overwriting the six registry writers' changes that commit just flushed (sightings, public evidence, placements, presence conduct, carrier state). `plant_structure`, beside it, does its read-modify-write inside `transaction()` (`world/structure.py` ~1501).
- **Verified.** Traced; not reproduced (needs two threads timed against a commit). **PLAUSIBLE.**
- **Severity.** CORRUPTION.
- **Fix.** Wrap `deal_berths`' read and write in `with transaction():` so the read happens under the write lock. Test shape: assert the read-modify-write runs inside one transaction (patch `transaction` to record nesting), plus a two-thread test with a held `BEGIN IMMEDIATE`.

### F5 — A short room slug captures any destination or query that contains its letters, and the beat is walked there
- **Where.** `agents/mapping.py:286` `plan = planned_for(target)` -> `world/structure.py:2584` tier 1:
  ```python
  if not exact and not any(key in folded for key in keys):
  ```
  and `agents/mapping.py:331-332` `if any(sp == folded or sp in folded for sp in room_spellings(rid, room))`. A `planned` verdict is then made canonical for every reader by `core/pipeline_context.py:193-212` (`canonical_movement` rewrites `to_room`, which `PipelineContext.declared_movement()` serves to the resolve floors and the commit's destination ledgers).
- **Failure.** The plan holds one room `inn`. The Director declares a walk to "the spinning mill" (never planned): the compiler answers `planned`, `declared_movement()` becomes `{'to_room': 'inn', 'declared_as': 'the spinning mill'}`, the beat goes to the inn and no `declared_destination_unplanned` need is filed. Same for "the winner's podium", "Finnegan's forge", "the dinner hall". For location queries a held room `inn` answers "the old spinning mill", "the inner keep" and "dinner at the Ferrier house" as `known`, so `location_query_unmatched` is never raised.
- **Verified.** `rt_audit/planned.py` and `rt_audit/pure.py` (registry stubbed in-process):
  ```
  classify_movement: {'to_room': 'inn', 'status': 'planned', 'declared_as': 'the spinning mill'}
  declared_movement after canonicalisation: {'to_room': 'inn', 'why': 'to find the miller', 'declared_as': 'the spinning mill'}
  query 'the old spinning mill' -> known
  ```
  **CONFIRMED.** `docs/UNBUILT_WORLD.md` §1.127's residual says "the deterministic matcher is deliberately exact" -- it is not (tiers 1 and 2 are loose).
- **Severity.** WRONG-SCENE (the player is walked into the wrong place); SILENT-NOOP for the suppressed needs.
- **Fix.** The class: a spelling sits inside a description only as whole slug words -- `f"_{key}_" in f"_{folded}_"` in both readers (the name-word tier already reads words). Test: plan holds `inn`; "the spinning mill" -> `unplanned`, "the Inn's back room" -> `planned`; scene room `inn`, query "the inner keep" -> `unmatched`.

### F6 — At autonomy 0 a contested beat leaves reactors with no declaration at all
- **Where.** `agents/runtime.py:1092-1110`: contested + autonomy 0 plans `reaction_loop` and no `character:<id>` steps, on the comment "reaction_loop above already gives every reactor its single character_step declaration". The planner's reactor list is widened by rejoined, acted-upon, skip far end, hearers, engaged and enclosure (`:993-1084`). `reaction_loop` (`agents/loops.py:1940-1980`) asks only `flow.reactors` widened by acted-upon (`:1945`), cut to `max_reactors` (`:1947`), skips a reactor with no onset view (`:1958`), and `break`s after the first reaction that needs resolution (`:1977`) -- which a contested physical reaction usually does.
- **Failure.** Player swings at Ann; flow reactors [Ann, Bob]; Cy, in the next room, hears the shout (planner widens him in). Autonomy 0: Ann reacts (contestable dodge -> break); Bob and Cy never run -- no appraisal, no memory of choosing, the narrator renders their silence. At autonomy > 0 the interaction loop picks them up, so only autonomy 0 strands them.
- **Verified.** `rt_audit/plans.py` (all gates stubbed) shows the autonomy-0 contested plan `[... 'perception_act', 'reaction_loop', 'director_resolve', ...]` with the hearer planned for and no character step; `rt_audit/reaction.py`: `reaction_loop asked: [1] stop_reason: completed`. **CONFIRMED.** The docstring (`loops.py:1906-1912`) also claims the loop runs on `contested or possible_reactors`; the planner plans it on `contested` only.
- **Severity.** WRONG-SCENE.
- **Fix.** One reactor derivation shared by `build_plan`, `interaction_loop` and `reaction_loop` (they are three copies today); give the `character:<id>` path the `already_reacted` dedup the interaction loop has (return the reaction for an id already in `ctx.reaction_results`) and plan the per-character steps at autonomy 0 even when contested. Test: autonomy 0, contested, two flow reactors + one hearer -> every one of the three has a stored declaration.

### F7 — The compiler reads a renamed room's old name as unplanned; the prose Director reads it as held
- **Where.** `agents/mapping.py:267` `held = scene_room_id(scene, target)` -- no registry aliases -- while `agents/director_prose.py:1215` resolves the same destination with them (`destination_place(..., aliases)`, aliases from `room_aliases`, `:1257`).
- **Failure.** A room minted as "Scullery" and since renamed "Kitchen" (the registry keeps "Scullery" as an alias): the Director's beat walks to "Scullery". The prose reader resolves it to `mill_kitchen`; the compiler answers `unplanned`, files `declared_destination_unplanned`, and `canonical_movement` leaves `to_room` as "Scullery" for the commit's destination ledgers -- the chat-114 split `canonical_movement` exists to prevent.
- **Verified.** An inline `.venv/bin/python -c` (not saved): `destination_place(None, scene, 'Scullery', {'mill_kitchen': ['Scullery']})` -> `('mill_kitchen', True)`; `mapping.classify_movement(...'Scullery'...)` -> `{'to_room': 'Scullery', 'status': 'unplanned'}`. **CONFIRMED** (the disagreement; the alias read from a live registry not exercised).
- **Severity.** WRONG-SCENE (a planning need and a second spelling of a held room).
- **Fix.** Pass `room_aliases(cid, ...)` into `classify_movement`'s `scene_room_id` (one reader answers "is this room held?"). Test: scene room with a registry alias; a declared walk under the alias -> `known`, `to_room` the room id.

### F8 — A vessel bound for a held room spelled by its name raises a transit planning need every beat
- **Where.** `agents/mapping.py:212` `if not (destination and (destination in rooms or planned_for(destination))):` -- exact key -- while the mechanics reading of the same field folds (`world/mechanics.py:828` `held = scene_room_id(scene, destination)`, `world/spatial_transit.py:1494`).
- **Failure.** `destination_room: "Cope's Boatyard"` with the scene room `copes_boatyard` named "Cope's Boatyard" and no plan row: the compiler files `transit_destination_unplanned` for a room the world holds, asking the Writers' Room to plan a duplicate of it.
- **Verified.** `rt_audit/pure.py`: `scene_room_id -> 'copes_boatyard'`; `compiler's needs: [('transit_destination_unplanned', "Cope's Boatyard")]`. **CONFIRMED.** Sibling of the registered `settle_departures` exact-id rule (`UNBUILT_WORLD.md` §1.225, "A built end under another id"); this reader is not registered.
- **Severity.** WRONG-SCENE (a spurious need; a duplicate room if the Room answers it).
- **Fix.** `held = scene_room_id(scene, destination)`, as the mechanics reads it. Test: the `pure.py` case yields no need.

### F9 — The impossible-knowledge floor counts a word as aired only if it was said in this very frame
- **Where.** `agents/impossible_knowledge.py:206-210` `... WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? ...`, called with the beat's own frame (`agents/character.py:1123-1124`). The module's rule (`:189-191`): "a word anyone has said aloud has a channel, whoever heard it".
- **Failure.** A name said aloud in the parent frame before a bubble split (or in a bubble since merged back) is "never aired" for the other frame; a mind there who hears it from someone who did hear it is handed a cue that the speaker could not have known it. The firewall is a gap; this invents one, and a mind treating a legitimate speaker as uncanny is a false inference fed by the engine.
- **Verified.** Traced the query and its caller. **PLAUSIBLE.**
- **Severity.** WRONG-SCENE.
- **Fix.** Read the frame's lineage (its parent up to the split, merged children), or the whole chat -- "anyone has said aloud" is the rule. Test: a token said in frame A at idx 3, spoken to an observer in bubble B at idx 9 -> no cue.

### F10 — The rulebook rows the Director is handed are English in every story
- **Where.** `agents/mapping.py:385` `"The day here runs %g hours; it is %s%s."`, `:412` `"Weather: "`, `:441` `"%s is a creature: it hunts %s ..."`, `:461` `"%s holds these posts here: %s."` -- literal English templates, not `compositor_text` (which the rest of the deterministic prose in this scope uses: loops' micro-views, `how_it_went`).
- **Failure.** A Japanese story's Director is handed its day, weather, creature and post rules in English beside a Japanese sheet.
- **Verified.** Read; no pack template exists for these rows (`grep` of `language_packs/*/cards/compositor.json`). **CONFIRMED** (that the text is English; the model-side effect not measured).
- **Severity.** WRONG-SCENE (language-pack hazard; not a word list).
- **Fix.** Move the four templates into `compositor.json` (en + ja) and render via `compositor_text(..., language)`. Test: a `ja` story's `rulebook_rows` carries no ASCII-only sentence.

### F11 — An extension stage anchored `before:director_interpret` never runs, the interpret runs twice, and every turn errors after it commits
- **Where.** `agents/runtime.py:1909-1911` runs `director_interpret` explicitly at ord 0, then walks the spliced plan from index 1 regardless of what index 0 holds: `:1974` `start_i = keys.index(start_key) if (start_key in keys) else 1`, `:1976` `i = 1`. `docs/guides/EXTENSIONS.md:356-358` and `:1145-1149` name `director_interpret` first among the anchors an extension may use; `api.add_stage` refuses only `character:` and `ext:` anchors (`extension_runtime/api.py:1557`).
- **Failure.** Plan `[ext:demo:pre, director_interpret, compile_world_context, ...]`: index 1 is the interpret, so it is computed again (a second model call; its step's `ord` rewritten from 0 to 1); the extension stage is never computed; the commit lands; then `_assert_plan_materialized` raises, `run_pipeline` reports a fatal error for a committed turn, and wipes `pending` (F3). Every turn of every chat with that extension enabled.
- **Verified.** `rt_audit/runs.py` part A:
  ```
  interpret calls: 2  ext stage calls: 0
  commit content: {'committed': True}
  run ended with: RuntimeError: Pipeline completion invariant failed; missing from context: ext:demo:pre; ...
  ```
  **CONFIRMED.** No test anchors before the interpret.
- **Severity.** CRASH.
- **Fix.** Walk the plan from index 0 and skip `director_interpret` by key when it already ran (and default `start_i` to the interpret's index + 1), or refuse `before:director_interpret` at `add_stage` with a reason. Test: a spliced stage before the interpret runs once, the interpret once, no invariant error.

### F12 — A completed off-screen beat at idx 0 is reported as an unfinished opening, and its Resume cannot run
- **Where.** `agents/runtime.py:879-880` `if turn["idx"] == 0: plan = establishment_plan(chat_id)` -- unconditionally -- while the run itself plans an idx-0 off-screen beat as an ordinary off-screen beat (`:1672-1673` `establishment = (turn_row["idx"] == 0 and not is_offscreen_beat(chat_id, turn_row))`; the comment at `:1657-1671` explains why such a beat exists).
- **Failure.** In a world stood up with no player, a bubble's first beat is idx 0. `resume_key_for_turn` returns `director_establish` for it although every step is complete: the drawer offers Resume; `_require_turn_resolved` (`web/app.py:1145-1166`) answers 409 to any new turn in that frame while this beat is its latest; and Resume runs `_run_pipeline(from_key="director_establish")`, which rewinds (F1) and raises `not in this turn's plan`.
- **Verified.** `rt_audit/offscreen0.py`: `resume_key_for_turn on a completed off-screen beat at idx 0: director_establish`; `resume from that key: RuntimeError step 'director_establish' is not in this turn's plan`. **CONFIRMED.**
- **Severity.** CRASH (the frame refuses turns; the resume fails and rewinds).
- **Fix.** Use the run's own predicate in `resume_key_for_turn` (`idx == 0 and not is_offscreen_beat(...)`). Test: the `offscreen0.py` setup returns `None`.

### F13 — A hand-edited interpret with a name in `flow.reactors` crashes every replan and the turn-creation gate
- **Where.** `agents/runtime.py:991-992` `reactors = [int(char_id) for char_id in (fl.get("reactors") or []) if int(char_id) in valid_ids]`; same in `agents/loops.py:1941`. The step edit route stores any JSON (`persist/steps.py:73-80` says so), and the model path normalises (`director.py:2488`), so only an edit reaches this.
- **Failure.** `"reactors": ["Ann"]` -> `ValueError` in `build_plan`, i.e. in every resume/rerun and in `resume_key_for_turn` under `_require_turn_resolved` (500 on the new-turn route for that frame).
- **Verified.** Read. **PLAUSIBLE** (manual-edit path only).
- **Severity.** CRASH.
- **Fix.** `normalize_character_refs(_list(fl.get("reactors")), cast_rows)` as `interaction_loop` already does (`loops.py:1116`). Test: a stored interpret with a name in `reactors` plans the matching id.

### F14 — A lot's storeys and cellar are told to the architect and never held
- **Where.** `agents/director_lots.py:166-171` accepts any integer `level` from the answer; only the joins are held (neighbouring storeys, `:196-205`) and the room count (`LOT_ROOMS_MAX`, `:164`). `LOT_STOREYS_MAX` (`world/lots.py:42`) caps only what a lot may *ask* (`:75`). The card says "It has the storeys the plan gives" (`language_packs/en/cards/system_prompts/prose_contract/layout_lot.txt`).
- **Failure.** A lot planned `storeys: 1`, no cellar, whose far look says a cottage: an answer with levels -1..4 is planted whole, no note. The lot's `storeys`/`far_look` and its planted building now disagree (two representations of one fact), and the layout tier lays out the tower. Where the plan gives no storeys, `LOT_STOREYS_MAX` does not bound the answer either; `LOT_ROOMS_MAX` (14) is the only ceiling.
- **Verified.** `rt_audit/pure.py`: `planted levels: [-1, 0, 1, 2, 3, 4] notes: []`. **CONFIRMED.**
- **Severity.** SILENT-NOOP (the field does nothing to the answer).
- **Fix.** Set aside, with a note, rooms outside `[-1 if cellar else 0, storeys-1]` (or `LOT_STOREYS_MAX-1` where the plan gives none) and whatever is then unreachable. The caps themselves are the owner's (named and tabled in `DESIGN_BUILDING_LOTS.md` "Defaults"); no number proposed. Test: the `pure.py` answer plants only level 0 and says why.

### F15 — Six documents still say a `not_known` skip row changes nothing; and the memories no longer agree "by construction"
- **Where.** 1342bbde made `skip_work.told_rows` tell `not_known` rows (`agents/skip_work.py:168`) and tag them (`_part_tag`), but left: the module docstring (`skip_work.py:18-21` "`done` ... a `not_known` row's outcome is not known"); `skip_stage.py:57` ("Each mind's `done` rows on the map are told") and `:897` (FarEnd); `Design.md:348` ("A `failed`, `not_known`, off-map or asleep row changes nothing" and "Not built: ... the mind's own part of a `not_known` row ... the owner's call"); `docs/UNBUILT_LIVING_WORLD.md:1524-1531` (§1.99d registers it as an open owner's call); `docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md:419` and `:546`.
- **Answer to the brief's question (6).** `skip_work.py:73-77` claims "THE MEMORIES AGREE BY CONSTRUCTION ... a row it remembers as done is a row whose changes the world now carries". That still holds for `done`. For an `[own part]` row (`not_known` because the plan named someone, `with`), the world now carries the mind's own part -- the lamp is out at dawn -- while the memory job tells the row as `skip_record_not_known`: "{name} set about it, and the rest was out of {name}'s hands" (`language_packs/en/cards/compositor.json:568`, chosen in `mind/skip_memories.py:409-411`) and its check pass holds each memory to that wording. The memory may therefore say the dawn extinguishing was not his to finish while the world shows it finished. `[partly: without ...]` rows agree (`skip_record_not_known_without`: "did it as far as it would go without ...").
- **Verified.** `git show 1342bbde --stat` (5 files; none of the six docs); read each site. **CONFIRMED** (docs); the memory/world disagreement **PLAUSIBLE** (depends on the writer and its check).
- **Severity.** STALE-DOC (plus a PLAUSIBLE WRONG-SCENE in memory).
- **Fix.** Update the six texts and delete the §1.99d entry (CLAUDE.md: "Delete an entry in the commit that lands it"); give an `[own part]` row its own record words ("did their own part; how the other answered is not theirs to know"). Test: `how_it_went("Elias", "not_known")` for a `with` row does not deny the mind's own completed part.

### F16 — PIPELINE.md, the stated authority on the turn's flow, has no skip stage and still describes two parallel pairings
- **Where.** `docs/guides/PIPELINE.md:305-330` (normal-turn diagram: no `skip_lives`; `grep -c skip_lives` = 0, likewise `CLAUDE.md:90`); `:1410-1420` "Both pairings go through `_run_parallel_group` ... (The third pairing, full mapping beside action-onset perception, went with the mapping model ...)" and "a typical story runs strictly sequentially and correctly shows no groups at all"; `:1436` "Each recomputation creates a new immutable variant"; `:337-340` "When a `reaction_loop` ran, it already collected each reactor's declaration".
- **Failure / truth.** `compile_world_context` + `perception_act` run as a group on every beat without a skip (`runtime.py:2007-2023`, restored in 1d61d3d5, 2026-09-07); the serial path reuses a byte-identical variant (`_save_or_reuse_variant`, b8453e1d); F6 shows the reaction-loop claim false; and the resume section omits that every rerun restores the pre-turn checkpoint and sweeps later ones (`runtime.py:1563-1650`, `:1636`).
- **Verified.** Read against the code and `plans.py`. **CONFIRMED.**
- **Severity.** STALE-DOC.
- **Fix.** Add `skip_lives` and the replan after it to both diagrams; restate the three pairings; say which path dedups; document the restore + sweep. Test: none (docs).

### F17 — agents/README.md's registry paragraph, pipeline_context's `runtime._run_step`, and the register's "deliberately exact"
- **Where / truth.**
  - `agents/README.md:65-80`: "**Nothing checks that the four agree.**" -- `tests/test_pipeline_context_fields.py:28-37` checks `STEP_HANDLERS` keys against `PipelineContext` fields. "seventeen entries ... FIVE entries are exercised by no test" -- `STEP_LABELS` has 18 now; `skip_lives` is a sixth label no test exercises. `SCHEMA_MAP` is keyed by the model call's schema, not by step id: 8 of the 13 plan keys are absent from it (`commit`, `compile_world_context`, `narrator_extra`, `perception_act`, `perception_establish`, `perception_outcome`, `reaction_loop`, `skip_lives`), so checklist step 2 ("including `SCHEMA_MAP`, keyed by step id") misleads. A fifth registry exists: `static/js/chat.js:859-883` `FRIENDLY_STEP_LABELS` (currently complete). The module list (`:5-26`) omits six modules of this package that own plan behaviour (`skip_stage`, `skip_work`, `offscreen_beat`, `director_layout`, `director_lots`, `impossible_knowledge`).
  - `core/pipeline_context.py:89`, `:132`, `:179` (and `story/greetings.py:677`, three tests): "armed on every step (`runtime._run_step`)" -- no such function; the funnel is `runtime.compute_step` (`runtime.py:444`).
  - `docs/UNBUILT_WORLD.md` §1.127 residual: "the deterministic matcher is deliberately exact" -- false (F5).
  - `docs/UNBUILT_PERCEPTION.md` §1.129, "PX5's THIRD floor, in `agents/loops.py` ... no third-body admission at all" -- landed in 4665a673; `loops.py:563-575` calls `_act_surface_admission`.
- **Verified.** `rt_audit/registries.py` output; greps. **CONFIRMED.**
- **Severity.** STALE-DOC.
- **Fix.** Restate the paragraph from the script's output (and add a test asserting every plan key is in `STEP_HANDLERS`, `STEP_LABELS`, `FRIENDLY_STEP_LABELS` and `PipelineContext`, dynamic forms excepted); rename the three references; correct the two register entries.

### F18 — The drawer says a step reroll leaves the world alone; for a committed turn it rewinds it, unconfirmed
- **Where.** `static/js/chat.js:2474-2477` -- "Every step's own reroll restores the checkpoint too when the step IS commit -- everything else leaves world/memory state alone" -- and the confirm dialog guards only `commit`. `agents/runtime.py:1726-1744` restores the pre-turn checkpoint for ANY pre-commit stage rerolled on a committed turn and marks everything after it stale (the turn then needs Resume, except narrator/narrator_extra which flow through the commit).
- **Verified.** Read. **CONFIRMED.** (Frontend file outside this audit's scope; listed because it describes runtime behaviour.)
- **Severity.** STALE-DOC.
- **Fix.** Correct the comment and confirm before any reroll on a committed turn. Test: the frontend guard test (`tests/test_frontend_state_guards.py`) can assert the confirm for a non-commit key.

### F19 — The PM19 variant dedup does not reach the parallel groups, so the two deterministic stages it was written for still mint duplicates
- **Where.** `_save_or_reuse_variant` (`runtime.py:806-841`) is called only from `_step_stream` (`:800`); `_run_parallel_group` calls `save_step` directly (`:781`). `compile_world_context` and `perception_act` -- the deterministic pair the dedup's docstring names -- always run as a group on a beat without a skip (`:2007-2023`; the pairing was restored two days after the dedup, b8453e1d 2026-09-05 vs 1d61d3d5 2026-09-07).
- **Failure.** Every rerun from `compile_world_context` (or a resume after a failure there) adds a byte-identical variant to both.
- **Verified.** `rt_audit/runs.py` part B: after two reruns `('compile_world_context', 1, 3), ('perception_act', 2, 3)` while serial stages stay at 1. Live, `engine.db` (`mode=ro`), last 400 turns: inactive variants byte-identical to the active one -- `compile_world_context` 135, `perception_act` 32, `perception_outcome` (serial path) 0, `director_resolve` 0. The regression test drives `_step_stream` directly (`tests/test_turn_is_a_beat_that_happened.py:141-157`; ran, passes). **CONFIRMED.**
- **Severity.** PERF (storage and drawer noise; the "variant is an alternative" invariant).
- **Fix.** Route `_run_parallel_group`'s save through `_save_or_reuse_variant`. Test: rerun from `compile_world_context` twice through `_run_pipeline` -> one variant each.

## Efficiency

1. **Reactor gating re-reads the scene ~20 times a beat.** `interaction_loop` (`loops.py:1115-1158`) wraps each of six widenings in `_drop_absent(ctx, _drop_non_awake(...))`: seven `get_scene` (`loops.py:656`) and seven `awareness_map` reads (`:619`), plus the scene read inside each `widen_reactors_*` (1-2 each, `agents/common.py`); `build_plan` repeats the widening with its own reads, and `reaction_loop` once more. `get_scene` = a DB read, a JSON parse (0.55 ms for the largest stored scene, 54.8 KB, measured), `apply_solved_plans`, `lay_held_open_marks` and the onset overlay. Per beat with reactors. Fix: read scene + awareness once per stage and pass them in (the planner already holds `_scene`/`amap`). Gain: ~20 scene parses and ~8 awareness queries a beat; cheap.
2. **Byte-identical variants on the deterministic pair** (F19): 135 + 32 duplicate rows (0.73 MB) in the last 400 turns; free to fix.
3. **Micro-perception recomputes per-observer sets per action event.** `deterministic_micro_perception` calls `_micro_body_forms` and `_micro_seen_bodies` inside the event loop (`loops.py:571-575`); neither depends on the event. `_micro_seen_bodies` walks every key of `scene.positions` -- things included ("positions is not a body roster", `offscreen_beat.py:389`) -- calling `visual_level_between` for each. Per micro-round x observers x action events x positioned subjects. Fix: hoist both above the event loop and filter to `scene_names_body`. Gain grows with crowded rooms and long sequences.
4. **`aired_in_story` scans the frame's whole dialogue history per candidate token.** `LIKE '%word%'` cannot use an index, so every active `director_interpret`/`director_resolve` variant of the frame is read (measured medians 15.7 KB + 53.6 KB per turn: ~28 MB for 400 turns); a non-ASCII token (a cased Cyrillic or accented name) skips the prefilter and `json.loads` every row (`impossible_knowledge.py:206-229`). Fires only when a private name is spoken and handed; cached per beat. The docstring's "a single indexed scan" understates it. Fix: a per-chat aired-token ledger written at commit.
5. **Interaction-loop content stores each declaration two or three times.** `rounds[*].result`, `character_results` (the same object for a one-round speaker, serialized again) and `combined_declarations[*].sequence` (`loops.py:1866-1902`); median 36.3 KB a beat (measured, last 150 turns). `_rehydrate_loop_results` already falls back from `character_results` to `rounds`. Medium storage gain; needs reader changes.
6. **Skip stage parses the stored scene ~4x per asked mind** (`_stored_scene` in `ask` twice, `_standing_place`, `_left_the_map_from`) plus once per far-end character call (`stretch_for_payload`, `skip_stage.py:1188`). Rare (skip beats only); low gain.
7. **Step sizes (measured, `engine.db` ro, last 400 turns):** 120.5 MB across all variants, ~300 KB a beat; medians `director_resolve` 53.6 KB (max 159), `commit` 35.9 (max 340), `interaction_loop` 29.2, `perception_outcome` 20.4, `director_interpret` 15.7, `perception_act` 12.6. Engine notes are small (median <= 2.5 KB); the weight is `orchestration`/`state_diff` (resolve), `results` (commit), `rounds` (loop), `observations`/`composer_ledger` (perception).

## Already registered

Confirmed present in the code and already in a register -- not findings.
- **`UNBUILT_PIPELINE.md` §1.195 (a)**: a rerun plans with `cast_rows` read before `_restore_and_refresh` (`runtime.py:1540` read; `_restore_and_refresh` refreshes only `ctx.cast`; `build_plan` at `:1926-1941` is handed `cast_rows`). Still live.
- **`UNBUILT_PIPELINE.md` §1.11a**: `build_plan`'s presence drop is silent (it also runs under `resume_key_for_turn`), so an autonomy-0 uncontested beat drops without a note (`runtime.py:1028-1063`).
- **`UNBUILT_PIPELINE.md` §1.11b (iii)**: the micro-round concealment floor (`common._conceal_from_targets_observer`, called at `loops.py:440-447`) and the composer disagree on an empty `conceal_from`.
- **`UNBUILT_PIPELINE.md` §1.11c**: residuals of the owed-exit draw (`loops._reaction_owed`, `_note_left_open`).
- **`UNBUILT_IDENTITY.md` §1.39**: micro-perception deliveries skip the composer's self-reference/identity floor (`loops.py` `_observable_predicate(display, surface)` with no self rewrite).
- **`UNBUILT_CHARACTERS.md` §1.29**: the isolated first wave is shelved (`loops._isolated_wave`, `parallel_isolated_reactors` False). Its docstring's "offscreen simulation is not built" is out of date now that bubbles and the skip stage run off screen (`loops.py:1063-1066`).
- **`UNBUILT_PLATFORM.md` §1.62**: the opening plan never appends `narrator_extra` (still true, `runtime.py:1214-1229`; the entry's step list still spells `mapping_stage`).
- **`UNBUILT_WORLD.md` §1.225**, "A built end under another id": `settle_departures`' docked rule matches `destination_room` by exact id (F8 is the compiler's sibling reader, not registered).
- **`UNBUILT_WORLD.md` §1.219**: no card tells the Room what `transit_destination_unplanned` / `transit_route_unplanned` ask for.
- **`UNBUILT_WORLD.md` §1.127 residual**: whether `planned_context` should fuzzy-match (but its premise "deliberately exact" is false -- F5).
- **`UNBUILT_WORLD.md` §2.43, "Building lots: what is left"**: a lot the beat walks into before the job is built room by room; a lot's footprint is advisory; only sleepers move; one lot a run.
- **`UNBUILT_LIVING_WORLD.md` §1.99d**: what a mind's skip work makes, destroys or consumes; dormant cast at every skip; the walk to a thing used where it stands (and see F15: its `not_known` bullet has landed).

## Structure notes

- **Monolith in miniature: `runtime._run_pipeline`** (`:1535-2051`, ~520 lines) holds three plan walkers -- the `only_key` reroll (`:1687-1786`), the opening (`:1801-1880`) and the normal hydrate/compute loop (`:1882-2051`) -- each re-implementing hydration, stale refusal and the restore, and they already drift: the reroll refuses before it restores, the other two after (F1); the opening marks steps stale and deletes orphans before its stale refusal, the normal path claims to refuse first. Natural seam: one `PlanWalk` (refuse -> restore -> hydrate -> compute) used by all three. `build_plan` (`:951-1177`) is the second miniature monolith.
- **Reactor derivation, three copies:** `build_plan` (`:993-1084`), `interaction_loop` (`loops.py:1115-1158`) and `reaction_loop` (`:1936-1947`) each widen and gate `flow.reactors` themselves, in different orders and with different subsets (the planner gates awareness/presence BEFORE hearers/engaged/enclosure and not after; the loop gates after every widening; the reaction loop widens by acted-upon only). F6 is the drift. Seam: `common.beat_reactors(ctx_or_args) -> [ids]`.
- **Two appliers of one settled skip work:** `skip_work.settle_work` (`:641-676`, one merge per change, floors per change) and `work_scene` (`:678-722`, one merge per ROW after `_merge_channel` folding, only `_refuse_unheld_transfers` re-run). `_refuse_unheld_transfers` replays `inventory_ops` alone, so a row whose first change puts a thing into a container and whose second transfers it out of that container passes in the first and is refused in the second -- the step's `worked.changes` then says it landed while the far end (`FarEnd` via `work_scene`) drops it. PLAUSIBLE, not reproduced; fold the two into one pass that returns both the record and the world.
- **A docstring promise nothing enforces:** `director_layout.lay_out_buildings` "Never raises" (`:640-647`), but everything after the solve (`planned_layout`, `_take_off_what_is_not_laid`, `write_planned_layout`, `apply_planned_layout`, `:712-745`) is unguarded, and its caller does not guard it (`director_rooms.py:2839-2852`, `expand_lots_near` beside it likewise); a raise there fails the whole rooms-in-view run and files no `failed` record, so the back-off never engages. No concrete trigger found (DB writes retry 30 s).
- **Check-then-write across a model call:** `director_lots.expand_lot` re-reads the lot (`:368`) and then plants (`:371`) outside one transaction; the job's expansion and a beat's `expand_entered_lots` can both pass the re-check and both plant (`taken` uids were computed before either planted, so the second overwrites the first's `lot__<rid>` rows). Narrow window; PLAUSIBLE.
- **Shape drift in a deterministic producer:** `offscreen_beat.offscreen_interpretation` writes `state_assertions`/`onset_state_assertions` as `[]` (`:106-107`) where the schema declares a `StateDiff` dict (`llm/schemas.py:1621-1625`); every reader found tolerates it only because `[]` is falsy or an `isinstance` guard catches it (`director.py:5564`, `director_rooms.py:2563`, `loops.py:931-935`).
- **Context reset by `.set(None)`:** `run_pipeline`'s `finally` (`:2172-2175`) clears `cancel_event` and `active_frame_id` without tokens. Harmless on the routes' drain thread; it clobbers an outer value for in-process callers (the off-screen job runs several pipelines in one thread; replay harnesses).
- **The turn-scoped contextvar check scans two modules** (`tools/project_check.py:2543`); five more ContextVars live elsewhere (`world/charter_runtime._REGISTRY_SESSION`, `persist/llm_capture._room_scope`, `story/room_citations._rows_read`, `extension_runtime/api._COMMIT_SCOPE`, `llm/llm_quality.answered_by`). None was found riding into a job today (the commit schedules its tail after `registry_session` exits, `persist/commit.py:556` vs `:700-890`), but nothing enforces it.
- **Module-level mutable state:** `runtime.ABORTS` (written under `_ABORTS_LOCK` by `begin_pipeline`, `run_pipeline`, `stop_off_screen_beats`, `offscreen_beat._give_back_the_slot`; read without the lock by `running_frames` -- a snapshot, fine under the GIL); `runtime.STEP_HANDLERS` (written by `register_step`, i.e. `extension_runtime` at enable time, and by tests).
- **Step-key spellings outside the four registries:** `"skip_lives"` is spelled literally in `loops.py:1152`, `runtime.py:507`, `persist/commit.py:581`, `persist/commit_scene_state.py:1752`, `persist/commit_skip.py:42` and as `mind/skip_memories.SKIP_LIVES_STEP` instead of `skip_stage.STEP_KEY`; runtime also keys behaviour on `_BEFORE_THE_FAR_END`, `PERCEPTION_STEP_KEYS` and `_PRESENTATIONAL_TAIL`.
- **Named caps in scope** (owner's rule: named, not chosen here): `SKIP_PAYLOAD_ROWS` 48, `SKIP_ASK_WORKERS` 8, `SKIP_QUESTION_REASONING` "off", `SKIP_PLACE_OPTION_CHARS` 120, `SKIP_WORK_WORKERS` 8, `SKIP_WORK_ROWS` 48, `LAYOUT_TIER_PER_RUN` 1, `LAYOUT_DESCRIPTION_CHARS` 16000, `LAYOUT_LORE_INDEX_MAX` 80, `LAYOUT_LORE_OPENING_CHARS` 600, `LOTS_PER_RUN` 1, `LOT_STOREYS_MAX` 4, `LOT_ROOMS_MAX` 14 (all three tabled as "the owner's to change" in `DESIGN_BUILDING_LOTS.md`), `STALLED_AFTER_BEATS` 3, `WORLD_CONTEXT_LORE_K` 14 / `_CAP` 12 / `_RECENT_EVENTS` 5, `RULEBOOK_ROWS_CAP` 8, `RULEBOOK_ROW_CHARS` 400, `DECISION_LOG_LIMIT` 2000. **Unnamed caps:** the skip's place/thing decision request shows the model only the first 40 stretches (`skip_stage.py:552` `stretches[:40]`) -- a week of routine is ~50 rows (the stage's own comment at `:95`); `reaction_loop`'s `max_reactors` default 6 lives inline (`loops.py:1935`); `run_offscreen_beat`'s and the layout tier's reason lists are cut at 12/6 (diagnostic only).

## Docs checked

| Claim | Where | Holds? |
|---|---|---|
| Normal turn: interpret -> compile -> perception_act -> [reaction_loop] -> [interaction_loop / character:<id>] -> resolve -> background -> outcome -> narrator -> [narrator_extra] -> commit | CLAUDE.md:89-93, PIPELINE.md:305-330 | Order holds (`plans.py`: 50+ plans, every one ends in `commit`, `narrator` always after `perception_outcome`, interpret first) -- but neither names `skip_lives` (F16) |
| "Contested beats plan no parallel character steps ... it already collected each reactor's declaration" | PIPELINE.md:337-340, runtime.py:1103-1110 | No (F6) |
| "Both pairings go through `_run_parallel_group` ... a typical story runs strictly sequentially" | PIPELINE.md:1410-1420 | No: three pairings; compile + perception_act on every unskipped beat (F16) |
| "Each recomputation creates a new immutable variant" | PIPELINE.md:1436 | Partly: the serial path reuses a byte-identical variant; parallel groups still mint (F19) |
| "A single-step reroll skips [`_assert_plan_materialized`]" | PIPELINE.md:1440-1443 | Yes (`runtime.py:1747-1786`) |
| A rerun restores the pre-turn checkpoint and sweeps every later one | `runtime._restore_and_refresh` docstring (chat 87); UNBUILT_CHARACTERS.md:428 | Intended and documented in code; absent from PIPELINE.md's "Resume and rerun" and DATABASE.md's `checkpoints` entry. Via HTTP only the latest turn can be rerun (`web/app.py:1136`), so the sweep reaches only orphan checkpoints there; direct callers (replays) lose later checkpoints -- the memory note's "reroll latest turn first" |
| "Nothing checks that the four agree"; 17 labels / five untested; SCHEMA_MAP keyed by step id | agents/README.md:65-80, :37 | No (F17) |
| Role-module edges `loops -> character`, composer a shared leaf | agents/README.md:51-63 | Holds for loops (imports `character`, `composer`, lazily `perception`, `director`, `skip_stage`) |
| Anchor `before:director_interpret` is a valid core anchor | EXTENSIONS.md:356-358, 1145-1149 | Accepted at registration; breaks the run (F11) |
| "An anchor naming a step this turn does not run ... simply not planned" | EXTENSIONS.md:367-370 | Yes (`extension_runtime.apply_plan_splices`) |
| `agents/__init__.py` is a compatibility facade re-exporting public names and step handlers | CLAUDE.md, `__init__.py` docstring | Yes (`skip_lives` included) |
| Sinks "armed on every step (`runtime._run_step`)" | pipeline_context.py:89,132,179 | No such function (F17) |
| "A `failed`, `not_known`, off-map or asleep row changes nothing"; `not_known` own part not built | Design.md:348, DESIGN_THE_CAST_ACROSS_A_SKIP.md:419,546, UNBUILT_LIVING_WORLD.md:1524, skip_work.py:18-21, skip_stage.py:57,897 | No since 1342bbde (F15) |
| "THE MEMORIES AGREE BY CONSTRUCTION" | skip_work.py:73-77 | For `done` rows only (F15) |
| Skip question: "never the player", "not bubble cast", asleep minds asked, sedated/unconscious not | DESIGN_THE_CAST_ACROSS_A_SKIP.md §4.2; skip_stage.py:248-268 | Yes |
| The skip question builds from a private snapshot so nothing pre-skip reaches the far-end minds | character.py:3602-3607 | Yes (`shared = {} if skip is not None`) |
| "PX5's THIRD floor ... no third-body admission at all" in loops | UNBUILT_PERCEPTION.md §1.129 | No: landed 4665a673, `loops.py:563-575` (F17) |
| "the deterministic matcher is deliberately exact" | UNBUILT_WORLD.md §1.127 | No (F5) |
| Opening plan "a fixed five-step list (`mapping_stage`, ...)" | UNBUILT_PLATFORM.md §1.62 | Stale spelling (`compile_world_context`, and it splices now); the `narrator_extra` gap holds |
| `LOT_STOREYS_MAX`: "storeys a lot may ask for" | DESIGN_BUILDING_LOTS.md:138, world/lots.py:39-42 | Holds as worded; the answer is never held to it (F14) |
| Layout tier "FAILS OPEN, ALWAYS" / `lay_out_buildings` "Never raises" | director_layout.py:53-58, :640-647 | Not enforced after the solve (structure note) |
| `_save_or_reuse_variant`: deterministic stages no longer mint duplicates on resume | runtime.py:806-829 | Only on the serial path (F19) |
| "Refuse before deleting orphans or marking anything stale" | runtime.py:1957-1961 | The restore and commit-stale mark already ran (F1) |
| `reaction_loop` runs on `contested` or `possible_reactors`; "each eligible reactor" declares | loops.py:1906-1912 | Planned on `contested` only; breaks after the first reaction needing resolution (F6) |
| `aired_in_story`: "a beat with one costs a single indexed scan" | impossible_knowledge.py:192-194 | The leading-wildcard LIKE reads every row's content (Efficiency 4) |
| Frontend: a non-commit step reroll "leaves world/memory state alone" | static/js/chat.js:2474-2477 | No (F18) |
| AGENTS.md routing row "Flow planning, resume, or streaming -> runtime.py (`build_plan`, `_run_pipeline`)" | AGENTS.md:429 | Yes |
