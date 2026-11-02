# Building lots: a building planned from outside, designed when someone comes upon it

Status: built 2026-10-28, on wherever a plan marks a lot (nothing to switch).
The owner's idea, the same day, after a walk into an unplanned village built
the whole village as one six-by-eight-pace room: "mark spaces as a building
generation for when an actor like a player or major character stumble upon
it. These marked spaces can act as homes and work places for charter npcs."
What is left is `UNBUILT_WORLD.md` §2.43 (the lots bullet).

## What a lot is

One planned room standing for a whole building nobody has been inside yet:
a row of the registry like any planned room, carrying a `lot` record
(`world/lots.py`, `normalize_lot`) -- `storeys` above the ground (1 to
`LOT_STOREYS_MAX`, 4; left out for the architect to choose, and since
2026-11-01 its answer is held to the same 4) and `cellar` (a lot with none
refuses a room at level -1).
The rest of the lot is the plan's ordinary fields: its name is the
building's, its purpose says what the building is and who keeps it, its
`far_look` how it reads from outside, its `extent` its footprint in paces,
its `adjacent` its door onto the way or the yard.

Until it is expanded it is the building seen from outside. Everything that
names a place names it by uid -- a charter body's berth, a post, an upkeep, a
join from the street, a far look, a memory -- so the lot is a home or a
workplace to the charter exactly as a room is, and no reader needed to learn
the word.

## Where lots come from

