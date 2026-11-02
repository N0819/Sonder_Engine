# Audit: world off-screen & time (offscreen, skip_itinerary, mechanics, weather, day_cycle, living_world, routines, region_events, regions, crowds, background_claims)

Auditor run 2026-11-01, tree at `84f3de23` (worktree-jev-character-tracking, clean). Read-only. No pytest run
(pure snippets on `.venv/bin/python` were enough); read-only measurements on the owner's `engine.db`
(`sqlite3 file:engine.db?mode=ro`). Every snippet quoted below was executed and its output pasted.

## Scope read

Read in full, line by line:
- `world/offscreen.py` 1-2305, `world/skip_itinerary.py` 1-2004, `world/mechanics.py` 1-1658,
  `world/weather.py` 1-1709, `world/day_cycle.py` 1-603, `world/living_world.py` 1-639, `world/routines.py` 1-256,
  `world/region_events.py` 1-461, `world/regions.py` 1-755, `world/crowds.py` 1-783, `world/background_claims.py` 1-598.

Read in part, to trace callers/consumers (not audited as a whole):
- `persist/commit.py` 280-305, 556-700 (domain order), 795-830, 855-892, `commit_crowds` (whole function);
  `persist/commit_mechanics.py` 1-345, 352-378; `persist/commit_scene_state.py` 2530-2600, 2620-2740;
  `persist/commit_entities.py` 140-175, 520-630; `persist/commit_destruction.py` 300-410;
  `persist/commit_room_registry.py` 340-400.
- `story/scene.py` 2286-2340, 2440-2575 (`dialogue_config`); `story/plot_packages.py` 3107-3185, 3640-3660,
  4100-4175; `story/authored_events.py` 160-290; `story/room_tools.py` 672-700.
- `agents/skip_stage.py` 437-470, 500-560, 690-705, 790-880; `agents/director.py` 5664-5730;
  `agents/common_identity.py` 117-200; `mind/skip_memories.py` 160-170, 470-490.
- `core/jobs.py` 91-150, 200-262; `core/db.py` 33-170 (scoped keys); `world/gaps.py` 150-260;
  `world/charter_space.py` 32-71, 202-227; `world/charter_runtime.py` 2838-2955, 4008-4022;
  `world/spatial_light.py` (`room_light`, `_declaration_is_the_only_account`); `world/spatial_frames.py` 1870-1890;
  `llm/schemas.py` 2860-2876 and the `conditions` field types.
- Cards: `language_packs/en/.../encoder/weather.txt`, `encoder/conditions.txt`, `prompts/director_establish.txt`
  (weather clause); grep of both packs for `moon`.
- Registers (by grep + the cited sections): UNBUILT_WORLD §1.228, §2.28, the skip residuals (~4300-4345,
  4535-4590); UNBUILT_PERCEPTION §1.18; UNBUILT_LIVING_WORLD §1.98, §1.105, 120-140, 1620-1660, 3155-3165;
  UNBUILT_PLANNING 535-600, 620-635; UNBUILT_PLATFORM 238-250. AGENTS.md 185-205, 460-465; Design.md rows at 283,
  543, 553, 567; `docs/guides/LIVING_WORLD.md` (grep).

Skimmed only: none of the eleven assigned files.

## Findings

Answers to the assignment's seven questions, pointing into the findings:
1. Clock arithmetic — no wall clock anywhere in the eleven modules (grep for `time.time`/`datetime`/`monotonic`: none);
   hour/second conversions check out (region waves, routines, epochs, drift windows, Span). Defects: F4 (12 a.m.
   read as noon), F14 (non-finite clock claims adopted), F17 (`scheduled_events.due_at` holds turn indices for one
   kind and story seconds for the rest).
2. `stable_event_key` — no new collision in these modules; the charter `(kind, subject, at_hours)` collision is
   registered (§1.98). The helper also folds every falsy part to `""` (`str(part or "")`, mechanics.py:78), so
   `0`/`0.0`/`None`/`False` are one key material (e.g. a charter event at `at_hours` 0.0 and one with no hour) — a
   latent widening of that registered class, not a separate finding. Expiry vs firing: pass (a) fires before
   (c2) expiry and (c1) ticks before (c2) by construction — holds. The crash in that pass is F2.
3. Plans/epochs — the epoch is written only inside `commit_all` (domain `offscreen_epoch`); plan stores can no longer
   be written at all (F11), so "a plan referencing a retired room or dead body" is moot (owner's DB: one plan row,
   chat 78, `completed`). Writers outside the commit transaction in scope: `region_events.apply_wave` (publish path
   and commit TAIL), the dead off-screen landings, and the host's region routes. F5/F6 are the live consequences.
4. `skip_itinerary.Ways` — bounded by `SKIP_ROUTE_ROOMS` 40 (a longer walk reports `no_route`, not `too_far`; a
   named cap, owner's); a way only past a fastened door is `shut_way` (the walk graph is `people_neighbors` minus
   fastened edges; sealed/bricked fold to wall) — holds. The frontier-join residuals are §1.228 (registered).
   New: F1 (company at an off-map label), F7 (a ride never fetches).
5. Weather — drift is seeded per window on the story clock and bounded (`DRIFT_WINDOW_LIMIT` 168); a declaration
   wins its own beat (`sc["weather"] = declared or drifted`, commit_scene_state.py:2692) and stands in the window it
   was written (`written_at`) — holds; the skip's sky uses the same seed (`skip_stage.py:700`). Enum vocabulary:
   the establish card teaches every axis value; the encoder card names the axes without values; neither teaches
   `moon` (F8). The exposure fallback is the real defect (F3).
