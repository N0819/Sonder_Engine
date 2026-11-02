# Audit — world/ misc + the four causal modules (2026-11-01)

Auditor scope: `world/landscape.py`, `world/causal_verification.py`, `world/causal_program.py`,
`world/causality.py`, `world/causal_completion.py`, `world/paradox.py`, `world/place_purpose.py`,
`world/subjects.py`, `world/survival.py`, `world/gaps.py`, `world/planning_needs.py`,
`world/vistas.py`, `world/comfort.py`, `world/place_names.py`, `world/stimulation.py`,
`world/exposure.py`, `world/scene_memo.py`, `world/beat_ledger.py`, `world/degradation.py`
(9,065 lines). Read-only; every snippet ran on `.venv/bin/python` against in-memory scenes or a
scratch DB under the scratchpad; the owner's `engine.db` was opened `mode=ro` only.
Scripts: `<review scratch>/wm_audit/`.

## Scope read

Read in full, every line: all nineteen files above —
landscape 1-1761, causal_verification 1-1189, causal_program 1-417, causality 1-402,
causal_completion 1-165, paradox 1-655, place_purpose 1-554, subjects 1-505, survival 1-489,
gaps 1-459, planning_needs 1-439, vistas 1-391, comfort 1-340, place_names 1-267,
stimulation 1-239, exposure 1-232, scene_memo 1-206, beat_ledger 1-184, degradation 1-171.

Read in part, to trace callers (not audited): `agents/director.py` 1639-1700, 2415-2460,
3740-3975, 4100-4145, 4877-4930, 6590-6650, 6930-7020; `agents/director_movement.py` 1085-1125,
1500-1560, 1930-1960, 2566-2660, 3165-3195; `agents/director_prose.py` 4546-4680;
`agents/director_evidence.py` 1841-1870, 3514-3600; `agents/mapping.py` 150-330, 520-600;
`agents/perception.py` 1818-1900, 5390-5430, 6255-6320; `agents/character.py` 4340-4372,
4640-4700; `agents/common_rooms.py` 760-860; `agents/common_beat.py` 868-900;
`world/spatial_merge.py` 1817-1960, 2090-2110; `world/spatial_identity.py` 92-200, 279-292,
498-593; `world/mechanics.py` 1290-1420, 1600-1645; `world/charter_enrol.py` 302-362;
`world/charter_runtime.py` 794-823; `persist/commit.py` 560-700; `persist/commit_background.py`
2483, 2660-2700, 2975-3035; `persist/commit_scene_state.py` 1985-2010, 2395-2410;
`persist/checkpoints.py` 900-960; `web/app.py` 6405-6460; `story/room_frontier.py` 390-420;
`story/room_slice.py` 415-440; `agents/story_planner.py` 210-221, 2940-2960;
`language_packs/en/cards/system_prompts/encoder/core.txt` (the `look` field) and
`prompts/interpret_repair.txt`; `docs/UNBUILT_*.md` sections cited below;
`docs/design/DESIGN_PARADOX_CONSEQUENCES.md` §2, §5.

Not read: `world/planned_entities.py` (another auditor, by assignment).

## Liveness: the four "causal" modules are NOT remnants

The 2026-09-27 deletion removed the causal Director (ledger author + five specialist calls);
the encoder path kept the whole transform/ledger/chrono machinery. Evidence command (the full
survey, every top-level symbol of all 19 modules, prod/test split):
`.venv/bin/python scratchpad/wm_audit/liveness.py world/<mod>.py ...` (output saved at
`scratchpad/wm_audit/liveness_out.txt`), cross-checked with
`grep -rn --include='*.py' -E "from world\.(causal_verification|causal_program|causality|causal_completion) import" agents core llm world mind story dressing persist web extension_runtime tools`.

| Module.function | Production callers (file:line, current tree) | Verdict |
|---|---|---|
| `causality.compile_transforms` | `agents/director.py:3954` (`_run_specialists`, per owner), `:4118` (the bound recompile), `:6634` (speech channel) | LIVE — the encoder path's recompiler |
| `causality.LIST_CHANNELS` / `LIST_MAP_CHANNELS` / `ATOMIC_CHANNELS` | internal (`_merge_channel`, `_stamp_from_event`); `causal_program.py:348` | LIVE |
| `causality._merge_channel` (private, imported) | `agents/skip_work.py:692`, `causal_program.py:259,308` | LIVE |
| `causal_program.bind_items` | `agents/director.py:4115,4879`, `agents/director_repair.py:377` (`native_failures`), `agents/skip_work.py:341` | LIVE |
| `causal_program.fold_steps` | `agents/director.py:1649`, `persist/commit_scene_state.py:2005` | LIVE |
| `causal_program.event_worlds` | `agents/perception.py:6967,7811` | LIVE |
| `causal_program.program_from_history` | `agents/director.py:4138` | LIVE |
| `causal_program.program_steps` | `world/spatial_merge.py:1861` (every program merge), `agents/director.py:1649`, `agents/director_evidence.py:1858` | LIVE |
| `causal_program.prune_program` | `agents/common_acts.py:620` (was `agents/common.py:699` before the in-flight split) | LIVE |
| `causal_completion.execution_receipt` | `world/spatial_merge.py:1895` (per step, whenever a caller passes `causal_worlds`) | LIVE |
| `causal_completion.annotate_event_execution` | `persist/commit_scene_state.py:2404` | LIVE (but its output field has no reader — F15) |
| `causal_completion.event_execution_statuses` | `agents/perception.py:6970,7815` | LIVE |
| `causal_verification.verify_patch` | `causal_completion.execution_receipt` (above) | LIVE |
| `causal_verification.TRANSIENT_EVENT` / `LEDGER_LIMIT` | `causal_completion.py:9` | LIVE |
| **`causal_verification.verify_causal_worlds`** | **none** — tests only: `tests/test_causal_verification.py:61`, `tests/test_causal_overlay_verification.py:113` | **DEAD** (F16) |

