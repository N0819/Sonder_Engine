# The site plan: rooms where a plan put them, floors at their heights

Status: STEP 1 BUILT 2026-10-03 (positions, elevations, the map); STEP 2
BUILT 2026-10-04 (sight with height); STEP 3 BUILT 2026-10-04 (drops as
facts); FLIGHT BUILT 2026-10-04. Terrain is argument; the register entry is
[`../UNBUILT_WORLD.md` §2.39](../UNBUILT_WORLD.md#unbuilt-2-39).

## Why

A room's geometry has always been its own grid, joined to its neighbours by
doorways with a bearing, and laid out on a map only by walking those bearings
outward (`spatial_lint.layout_rooms`). Two things cannot be said that way:

* **A building standing in its grounds.** The layout lab drew the shrine
  inside a garden, a torii and lanterns down the path, the latrine apart, and
  the owner (2026-10-03): "outdoor areas like that would be cool". Laid out
  by bearings, a room inside another is a collision by construction.
* **Height.** A third-storey window joined to the garden by a `window` edge
  was read as a ground-floor window a pace away -- `distance: near`, the
  whole room visible -- because nothing knew the window was eight metres up.
  The owner: "the easiest solution is to add something akin to a 3rd
  dimension", and "this would also allow falling from an upper story or
  landscape", and flight.

## The shape

A room may carry `site = {plan, x, y, elev_m}` (`world/site_plan.py`):

* `x`, `y` -- the room grid's north-west corner on the plan, in the grid's own
  unit (paces; x east, y south). Rooms naming one plan share one frame.
* `elev_m` -- the height of the room's floor in metres. Absent, the room's
  `level` times `STOREY_M` (3 m), else 0.

A garden round a house is ONE open-air room whose `composite` shape is a ring:
its cells are the site less the buildings' ground-floor footprints, and the
house's rooms stand in the hole. A doorway onto a ring may pin its `cell`
(room-local, as an anchor's), because "the north wall" of a ring is several
walls and a fraction along it is ambiguous.

**It is not the unification [`DESIGN_METRIC_SPACE.md`](DESIGN_METRIC_SPACE.md)
§1 warns against.** Passage is still topological: a body walks doorways, and
a plan adds no way between rooms that their edges do not. A plan is the
metric regime reaching across ONE planned place -- a site, a few dozen paces
-- so the facts that need a distance or a height have one. A room on no plan
is exactly what it was.

**A plan is a stored fact the beat does not re-measure.** A room with a
`site` keeps its `extent`, `shape`, `parts`, `size`, `level` and `site`
against a diff, as a planned room's measurements already were
(`spatial_merge._merge_room`). Described, never re-measured; the plan moves it.

## Step 1 (built)

* `world/site_plan.py` -- `normalize_site`, `room_elevation_m`, `site_plans`,
  `site_cells`, `site_overlaps`.
* The structure map (`web/world_routes.map_view`) draws each plan storey by
  storey, cellar first, every room at its site; rooms on no plan keep the
  bearing walk, which never draws a plan's room a second time.
* The layout lint defers to the plan: `rooms_overlap_when_placed` is not
  raised between two rooms of one plan, and `site_plan_overlap` reports a plan
  that does not hold together.
* `tools/site_plan_from_layout.py` writes a layout lab result into engine
  rooms: storeys, stair halls joined by vertical stair edges, doorways on both
  sides, fixtures, zones and windows as anchors, and the grounds as one
  composite open-air room carrying the features and ways. Measured on the
  preferred shrine (`layout-solver-test`, `tools/layout_lab/baselines`): 18
  rooms on four storeys, no overlaps, every doorway's two sides meeting across
  the wall, every room reachable from the grounds.
* Rooms may be 96 paces a side (`EXTENT_MAX_PACES`, the owner's number), after
  sight was measured cheap (`spatial_fov.room_grid`'s memo).

## Step 2 -- sight with height (built 2026-10-04)

`site_plan.plan_sight`, asked by `spatial_fov.body_visibility` for two bodies
in rooms of one plan whose floors differ by `LEVEL_STEP_M` or more. The line
runs from the observer's eye to the top of the other body (`EYE_M`, `TOP_M`
by posture; an unmeasured body stands at its room's centre). It must cross
the upper room's wall inside the window -- between `SILL_M` and `LINTEL_M`
above that floor -- and pass through no building slab on the cells between
(each enclosed room a slab floor to ceiling, the two rooms of the line
excepted). Reaching the top but not `CHEST_BELOW_TOP_M` lower is
`hidden_below: "waist"`. Past `FACE_READ_M` (25 m) a body is a shape.
`visual_level_between` trusts this line in place of the room-grain opening
cone, the field never lays such a room flat beside the other
(`_placed_neighbours`), and from below `visible_adjacent_rooms` shows the
window and not the room behind it. Measured on the shrine: Hinami at her east
window is seen from the waist up 7-10 paces out, hidden by the lower wing's
roof at its foot, and hidden by the sill from anywhere when she stands deep in
the room. The converter now gives every upper-floor window a window edge to
the grounds, pinned on the first open-ground cell outward from it.

The argument it built: the field-of-view model is a 2-D grid with height ranks for what stands in it.
With elevations, a line between two rooms of one plan has a rise. From the
garden below a third-storey window the observer sees what stands at the sill
and the ceiling; the sill hides a body deeper in or sitting, more so the
nearer the wall. From the window, the garden, less the strip the wall hides at
its foot. Terrain that rises between two bodies blocks them. Distance becomes
three-dimensional for hearing and for recognising a face.

## Step 3 -- drops as facts (built 2026-10-04)

`site_plan.drop_m`: a way out of a room that is not a stair and opens onto a
room of the same plan a storey or more below is a drop of the floors'
difference. The Director sees it before it writes -- `causal_world_index`
gives the room `drops: {exit: metres}`, and one sentence of the resolve card
(en, ja) says what it means -- and is told after the beat
(`report_drops`, through the crossing report and `ctx.tell_director`) when a
body went straight down one through a way it could pass that beat: an opened
window, an open side. A shut window is passed by nobody; a walk down the
stair is never a fall. Injury is not computed.

The argument it built:

Geometry proposes, the Director disposes
([`DESIGN_METRIC_SPACE.md`](DESIGN_METRIC_SPACE.md) §4). A body that leaves a
height -- a window, a balcony, a bank, a roof -- has a drop the engine can
state: how far, onto what. The Director is told it and writes what the fall
does. Injury stays the story's judgement, with a real number under it; a body
cannot step off a balcony into the garden and the drop pass unremarked.

## Flight (built 2026-10-04)

`stations[body].altitude_m` is a body's height above its floor
(`site_plan.normalize_altitude`: positive metres, capped under the ceiling of
an enclosed room, dropped at 0; kept by `normalize_scene_stations`). Its
readers: `plan_point` (so a flier in the garden looks straight into an upper
window); `body_visibility`, which draws the line within a room with a rise
whenever either body is aloft -- each fixture against the line's height where
it stands (`_aloft_blocker`), so a flier just over a wall still loses the body
pressed behind it and one high over the yard does not; `eye_rank`, so a flier
sees over the fixtures a room holds; `proximity_rel`, which caps
`within_reach` at `near` across `REACH_ALTITUDE_M` (1.5 m); and the
Director's index, which marks a body aloft with `aloft_m`. The encoder card
(stations, en and ja) asks for `altitude_m`, and 0 on landing. Landing and
falling are the Director's to tell apart.

The argument it built:

A body's own height above its floor (an altitude) is the same number: the
body's eye is its floor's elevation plus its altitude. Outdoors the air over a
room is that room -- open ground has no ceiling -- and indoors the ceiling
bounds it. A flier over a courtyard sees over its wall and is out of reach
from the ground; landing, falling when flight fails, and swooping to a window
are the same question about heights, which is why it follows step 3.

## Vistas -- what stands on the horizon (built 2026-10-04)

Far scenery is not a place (`world/vistas.py`). A vista is a record on the
scene -- `{name, desc, bearing, distance_km, height_m, lit}` -- set by the
Writers' Room's `set_vistas` operation (allowed at the opening), shown to the
Director in `causal_world_index["vistas"]`, and seen by a body when, at the
moment of looking:

* its room looks that way: open air every way; an enclosed room through a
  window, an open door or bars onto open air, that edge's bearing and the
  two beside it;
* (not which way it faces: that filter withheld the lit town from a body
  at the south windows whose facing, derived from the man beside her, read
  north-west -- Larch Hill, 2026-10-04 -- so it was cut);
* the weather reaches that far (`VISIBILITY_KM`, sourced where the condition
  is defined by visibility: fog under 1 km, mist 1-5, haze up to 5; snow
  light 1.5, moderate 0.8, heavy 0.4; rain kept generous, 10/5/2);
* the dark leaves it: whatever the day cycle calls dark (`SUN_LIGHT`,
  evening included since 1dbea654) hides what is not `lit` -- a lit one shows
  as its lights -- and a moon through clear air leaves a skyline as a
  silhouette;
* its top clears what stands nearer on the site plan in that direction --
  buildings, higher terraces -- with earth curvature and refraction
  (k = 0.13).

A room's own `windows` (compass bearings of glass or windows onto open air
with no room beyond) open the same outlook as an edge does; the room
vocabulary says a view is never written into a desc (live, the first Larch
Hill opening wrote the range into the clearing's desc and glassed a watch
cabin with no way to see out of it).

It reaches every view as a sight line (`composer.vista_percepts`, en and ja
templates) and is never a target of touch or movement. Prior art: TADS 3
`Distant`, Inform 7 backdrops, Discworld MUD's terrain rooms, open-world
games' distant-land layers, GIS viewsheds.

## Ground that is not flat

Terrain is flat by default. A room may later state a slope, and a cliff, bank
or retaining wall is a step in height between two cells or two rooms. Neither
is built; both are the room designer's and the Writers' Room's to state where a
place has them, never a default.