6. Crowds / region events / claims — crowds capped (`MAX_CROWDS` 8, `CROWD_REPORT_CAP` 4; owner's DB holds no crowd
   rows at all); claims capped in the payload (`MAX_SURFACED` 6) but ratified/contradicted rows are kept forever
   (E5); region hazards never end (F6). News latency math (hops × 3600 s, unmatched = 1 day, declared wins) — holds.
7. Efficiency — the per-beat `scheduled_events` sweep is index-served (`idx_scheduled_events_due (chat_id,
   status, due_at)`, `EXPLAIN QUERY PLAN` = SEARCH); weather is per-scene, but re-normalized per call (E1).

### F1 — Two minds who each spent a skip "home" are told what the other was doing there
- **Severity:** LEAK (a fact reaching a mind through no channel), also WRONG-SCENE. **Confidence:** CONFIRMED.
- **Where:** `world/skip_itinerary.py:1962-1966` (`_place_key`) and `:1969-2004` (`share_company`):
  ```python
  def _place_key(row):
      if row.get("room"):
          return ("room", str(row["room"]))
      folded = _fold(row.get("away"))
      return ("away", folded) if folded else None
  ...
              for other, theirs in by_place.get(key, ()):
                  ...
                  entry = {"who": label_for(observer, other), "doing": doing}
  ```
  An off-map label is the mind's OWN words (`place_stretches`: `away=text`, :788-805). Co-presence is decided by
  string equality of those words across different minds, and words that name a place relative to the speaker
  ("home", "my room", "bed", "work") name different places for different speakers.
