# Audit — agents/character.py, character_bare.py, character_tools.py, character_evidence.py, background.py (2026-11-01)

Read-only. Snippets ran on `.venv/bin/python` against a scratch `ENGINE_DB`
(`scratchpad/snip/probe.db`); the owner's `engine.db` was read only through
`sqlite3 file:engine.db?mode=ro`. One focused test file run
(`tests/test_scene_life.py`, 28 passed).

## Scope read

Read IN FULL, top to bottom:
- `agents/character.py` 1-5154 (every line, including all of `character_step` 3555-5154).
- `agents/character_bare.py` 1-1172.
- `agents/character_tools.py` 1-732.
- `agents/character_evidence.py` 1-146.
- `agents/background.py` 1-3257.

Read in part, to trace a finding (not audited):
- `persist/commit_background.py`: `overt_declaration` 1086-1133, `_background_name_mentioned` 1136-1160, `owed_service`/`owed_to` 1660-1733, `_thread_charters`/`_thread_peers` 3112-3145, recent-ring writer 3320-3340, `pick_background_reactors` 4141-4170.
- `agents/common.py`: merge tables + `_merge_character_results` 1150-1344, `_uncarded_person` 5434-5448, `observer_label_fn` 5517-5612.
- `agents/director_movement.py` 292-307, 600-730; `world/spatial_merge.py` 1433-1470; `world/spatial_geometry.py` `spatial_digest` 151-260; `world/spatial_identity.py` `room_of` 92-130.
- `mind/affect.py` 178-187, 1973-2100; `mind/affect_pass.py` 447-490; `mind/character_jev.py` 596-640, 680-700, 1016-1021; `mind/memory_context.py` 30-140, 790-840; `agents/impossible_knowledge.py` 91-164; `world/place_purpose.py` 227-272, 380-455; `world/charter_promote.py` 540-580; `story/character_schema.py` `name_boundary_pattern` 1813-1841; `core/db.py` `wget` 2993-2996; `core/pipeline_context.py` 540-560; `agents/skip_stage.py` 670-700, 1171-1216; `agents/loops.py` 1490-1510, 1860-1900.
- Language packs: `en/cards/system_prompts/prompts/character_bare.txt`, every `en/.../character_bare/*.txt` section name, `their_silence.txt`, `ways_on.txt`; `en`+`ja` `linguistics.json` tables for `agents.character` / `agents.background`.
- Docs: AGENTS.md rows 432/435, Design.md rows 353/530, `docs/guides/MEMORY.md` 250-330, the UNBUILT registers (grepped per finding).

Skimmed only (NOT audited): the rest of `persist/commit_background.py`, `agents/loops.py`, `agents/skip_stage.py`, `story/scene.py` (`dialogue_budget` head only).

## Findings

Severity counts (21 findings): LEAK 8 (F1-F8), WRONG-SCENE 7 (F9-F13, F19, F20), SILENT-NOOP 2 (F14, F15), STALE-DOC 1 (F16; F10 is also stale-doc), DEAD 2 (F17, F21 trivia), logic 1 (F18). Efficiency items: 6.

### F1 — A background voice is told the full name of every body that has no card (charter townspeople, Director-minted people, other presences)
- **Severity:** LEAK. **Confidence:** CONFIRMED (label behaviour by snippet; reach traced by reading).
- **Where:** `agents/background.py:2399-2438`, `_presence_label_fn.label`:
  ```python
  info = sheets.get(text)
  if info is None:
      return text         # not a body: an entity, a room, a prop
  ```
  `sheets` holds only cast cards and the persona. `agents/common.py:5589-5609` (`observer_label_fn`) has the branch this lacks — `_uncarded_person(_scene(), text)` then `_unknown_actor_label(...)` — added after "Emory" was handed "Master Leofelric Fenstonwell" (playerless Aldermill round 6). The presence floor never got it.
- **Reach:** `_beat_for_presence` → `_presence_line(label=)` (244-247) and `_presence_act` (307); `_manager_events` `speaker`/`intended_target` (1768-1771); `_thread_heard` `speaker`/`to` (2534-2536); `_voice_thread` `for` (2555); `_react_one` `addressed_by.speaker` (3113-3114). `_presence_line` swaps to the unseen-voice label only `if not can_see and shown != speaker` (245-246), so an UNSEEN uncarded speaker is named as well. `_presence_identity_floor` (333-378) builds its `unknown` list from cast + persona only, so act surfaces naming uncarded bodies pass unscrubbed too.
- **Scenario:** a charter body declared this beat (`declare_charter_figures`) speaks in a taproom; the barman (empty `known` row) is handed `Master Leofelric Fenstonwell: "..."` in `beat.resolved_event` / `events[].speaker`, while `present_others` in the SAME payload calls him "the stout man" (`_room_presences_in` labels) — two representations of one fact, free to disagree, and the voice's reply then names him on the page.
- **Verified:** `scratchpad/snip/label_probe.py` — scene entity `{name: "Master Leofelric Fenstonwell", kind: "person", appearance: "a stout man in a scorched leather apron"}`:
  `observer_label_fn(...)(n) -> 'the stout man'`; `_presence_label_fn(ctx, "Barman")(n) -> 'Master Leofelric Fenstonwell'`.
