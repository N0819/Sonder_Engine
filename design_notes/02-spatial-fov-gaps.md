# Spatial / FOV substrate: gap analysis for zero-LLM perception

Branch goal: perception becomes a pure function of spatial data. The mapping
stage and Director only ever CHANGE SPATIAL DATA; perspective is computed
entirely by code. This note audits what the substrate already proves, what it
is missing, and where its approximations would become reader-visible once no
model is left to paper over them.

Method: the perception system prompt (`prompts.py:571-928`) was read as the
specification — every threshold and rule it states either has a backing field
or deterministic function, or is a gap. All claims below carry file:line
citations against this worktree; anything not verified in source is flagged.

Authority context (unchanged by this plan): `world.scene` is the sole runtime
authority for live rooms/positions/entity state; `room_registry` the
cross-frame room ledger; `world_entities` a derived projection
(`AGENTS.md:312`). Every field proposed below lives INSIDE the `world.scene`
blob or on an already-persisted schema model, so commit (`commit_scene` →
`wset`) and restore (whole-blob checkpoint/archive of the `scene` world key)
carry it with no new persistence machinery — the one hard rule is that any
model-authored field must be DECLARED on its Pydantic model or the validation
round-trip deletes it silently (the `stations` lesson, `schemas.py:1770-1780`;
the `RoomDef.anchors` lesson, `schemas.py:1105-1121`; entity fields must also
join `_ENTITY_DEFAULT_FIELDS`, `spatial.py:5778`, or they are settable only at
entity creation).

---

## 1. Prompt rules ALREADY backed by data + code (verified)