- **The Room's `plan_rooms`** may mark any room `lot` (`plot_packages.
  _plan_lot`; the field's help in `OPERATION_FIELDS`). `expanded` is the
  engine's alone and is stripped from a plan.
- **The location path** -- what the Room uses when asked for a building or a
  town (`request_location` → `draft_location` → `charter_generate.close_plan`)
  -- now says "A BUILDING IS A LOT until a story goes into it" in the plan
  specification, lists `extent` and `lot` on the room template, and keeps the
  mark through the closure. A lot is never split into copies of itself when
  its household overflows `BERTH_CEILING` (`_spread_berths`): its sleepers wait
  for its rooms.

Measured live on a copy of the owner's shrine story, the Room asked once for
"the village in the valley below the shrine: its street, its houses and its
shops": Kurotani as a street, three lanes, terraces, an orchard and the
riverbank, and 23 lots -- fifteen houses, the store, the closed school, the
village office, the miso shed and three farmhouses of two storeys -- each with
a footprint, a purpose and its door.

## Expanding one

`agents/director_lots.py`. ONE call on the room designer's role
(`LOT_STEP`, card `prose_contract.layout_lot`, en + ja) reads the lot (name,
purpose, far look, footprint, storeys, cellar, its door: what it opens onto,
which wall, what stands in it), who the charter has there (how many sleep
there, the work done there, what is kept there -- counts and kinds, never a
name) and what the story's lore says of it by its labels
(`director_layout.building_description`). It answers the building's rooms,
each with its storey, its joins (the wall each is in and what stands in it,
a stair or a ladder as `vertical`), which room is the entry, and how many
sleep in each room people sleep in.

Code holds the answer (`planned_rooms_of`): at most `LOT_ROOMS_MAX` (14)
rooms; one entry on the ground storey; a join to a room the answer does not
hold, a stair past a neighbouring storey, a room no join reaches and (since
2026-11-01) a room on a storey the lot does not have are set aside and said. The entry keeps the lot's uid, name, far look, fixtures and
ways onto the ground, and takes its own purpose; the lot's purpose and
footprint move onto its record (`building`, `footprint`) with the turn it was
expanded. Every other room is a new planned room of the lot's part of the map,
`enclosed`, marked `lot_of`. The rooms are planted as the plan's own
(`structure.plant_structure`), and the bodies berthed at the lot are dealt
into the rooms the architect says people sleep in (`deal_berths`); their
`place` stays, so a body at home is still at home.

**Where.** In the rooms-in-view job, before the layout tier
(`director_rooms._predevelop_run`), for the lots an actor -- a player or the
cast, never a charter body -- has come upon (`lots_near`): the lot it is
walking to and the next room on its way first, then every lot in its reach,
then every lot whose door opens off the room it stands in, whatever the
door. `LOTS_PER_RUN` (1) a run. And in the beat that walks into a lot the job
has not reached (`expand_entered_lots`, where the beat chooses the planned
rooms it enters), so the room it designs is the building's entry with its
rooms beyond. That beat pays one call, and the building is then not laid out
by the tier, since its entry is a room the story has seen.

**Laid out as one building, whatever its storeys.** The layout tier's
grouping reads `lot_of`: the rooms of one lot are one building and no other's
-- two lots that share a wall are two buildings -- and a lot's building is
laid out on one storey too, where an unmarked one-storey cluster is still left
to the doorway walk (`layout_bridge.plan_buildings`, `building["lot"]`).

**Never another building's ground.** The layout tier lays a building's
outdoor places with it; a lot along the same street is a building of its
own, expanded or not, and is never collected (`layout_bridge._grounds_of`).

**Never designed as one room.** An unexpanded lot is kept out of the job's
rooms to design (`director_rooms.rooms_to_build`, as a frontier space is). A
lot the story has already described is never expanded. A failed answer is
filed (`LOT_RUNS_KEY`) and waits as a failed design does
(`predevelop_retry_beats`).

## Measured live (2026-10-28)

On a copy of the owner's shrine story (chat 179), the Room on the owner's
routing (DeepSeek V4.1 Flash for the room role), Hinami walked in seven legs
through the drive harness: to the torii, down the planned mountain path, onto
the street of the village the Room had planned ("Kiriya": a street, the valley
road, the paddies and eight lots), along it to the general store, in, and
through to the back.

- **After she reached the street**, the job expanded the first lot in view,
  the Headman's House and Office: 10 rooms in 3.3 s -- the entry, a main
  room, the office, the kitchen, pantry, scullery and washroom, the headman's
  bedroom, a stair foot and a sleeping loft above -- 6 sleepers dealt into its
  bedrooms; the tier laid it out in 30 s, the house whole. Its ground walk
  had swept six of the village's other lots in as places to lay round it and
  dropped every one as failing; laid, they would have stood on the headman's
  plan as his outbuildings. Fixed the same day: a lot, expanded or not, is
  never another building's ground (`layout_bridge._grounds_of`).
- **The beat that slid the store's door open** walked into it before the job
  reached it: the beat expanded it itself, 12 rooms in 2.4 s -- the shop, the
  counter, the storeroom, the back room, the kitchen, the living room, the
  washroom and the stair hall below, a landing, the master bedroom, the
  children's room and a spare room above -- 5 sleepers dealt. Its entry was
  designed that beat, so the tier never lays it out: Hinami walked from the
  entry into the planned back room, built room by room.
- **The tea house** (10 rooms, 6 sleepers) and **the village shrine** (7)
  were expanded by later runs; the tier refused the tea house twice for one
  doorway it did not lay between two rooms that share a wall.
- The charter's shopkeepers stood in the store, and one called through from
  the back that it was not open yet.

Before this walk, a first one on another planned village never reached a lot:
it went from Hinami's room to the bottom of the mountain in one beat, and the
beat invented the places the plan held (`UNBUILT_WORLD.md` §2.43).

## Defaults (named, the owner's to change)

| Constant | Value | What it bounds |
|---|---|---|
| `world.lots.LOT_STOREYS_MAX` | 4 | storeys a lot may ask for, and the architect's answer for a lot that asked for none (2026-11-01) |
| `world.lots.LOT_ROOMS_MAX` | 14 | rooms one expansion plants |
| `agents.director_lots.LOTS_PER_RUN` | 1 | lots expanded per run of the rooms-in-view job |

## Tests

`tests/test_a_lot_becomes_its_building.py`.
