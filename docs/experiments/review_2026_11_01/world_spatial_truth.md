# Audit — world/spatial facade, geometry, frames, merge, containment

Auditor scope: `world/spatial.py`, `world/spatial_geometry.py`, `world/spatial_frames.py`,
`world/spatial_merge.py`, `world/spatial_containment.py` at commit `84f3de23` (working tree
clean for these files during the audit). Read-only. All snippets were run on `.venv/bin/python`
against in-memory dicts; the timing runs read `engine.db` with `mode=ro` only. No test file was run.

## Scope read

Read in full, every line:

- `world/spatial.py` 1–461 (facade).
- `world/spatial_merge.py` 1–2964.
- `world/spatial_containment.py` 1–3808.
- `world/spatial_frames.py` 1–2718.
- `world/spatial_geometry.py` 1–2435.

Read in part, to answer questions the five files raise (NOT audited):

- `world/spatial_transit.py` 40–260, 471–615, 689–760 (+ grep of 760–940), 1583–1631
  (`_is_body_entity`, `_interior_rooms_of`, `sync_entity_interior_rooms`,
  `_interior_entry_room`, `evict_self_contained_entities`, the head of `apply_transit_dock_edges`,
  `containment_chain`, `ambient_scope`).
- `world/spatial_identity.py` 1–320, 421–735 (`room_of`, `same_subject`, `_unique_entity_keyed`,
  `canonical_subject_map`, `normalize_scene_subjects`).
- `world/spatial_contacts.py` 1208–1268 (`_restation_interior_contact`).
- `world/spatial_prose.py` 325–410 (`spatial_facts`), `world/spatial_lint.py` 60–90,
  `world/spatial_fov.py` grep of `room_grid`.
- `core/db.py` 33–330 (frame-scoped keys, `_scoped_world_key`) and 2985–3160 (`wget`/`wset`/`*_for_frame`).
- `persist/commit.py` 560–673 (domain order), `persist/commit_scene_state.py` 300–375, 1150–1180, 2338–2392.
- `agents/director_movement.py` 2165–2210, `agents/director.py` 1225–1290 and 1655–1700.
- `mind/knowledge_circles.py` 1–60.
- `llm/schemas.py` RoomDef (1730–1935), StateDiff field types (grep).
- Encoder cards (`language_packs/en/cards/system_prompts/encoder/`): containment, inventory_ops,
  entities__inside, entities__new (line 4), positions, poses, remove_entities, remove_rooms,
  remove_adjacent, following_ops, rooms (grep).
- Docs: `docs/design/SPLIT_SPATIAL.md` (all), `docs/experiments/AUDIT_SPATIAL.md` (all — the
  pre-split audit, alpha 9.5), `docs/guides/DATABASE.md` 184–280 and 340–347,
  `docs/guides/PIPELINE.md` 1320–1394, `docs/UNBUILT_WORLD.md` 270–400, 738–757, 1347–1365.
- Tests read for intent: `tests/test_nothing_is_inside_itself.py` 1–56,
  `tests/test_frame_merge_carries_ledgers.py`, `tests/test_causality_bubbles_wired.py` 1005–1035,
  `tests/test_senses_gate.py` 15–50, `tests/test_acuity_proportionality.py` 1–30.

## Findings

### Answers to the assignment's six questions (pointers into the findings below)

**(1) `merge_scene_with_diff`, channel by channel — what an unknown key / entity / room does.**
Nothing in the merge writes to `ctx.warnings`; it has four typed report lists
(`contact_report`, `substance_report`, `crossing_report`, `inventory_report`, plus
`light_report`), and only the channels routed to those lists ever say anything.

| channel | unknown / malformed input | outcome |
| --- | --- | --- |
| `rooms` | non-dict room value | skipped silently (1982) |
| `rooms` | planned/sited room re-measured (`extent`,`shape`,`size`,…) | ignored silently, by design (261–283) |
| `rooms.adjacent` | one-sided re-bearing of a standing pair | `dir` stripped silently (`_shield_standing_bearings`, no warning parameter at all) |
| `rooms.adjacent` | one-sided seal of an open way / one-sided unseal of a wall | refused; the warning text exists but is never emitted (**F19**) |
| `rooms.adjacent` | edge to a room that does not exist | kept verbatim ("tolerated forward reference", 1268–1272) |
| `rooms.parent_entity` | holder spelled by name/alias, not by entity key | kept verbatim; structural readers miss it (**F1**) |
| `entities` | key in `NON_ENTITY_FIELD_KEYS` | dropped silently (2033–2034) |
| `entities` | non-dict value for an existing entity | REPLACES the record (2010–2015; rooms skip the same shape). Validated `StateDiff` (`dict[str, SceneEntityDef]`) cannot carry it; unvalidated callers can |
| `positions` | key in `NON_ENTITY_FIELD_KEYS` | dropped silently (2066–2067) |
| `positions` | room id with no room / a removed room | accepted verbatim, body is nowhere, no warning (**F20**) |
| `positions` | an entity id where a room belongs | repaired to the entity's room + station, silently (`repair_entity_positions`, return unread) |
| `positions` | a bodiless voice | dropped silently (`prune_bodiless_positions`) |
| `positions` | fresh write under an alias / case variant of a standing body | alias: lost to the standing record; case variant: two keys, body in two rooms (**F9**) |
| `stations`, `poses` | unknown body | dropped later by hygiene (`normalize_scene_stations`/`_poses`), silently |
| `scales` | unknown name | kept (by design: not pruned by position), capped at 40 silently |
| `containment` | `{}`, `{mode}` only, wrong key (`holder`), a list, self-holder | treated as a RELEASE of the standing record (**F5**) |
| `containment` | unknown holder | dropped by `normalize_scene_containment` unless `carriers` vouches, silently |
| `inventory_ops` | unknown object / unvouched destination | refused and REPORTED (`inventory_report`) — the one channel that says so |
| `following_ops` | unknown op, unpositioned follower/target, cycle | ignored silently (1446–1484) |
| `remove_entities` | name/alias instead of key | silent no-op (**F21**); on success leaves `contained`/`scales`/`following`/interior rooms (**F3**, **F4**) |
| `remove_rooms` | room occupied (even by an object) | refused silently; on success leaves every edge into it (**F11**) |
| `remove_adjacent` | unknown room | silent no-op |
| `contact_ops`, `substance_ops`, `comms_ops`, `contact_action_ops`, `vitals` | delegated to `spatial_contacts`/`_substance`/`_senses`/`survival` — not audited here |