- **Registers:** none (`_presence_label_fn`, `_uncarded_person` not mentioned).
- **Fix:** build the presence label on `observer_label_fn`'s inner `label` with the recognized set as a parameter (one floor, not two), so uncarded persons get `_unknown_actor_label` + the ledger looks; extend `_presence_identity_floor`'s `unknown` to the scene's uncarded persons. **Test:** one uncarded person entity speaking and acting in a room with a presence whose `known` row is empty — `_beat_for_presence`, `_manager_events` and `_thread_heard` carry the label, and agree with `_present_others`.

### F2 — `self.still_waiting_for[].from` hands a mind the canonical name of whoever owes it
- **Severity:** LEAK. **Confidence:** CONFIRMED (traced by reading).
- **Where:** `agents/character.py:4392-4401`
  ```python
  _owed = owed_to(character_name(sh), wget(chat.id, "background_presences", {}) or {}, ...)
  ...
  _self["still_waiting_for"] = _owed
  ```
  `persist/commit_background.py:1729`: `owed["from"] = str(record.get("name") or "")` — the presence record's canonical name. Nothing between there and the wire relabels it (`compact_character_evidence`, `reading_order`, `without_engine_numbers` keep strings).
- **Scenario:** the exact story `tellers_as_known` (character.py:3456-3480) was written for: Sal asks a never-introduced hostler for an ale, he answers "Aye, in good time" with `still_owes`, and every later character call carries `still_waiting_for: [{"from": "Hostler Gidoton Barrelfielder", ...}]`. `told_by` was floored on 2026-09-23; `from` was not. The row also carries `to`, the figure's own label for the asker (its private view), handed to the asker.
- **Registers:** none.
- **Fix:** label `from` exactly as `tellers_as_known` labels `told_by` (`observer_label_fn(chat, observer, cast, scene=sc)`), and keep the raw name host-side so `compile_bare`'s `stop_waiting` → `waiting_ops.from` (character_bare.py:888-892) still closes the right debt (map the label back, as `name_concealed_bodies` does). **Test:** a presence with a `pending_act` to the character and no `known` row → payload `from` is a label; an abandon from the read-back still removes that row.

### F3 — Conversation-thread participants are told each other's names on any shared charter
- **Severity:** LEAK. **Confidence:** PLAUSIBLE (needs a charter that spans strangers).
- **Where:** `agents/background.py:2556-2557` `"participants": [{"name": n, "post": ..., "look": ...}]`. Peers come from `persist/commit_background._thread_peers` (3117-3145): any body in the room sharing ANY charter key (`_thread_charters`, 3112-3114).
- **Contradiction in the same module:** `_present_others` (background.py:2290-2318): "Sharing a charter is not that claim: a households charter holds a whole town of people who have never met" — it names a colleague only on a `known_members` claim.
- **Scenario:** two residents of a households-style charter who never met stand in a room; one answers the player with `still_owes`; a thread opens; the one call voicing both is handed both names, they address each other by name, and the narrator renders it as canon.
- **Registers:** UNBUILT_LIVING_WORLD §2.42 covers thread numbers and steps 3-4, not this.
- **Fix:** label participants by the same rule as `_present_others` (recognition ∪ `known_members`), or open a thread only between bodies holding a `known_members` claim on each other. **Test:** two bodies sharing only a town-wide charter → the thread payload carries labels.

