# Audit: `agents/director_prose.py`, `agents/director_movement.py`, `agents/director_rooms.py` (+ `agents/director_lots.py`)

Auditor run 2026-11-01, working tree at `84f3de23` (branch `worktree-jev-character-tracking`, clean).
Read-only. Snippets ran on `.venv/bin/python` with `ENGINE_DB` pointed at a scratch file in the
scratchpad; one focused test file run (`tests/test_a_walk_is_its_owners.py`: 13 passed).

## Scope read

Read in full, every line:
- `agents/director_prose.py` 1-5186
- `agents/director_movement.py` 1-3372
- `agents/director_rooms.py` 1-3003 (the geometry passes 400-1180 were read, not re-derived)
- `agents/director_lots.py` 1-450 (read because `expand_entered_lots` is on the beat path)

Read in part, as supporting context (not audited):
- `agents/director_scopes.py` 1-140, 255-300, 395-500 (`SPECIALISTS`, `channel_serves_stage`, `_gate_facts`)
- `agents/director.py` 1735-1760, 1840-1866, 2095-2125, 2200-2240, 2440-2470, 6680-6720, 6890-7060
  (the call sites of `run`, `install_prepared_rooms`, the movement backstops)
- `agents/director_repair.py` 905-925 (its `select_channels` call only)
- `llm/prompts.py` 30-60, 320-620; `llm/decisions.py` 1-80
- `world/spatial_walk.py` 357-530 (`walk`); `world/spatial_merge.py` 1817-1945, 2000-2025;
  `world/structure.py` 866-960, 1362-1560; `world/lots.py` 36-119; `world/charter_runtime.py`
  751-823, 964-994; `world/spatial_lint.py` 724-775
- `persist/commit_scene_state.py` 2230-2420 (the approach ledger); `persist/commit_room_registry.py`
  395-454; `persist/commit_destruction.py` 193-265; `persist/commit_ledgers.py` 121-161, 261-301;
  `persist/commit_mechanics.py` 474-530
- `core/db.py` `transaction` (2349-2389), `db_read_token` (3040-3069), `FRAME_SCOPED_WORLD_KEYS`
- `tools/project_check.py` 856-916 (`check_channel_owners`)
- Cards (en): `prose_contract/{director_interpret,director_resolve,encoder_interpret,room_author,room_reconcile,room_prepare_note,room_done_missing,room_done_unlisted,encoder_cue,layout_lot}.txt`;
  `encoder/{positions,poses,contact_action_ops,crowd_ops,courier_ops,destruction}.txt` (opening paragraphs);
  `jev_questions/{walk_stopped,positions,rooms,entities__inside,crowd_ops,courier_ops}.txt`;
  `linguistics.json` `_RAPID_FOLLOW_VERBS` (en, ja)
- Docs: `AGENTS.md` 255-300; `Design.md` row "A mind goes only where its own declaration takes it";
  `docs/design/DESIGN_PROSE_CONTRACT.md` 1-126; `docs/design/DESIGN_BUILDING_LOTS.md` 1-140;
  `docs/UNBUILT_PIPELINE.md` §1.1, §1.133, §1.188, §1.227; `docs/UNBUILT_WORLD.md` §2.15, §2.43 (lots
  bullet), 3062-3080

Not read (skimmed headings only, or not opened): `docs/design/DESIGN_LAYOUT_TIER.md`;
`DESIGN_PROSE_CONTRACT.md` past line 126; `agents/director_layout.py`; `agents/director_fanout.py`
(`_specialist_payload`, `_beat_rooms`); `director._run_specialists`; the ja cards' prose.

## Findings

### F1 — The walk floor refuses a body the WORLD moves inside another mind's declared event, and `_doer_alone` then drops the whole event (the world's own writes included) and offers it to that body as its conduct

- **Where:** `agents/director_prose.py:2348-2379` (`_walks_refused`), `2389-2441` (`_doer_alone`),
  `2267-2295` (the doer read in `a_walk_is_its_owners`), `2072-2104` (`_linked`).
  ```python
  # _walks_refused
  return {key for key in moved
          if key != source and key not in declarers
          and not _linked(scene, events, names.get(key) or key,
                          names.get(source) or source)}
  # a_walk_is_its_owners
  own = mind(event.get("source_entity_id"))
  doer = own if own != source else _doer_alone(event, person)
  ...
  if doer in refused:
      continue                      # the event is dropped whole
  ```
  `_doer_alone` counts only identity-index bodies, so a THING moved in the same event (a cart) and every
  non-placing write (`entities`, `rooms`, `sensory_events`) are invisible to "ONE body".
- **The rule it contradicts.** The encoder's own `positions` chunk
  (`language_packs/en/cards/system_prompts/encoder/positions.txt:2`): "WHERE A BODY WALKS IS ITS OWN;
  WHERE THE WORLD PUTS IT IS YOURS TO WRITE. A body that is moved rather than moving -- dragged, carried
  off by a current or a press, dropped through a floor, whatever did it ... the player included -- ends
  where the prose leaves it, and you MUST write that room". The owner's 2026-10-07 ruling targets a
  mind's OWN-POWER move, and 2026-10-20 ("undergoing, never deciding") gives what a body undergoes to
  the Director. The floor's only "world" exemptions are a `world`/`mechanical` input or a hold/carry/
  inside link (`_linked`); a consequence of a declared act -- the floor that breaks under the player's
  stamp, the passenger of a cart she drives, a body shoved through a doorway without a recorded
  contact -- carries the declarer's `source_event_id` and is refused.
