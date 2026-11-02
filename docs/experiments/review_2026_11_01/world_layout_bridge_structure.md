# Audit: `world/layout_bridge.py`, `world/structure.py`, `world/site_plan.py`, `world/frontage.py`, `world/lots.py`, `world/planned_entities.py`

Auditor scope as assigned (2026-11-01, tree at 84f3de23). Read-only; every
reproduction script lives in
`<review scratch>/lb_audit/`
and imports the repository read-only (pure functions, registry readers
monkeypatched in-process). Three read-only queries were run against
`engine.db` with `mode=ro`. One focused test file was run:
`tests/test_a_lot_becomes_its_building.py` -> 16 passed.

## Scope read

Read in full:
- `world/layout_bridge.py` 1-3960 (the grounds floor 2400-2725 and
  `_ground_plan` 1642-2003 read once, line by line; the rest closely), plus
  `git show 84f3de23 -- world/layout_bridge.py`.
- `world/structure.py` 1-3285.
- `world/site_plan.py` 1-1689 (`_layout`'s nested closures 974-1370 read
  for what they decide, not re-derived step by step).
- `world/frontage.py` 1-1216.
- `world/lots.py` 1-119.
- `world/planned_entities.py` 1-714.
- `agents/director_lots.py` 1-450 (needed for question 4; it is the lot's
  only writer).

Read in part, for the paths my files feed: `agents/director_layout.py`
640-730 (`lay_out_buildings`), `agents/director_rooms.py` 2790-2900
(`_predevelop_run`), `story/plot_packages.py` 1074-1084, 1239-1262,
1340-1420, 1470-1530, 1745-1810, 2343-2400, 4065-4160,
`persist/commit.py` 455-560, `persist/commit_scene_state.py` 2725-2800,
`persist/commit_room_registry.py` 300-470, `world/spatial_merge.py` 240-305,
`story/scene.py` 464-545, `core/db.py` 33-140, 224-254, 2993-3148,
`world/layout_solver.py` 105-150, 436-445, `world/spatial_sound_field.py`
2008-2100, 3920-4030, `world/charter_generate.py` 830-870.
Design notes read: `DESIGN_BUILDING_LOTS.md` (whole); registers
`UNBUILT_WORLD.md` §1.127 residual, §2.39, §2.43, §2.44.

## Findings

### F1 — A planned thing stood up during commit PREPARATION is marked rendered in a chat-wide ledger outside the transaction: a rolled-back commit, or any other frame, loses it for good

- **Where.** `world/planned_entities.py:426-456` (inside
  `materialize_plans_in_sight`):
  ```python
  plan["rendered"] = {"entity_id": key, "turn": None,
                      "render": look or name, "by": "engine"}
  ...
  if changed:
      save_planned_entities(cid, plans, frame_id)
  ```
  called from `persist/commit_scene_state.py:2787` inside
  `prepare_scene_commit`, which `persist/commit.py:468-471`
  (`_prepare_turn_commit`) runs BEFORE `with transaction(), registry_session():`
  (`persist/commit.py:556`). And `PLANNED_ENTITIES_KEY = "planned_entities"`
  (`:41`) is not in `core/db.FRAME_SCOPED_WORLD_KEYS`, so every
  `frame_id` threaded through `planned_entities()` / `save_planned_entities()`
  (`:539-545`) is ignored by `_scoped_world_key`.
- **Failure.** (a) A beat in a room where a planned thing stands: the
  preparation mints `entities[key]` into the prepared scene AND writes the
  plan `rendered` to the world row at once. Any of the ~20 commit domains then
  raises; the transaction rolls back the scene, never the ledger. Next beat:
  the plan is `rendered`, so `materialize_plans_in_sight` skips it (`:394`),
  the healing loop skips it (`key not in entities`, `:445`), and
  `plans_in_view` / `reserved_plans` stop offering it (`:624`, `:642`). The
  thing never exists. (b) Frames: a thing first rendered in frame A after a
  split is `rendered` for frame B too (one row), so B never stands it up and
  its Director is never shown the plan. Same for `settle_rendered_plans`
  (`:691`). The module docstring (`:31-32`) says the ledger rides the world
  row "so archive, checkpoint, branch and frame split carry it without their
  own handling" -- a frame split shares it, which is the defect.
- **Verified.** `lb_audit/plans_rollback.py` (ledger stubbed in-process):
  ```
  first commit's preparation minted: [{'plan': ..., 'entity_id': 'police_box', ...}]
  ledger now: {'entity_id': 'police_box', 'turn': None, 'render': 'a blue box', 'by': 'engine'}
  next beat minted: [] entities: []
  offered to the Director: [] reserved: []
  ```
  `.venv/bin/python -c` on `core.db._is_frame_scoped_world_key`:
  `planned_entities False`, `known True`, `scene True`. Read-only scan of
  `engine.db`: 21 rendered plans, every one's entity present in every scene
  row of its chat -- no live loss yet. **CONFIRMED** (mechanism);
  no live instance.
