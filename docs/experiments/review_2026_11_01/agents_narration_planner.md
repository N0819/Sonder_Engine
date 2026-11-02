# Audit: narration, the Writers' Room (planner, dramaturge, room tools), plot packages, prompts

Auditor scope: `agents/narration.py`, `agents/story_planner.py`, `agents/dramaturge.py`,
`story/room_tools.py`, `story/plot_packages.py`, `llm/prompts.py`. Working tree at
`84f3de23` (branch `worktree-jev-character-tracking`), 2026-11-01. Read-only; no test
run was needed (every CONFIRMED item below was reproduced with a pure-function snippet
on `.venv/bin/python` or traced call by call).

## Scope read

Read in full, line by line:

- `agents/narration.py` 1-3196 (all of it).
- `agents/story_planner.py` 1-3485 (all of it).
- `agents/dramaturge.py` 1-469 (all of it).
- `story/room_tools.py` 1-1791 (all of it).
- `story/plot_packages.py` 1-4571 (all of it; the anatomy in `S/anatomy/plot_packages.md` used as a map).
- `llm/prompts.py` 1-719 (all of it).

Read in part, to trace a call or a claim (not audited):
`persist/commit.py` 440-850 (commit_all, the tail), `persist/commit_scene_state.py`
1547-1720 and 2439-2990 (compose/prepare/commit_scene), `persist/commit_common.py`
465-487, `persist/commit_mapping.py` 262-300 and 745-765, `persist/commit_memory_write.py`
318-333, `core/db.py` `transaction` (2349-2392) and `get_setting`, `core/jobs.py`
`read_through`/`spared`/`is_cancelled`/`story_rewound_past`, `persist/steps.py`
`active_content`/`active_mapping`, `story/room_conversation.py` `converse_stream`,
`story/room_calls.py` 35-155, `story/room_proposals.py` (kinds, statuses, judge/settle/
take/mark_due), `story/mandates.py` spend/pacing constants, `world/region_events.py`
`apply_wave` head, `world/spatial_geometry.spatial_digest`, `world/spatial_prose.
contact_sensation` head, `world/spatial_routing.visible_adjacent_rooms` head,
`world/spatial_levels.py`/`spatial_sound_field.py` floor tables, `agents/common.jparse`,
`agents/composer.observations_from_render`/`perception_packet`, the en/ja narrator,
story_planner and dramaturge cards, `docs/design/DESIGN_ROOM_PRELUDE.md` §§1-4c,
`docs/design/DESIGN_STORY_PLANNER_AND_DRAMATURGE.md` §5, the AGENTS.md rows for
Narration / plot packages / room tools, Design.md rows 206/215/398/401/411,
PIPELINE.md 1238-1256 and 1395.

`agents/common._check_narrator_fidelity` internals were NOT audited (another auditor);
only how narration uses its verdicts.

## Findings

Most severe first. "Line" numbers are the current working tree.

### F1 — A clocked operation can land twice: `fire_due_clocks` is not atomic, and the package store is rewritten whole by racing threads

- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (partial-failure path, traced); PLAUSIBLE (the thread race, needs timing).
- **Where:** `story/plot_packages.py:4284-4385` (`fire_due_clocks`), `4065-4148` (`publish_package`), every store writer (`new_package` 423/447, `edit_package` 457/493/506, `draft_operation` 514/542, `remove_operation` 547/560, `activate_due_packages` 4461/4471, `resolve_package`, `retire_package`); caller `persist/commit.py:811-819`.
- **Code:**
  ```python
  stored = packages(cid, frame_id)            # 4306, no transaction
  ...
  op["applied"] = _apply_operation(...)       # each seam autocommits its own writes
  except ValueError as exc: ...               # only ValueError is caught
  ...
  if dirty:
      save_packages(cid, stored, frame_id)    # 4382, once, at the very end
  ```
  and in `publish_package`: `stored = packages(cid, frame_id)` at 4078, a possible `preview_package` re-run (4102), then `with transaction(): ... save_packages(cid, stored, frame_id)` at 4122-4145 — the read is outside the transaction.
- **Failure scenario 1 (deterministic):** a package clock carries op A (`arrival`) then op B (`incident`). At the beat it is due, A lands (planned entity moved, an authored-event notice minted, both autocommitted), then B's seam raises anything but `ValueError` (a `KeyError`/`TypeError` in a charter surgery, a sqlite error). The exception leaves `fire_due_clocks` before `save_packages`; the commit tail turns it into a warning (`commit.py:817`). A's `applied` and the clock's `fired_turn` were never saved, so on EVERY following beat the clock is still due, A lands again (another notice, another move), and B raises again — a repeating double application until someone retires the package.
- **Failure scenario 2 (race):** a fill job (Room thread) calls `publish_package` for package P2 while the turn thread's commit tail runs `fire_due_clocks` for P1. Whichever `save_packages` lands second writes back the WHOLE store as it read it: either P1's `applied`/`fired_turn` marks are reverted (its clock fires again next beat: double arrival/harm/notice), or P2 is reverted to `draft` with its operations already applied in the world (a later re-publish applies them a second time: duplicate lore, artifact, plan). `draft_operation`/`new_package` racing with each other (panel reply + fill job) lose a draft or an operation the same way.
- **Verified:** read `fire_due_clocks`, `publish_package`, all writers; `core/db.transaction` (2349) takes `_write_lock` + `BEGIN IMMEDIATE`, but `fire_due_clocks` and the drafting writers never enter it, and `publish_package` reads before entering it. Call site `commit.py:811-819` runs after the turn's transaction ("Out of band like its neighbours").
- **Fix:** every store writer does read-modify-write inside one `transaction()` (the process lock serialises them); `fire_due_clocks` saves the package (marks included) in the same transaction as each clock's operations, so a failure rolls back both or neither. Catch-all per op recorded as `refused` rather than aborting the pass.
- **Test shape:** monkeypatch op B's apply to raise `KeyError`; call `fire_due_clocks` twice; assert op A applied exactly once (count of minted authored events / planned-entity writes).

### F2 — A ruin that lands at publish is never retired: `publish_package` passes `turn_id=None`

