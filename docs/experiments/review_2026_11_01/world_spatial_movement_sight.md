# Audit: world/spatial_{fov,contacts,routing,transit,walk,orientation}.py

Auditor scope: movement, sight, contacts, transit, bearings. Working tree at
84f3de23 (clean). Read-only; one focused test file run
(`tests/test_sightlines_cross_only_what_sight_does.py`, 6 passed). Every
snippet below ran on `.venv/bin/python` with `ENGINE_DB` pointed at a scratch
file; the owner's `engine.db` was opened `mode=ro` only, for counts. Snippet
files: `S/sn/wsms_corridor.py`, `S/sn/wsms_digest.py`, `S/sn/wsms_perf.py`,
`S/sn/wsms_route_perf.py`, `S/sn/wsms_dead2.py` (S = the scratchpad).

## Scope read

Read IN FULL, every line:

- `world/spatial_orientation.py` 1-468
- `world/spatial_walk.py` 1-548
- `world/spatial_routing.py` 1-1649
- `world/spatial_transit.py` 1-1631
- `world/spatial_contacts.py` 1-2019
- `world/spatial_fov.py` 1-2716

Read for context only (the readers/writers my findings touch; NOT audited):
`world/spatial.py` 1-140 (facade); `world/spatial_barriers.py` 220-330,
540-1200 (vocabularies, `frontier_joins`, `neighbor_map`, `edge_passable`,
`effective_adjacent`, `resolve_edge`, `normalize_scene_passages`);
`world/spatial_merge.py` 875-910, 1512-1600, 2235-2280, 2505-2545, 2630-2640
(merge order); `world/spatial_containment.py` 1285-1352;
`world/spatial_geometry.py` 286-292, 441-470, 623-690, 1384-1450;
`world/spatial_substance.py` 120-335, 920-935; `world/spatial_listener.py`
80-120; `world/spatial_sound_field.py` 1590-1625; `world/spatial_light_field.py`
301-315; `world/skip_itinerary.py` 1185-1265; `world/spatial_identity.py`
498-593; `world/charter_space.py` 80-140; `agents/director_movement.py` call
sites of `walk` (2040-2060, 2190-2215, 2391-2445, 2585-2625, 3040-3080,
3160-3180); `agents/perception.py` 2250-2282 (at 84f3de23);
`world/spatial_senses.py` 1135-1160, 1890-1910; `persist/commit_place_graph.py`
180-200, 300-330; `persist/commit_scene_state.py` 2860-2885;
`language_packs/ja/cards/system_prompts/encoder/{contact_ops,poses}.txt`;
`tests/test_sprint.py` 176-200, `tests/test_spatial_affordances.py` 225-252,
`tests/test_site_plan.py` 210-255, `tests/test_storeys.py` 1-60.

## Findings

Ordered most severe first. Line numbers are the current working tree.

### F1 — Nearly a fifth of written postures read as STANDING, so a body the fiction lays down behind a sill or counter is seen over it

- **Where:** `world/spatial_fov.py:161-174` (`_EYE_RANK`, `_POSTURE_TOKENS`),
  `:325-354` (`posture_word_class`, `posture_class`), read by `eye_rank`
  (`:356`), `_hold_doorways` (`:1949`), `_aloft_blocker` (`:2193-2194`),
  `body_visibility` (`:2557-2558`).
- **Code:**
  ```python
  _POSTURE_TOKENS = {"standing": "standing", "stands": "standing", ...
      "lying": "lying", "prone": "lying", "supine": "lying", "lies": "lying",
      "sprawled": "lying"}
  ...
  for token in _tokens(field):            # re.split(r"[^a-z]+", ...)
      if token in _POSTURE_TOKENS: return _POSTURE_TOKENS[token]
  return "standing"
  ```
- **Failure:** `poses[*].posture` is open free text (both packs' poses cards:
  "All are open, genre-neutral strings"), and the classifier is an English
  word list. Any posture it does not list reads `standing` (eye 2.0, the
  tallest body). Measured read-only over every active step output in the
  owner's db: **3,074 of 15,689 posture writes (19.6%) are unclassified**, at
  least 505 of them plainly low -- `reclining` (258), `pinned face-down in the
  soft tideline sand` (99), `bent forward, head lowered close` (69), `curled`
  (35), `crawling inside the narrow tube` (20). Over the current stored poses:
  36 of 191 (19%). A Japanese posture word classifies as nothing at all.
  Reproduced on `tests/test_site_plan.py::_window_over_the_garden`: with
  posture `lying` the body by the window a storey up is hidden by the sill
  (`visible False`); with `reclining` or `curled on her side` it is seen from
  the garden (`visible True, hidden_below 'waist'`). The same misread makes a
  reclining body's eye see over every waist-high fixture, and a body curled in
  a doorway "fill" it at standing height.
- **Severity:** LEAK (a body the fiction hides behind a fixture is delivered
  as seen, and its acts as seen: `spatial_senses.visual_level_between` folds
  `body_visibility` into every sight decision). CONFIRMED (db count + snippet
  `S/sn/wsms_digest.py`).
