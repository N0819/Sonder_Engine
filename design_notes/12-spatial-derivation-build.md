# Spatial derivation build — what landed on `spatial-derivation`

Implementation notes for the buildout specified in
`design_notes/07-spatial-buildout.md` (primary brief) and
`02-spatial-fov-gaps.md` (gap analysis). Base: `9463d07`, green at 5,576.
This tree: green at **5,652** (`make check`, exit 0) — 76 new tests, zero
regressions, all pre-existing tests untouched.

Scope discipline held throughout: everything below is **derived or
defaulted, never a new authoring obligation**; nothing below stores a single
new field anywhere (no commit path, no restore path, no archive handling, no
branch remap — the persistence table in note 07 §7 stands with every row
"none"). `agents/perception.py`, `agents/composer.py`, `persist/commit.py` and
`mind/memory.py` were not touched (composer agent's seam).

---

## 1. What landed

### S1 — the read-time derivation layer (`world/spatial.py`)

- **S1a `effective_anchors(scene, room_id)`** — authored anchors plus one
  implicit `door:<to>` pseudo-anchor per adjacency edge, declared from
  either side (reverse edges bear reciprocally, verticals flip). Authored
  anchors win id collisions; implicit ones carry `implicit: True` and are
  never written. Threaded through `_anchor_dir`, so `_relative_sector`,
  `anchor_bearing_of`, `room_layout` and `normalize_scene_stations` all see
  door anchors. `room_layout` now lists doorways as positioned features with
  sides. Vertical edges become `up`/`down` pseudo-anchors (the S3c slice
  that came free).
- **S1b `effective_station(scene, name)`** — resolution order: authored
  station → contact-derived placement (anchor-backed partner seats the body;
  co-located body partner becomes a mutual `near` link) → crossing-derived
  door placement (live crossing ⇒ at the `door:<from>` pseudo-anchor;
  expires with the crossing record, so it cannot go stale) → nothing.
  Unknown station keys (future `cover`) pass through. Consumers rewired:
  `proximity_rel`, `measured_proximity_rel`, `_relative_sector`,
  `anchor_bearing_of`. Crossing/contact-derived placements count as
  **measurements** in `measured_proximity_rel` — they are evidence, not
  defaults.
- **S1c `effective_facing(scene, name)`** — persisted `orientation.facing`
  wins; else derived at read time from the focus edge/target through the
  layer above. Used by `_relative_sector` and `room_layout`. The bigger S1c
  effect needed no code: `infer_facing`'s focus arm (`spatial_frames.py:591`)
  already derives facing through `anchor_bearing_of`, which now resolves for
  any body in a doorway or in contact with an anchored feature — pinned by
  `test_infer_facing_focus_arm_is_unstarved_by_derived_stations`.
- **S1d `normalize_edge_distance`** — four tiers
  (`adjacent|near|far|remote`), word aliases plus numeric/metric parsing
  (≤5 m adjacent, ≤20 near, ≤75 far, else remote; bare numbers read as
  meters; steps/paces ≈ 0.75 m). Applied at `spatial_rel`'s single edge-read
  site, mirroring `normalize_barrier`, so every consumer inherits it.
  Absent/unparseable → `near`, i.e. exactly the old default — the default
  cannot masquerade as a measurement because only authored values reach the
  other tiers. `hear_level`'s `remote` branch fires on real data for the
  first time; a `far`/`remote` edge also caps cross-room body sight at
  `shapes` (composes with S2a).
- **S1e `effective_room_size`** — authored `size` wins; else a token-matched
  keyword hint on name/desc/notes (`hall` yes, `hallway` no) → `large` for
  proximity purposes only; else `medium`. Consumed only by `proximity_rel`.

### S2a — the opening view-cone (`_opening_view_cap` in `visual_level_between`)

Off-axis bodies seen through a sight-passing barrier degrade by anchor
bearing vs the opening's axis, **on both sides** (one function, both
orderings). In-cone = within one 8-way sector of the direction pointing away
from the opening, OR at that edge's door pseudo-anchor, OR live crossing on
that edge. Placement unknown → size fallback: tiny/small always in cone,
medium keeps today's fail-open, large+ caps at `shapes`. Dark still wins
(the cap is min-composed with light).

