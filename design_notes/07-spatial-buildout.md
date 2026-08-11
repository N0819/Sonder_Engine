# Spatial buildout: derived depth for deterministic perception

Successor to `02-spatial-fov-gaps.md`. The owner has authorised building the
spatial system out as a legitimate path to better non-agent perception, which
un-defers the items note 02 parked. This note designs that buildout.

Two framings govern everything below:

1. **Composer-independent value.** The Director, the character agents, and the
   model-based perception path all read the same per-observer projection
   (`_observer_scene_payload`, `agents/perception.py:849-1052`). Every
   proposal is ranked partly on whether it pays off even if the composer
   (note 03) never ships.
2. **Derived or defaulted, never author-dependent.** The measured failure mode
   is the silently empty field: `stations` was prompted for since Phase 2,
   merged by `spatial.merge_scene_with_diff` forever, and appeared in 0 of 45
   live scenes (`schemas.py:1770-1777`); the fresh corpus count below says the
   fix lifted it only to 11% of bodies. CLAUDE.md documents the same failure
   for psychology (`drive` empty for 150 beats, nothing objected). So every
   field below is classified **derived / defaulted / authored**, an authored
   field must carry a derivation or default as fallback plus a coverage
   warning, and a proposal that only adds author obligations is rejected on
   principle — it also contradicts note 04's goal of *reducing* the Director's
   mechanical burden.

The owner's bar: "same quality as the current engine, just faster." Buildout
is justified where it protects that bar under determinism (a leak the model
used to paper over) or raises quality outright — never as simulation for its
own sake. Section 9 states where fidelity stops buying anything.

---

## 1. Corpus ground truth

Method: all 64 live `world.scene` blobs (61 chat-scoped + 3 frame-scoped) in
the read-only snapshot at `engine.db` (2,296 turns). Aggregates only. Caveat:
these are *end-state* scenes, one per chat/frame, not per-turn history —
coverage over the whole corpus of historical turns is unmeasured (it would
require walking checkpoint snapshots) and is flagged unverified where it
matters.

**Rooms (n=416):**

| field | present | note |
|---|---|---|
| `size` | 217 (52%) | vocabulary in the wild: `large` 101, `small` 108, `medium` 8. **`huge`/`vast` appear 0 times** — D2's exact-match bug (`spatial.py:1374-1376`) is currently unfired live, but the trap is loaded in `_ROOM_COST` (`spatial.py:5279`) |
| `light` | 45 (11%) | absent defaults to lit (`RoomDef.light` comment, `schemas.py:1098`) — safe |
| `exposure` | 56 (13%) | keyword-derivation fallback exists (`weather.room_exposure`) — safe |
| `anchors` | 179 (43%) | 618 anchors total; **595 (96%) carry `dir`** — when anchors exist at all, they are bearing-rich |
| `zone` | 151 (36%) | |

**Edges (n=564):**

| field | present | note |
|---|---|---|
| `barrier` | 564 (100%) | vocabulary clean: `open` 224, `closed_door` 120, `open_door` 114, `wall` 98, `membrane` 8. **`window` and `bars` appear 0 times live** — those two `hear_level`/`_SIGHT_BARRIERS` branches have never fired on real data |
| `dir` | 221 (39%) | the egocentric starvation point |
| `distance` | **484 (86%)** | note 02's D5 said "unverified whether any live scene authors it" — the answer is *almost all of them*, in **29 distinct surface forms**: `near` 224, `close` 61, `immediate` 42, `short` 20, plus raw numbers (`10` ×24, `1` ×28), metric strings (`2m`, `20m`, `50m`, `200 m`), `1 step`, `mid`, `moderate`… The only value any code consumes, `remote` (`hear_level`, `spatial.py:1046` region), **appears 0 times**. This is an unnormalized free-text field whose one load-bearing value is never authored — the exact inverse of the stations failure: data everyone writes and nothing can read |
| `vertical` | 31 (5.5%) | |

**Bodies and within-room position:**

- 522 positioned bodies; **55 (10.5%) have a station** (`scene.stations` present in 17 of 64 scenes, 56 entries, all `{at, near}` shaped).
- 1,012 co-located body pairs; only 12 (1.2%) are linked by a standing
  `contact` or a pose `relative_to`. Multi-occupant rooms are the *norm*, not
  the exception: of 185 occupied room-instances, 108 (58%) hold ≥2 bodies
  (2 occupants ×30, 3 ×28, 4 ×16, ≥5 ×34); 61 of 64 scenes have at least one.
  **54 of the 108 multi-occupant room-instances have zero anchors** — even a
  perfect station-derivation starves in half of them without S1a below.