- **Failure:** the stage's place resolution leaves "home" off the map whenever the decision model does not place it
  (registered as possible: UNBUILT_WORLD's skip residual "Mellisande's 'home' went off the map ... while her
  cottage stood in the world"). Two cast members who both answer "home" for overlapping hours each receive
  `{"who": <label>, "doing": <the other's doing>}` in `seen`; `mind/skip_memories.py:476-484` turns `seen` into
  `row["with"]`, i.e. a memory of watching the other, and the log is the mind's `the_stretch_just_passed`.
  Snippet (pure function):
  ```
  logs = {'Alice': [{... 'away': 'home',  'doing': 'bathes by the fire', 'seen': []}],
          'Bob':   [{... 'away': 'Home.', 'doing': 'counts the stolen coins', 'seen': []}]}
  it.share_company(logs, lambda o, x: x)
  Alice saw: [{'who': 'Bob', 'doing': 'counts the stolen coins'}]
  Bob saw: [{'who': 'Alice', 'doing': 'bathes by the fire'}]
  ```
- **Verified:** traced `agents/skip_stage._share` (850-876) → `itin.share_company` → `skip_memories.record_rows`.
  Not registered (the design note §"Company" states the label rule; the registers record only that "home" may go
  off-map).
- **Fix (class):** an off-map label is not evidence of a shared place; co-presence off the map should need a
  structural anchor both rows carry (the same lore place `entry_uid` via `subjects.resolve_subject`, or a mutual
  `with` naming each other), never word equality. Test: two logs at `away: "home"` with no shared anchor and no
  mutual `with` produce empty `seen`; two that name each other in `with` still do.

### F2 — A condition whose `expires_at` is not a number stops every later turn from committing
- **Severity:** CRASH (persistent: the story cannot commit again until the row is edited). **Confidence:** PLAUSIBLE
  (path reproduced in code; 0 of 538 live `world_conditions` rows are non-numeric today).
- **Where:** `world/mechanics.py:1569-1577`:
  ```python
  def _expire_conditions(conditions, elapsed):
      for cond in conditions or []:
          expires = cond.get("expires_at")
          if expires is not None and float(expires) <= elapsed:
  ```
  The sibling pass guards the same column (`_tick_conditions`, :1315-1320: `try: ... float(cond["expires_at"])
  except (TypeError, ValueError): expires = None`). The writer stores the encoder's value raw:
  `persist/commit_entities.py:612-624` (`cond.get("expires_at_seconds")`), schema `StateDiff.conditions:
  dict[str, list[dict]]` (untyped items), and the encoder card asks the model for `expires_at_seconds`
  (`encoder/conditions.txt`).
- **Failure:** a model writes `"expires_at_seconds": ""` (or a word). SQLite REAL affinity keeps a non-numeric
  string as TEXT; the next beat's `commit_transit_sweep` (the FIRST domain inside the transaction) raises
  `ValueError`, `commit_all` rolls back, and so does every later beat, because the row is still there. Snippet:
  ```
  sqlite: [("''", '', 'str'), ("'dawn'", 'dawn', 'str'), ("'3600'", 3600.0, 'float'), ('None', None, 'NoneType')]
  mechanics_sweep(..., conditions=[{..., "expires_at": ""}]) -> sweep raised: ValueError could not convert string to float: ''
  ```
- **Fix:** coerce at both ends — `_expire_conditions` reads `expires_at` with the same try/except as
  `_tick_conditions` (one helper for both), and the conditions writer stores `expires_at_seconds`/
  `started_at_seconds` as float-or-NULL, warning on a value it drops. Test: a sweep handed a condition row with
  `expires_at` `''` and `'dawn'` returns ops without raising; a commit of a diff carrying
  `expires_at_seconds: "soon"` stores NULL and warns.

### F3 — The exposure fallback matches substrings, so lamplit indoor rooms go dark at night and get rain
- **Severity:** WRONG-SCENE (sight is gated by light). **Confidence:** CONFIRMED (measured on live rows).
- **Where:** `world/weather.py:706-737` (`_derive_exposure`), also `anchor_exposure` (:947-972) and `_matches`
  (:866-870):
  ```python
  if any(word in haystack for word in _ENCLOSED_WORDS):
      return "enclosed"
  ...
  if any(word in haystack for word in _OPEN_WORDS):
      return "open"
  ```
  `word in haystack` is a substring test: "wood" in "wooden", "roof" in "soundproof", "road" in "broad",
  "yard" in "Halyard's", "park" in "sparkling", "shop" in "shops", "lane" in "planetarium".
- **Failure:** `world/spatial_light.room_light` returns `_darker(sky, declared)` for any room that is not
  `enclosed` once the day has a phase, and only a `sheltered` room may keep a brighter declared word
  (`_declaration_is_the_only_account`). So an indoor room misread `open` is dark at night whatever light it
  declares, and `weather_for_room` puts the rain on whoever stands in it (`falls_on_you`). Read-only measurement,
  `engine.db`: 1,093 live rooms, 666 with no authored `exposure`; 41 read differently under a whole-word match —
  20 falsely `open`, 20 falsely `enclosed`, 1 sheltered/enclosed. Examples:
  ```
  16 tavern_main  "Tavern Common Room ... wooden tables are scattered"     -> open   (open substr: ['wood'])
  20 observation_dome "Observation Dome ... soundproof reinforced glass"   -> open   (['roof'])
  10 halyards_rest_observation_deck "... a broad viewport gallery"         -> open   (['road', 'yard'])
  30 street "a quiet city street at night, li[ned with shops]"             -> enclosed (enclosed substr: ['shop'])
  ```
  Pure check: `_derive_room_facts({'name':'Study','desc':'A wooden-panelled study lit by a fire.'})` → `open`.
- **Contradicts:** weather.py's module docstring rule 2 (:40-45, "never a room darkened by a keyword"),
  `room_exposure`'s docstring (:745, "conservative by construction"), UNBUILT_PERCEPTION §1.18 and UNBUILT_WORLD
  §2.28 ("the failure direction is ... never the reverse"). §1.18 registers that the fallback does the work for
  86% of rooms; it does not register the substring mis-match.
- **Fix:** whole-word matching (the `\b...\b` form `_resolve`/`_fold_legacy` already use) in all three readers; the
  registered §1.18 fix (store the derived exposure at commit) then makes it editable. Test: "Tavern Common Room /
  wooden tables" and "Observation Dome / soundproof glass" read `enclosed`; "Street / lined with shops" reads `open`.

### F4 — "12:40 AM" and "Midnight, 12:00" anchor the story's day at noon
- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED.
- **Where:** `world/day_cycle.py:278-300`:
  ```python
  if hour < 12 and PM_MARKER.match(text[match.end():match.end() + 12]):
      hour += 12
  ```
  There is a p.m. rule and no a.m. rule, so the twelve o'clock hour after midnight reads as noon.
- **Failure:** every reader of a written label goes through this: `label_hour`/`label_phase` (the opening anchor in
  `clock_anchor`, a declared re-anchor), `seconds_until(phase=...)` (a skip "until 12:30 am"), and the skip's
  `Span.offset_hours` (itinerary windows). The anchor lands 12 hours off: `day_phase` midday at midnight → outdoor
  `room_light` lit, `sun_light`, backdrops, and `RESTING_PHASES` (charter errands at night). Snippet:
  ```
  'Late night, 12:40 AM' -> hour 12.666666666666666 phase midday
  '12:30 a.m.'           -> hour 12.5 phase midday
  'Midnight, 12:00'      -> hour 12.0 phase midday
  '00:30'                -> hour 0.5 phase night
  ```
- **Verified:** not in §2.28's residual list.
- **Fix:** an a.m. marker on hour 12 reads 0 (and p.m. on 12 stays 12). A phase word that contradicts the reading
  ("midnight", "night" beside 12:00) is a second, owner-level question. Test: the four strings above read
  0.67/0.5/night, 0.0/night, and "12:30 p.m." stays midday.

### F5 — A region event published unclocked ruins rooms the registry still calls live
- **Severity:** CORRUPTION (two stores disagree on whether a room exists). **Confidence:** CONFIRMED (traced).
  Reported first by the agents_narration_planner auditor; confirmed and extended here.
- **Where:** `world/region_events.py:314-317`:
  ```python
  if destroy and turn_id is not None:
      for rid in report["ruined"]:
          qi("UPDATE room_registry SET retired_turn_id=? ...", (turn_id, cid, rid))
  ```
  `story/plot_packages.py:4136-4137` publishes every unclocked operation with `turn_id=None`
  (`_apply_operation(..., turn_id=None)` → `_apply_region_event` 3133-3149 → `apply_wave`). Waves due later fire from
  the commit tail with `turn_id=getattr(ctx.turn, "id", None)` (`persist/commit.py:815-817`) and DO retire.
- **Failure:** an `at_once` destructive event published from the Writers' Room (or the first ring of a `front`,
  the first step of a `decay`) writes the `world_conditions` row `state: "ruined"`, harms and displaces the
  charter's bodies (berths moved off the "ruined" rooms) — and leaves `room_registry` live, which module docstring
  and `commit_room_registry` (340-350) both call "the sole answer to whether a room is retired". The rooms stay
  walkable and plannable. Worse for a `decay`: `_stand_hazard` restates the same `condition_id` per wave, so the
  next, weaker wave overwrites `state: "ruined"` with `effects["damage"]` — the one record of the ruin is gone.
- **Fix:** retire with the publish's own turn (the latest turn row's id, which a rewind past it un-retires) or
  defer destructive waves to the next commit; keep `ruined` sticky in `_stand_hazard` once written. Test: publish an
  unclocked `at_once` event with `destroy` and assert `retired_turn_id` is set; a decay's second wave leaves
  `state == "ruined"`.

### F6 — A region event's hazard never ends, and warns about every body that walks through it afterwards
- **Severity:** WRONG-SCENE (the Director is shown a passed flood as standing danger) plus a warning on every beat.
  **Confidence:** CONFIRMED for the predicate; "forever" by reading (no ender found).