- **Severity.** CORRUPTION.
- **Fix.** Make "rendered" a fact of the scene it was rendered into: either
  write the ledger in a commit domain inside the transaction (prepare only
  computes the mint), and make the key per-era like `plot_packages` (whose
  publish files these plans); or derive "rendered in this frame" from the
  frame's scene (an entity whose `plan_ref.uid` is the plan) instead of a
  stored flag. Test: stub a domain to raise after preparation; assert the
  next beat stands the thing up; and a two-frame test that renders in one
  frame and asserts the other still offers the plan.

### F2 — The house's front door is ranked by English substrings of room names: an "Entrance" loses to any "Great Hall", and every Japanese story falls back to first-by-id

- **Where.** `world/layout_bridge.py:905-924` (84f3de23):
  ```python
  def purpose_of(uid):
      said = purpose_key({"id": uid, "name": names.get(uid)})
      return said if said != "other" else \
          purpose_key(dict(plan.get(uid) or {}, id=uid, name=names.get(uid)))
  def entry(o):
      purpose = purpose_of(o["room"])
      return ENTRY_PURPOSES.index(purpose) if purpose in ENTRY_PURPOSES else len(ENTRY_PURPOSES)
  entrance = sorted(outside, key=lambda o: (bool(o.get("vertical")),
                    abs(levels.get(o["room"], 0)), entry(o), o["room"], o["to"]))
  ```
  `layout_solver.purpose_key` (`world/layout_solver.py:436-444`) is
  `key.replace("_", " ") in text or key in text` over the PURPOSE_AREA keys;
  `ENTRY_PURPOSES = ("entryway", "hall")` (`:142`).
- **Failure.** The rank is global across grounds (the comment says so: "an
  entry's door, then a hall's, then the first by id"), and it is read off
  English substrings: "Entrance", "Entry", "Foyer", "Vestibule", "Genkan" and
  "玄関" all rank `other`; "Great Hall", "Front Hall", "Marshall's Study" and
  "Whitehall Office" rank `hall`. A house with an "Entrance" whose front door
  opens onto the approach and a "Great Hall" with a garden door gets the
  hall's garden door as its front door and its plan named `layout:great_hall`
  -- the very class the commit fixed for chat 179, unfixed for any entry not
  called entryway or a hall, and wholly unfixed in a Japanese story (every
  name ranks `other`, so the old first-by-id rule decides: `back_kitchen`
  before `front_room`). The entrance drives `front`, the approach, the ground
  plan and the second call's compass (`:1123-1126`, `:1344-1351`,
  `:1406-1408`). The module docstring (`:26`) still says "Nothing here reads
  a name or a purpose for meaning."
- **Verified.** `lb_audit/entrance.py`:
  ```
  entrance: {'room': 'great_hall', 'to': 'garden', ...} plan: layout:great_hall
  'Entrance' -> other  'Entry' -> other  'Foyer' -> other  'Genkan' -> other
  "Marshall's Study" -> hall  'Whitehall Office' -> hall  '玄関' -> other
  ```
  Read-only over `engine.db`: all 10 real buildings choose the right door
  (the shrines' genkan purposes say "entryway"/"hall", their rivals are named
  Kitchen/Washroom). **CONFIRMED** (mechanism); frequency outside the
  shrine PLAUSIBLE.