| Prompt rule (prompts.py) | Backing |
|---|---|
| Spatial gradient by barrier (589-597) | `spatial_rel` `spatial.py:806`; `normalize_barrier` `:301` (folding, 14.6% wall-bug fixed); `_SIGHT_BARRIERS` `:219` |
| Dialogue hearing by volume/barrier (879-884) | `hear_level` `spatial.py:988-1107` incl. material shift `:973`, proximity downgrade `:1039`; `_dialogue_hear_level` + comm rescue `agents/perception.py:287-316`; `SpeechVolume` + `normalize_speech_volume` `schemas.py:149,209` |
| Light levels / dark hides same-room bodies (spec implied; facts at 5093) | `RoomDef.light` `schemas.py:1098`; `room_light`/`source_light`/`light_at`/`effective_light` `spatial.py:455-606`; `sight_level` `:626`; spill lifts dark→dim only `:578-606` |
| Light emitters, pools vs room-filling | `SceneEntityDef.light_source` `schemas.py:1077`; `_light_radius` `spatial.py:527`; per-body `light_at` `:534` |
| Exposure / weather per room, per channel | `RoomDef.exposure` `schemas.py:1104`; `weather.room_exposure:277`, `weather_for_room:446`, `weather_words(channel):549` |
| Sightlines: terminus + vagueness, no room counts (842-847) | `corridor_sightlines` `spatial.py:5185-5269`; delivered `agents/perception.py:1046` |
| onward_exits / onward_bearings (848-856) | `_onward_exits` `spatial.py:5510-5575` (reverse-declared edges counted, full-sight required); `visible_adjacent_rooms` `:5578` |
| Anchors with `dir`, egocentric room map (703-710) | `RoomDef.anchors` `schemas.py:1121`; `room_layout` `spatial.py:1526`; `spatial_digest` `:1260` (with per-edge `bearing` `:1287-1290`) |
| Enclosure transparency (opaque/transparent/barred/membrane) | `SceneEntityDef.enclosure` `schemas.py:1071`; `_closed/_open_enclosure_barrier` `spatial.py:6001/5987`; carried interiors excluded `_is_carried_interior:5130` |
| Scales (823-824) | `StateDiff.scales` `schemas.py:1789`; `scale_of`/`size_relation`/`size_facts` `spatial.py:1906/1964/1999` |
| Containment, 3-direction relations (818-822) | `StateDiff.containment` `schemas.py:1793`; `hiding_holders_of` `spatial.py:2264`; `containment_conceals:2290`; `inside_source`/`enclosed_from_source`/`source_enclosed` in `spatial_rel_between:729-781`; conducted hearing `hear_level:1009-1032` |
| Scent channel full/muffled/none (727-738) | `scent_level` `spatial.py:234-288`; `_SCENT_BARRIERS:232`; delivered `agents/perception.py:1576` |
| Unified delivery gate | `_delivery_ok` `agents/common.py:2176-2214` (awareness, containment, hearing+proximity, sight+rear arc) |
| behind_rooms (646-653) | `infer_came_from` `spatial_frames.py:327`; `egocentric_frame` `spatial.py:1178`; `_behind_rooms` `agents/perception.py:1890`; SUBTRACTED from visible_rooms `_visible_rooms_for:1901` (chat-67 fix) |
| behind_sources / rear arc (653-658) | `infer_facing` `spatial_frames.py:541`; `entity_arc` `spatial.py:1495`; `_behind_sources` `agents/perception.py:1965`; enforced deterministically in `_delivery_ok` `agents/common.py:2212` |
| focus_target data (670-681) | `infer_focus` `spatial_frames.py:467`; `_focus_target` `agents/perception.py:1933` |
| Proximity tier / side / arc (686-702) | `proximity_rel`/`entity_side`/`entity_arc` `spatial.py:1358/1479/1495`; `_proximity_to_sources` `agents/perception.py:1946`; `_co_present_company:1976` (identity-gated, sight-graded) |
| spatial_facts ground truth (711-715) | `spatial_facts` `spatial.py:5044` — but env-gated OFF at perception (`SPATIAL_SCAFFOLD`, `agents/perception.py:318-327`) |
| Identity gate (716-723) | `known` ledger; `_scrub_unknown_identities` `agents/common.py:2274`; `observer_label_fn:1980`; quoted-span protection `:2268` |
| Visual channel booleans, beat-start union (724-726) | `_source_channels` `agents/perception.py:1492-1577`; `_saw_across_beat:1475`; `visual_level_between` `spatial.py:784` |
| Touch-only cause-blindness (777-786) | `_touch_only_sources` `agents/perception.py:2995`; `_surface_translate_event:3079` (fails closed to one generic sentence) |
| Standing contact as continuous percept (787-804) | scene `contacts` + `standing`/`sensation` in payload `agents/perception.py:894-921`; `contact_phrase`/`contact_sensation` `spatial.py:4680/4911` |
| Substances, source-blindness (805-817) | payload filter `agents/perception.py:967-1005` (interior matter recipient-only, source popped) |
| Poses / pose_unknown (615-624) | payload `agents/perception.py:922-966`; `_strip_unknown_pose_claims:1104` |
| body_regions pre-gated (605-614) | `observer_body_regions` (imported `agents/perception.py:842`) |
| Ambient scope by nesting (830-835) | `ambient_scope` `spatial.py:6246`; `_ambient_location_for` `agents/perception.py:1595` |
| Threshold crossings | `infer_threshold_crossings` `spatial_frames.py:369`; `crossing_of`/`crossing_visible_from` `spatial.py:688/705`; floors sight at `shapes` `sight_level:643-656` |
| Consciousness gate (865-877) | `NON_AWAKE_GATED`; `_delivery_ok` awareness arm `agents/common.py:2200`; engine-rendered residue `_compose_residue_view` (imported `agents/perception.py:835`) |
| Concealed speech conceal_from (893-899) | deterministic skip `agents/loops.py:96-104`; sentence-level event redaction (`AGENTS.md:38`) |
| Disguise (636-645) | `_subject_disguise_context` `agents/perception.py:2136`, consumed at `:2500,2610,3254,3620`; honored by `_co_present_company:2029-2039` |
| Fragment degradation of heard speech | deterministic precedent `agents/loops.py:113-120` |

Conclusion for Q1: the CHANNEL layer (can X reach Y, at what grade, through
what) is almost entirely computed already, and the per-observer projection
`_observer_scene_payload` (`agents/perception.py:849-1052`) is already an
identity-gated, containment-gated, blind-edge-scrubbed view — it is the right
input format for a deterministic composer. What the model still does is (a)
RENDER, and (b) adjudicate a short list of rules that have no data. Those are
the gaps.

---

## 2. Rules with NO backing data — new fields / computations required

