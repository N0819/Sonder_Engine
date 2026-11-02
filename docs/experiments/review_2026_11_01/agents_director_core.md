# Audit — `agents/director.py`, `director_scopes.py`, `director_reconcile.py`, `director_lingua.py`

Auditor: director-core lane, 2026-11-01. Working tree at `84f3de23` (clean; `agents/director.py` 7,999 lines, unchanged during the audit).
Method: full read of the four files; every finding traced to its readers/writers by grep across the repo (tests, tools, extension_runtime included); five read-only `.venv/bin/python -I` snippets (outputs quoted below; one ran with `ENGINE_DB` pointed at a scratch file); read-only (`mode=ro`) samples of the owner's `engine.db` (last 400 `director_interpret` / `commit` variants, the `world` table). No test file was run (snippets sufficed). Nothing in the repo was written.

## Scope read

Read IN FULL:
- `agents/director.py` 1–7999 (every line: imports 1–378, `director_establish` and opening helpers 380–1211, interpret helpers 1214–1698, `director_interpret` 1701–2808, `_mover_as_self`/`_reconcile_interpretation`/`_deep_audit_omissions` 2811–3067, resolve-seam block comment and `_block_restrained_moves`/`_reconcile_resolution` 3070–3682, `_span_coherency_report`/`_refuse_cast_doubles`/`_run_specialists`/`_require_complete_entity_interiors` 3685–4261, speech-act and public-evidence helpers 4264–4419, movement/event-input/target helpers 4422–5374, `director_resolve` 5377–7965, campaign helpers 7968–7999).
- `agents/director_scopes.py` 1–608, `agents/director_reconcile.py` 1–559, `agents/director_lingua.py` 1–29.

Read in part, only as far as needed to trace a finding (NOT audited):
- `agents/director_prose.py`: module docstring 1–120, `already_happened`/`_waiting_spans` 224–300, `author` 376–389, `run` head 4670–4700 and tail 4905–5052, row conversion 4570–4625, `dispatch`/`answer_for`/`attach_record` 5055–5143, `standing_is_authorship` 3020–3069, `skip_is_authorship` head, `pressures_ended`.
- `agents/director_fanout.py`: `_resolve_beat_view` 49–190, `_interpret_beat_view` 203–270, `_specialist_span_slice` 287–330, `_specialist_payload` 598–700 and the spatial slice 860–915, `_stage_container`/`_stage_state` 923–960, `_granted_event_ids` doc.
- `agents/director_evidence.py`: `normalize_causal_ledger` 2802–3089, `authority_by_entity`, `_span_items`, `span_result_findings`, `speech_transforms` head, `causal_world_index` figures block, `beat_event_ledger` doc.
- `agents/common.py`: `rooms_in_view`/`_aperture_centers`/`figures_in_view` 12628–12790, `lay_charter_figures`, `present_charter_figures` head, `preview_player_state_assertions`/`merge_player_state_assertions` head, `validated_player_state_assertions` head, `observer_label_fn` head, `_check_prose_quote_authority` head.
- `agents/director_contact.py` `_validated_player_contact_assertions` head; `agents/director_floors.py` concealment floors' docs, `_refuse_minted_cast_doubles`, the binder's dialogue rename; `agents/director_movement.py` `movement_for_resolve`, `_sightlines_view`; `agents/director_views.py` `_lazy_view`, `_extension_director_payload`; `agents/background.py` `_provisional_beat` and the voice declaration shape; `agents/mapping.py` `_query` and the planning-need block; `agents/runtime.py` 970–990; `story/scene.py` `_ability_mod`, `player_authority`; `persist/commit.py` 920–935; `world/routines.py` docstring; `world/living_world.living_world_config`; `mind/memory_lore_entries.search_lore`; `core/pipeline_context.py` `add_warning`/`tell_director`/`engine_feedback`; `core/db.wget`; `extension_runtime.validate_director_result`.

## Findings

### F1 — The silent-beat guard clears the sequence and leaves the same invention standing in four other representations, which the resolve, the clock, the speech channel and the charter voices all read

- **Where:** `agents/director.py:2221-2246` (the guard), with readers `agents/director_prose.py:261-262`, `agents/director.py:2497`, `6572-6578`, `6613`, `agents/background.py:2701`, and (multi-player) `agents/director.py:2148` → `director_fanout.py:253-257` → `director.py:2386`.
- **Code:**
  ```python
  # director.py:2221
  if not str(ctx.input or "").strip():
      ...
      out["sequence"] = []
      out["speech"] = None
      ...
      out["state_assertions"] = {}
      _silent_rooms = _installed
  # director_prose.py:261 (already_happened, read by the resolve's run())
  if prose and not waiting and not record.get("conduct_refused"):
      return str(prose)
  # director.py:6613
  _interpret_speech = speech_transforms(interp.get("causal_ledger") or [])
  ```
- **Failure:** on an empty input the interpret author is still called (`director_prose.run` raises if it returns no prose, so there is always prose), the encoder still writes rows, and `normalize_causal_ledger` puts them in `ledgers`, `causal_ledger` and `sequence` (`director_evidence.py:3086-3088`). The guard (whose own comment says "on an empty input that prose is the Director restating stale conduct") empties `sequence`/`speech`/`action(s)`/`contact_assertions`/`state_assertions` only. Left standing: `ledgers`, `causal_ledger`, `_all_causal_sequence` and `orchestration.prose_contract.prose` (attached at 2389). Then:
  1. `director_prose.already_happened` hands the stale prose to the resolve AUTHOR and ENCODER as "what the player's side already put into the world this beat" (`run`, 4674-4677; the encoder gets it too, `tests/test_prose_contract.py:629-632`);
  2. `speech_transforms(interp["causal_ledger"])` (6613) compiles the invented player line into the committed `state_diff.speech` — the record later beats read;
  3. `beat_time_from_spans` (6572-6578) charges the invented rows' `seconds` to the clock;
  4. `background._provisional_beat` (background.py:2701) builds the pre-resolve charter voices' beat from `interp["ledgers"]` speech rows, attributed to the player — the voices hear her say it (chat 59 t154's "Kaa Sama, your cooking is too good", again);
  5. `_addressed_characters(out.get("ledgers"))` (2497) asks the invented line's addressee to react;
  6. with an extra player declaring, `_all_causal_sequence` (2148) still holds the primary's invented rows, `_interpret_beat_view` takes its spans from it, and `_run_specialists` (2386, AFTER the guard) folds their transforms back into the `state_assertions` the guard just emptied.
- **Verified:** snippet (fake ctx shaped exactly as the guard leaves `director_interpret`):
  ```
  $ .venv/bin/python -I -c "... director_prose.already_happened(Ctx()) ..."
  'Mara steps inside the shrine and says: "Kaa Sama, your cooking is too good."'
  ```
  Readers 2–6 traced in code. `tests/test_silent_beat_declares_nothing.py` checks only source strings of the interpret; nothing tests the resolve side. CONFIRMED (code path); live frequency PLAUSIBLE (the corpus measured 2 of 10 empty-input turns inventing speech on the old contract).