- **Fix:** do not widen the token list (CLAUDE.md: "NO WORD LISTS... a list
  that tries to anticipate how English will phrase something is the thing
  that fails"). Add a closed, engine-owned posture class to the pose record
  (`standing|sitting|kneeling|crouching|lying`), asked of the encoder beside
  the free `posture` text, and read the class first; the token pass becomes
  the legacy fallback. Test: a pose `{posture: "reclining", posture_class:
  "lying"}` behind a waist-high counter is hidden, and the same pose with the
  class absent behaves as today.

### F2 — `_part_identity` reads only ASCII, so every non-English body part has no identity: Japanese releases are discarded and moved limbs never move

- **Where:** `world/spatial_contacts.py:183` inside `_part_identity`
  (`:168`); everything built on it: `canonical_region` (`:217`),
  `_same_region` (`:247`), `_displaces`, `_mirrored_displacements`,
  `contact_id` (`:432`), and outside the file `spatial_substance` (`:136-138`,
  `:328-335`, `:929-931`) and `spatial_listener._is_an_ear` (`:89-91`).
- **Code:** `text = re.sub(r"[^a-z0-9]+", " ", str(part or "").casefold()).strip()`
- **Failure:** `_part_identity("左手") == ("", "")`, `canonical_region("口") ==
  ""`, `_same_region("口", "口") is False`, and `"épaule"` folds to `"paule"`.
  Consequences, each reproduced:
  1. A substance add into the very cavity the standing contact names is
     DISCARDED: contact `指 -> B, target_interior 口`, then `substance add
     target_interior 口` -> `0 records, "discarded substance add whose
     target_interior contradicted standing interior topology"`; the English
     equivalent (`finger`/`mouth`) lands.
  2. `_displaces` requires a non-empty kind, so re-asserting `手` on a new spot
     never retires the old one -- the behaviour the ja contact card promises
     ("新しい場所で `hand` を再び主張すれば…エンジンは古い場所を退かせます") and
     AGENTS.md's contact row states.
  3. `contact_id` hashes `canonical_region`, so every contact between the same
     two bodies with Japanese parts shares ONE id; `contact_action_ops` bind
     to whichever row, and `director_prose`'s standing-id check conflates them.
  4. `_is_an_ear("耳")` is False: covered ears never muffle a Japanese story.
  The ja contact card's own qualifier examples are Japanese (「左手」「もう一方の
  手」「尾の先」), so the shape is invited. Latent today: 0 of 118 stored
  contacts and 0 of 246 substances carry a non-ASCII part.
- **Severity:** WRONG-SCENE (language-pack hazard: a recogniser that works only
  for English in an engine that ships Japanese). CONFIRMED (snippets).
- **Fix:** fold with a Unicode-aware tokenizer (`\w`, NFKC) and keep the
  structural rule; the lateral-qualifier table (`_LATERAL_QUALIFIERS`) is
  English and needs the same treatment or a pack-supplied list. Test: the
  Japanese release above lands; `_displaces` fires for `手`->`手`; two
  Japanese parts get two `contact_id`s.

### F3 — A contact `remove`/`clear`/`cross` written in another spelling of a body silently misses, and the released hold stands

- **Where:** `world/spatial_contacts.py:1517-1531` (clear), `:1533-1556`
  (remove), `:1566-1575` (cross); caller `world/spatial_merge.py:2538`
  applies `diff["contact_ops"]` raw.
- **Code:**
  ```python
  actor = _contact_text(raw.get("actor"), 120).casefold()
  ...
  pair = {c["actor"].casefold(), c["target"].casefold()}
  if pair != {actor, target}: return True     # survives
  ```
