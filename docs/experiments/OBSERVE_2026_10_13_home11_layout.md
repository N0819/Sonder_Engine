# Observed: Home 11's layout (chat 174), 2026-10-13

The owner asked for a review of Home 11's layout: the shrine the layout tier
laid out at the opening (turn 4626, on the code the owner's server ran after
its restart that afternoon), with its grounds. Read against its own
architect, it is a different house. The brief the tier wrote itself makes 30
spatial claims; the building keeps 11, keeps 4 in part and breaks 15.

Method: read-only, on a backup copy of engine.db (no model calls). The World
Browser was opened on the copy headlessly and screenshotted as the owner sees
it -- the room editor, each storey plan, all rooms -- with every API answer
those views drew from, the scene, the Writers' Room's plan, the tier's run
record and the 18 recorded model calls of the opening. Four lenses -- brief
fidelity, the house as reality, the engine's own rules, the grounds -- and
every finding put to a skeptic told to refute it from the coordinates and the
code. 66 findings, 65 confirmed (several corrected), 1 left as a question;
merged here into 10. Replaying the captured answers through the tier's own
code reproduces every installed rectangle (solver seed 9, after seed 7 left a
stair unlanded and seed 8 was refused), so each finding below is separated
into what the model answered and what code did with it. Spot-checked by hand:
the rooms and doorways of every storey plan, the closet on the genkan's
doorway, the stair halls drawn with no door.

Coordinates are `(x, y, w, d)` in paces on plan `layout:genkan`; y runs
south. "Ground" is storey 0.

## The house

**1. The divider cannot lay the house the architect described, and the tier
takes the first seed that solves.** High; engine (solve), with three model
misses beside it.
- Saw: the washroom stands north of the main hall (asked west), the latrine
  is the north-east corner room opening off the bath (asked as a structure
  behind the west end), the wooden stair rises on the hall's west wall (asked
  east, off the north wall), the genkan is the south-west corner (asked in the
  middle of the south front), the kitchen lies under the hall rather than
  beside it, and the tokonoma -- the place of honour in the middle of the
  north wall -- stands end-on in the north-east corner. The rooms' own text
  still says "the bathing room west of the hall".
