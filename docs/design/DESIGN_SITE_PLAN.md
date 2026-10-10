# The site plan: rooms where a plan put them, floors at their heights

Status: STEP 1 BUILT 2026-10-03 (positions, elevations, the map); STEP 2
BUILT 2026-10-04 (sight with height); STEP 3 BUILT 2026-10-04 (drops as
facts); FLIGHT BUILT 2026-10-04; THE DERIVED PLAN LAID ROOM BY ROOM AND
RECOMPUTED EVERY MERGE 2026-10-09. Terrain is argument; the register entry
is [`../UNBUILT_WORLD.md` §2.39](../UNBUILT_WORLD.md#unbuilt-2-39).

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

**A decided plan is a stored fact the beat does not re-measure.** A room
whose `site` was decided -- solved by the layout tier, converted from the
lab, placed by a host -- keeps its `extent`, `shape`, `parts`, `size`,
`level` and `site` against a diff, as a planned room's measurements already
were (`spatial_merge._merge_room`). Described, never re-measured; the plan
moves it. A site the derivation wrote is not one: it is the engine's reading
of the rooms, recomputed every merge (below), and a beat may re-measure its
room.

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
  the wall, every room reachable from the grounds. Since 2026-10-08 each
  fixture carries its whole rectangle, and a planned building can be laid out
  onto a plan in play by the layout tier ([`DESIGN_LAYOUT_TIER.md`](DESIGN_LAYOUT_TIER.md)).
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
`hidden_below: "waist"`. (Past `FACE_READ_M`, 25 m, a body was a shape
until 2026-10-05, when the owner ruled distance caps one doorway away
"an overzealous feature overall" and it was removed.)
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

## A plan derived room by room (built 2026-10-09)

The derivation (`derive_site_plans`, every merge; d8357aae) lays a group of
rooms spanning two storeys out by its doorways and stacks it by its stairs.
Measured before this round on the play database's 139 stored scenes: 0 of
1,069 rooms carried a site, and one merge left 54 sited, none of them in the
towns of the latest runs. Every clash pair the derivation met, classified:

| Class | Pairs | Where | What it was |
|---|---|---|---|
| A whole group refused on one clash | 7 groups, 158 rooms | 165, 166 and its frames 6 and 7, 163, 27, 40 | the rule, not a datum: a town is one group |
| An open side laid at its wall's start | 12 | 166, 4 in each frame | the boat sheds, the drying racks and the reed flats each landed on a room; each could stand clear further along its side |
| A stair between two rooms of one storey read as a stack | 2, and 1 in a one-storey group | 166 and frame 7; 83 | the Gale house landing, written on the low walk's storey, laid on the walk |
| Storeys never inferred | 24 on the stored scenes, none after a merge | 23-27, 40, 63, 64, 82, 83 | scenes stored before `infer_room_levels` (2026-09-15); the merge's inference ends them, and chat 83's becomes the row above |
| Rooms on one wall nearer together than they are wide | 23, and 2 in one-storey groups | 165 (22: the Back Row and its four siblings, 10; unmeasured stubs on the six-pace cross and low walks and on the designed main walk, 12); 163 (1: a hand's offsets, 0.2 and 0.8 of the hallway); 22, 84 | guessed squares, and two hands' doorways placed without the rooms' depths |
| Rooms meeting past a corner, or across two branches | 15, and 7 in one-storey groups | 165 (11), 27 (3: a descent declared east of the chamber whose east is the passage), 40 (1); 70, 71, 79-81 | the same squares round a corner, and bearings no plane draws |

The counts are after one merge of each stored scene (52 pairs in groups of
two storeys, 10 in one-storey groups); on the scenes as stored there are 87.
The owner's `engine.db` holds the same chats up to 163 and adds no class.

What changed, each at the stage the data first goes wrong:

* **Room by room.** A room that would land on a room already on the plan, or
  one of whose doorways onto a room on the plan would not meet, stands off it
  (`_layout`, `plan_refusals`); every other room stands where its doorways
  put it. Before, a clash refused the group whole.
* **An open side slides.** An open side is the whole of its wall, so where
  the far room stands along it is no measurement; past the doorways' own
  alignment the plan offers every place along the side where the two walls
  still meet, nearest first (`_spots`).
* **A stair between two rooms of one storey places nothing.** Stacking is
  the reading of a stair that joins two storeys.
* **The measured before the guessed, the building before the ground.** Where
  two rooms cannot both stand, the frontier lays a room somebody measured
  before a size tier's square, and a building before a stretch of open
  ground, whose loose rectangle is the likelier to be wrong.
* **A building stands only in its own grounds.** An overlap between open
  ground and a building is no clash only where the building -- the rooms
  joined to it through rooms that are not open air -- opens onto that ground
  (`_stands_on`). Read as any open room under any building, the first plan
  derived for chat 166 stood a chandlery on the drying racks and an inn in
  the Blackreed channel. The Larch Hill tower still stands on its landing.
* **A plan is written where its rooms span two storeys.** At least two rooms
  laid out, one of them not decided already, on two storeys or more. A group
  whose other storey the plan refused or could not reach is, on the plan, a
  group of one storey, and a plan of one storey gives height nothing to do
  while it changes far sight -- the owner's call for every one-storey group.
  Chat 40's roost stair refused, a plan of three rooms at -3 m had been
  written for its room; chats 160 and 161 wrote one at -9 m before this
  round too.
* **A derived site is the engine's reading, recomputed every merge, from
  where it stood.** It carries `derived` and the room its plan was grown from
  (`origin`). The plan is grown again from that room, where it stood -- or,
  in a group that no longer holds it, from the first room of the group that
  stood on the plan, a room on the storey it stood on before one a beat
  moved (`_lay_group`) -- and the rooms of other groups standing on the plan
  are ground nothing may land on. A decided site is kept and the plan grows
  from it. The fringe pass re-reads the plan after it mints stubs and moves
  split rooms, a read through a solved plan re-reads it where a solve was
  laid or taken back (`structure.apply_solved_plans`), and so does a host's
  field edit in the World Browser (`world_routes._write_scene`); the raw
  scene editor (`world_put`) writes what the host typed, read again at the
  next merge.
* **A room keeps the ground it stood on against a room that comes onto it.**
  A room that stood on the plan, on its storey, and that the doorway it is
  offered through still puts exactly where it stood, has a claim, and every
  claim is laid before any room without one (`_layout`). A room added since
  is the one refused and named where the two cannot both stand (a measured
  bakery drafted onto the street, its door a tenth of the way along the wall
  the chandler's opens off and its id sorting first, took the chandler's
  place before). A room whose place MOVED -- its box re-measured, a doorway
  moved, a room it hangs from laid elsewhere -- claims nothing and is laid as
  one reading of the rooms lays it, the measured before the guessed and a
  building before open ground, a room that stood before one that did not
  where the two are otherwise alike. Laying whatever stood before anything
  else, the plan never read a change again: played forward through chat
  165's stored checkpoints, a boat-shed stub laid against a six-pace main
  walk kept its first claim after the walk was measured at fourteen, the
  chandlery and the rope bridge were refused, and the whole cross-walk side
  of the town never reached the plan (7 of 30 rooms where one reading holds
  14).
* **An open side holds its side, not a place along it.** A room with one
  place -- a doorway's, a stair's -- that would land on rooms laid along an
  open side has each of them slide along it, with the storeys stacked on
  it, to the nearest place clear of the room, every doorway onto a room that
  stays still meeting; a room with many places takes one that is clear, or
  is the one refused. Played forward, chat 166's boat sheds stood at the
  reed staithe's north end before the Gale house was written onto the low
  walk beside them, and the house was refused; now the sheds and the loft
  over them stand five paces down the staithe and the house stands, as one
  reading lays them. Only a stack slides: carrying the rooms laid from it by
  doorways too, the main walk of chat 165, laid along the landing stage with
  the town hanging off it, slid the whole town three to six paces at five
  of its six checkpoints played forward (60 room moves where a stack alone
  makes 5), for two more of chat 166's rooms on its plan in each frame.
* **A room is reached through an edge either room declares.** A wall the far
  room declares is still where the two stand side by side, though
  `effective_adjacent` derives no far-side wall (a wall is no way through).
  Chat 27's deep-shelter corridor declared the wall it shares with the lobby
  on its own side only: grown from the lobby, where the plan stood, the plan
  never reached it nor the six rooms past it (3 of 13 rooms sited played
  forward, 10 read once).
* **What stood and no chain of doorways reaches is laid where it stood.** The
  far half of a town whose joining walk was lost, or a stretch whose doorway
  lost its bearing, is laid where it stood while it stands clear there; a
  room a chain still reaches, through a room the beat added included, is laid
  by the chain, so a lane replaced by a longer bridge, or a porch put between
  a street and a shop, carries the far room where the doorways the beat wrote
  put it (laid where it stood first, the far room refused the bridge and the
  porch). A town whose joining walk is lost keeps both halves where they
  stood on its one plan -- a half of one storey too, while the plan still
  spans two storeys: it is part of a plan that stands, never a plan of its
  own -- and a plan laid out for the first time takes a name no plan of the
  scene carries, so two buildings joined by no room are never one frame
  (`_fresh_name`).
* **A join stands whole, or not at all.** A room added later can join two
  groups that stood on two plans -- an alley between two buildings of two
  storeys. The group is laid on the plan more of its rooms stood on; where
  that layout lays every room that stood on the other plan, on its storey,
  the two are one plan from then on. Where it does not, each plan's rooms
  are laid where they stood, on their own plan, and the room the beat added
  stays with the first: laid into the first plan's frame, the second
  building's hall landed on the alley, or the alley on the first building's
  hall, and the second building lost its hall and loft, or every room,
  never named as lost (29 of 54 alleys tried between two such buildings;
  none now).
* **The readers follow the plan.** Where one plan holds two rooms of one
  storey and their doorway meets there, the sight, light and sound fields and
  the layout lint lay the neighbour where the plan put it (`plan_offset`) --
  wherever the plan laid it by its doorway, the doorway's own placement,
  cell for cell; where it slid an open side, where it slid it.
* **What cannot stand is said.** `site_plan_unplaced` names each room a
  derived plan refused and why, to the Room (`inspect_contradictions`), the
  host (the commit's layout warnings, the World Browser) -- never to the room
  designer's own check, which judges a draft one band apart and would hold a
  design unclean for a room its own rule places. Where the refusal leaves
  the rest on one storey the row says the building has no plan; a plan of
  decided sites spanning two storeys stands whether or not the derivation
  wrote any of it (`plan_refused`'s `stands`: read off what it wrote, a
  passage refused beside a solved hall and loft was told its rooms have no
  plan). The World Browser draws a refused room on its plan's storey where
  its first doorway would have put it, flagged with what it lands on.
* **A derived site keeps the layout tier out only in another building's
  solve** (`layout_bridge._on_a_plan`), where a second solve would pull the
  ground that building opens onto off its plan. A re-planned building is
  laid out again, its ground re-read from the rooms, where it used to be
  left to the designer for good; a re-plan the answers cannot solve costs
  the tier's two calls and then waits as every refused solve waits (2 beats,
  then 4, 8 and every 16 while it keeps failing on the same plan), where
  before it was refused at no call.

Measured after, on the same 139 scenes and one merge: 163 rooms sited where
54 were (166: 17 of 34, 165: 14 of 30, 163: 15 of 18, 27: 10 of 13; the
plans of one storey in chats 40, 160 and 161 no longer written), no site
changed by a second merge, no plan name carried by two groups, no plan's
rooms on each other; chat 166's merge 32 to 34 ms against the base's 48 to
51 and chat 165's 18 to 20 against 24 to 25 (medians of nine runs, each
measured more than once).
22 rooms stand off a plan and are named, 21 of them already named by the
room designer's own collision rows, and chat 40's roost stair is said to
leave its building with no plan; the room designer's check reads 142
standing rows before and 130 after -- 15 removed, all in chat 166's three
frames, each a pair the plan now holds apart or lays wall to wall, and 3
added, the reed flats against the channel once the channel slid west. The
owner's `engine.db` (read only) sites 98 rooms in one merge, three of them
named off a plan.

Played forward, as commits store sites -- each stored checkpoint of a chat
given the sites the turn before it derived, then one merge, then the stored
scene the same way -- the eighteen chats with a plan hold 173 rooms where
one reading of their stored scenes holds 163: equal in every chat but 160
and 161, which keep five rooms each on two storeys that one reading of the
last scene lays out on one. At each of the 161 checkpoints of chats 165, 166
and 27, frames included, the rooms played forward are the rooms one reading
sites, and at all 64 of 165 and 166 they stand in the same places relative
to each other, so the replays below describe a story played forward as much
as one read once. Round two's ordering, which laid whatever stood before
anything else, held 158: chat 165 7 of 30, chat 166 16 of 34, chat 27 3 of
13. Of the 1,015 times a body stood in a room at a checkpoint, the room was
on a plan 221 times, where round two's had it 189. No room a body stood in
moved on its plan or left it. Three rooms left one -- chat 165's boat-shed
stub, re-measured beside a walk measured at fourteen paces, refused and
named, and chat 160's and 161's crash site, moved onto the elevator shaft's
storey -- and seven moved: chat 165's main walk with its new box, the inn
and its upper rooms with the walk they hang from and then with a box of
their own, and chat 166's boat sheds and their loft, five paces down the
staithe for the Gale house. `live.db` played the same way holds 132 rooms
where one reading holds 122 (round two's ordering 125), and the owner's
`engine.db` 108 where one reading holds 98 (101): in each, as in the play
database, the ten are chats 160's and 161's five rooms each.

What changes on the page, replayed (every perception step of chats 165 and
166, base and patched code each from a fresh copy of the play database,
perception making no model call, the stored scene read as a commit by that
code leaves it; 119 far views; every one of the 64 checkpointed scenes of
the two chats derives the same plans today as when this was replayed): the
plan answers 14 of them differently, all by a building now standing in the
line, and no line of sight between storeys fires, because no stored beat
has two bodies a storey apart with a window between them. In chat 165 the
five people deep in the Eel and Lamp's taproom lose "To the east, past the
Main Walk, you can see the Landing Stage": from where they stand, the line
leaves through the taproom's own south-east wall and over the Main Row 2's
houses -- what hid it is the wall, which the far layer does not count
(`landscape._eye_on_plan` places an eye inside a closed room at the cell
nearest the place, not at the opening it looks out of). In chat 166, "To
the east, you can see a few buildings" becomes "two buildings" from the low
walk: the Turned Tide stands behind the Gale house, which fronts the walk
between them. Put in the bell loft, a body still sees the wreck of the
Corvina over the roofs, no longer "far off" (under `landscape.OUTLINE_M` on
the plan); on the rope bridge and the high walk, at the eye's height, the
counting house now hides it.

The layout tier, turned on for chat 165 in a copy (the story's own switch;
one run, OpenRouter GLM 5.2, about $0.01): the tide chapel and its bell
loft laid out in 4.7 s on `layout:chapel`, the chapel 7 by 4, the loft 6 by
6 three metres up, 7 fixtures off their walls left to the designer, none
unplaced. The town is then derived onto the solve's plan: 15 of its 30
rooms sited where it had 14, the chapel and its loft now standing and the
agency office, which the chapel's solved footprint covers, standing off.
No stored beat of 165 has a body near the chapel, so its page does not
change; a replay through the pipeline restores each turn's checkpoint,
which rolls the plan back before the solve, so the solve is measured on
the plan, never on a replayed page.

Left (the register's §2.39): a one-storey group gets no plan; a room whose
doorways carry no bearing is on none; an unmeasured stub street too short
for the stubs on it is measured longer only for the rooms the closure split
(`frontage.FRONTAGE_MEASURES_STREETS`); a doorway at its seeded place is
never slid; a town with two solved buildings is laid on the plan holding
more of them; the greedy layout keeps the first of two rooms that cannot
both stand -- a room still where it stood, then the measured, then the
building -- which on a loose rectangle of open ground can be the wrong one;
an open side carrying rooms laid from it by doorways does not slide, nor
does the room a plan is grown from; a room a beat moves onto another
storey, where its column on that storey is taken, leaves the plan without
being named (chat 160's crash site, on the elevator shaft's storey where
the shaft stands; the shaft keeps its site) -- no doorway was tried for it
-- and a level doorway joining two storeys, which is what put it there, is
named by no check; a plan played forward can hold rooms one reading of the
same scene lays on one storey (chats 160 and 161); the raw scene editor
(`world_put`) writes what the host typed, read into the plan at the next
merge; and the far layer's eye in a closed room on a plan is not put at the
opening it looks out of, nor its own walls counted, so what it names as
hiding a place can be the wrong thing.

## Ground that is not flat

Terrain is flat by default. A room may later state a slope, and a cliff, bank
or retaining wall is a step in height between two cells or two rooms. Neither
is built; both are the room designer's and the Writers' Room's to state where a
place has them, never a default.