- **Failure:** the ledger's endpoints are canonicalised (`normalize_scene_
  contacts` -> `canonical_subject`, the entity's display name), but release
  ops are matched on the raw op text. The encoder writes entity keys (the
  module's own note at `:1278-1290`: "the encoder wrote `char_emory_vane`…").
  Reproduced: ledger `Emory Vane hand -> Ada wrist`; `{op: remove, actor:
  char_emory_vane, target: Ada}` and `{op: clear, actor: char_emory_vane}`
  both leave the hold standing (`unasserted 1`), no report line. Adds work in
  either spelling only because hygiene canonicalises AFTER apply. A hold so
  missed then stands through every contact-silent beat (they do not age it)
  and is delivered to both minds as a live touch.
- **Severity:** WRONG-SCENE. CONFIRMED (snippet). Frequency not measured
  (needs a replay of each op against its pre-beat scene).
- **Fix:** canonicalise `actor`/`target` of every op (`canonical_subject`, or
  compare with `same_subject`) at the top of the op loop, once, as hygiene
  already does for adds. Test: the snippet above -- a remove and a clear in
  the entity-key spelling end the display-name-keyed hold.

### F4 — A vessel's journey is priced through a frontier MEDIUM join: a 13 km crossing arrives in 7 minutes

- **Where:** `world/spatial_transit.py:1309-1340` (`_shortest_way_paces`),
  `:1516-1517` (`journey_seconds`' only guard, `skip.add(origin)`).
- **Code:**
  ```python
  for edge in room.get("adjacent") or ():
      ...
      joins.setdefault(rid, {}).setdefault(other, []).append(edge)
  ```
  -- every raw edge, walls and unbuilt frontier joins included.
- **Failure:** AGENTS.md (frontier-join row): "A reader that walks
  `room["adjacent"]` itself must ask `frontier_joins`." This one does not. The
  lighthouse shape: landing --(stub join, `open_door`, no distance)-- mainland
  stub; channel (`floor: water`) 1.5 km to the landing, 13 km to the mainland.
  `frontier_joins` says the landing/mainland join is `medium` (no way of its
  own). Boat in the channel bound for the mainland at 7 kn:
  `departed_from: landing` -> 3,612 s (1.00 h, correct: the landing is
  skipped); `departed_from: cove` -> **422 s (0.12 h)**, priced channel ->
  landing (1.5 km) -> mainland (`near` doorway). Only the one origin the
  docstring names is protected. Walls are also taken as ways ("Any edge joins
  its two rooms"), against `effective_adjacent`'s "a wall is not a way through".
- **Severity:** WRONG-SCENE (the timed arrival docks the vessel hours early).
  CONFIRMED (snippet).
- **Fix:** build `joins` from `neighbor_map(scene, None)` minus walls (it
  already drops medium joins and reads far joins as `far`), and drop the
  origin special case. Test: the snippet's `cove` case prices 13 km.

### F5 — Under the owner's D2 a departure that names no space makes the room it stands in a MEDIUM: nobody may walk onto, across or off the beach

- **Where:** `world/spatial_transit.py:1225-1233` (D2: `route = ... str(origin)`)
  feeding `medium_rooms` `:957-982` (every under-way `route_room` is a
  medium); read by `world/skip_itinerary.py:1252-1264` (`Ways`) and
  `spatial_barriers.frontier_joins`.
- **Code:** `route = named or placed or kept or ("" if elsewhere else str(origin or "").strip())`
  then in `medium_rooms`: `route = str(transit.get("route_room") ...); out.add(route)`.
- **Failure:** D2 (2026-10-09) stands a journey that names no other space in
  the room it set off from by writing that room as its `route_room`;
  `medium_rooms` (2026-10-21) reads every under-way route room as "the rooms a
  body does not walk into, across or out of". Reproduced: TARDIS docked on a
  beach, written `{phase: in_transit, hatch: closed}` -> `route_room: beach`,
  `medium_rooms == {'beach'}`, and the skip's walk graph has no edge out of
  the beach and none into it from the village. 18 stored TARDIS writes are
  this shape (UNBUILT_WORLD §1.194). A frontier stub hung off the beach would
  also read as "across a medium".
- **Severity:** WRONG-SCENE (bodies on the beach are stranded in every skip
  while the box is "under way"). CONFIRMED (snippet).
- **Fix:** `medium_rooms` should count a route room only when it is not the
  journey's own `departed_from` (D2's moving-within case), or D2 should mark
  the case (`within: true`) and `medium_rooms` skip it. Test: the snippet --
  `medium_rooms` is empty and Rose can walk to the village in a skip.

### F6 — A body or thing CONTAINED in a vessel stays where the vessel left when the vessel goes into no room

- **Where:** `world/spatial_transit.py:1263-1270` (`settle_departures` takes
  the vessel out of `positions`/`stations` only); `world/spatial_containment.py:
  1334-1335` (`derive_contained_positions`: `if room is None: continue`).
- **Failure:** two representations of one fact: `contained[Ada] = {in:
  skiff}` and `positions[Ada]`. Reproduced through `merge_scene_with_diff`:
  skiff on the quay with Ada contained in it, written `in_transit`,
  `destination_room: harbour`, no route -> the skiff is in no room (the
  2026-09-25 rule), Ada stays `positions: quay` with her containment intact,
  in view of everyone on the quay. This is §1.194's class ("an unnamed
  departure stands at origin") one level down, for the vessel's CONTENTS;
  §1.225 covers only a body written into the route room.
- **Severity:** WRONG-SCENE. CONFIRMED (snippet). Rare today (UNBUILT_WORLD
  §1.225 measured 16 of 17 departing bodies in the vessel's rooms, not
  `contained`).
- **Fix:** when `settle_departures` stands a vessel in no room, do the same
  for everything `carrier_chain` puts in it (`stand_in_no_room` on each), or
  have `derive_contained_positions` drop the position of a body whose
  outermost carrier has none. Test: the snippet -- Ada leaves the quay with
  the skiff.

### F7 — `walk`/`passable_path` cannot cross a link that admits the walker, though `passable_route_exists(body=)` says the route exists

- **Where:** `world/spatial_routing.py:1184-1215` (`passable_path`, no `body`
  parameter: `passable_neighbors(scene)`), `:686-722`
  (`passable_route_next_step`), `world/spatial_walk.py:393`.
- **Failure:** `_link_edge` (`spatial_transit.py:392-416`) derives a closed
  admitting link as `{barrier: wall, admits: [...]}`. Reproduced on the
  shrine's Seal shape: `passable_route_exists(cavern, realm,
  body='Amaterasu') == True`, but `passable_path == []`,
  `passable_route_next_step is None`, `walk(...) is None`. In
  `director_movement` that means: a declared walk is teleported with no cell
  or walk record (`:2610-2611`), a follower is skipped (`:2062-2063`), and a
  continuing walk is held "no passable route" every beat (`:3074-3080`). Two
  answers to one question on two graphs.
- **Severity:** WRONG-SCENE. CONFIRMED (snippet).
- **Fix:** give `passable_path`, `passable_route_next_step` and `walk` the
  `body` parameter `passable_route_exists` already has and pass it through
  (`passable_neighbors(scene, body)`). Test: the snippet -- the admitted body
  walks into the realm; a stranger does not.

### F8 — Any positioned THING on a doorway cell blocks sight through it as a standing body

- **Where:** `world/spatial_fov.py:1928-1951` (`_hold_doorways`) against
  `world/spatial_walk.py:95-115` (`held_cells`, which asks `scene_names_body`).
- **Code:** `for name, room_id in positions.items(): ... rank =
  _EYE_RANK.get(posture_class(scene, name), 2.0)` -- no body test, and
  `posture_class` of a key is `standing`.
- **Failure:** "A body in a doorway is the door" has two readers that
  disagree on what a body is. Reproduced: a `brass key` entity pinned on a
  doorway cell -> `body_visibility(Obs, Tgt)` through that doorway goes
  `visible True` -> `False, occluded_by 'brass_key'`, while the walk's
  `held_cells` ignores it. A lantern set down on a threshold hides the next
  room like a person. (It also ignores flight: `eye_rank`'s altitude bump is
  not used.)
- **Severity:** WRONG-SCENE (over-subtraction). CONFIRMED (snippet).
- **Fix:** skip names `scene_names_body` refuses (as `held_cells` does), and
  use `eye_rank` for the height. Test: the snippet's key no longer hides Tgt.

### F9 — The cone still hides a hash-placed doorway when the edge was declared only from the FAR side

- **Where:** `world/spatial_fov.py:2343-2370` (`_unbeared_doorways`), used by
  `feature_visibility` (`:2296-2317`).
- **Code:** `for edge in room.get("adjacent") or []:` -- the observer room's
  own edges only.
- **Failure:** UNBUILT_PERCEPTION §1.147 (FIXED 2026-09-06) says "The cone may
  not hide a doorway whose bearing nobody declared, on either side of the
  edge". A doorway declared only by the far room (31.3% of room pairs are
  one-sided, Design.md) still gets an implicit, hash-placed anchor
  (`effective_anchors`), but never enters the carve-out set. Reproduced: room
  X with no edges, Y declares `{to: x, open_door}` with no `dir`; facing s, sw
  or w, `door:y` is culled with `basis 'cone'` (and is given a hash `side`);
  declared from X's side it is never culled. This is §1.147's own failure
  (the way on hidden behind you) for the far-declared half.
- **Severity:** WRONG-SCENE. CONFIRMED (snippet). Not in the registers as open.
- **Fix:** iterate `effective_adjacent(scene, room_id)` (whose derived edges
  carry the far side's reversed bearing) instead of the raw list. Test: the
  snippet's far-declared doorway is never culled and claims no side.

### F10 — `visible_adjacent_rooms` ignores `sight_from` on its reverse pass: the watcher of a mirror declared from the blind side sees nothing

- **Where:** `world/spatial_routing.py:1606-1620`.
- **Code:** `or barrier == "one_way_window"` -- every reverse-declared one-way
  window is skipped, whatever `sight_from` names.
- **Failure:** `sight_direction`'s docstring endorses repairing a mirror "by
  naming a room rather than by deleting a declaration": cell declares `{to:
  annex, one_way_window, sight_from: annex}`, annex declares nothing.
  Reproduced: `spatial_rel(annex, cell)` -> `one_way_window`, `sees_across`
  -> True, but `visible_adjacent_rooms(annex) == []`. The watcher's view,
  `seen_onward`, and the place graph (`commit_place_graph`) all lose the room
  the interviewer is there to watch. Design.md "A sightline crosses only what
  sight does" says `visible_adjacent_rooms` "now asks [sees_across] too
  instead of its own copy" -- only its forward loop does.
- **Severity:** WRONG-SCENE (subtracts more than the rule); STALE-DOC on the
  Design.md row. CONFIRMED (snippet).
- **Fix:** in the reverse loop replace the unconditional skip with
  `not sees_across(all_rooms, room_id, other_id, barrier)`. Test: the snippet
  -- annex sees the cell, the cell does not see the annex.

### F11 — `travel_bearing` reverses a one-sided stair: a climber's facing flips 180 degrees depending on which floor declared it

- **Where:** `world/spatial_orientation.py:133-150` (`travel_bearing`'s
  back-edge branch); the same reversal in `spatial_barriers.effective_adjacent`.
- **Code:** `bearing = normalize_bearing(back.get("dir")); if bearing: return opposite_bearing(bearing)`
- **Failure:** `normalize_scene_bearings` (`:228-249`) rules "A STAIR IS ONE
  SHAFT ... a floor that names none takes the other's ... never its
  opposite" -- but it only reconciles pairs declared from BOTH sides. For a
  stair declared only upstairs (`{to: hall, dir: n, vertical: down}`):
  `travel_bearing(hall, up) == 's'`; the same stair declared from both sides
  gives `'n'`; and `effective_adjacent(hall)` derives the stair foot on the
  `s` wall. So after a climb `infer_facing` faces the body the opposite way
  and every left/right in the next view is mirrored, by an accident of which
  side wrote the edge.
- **Severity:** WRONG-SCENE. CONFIRMED (snippet). Frequency unmeasured.
- **Fix:** in `travel_bearing` (and `effective_adjacent`'s derivation) return
  the back edge's bearing unreversed when either side carries `vertical`.
  Test: one-sided and two-sided declarations of one stair give the same
  `travel_bearing` both ways.

### F12 — `_onward_exits` counts windows, bars and one-way panes as ways ON, so a chamber whose only other opening is a window is never a dead end

- **Where:** `world/spatial_routing.py:1453` and `:1470` (`_onward_exits`),
  read by `visible_adjacent_rooms` -> `commit_place_graph` (`known_dead_ends`,
  `closed`) and `agents/character.py` (`onward_exits_visible`,
  `onward_bearings`, `visibly_no_way_through`).
- **Code:** `if normalize_barrier(edge.get("barrier")) == "wall": continue` --
  the only exclusion.
- **Failure:** reproduced: a chamber whose only edge besides the way in is a
  `window` (or `bars`) reports `{'onward_exits': 1, 'onward_bearings': ['n']}`.
  The function exists so a maze runner is not sent into a dead end hunting
  an exit (its docstring's measured case: "walked west into it four times");
  this hands him a north "exit" that is glass. The engine's own route rule
  (`_ROUTE_MEMORY_BARRIERS`' docstring: a map that records a window as a
  doorway "sends its owner marching at a pane of glass") is the class.
  `unknown` and `separated` count too.
- **Severity:** WRONG-SCENE. CONFIRMED (snippet `S/sn/wsms_corridor.py`).
- **Fix:** count only `route_memory_barrier` edges (open, open_door,
  membrane, closed_door) and admitting links; keep the reverse-declared pass.
  Test: window-only chamber -> `onward_exits: 0`.

### F13 — `corridor_sightlines` calls a closed door or a curtain straight ahead a TURN ("bends and continues")

- **Where:** `world/spatial_routing.py:1116-1148`.
- **Code:** `onward` keeps every non-wall edge; `straight` requires
  `sees_across`; `if not straight: terminus = "turn"  # The passage bends`.