- **Severity:** CORRUPTION (an invented player line committed to `state_diff.speech`) + WRONG-SCENE.
- **Fix (class: a guard that removes a declaration removes every representation of it):** in the guard, filter `ledgers`/`causal_ledger`/`_all_causal_sequence` to the places row (`director_prose.is_places_row`) exactly as `sequence` is, and blank the prose record (or mark it `silent`) so `already_happened` returns `""`. Test: drive `director_interpret` with empty input, a fake author returning conduct prose and a fake encoder speech row; assert `already_happened(ctx) == ""`, `interp["causal_ledger"]` holds no conduct row, and a resolve over it has no player line in `state_diff.speech`.
- Related, not the same: UNBUILT_PIPELINE §1.216 residual ("a silent beat stays whole with the empty-input guard").

### F2 — The cast-double floor never runs on the interpret's mints: it reads `state_diff`, which interpret does not have, and the resolve's run precedes the merge of the interpret's assertions

- **Where:** `agents/director.py:3720-3722` (reader), calls at `2388` (interpret) and `6499` (resolve); merge of the interpret's state at `6670-6687`.
- **Code:**
  ```python
  sd = out.get("state_diff") if isinstance(out.get("state_diff"), dict) else None
  if not sd or not sd.get("entities"):
      return []
  ```
- **Failure:** interpret's encoder entities land in `out["state_assertions"]["entities"]` (`director_fanout._stage_container`, 923-938); `DirectorInterpret` has no `state_diff` field (`llm/schemas.py`, class `DirectorInterpret`). So at 2388 the floor returns `[]` without looking. At resolve the floor runs at 6499 on the resolve's own diff, and the interpret's `onset_state_assertions` are merged into `sd` afterwards (`sd.update(merge_player_state_assertions(...))`, 6676). A person the player's interpretation mints under a cast member's identity — the concept-lab class the floor's docstring was written for (`director_floors.py:2471-2491`: a stranger filed as `ines_calder` while the doctor was in a bubble, answering a line in her place 38 turns later) — reaches the commit unrefused. The binder (`_bind_minted_entities_to_present_figures`, 7171) does see merged mints, so only the cast-double rule has this hole.
- **Verified:** snippet: `director._refuse_cast_doubles(C(), {'state_assertions': {'entities': {'ines_calder': {...person...}}}}, {})` → `[]` (no query reached). Ordering traced. `tests/test_cast_double_refused.py` tests only the pure `_refuse_minted_cast_doubles`. CONFIRMED (the no-op and the order); live frequency PLAUSIBLE.
- **Severity:** CORRUPTION.
- **Fix:** read the stage's container (`_stage_state(out, stage)`) and run the resolve's pass after 6676 on the merged `sd`. Test: interpret with a fake encoder minting a person entity keyed by a cast member's id → refused and warned; resolve with that onset assertion → absent from the final `state_diff.entities`.

### F3 — A charter creature's noise is dropped on every prose beat: it is folded into a `state_diff` that does not exist yet

- **Where:** `agents/director.py:6459-6468`.
- **Code:**
  ```python
  _figure_noise = [row for _fd in _figure_declarations
                   for row in (_fd.get("sensory_events") or []) if isinstance(row, dict)]
  if _figure_noise:
      _sd = out.get("state_diff")
      if isinstance(_sd, dict):
          _sd["sensory_events"] = list(_sd.get("sensory_events") or []) + _figure_noise
  ```
- **Failure:** at 6465, `out` is `director_prose.run`'s `{"ledgers": rows}` (`director_prose.py:5052`) after `normalize_causal_ledger` (which sets only `ledgers`/`causal_ledger`/`sequence`); nothing between 6256 and 6465 creates `state_diff` (it first exists after the validation at 6475 and the fold at 6497). So the `background._creature_noise` row ("a wet dragging", faint, from the Well Thing) never reaches `state_diff.sensory_events`. No other reader takes `charter_declarations[*].sensory_events` (perception reads their `sequence`/`name`/`room` at perception.py:1062, 4208, 4273; `commit_background.beat_reactions` reads dialogue/action). The comment above the block says perception and commit read it from the diff — they never get it.
- **Verified:** traced; the only test (`tests/test_a_charter_body_speaks_before_the_director_resolves.py:159-168`) checks the producer, not the fold. CONFIRMED.
- **Severity:** WRONG-SCENE (a hunting creature dragging itself closer is silent to every observer).
- **Fix:** fold after `_run_specialists` (into `sd` after 6504) or `out.setdefault("state_diff", {})` first. Test: resolve with a fake voice returning a creature act with an activity → the row is in the final `state_diff.sensory_events`.

### F4 — `ctx.tell_director` / `engine_notices` reach no model: their only two readers are the staging payloads, which no model call receives

