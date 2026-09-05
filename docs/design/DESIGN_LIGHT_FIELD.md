# The light field: light as a quantity on the sight grid

Status: PROTOTYPE, on a branch. Built 2026-09-04 in an isolated worktree
from this note, §§ 3-8, as `world/spatial_light_field.py` behind the
`world/spatial.py` facade, with `tests/test_light_field.py` (36 tests) and
the measurements of § 9.1-9.4 taken read-only on a copy of the owner's
database (chat 111 excluded). Nothing here is merged. Headline numbers:

    corpus (104 scenes, 589 rooms, 823 entities)
      entities carrying light_source             2   (one dim, one lit)
      of those portable / stationed / held       0 / 0 / 0
      rooms with a size tier or anchors        321 / 589   (the field exists)
      rooms with an authored geometry field      2 / 589
      rooms holding a source                     2, both with size/anchors,
                                                    neither with a height
    before/after over scenes carrying geometry (81 scenes, 321 rooms)
      effective_light changed                    3 rooms (dim->dark 2,
                                                          lit->dim 1)
      light_at over 171 positioned bodies        0 changed (81 hold a cell)
      sight_level over 312 body pairs            0 changed
    pin: 7 no-geometry scenes compose byte-identically with the field's
    readers on and off (`test_a_scene_without_geometry_composes_byte_
    identically`)

One constant moved from the § 6 proposal: LIT_T 2.0 -> 2.5, because 2.0 was
exactly POWER[dim] and the ambient floor of every `dim` room with a grid
quantised back to `lit` on the pin's first run. The § 6 table below keeps
the proposal and § 9.3 records the consequence. Three assertions in
`tests/test_light_and_survival.py` that encoded the room-level model on a
scene which carries geometry now pin both contracts (§ 9.4). The § 9.5 live
beats were not played.