**(2) Two representations of a body's whereabouts.** Stored in the scene: `positions[x]`
(primary); `contained[x] = {in, mode, by}` (ledger form; the position is re-derived from it every
merge); a room whose `parent_entity` is the holder plus `positions[x]` naming that room (place
form); `entities[holder].interior_rooms` (index of the place form, add-only); `entities[x].held_by`
(folded into `contained` each merge, retired at commit); `entities[x].state.held_by` /
`state.held_items` / `state.worn_by`; `attire[wearer]` (folded into `contained` by
`derive_worn_containment`); interior `contacts` with `target_interior` (minted into `contained`;
rewritten to the occupant's room name by `_restation_interior_contact`); `stations[x]`
(`at`/`near`/`cell`/`altitude_m`); `poses[x]` (`support`, `relative_to`, and `relation:"inside"`,
which `contain_posed_inside` reads as containment); `room_since[x].room`; `crossings[x]`;
`orientation[x].came_from`; `following[x].target`; `entities[v].state.transit`/`state.link`;
`entities[x].state.position` (free text read as a last resort). Outside the blob: lorebook
`currently_within` links (`commit_scene_state.py:243–304`), `subject_last_seen`, `whereabouts`,
charter places. **There is no `entities[x].room` and no `rooms[r].occupants`** — the assignment
lists both; neither exists (`world_entities` has no room column, `core/db.py:1171–1189`;
`spatial_containment.py:1358–1360` says so). `currently_within` is a lorebook relation, not a
scene field. Writers that update fewer than all of their siblings: `evict_self_contained_entities`
(positions only, leaves the `contained` record that re-derives the bad position, **F6**);
`remove_entities` (positions/poses/substances/room_since only, **F3**); `remove_rooms` (rooms
only, **F11**); `repair_entity_positions` (positions + `stations.at`, deliberately not
`contained`); `normalize_scene_subjects` (folds `contained.in` but never `rooms[*].parent_entity`,
**F1**, **F15**); frame split/merge (partition `_SUBJECT_KEYED`, which omits the body-keyed
`room_since`, `crossings` and `expired_entity_state` — those are copied whole to the child and
dropped from the child at reunion; minor, noted in Structure notes).

**(3) Containment cycles and "which room is a nested body in".** Ledger cycles are refused:
`_clean_containment` refuses direct self-containment (389), `normalize_scene_containment` breaks
chain cycles by a casefolded string walk (1029–1040), `derive_inventory_placements` refuses a
transfer that would close one (1874–1879, identity-aware). Cycles ACROSS the two forms (A carried
by B while B stands in A's interior) are refused by nothing: the ledger walk cannot see the place
form, and `evict_self_contained_entities` runs before the derivation that recreates the paradox
(**F6**). "Where is a body inside a vehicle inside a room" is answered by `room_of` (the interior
room) — but "what encloses it" is answered by at least six functions with three identity rules:
exact entity key (`_interior_rooms_of`, `apply_transit_dock_edges`, `infer_vehicle_zones`,
`containment_chain`'s `entities.get(eid)`), identity-resolving (`_body_interior_holder`,
`_effective_zone`, `enclosure_joins_rooms`, `inside_as_holder`, `_shares_enclosure`), and raw
string equality (`containment_conceals`, `carrier_chain`, `normalize_scene_containment`). They
disagree whenever `parent_entity` or `contained.in` is not spelled as the entity key (**F1**,
**F15**).

**(4) Frames.** Two frame-scoped reads/writes go through the ambient contextvar instead of the
explicit frame argument (`detect_split` 1027, `perform_split` 1253/1386, **F7**). Seeding at a split
omits per-party keys, `knowledge_circles` being the one with a firewall consequence (**F10**). The
reunion and couple fusers revert the home frame's map (**F2**). Order: commit runs scene (where all
five `infer_*` run, in their documented order, `commit_scene_state.py:2350–2383`) → `skip_lives` →
entities → cast → paradox → spatial reconciliation (`persist/commit.py:572–603`). PIPELINE.md's
relative order holds, but its numbered list omits `skip_lives` (Docs checked).

**(5) Geometry.** `ROOM_SIZES` is enforced by `effective_room_size` (1014–1024): an unknown word
falls to the extent, then an English name hint, then `medium`; the live G6 warning skips such a
room (**F22**), the name hint is English-only (**F18**). Pace/cell: one cell is one pace
throughout (`room_grid` builds `RoomGrid(extent.w, extent.d)` or the tier side;
`CELL_REACH_PACES=1` compares a Chebyshev cell distance); no unit mixing found. One stale unit
claim (**F27**).

**(6) Efficiency.** The merge DOES copy: `copy.deepcopy(scene)` (1915), `copy.deepcopy(diff)`
(1925), `copy.deepcopy(contacts)` (2537); the causal-program path adds one scene deepcopy plus one
per step and a deepcopy of every step (1863, 1896). See Efficiency.

---

### F1 — `parent_entity` spelled by the holder's name splits the structural readers from the permissive ones; a body inside a body becomes visible from outside

- Severity: **LEAK**. Confidence: **CONFIRMED** (snippet).
- Where: ingest `world/spatial_merge.py:217-223` copies the value verbatim, and
  `world/spatial_identity.py:681-731` (`normalize_scene_subjects`) folds `contained.in` but never
  `rooms[*].parent_entity`. The exact-key readers: `world/spatial_transit.py:128-130`
  (`_interior_rooms_of`), `world/spatial_transit.py:734-737,770` (`apply_transit_dock_edges`:
  `interiors.setdefault(room["parent_entity"], …)` then `interiors.get(eid)`),
  `world/spatial_frames.py:207-208` (`r.get("parent_entity") == eid`). The identity-resolving
  reader: `world/spatial_containment.py:764-769` (`room_of(scene, parent)`).

```python
# spatial_merge.py:217
for field in ("name", "desc", "notes", "parent_entity"):
    if not incoming.get(field):
        continue
    ...
    merged_room[field] = incoming[field]
# spatial_transit.py:128
return [rid for rid, room in rooms.items()
        if isinstance(room, dict)
        and str(room.get("parent_entity") or "").strip() == target]
```

- Scenario: the room author / encoder writes `parent_entity: "Mirelle"` (the display name; the
  card says "the entity id", `encoder/rooms.txt:3`, but `prose_contract/room_author.txt:15` says
  only "is that body or thing") for an entity keyed `mirelle_01`, with an authored
  `adjacent: [{to: hall, barrier: open}]`. The interior index stays empty, `infer_body_enclosures`
  never defaults it to `membrane`, the dock rewrite never replaces the open edge, so
  `_hiding_holders` walks through the open edge and conceals nothing.
- Verified (merge with an empty diff, then the sight reader):

```
parent_entity='mirelle_01'  stomach edges: [{'to':'hall','barrier':'membrane',...}] enclosure: membrane
                            conceals Bo/Hinami: True   visual Bo->Hinami: none
parent_entity='Mirelle'     stomach edges: [{'to':'hall','barrier':'open'}]        enclosure: None
                            conceals Bo/Hinami: False  visual Bo->Hinami: conduct
```

  For a vehicle (`lift_01` named "Lift Car", interior `car_int` with `parent_entity: "Lift Car"`):
  `_interior_rooms_of → []`, the car's interior gets no doorway at all (`adjacent: []`, an island —
  `connect_orphan_new_rooms` skips interiors), while `_body_interior_holder(Ana) → "Lift Car"`.
  With the id spelling the same scene gets `open_door` to the hall.
