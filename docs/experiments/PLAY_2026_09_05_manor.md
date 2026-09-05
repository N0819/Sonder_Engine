# Play run, 2026-09-05: "Winter at Harrowgate Manor" — a locked study, three secrets, twenty beats

Status: EVIDENCE. One fresh non-explicit scenario authored through the app's own
routes on an export-built scratch database (`tools/export_bench.py prepare --src
engine.db --chats 115`), Gemini 3.8 flash on provider 3 for every role, capture
on with full bodies. Twenty player turns (idx 0–19), every stage of every beat
read against the others — the merged `state_diff` and its specialist channels,
the scene before and after, the registry, and the trace of what each call was
SENT — plus deterministic probes of the light, sound and sight fields on the
committed scenes, three Writers' Room sessions and three World Browser write
sessions. Finding ids are `PC1…`; where a class recurs from
`docs/experiments/DEBUG_RUN_2026_09_05.md` or `DEBUG_RUN_2026_09_04.md` the F id
is cited. `export_bench.py scan` was run over everything written outside the
scratch database before this file was committed: no provider key in any file.

Engine version: turns 0–11 ran in a worktree of `writers-room` at `527ffcc3`;
the session was interrupted by a model usage limit and turns 12–19 ran in the
main tree at `3e56c6d8`. The diff between the two touches `web/world_routes.py`,
`world/charter.py`, the map's JS, docs and tests — nothing in `agents/`,
`world/spatial*`, `mind/` or `persist/`, so no finding below spans the change.
No beat was F1-class (no reasoning-only reply on any of the 249 calls).


## 1. Story and setup

**Player persona** (`persona_create`): Inspector Ada Quill — methodical, asks
precise questions, notices doors.

**Cast** (`char_create` + `chat_add_char(already_known=True,
already_known_cast=True)`; `character_card_warnings` empty for all three):

- **Lord Edmund Harrowgate** — drive: *the Harrowgate name must stand unstained
  in every eye that looks at it*; taboo: *admitting the estate is bankrupt*.
  Private history: he moved the ledger himself, locked it in the tower window
  seat, and reported it stolen.
- **Mrs Penrose** — drive: *the people who work in this house must come to no
  harm through the doings of the family*; taboo: *letting a servant take the
  blame for something the family did*. Private history: she SAW him do it, from
  the dark of the servants' passage, and has told no one.
- **Felix Brand** — drive: *to be believed*; taboo: *being caught in a lie and
  having to admit it*. Private history: innocent; he was on the terrace with
  Edmund's cigars, not in the library as he claims.

