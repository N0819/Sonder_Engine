# The light field: light as a quantity on the sight grid

Status: DESIGN, not built. Agreed with the owner 2026-09-04 as the item
after the Writers' Room waves and regions (see `docs/UNBUILT.md` § 2.34).
Every number in § 6 is a proposed constant, not a measurement; the
measurements this note asks for are listed in § 9 and none has been taken.

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

Computed once per (scene, observer) alongside `observer_field`, over the
same composite grid (own room plus sight-neighbours beyond their doorways),
cached with it for the turn. Steps, each a small pure function:

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
   today. This is the one place the room-level word survives, and it is a
   FLOOR, never a source: it casts nothing, shadows nothing, and does not
   spill. (A daylit room's floor is `lit`; the doorway spill into the
   cellar comes from the sources and bounce below, not from the floor.
   § 9 asks whether the floor should spill and by how much.)

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
  * The composer's darkness sentences, the Director's dark-room check
    (`agents/director.py`, "any room not lit") and `spatial_routing`'s
    light gates all read through these three and change nothing.
  * The Narrator and the Director payload get, per room in view, the
    field's SHAPE in the composer's words -- "the lamp lights the table and
    the near wall; the far end of the room is dark" -- from the same
    per-anchor cell mapping `neighbour_feature_visibility` uses. Prose,
    from geometry, never a number.

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

## 6. Constants the owner sets

Named here so none is buried; each is a module constant with this table
beside it. The values are STARTING POINTS chosen so that a `lit` source in
a `medium` (6-cell) room reads `lit` to about two cells, `dim` to about
four, and reaches the far wall as `dark`, and so that a `bright` fixture at
`full` height fills a medium room to `lit` once bounce is applied.

    POWER          dark 0 | dim 2 | lit 6 | bright 18   ladder units at d=0
    DIM_T / LIT_T / BRIGHT_T   0.5 / 2.0 / 8.0          quantisation
    DARK_THRESHOLD  = DIM_T                              reach and bounce stop
    CONE_HALF_ANGLE 30 deg     CONE_PENUMBRA 20 deg
    BOUNCE          enclosed 0.25 | sheltered 0.12 | open 0.05
    BOUNCE_REACH    3 cells    BOUNCE_PASSES_CAP 4
    GLARE_POWER     = POWER[lit]   GLARE_CELLS 2
    FLICKER_RATE    1 beat in 4    FAIL_RATE 1 beat in 12

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