- **Failure:** reproduced (corridor A-B-C, C->D straight north):
  `closed_door` -> `{"terminus": "turn", "distance": 2}`; `membrane` -> `turn`;
  a dead end whose only other edge is a side `window` -> `turn`. The payload
  goes raw into every character's `corridor_sight` (`agents/character.py:4560`),
  telling them the passage north bends on, when it ends at a door. The
  docstring promises "sight follows the line until the passage turns, a door
  blocks it, or the dark swallows it" and no `door` terminus exists.
- **Severity:** WRONG-SCENE. CONFIRMED (snippet). No test pins it.
- **Fix:** before the `straight` test, a single onward edge in the line's
  heading that sight does not cross ends the line as `"door"` (a new
  terminus the renderer must learn, or `dead_end` if the owner prefers);
  see-through side openings should not make a junction. Test: the snippet's
  three shapes.

### F14 — `sprint_reach` says `stops: "door"` for a dead end whose only other edge is a wall or a window

- **Where:** `world/spatial_routing.py:1372-1390`.
- **Failure:** `onward` is every `effective_adjacent` edge except the way
  back -- own-side `wall` edges and windows included -- so it is non-empty,
  `passable` is empty, and the run reports "The only way on is shut" for a
  room with no way on. Reproduced for both. A runner is told to expect a door
  he may open. `tests/test_sprint.py:176-188` pins `"door"` for the window
  case (its subject is "you cannot run through glass", so the label looks
  incidental); the wall case is unpinned.