- Fix: canonicalise at ingest, against the holder — resolve `parent_entity` to the unique entity
  key (`_unique_entity_keyed`) in `_merge_room`/`_name_nameless_new_rooms` (and in
  `normalize_scene_subjects` for stored scenes), leaving an unresolvable or ambiguous value as
  written. Test: merge a body interior whose `parent_entity` is the holder's display name and
  assert it is rewritten to the key, its doorway is `membrane`, and `visual_level_between` from the
  outer room is `none`.

### F2 — A reunion (and a couple's fused view) reverts the home frame's map to the away frame's copy from the split instant

- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_frames.py:1172-1175` (the default rule), called with no `child_rooms` by
  `perform_merge` (`1752`) and `open_couple` (`2246`); the premise was broken by
  `perform_split` giving the child the WHOLE map (`1366`).

```python
if child_rooms is None:
    child_rooms = {str(r) for r in (child_scene.get("rooms") or {})}
    merged_rooms = {**(parent_scene.get("rooms") or {}),
                    **(child_scene.get("rooms") or {})}
```

- Scenario: the party splits; while apart the home party shuts the hall door and opens a new way
  to a cellar it mints. On reunion every room the child carries — i.e. every room that existed at
  the split — is replaced by the child's untouched copy. `_FRAME_ROOM_TABLES` follow the same
  rule (`_touches_rooms` is true for every passage/comm naming any room), so passage and comms
  edits revert too.
- Verified: `merge_frame_scenes(parent, child)` → hall edges `[{'to':'yard','barrier':'open'}]`
  (parent had `closed_door` + a `cellar` edge), yard `open` again, cellar keeps a one-sided edge
  back. The fusion for a couple uses the same default, so during a call the home party plays in
  the away frame's stale copy of its own rooms (the close is protected by `_own_or_fused`, the
  play is not). `tests/test_frame_merge_carries_ledgers.py` models the pre-2026-09-17 shape (child
  holds a subset of rooms) and so cannot see this.
- Fix: since both sides now hold the whole map, pass `child_rooms` = the rooms the away bodies
  stand in (the sibling-merge rule, 1868–1875) from `perform_merge` and `open_couple`, so
  `_merged_rooms` keeps the parent's copy elsewhere and unions doorways. Test: split, change a
  barrier and add an edge in the parent, merge, assert both survive.

### F3 — `remove_entities` leaves the removed thing's carriage record, so a consumed thing is re-placed and still "held"

- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:2144-2184` (removal clears positions, poses, pose referents,
  substances, `room_since` only); `world/spatial_containment.py:1001-1025`
  (`normalize_scene_containment` checks only the HOLDER is known); `1306-1338`
  (`derive_contained_positions` re-writes the position).
- Scenario: `remove_entities: ["coin"]` ("consumed", per `encoder/remove_entities.txt`) for a coin
  `held` by Hinami.