- **Severity:** CORRUPTION (two stores disagree). **Confidence:** CONFIRMED (traced).
- **Where:** `story/plot_packages.py:4136-4137` (`_apply_operation(..., turn_id=None)`) → `_apply_region_event` 3133-3155 → `world/region_events.py:314` (`if destroy and turn_id is not None:` retire in `room_registry`).
- **Failure scenario:** the Room publishes an unclocked `region_event` with `effects.destroy` (`at_once`, intensity 1). The first wave lands at publish: `_stand_hazard` writes a `world_conditions` row `state: "ruined"`, but the `room_registry` retirement is skipped because `turn_id` is None. The registry (the ONE answer to "is this room retired", per the B8 comment in `apply_wave`) says live while the condition says ruined; nothing later retires it (a ruin stays in the scene, so the commit's registry projection never sees it leave). Only waves fired by a clock (`fire_due_clocks` passes `turn_id`) retire. `tests/test_plot_drama.py::test_ruin_retires_the_room...` covers only the clocked path.
- **Fix:** resolve the latest turn's id at publish (the same row `_latest_turn_idx` reads) and pass it, or file the retirement for the next commit.
- **Test shape:** publish an unclocked destructive region_event; assert `room_registry.retired_turn_id` is set.

### F3 — A bare string in a list-valued operation field is split into its letters

- **Severity:** CORRUPTION (bad persistent rows; one-letter rooms/aliases). **Confidence:** CONFIRMED (snippet).
- **Where:** `story/plot_packages.py:1046,1056` (`plan_rooms.frontier`), `1339` (`plan_entity.aliases`), `1557,1559` (`plan_creature.hunts`/`prey`), `1944` (`file_lore.knowledge_locations`), `2483` (`presimulate.charters`), `226` (`clock.advance_on`).
- **Code:** `"frontier": [_text(x, 60) for x in raw.get("frontier") or () if _text(x, 60)]`
- **Reproduced:**
  ```
  _shape_plan_rooms({...'frontier': 'yard'})      -> ['y', 'a', 'r', 'd']
  _shape_plan_rooms({...'frontier': 'harbour'})   -> ['h','a','r','b','o','u','r']
  _shape_plan_rooms({...'frontier': 'the quay road'}) -> REFUSED: "frontier 'e' is a direction"
  _shape_plan_entity({'name':'Tom Harrow','aliases':'Old Tom'})['aliases'] -> ['O','l','d','T','o','m']
  _shape_plan_creature({..., 'hunts':'cellar','prey':'rats'}) -> hunts ['c','e','l','l','a','r'], prey ['r','a','t','s']
  _normalize_clock({'advance_on': 'fire'}, {})['advance_on'] -> [{'event_kind':'f'},{'event_kind':'i'},...]
  ```
  A frontier of one-letter axes mints one-letter stub rooms; one-letter aliases enter `reserved_identities` and, for a `thing` plan, the minted scene entity's `aliases` (`world/planned_entities.py:409-411`); a word containing n/s/e/w is refused with an error naming a letter the model never wrote. `known_by` (1361-1364) and `director_note.rooms` (2971) already handle the bare string; `_plan_geometry.over` was fixed for exactly this ("'chapel' read as ['c','h','a','p','e','l']", review L3) — the class was fixed at one instance.
- **Fix:** one `_as_list(value)` helper (a str is `[str]`, a non-list non-str is `[]`) used by every list field of every shape. **Test:** parametrize over every list-typed field in `OPERATION_FIELDS` with a bare string; assert no single-character entries.

### F4 — `deliberate` marks every accepted-without-package proposal "implemented" by the round's FIRST published package

- **Severity:** CORRUPTION (proposal ledger). **Confidence:** CONFIRMED (read).
- **Where:** `agents/story_planner.py:2369-2370`.
- **Code:**
  ```python
  if verdict == "accept" and not package_uid and out["published"]:
      package_uid = out["published"][0]
  ```
- **Failure scenario:** a round judges proposals A (a storm) and B (a rival arrives). The Planner accepts both, publishes only the storm package P1 (B needs a grant it lacks, so per the card it "asks the player in questions for that grant ... and opens no package that cannot validate"), and writes `package_uid: null` for both (the card's schema says "or null"). Both become `implemented` with `package_uid = P1` (`room_proposals.judge_proposal` 347-351): B is settled as built although nothing implements it, leaves the status row, and the grant question tied to it lapses. The single-proposal test (`tests/test_dramaturge.py:183-210`) pins the one case where the default is right.
- **Fix:** default only when exactly one proposal is accepted without a uid AND exactly one package was published; otherwise leave it `accepted`. **Test:** two accepted verdicts with null uids, one published package; assert the second stays `accepted`.

### F5 — Verdicts (and questions) are last-list-wins across steps and passes, not merged by key

- **Severity:** CORRUPTION (proposal ledger). **Confidence:** PLAUSIBLE.
- **Where:** `agents/story_planner.py:1442-1443` (`verdicts = [v for v in out["verdicts"] ...]` per step), `1697` (`"verdicts": this["verdicts"] or out["verdicts"]` per pass), `1439` (questions).
- **Failure scenario:** the card's single OUTPUT schema carries `"verdicts": [...]` in every answer. A model that judges A at step 3 and, on a later tool-only step, writes `"verdicts": []` (or only B's) wipes A's verdict; A stays pending, round 2 runs another `_run_task` for it, and at the end `deliberate` RETURNS it to the player as a disagreement ("The room could not agree on a direction") although the Planner accepted and may have built it. Questions behave the same within a reply (the progress write puts a question on the row; a later `"questions": []` removes it). This is the "models split keyed answers ... merge by key" and "an empty field is not a no" classes from the owner's notes.
- **Fix:** merge verdicts by `proposal_uid` across steps and passes (a later verdict for the same uid wins); treat a present-but-empty list as "said nothing". **Test:** scripted planner answering A at step 1, `"verdicts": []` at step 2; assert A is judged.

### F6 — The narrator crashes for twelve turns after a narrator step is hand-edited into a non-object

- **Severity:** CRASH. **Confidence:** CONFIRMED (snippet).
- **Where:** `agents/narration.py:1723` (`_past_narration_block`) and `1780` (`_past_narration_extra_block`).
- **Code:** `prose = (json.loads(r["content"]) or {}).get("prose") or ""` inside `except (TypeError, ValueError)`.
- **Reproduced:** content `"a hand-edited page"` or `[1,2]` -> **uncaught AttributeError**; `null` -> fine. `persist/steps.active_mapping` (70-87) documents that `/api/steps/{sid}/edit` "stores whatever the request body holds, with no shape check, so a hand-edited step legitimately holds a list, a string or null", and B23 fixed the same read in the Dramaturge (`dramaturge.player_visible_stream` uses `active_content` + `isinstance`). Narration kept its own SQL and `.get`. Every narrator (and `narrator_extra`) call whose history window (`narrator_history_turns`, default 12) includes that turn raises, so the beat fails until the edited turn ages out.
- **Fix:** read through `persist.steps` (`active_mapping` semantics: a non-mapping answers `{}`), or `isinstance(parsed, dict)` before `.get`. **Test:** store a narrator variant whose content is a JSON string; run `_past_narration_block`; assert no raise.

### F7 — The page's identity scrub fails OPEN

- **Severity:** LEAK. **Confidence:** PLAUSIBLE (needs an exception in perception's roster readers).
- **Where:** `agents/narration.py:559-569`.
- **Code:**
  ```python
  except Exception as exc:
      ctx.add_warning(f"narrator: the page's identity roster failed ({exc}); "
                      "the Director's words about the player went as written")
      return lambda text: text
  ```
- **Failure scenario:** `_identity_roster` or `_charter_titles_of` raises (a malformed registry entry, a persona shape). The scrub becomes the identity function for exactly the three fields its docstring exists to protect — `player_declared` (targets, onset, action), the player's acts in `current_events`, `spatial_frame.turned` — so the Director's canonical bindings ("Goddricey took up the mooring line", the measured Saltmarsh case in the docstring) reach the page for a stranger the player never heard named. The same module's `_player_perceives` (1187) states the opposite policy: "Fails CLOSED ... a thin beat is a worse page, a leaked act is a broken firewall."
- **Fix:** on failure, fail closed: drop the Director-written act surfaces (`onset`, `action`, `targets`, `turned.look(s)`) and keep the player's own `current_narration`. **Test:** monkeypatch `perception._identity_roster` to raise; assert no canonical stranger name in `player_declared`/`current_events`.

### F8 — `fit_result` erases the whole `inspect_charters` overview past 12,000 characters, under a message saying nothing is truncated

- **Severity:** SILENT-NOOP (the authoring tool answers nothing, confidently). **Confidence:** CONFIRMED (snippet).
- **Where:** `story/room_tools.py:1721-1783` (`fit_result`) with `657-664` (the overview's shape: `charters` is a DICT, `sections` the only top-level list).
- **Reproduced:** a 12-institution overview of 14,668 characters ->
  `kept keys ['dropped','paging','rows_per_page','sections','truncated'] dropped 6 chars 188` — five drops empty `sections`, the sixth deletes `charters`. The Room receives `{"sections": [], "paging": "every section is paged, never truncated ...", "truncated": true, "dropped": 6}`. The `fit_result` docstring's own measurement ("`inspect_charters` fell from 30,988 characters in 6 drops", chat 114) is exactly this outcome: on the bench copy the no-argument call returned no institution. `tests/test_charter_ops.py:276-287` knows the hazard ("an overview over the cap would lose every charter at once") but tests two institutions. This is the caravanserai failure the tool was rebuilt to prevent (the Room inventing staff it could not see).
- **Fix:** `fit_result` descends into a dict-valued key (trim its largest member's lists, then drop whole members with a count) before dropping a top-level key; or `inspect_charters` shrinks `rows_per_page` until the overview fits. **Test:** 12 synthetic charters; assert `out["charters"]` is non-empty and every dropped one is named.

### F9 — A clock whose due is unreadable validates clean and never fires

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (snippet).
- **Where:** `story/plot_packages.py:3774-3777` (`_package_checks` tests only `is None`), `4256-4281` (`_clock_due` swallows the `int()`/`float()` failure).
- **Reproduced:** clocks `{'due_turns': 'three'}` and `{'due_story_hours': 'at dawn'}` with an op riding one: `_package_checks` -> `errors: [] warnings: []`; `_clock_due(..., turn 500, elapsed 1e9)` -> `False` for both. Every operation on that fuse is silently never landed — the exact silence D15 ruled out for triggers ("A CLOCK THAT WILL NEVER TICK SAYS SO"). Sibling: `_normalize_entry` (160-184) keeps free keys, so an authored draft clock carrying `fired_turn`, `refused_turn`, `filled` or `ticked_turn_idx` (engine-owned state) is accepted — `fired_turn: 0` makes a clock that never fires, `filled: N` one that fires at once.
- **Fix:** in `_package_checks`, error when `due_turns`/`due_story_hours` is present and not a finite number ≥ 0; strip the engine-owned keys from authored clocks in `edit_package`. **Test:** the snippet above as a test.

### F10 — The Dramaturge's `revise` reads an unreadable answer as a withdrawal

- **Severity:** SILENT-NOOP (a suggestion dropped by a parse failure, recorded as the author's choice). **Confidence:** CONFIRMED (read).
- **Where:** `agents/dramaturge.py:451-462`.
- **Code:** `out = _call(...)` (`jparse` returns `{"text": raw}` for garbage) ... `if not revision: row = settle_proposal(cid, frame_id, proposal["uid"], "withdrawn", ...)`.
- **Failure scenario:** the revise call is cut off at the token ceiling or answers in prose; `out` has neither `revision` nor `withdraw`; the proposal is settled `withdrawn` and `deliberate` reports it withdrawn. `propose` in the same module treats an answer with none of `ANSWER_KEYS` as a cut-off (CUT_OFF_NOTE) — `revise` does not. (The reader side is UNBUILT_PIPELINE §1.214; the consumer turning absence into a decision is not registered.)
- **Fix:** an answer carrying none of `revision`/`withdraw` leaves the proposal as it stands (it is judged again at its bound). **Test:** scripted dramaturge returning `"not json"` to `revise`; assert status stays `revised`.

### F11 — `presimulate.charters` is accepted, previewed and ignored; the presim runs without its scene

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (charters ignored); PLAUSIBLE (missing `scene`/`story_day`).
- **Where:** `story/plot_packages.py:2474-2513`.
- **Detail:** `_shape_presimulate` stores `charters`; `_preview_presimulate` reports `"charters": op["charters"] or sorted(items)` to the author; `_prepare_presimulate` calls `presim_registry(registry, horizon_hours=..., active_tail_hours=0.0, tail_places=(), seed=...)` — no charter filter (the function has none), so EVERY institution is lived forward. It also passes no `scene`/`story_day`, which `presim_registry`'s docstring (`world/charter_runtime.py:1400-1420`) calls "the missing argument" (without it "every one of the 720 hours was a teleport") — harmless only for institutions that already carry a scene stamp.
- **Fix:** filter the registry to the named charters (or refuse the field); pass the scene and the story day as the launch does. **Test:** presimulate naming one of two charters; assert the other's `clock_hours` is unchanged.

### F12 — Package `scope` is stored and advertised, and nothing reads it

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (grep: no reader outside `normalize_package`).
- **Where:** `story/plot_packages.py:270, 286-290`; `story/room_tools.py` `new_package` description ("a scope (locations, earliest/latest time)") and `edit_package` (lists `scope`).
- **Failure scenario:** the Room sets `scope.latest_time` expecting a package to lapse, or `scope.locations` expecting it to bind; nothing validates, normalises (`earliest_time`/`latest_time` are stored raw, any type) or acts on either.
- **Fix:** drop the field from the tool text (or give it a reader: a `latest_time` that retires). **Test:** n/a for removal; a lint that every documented package field has a reader.

### F13 — Narrator payload fields no sheet teaches, and a dead `correction_notes` channel that still ships in Japanese

- **Severity:** SILENT-NOOP / DEAD. **Confidence:** CONFIRMED (grep of both packs).
- **Where:** `agents/narration.py:2152-2156` (`_generate_narration(..., correction_notes=None)` — no caller passes it; `tools/` does not call `_generate_narration`); payload keys built at 2743-2815; `language_packs/en/.../narrator.txt:110-112` (`[[when: correction_notes]]`), `language_packs/ja/.../narrator.txt:89` (the same paragraph, UNMARKED).
- **Detail:** counts of each payload key's name in the sheets (en/ja): `long_established` 0/0, `rhythm_report` 0/0, `register` 0/0 (en's single hit is the word in another sentence), `scene_opening` 0/0, `variant_seed` 0/0. `long_established` (D7), `rhythm_report` (D11) and `register` (D10) all arrived in `cb5a6675` with no sheet change, so the model must guess what an opaque `{detail, unmentioned_for, established_for}` list is for (`private_voice_setting`'s absence is deliberate, AGENTS.md:466). The correction pass was removed 2026-09-06; in English its section is never emitted (dead text), in Japanese the CORRECTION NOTES paragraph ships on EVERY beat describing a field that never arrives — the "rule with no referent" AGENTS.md warns about.
- **Fix:** delete the parameter and both sections; add a `[[when: long_established]]`/`[[when: rhythm_report]]`/`[[when: register]]` clause each (en+ja) or stop sending the field. **Test:** a guard that every non-core payload key the narrator can emit is named by some section of each pack's sheet.

### F14 — `due_turns` counts chat-global turn indices, so a live bubble's beats bring a player-frame clock due early

- **Severity:** WRONG-SCENE. **Confidence:** PLAUSIBLE.
- **Where:** `story/plot_packages.py:384-394` (`_latest_turn_idx(cid, frame_id)` ignores `frame_id`: `SELECT MAX(idx) FROM turns WHERE chat_id=?`), `4267-4271` (`published_turn + due_turns <= turn_idx`), called with `ctx.turn.idx` (`commit.py:815`).
- **Failure scenario:** a package published at chat-wide idx 100 rides `due_turns: 3`. A causality bubble plays offscreen beats 101-104 in its own frame; the player's next beat is idx 105 and the clock fires after ONE beat of the player's story. `room_frontier.frame_turn_idx`/`_other_frames_beats` (645-660) exist precisely because "a live causality bubble inserts its own beats into that numbering"; the clocks were not given the same correction.
- **Fix:** count the frame's own beats since publish (as `_other_frames_beats` does) and pin `published_turn` with `frame_turn_idx`. **Test:** insert other-frame turn rows between publish and fire; assert not due.

### F15 — English sentences in the narrator payload, and an English section in the Japanese narrator sheet

- **Severity:** WRONG-SCENE (language-pack hazard). **Confidence:** CONFIRMED (read; the JA paragraph found by script).
- **Where:** `agents/narration.py:636-656` (`_standing_substance_clauses`: "your {interior} still holds {material}", "{material} on your {part}", "released from your {part}"), `940-1000` (`_sensory_channels_manifest`: "%s %s falling on you", "%s on your skin", "no light reaches this room", "dim light -- shapes, not detail", "nothing is in contact with your body this beat", "open air; nothing ledgered rides this channel", "your own body, always", "light: %s"), `1650-1653` (portal keys "door to {to_name}", "doors", "{name} hatch"), `3014` (`narrator_extra`'s fallback view "Nothing in particular reaches you this beat." where `narrator` uses `compositor_text("narrator_nothing", ...)`), `1598-1599` (door-like entities recognised by the English words door/gate/hatch/portal/shutter, so the guess never fires for a Japanese entity name); `language_packs/ja/cards/system_prompts/prompts/narrator.txt:105-107` (DIALOGUE PLACEHOLDERS, verbatim English, shipped whenever `dialogue_lines` is present); `_craft_tells` (`narration.py:332`) masks only `"` and curly quotes, not 「」, although `_quote_marks()` in the same module reads the packs' marks.
- **Why it matters:** the module's own `_event_line` docstring records the measured cost of exactly this — markers reaching "a Japanese story in English, inside an otherwise Japanese sheet" — and the sensory manifest is the field the sheet calls authoritative ("its why is a fact of the scene"). `tests/test_language_pack_integrity.py` checks protocol tokens only, so an untranslated paragraph passes.
- **Fix:** move these strings to `linguistics.json`/compositor templates beside `_EVENT_LINES`; translate the JA section. **Test:** a pack test that no non-schema paragraph of a non-English card is mostly ASCII letters.

### F16 — The Room's tool table, operation shapes, citation contract and authored-event summaries are English in every story

- **Severity:** WRONG-SCENE (language). **Confidence:** CONFIRMED (read); impact on reply language unmeasured.
- **Where:** `story/room_tools.py` `TOOLS` descriptions (the table is now 38,731 characters, measured); `story/plot_packages.py:3299-3468` (`OPERATION_FIELDS`), preview errors/warnings throughout; `story/room_citations.CONTRACT_TEXT` (via `story_planner._contract_block`); `story_planner._manifest` (the charter_planner tool); `agents/dramaturge.py` `DIAL_SCALE`, `CUT_OFF_NOTE`; `_mint_notice` summaries handed to the Director as circumstances (`plot_packages.py:2682` "%s arrives at %s, carrying ...", `2917` "%s is summoned to %s by the %s", `2947` " (at %s)").
- **Detail:** `llm/prompts.py`'s module rule is "Authored human-language text belongs to language_packs/<id>". A Japanese story's Room reads a Japanese card beside ~45k characters of English, and the Director of a Japanese story is handed English event summaries to render.
- **Fix:** move tool descriptions and field texts into the pack (`room_tools` keeps names/schemas); render `_mint_notice` from a compositor template. **Test:** as F15.

### F17 — The smell channel says "open air" in every room

- **Severity:** WRONG-SCENE. **Confidence:** PLAUSIBLE.
- **Where:** `agents/narration.py:993-994`: `"smell": ("live", "open air; nothing ledgered rides this channel" if not by_channel.get("smell") else "")`.
- **Failure scenario:** a sealed cell, a submarine, a cellar: the manifest's `why` — which the SENSORY CHANNELS section tells the model is "a fact of the scene" and licenses "the smell a listed ... weather would carry" — asserts open air. The string came in with the manifest (`b2d04429`); `weather_for_room` (read at line ~940 for the touch and hearing rows) returns the room's `exposure`, which the smell row never consults (and returns `{}` for a story with no weather, where `world.weather.exposure_at`/`room_exposure` still answers).
- **Fix:** derive the clause from the exposure the engine holds, or say only "nothing ledgered rides this channel". **Test:** enclosed room -> the smell `why` contains no "open air".

### F18 — Door states from entities and hatches in the player's own room ignore light; the edge branch does not

- **Severity:** LEAK (low). **Confidence:** PLAUSIBLE.
- **Where:** `agents/narration.py:1563-1610` (`_visible_portal_states`, entity `link`, `transit.hatch` and door-word branches gated on `room_id`/`visible_rooms`, which always contains the player's room) versus the edge branch (1636-1653, gated on the target room being in `visible_adjacent_rooms`, which consults the far room's light — reproduced: an open door to a dark hall reports nothing, to a lit hall reports "open").
- **Failure scenario:** the player sits in a pitch-dark storeroom; another body silently opens the "cabinet door" (or a lift hatch while the player is inside the car). The narrator payload carries `"cabinet door": "open"` under a sheet rule that says the prose "MUST match it" and describes these as states "the player can currently see". No sound or touch delivered it.
- **Fix:** gate the entity/hatch branches on the player's own sight of their room (`effective_light`/sense card), as `_player_sees_character` does. **Test:** dark room + door-like entity state change -> `portal_states` omits it.

### F19 — The interactive Room reply runs with the rewind guard off, while its comment says the guard covers that thread

- **Severity:** STALE-DOC (with a narrow logic gap). **Confidence:** CONFIRMED.
- **Where:** `agents/story_planner.py:1341-1342` ("this loop runs in `converse_stream`'s daemon thread against no lock, which is why `story_rewound_past` is checked below"), `1502-1503` (`if base_turn is not None and _is_write(name) ...`), `2212` (`_planner_reply` calls `run_planner(..., regime="reply")` with no `base_turn`); `story/room_conversation.converse_stream` computes `turn_idx` and does not pass it.
- **Detail:** the only production `reply` caller never has a base turn, so the check never runs on the thread the comment names. The same function's A33 comment (2216-2226) explains that `None` "is the guard switched off" and fixes it for the Dramaturge job it queues, not for its own `run_planner` call. The practical damage is bounded: `publish_package` re-validates when history moved (rebase/conflict), so a publish onto a rewound story lands only if it still validates; drafts, grants and the status row land regardless.
- **Fix:** pass `base_turn=room.current_turn_idx(cid)` from `_planner_reply` (or correct the comment). **Test:** reroll under a scripted reply; assert the publish is refused "rewound".

### F20 — The narrator's warning disposition is documented as it was before 2026-09-06

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- **Where / what:**
  - `agents/narration.py:2879-2881`: "ctx.warnings is accumulated pipeline-wide but never surfaced anywhere (not streamed, not persisted, not logged)". False since `StepTaggedWarnings`: `runtime._with_engine_notes` (`agents/runtime.py:521-545`) persists each step's warnings on its saved content and the pipeline drawer shows them. (Consequence: every fidelity warning is now stored twice on the narrator variant, under `fidelity_warnings` and the engine notes.)
  - `narration.py:75`: "live checks use `_ling(...)`" — no live code reads the partition at all; only `tools/narrator_sheet_bench.py:712-713`.
  - `narration.py:322-337` (`_craft_tells` docstring): "would burn a pointless retry every turn" — there is no retry.
  - AGENTS.md:466 (Narration row): "An enforceable warning costs a rewrite, so only add one whose false-positive rate you have measured" — nothing costs a rewrite; and "[event_order] reaches the model as the rendered `current_events` package" — since E14 `current_events` is perception's packet (`_narrator_perception_fields`) with only the player's own acts taken from `event_order`; `_render_current_events` is bench-only (its own docstring says so).
  - UNBUILT_PIPELINE §1.82's premise ("neither buys a correction rewrite", "each enforceable firing costs a whole narrator call") — see "Already registered": the class is that EVERY narrator verdict is now warn-only.
- **Fix:** correct the comments and the AGENTS.md row; restate §1.82 as "no narrator check has a consumer; promotion would need a mechanism that no longer exists".

### F21 — The author-layer invariant is stated without the two mind-facing channels the Room now writes

- **Severity:** STALE-DOC (firewall documentation). **Confidence:** CONFIRMED.
- **Where:** `story/plot_packages.py:45-47` ("There is no operation that writes `chat_chars.state`, a memory row, a perception view, a relationship or a character's knowledge"), AGENTS.md:449 ("no kind writes a mind, a memory, a relationship or a view").
- **Detail:** `plan_entity.known_by` writes the recognition ledger `known` both ways at publish (`_seed_prior_ties`, 1751-1785, owner ruling 2026-10-07), and a truth's `known_by` reaches named minds' private knowledge from the next beat (`truths_known_by`, 4388-4423, owner ruling 2026-10-10). Both are sanctioned; the invariant text a firewall reviewer reads denies both exist.
- **Fix:** name the two ruled channels in both places.

### F22 — Assorted stale comments and docs in the Room

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
  - `agents/story_planner.py:136` "Raised to 20k on the owner's ruling" above `PLANNER_MAX_TOKENS = 40_000` (143).
  - `agents/story_planner.py:3357` `schedule_room_work` "Never raises": `frontier_report` (3383), `spend_limits`, `fill_due`, `pass_due`, `schedule_fold` are unguarded; the caller (`commit.py:773-779`) catches, but one failure in the frontier also skips that commit's Dramaturge pacing, follow-up and fold.
  - `llm/prompts.py:103` "The one surviving eager English fragment, and it is read (story/importers.py)": `EXTRA_PARTS_NOTE` and `extra_parts_note()` have no production reader (only `tests/test_extra_parts_authoring.py:57`).
  - `llm/prompts.py:682-683` "A sheet with no markers ... which is what the Japanese pack is until it adopts them": the JA sheet has one marker pair (`dialogue_lines`), so every OTHER section ships on every Japanese beat.
  - `docs/design/DESIGN_ROOM_PRELUDE.md` §2: a `ground` regime of "10 steps / 180s" (the code has `location`, `LOCATION_STEPS = 40`, `LOCATION_WALL_SECONDS = 900`) and "`spend_limits` returns its default 60 calls per reply" (`mandates.CALLS_PER_REPLY = None`).
  - AGENTS.md:450 "Sixteen read tools" (17 carry `reads: True`; `inspect_config` is the uncounted one).
  - Design.md:411 "`tests/test_room_is_captured.py` (11 tests)" (19 now).
  - `agents/story_planner.py:38-47` (module docstring, TWO REGIMES): "What actually stops a reply is ... the SPEND the player granted" and a background task "RESUMES ... until spend stops it" — with `CALLS_PER_REPLY`/`CALLS_PER_STORY_HOUR` = None by the owner's 2026-10-01/03 rulings, spend stops nothing unless a grant states a number; the walls, the step/call ceilings and `TASK_PASSES_CAP` are the stop. (UNBUILT_PLANNING §2.26's "`calls_per_reply` default 60 / ceiling 200, `calls_per_hour` default 240 / ceiling 1200" is stale for the same reason.)

### F23 — Dead code and two-lists-of-one-thing

- **Severity:** DEAD. **Confidence:** CONFIRMED (grep across repo incl. tests/tools).
  - `story/plot_packages.py:3276` `CLOCK_ONLY_KINDS` — no reader; `_shape_scheduled_consequence` enforces the rule itself.
  - `story/plot_packages.py:3757-3761` `truths_with_evidence` built, never read.
  - `story/plot_packages.py:3144-3149` (`_apply_region_event`): `if <due> and not done:` and `elif <due>:` do the same thing; the docstring's "The first wave lands now" is not what the code does when several waves are due.
  - `llm/prompts.py:107, 209` `EXTRA_PARTS_NOTE` / `extra_parts_note()` — test-only.
  - `story/plot_packages.py:384` `_latest_turn_idx(cid, frame_id)` — `frame_id` accepted and ignored (see F14).
  - `agents/narration.py:2152` `correction_notes` parameter (F13).
  - Two lists of one thing: `agents/dramaturge.py:267` literal `"kinds"` duplicates `room_proposals.PROPOSAL_KINDS`; `story_planner._is_write` (1181-1184: publish/prepare only) vs `room_tools.tool_only_reads` — two answers to "does this tool write", disagreeing on every drafting tool; `plot_packages.operation_shape_text` (3588-3596) re-implements `operation_shape_line`'s join.
  - Fields read but not declared to the model: `post_artifact` takes `clock` (`_shape_post_artifact` 1848, comment "left when the package's clock fires") but `OPERATION_FIELDS["post_artifact"]` lists no `clock?`; `plan_entity.surface` is read (1357) and undeclared.

### F24 — `inspect_events` is not frame-scoped

- **Severity:** WRONG-SCENE (the author's read). **Confidence:** CONFIRMED (read).
- **Where:** `story/room_tools.py:673-690`: `events e ... WHERE e.chat_id=?` and `scheduled_events WHERE chat_id=? AND status='pending'` — no frame filter (`events` has no frame column; it joins `turns`).
- **Failure scenario:** in a multi-era or bubbled story the Room reads another frame's beats and pending events as "the most recent objective beats" of the frame it is planning, while every other Room read (`packages`, `frontier`, `world_event_kinds`) is frame-scoped. (UNBUILT_PLANNING §2.26 registers that this tool reads the omniscient `events` row "by design" — omniscience, not the cross-frame mix, which is what this finding is about.)
- **Fix:** `JOIN turns t ON t.id=e.turn_id AND t.frame_id IS ?`.

## Efficiency

### E1 — The Room's per-step payload is ordered against provider prefix caching (largest, cheapest)

- **Where:** `agents/story_planner.py:718-825` (`_payload`; the dict literal at 775). Insertion order (= wire order, `room_call` sends `json.dumps(payload)`): story, clock, minds, conversation, mandates, withdrawn, capabilities, limits, **status**, frontier, packages, pending_proposals, **transcript**, **budget**, then unbacked_claims, **player_says**, **task**, free_hand.
- **Hotness:** every step of every Room reply/pass (up to 40 steps; 24 for the opening; 40 for a location design; tasks resume up to 12 passes). `budget` changes every step (`seconds_left`, `calls_left`, `step`); in the reply regime `status` is rewritten on every step that carries a `status_line` (1454-1463) and the memo re-derives it. So the cacheable prefix of the user message ends at `status` or `budget`: the transcript (≤96k chars) is re-billed uncached every step, and the STATIC `task` and `player_says`, which sit after `budget`, are never cacheable — a location task is lore (≤24k) + the plan spec (8,648 chars, measured) + the brief (≤4k); an opening task carries the passage up to 96k chars (`PLANNER_TRANSCRIPT_CHARS` reused as its cap).
- **Fix:** static first (story, capabilities, limits, task, player_says, minds, conversation), then the append-only transcript, then the volatile keys (clock, mandates, withdrawn, status, frontier, packages, pending_proposals, unbacked_claims, free_hand, budget). No information changes.
- **Gain:** where the route caches prefixes (OpenRouter/DeepSeek automatic caching; GLM only with the replica hint, per the owner's notes), most of the per-step input becomes cached input: ~40k static characters × up to 40 steps per location design, plus the transcript's unchanged prefix on every step. Measure from the per-call `cached` counts the engine already records (`llm_calls` engine notes / room capture) on a replay of chat 165's lines.

### E2 — With spend uncapped (the owner's ruling), the passes cap is what bounds a background Room task, and spend never sees model calls

- **Where:** `story/mandates.py:163,171` (`CALLS_PER_REPLY = None`, `CALLS_PER_STORY_HOUR = None`), `agents/story_planner.py:87,307,1672-1699` (`TASK_PASSES_CAP = 12`, `RESUMABLE_STOPS`).
- **Detail:** spend defaults were removed on the owner's word (`mandates.py:155-171`: "the writers room spend limits are making it basically useless", "raise to infinity"), so this is NOT a proposal to cap anything. What it leaves: a fill or deliberation that ends each pass on `steps` (the re-reading loop the owner's notes describe) resumes up to 12 passes × 40 steps = 480 model calls (~2 h of 600 s passes), each re-sending the payload of E1, and that ceiling — not spend — is what bounds a runaway. A grant's own number, when a player states one, counts TOOL calls (`record_spend(calls=calls_made)`), never model calls, and a Dramaturge pass records spend only for its lore lookups (`_dramaturge_pass`: `if out["calls"]: record_spend(...)`), so even a stated allowance does not see the dominant cost. The docs still describe spend as the stop (F22). Worth naming to the owner; E1 is the cheaper lever.

### E3 — Prompt presets are re-read and re-parsed per prompt piece

- **Where:** `llm/prompts.py:144-155` (`presets()`: `json.loads(get_setting("prompt_presets"))` + `normalize_preset` of every preset), `213-234` (`_preset_override` calls it), `500-505` (`_encoder_pieces.piece()` calls `_preset_override` once per piece: core, stage piece, each granted channel and each part), plus `nsfw_overlay` -> `nsfw_enabled()` (a settings query) twice per hand (`529-530`). `get_setting` is an uncached query (`core/db.py:2982`).
- **Hotness:** every encoder sheet assembly (interpret, resolve, repairs; `encoder_sheet_additions` assembles two sheets). With the Default preset the cost is one query per piece (negligible); with a stored preset each piece parses the whole presets blob (every preset's full prompt bodies).
- **Fix:** resolve the active preset once per assembly (or cache by a settings write counter). **Gain:** proportional to preset size × pieces (tens of parses per beat when a preset is active).

### E4 — `_shown_transcript` re-encodes every entry on every trim iteration

- **Where:** `agents/story_planner.py:663-677`: `candidates = [i for i in kept if ... len(_encoded(entries[i].get("result"))) > PLANNER_TRIM_HEAD_CHARS]` is rebuilt (re-serialising each kept result) on every loop iteration, so trimming is O(entries × trims) JSON encodes per step (≤200 entries, results ≤12k chars).
- **Fix:** compute each entry's result length once (as `sizes` already does for the entry) and update it on `_trim`. **Gain:** CPU only (small beside model latency); cheap.

### E5 — The Japanese narrator sheet ships all of its conditional sections every beat

- **Where:** `language_packs/ja/cards/system_prompts/prompts/narrator.txt` (one marker pair) with `llm/prompts.narrator_prompt` (699-713).
- **Measured:** bare-beat sheet en 16,553 characters (of a 28,130 body: 11 conditional sections, 12,792 characters, cut when absent) vs ja 20,841 of 21,731 (only `dialogue_lines` is ever cut). Adopting the en markers saves the conditional share on ordinary Japanese beats and removes the dead CORRECTION NOTES paragraph (F13).

### E6 — `narrator_extra` rebuilds one seat's identity floor four times

- **Where:** `agents/narration.py:3043-3123`: `_extra_view_label` is called four times per seat; each call re-reads `known` (`wget`) and re-normalises every cast card (`normalized_character_of_row`). Build it once per seat and reuse. Per extra seat per beat; small.

## Already registered

- **The Room's scene writes (`set_far_looks`, `set_vistas`) can be lost to a beat's commit that prepared its scene before the publish landed:** UNBUILT_WORLD §2.40 ("A look written at publish can be lost to a beat's commit that prepared its scene before the publish landed, as `set_vistas`' can"). Confirmed by trace here: `_apply_set_vistas`/`_apply_set_far_looks` `wset` the scene from a Room thread (`story/plot_packages.py:2184`, `2392`) while `persist/commit.py:471` reads it before the write lock and `persist/commit_scene_state.py:2984` writes it back whole; `commit.py:833-837` and PIPELINE.md:1395 state the same class for promotions. The register frames it as looks/vistas; a `region_event` wave at publish writes `world_conditions`, artifacts, the registries and `engine_notices` rather than the scene (whether the commit rewrites `engine_notices` from a pre-lock read was not checked here).
- **`narrator_extra` lacks the consciousness gate and fidelity facts** (`spatial_frame` unconditional at `narration.py:3119-3123`, no `player_awareness` key, `_generate_narration` without `fidelity_facts`): UNBUILT_PLATFORM §3.4, S3-A6.
- **An extra player has no opening turn** (`narrator_extra` reads `establish_views["extra:<pid>"]`, which nothing writes): UNBUILT_PLATFORM §1.62.
- **Two narrator checks that fire and buy nothing:** UNBUILT_PIPELINE §1.82. *The class:* since 2026-09-06 every narrator reading is warn-only — `_check_narrator_fidelity`'s verdicts, `_craft_tells`, the `repeated_closer` report, `_report_prose_guards`' four echo/dedupe/cap readings, the omitted-placeholder and stray-token warnings — appended to `ctx.warnings` (persisted per step) and `out["fidelity_warnings"]`, with no production reader (grep: none outside narration; `new_specifics` is the one field commit reads, as a warning). The only mutations are mechanical: the `{{Ln}}` weld (`_substitute_dialogue_tokens`), the stray-token strip, and the `text`/`prose` alias. `_ENFORCEABLE_PREFIXES` partitions warnings for `tools/narrator_sheet_bench.py` alone (also recorded in `docs/experiments/AUDIT_RUNTIME.md` §16, not an UNBUILT register). So §1.82's two checks are not special; the register's premise (an enforceable firing costs a narrator call) is stale — see F20.
- **The Room reads a whole answer with plain `json.loads` (`jparse`), with no cut-off guard outside the ladder:** UNBUILT_PIPELINE §1.214. In these files the Room's readers are `story_planner._call` (`jparse` then `_native_answer`), `dramaturge._call` (`jparse`), `story_planner._native_value` (`json.loads` then `jparse`). F10 is a consumer of that reader turning its fallback into a decision.
- **`spatial_digest` renders the authored room name behind every edge** (reaches the narrator's `spatial_frame`): UNBUILT_PERCEPTION §3.3, F6/S3-A5 residual.
- **A door exists twice (entity vs edge) in `_visible_portal_states`:** UNBUILT_WORLD §1.143 (the door-word guess list is named there; its English-only reach is F15).
- **A floor word outside the sound tables reads as masonry** (`_plan_geometry` keeps 20 free characters; `OPERATION_FIELDS` names three of the eight table words): UNBUILT_WORLD §1.209.
- **The knowledge-tag door is the widest lore-to-mind channel** (the Room's `file_lore` with `knowledge_tag`/`knowledge_range: global` is one of its writers): UNBUILT_PLATFORM §3.5, P6.
- **A quoted line under four characters is neither scored nor tokenised** (affects `_dialogue_tokens` / `dialogue_lines`): UNBUILT_PERCEPTION §1.109, first half open.

## Structure notes

- **Monoliths in miniature:** `narration.narrator` (2347-2897, ~550 lines: payload assembly, world fields, generation, reporting); `narration.narrator_extra` (2970-3196) re-implements the same assembly per seat and has drifted (S3-A6, F15's fallback string, E6) — the natural seam is one `_seat_payload(ctx, seat)` both call; `_sensory_channels_manifest` (783-1023), `_ordered_beat_events` (1147-1396). `story_planner.run_planner` (1241-1651, ~410 lines: budget/regime setup, step loop, call execution with echo policy, stop/reply assembly, final status write) — seams: the call executor (1468-1586) and the transcript compaction (`_shown_transcript`, `_receipt`, `_echo_items`, which could be `story/room_transcript.py`); `deliberate` (2276-2437); `run_fill` (3118-3286). `plot_packages.py` (4571 lines) splits naturally by operation family (plan_rooms 781-1295; plan_entity/creature 1300-1831; far looks 2190-2406; local drama + nudges 2516-3176), lifecycle (420-560, 3929-4148), clocks (4167-4385) and checks (3604-3926).
- **Deferred imports in `plot_packages.py`:** 108 function-local imports over 28 modules. Verified in a fresh interpreter per module: none of the 28 imports `story.plot_packages` (or `story.room_tools`, its only module-level importer) at import time, so none exists to break a cycle today; `world.spatial` (9 local imports) is already imported at module level (line ~3290) and `core.db` (15) is a base module. If they are kept for import-time laziness that is a different argument and should say so.
- **Module-level mutable state:** `narration._QUOTE_MARKS_CACHE` (global, written once by `_quote_marks`, never invalidated when a pack installs at runtime). `llm/prompts._ENGLISH`, `DEFAULT_PROMPTS`, `EXTRA_PARTS_NOTE` computed at import (reads the English pack); `_PAYLOAD_LEGACY_ARMS` reads the environment at import. `room_tools.TOOLS` builds the `draft_operation` description at import (`operation_shape_text()` imports `world.charter_surgery`/`world.region_events`). `plot_packages` tables (`OPERATIONS`, `OPERATION_FIELDS`, `SURGERY_FIELDS`, `ROOM_FIELDS`, `NEED_FIELDS`, `AUTHORITY_CAPABILITY`, `_LOOK_KEPT`, `_LIST_FIELDS`) have no writer after import.
- **Two persistence boundaries:** the Room writes the world only through `publish_package` (its own short `transaction()`, AGENTS.md's documented author seam) and through `fire_due_clocks` (no transaction, F1), never through `persist/commit.py`. Beside packages the planner writes author bookkeeping directly (status row, mandates, spend, room messages, bible notes, proposals) — frame-scoped world rows, not world state. The location designer writes `location_design` rows; its plan is planted by `generate_lived_location` in the launch.
- **`OPERATIONS` vs `OPERATION_FIELDS` vs `SURGERY_FIELDS`:** keys agree (27/27/6, snippet); declared vs read fields differ only as F23 lists (plus helper-read fields that a static scan misses: `_plan_sources`, `normalize_region_event`).

## Docs checked

- CLAUDE.md "The Narrator renders only the player-facing slice and cannot ... reveal unperceived facts": holds for every payload field traced (`player_declared` is the player's own rows scrubbed by the page floor; `current_events`/`present_scene`/`changes_noticed` are byte-contained in the view; `co_present_positions` is sight-gated; `cast_pronouns`/`authored_body_parts` are keyed by the roster rule; `long_established` is the player's own ledger; background acts reach `_fidelity_facts` only), with the exceptions F7 (fail-open scrub) and F18 (entity/hatch door states in the dark); `narrator_extra` per S3-A6.
- CLAUDE.md "Narrator ... cannot originate new player conduct": holds structurally (`_narrator_player_declared` keeps only the player's own rows, `_is_own_row`); enforcement on the prose is warn-only (see §1.82).
- AGENTS.md:466 (Narration): "An enforceable warning costs a rewrite" — fails; "`event_order` ... reaches the model as the rendered `current_events` package" — fails (F20); "the per-line markers ... are language-pack data" — holds for `_EVENT_LINES`; the manifest/substance/portal strings are not (F15).
- AGENTS.md:449 (plot packages): every named constant matches the code (`PACKAGES_CAP` 32, `RETIRED_KEPT` 16, `OPS_CAP` 64, `LIST_CAP` 48, `TEXT_CHARS` 1200, `HISTORY_CAP` 40, `PLAN_ROOMS_CAP` 200, `EVENT_DUE_CAP` 200, `PRESIM_HOURS_CAP` 720, `DIRECTOR_NOTE_CHARS` 600, `FAR_LOOKS_CAP` 200); "twenty-seven kinds" holds; "a kind outside the table is refused at draft time" holds (and `normalize_package` drops one silently on read); "publish is ONE short transaction" holds for publish, not for clock fires (F1); "no kind writes a mind, a memory, a relationship or a view" — stale (F21).
- AGENTS.md:450 (room tools): constants match; "Sixteen read tools" — 17 (F22); "ten write tools" — holds for the package tools (location and research tools are extra); "no module under agents/ but story_planner.py and dramaturge.py imports this module" — holds (grep); "Paged, never truncated" — fails past the result cap (F8).
- Design.md:398 (Dramaturge): `tests/test_dramaturge.py` (68) holds; `BEATS_PER_PROPOSAL` 6, `SURPRISE_DEFAULT` 2, `DIRECTION_NEAR_FLOOR` 0.5, `DIRECTION_WAIT_INTERVALS` 2 hold; "runs in every story on pacing alone" holds (`schedule_room_work` queues `run_dramaturge_pass` when `pass_due`, no grant). **What it writes:** proposals (`room_proposals.file_proposal`, frame-scoped `PROPOSALS_KEY`), its pass log (`record_pass`/`land_pass`/`give_back_pass`), spend (lore calls only), a thread line (role `dramaturge`), the status row (`write_status`), due marks (`mark_due`), and, through `revise`, revisions/withdrawals; it reads lore only (every other tool refused, `dramaturge.py:391-401`).
- Design.md:411: "(11 tests)" — 19 (F22).
- PIPELINE.md:1245-1251 ("The stage blocks on being parseable JSON and on nothing else"; `_ENFORCEABLE_PREFIXES` survives for the bench) — holds. PIPELINE.md:1395 (out-of-band tail; promotions' lost-update argument) — holds, and the same lost update reaches the Room's scene writes (registered, UNBUILT_WORLD §2.40; see Already registered).
- DESIGN_ROOM_PRELUDE.md §2 regime table and "default 60 calls per reply" — stale (F22); §4 ("the review is the real closure", four location tools, "a pass that submits nothing FAILS the generation") — holds against `run_location_plan`/`room_tools`; §4c (adopt a submitted design by digest, resume an unsubmitted draft) — holds (`_location_digest`, `submitted_for`, `resumable_draft`, `pause_draft`).
- DESIGN_STORY_PLANNER_AND_DRAMATURGE.md §5 package shape — conceptual, as it says; `scope` is carried but has no reader (F12); `knowledge_seeds` is not a package field (edit refuses it by name — explicit, fine).
- Owner rulings checked: "the Room designs locations" (location regime, four tools, no fallback — holds); "plans ahead / initiative never cut for tokens" (planting is the fill's standing work; the sketch tier hands off rather than cuts — holds; E1/E2 are cost notes, not cuts); "Dramaturge suggests by default" (holds); "the 600 s wall is what stops it" — the wall is checked at step start only (`story_planner.py:1357-1360`), so one step's model call plus up to 8 tools (a `prepare_package` running a 227-250 s location generation) can overrun it; the stream's outer wall is 900 s (`room_conversation.STREAM_WALL_SECONDS`) and a worker that outlives it keeps writing with its reply discarded.