- **Severity:** WRONG-SCENE (low). CONFIRMED (snippet).
- **Fix:** compute `onward` over route-memory barriers only, so a wall or a
  pane leaves `dead_end`. Test: wall-only and window-only ends -> `dead_end`
  (update the pinned assertion with the owner's agreement).

### F15 — The Director's sight digest throws away every cross-storey answer; `body_visibility`'s contract no longer names the basis that produces it

- **Where:** `world/spatial_fov.py:2697-2700` (`_sight_digest`), docstring
  `:2509-2512`, module docstring `:28-31`.
- **Code:** `if rec["basis"] != "line": if room_of(scene, b) == room: seen.append(b); continue`
- **Failure:** since site plans, `body_visibility` returns `basis: "plan"`
  for two rooms of one plan a storey apart -- visible or hidden, with no
  measured station needed. The digest only accepts `line`. Reproduced on the
  window-over-the-garden fixture: the visitor sees Hinami (`visible True,
  basis plan`), the digest says `sees: {Visitor: [], Hinami: []}`; with her
  deep in the room (hidden by the sill) `hidden: []`. The docstring still
  says it "Subtracts ONLY when both bodies hold a measured station (`basis`
  "line"); otherwise ... basis "open"". `spatial_senses:1148` already reads
  `("line", "plan")`; `perception._line_of_sight_blocked` reads `line` only
  (same-room pairs, so no live effect there).
- **Severity:** SILENT-NOOP (computed, then dropped) + STALE-DOC. CONFIRMED.
- **Fix:** treat `plan` like `line` in `_sight_digest`; restate the contract
  as three bases. Test: the fixture's digest lists the sighting / the hiding.

### F16 — A refused contact op still counts as "contact talk" and ages every standing hold

- **Where:** `world/spatial_contacts.py:1342-1365`.
- **Code:** `if _clean_contact(raw) is not None: return True` -- no `scene`,
  so the scene-dependent refusals (placement verb between bodies, empty
  whole-body touch, worn-garment party) cannot refuse here.