- Verified: after the merge `entities` no longer has `coin`, but
  `positions == {'Hinami': 'hall', 'coin': 'hall'}` and `contained['coin'] == {'in': 'Hinami',
  'mode': 'held'}` — re-derived every later merge, so every reader of `contained` (the views' bearer list,
  per `derive_held_by_containment`'s docstring) keeps listing it — inferred, not executed. The same pass also leaves `stations` rows for other bodies `near` it until hygiene,
  `scales`, `following` and any other entity's `held_by` naming the removed thing.
- Fix: removal pops `contained` rows whose subject or holder is the removed entity (under any
  spelling, `same_subject`), plus `scales`/`following` rows. Test: remove a carried thing, assert no
  position and no record after one and two merges.

### F4 — Removing a holder leaves its interior rooms standing, still walkable through a frozen doorway

- Severity: **CORRUPTION** (WRONG-SCENE). Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:2144-2184`; the dock rewrite only rewrites interiors of entities
  that still exist (`spatial_transit.py:739-770`), and `sync_entity_interior_rooms` is add-only.
- Scenario: a TARDIS docked open on a beach is written into `remove_entities` (shattered).
- Verified: rooms after the merge `['beach', 'console']`; console keeps
  `parent_entity: 'tardis'` and `[{'to':'beach','barrier':'open_door'}]`;
  `spatial_rel(beach, console)` → `open_door/near`; `passable_route_exists(beach, console)` → True.
  (`commit_scene_state._guard_occupied_mover_removal` only refuses when bodies are inside.)
- Fix: when an entity is removed, sever (or retire through the same `remove_rooms` path) the rooms
  whose `parent_entity` names it, or at least drop their edges; destruction already has the
  book-scoped version. Test: remove an unoccupied vehicle, assert its interior is gone or
  unreachable.

### F5 — A malformed containment write is read as a RELEASE of the standing record

- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:2339-2353` with `world/spatial_containment.py:383-390`.

```python
record = _clean_containment(raw, label) if raw else None
record = canonical_enclosure_mode(merged, record)
if record is None:
    # Released: out of the pocket, off the shoulder, out of the jar.
    released.add(label)
```

- Scenario: the schema is `containment: dict[str, Optional[dict]]` (`llm/schemas.py:2812`), so
  `{Pip: {mode: "container"}}` (restating only the mode), `{Pip: {holder: "jar"}}` or
  `{Pip: ["jar"]}` all validate and all return None from `_clean_containment`.
- Verified: each of those four inputs turned `contained = {'Pip': {'in':'jar','mode':'container'}}`
  into `{}` — the jarred body walks free, with no report. The doctrine everywhere else in this file
  is that silence and defaults are never erasure (`_merge_entity`, 602–605); only an explicit
  `null` is the documented release (`encoder/containment.txt`).
- Fix: release only on an explicit falsy value (`None`/`{}`/`""` as the card says); a non-empty
  value that does not clean is refused and reported (to `contact_report` or a new containment
  report). Test: merge `{mode: "container"}` over a standing record, assert the record stands.

### F6 — A carried vehicle whose holder walks into it ends inside itself, every merge

- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:2223-2235` (eviction) runs BEFORE
  `world/spatial_merge.py:2517` (`derive_contained_positions`) and `place_enclosed_bodies`; the
  ledger-only cycle walk (`spatial_containment.py:1029-1040`) cannot see a cycle that runs through
  the place form.
- Scenario: the measured case its own docstring names (`spatial_transit.py:493-498`: the police
  box recorded `held` by the Doctor, who steps through its doors).
- Verified: `positions after: {'tardis': 'console', 'Doctor': 'console'}`, unchanged by a second
  empty merge; meanwhile the dock edge says `console → beach` (two representations of where the
  box is, disagreeing). `tests/test_nothing_is_inside_itself.py:46-51` builds its fixture with
  `"contained": {}`, the one shape where eviction sticks.
- Fix: treat "holder stands in the subject's own interior" as a cycle in
  `normalize_scene_containment` (drop or release the record), or run the eviction again after
  `derive_contained_positions`. Test: the fixture above with `contained: {ship: {in: Doc, mode:
  held}}`, merged twice.

### F7 — `detect_split` / `perform_split` read and write `scene` through the ambient frame, beside an explicit frame argument

- Severity: **CORRUPTION** (latent). Confidence: **CONFIRMED** by trace.
- Where: `world/spatial_frames.py:1027` (`scene = wget(chat_id, "scene", None)`),
  `1253` (`scene = wget(chat_id, "scene", {}) or {}`), `1386` (`wset(chat_id, "scene", scene)`);
  every other key in `perform_split` uses `wget_for_frame(..., parent_frame_id, ...)` (1320–1326).
- Scenario: `_scoped_world_key` (`core/db.py:224-238`) resolves `scene` from
  `active_frame_id`, not from `parent_frame_id`. The production caller (`detect_and_reconcile`, from
  commit) sets the two equal, but `tests/test_the_bubble_radius_is_rooms_walked.py:831` calls
  `perform_split(cid, past, ...)` with no active frame: the PRESENT frame's scene is read,
  partitioned and written back (Tamamo removed from the present), the past frame's scene is never
  touched, and the child is seeded from the present's rooms. The test asserts only `char_state`.
- Fix: `wget_for_frame(chat_id, "scene", parent_frame_id)` / `wset_for_frame(...)` in both
  functions. Test: split off a non-present frame with no active frame set; assert the present's
  scene is byte-identical and the past frame lost the body.

### F8 — Collapsing an entity's id-keyed and name-keyed records drops its `scent` and `held_by`

- Severity: **CORRUPTION** (minor). Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:856-871` (`_ENTITY_STRUCTURAL_FIELDS`) used at `958-961`;
  `_ENTITY_DEFAULT_FIELDS` (479–521) lists `scent` "pre-emptively" and `held_by` for exactly the
  reason the structural list exists.
- Verified: `censer_01` (scent myrrh, `held_by` Hinami, `light_source` dim) re-declared under its
  name `censer` → after collapse `{'scent': None, 'held_by': None, 'light_source': 'dim'}`.
- Fix: add `scent` (and `held_by`, or document why carriage is state-like) to the structural list,
  ideally derived from one shared tuple so the two lists cannot drift. Test: the collapse above.

### F9 — A position written under another spelling of a standing body is lost (alias) or duplicated (case)

- Severity: **WRONG-SCENE**. Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:2061-2076` (blind `update`, then `_dedup_duplicate_position_keys`
  which handles only the exact id/name pair, 830–850) and `world/spatial_identity.py:638-640`
  (the fold keeps the record already under the canonical spelling). Stations and poses got the fix
  (`_onto_standing_spellings`, 1744–1769); positions did not, although its docstring says
  "THE FRESH WRITE WINS, as it does for `positions`".
- Verified (cast entity `mel_01` named Mellisande, alias Mel, standing in the hall):
  `{'positions': {'Mel': 'kitchen'}}` → `{'Mellisande': 'hall'}` (the move is discarded);
  `{'positions': {'HINAMI': 'yard'}}` with an entity named Hinami → `{'Hinami': 'hall', 'HINAMI':
  'yard'}` (one body in two rooms); the id spelling works; `stations: {'Mel': ...}` lands.
- Fix: route `incoming_positions` through `_onto_standing_spellings(merged, "positions", ...)`
  before the update (and casefold-merge case variants onto the standing key). Test: the two
  inputs above.

### F10 — In-story knowledge-circle membership is dropped by a frame split and lost at reunion

- Severity: **WRONG-SCENE** (firewall-inverse: a mind concludes less than its channels allow).
  Confidence: **CONFIRMED** by trace + pinned test.
- Where: `world/spatial_frames.py:1310-1321` (the seed list: known, clock, intentions,
  obligations, shadow_profile, presences, log, charter_last_places — not `knowledge_circles`);
  `perform_merge` (1700–1772) merges clock/known/relationships/scene/cast only; only
  `perform_sibling_merge` unions it (`_SIBLING_UNION_KEYS`, 1780–1781).
- Scenario: a character initiated into an order at turn 60 (`mind/knowledge_circles.join_circle`)
  walks out of reach and gets a bubble: in the bubble `effective_circles` reads a blank overlay, so
  the knowledge gate withholds the order's lore she was granted; anything granted while away is
  discarded at reunion. `mind/knowledge_circles.py:24-27` claims the row "rides archive,
  checkpoint, branch and frame split with no handling of its own"; frame-scoped keys do not ride a
  split (`perform_split` 1287–1291: "a never-touched frame otherwise starts blank"), and
  `tests/test_causality_bubbles_wired.py:1028-1031` pins the exclusion as "per-beat scratch",
  which it is not.
- Fix: seed `knowledge_circles` into the child and union it back in `perform_merge` (as the
  sibling merge does); fix the test's classification. Test: join a circle, split, assert
  `effective_circles` in the child; join another in the child, merge, assert both.

### F11 — `remove_rooms` leaves every doorway into the vanished room, and refuses silently when anything stands in it

- Severity: **WRONG-SCENE** (+ SILENT-NOOP). Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:2186-2196`.

```python
occupied_rooms = set(merged["positions"].values())
for room_id in diff.get("remove_rooms") or []:
    if room_id in occupied_rooms:
        continue
    merged["rooms"].pop(room_id, None)
```

- Verified: removing an unoccupied `cellar` left the hall's `{'to': 'cellar', 'barrier':
  'open_door'}`; `spatial_rel(hall, cellar)` → `open_door / near`, and `effective_anchors` will
  mint a `door:cellar` feature for it. With only a crate positioned there the removal was refused
  with no word. Contrast `remove_adjacent` (2110–2142), which deletes both ends and the passage.
- Fix: on removal also strip edges whose `to` is the room (both directions) and passages naming
  it; report a refused removal to the Director (crossing/inventory report). Test: remove a room
  with a neighbour, assert no edge names it.

### F12 — The orphan-room heal attaches the new room to a vehicle interior, and the dock rewrite strips it: the documented case stays an island

- Severity: **WRONG-SCENE**. Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:1378-1392` (anchor = most-occupied pre-beat room, or the first
  room) — no `parent_entity` filter on the ANCHOR (the fresh room is filtered at 1385);
  `apply_transit_dock_edges` then strips "stale reverse edges from plain world rooms into the
  interior" (`spatial_transit.py:721-722`).