- **Where:** `world/region_events.py:421-451` (`_stand_hazard`): `INSERT ... started_at, expires_at, next_tick ...
  VALUES(?,?,?,?,?,NULL,NULL,?,1)` with `severity = intensity` (validated `0 < intensity <= 1`). The docstring says
  "No end is authored, because the event authors none".
- **Failure:** `mechanics._condition_states_harm` treats any non-empty `severity` as harm (:1444-1458), so the room
  is a hazard for good; `commit_transit_sweep` warns "The scene states a hazard where X stands..." on every beat a
  body stands there, and the row rides the Director's `active_conditions`. The only engine-side deactivations are
  expiry and `commit_entities` (singular body conditions only); the Director could end it only by re-emitting the
  exact `region:<slug>:<room>` id. Snippet: a row shaped as `_stand_hazard` writes, severity 0.1 →
  `hazard rooms: {'mill': ['flood']}`, `unanswered: ['Ada']`.
- **Verified:** not registered (UNBUILT_PLANNING registers "no rebuilding" for ruins, not hazards that never pass).
- **Fix:** give the hazard an end the event already implies (the last wave's due time plus a span the op states,
  else a named default — the owner's number), or retire a room's region hazard when its last wave lands below a floor.
  Test: a `decay` event's rows are inactive after the clock passes its last wave plus the end span.

### F7 — A stretch lived on a voyage never fetches what lies in another room of the vessel
- **Severity:** WRONG-SCENE ("a false failure becomes canon", the Reach docstring's own words). **Confidence:**
  CONFIRMED (pure snippet).
- **Where:** `world/skip_itinerary.py:1636-1665` (the ride branch of `live_through`):
  `missing = short(item, room, away, start); reason = REASON_NOT_HELD if missing else None` — `fetch_from` is never
  consulted there, while the walking branch (:1721-1729) and `lay_over` (:1804-1810) both fetch.
- **Failure:** snippet with a pot in the galley, the mind on deck, `missing_from`/`fetch_from` stubs:
  ```
  UNDER WAY: failed not_held ['pot'] fetch calls: []
  ASHORE:    done None [] fetch calls: [('deck', 0.0)]
  ```
  `judge_without` can only soften it to `not_known` when the decision model says the work is possible without the
  pot; otherwise the row stays failed and `skip_memories` records it.
- **Fix:** run the same holding-then-fetch sequence in both branches (one helper). Test: the snippet's two runs agree.

### F8 — The `moon` axis is taught by no card, so it reaches a record only through English prose
- **Severity:** SILENT-NOOP + language-pack hazard (WRONG-SCENE: moonlit nights read `dark`). **Confidence:**
  CONFIRMED.
- **Where:** `world/weather.py:580` (`"moon": axis("moon", MOONS, "") or _moon_in_prose(sky) or ...`),
  `_MOON_IN_PROSE` (:173-185), `_moon_in_prose` (:616-630). `grep -rl moon language_packs/` returns nothing: neither
  the establish card's weather clause (which lists every other axis and its values) nor the encoder's weather card
  nor `llm/schemas.py` names it.
- **Failure:** the axis can be set only if a model volunteers a key it was never shown. Otherwise a moon exists only
  when the sky's NAME contains an English phrase ("full moon", "moonlit", "the moon"). A Japanese story never gets
  one (満月 matches nothing), so `sun_light`'s moonlit `dim` (day_cycle.py:252-256) and `room_light` never fire there.
- **Verified:** the registers hold only "the moon never waxes" (UNBUILT_WORLD ~4583), not this.
- **Fix:** add `moon: none|new|crescent|half|gibbous|full` to the establish and encoder weather clauses in both packs,
  and keep `_moon_in_prose` as the legacy reader it says it is. Test: a pack-parity test that every axis
  `normalize_weather` reads is named in each pack's weather card.

### F9 — An explicit `destroy: true` below the threshold is accepted, previewed as ruin, and does nothing
- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED.
- **Where:** `world/region_events.py:128-129` keeps an explicit `destroy` whatever the intensity; `:286`
  `destroy = bool(effects.get("destroy")) and intensity >= DESTROY_THRESHOLD`.
- **Failure:** `normalize_region_event({... 'profile': {'intensity': 0.5}, 'effects': {'destroy': True}})` →
  `effects.destroy True`, `harms_a_body True`; the preview (`plot_packages.py:3123-3131`) warns "ruin harms whoever
  stands in a ruined room" and the package needs the harm grant (`operation_harms`), but `apply_wave` ruins no room
  and, with no `harm` named, harms nobody.
- **Fix:** refuse (or clamp up, said) a `destroy` whose intensity cannot reach the threshold at normalize time, so
  preview and apply read one rule. Test: normalize refuses `destroy: true` at 0.5, or the preview reports no ruin.

### F10 — A place's owed history crosses eras: the ledger ignores the frame each row records
- **Severity:** WRONG-SCENE. **Confidence:** PLAUSIBLE (multi-era story needed; 0 `place_obligations` rows in the
  owner's DB).
- **Where:** `world/living_world.py:530-582` stores `"frame_id": payload.get("frame_id")` per row under the
  unscoped key `place_obligations` (absent from `core.db.FRAME_SCOPED_WORLD_KEYS`); `owed_history` (:585-608) and
  `attach_owed_history` (:611-639) read every row with no frame filter. `gaps.py:246` filters the same kind of row
  by `payload.frame_id`; this reader does not.
- **Failure:** a fuse fired at an ungenerated lore place in one era is handed to `mapping` as owed aftermath when
  the same lore place is generated in another era (lorebooks are chat-wide).
- **Fix:** filter `owed_history` by the asking frame's era (or scope the key). Test: obligations recorded with
  `frame_id` A are not attached when mapping runs for frame B of another era.
- Also here, latent: `owed_history`'s `rows[-max(0, int(cap)):]` (:599) returns EVERY row for `cap=0` — the
  `[-0:]` class `crowds.talk_view` already fixed (crowds.py:751-757). No caller passes 0 today.

### F11 — The off-screen rungs are unreachable; ~1,700 lines of `offscreen.py` and the ladder tables are dead, and four authority docs call them live
- **Severity:** DEAD + STALE-DOC. **Confidence:** CONFIRMED.
- **Where / why dead:**
  - `world/living_world.py:123` `LIVING_WORLD_APPROACHES = ()`; `living_world_allows` (:299-310) returns False for
    every approach not in the tuple, i.e. always. So `apply_plan_ops` (offscreen.py:768-805; it also has no input:
    nothing writes `offscreen_plan_ops`, registered UNBUILT_PLANNING ~626), `advance_reactive_plans` (:936-949) and
    `schedule_agent_ticks` (:2188-2224) return at their gates on every beat.
  - `story/scene.py:2565-2567` sets `config["max_offscreen_actors"] = 0` unconditionally, so `advance_epoch`'s
    stochastic draw (offscreen.py:1126-1134, `eligible` False) and `schedule_profile_ticks` (:1507-1510,
    `ceiling_or_cap`) never run.
  - Snippet: `living_world_allows(cfg, 'antagonist_ladder', 'floor') -> False`, `'ceiling' -> False`,
    `normalize_living_world(cfg) -> {}`, `living_world_levels(cfg) -> []`.
  - Owner's DB: all 50 `offscreen_log` batches carry no `rung` (the pre-rung legacy shape) — no stochastic,
    profile or agent batch has ever been written.
  - Dead in production (reachable only from the closed branches; covered by tests): `stochastic_ticks`,
    `append_offscreen_log`, `_adjudicated_event_ids`, the importance/distance helpers (`derived_importance`,
    `importance_for`, `_non_wall_hops`, `_intention_mentions`, `_intention_owned_by`, `subject_distance`,
    `resolution_for`), the plan helpers (`_declared_plan_actors`, `_basis_is_grounded`, `_normalize_plan_stages`,
    `_truncate_plans`, `_reactive_triggered`), the profile rung (`compose_tick`, `_profile_surface`,
    `profile_summary_record`, `profile_candidates`, `_subject_importance`, `_has_memories`, `land_profile_ticks`),
    the agent rung (`full_agent_candidates`, `agent_context`, `_plans_for`, `agent_proposal`, `agent_adjudication`,
    `compose_agent_tick`, `compose_agent_memory`, `land_agent_tick`). `class _ProfileFallback` (:1224) is never raised
    or caught anywhere. In `living_world.py`: `LIVING_WORLD_DESCRIPTIONS`, `LIVING_WORLD_REQUIRES`,
    `LIVING_WORLD_BUILT`, `effective_depth`, `living_world_levels`, `normalize_living_world` (always `{}`).
  - Still live in `offscreen.py`: `epoch_reasons`, `_epoch_id`, `_beat_id`, `_beat_context`, `advance_epoch` (the
    charter's per-beat `beat_id` depends on it), `_reactive_due_crossed` (reads the plan store every beat).
  - A false comment inside the dead code: `full_agent_candidates` (:1409-1414) says `profile_candidates` "already has
    this shape" (bound first); `profile_candidates` appends and then checks (:1473-1478), so `cap=0` returns one.
- **Docs that describe the rungs as running:** Design.md:543 ("The `stochastic` rung is a real seeded draw ... The
  paid `character_agent` ceiling is built end to end"), Design.md:553 ("Floors of A–E built; C's and E's ceilings
  built ... opt-in per chat via `/api/chats/{cid}/living_world`"), AGENTS.md:190-192 ("THE PAID OFF-SCREEN RUNGS
  REMAIN EPOCH-GATED -- `schedule_profile_ticks`, the stochastic draw and the dormant-actor ticks each cost a model
  call"; the draw costs none), AGENTS.md:462 (the three gates incl. `antagonist_ladder=ceiling`), AGENTS.md:463
  ("`LIVING_WORLD_BUILT` is the declared/built authority" — it is `{}`), `docs/guides/LIVING_WORLD.md` 84-136
  (`offscreen_life`/`max_offscreen_actors` as settings; the approach and gate tables), UNBUILT_LIVING_WORLD §1.105
  :1931 ("Today it still enables ... `schedule_profile_ticks` and `schedule_agent_ticks`") and :1939 (a chat "sits
  at `character_agent`"; `dialogue_config` forces `stochastic`), `story/scene.py:2332-2333` ("the villain ladder's
  floor, which is deliberately kept reachable"), `story/scene.py:2306-2312` (`OFFSCREEN_LIFE_BUILT` comment),
  offscreen.py's module docstring (:10-18, `offscreen_life` as the author's ceiling), living_world.py's module
  docstring (:1, "settings for five approaches and their built floors") and the `LIVING_WORLD_BUILT` comment
  (:126-134, "its adaptive ceiling is built").
- **Fix (owner's call; DESIGN_OFFSCREEN_SUPERSEDED §4 says readers first, keys after):** delete the ladder half of
  `offscreen.py`/`living_world.py` and their tests, keep the epoch/beat-identity domain, and correct the rows above
  in the same commit. Test: `tests/test_charter_every_beat.py` keeps passing (the live half), and a structural test
  that `world/offscreen.py` exports only the epoch names.
- Cross-refs: the extension-contract face of the same retirement is web_routes_extensions F13.

### F12 — The comment that justifies the job's frame pin describes a context `jobs.submit` no longer creates
- **Severity:** STALE-DOC. **Confidence:** CONFIRMED (also flagged by the llm_providers_quality auditor).
- **Where:** `world/offscreen.py:1553-1560` ("The job thread starts with a FRESH contextvars context --
  threading.Thread does not inherit the submitting turn's ... copying the whole context instead would also drag the
  turn's token_sink/cancel_event into background model calls") and :2245-2247 ("the job thread's fresh contextvars
  context would otherwise land frame-scoped writes in the present frame's world").
- **Truth:** `core/jobs.py:126-131` copies the context (`contextvars.copy_context()`; `context.run(_run, ...)`) and
  `_clear_turn_scoped_context` (:202-237) clears the sinks and cancel event but NOT `active_frame_id` (its own
  docstring: "every job producer already sets it"). The pin is now redundant belt-and-braces; the reason given is false.
- **Fix:** reword both comments to "pinned explicitly; the inherited context already carries it". No test.

### F13 — Five comments still describe the retired `scheduled_consequence` gate; two dead parameters/imports ride with them
- **Severity:** STALE-DOC / DEAD. **Confidence:** CONFIRMED.
- **Where:**
  - `world/mechanics.py:731-739` (`_fire_due_events`: "``surface_consequences`` is the story's own
    `scheduled_consequence` depth, and it gates THAT NOTICE"); the only production caller passes `True`
    (`mechanics_sweep`, :1626-1630) and no test passes `False` → the parameter is dead.
  - `world/mechanics.py:1612-1619`: the first paragraph says the surface is "the `scheduled_consequence` depth's to
    decide. Read here, once ... a config that will not read" — the next paragraph says it was retired.
  - `world/routines.py:201-207` ("reads B's own depth ... what 'off' actually switches off") against :244-245
    ("UNCONDITIONAL"); and :214 imports `living_world_allows, living_world_config` which the function never uses.
  - `world/living_world.py:614` (`attach_owed_history`: "Gated by the D setting HERE") against :622 ("UNCONDITIONAL").
  - `persist/commit_mechanics.py:262-264` ("the walk-in notice ... and the re-entry residue read ... Both consult
    this chat's own depth").
- **Fix:** delete the gate language and the parameter/imports. No test needed.

### F14 — A non-finite time claim is adopted as the story clock
- **Severity:** CORRUPTION. **Confidence:** PLAUSIBLE (low likelihood: the encoder's span path already rejects
  non-finite values; a positioned block or an echoed key does not).
- **Where:** `world/mechanics.py:252-301` (`read_time_diff`: `claim = float(td[key])`; `float("NaN")`/`"inf"`/
  JSON `NaN`/`Infinity` parse) → `persist/commit_scene_state.py:2586` `clock["elapsed_seconds"] = claimed`.
  ```
  {'end_seconds': 'NaN'} -> (nan, None, [], False)
  {'duration_seconds': 'Infinity'} -> (inf, None, [], False)
  ```
- **Failure:** with `elapsed = nan`, every `row["due_at"] > elapsed` is False, so every pending consequence, news
  arrival and transit arrival fires at once on the next sweep; the clock then stays NaN (`nan + d`), drift windows
  and day phase stop reading.
- **Fix:** `read_time_diff` treats a non-finite number as unreadable (into `refused`), as `beat_time_from_spans`
  already does. Test: `beat_end_elapsed(100, {'end_seconds': 'NaN'}, floor=True)` returns the floor charge and
  reports the key refused.

### F15 — Displacement sends a whole institution to its alphabetically first standing place, or to nowhere
- **Severity:** WRONG-SCENE. **Confidence:** PLAUSIBLE (downstream reading of `place == ""` not traced).
- **Where:** `world/region_events.py:375-393`: `standing = sorted({post places} | {commons})`; every body whose
  berth is ruined gets `body["berth"] = standing[0] if standing else ""`, and `body["place"] = body["berth"]` when
  it stood in the ruin (a teleport, keeping walk/station — the latter noted by the world_charter_behaviours auditor).
- **Failure:** every displaced body of the institution berths at the same lexicographically first place regardless
  of distance; when no post or commons stands outside the ruin, berth and place become `""` — a body in no room.
  UNBUILT_PLANNING (~555-557) registers "rehoused at its own institution's standing workplace or commons" as design,
  not the `""` case.
- **Fix:** choose by the institution's own graph distance from the ruin and refuse (report) displacement when nothing
  stands rather than writing `""`. Test: a charter whose only commons is ruined keeps its bodies' places non-empty.

### F16 — `scheduled_events.due_at` holds a turn index for one kind and story seconds for the rest
- **Severity:** WRONG-SCENE (planner input). **Confidence:** PLAUSIBLE.
- **Where:** `story/authored_events.py:187-190` writes `due_at = float(int(turn_idx) + due_in)` for `authored_event`
  (a turn number); every other writer stores story seconds (`mechanics`, `living_world.mint_consequences`,
  `charter_runtime._scheduled_row`, `commit_destruction`). `story/room_tools.py:681-690` lists every pending row
  to the Writers' Room as `{"due_at": r["due_at"], "kind": ...}`, `ORDER BY due_at`, with no unit.
- **Failure:** the Room reads "due_at 31" (turn 31) beside "due_at 14400" (four story hours) as one scale. The
  seconds-window readers that skip the kind filter are saved by other filters today (`gaps.py:236-247` needs a
  location or `entity_id` owner, which authored rows lack) — one new reader away from a real mis-window.
- **Fix:** label the unit per row in the Room's listing (or move the turn index into the payload and keep `due_at`
  seconds-only). Test: `inspect_events`' pending rows carry an explicit `due_turn`/`due_seconds`.

## Efficiency

Cheap-to-fix and largest gain first.

- **E1 — `weather_for_room` re-normalizes the scene's sky on every call.** `world/weather.py:1013`
  (`normalize_weather((scene or {}).get("weather"))`), 94 call sites (composer, narration, perception sound/light,
  `Skies.words`), per observer × room × channel per beat. Measured: 10 µs for a record in the engine's own words,
  **228 µs** for a story-named sky/fall or synonym axis words (the A88 design's intended case) — the fold and synonym
  regex loops run every time. Memoize on the record's content (the `_ROOM_FACTS` pattern: key = JSON of the record,
  cleared whole at a cap), or normalize once per scene read. Gain: tens of ms per beat in stories that name their
  weather; nothing for canonical records.
- **E2 — Per-beat reads for rungs that cannot run (F11).** Every beat: `apply_plan_ops` → `living_world_config`
  (wget `living_world` + `dialogue_config`), `advance_epoch` → wget `offscreen_plans` + `offscreen_epoch`. Every
  epoch: `advance_reactive_plans` → `living_world_config`; `dialogue_config`; `dormant_subjects` (a join plus two
  `json.loads` per dormant member — 0.31 ms for the largest dormant sheet on the owner's DB, 23,960 bytes) whose
  result is used only for `len()`. Commit tail per epoch: `schedule_profile_ticks` (`dialogue_config`),
  `schedule_agent_ticks` (`living_world_config`). All inside or right after the write transaction. Gain ~1-3 ms a
  beat; the fix is deletion.
- **E3 — `routines.residue_for` runs on every movement beat for a payload key no model receives** (the
  `destination_residue` dead-delivery is the agents_director_core auditor's F5): `style_guide`, the last-seen
  ledger and an indexed query per move, plus `charter_runtime.residue_facts`. Deliver it or delete the call.
- **E4 — Each unresolved place in a skip carries the mind's whole known-place list as its options.**
  `world/skip_itinerary.py:643-662` (`place_questions`) over `skip_stage.known_places` (every room in the mind's
  `place_graph` plus the building) — uncapped, unlike things (`SKIP_THING_OPTIONS` 64); N unresolved texts × K known
  rooms option strings in one decision request, per mind, per skip. Propose a named cap (owner's) or one shared
  option table per request.
- **E5 — `background_claims.settle_claims` rewrites the whole blob every beat and never drops a settled claim.**
  `:578` `wset` is unconditional once the blob is non-empty; ratified and contradicted rows are kept forever by
  design, so the read-modify-write grows with every settled claim. Owner's DB: one chat, 7 rows, 2,099 bytes —
  negligible today; write only on change.
- Verified NOT a problem: the transit sweep's pending query is index-served (`idx_scheduled_events_due`); the
  weather drift walks at most 168 windows (~5 ms for a year, per its own measurement); `Skies.over` memoizes words.

## Already registered

- Charter `_scheduled_row` `INSERT OR IGNORE` on `(kind, subject, at_hours)` collides two acts by one actor in one
  window — UNBUILT_LIVING_WORLD §1.98. (`stable_event_key`'s falsy-to-`""` folding widens the same class.)
- Frontier-stub joins in the skip (`Ways.frontier_joins` stricter than the class, reads `provisional` alone),
  `weather_depth` reading the raw join, one reading of the medium — UNBUILT_WORLD §1.228.
- Skip residuals: "home" reaches the decision model with nothing to read it by; far end read on the stored clock;
  the things a mind worked on — UNBUILT_WORLD skip residuals (~4304-4345). The two executors disagreeing on the
  final stretch — reported by the world_charter_generation_run auditor (F2/F5).
- Exposure keyword fallback decides 86% of rooms — UNBUILT_PERCEPTION §1.18 (F3 is the substring defect inside it).
- Day-cycle residuals (phase-word table, label is a phase not a reading, sheltered as daylight) — UNBUILT_WORLD §2.28.
- The moon never waxes — UNBUILT_WORLD ~4583.
- Region events: harm cap 12 per WAVE (the constant's own comment, region_events.py:52-55, says "in one story
  hour"), front/decay approximations, no rebuilding, rehousing at the own institution — UNBUILT_PLANNING ~548-566.
- Reactive-plan rung has no writer of `offscreen_plan_ops` — UNBUILT_PLANNING ~626 (its "the character frames are
  the intended writer" is itself stale: living_world.py:104-108 retires the machinery).
- The ladder collapse — UNBUILT_LIVING_WORLD §1.105, §1.108 (texts stale; see F11).
- Obligation retirement at honour time — UNBUILT_LIVING_WORLD ~3160.
- The claims lane is held shut by prompt compliance; `novel_proper_nouns` is capital-letter based (and therefore
  English-only) — UNBUILT_LIVING_WORLD ~126-139.
- `background_claims` is not frame-scoped — UNBUILT_PLATFORM F17 (~242-246); background_claims.py:40-41 still says
  it is.
- `time_diff_duration` reads 0 for an absolute-only block — UNBUILT 1.83 (cited in mechanics.py:625-627).
- Sibling-reported in this run (not registers): region `turn_id=None` (agents_narration_planner; F5 confirms),
  living-world provisioning contract (web_routes_extensions F13), `destination_residue` reaches no payload
  (agents_director_core F5), the offscreen 1553 comment (llm_providers_quality; F12 confirms).

## Structure notes

- `world/offscreen.py` (2,305): the natural seam is a deletion, not a split — ~250 live lines (epoch/beat identity:
  `epoch_reasons`, `_epoch_id`, `_beat_id`, `_beat_context`, `advance_epoch`, `_reactive_due_crossed`) against ~1,700
  lines of retired ladder (F11). `advance_epoch` (~120 lines) is the only live monolith.
- `world/living_world.py` (639): live half = `mint_consequences`, `fired_consequences_at`, `record_obligations`,
  `owed_history`, `attach_owed_history` (~290 lines); the settings ladder above it is dead.
- `world/skip_itinerary.py` (2,004): the docstring already names the seams — Span/itinerary (`Span`,
  `expand_itinerary`, `default_day`, ~330 lines), places and things (`resolve_exact`..`read_thing_picks`, `Reach`,
  `Holding`, ~550), the executor (`Ways`, `journeys`, `rides`, `live_through`, `lay_over`, `judge_without`,
  `share_company`, ~700), `Skies` (~95). `live_through` (~180 lines) is a monolith in miniature with two near-copies
  of the stretch body (ride vs walk) — the asymmetry in F7 lives in the gap between them. `Reach.__init__` ~80 lines.
- `world/weather.py` (1,709): three concerns — the sky (`normalize_weather` ~150 lines, drift), room exposure
  (keyword fallback, `weather_depth`, `exposure_at`, `weather_for_room`) and the ground ledger. Exposure is the seam
  F3 would move with.
- `world/mechanics.py` (1,658): the time-diff vocabulary (`read_time_diff`..`time_diff_duration`, ~450 lines) is a
  separate owner from the sweep (`_fire_due_events`, `_schedule_new_arrivals`, ticks, expiry); a `world/story_clock.py`
  would match how many readers import only the former.
- `world/region_events.apply_wave` (~145 lines): rooms / institutions / evidence-and-news blocks.
- Module-level mutable state: `weather._ROOM_FACTS` (dict, cleared whole at 1,024; sole writer `_room_facts`; keyed on
  record content and observer-free — safe). No other module-level mutable state in the eleven files (offscreen's
  `__getattr__` serves prompt text lazily).
- `region_events.apply_wave` writes `engine_notices` with a bare `wget`/`wset` (:413-417), bypassing
  `commit_common.add_engine_notice`, which the destruction path names "the one writer"; it runs at publish (out of band)
  and in the commit tail, after the sweep's rewrite — it lands for the next beat, but it is a second writer.
- `regions.backfill_regions` writes a per-FRAME `regions` key (:727-741) although `regions` is an ERA key
  (`core.db.ERA_WORLD_KEYS`); a one-shot migration, so only an old archive imported now would meet it.

## Docs checked

| Claim | Where | Result |
|---|---|---|
| Due times compare against the SIM clock only, never wall clock | mechanics.py module docstring | HOLDS (no wall-clock call in any of the 11 modules) |
| Event ids are stable hashes of (kind, chat, frame, subject, turn) | mechanics.py docstring | HOLDS for transit/news; consequences add the declaration index |
| A fired fuse writes a notice only where the player stands (walk-in) | living_world.py header; `_fire_due_events` | HOLDS (plus `presence_rooms` for a playerless frame) |
| The obligation ledger's ONLY reader is mapping | AGENTS.md:463 | HOLDS (`attach_owed_history` called only at agents/mapping.py:504) |
| `LIVING_WORLD_BUILT` is the declared/built authority | AGENTS.md:463 | STALE (it is `{}`; F11) |
| A paid off-screen tick needs card opt-in + `offscreen_life=character_agent` + `antagonist_ladder=ceiling` | AGENTS.md:462 | STALE (the approach does not exist; unreachable; F11) |
| The paid off-screen rungs remain epoch-gated; each costs a model call | AGENTS.md:190-192 | STALE (none can run; the stochastic draw costs none; F11) |
| Off-screen world ticks: stochastic rung live, `character_agent` built end to end | Design.md:543 | STALE (F11) |
| Living world: floors of A-E built, C/E ceilings built, opt-in per chat | Design.md:553 | STALE (approaches `()`; F11) |
| The off-screen institution advances every beat | Design.md:283 | HOLDS (`advance_epoch` stamps `beat_id` on every path, including no-epoch and bootstrap) |
| `offscreen_life` and `max_offscreen_actors` are settings | docs/guides/LIVING_WORLD.md 84-86 | STALE (`dialogue_config` forces both, scene.py:2565-2567) |
| The toggle still enables `schedule_profile_ticks`/`schedule_agent_ticks` | UNBUILT_LIVING_WORLD §1.105 :1931 | STALE (F11) |
| An unrecognised room never gets darker by a keyword | weather.py:40-45, 745; UNBUILT_PERCEPTION §1.18; UNBUILT_WORLD §2.28 | FALSE (substring matching; F3) |
| Weather drifts deterministically on the clock, one walk per window | weather.py rule 3 | HOLDS |
| A declaration stands in the window it was written | weather.py `DECLARED_STEP` | HOLDS (`declared or drifted`; `written_at=prev_clock`) |
| Job threads start with a fresh contextvars context | offscreen.py:1553, 2245 | STALE (F12) |
| The surface of a fired fuse is the `scheduled_consequence` depth's | mechanics.py:731, 1612-1619; routines.py:201-207; living_world.py:614; commit_mechanics.py:262-264 | STALE (F13) |
| Region ruin = the room retired in `room_registry` | region_events.py header | FALSE on the publish path (F5) |
| `background_claims` is frame-scoped | background_claims.py:40-41 | FALSE (registered UNBUILT_PLATFORM F17) |
| The one consumer of routine residue is the Director's staging payload | routines.py:19-23 | STALE (reaches no model; agents_director_core F5) |
| `profile_candidates` bounds before appending | offscreen.py:1409-1414 | FALSE (appends then checks; dead code) |
| Crowd heading is spent before this beat's ops | commit_crowds docstring | HOLDS (`advance_crowds` then `apply_ops`) |
| News latency: one hop = one story hour, unmatched = a day, declared wins | mechanics.py:636-661 | HOLDS (commit_destruction.py:323-333) |
| Harm capped at 12 bodies in one story hour | region_events.py:52-55 | STALE (per wave; registered UNBUILT_PLANNING) |