### MUST-HAVE for correctness (a pure function is wrong without these)

**G1. Per-event sound surface (the non-visual channel has no content).**
Prompt rules 739-757 ("sensation, not acts"; "the observable is written for a
sighted bystander") are today satisfied by the model rewriting, and by two
deterministic fallbacks that fail closed: actions are DROPPED for sightless
observers (`_delivery_ok` treats action ≈ sight, `agents/common.py:2197-2214`;
`agents/loops.py:122-137`), and touch-only observers get the single generic
sentence `_surface_translate_event` `agents/perception.py:3079-3104`. A
composer with no model cannot rewrite "draws the knife" into "a faint scrape
of metal" — the data does not exist.
- Field: `sound: {desc: str, loudness: whisper|quiet|normal|loud|violent}`
  (and optionally `touch_desc`) on each sequence/action element.
- Type/home: sequence elements are untyped `list[dict]`
  (`schemas.py:1012,1017`) so nothing is round-trip-deleted, but the field
  should be named in the Director interpret/resolve and character prompts and
  normalized in `agents/common.py`'s sequence normalization.
- Authored by: Director (`director_interpret`/`director_resolve`) and
  character steps, exactly as `volume` already is for speech.
- Derived fallback: a verb→sound-class lexicon for undeclared elements
  (default `quiet`), so silence of authorship degrades to "you hear movement
  nearby", never to a leak or a dropped act.
- Sync: transient per-beat data (rides `steps`/`variants`); nothing persists.

**G2. Alarm/salience classification (the EXEMPTION has no data).**
Prompt 681-685: a violent/alarming event bypasses behind/focus/periphery.
Nothing computes this; `infer_focus` explicitly defers it
(`spatial_frames.py:483-484` "Reflexive salience-snap (spec B) is
intentionally not implemented here; the perception prompt's salient-event
zone-exemption stands in for it"). Zero-LLM, the exemption vanishes: a gunshot
behind you would be delivered as sound only and your focus would never snap.
- Derivation: `alarming = loudness in (loud, violent) or event targets the
  perceiver's own body` — i.e. G1's `loudness` plus the existing `targets`
  binding (`AGENTS.md:289`). No second authored field needed if G1 lands.
- Consumers: the composer (bypass rear-arc/periphery for that event) and
  `infer_focus` (snap focus to the source at commit).

**G3. Turning in place (orientation has no op).**
`facing` changes only via movement through a beared edge, focusing an edge, or
addressing a co-located anchored target (`infer_facing`
`spatial_frames.py:541-599`). The prompt lifts the rear-arc restriction "if
this beat has the perceiver turn, look back, or face that source"
(prompts.py:667-669) — model-adjudicated today, unrepresentable in data. A
deterministic composer would keep a player blind to a room they just turned to
face.
- Field: `StateDiff.orientation_ops: list[dict]` —
  `{name, face: bearing | {target} | {room}}` — DECLARED on `StateDiff`
  (Pydantic round-trip rule), authored by Director interpret/resolve when a
  turn/look-back is declared, applied at commit beside `infer_facing`.
  A matching entry point for the player's own declaration (interpret) matters
  most: "I turn around" is a player verb.
- Sync: writes only `scene.orientation`, which already persists inside the
  blob and is already pruned/GC'd by `infer_came_from`
  (`spatial_frames.py:361-365`).

**G4. Perceiver senses are never consulted by the deterministic floor.**
Cards carry typed senses `{channel, acuity, range, notes}`
(`character_schema.py:461-463`), the prompt spends four paragraphs on them
(600-602, 767-786), and the only deterministic consumer is tell-gating
(`_tell_acuity` `agents/perception.py:2055-2080`). `hear_level`,
`sight_level`, `scent_level` all ignore the perceiver: a card that says
vision `absent` produces a fully sighted composed view. With a model in the
loop the prompt caught this; pure code will not.
- Computation (no new authored data): `sense_adjusted(level, senses, channel)`
  in `world/spatial.py` or `agents/common.py` — vision absent → sight `none`,
  impaired → cap at `shapes`; hearing absent → `none`, keen → rescue one grade
  at `near` proximity; scent keen → `muffled`→`full` at same room. Free-text
  `notes` ("echolocation") stays uninterpreted — the deterministic floor
  honors only the typed axes; anything richer remains authoring debt, not an
  engine guess.
- Called from `_delivery_ok`, `_source_channels`, and the composer.

**G5. Standing hidden ("behind the counter") is unrepresentable.**
Concealment today is per-EVENT (`visibility:'concealed'`) or full containment
(`contained` ledger — which blocks sound too via `containment_conceals` in
`_delivery_ok` `agents/common.py:2204`, wrong for a body crouched behind
furniture, and requires the holder to be a positioned ENTITY,
`normalize_scene_containment` `spatial.py:2334-2336`, which an anchor is not).
A composer will render every hiding body as plainly visible, in bright light,
at `near` proximity.
- Field: station-level `cover: true` in `scene.stations[name]`
  (`{at: anchor, near: [], cover: true}`) — sight-only concealment from
  observers not at the same anchor; sound/scent unaffected. Stations are
  already a plain dict by design (`schemas.py:1778-1780`), so the key costs
  nothing structurally; `StateDiff.stations`/`ScenePatch.stations` already
  merge it. Authored by Director resolve (a hide is an act it already
  adjudicates); cleared by `normalize_scene_stations` when the station drops
  (`spatial.py:1559`).
- Consumers: `visual_level_between` / the single graded-sight authority (D4
  below) and `_delivery_ok`'s sight arm.

**G6. Data density: bearings, anchors, stations — the fidelity budget.**
Everything egocentric fails open without authored `dir` on edges, `dir` on
anchors, and stations on bodies: no facing → no left/right, no rear arc, no
`across` (`egocentric_frame` `spatial.py:1226-1244`; `_relative_sector:1469`;
`proximity_rel:1374`). That fail-open is correct firewall posture, but it
means the "pure function of spatial data" degrades to omnidirectional,
distance-flat vision exactly as often as the mapping stage declines to author
layout. `stations` were silently dropped for two releases and 0 of 45 live
scenes had one (`schemas.py:1770-1777`) — density is currently near zero.
- Not a schema change: a pipeline OBLIGATION on the mapping stage (the layout
  authority, `schemas.py:2576-2579`) to emit `anchors` (with `dir`), room
  `size`, and stations for every room it creates, plus an engine-notes
  coverage warning when a scene's edges/anchors are mostly bearingless, so
  sparse fidelity is visible instead of silent.

### Deterministic-floor DEFECTS found during audit (fix before composing)

- **D1 — whisper is never proximity-downgraded.** `SpeechVolume` keeps
  `whisper` distinct (`schemas.py:149-155`, `normalize_speech_volume:209`),
  but `hear_level`'s same-room branch tests only `volume == "mutter"`
  (`spatial.py:1039`; the comment at 1035 says "A whisper (mutter)" as if they
  were folded — they are not). A same-room whisper `across` a great hall
  returns `full`, contradicting prompt 880 ("whisper: ONLY same-room
  perceivers in close proximity"). One-line fix; today the model quietly
  corrects it, a composer will not.
- **D2 — `across` requires `size == "large"` exactly** (`spatial.py:1374-1376`)
  while the engine's own size vocabulary includes `huge`/`vast`
  (`_ROOM_COST` `spatial.py:5279`). A vast hall never produces `across`.
- **D3 — descriptionless-neighbor asymmetry in `visible_adjacent_rooms`.**
  The forward loop skips a neighbor with no desc/notes entirely
  (`spatial.py:5626-5629`), the reverse loop includes it
  (`:5669-5689` has no such check) — whether a bare room is visible depends
  on which side declared the edge.
- **D4 — two graded-sight authorities.** `sight_level(rel)` reads room-ambient
  light off the rel (`spatial.py:626-656`, light set by `spatial_rel:827,857`)
  while `visual_level_between` reads per-body `light_at`
  (`:784-803`); `_source_channels` documents choosing the latter to dodge the
  torch-pool disagreement (`agents/perception.py:1511-1521`). A pure FOV layer
  needs ONE function: `visual_level_between` extended with
  `spatial_rel_between`'s crossing/enclosure flags, and every caller of
  `sight_level`/`has_visual` on body pairs migrated to it.
- **D5 — edge `distance` is read but never normalized.** `spatial_rel` returns
  `edge.get("distance", "near")` (`spatial.py:854`) and `hear_level` branches
  on `"remote"` (`:1046`); no normalizer exists (compare `normalize_barrier`).
  Unverified whether any live scene authors it — audit before making it
  load-bearing.
- **D6 — `spatial_facts` at perception is env-gated OFF**
  (`SPATIAL_SCAFFOLD`, `agents/perception.py:318-327`). Under this branch it
  is not a scaffold, it is the spine; the gate inverts or disappears.

---

## 3. FOV model: current fidelity and where it breaks down

**Grain.** The model is room-graph + within-room stations, all topological.
No coordinates, no geometry. This is the right substrate for prose — every
output the prompt asks for is a WORD ("across", "to your left", "some way
north"), not a number — and the failure modes below are all places where the
topology is missing a relation, not places that need geometry.

- **Line of sight through openings: binary and whole-room.**
  `visible_adjacent_rooms` (`spatial.py:5578`) grants the entire neighbor
  (desc, onward exits) through any `_SIGHT_BARRIERS` edge; `_source_channels`
  grants every BODY in that room by the same room-level rel
  (`agents/perception.py:1546-1575`). Nothing models the view CONE of a
  doorway: a body standing beside the doorframe in the next room is fully
  visible. This over-grants sight (leak-shaped, though room-grain-small).
  Derivable improvement with existing data: compare the target's anchor
  bearing to the connecting edge's reciprocal bearing
  (`opposite_bearing(edge.dir)` vs `_anchor_dir`) and degrade off-axis bodies
  to absent/`shapes` — sparse-data fail-open, no new authoring.
- **Occlusion by entities and bodies: absent entirely.** No field says a
  pillar, crowd, or another body blocks sight (grep `occlu` hits only the
  prompt, `prompts.py:590`). Sight within a room is light + containment +
  rear-arc + (unenforced) periphery, nothing else. G5's `cover` covers the
  deliberate-hiding case; general occlusion needs per-anchor `blocks_sight`
  plus station adjacency and is the one item here that starts to WANT
  geometry — defer it.
- **Within-room distance: three tiers, rarely derivable.** `proximity_rel`
  (`spatial.py:1358`) is sound but starves without stations/anchors/size (G6,
  D2); default `near` makes a ballroom as intimate as a wardrobe.
- **Rear arc: two half-strength mechanisms.** Cross-room `behind_rooms` needs
  only movement history (robust); within-room `behind_sources` needs facing
  AND the target's anchor bearing (`_relative_sector` `spatial.py:1458`), and
  the sector approximation ("target anchor's absolute room bearing taken as
  its direction from an observer near room centre", `:1463-1465`) is wrong
  when the observer stands at a wall — sides can flip. Acceptable at
  room-grain; will occasionally misplace left/right in composed prose.
- **Elevation: edges only.** `vertical` up/down is normalized and reciprocal
  (`spatial_orientation.py:183-226`), bucketed above/below
  (`spatial.py:1219-1224`). No within-room verticality (catwalk, loft — only
  free-text poses), and `corridor_sightlines` requires `dir` so a shaft/
  stairwell never forms a sightline. A balcony-over-hall reads as an ordinary
  visible adjacent room, which is coarse but not wrong.
- **Directional hearing: level only, no bearing.** `hear_level` returns
  none/fragment/full; the prompt promises "a heard event may carry a
  direction" (658-660). Fully derivable: cross-room via
  `travel_bearing`+`relative_bearing` → "through the doorway behind you";
  within-room via `_relative_sector`. Needs one new pure function
  (`sound_bearing(scene, observer, source)`), no data.
- **Acoustics are single-hop.** Non-adjacent rooms are `separated`
  (`spatial_rel:860-864`) → shout=fragment, else nothing. A shout down three
  open arches dies at the second. Note the prompt AGREES with this
  approximation ("separated/far -> nothing for ordinary senses", 595), so
  changing it is a spec change: a graded walk over the open-edge graph
  (rungs of `_SOUND_LADDER` per hop; `ambient_scope`'s component,
  `spatial.py:6246`, already computes the reachable set). Nice-to-have.
- **Focus/periphery: data yes, enforcement no.** Focus is computed and
  persisted; what "foveal detail" means (faces, text, sleight, gaze) exists
  only as prompt vocabulary (670-681). The composer needs a detail taxonomy —
  each deliverable already arrives typed (tells: gated; body_regions: gated;
  speech: heard regardless; appearance: novelty-gated), so the remaining rule
  is roughly "periphery/`across`/`shapes` ⇒ withhold body_regions detail,
  tells, text-bearing entity state, and fine-motor acts" — which needs G1's
  element classing (`motor: gross|fine` or the sound/loudness proxy) to gate
  "slips it into a pocket" honestly.
- **What is already excellent** and battle-hardened (each carries a
  measured-live regression in its docstring): containment three-direction
  relations, threshold crossings, carried-light pools, barrier folding,
  membrane semantics, corridor sightlines with vagueness, onward exits with
  bearings, beat-start channel union (`_saw_across_beat`), ambient nesting.

---

## 4. Sole-source vs approximations (what determinism exposes)

**Good enough to be the sole source of a view, today:**
- Channel grading: `hear_level` (+material), `scent_level`,
  `visual_level_between`, `_delivery_ok` — subject to D1/D4 fixes and G4.
- Light: the whole stack `room_light→light_at→effective_light`.
- Containment/enclosure/crossing/carried-interior logic.
- `corridor_sightlines`, `_onward_exits`, `visible_adjacent_rooms` (after D3)
  — already emit render-ready vocabulary (`vagueness`, bearings).
- Prose atoms: `contact_phrase`, `contact_sensation`,
  `substance_event_clause`, `spatial_facts`, `weather_words`,
  `observable_action_text` + `_observable_predicate` (the micro-loop,
  `agents/loops.py:45-140`, is the working proof that deterministic view
  composition already ships).
- The projection layer: `_observer_scene_payload` — the target input format;
  a composer consumes it instead of a model.

**Approximations a reader will catch once no model smooths them:**
1. Whole-room sight through any opening (bodies beside the doorframe seen;
   "you see the whole guardroom through the grate").
2. Everyone `near` by default — distance-flat rooms (G6/D2).
3. No hiding without a container entity (G5).
4. Unseeable acts vanish or collapse to one generic sentence instead of
   becoming sound (G1) — a fight behind a wall is silence.
5. No alarm exemption — nothing behind you can startle you (G2).
6. Turning does not exist — the blind spot survives "I turn around" (G3).
7. Blind/deaf/keen senses ignored (G4).
8. Anchor-bearing side approximation occasionally flips left/right at walls.
9. Same-room whisper carries across a hall (D1).
10. A shout dies at the second open archway (spec-consistent, but readers
    notice).

---

## 5. Priority summary

Must-have (correctness of the pure function): **G1** per-event sound surface
(+ verb-lexicon fallback), **G2** alarm derivation + focus snap, **G3**
orientation_ops for turning, **G4** deterministic sense gate, **G5** station
`cover`, **G6** mapping-stage layout-density obligation + coverage warning,
and defect fixes **D1-D4, D6** (D5 audit).

Nice-to-have (prose quality, no firewall exposure): doorway view-cone
degradation from existing bearings, `sound_bearing` derivation, multi-hop
acoustic walk over the open graph (deliberate spec change), `distance` edge
normalizer, periphery detail taxonomy refinement beyond the G1 classing,
within-room elevation, general entity occlusion (defer — the only item that
wants geometry).

Everything proposed lives inside `world.scene` (stations/orientation keys the
blob already carries) or on already-persisted models (`StateDiff`, sequence
elements, character sheets), so checkpoint restore, chat archive, and
branch/clone remapping are untouched; the `world_entities` projection is
unaffected because no new entity-level field is introduced (if one ever is,
it must join `_ENTITY_DEFAULT_FIELDS` `spatial.py:5778` and `_merge_entity`
`AGENTS.md:52`).

Unverified items flagged above: whether edge `distance` is ever authored live
(D5); `observer_body_regions` internals (read only at the import/call sites);
exact live density of `anchors.dir`/edge `dir` (the 0-of-45 stations figure is
from the schema comment, `schemas.py:1772-1774`, not a fresh count).