- Of 25 large-room multi-occupant instances (the "great hall" case), **6**
  have any occupant at a station — so `proximity_rel` (`spatial.py:1358`)
  returns its `near` default for roughly 90% of the pairs that matter, which
  is the measured form of "everyone in a great hall reads as `near`".
- 1,868 cross-room body pairs; **330 (17.7%) sit across a sight-passing
  barrier** (`_SIGHT_BARRIERS`, `spatial.py:219`), in 28 of 64 scenes. That is
  the live exposure of the whole-room-through-a-doorway over-grant: about one
  in six cross-room pairs, in nearly half of all scenes.

**Orientation (`scene.orientation`, 42 of 64 scenes):** `came_from` 292
entries, `focus` 295, **`facing` 67** (13% of positioned bodies). Facing is
the input to the entire egocentric stack — rear arc, left/right, `across`
sectors (`_relative_sector` `spatial.py:1458`, `entity_arc` `:1495`,
`room_layout` `:1526`) — and it starves *because stations starve*:
`infer_facing`'s focus arm (`spatial_frames.py:586-592`) already derives
facing deterministically from an attended target, but only through
`anchor_bearing_of` (`spatial.py:1546-1556`), which returns None unless the
target has a station at a beared anchor. 11% station coverage is why facing
sits at 13%. **Fixing station density mechanically unlocks derivation code
that already exists and already runs at commit.**

**Entities (n=557):** `enclosure` 3, `light_source` **0**, `container` 66.
The carried-light-pool stack (`_light_radius` `spatial.py:527`, `light_at`
`:534`) has zero live data behind it — harmless (rooms default lit) but worth
a coverage warning alongside G6.

---

## 2. The keystone: a read-time derivation layer (S1)

Everything else in this note either feeds on or is fed by within-room
position. The buildout's center of gravity is therefore not a new field but a
**derivation layer**: pure functions that answer "where in the room is this
body, which way does it face" from data the scene already persists, falling
back to today's behaviour when nothing supports an answer. Read-time
derivation is the strongest possible answer to the persistence checklist —
**a value that is never stored needs no commit path, no restore path, no
archive handling, no branch remap, and can never go stale in a checkpoint.**

### S1a. Implicit door anchors — `effective_anchors(scene, room_id)`

Every beared edge *is* an anchor: a doorway is a named feature of the room at
a known wall. Derive, at read time, a pseudo-anchor per adjacency edge that
carries `dir` (221 edges today, plus every `vertical` edge as `up`/`down`
pseudo-bearing, S3c):

```
effective_anchors(scene, room_id) ->
    dict(room.anchors or {}) + {"door:<to>": {"desc": <barrier phrase>, "dir": edge.dir, "implicit": True}}
```

- **Classification: derived.** No storage, no authoring, no default needed.
- **Consumers:** `proximity_rel` (two bodies at different door-anchors of a
  `large` room → `across`), `_relative_sector`/`entity_side`/`entity_arc`
  (a body at the north door is `behind` an observer facing south),
  `room_layout` (the look-around map gains its exits as positioned features —
  it already lists exits, but not as anchor rows), S2a's view-cone, and
  `anchor_bearing_of` → `infer_facing` (turning to attend someone standing in
  a doorway now yields a bearing).
- **Effect on the 54 anchor-less multi-occupant rooms:** any such room with
  ≥1 beared edge gains at least one usable anchor with zero authoring.
- **Cost:** one pure function plus threading it through the five `_anchor_dir`
  call sites. No schema change, no sync obligations.

### S1b. Derived stations — `effective_station(scene, name)`

Resolution order, first hit wins:

1. **Authored station** (`scene.stations[name]`) — unchanged, always wins.
2. **Contact-derived `near` link** — a standing contact (`scene.contacts`) is
   *physical touch*; two bodies in sustained contact are `within_reach` by
   definition, yet `proximity_rel` (`spatial.py:1358-1377`) never reads the
   contacts ledger. Derive a mutual `near` link for every actor/target pair
   in `scene.contacts`. Classification: **derived** (from a ledger the
   Director already maintains via `contact_ops`, which note 00 says is
   under-used at 13% of residual — every improvement in contact authorship
   now also buys proximity fidelity). Corpus: only 12 of 1,012 co-located
   pairs today, but these are precisely the pairs where "across the room"
   would be *narratively wrong*, so the error it prevents is severe even
   where rare.