- **Where:** readers `agents/director.py:1937` (interpret staging `payload`) and `6057` (resolve staging `payload`); writers: 51 production `tell_director(` call sites (director.py 15, persist/commit_attire.py 22, commit_scene_state.py 6, commit_background.py 3, director_views.py 2, commit_mechanics/commit_mapping/commit_common 1 each) plus `commit_common.add_engine_notice` and the mechanics sweep.
- **Code:** `"engine_notices": wget(chat["id"], "engine_notices", []),` (both sites).
- **Failure:** since the prose contract, the author is handed `_interpret_model_payload` (2010-2039) / `_model_payload` (6175-6205, plus `already_happened`/`pronouns`), and the encoder the owner slices built from `_first_extras`/`_orch_extras` (`director_fanout._specialist_payload`). Neither carries `engine_notices`. The interpret staging `payload` is read for exactly one key (`payload.get("author_notes")`, 2095); the resolve staging `payload` for the keys listed under F18 — not `engine_notices`. `grep -rn engine_notices` finds no other reader in the repo (UI included). So every "for next beat" correction the engine writes — "attire: nothing knows what Hinami's 'fitted tank top' covers … say so once: attire.Hinami.coverage = …", "contact moved: …", "span 2: settled_and_silent (spatial)", a failing lamp gone out, a mint stood with no room, "The player said and did nothing that beat…" — is stored and read by nobody.
- **Verified:** grep of every reader; DB: `world.engine_notices` is non-empty for 71 of 132 chats (chat 174, 178, 177… sample above). Documents that claim delivery: `core/pipeline_context.py:436-445` ("This one is for the model"), `Design.md:452` and `:455` ("The Director can see what the engine did" — the row is duplicated), `Design.md:877`, `director.py:2592-2596`. CONFIRMED.
- **Severity:** SILENT-NOOP (a whole correction channel, project-wide).
- **Fix:** hand `engine_notices` to the author's lean payload (and/or the encoder core) when non-empty — a payload widening on every beat that has notices, so the owner's call (same shape as UNBUILT_PIPELINE §1.1 item 4's proposal: "a sheet section per field, added only when present"); or retire `tell_director` and say so in the docs. Test: `wset(cid, "engine_notices", ["X"])`, run `director_interpret`/`director_resolve` with `_agent_json` captured; assert the prose author's payload carries `X`.
- Related registered: UNBUILT_PLATFORM PERSISTENCE-F17 (the key is not frame-scoped) and UNBUILT_PIPELINE §1.1(4) (fields the lean payload lacks — `engine_notices` is not among those named).

### F5 — Living-world approach A's destination residue is computed on every movement beat and delivered to no model; the commit reports it as `delivered`

- **Where:** `agents/director.py:5671-5726` (compute), `6062-6063` (only consumer: the staging payload), `persist/commit.py:923-932` (report).
- **Code:** `_destination_residue = residue_for(...)` … `ctx["_destination_residue_report"] = {"to_room": ..., "delivered": len(... facts)}` … `**({"destination_residue": _destination_residue} if _destination_residue else {})` (staging payload).
- **Failure:** `destination_residue` appears in no lean payload, no owner slice and no language-pack card (`grep residue` over `director_prose.py`, `director_fanout.py`, `director_scopes.py`, `llm/prompts.py`: nothing). The comment says "Delivered to THIS payload only"; `world/routines.py:19-23` names the staging payload as "the one consumer". `tools/fire_rates.py` will count `routine_residue.delivered` facts that were delivered to nobody.
- **Verified:** trace + DB: 16 of the last 400 commits carry `routine_residue`; 0 have `delivered > 0`, so no fact has been lost in that window — the mechanism is disconnected rather than visibly failing. CONFIRMED.
- **Severity:** SILENT-NOOP (and a misleading measurement).
- **Fix:** put `destination_residue` on the resolve author's payload when present, or delete the computation and the report. Test: patch `residue_for` to return one fact; assert it reaches the captured author payload.

### F6 — Dice and ability modifiers cannot run on the prose path: no card asks for `ability`/`difficulty`, and `_ability_mod` would read 0 anyway because the actor is an identity handle

- **Where:** `agents/director.py:2162-2176` (builds `flow.dice`), `5399-5411` (rolls), `story/scene.py:2144-2171` (`_ability_mod`).
- **Code:**
  ```python
  _flow.setdefault("dice", [{"actor": entry.get("source_entity_id"), ...}
      for entry in out.get("causal_ledger") or []
      if isinstance(entry, dict) and entry.get("ability") and entry.get("difficulty")])
  ```
- **Failure:** (a) no file under `language_packs/` (en or ja) contains the word `difficulty`, so the encoder is never asked for it; the row fields exist only on the schema (`llm/schemas.py:3298-3299`). (b) `source_entity_id` is normalized to an identity handle (`persona:7`, `character:58`) by `normalize_causal_ledger`, and `_ability_mod` matches `persona_name(...)`/sheet names and the literals "player"/"you"/"pc". Every downstream use is therefore dead: the dice groups in `_causal_event_inputs` (4558-4566), the `provably_physical` tripwire, the resolved-event dice suffix (7352-7354).
- **Verified:** DB: 0 of 149 recent prose-contract interprets carry `flow.dice` or a row with `ability`/`difficulty`. Snippet (`story.scene.persona_of` stubbed in-process, `ENGINE_DB` on a scratch file): `_ability_mod('Hinami','lockpicking')` → `6`; `_ability_mod('persona:7','lockpicking')` → `0`. CONFIRMED.
- **Severity:** SILENT-NOOP (an authored mechanic — sheet abilities — has no effect on outcomes).
- **Fix:** an owner decision: either teach the encoder the two fields (both packs) and map the actor through the identity index before `_ability_mod`, or retire the dice path. Test: an interpret row `{ability, difficulty, source_entity_id: "persona:N"}` → the resolve's dice modifier equals the persona's level.

### F7 — The resolve's span accounting reads interpret-numbered records as resolve spans, and the engine-compiled `speech` channel is "unowned" by construction

- **Where:** merge at `agents/director.py:6670-6687`; `_span_coherency_report` at `7896` (→ `director_evidence.span_result_findings`); speech compiled at `6613-6639`; same ids used by `single_span_attributions`/`span_mint_rooms` at `7275-7287`.
- **Failure:** both stages number their chronology from 1. Speech offsets the interpret's ids (`chrono_offset`), the state merge does not: the interpret's records keep `from_event` = interpret chrono ids inside the resolve's merged `sd`, and the coherency report attributes them to the resolve span with the same number. And `speech` is in no owner's channels (deliberately — "the one channel no specialist owns"), so every speech record is reported `unowned_channel`.
- **Verified (owner's DB, chat 177, read-only):** turn 22 — resolve spans 1–3 have categories `['speech'], ['attention'], ['speech']`; findings: `written_by_non_owner (objects) inventory_ops[0]`, `(spatial) poses.Mellisande`, `(objects) inventory_ops[1]` — exactly the interpret's rows 1–3 (`['inventory'], ['poses'], ['inventory']`). Turn 21 — `unowned_channel` for `speech[0]`, `speech[1]`. These are `orchestration.span_findings` and `tell_director` notes ("span 1: written_by_non_owner (objects)" is in `world.engine_notices` for chat 177). CONFIRMED for the report.
- **Severity:** SILENT-NOOP (a diagnostic that is wrong on most beats). PLAUSIBLE WRONG-SCENE on the second consumer: an interpret mint citing interpret chrono k is placed by `span_mint_rooms` at the room of resolve span k's actor.
- **Fix:** give merged interpret records a stage-qualified or offset id at merge (the speech path's `chrono_offset` rule), and exclude the engine-owned `speech` channel from `unowned_channel`. Test: a merged diff with an interpret record citing 1 and a resolve span 1 of another owner yields no finding.

### F8 — The resolve encoder's sightlines are computed on the stored scene while every placement it reads is the onset preview

- **Where:** `agents/director.py:5933` (`"sightlines": _sightlines_view(sc, ctx, p_name)`), passed at `6239` into `_orch_extras`, consumed by the spatial slice (`director_fanout.py:899-903`); the encoder's world is `resolve_sc` (`6256-6257`), built from the player's onset assertions at `5556-5569`.
- **Failure:** the spatial slice's own comment says the digest is "computed from the ledgers this hand writes (stations, poses, facing) so it can see what its own entries come to". After an asserted onset move ("I duck behind the bar", a station/pose/position change applied to `resolve_sc`), the encoder's positions say behind the bar and its sightlines say in the open. Two representations of one placement in one payload.
- **Verified:** traced. PLAUSIBLE (effect on a live beat not replayed).
- **Severity:** WRONG-SCENE.
- **Fix:** `_sightlines_view(resolve_sc, ctx, p_name)`. Test: onset assertion moving the player's station behind cover → the captured encoder payload's sightlines reflect it.

### F9 — The resolve derives its aperture twice from two spellings of the destination, so the bodies voiced before resolve are not the bodies the payload and floors are shown

- **Where:** `agents/director.py:5579-5586` (aperture A: raw `interp["movement"]["to_room"]`, `resolve_sc`) vs `5763-5765` (aperture B: `_mv_target` from `movement_for_resolve`, 5663, `sc`).
- **Code:**
  ```python
  _mv_resolve = interp.get("movement")
  _aperture = rooms_in_view(ctx, resolve_sc, ctx.get("_player_room") or room_of(resolve_sc, p_name),
                            _mv_resolve.get("to_room") if isinstance(_mv_resolve, dict) else None)
  ...
  _fig_rooms = rooms_in_view(ctx, sc, ctx.get("_player_room"), _mv_target)
  ```
- **Failure:** `movement_for_resolve`'s docstring (`director_movement.py:273-282`) says every resolve reader of the destination, "the figures in view" included, takes the compiler's resolved id. Aperture A does not: when the compiler resolved a spelling the interpret could not (`classify_movement` against the plan), A adds the raw string (no room), so the destination's charter bodies are not laid into `resolve_sc` and not voiced by `declare_charter_figures`, while B puts them into `present_figures`, the causal index (6174) and the identity floor (7171). The memo (`common.py:12676-12712`, one entry keyed `(player_room, destination)`) then thrashes and the aperture is derived twice.
- **Verified:** traced. PLAUSIBLE (requires a beat where the compiler re-spelled the destination).
- **Severity:** WRONG-SCENE (+PERF).
- **Fix:** compute `_mv_for_context` before the charter block and use it for A. Test: a planned destination named by a variant spelling with a charter body there → the body is laid and voiced.

### F10 — The resolve reports the player's authority as `world_author` unless that beat had a downgrade

- **Where:** `agents/director.py:4527` and `4539` vs `2598-2600`; interpret reads the dial at `1964`, `1976`, `2424`, `2574`.
- **Code:** `add_group(primary_id, interp.get("authority_mode") or "world_author", unresolved)`; `out["authority_mode"] = _authority_mode` is set only inside `if _downgrades:`; extra players' entries never carry it.
- **Failure:** on a chat at `actor_only`/`explicit_outcomes`, every beat without a downgrade sends the resolve author and encoder `event_inputs` labelling the player's contestable events `world_author` — "the input it judges `commitment` WITH" (`director_evidence.authority_by_entity` docstring); extra players are always `world_author`. One fact, read two ways, free to disagree. (Answer to question 6: the DEFAULT is honoured wherever it is consulted; the non-default dial is not carried to resolve.)
- **Verified:** snippet: `_causal_event_inputs(...)` with an interp lacking `authority_mode` → `[('persona:7', 'world_author'), ('persona:9', 'world_author')]`. CONFIRMED (the label); effect PLAUSIBLE.
- **Severity:** WRONG-SCENE.
- **Fix:** read `player_authority(chat["id"])["mode"]` in `_causal_event_inputs` (or always stamp `interp["authority_mode"]`). Test: chat at `actor_only`, no downgrade → resolve `event_inputs[0].authority_mode == "actor_only"`.

### F11 — The reachability, movement and restraint floors run only at resolve, but the interpret's positions are previewed unchecked to the cast and to the resolve author

- **Where:** floors at `agents/director.py:6755-6993` (movement backstop), `7144-7155` (`_unreachable_position_writes`), `7816-7817` (`_block_restrained_moves`); onset preview via `onset_state_assertions` (2432-2453) → `common.preview_player_state_assertions` (→ `merge_scene_with_diff`, no route check) at `5568` and in `perception_act`.
- **Failure:** a player's interpretation that writes her position through a wall (or out of a binding) is the world the cast's onset views and `resolve_sc` show; the resolve then pops the committed position. The rule (a body does not pass a wall; a bound body does not walk) is stage-independent, the floor is not. (Answer to question 3, with F2.)
- **Verified:** traced. PLAUSIBLE (no live beat replayed).
- **Severity:** WRONG-SCENE.
- **Fix:** run the same two floors over `onset_state_assertions` at interpret, before the onset copy is taken. Test: interpret asserting the player's position across a `wall` edge → absent from `onset_state_assertions` with a warning.

### F12 — English cue lists append English instructions to `flow.mapping_request`, which feeds the lore query and planning-need surfaces

- **Where:** `agents/director.py:2710-2742` (`movement_cues`, `mutation_cues`), `2700-2708`; readers `agents/mapping.py:78` (`_query` → `search_lore`: 0.65 embedding + 0.35 FTS over the joined text, `mind/memory_lore_entries.py:442-519`) and `agents/mapping.py:556, 562` (planning-need `surface.request`).
- **Failure:** "picks up", "hands ", "places ", "breaks", "through the door"… in the input or attempts append "Inspect the declaration for new, moved, transferred, transformed, opened, destroyed, or contained scene entities and propose the minimum scene graph patch." (or the contained-space / "generate room description" variants) to the text the beat's lore is retrieved with. A lorebook key such as "space", "room" or "scene" then matches every such beat; the query embedding drifts toward boilerplate. English-only by construction (a ja story never triggers), the exact "word list in a free-prose guard" the project forbids. `needs_mapping`, which the lists also set, is read by nobody (`runtime.py:979`).
- **Verified:** DB: 13 of the last 149 prose-contract interprets carry the boilerplate (11 mutation, 1 movement, 1 new-room). Effect on retrieval PLAUSIBLE (not replayed).
- **Severity:** WRONG-SCENE (+ language-pack hazard).
- **Fix:** delete both cue blocks and the `needs_mapping` writes; the compiler already files typed needs from `movement`/`location_query`/`generation_requests`. Test: interpret on "I pick up the cup" → `flow.mapping_request == ""`.
- Registered in part: UNBUILT_WORLD §1.131 names the cue list as the source of `needs_mapping`; the `mapping_request` pollution is not registered.

### F13 — `_route_doorway_rows` says it routed a door to `rooms`, and on the prose path that changes nothing

- **Where:** `agents/director.py:1321-1369`; warnings at `2129-2131` and `6276-6278` ("the engine routed rooms").
- **Failure:** under the hands, adding `rooms` to a row's categories dispatched the spatial hand, which wrote the edge (docstring: "the spatial hand decides which edge the row moves once it is handed the row"). Now a row's categories are the channels the encoder already wrote (`director_prose.py:4596-4605`) and an owner runs only for channels granted or written (`dispatch`, 5071-5094): the added category re-asks nobody and the door stays shut on the record while the page opened it. Possible side effect (PLAUSIBLE): the routed row now passes `_require_complete_entity_interiors`' `rooms/spatial` gate (4197-4241) and can raise a false "required visible entity interior" warning when the door is also an entity.
- **Verified:** snippet: `_route_doorway_rows(...)` → `['yard door']`, categories `['contact_ops', 'rooms']`; `director_prose.dispatch(...)` for that answer → `spatial runs: False | contact runs: True`. CONFIRMED.
- **Severity:** SILENT-NOOP (with a warning that reports the opposite).
- **Fix:** retire it on the prose path; if the class still occurs, it is a clause in the encoder's `rooms` chunk ("a door between rooms is the edge's barrier") — check that it is there before adding one.

### F14 — Two resolve readers consult `dialogue_log` before it exists

- **Where:** `agents/director.py:6417` (prose-quote exemption) and `7175` (binder's speaker rename); the log is first built at `7386-7759`.
- **Failure:** `for _d in (out.get("dialogue_log") or [])` iterates nothing on a prose beat, so the exemption the comment describes ("any line the resolve attributes to a speaker who is neither cast nor the player") never applies and `_check_prose_quote_authority` files every quoted line the Director gives a creature, a PA or a presence in `player_act_warnings`. At 7175 `_bind_minted_entities_to_present_figures(..., dialogue_log=None)`, so its rename of a bound mint's lines (`director_floors.py`, binder 266-272) is inert.
- **Verified:** traced. CONFIRMED (readers inert); the volume of false warnings unmeasured.
- **Severity:** SILENT-NOOP (a guard firing on valid output; its FP rate should be measured before anything else is decided about it).
- **Fix:** read the speakers from `sd["speech"]`/the rows, or run both after 7759. Test: resolve prose quoting a creature's line → no prose-quote warning.

### F15 — Floors that degrade on an exception and tell nobody (question 5)

The same functions warn in their neighbours (1727, 1747, 1791, 2049, 5588, 5621, 5677, 5706, 5721, 5799), so these are omissions, not policy:

| Site | Swallow | What silently stops |
|---|---|---|
| `director.py:7124-7131` | `except Exception: _route_sc = sc` | the physical floor's route check of every charter body ("THE TOWN'S PEOPLE, AT THEIR CELLS") |
| `director.py:5291-5297` | `except Exception: return []` in `_bodies_addressed_as` | every address resolution (lines aimed at nobody, the Skerry Light class) |
| `director.py:7994-7999` | `except Exception: return [], False` | every campaign validator, `on_error="fail"` ones included, if `extension_runtime` cannot import |
| `director.py:702-713` | `except Exception: return None` in `_opening_planned_rooms` | the plan's room brief at the opening (the opening then mints rooms beside the plan) |
| `director.py:603-609`, `618-630`, `648-652` | `return None` / `pass` | opening placements and the plan's room set (`_enforce_opening_placements` then does nothing) |
| `director.py:765-781` | `notes = []` / `pass` | author notes and the charter's moves (documented fail-open) |
| `director.py:7189-7194` | `_roster = [p_name]` | `_stand_up_plans_placed_by_name`'s roster |
| `director_reconcile.py:250-319` | `return []` | scale/enclosure contradictions (documented) |

- **Verified:** read. CONFIRMED (the swallows); impact per site PLAUSIBLE.
- **Severity:** SILENT-NOOP (class).
- **Fix:** `ctx.add_warning` in each, naming the floor that degraded (`_scale_relation_conflicts` and `_GateFacts` fail open by design; a warning costs nothing there either). Test: monkeypatch `common.charter_view_for_rooms` to raise → a warning names the physical floor.

### F16 — Public evidence is cut to 20 sources and then 12, silently

- **Where:** `agents/director_fanout.py:189` (`public_sources[:20]`), `agents/director.py:4418` (`out["public_evidence"] = grounded[:12]`).
- **Failure:** sources are ordered player speech, each declarer's speech, then actions, so on a crowded beat the actions are cut first, and `_ground_public_evidence`'s docstring (4316-4318) promises "every legitimate source receives a deterministic fallback record". The charter ledgers that file commitments from this evidence never see what is cut, and nothing says so.
- **Verified:** read. CONFIRMED (the cap); live beats over 12 sources unmeasured.
- **Severity:** SILENT-NOOP. A cap is the owner's to set: name both numbers as constants, warn when they cut, and ask the owner for the value.

### F17 — The interpret builds a staging payload every beat and reads one key of it

- **Where:** `agents/director.py:1808-1952`; the only read is `payload.get("author_notes")` at `2095`.
- **What is built and discarded:** `director_context(chat, 5)` (a DB query), `with_charter_presences` (deep-copies the presence ledger and derives the charter's records for the room), `addressable_presences` (two `room_of` per presence), `_planned_rooms_view` + `_planned_elsewhere_view` (plan reads), `_sightlines_view` and `_egocentric_exits` (built again in `_interpret_extras`), `_interpret_scene_entities` (a `room_of` per entity), `appearance_of`, `paradox_visible_to` (built again at 2033), and `wget`s of `shadow_profile`, `background_presences`, `standing_intentions`, `pending`, `engine_notices`.
- **Verified:** grep of every `payload` read in 1840-2808. CONFIRMED.
- **Severity:** DEAD (+PERF, see Efficiency E1). Fix: compute `_author_notes_view` into a local and delete the dict (move any field still wanted into `_interpret_model_payload` deliberately).

### F18 — The resolve's staging payload builds about twenty keys no reader takes

- **Where:** `agents/director.py:5802-6112`. Read later: `notices`, `couriers`, `carried_reports`, `unratified_claims`, `world_pressure`, `travel_in_flight`, `active_awareness`, `active_restraints`, `active_conditions`, `scene.body_parts`, `planning_needs`, `sightlines`, `planned_rooms`, `planned_elsewhere`, `author_notes`, `social_standing`, `crowds` (6122-6290). Never read: `style_guide` (two DB reads), the rest of `scene` (incl. `_contextual_rooms`, `scene_compact_attire(sc)` — taken from `sc`, against the block's own "THE WORLD AS THE REACTORS SAW IT" comment), `simulation_clock`, `paradox` (re-read at 6191), `fiction_model`, `fiction_frame`, `player_declaration`, `other_players_declarations`, `character_declarations`, `character_contact_endings`/`material_effects` (passed separately), `character_abilities` (normalizes every sheet), `dice_results_final`, `dialogue_mode`, `relevant_lore` (`lore_for`), `standing_intentions`, `due_authored_events`, `engine_notices` (F4), `destination_residue` (F5), `background_presence_knowledge` (a `wget` and `room_of` per presence), `present_figures` rows, `dwellings` (registered §1.1(4)), `interaction_rounds`, `reaction_rounds`, `variant_seed`.
- **Severity:** DEAD (+PERF, E2). CONFIRMED by grep. Fix: build only what `_orch_extras`/`_gate_facts`/`_causal_event_inputs` read.

### F19 — Smaller dead remnants of the hands

- `agents/director.py:5674-5679` imports `living_world_allows` (unused) and assigns `_living_cfg` (never read): two DB reads per resolve (`world/living_world.living_world_config`); `5687` `if True:`.
- `agents/director.py:5092` reads `state.get("item_verdicts")`; no writer exists anywhere in the repo.
- `agents/director_scopes.py:308` and `agents/director_prose.py:167, 5071` branch on `spec.get("ext_id")`; no `SPECIALISTS` entry can carry one (`register_specialist`, cited at `director_scopes.py:215`, does not exist; extensions use `api.add_director_channel`). `_rebuild_channel_owners` runs once, at import, and nothing else writes the registries.
- `agents/director_reconcile.py:18, 42-46` import `CAUSAL_CATEGORY_REDIRECTS`, `SPECIALISTS`, `_CATEGORY_CHANNELS`, `_CHANNEL_SPECIALISTS`, used nowhere (the module is imported only by `director.py`).
- `director_scopes._DELEGATED_CHANNELS` is maintained and read only by `tests/test_prose_author_channel_discipline.py`.
- `agents/director.py:6700-6753` materialises a room from a `staged_lore` layout entry; `mapping.py:668` always returns `[]`, so only a rerun of a pre-2026-09-04 stored step reaches it — and there it is the one place this stage invents a room with an assumed `open` edge.
- `fl["needs_mapping"]` (2514, 2549, 2684, 2704, 2718, 2735, 2745, 2752, 3000) is written and read by nobody (`runtime.py:979` says so); `wget(pending)` at 2744 only feeds it.
- `_bind_specialist_patches`' `state_diff`-envelope unwrap and "unowned transform channels" notes (4897-4910), and `_completion_requests`' unwrap (5177-5178): `answer_for` already filters each patch to the owner's channels.
- **Severity:** DEAD. CONFIRMED by grep.

### F20 — Comments and docstrings that describe the deleted contract (one finding, many sites)

Each is read as current behaviour by the next reader:
- `director.py:1452-1457` `_canonicalize_interior_movements`: "The causal Director sees entity ids … asking the spatial hand to mint". Same "hand" vocabulary at `1507-1508`, `1531`, `1575-1585`, `1606-1621`.
- `director.py:2068-2070` `_interpret_extras`: "Shared by the causal fan-out below".
- `director.py:2334-2361` "Orchestrated interpret (design note 19): THE SAME specialists resolve dispatches … (`_dispatch_specialists`)" and "AND NONE OF THE FIVE IS BUILT ON A BEAT NOBODY READS THEM ON" — `_dispatch_specialists` does not exist and `_first_extras` (2106) builds all five every beat (registered §1.1(9)).
- `director.py:3070-3120` resolve-seam block: "Tier 1 (near-zero cost, same call): director_resolve's own changes_asserted manifest" — no sheet asks for it (`director_fanout.py:1006`), and the seam runs only without rows (§1.1(3)).
- `director.py:3757-3762` `_run_specialists`: the interior floor "raises before perception"; `4155-4164` catches it and warns. `4168-4176` `_require_complete_entity_interiors`: "no beat may introduce another one" — a beat can, with a warning. Its message (4257-4261) blames "the spatial specialist ladder".
- `director.py:3823-3825` "specialist failed; the stage model's own channels stand" — the stage model writes no channels.
- `director.py:4491` `_causal_event_inputs`: "consumed by the causal Director".
- `director.py:6281-6289` "WORLD PRESSURE must-tick floor (F5), enforced … buys exactly one correction retry", `6330-6339` "PLAYER-ACT AUTHORITY, enforced … One correction retry", `6447-6450` "a content violation that survives the retry", `6483-6487` "Orchestrated fan-out (design note 19): specialists read the FINAL prose … after the authority retries" — no retry exists (§1.1(6)).
- `director.py:5671` "Delivered to THIS payload only" (F5); `2592-2596` `tell_director` "reaches the NEXT beat" (F4).
- `director_scopes.py:215` `register_specialist`; `277-284` `_CHANNEL_SPECIALISTS` "The reconciliation repair router reads this … `_route_repair_omissions`" (neither exists).
- `director_scopes.py:17-19`, `director_reconcile.py:9-11`, `director_lingua.py:8-10`: "no `director_*` module may import `agents.director`" — `director_prose.py:220` and `director_repair.py:375` do, lazily, on purpose (the `_agent_json` patch seam); the rule needs its exception stated.
- **Severity:** STALE-DOC. CONFIRMED by grep (`_dispatch_specialists`, `_route_repair_omissions`, `register_specialist`: no definition anywhere).

## Efficiency

Ordered cheap-and-large first. "Per beat" = every played turn.

- **E1 — the interpret staging payload (F17), every interpret.** `agents/director.py:1808-1952`. One DB query (`director_context`), five `wget`s, a deep copy of the presence ledger plus a charter derivation (`with_charter_presences`), two plan reads, a sight digest, exits, an entity walk with `room_of` per entity — for one key. Gain unmeasured; on the owner's DB the durable presence ledgers are small (≤6 records; the `room_of` walk timed at 0.0–0.3 ms), so the cost is the reads and derivations, likely tens of ms on a charter town. Cheapest fix in the file: delete.
- **E2 — the resolve staging payload's dead keys and the residue (F5, F18), every resolve.** `5671-5726` (`residue_for`, `residue_facts`, `living_world_config`: 3+ DB reads on movement beats), `5802-6112` (`lore_for`, `style_guide` ×2, `paradox_visible_to` ×2, `wget` ×3, `character_abilities` normalizing every sheet, `background_presence_knowledge`). Unmeasured; delete.
- **E3 — per-call identity work in `_bodies_addressed_as`.** `5291-5297`: `observer_label_fn` (a `wget` of `known`, `persona_of`, a normalize of every cast sheet) per call, and `get_scene` (an uncached DB read and full JSON parse, `core/db.wget`) whenever `scene=None` — at `5479` (per declaration with an untargeted line) and `5510`. Also called per target per event in `_name_declared_targets` (4641) and per line in `_last_lines` (874). Fix: one `label_of` per speaker per stage, pass `resolve_sc`. Hotness: every resolve with speech.
- **E4 — `_interpret_extras(out)` rebuilt for `_run_specialists`.** `2381-2385`: `_awareness_view`, `_restraint_view` (`restraint_conditions` + `awareness_map`), `_conditions_view`, `_sightlines_view`, exits — rebuilt on every interpret where the encoder wrote anything, for a consumer that reads only `identity_index` and `entity_interiors` (3811, 3883, 4162). Fix: pass `_first_extras`.
- **E5 — the aperture and charter walks (F9).** Two `rooms_in_view` keys per resolve when the destination was re-spelled; `lay_charter_figures` walks `presence_figures_for_room` per room (a different view, by design); `reserved_plan_figures` + `reserved_charter_bodies` (5776-5782) walk every plan/body out of view every beat; `charter_view_for_rooms` (7127) walks again for the floor; `director._figures_in_view` (786-810, used at 419, 1192, 1996) calls `present_charter_figures` directly, bypassing `common.figures_in_view`'s memo (measured there: 8.1–14.9 ms per walk on chat 114). Answer to question 7: yes, three walks bypass the memo.
- **E6 — repeated reads of one row.** `player_authority` 4× per interpret (1964, 1976 per extra player, 2424, 2574); `style_guide` 2× in establish (399-400) and resolve (5807-5808); `paradox_visible_to` 2× per stage. Trivial each.
- **E7 — two bindings and two compilations per stage.** `_bind_specialist_patches` → `bind_items`, then `bind_items` + `compile_transforms` over the whole history again (4111-4125). CPU only, small at 1–5 spans a beat.
- Model calls in loops: none in these four files. The campaign re-entry (7945-7962) re-pays the author, decision model, encoder, room author and the charter voices once, by design; `pressures_ended` is one batched decision call.

## Already registered

- **UNBUILT_PIPELINE §1.1(1)** — hard player authority refuses nothing on encoder events (`apply_player_authority`, 2575). Confirmed still true.
- **§1.1(3)** — `_reconcile_resolution` runs only `if not out.get("causal_ledger")` (7793). Consequence I traced: `_player_claim_findings`, `_acquit_addressed_events`, `_verify_already_true`, `_verify_no_referent` (director_reconcile) and `_deep_audit_omissions`/`resolve_repair` are unreachable on live prose beats; only `_stamp_dialogue_articulation`, `_scale_relation_conflicts`, `_block_restrained_moves` and the placeholder strip run (7813-7820).
- **§1.1(4)** — the lean author payload lacks `dwellings` (built at 5797, read by nothing), `present_figures` answers, `planning_needs`, `author_notes`. F4/F5 are further members of this class not named there.
- **§1.1(6)** — authority limits warn and never correct (6391-6456); the comments that still describe retries are in F20.
- **§1.1(7)** — `fact_adjudications` (`_audit_fact_adjudications`, 7771).
- **§1.1(8)** — Director-originated lines reach no view; `dialogue_order`/`routed_to_background` never populated. Traced further: the whole loop at 7437-7509 (invented cast-line drop, PLAYER-SPEECH AUTHORITY drop, the presence-knowledge floor `_check_presence_knowledge_channel`, the background re-homing) iterates the empty post-validation `dialogue_log` on every prose beat.
- **§1.1(9)** — interpret builds all five world views (`_first_extras`, 2106, invokes every thunk).
- **§1.1(11)** — "the `required_channels` and verdict branches … trace before cutting". The trace, done: `director_prose.dispatch.answer_for` (5096-5124) emits only `{"transforms", "status": "encoded"|""}`; `tests/test_the_encoder_has_its_own_card.py:69` pins that the card never asks for `required_channels|reroute_to|not_mine`; `item_verdicts` has no writer anywhere. Unreachable on the prose path: `already_true`/`reroute_to` receipts and positional-misalignment errors (3895-3949), the legacy top-level `transforms` branch (3951-3952), `_completion_requests`' `required_channels`/`reroute_to` (5160-5200 — only the garment→attire rule is live), `_causal_completion_requirements`' `not_mine`/`item_verdicts` (5068-5103), `_unfulfilled_completion_requests`' `already_true` arms, `_reconcile_resolution`'s `repair_verdicts` (always `{}`, 3527/3620-3626). Also the ledger-notes layer (`note_key_targets`, `RETIRED_HANDS`, `manifest_category_targets`).
- **§1.216 residual** — "a silent beat stays whole with the empty-input guard" (conduct rule only on input). Adjacent to F1, not the same defect.
- **UNBUILT_WORLD §1.131** — `needs_mapping` from a word-cue list (F12 adds the `mapping_request` pollution).
- **UNBUILT_PLATFORM PERSISTENCE-F17** — `engine_notices` not frame-scoped (F4 is that nothing reads it).
- **UNBUILT_WORLD §1.168** — resolve crossings read from `out.orchestration` after `attach_record` (fixed; verified at 7144-7147).

## Structure notes

**Question 1 — phases of `director_interpret` (1701-2808).**

| # | Lines | Phase |
|---|---|---|
| P0 | 1701-1729 | offscreen (bubble) beat: deterministic interpretation, prepared rooms carried, early return |
| P1 | 1730-1754 | scene, persona, rooms built in view (`director_rooms.install_prepared_rooms`), player room |
| P2 | 1756-1806 | cast rows; raw reads (shadow, presences+charter, intents); fm, clock, room window, due authored events |
| P3 | 1808-1952 | staging `payload` — dead except `author_notes` (F17) |
| P4 | 1954-2057 | lean model payload: event inputs, identity index, causal rooms/figures/world index, players' view |
| P5 | 2059-2121 | lazy world views, `_interpret_extras`, `_first_extras`, `director_prose.run` (author → decision model → encoder → room author) |
| P6 | 2122-2181 | post-run: quoted lines, `normalize_causal_ledger`, doorway routing, multi-player split, final movement, interior ids, `flow.dice`, validation, `norm_sequence` |
| P7 | 2182-2246 | silent-beat guard (F1) |
| P8 | 2247-2323 | player-declaration floors: narrated speech, unanchored speech, authorial NPC routing, refused-conduct offers, target binding, concealment (player and extra players) |
| P9 | 2324-2391 | encoder split and fold: addressees from spans, beat view, dispatch, extras rebuild (E4), `_run_specialists`, cast doubles (F2), attach record, minted interiors |
| P10 | 2392-2474 | standing facts, validated assertions, contact program, onset preview assertions, silent rooms, installed-rooms record |
| P11 | 2476-2535 | flow: reactors (+ addressed cast, + co-present fallback), defaults |
| P12 | 2536-2560 | interpret reconciliation (model repair only without rows), mover-as-self, authority claims |
| P13 | 2561-2642 | player-authority dial, skip refusals, voided spans |
| P14 | 2643-2681 | contested-action flags |
| P15 | 2682-2761 | location query, destination canonicalization, English cue lists (F12), pending, due events |
| P16 | 2762-2805 | follow ops, follow-walk waits |
| P17 | 2806-2808 | span coherency report, return |

**Phases of `director_resolve` (5377-7965).**

| # | Lines | Phase |
|---|---|---|
| R0 | 5377-5411 | setup; shown clock; dice rolls (F6) |
| R1 | 5413-5537 | declarations: reaction rounds, loop, concealment refs, `_take_declaration`, parallel character results |
| R2 | 5538-5577 | stored scene; declared/onset contacts; character endings/material effects; `resolve_sc` onset preview |
| R3 | 5578-5644 | onscreen charter figures: aperture A (F9), lay, addresses, `declare_charter_figures` (model), echo floor |
| R4 | 5645-5670 | per-declaration exits and sprint reach; intents; `movement_for_resolve` |
| R5 | 5671-5726 | destination residue + living-world config (F5, F19) |
| R6 | 5728-5800 | social standing, body parts, crowds, aperture B, present/reserved figures, figure answers, dwellings |
| R7 | 5802-6112 | staging `payload` (F18) |
| R8 | 6113-6255 | gate facts, identity index, event inputs, named targets, causal index, `_model_payload`, campaign notes, `_orch_extras` |
| R9 | 6256-6289 | `director_prose.run`, normalize, doorway routing, interior ids |
| R10 | 6290-6329 | world-pressure ticks and endings |
| R11 | 6330-6456 | authority readings on the prose (warn-only) |
| R12 | 6457-6502 | charter declarations, figure noise (F3), validation, fan-out fold, cast doubles, attach, interiors |
| R13 | 6503-6699 | diff assembly: positions, following ops, beat time, speech compile, contact/substance ops, onset merge, `out["state_diff"]`, travel continues |
| R14 | 6700-6993 | movement backstop (legacy staged lore 6700-6753; mover; blocked / contested prefix / walk / approach; vehicle) |
| R15 | 6995-7040 | every mover walks; within-room; following; near-group |
| R16 | 7041-7160 | physical floor (unreachable positions; charter view) |
| R17 | 7161-7325 | identity floor, plans stood up, touching figures, mint placement |
| R18 | 7327-7362 | `resolved_event`/`summary` synthesis |
| R19 | 7364-7760 | dialogue-log assembly (drops dead on prose beats; concealment restore; re-attribution; re-append; addressees; dedup; occurrences from the timeline) |
| R20 | 7760-7792 | public evidence grounding; fact-adjudication audit; epithet/address-form reports |
| R21 | 7793-7841 | reconciliation (only without rows) or structural floors; approach-is-not-arrival LAST |
| R22 | 7843-7895 | causal phase floor; recompiler stats |
| R23 | 7896-7965 | coherency report; beat events; campaign validation and one re-entry |

Natural seams for the split program: R1+R3 (declaration intake and charter voices), R5+R6 (aperture, figures and their views — one derivation, fixing F9 on the way), R13 (diff assembly), R14-R16 (≈450 lines that belong beside `director_movement`), R17 (mint floors), R19 (≈400 lines: a `director_dialogue` sibling), R21-R22 (structural floors beside `director_reconcile`). Interpret: P8 (player-declaration floors), P10 (assertions/onset), P11-P15 (flow normalization; P15 is mostly dead, F12/F19). P3 and R7 are deletions, not moves (F17/F18). Monoliths-in-miniature: `director_resolve` 2,589 lines, `director_interpret` 1,108, `_reconcile_resolution` 521 (reachable only without rows), `_run_specialists` 425 (about half is verdict handling dead on the prose path).

**Question 2 — state threaded through locals (two representations free to disagree).**
- Destination: raw `interp["movement"]["to_room"]` (5580-5585, aperture A) vs `_mv_for_context` (5663, canonical) vs `mv`/`_mv_for_context` reset to `None` at 6726 after `_orch_extras["movement"]` (6228) already captured the movement (F9).
- Player room: `ctx["_player_room"]` (payload rooms/plans/notes 5827/5942/5954, mint fallback 7171) vs `room_of(resolve_sc, p_name)` (5584, lean payload `here`/fallback 6170-6174) vs `room_of(sc, p_name)` (`subject_prev_room`, 6727) — three readings of one fact in one stage; the B36 note (3452-3463) explains only the first.
- Scene: `resolve_sc` (author, encoder, aperture A, plans, causal index) vs `sc` (sightlines F8, payload attire 5856, exits/sprint 5645-5654, crowds 5742, author-notes reach 5995-5997, aperture B, route checks). `common.rooms_in_view` keys its memo without the scene, so A and B can be served each other's answer.
- Figures: `_figure_rows`/`_figure_declarations` (aperture A, presence view) vs `_present_figures` (aperture B, Director view); `_identity_index` takes the former (6145), the causal index the latter (6174).
- Authority mode: interpret dial vs resolve fallback (F10).
- Rows: `ledgers` / `causal_ledger` / `sequence` / `_all_causal_sequence` — one list object for the first two until the schema dump; guards edit only `sequence` (F1).
- `dialogue_log` read at 6417 and 7175 before it is built at 7759 (F14).
- Chrono ids: interpret's and resolve's numbering meet in one merged diff with no stage mark (F7); speech alone is offset (6613-6625).
- `dice` built at 5399 from interp `flow.dice`, read at 6116, 6146, 6488, 7354 (dead, F6).

**Module-level mutable state.** `director.py`: none. `director_scopes.py`: `SPECIALISTS` (dict; no writer after import), `_CHANNEL_SPECIALISTS` (dict), `_DELEGATED_CHANNELS` (list), `_LIST_DELEGATED` (set) — all written only by `_rebuild_channel_owners`, in place (no rebind), called once at import (314); `_CATEGORY_CHANNELS`, `CHANNEL_STAGES`, `RETIRED_HANDS`, `_STRUCTURAL_CHANNEL_FACTS` are dicts nothing writes. `director_reconcile.py`, `director_lingua.py`: none. `director.py` is also half a facade: 108 of its 349 module-level imported names are never referenced in its body (re-exports read by tests through `agents.director`).

**Duplicated helpers.** Three line-folding functions with different rules: `director._fold_line` (strips all punctuation), `director_prose._fold_line` (trims edge punctuation), `common._echo_fold`; each comparison stays within one of them today. `director._figures_in_view` vs `common.figures_in_view` (memoised; F9/E5).

## Docs checked

- CLAUDE.md, "a beat that reaches for a room no plan holds raises a typed planning need … instead of inventing one" — HOLDS on the live path (2690-2709 hands the destination to the compiler); the one exception is the legacy `staged_lore` loop (6729-6753), reachable only by rerunning a pre-2026-09-04 step.
- CLAUDE.md / AGENTS.md, "must not silently replace the player's declared speech/action" — HOLDS for the declaration channels (`restore_declared_quotes`, `discard_unanchored_player_speech`, `ABSOLUTE` declaration); fails on the empty-input path (F1); warn-only limits registered (§1.1(6)).
- AGENTS.md:259-287 Director contract: "categories are the channels actually written" — HOLDS (`director_prose.py:4596-4605`); "a channel written at a stage that cannot carry it is DROPPED and said to be dropped" — HOLDS (3994-4005, 4061-4069).
- AGENTS.md:289, "a silent beat, which keeps nothing its own prose made" — FAILS (F1).
- AGENTS.md:297-299, the resolve "is told what the player side already put into the world (`already_happened`)" — HOLDS, and on a silent beat it is told what the player never did (F1).
- Design.md:452 and :455 — the row "The Director can see what the engine did" is in the table TWICE with different text; both say `tell_director` reaches the next beat's Director — FAILS (F4). Design.md:877 — same claim, FAILS.
- `core/pipeline_context.py:436-445` (`engine_feedback` "is for the model") — FAILS (F4).
- Design.md:544, "Player authority modes … enforced in `director_interpret`" — HOLDS at interpret; the resolve reports `world_author` (F10).
- `director_movement.movement_for_resolve` docstring ("the figures in view … take it from here") — FAILS for aperture A (F9).
- `common.rooms_in_view` docstring ("the scene graph itself does not change within a beat … so it is not part of the key") — resolve passes `resolve_sc` and `sc` to it in one stage (5582, 5764).
- `world/routines.py:19-23` and `world/living_world.living_world_config` docstring (the Director's residue gate composes the config) — STALE (F5, F19).
- `director_scopes` module docstring ("`SPECIALISTS` is now only the owners table") — HOLDS; its `_CHANNEL_SPECIALISTS`/`register_specialist` comments — STALE (F20).
- `director_reconcile` module docstring ("makes no model call") — HOLDS; most of it is reachable only through §1.1(3).
- `director_lingua` / `director_scopes` / `director_reconcile` import-direction rule — two lazy exceptions exist (`director_prose.py:220`, `director_repair.py:375`) and are deliberate; the rule's text should name them.