- Scenario: the function's own story (chat 58, 1343–1347): everyone is in the TARDIS console
  room, the Director mints `northern_plaza` with no edges.
- Verified: plaza edges `[]` after the merge; console keeps only its dock edge. The plaza is an
  island and its occupants perceive nothing.
- Fix: map an interior anchor to its holder's exterior room (`_entity_exterior_room`), and skip
  interior rooms in the fallback. Test: the scenario above, assert the plaza joins the vehicle's
  exterior room.

### F13 — A pose `relation: "inside"` against any non-body entity (a door) mints an interior for it and moves the body in

- Severity: **WRONG-SCENE**. Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_containment.py:2504-2514` (any non-body entity named by `relative_to` or
  `support` qualifies); the enterable-kind test exists only for the minted-and-unplaced fallback
  (2493).
- Verified: `poses: {Mara: {relation: "inside", relative_to: "oak_door"}}` with an `oak_door`
  entity (kind `door`) → room `oak_door_interior` minted, Mara positioned in it, shut away from
  the hall. The docstring (2463–2465) promises "a pose against an anchor, a room or another body
  is an arrangement and is left alone ('inside the doorway')" — a doorway that is an ENTITY is not.
- Fix: apply the same enterability test to the named-ref path (kind in the engine's enterable
  set, `container: true`, `interior_spec`, or existing interior rooms). Per the owner's ruling on
  guards, measure the false-positive rate on stored poses first. Test: the door case stays an
  arrangement; a crate case still contains.

### F14 — A thing handed to a body with relation `inside` is placed INSIDE the body, contradicting the transfer path's own rule

- Severity: **WRONG-SCENE** (possible LEAK). Confidence: **CONFIRMED** (placement), **PLAUSIBLE**
  (perception consequence).
- Where: `world/spatial_containment.py:1889-1894` (only `interior` is demoted) vs
  `world/spatial_containment.py:1247` and `1270-1280` (`_INTERIOR_MODES = {"inside",
  "interior"}` drives placement in `_interior_room_for`).

```python
# An interior is a PLACE ... A transfer op is evidence of carriage and never
# of that, so the one mode that would trigger it is not derivable here
if record["mode"] == "interior":
    record["mode"] = "container"
```

- Scenario: the inventory card offers `inside` as a shut-away carry word for a BODY
  (`encoder/inventory_ops.txt:2`); the body has interior rooms (a card-authored inside, or the
  room left after a swallow — "the place it came out of STAYS").
- Verified: `transfer coin Hinami → Mirelle relation inside` → record `{'in': 'mirelle_01',
  'mode': 'inside'}`, position `mirelle_01_interior`. A body standing in that interior then shares
  the coin's innermost holder (`mirelle_01`), so it is not concealed from her — she perceives a
  thing her captor pocketed. `place_enclosed_bodies` (2869–2872) says the opposite of
  `_interior_room_for` for the same record ("`inside` a BODY stays the ledger's"): two structural
  readers of one word disagree, the class of the `inside`/`interior` memory, at the inventory
  door rather than the containment door (where `canonical_enclosure_mode` already canonicalises).
- Fix: canonicalise the transfer mode at ingest against the holder — for a body holder map
  `inside` to `pocket` (shut away, no place) — or make `_interior_room_for` require `interior` for
  a body holder. Test: the transfer above leaves the coin with the holder's room.

### F15 — `containment_conceals` compares holder strings while `_shares_enclosure` compares identities

- Severity: **WRONG-SCENE** (subtractive). Confidence: **CONFIRMED** at function level,
  **PLAUSIBLE** reachability.
- Where: `world/spatial_containment.py:959-960` and `907` (`str(holders[0]).strip().casefold()`)
  vs `938-941` (`same_subject`); also read by `normalize_scene_poses`
  (`spatial_geometry.py:1612,1625`).
- Verified: one body in the stomach by ledger (`in: "Mirelle"`, the folded display name) and one by
  place form (`parent_entity: "mirelle_01"`): `_hiding_holders` → `['Mirelle']` vs
  `['mirelle_01']`, `containment_conceals` → True, `visual_level_between` → `none`, while
  `_shares_enclosure` → True. `normalize_scene_subjects` folds `contained.in` toward the display
  name while `parent_entity` stays the key, so the two forms systematically spell one holder two
  ways; mixed forms survive a merge for any record `place_enclosed_bodies` does not convert (F14's
  case, an unplaced holder).
- Fix: compare innermost holders with `same_subject` (or canonicalise both to the entity key,
  which F1's ingest fix would do). Test: the mixed scene above, assert not concealed.

### F16 — Vehicle zone stamping only recognises `kind == "vehicle"`, exact `parent_entity`, exact party keys

- Severity: **WRONG-SCENE**. Confidence: **CONFIRMED** by trace (needs a DB to execute).
- Where: `world/spatial_frames.py:196`, `207-208`, `213`.

```python
if not isinstance(ent, dict) or ent.get("kind") != "vehicle":
    continue
...
interior_rooms = {rid for rid, r in new_rooms.items()
                  if isinstance(r, dict) and r.get("parent_entity") == eid}
aboard = any(new_positions.get(name) in interior_rooms for name in party_names)
```

- Scenario: the engine's own word list for a thing that moves is `MOVING_KINDS = {vehicle, ship,
  boat}` (`spatial_transit.py:136`), and the encoder card names `ship` and `boat` as engine words
  (`encoder/entities__new.txt:4`). A party aboard a `kind: "ship"` (or `"Vehicle"`) crossing to a
  disconnected place gets no zone, so `detect_split` never fires; the same happens for an interior
  whose `parent_entity` is the display name (F1) or a party member keyed differently in
  `positions`. `contain_posed_inside` has the same literal (`("vehicle", "container")`, 2493).
- Fix: `str(kind).casefold() in MOVING_KINDS`, `_interior_rooms_of`/F1's canonical key, and
  `room_of` for the aboard test. Test: a pure call with a stubbed `_all_party_names`.

### F17 — The pose-prose reconciliations are English-only; in a Japanese story they never fire

- Severity: **WRONG-SCENE** (language pack). Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_geometry.py:1635-1639` (`_CONTACT_BOUND_POSE_WORDS`), tokenised with
  `[a-z'’-]+` (1731) / `[\w'-]+` (2082, 2146), clauses split on ASCII punctuation (2081),
  names matched with `\b`/`(?<!\w)` (1976–1977, 2085, 1516).