- **Reproduced** (snippet, scene loft->barn; player `persona:1` world_author, act `e1`):
  ```
  event: "The rotten boards give way under Elias and he drops into the barn below."
         transforms: entities{loft_boards: broken}, positions{Elias: barn}
  targets=None   -> kept events: []          (the boards' breaking is lost too)
                    refusals: [{"mind":"character:2","event":"the boards give way and Elias drops through","offer":true,"to":"barn"}]
  targets=[Elias]-> boards break, Elias stays in the loft; offered "in Barn"
  ```
  And a driven vehicle (scene `contained` Elias and Rhona on `cart`):
  ```
  event: "Rhona drives the cart out of the yard onto the road, Elias riding in the back."
         transforms: positions{cart: road, Elias: road}
  -> kept: []   refusals: [{"mind":"character:2","event":"the cart rolls out onto the road","offer":true,"to":"road"}]
  ```
  The player's own declared drive moves nothing, and the cart's move is offered to Elias as his act.
- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED (snippets above; `tests/test_a_walk_is_its_owners.py`
  passes, so no test covers a world-put body). Design.md's row and the register's measurements
  (4,210 stored outputs, four firings, all of the class) say this has not fired on stored data: a
  latent over-subtraction, not a measured regression.
- **Fix:** (a) In `_doer_alone`, return None unless the event writes nothing but that one body's
  placement -- any other key in a placing table (a thing) or any other channel means the event is not
  about that body alone; never drop the declarer's non-body writes. (b) Give the encoder a typed way to
  say "put, not walked" that the floor reads (e.g. the event's `targets` naming the moved body, or a
  `put` marker on the position) and exempt it; measure the false-positive rate on the stored corpus
  before landing, per the guards ruling. Tests: a fall through a floor in the player's event keeps the
  floor's break and the fall; a driven cart with a passenger keeps the cart's move; the lighthouse
  shape (`test_the_account_and_the_world_agree.py`) still refuses and offers.

### F2 — Every agency floor matches a mind by its exact identity-index spelling, so a uid, alias or short name walks a registered mind past it

- **Where:** `agents/director_prose.py:2227-2238` (`a_walk_is_its_owners`), same tables at
  `2511-2517` (`the_account_places_its_own_body`), `2979-2987` (`conduct_is_its_owners`),
  `_follows_of_the_declarer` via `mind`.
  ```python
  key_of = {name.casefold(): key for key, name in names.items() if name}
  key_of.update({key.casefold(): key for key in names})
  def mind(label):
      key = key_of.get(str(label or "").strip().casefold())
      return key if key and _MIND_KEY.match(key) else None
  ```
- **Scenario:** the encoder spells a cast member by entity id or a short form -- it has done so
  (`director_movement._canonical_following_ops` docstring: scratch story 166 turn 4598 filed the pilot
  as `char_hester_gale`). `mind()` returns None, the move is not checked, and the commit's spelling
  policy (`common.cast_spelling_policy`, which folds the sheet uid "regardless of `aliases`") then
  lands the position on the mind.