Every private helper in the four modules has a live internal caller. Two BRANCHES look
unreachable from production (not functions): `compile_transforms`' transform-level
`legacy_object_id` path (`causality.py:289,310,394`) — no producer writes a transform-level
`object_id` any more (the encoder's transforms carry `item`, converted to `item_id`;
`speech_transforms` carries `item_id`) — and the `row.get("event_id")` chrono fallback
(`causality.py:233`, `causal_program.py:302`), the old causal ledger's key. Both are plausibly
kept for stored-beat replays; flagged in Structure notes, not proposed for deletion without a
replay measurement.

Dead or test-only elsewhere in scope (same survey; string-form references searched with
`grep -rn '"<name>"'` — none found except the deliberate `lost_at` guard):

| Symbol | Refs | Verdict |
|---|---|---|
| `landscape._line_clear` (`world/landscape.py:637`) | none anywhere | DEAD — delete |
| `vistas._PACE_M` (`world/vistas.py:56`) | none anywhere | DEAD — delete |
| `landscape.LOOK_WRITE_REASONS` (`:1500`) | `tests/test_standing_far_looks.py:90,112` only | test-pinned enum of reason codes; keep or move to the test (owner's call) |
| `scene_memo.clear_scene_memo` (`:204`) | `tests/test_scene_memo.py:30,32` only | test helper in production code |
| `degradation.lost_at` (`:153`) | tests only, BY DESIGN (`tests/test_degradation.py:209-226` asserts no engine module references it) | keep |
| `paradox` room field `paradox_consumed` | written `paradox.py:294,308`, popped `:263`, read by nothing in the repo | DEAD state (F4) |
| `beat_events[].execution` | written `causal_completion.py:139`, read only by two tests | DEAD field (F15) |

Everything else surveyed has a production caller (e.g. `drain_planning_needs` is reached through
`schedule_planning_needs`' job closure, `planning_needs.py:436-437`; `vista_verdict`,
`near_field`, `pattern_filler`, `default_vitals` through live internal callers).

## Findings

Tally (primary severity): LEAK 1 (F1) · CORRUPTION 2 (F5, F7) · WRONG-SCENE 6 (F2, F3, F4, F6, F8, F14) · SILENT-NOOP 5 (F9-F13) · DEAD 2 (F15, F16) · STALE-DOC 1 (F17) · PERF 6 (Efficiency). 17 findings.

### F1 — A look at a far place tells the mind the place's real name, learned or not
- **Severity:** LEAK. **Confidence:** CONFIRMED (snippet + the existing tests pin it).
- **Where:** `world/landscape.py:1198-1199`, `:1210`, `:1233`, `:1241`, `:1248`:
  ```python
  label = place.get("name") or (
      str((rooms.get(hit) or {}).get("name") or "") if hit else "")
  ...
  label = rec.get("name") or str((rooms.get(hit) or {}).get("name") or "")
  ...
  label = str((rooms.get(target) or {}).get("name") or target)
  ```
  `place["name"]` / `rec["name"]` are the gated `known_name` (empty for a place the mind has not
  learned). When they are empty the label falls back to the room's CANONICAL name whenever the
  look word matched the room's id or name. The standing view (`far_places`) never does this —
  ruling 3, "a far place is named only once the mind knows it".
- **Why the look word is an id:** the encoder card tells the model to write it —
  `language_packs/en/cards/system_prompts/encoder/core.txt:23`: "A look at a place further off …
  names that place: its id where world_index gives one". The docstring's justification
  ("by its own name, which the actor used and so may hear back", `landscape.py:1153-1155`) is
  false on the engine's own card: the encoder chose the id, and the label is the canonical
  name, not the look word.
- **Repro** (`scratchpad/wm_audit/far_name_leak.py`): Ada knows only `yard`/`lane`.
  Standing view names: `['']`. `looked_far(..., ["gale_green"])` → "To the east, you can see Gale
  Green."; `["orchard"]` → "Toward Widow Marsh's Orchard, the buildings around you stand between
  you and it." — a place name AND a person's name ("Widow Marsh"); the label is never passed
  through the observer's people gate either.
- **Pinned by:** `tests/test_what_stands_between.py::test_a_look_at_a_storey_is_a_look_at_its_building_and_is_answered`
  (known=None, expects "where the bell loft is") and `::test_a_look_at_a_hidden_place_names_what_stands_between`
  (known=None, a look at id `chapel` expects "Toward The Chapel, …"). 19/19 pass today.
- **Fix:** label an unknown place the way the standing view does (its look/ground/building
  height), and say a name only when `known_name(m)` gives one; route any label through the
  observer's gate. Regression test: a stranger's look by id at a named far place yields a line
  with no room name and no person name; retire/rewrite the two pinning asserts.

### F2 — Rumour degradation does nothing in a Japanese story: names, places and counts survive every hop
- **Severity:** WRONG-SCENE (firewall-adjacent: the module's own rule is that hop 3 loses the
  NAME). **Confidence:** CONFIRMED (snippet `scratchpad/wm_audit/degrade_ja.py`).
- **Where:** `world/degradation.py:72-87` (`_PLURAL_NUMBER_WORDS`, an English word list, and
  `_COUNT` with `\b`), `:105` (`_replace_phrases`: `r"%s\b%s\b" % (_ARTICLE, re.escape(phrase))`).
  In unspaced CJK text `\b` never falls between two word characters, so a caller-supplied name or
  place embedded in the claim never matches; kanji numerals are not in the list, and "3人" fails
  `\b` after the digit.
- **Repro:** `degrade("ミラ・ホルトが門の通路で衛兵を三人殺した", 3, names=["ミラ・ホルト"], places=["門の通路"])`
  returns the claim unchanged at hops 1, 2 and 3 (English: "a stranger killed several guards at
  some place"). Then `is_exhausted(4)` stops it — so in Japanese the rumour travels exact until it
  stops. Callers: `story/couriers.py:439,680,762,1002`, `story/carriers.py:1334`,
  `world/charter_mind.py:121`, `world/charter_talk.py:103`.
- **Fix:** match caller-supplied names/places as literal substrings with script-aware boundaries
  (the `name_boundary_pattern` the far layer already uses, `story.character_schema`), and take the
  count vocabulary from the language pack (its linguistics card), never a module tuple; the
  English replacement words (`VAGUE_*`) belong on the pack too. Test: the same claim in both packs
  loses count/place/name at hops 1/2/3.

### F3 — In English the count list garbles rumours ("settled the several", "quarter past several")
- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED (snippet).
- **Where:** `world/degradation.py:72-87`: "score", "couple", "few", "handful" are in
  `_PLURAL_NUMBER_WORDS`; any digit run is a count.
- **Repro:** `degrade(c, 1)` →
  "Mira settled the several with the several from the mill";
  "a several of the guards saw a several of riders";
  "… at No. several Mill Lane"; "They met at quarter past several".
  The module's own docstring (`:60-64`) says a claim that reads as broken grammar "reads as an
  engine fault rather than as vague hearsay"; a time became a crowd.
- **Fix:** the class is "a word list anticipating English" — restrict count redaction to a
  number followed by a noun the caller supplies (or to the typed `count` the engine knows, when
  the claim carries one) and drop idiom words. Test: idioms and times survive hop 1 unchanged.

### F4 — The hazard wound REPLACES a room's description, is cut off on long rooms, and "consumes" nothing
- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED (snippet `wound_note.py` + scratch-DB run
  `paradox_removed.py`).
- **Where:** `world/paradox.py:294-295, 308-309`:
  ```python
  rooms[epicenter]["paradox_consumed"] = True
  rooms[epicenter]["notes"] = (rooms[epicenter].get("notes") or "") + _HAZARD_WOUND_NOTE
  ```
  Reader: `agents/common_rooms.py:780-806` `room_prose` (`ROOM_PROSE_CHARS` at `:811`) returns `notes` FIRST, else `desc`, cut by
  `whole_sentences(…, ROOM_PROSE_CHARS=600)`.
- **Failure:** (a) a room described only by `desc` (268 of 1,093 rooms in the owner's live scenes,
  read-only count) gets `notes` = the wound sentence alone, so every mind is told
  " Something about this place feels wrong now…" INSTEAD of the room (repro: "A low kitchen with a
  black range…" → the wound text, with its leading space); `_restore_consumed` strips it and the
  desc returns only on resolution. (b) A room whose `notes` already exceed 600 characters never
  shows the wound: the appended sentence is cut (repro: 763-char notes → wound absent).
  (c) `paradox_consumed` has no reader anywhere (`grep -rn paradox_consumed` → only paradox.py), so
  "room consumption" / "flagged impassable" (`_restore_consumed` docstring, `:256-258`) does not
  happen: consumed rooms stay walkable.
- **Fix:** carry the wound as its own field the view composes beside the room's prose (and a
  movement floor that reads `paradox_consumed`, or drop the claim), not as a suffix on `notes`.
  Test: a desc-only room under stage 2 still delivers its desc plus the wound; a 700-char room
  delivers the wound.
- Related, registered: `_HAZARD_WOUND_NOTE` is English (UNBUILT_IDENTITY ~l.357); the owner's
  2026-09-21 ruling moves the consequence to the Writers' Room (see Docs checked).

### F5 — Deleting a fixed point leaves its wound running to the ceiling (toll mode: irreversible)
- **Severity:** CORRUPTION (toll) / WRONG-SCENE (hazard, warden). **Confidence:** CONFIRMED
  (scratch DB, `scratchpad/wm_audit/paradox_removed.py`).
- **Where:** `world/paradox.py:507-509, 528`:
  ```python
  anchor = next((p for p in fixed_points(chat_id) if p["anchor_id"] == state["anchor_id"]), None)
  if anchor and _anchor_satisfied(chat_id, anchor):   # never true once the anchor is gone
  ...
  if anchor:
      _force_restore_anchor(...)
  ```
  `web/app.py:6445-6448` `fixed_points_delete` only calls `paradox.remove_fixed_point`; nothing
  clears the frame's paradox slot.
- **Repro:** wound opened in `hall`; host deletes the fixed point; clock 300/600/800 s →
  `stage 1, 2, 3`, `resolved None`, consumed `['hall']` then `['hall','yard']`. In `toll` mode each
  stage runs `_apply_toll`'s `UPDATE memories SET confidence=…` — irreversible by design
  (DESIGN_PARADOX_CONSEQUENCES §5) — for a constraint the host withdrew. Latent: no live story has
  opened a wound (Design.md:568).
- **Fix:** in `_advance_paradox`, an anchor that no longer exists resolves the wound
  (`_restore_consumed` + `_clear_paradox`), or `remove_fixed_point` clears its slot. Test: remove
  the anchor mid-wound; next commit resolves and nothing further decays.

### F6 — A far look's answer names an occluder that is not there
- **Severity:** WRONG-SCENE ("no placeholder answers" ruling: name the real occluder).
  **Confidence:** CONFIRMED (snippets `far_gate.py`, `far_cap.py`, `blind_vista.py`).
- **Where:** `world/landscape.py:1251-1253`, the fallback for a named place the walk never
  delivered: `{"kind": ("around" if <here is open ground> else "walls") …}`, rendered by
  `far_look_hidden_around` = "Toward {label}, the buildings around you stand between you and it."
  The walk discards the real reason at four silent exits: `:795` (blind observer → `[]`),
  `:897` (`REACH_HOPS`), `:916` (another locale), `:923` (open ground behind a wall or shut gate),
  `:966` (`PLACES_GRADED_MAX` = 32, places ordered by `(hops, room id)` so the cut is ALPHABETICAL
  within a hop count). None of them records into `hidden`.
- **Repros:** (a) all-open-ground map, the orchard behind a wall → "the buildings around you"
  (there are no buildings; the wall is the occluder). (b) 40 meadows two hops off around one hub:
  `spoke05` is seen; `spoke39`, identical but past the graded cap → "around". (c) a blind
  observer's look at a visible meadow → "around". (d) `world/vistas.py:391`: a blind body's look at
  a range on a flat cliff top → `"unseen_nearer"` = "To the north, nearer ground rises between you
  and the Grey Range" (`visible_vistas` returns `[]` for blind at `:315`, then the verdict chain
  falls through).
- **Fix:** record each refusal's reason into `hidden` (`{"kind": "wall"|"locale"|"reach"}`), grade
  a looked-at place regardless of the graded cap, and let a sightless observer's look return
  nothing (or a "your eyes" answer) rather than an occluder. Test per exit: a look at a place
  behind a wall names the wall; past the cap it is answered as seen.
- Owner caps named here (do not pick numbers): `PLACES_GRADED_MAX` 32, `REACH_HOPS` 12,
  `LINES_MAX` 4 are named to the owner in the module; the defect is what a LOOK reports past them.

### F7 — `program_steps` resurrects a field a deterministic floor removed from a record an earlier span wrote
- **Severity:** CORRUPTION (a field a floor refused is committed to the scene). **Confidence:**
  mechanism CONFIRMED (snippet `prog_steps.py`); production reachability PLAUSIBLE.
- **Where:** `world/causal_program.py:367-368`:
  ```python
  elif _content(old[key]) != _content(new[key]):
      places[-1][key] = deepcopy(new[key])
  ```
  Only the LAST step that wrote the key is corrected; earlier steps keep the field the floor
  deleted, and `merge_scene_with_diff` (`world/spatial_merge.py:1860-1893`) replays every step.
- **Repro:** steps 1 `{box: {held_by: Mara}}`, 2 `{box: {state: {open: True}}}`; floor pops
  `held_by` from the folded diff → replayed fold still has `held_by: "Mara"`.
- **Reachable shape:** resolve's floors edit `sd["stations"][subject]` in place AFTER
  `_run_specialists` built `causal_steps` — `agents/director_movement.py:2648` (`entry.pop("at")`
  on a walk that fell short), `:3189`, `:1951/2073` (`entry.pop("cell")`); stations merge
  per field (`spatial_merge.py:2096-2103`, `cur.update(st)`), so an `at` written by an earlier
  span survives the floor whenever two spans wrote the walker's station.
- **Fix:** when a corrected record differs, strip from EVERY earlier occurrence the fields the
  correction no longer carries (or replace earlier occurrences with the corrected record's
  subset). Test: two spans write a station, a floor pops `at`, the merged scene has no `at`.

### F8 — A transit need is filed for a room the scene holds under another spelling, or under the vehicle's own name
- **Severity:** WRONG-SCENE (junk need; the Room is asked to build what exists).
  **Confidence:** CONFIRMED (snippet; stored data).
- **Where:** `agents/mapping.py:212-219` (the planning-needs producer):
  `if not (destination and (destination in rooms or planned_for(destination))):` — an exact key
  test, where `classify_movement` (`:267`) uses `scene_room_id`; and `subject=destination or label`.
- **Repro:** destination `"Boat Slip"` with room key `boat_slip` (`scene_room_id` resolves it) →
  `room transit_destination_unplanned room:boat slip`. No destination → `room:the ferry`, a ROOM
  need named after the vehicle. Owner's db: chats 154, 157, 158 each hold an open
  `room:the tardis` need (the vessel's own name; chat 154's scene has `tardis_console_room` with
  `parent_entity` the TARDIS).
- **Fix:** resolve the destination through `scene_room_id`; with no destination, file the need
  under a structural identity (`vehicle:<eid>:destination`) whose subject says what is asked.
  Test: name-spelled destination raises nothing. Sibling of the registered docking half
  (UNBUILT_WORLD ~l.2629, "A built end under another id").

### F9 — The need-kind vocabulary is unstated to the producer and read three ways
- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (snippet).
- **Where:** `world/planning_needs.py:159-162`:
  ```python
  kind = declared_kind or "person"
  if kind not in NEED_KINDS:
      kind = "thing"
  ```
  vs `agents/mapping.py:572` `str(request.get("kind") or "room") == "room"`; the producer
  (`interpret_repair.txt:7`, both packs) asks for `{kind, …}` "for each declared
  place/object/event" and never names the closed set.
- **Repro:** `planning_need(None|'', 'generation_request', …)` → `person` (mapping treated it as a
  ROOM for the plan check); `'place'`/`'location'` → `thing` (a declared place is never a room
  need, and a planned room is not checked for it); `'npc'` → `thing` (a person never enrolled).
- **Fix:** state the closed set in the card (room | person | thing) and default a missing kind to
  the same value in both readers. Test: a kindless request is one kind everywhere.

### F10 — An open person-need enrolment can never answer queues a no-op drain job every beat
- **Severity:** SILENT-NOOP / PERF. **Confidence:** CONFIRMED by trace; cost PLAUSIBLE.
- **Where:** `world/planning_needs.py:432-433` (`if not open_planning_needs(cid, frame_id,
  kind="person"): return None`) and `:389-408`; `world/charter_enrol.py:315-317` returns None
  for a surface with no `name`, and refuses a named one when no institution can keep them
  (`persist/commit_background.py:3006-3018` leaves that need open on purpose).
- **Failure:** the docstring promises "QUEUED FOR WORK THE DRAIN CAN DO, not for a non-empty
  ledger"; a need with no surface name (F9's kindless request) or with no institution is
  retried every beat, each retry re-reading the ledger and, for a named need, taking
  `registry_for_update` — a fresh parse of the whole `charters` row (41 MB in a generated town
  per the `core/db.py:3002-3005` measurement). Owner's db: chat 125's one open person need is
  `subject: "{{PLAYER}}"` — an unsubstituted template token filed as a person at turn 0 (the
  presence producer is outside this scope; `normalize_need` accepts it silently).
- **Fix:** queue only for person needs whose surface names someone and whose last refusal is
  older than the registry's last write; refuse a template token as a need subject. Test: an
  unanswerable person need queues no job.

### F11 — Retired `setting_fact` needs hold the fill job's first three slots forever
- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (read-only data).
- **Where:** `world/planning_needs.py:264-267` (`open_planning_needs`, oldest first) consumed by
  `agents/story_planner.py:2947` `open_planning_needs(cid, frame_id)[:FILL_NEEDS_PER_JOB]` (= 3).
  `NEED_REASONS` keeps `setting_fact` readable ("nothing raises this reason now", `:64-71`) but
  nothing closes the stored ones and the drain answers persons only.
- **Data:** in 19 of the 20 chats with open needs, the three oldest open needs are
  `setting_fact` filed at turn 0; chats 154, 157, 158 hold real room needs (turn 23-24) behind them.
- **Fix:** close stored needs of a retired reason on read (`closed_reason: "channel retired"`), or
  order the fill slice by reason. Related, registered: UNBUILT_PLANNING ~l.442 (the first-three
  slice); not registered: that a retired reason occupies it permanently.

### F12 — The comfort and place-purpose lexicons read only English, and only ASCII
- **Severity:** SILENT-NOOP (language-pack hazard). **Confidence:** CONFIRMED (snippet
  `comfort_ja.py`).
- **Where:** `world/comfort.py:130-131` `re.split(r"[^a-z0-9]+", …)` over entity names,
  descriptions, anchor descs and `pose.posture` (free text, `spatial_geometry.py:1484` "Values
  stay open strings"); `world/place_purpose.py:205-210` (same tokenizer) over node names,
  descriptions and claim text (`_NAME_LEXICON`, `_HERE_LEXICON`, `_CLAIM_LEXICON`).
- **Repro:** a body lying (`posture: "横になっている"`) on an entity named 布団 described
  羽毛の掛け布団… (neutral key) → `comfort_level = (0.0, "")`, `rest_affording = False`; the
  English twin → `(0.3, "bed")`, True. So in a Japanese story: no comfort floor, no passive
  stamina recovery in `survival.tick_vitals` (`:396`), no `here_affords`, no assumed affordances.
  The vocabularies themselves are closed engine sets (fine); the defect is that the text they are
  matched against is authored prose in the story's language. Also English glue reaching a mind:
  `world/exposure.py:205` "standing out in %s" becomes the hedonic `source`
  (`mind/psychology_runtime.py:293-299`), and `place_purpose.py:223` "the name says '…'".
- **Fix:** move the token sets onto the pack's linguistics card with a script-aware tokenizer, as
  the Design.md language-pack row requires of "deterministic recognition tables". Test: the ja
  twin scores like the en one.

### F13 — A room named in a non-Latin script never resolves as a subject
- **Severity:** SILENT-NOOP (language). **Confidence:** CONFIRMED (snippet).
- **Where:** `world/subjects.py:237-251` and `:258-277`: matching through `normalize_room_id`,
  which folds 広場, 石段, 船着き場 all to `""` (then `labels.discard("")`).
- **Repro:** `_scene_room_matches({'rooms': {'hiroba': {'name': '広場'}}}, '広場')` → `[]`;
  by id → match. So `gap_for(…, "room", "広場")`, `living_world`'s place resolution and
  `offscreen.py:688` answer "is not a scene room" for every room spelled by its Japanese name.
  `world/place_names.spelling_key` (`:161-170`) is the script-aware fold the engine already has
  ("Not `normalize_room_id`…").
- **Fix:** match labels by `spelling_key` alongside `normalize_room_id`. Test: a kana-named room
  resolves by name.

### F14 — The wound opens where the player stands, not where the violation happened
- **Severity:** WRONG-SCENE. **Confidence:** PLAUSIBLE (latent: no story has opened a wound).
- **Where:** `world/paradox.py:484-491`: `epicenter = positions.get(anchor["entity_id"])`, else
  `_player_room` — "the player is who committed the violation". A removal anchor's entity has no
  position after the commit, so EVERY removal wound opens in the player's room, whoever removed
  it (a character, the charter, the Director off screen); the exact `.get` also misses a body
  keyed by another spelling (use `room_of`).
- **Fix:** take the room from the before-scene/the beat's `remove_entities` span (or the
  `subject_last_seen` ledger). Test: an NPC removes the anchor two rooms away; epicenter is that room.
- Player authority (question 5): detection is post-commit and authority-agnostic, which is right —
  the `player_authority` ladder decides what lands; paradox detects what landed. No finding there.

### F15 — `beat_events[].execution` is written with the strict status and read by nobody
- **Severity:** DEAD / STALE-DOC (two representations free to disagree). **Confidence:** CONFIRMED.
- **Where:** `world/causal_completion.py:128-140` writes `event["execution"] = status` (the
  `status` in which `missing_effect`/`unsupported_channel`/`ledger_cannot_hold` count against the
  act); `persist/commit_scene_state.py:2404-2406` persists it in the scene's `beat_events`;
  `grep -rn '"execution"'` → no production reader (two tests only). Perception decides delivery
  from `event_execution_statuses(…, action=True)` (`action_status`). PIPELINE.md:1314-1316 says
  the beat log "retains every event with its `execution` status". A future reader of the
  persisted field would un-see the 54 acts the 2026-10-20 fix restored.
- **Fix:** write `action_status` beside it (or instead), or drop the field. Test: none needed
  beyond a schema assertion.

### F16 — Dead code (deletion proposals)
- **Severity:** DEAD. **Confidence:** CONFIRMED (survey above).
- `world/causal_verification.py:1178-1189` `verify_causal_worlds` — no production caller; retire
  by rewriting `tests/test_causal_verification.py:61` and
  `tests/test_causal_overlay_verification.py:113` to call `verify_patch` per span.
- `world/landscape.py:637-638` `_line_clear` — no reference anywhere.
- `world/vistas.py:55-56` `_PACE_M` — no reference anywhere (readers use `site_plan.PACE_M`).
- Test-only by design, keep or relocate (owner's call): `landscape.LOOK_WRITE_REASONS`,
  `scene_memo.clear_scene_memo`, `degradation.lost_at`.

### F17 — Docstrings that describe the deleted pipeline or a reader that does not exist
- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- `world/causality.py:1-6` "compilation of specialist transforms … The Director decides causality
  and routes spans. Specialists describe state changes." — since 2026-09-27 one encoder writes
  the events and `_run_specialists` only splits them by owner.
- `world/beat_ledger.py:10-13` "after the Director dissected the input and five hands resolved
  it in parallel" — five hands are deleted.
- `world/paradox.py:252-255` `_restore_consumed`: "consumed rooms were only ever flagged
  impassable" — no reader makes them impassable (F4). `docs/design/DESIGN_PARADOX_CONSEQUENCES.md`
  §2: "visible (perception reads `room.notes` verbatim)" — it reads notes-else-desc cut to 600 (F4).
- `world/landscape.py:1153-1155` "or by its own name, which the actor used and so may hear back"
  and Design.md:580 "named by the look's word where the mind knows no other" — the code names it
  by the room's canonical name, and the encoder, not the actor, chose the word (F1).
- `world/planning_needs.py:421-426` "QUEUED FOR WORK THE DRAIN CAN DO" — F10.

## Efficiency

1. **`causal_verification._same` rebuilds `canonical_subject_map` twice per comparison.**
   `world/causal_verification.py:64-68` → `spatial_identity.canonical_subject` (`:587-593`)
   → full `canonical_subject_map(scene)` (`:498-586`, not memoised; its alias loop is
   O(names × aliases)). `_record` (`:71-76`) calls `_same` once per key of a channel table, and the
   stations check (`:389-402`) nests it. Hotness: `execution_receipt` runs per step inside every
   `merge_scene_with_diff(…, causal_worlds=…)` — perception onset (`agents/perception.py:3620,
   3803`), loops micro-perception (`agents/loops.py:947`), `director_movement._heard_this_beat`
   (`:1106`, which never reads the receipts), `director_evidence.beat_worlds`, and the commit's
   preview and apply (`persist/commit_scene_state.py:2002, 2436`). Measured on real scenes
   (read-only, `verify_real.py`): `verify_patch` of 4 positions + 4 stations = 0-34 ms (chat 177,
   14 entities: 34 ms); synthetic 30 entities with aliases: 624 ms, 100 entities: 7.6 s
   (profile: 904 map rebuilds for one call). Fix: build each world's map once at `verify_patch`
   entry (the before/after worlds are fixed for the span) and compare against it. Expected:
   two orders of magnitude on the stations path; cheap.
2. **`vistas.obstructed` rebuilds the plan's slab map per vista per observer, and a look re-runs
   the whole horizon.** `world/vistas.py:270-279` (no `scene_memo`, unlike
   `landscape._plan_slabs`), `:370` (`what_a_look_finds` calls `visible_vistas` again per looked
   vista). Per observer per perception stage. Measured (`vista_perf.py`, warm, inside a read pass):
   120 rooms on a plan × 6 vistas = 117 ms per `visible_vistas`; a look at each vista 711 ms.
   Fix: memoise the slab map per (plan, own room) through `scene_memo`, or reuse
   `landscape._plan_slabs`; hand `visible_vistas`' result to `what_a_look_finds`.
3. **`place_purpose.here_affords` is O(entities²).** `world/place_purpose.py:262-266` calls
   `room_of(scene, label)` and `room_of(scene, eid)` per entity; a name miss falls to
   `_unique_entity_keyed` (O(entities)). Per character payload build (`agents/character.py:4357`).
   Measured (`here_perf.py`): 30 entities 4.4 ms, 100 → 50 ms, 300 → 394 ms (the owner's live
   scenes peak at 28 entities, so cold today; procgen worlds scale it). Fix:
   `room_of_record(scene, eid, ent, index=PositionsIndex(...))`.
4. **`far_places` walked twice for an observer who looked.** `agents/perception.py:6291-6299`:
   `looked_far` runs `far_places(..., hidden=...)` internally (`landscape.py:1175`) and the
   standing call runs it again with identical arguments. Only on beats with a far look, per
   looking observer. Fix: let `looked_far` return the standing places too.
5. **Unanswerable person needs trigger a drain job every beat** (F10) — out of band, but a full
   `charters` parse per beat in a generated town. PLAUSIBLE.
6. Minor: `gaps.gap_for`'s record goes whole into the character payload
   (`agents/character.py:4686`, `while_you_were_offscreen`) including `producer`, `seed`,
   `inputs.ledgers`/`inputs.notes`, `basis`, `resolution`, `deltas`, `event_id`s — engine
   bookkeeping tokens on every returning character's call; project `moves`/`events` only.
   `merge_scene_with_diff` computes receipts for callers that only want worlds
   (`director_movement.py:1106`).

## Already registered

- Junk `generation_request` needs displacing real ones under `PLANNING_NEEDS_CAP` —
  UNBUILT_PIPELINE §1.154.
- The fill job sees only the first `FILL_NEEDS_PER_JOB` = 3 open needs — UNBUILT_PLANNING ~l.442
  (F11 adds the retired-reason case, which is not).
- Far layer cannot read planned registry rooms outside the scene, frontier stubs, another
  locale; 72% of rooms declare no exposure — UNBUILT_WORLD §2.40.
- A docked vessel takes its destination by exact id — UNBUILT_WORLD ~l.2629 (F8 is the
  need-filing sibling).
- `world_entities` has no frame partitioning (cross-frame wounds), a warden outliving its wound,
  the toll's missing restore — UNBUILT_WORLD §6.13 → DESIGN_PARADOX_CONSEQUENCES §5.
- `paradox` computed twice a turn and read by nobody — UNBUILT_PIPELINE (f) ~l.1599.
- `_HAZARD_WOUND_NOTE` is English content in non-English views — UNBUILT_IDENTITY ~l.357.
- Paradox projection-writer gaps (World Browser `_write_scene`, `world_put`, presence handovers
  leave `world_entities` stale) — other auditors (`audits/web_routes_extensions.md` F4/F5,
  `audits/persist_background_memory.md`). The READER side, in scope here: `_entity_exists`
  (`paradox.py:184-188`) asks only the projection, though `check_and_apply_paradox` runs inside
  the operative frame's commit with the scene blob — the engine's single source of truth — at
  hand; every projection lag becomes a spurious or missed wound. Fix: check the frame's scene
  (`_unique_entity_keyed` / `room_of`) first, the projection only as fallback.
- Conditions with no end — UNBUILT_WORLD §1.84 (`world_conditions`). In scope: `survival`'s
  `air_denied` is rebuilt by every sweep (`mechanics.py:1416-1419`) and injury heals; no new
  instance found.

## Structure notes

- `world/landscape.py` (1,761): four seams — the walk (`far_places`, 757-1142, a 385-line
  monolith-in-miniature with its own BFS, heap walk, grading and line assembly), the look matcher
  (`looked_far`, 1145-1255), the name floor (`_Floor`, `_place_forms`, `_said_as_a_word`,
  `_writes_as_a_word`, `_through_gate`, `_admit_look`, 1258-1460), and the authoring side
  (`WRITTEN_LOOKS_KEY` … `standing_looks_wanted`, 1480-1761), which only `story/` and
  `web/world_routes.py` read — a natural `world/landscape_looks.py`.
- `world/causal_verification.py`: `_map_receipts` (125 lines) and `_inventory_receipts` (100) are
  monoliths; `verify_patch`'s if-chain is a channel→verifier table in all but name.
- `world/causal_program.bind_items` (192 lines) is a monolith-in-miniature.
- `world/vistas.obstructed` and `landscape._plan_slabs`/`_line_block` are two implementations of
  "the line over the plan's masses"; only one is memoised (Efficiency 2).
- The lit-off vocabulary `(False, 0, "off", "false", "no", "doused", "out")` is spelled five times
  (`landscape.py:401`, `spatial_light.py:357,495,738`, `spatial_light_field.py:339`). Stored data
  holds booleans only (light-source entities in live scenes: 25 True, 3 False, 29 absent), so no
  live defect — one helper would keep it so.
- `stimulation.py:207-208` matches an authored responsive region as a SUBSTRING of a contact
  part (`w in candidate`: "ear" in "rear"). It GRANTS a tier; false-positive rate unmeasured, so
  noted, not filed (house rule: measure before cutting).
- Legacy branches with no live producer (Liveness section): `compile_transforms`' transform-level
  `object_id`, the `event_id` chrono fallback. Measure on stored-beat replays before removing.
- Module-level mutable state: `world/scene_memo._PASSES` (writers `scene_read_pass.__enter__/
  __exit__`, `clear_scene_memo`; released on every exit, exception included; keys hold the scene
  object so ids cannot be recycled; every opener is a `with`). `landscape.REGIONS_UNREAD` is a
  shared sentinel dict with no writer. No `ContextVar` is declared in any of the 19 modules;
  `paradox` and `gaps` read `core.db.active_frame_id` and both pass an explicit frame where it
  matters. `beat_ledger` is not a cache: the beat number is the record's lifetime, and a reroll
  restores checkpoint N (the world before N), so the record answers `[]` until
  `compose_beat_scene` writes the new beat — held.
- Per-observer caches: `landscape._through_gate` keys on the observer's own gate closure
  (`perception._authored_prose_gate`, one per observer per stage), so no observer's gated text can
  answer for another's — held.

## Docs checked

- AGENTS.md:303-307 (`compile_transforms` the pure recompiler; verification then completion) — held.
- AGENTS.md:431 landscape row (declared ground only, never the near field, names gated) — held for
  the standing view; the look path (F1) is outside what it states.
- AGENTS.md:447-448 (`drain_planning_needs` CLOSES a person need a plan answers;
  `PLANNING_NEEDS_CAP`) — held (`planning_needs.py:391-398`, `:119`).
- AGENTS.md:488 (exposure: one caller, never `charge`, capped 0.3) — held.
- AGENTS.md:536 (`PLACE_NAME_ATTEMPTS` = 32, `DEAL_SIBLING_NAMES` = True) — held.
- AGENTS.md:539-540 (`PLANNING_NEEDS_CAP` = 64; `setting_fact` stays readable, nothing raises
  it) — held; consequence F11.
- Design.md:166 (prose → ordered engine state; the causal Director deleted 2026-09-27) — held;
  the module docstrings lag it (F17).
- Design.md:568 (paradox: four rungs, terminal ceiling, toll opt-in) — held
  (`STAGE_THRESHOLDS`, `paradox.py:518-533`); "no story has ever opened a wound" — re-checked
  read-only: no `paradoxes` row carries a wound.
- Design.md:580 ("named by the look's word") — FALSE (F1, F17).
- PIPELINE.md:1303-1330 (receipts per span; `action_status` controls delivery;
  `LIMITATION_CODES`) — held; the `execution` field it says is retained has no reader (F15).
- DESIGN_PARADOX_CONSEQUENCES §2 ("perception reads `room.notes` verbatim") — FALSE (F4).
- Owner ruling 2026-09-21 (paradox consequence moves to the Writers' Room as a plot package from a
  typed planning need) — NOT BUILT: `NEED_REASONS` has no paradox reason and the five hardcoded
  modes still run (`paradox.py:432-455`, `_apply_stage_consequence`); not found in any UNBUILT register (the memory note
  itself lists "whether to build now" as open).
- Owner ruling 2026-10-05 (LOD only for far landscapes; never within a room or one doorway) —
  held: `near_field` (`landscape.py:270-282`) excludes the room, every neighbour by any edge, and
  rooms straight over/under; `MID_HOPS` = 4 is the owner's; `OUTLINE_M` = 250 m (engine estimate,
  named) makes a measured place past 250 m outline even two rooms off, and dusk/twilight forces
  outline grain (`:1104-1105`) — consistent with the light words grading sight, flagged only so
  the owner sees both.