- Verified: the same transfer that retires "holding the jar against her chest" retires nothing
  for 壺を胸に抱えて持っている (detail kept); `invalidate_moved_body_pose_details` likewise `[]`
  for ミレルを抱きかかえている. The measured chat 98/99 defects these three functions exist to close
  therefore recur in every Japanese story. The list is the engine's own "one list" (1695–1699),
  but it is a list of English verbs read out of free prose — the class CLAUDE.md warns against
  for guards that read prose.
- Fix: decide per the rulings (state the class, not a word list): e.g. retire a possession clause
  by the structured ledger alone (the transfer named the thing and the clause names the thing),
  dropping the verb gate, or move the vocabulary into the language pack. Test: a `ja` detail
  naming the transferred thing is retired.

### F18 — The room-size name hint is an English word list

- Severity: **WRONG-SCENE** (language pack, low). Confidence: **CONFIRMED** by reading.
- Where: `world/spatial_geometry.py:993-997`, read at `1021-1023`.
- Scenario: `re.split(r"[^a-z]+", text.casefold())` against `{"hall", "ballroom", ...}`: a
  Japanese 大広間 (or an English "throne room", "cavern", "market square") is never `large`, so
  `proximity_rel` never says `across` there. Fails toward `medium`, as its comment says.
- Fix: owner's call — drop the hint (extent and `size` exist now) or move it to the pack.

### F19 — The edge shields' refusal warnings are never emitted

- Severity: **SILENT-NOOP** (a parameter nobody passes). Confidence: **CONFIRMED** (grep).
- Where: `world/spatial_merge.py:1079,1130-1135` and `1236,1322-1326` accept `add_warning`;
  the only live caller passes none:

```python
incoming_rooms = _shield_standing_passage(
    _prior_rooms, incoming_rooms)
incoming_rooms = _shield_minted_edges(
    _prior_rooms, incoming_rooms)
```

  (`1935-1938`). Only `tests/test_barrier_vocabulary.py:135` passes a list.
- Scenario: a beat seals a doorway from one side or unseals a wall from one side; the merge
  refuses it and nobody — Director, warnings, receipts — is told why the door did not change.
- Fix: thread a report list through `merge_scene_with_diff` (as `crossing_report`) into both
  shields, and give `_shield_standing_bearings` the same. Test: merge a one-sided seal with a
  report list, assert one sentence.

### F20 — A position naming a room the scene does not hold is accepted silently

- Severity: **SILENT-NOOP** (body nowhere). Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:2061-2062`; the movement floor upstream is deliberately silent
  about an unknown destination ("a room this beat is minting", `agents/director_movement.py:2168-2180`),
  and nothing later checks that the room was in fact minted.
- Verified: `positions: {Ann: "attic"}` (no attic) → `{'Ann': 'attic'}`; Ann/Bo →
  `separated / far`. The same holds for a room this frame removed or retired.
- Fix: at the end of the merge, report (do not repair) any position whose room is neither a room
  nor resolvable by `repair_entity_positions`. Test: the input above yields one report line.

### F21 — `remove_entities` by display name is a silent no-op

- Severity: **SILENT-NOOP**. Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial_merge.py:2145` (`merged["entities"].pop(entity_id, None)`).
- Verified: `remove_entities: ["brass lamp"]` for `lamp_7` named "brass lamp" → entity and
  position remain. The card asks for ids; the engine has an identity test it does not use here.
- Fix: resolve through `_unique_entity_keyed` (ambiguity refuses), and report a miss.

### F22 — The live "guessed room size" warning skips a room whose size word is out of vocabulary

- Severity: **SILENT-NOOP**. Confidence: **CONFIRMED** by reading.
- Where: `world/spatial_geometry.py:1072-1073` (`if str(room.get("size") or "").strip(): continue`)
  vs `1014-1024` (`effective_room_size` treats that word as no size). `RoomDef.size` is free text
  (`llm/schemas.py`, `size: Optional[str]`), and only the offline `tools/scene_lint.py:632-634`
  reports the word.
- Scenario: `size: "enormous"` is graded by the name hint/`medium` and the commit
  (`commit_scene_state.py:2930`) never says so — the exact silence `guessed_room_sizes` exists to end.
- Fix: skip only when `size in ROOM_SIZES`; report the word in the row. Test: an invalid word in a
  shared room yields a row.

### F23 — `spatial_facts` and the fact builders it alone calls reach no mind; `room_layout` too

- Severity: **DEAD**. Confidence: **CONFIRMED** (grep across repo).
- Where: `world/spatial_containment.py:304-343` (`size_facts`), `3753-3808`
  (`containment_facts`), `world/spatial_geometry.py:2271-2302` (`pose_facts`), `1347-1368`
  (`room_layout`). Only caller of the first three is `spatial_prose.spatial_facts`, which has no
  non-test caller (its own test, `tests/test_acuity_proportionality.py:5-7`, says so); `room_layout`
  is called only by tests.
