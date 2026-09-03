# Harrowmere replay, 2026-09-03 — merged main against the 2026-09-02 baseline

Same brief, seed 3, persona, lorebook and the same forty first-person inputs as
`demos/harrowmere-playtest-2026-09-02/` (traversal worktree), replayed on main
`3bfbd33e` (steps 1–3 of the plan, the day cycle, forks E/F/G; 11,351 tests
green). Scratch DB with the owner's providers and settings copied in;
`reasoning_effort.utility=off`; `population: 100` on the generate request;
`promotion_thresholds` left at the defaults. Chat 1, forty turns, no errors, no
resumed turns. Artefacts beside this file: `transcript.md`, `audit.json`
(per-turn digest incl. commit results, stations, light, voices), `summary.json`.

The planner is a model call, so the town is not byte-identical to the
baseline's: 39 planned rooms (baseline 19), 7 charters, 100 bodies closed
exactly (baseline 108), room ids differ (`inn_common` for `ford_inn_common`,
`upland_gate` for `gate_post`, `shrine` for `orrin_shrine`). Comparisons below
are by role, not id. The scripted inputs still name the baseline's reeve
("Nookfeller"); this town's reeve is "Brgaron Brfordwick", and the engine
resolved the address to him anyway.

## Before / after

| measure | baseline 2026-09-02 | replay 2026-09-03 |
|---|---|---|
| turns | 40, one resumed after a 503 | 40, none resumed, no errors |
| wall clock / turn | median 33.5s, mean 33.0, max 63.2 | median 35.9s, mean 35.8, max 67.3 |
| model calls / turn | median 17, mean 16.2 | **median 8, mean 8.2** (dispatch-keyed specialists) |
| mapping_stage : mapping_quick | 24 : 16 | 21 : 19 |
| planned_context calls : hits | 23 : 15 | 21 : 12 |
| background_react fired | 15 / 40 | 21 / 40 |
| plan size | 19 rooms (+4 frontier stubs) | 39 rooms (+4 frontier stubs) |
| planned rooms at the opening commit | 4 of 19 survived turn 0 | **all 39 in the scene at turn 0**, every planned edge kept ("planned exit restored" fired once, t38) |
| planned rooms entered : described | 14 : 14, **0 described before entry** | 17 : 17, **2 described before entry** (market_square from the gate at t0, clerk_office through the hall doorway at t26) + house_aldred developed through its open door at t17 and never entered |
| stubs developed in view (not the player's room) | 0 | 4 events (t0, t17, t26, t38) |
| planned stubs still bare at the end | 4 of 23 (7 held constant while in view) | 25 of 43, all houses/annexes/back rooms never approached |
| Director-minted people | 10 (8 duplicating a present post-holder) | **7 (6 duplicating a present post-holder; identity floor bound 0)** — see N1 |
| duplicate / unplanned rooms | 8 (`town_mill`, `ford_inn_stables`, `stone_lane_cottage`, `market_square_2`, `ford_road` ×3, …) | **6**: frontier-grammar stubs `bridge_road_2`, `slate_lane_2`, `market_square_2`, `market_square_3`, plus `upland_road`/`upland_road_rise` minted beside the misnamed stub. **Movement-target duplicates: 0** (`mill`, `inn_stable`, `inn_kitchen`, `inn_cellar`, `clerk_office` all landed on their planned ids) |
| charter observations acquired | **0 on all 40 turns** | **213 claims over 27 turns** (max 26 in one beat); figures sighted on 5 turns |
| figure acts (fork E) | n/a | 1 landed (t26 request → `declined`, reason `pressed`), 0 refused, **6 act beats that never reached the ledger** — see N4 |
| a handed thing follows its carrier | letter and satchel stuck at `gate_post`/`reeve_hall`/`ford_inn_guests` | **still stuck**: satchel + letter at `reeve_hall` t3–t26 while the player slept at the inn and walked the town; at `market_square` t28–t39 — see N3 |
| voiced body continuity | three reeves, three innkeepers | reeve `reeve:0001` on all 6 hall beats, innkeeper `innkeeper:0001` on all 3; **smithy: three different bodies on four beats** (t23 gate watchman, t24/t29 ambient duplicate, t30 the real smith) |
| name case | "halinham nookfeller" | capitalised; but "Brgaron Brfordwick", "Kelselwell Brbrookmere", "Tamstanmere Gargatebridge" — see N8 |
| `{{L1}}` in prose | 3 turns | **0** (3 stray tokens stripped with a warning: t12, t22, t25) |
| narrator invented quoted dialogue | 3 turns | 5 turns (t5, t24, t33 quote the player's own line; t18, t26 invent NPC lines) |
| composer tripwire | 2 | 1 (t32, the trader's canonical name) |
| promotion proposals | 0 (thresholds set to 99) | **5 proposed** (reeve t5, innkeeper t10, gatekeeper t28, blacksmith-duplicate t29, trader t32); Director named 0 cast changes |
| clock display over the run | "mid-morning" for 65 story hours | mid-morning → dawn → afternoon → morning → midday → dusk; hour 9.00 → 18.22 over 57.2 story hours; anchor 9.0, day 24h |
| outdoor light | declared only | derived: lit by day, **dim at dawn (t11–t17) and dusk (t39), dim under the storm at midday (t28–t32)**; declared `bright` never overrode the sun |
| stations written by the spatial hand | not measured | 34 / 40 turns; `cover` 0 / 40; sightlines payload not persisted by any stage, so unmeasured |
| charter 4h window | 0.69s at 119 bodies | 0.76s at 107 bodies |
| walked edges over the run | 1,533 (householders 0) | 11,136 (householders 5,214) |
| warnings | 108 | 97 |

## Baseline gaps: gone, partial, persisting

| # | baseline gap | status | evidence |
|---|---|---|---|
| 1 | Director mints duplicates of present charter bodies | **partial** | 8 → 6 duplicates, but the identity floor fired on none: every mint was UNPLACED on a movement beat (N1) |
| 2 | voices from other rooms reach the narrator | **partial** | t7 reeve answers as the player leaves for the inn (same-beat move); t11 innkeeper voiced with the player on Bridge Road; t23 the gate watchman answers a line spoken in the smithy; t24 the smithy duplicate's owed reply lands while the player stands at the gate. t13 (shrine-keeper's wave seen from the bridge, line withheld) is the rule working |
| 3 | parallel voices contradict on one fact | **gone** | one voice per beat on all 21 fired turns |
| 4 | duplicate rooms beside planned ones | **partial** | the movement-target half is gone; the frontier-axis half persists and is now the whole of it (N2) |
| 5 | opening commit discards the seeded plan | **gone** | 39/39 rooms and every edge at turn 0 |
| 6 | seed keyed on query text and gated on needs_mapping | **partial** | hits 12/21, but the handoff described 17/17 entered rooms regardless, 2 before entry |
| 7 | presim ignores the skeleton | **gone** | 11,136 walked edges; households walked 5,214 |
| 8 | planner scale and budgets | **partial** | population exact (100), one head per post; historian overran again (N9); one house holds 48 sleepers (N10) |
| 9 | narrator line-protocol leaks | **partial** | tokens gone; echoed/invented lines persist (N11) |
| 10 | composer tripwire | **partial** | 2 → 1 (N7) |
| 11 | provider 503 aborts the turn | not exercised | no 503 this run; the stage degrades to silence by construction |
| 12 | carried things don't follow the carrier | **persists** | the vouched-carrier fix covers charter holders; the player's own satchel/letter still stay in the room they were last stationed in (N3) |
| 13 | charter news never reaches a voice | **unverified** | t32's trader line ("fewer carts from the upland farms, harvest thin") is consistent with the traders' 28 news keys; t21's "Old Geddric" is invented (no such body). The payload carries news now; whether a line came from it is not observable in the rows |
| 14 | authority / reports_to consulted by nothing; clock frozen | **partial** | clock fixed; the t24 order at the gate was classified `claim and request`, never `command`, so `has_standing` was never consulted (N4) |
| 15 | private interiors have no rule | **partial** | t17 the Director waited on the threshold for leave (clause held); but mapping minted a resident for a charter-berthed house and nobody inside could answer the knock (N5, N6) |

## New or re-originated defects, by the stage they originate in

Every one below was read across all of the turn's stages (`audit.json` carries
the digest; the scratch DB carries the rows).

- **N1 — director_resolve → director_floors.** All 7 person mints (`gatekeeper` t0, `shrine_keeper` t12, `bridge_watch` t13, `the_miller` t15, `the_blacksmith` t23, `the_hostler` t35, `the_brewer` t36) were emitted with NO `state_diff.positions` entry ("Unplaced entities" warning on each), and six of the seven were minted on the beat the player moved into the room. `_bind_minted_entities_to_present_figures` binds only against figures in the mint's room, with `fallback_room=ctx["_player_room"]` — the room the player was in BEFORE the move — so the floor found no figures and bound nothing (`identity_bindings` null on all 40 turns). The gatekeeper at t0 is `director_establish`, which does not run the floor at all. Each unbound mint then became an `ambient` charter body that shadowed the real one for every later act and voice (t24/t29 "The Blacksmith" is `ambient/the_blacksmith:2b61fc`; the real smith spoke only at t30 when the input said "the smith himself"). Rule: a mint with no position on a movement beat stands where the player ARRIVED; the establish beat needs the same floor.
- **N2 — commit_scene_state → structure.prepare_frontier_expansion / mint_frontier.** The frontier grammar names an axis stub after a room the plan already has: t0 `upland_gate`'s "upland road" axis minted "bridge road" (purpose `crossing`) → `bridge_road_2`; t13 `slate_lane_2` ("dwelling") off `toll_bridge`; t14/t15 `market_square_2`/`_3` ("trade") off `mill_lane`/`mill`. At t38 the Director, shown a stub called "bridge road" north of the gate, minted `upland_road` and `upland_road_rise` beside it. Same class as the baseline's `ford_road` ×3.
- **N3 — director_resolve (objects hand) + spatial merge.** t5 "I hand Nookfeller the letter": the objects hand ran and emitted no `inventory_ops`; the letter stayed a loose object at `reeve_hall` (positions), never held by the reeve, so the vouched-carrier path had nothing to vouch. The satchel (worn, in `attire`) and the letter were left at `reeve_hall` from t3 to t26 while the player was at the inn, the bridge, the mill and the lane; `derive_contained_positions` moved them only when the spatial hand happened to restate a `near` group (t27 "Reconciled near group … by fresh anchor"). A worn or held thing has one position: its carrier's.
- **N4 — director_social + charter_observe.resolve_target_body.** Of seven beats carrying an act toward a body, one landed. Misses: t18 kind `ask` (outside `FIGURE_ACT_OF_SPEECH`, dropped silently); t24 kind `claim and request` (outside the card's closed list, so the order was never an order and `has_standing` was never consulted); t15 target "The Miller" and t23/t29 "The Blacksmith" resolve by exact name only to the AMBIENT duplicate, never to the post-holder (token subset requires the article "the" to be a word of the body's forms); t36 "the brewer" matches nothing because the post is `cook` (authority text "brews small beer" is the engine's own vocabulary and the resolver does not read it); t35 no speech act at all. Rule: an unknown kind warns; an article or title in a spelling is not a token to match; a role noun resolves through the post's authority text, not only its name.
- **N5 — director_resolve prose vs the charter ledger (t26).** The prose author had the reeve grant the request ("Clerk's through here. Mind the dust") and the narrator rendered it; the same beat's figure act landed as `request → declined, reason pressed`. The `answers` preview exists for the voice (`presence_view`) but the Director never sees it, so the story and the ledger now disagree about whether Wren was shown the rolls (t33 continues as if granted).
- **N6 — mapping_stage (t17).** Developing the planned stub `house_aldred`, the mapping model minted "Mistress Tamar Aldred" (entity + position + station + npc_suggestion) for a house the charter already berths eight sleepers in. The Director spoke to her in prose; no ledger holds her, so nothing could voice her; the narrator wrote "No answer comes from within". The room-development seed does not carry the charter's residents, so the developer invents them.
- **N7 — background_react gate (t17, t23).** The knock at Aldred House reached 26 minds (acquired 26) and produced no voice, because a voice candidate must stand in the player's room; a door is a channel the gate does not model. At t23 the gate watchman (`watchman:0003`, room `upland_gate`) answered a line spoken inside the smithy; the step records `selected` but no reason, so the trigger that qualified him is not auditable from the rows.
- **N8 — director_resolve → composer (t32).** `dialogue_log[].intended_target` and `resolved_event` carry the trader's canonical name from `present_figures`; the composed view admitted it and the tripwire fired ("Layer A admitted a fact with no channel"). The Director may know the name; the player's view may not.
- **N9 — charter_identity._syllable_name + planner naming profile.** Starts like `br` joined to consonant-initial middles give "Brgaron", "Brbrookmere", "Brfordwick"; every voiced name is three or four syllables of fragments. Display names also prefix the rank title, so the voice is "Reeve of Harrowmere Brgaron Brfordwick".
- **N10 — charter_generate.historian_budget.** At 100 residents the budget is 12,000 tokens; the historian returned 13,327 and the JSON was unterminated (`historian_error`), so the town opened with no history brief. Same class as the baseline's overrun at the old 7,000.
- **N11 — charter_generate berth split.** Population scaling put the generic `household_member` post into `house_aldred`: 8 + 5 annexes × 8 = 48 sleepers under one roof, while the other nine houses hold 3 each.
- **N12 — narrator.** Quotes the player's own input as dialogue (t5, t24, t33); invents "Back already?" (t18) and the reeve's grant (t26); reuses a signature phrase ("dry earth scent sharpens") on at least 9 turns, flagged 4 times; relabels the blacksmith as "the miller" (t24, the label exists in no other stage).
- **N13 — director_resolve time.** t19: `display_advance: "by dusk"` with `duration_seconds: 39600` from 06:19 lands at 17:19; the cycle correctly derived `afternoon` from the duration and the Director's stated phase was silently wrong. t9's skip fired "orchestration scope: a room was set dim … 'light' duty block was not loaded" — the dispatch key did not reach the light duty on a skip that changed the sky.
- **N14 — planner output variance.** Same brief and seed: 19 rooms/108 bodies on 2026-09-02, 39 rooms/100 bodies today. The closer holds population; nothing holds the layout.

## What is verified working on merged main

- Opening commit keeps the plan; minted rooms land on planned ids; a developed room keeps its planned exits.
- Rooms in view get developed (4 events) and every entered planned room is described on the beat of entry.
- Charter minds receive what is said in their room (213 claims), figures are sighted on arrival, the player is a claim subject ("the slight woman") and greeted as met on return.
- One voiced body per beat; the same reeve and the same innkeeper answer across visits.
- Promotion proposals surface at the named thresholds (5 in 40 turns); the Director did not name a cast change.
- The day cycle: two sleeps and two afternoon skips moved the hour 9.00 → 18.22; outdoor rooms went dim at dawn, at dusk and under the storm; declared `bright` never overrode the sun; charter bodies were home at dawn (the mill and smithy were manned by the head post only) and "neighbours drift toward their doors" at dusk.
- Stray line tokens are stripped; the berth-privacy clause held at the threshold.
- Calls per turn halved; wall clock unchanged (the narrator call dominates).

## Harness caveats

- The scripted inputs are the baseline's verbatim, so they address "Nookfeller" and "her" (the innkeeper) in a town where the reeve is Brfordwick and the innkeeper is voiced as "he"; the engine resolved the name to the reeve and the narrator followed the input's gender on t9.
- Planner variance (N14) makes per-room comparison possible only by role.
- The `sightlines` digest is computed inside the Director payload and persisted nowhere, so the geometry measure here is the station write rate only. `sight_digest` on the final scene returns an empty `sees` because charter bodies hold no scene stations.
- The historian overran and the town opened without its history brief (N10); non-fatal, but the "recent life" of residents was never authored.
- No 503 this run, so the non-fatal voice stage was not exercised.
- Persona `initial_outfit.wearing` as strings worked ("bare arms" in the rain is the narrator, not the outfit).