**Extended 2026-09-04 at the merge with the sound field**, under the
owner's ruling of the same day, each item pinned: ONE grid derivation for
every sense (`spatial_fov.room_field` takes a placement predicate;
`light_passes` places every barrier sight crosses, glass included -- § 4,
§ 4a); the ambient floor SPILLS through apertures (`FLOOR_SPILL` 0.25,
§ 4.6, the note's open question 1 answered yes); the composer says WHERE the
light falls (`light_shape`, § 4b, `tests/test_field_sentences.py`); a body
with no station reads the room's MEDIAN, not the room-level model (§ 4b);
glare counts an all-round lantern (§ 4b, decided); and the commit's
failed-source block is shared with the sound field (§ 5). The corpus was
re-measured (§ 9.6): the room, body and pair distributions are unchanged
from § 9.4, chats 73 and 74's back office reads `dim` in the three cells at
its doorway, and the light sentence would speak in 3 of 321 live rooms.

The ask, in the owner's words across one conversation: make lighting
realistic; allow a held conical flashlight and all-round lights like a
lantern, a torch or a phone, WITHOUT a vocabulary of devices ("a lighting
category for the specialist, not a list"); decay light realistically by
raycasting; include bounce ("per turn and on a grid, not too expensive");
have the Director mint light sources; handle ceiling lights, and ceilings
and floors generally, cheaply -- where cheap does not mean low quality; and
let a light be minted unreliable, flickering or failing.

---

## 1. What exists, and where it stops

`world/spatial_light.py` is a ROOM-level model with one per-body
refinement. A room has a light on the four-step ladder `LIGHT_LEVELS =
dark | dim | lit | bright`; outdoors the sky sets it from `day_phase`
(`day_cycle.sun_light`) and a declared `light` may only darken it; an entity
with `light_source` lights the room it stands in (`source_light`), filling
it when `light_radius` is `room` and making a pool when `spot` (portable
things default to a pool); `light_at(scene, body)` lifts a body to the
source's level when it holds the source or stands `within_reach`/`near` of
it, and to `dim` when it is merely in the same room; `effective_light`
lifts a dark room to `dim` when an open sight barrier faces a lit
neighbour. `_LIGHT_SIGHT` turns the ladder into `SIGHT_LEVELS = none |
shapes | full`, and `spatial_senses.sight_level` reads the TARGET's light.

That model is right about the four things it decides and silent about
everything geometry would decide:

  * a source has no DIRECTION -- a flashlight lights the room around its
    holder exactly as a lantern does;
  * a source has no DISTANCE beyond `near` -- three paces and ten paces are
    the same `dim`, and a bright lamp and a candle differ only in the word;
  * a source casts no SHADOW -- a body behind the counter is as lit as the
    body in front of it, though the FOV layer knows the counter is there;
  * spill is one step and one hop -- a lit kitchen makes the cellar `dim`
    whatever the doorway's width, wherever in the cellar you stand.

`world/spatial_fov.py` already has every geometric input the missing
answers need: a per-room grid (`GRID_SIDE`, 3-12 cells a side), anchors as
occluders with a HEIGHT rank (`_HEIGHT_RANK` floor 0 / waist 1 / head 2 /
full 3), body cells from stations, eye height from posture (`_EYE_RANK`),
a facing (`effective_facing`), recursive `shadowcast`, and since
`3fd93680` the wall between two placed rooms as a LINE with the doorway as
a gap (`_Field.walls`, `_wall_verdict`). Light is sight run backwards: the
same rays, from the lamp instead of the eye.

## 2. The rule in one sentence

Light is a scalar on every cell of the observer's field, summed from every
source whose rays reach the cell, decayed by distance, shaped by the
source's cone, shadowed by anything at or above the source's height, filled
in by bounce, floored by the room's ambient, and QUANTISED TO THE LADDER
LAST -- so every reader that exists today (`light_at`, `effective_light`,
`sight_level`, the composer, the Director's dark-room check) keeps its
four words and gets them from geometry instead of from the room.

## 3. Schema: a source is a class, not a device

On an entity, beside the existing `light_source` (the level it EMITS, kept
as the ladder word because that is what the Director already writes):

    light_shape   all_round | cone     how the emission is distributed;
                                       absent = all_round
    light_height  floor | waist | head | full
                                       where the source sits; absent = the
                                       holder's eye rank when held, `head`
                                       when standing free, `full` when the
                                       entity is a fixture of the room
                                       (not portable)
    steadiness    steady | flickering | failing
                                       absent = steady

And two fields under the entity's free `state`, both already the kind of
thing a Director writes there:

    state.lit          true | false      exists today; a doused source stops
                                         lighting without ceasing to exist
    state.pointed_at   <entity or anchor id> | <bearing> | null
                                         a cone's axis; absent = the holder's
                                         facing; a cone with neither is
                                         all_round (fail-open to the wider
                                         answer)

Four closed sets the engine OWNS and reads: `LIGHT_LEVELS` (existing),
`LIGHT_SHAPES`, the height vocabulary shared with anchors (`HEIGHTS`), and
`STEADINESS`. That is a schema in CLAUDE.md's sense, not a vocabulary
table: nothing here names a lantern, a torch, a phone, a rune or a spell.
The prompt clause for the objects hand states the CLASS: "a thing that
emits light carries `light_source` at the level it emits, `light_shape`
cone when its light has a direction and all_round when it has none, and
`light_height` for where it sits; what the thing IS lives in its name and
description, as it does for every other entity." The one distinction the
model must draw -- has the light a direction -- is one a model draws
without a list. `light_radius` (room | spot) stays readable for the
no-geometry path (§ 7) and becomes derived where geometry exists: a source
with power to fill the room fills it, and a spot is what a weak or coned
source looks like on the grid.

## 4. The field

Computed once per (scene, room) over the composite grid `room_field`
derives -- the own room plus every neighbour placed beyond its aperture --
and cached for the turn. ONE derivation serves three senses (2026-09-04):
`room_field(scene, room, through=...)` takes a placement PREDICATE, and the
three are `sight_passes` (what a body walks into: open, open_door -- the
rule `observer_field` always had, byte-identical on every scene shape,
`tests/test_one_grid_two_senses.py`), `light_passes` (every barrier sight
crosses, glass and grilles included: a lamp behind a window lights this
room, and so does the lit room's floor through it) and the sound field's
`sound_passes` (whatever is not a wall, at the aperture's drop). Each wall
record carries the predicate's `pass` beside its five keys. Steps, each a
small pure function:

1. **Power.** Each active source (`state.lit` not false, this beat not a
   flicker-out, § 5) has power `P = POWER[light_source]`. Power is in
   "ladder units at one cell": a source of power P lights the cell it
   stands in to intensity P.

2. **Reach.** From the source's cell, `shadowcast` over the composite
   field with `blocked(cell)` = the cell's occluder rank is >= the source's
   height rank, or the cell is outside the field, or the ray crosses a
   wall line outside its aperture (`_wall_verdict`, § 4a). A ceiling light
   (`full`) is blocked by nothing but walls, so it casts no shadow and
   needs no ceiling geometry; a candle on the floor is shadowed by a
   waist-high counter; a lantern held by a standing body is shadowed by
   head-high things only. The radius is `ceil(sqrt(P / DARK_THRESHOLD))`,
   the distance at which the source alone would fall below dark -- past
   it the source contributes nothing, so nothing is cast.

3. **Decay.** For each reached cell at Euclidean distance d (cells),
   `I = P / (1 + d^2)`. The `1 +` keeps the source's own cell finite and
   equal to P. Inverse square is what the owner asked for and it is also
   the reason a candle lights a table and not a hall.

4. **Shape.** A cone multiplies I by an angular term: 1 inside
   `CONE_HALF_ANGLE` of the axis, falling linearly to 0 over
   `CONE_PENUMBRA` degrees beyond it. The axis is `state.pointed_at`
   resolved to a bearing (an entity or anchor id resolves through its cell;
   a bearing word through `_BEARING_DEG`), else the holder's
   `effective_facing`, else the source is all_round for this beat. Bearings
   are the eight compass points the engine already uses, so the axis is
   quantised to 45 degrees; the penumbra hides that quantisation, which is
   the reason it exists as a constant rather than a nicety.

5. **Sum.** Cells sum their contributions. Two candles are brighter than
   one, which the max-of-levels model could never say.

6. **Ambient floor.** Every cell of a room is lifted to at least
   `POWER[room_light(scene, room)]` -- the sky through `sun_light`
   outdoors, the declared `light` indoors, exactly as `room_light` answers
   today. This is the one place the room-level word survives, and within
   its own room it is a FLOOR, never a source: it casts nothing and shadows
   nothing there.

   **6a. The floor spills through doorways** (the owner agreed, 2026-09-04;
   this note's open question 1). Each aperture cell of every wall between
   two placed rooms emits the GIVING room's floor into the TAKING room at
   height `full`, power `FLOOR_SPILL * POWER[floor word] * pass`,
   inverse-square from the aperture cell, summed over the aperture's cells
   (a wide door spills more) and with everything else, quantised last.
   Through whatever passes light -- an open doorway, a window -- never
   through a wall or a closed door; onto the taking room's cells only (the
   giver already has its floor). `FLOOR_SPILL` = 0.25, the largest value at
   which a `bright` floor's spill still reads `dim` at the door (0.33 makes
   it `lit`; the room-level rule this replaces never lifted borrowed light
   past dim); a `lit` neighbour makes a dark medium room `dim` at the door
   cell and the two beside the frame, `dark` two paces in and in the far
   corner, its median still dark. `FLOOR_SPILL = 0` reproduces the field as
   first built. The table is beside the constant in the module.

7. **Bounce.** Indirect fill, iterated: on each pass every cell with
   intensity I above `DARK_THRESHOLD` re-emits `BOUNCE[exposure] * I`
   all-round to its shadowcast neighbours within `BOUNCE_REACH` cells at
   inverse-square decay; passes repeat until the largest added intensity
   falls below `DARK_THRESHOLD` or `BOUNCE_PASSES_CAP` is hit. The room's
   `exposure` is the whole of its ceiling and floor: `enclosed` bounces
   most (walls, ceiling and floor all return light), `sheltered` less (a
   roof, no walls), `open` least (the ground alone). This is what makes a
   lit kitchen glow into the cellar past the beam and a bright room fill
   its own corners behind the furniture. Bounce is computed on the SUMMED
   direct field, once, not per source.

8. **Quantise.** `level(cell) = bright if I >= BRIGHT_T else lit if I >=
   LIT_T else dim if I >= DIM_T else dark`. Three thresholds, named. Every
   reader below this line sees four words.

### 4a. Spill is the wall as a line

`effective_light`'s one-step spill becomes a consequence rather than a
rule: a source in the kitchen casts into the cellar's cells through the
doorway's aperture and nowhere else, decaying with distance, so the cellar
floor just inside the door is `dim` or `lit` and its far corner is `dark`,
and a body standing beside the doorframe on the kitchen side of the cellar
wall is in the dark, as it is in life. The composite field already places
the neighbour's grid on the far side of the wall line (`observer_field`);
the same `_wall_verdict` that judges a sight line judges a light ray. The
cell-model ceiling "spill lifts dark to dim and never further" is replaced
by decay, which is why it can be dropped without a special case.

### 4b. Readers

  * `light_at(scene, body)` -> the quantised level of the body's cell in
    its own field (the body's room is always the own room of its field).
    A body with NO cell reads the room's median (2026-09-04): it is
    somewhere in the room, and the room's typical light is the one
    statistic the field already answers for 'somewhere'. It used to keep
    the room-level answer, so one room had two -- chat 115's corridor read
    `dim` as a room and `lit` for every unstationed body in it.
  * `effective_light(scene, room)` -> the level of the room's MEDIAN cell
    intensity, so a room reads as its typical light, not its brightest
    corner or its darkest; callers that gate on "is this room dark" keep
    working and stop being fooled by one candle. (§ 9 asks whether median
    is the right statistic; a mean is the alternative.)
  * `sight_level(rel)` keeps reading the TARGET's light -- a body in the
    dark sees a lit body across the room, and is not seen back -- with one
    addition: **glare**. A source of power >= `GLARE_POWER` inside the
    observer's front cone at <= `GLARE_CELLS` cells, with the target on the
    far side of it (the source's cell lies on the target's line), caps
    sight at `shapes`. The flashlight in your face is the whole reason a
    cone exists in fiction, and it is one line once the field is there.
    An all-round lantern held up between two faces counts too (decided
    2026-09-04): glare is about power in the eyes, not the source's shape;
    the cone only decides whether the power reaches the eye at all.
  * The composer's darkness sentences, the Director's dark-room check
    (`agents/director.py`, "any room not lit") and `spatial_routing`'s
    light gates all read through these three and change nothing.
  * **Where the light falls** (built 2026-09-04: `light_shape`, rendered by
    `composer.render_light_shape` and the Japanese adapter from templates
    over the four words; `tests/test_field_sentences.py`). Five rules, the
    owner's, shared word for word with the sound field: (a) speak only when
    the room is UNEVEN -- every cell one word and the flat `light_dim` /
    `light_dark` sentence stands, byte-identically; (b) grade by ANCHOR,
    not by cell -- the visible anchors (`feature_visibility`, cone and line
    already subtracted) grouped by the word at each anchor's nearest cell,
    the mapping `neighbour_feature_visibility` uses, bright to dark, as
    templates over the closed set, never free text, no number, cell or
    sector reaching prose; (c) name the source when it is IN VIEW, else the
    opening its light comes through when that opening is in view ("the
    light from the open doorway"), never a source the observer cannot see;
    (d) say where the observer stands in it -- with a cell; no cell, no
    claim; (e) subtract, never add -- `observations_from_render` re-derives
    the same sentence and an observer receives only their own view's. When
    the shape is present it REPLACES the flat sentence, which spoke for the
    whole room. The same sentences reach the Director's sight digest
    (`payload.sightlines.light[name]`, through
    `composer.field_shape_sentence`). "The light from the lamp falls on the
    table, thins to half-light at the shelf, and leaves the hearth in the
    dark. You stand in half-light."

## 5. Steadiness

A `flickering` source drops one level on beats chosen by a hash of
(turn index, source id) against `FLICKER_RATE`; a `failing` source goes out
by the same hash against `FAIL_RATE`, and when it does the engine files a
NOTICE the Director reads next beat ("the lamp in the corridor has gone
out") so the world can answer it -- the Director may relight it, replace
it, or leave the corridor dark. The hash, not a random draw, so a REROLL
of the beat sees the same light as the beat it replaces (the same reason
anchor placement is seeded on (room, anchor)). Nothing about a device:
`failing` is true of a guttering candle, a dying torch battery and a spell
running out alike.

The commit's failed-source block is ONE block for both fields
(`persist/commit_scene_state._record_failed_sources`, 2026-09-04): it reads
`failing_sources_out` and the sound field's `failing_sound_sources_out` --
the same hash -- writes every switch the thing carries (`state.lit`,
`state.running`), and files one notice per THING: a lamp "has gone out", a
generator "has stopped", a thing that both lights and hums "has failed",
once. Perception no longer files the sound notice itself.

## 6. Constants the owner sets

Named here so none is buried; each is a module constant with this table
beside it. The values are STARTING POINTS chosen so that a `lit` source in
a `medium` (6-cell) room reads `lit` to about two cells, `dim` to about
four, and reaches the far wall as `dark`, and so that a `bright` fixture at
`full` height fills a medium room to `lit` once bounce is applied.

    POWER          dark 0 | dim 2 | lit 6 | bright 18   ladder units at d=0
    DIM_T / LIT_T / BRIGHT_T   0.5 / 2.0 / 8.0          quantisation
                   (built at 0.5 / 2.5 / 8.0: the thresholds must lie
                    strictly between the powers or a word's own floor
                    renames it -- § 9.3)
    DARK_THRESHOLD  = DIM_T                              reach and bounce stop
    CONE_HALF_ANGLE 30 deg     CONE_PENUMBRA 20 deg
    BOUNCE          enclosed 0.25 | sheltered 0.12 | open 0.05
    BOUNCE_REACH    3 cells    BOUNCE_PASSES_CAP 4
    GLARE_POWER     = POWER[lit]   GLARE_CELLS 2
    FLICKER_RATE    1 beat in 4    FAIL_RATE 1 beat in 12
    FLOOR_SPILL     0.25   (added 2026-09-04, § 4.6a; 0 = no spill)

The cap on bounce passes is a SAFETY ceiling, expected never to bind: with
BOUNCE <= 0.25 and inverse-square decay the second pass already adds under
a tenth of the first.

## 7. Cost, and fail-open

A composite field is at most one `vast` room plus its placed neighbours,
under 600 cells; a scene rarely has more than a handful of sources.
Direct light is one shadowcast per source (the same routine sight runs
once per observer); bounce is BOUNCE_PASSES_CAP sweeps over the cells above
threshold, each a small shadowcast of radius BOUNCE_REACH. This is
microseconds against a turn that is seconds of model time, and it is
computed once per (scene, observer) and cached with the field. Nothing
here calls a model.

Where the scene carries no geometry -- a room without a size tier or
anchors, a body without a station, an old story -- the field does not
exist and every reader falls back to the current room-level functions
unchanged, so an existing scene composes byte-identically. This is the
same fail-open `observer_field` already has, and it is pinned the same
way (§ 9).

## 8. Ownership

  * The **objects** hand mints and changes sources: `light_source`,
    `light_shape`, `light_height`, `steadiness`, `state.lit`,
    `state.pointed_at` when a thing is set down aimed at something. One
    clause, stating the class (§ 3).
  * The **body** hand owns where a held source points when it follows the
    holder: it already owns `facing`; a held cone points where its holder
    faces unless `state.pointed_at` says otherwise.
  * **Perception** computes the field and reads it. No model role, no new
    stage: `light_at`/`effective_light`/`sight_level` are the seam, as they
    are now.
  * The **Narrator** renders the shape the composer hands it and cannot
    light or darken anything.
  * The **Writers' Room** may plant a source through the existing
    `new_artifact`/entity operations like any other entity; light is not
    an operation of its own.

## 9. To measure before and while building

  1. Corpus: how many entities carry `light_source` today, how many are
     portable (so would default to `spot`), how many rooms carrying sources
     also carry geometry (so the field would exist at all). Read-only on a
     copy of the owner's db.
  2. Pin: every scene without geometry composes byte-identically with the
     field code present (the `observer_field` fail-open test, extended).
  3. Synthetic: one `lit` all_round source in a medium room -- the level at
     each ring; a `lit` cone -- cells inside the cone versus beside it; a
     candle behind a waist-high counter with a standing body -- the shadow;
     the same with a `full`-height fixture -- no shadow; a lit kitchen and a
     dark cellar joined by a one-pace door -- the wedge of light on the
     cellar floor, and dark beside the doorframe; bounce on versus off in an
     enclosed room -- the corners.
  4. Corpus, before/after: the distribution of `light_at` answers over every
     positioned body in scenes carrying geometry, and every body whose
     `sight_level` to another changes, read one by one for the first twenty.
  5. Live: two beats with a held cone in chat 114 or a fresh non-explicit
     scenario (Gemini on a copy), reading every stage's output, per the
     standing grant in the queue.

Open questions for the owner, in the order they bite: whether the ambient
floor should spill through doorways at all (§ 4.6); median or mean for a
room's reading (§ 4b); and the starting constants themselves (§ 6), which
the owner may want to set after seeing the synthetic table in § 9.3 rather
than before.

### 9.1 Corpus (2026-09-04, read-only on a copy, chat 111 excluded)

    scenes / rooms / entities                    104 / 589 / 823
    entities carrying light_source                 2   (dim 1, lit 1;
                                                        light_radius unset on both)
    of those: portable / with a station / held     0 / 0 / 0
    with state.lit off                             0
    rooms with a size tier or anchors            321 / 589   (the field's gate)
    rooms with an authored footprint/height/
      opacity on an anchor                         2 / 589
    rooms holding a source                         2; both carry size/anchors,
                                                   neither an authored height

So the field exists for 55% of live rooms and bites, today, on ambient and
on spill; the two sources are one `dim` and one `lit` fixture with no
station, placed at their room's centre.

### 9.2 Pin

`test_a_scene_without_geometry_composes_byte_identically`: seven scenes
drawn from the existing light fixtures (two rooms, no size, no anchors;
lit/lit, dark/lit, lit/dark, dim/dim, dark/bright through a closed door,
dark/lit through a window, and a held torch in two dark rooms) are composed
-- `light_at` for every body, `effective_light` for every room,
`spatial_rel_between`, `sight_level` and `visual_level_between` for every
pair, `presence_percepts` and `environment_percept` for every observer --
once with the field's three readers live and once with them replaced by
"no field", and the two JSON strings are equal. A geometry room with no
source reads its own light for all four words
(`test_a_room_with_geometry_and_no_source_reads_its_own_light`).

### 9.3 Synthetic (constants as built: LIT_T 2.5, the rest as § 6)

One all_round source standing free at the centre of a medium (6-cell),
enclosed, dark room, head height. Intensity then level, direct / with
bounce, along the north ray:

    source   d=0            d=1            d=2            d=3            corner (4.2)
    dim      2.00/2.13 dim  1.00/1.12 dim  0.40/0.48 dark 0.00/0.03 dark 0.00 dark
    lit      6.00/6.60 lit  3.00/3.56 lit  1.20/1.60 dim  0.60/0.81 dim  0.32/0.37 dark
    bright  18.0/20.1 brt   9.00/11.0 brt  3.60/5.03 lit  1.80/2.64 lit  0.95/1.28 dim
    room median (with bounce): dim -> 0.40 dark; lit -> 1.34 dim; bright -> 4.25 lit

Against the § 6 intention ("a lit source ... lit to about two cells, dim
to about four, and reaches the far wall as dark"): lit reaches ONE cell as
lit and three as dim, the far wall of a medium room as dim and only the
corners as dark. The constants that would meet the sentence are LIT_T
<= 1.2 or POWER[lit] >= 12; that is the owner's call, and the reason the
table exists. A `bright` fixture at `full` height DOES fill a medium
enclosed room to `lit` once bounce is applied (no cell darker than dim;
the edge cell at d=3 goes 1.80 dim -> 2.64 lit), which is the other half
of the § 6 sentence and holds.

Bounce, as built: a cell re-emits BOUNCE[exposure] of its intensity IN
TOTAL, shared among the cells it reaches within BOUNCE_REACH in proportion
to 1/(1+d^2). Read as "that much to each cell" the first prototype returned
about six times the light that fell (the weights over a 3-cell disc sum to
about 6) and a single lit lamp made a medium room bright to its corners.
Shared, bounce adds 43.5 to a direct total of 140.6 for the bright fixture
(ratio 0.31, i.e. 0.25 + 0.25^2 + ..., the cap never binding), and the
open-air coefficient adds least (`test_an_open_room_bounces_least`).

A lit CONE at the centre pointed north (half-angle 30, penumbra 20),
direct intensities:

    on the axis (3,1) d=2      1.20     the same as all_round
    diagonal ahead (4,2) 45deg 0.50     the penumbra's ramp: 2.00 x 0.25
    beside (5,3) 90deg         0.00
    behind (3,5)               0.00

A lit candle at a waist-high counter (run, one pace off the north wall),
a standing body H at the same counter on the wall side (`cover`), P on the
room side. The candle stands at (2,2), H at (2,0):

    candle height   H's cell direct / total -> level    cell in front at H's x
    floor           0.00 / 0.28 -> dark                  6.51 lit
    waist           0.00 / 0.28 -> dark                  6.51 lit
    head            1.20 / 1.60 -> dim                   6.60 lit
    full            1.20 / 1.60 -> dim                   6.60 lit

The counter cuts the ray from anything at or below its own height and
nothing above it; the ceiling light casts no shadow and needed no ceiling.
Bounce puts 0.28 behind the counter -- still dark.

A lit kitchen (bright fixture at its centre) and a dark cellar joined by a
one-pace door (both medium; the cellar's own field, kitchen placed north
across the wall line at row -1, aperture x in [3.5, 4.5]; the stove lands at
(3,-4), one cell west of the door's axis):

    cellar cells receiving direct light   (4,0) (4,1) (4,2) (5,0) (5,1) (5,2)
    (3,0) beside the frame, stove's side  ray crosses the wall at 3.25: out
                                          0.00 direct, 0.14 total -> dark
    (4,0) the door cell                   1.00 direct, 1.25 total -> dim
    (5,0) beside the frame, far side      ray crosses at 4.25: through
                                          0.86 direct, 1.00 total -> dim
    cellar median                         dark; effective_light(c) = dark
    without the stove (floors only)       dark  (the room-level rule: dim)

The wedge is exactly the set of cells whose straight ray threads the gap:
a source standing off-axis lights the cell beside the frame on the FAR
side, through the gap at an angle, and never the one on its own side. The
kitchen's `lit` floor spills nothing -- which is open question 1.

### 9.4 Corpus before/after (81 scenes with a geometry room)

    effective_light, 321 rooms   before dark 9 / dim 43 / lit 269
                                 after  dark 11 / dim 42 / lit 268
    changed: 3 rooms
      chat 73 and 74, 'Hotel back office' (small, declared dark, 2 anchors,
        no source): dim -> dark. The open edge onto the lit lobby spilled
        under the room-level rule; the field has no source to cast and the
        floor does not spill. Chat 74's room holds the night clerk.
      chat 115, 'Sublevel Four Shelter Approach' (medium, declared dim,
        enclosed): lit -> dim. Its `lit` source (`elevator_shelter`, no
        station, at the centre) filled the room under `light_radius`
        defaulting to `room`; the median cell of the field is 2.00 -- the
        floor -- so the room reads its own word, dim.
    light_at, 171 positioned bodies in geometry rooms (81 hold a cell)
                                 before dark 6 / dim 19 / lit 146; after identical
    sight_level, 312 body pairs  before full 190 / none 70 / shapes 52; after identical

There were no changed pairs to read one by one: no live body with a cell
stands in a room whose field differs from its floor, because the two live
sources have no station and light a room whose bodies have none either.
The three existing assertions that changed are in
`tests/test_light_and_survival.py::TestLightIsLocalNotRoomWide`: a hall
carrying a size tier and anchors, where `light_radius: room` and the
fixed-source default no longer fill a LARGE room with a `lit` source (a
`bright` one does), and one lit torch reads the hall as `dim` (median)
rather than `dark`. Each now pins the room-level answer on the same hall
without geometry beside the field's answer with it.

### 9.5 Live

Not played. The standing grant covers it; two beats with a held cone in a
fresh non-explicit scenario are the next measurement.

### 9.6 After the merge (2026-09-04; read-only, streamed, chat 111 excluded)

The § 9.4 comparison re-run with three configurations over the same 104
scenes / 589 rooms / 823 entities and the same 321 gated rooms: A the
room-level model alone, B the field as merged at `c3f274ea`, C the field
with the unified grid (glass placed), `FLOOR_SPILL` 0.25 and unstationed
bodies at the median. (The database could not be copied -- 3.9 GB free
against a 3.4 GB file -- so rows were streamed from a `mode=ro` connection
and nothing content-bearing was written.)

    effective_light, 321 rooms   A dark 9 / dim 43 / lit 269
                                 B dark 11 / dim 42 / lit 268
                                 C dark 11 / dim 42 / lit 268   (B -> C: 0 rooms)
    light_at, 106 bodies whose room carries the gate
                                 A = B = C  dark 4 / dim 3 / lit 99
    sight_level, 176 pairs of such bodies
                                 A = B = C  full 142 / none 32 / shapes 2

(§ 9.4 counted 171 bodies and 312 pairs by a wider rule -- every body in a
scene with any gated room; the three configurations agree under either.)
The spill changes no room's MEDIAN: chats 73 and 74's 'Hotel back office'
(small, dark, an open edge onto the lit lobby) now reads `dim` in the three
cells at its doorway and `dark` in its other thirteen, so `effective_light`
stays dark -- "dim by the door", as the owner asked, not dim as a room, which
is what the room-level rule had said. Chat 115's corridor keeps dim, with
its lit fixture's 3x3 pool at the centre. No live body changed: chat 74's
night clerk is unstationed and both models read the room dark for it. Six
light composites now place a glass neighbour sight's does not. The light
sentence would speak in 3 of 321 live rooms (the two back offices and the
corridor) and is handed to 1 live body -- the night clerk, whose sentence
names the opening and grades the two anchors it can see; the sound
sentence to none (2 live rooms carry the sound field's gate and neither is
uneven).