3. **Crossing-derived door station** — a body with a live threshold crossing
   (`crossing_of`, `spatial.py:776-790`; `scene.crossings`, beats > 0, i.e.
   within the last `THRESHOLD_CROSSING_BEATS = 2` beats) stands at the
   implicit door-anchor of the edge it entered through (`rec["from"]` names
   the room left → identifies the edge). Classification: **derived**, and
   deliberately gated on crossing freshness so it cannot go stale — the
   moment the crossing record expires the body falls back to unplaced,
   exactly today's behaviour. (`orientation.came_from` also names the entry
   edge and persists longer — 292 live entries — but carries no timestamp I
   verified, so it is *not* used for placement: a body that entered five
   beats ago has plausibly wandered. Unverified: whether `came_from` has
   freshness semantics beyond "pruned on next move", `spatial_frames.py:361-365`.)
4. **None** → callers keep their current defaults (`near`, no sector).

- **Where derived stations live: nowhere.** This is a read-time accessor,
  not a commit-time writer. The alternative — materializing derived stations
  into `scene.stations` at commit beside `infer_facing` — was considered and
  rejected: it would need a `derived: true` marker so authored stations win,
  hygiene in `normalize_scene_stations` (`spatial.py:1559`), and it would
  freeze a guess into the persisted blob where checkpoints and archives would
  carry it. A pure function has none of those problems and reruns correctly
  under restore by construction.
- **One write-side exception, and it is an act, not authoring:** when the
  Director's resolve *does* emit `stations` (the merge path has existed since
  Phase 2, `StateDiff.stations` `schemas.py:1780`), nothing changes. The
  derivation layer is the fallback under it, which is exactly the
  fallback-under-authored shape the discipline requires.
- **Cost:** one function + rewiring `_station()` callers (`spatial.py:1336`)
  through it. The blast radius is `proximity_rel`, `_relative_sector`,
  `anchor_bearing_of` — three functions, each with existing tests.

### S1c. Facing coverage — no new mechanism, just fuel

With S1a+S1b in place, `infer_facing`'s existing arms
(`spatial_frames.py:541-599`) stop starving: movement through beared edges
(unchanged), focus-on-edge (unchanged), and focus-on-target now resolves
through `anchor_bearing_of` for any target at an authored *or derived*
anchor. Expected effect: facing coverage rises toward focus coverage
(295 entries) from today's 67. **No new field, no new writer** — the
derivation was built in the deterministic-facing work and has been waiting
for data. This is the single highest-leverage consequence of S1: rear arc
(`entity_arc` → `_delivery_ok` `agents/common.py:2212`), left/right
(`entity_side`), egocentric exits (`egocentric_frame` `spatial.py:1178`) all
fire only under a known facing.

One addition — **read-time facing fallback** `effective_facing(scene, name)`:
`orientation.facing` if set, else the bearing of the current focus target /
edge if resolvable *at read time*. Classification: **derived**. This catches
the window between a focus change and the next commit and lifts old scenes
restored from checkpoints that predate `infer_facing`. Cheap; optional; do it
if the accessor is being built anyway.

### S1d. Edge-distance normalizer — `normalize_edge_distance`

The corpus verdict on D5 is in: `distance` is authored on 86% of edges in 29
surface forms, and the single consumed value (`remote`) appears zero times.
Build the normalizer note 02 deferred as an audit:

- Vocabulary: `adjacent | near | far | remote` (four tiers, matching the
  ladder `hear_level` and `spatial_rel` already imply).