- **Severity.** WRONG-SCENE (written into the plan by the tier).
- **Fix.** Class, not words: decide the entrance from a closed-vocabulary
  answer the model gives per room (the second call already returns
  `purpose` from `vocabulary()["purposes"]`, `spec_from_answers:1416`; the
  first call would need it -- a card change, the owner's call), the way
  `entrance_of` already re-decides from the first call's ground kinds.
  Interim: match whole slug tokens, never substrings (kills Marshall /
  Whitehall). Test: the `entrance.py` plan -> `entrance` room; a ja-named
  plan where the model marks the entry.

### F3 — A lot's entry keeps the whole building's footprint as its own size, and the merge then holds it as "the plan's measurement"

- **Where.** `agents/director_lots.py:254-283` builds the entry's spec with
  no `extent` (the footprint moves to `record["footprint"]`, `:264`);
  `world/structure.py:1644` (`materialize_planned_fringe`)
  `room.update(planned_geometry(spec))` only ever adds; `world/spatial_merge.py:262-264`
  ```python
  if existing.get("planned") and existing.get("extent"):
      _planned_geometry = {"extent", "shape", "parts", "size", "exposure", ...}
  ```
  refuses a describing beat's measurement for any planned stub that carries
  an extent, whoever wrote it.
- **Failure.** The lot is a fringe stub before it is expanded (every path in
  `lots_near` reads rooms the scene holds), minted with the lot's `extent`
  (the building's footprint). After `expand_lot` the plan says the entry has
  no size, the stub still says 10x14, the fringe never takes it off, and the
  beat that describes the shop floor as 4x5 is refused. The entry room is the
  size of the whole building and the building's other rooms are laid around
  it. Fixed only where the tier lays the lot out and writes a solved extent;
  the two live cases the design note records -- the store the beat walked
  into before the job, the tea house the tier refused twice -- are exactly
  the ones where it never is.
- **Verified.** `lb_audit/lot_extent.py`:
  ```
  before expansion, stub extent: {'w': 10, 'd': 14}
  entry spec keys: ['adjacent', 'exposure', 'level', 'lot', 'lot_of', 'name', 'purpose']
  after expansion + next commit's fringe, stub extent: {'w': 10, 'd': 14} purpose: the shop floor
  a beat describes the shop as 4x5; merged extent: {'w': 10, 'd': 14}
  ```
  **CONFIRMED.**
- **Severity.** WRONG-SCENE (persistent).
- **Fix.** The class is "a re-plan that drops a measurement never takes it
  off its stub". Have the fringe record what it laid from the plan (as
  `LAID_LOOKS_KEY` does for far looks) and take a measurement off while the
  stub still holds the value the plan laid and the plan no longer states it.
  Test: the script's sequence ends with no extent on the entry and the 4x5
  landing.

### F4 — An unexpanded lot joined by a door to a planned building is laid out as one room of that building

- **Where.** `world/layout_bridge.py:505-510`:
  ```python
  lot_of = {uid: str(((spec or {}).get(LOT_OF_KEY) or "")) for uid, (_n, spec) in specs.items()}
  ...
  if lot_of.get(a) != lot_of.get(b):
      continue
  ```
  An unexpanded lot carries `lot` but no `lot_of`, so its "lot" is `""`
  exactly like every ordinary room's. The same commit's `_grounds_of`
  (`:728`) tests both keys: `spec.get(LOT_KEY) is not None or spec.get(LOT_OF_KEY)`.
- **Failure.** The inn is planned room by room with a stair; the stable next
  door is a lot (one room standing for a two-storey building), joined to the
  taproom by a door. The stable is unioned into the inn's building, laid out
  as an inn room, and its row written with the inn's site. When an actor
  comes upon it, `expand_lot` replants the row whole (no site, no `layout`):
  `apply_planned_layout` takes the solve off that stub while the inn's other
  rooms keep it, the inn is refused for good ("stands on a plan already"),
  and the stable's own building is laid on a second plan beside it. AGENTS.md
  (row "A building lot") says a lot's rooms are "never merged with a
  neighbour's" -- true only once expanded.
- **Verified.** `lb_audit/lots_group.py`:
  `1) building rooms: ['guest_rooms', 'stable', 'taproom'] lot: None refusal: None`.
  **CONFIRMED** (grouping); the consequences traced by reading
  `structure.apply_planned_layout`/`_take_the_solve_off` and `_building`'s
  holder refusal.
- **Severity.** WRONG-SCENE (persistent plan geometry).
- **Fix.** A room carrying `lot` is its own building: key it
  `lot_of or (uid if LOT_KEY in spec)` -- or keep unexpanded lots out of
  `candidates` (nothing to lay inside one room). Test: the script's plan
  yields a building of `taproom` + `guest_rooms` only.

### F5 — `_walled_by_a_door` excludes the commonest filings: the outside place's exposure unstated, and the sheltered place filed in another part of the map

- **Where.** `world/layout_bridge.py:562-582`:
  ```python
  if not any(b in walled and structure_of.get(b) == structure_of.get(uid) for b, _rec in joins):
      continue
  if any(_exposure(b, specs, rooms) == "open" and {...barriers...} & set(DOOR_BARRIERS)
         for b, rec in joins):
      out.add(uid)
  ```
- **Failure.** The rule its comment states is "a door stands in a wall";
  the code reads "open ground" only as the literal word `open`, and the walled
  neighbour only in the same structure. 338 of 586 planned rooms in
  `engine.db` state no exposure, so a genkan whose door gives onto an
  unstated path stays ground: the hall's door onto the genkan becomes the
  entrance and the genkan is laid as a block of the garden -- the chat 179
  shape. A genkan filed with the grounds (the Room files grounds and house
  apart; chat 179's own latrine is `shrine_grounds` beside a `shrine_house`
  washroom) is never walled either.
- **Verified.** `lb_audit/lots_group.py`:
  ```
  3a) path open:              rooms ['genkan','kitchen','main_hall','upper'] entrance: genkan -> lantern_path
  3b) path exposure unstated: rooms ['kitchen','main_hall','upper']          entrance: main_hall -> genkan
  2)  genkan in shrine_grounds: rooms ['kitchen','main_hall','upper']        entrance: main_hall -> genkan
  ```
  Exposure counts from a read-only query of `room_registry`. **CONFIRMED**
  (mechanism); frequency PLAUSIBLE (no live plan hits both conditions today:
  chat 179's genkan is same-structure with an `open` path).
- **Severity.** WRONG-SCENE.
- **Fix.** Read the far side as "not a room of the building" (not walled,
  not a storey) rather than `== "open"`, and accept a walled neighbour of any
  structure, as `_a_storey_of` already does for a stair. Test: 3b and 2 above
  make the genkan a room and the entrance the genkan's door.

### F6 — `_a_storey_of` refuses a cellar whose storey the plan leaves to its stair, so the cellar stair is laid as a door in an outside wall

- **Where.** `world/layout_bridge.py:593-595`:
  ```python
  level = normalize_level(((specs.get(uid) or (None, {}))[1] or {}).get("level"))
  if level is None or level == 0:
      return False
  ```
- **Failure.** The plan specification itself says "level? ... a stair
  changes it, a door does not" (`story/plot_packages.py:3345`), so a cellar
  reached by a `down` stair with no `level` is a storey below by the engine's
  own rule -- and `_building` infers exactly that a few lines later
  (`:857-870`). Across two parts of the map the helper reads only a stated
  level: the cellar stays outside, its stair becomes an outside door of the
  hall, the case the commit was written for.
- **Verified.** `lb_audit/cellar.py`:
  ```
  cellar level stated -1:         rooms=['cellar','hall','upper'] outside=[('hall','path',None)]
  cellar level left to the stair: rooms=['hall','upper'] outside=[('hall','cellar','down'), ('hall','path',None)]
  ```
  **CONFIRMED.** (Not the registered "a cellar that other buildings' cellars
  open into" case, §2.43.)
- **Severity.** WRONG-SCENE.
- **Fix.** Give an annex room with no stated level the host's level plus
  the stair's step before the test. Test: the second case joins the cellar.

### F7 — A planned thing's projected noise is never taken back: the room goes on sounding after the thing is rendered, moved or switched off

- **Where.** `world/planned_entities.py:263-286`
  (`project_planned_emissions`): rendered plans are skipped (`:267`) and a
  room's `sound` is only ever set (`:285` `room["sound"] = {"level": level}`),
  on the scene the commit persists (`persist/commit_scene_state.py:2739-2740`).
  Nothing pops a room `sound` anywhere in `world/ persist/ agents/ story/`.
- **Failure.** A planned generator projects `loud` onto the plant room. It
  is rendered as an entity and later switched off (its `sound_source`
  cleared): the room's own `sound` record stays, and `sound_sources`
  (`world/spatial_sound_field.py:2073-2081`) carries it as a standing room
  voice across storeys for the rest of the story -- the plan specification's
  own warning, "a noise nothing is making". While it runs it is heard twice
  (room + entity). A plan re-placed (`brief.where` changed) leaves the old
  room sounding.
- **Verified.** `lb_audit/emission.py`:
  `beat 1, the plan unrendered: {'level': 'loud'}` /
  `beat 2, rendered and switched off: {'level': 'loud'}`. **CONFIRMED.**
- **Severity.** WRONG-SCENE.
- **Fix.** Record what was projected (a scene key like `LAID_LOOKS_KEY`) and
  take back a projection whose plan no longer projects it; a room's own
  authored `sound` (with `detail`) is untouched as today. Test: the script's
  two beats end with no `sound` on the room.

### F8 — The planned-room matchers match inside words (confirming the other auditor's F5 and widening the class)

- **Where.** `world/structure.py:2584` (`planned_context` tier 1)
  `if not exact and not any(key in folded for key in keys):`;
  `world/structure.py:2482` (`planned_rooms_named_in`)
  `if any(k == folded or k in folded for k in keys):`; and tier 2's
  "tail of one" rule (`room_words_answer`, `:2585-2596`).
- **Failure.** Tier 1: a planned `inn` answers "the spinning mill",
  "Finnegan's forge", "the inner keep"; a planned `hall` answers "a shallow
  ford". `planned_rooms_named_in` feeds `agents/director.py:612-631`
  `_opening_rooms` -> `_figures_in_view`, so a scenario saying "the spinning
  room of a marshall's house" hands the opening Director the residents of the
  planned inn AND hall as present figures. Tier 2's tail rule crosses word
  boundaries too: "the hall" -> "Marshall House", "the ford" -> "Stafford
  Mill", "the house" -> "Lighthouse". `docs/UNBUILT_WORLD.md` §1.127's
  residual calls this matcher "deliberately exact".
- **Verified.** `lb_audit/substr.py`:
  ```
  'the spinning mill' -> inn   "Finnegan's forge" -> inn   'the inner keep' -> inn
  'a shallow ford' -> hall     named_in: ['hall', 'inn']
  ```
  and an inline `room_words_answer` probe (output in the scratch log).
  **CONFIRMED.**
- **Severity.** WRONG-SCENE.
- **Fix.** Whole slug words in both readers (`f"_{key}_" in f"_{folded}_"`);
  tier 2's compound tail ("Cope's yard" for "Cope's Boatyard") cannot be told
  from "Marshall" without a word list -- name it to the owner rather than
  widen. Test: `inn` vs "the spinning mill" -> None; `named_in` of the
  scenario sentence -> [].

### F9 — The development brief hands the designer the plan's barrier over the one the story settled

- **Where.** `world/structure.py:2059-2071` (`planned_room_brief`):
  ```python
  for edge in list(spec.get("adjacent") or ()) + list(room.get("adjacent") or ()):
      ...
      for key in ("barrier", "dir", "name"):
          if edge.get(key) and key not in entry or key == "name" and edge.get(key):
  ```
  The plan's edges come first and the first writer wins `barrier` and `dir`.
- **Failure.** `_settle_stub_barriers` (`:1845-1885`, "The plan yields and the
  story stands") makes a stub's doorway carry the barrier the room on the
  other side declares: the spine's shut containment door. The brief still
  tells the designer and the beat's Director `open_door`; a design that echoes
  the exit writes `open_door` back onto the stub's side, and the doorway again
  disagrees with itself -- chat 117's measured class, re-entered through the
  brief.
- **Verified.** `lb_audit/brief_barrier.py`:
  `stub edge after settle: [{'to': 'spine', 'barrier': 'closed_door', ...}]` /
  `brief exits: [{'to': 'spine', ..., 'barrier': 'open_door', 'dir': 'w'}]`.
  **CONFIRMED** (the brief); the re-write by a design PLAUSIBLE.
- **Severity.** WRONG-SCENE.
- **Fix.** Read the live stub's edge first for `barrier`/`dir` (the story's),
  the plan's only where the stub holds none. Test: the script's brief says
  `closed_door`.

### F10 — `deal_berths` puts every overflow sleeper in the last bedroom, silently, and materializes an unbounded model integer as a list

- **Where.** `agents/director_lots.py:327-330`:
  ```python
  slots = [uid for uid, n in sleeps.items() for _ in range(int(n))]
  last = list(sleeps)[-1]
  for k, body in enumerate(berthed):
      body["berth"] = slots[k] if k < len(slots) else last
  ```
  `sleeps` comes from `int(item.get("sleeps") or 0)` with no ceiling
  (`:248-253`).
- **Failure.** (a) Twelve bodies berthed at an inn lot, an answer that sleeps
  2 + 2 + 1: the one-bed garret is berthed eight -- past the charter's own
  `BERTH_CEILING` (8, `world/charter_generate.py:47`) that a lot's household
  was allowed to exceed only "waiting for its rooms" -- and `expand_lot` notes
  only "12 sleepers berthed". (b) `"sleeps": 100000000` builds a hundred
  million-element list in the job thread before anything is dealt.
- **Verified.** `lb_audit/berths.py`:
  `moved: 12 Counter({'inn__garret': 8, 'inn__room_a': 2, 'inn__room_b': 2})`.
  (b) read, not executed. **CONFIRMED** (a); (b) PLAUSIBLE.
- **Severity.** WRONG-SCENE (a); CRASH-adjacent (b).
- **Fix.** Deal by arithmetic (no list), cap each room's count at the bodies
  berthed, and put overflow somewhere stated -- round-robin over the sleeping
  rooms, or left at the entry with a note; which is the owner's call (a
  ceiling). Test: twelve bodies over 2/2/1 leave no room past its count + the
  share the policy names, and the notes say so.

### F11 — With no storey stated, a building's ground floor is seeded from the first outside way by id -- an outside ladder included -- and can be laid upside down

- **Where.** `world/layout_bridge.py:854-856`:
  ```python
  if not levels:
      start = outside[0]["room"] if outside else members[0]
      levels[start] = 0
  ```
  `outside` is sorted by `(room, to)` and holds vertical ways too (`:834-852`).
- **Failure.** A loft (`a_loft`) with a ladder down to the yard and a stair
  down to the hall; the hall's front door onto the yard. No `level` anywhere:
  `a_loft` sorts first, is made the ground, and the hall and kitchen become
  storey -1. The solve writes `level: -1` and `elev_m: -3.0` onto both plan
  rows; the front door then opens onto a yard three metres above the hall.
- **Verified.** `lb_audit/levels.py`:
  `levels: {'a_loft': 0, 'hall': -1, 'kitchen': -1}`. Read-only over
  `engine.db`: 0 of 10 real buildings state no storey. **CONFIRMED**
  (mechanism); live frequency today nil.
- **Severity.** WRONG-SCENE (persistent once written).
- **Fix.** Seed only from a non-vertical way onto a place that is not a room
  of the building (and prefer a stated storey of the place beyond); never
  from a vertical outside way. Test: the script's plan -> hall 0, loft 1.

### F12 — A structure's `max_planned` is read two ways, so lot expansions silently freeze its frontier

- **Where.** `world/structure.py:1419` (`plant_structure`: the cap per CALL,
  `len(normalized) > structure["max_planned"]`) vs `:2799-2802`
  (`prepare_frontier_expansion`: the cap on the STRUCTURE's total,
  `counts.get(structure_key, 0) >= ...max_planned`).
- **Failure.** `expand_lot` plants up to 14 rooms per lot into the lot's
  structure and is never stopped by the per-call check; once a village's
  expanded lots take the structure past `max_planned` (default 200), every
  frontier axis of that structure is `retained` with no warning, and walking
  to the village's edge mints nothing -- the beat invents the places
  (`§2.43`'s "a long walk invents the places a plan already holds" in a new
  way).
- **Verified.** Read both readers; not executed. **PLAUSIBLE.** (The cap's
  meaning as a chase bound is registered, `UNBUILT_WORLD.md` §1.153;
  this interaction is not.)
- **Severity.** SILENT-NOOP.
- **Fix.** One meaning: either count rooms a lot expands into outside the
  frontier's quota (they are interior), or check the total in
  `plant_structure` too and say so. The number is the owner's. Test: a
  structure at `max_planned` after a lot expansion still mints an axis (or
  reports why not).

### F13 — Prior ties (`known_by`) are seeded into the ambient frame's `known`, and never taken back on a re-plan

- **Where.** `story/plot_packages.py:1775-1784` (`_seed_prior_ties`:
  `wget(cid, "known")` / `wset(cid, "known", known)`, the ambient frame),
  called from `_apply_plan_entity` (`:1800-1801`) under `publish_package(...,
  frame_id=...)`, which sets no `active_frame_id` (only `_apply_set_far_looks`
  does, `:2359`); the plan itself is filed with `frame_id`.
- **Failure.** Question 6's answer, below. Mechanically: in a story whose
  beats run in a non-None frame, a tie the Room publishes lands in the root
  frame's `known`, not the one its beats read; and a plan re-published
  without a name in `known_by` keeps the recognition seeded before.
- **Verified.** Traced the publish path (`story/room_tools.py:1395-1397` ->
  `publish_package` -> `_apply_operation`); not executed. **PLAUSIBLE.**
- **Severity.** SILENT-NOOP.
- **Fix.** Seed with `wget_for_frame/wset_for_frame(..., frame_id)`; on
  re-plan, take back ties the previous `known_by` seeded that the new one
  drops (keep a record of what the plan seeded). Test: publish in frame N and
  read `known` under N.

### F14 — Stale docstrings

- `world/structure.py:553` and `:1822`, `world/layout_bridge.py:3899` name
  `layout_bridge.ground_refusals`; the function is `ground_breaches`
  (`grep -rn "def ground_refusals"` -> nothing). **CONFIRMED.**
- `world/layout_bridge.py:26`: "Nothing here reads a name or a purpose for
  meaning" (F2).
- `world/planned_entities.py:31-32`: "frame split carry it without their own
  handling" (F1).
- **Severity.** STALE-DOC. **Fix.** Rename in place.

## Efficiency

- **E1 -- `apply_solved_plans` runs on every `get_scene` call.**
  `story/scene.py:521-523` -> `world/structure.py:486-533`: a `_layout_print`
  JSON dump of every sited stub twice, `apply_planned_layout`'s deep copies of
  each solved spec's geometry and anchors, and `strip_one_storey_verticals`,
  even when every stub already stands on its solve. Measured on a synthetic
  scene (`lb_audit/timing.py`): 150 sited stubs, already laid -> **32 ms a
  call**. `get_scene` has 35 call sites in `agents/ persist/ world/ story/`;
  with the tier on by default and lots laying out a building per run, sited
  stubs only accumulate. Gain: memoize per (scene row token, registry token),
  or a fast path that skips a stub whose `laid_out` record already names its
  plan's `layout.plan` and turn. Likely the largest per-beat saving here.
- **E2 -- `plan_buildings` builds every building of the story on every
  rooms-in-view run, quadratically.** `agents/director_layout.py:660-663`
  groups and fully builds (`_building`: grounds walk, `_ground_parts`,
  signature hash) every building, then keeps those near. Inside, each
  building re-sorts and re-scans ALL edges (`:834`, `:857-870`, `:873`).
  `lb_audit/timing2.py` (expanded lots of 8 rooms on one street, grounds on):
  25 lots 112 ms, 50 lots 391 ms, 100 lots **1,485 ms** per run. Gain:
  index edges by source room once; build only the groups that hold a wanted
  room.
- **E3 -- `_joined_apart` recomputes `_apart_habit` on every call**
  (`world/layout_bridge.py:405`, a scan of every spec's adjacency), and it is
  called per (room, place) pair in `_ground_plan` and in `ground_breaches`
  once per seed. Cache per building. Small.
- (Registered: the grounds floor's per-seed `planned_layout` +
  `solved_scene` cost and the frontage's per-commit plane reads -- see below.)

## Already registered

- Storeys and cellar of a lot never held (`director_lots.py:166-171`) -- the
  other auditor's F14. Structure side confirmed: `plant_structure` copies any
  `level` through `planned_geometry` unnormalized (`structure.py:211-212`;
  `planned_geometry({'level': 99})` -> `{'level': 99}`), and `expand_lot`
  bypasses `plot_packages._plan_geometry`, the only clamp. Not a new finding.
- `plant_structure` / `expand_lot` write only the registry: by design
  (`structure.py:1-6`). The window: job path -- from the job's
  `plant_structure` until the next commit's `materialize_planned_fringe`;
  meanwhile registry readers (`planned_room_brief`, `planned_context`,
  `lots_near`) see the building and the scene's stub keeps the lot's purpose,
  exits and size; after the commit the purpose follows, the interior rooms
  come in only once the entry is occupied, and the size never follows (F3).
  Beat path -- from `expand_entered_lots` to that beat's commit. The
  "registry/entity projection" question: planned rooms have no
  `world_entities` rows; the scene-only entity mint is
  `materialize_plans_in_sight`, the other auditor's
  persist_scene_entities F4.
- Lot expanded twice (job + beat): prevented only by the post-call re-check
  `director_lots.py:368`, outside any transaction; reported by the
  director-prose auditor (F6) and the runtime auditor (F4, `deal_berths`
  outside a transaction). Not re-reported.
- `UNBUILT_WORLD.md` §2.43: the chat 179 residual "the basement is never under
  the north half (0 of 4)" -- I found no carrier for it in the bridge: the
  spec carries no relative placement between storeys and `_building` never
  reads the plan's `over`; the register's "*No carrier for ... a cellar under
  one half of the house*" covers it. Also: "the plan's entrance is its
  entrance room's first outside place by id"; "a cellar other buildings'
  cellars open into" (`_a_storey_of`); "one building to a plan, so one to a
  street"; the grounds' cost bullet (16 solves, the floor on each); "a lot's
  footprint is advisory" (the tier's sizing -- F3 is the stub, not the tier).
- §2.39: "One-storey groups get no plan" (`site_plan._derive`) -- confirmed
  in code; a lot is the exception by design (the tier writes decided sites
  for a one-storey lot).
- §2.44: `lay_frontages`' report reaches no reader (both production callers,
  `structure.py:1701`, `:1839`, discard it); "a street the Room measured is
  never lengthened" holds (`frontage._measure_street:646-650`); the per-commit
  retry cost.
- `persist_scene_entities` F4 (scene-only mints) covers `materialize_plans_in_sight`'s
  missing `world_entities` row.

## Structure notes

- **Monoliths in miniature.** `layout_bridge.planned_layout` (~430 lines,
  3015-3445), `_ground_plan` (~360, 1642-2003), `ground_breaches` (~325,
  2400-2725), `spec_from_answers` (~250, 1388-1640), `_building` (~190,
  834-1025); `site_plan._layout` (~395 with eleven nested closures,
  974-1370); `structure.claim_frontier_spaces` (~235), `mint_frontier` (~215),
  `materialize_planned_fringe` (~180), `prepare_frontier_expansion` (~170),
  `hold_planned_fixtures` (~150).
- **Seams.** `layout_bridge`: grouping (228-830) | call payloads (1030-1385) |
  spec (1388-2045) | solve (2047-2400) | grounds floor (2400-2870) | write-back
  (2870-3960). `structure`: plan-row geometry and solve write (1-845) |
  registry parse (845-1000) | fringe and stubs (1500-1900) | frontier mint and
  claims (1100-1350, 2690-3170) | briefs and matchers (1900-2690).
- **Order dependence (question 2).** Decides geometry, first by id/order:
  `_building:855` (ground storey, F11); `:921-944` (entrance: name rank then
  id, F2); `:946`, `:1084`, `:1627` (plan/building name from `members[0]`);
  `_ground_plan` `:1743` (`houses[0]`, the door a walk leaves), `:1796`
  (`opens[0]`), `:1841`/`:1898` (`usable[0]`), `:1921`, `:1959`
  (`joined_rooms[0]`); `entrance_of:3862`; `_door_already:2848`;
  `structure.prepare_frontier_expansion:2727-2731` (`by_name.setdefault`: the
  first row in table order owns a shared spelling, where
  `planned_room_spellings:1928-1937` names neither -- two readers disagree);
  `hold_planned_fixtures:2226-2230` (first scene room sharing a spelling,
  mirroring the commit's dedup); `director_lots._door` (the architect is told
  the plan's first way out only), `planned_rooms_of` entry (answer order),
  `deal_berths` overflow (F10). Deliberate and documented: `site_plan`'s
  `_laying_key`/`_fresh_start` id tiebreak, `_lay_group:1465`,
  `frontage._street_for` (refuses rather than first-by-id). Lot room names
  are not scoped by building ("Kitchen" in every house), so every
  name-keyed reader of the whole plan refuses or picks the first.
- **Facts stored more than once.** The pace: `PACE_M = 0.75` in
  `site_plan.py:213`, `layout_solver.py:82`, `spatial_sound_field.py:1862`,
  `vistas.py:56` (and prose in `spatial_walk.py:28`) -- equal today, free to
  disagree. Bearing unit vectors: `layout_bridge._STEP` and `_UNIT` are the
  same map; `site_plan._UNIT4`; `frontage._WALLS`; `director_lots._SIDES`.
  "Walled": `layout_bridge._exposure` (plan, else scene) vs
  `_ground_parts.walled` and `_apart_habit.walled` (plan only). `_slug`/`_text`
  in `layout_bridge` and `planned_entities` with different rules.
- **Module-level mutable state.** `structure._REGISTRY_CACHE`
  (`threading.local`, written by `registry_rows` only; token-validated via
  `db_read_token`, which sees other connections through `data_version`).
  Everything else is constants (`FALL_BACK_ON_GROUND`,
  `FRONTAGE_MEASURES_STREETS`, the caps).

## Docs checked

| Claim | Where | Held? |
|---|---|---|
| "a lot's building is laid out ... reads `lot_of`: the rooms of one lot are one building and no other's" | DESIGN_BUILDING_LOTS.md, AGENTS.md row "A building lot" ("never merged with a neighbour's") | Expanded lots only; an unexpanded lot merges (F4) |
| "Never another building's ground" | DESIGN_BUILDING_LOTS.md; `_grounds_of:728` | Holds |
| "The entry keeps the lot's uid, name, far look ... its purpose and footprint move onto its record" | DESIGN_BUILDING_LOTS.md; `planned_rooms_of` | Holds for the plan; the scene stub keeps the footprint (F3) |
| "A lot the story has already described is never expanded" | DESIGN_BUILDING_LOTS.md; `_story_described` | Holds |
| "a place entered from open ground through a door is walled" | AGENTS.md layout-tier row; commit message | Only where the outside says `open` and the walled room shares the structure (F5) |
| "the front door is an entry's, `entry`" | AGENTS.md layout-tier row | Only for English names/purposes with "entryway"/"hall" (F2) |
| "Nothing here reads a name or a purpose for meaning" | layout_bridge.py:26 | False (F2) |
| "Planned rooms live in `room_registry.payload` ... the live scene receives only adjacent stubs" | structure.py:1-6 | Holds |
| `write_planned_layout` "never a second scene writer"; all-or-nothing; cancelled job writes nothing | structure.py:651-685 | Holds (checked inside the transaction) |
| "WHAT DOES NOT FIT IS LEFT WHERE IT WAS AND REPORTED" | frontage.py:35 | Left, yes; reported to no reader (registered §2.44) |
| "a street the Room measured is never lengthened at run time" | frontage.py:83-91; owner's ruling | Holds (`_measure_street:646-650`) |
| "A PLAN IS WRITTEN WHERE ITS ROOMS SPAN TWO STOREYS" | site_plan.py:1510-1516 | Holds (registered §2.39) |
| units: `site` x/y in paces, `elev_m` metres, `STOREY_M` 3.0, pace 0.75 m | site_plan.py:12-16, 32, 213 | Holds; pace defined four times |
| "This ledger rides the world row ... frame split carry it without their own handling" | planned_entities.py:31-32 | Misleading: not frame-scoped (F1) |
| "`ground_refusals`" | structure.py:553, :1822; layout_bridge.py:3899 | Stale: `ground_breaches` (F14) |
| UNBUILT_WORLD §1.127 "the deterministic matcher is deliberately exact" | register | False (F8) |

**Question 6 (`known_by`).** Seeding recognition both ways for a tie the
Room states is the owner's ruling of 2026-10-07 ("prior ties via the Room"):
the Room's statement IS the channel (a pre-story acquaintance), and the
validator (`plot_packages._preview_plan_entity:1389-1398`) admits only a
registered character, a person the Room planned, or the player. What `known`
grants is recognition on perception -- a name in place of a descriptor
(`agents/common_identity.py:139`, `:247`) -- never a location or a fact about
the body. **Not a LEAK.** The residuals are F13: the tie is written to the
ambient frame, and a re-plan that drops a name leaves its recognition behind
(a stale author grant, not a perception leak).