- **Failure:** docstring: "A beat with no ops (or only junk) is not evidence
  of anything". Reproduced: A's hold on B's wrist (`unasserted 1`); the beat's
  only op is `C -> B, manner "stand"`, refused and reported -- the hold
  retires anyway. Placement verbs are the measured commonest refusal.
  Related to, not the same as, the registered §1.28 asymmetry (strangers'
  VALID contacts age everyone's).
- **Severity:** WRONG-SCENE (low). CONFIRMED (snippet).
- **Fix:** pass the scene (`_clean_contact(raw, scene)`); `apply_contact_ops`
  has it. Test: the snippet keeps the hold.

### F17 — The 40-contact cap evicts by first insertion, so a hold that never ages is the first to go

- **Where:** `world/spatial_contacts.py:1338` and `:1819`
  (`list(...)[-_MAX_CONTACTS:]`).
- **Failure:** re-asserting a key keeps its dict position; only a displacement
  re-inserts. Reproduced: 41 contacts, oldest not re-asserted this beat ->
  silently dropped, no report. A bearing hold `_hold_the_containment_keeps`
  exempts from ageing is by construction the oldest, so it is evicted first
  and the contact and containment ledgers disagree again -- the defect that
  exemption was built to close.
- **Severity:** WRONG-SCENE (low; needs 41 standing contacts). CONFIRMED.
- **Fix:** evict by staleness (`unasserted`, then age), never a containment-
  kept hold, and report the eviction. The cap itself is the owner's.

### F18 — `SWEEP_REACH_PACES` is "the owner's cap on what a sweep takes in", and nothing has ever read it

- **Where:** `world/spatial_fov.py:176-180`.
- **Failure:** whole-repo scan (`S/sn/wsms_dead2.py`, every .py/.js/.json/
  .txt/.html outside docs): one occurrence, its definition. History: added
  2026-09-15 (aeecf008), raised to 96 (1e00bece), deleted by dab39f66 with
  the note "read by nothing", restored by the revert 594e4f67. A sweep is
  bounded by the field, not by this.
- **Severity:** DEAD + STALE-DOC (a named cap that caps nothing misleads a
  reader of the owner's numbers). CONFIRMED.
- **Fix:** delete it, or wire it if the owner wants a sweep cap.

### F19 — `cover_between` has no caller anywhere

- **Where:** `world/spatial_fov.py:2659-2663`; re-exported by
  `world/spatial.py:338`.
- **Failure:** whole-repo scan: definition and facade import only, no test;
  its last test import went in 822c02e9 (2026-09-04). The facade docstring
  says "Four public names here have no caller anywhere ... RETAINED
  deliberately" and does not list it, so the count is also stale.
- **Severity:** DEAD. CONFIRMED (grep + history).
- **Fix:** delete it, or add it to the facade's retained list with a reason.

### F20 — Two bearing comments still describe the collision rule the owner changed on 2026-10-03

- **Where:** `world/spatial_orientation.py:189-190` ("Contradictions and
  same-bearing collisions are dropped rather than guessed") and `:390-394`
  (`DERIVED_BEARING_LIMIT`: "sharing is the collision
  `normalize_scene_bearings` already drops both sides of").
- **Failure:** since 2026-10-03 two horizontal doorways on one wall are kept
  and spread (`_spread_along_wall`, `:340-350`); only vertical ways of one
  kind still drop. The limit's stated reason no longer exists, so the ninth
  doorway's refusal in `derived_edge_bearings` now rests on nothing written.
- **Severity:** STALE-DOC. CONFIRMED (reading).
- **Fix:** restate both; whether a derived doorway may now share a wall (with
  an offset) is the owner's call.

## Efficiency

Measured live scenes are small in ROOMS (largest stored scene: 24 rooms,
chat 63) but large in CELLS (16 of 1,093 stored rooms hold 1,000+ cells;
the largest a 60x60 garden, chat 167). So the per-cell work is what is hot.

1. **`body_visibility` runs a full-field shadowcast per call, unmemoized**
   (`spatial_fov.py:2625`, `_visible_set` `:2038-2062`). The cast depends on
   (observer cell, eye, target top, supports), not on the pair, and
   `side_max` is an O(field cells) `max` recomputed every call (30% of the
   time in the profile). Called by the Director digest (n² pairs), by
   `visual_level_between` (every sight decision), by `composer` and by
   perception, inside a read pass that memoizes the field but not this.
   Measured (`S/sn/wsms_perf.py`): 8 bodies, 56 pairs -- 12x12 room 15 ms,
   40x40 190 ms, 64x64 409 ms, 96x96 912 ms (96% in `_visible_set`); the
   slowest stored digest 74 ms (chat 122). Fix: memo `body_visibility` per
   (observer, target) in the pass; cache the cast per (origin, eye, top-rank,
   supports key) -- five posture ranks; compute the reach from the field's
   bounds once. Expect the digest to drop by roughly the pair count over the
   observer count (7x at 8 bodies), and every repeat read to near zero.
2. **Within-room paths copy the whole path per heap push**
   (`spatial_walk.py:204`, `_path_past_fixtures` `:225-229`) and
   `landing_cell` sorts every cell of the room (`:292`). Measured in a 96-pace
   room: `cell_path` corner to corner 38 ms, `landing_cell` 31 ms, `walk`
   52 ms -- per walker per beat. Fix: parent map instead of path tuples,
   Manhattan-heuristic A*, and ring-scan instead of a full sort. 5-10x.
3. **`passable_path`/`passable_route_exists`/`passable_neighbors` rebuild the
   whole passable graph on every call** (`spatial_routing.py:1207-1208`,
   `:757`, `:664`), even for one step and whatever `limit` says; ~15 call
   sites per beat. Measured: 0.2 ms at the 24-room live scene, 6 ms at a
   synthetic 900-room grid (`S/sn/wsms_route_perf.py`). Not hot today; it is
   O(world) per call the day a town lives in one scene. Fix: `scene_memo` the
   graph per pass, keyed by `body`. Same shape, cheaper: `effective_adjacent`
   scans every room per call (0.63 ms at 900 rooms) inside the per-room loops
   of `corridor_sightlines`/`sprint_reach`.
4. **`contradictory_sight_edges` is O(rooms²) once per commit**
   (`spatial_routing.py:346-349`): 0 ms at 24 rooms, 59 ms at 400, 292 ms at
   900. Fix: iterate one-way-window edges only (O(edges)).
5. **`walk` recomputes `held_cells` once per far door cell**
   (`spatial_walk.py:500-501`) and `blocked_cells` once per candidate cell
   (`:477-479`); each `held_cells` walks every position and derives a
   `body_cell`. Small; hoist both out of the generator.
6. **`_ANCHOR_CACHE` clears wholesale at 256 entries**
   (`spatial_fov.py:684-686`) and the seeded crowding search calls
   `RoomGrid.rim()` (O(cells) plus a sort) for every trial offset
   (`:862-866`). Content-cached, so cold-path only; an LRU and a per-grid rim
   cache would remove the cliff.
7. **`apply_transit_dock_edges` scans every room once per link and once per
   holder** (`spatial_transit.py:748-757`, `:913-924`), on every merge (several
   per beat). Small at today's sizes.

## Already registered

- **UNBUILT_WORLD §1.138** -- an anchor with no bearing is placed on the
  floor, not against a wall. Still true, but the entry's mechanism is stale:
  it quotes `1 + seed % (w - 2)` (interior only); the code now seeds
  `seed % w` over the whole floor, ring included (owner ruling 2026-09-16),
  and since 2026-10-12 moves the fixture off doorways and other fixtures
  (`spatial_fov.py:871-897`). The register should be restated.
- **UNBUILT_WORLD §1.145** -- 62% of bodies have no facing. Checked as asked:
  nothing in these six files breaks on a `None` heading (`turn_bearing`,
  `relative_bearing`, `lateral_of`, `_cone_sector`, `feature_visibility`,
  `neighbour_feature_visibility`, `body_visibility`, `_stand_cell`, `_inward`
  all fail open). Bearing math verified exhaustively for 8x8 pairs, wrap
  (`nw`->`n` is `ahead_right`), turns and mirror (`n` facing: `e` is right).
- **UNBUILT_WORLD §1.194** -- departure residuals (unnamed departure stands
  where it set off; hatch not carried; sealed with no route severs). F5 and F6
  are new consequences of the same rules, not listed there.
- **UNBUILT_WORLD §1.219** -- "Sight still crosses a far way as a doorway"
  (owner's 2026-10-05 ruling). Confirmed: `sight_passes` (`spatial_fov.py:
  1732`) and `light_passes` lay a `{open, far}`/13 km neighbour flush against
  the wall (a body 13 km off seen `basis line` through it), while
  `sound_passes` refuses since 2026-10-20. Three predicates of one placement
  now disagree; the owner's call.
- **UNBUILT_WORLD §1.225** -- a body written into the route room is not aboard.
- **UNBUILT_WORLD §1.228** -- an ordinary beat's walk and the charter do not
  read `medium_rooms` (`passable_path` walks onto the water by the medium's
  own `open` ways).
- **UNBUILT_WORLD §1.28** -- contacts age only on contact-talk beats; a
  contact is retired by strangers and never by its participants. F16 is a
  narrower, unregistered variant (REFUSED ops count).
- **UNBUILT_WORLD §1.132** item 1 -- a posture that means "carried"; needs the
  posture table exported. Different from F1 (misread low postures).
- **UNBUILT_PIPELINE §1.32** -- a region's owner is known only by slot.
- **UNBUILT_PERCEPTION §1.147** -- the cone hiding the way on: FIXED, but F9
  is a gap in that fix.
- The contact `relation`/`motion` enums vs producers (asked): over 12,073
  `contact_ops` blocks in active step outputs the encoder wrote only
  `surface` (9,724) / `interior` (814) and `settled` (7,665) / `moving`
  (2,876), plus 2 prose values in `motion` that fall back to the manner/detail
  word scan. The enum is honoured; not a finding.

## Structure notes

- **Monoliths in miniature:** `apply_contact_ops` (`spatial_contacts.py:
  1396-1827`, ~430 lines; the refusal-report block `~:1612-1750` is its own
  function); `_clean_contact` (`:928-1095`); `settle_departures`
  (`spatial_transit.py:1005-1271`, ~110 lines of docstring over a ~150-line
  rule chain); `apply_transit_dock_edges` (`:689-925`); `body_cell`
  (`spatial_fov.py:1304-1440`); `body_visibility` (`:2502-2656`);
  `walk` (`spatial_walk.py:357-538`); `sprint_reach` (`spatial_routing.py:
  1230-1409`, 140 lines of docstring).
- **Seams:** `spatial_routing.py` is three modules -- edge distance
  (`_distance_text`, `edge_metres`, `normalize_edge_distance`, `is_long_way`),
  the sight readers (`sight_direction`..`contradictory_sight_edges`,
  `spatial_rel`, `_across_the_medium`, `visible_adjacent_rooms`,
  `_onward_exits`, `_is_carried_interior`, `corridor_sightlines`), and the
  walks (`passable_*`, `nearby_rooms`, `rooms_walked_within`,
  `rooms_under_one_roof`, `_walk_steps`, `attended_rooms`,
  `_body_enclosure_rooms`, `sprint_reach`). `spatial_fov.py` splits into
  cells (grid, `_place_anchors`, `anchor_cells`, `body_cell`, `_stand_cell`,
  `_resting_cell`, `_stand_grades`, `_floor_things`) and sight (lines,
  `_Field`, `room_field`, the answers). `spatial_walk` already imports five
  PRIVATE names from the cells half (`_door_cells`, `_inward`,
  `_floor_things`, `_stand_grades`, `_anchor_stand_cells`) -- the seam is
  real. `spatial_transit.py`: dock edges/links, departures, journey pricing
  and speed, ambient scope.
- **Module-level mutable state:** `spatial_fov._ANCHOR_CACHE` (`:690`),
  written only by `_anchor_cells` (`:676-687`), shared across scene objects;
  `anchor_cells` copies each record and its `cells`, but nested lists such as
  `rec["cell"]` are still the cached objects, so a caller that mutated one
  would corrupt every later read. No other module state in the six files.
- **Two copies of one rule:** `fold_body_id` (`spatial_transit.py:387`) and
  `edge_admits`' inline `fold` (`spatial_barriers.py:876`) are the same regex;
  `posture_word_class` and `posture_class` repeat one token loop;
  `visible_adjacent_rooms` and `_onward_exits` each re-derive reverse edges
  `effective_adjacent` already derives (and diverge from it: F10).
- **Readers of "who is in the doorway":** `_hold_doorways` (any positioned
  name), `held_cells` (bodies only), `stands_in_doorway`/`at_doorway`
  (stationed `at` the door OR on its cell -- yet `body_cell` stands an `at:
  door:x` body one pace INSIDE, so for sight and walk such a body is not in
  the doorway at all). Three answers to one question.

## Docs checked

- AGENTS.md, contact row ("re-asserting the same limb on a new spot MOVES
  it"; "do not add a synonym table"): holds for ASCII parts; FAILS for any
  non-ASCII part (F2). The no-synonym-table rule holds.
- AGENTS.md, containers row (membrane overrides an authored `open_door`;
  closed transparent -> `window`; `_is_carried_interior`): held
  (`spatial_transit.py:281-305`, `:801-813`; `spatial_routing.py:1006-1040`).
- AGENTS.md, frontier-join row ("a reader that walks `room["adjacent"]`
  itself must ask `frontier_joins`"): held by `visible_adjacent_rooms` and
  `_onward_exits`; VIOLATED by `_shortest_way_paces` (F4). `derived_edge_
  bearings` also walks raw edges without asking, harmlessly (its consumers
  drop the join).
- Design.md "A sightline crosses only what sight does" (`visible_adjacent_
  rooms` asks `sees_across` "instead of its own copy"): half true -- the
  reverse pass keeps its own copy (F10).
- Design.md "A journey under way ... arrives when its way is done" ("shortest
  chain of the world's own edges ... never back through the room it left"):
  holds literally; the chain admits frontier medium joins and walls (F4).
- Design.md "Adjacency resolves both ways for EVERY reader": not for
  `_unbeared_doorways` (F9) or `travel_bearing` (F11).
- Design.md "Multi-room movement (running)" (`sprint_reach` decision-bounded;
  `passable_path` reconstructs rooms crossed): held.
- Design.md "One-way PASSAGE is a field": held -- `passable_neighbors` uses
  `directional=True`; `edge_passable` honours `passage_from`.
- `spatial_fov` module docstring ("OCCLUSION between two bodies needs BOTH
  bodies to hold a measured station") and `body_visibility`'s: stale since the
  `plan` basis (F15).
- `world/spatial.py` facade docstring ("Four public names ... no caller"):
  stale -- `cover_between` is a fifth (F19).
- `spatial_routing.passable_route_exists` docstring (closed door, wall,
  unknown do not count; directed by `passage_from`): held. Closed doors, as
  asked: every routing primitive in these files treats `closed_door` as
  impassable THIS beat (`_PASSABLE_BARRIERS`), sight as opaque
  (`sight_passes`, `_SIGHT_BARRIERS`), sound as attenuated (`sound_passes`);
  the bubble walks (`_walk_steps`) count it one room, by design. The three
  readers agree; the label readers do not (F13, F14).
- `spatial_walk` docstring (two owner numbers, 1.8 paces/s and 10 s) and
  `cell_path`'s "FURNITURE IS NEVER A WALL": held.
- `normalize_scene_bearings` docstring and `DERIVED_BEARING_LIMIT` rationale:
  stale (F20).
- UNBUILT_WORLD §1.138's formula: stale (see Already registered).