- Mapping: word aliases (`close`/`immediate`/`1 step`/`short` → adjacent;
  `mid`/`moderate`/`medium` → near; `far`/`long` → far) **and numeric/metric
  parsing** (`≤5` → adjacent, `≤20` → near, `≤75` → far, else remote — the
  corpus's `200 m` is a genuinely remote edge that today reads as `near`
  by `spatial_rel`'s raw passthrough, `spatial.py:854`).
- Applied inside `spatial_rel` at the one read site, mirroring
  `normalize_barrier` (`spatial.py:301`), so every consumer inherits it.
- Consumers gained for free: `hear_level`'s `remote` branch starts firing on
  real data; `corridor_sightlines`' `distance`/`vagueness` ordering improves;
  a `far`/`remote` open edge should also degrade S2a's cross-room body sight
  (a figure across a courtyard is `shapes`, not a readable face — one extra
  clause in `visual_level_between`).
- **Classification: derived** (normalization of an already-authored field);
  default `near` (today's exact behaviour) when absent or unparseable.

### S1e. Room-size default and keyword hint

`size` is absent from 48% of rooms; absent currently means "not large" which
means `across` can never fire there. Keep the safe default (`medium`) but add
a **keyword derivation hint** in the same pattern as
`weather.room_exposure`'s keyword fallback (precedent verified in note 02's
table row for exposure): room name/desc containing hall, warehouse, cathedral,
ballroom, hangar, plaza, field… → treat as `large` *for proximity purposes
only* when `size` is unset. Classification: **derived-with-default**;
authored `size` always wins. This is deliberately the weakest proposal in S1
— a keyword table is a blunt instrument — but it is bounded (affects only the
`near`→`across` distinction), fails toward today's behaviour, and its
false-positive cost is "two people in a big-sounding room read as farther
apart until one approaches", which the Director corrects by moving them
(spatial data, per the branch's contract). Ship behind the G6 coverage
warning so authored sizes remain the norm.

---

## 3. Leak-shaped fixes first (S2)

Leaks are the serious direction: the firewall subtracts, and an over-grant is
an engine failure. Note 02 identified exactly one leak-shaped FOV
approximation; G5's missing `cover` is its within-room sibling. Both are
fixed by *subtraction*, so neither can regress the information budget.

### S2a. Opening view-cone: degrade off-axis bodies seen through a barrier

Today `visible_adjacent_rooms` (`spatial.py:5578`) grants the whole neighbour
room through any sight barrier, and `_source_channels`
(`agents/perception.py:1492-1577`) grants every body in it by the same
room-level rel — a body pressed against the wall beside the doorframe is
fully seen. Live exposure: 330 cross-room body pairs across sight barriers,
28 of 64 scenes (§1).

**Mechanism** (in `visual_level_between`, `spatial.py:784` — the per-body
authority D4 designates as the single graded-sight function):

For observer O in room A, target T in room B, rel not `same_room`, barrier in
`_SIGHT_BARRIERS`:

1. Find the connecting edge and its bearing `d` (from A's side; or the
   reciprocal of B's declared edge via `opposite_bearing`,
   `spatial_orientation.py:58`).
2. Resolve T's station via `effective_station` (S1b) and its anchor bearing
   in room B via `effective_anchors` (S1a).
3. **If T's anchor bearing is known:** T is *in the cone* iff its bearing is
   within one 8-way sector of `opposite_bearing(d)` — i.e. roughly on the
   axis of the opening as seen from A — **or** T is at the door pseudo-anchor
   of this very edge, **or** T has a live crossing on this edge
   (`crossing_visible_from`, `spatial.py:793`). In cone → current behaviour
   (light-graded). Off-axis → **`none`**: beside the doorframe is precisely
   the place a doorway does not show.
4. **If T's placement is unknown:** fall back by room `size` (S1e): `small` →
   in cone (a closet has no off-axis corner worth modelling); `medium` →
   current behaviour (fail-open, status quo); `large`+ → cap at `shapes`
   (through a door you can tell a big room is occupied, not read a face
   across it — this also composes with S1d's far-edge degrade).

- **Classification: derived** (edge bearings, stations, crossings, size — all
  existing or S1); **defaulted** to today's behaviour exactly where data is
  absent, so quality cannot regress in sparse scenes.
- **Firewall direction:** pure subtraction. The failure mode of the
  approximation (sides flipping at walls, note 02 §3) can only *withhold*,
  never grant.
- **Symmetry note:** the same cone test must gate the *observer's* side — O
  standing off-axis in A cannot see through the opening either. One function,
  called with both orderings; `_saw_across_beat`
  (`agents/perception.py:1475`) already unions beat-start/beat-end so a body
  that steps out of the cone mid-beat is still seen leaving.
- Whole-room *description* through the opening (`visible_adjacent_rooms`)
  stays as is — knowing what the guardroom looks like through the grate is
  room-grain and fine; it is the *bodies* that leak.

### S2b. Station-level `cover` (G5, adopted as specified, one refinement)

Note 02 §2-G5 stands: `scene.stations[name] = {at, near, cover: true}`,
sight-only concealment from observers not at the same anchor; sound and scent
unaffected (unlike `contained`, whose `containment_conceals` blocks sound —
wrong for a body crouched behind a bar). Consumed by `visual_level_between`
and `_delivery_ok`'s sight arm.

- **Classification: authored-as-act with engine validation.** The Director
  sets it when resolving a hide — that is transcription of an adjudicated
  act, not world-building homework, so it does not violate the discipline.
  Two guards keep it honest:
  - **Fallback:** absent `cover`, behaviour is today's (visible) — a hide the
    Director forgets to transcribe degrades to the current engine, never to a
    leak *of* the hider (fail-visible is the pre-existing quality bar).
  - **Coverage warning:** when a resolve narrates concealment-shaped outcomes
    (the existing `conceal_from` event machinery fires,
    `agents/loops.py:96-104`) with no station/cover/containment op in the
    same diff, emit an engine notice — same pattern as G6's layout warning.
- **Refinement — cover plausibility, derived:** warn (do not block) when
  `cover: true` is set at an anchor whose entity is smaller than the hider
  (`size_relation`, `spatial.py:1964`) — hiding behind a candlestick should
  be visible to the author. Derived check, zero authoring.
- **Clearing:** `normalize_scene_stations` (`spatial.py:1559`) already drops
  a station whose entity vanishes; movement replaces the station and the key
  dies with it. No new lifecycle.

### S2c. The Phase-0 defects, reaffirmed with corpus weights

D1 (same-room whisper never downgraded, `spatial.py:1039-1046` — confirmed
still `volume == "mutter"` only in this worktree) remains the top leak and is
Phase 0 property, not this note's. D2's exact-`large` match is *currently*
unfired live (0 `huge`/`vast` in corpus) but must land with S1e since keyword
hints will produce `large` more often. D3/D4/D6 unchanged from note 02. D5 is
superseded by S1d (upgraded from "audit" to "build" — the audit happened, §1).

---

## 4. Cheap pure wins (S3)

### S3a. `sound_bearing(scene, observer, source)` — hearing gets a direction

Note 02 §3 established this is fully derivable; specification:

- **Same room:** `_sector_label(_relative_sector(observer, source))`
  (`spatial.py:1458,1500-1511`) → "behind you", "to your left". None (no
  facing/anchor) → no bearing, today's behaviour.
- **Adjacent room:** the connecting edge *as seen from the observer's room* —
  bearing `edge.dir` relative to `effective_facing` via `relative_bearing`
  (`spatial_orientation.py:79`), rendered against the barrier: "through the
  doorway to your right", "beyond the north wall". No facing → compass only
  ("from the north"); no edge dir → barrier only ("through the door").
- **Non-adjacent (S4a multi-hop):** the *first* edge of the sound path out of
  the observer's room — you hear which doorway it came through, not the
  route. This is also the firewall-clean formulation: the bearing names an
  opening in the observer's own room, whose blind edges already survive
  payload projection with `barrier` and `dir` but no destination
  (`_observer_scene_payload`'s F6 blind-edge rule,
  `agents/perception.py:869-885`) — so a bearing **never names an unseen
  room** and grants no layout knowledge the payload did not already carry.
- **Classification: derived.** No fields, one pure function in `spatial.py`,
  delivered beside `hear_level` grades in the payload and consumed by the
  composer/perception prompt symmetrically.
- This is the best benefit-per-line item in the note: every fragment/full
  hearing event in a multi-room scene gains a spatial clause the model
  currently invents (sometimes wrongly — it has no data either).

### S3b. Perceiver-senses gate (G4) — adopted as specified

Reference note 02 §2-G4; nothing to refine except placement: implement
`sense_adjusted` as a wrapper applied at the **three grade functions' call
sites in `_delivery_ok`/`_source_channels`/composer**, not inside
`hear_level`/`sight_level` themselves — the grade functions describe the
*channel*, the wrapper describes the *perceiver*, and mixing them would make
D4's single-authority migration harder. Classification: **derived** from
already-typed card fields (`character_schema.py:461-463`); free-text `notes`
stay uninterpreted.

### S3c. Verticality: accept `vertical` as a pseudo-bearing — and stop

The representation already exists and is sufficient: edge `vertical` up/down
is normalized and reciprocal (`spatial_orientation.py:183-226`), bucketed
above/below in `egocentric_frame` (`spatial.py:1219-1224`), and a
balcony-over-hall is exactly `{to: hall, vertical: down, barrier: open}` —
representable today. What is missing is *consumers*:

- `corridor_sightlines` (`spatial.py:5185`) skips any edge without `dir`
  (verified: `if not isinstance(edge, dict) or not edge.get("dir")`), so a
  stairwell or shaft never forms a sightline. Accept `vertical` as the
  heading: "below, the shaft drops to…" — one branch.
- `_onward_exits`/`spatial_digest` bearing rendering: bucket vertical edges
  as `above`/`below` instead of dropping them from egocentric output.
- S1a's implicit anchors: a vertical open edge is a hole/stair anchor.
- S3a: a sound from below renders "from the floor below / down the stairwell".

**Classification: derived** (consumers of an existing field; corpus: 31 live
vertical edges get better prose). **Not built:** within-room elevation fields
(`anchors[].elev`, catwalk/loft modelling). A loft the fiction treats as a
distinct vantage *is a room* — the substrate already prices that correctly
(rooms are cheap, `room_registry` handles identity) — and an `elev` value on
an anchor has no consumer that three proximity tiers and a `vertical` edge
don't already serve. Adding it would be fidelity below the prose quantum
(§9).

---

## 5. Spec-change tier (S4)

### S4a. Multi-hop loudness walk (bounded)

Today non-adjacent is `separated` → only shout-fragment survives
(`spatial_rel` `spatial.py:860-864` + `hear_level` wall/separated arm), and
the perception prompt agrees — so this is a deliberate spec change, adopted
because G2's alarm semantics are hollow without it (a gunshot two rooms away
*must* arrive as sound for the focus-snap to mean anything).

- Walk the open-edge graph (`passable_neighbors` `spatial.py:880` /
  `ambient_scope`'s component `spatial.py:6246` already compute reachability)
  from source room, max **2 hops**, only for `volume in (loud, shout)` (and
  G1 event loudness `loud|violent`). Per hop, shift one rung down the
  existing `_SOUND_LADDER` (`spatial.py:970`) — the mechanism
  `_material_shifted_barrier` already uses; grade the *worst* barrier on the
  path; result caps at `fragment` beyond the first hop. Normal speech and
  below never propagate (unchanged).
- Bearing: S3a's first-edge rule.
- **Classification: derived.** No fields. Cost: one bounded BFS per loud
  event per perceiver-room pair, cacheable per (source-room, volume) per
  beat.
- **Why bounded at 2:** each hop adds a rung of attenuation, so hop 3 is
  almost always `none` anyway; an explicit cap keeps the walk O(edges) and
  keeps "the castle hears every shout" impossible by construction.

### S4b. Alarm/salience (G2) — adopted; one integration note

As specified in note 02 (derived from G1 `loudness` + existing `targets`
binding, no second authored field). Integration with this note: the alarm
exemption's *reach* is S4a's sound reach — an alarming event bypasses
rear-arc/periphery/focus **for any perceiver it reaches through any
channel**, and snaps `infer_focus` toward S3a's bearing (the first edge, not
the source — you spin toward the doorway the bang came through, which is
also all the information you legitimately have).

### S4c. Turning in place (G3) — adopted; the authored surface is an act

`orientation_ops` stays as note 02 specifies (declared on `StateDiff`,
applied at commit beside `infer_facing`). Classification note under this
note's discipline: it is **authored-as-act** — transcription of "I turn
around", the same legitimacy class as S2b — with a **derived fallback already
live**: the focus→facing arm of `infer_facing`, which S1 finally fuels
(§2-S1c). So a missed op degrades to "facing follows attention", not to a
permanent blind spot. The corpus's `facing` 67 / `focus` 295 split says the
fallback will carry most of the load; the op exists for the explicit player
verb where attention hasn't moved.

### G1 / G6 — integration only (owned by notes 00/02, Phase 1)

- **G1** (per-event `sound` surface + verb-lexicon fallback) is a Phase 1
  Director-contract change, not spatial buildout; this note consumes its
  `loudness` (S4a/S4b) and contributes nothing new to it. Its lexicon
  fallback is what keeps it out of the authored-only failure class.
- **G6** (layout-density obligation on the mapping stage) gains teeth from
  §1's numbers. The warning should be **denominator-honest** (AGENTS.md
  fire-rate doctrine): fire per *multi-occupant room without anchors* (54
  live instances) and per *sight-barrier edge without `dir`* (feeds S2a/S3a),
  not per-field blanket nagging. With S1a/S1b, the obligation shrinks — door
  anchors come free, so the mapping stage owes only the *named-feature*
  anchors (`the bar`, `the hearth`) that derivation cannot invent. That is
  the burden-reduction shape note 04 wants: the engine derives the geometry
  of openings; authors contribute only what is genuinely creative.

---

## 6. Entity occlusion: what gets built and what does not

Note 02 called general occlusion "the one item that genuinely wants
geometry." Un-deferred and examined, it splits into three cases with very
different economics:

1. **Deliberate concealment** (crouching behind the counter): **build** —
   this is S2b/G5 `cover`, an occlusion *relation* (this body is hidden at
   this anchor) costing one dict key. It is the case with narrative intent
   behind it, the case the Director already adjudicates, and the case whose
   absence is leak-shaped.
2. **Aperture occlusion** (the doorframe hides what is beside it): **build**
   — S2a, derived entirely from bearings that exist.
3. **Incidental interposition** (a pillar happens to stand between two
   bodies neither of whom sought it): **do not build.** To answer it honestly
   needs observer position, target position, *and* blocker position on a
   shared metric — that is geometry, the representation the whole substrate
   correctly refuses (`02` §3: every output is a word, not a number). The
   cheap approximations all fail the discipline: an `occludes: [pair]`
   relation is authored-only with no derivation (worse than `stations`); a
   sector-interposition heuristic from anchor bearings is wrong whenever the
   observer is off room-centre, and *wrong toward concealment* — it would
   subtract sight two people actually have, which is the safe direction for
   the firewall but a **quality** regression with no act behind it, in the
   90% of rooms where nobody authored the pillar as mattering. And the
   baseline being defended ("same quality as the current engine") does not
   include it: the model-based path never tracked incidental interposition
   either — there is no data channel by which it could have. The one honest
   entry point, if it is ever wanted: an entity-level `blocks_sight` flag
   consumed only as a *cover candidate validator* for S2b (§3), declared on
   `SceneEntityDef` + `_ENTITY_DEFAULT_FIELDS` (`spatial.py:5778`) per the
   enclosure/light_source precedent. Not proposed now — `enclosure` sits at
   3 of 557 entities and `light_source` at 0; a third under-authored entity
   flag is a known failure shape.

---

## 7. Persistence and sync (the whole table)

The buildout's persistence story is deliberately near-empty. Per the
authority hierarchy (`AGENTS.md:312`; CLAUDE.md): `world.scene` is runtime
truth, `room_registry` the cross-frame ledger, `world_entities` a derived
projection, `world_placements` decommissioned.

| item | storage | commit path | restore/archive/branch | class |
|---|---|---|---|---|
| S1a implicit anchors | **none** (read-time) | n/a | n/a — recomputed | derived |
| S1b derived stations | **none** (read-time; reads `scene.contacts`, `scene.crossings` — both already persisted in-blob) | n/a | n/a | derived |
| S1c `effective_facing` | **none**; persisted `orientation.facing` unchanged, written by existing `infer_facing` | existing | existing (in-blob) | derived |
| S1d distance normalizer | **none** (normalizes at read, like `normalize_barrier`) | n/a | n/a | derived (default `near`) |
| S1e size keyword hint | **none** (read-time); authored `size` unchanged | existing | existing | derived-with-default (`medium`) |
| S2a view-cone | **none** (pure function of edge dir + S1) | n/a | n/a | derived (defaults = status quo) |
| S2b `cover` | `scene.stations[name].cover` — inside the blob, plain-dict key; `StateDiff.stations`/`ScenePatch.stations` already merge arbitrary station keys (`schemas.py:1780,2579`, `_coerce_station_table`); `normalize_scene_stations` must *preserve* unknown keys (verify — it currently rebuilds `{at, near}`, flagged as the one code check S2b needs) | `commit_scene` → `wset(chat_id,"scene",…)` (`commit.py:2302-2309`), no change | whole-blob checkpoint/archive carries it; no IDs to remap (names are in-blob) | authored-as-act; fallback = visible (status quo); coverage warning |
| S3a/S3b/S3c/S4a/S4b | **none** | n/a | n/a | derived |
| S4c `orientation_ops` | transient on `StateDiff` (declared, per note 02); lands in `scene.orientation` — already in-blob, already pruned by `infer_came_from` | existing | existing | authored-as-act; derived fallback (focus arm) |

No new tables, no `world_entities` field (nothing joins
`_ENTITY_DEFAULT_FIELDS`), no `room_registry` payload change (implicit
anchors are never written, so the registry projection is untouched on both
the commit and restore paths), no `chat_archive` handling, no branch/clone
remap. The only schema-adjacent verification item is `normalize_scene_stations`
key preservation for `cover`.

---

## 8. Ranked build order

Ranked by (leak seriousness) → (quality per cost, composer-independent).
Every item pays off for the Director/character/model-perception consumers of
`_observer_scene_payload` today; none waits for the composer.

1. **Phase-0 defects D1–D4, D6** (note 00) — leaks on the live no-LLM path.
   Not re-litigated here; everything below assumes them.
2. **S1 derivation layer** (S1a implicit anchors, S1b derived stations, S1d
   distance normalizer; S1c falls out free; S1e last, behind the G6 warning).
   The multiplier: it feeds S2a, unfires the `stations` failure mode without
   asking authors for anything, and turns three dead code paths (facing
   derivation, `across`, `remote`) into live ones. ~3 pure functions + call-site
   threading.
3. **S2a opening view-cone + S2b cover (G5)** — the leak-shaped over-grants,
   335+ live pair-exposures between them. Pure subtraction; defaults equal
   status quo.
4. **S3a sound_bearing** — best quality-per-line in the note; zero risk.
5. **S3b senses gate (G4)** — correctness of the pure function; small.
6. **S4b alarm (G2) + S4a bounded multi-hop loudness** — land together; G2
   without S4a is hollow, S4a without G2 is scenery.
7. **S4c orientation_ops (G3)** — after S1 proves how much the focus-arm
   fallback already covers; the op then handles only the explicit verb.
8. **S3c vertical pseudo-bearings** — nice prose, 31 live edges, cheap.
9. **G6 coverage warnings** (multi-occupant-room-without-anchors, beared-edge
   density, plus a `light_source`-never-authored notice) — alongside 2, since
   S1 changes what is worth warning about.

## 9. What I would not build, and where fidelity stops paying

The prose register quantizes space to: 3 proximity tiers, an 8-way sector
(rendered as 4 words), 3 grades per channel, 4 distance tiers, above/below.
**Any fidelity finer than that quantum is invisible in the output medium** —
it can only consume authoring effort and code surface. Concretely not built:

- **Coordinates / metric geometry** in any form, including parsing `20m`
  into anything finer than S1d's four tiers. No consumer can print a number.
- **Incidental entity occlusion** (§6.3) — wants geometry, has no derivation,
  subtracts real sight when guessed, and the model baseline never had it.
- **Within-room elevation fields** (§S3c) — a vantage that matters is a room.
- **Acoustics beyond 2 hops, echo/material reverb** — every hop past the
  second is `none` by the existing ladder; material shift already exists.
- **Scent bearings/trails** — `scent_level`'s three grades are already ahead
  of what the fiction asks; a tracking mechanic is a gameplay feature, not a
  perception fix.
- **Peripheral-vision cones finer than front/rear arc + sectors** — the
  perception prompt's own vocabulary (focus/periphery) never needed more, and
  G1's detail-classing handles the fine-motor gating (note 02 §3).
- **Materializing derived stations into the blob** (§S1b) — persistence buys
  staleness and sync obligations, and nothing else.
- **A third under-authored entity flag** (`blocks_sight`) while `enclosure`
  reads 3/557 and `light_source` 0/557 — fix authoring density before adding
  vocabulary to it.

The honest summary of diminishing returns: after S1+S2, the remaining gap
between the deterministic floor and the model-smoothed baseline is no longer
spatial — it is G1's event-surface problem (what things sound like), which is
a Director-contract question, not a geometry question. Spatial fidelity past
this note's line would be simulation for its own sake, and the corpus —
where 100% of barriers but 39% of edge bearings are authored — says the
binding constraint is data density, which S1 attacks by derivation and G6 by
visibility, not schema depth.

---

### Unverified items carried forward

- `came_from` freshness semantics beyond next-move pruning
  (`spatial_frames.py:361-365`) — why S1b uses crossings, not came_from, for
  placement.
- Historical (per-turn) field coverage — §1 measures live end-state blobs
  only; checkpoint-walk sampling would firm the trend but not change the
  ranking.
- `normalize_scene_stations` unknown-key preservation for `cover` (§7) —
  one function to read before S2b lands.
- `observer_body_regions` internals (inherited flag from note 02).