**Deviation from note 07 §3 as written, deliberate:** the note words the
cone as "within one sector of `opposite_bearing(d)` [d from A's side]",
which resolves to the *door-wall* side of the target's room — the set that
*contains* "beside the doorframe", the note's own motivating leak. Read from
the target room's own edge bearing, the visible strip is the **far half**
along the opening's axis; the note's separate "at the door pseudo-anchor"
clause (redundant under its literal wording, necessary under this one)
confirms the intent. Implemented as the far-half rule; the doorframe test
pins it.

**Subtract-only invariant (per coordinator addendum):** the cone is written
as a cap over what `visual_level_between` already computed (`_weaker_sight`
composition), so it cannot grant by construction, and
`test_the_cone_only_ever_subtracts` sweeps 1,200 combinations of bearings ×
placement × size × light × distance × barrier × crossing asserting
post-cone ≤ pre-cone against an inline reimplementation of the pre-S2a
function.

### G4 — the senses gate (`sense_adjusted` + friends, `world/spatial.py`)

- `sense_entry` / `sense_acuity_offset` / `sense_range_class` /
  `sense_adjusted(level, channel, senses)`. Acuity is an integer ladder
  offset: absent → hard cut to `none`; dulled −1; ordinary 0
  (**byte-identical**, pinned); keen +1; extraordinary +2. Token-matched
  vocabulary ("super enhanced" → +2, "hard of hearing" → −1); unrecognized
  free text is 0 — free text never adds capability. Channel aliases map
  card channels onto the engine's three (`sight|hearing|scent`); channels
  the floor does not model stay unread.
- **The `trace` tier** (hearing only): `HEARING_LEVELS = (none, trace,
  fragment, full)`. The prompt ceiling — *extraordinary senses register
  gross direction and noise character, NEVER words/identity/visual detail* —
  is enforced structurally: an upward shift from `none` lands on `trace`
  and only at +2; sight and scent never leave `none` (a wall and an airtight
  seal are not things acuity penetrates, and the level cannot say which it
  was). Above `none`, an upward shift upgrades clarity of content already
  flowing (fragment→full is an ear pressed to the door). Downward shifts
  are plain ladder moves (dulled turns a fragment into a trace).
- `range` is the separate envelope axis: `sense_range_class` →
  `reduced|ordinary|extended`; `extended` is meant to widen
  `sound_walk_level`'s `max_hops` (the hook exists and is tested;
  nothing passes 3 yet — see deferred).
- **Wiring:** `_delivery_ok` (`agents/common.py`) gained an optional
  `senses=None` parameter (None → byte-identical; docstring warns callers
  that a trace-passing True is detection-only). The deterministic micro-loop
  (`agents/loops.py`) passes the observer's card senses on both channels and
  renders `trace` as an identity-free, quote-free line with a
  `sound_bearing` phrase. Deaf observers lose speech but keep sight; blind
  observers lose actions but keep speech; ordinary cards are pinned
  byte-identical through the loop.

### S3a — `sound_bearing(scene, observer, source)` (`world/spatial.py`)