- Origin: the relate answer encoded the sides correctly and the bridge kept
  them; the solver turned them (its own warnings: "The Washroom was asked on
  the w side of The Main Hall and stands on the n", and two more). The divider
  emits each zone as one contiguous run (`world/layout_solver.py` `_order`,
  with `_slice` handing the first rooms to the west/north piece), so within a
  piece one zone can never stand on both sides of another -- which is exactly
  a washroom west and a kitchen east of the hall. The random mirror is skipped
  on any storey with a stair hole, and `layout_bridge.solve_for` takes the
  first seed that is unrefused and landed: seed 9 turned six sides, seed 10
  would have turned four and seed 15 three. A division keeping every asked
  side exists among the solver's own candidates and scores better under its
  own scorer.
- Beside it: the relate marked storey 1 `smaller` against its own card ("only
  a storey under the roof"), which insets that storey for eaves and pushed the
  wooden stair off the north wall (with only storey 2 marked, the stair stood
  north in 9 of 9 solves); nothing in the relate schema can say "the middle of
  the front", so the entrance lands wherever the front edge is touched; the
  plan's diagonal bearings and its `access` lines never reach the architect
  (the kitchen's back door was planned south-west toward the path, `_building`
  keeps only n/e/s/w and `sort_payload` sends no `access`, so the brief
  guessed "east"); the brief names the whole building "The Genkan".
- Fix: order each piece from the joins' sides as well as by zone, and offer
  the reversed order at each cut; choose among the solve seeds by score or by
  fewest turned planned sides, not the first acceptable. Keep `smaller` only
  for a storey with no storey above it (deterministic, in `spec_from_answers`:
  the card already says it and the answer ignored it). Give the entrance and
  any outside door an optional place along its wall. Carry a diagonal bearing
  as the two walls it allows and pass `access` into the brief and relate.
  Regression: these captured answers.

**2. Rooms come out 1.5 to 2.8 times the size the lore gives them.** High;
engine (solve) and model (relate), with an owner question.
- Saw: Hinami's "six mats of tatami" is a 12x4 strip (about 17 mats) with all
  its furniture in the west three paces; the twelve-mat hall is 13x5 (about 23
  mats), the six-mat kitchen an 11x3 corridor whose kamado takes two of its
  three paces of depth, the four-and-a-half-mat meditation room 4x5. The
  editor's own lint says Hinami's room is "small" against a "medium" extent.
  The Roost, "smaller under the roofline", is the largest room in the house
  and its storey has Floor 1's outline exactly.
- Origin: the relate gave no `area_m2` although its card asks for any stated
  size. And a stated size would not have held: `room_target` keeps the larger
  of the stated size and furniture/0.35 plus the doors, and size words
  compound `FIXTURE_SIZES` (a "large" futon is 3 m by 2.25 m), so with the
  mats stated the hall still solved anywhere from 10 to 112 cells. The roof
  inset is applied before the clip to the storey below, so it is removed.
- This follows the owner's 2026-10-10 ruling "size from contents" (a stated
  size is aimed at, contents are never squeezed) -- see question A.
- Also: Hinami's room and the hall carry floor `timber` where their lore says
  tatami (the sound tables treat the two alike, so only the record disagrees).

**3. Every staircase looks sealed, and the stair halls below the first floor
swell.** High; engine (install, then solve).
- Saw: no storey plan draws a door from the main hall, the hallway or the
  Roost into any stair hall; Floor 2 draws no door at all; only the cellar's
  stair door is drawn. The cellar's "Stone stairs" is a 10x5 room filling
  half the basement, drawn as treads wall to wall; the ground floor's two
  halls take 25 and 20 cells for 10-cell flights. The doors into a flight sit
  at its middle, not its foot and head, and every enclosed stair gets a closed
  paper door at both ends where the lore names one. The far layer measures the
  shrine as 21 m tall (seven storeys).
- Origin: the opening's establish tagged the doorways into stair halls
  `vertical`/`way` (its card invites it for "a stair"; `planned_room_brief`
  lists each hall as an exit named after the stair and gives no room a
  level), the scene merge keeps the tags (`structure.LAYOUT_EDGE_FIELDS`
  overwrites only dir, offset and cell) and mirrors them; `web/storey_plan.py`
  skips any vertical edge as a door; `landscape.building_of` adds a storey per
  "up" edge. Below the first floor the landing cap does not apply and the
  score never sizes a hall -- registered as §1.210 and in
  DESIGN_LAYOUT_TIER's "Why not clean yet", where sixteen variants were
  measured. Doorways go at the even division of the shared wall, with no
  notion of a flight's foot or head.
- Fix: at merge, an edge between two rooms on one storey is level -- strip
  `vertical` and `way` and do not mirror them (deterministic); carry each
  room's storey in the establish brief. Write the flight's rectangle, foot and
  head on the hall, draw treads only there, and put the lower doorway at the
  foot and the upper at the head. Cap landings on every storey only weighed
  against the sixteen measured variants.

**4. Furniture code placed lands on the genkan's doorway and on other
furniture.** High; engine (install, read-time placement).
- Saw: stepping in from the genkan you walk into a full-height wall closet:
  "Deep wall closets" (4,8,2,2) holds the pace inside the genkan->hall doorway
  at (5,10) and stands on the wooden chests. The bath's wood-fired stove
  stands inside the cedar tub; Hinami's futon lies under her trunk. Both
  residents are drawn inside furniture (Hinami in her trunk, Tamamo on a box
  stack).
- Origin: these are the four fixtures the solver moved (the run's "moved: 4"
  counts fixtures, not rooms). The solve had each clear; a moved fixture is
  written unpinned on the wall it was asked for (deliberate: "capacity goes
  back to the model"), and `spatial_fov._place_anchor` then takes the
  least-crowded slot along that wall -- every slot on the hall's west wall
  touches a doorway, and the least-crowded is the genkan's. A cell is taken at
  one height, so floor-standing things of different heights share cells.
  Separately, the opening's establish described the Roost without the plan's
  fixtures and added a second futon nest and a second box stack, and Tamamo
  was stationed at the copy (§1.205; the cause is that `planned_room_brief`
  never names the laid-out anchors).
- Fix: until the designer settles a moved fixture, keep the solver's clear
  place; never put a code-chosen place on a doorway's step or pace. Hand the
  establish each laid room's anchor ids. Seat a body on a free cell of its
  station. See question B.

**5. The warded door to the seal cavern is a piece of furniture.** High;
engine (sort payload, install).
- Saw: the basement's most important door -- "the warded door to the seal
  cavern" in the brief, the iron-banded door at the far north end in the lore
  -- is a 2x1 waist-high box against the stair hall's wall, beside the real
  stair door, with nothing behind it. It breaks the owner's rule that a door
  is its edge.
- Fix: pass each room's frontier into the sort and let a fixture mark a
  frontier the way it marks a planned room; the bridge holds it as a doorway
  onto a frontier stub, never as floor furniture, and the solve keeps that
  wall free.

**6. The latrine outbuilding is absorbed into the house.** Medium; engine
(the bridge's building grouping, `plan_buildings`, with `_edges_of` dropping
the plan's distance).
- Saw: the plan's "small weathered outbuilding at the shrine's west end",
  reached by a roofed walkway from the washroom's back door, is a 3x5 room in
  the house's north-east corner whose only way in is through the bath. Its far
  look still describes an outbuilding.
- Fix: an enclosed room joined to a building only by non-adjacent links (a
  walkway, "near") becomes its own block standing apart beside the room it
  serves, or a ground outbuilding -- never a member room.

**7. The upper Hallway is a windowless 5x3 landing.** Medium; engine (solve).
- Saw: the lore's narrow corridor running north to south with windows along
  its west wall is a 5x3 box with no outside wall; Hinami's door opens on its
  north side. Its windows were dropped and the run record says nothing was
  left unplaced. No ground-floor room has a window at all (question C).
- Origin: outward pull goes only to rooms joined to outdoors or the entrance,
  and above the ground only toward the front; `_place_windows` drops what it
  cannot place.
- Fix: pull every room that has windows toward an outside wall on every
  storey, weighted like a door out; count dropped windows in the run record.

## The grounds

**8. The grounds do not hold together.** High; engine (solve, install,
establish). This is A6's subject, measured on a fourth story.
- Saw: the well, asked to stand beside the lantern path on its east side,
  sits across the path's foot; the torii is a 2x2 block off the path's line,
  half outside the plot, and the path never reaches it; the kitchen's back
  door opens east onto the garden, 18 to 26 paces from the well its exit
  names; the path cuts the garden's front in two with one doorway between
  them, so three paces east of the path is an 85-pace walk; one-pace strips
  (behind the camphor tree, at the path's foot) belong to no place; and the
  opening's guessed distances replace the plan's on every ground edge (the
  torii reads "60 paces", a far edge, from a path two paces off).
- Origin: `by: <way>` is read as "at its far end" and the side is dropped;
  a way that gives up ground leaves its `rows` stale; the kitchen's south-west
  bearing never reached the brief (item 1); open grounds meet at one doorway;
  the room vocabulary invites a distance on every outdoor edge and the merge
  keeps it; and the grounds' own lore never reaches the tier
  (`building_description` matches lore only against the building's rooms).
- A6: its floor alone would refuse this site and lose the grounds; its
  generator rules (G3a/G3c) lay the well and the back door right (measured on
  the A6 design tree). Land the `by: <way>` and stale-rows fixes with it, and
  add reach to the floor (joined places must not be far apart on foot across
  a shared edge).

## The record and the drawing

**9. The tier's record hides what the solve gave up.** Medium; engine
(install).
- "moved: 4" counts fixtures; the turned doorway sides (filed per room,
  never surfaced), the turned stair walls, the dropped windows and the
  tokonoma's move are in no run record, and the solver's warnings are built
  and thrown away. The model that describes a room is never told a side
  turned, so the lore keeps the plan's bearings.
- Fix: file the warnings and turned sides in the run entry; pass turned sides
  into the describing brief in the building's own terms.

**10. Drawing.** Low; render.
- The ground plan draws three upper-storey windows in ground-floor walls
  (Hinami's and the meditation room's east windows, the Roost's gable window).
- The Floor 2 writing desk's label lies on the stair's; the desk itself is
  clear of the doorway.
- Oil lamps "in wall niches" and the hall's pillars are laid as 2x2 blocks
  on the floor (the sort card steers a built-in thing to the floor, and the
  fixture table's lamp is 2x2; the model also wrote `count: 1` for every
  plural, against its card).

## Questions for the owner

- **A. Size from contents.** The 2026-10-10 ruling sizes a room from what it
  holds and never squeezes contents. Here it grows a six-mat room to
  seventeen. Should a size the lore states (mats, m²) hold the room near that
  size, and furniture that will not fit go back to the model as capacity?
- **B. One cell, two heights.** "A cell is taken at one height" (2026-10-08)
  lets a futon lie under a trunk and a stove stand in a tub. Should anything
  standing on the floor hold the floor whatever its height, with heights
  separating only hung, ceiling and on/in things?
- **C. Windows by default.** No ground-floor room has a window because the
  description names none. Should a room lived or worked in by day, with an
  outside wall, take a window unless its description shuts it in?