- **Reproduced** (interpret, player's span `t1`, identity `character:2: "Abel Coyle"`):
  ```
  'Abel Coyle'      -> {"Tamsin Reed": "low_walk"}                       (refused)
  'Coyle'           -> {"Tamsin Reed": "low_walk", "Coyle": "low_walk"}   (passes)
  'char_abel_coyle' -> {"Tamsin Reed": "low_walk", "char_abel_coyle": "low_walk"}  (passes)
  ```
- **Severity:** WRONG-SCENE (a mind moved by another's declaration). **Confidence:** CONFIRMED for the
  floor; PLAUSIBLE that the uid spelling lands (read `cast_spelling_policy` and `canonicalize_positions`,
  not executed through the commit). "The deterministic floor must not depend on a model cooperating."
- **Fix:** resolve labels through the one spelling policy (`cast_spelling_policy(cast, player)` and
  `same_subject`) in `mind()`/`person()`, as `_canonical_following_ops` already does. Test: the same
  refusal fires when the position is keyed by the uid and by an alias.

### F3 — A walk left under way inside its own destination room is retired as "arrived" the next beat without being walked

- **Where:** `agents/director_movement.py:3012-3015` (`_travel_continues`) and `2896-2898`
  (`_travel_in_flight_view`):
  ```python
  here = room_of(route_scene, subject)
  if here and here == destination:
      record["arrived"].append(subject)
      continue
  ```
  Writers of such legs: `walk_within_room` (`2861-2868`, `from == to == destination == room`,
  `underway: True`, warning "silence carries the walk on") and `walk_declared` when the paces run out
  after entering the destination but short of its `to_anchor`/`to_cell` (`world/spatial_walk.py` ~469
  returns `room == to_room, arrived False`). The commit turns each into an approach
  (`persist/commit_scene_state.py:2309-2318`) and retires it on `arrived` (`2327-2331`).
- **Reproduced:**
  ```
  walk_within_room: {"advanced":[{"subject":"Hester","from":"square","to":"square","destination":"square",
                     "to_cell":[23,12],"paces":18,"underway":true}]}
                    warning: "...ends the beat at [18, 12]; silence carries the walk on."
  next beat, approach {to_room: square, to_cell: [23,12]} ->
  _travel_continues: {"arrived":["Hester"], ...}  sd: {}   (no step walked)
  _travel_in_flight_view: []                          (the Director is told nothing)
  ```
- **Severity:** WRONG-SCENE (the body stays mid-room with its `at` and `near` cleared and an on-the-way
  pose; the warning promised the opposite). **Confidence:** CONFIRMED.
- **Fix:** where `here == destination` and the leg names `to_cell`/`to_anchor` the body has not reached,
  walk it (`walk(route_scene, subject, destination, to_cell=..., to_anchor=..., paces=...)`) and report
  it in `travel_in_flight` as a within-room leg. Test: a pending within-room leg longer than one beat's
  paces is `advanced`, not `arrived`.

### F4 — The record-fact gate removes channels whose ops CREATE their record, and the encoder cannot even request them: a story's first crowd can never be raised

- **Where:** `agents/director_prose.py:100-108` (`_RECORD_FACTS`), `176-178` (`candidate_channels`),
  `3977-3992` (`encode`: `known = set(stage_channels)`, `lacking` filters `missing_tools` to `known`).
  ```python
  _RECORD_FACTS = {"crowd_ops": ("crowds_present",), "courier_ops": ("couriers_present", "reports_carried"),
                   ..., "destruction": ("destructible_entity",)}
  ```
  The docstring's premise is "Channels whose only possible subject is a record the world ALREADY holds".
  But `encoder/crowd_ops.txt:1` says "Leave crowd_id EMPTY to raise a new crowd" and the Jev question
  asks whether a crowd "appear[s]"; `courier_ops` sends on "a `claim` they are making up" with no
  carried report; `destruction` accepts any target a lorebook is anchored to at building/region scale
  (`persist/commit_destruction.py:212-265`), while `destructible_entity` counts only scene entities of
  kind vehicle/building/structure/ship/boat or with interiors (`director_scopes._gate_facts`).
- **Reproduced:**
  ```
  candidate_channels("resolve", facts={crowds_present: False, ..., destructible_entity: False})
  -> crowd_ops False | courier_ops False | destruction False | telling_ops False
  encoder may request crowd_ops via missing_tools: False
  ```
  So on a beat where onlookers first gather, `crowd_ops` is not asked, its chunk does not ship, it is
  not in `requestable_tools`, and an encoder that asks for it anyway has the request silently dropped
  (it is not even recorded in `record["missing_tools"]`).
- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED for crowd_ops; PLAUSIBLE for the
  destruction/building case (depends on stories anchoring books to buildings rather than minting
  building entities). The gate was a measured choice (chat 153 false yeses); not in any register.
- **Fix (class):** keep the gate on the decision question if its false-positive rate still warrants it,
  but keep gated channels in `encode`'s `known`, so `missing_tools` can grant them when the prose
  creates the record; or split create-ops from act-on-existing ops. Test: with `crowds_present` False,
  an encoder answer naming `crowd_ops` in `missing_tools` is widened with it.

### F5 — A lot the job expands while a beat is running is designed by that beat as the whole building in one room (stale brief), and the beat path's failures leave no trace

- **Where:** `agents/director_prose.py:4720-4735`, `agents/director_lots.py:431-450`.
  ```python
  develop = {rid: planned[rid] for rid in jev.get("entered") or () if rid in planned}
  if develop:
      try:
          develop = expand_entered_lots(...)
      except Exception:  # noqa: BLE001 -- a lot never stops a beat
          pass
  # director_lots.expand_entered_lots
  lots = [rid for rid in develop if is_unexpanded_lot((rows.get(rid) or {}).get("planned"))]
  ...
      if expand_lot(...):
          brief = (planned_room_brief(cid, scene, [rid]) or {}).get(rid)
          if brief: out[rid] = brief
  ```
  `planned` is the brief built when the stage's payload was built (`director.py:1860`,
  `_planned_rooms_view`). The rooms-in-view job (`_predevelop_run` -> `expand_lots_near`) runs beside
  turns and expands exactly the lot an actor is heading for. If it plants the building after the
  beat's payload and before `expand_entered_lots` (the author's prose call plus Jev in between), the
  fresh `registry_rows` says "expanded", the lot is skipped, and `develop[lot]` keeps the LOT brief --
  the whole building's purpose and only its ways onto the ground. The same happens when the beat's own
  `expand_lot` loses the race (`director_lots.py:368` returns `[]` because the plan moved). The room
  author then develops the entry from that brief ("A plan says what the room is for ... Its purpose and
  its exits are given and stay"), which is exactly what `DESIGN_BUILDING_LOTS.md` "Never designed as one
  room" exists to prevent.
- **Silent failure:** `expand_lot` never raises (it files `LOT_RUNS_KEY` and logs at INFO), and
  `run` neither warns nor records anything: `room_record` holds no "lot expanded / failed" entry, so a
  beat that paid the lot architect's call, or failed it and designed the lot as one room, cannot say so
  in the pipeline drawer.
- **Severity:** WRONG-SCENE (stale brief) + SILENT-NOOP (no record). **Confidence:** PLAUSIBLE (traced:
  `_planned_rooms_view` at payload time, job concurrency via `jobs.submit_latest`; not reproduced live).
- **Fix:** after `expand_entered_lots`, re-read `planned_room_brief` for every rid whose registry row
  differs from the one the payload saw (whoever expanded it); add `room_record["lots"]` with
  expanded/failed/skipped and a `ctx.add_warning` on failure. Test: a develop dict holding a lot whose
  registry row is already expanded comes back with the entry's brief.

### F6 — `expand_lot`'s "plan moved" re-check and its planting are not one transaction, and `deal_berths` is a read-modify-write outside any

- **Where:** `agents/director_lots.py:364-373`, `316-331`.
  ```python
  if registry_rows(cid).get(lot_uid, {}).get("planned") != entry["planned"]:
      return []
  structure = _structure_as_held(cid, {...})
  _structure, planted = plant_structure(cid, structure, rooms)   # its own transaction
  dealt = deal_berths(...)   # registry_for_update(...) ... save_registry(...)
  ```
  `core.db.transaction()` is the process-wide write lock plus `BEGIN IMMEDIATE`; `_file_prepared` uses
  it for exactly this read-then-write and says why. Here two expansions of one lot (the job and the
  beat, or two frames' jobs that both have an actor near it) that return from their model calls
  together can both pass the check and both plant: a second building's rooms (`lot__<rid>` uids chosen
  against rows read before the other planting), the entry's `adjacent` rewritten to the second set,
  the first set's rooms left planned and unreachable. `deal_berths` reads the frame's charter registry
  and saves it later; a charter save landing between (a commit's charter flush) is lost.
- **Severity:** CORRUPTION (plan rows / charter state). **Confidence:** PLAUSIBLE, low probability (the
  window is the time between the re-check and the plant, milliseconds).
- **Fix:** wrap the re-check, `plant_structure`, `deal_berths` and a `jobs.is_cancelled` check in one
  `transaction()` (savepoints make the nested ones safe), and read the charter registry inside it.
  Test: two threads expanding one lot with stubbed calls plant once.

### F7 — At any stage, a mind that declared ANYTHING may be walked by another mind's span: the declarer exemption accepts a move the mind never declared

- **Where:** `agents/director_prose.py:2376-2379` (`key not in declarers`), docstring `2127-2131`.
- **Reproduced** (resolve; Hester `character:1` act `h1`, Coyle `character:2` act `c1`, e.g. "stays by
  the boat"; event filed under Hester's `h1` writes `positions{Hester: low_walk, Coyle: low_walk}`):
  ```
  kept positions: {"Hester": "low_walk", "Coyle": "low_walk"}   refusals: []   warns: []
  ```
- **Why it matters:** the 2026-10-07 ruling (owner's memory note `a-walk-is-its-owners`): "a move whose
  `source_event_id` belongs to ANOTHER actor's declaration is not that mind's walk: drop the move ...
  unless a hold/carry (contact) links the two". The code adds "or it has a declaration of its own at
  this stage" (also written into Design.md's row), which at resolve covers every cast member who acted
  at all. The register's measurement (UNBUILT_PIPELINE §1.227: "81 cast moves at resolve ... every one
  the mover's own") means 0 stored firings of this shape.
- **Severity:** WRONG-SCENE (a mind's declared stillness overridden by another's span). **Confidence:**
  CONFIRMED behaviour; whether the exemption is intended is the owner's call (Design.md documents it,
  the ruling's text does not have it).
- **Fix:** exempt only a move the moved mind's own declaration carries (its own `source_event_id` on
  some event moving it this stage), not "has a declaration". Test: the snippet above refuses Coyle.

### F8 — A world_author player's standing fact about a signal elsewhere is refused, because the signal floor re-files it under `world` first and the authority check keys by the FILED source

- **Where:** `agents/director_prose.py:3056-3059` (`standing_is_authorship`), call order `4922-4923`
  then `4944-4946`.
  ```python
  source = str(event.get("source_entity_id") or "").strip()
  key = key_of.get(source.casefold(), source)
  mode = mode_of.get(key)          # "world" is never a key of mode_of -> refused
  ```
  `skip_is_authorship` does it right: by `source_event_id` (`mode_of_event`).
- **Reproduced:**
  ```
  after re-file source: world
  kept: 0 refused: [{'source': 'world', 'mode': None, 'event': 'The bell in the tower has been tolling all morning.'}]
  without the re-file: kept 1 refused []
  ```
- **Severity:** WRONG-SCENE (minor; warned). **Confidence:** CONFIRMED.
- **Fix:** key the mode by the event's `source_event_id` -> its input's `authority_mode`, as
  `skip_is_authorship` does, falling back to the filed source. Test: the snippet's event is kept.

### F9 — Decision-model questions and states authored inline in English, outside the language packs

- **Where:** `agents/director_prose.py:700-706` (the "enter" question for every planned room in
  reach), `1612-1623` (`bind_new_places`: question and the "none of these places" criterion),
  `583-596` (`_jev_state` labels "PASSAGE:", "PEOPLE:", "WHERE EACH PERSON IS BEFORE THE PASSAGE:", ...),
  `5177` (`pressures_ended` "PASSAGE:"); `agents/director_rooms.py:1763-1793` (`_record_text`, the state
  for the designer's finish questions: "PLACE:", "Fixtures:", "Ways out:").
  ```python
  "instructions": f"Does the passage enter, open onto or reveal the place "
                  f"called \"{name}\"? Answer no when it is only mentioned "
                  "or lies beyond a door nobody opens."}
  ```
  Every channel question, `walk_stopped` and `pressure_ended` come from `jev_questions/` in both packs;
  these do not (no `enter`/`bind` key exists in either pack).
- **Scenario:** a Japanese story asks Jev an English question about a Japanese passage. The project's
  own finding is that Jev options are read by their words and each pack must be probed separately; the
  enter question decides which planned rooms the room author develops, so a misread leaves an entered
  stub undeveloped (or develops one only mentioned).
- **Severity:** WRONG-SCENE (language hazard). **Confidence:** PLAUSIBLE (not probed on ja).
- **Fix:** move both questions and the state labels into `jev_questions`/`prose_contract` (en + ja) and
  probe them per pack. Test: `jev_question("enter_place", "ja")` exists and `select_channels` uses it.

### F10 — The "rapid movement" guard reads free prose: a verb word list over a free-text field, and an English-only regex over `attempt`

- **Where:** `agents/director_movement.py:645-661`.
  ```python
  verb = str(event.get("verb") or "").strip().casefold()
  if verb in _ling("_RAPID_FOLLOW_VERBS"): return True
  attempt = str(event.get("attempt") or "").strip().casefold()
  if re.match(r"^(?:tries to |attempts to )?(?:run|sprint|flee|dash|bolt|race)\b", attempt): return True
  ```
  `verb` is a free `str` (`llm/schemas.py:1267`); the regex has no ja counterpart.
- **Scenario:** in a Japanese story with an empty `verb`, or an English one written "takes off down the
  lane", a flight is not detected: `_apply_following_movement` carries a willing follower through a
  pursuit (the case the guard exists to refuse), and `walk_declared` walks a sprint at walking pace.
- **Severity:** WRONG-SCENE (language hazard). **Confidence:** PLAUSIBLE.
- **Fix:** read the typed `pace` the movement already carries (`mv.pace`, `MovementDecl.pace`) and give
  characters' declarations the same field, instead of the verb/attempt text. Test: a ja declaration
  with `pace: run` and no verb is rapid.

### F11 — An approach record never retires except by arrival or interruption: a body with no room holds it forever, and it resumes undeclared when the body is placed again

- **Where:** `agents/director_movement.py:3046-3050` (no step -> `held: "no passable route"`), the
  retirement set in `persist/commit_scene_state.py:2327-2331` (`arrived` + `interrupted` only); no
  age, departure or dormancy check anywhere (`leg["turn"]` is written and never read).
- **Reproduced:**
  ```
  approach {Coyle: {to_room: tavern, turn: 3}}, Coyle in no room
  -> {"held":[{"subject":"Coyle","reason":"no passable route"}]}       (kept, silently)
  Coyle placed on the quay again ->
  -> {"advanced":[{"subject":"Coyle","from":"quay","to":"tavern",...}],"arrived":["Coyle"]}
     "Travel continues: Coyle declared a walk to 'tavern' and this beat did not stop it ..."
  ```
  `commit_scene_state.py:2045-2047` notes that departures leave stale positions, so a departed body
  that keeps one may be walked, and offered to the resolve author as `travel_in_flight`, every silent
  beat.
- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED mechanism; PLAUSIBLE on live data (departure
  handling of positions not traced).
- **Fix:** retire a leg whose subject has no room (or is dormant/departed) as `interrupted` with a
  reason; optionally age it by `turn` (an owner-named limit). Test: the snippet's leg is retired.

### F12 — `already_happened`'s row fallback hands the resolve the engine's bookkeeping row as something that happened

- **Where:** `agents/director_prose.py:262-274`: the fallback (taken whenever the stage refused conduct
  or a walk waits) joins every asserted `causal_ledger` row's `event`, including the places row
  (`room_event`: "The places this beat establishes.", commitment asserted). `is_places_row` exists for
  this and is not used here.
- **Reproduced:** `already_happened(...)` -> `'The places this beat establishes. Rhona sits at the kitchen table.'`
- **Severity:** WRONG-SCENE (minor: a meta sentence in the resolve author's input). **Confidence:**
  CONFIRMED (given a ledger holding the places row, which every beat that builds or installs a room has).
- **Fix:** skip `is_places_row(row)` in the fallback. Test: the snippet returns only Rhona's row.

### F13 — The room designer's `inspect_rooms` silently inspects only the first six ids, and iterates a string id character by character

- **Where:** `agents/director_rooms.py:386` (`for rid in list(room_ids or [])[:6]:`), called from
  `2013-2015` with `args.get("room_ids") or []`.
- **Scenario:** a designer asks for eight rooms: two vanish without a word (`_fit_inspection` names
  only rooms cut by size, under `not_shown`); asked `"room_ids": "kitchen"`, it gets six
  `{"refused": "no such room"}` for `k`, `i`, `t`, ...
- **Severity:** SILENT-NOOP (minor). **Confidence:** CONFIRMED by reading.
- **Fix:** accept a string as one id, and name ids past the cap in `not_shown`. Test: eight ids ->
  six records plus two named.

### F14 — The room designer's `remove_rooms` / `remove_adjacent` tools are not in its manifest and take an undocumented `items` argument

- **Where:** `agents/director_rooms.py:113-154` (`ROOM_TOOLS`: inspect/draft/view/check/submit only),
  `2031-2034` (`elif tool in ("remove_rooms", "remove_adjacent") and isinstance(args.get("items"), list)`).
  The sheet (`llm/prompts.room_author_prompt`) ships the spatial `remove_rooms`/`remove_adjacent` chunks,
  which teach the state-diff shape (`remove_rooms:[room_id]`), and the card tells the designer the tools
  are in `tools`. A call shaped as the chunk teaches is refused as "unknown tool".
- **Severity:** DEAD (a path no documented call reaches). **Confidence:** CONFIRMED by reading (no test
  exercises it).
- **Fix:** either list both tools in `ROOM_TOOLS` with their argument, or stop shipping the two chunks to
  the designer (the encoder keeps both channels). Owner's call which.

### F15 — The rooms-in-view job's designer is told it has records and indexes it is never handed

- **Where:** `agents/director_rooms.py:2943` (`payload = {"prose": "", "note": note, "develop": {...}}`);
  `_groundwork` adds `out["rooms"]` only when `payload.get("rooms")` is a dict (`1619-1622`).
  `room_author.txt` INPUT: "identity_index and world_index ... `rooms` holds the stored records of the
  rooms in `surroundings`". The job passes neither the spatial slice, `world_index` nor `identity_index`,
  so `surroundings` reach it as the short projection only (`_inspect` non-whole: name, desc[:400],
  extent, edges, map) and every record costs an `inspect_rooms` step.
- **Severity:** STALE-DOC (card vs job payload). **Confidence:** CONFIRMED by reading; impact on design
  quality/steps PLAUSIBLE.
- **Fix:** give the job the records `_groundwork` would keep (it holds the scene), or say in
  `room_prepare_note` what the job's payload lacks.

### F16 — `obligations` is retired only by not being asked: the docstring still describes its question, and a stray write is still dispatched and committed

- **Where:** `agents/director_prose.py:567-572, 590-593` (`_jev_state` docstring and the "ALREADY OWED"
  line; no production caller passes `owed` -- `director_prose.py:4718` and `director_repair.py:914`
  do not; only `tests/test_prose_contract.py:1265`), `156` (`RETIRED_CHANNELS`), `5040-5043` (the
  unowned check counts `obligations` as owned), `5067-5075` (`dispatch` scopes any written owned
  channel). `persist/commit_ledgers.causal_obligation_ops` still opens debts from the Director's
  transform history.
- **Severity:** STALE-DOC + DEAD parameter; silent acceptance PLAUSIBLE (an unprompted write is unlikely:
  its chunk never ships).
- **Fix:** drop the `owed` parameter and paragraph; refuse `RETIRED_CHANNELS` in `run` beside the
  unowned check, out loud.

### F17 — `bind_new_places` offers the decision model only the first 250 rooms, an unnamed cap

- **Where:** `agents/director_prose.py:1614` (`for rid, room in list(candidates.items())[:250]`).
  Exact-fold matches run over all candidates, so only a `new:` reference that needs the model past the
  250th room is lost (left unbound, its positions dropped by `bodies_stand_in_rooms`, warned).
- **Severity:** SILENT-NOOP (cap; the owner's ask-before-limiting rule). **Confidence:** CONFIRMED by
  reading.
- **Fix:** name it as a constant, and order candidates by relevance (author's rooms, rooms in play)
  rather than dict order.

### F18 — `DESIGN_PROSE_CONTRACT.md` states a threshold and a no-retry rule the code no longer has

- **Where:** `docs/design/DESIGN_PROSE_CONTRACT.md:40-41` "`prose_contract_threshold` (default 0.3)" vs
  `agents/director_prose.py:87` `DEFAULT_THRESHOLD = 0.5`; `:121-127` "No author-side retries" vs
  `carry_every_quoted_line` and `aim_by_their_view` (both re-ask the author, `director_prose.py:417-548`).
  `:44-49` says the encoder reads the hands' "existing, unmodified chunks" while `:106-114` of the same
  note says it has its own card.
- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.

## Efficiency

1. **`reconcile_rooms` makes a room-role model call whenever the author built anchored rooms and the
   encoder minted ANY named object, wherever it stands** (`director_prose.py:3700-3713`). Only an
   object that lands in an authored room can duplicate one of its fixtures. Prefilter `objects` to those
   the events place in `rooms_answer["rooms"]` (`mint_source_rooms`, `inventory_ops.to_id`,
   `positions`) and skip the call when none. Hot: every beat with a room author and a new object (a
   lantern picked up in the room the player stands in while the author builds the next one). Gain: a
   whole model call (seconds and a few k tokens) on those beats.
2. **Every designer merge deep-copies the town twice** (`director_rooms.py:189-196`, `_merged`):
   `merge_scene_with_diff(copy.deepcopy(scene), {"rooms": copy.deepcopy(rooms)})`, and
   `merge_scene_with_diff` already deep-copies both its scene and its diff (`spatial_merge.py:1909-1923`;
   the causal branch copies too). Hot: every `_Reading` entry, every refit/doorway search base, every
   `_predevelop_run` step, both in the beat's worker thread (beside the encoder, competing for the GIL)
   and in the job. Gain: half the copying of a 33-room town per merge; one-line fix.
3. **`install_prepared_rooms` runs at the start of every interpret whose cache is non-empty**
   (`director_rooms.py:2521-2532`): `actors_ahead` (an `active_cast` read) and `rooms_in_reach` (sight
   and heading) for the player and every placed cast member, then the job repeats the same reach on
   commit. Unmeasured here; on the critical path of every beat in a story with prepared designs. A
   per-scene memo, or skipping when no cached id is a stub of the scene, would cut it.
4. `encode`'s widening rebuilds the whole `encoder_payload` (`director_prose.py:4048-4052`: every owner's
   slice, `_scope_rooms_in_play`, `room_aliases` -> `registry_rows`, extension records) instead of adding
   the new owners' slices to the first. Per widened stage.
5. `director_repair`'s `select_channels` call (`director_repair.py:914`) asks the walk questions, the
   time-of-day and where-each-is lines and every part against a sentence subset, and keeps only
   `selected`/`parts`: wasted decision-model questions and a `simulation_clock` read per repair.
6. `pressures_ended` (`director_prose.py:5150-5186`) is a second decision request over the same resolve
   passage `select_channels` already sent; it could ride the same battery (the state then carries the
   `_jev_state` lines -- the owner's call whether that changes the pressure answers).
7. `bind_new_places` repeats the same <=251-criterion map in every unbound reference's question
   (`director_prose.py:1612-1623`), N x ~40k characters to Jev; restricting candidates to authored rooms
   and rooms in play shrinks it. Rare beats only.
8. `_heard_this_beat` runs a full un-memoized `merge_scene_with_diff(..., causal_worlds=...)` (deep copy
   per step) per follower whose target it did not see (`director_movement.py:1104-1108`); rare.
9. `rooms_named_in` compiles one regex per room spelling per encoder payload (`director_prose.py:961-968`
   via `name_boundary_regex`, which relies on `re`'s 512-entry cache): in towns with more than ~250
   room spellings the cache thrashes on every payload build (first call, widening, each repair).

**Model calls per beat on this path (Q7).** Per stage: the author (1; +1 at interpret when a quoted
line is left out -- the SAME payload re-sent by design, relying on sampling at 0.4; +1 when an
unperceived person is named, with a note); Jev selection (1 batched request); the lot architect (0-1,
interpret or resolve, when a lot is entered); the room author (0-8 steps, each step's clean check may
add one Jev finish call per owed room; +1 reconcile; or the serial fallback); Jev place binding (0-1);
the encoder (1; +1 widening); the repair pass (Jev checks + encoder repairs + one more Jev selection);
at resolve `pressures_ended` (1). Minimum six model calls a beat (2 author, 2 Jev, 2 encoder). The only
call repeated with identical input is the quoted-line re-ask (intended). Between turns, each frame's job
adds the lot architect (<=1), the layout tier, and up to `PREDEVELOP_PER_TURN` (4) designer runs.

## Already registered

- **At resolve the walk floor sees only the minds that declared**; a non-declaring cast member walked by
  another's declaration walks as a figure -- UNBUILT_PIPELINE §1.227 residuals. (F7 is the other half:
  declarers exempt.)
- **`the_account_places_its_own_body` would read a throw onto a fixture across a doorway as a walk** --
  §1.227 ("Waiting on the owner's ruling"). Same class, not named there: a pose `relative_to` naming a
  fixture of the next room (the card says `relative_to` names a co-located anchor; an encoder that
  turns her "to" a fixture seen through an arch walks her there, `director_prose.py:2544-2581`).
- An event recorded as a cast member's own conduct is dropped whole with any player walk inside it --
  §1.227 residuals.
- A declaration of stillness read as silence by `_travel_continues` -- UNBUILT_PIPELINE §1.133 (code
  landed 2026-09-28, replay outstanding). The walk-stop question -- §1.1 item 2 (closed).
- The resolve's prose-reading floors skipped on beats with rows -- §1.1 item 3.
- Encoder payload room scope residuals (`room_name_words` reads only a-z, so a partial Japanese room
  name is not found; the 4-hop radius; the room author's `elsewhere` repeat) -- §1.188 (c)-(e).
- A lot entered before the job reached it is built room by room, never laid out; one lot a run on a
  street of open doors; names left as ids -- UNBUILT_WORLD §2.43 (lots bullet).
- The rooms chunk tells the designer to furnish planned rooms "in view"; `room_done_missing` false hold
  -- UNBUILT_WORLD (§2.43 area, lines 3062-3080).
- No within-room approach INTENT ("she crosses to the hearth") -- UNBUILT_WORLD §2.15. Note: its text
  ("room-level `scene.approach` is the only staged-movement memory there is") is stale since
  `walk_within_room` records within-room legs; F3 is what then happens to them.

## Structure notes

Monoliths in miniature: `director_prose.run` (383 lines, 4670-5052), `a_walk_is_its_owners` (239),
`encode` (151), `the_account_places_its_own_body` (139), `select_channels` (138);
`director_movement._apply_following_movement` (452, 1675-2126), `_reconcile_near_group_positions`
(~290), `_travel_continues` (~190), `walk_declared` (~135), `walk_within_room` (~135);
`director_rooms.design_rooms` (~266), `_doorways_that_fit` (~176), `_predevelop_run` (~200).

Natural seams:
- `director_prose`: (1) channel selection -- `candidate_channels`, `_RECORD_FACTS`, `BODY_PLACING_PARTS`,
  `_jev_state`, `where_each_is`, `walks_in_flight`, `select_channels` (77-776); (2) encoder payload
  scoping -- `identities_with_figures` .. `encoder_payload`, `implied_tools` (781-1447); (3) room-author
  glue -- `_isolated` .. `bodies_stand_in_rooms` (1450-2055) plus `mint_source_rooms` .. `room_event`
  (3619-3820); (4) agency floors -- `_MIND_KEY` .. `time_is_the_inputs` (2058-3225); (5) event hygiene
  -- signals, voices, entity keys, emissions, quotations (3228-3573, 4109-4259); (6) time solving --
  `_skip_patches` .. `_spans_until` (4267-4543); (7) conversion and dispatch -- `patch_as_written`,
  `_call_encoder`, `encode`, `ledger_from_events`, `run`, `dispatch`, `attach_record`.
- `director_movement`: payload views (1-290); near-group repair (311-642); following -- ops, perception
  of the one followed, waits, carry (645-2126); reachability and route search (2128-2445); multi-beat
  travel (2447-3312); `crossing_legs` (3314-3372, a perception helper living here).
- `director_rooms`: the design loop and tools; code's passes (pack, doorways, far bearings, sizes);
  groundwork and the doorway search; the between-turns job (2110-3003).

Module-level mutable state: `director_prose._RECORD_FACTS`, `BODY_PLACING_PARTS`, `RIDING_LEDGERS`,
`EMISSION_SWITCHES`, `director_rooms.ROOM_TOOLS`, `ROOM_DONE_BARS` -- all read-only tables, no writer
anywhere in the repo, no `global` rebinds in any of the four files.
`director_rooms.DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY` is an owner's switch constant.

Leftover: `encode`'s `known_parts = set(parts_of([c for c in stage_channels if c in known], ...))` and
`requestable()`'s `c in known` filter nothing (`known = set(stage_channels)`); the comment above them
("EVERY ROOM CHANNEL STAYS REQUESTABLE under a room author") describes a removed exclusion.

Threading (Q5): the in-beat room author runs in one pool worker on a copied context; it writes no
persistent state (draft, `room_record`, `ctx.add_warning`) and every merge it makes deep-copies, so it
does not mutate the shared `sc`. The between-turns job writes the `PREPARED_KEY` world row only through
`_file_prepared` (one `transaction()`, cancellation checked inside), `LOT_RUNS_KEY` through
`_file_failure` (transaction), plan rows through `plant_structure` (its own transaction -- see F6 for
the check outside it), the frame's charter registry through `deal_berths` (no transaction, F6), and
never the scene: designed rooms reach `room_registry` only through the commit's projection (install in
band at interpret, `carry_installed_rooms` for silent and bubble beats), and the commit re-reads a
registry payload under its lock (`commit_room_registry.py:408-421`). The beat path's
`expand_entered_lots` is the one mid-turn writer of plan rows and charter berths outside the commit; a
reroll's checkpoint restore covers `room_registry` (`persist/checkpoints.py` 269-305, 811-821).

## Docs checked

- AGENTS.md, Director contract (255-292):
  - "(2) ... a channel whose subject the world does not hold is not asked" -- holds in code; the rule
    itself is F4's flaw for create-ops.
  - "FAILS OPEN -- every channel granted -- when it cannot answer" -- holds (`select_channels` 733-742).
  - "(3) ONE encoder (role `encoder`, step key `director_specialist`)" -- holds (`_call_encoder`).
  - "ONE widening pass whose answer REPLACES the first" -- holds, plus two keeps of the first answer
    (widening failed, widened answer thinner) that the text does not mention.
  - "(4) ledger_from_events: position is chrono_id, one handle per distinct item name, categories are
    the channels actually written" -- holds.
  - "A channel written at a stage that cannot carry it is DROPPED and said" -- holds via `dispatch`'s
    `stray` (relies on `_run_specialists`).
  - "the room author (`agents/director_rooms.py`, the one model call run in a pool ...)" -- loose: the
    author is up to eight model steps plus decision calls; it is the one WORKER run in a pool.
  - "handed the stored records of the rooms around its places rather than the town's whole ledger" --
    holds in the beat; the job is handed none (F15).
  - "so the commit stays the one scene writer" -- holds for the scene; the plan and charter berths are
    written mid-turn by the beat's lot expansion (F5/F6).
  - "the repair ... does not wait for the room author" -- holds (`run` 4809-4840).
  - "Raw player text never reaches the encoder (`without_raw_text`)" -- holds for `event_inputs`.
- CLAUDE.md: "`SPECIALISTS` ... is now only the owners table" -- holds; "a beat that reaches for a room
  no plan holds raises a typed planning need instead of inventing one" -- not this path: the prose
  contract's room author builds an unplanned place (`reserve_places`, `new:`), by the owner's 2026-09-23
  ruling; `journeys_end_where_the_world_is` is the one place here that defers to a planning need.
- Design.md row "A mind goes only where its own declaration takes it" -- the code matches it, including
  the two exemptions F1 and F7 contest ("unless the world moved it (a `world`/`mechanical` input), it has
  a declaration of its own"); its claim "the resolve's identity index lists only the minds that declared,
  which keep their own walks -- so the only mind it can refuse is the player" holds as code, but F7 shows
  "keep their own walks" is not what is checked.
- `DESIGN_BUILDING_LOTS.md` "Never designed as one room" -- does not hold under F5's race.
- `DESIGN_PROSE_CONTRACT.md` -- stale threshold, retries and card description (F18).
- `llm/prompts.jev_channel_questions` docstring "A channel with no authored question is simply not asked
  -- it cannot be selected" -- `select_channels` SELECTS such a channel always (751-753); moot today
  (every non-retired channel and part has a question in en and ja -- checked by snippet), but the
  sentence reads as the opposite of what the code does.
- `tools/project_check.check_channel_owners` -- guards owners vs `SPECIALIST_CHANNELS`, pack `order` and
  encoder chunks; it does not guard Jev questions per channel (a missing one would be granted every beat).
- UNBUILT_WORLD §2.15 "room-level `scene.approach` is the only staged-movement memory there is" -- stale
  (see Already registered).

### Answers to the assignment's questions, in one place

1. Every owned channel has an encoder chunk and a Jev question in en and ja (snippet over `SPECIALISTS`,
   `schemas.SPECIALIST_CHANNELS`, both packs' `specialists.*.order`, `encoder`, `jev_questions`); all are
   reachable except `obligations` (retired, F16), `vitals` when the story tracks none, `public_evidence`
   at interpret, and the record-gated channels whose create-ops F4 makes unreachable. No category is
   routed without a writer: `ledger_from_events` derives categories from the channels written.
2. A channel no owner holds: dropped with a warning and `record["unowned_channels"]` (`run` 5037-5047);
   a retired-but-owned one (`obligations`) is dispatched silently (F16); an ungranted owned one is
   accepted as the encoder's work (`dispatch`, by design). An entity key the scene lacks: re-keyed when
   the transform's `item` names one held thing and the key is a slipped copy or a name of it, else
   "filed as written" with a warning -- never a planning need; what the objects owner's validation then
   does with a nameless new key was not traced.
3. World moves wrongly refused: F1 (falls, shoves without a contact, passengers, and the whole-event
   drop). Moves wrongly accepted: F2 (spelling), F7 (declarer exemption).
4. Travel record vs positions: F3 (within-room legs retired unwalked), F11 (legs never retired); the
   near-group repair and the relation carry move bodies with no travel entry (no footfalls on the
   record; a cast follower with its own pending approach can be re-placed by the carry after
   `_travel_continues` advanced it -- PLAUSIBLE, rare).
5. See Structure notes, Threading; F5, F6.
6. Cards: no single-story examples found in the cards these modules load; illustrations are marked or
   class-shaped. Code-side English: F9, F10; also `_fold_place` strips English articles and
   `_set_down_where_they_are` parses "'s " possessives (benign for ja, noted).
7. See the paragraph under Efficiency.