### F4 — Every per-presence voice is handed every room of the scene by name, planned stubs and person-named rooms included
- **Severity:** LEAK. **Confidence:** PLAUSIBLE (path CONFIRMED by reading; content measured).
- **Where:** `agents/background.py:1361-1372` `_presence_rooms` (no filter but `isinstance(room, dict)`), added at 1333-1335 whenever `walkable_from` is set — every `_react_one` call (3163-3164). Docstring: "the layout anyone who works or lives here knows ... nothing about what it would find".
- **Measured (owner's engine.db, read-only):** 368 stored rooms carry `planned: true`; 174 of them in chats ≥ 160, e.g. "Mellisande's Room" (chats 177/178), "Decommissioned Corridor West" (160), "Steep straight flight to Tamamo's Roost" (179). A plan the Room planted ahead, and a cast member's name, go to a bystander in another building who never entered either.
- **Fix:** limit `rooms` to the presence's own building/plan region (or its charter place graph), drop unentered `planned` stubs, and pass room names through the identity floor. **Test:** a planned stub and a room named after a cast member in another building are absent from a presence's `place.rooms`.

### F5 — The scene manager hands every managed presence the PLAYER's room description and room-scoped lore; an unplaced presence gets the player's room
- **Severity:** LEAK. **Confidence:** PLAUSIBLE.
- **Where:** `agents/background.py:1803` `place = _place_block(ctx, p_room)`, while `managed_presences` (1394-1460) admits bodies anywhere in `ambient_scope` (on a vessel "every room aboard", comment at 1630-1632); `agents/background.py:3163` `_place_block(ctx, here or _player_room(ctx, sc), ...)`.
- `_place_block` (1264-1337) carries `room_desc`, room-scoped `world_knowledge` (`_room_notes_from_lore` — its own comment, 1305-1307: room-scoped "because books hold secrets, and an extra is the last mind that should be told one") and `common_knowledge` with ranges for that room. Docstring: "Every field is something anyone standing in the room trivially has." An unplaced presence is refused the beat (X1, 691-701, fails closed) yet handed the player's room.
- **Fix:** in `scene_life` admit the room fields only when every managed presence stands in that room (the rule `_beats`/`_declarations` already follow at 1840-1856); unplaced → no room fields. **Test:** a managed presence in an adjacent room receives no `room_desc`/`world_knowledge` of the player's room.

### F6 — `self.following.same_room` is read off `scene.positions` with no perceptual channel
- **Severity:** LEAK. **Confidence:** PLAUSIBLE.
- **Where:** `agents/character.py:4337-4344` `"same_room": (room_of(sc, _my_follow.get("target")) == char_room ...)`.
- **The same file states the rule it skips:** `_player_silence_note` (1166-1185): "A PRESENCE THIS MIND CAN PLACE, not merely a shared room ... Co-location alone handed the fact over", gated on `visual_level_between` + `sense_adjusted` and the rear arc. The following block's own comment removed `target_room` for having "no perceptual channel of any kind" and kept the co-location bit.
- **Scenario:** the target hides in a wardrobe in the same room (`room_of` still answers the room), or stands behind a blindfolded follower → `same_room: true` tells the follower the target is still here.
- **Fix:** emit `same_room` only where the follower can place the target by the silence note's predicate; absent = cannot tell. **Test:** target contained in a wardrobe entity → no `same_room: true`.

### F7 — `decision.quiet_for_beats` counts beats this mind did not witness
- **Severity:** LEAK (minor). **Confidence:** CONFIRMED by reading.
- **Where:** `agents/character.py:956-997` counts consecutive `director_interpret` beats without player communication — no reference to this mind's presence — and `4609-4616` hands it over whenever the player is visible NOW. The `their_silence` card: "`decision.quiet_for_beats` says how long".
- **Scenario:** a mind walks in this beat; the player has acted silently elsewhere for six beats → `quiet_for_beats: 6`.
- **Fix:** stop counting at the first beat this mind's own stored view did not place the player (e.g., `perception_act.company[cid]` in the same window). **Test:** absent for the window, present now → key absent or 1.

### F8 — Background concealment-by-name fails OPEN for Japanese name forms
- **Severity:** LEAK (language). **Confidence:** matcher CONFIRMED by snippet; delivery PLAUSIBLE (needs a half-compliant `visibility: overt` + `conceal_from` line, the case register X3 exists for).
- **Where:** `agents/background.py:609-611, 684-686, 1713` → `persist/commit_background._background_name_mentioned` (1136-1160), `\b`-bounded.
- **Verified:** `_background_name_mentioned('田中', '田中さん') -> False`, `('Tanaka', 'Mr. Tanaka') -> True`; `re.search(name_boundary_pattern('田中'), '田中さん') -> True`.
- **Fix:** match with `story.character_schema.name_boundary_pattern`, whose docstring names this failure ("`ヒナミに` never matched `ヒナミ` ... each failing OPEN"). **Test:** ja `conceal_from: ["田中さん"]`, overt visibility → presence 田中 receives nothing.

### F9 — `awaiting_your_answer` reads merged per-mind results, so dict order and latest-wins `interaction` decide the debt
- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED by snippet.
- **Where:** `agents/character.py:776-842`: `results = (content.get("character_results") or content.get("reaction_results") or {})`, `for result in results.values()`. In `_merge_character_results` `sequence` is APPEND and `interaction` LATEST-WINS (`agents/common.py:1179, 1256`). The same row stores `rounds` in order, each with `speaker_id` and its own `result` (`agents/loops.py:1494-1500`), unread here.
- **Verified** (`scratchpad/snip/debt_probe.py`, rows fed through `rows_cache`):
  - Tamamo asks Q1, the Doctor answers, Tamamo asks Q2: Tamamo-first dict (the natural insertion order) → `{}`; Doctor-first → `{'awaiting_your_answer': {... 'asked': 'And who do you think built it, Doctor?'}}`.
  - Tamamo asks Q1 in round 0, then addresses Hinami in round 1 → `{}` (Q1's debt lost to the latest-wins interaction).
- **Reach:** `dialogue_budget(awaiting_answer=)` and the interaction loop's owed-answer sweep read the same cached note (comment at 642-650).
- **Registers:** UNBUILT_IDENTITY §1.91 (one-beat lag, vocative residual) — not this.
- **Fix:** walk `rounds` in order when present; merged results only for legacy rows. **Test:** both scenarios as `rows_cache` fixtures.

### F10 — Goal routing matches room names as raw substrings of goal prose, in two copies, under docstrings that say it does not
- **Severity:** WRONG-SCENE + STALE-DOC. **Confidence:** CONFIRMED by snippet.
- **Where:** `agents/character.py:2431-2454` (`pos = folded.rfind(key)`; docstring 2366-2368 "exact node-NAME matching ... identifier recognition, not reading prose") and `mind/affect.py:1973-1987` `_last_named_room` (same algorithm, same claim), which stamps `goal_room`/`goal_room_reached` at commit and feeds `projects_served_this_beat`.
- **Verified:** nodes {Study, Hall, Inn, Kitchen}: "Study the carvings on the far wall" → Study; "Keep the beginning of the story straight" → **Inn**; "who left the hallway lamp burning" → **Hall**; "Ask the cook what she saw" → None.
- **Effect:** exits re-ranked toward, and verdict-suffixed with, the wrong room (3150-3165, clamp 3187); `en_route` asserts a journey (4370-4372); run offers quote distances to it (3366-3376); at commit `goal_reached` tells the mind its goal is spent. Promotion seeds `told` nodes for the whole public town (`world/charter_promote.py:540-580`), multiplying the names to collide with.
- **Fix:** one shared matcher on `name_boundary_pattern` (script-aware, still substring for CJK). **Test:** the four goals above.

### F11 — Exit annotations map exits back to rooms by display name; duplicate names collapse onto the first room
- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED in data; effect by reading.
- **Where:** `agents/character.py:2803-2808` `name_to_id.setdefault(display, rid)`, used at 3044-3046 and 3066; `seen_onward` is keyed by the true rid (2846-2857), so the onward count is looked up under the wrong one too.
- **Measured (owner's engine.db, read-only):** 8 of 156 scenes hold duplicate room names — all recent stair rooms: chats 172, 173, 174, 179 ("Narrow wooden staircase" ×2, "Steep straight flight" ×2, "ladder" ×2).
- **Effect:** the upper storey's stair exit carries the lower stair's `been_there`/`times_entered`/`worked_before`/`toward`; its `untried` marker and the completeness test (`untried_here`, `fully_known`) are wrong.
- **Registers:** UNBUILT_PERCEPTION §3.3 F6 is about naming the room behind an edge, not this collision.
- **Fix:** resolve each digest exit among the CURRENT room's own edges (or carry the rid on the digest ref and strip it at the wire). **Test:** two rooms named "Stair" on two storeys; the mind walked one; beside the other, that exit reads `untried`.

### F12 — Question and addressee recognisers are English-only
- **Severity:** WRONG-SCENE (language). **Confidence:** CONFIRMED by snippet.
- **Where:** `agents/character.py:359, 413, 751, 1506` test `"?" in line`; `'?' in 'どこへ行くの？' -> False` (the engine's other readers include `？`: `agents/director_floors.py:138`, `agents/impossible_knowledge.py:47`). In a Japanese story the player's questions never become `awaiting_your_answer` (751), `recent_self_moves.asked` stays empty, and the repeated-ask screen never fires (1506).
- `agents/character_bare.py:639-651` `_named_here` uses `(?<!\w)…(?!\w)`: `_named_here('田中さん', ['田中']) -> None` while `_named_here('Mr. Tanaka', ['Tanaka']) -> 'Tanaka'`. The speaker's own `to` is ignored whenever it carries an honorific or particle; unread, the line then has no target at all (745-748).
- **Registers:** related UNBUILT_PIPELINE §1.11c(iii) (the `?` fallback in `common._asks_player`), a different site.
- **Fix:** a pack-owned question-mark set (one shared `is_question`), and `name_boundary_pattern` in `_named_here`. **Test:** ja fixtures for both.

### F13 — English sentences spliced into payloads the ja pack otherwise localizes
- **Severity:** WRONG-SCENE (language). **Confidence:** CONFIRMED by reading (ja `linguistics.json` localizes `_VERDICTS`, `_VERDICT_TEMPLATE` `{label}——{detail}`, `_VERDICT_DETAILS`; it has no `agents.background` table at all).
- **character.py:** 3159-3165 (destination suffixes on `verdict`), 3221-3223 (only way onward), 3278-3281 (`_run_end_note`), 3374-3376 (run notes), 4217 (`attention.means` = `affect.CAPACITY_DESCRIPTIONS`, English, every beat), 4307-4316 (`speaking_now.sense`), 4452-4453 (`as_you_remember_it`).
- **background.py:** 326-328 (`_seen_act`), 619-631 ("an indistinct remark"), 738-740 ("an indistinct exchange from …"), 1531-1532 (chorus action, which the narrator renders).
- **Fix:** move each into the pack tables. **Test:** a pack-parity check that a ja payload carries no ASCII sentence (snapshot one ja payload).

### F14 — A mind can never start following someone it knows only by sight
- **Severity:** SILENT-NOOP (a warning is written; no follow). **Confidence:** CONFIRMED by reading.
- **Where:** `agents/character_bare.py:996` emits `follow_op.target = h.people[k]` — a view label (`_actor_labels`). `agents/director_movement.py:664-685` resolves it with `_ci_mapping_key` over `scene.positions` (case-only, 292-307): "the tall man in the oilskin" → None → "Ignored invalid follow start", no ledger row. The read-back offers the follow over the same labels (`mind/character_jev.py:693-700`).
- **Precedent:** `name_concealed_bodies` (character_bare.py:674-712, called at character.py:4939-4945 through `director._bodies_addressed_as`) solved label→body for `conceal_from`; the follow target has no such pass.
- **Registers:** none.
- **Fix:** resolve `follow_op.target` through the speaker's own label map before `character_step` returns; fail closed on an ambiguous label. **Test:** a stranger label → follow starts; two bodies under one label → no follow + warning.

### F15 — `decision.deep_tom_requested` / `decision.dialogue_mode`: Director flags in every payload that no card explains
- **Severity:** SILENT-NOOP (plus a Director-raw reach). **Confidence:** CONFIRMED (grep: zero hits in `language_packs/`).
- **Where:** `agents/character.py:4589-4591` from `ctx.director_interpret.flow.tom_triggers` / `dialogue_mode`. Both booleans survive `without_engine_numbers`. `tom_triggers` is the Director's judgement of whose mind matters this beat, made from the whole beat including acts this mind did not perceive.
- **Registers:** UNBUILT_IDENTITY §1.91 lists the keys; their having no reader is not registered.
- **Fix:** drop both (or gate a card section on them if the behaviour is wanted). **Test:** payload has neither key.

### F16 — `time_passing`: the comment promises elapsed time; the wire drops it unless the clock happens to be stored as an int
- **Severity:** STALE-DOC. **Confidence:** CONFIRMED by snippet.
- **Where:** `agents/character.py:156-162` ("`{elapsed_seconds: 1062.0, display, time_scale}` -- a person has a sense of how long they have been at this") and 145-147 ("holds this table against the prompt and the gate" — the gate went with the full card, `tools/project_check.py:3080-3081`). `without_engine_numbers` (character_bare.py:135-181) drops every float.
- **Verified:** float clock → `{'time_passing': {'display': '08:42 AM', 'time_scale': 'scene'}}`; int clock (3600) → `elapsed_seconds: 3600` survives. Same field present or absent by JSON type. No pack text names `time_passing`.
- **Fix:** decide what the mind gets (a worded duration from `MemoryClock` fits the no-numbers ruling), coerce the type, fix the comment. **Test:** `time_passing` identical for int and float clocks.

### F17 — `_redacted_resolved_event` has had no production caller since 2ba99b22; two tests pin it
- **Severity:** DEAD. **Confidence:** CONFIRMED (repo grep; `git log -S`; `tests/test_scene_life.py` 28 passed).
- **Where:** `agents/background.py:2100-2117`; only callers `tests/test_scene_life.py:218, 227`. The manager admits each presence's perceived beat (`_beat_for_presence`), never the prose.
- **Fix:** delete with its two tests.

### F18 — The verbatim-repeat screen runs before the within-beat reissue floor
- **Severity:** logic (false record). **Confidence:** PLAUSIBLE.
- **Where:** `agents/character.py:4950-4952` screens against `_self_lines`, which already holds this beat's lines (3784); `5004` `_repeat_survived = bool(_repeated)`; `5080-5083` `strip_beat_reissues` then removes the line.
- **Effect:** warning "(recorded; the beat stands)" for a line that did not stand, and `unbidden_probe.repeat_survived=True` → commit's `repeat_flag` → `_unbidden_trigger` (1630) arms on a repeat that never reached the page.
- **Fix:** compute `_repeat_survived` after the floor, or screen committed lines only (the move screen's rule, 398-402).

### F19 — `impossible_knowledge` cues a second speaker who heard the first say it
- **Severity:** WRONG-SCENE (low). **Confidence:** PLAUSIBLE.
- **Where:** `agents/impossible_knowledge.py:144-163` (fed by `agents/character.py:1091-1110`): `aired_this_beat` grows only with tokens HANDED to this observer, so B repeating a private word A said out of this observer's earshot is cued as knowledge with no channel; `lines` run interpret-first then in `character_results` dict order, not speaking order.
- **Fix:** mark a token aired when its line was delivered to the later speaker (their delivered views are in the rows), and order lines by round. **Test:** A says the word (not delivered to O), B who heard A repeats it → no cue.

### F20 — A raised voice anywhere admits every charter figure in the aperture to a voice call
- **Severity:** WRONG-SCENE (low) / PERF. **Confidence:** PLAUSIBLE.
- **Where:** `agents/background.py:2850-2854`: `raised = any(volume in ("loud", "shout"))` admits ALL `figure_rows` regardless of whether the shout reaches their room; creatures are admitted unconditionally. The payload's hearing gate then hands such a figure nothing, and it is still asked (comment 2844-2849: "earshot is what a shout reaches").
- **Fix:** admit on the shout only where `presence_hearing` grades it above `none` for that figure. **Test:** a shout in room A and a figure three rooms off → not asked.

### F21 — Trivia (DEAD / STALE-DOC)
- `agents/character.py:860` unreachable `return result` after `return {...}` in `_labelled_debt`.
- `agents/character_evidence.py:125-143` `visit(..., evidence_row=False)` is never called with `True`; the branch at 128-130 is unreachable (containers are rewritten by `_rewrite_evidence_container`).
- `agents/background.py:62` imports `pick_background_reactors` and never calls it; the module docstring (13-17, 30-35) says the stage is gated by `commit.pick_background_reactor` with "the single slot" — the per-presence path calls `pick_voice_demand` (1113) with a cap up to 3 (1110-1111).
- `agents/character.py:1981-2028`: one two-paragraph argument appears twice in `_ground_observation_citations` (comment debris).

## Efficiency

### E1 — Three independent decision-model passes run one after another before every character call
- **Where:** `agents/character.py:4131-4137` `affect_pass.before_call` (one `decide`), then `4770-4775` `character_jev.ask_before` = two more sequential `decide`s (`mind/character_jev.py:605-612`, disputes vs. moment checks, disjoint inputs). `holding_from` reads nothing the affect pass produces (`agents/character_bare.py:223-280`).
- **Hotness:** every character step, on the critical path; interaction-loop micro-rounds are sequential. Measured 0.4 s median per pass (`docs/experiments/BARE_CARD_REPLAY_2026_09_27.md:113`).
- **Gain:** ~0.4-0.8 s per character call, no quality change. Cheap: run them in a small executor under `copy_context`, as `_voices_at_once` does.

### E2 — `_MEMORY_CONTEXT_POOL` (4 workers) throttles the skip stage's 8-way fan-out
- **Where:** `agents/character.py:125-126`; `agents/skip_stage.py:102, 690-693` (`SKIP_ASK_WORKERS = 8`, each calls `character_step(skip=...)`); parallel `character:<id>` steps share the same pool.
- **Hotness:** every skip with more than 4 minds asked; any beat with more than 4 parallel minds. Minds 5-8 queue for an embedding round trip plus the Jev picker. The step thread blocks on `future.result()` (3998) anyway, so on saturation it could run its own build. The 4 is a cap — name it to the owner.

### E3 — Prefix-cache order inside `self`
- **Where:** `agents/character.py:4148-4192`: `active_state` (changes every beat) sits at position 7, ahead of the static card block `voice, senses, sense_profile, interoception, abilities, embodiment_capabilities, body_parts`. Volatile too: `attire`, `recent_self_lines/moves`, `feelings`, `notebook`; top level `decision`, `time_passing`, `variant_seed` precede `memory`/`perception`.
- **Gain:** static card first makes a per-character prefix of a few KB cacheable across beats. Unmeasured and provider-dependent (`character_major` 1.4% cached on Fireworks; NanoGPT kept a 12k prefix across a beat gap 1 time in 5 — memory notes). Order-only, same keys.

### E4 — Per-character reads that are identical for every mind in the turn
- `wget(known)` via the label builders 3-4× per call (`present_label_fn` 4264, `observer_label_fn` 4281, `tellers_as_known` 3469-3470, `observer_name_scrub` 3902); `wget(background_presences)` in `owed_to` (4395); `_player_persona_name` `SELECT * FROM chats` (589-594); `_addressed_names_include` one roster query per numeric ref per window row (505-516) — it compares names where `int(ref) == char_id` would answer; `_impossible_knowledge` rebuilds and tokenizes the public corpus (every cast sheet, room and entity) per mind (1065-1083).
- **Measured row sizes (read-only):** `known` avg 69 B, `background_presences` avg 508 B, `scene` avg 19.6 KB / max 56 KB. Low gain; cheapest fix is the existing per-turn `shared` snapshot.

### E5 — Background stage re-reads
- `_beat_scene` (wget scene + `far_end_scene` + `beat_scene`) ≥4× per stage (`_background_react`, `managed_presences`, `_demanded_presences`, `scene_life`); `_presence_recognizes` (wget known) ~6-8× per presence; `_place_block` re-reads the stored scene per call; `_presence_rooms` puts O(rooms) names in every per-presence call (avg 7.5, max 24 rooms today; grows with planned towns). Low.

### E6 — Three full payload copies per call
- `compact_character_evidence` deep-copies the payload (character_evidence.py:35), then `reading_order` and `without_engine_numbers` rebuild it (character.py:4812-4816); the lookups path folds and walks again. Milliseconds; lowest.

## Already registered

- **UNBUILT_PERCEPTION §3.3, F6 residual:** `spatial_digest` renders the authored room name behind every edge, including rooms never visited — the name `_annotate_known_exits` maps back to a rid. (Q4.)
- **UNBUILT_PERCEPTION §3.3, F7:** `known_pronouns` releases pronouns on unverified mind-model keys (`set(relationships) | set(mind_models)`).
- **UNBUILT_IDENTITY §1.91:** nothing marks addressee-hood; `_unanswered_question_note` fires one beat late; the vocative residual.
- **UNBUILT_PIPELINE §1.11c(iii):** the player exit reads an address by name, through the `?` fallback.
- **UNBUILT_CHARACTERS §2.26:** lookup caps unruled (`TOOL_BUDGET` 5, `SPAN_TURNS` 5, `TOOL_WALL_SECONDS` 60, `RESULT_CHARS` 16000, `WHERE_LIMIT` 6).
- **UNBUILT_LIVING_WORLD §2.42:** thread numbers unconfirmed; **§6.1:** the `recent` ring (`BACKGROUND_RECENT_TAIL = 4`) is what a presence's reaction reads.
- **UNBUILT_PIPELINE §3.1:** the identity floor is token-based prose matching (also what `_presence_identity_floor` relies on).

## Structure notes

- **character.py** (5154 lines, 63 defs; anatomy `scratchpad/anatomy/character.md`): `character_step` 3555-5154 is a 1600-line monolith with clear phases — gates 3570-3672; memory submission 3674-3862; knowledge, relationships, frame mask 3863-3995; memory result + unbidden 3996-4045; psychology + `self` 4047-4400; places + debt notes 4402-4505; perception/decision assembly 4507-4627; late contributors 4628-4712; card, lookups, call 4713-4900; read-back + floors 4900-5154. Other monoliths: `_annotate_known_exits` 469, `_ground_observation_citations` 293, `_unanswered_question_note` 246.
- **Seams:** (a) self-record ledgers + repetition screens (206-1560); (b) address/debt notes (439-1201); (c) navigation (2120-3380); (d) unbidden recall + citation grounding (1563-2117); (e) small helpers (`_impossible_knowledge`, `_known_pronouns`, `_prune_seeded_psychology`, `tellers_as_known`, `_character_perception`, `_private_continuity`). `_delivered_memory_rows` and `_taken_adjacency` are imported LAZILY by `character_bare.py:203` and `character_tools.py:179, 429, 457` to dodge a cycle — move both to a leaf first.
- **Split blast radius:** 56 monkeypatch sites (41 `_agent_json`), 28 source-text pins (13 whole-module `inspect.getsource(character)`), 5 file pins incl. `tools/project_check.py:3089` (reads `agents/character.py` by path for `PAYLOAD_NAMES`).
- **Module-level state:** `PAYLOAD_NAMES`, `_PROJECTED_AT` (dicts; no writers; read by `project_payload_names` and by project_check via AST); `_MEMORY_CONTEXT_POOL` (process-lifetime executor, never shut down; shared by every character call including the skip stage). No `global` rebinds.
- **background.py** (3257 lines, 62 defs): `_react_one` 219, `_background_react` 192, `declare_charter_figures` 188, `scene_life` 176, `_demanded_presences` 148, `_present_others` 135. Seams: presence perception (96-748), voice orchestration (750-1203), scene manager (1206-2127), identity/presence gates (2128-2440), charter voices + threads (2440-3020), `_react_one` (3028-3257). Imports ~25 names from the `persist.commit` facade, about half private (`_background_name_mentioned`, `_quote_body`, `_room_of`, ...) — cross-package private coupling. No mutable module state besides `_log`.
- **character_bare.py:** `compile_bare` 372 lines (715-1086), `_compile_notebook` 122. **character_tools.py:** `Lookups` 460 lines. **character_evidence.py:** small, pure.

## Docs checked

- CLAUDE.md, "character agents declare behavior from private perception/memory/relationships only": **does not fully hold** — F2, F6, F7, F15.
- CLAUDE.md, "`agents/background.py` gives ... a stateless reaction per beat — no persistent memory or psychology": **partially holds.** The voice is handed its own last 3 recorded exchanges (`recent_interaction` / `cast[].recent`, from a persisted ring of 4), a frozen `blurb`, `pending_reply`/`pending_act` across beats, and for charter bodies an `institutional_context` (condition, duties, acquaintances, news). Conversational state by design (module docstring; UNBUILT_LIVING_WORLD §6.1), but not stateless.
- CLAUDE.md, "gated by `pick_background_reactors` ... cap `max_reactors` (default 1, hard ceiling 3)": the per-presence path calls `pick_voice_demand` (background.py:1113), of which `pick_background_reactors` is the names-only wrapper (commit_background.py:4145-4149). Cap and ceiling hold (1110-1111).
- AGENTS.md:432, "findings are recorded on the step as `repeat_correction`/`move_correction`/`intention_correction`": **loosely** — only as step warnings; the dicts are never attached to the result (character.py:4960-5014); `_barren_beat` is the one data consumer. The row also names `decision_continuity` as a `character_bare.py` symbol; it is an output key, not a function.
- Design.md:530 (lookups): read-only over the mind's own stores through `visible_memory_rows`, no engine numbers (`Lookups.run` → `without_engine_numbers`, character_tools.py:563), budget 5 / 60 s — **holds**.
- `docs/guides/MEMORY.md:250-280` (RECENT_TURNS 8, `_RECALL_LIMIT` 30, `NET_SIZE` 100; wire order memory → perception, recalled → recent): **holds** (`character_bare.reading_order`, 102-128). `MEMORY.md:314` ("those three recent lanes ... projected with ... `memory_form`"): **stale** — one recent lane since 2026-09-28, and `_with_reading` no longer projects `memory_form` (`mind/memory_context.py:62-65`).
- Docstrings: `PAYLOAD_NAMES` comment (F16), `_destination_from_goals` / `_last_named_room` (F10), `_place_block` (F5), `_presence_rooms` (F4), background module docstring (F21) — **stale**. `_attach_unbidden` — holds (absorption-narrowed recall cannot reach 30, so the entry always takes a spare slot).

## Appendix — the assignment's questions

**Q1. Every payload key and its source.** `self`: own card (`entity_id, name, public_history, psychology` (+ interior drive, pruned seeds), `stance, curiosity, voice, senses, sense_profile, interoception, abilities, embodiment_capabilities, body_parts`), own stored state (`active_state` annotated, `intentions`, `steering_intention_ids`, `projects`, `former_*`, `learned_*`, `decision_continuity`, `my_notes`, `earlier_this_beat`, `rupture`, `crisis`, `recent_tells`, `tell_grounds`, `project_review`, `notebook`), own committed declarations (`recent_self_moves`; `recent_self_lines` from the Director's `dialogue_log` filtered to this speaker — own words only), the scene about OWN body (`attire`, `body_state`, `speaking_now`, `standing_contacts` labelled), own place graph (`en_route`), affect pass (`feelings`). Scene reads about OTHERS: `following.same_room` (**F6**), `still_waiting_for` from the `background_presences` ledger (**F2**). `perception`: own scrubbed observations (`perception_packet`), sight/light-gated `here_affords` and `corridor_sight`, `spatial_frame` (scene digest — registered §3.3 F6 — annotated from own history, **F11**), `current_room` (scene room name; the composed view names the room too), `sprint_reach` (scene, gated to remembered rooms), `impossible_knowledge` (other minds' raw lines this beat, kept only where delivered to this mind). `memory`, `relationships`, `mind_models`, `private_knowledge`: own. `world_knowledge`: lore, circle/tag gated, names scrubbed. `known_pronouns`: registered §3.3 F7. `decision`: `deep_tom_requested`/`dialogue_mode` straight from `ctx.director_interpret.flow` (**F15**); `speech_budget` config + own voice; `they_said_nothing`/`their_name`/`quiet_for_beats` from `director_interpret` + scene + sight gate (**F7**); `awaiting_your_answer` (**F9**); `not_answered_yet` (loop record); `comes_to_you` (`director_interpret.authorial_offers` for this subject — by design). `time_passing` (world clock, **F16**), `variant_seed`, `carried_reports` (tellers labelled), `while_you_were_offscreen` (own gap, scrubbed), `the_stretch_just_passed` (own skip log). No key reads `state_diff`.

**Q2. `character_tools`.** Every lookup reads the mind's own stores: memory rows through `visible_memory_rows` (own char, this frame, before this turn, archived included — archived means consolidated, `mind/memory_summaries.py:731`); `notebook` reads the frame-masked `_recognized_state`; `where_can_i`/`route_to` read the mind's own `place_graph` (`told` affordances come from its own mind-model stated facts, labelled `basis: told`); `why_do_i_think` reads its own hypotheses. No tool reads the scene, another mind or the clock (`when` is the `MemoryClock` relative wording; `sureness` is worded). Note only: `route_to` returns the raw room id for a node with no name (`named.get(rid) or rid`, 492). The "no clock" ruling found is for the prose Director (2026-10-04); minds receive the standing time of day as `time_passing.display` by design (Design.md row "What time it is...").

**Q3. Memory packet.** Matches the design: 8 whole recent turns (`RECENT_TURNS`), 30 recalled (`_RECALL_LIMIT`) from a 100 net, recalled then recent at the end of `memory`, `perception` last (`reading_order`). The emotional pass reads every delivered memory and runs after the unbidden entry is attached (4017-4045, then 4131); `recalled_places` and `may_mean_otherwise` join afterwards (not memories). Absorption-narrows-recall-only lives in `mind/memory_context.py` and was not re-verified.

**Q4. `_annotate_known_exits`.** The exits listed are the current room's own edges (`spatial_digest`, minus one-sided walls), named even when never entered or seen — registered (UNBUILT_PERCEPTION §3.3 F6). The markers read only the mind's own route, `known_exits` and `place_graph`; `onward_*` are sight-gated (`visible_adjacent_rooms`, `sight_reaches`). `told` nodes DO exist now (charter promotion seeds the public town, `world/charter_promote.py:540-580`); they add adjacency, never routes (`_taken_adjacency` needs `taken`). New defect: duplicate room names (**F11**).

**Q5. `background.py`.** Voicing beyond the beat's reach: the scene manager voices only the demand set, each address channel-tested (`address_reaches` / `demand_reaches`); `declare_charter_figures` admits every creature, and every figure on any loud or shouted line, regardless of reach (**F20**). Memory across beats, from the ledger: `recent` (heard + said words, last 3 of 4), `blurb` (manner, trait, tell, look, frozen), `sketch` (role_hint, station_room, appearance, surface), `nature`, `first_turn`, `pending_reply`, `pending_act`, `engaged_turns` and `charter_refs` (gates), `dialogue_turns`/`mention_turns`/`addressed_turns` (promotion counters, not delivered). Name learning: `_presence_recognizes` reads `known[presence name]`, normally empty, so carded people become labels; uncarded people leak (**F1**); `_present_others` names charter colleagues only on a `known_members` claim, thread participants unconditionally (**F3**).

**Q6. Prompt text.** These modules build no prompt prose of their own (the cards are pack files) and carry no single-story examples. What they do splice in is English sentences (**F13**) and English-only recognisers (**F8**, **F12**). No free-prose word lists here; the vocabularies used (`loud`/`shout`, appeal-order keys, the affordance enum) are engine-owned.

**Q7. Efficiency.** E1-E6 above.