Values were phrased as trade-offs throughout ("the family's reputation over the
plain truth", "silence over a scene, until the silence costs a servant"), each
card carrying traits, capacity, coping style, self-model, one protected belief
and two ranked goals.

**Geometry.** The opening (`director_establish`) minted all twelve rooms from
the scenario by id, with barriers, verticals and named doorways — nothing had to
be corrected by hand. What the establish did NOT write was measurement: 0 of 12
rooms carried `extent`, `shape` or `parts`, and no thing carried a source field
(F45 recurs exactly). Those were authored afterwards through the World Browser
routes: `PATCH /rooms/{id}` for `extent`/`shape`/`parts`/anchors (the hall an L
of 14×8, the gallery an L in an 8×16 box, the tower `round` 6×6, the passage
2×10), `PATCH /doorways/{a}/{b}` for offsets, names, materials, the study door's
`state {locked, key}`, `POST /rooms/{id}/entities` + `PATCH …/entities/{eid}`
for eleven light and sound sources (`light_source`, `light_height`,
`light_shape`, `steadiness`, `sound_source`, `state.lit`, `state.running`),
`PUT /bodies/{name}/station` for cells. Every one of those writes was accepted;
none was refused. Written **by hand into the scene blob** because no route
exists: `scene.contained` (the study key carried on Edmund's chain, the
notebook and Felix's book held). No charter: this scenario has four bodies and
no institutions, so the charter path was deliberately not exercised.

Two geometry corrections were made after reading the first grids: the hearth's
`footprint` from `large` to `small` (a `large` waist anchor on a wall inset two
rows and swallowed the bodies stationed at it) and three doorway offsets, after
which `inspect_contradictions.layout` went from four `rooms_overlap_when_placed`
rows to zero and stayed there for the rest of the run.


## 2. Turn table

| # | Player prose (summary) | Outcome | Findings |
|---|---|---|---|
| 0 | Arrives from the snow, asks to see the door the ledger went through | Establish mints 12 rooms, 4 items, all positions; 6 setting-fact needs filed | F45 |
| 1 | Tries the locked study door, asks who else holds a key | Edmund answers; hall loses hearth + table anchors to a one-anchor diff | PC6, PC8 |
| 2 | Walks to the hearth, holds out her hand for the key | Key transferred by `inventory_ops`, containment follows | works |
| 3 | Pockets the key, questions Felix in the library about his book | Felix deflects, names "pastoral elegies" | PC11 |
| 4 | Leaves through the service door into the dark passage | Movement refused (library→passage not adjacent), travel completes next beat | F28 |
| 5 | Down to the kitchen; asks staff names and where Penrose stood | Penrose names four servants, places herself in the passage | works |
| 6 | Whispers an accusation at her elbow, covers it aloud | Whisper correctly undelivered at arm's reach (measured `none`) | works |
| 7 | Takes her elbow, tries to lead her upstairs | Contested; Penrose refuses, reaction loop fires | works |
| 8 | Orders her formally; climbs and waits at the stair head | Penrose lights a candle and follows; a new lit source minted | works |
| 9 | Unlocks the study, opens it, calls for the candle | Door opens on both edges; hall anchors dropped again | PC6 |
| 10 | Enters the dark study, lights the desk lamp, has the door shut | Room `dark`→`lit`; door `closed_door` on both edges | works |
| 11 | Presses Penrose across the lamp | Penrose deflects; Edmund receives the study's conduct through the shut door | **PC1** |
| 12 | Offers to keep her name out of it | Penrose refuses, half-admitting; Edmund again receives the conduct | **PC1** |
| 13 | Douses the lamp, locks up, crosses to the gallery | Movement refused whole; pose says gallery, position says study | PC7 |
| 14 | Unlocks, sends Penrose down, walks to the gallery | Two-room walk commits; the hidden ledger's scent reaches the gallery | PC5 |
| 15 | Steps behind the folding screen and waits, silent | Stationed at the screen; `cover` never set from prose | PC9 |
| 16 | Shouts down the house for Edmund and Felix | Nearest, addressed listener hears nothing; two farther ones get fragments | **PC3** |
| 17 | Whispers the accusation at Edmund's ear, asks Felix for a match aloud | The whisper reaches NOBODY, addressee included; the aloud line lands | **PC2** |
| 18 | Lights the tower candle, opens the window seat | Candle contributes no light this beat; the reveal cannot be encoded | PC4, PC5 |
| 19 | Lifts the ledger into the candlelight and confronts him | Edmund holds the line without breaching his taboo | works |


## 3. Findings

### PC1. A `shapes`-only sight channel is spent as a boolean, so the act channel delivers full conduct through a shut door
**Severity: firewall (engine).** Stage of origin: `agents/perception.py`
(`_in_plain_view`) with `agents/composer.py::act_percept`.

Turns 11 and 12. Ada and Mrs Penrose are inside the study; the door is
`closed_door` on BOTH edges and locked; Lord Edmund is at the hearth in the
hall. His `perception_act` view carried, verbatim:

> "Ada Quill perches on the corner of the desk, setting the lamp between herself
> and Mrs Penrose. Ada Quill opens a black notebook on her knee."

and at turn 12 "Ada Quill pauses, letting the silence hold. Ada Quill turns the
notebook face down onto the desk," plus Mrs Penrose's own conduct. No speech
crossed — the dialogue gate honoured the barrier perfectly — so the two channels
disagreed about the same wall in the same beat.

Mechanism, probed on the committed scenes: `closed_door` is not in
`_SIGHT_BARRIERS`, so `sight_level` is `none`; but turn 10 moved both women
through that door as it shut, and `spatial_frames.infer_threshold_crossings`
wrote `crossings: {Ada Quill: {from: great_hall, to: study, beats: 1}, …}`. The
crossing floor is by design — "a body that has just crossed an opaque boundary
is not instantly gone" — and it floors sight at **`shapes`**. `_in_plain_view`
then reduces that to `bool`, and `act_percept` takes `can_see` as a boolean, so
a shape-in-the-doorway budget buys a readable description of conduct at the far
side of the room. The record survived two composed beats (written at turn 10,
decremented at turn 11's commit, dropped at turn 12's).

The class, in engine vocabulary: **sight is graded and the act channel is not.**
Anything that grades to `shapes` — a crossing, a dim room, a `far` edge, an
opening's view cone — currently admits the same text a `full` line does.

Fix (`agents/composer.py`, `agents/perception.py`): pass the sight LEVEL, not a
boolean, into `act_percept`; at `full` admit the observable surface, at `shapes`
admit a motion percept that names no object and no detail ("someone moves,
beyond the door"), at `none` refuse — one rule, every grader that already
returns three words. Test: two bodies either side of a `closed_door` with a live
crossing record; assert the actor's surface is absent from the observer's view
while the shape line is present, and that the same pair at `full` gets the
surface.

### PC2. A line whose `conceal_from` names its own addressee is delivered to nobody, the addressee included
**Severity: story-breaking.** Stage of origin: `director_interpret` (the
concealment validation), consumed by `agents/composer.py::concealed_from_observer`.

Turn 17. The player whispered to Edmund at arm's reach: *"Your housekeeper will
not say it, so I shall. You carried it out yourself."* The interpret captured it
correctly (`speech` holds the exact line) and warned:

> `llm validation: speech concealed from its own addressee (4); dropped from conceal_from, 1 excluded remain`

The line then appears in **no view at all** — not Edmund's, not Felix's, not the
player's own outcome view — and in no narration. Searched the whole beat blob:
the phrase exists only in the interpret's `speech` field. The player's declared
speech was silently deleted; the same beat's aloud line was delivered to
everyone correctly, so the loss is specific to the concealed line.

The validator repaired one id (4, Felix) and left the other exclusion standing,
which happened to be the addressee. The class: **a line cannot be concealed from
its own addressee, and a line concealed from every present observer is a
declaration the engine dropped rather than a secret it kept.**

Fix (`agents/director.py`'s interpret validation): strip EVERY addressee from
`conceal_from`, not the one the check happened to identify; and where the
resulting audience is empty, warn as a dropped player declaration
(`player state:` family) rather than passing it through silently. Test: an
interpret output whose `conceal_from` lists the whole cast including
`intended_target`; assert the addressee receives it.

### PC3. The act floor and the outcome floor grade one shout differently, and the mind gets the stricter one
**Severity: story-breaking.** Recurs `F61` (2026-09-05) with the roles reversed.
Stage of origin: `agents/perception.py` (the act pass's sound field).

Turn 16. Ada, in the gallery, shouts by name for Edmund and Felix. Delivery:

| listener | where | act view | outcome view |
|---|---|---|---|
| Lord Edmund (addressed) | great hall, one **open** stone archway away | **nothing** | full: `Ada Quill shouts: "Lord Harrowgate! Mr Brand! …"` |
| Felix (addressed) | library, two rooms | `A muffled voice: …Harrowgate… please… gallery…` | fragment |
| Mrs Penrose | servants' passage, behind a shut service door | fragment | fragment |

Probed on the scene as the act pass saw it (Ada stationed at `folding_screen`,
the far arm of a 16-pace L, behind an opaque head-height run anchor): the
composite field gives gain **0.00214** against noise **0.5** — SNR 0.13, under
`FRAGMENT_SNR` 0.8 — so `shout` quantises to `none`. The edge model on the same
pair gives `full` (`barrier: open`, `distance: near`). The two listeners the
field could not place on the listener's grid fell through to the edge model and
got fragments. So the nearest listener across the most open edge in the house
heard less than one behind a shut door, and the character call for the man being
summoned by name saw only her movements.

The class: **one line, two floors, and which floor answers depends on whether
the listener's composite grid happens to place the speaker's room.** Fix
(`agents/perception.py`): hand the act pass and the outcome pass the same field
for the same beat (F61's fix, applied in this direction too); and, in
`world/spatial_sound_field.py`, floor a raised voice one passable edge away at
`fragment` — a shout that carries less than a shut door does is the field
disagreeing with the ladder it quantises onto, not a measurement.

**SECOND HALF FIXED (2026-09-05).** The perception half landed first, and on
its own it made both passes agree on the STRICT answer — so a shout across one
open archway reached nobody in either pass, which is the disagreement fixed
and the reach lost. *A raised voice carries through an opening: one passable
edge away it is at worst a fragment.* `open_edge_floor` in
`world/spatial_sound_field.py` says so, `stamp_sound_relation` marks the pair
that has an opening between them (`one_opening_away` — undirected, because a
doorway is one object declared from either side, which is also what keeps the
floor reciprocal, and material-shifted, so a paper door is the opening it
acoustically is), and `hear_level` applies it wherever its answer would be
`none`, on the field branch and the edge branch alike. It is capped by the
same masking rule everything else answers to (§ PA5): where the noise at the
listener's own cell would refuse the same voice ONE PACE OFF, nothing from
the next room survives either — an opening carries a voice INTO a room, not
through the machine running in it. Pinned by
`tests/test_sound_field.py::test_a_raised_voice_across_one_opening_is_at_worst_a_fragment`,
`::test_the_floor_needs_an_opening_and_yields_to_the_room_it_arrives_in` and
`::test_the_opening_is_one_doorway_however_it_was_declared`.

### PC4. A `flickering` source on the bottom rung of the ladder is extinguished, not dimmed, and nothing says so
**Severity: wrong-but-recoverable.** Stage of origin:
`world/spatial_light_field.py` (`steadiness_this_beat` + `_power_of_level`).

Turn 18. Ada strikes a match and lights the tower candle; `state.lit` is `true`,
`light_source: dim`, `steadiness: flickering`. The tower room's light field for
that beat lists sources `[north_sconce, south_sconce]` — the two sconces of the
NEXT room — and not the candle burning in the room. All 32 cells read `dim` (the
room's declared floor), and the composed view says "The light is dim."

Isolated on the committed scene by four probes: with `steadiness: steady` the
candle appears (power 2.0); with `light_source: lit` it appears; stationed, or
made non-portable, it still does not. The cause is the flicker rule — one beat
in `FLICKER_RATE` a flickering source "drops one level", and one level below
`dim` is `dark`, i.e. no emission at all — applied to the lowest emitting rung.
`state.lit` stays true, no notice is filed, and the only light in the room
vanishes for a beat while the story holds it in the player's hand.

Fix (`world/spatial_light_field.py`): clamp the flicker drop at the lowest
emitting rung — a flickering candle guts, it does not go out — and leave
extinction to `failing`, which has its own notice. Test: a `dim`+`flickering`
source over `FLICKER_RATE` consecutive beats; assert it is a placed source on
every one of them.

**FIXED (2026-09-05).** `_one_level_down` stops at the dimmest light a source
can still give, and `_power_of_level`'s drop stops at the quietest sound: a
flicker is a source WAVERING, not a source failing, and going out is what
`failing` means — which files a notice the Director answers, where a flicker
files nothing. The sound field had the same arithmetic and the same defect (a
`faint` generator dropping to silence), so both were fixed together off one
rule; a source declared `dark` is not a light and a flicker does not make it
one. Pinned by
`tests/test_light_field.py::test_a_flickering_source_on_the_bottom_rung_still_gives_light`
and `tests/test_sound_field.py::test_a_flickering_source_on_the_bottom_rung_still_sounds`.
Landed in the same commit as PA3, and the pair is consistent: PA3's floor
reads the SWITCH (`state.lit`), never the beat, so a flickering fixture
between its beats still holds its room's floor up and this repair means it is
never off in the first place.

### PC5. Concealment authored as free text is not a channel, so the beat that ends it cannot encode the reveal
**Severity: story-breaking (the scenario's payoff).** Stage of origin: the
objects specialist's `state_diff.entities`, caught by the resolve reconciliation.

**RESOLVED 2026-09-05 (a), (b) partly, (c) not taken.** The channel was
never absent -- `containment` carries a THING on exactly the terms it
carries a body, `_clean_containment` accepts any holder the scene places,
`derive_contained_positions` puts the thing where its holder is, and
`hiding_holders_of` then subtracts scent, sight, sound and reach for free.
What was absent was any sentence telling either hand so: the containment
chunk opened "when a BODY stops being independently placed", and the objects
chunk enumerated `state` as configuration ("open, worn, held, lit, in
transit"), which is an invitation to write exactly the key that broke this
story. Two clauses, stating one class from each side -- something is between
the thing and the room and that something has a name; where a thing is is
never a word in `state`. Release (`{thing: null}`) is what makes finding it
an act with a result. (b) is served by the second clause naming what the
silent failure costs rather than by a new warning; (c), a planning need from
the reconciliation, is not taken -- it already warns. Pinned in
`tests/test_played_scene_classes.py::test_a_thing_shut_inside_a_scene_object_is_revealed_by_opening_it`.

The ledger was authored as the establish left it: `state: {condition: intact,
concealment: "hidden inside the locked tower window seat"}`, positioned in the
tower room at the `window_seat` anchor. Nothing in the engine reads
`state.concealment` (grepped: no reader). Two consequences, both measured:

- Turn 14, the player standing in the gallery: `The air carries old paper,
  binding paste, and dry leather` — the ledger's own authored scent, through the
  open doorway from the tower room, while the ledger is supposedly shut inside a
  chest. The clue that should have cost an act of search was free.
- Turn 18, the beat that opens the seat: the objects hand minted `window_seat`
  as a `container` with `state.open: true` and flipped the ledger's
  `state.concealment` to `"exposed"` — but nothing moved the ledger into the
  container and nothing put the container in a room. Both warnings fired:
  `Unplaced entities: console_table, window_seat exist after this beat but are
  in no room, so nothing can perceive or act on them`, and
  `Resolve reconciliation: prose asserts 'Concealment ended; estate ledger is
  exposed and illuminated inside the open window seat.' … but state_diff still
  does not encode it after self-repair`. The player's view of the opened seat
  named the bench and no ledger.

The class: **a thing is hidden by being inside something, not by a sentence
about it.** The engine already owns the record — `scene.contained` with a
container whose `state` says shut — and every field subtracts from it for free
(scent, sight, sound, reach). Fix, in this order: (a) the objects hand's clause
should state that a thing inside another thing is a `containment` entry naming
the container, and that revealing it is removing that entry, never a word in
`state`; (b) `character_card_warnings`' sibling for scene authoring — or the
establish validator — should say out loud that `state.concealment` is read by
nothing, exactly as the card warnings say it for `distinctive_features`;
(c) the reconciliation that already detects the mismatch should file a planning
need rather than only warning. Test: an entity contained in a shut container in
an adjacent room; assert its scent and sight are absent from a neighbour's view,
and present after the container's `state.open`.

### PC6. F60 recurs twice: a diff that adds one anchor drops every anchor the room had
**Severity: wrong-but-recoverable.** Recurs `F60` (2026-09-05), same shape,
new consequence. Stage of origin: `world/spatial_merge.py::_merge_room`.

Turn 1, `state_diff.rooms.great_hall.anchors` = `{study_door: {...}}` alone; the
committed hall kept `study_door` and lost the host-authored `hearth` (waist,
`offset` 0.15) and `oak_table` (waist, `cell` [9,3]). Turn 9 did it again after
I had restored them. The measured consequence beyond the loss itself: Lord
Edmund's station `at: hearth` no longer resolved, so `body_cell` returned None
and the grid reported him `source: "none"` — an unmeasured body in the room
where the whole beat was happening, which is exactly the input the sound field
needs (see PC3). Two anchors carrying heights were the hall's only cover and its
only sound geometry.

Fix as UNBUILT § 2.35 already states it: incoming anchors ADD to the room's; a
removal needs its own channel. This run is the second measurement and adds the
argument that the loss is not cosmetic — it un-measures the bodies standing at
them.

### PC7. A declared walk that crosses one room is refused whole, and the pose that asserts the destination survives
**Severity: wrong-but-recoverable.** Same family as `F28` (2026-09-04),
one step on. Stage of origin: `agents/director_movement.py` (the backstop) and
`world/spatial_merge.py::invalidate_moved_body_pose_details`.

Turn 13: "…walks west across the lit hall and out under the stone archway into
the dim gallery." Interpret: `movement {to_room: long_gallery, arrives: true}`.
Warning: `Blocked movement: no passable route from 'study' to 'long_gallery'
(barrier=separated); position unchanged.` Ada stayed in the study — with the
door she had just locked — while the committed pose read

> `detail: "standing on the flagged floor of the long gallery after passing beneath the stone archway"`

and Penrose's pose put her "at the locked study door with an ear pressed against
the cold oak panel", inside the room she was locked in. The narrator then wrote
the scene from the poses, so the reader ended the beat with two people in the
gallery and the engine with two people locked in the study. (The same shape
committed correctly on turn 14 once the door was open, so the refusal is about
passability, not the two-room span.)

Fix: (a) when a declared walk is refused, clear the mover's own pose `detail`
if it names the destination — the F49 rule, applied to a refusal rather than a
move; (b) walk the passable prefix of the declared path (F28's own rule) so a
refusal is "she got as far as the hall", not "she never moved". Test: a locked
edge two rooms along a declared walk; assert the position lands on the last
passable room and no pose text names the room beyond it.

**FIXED (2026-09-05).** (a) landed first as `state_diff.movement_refused`:
`director._refuse_movement` records every body the backstop holds back and
`spatial_merge._refused_movers` subtracts that body's position, station and
pose together, so a refused walk leaves nothing behind. (b) landed the same
day with the contest rule it belongs beside: a route whose only impassable
edges are shut doors is CONTESTED rather than blocked, the resolve owns the
crossing as it always has at one hop, and where the resolve does not assert it
the walk commits its passable prefix. A locked door is a shut door
(`normalize_barrier` folds locked/jammed/padlocked onto `closed_door`), so
turn 13's walk now either commits — the resolve having said she unlocked it
and went — or lands her in the hall with the gallery pose dropped;
`_strip_unreached_placement` makes the second case the same subtraction the
refusal channel makes, minus the position, which is true and stands.

### PC8. The second-person rewrite substitutes inside titles and repeated names
**Severity: cosmetic, but it fires the composer's own engine-defect tripwire.**
Recurs and widens `F65` (2026-09-05, "toward you you"). Stage of origin:
`agents/composer.py` (`_action_target_second_person` / `_self_second_person`).

Measured strings from this run's views: "facing Lord you", "before Lord you",
"toward Mrs. I with practiced, gentle courtesy", "turns away from you you",
"turns away from Felix Brand Brand", "letting the door swing shut behind Ada
Quill's". Twice the tripwire caught it and said so:
`perception_outcome: COMPOSER TRIPWIRE -- composed view of Lord Edmund
Harrowgate narrated its own perceiver (engine defect): 'Harrowgate…'`.

Fix: substitute on a whole NAME occurrence — the display form and its aliases,
bounded — rather than on a name fragment, and never inside a token already
rewritten. Test: an act surface naming "Lord Edmund Harrowgate", "Mrs Penrose"
and a bare surname, rewritten for each as observer; assert no output contains a
title adjacent to a pronoun or a doubled token.

**FIXED (2026-09-05), as one rule in one place.** A NAME'S OCCURRENCE INCLUDES
THE TITLE AND ARTICLE THAT LEAD IT: `common.name_occurrence_pattern` builds
every name match from the engine's own closed table (`_NAME_LEADERS` narrowed
to `_NAME_TITLE_TOKENS`, the same table `_identity_token_set` strips when it
compares two names and `_subject_opener` accepts before a subject — the
alternation is now shared, `_name_title_alternation`), so "Lord Edmund
Harrowgate" and "Mrs. Penrose" are each one occurrence, matched from the title.
And the forms of one body are alternated WIDEST FIRST, which is the doubling
half: applied in arrival order the short form fired inside the long one, so
"toward Dov Aharon" became "toward you Aharon" became "toward you you" (F65).
`_self_second_person`, `_action_target_second_person` and
`_pose_owner_second_person` all match through it, so the episode renderer's
first-person pass ("Mrs. I") inherits the boundary rather than needing its own.
NOT rewritten on the typed percept before rendering: the rewrite already
operates on ONE authored surface with a known owner and a known observer
rather than on free prose, and the defect was the match's boundary, not the
layer. "turns away from Felix Brand Brand" and "behind Ada Quill's" are not
this — neither is a second-person substitution — and are unaddressed.

### PC9. `cover` is authored only by a station, so "behind the screen" is prose the geometry never sees
**Severity: wrong-but-recoverable (owner decision on the second half).**
Stage of origin: `director_resolve`'s spatial channel.

**RESOLVED 2026-09-05, and the diagnosis above was half wrong in the way
worth recording.** The prompt half was already done: the spatial chunk has
carried the cover clause since 2026-09-02 (`EXPECTED_DIVERGENCE`,
`specialists.spatial.chunks.stations`). What no one had checked is whether
the field the clause names could reach the geometry, and it could not --
`schemas._coerce_station_table` built its entry from `at` and `near` alone,
so every `cover` any hand has ever written was dropped at the schema
boundary before the merge saw it. One key through the coercion is the whole
fix; `normalize_scene_stations` cleans a cover naming a fixture the body has
left, the sibling of the stale `at` it already blanks. The clause was right
and had nothing to write to. Pinned in
`tests/test_played_scene_classes.py::test_a_body_that_takes_cover_is_out_of_the_line_that_crosses_the_fixture`
and `::test_the_station_table_carries_the_cover_the_hand_was_told_to_write`.
The owner decision below (should `relation: "behind"` set cover
deterministically) is untouched and stays open.

Turn 15 the player stood behind the opaque folding screen. The diff wrote
`stations.Ada Quill = {at: folding_screen, near: []}` and a pose whose
`relation` is "behind"; the station carried no `cover`, which `body_cell`
documents as "declared by the station's owner, never inferred from prose". So
she stood on the room side of the screen with a pose saying otherwise.

Two separate things are worth reporting, and the second is a **works**: the
screen itself occludes correctly. Probed on the committed scene with the gallery
forced `lit`: a body north of the screen line is `none` from three cells south
and `full` from the same side; delete the two screen anchors and the same pair
reads `full`. In the room as authored (`dim`) every cross-room pair is already
`shapes`, so the screen adds nothing observable — which is the honest reading of
the "screen occluding a body in the dim gallery vs the lit hall" test: **the
occluder works, and a dim room cannot show it.**

Fix (prompt, not a guard, per CLAUDE.md): the spatial hand's station clause
should say that `cover` is what a body puts between itself and the room, and
that a pose relating a body to an anchor on the far side of it is a cover
declaration. Owner decision on whether `relation: "behind"` should set it
deterministically.

### PC10. The Room explains a tool result with a mechanism the engine does not have
**Severity: wrong-but-recoverable (Writers' Room).** Stage of origin:
`agents/story_planner.py`'s reply, over `inspect_route`.

I dragged the terrace doorway to `offset` 0.98 through the World Browser and
asked the Room what the contradiction check said. It answered, correctly, "zero
rows", and then:

> "pathfinding verification between the Long Gallery and the Snowy Terrace
> reports that the terrace is currently **unreachable** (`hops: null`) … it
> pushes the portal beyond the traversable mesh/navigable cell, meaning a
> character cannot physically walk through it."

`inspect_route` returns `{hops: null, path: [], reachable: [...]}` and no cause.
The terrace is unreachable because the glazed door is `closed_door`, which is
not in `_PASSABLE_BARRIERS`; the offset is irrelevant and "traversable mesh" is
not a thing this engine has. The class: **a tool that answers WHAT without WHY
invites the reply to invent the why.** Fix (`story/room_tools.py`):
`inspect_route`'s unreachable answer should name the first blocking edge and its
barrier, which the router already knows.

### PC11. The quote guards fire on the narrator's own delivered fragments
**Severity: cosmetic, but it is 35 of the run's 163 warnings.** Recurs `F54`,
`F29`. Stage of origin: `agents/narration.py`'s fidelity checks.

Counts across 20 beats: `Delivered line rendered without quotation marks` ×17,
`Narrator invented quoted dialogue absent from the player view` ×18. Inspected,
almost all are false in the same two ways: the narrator doubled its quotation
marks (`""line""`, ten beats), and — new here — the guard matched the composed
MUFFLED FRAGMENTS as invented dialogue, e.g. `"…indeed… Inspector… Precisely…"`,
which the view itself delivered. Fix: normalise repeated quote runs before
matching (F54's own proposal) and exclude the fragment form the composer emits
from the "invented dialogue" match — it is engine text, not model text.


## 4. Works — what behaved by the rules

- **The firewall held on all three of the story's secrets.** Searched every
  memory row of all three minds at the end of the run: Felix never learned what
  Penrose saw (his rows carry only what he saw of Edmund in the hall and heard
  through two doorways); Edmund never learned that Penrose saw him (nothing in
  54 rows); Penrose's knowledge stayed hers and she never said it aloud, holding
  her taboo under direct pressure for four beats. The inspector's conclusion was
  her own: the only channel she had was Penrose's refusal shape ("If you intend
  to accuse his lordship of taking what belongs to him, you will have to do it
  without an old woman bearing witness"), and Penrose's own `inference` rows
  track that exchange truthfully. **The one breach measured anywhere in the run
  is PC1**, and it is an ACT-channel breach across a shut door, not a
  knowledge-tier one.
- **Dramatic irony worked as designed.** Edmund answered questions about a theft
  he committed while composing himself for an audience; his appraisals cite the
  right evidence ("Quill's focus on key access threatens to expose that no one
  else could have entered"), his `about_others` model of the inspector sharpened
  over the run ("willing to bypass the primary crime scene", 0.75), and at turn
  19, holding the recovered ledger in his own house, he still did not breach his
  taboo: *"A remarkably clumsy place for an intruder to abandon it, Inspector."*
- **Deception behaved.** Felix lied about small things unprompted and in
  character (offering the book's title, then looking at the title page to check
  it), which is precisely his drive expressed rather than a plot device.
- **The locked door, end to end.** The `state {locked, key}` I authored on the
  passage record survived twelve beats and four merges; the door refused
  movement while shut; the key transferred by `inventory_ops` with containment
  following; the unlock, the open, the shut and the re-lock each landed on BOTH
  edges and on the passage record, and `inspect_contradictions` never reported a
  reciprocal disagreement. Opening from the study side (turn 13) and from the
  hall side (turn 9) both synced. This is F16/F22's class, and the passage
  record closed it.
- **Whisper grading, measured.** Turn 6, at the housekeeper's elbow with the
  range roaring: field gain 0.5, noise 0.77 → `whisper: none`, `normal: full` —
  the whisper was correctly NOT delivered even at one cell, because the range is
  a `faint` running source beside them. Turn 17's aloud line reached the library
  through two doorways while its paired whisper reached nobody (PC2 aside).
- **Light, when the field has sources.** The study went `dark`→`lit` on the
  beat its lamp was lit and back to `dark` when doused; the shape sentence fired
  where the room was uneven — "The light from brass candlestick thins to
  half-light at a cold iron grate … and leaves shelves of leather-bound legal
  folios in the dark. You stand in half-light." — and the flat sentence where it
  was even. (The article gap F52 noted is still there: "from brass candlestick",
  "from north sconce, south sconce, and the opening".)
- **Occlusion by an opaque anchor** — see PC9's second half.
- **The round room.** The 6×6 `round` tower composed 32 cells, placed the window
  seat and sill on the northern arc and the doorway on the south arc as a gap in
  the rim, and the L-shaped gallery blocked sight between its two arms (a probe
  body in the far arm read `none` in both directions).
- **World Browser writes survived every commit.** Every authored `extent`,
  `shape`, `parts`, doorway `offset`, `material`, `state`, source field and
  station `cell` written between beats was still there at turn 19 — with the
  single exception of anchors, which PC6 covers. The `steadiness: flickering` I
  set on a sconce mid-run persisted; the station `cell` I pinned Felix to
  ([1,4], `source: "cell"`) survived the next two commits and was dropped
  correctly when he changed room. The routes refused what they should: `offset
  1.6` came back "must be a number between 0 and 1 … (got 1.6)".
- **The engine's own warnings did their job repeatedly** — the movement
  backstop, the resolve reconciliation on both the door prose (turn 4) and the
  concealment prose (turn 18), the unplaced-entity notice, the claims floor, and
  the composer tripwire. Nearly every finding above was first visible in a
  warning the engine raised itself.


## 5. The Writers' Room as co-author

Three sessions (turn 5, turn 13, turn 19), one grant, one published package, one
resolve.

**What it did well.**

- The grant was read exactly as written and turned into a mandate carrying
  `plan_rooms` and `director_note` and nothing else; it then declined
  everything outside those two for the rest of the run and cited the mandate
  text when declining. F15/F53's "full authority is a snapshot" did not recur,
  because the grant was specific.
- `plan_rooms` with a `director_note`, published in one reply: a wine cellar
  under the kitchen, a stable yard and a carriage house, each with barriers and
  bearings. Validation clean, no reach warning, and the planned rooms appeared
  in the registry and in `inspect_route`'s reachable set on the next beat.
- **It refused to write a mind, and refused it on the right grounds.** Asked to
  set Felix's belief directly, it answered: *"an author never writes directly
  into a character's head or dictates their beliefs; minds form their own
  conclusions exclusively from circumstances, testimony, and evidence they
  encounter"*, and separately that its mandate covers no such capability, and
  that even with one *"we could only author an encounter or spoken testimony,
  never his interior belief."* That is the design stated back correctly, without
  being asked to explain itself.
- `inspect_minds` gives the author tier as F8's fix intended: drive
  essence/expression/taboo, the authored self-model, values, traits and
  protected beliefs, plus the live ledgers — strain, stress, goal, intentions
  with progress and idle beats, beliefs by credence, and `about_others`. Asked
  what the three minds believe about the ledger, the Room's answer matched the
  ledger row for row. **Is that a leak channel?** No, on the evidence: it is a
  host-only tool (`web/world_routes.py` and `story/room_tools.py` are both
  host-only by construction), the Planner is not a mind, and nothing it read
  reached a character payload — I checked the three minds' memory and belief
  rows after each session and none moved. It is author knowledge, correctly
  labelled as such in the tool description.
- A five-line recap of what had actually happened, accurate to the beat.

**What it could not do.**

- **It cannot author geometry** (F47 recurs, unchanged): I asked for extents and
  shapes in paces, twice and explicitly. The measurements came back as PROSE
  inside `purpose` — "Round-vaulted brick chamber four paces by four paces under
  the kitchen floor" — because `plan_rooms` has no `extent`/`shape`/`parts`
  field. The reply then reported the sizes back to me as though they had been
  set, and one of them silently changed on the way (I asked for a stable yard
  "roughly ten by six"; the reply says fourteen by twelve).
- It cannot retire what it published: I asked it to retire the package, it
  resolved it instead (`retire_package` is host-only) and did not say that was
  why.
- It would not propose a complication without a `surprise` mandate: *"room
  policy requires an active mandate holding the surprise dial before briefing
  the Dramaturge."* A PROPOSAL is not an act, and refusing to think aloud until
  granted a capability makes the room less useful than a notepad on exactly the
  question a co-author is for. (When I asked the same question with no package
  attached in the third session, it answered at length and well.)
- Room calls are still not captured (`export_bench`'s documented gap), so a
  session's payloads cannot be read the way a beat's can.

**Where it overstepped, or came close.**

- PC10: it invented a mechanism and a cause for a tool result it had not
  verified.
- Third session, unprompted: *"standing out on the terrace put him directly
  alongside the glazed gallery door — meaning Felix may have seen Lord Edmund
  carrying the ledger to the tower room."* That is a perception Felix never had,
  derived from reading his card. It did not write it anywhere, so nothing landed
  — but it is one step from a `director_note` asserting a fact the card denies,
  which is exactly F8's failure mode. The line between "what this mind holds"
  and "what this mind might have seen" is the line the room has to hold, and the
  tool that hands it minds should say so in its own description.

**What I would improve, in order.** (1) `plan_rooms` gains `extent`, `shape`,
`parts` — the Room is asked for rooms and cannot say how big they are, and the
Director does not write extents either (F45), so nothing in the engine does.
(2) Let the room THINK without a mandate: separate proposing from acting, since
every write already goes through a package that checks the grant anyway.
(3) `inspect_route` should name the blocking edge (PC10). (4) Capture Room
calls.

> **Answered 2026-09-05**, items 1 and 4, and half of 2. (1) `plan_rooms`
> takes `extent`, `shape` and `exposure` and an edge takes `vertical`; the
> preview now shows what the plan MEASURED, which is the check this run
> wanted -- a stable yard asked for at ten by six and reported back as
> fourteen by twelve would show its extent or show none. `parts` is
> deliberately not offered, and `world/structure.py` still drops the
> room-level three between plan and scene. (4) the Room's model calls record
> through `story/room_calls.room_call` into `llm_capture`, once
> `agents/story_planner._call` routes through it. (2) is answered where a
> proposal meets an assertion rather than where it meets a mandate:
> `story/room_citations.py` marks the difference, so a room may say what it
> is only suggesting without borrowing the world's authority for it -- the
> mandate question itself is untouched.


## 6. Prompt and payload proposals, per stage

Read from the capture (`read_trace`, 249 calls, 220 capture rows).

- **`director_establish`** (1 call, 26.4 s, 20.3k system + 10.4k payload). It
  minted twelve rooms with barriers, verticals, names and distances from prose,
  and zero measurements — F45 exactly. The source-class clause yields the level
  word and never the geometry: the scenario said "fourteen paces east-west by
  eight north-south" and "a round stone room" and got `size: large` and no
  `shape`. **Proposal:** the rooms clause should say that a room's SIZE is a
  word and its EXTENT is a measurement, and that a measurement in the material
  is written as `extent`; that a room which is not one rectangle is `shape` plus
  `parts`; and that a thing which gives light or sound carries the source field
  at the level it emits with the switch as `state.lit`/`state.running`. State
  the class; name no lamp.
- **`director_interpret`** (79 calls, 6.9 s and 34.5k chars mean). The main call
  carries `world_books`, `standing_intentions`, `due_authored_events`,
  `paradox`, `other_players` on every beat of a four-person parlour scene; the
  five specialists receive `worn_garments` and `scales` for a beat that opens a
  door. The interpret got the player's intent right on 19 of 20 beats, so this
  is cost, not error. **Proposal:** the specialists' payloads should be scoped
  to their own channels' subjects — the contact hand needs the garments of the
  bodies in the beat, not the cast's.
- **`director_resolve`** (76 calls, 913 s — 40% of the run's wall clock, 51k
  chars sent per call against a 41k system prompt). Measured over the 22 main
  calls: `scene` is 15.3k chars mean, and **sixteen payload keys arrived empty
  on every single call** (`paradox`, `active_awareness`, `active_restraints`,
  `travel_in_flight`, `other_players_declarations`, `character_material_effects`,
  `dice_results_final`, `standing_intentions`, `crowds`, `couriers`, `notices`,
  `carried_reports`, `due_authored_events`, `unratified_claims`,
  `background_presence_knowledge`, `character_contact_endings` 21/22). They cost
  almost nothing in bytes — 2 chars each — so the proposal is NOT about size: it
  is that a payload where two-thirds of the keys are always empty teaches the
  model that the payload is furniture. **Proposal:** omit a key with nothing in
  it (the establish payload already does this for `planned_rooms` and
  `author_notes`), so that a key's PRESENCE means something happened on that
  channel. The real size lever here is the 41k system prompt, not the payload.
- **`interaction_loop` / `character_mid`** (39 calls, 86.6k chars mean — the
  largest payload in the run). `character … no delivered present observation was
  cited` fired **44 times** across the run, on all three characters. The most
  expensive payload's central section is the one the model most often fails to
  cite. **Proposal worth measuring before building:** the `perception` block
  arrives as one long composed view; the citation the floor asks for is by
  `observation_id`. Deliver the view AND the numbered observations as the same
  list the floor checks against, so citing is picking a number rather than
  matching prose. *(The 44 warnings were the guard, not the minds: it read a
  retired wire lane while the citations sat in `appraisal.present_evidence`.
  Closed 2026-09-05 — flat run PE20. The payload proposal above stands on its
  own merits and is unaffected.)*
- **`narrator`** (20 calls, 11.9 s, 53.6k mean sent of which 38.2k is a constant
  system prompt). Two of the run's biggest warning classes are its quoting
  (PC11) and `narration: echoed the player's own line` ×10 — the latter fired on
  beats where the player's line was genuinely part of the exchange being
  rendered. **Proposal:** the prompt already forbids re-narrating the player's
  declaration; the guard should distinguish re-narrating it from a character
  answering it, or the warning is noise on a third of all beats.
- **Perception** (deterministic, no call). PC1 and PC3 are both perception
  findings and both are about a GRADE being spent as a boolean or computed
  twice. Neither needs a prompt change.


## 7. Measurements

Wall clock, 20 beats: **2,285 s** total, mean 114 s, median 116 s, range 48 s
(the opening) to 182 s. 249 model calls, 8–16 per normal beat.

| stage | calls | seconds | mean s/call | chars sent | mean sent |
|---|---|---|---|---|---|
| `director_resolve` (main + specialists) | 76 | 913 | 12.0 | 3,873,094 | 50,961 |
| `director_interpret` (main + specialists) | 79 | 546 | 6.9 | 2,725,838 | 34,504 |
| `interaction_loop` (`character_mid`) | 39 | 494 | 12.7 | 3,377,881 | 86,612 |
| `narrator` | 20 | 238 | 11.9 | 1,072,998 | 53,649 |
| `reaction_loop` | 5 | 56 | 11.2 | 467,179 | 93,435 |
| `director_establish` | 1 | 26 | 26.4 | 30,707 | 30,707 |

Specialist fan-out actually used across the run: `spatial` on 18 beats,
`contact` on 11, `objects` on 7, `body` on 2, `social` on 1 — the spatial hand
is the one that runs almost every beat, and it is also the one receiving the
largest payload (`rooms` at 17.9k chars on turn 1).

Warnings: **163** across 20 beats — narrator 57, interaction_loop 55,
director_resolve 19, commit 17, reaction_loop 10, director_interpret 3,
perception_outcome 2. The four largest classes are `no delivered present
observation was cited` (44), the two quote guards (35), `narration: echoed the
player's own line` (10) and `World pressure stalled` (6).

Capture: 220 `llm_capture` rows, one `trace_<turn>.json` per beat (12 files kept
in the job scratch dir; none committed). No F1-class retry on any call; the only
retries in the run were three attempts inside one Writers' Room reply
(153 s total), which succeeded.

Backdrop and ambience were off by harness policy, so the backdrop brief was not
exercised. **Japanese: not run** — the budget went to the firewall and geometry
tests, so this run says nothing about the ja pack.