Same room → egocentric sector ("behind you"); adjacent → the connecting
edge rendered against barrier and facing ("through the doorway to your
right"; compass-only without a facing); non-adjacent → the **first edge of
the sound path out of the observer's own room**; vertical edges → "from
above"/"from below". Returns `None` rather than guessing. Firewall-clean by
construction and by test: the returned dict carries no room ids and no room
names (`test_beyond_names_only_the_first_edge_never_the_unseen_room`
asserts it on the serialized output).

### G2 + S4a — alarm and the bounded loudness walk (**deliberate spec changes**)

- **S4a `sound_path` / `sound_walk_level`**: raised volumes only
  (loud/shout, G1's `violent` mapped to shout), max 2 hops over
  sound-passing edges (`open|open_door|bars|membrane` — the passable set
  plus `bars`, hear_level's own acoustic-hole precedent; membrane grades as
  closed_door on the ladder, matching its hear_level table exactly), worst
  barrier on the path shifted one `_SOUND_LADDER` rung per hop past the
  first, capped at `fragment`. Normal speech and below never propagate.
  This changes spec: non-adjacent used to be `separated` (nothing but a
  shout-fragment); a gunshot two open rooms away now arrives as sound, which
  is what makes the alarm exemption mean anything. Attenuation-only pinned
  by `test_a_hop_may_only_attenuate`.
- **G2 `is_alarming(loudness, targets, perceiver)`**: derived — raised
  loudness or the event targets the perceiver. The composer's
  rear-arc/periphery bypass consumes this predicate; the engine-side
  consumer landed now is **`infer_focus`'s salience snap**
  (`world/spatial_frames.py`): a raised dialogue volume snaps the focus of any
  perceiver it reaches — the shouter if co-located, else the edge the sound
  arrived through (first edge of the sound path, never the unseen source
  room; an unreachable shout snaps nothing). Ranked below
  addressing/being-addressed and locomotion, above bare persistence.
  Per-event loudness richer than dialogue volume waits on G1's sound
  surface (Director-contract work, not spatial).

---

## 2. Caller audits (vocabulary/signature changes)

**`trace` (new hearing value).** It does not exist in `hear_level`'s
return set — only `sense_adjusted` can produce it, so only opted-in callers
ever see it. Every `hear_level` caller audited:
`spatial.can_perceive`, `agents/loops.py:120` (updated — handles trace),
`agents/loops.py:333` (`_no_mutual_perception`, raw, unchanged),
`agents/common.py:_delivery_ok` (senses-optional; trace passes the boolean
gate only when a caller passed senses — sole such caller is the updated
micro-loop; docstring warns), `commit.py:3476` (raw, unchanged, off-limits
file), `agents/background.py:154,435` (raw — background presences have no
cards), `agents/perception.py:322,1306,2178` (untouched, composer seam),
`tools/perception_quality.py` (reads `_dialogue_hear_level`, unchanged).

**`_delivery_ok` signature** — one new optional kwarg `senses=None`;
callers: `agents/loops.py:115,134` (both updated), no others in the tree.

**`rel["distance"]` (now always a tier on edge rels).** Sole consumer of
the value: `hear_level:1082` (`== "remote"`), plus the new far/remote sight
cap in `visual_level_between`. All other `"distance"` sites construct rels
with literal `near|same|far` (commit.py:2060, director.py:4579,
perception.py:3848, spatial.py transit/dock edges, offscreen.py) — the
normalizer is idempotent on those. `corridor_sightlines`' `distance` output
field is a different, unrelated key (vagueness label).

**`visual_level_between` / `proximity_rel` (values, not vocabulary).**
S2a/S1b can only lower sight grades and raise proximity *on evidence*.
Callers checked: `agents/loops.py:330` (subtraction → strictly safer),
`agents/narration.py:445`, `agents/common.py:568,2212ff,3983`,
`agents/perception.py` (nine sites, composer seam — same vocabulary,
values only ever dimmer), `spatial.py:571` (`source_light` spill:
within_reach/near both pass, no behavioural change), `spatial_facts:5132`
(tier display improves). `hear_level`'s proximity downgrade now sees
`within_reach` for contact pairs — a mutter/whisper between two touching
bodies arrives whole, which is the corrected direction (evidence, not
default).

**`normalize_scene_stations`** now validates `at` against
`effective_anchors`, so a Director-echoed `door:<to>` station survives the
merge; a room move still clears it (the new room's door anchors name
different neighbours — tested).

## 3. Behavioural deltas on existing data (intended, evidence-gated)

A scene with none of the relevant data behaves identically (pinned). Where
data already exists live:

1. Authored `size: large`+ rooms: an unplaced body seen through an opening
   now reads `shapes`, not `full` (the S2a fallback — 330 live pair
   exposures were the leak).
2. Authored edge `distance` parsing ≥75 m: hearing dies (`remote` branch),
   far edges cap body sight at `shapes`.
3. Standing contacts: co-located contact pairs read `within_reach` (quiet
   volumes between them stop degrading; whispers still die `across`).
4. Raised dialogue volumes: bystander focus snaps (G2, deliberate).

## 4. Deferred, with reasons

- **G3 `orientation_ops`** (turn-in-place) and **G5 station `cover`** —
  per brief, deferred unless the rest landed easily; both are
  authored-as-act surfaces touching the Director contract and `StateDiff`,
  and the composer does not block on them. S1's focus→facing fallback
  carries most of G3's load already (note 07 §S4c expects exactly this).
  The one G5 precondition in this layer is done for free:
  `effective_station` preserves unknown keys, so `cover` will survive it.
- **G6 coverage warnings** — the denominator-honest warning belongs at the
  mapping/commit seam (`persist/commit.py` off-limits this session). The size hint
  shipped without its warning; flagging rooms sized by keyword is one
  `effective_room_size`-vs-authored comparison when the seam owner wires it.
- **S3c further consumers** (`corridor_sightlines` vertical headings,
  `_onward_exits` vertical bucketing) — vertical pseudo-anchors and
  vertical `sound_bearing` landed; the sightline/exit rendering is prose
  surface for 31 live edges and lost the priority race.
- **Extended-range wiring** — `sense_range_class` and
  `sound_walk_level(max_hops=3)` both exist and are tested; the call site
  that joins them is perception/composer-side delivery, which is the other
  agent's seam. Same for the `remote`-distance rescue by extended range.
- **`layout_coverage_warnings`** — not built at all rather than built
  unwired; an unfired guard is this repo's least favourite object.

## 5. Credits and provenance

- **Everything in this build is derived from the owner's own design notes
  (`design_notes/02`, `07`, `00-PLAN`), the owner's existing MIT-licensed
  Sonder code, and aggregate vocabulary counts from the owner's own
  read-only corpus (`engine.db`: edge-distance surface forms, card
  acuity/range/channel words, room-size words).** No external code, data,
  tables, vocabularies or class structures were consulted or incorporated.
  Python standard library only.
- **Subtract-only final pass ("a gating pass may only remove"):** adopted
  as a general engineering principle at the coordinator's request, on
  independent grounds (this branch removes the model that masked
  floor defects). The coordinator's lead mentioned a reported description
  of TADS 3's occluder concept as corroboration; TADS 3 is proprietary and
  nothing was read from, derived from, or modelled on it or its adv3
  library — no code, no data, no naming, no structure. Inspiration-only at
  one further remove (a second-hand description of an idea), implemented
  from scratch as `_weaker_sight` cap composition plus property tests.
- Nothing GPL-licensed or otherwise externally licensed touched this work.

## 6. Verification

- `make check` exit 0: compile + map regeneration + structure checks +
  full suite, **5,652 passed** (base 5,576 + 76 new), ~51 s.
- New test files: `tests/test_spatial_derivation.py` (29),
  `tests/test_view_cone.py` (14, incl. the 1,200-case subtract-only sweep),
  `tests/test_sound_bearing.py` (20, incl. attenuation-only and the
  no-unseen-room firewall assertion), `tests/test_senses_gate.py` (13,
  incl. micro-loop integration on `temp_db`).
- Microbenchmark: 26,400 `proximity_rel`+`visual_level_between` pair calls
  on a 40-room/12-body scene in 0.40 s (~15 µs/pair) — the derivation
  layer's room scans do not move the needle.
- Uncommitted by instruction; diff: `world/spatial.py`, `world/spatial_frames.py`,
  `agents/common.py`, `agents/loops.py`, `docs/CODE_MAP.md` (regenerated),
  four new test files, this note.