- Why it matters beyond dead weight: `containment_facts` would hand a mind raw ledger keys
  ("da5e941e17264941 is carried by you", contrary to `interior_occupants`' own rule at 3718–3722)
  and ungrammatical English mode sentences ("You are pocket by …"), and `AGENTS.md:501-502` still
  lists `spatial_facts`/`size_facts` as live co-routes.
- Fix: delete (with their tests) or wire deliberately; correct AGENTS.md either way.

### F24 — `invalidate_moved_body_place_details` builds a place vocabulary it no longer reads

- Severity: **DEAD** (+ PERF). Confidence: **CONFIRMED** (grep).
- Where: `world/spatial_geometry.py:1837-1854` (`room_phrases`, `_anchor_phrases` computed, never
  read — the docstring says "THERE IS NO PLACE VOCABULARY ANY MORE"); `_detail_names_a_place`
  (1762–1771) and `_PLACE_PHRASE_MIN` (1747) have no caller anywhere.
- Cost: an O(rooms) walk on every merge that has a mover. Fix: delete the dead locals and helpers.

### F25 — The facade imports `SCENT_LEVELS` twice; the second shadows the first and blinds a test

- Severity: **DEAD** (vacuous test). Confidence: **CONFIRMED** (snippet).
- Where: `world/spatial.py:282` (from `spatial_senses`: `('none','muffled','full')`) and
  `world/spatial.py:447` (from `spatial_scent_field`: `('trace','faint','clear','strong',
  'overpowering')`); `world.spatial.SCENT_LEVELS is spatial_scent_field.SCENT_LEVELS` → True.
- Scenario: `tests/test_senses_gate.py:22-46` imports `SCENT_LEVELS` from the facade and iterates
  it as the `sense_adjusted("scent")` ladder, so the scent third of its byte-identity check runs
  over words that ladder does not hold. `charter_runtime.py:3477` wants the field ladder and gets it.
- Fix: rename one (e.g. `SCENT_GRADE_LEVELS` in senses) and import both explicitly.

### F26 — `detect_merge`'s docstring describes the merge-on-empty-zones rule `_back_together` calls a leak

- Severity: **STALE-DOC**. Confidence: **CONFIRMED**.
- Where: `world/spatial_frames.py:1441-1445` ("same zone, or both have no declared zone at all --
  either reads as 'back together'") vs `1519-1525` ("The previously-present 'both zone sets
  empty' branch is a bug ... leaked permanent bidirectional memory across an active split").
- Fix: rewrite the docstring to the three positive signals the code uses.

### F27 — `extent_clamp`'s docstring states the old 24-pace cap

- Severity: **STALE-DOC**. Confidence: **CONFIRMED**.
- Where: `world/spatial_geometry.py:820-823` ("`EXTENT_MAX_PACES`, an owner-visible cap: 24 paces
  a side, 576 cells") vs `769-770` (`EXTENT_MAX_PACES = 96`, raised 2026-10-03 per 763–767).

### F28 — "Body-scoped" claims about the interior index that stopped being true on 2026-09-04

- Severity: **STALE-DOC** (code and a register). Confidence: **CONFIRMED**.
- Where: `world/spatial_containment.py:2553-2561` (gate 3: "`sync_entity_interior_rooms` and
  `infer_body_enclosures` are both body-scoped, so an interior minted for a non-body is never
  indexed") and `3100-3103`; `world/spatial_transit.py:154` says "EVERY HOLDER, since 2026-09-04".
  `docs/UNBUILT_WORLD.md` §1.28 (lines 349–358, "A non-body holder never gets an engine-minted
  interior") is contradicted by `_mint_thing_interior` (2388–2447), which mints one shut.
- Fix: correct both docstrings; retire or rewrite the register bullet (per CLAUDE.md, the register
  first).

### F29 — The couple code and the reunion rule still assume the child holds a subset of rooms

- Severity: **STALE-DOC** (and the root of F2). Confidence: **CONFIRMED**.
- Where: `world/spatial_frames.py:2055-2057` and `2359-2361` ("`perform_split` gives the child
  every unzoned room"), `1159-1161` ("rather than every room the child's scene carries (the
  default, and the parent reunion's rule)") vs `1342-1366` (the child gets every room).

### F30 — Rationale comments that describe the deleted specialist fan-out

- Severity: **STALE-DOC** (low). Confidence: **CONFIRMED** against CLAUDE.md's 2026-09-27 deletion.
- Where: `world/spatial_containment.py:1358-1372` ("`entities` belongs to the objects specialist,
  `positions` to the spatial specialist, the two run in parallel on disjoint scopes"),
  `1731-1736`, `world/spatial_geometry.py:2025-2029`, `world/spatial_merge.py:2365-2378`. One
  encoder now writes every channel; the owners table survives, the parallel hands do not. The
  measurements quoted remain evidence; the mechanism they explain is gone.

### F31 — `docs/design/SPLIT_SPATIAL.md` is stale as a description

- Severity: **STALE-DOC** (low). Confidence: **CONFIRMED**.
- `Status: PROPOSED` (executed, per `docs/experiments/AUDIT_SPATIAL.md`'s execution record);
  module sizes (merge "1015", containment "644" → 2964, 3808); "Module-level state: There is none"
  (the facade now re-exports `_FIELD_CACHE` and `_SOUND_FIELD_CACHE`, `world/spatial.py:354,371`).

## Efficiency

Measured on stored scenes (read-only): chat 172 (22 rooms, 7 entities, 7 positions), 175, 63.
`merge_scene_with_diff(scene, {})` ≈ **11–13 ms steady** (first call 13–42 ms); `copy.deepcopy`
of the scene 1.5–2.5 ms; `json.loads` of the blob 0.4–0.8 ms. Profiled (10 merges, chat 172):
`copy.deepcopy` 0.132 s of 0.460 s (**29 %**), `site_plan.derive_site_plans` 0.132 s (**29 %**),
`effective_adjacent` 22 calls per merge (one per room, each walking every room),
`infer_room_levels._edges` likewise, `_entities_named` 41 linear scans per merge.

1. **The merge copies three times and many callers copy before calling** (per merge; merges per
   beat are many). `spatial_merge.py:1915` (scene), `1925` (diff), `2537` (contacts). Callers
   add their own: `agents/director_movement.py:3143`
   (`merge_scene_with_diff(copy.deepcopy(sc), copy.deepcopy(sd))` — four deep copies for one
   merge), `agents/director.py:1655`. Gain: ~2–3 ms per merge (≈ 20–30 %) by letting a caller that
   already owns fresh copies say so (`_owned=True`), or by copying the diff only where the merge
   stores incoming records. Cheap; correctness argument in 1908–1925 must be kept for the
   default path.
2. **Per-op and per-step full merges multiply (1).** `persist/commit_scene_state.py:1173` runs a
   whole merge per accepted inventory op when a beat has more than one;
   `agents/director.py:1662,1695` runs two merges per causal step when the step carries contact
   ops; `spatial_merge.py:1860-1907` (the causal program) does one scene deepcopy plus one merge
   per step, `copy.deepcopy(step)` per step, and keeps every step's `before`/`after` scene alive in
   `causal_worlds`. A 6-step beat ≈ 7 scene copies + 6 merges ≈ 80–90 ms on a 22-room scene before
   any caller-side work (an estimate from the per-merge figures above, not a measurement). Gain: merge only the channels a per-op preview needs, or reuse one working
   copy across steps.
3. **`derive_site_plans` re-derives every derived site from scratch on every merge**
   (`spatial_merge.py:2703-2704`), ~29 % of an empty merge. Cacheable on a fingerprint of the rooms'
   geometry fields; most merges change none.
4. **O(rooms²) passes per merge.** `_effective_anchors` walks every room for reverse edges
   (`spatial_geometry.py:591-604`, memoised only inside a read pass), `effective_adjacent` and
   `infer_room_levels` do the same per room, `_dedupe_adjacent` touches every room, and F24's dead
   phrase walk runs per mover. Negligible at 20 rooms; it is the term that grows with planned
   towns ("a town is planned as its ways and its lots", HEAD commit) and charter scenes. One
   reverse-edge index per merge would serve all of them.
5. **`canonical_subject_map` is rebuilt three times per merge** (`_onto_standing_spellings` ×2,
   `normalize_scene_subjects`) plus inside `canonical_subject`/`inside_as_holder` calls; each walks
   every entity and every subject ledger. Small today; one map per merge would do.

## Already registered

- `docs/UNBUILT_WORLD.md` §1.28 — the place-form residuals: a non-body inside a place-form
  interior is in no view; a story-written mint never gets the card's chain; a region the ledger
  names that an authored chain omits is dropped (`materialize_named_stations` gate 5); an exterior
  conduit's crossing time cannot be directed. Seen in code, consistent with the register (except the
  stale bullet in F28).
- `docs/UNBUILT_WORLD.md` §1.2 — no geometric validation of an asserted doorway
  (`_shield_minted_edges`' stated limits, 1263–1274).
- `docs/UNBUILT_WORLD.md` §1.79 — tolerant ledger lookups spelled several ways (the read-side
  sibling of F9/F15).
- `docs/UNBUILT_PIPELINE.md` (around line 780) — the possession/pose-detail history behind
  `invalidate_transferred_pose_details`; the language-pack gap in F17 is not registered there.
- Prior, non-register evidence: `docs/experiments/AUDIT_SPATIAL.md` (alpha 9.5) F12 (unknown room
  size read as medium) is FIXED in `effective_room_size`; its F2/F4 dead names were partly removed
  (the facade docstring records which four remain, verified still uncalled).

## Structure notes

- **Monoliths in miniature.** `merge_scene_with_diff` (`spatial_merge.py:1817-2706`, ~890 lines;
  318 at the split), `derive_inventory_placements` (containment 1686–1945, ~260),
  `infer_focus` (frames 463–707, ~245 with six closures), `perform_split` (1223–1424),
  `open_couple` (2155–2334), `_effective_anchors` (geometry 460–620, whose inner `add()` reads the
  enclosing loop variable `edge` at 544 — correct today, fragile), `advance_room_transits`,
  `materialize_named_stations`, `invalidate_contact_bound_poses`.
- **Natural seams.** `spatial_merge`: field merges + edge shields (164–1330) | structural repairs
  (1333–1610) | seating (1611–1815) | the orchestrator | the beat-chronology tail
  (`moved_within_beat`/`beat_movement_cuts`/`scene_as_of`, 2728–2964), which serves perception,
  not the merge. `spatial_containment` (3808 lines): scale (136–350) | the ledger and concealment
  (352–1045) | derivations from other ledgers (1045–2170) | interiors and the place form
  (2172–2895) | timed crossing (2897–3445) | departures/joins/facts (3446–3808).
  `spatial_frames`: the five `infer_*` (160–943) | split/merge surgery (944–1915) | couples
  (1917–2578). `spatial_geometry`: poses and the three pose-prose reconciliations (1457–2302)
  would make a self-contained `spatial_poses`.
- **One fact, several identity rules.** The enclosure question is answered with exact keys, with
  `same_subject`, and with casefolded strings (Q3 above, F1, F15). A single
  `holder_key(scene, spelling)` used by every reader would close the class.
- **Body-keyed scene ledgers outside `_SUBJECT_KEYED`.** `room_since`, `crossings`,
  `expired_entity_state` are keyed by body but neither folded by `normalize_scene_subjects` nor
  partitioned/merged by the frame code (copied whole to the child at a split, dropped from the
  child at reunion). Minor today (short-lived records); the same "two lists of one thing" the
  `_FRAME_SUBJECT_LEDGERS` comment (frames 1060–1065) warns against.
- **Module-level mutable state in the five files:** none (no `global`, no caches);
  `spatial_geometry` memoises through `world/scene_memo.py` (per read pass). The facade re-exports
  two caches from other modules (`_FIELD_CACHE`, `_SOUND_FIELD_CACHE`).
- **Unused facade imports.** `world/spatial.py:30-34` imports `copy`, `hashlib`, `re`,
  `defaultdict`, `Optional`, used by nothing in the facade (harmless; kept for attribute access).

## Docs checked

- `world/spatial.py` docstring: four retained names have no caller — **held** (grep: only defs and
  docstrings).
- `CLAUDE.md`: `world.scene` is the single runtime truth; `room_registry`/`world_entities` are
  projections — **held** for the merge (pure function); `world_entities` has no room column
  (`core/db.py:1171-1189`) — the assignment's `entities[x].room` does not exist.
- `CLAUDE.md` "twenty domains" / `docs/guides/PIPELINE.md:1334-1394` numbered commit list —
  **drifted**: `persist/commit.py:581` runs a `skip_lives` domain between scene and entities that
  the list omits (21 domains; "Domains 6 and 7" are 7 and 8). The relative order the frames code
  depends on (scene → … → cast → paradox → spatial) **held**.
- PIPELINE.md / `commit_scene_state.py:2364-2367`: `infer_came_from` → `infer_threshold_crossings`
  → `infer_focus` → `infer_facing`, after `infer_vehicle_zones` — **held**.
- `docs/guides/DATABASE.md:184/187`: `contained` derives a carried body's position transitively —
  **held** for the ledger form; the place form is not mentioned there. "This is separate from
  `inside`/`container`/`pocket`, which require the target's `container: true`" (248–250) —
  **held** for a non-body target, **not** for a body target (F14).
- `docs/guides/DATABASE.md:263-277`: `remove_anchors` and `movement_refused` are consumed at merge
  and never persisted — **held** (1990–2005, 1970–1978).
- `mind/knowledge_circles.py:24-27`: the row "rides ... frame split with no handling of its own" —
  **false** (F10).
- `world/spatial_merge.py:1748-1749` (`_onto_standing_spellings`): positions already let the fresh
  write win — **false** for aliases and case variants (F9).
- `world/spatial_containment.py:2463-2465` (`contain_posed_inside`): "inside the doorway" is left
  alone — **false** for a door entity (F13). `1889-1892`: a transfer cannot trigger the place form
  — **false** for `inside` (F14).
- `world/spatial_merge.py:2223-2234` and `spatial_transit.py:487-518`: the "tardis followed them
  into the tardis" case is closed — **false** while the carriage record stands (F6).
- `world/spatial_frames.py:1441-1445`, `2055-2057`, `2359-2361`, `1159-1161`; `spatial_geometry.py:820-823`;
  `spatial_containment.py:2553-2561`, `3100-3103`, `1358-1372` — **stale** (F26–F30).
- `materialize_named_stations` docstring "FOUR GATES" lists six (1, 2, 2b, 3, 4, 5) — cosmetic.
- `AGENTS.md:501-502` cite `spatial_facts`/`size_facts` as co-routes — **stale** (F23).
- `docs/design/SPLIT_SPATIAL.md` — **stale** (F31). `docs/UNBUILT_WORLD.md` §1.28 bullet
  "A non-body holder never gets an engine-minted interior" — **stale** (F28).
