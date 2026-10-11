# Buildings from relations: the layout solver as a tier of the plan

Status: first slice built 2026-10-08, OFF by default -- the host's
`layout_solver_tier` setting, or the same switch on one story. The bridge
lane (2026-10-10, below) lays the owner's own shrine plan with no refusal;
the owner judged the result not yet clean beside the lab's, so the tier
stays off. What is left is `UNBUILT_WORLD.md` §2.43.

## Why

The owner chose four procedural-generation items on 2026-10-08, this one
fourth: the layout lab's solver (`world/layout_solver.py`, merged from the
owner's `layout-solver-test` branch) as an out-of-band tier for planned
buildings. The ruling behind all four: "a model decides what and why, code
decides where and how, and a model dresses it only when an actor comes
near." The lab had shown the split (`tools/layout_lab`): a model sorts what a
description names and writes relations, and the solver owns every coordinate.
Nothing in play called it.

## What the first slice holds

1. **No L the solver chose.** The owner withdrew L stairs on 2026-10-03 ("I
   was wrong recommending l shaped stairs"); `STAIR_FALLBACK` still offered one
   right after a straight flight. It is gone from the fallback
   (`layout_solver._stair_shapes`); an answer that names an L still gets one.
   Re-solved from the saved answers: the preferred shrine, the original shrine,
   the lighthouse and fresh runs 1-3 are byte-identical; the lab inn's two
   stairs, both L halls the fallback chose, become U stairs and the inn
   re-lays (15 room rectangles move). The inn is the owner's named win, so
   that is an owner question. This is the round's one solver change.
2. **A solved fixture lands on the solver's own cells.** A pinned anchor
   (`cell`) may carry its whole rectangle (`extent` {w, d},
   `spatial_fov.anchor_extent`); the engine lays exactly those cells from the
   origin and reports the footprint word the rectangle falls in
   (`footprint_for_extent`). Absent, every anchor lands where it did. Measured
   through the engine's own placement: the footprint words laid 27 of the
   preferred shrine's 53 solved fixtures on the cells the solver chose, 5 of the
   lab inn's 17, 37 of fresh run 1's 53 and 3 of the lighthouse's 7 -- every
   north-south pair, every run and every large thing over two by two landed
   elsewhere. With the rectangle, all of them. The converter
   (`tools/site_plan_from_layout.py`) writes it.
3. **A plan carries `site`** (`structure.GEOMETRY_FIELDS`, read through
   `site_plan.normalize_site`). No model writes one: `plan_rooms` never reads
   it, `llm.schemas.RoomDef` does not declare it, and the tier's writer is code.
4. **The tier** (`agents/director_layout.py`, `world/layout_bridge.py`).
5. **A comparison page for the owner**: the shrine and the inn re-solved
   beside the versions the owner liked, every fixture not where it was asked
   listed, and the tier's live run.

## The tier, decision by decision

**Where it runs: inside the rooms-in-view job** (`director_rooms.
_predevelop_run`), before any room is designed. That job is the owner's heavy
tier ("save heavy plans for when the actors near them"): already out of band,
bounded per run, backed off on failure, stopped by a restore, on the room
role the lab's two calls used, and the designer that dresses the building is
the next thing it does. The planting sketch is one compact call by the
owner's design, and a Writers' Room tool would sit inside the loop whose
re-reading the owner had just cut. Given up: a building nobody nears is never
laid out, so the height-aware far readers meet it only then. At most one
building is laid out a run (`LAYOUT_TIER_PER_RUN`).

**The switch.** Off unless turned on: for one story, by that story's own
`layout_solver_tier` world key (`LAYOUT_TIER_STORY_KEY`, read first, and kept
across a reroll or a restore as a dial the author set,
`persist.checkpoints.SETTING_PROVENANCE`), or for every story by the host's
setting of the same name (`LAYOUT_TIER_SETTING`). A story's `off` holds even
where the host's is on. The owner's ruling of 2026-10-10, "Bridge lane now,
then on": on by default once the bridge lays a real Room plan cleanly.

**What a building is.** The plan says which rooms exist and how they join, not
which share a roof. A stair does: two rooms joined `up`/`down` are two storeys
of one building -- when both are rooms a wall can go round. A room the plan or
the scene states is `open` or `sheltered` has no walls round it and is never a
storey (`layout_bridge.STOREY_EXPOSURES`): a plank walk up a flight of steps to another
walk is ground on two heights, and a stair from a storey down to such a place
is an outside stair, laid as an outside door of the storey it leaves from. A
building is the rooms of one structure joined by stairs between rooms that may
be storeys, grown along level joins into rooms the plan or the scene states
are `enclosed`; a room of unstated exposure is never guessed in along a level
join -- it is ground the building opens onto. The tier lays out a building
only when every room is a planned stub nobody has described, none is sited or
held open as a frontier space, none is planned another shape than a
rectangle -- save one that opens into the building by a single doorway on a
side the plan states, which stands in a block of its own beside the room it
opens from, keeping its shape (`SOLVED_SHAPE`: the solver lays rectangles,
and written back one would square a round tower room for good; a room built
from `parts` cannot be re-boxed and still keeps its building out) -- it
spans two storeys, it opens
onto something, it holds at most `LAYOUT_TIER_MAX_ROOMS` rooms, and no other
room already stands on the plan it would be written on
(`layout:<entrance room>`): a room placed there beside an earlier solve stands
in that solve's coordinates, and a new solve on the same plan would read two
frames as one.

A stub's site the engine DERIVED keeps its building out only where it lies
in another building's solve. Derivation (`site_plan.derive_site_plans`)
places every room it can beside one already on a plan on that plan, so once
a laid-out building's upper storey stands in the scene, the street it opens
onto and the ground floor of the next planned building along that street
stand on its plan, and that building is left to the designer (tried: two
planned buildings on one street, the second refused "stands on a plan
already" the commit after the first's upper storey was minted) -- a second
solve there would pull the ground the first opens onto off its plan. A
derived site on a plan no solve holds is the engine's reading of the stubs,
recomputed every merge (`site_plan.DERIVED_KEY`, 2026-10-09), and keeps
nothing out: a building whose own solve a re-plan took back is laid out
again, the ground beside it re-derived from the rooms -- until then it was
left to the designer for good, its street keeping the old solve's
coordinates. A re-plan the answers cannot solve (a hall re-planned 12 by 3)
is attempted too: its two calls, the bridge's refusal of the solve, and the
wait every refused solve waits (`director_rooms.predevelop_retry_beats`: 2
beats, then 4, 8 and every 16 while it keeps failing on the same plan) --
where the stale street had refused it before any call. A building already
in reach before its neighbour's upper storey stands is laid out on a plan
of its own, and the group is then laid on the plan holding more of their
rooms, the other building standing on its own (review V3-1). Laying a
solve onto a plan its ground already stands on -- translated to where the
doorway meets it -- is the town fabric's first step (survey rank 7).

**Two calls, the lab's split, narrowed to what a plan leaves open.**
`prose_contract.layout_sort` says what each planned room holds (fixtures and
how each stands, zones, windows) and whether each stair is enclosed;
`layout_relate` says how they relate (purpose, sides, walls, near/beside/
facing, stair walls and shape). Every word the solver reads -- purpose,
fixture kind, size, place, stair shape -- is chosen from a closed set the
solver's own tables enumerate, handed to the model in the payload
(`layout_bridge.vocabulary`); a word outside it is no word. Both calls read
the story's own lore of the building (`description`,
`director_layout.building_description`): the lorebook entries whose labels,
read whole, name the building or one of its rooms, whole entries up to
`LAYOUT_DESCRIPTION_CHARS`, as the layout lab read its descriptions; the
second call gives a room's `area_m2` only where that lore states the room's
size. The first call
names every entry for what it is, never whose it is -- the room author's own
class, since a name it gives a thing the plan does not describe becomes that
anchor's desc, which every mind that sees the room reads -- and an entry for
several alike names one of them, since each is laid and named as a thing of
its own. The lab's own prompt and its prose reader of room names
(`purpose_key`'s fallback) are untouched and never reached from play.

**What the plan fixes, code keeps** (`layout_bridge.hold_inventory`,
`spec_from_answers`). The plan's rooms, ids, names, storeys, joins and stairs
are the plan's: a room or a join the model invents is dropped, a side the
plan's bearing states wins, the front faces the ground whose bearing the plan
or the live scene states, a ladder the plan names is a ladder, and a thing
the sort named is never lost. So are the plan's FIXTURES. Each keeps its id as
a fixture, a window or a mark, never as a zone (a zone is no anchor, and a
fixture whose id went to one was written nowhere; the zone takes an id of its
own). One the answer leaves out, or files only as a zone, is kept as the
plan holds it -- its own record, unpinned, never handed to the solver -- and
the solve's record lists every one so restored (`planned.layout.restored`).
What it is stays the model's to say: restored as a floor thing of a middling
size, a gable window and the place where people wait at the foot of a stair
were each pinned as an opaque, waist-high obstacle (review R2-2). A fixture
the plan lists that is no thing in the room but the place where a stair or a
doorway meets it is given with `marks`, the room that way leads to, and is
pinned there after the solve -- a point that blocks no line -- never handed to
the solver (the first live run pinned the taproom's `stair_foot` four paces
from its stair).

**What a solve becomes** (`layout_bridge.planned_layout`): each room its
rectangle -- `extent`, `level`, and `site` on the building's plan
(`layout:<entrance room>`); each fixture the solver stood where asked an
anchor pinned to its rectangle; several alike one anchor each, fixtures and
windows alike, the first under the plan's own id when the plan named them
(the first live run left the plan holding four box-bed records for three
beds), each named as one of them, and the plan's words for the group kept in
the solve's record (`planned.layout.split`) rather than on the first copy (the
second live run wrote "three box beds along the wall" on one bed and "box
beds" on two more); each doorway's `dir` and
`offset` on the plan's edges; each stair the plan's own vertical edge, pinned
(`cell`) where each room meets it; each window an anchor in its wall that
blocks no line; each stated measurement filed against the solved one
(`planned.layout.stated`). The solver's stair halls, stores and voids are not
rooms: the plan holds no such room, and a tier that invents rooms was refused
once (98827d9f, reverted). Zones are not carried: an anchor is the engine's
only floor place, and a zone holding a cushion would read as two fixtures on
one cell to the designer's check.

**Never a move made silently.** A fixture the solver stood off the wall the
model named, out of the corner it named, or against a wall when it asked for
the middle, is written on the place the model named and pinned nowhere; one
it could not place at all, the same. The engine lays it as it lays every
unpinned fixture, the designer dressing the room sees what it crowds, and
settling it is the model's (the owner: "capacity goes back to the model").
A window keeps the outside wall the solver found -- a window in an inside wall
is none -- and its move is listed. Every move and every unplaced fixture is
in the solve's record (`planned.layout`) and the log.

**Never a second scene writer, and never half a building.** The tier writes
the plan (`structure.write_planned_layout`: all or nothing, only onto the rows
the solve read, nothing once the job is cancelled). Three readers then read
the scene THROUGH the plan, because the stored scene holds a stub the commit
minted before the solve until the next commit's fringe pass lays it down
(`structure.apply_solved_plans`): `story.scene.get_scene`, so every reader of
the next beat -- the install, the Director, perception -- sees the stubs on
their solve; the commit's merge base (`compose_beat_scene`), so a room the beat
builds in or designs is merged onto the stub as the beat read it; and the
design job itself, so what it designs is what the next beat holds. Before
this the job designed the room in view on the solved plan, the next beat
installed that design onto the stored, unsited stub, and the commit stored it
off the plan with its fixtures unpinned, the rest of the building on the plan
(review of 2026-10-08, F1). A design the job filed for one of the building's
rooms before the solve is dropped by the run that solves it, since its brief
reads only names, purposes and exits and can still match. The commit's
fringe pass lays a solved plan onto the stubs it stores
(`structure.apply_planned_layout`), the plan's positions winning on a
prose-free stub, never onto a described room. And the commit's registry
projection, prepared before the write lock while the tier may write the plan,
lays only what it owns -- whether a planned room is described yet, and its
region -- onto the row as it stands inside the lock (review F5: it used to
write back the payload it read before, taking a solved building's site off
every row it upserted). So does the frontier expansion, the commit's other
write to a planned row prepared before the lock: it lays only the edges it
drew, the axes it spent and what now stands in them onto the holder's row
(`structure.apply_frontier_mutations`; review R2-4: the hall lost its solved
site while its kitchen and loft kept theirs).

**A re-plan drops the solve, and only the solve.** `plant_structure`
replaces a planned row whole, so a building the Room re-plans after it was
laid out has rows with no `site` while its stubs still stand where the solve
put them. A stub the solve laid carries the record of it (`laid_out`: the
plan, and the doorways and stairs the solve placed), written by the code
that lays it and by nothing else, and gives back what that record lists --
its `site`, any rectangle or storey the plan no longer states, every
placer's pin (`cell` with `extent`) on its fixtures, and the `cell` and
`offset` of the doorways the solve placed -- taking the new plan's
measurements. A neighbour the engine's derivation placed beside the building
on its plan carries no such record and keeps its site and whatever a beat
measured on it (review R2-1: read off the plan's name, the rule took the
derived site, a 3 by 3 a beat wrote and the doorway offset off a planned
yard every commit). The building is laid out again only on a plan nothing
else stands on: the street it opened onto, once derivation has placed it,
stands on the old solve's plan, so a re-planned building is left to the
designer, its stubs placed by derivation beside that street.

**Fails open, always.** Off; not a building; an answer that cannot be read; a
solve the bridge refuses on every seed it is tried with
(`layout_bridge.solve_for`, `LAYOUT_SOLVE_SEEDS`; `refusals`: a planned room
with no floor, a stair with no hall, a join with no doorway, a doorway
outside missing, a side the plan states put on another wall -- never a
room's size, below); a plan changed underneath; a cancelled job. A side only the model chose that the solver put
on another wall is listed in the record (`planned.layout.sides`), as the
survey counted four on the shrine, and never refused. Each writes nothing and
today's designer builds the rooms as it did. A failed attempt waits as a
failed design does (`director_rooms.predevelop_retry_beats`).

**One check, corrected.** `wall_overfull` counted a pinned anchor's whole area
against its wall's length, so a bed solved two by three against a four-pace
wall read as six paces of it. A pinned anchor now takes of its wall the cells
of that wall it stands on (`spatial_lint._wall_rows`) -- not nothing, which
would hide a pinned bench three paces along a four-pace wall from the two
chests laid beside it. Measured on every scene row of the play database (139
rows over 133 chats, 1 to 166, frames included; 10 pinned anchors, none with
a rectangle): 8 rows before, 8 after, none removed or added.

## The bridge lane (2026-10-10)

The owner tried their shrine in the engine (chat 164) and found it built with
no solve at all, nothing like the layout lab's. Four causes: the tier was off;
the opening had described the room Hinami woke in before the tier could run
(fixed first: `director_layout.lay_out_opening_ground`); the plan's Seal
Cavern is planned `composite`, which refused the whole building; and, forced
through, the calls read one-line purposes and no lore, so the solve lost every
planned size and turned three doorways. The owner's ruling, "Bridge lane now,
then on": lay the shrine's own plan, replicated with nothing described
(scratch chat 168, its sixteen planned rooms), against the lab's, one change a
round, and turn the tier on once it lays out cleanly. From round 4 every round
was measured on recorded answers replayed, so only the code differed, and
every solver change re-solved the lab's liked shrine cell for cell
(`tools/layout_lab/baselines`).

1. **The lore.** Both calls read the story's own entries about the building,
   matched by the labels the lorebook's author wrote, read whole: on the
   owner's lorebook, exactly the seven entries the lab was laid out from,
   less the grounds -- 10,101 characters.
2. **A room of another shape off one doorway stands in a block of its own**,
   as the lab's own hand edit stood the Seal Cavern beyond the basement's
   north wall; its doorway is written from its side, its shape kept.
3. **Size from contents** (the owner's ruling, that day): the plan's `extent`
   is the Writers' Room's estimate -- Hinami's room 36 m2 against the lore's
   six mats -- and a solve held to a quarter of it was refused room after
   room. The solve's size replaces it, each filed against the other
   (`stated`); a size the lore states is the one size aimed at (`area_m2`,
   filed as `described`). No size refuses a building any more.
4. **A storey under the roof never sizes its block.** The roost's nest, asked
   huge, set the whole shrine at 20 by 14 -- its need taken a quarter larger
   for its inset -- and the ground floor's spare went to a stair hall 20 by 5.
5. **A side the plan holds costs what a missing doorway costs** (`held`,
   60): at 20 the solve traded two of them for a better-scoring stair.
6. **A room joined to another block stands on the wall facing it at 60, not
   15**: on one answer set the basement stood off the cavern's wall in all
   20 seeds; after, 15 of 20 stood with no refusal.
7. **Up to `LAYOUT_SOLVE_SEEDS` seeds (4)**, each tried only where the one
   before fell short: one with every stair landed wins at once, else the
   first the bridge does not refuse. A solve of the shrine takes 7 to 9 s.

Measured at the end, three answer sets through the tier's own path: all three
stand with no refusal; one with every stair landed in each room it joins (14.4
s, two seeds); two with the stone stairs' hall opening off the Main Hall's
neighbour rather than the Main Hall (35 s and 32 s, four seeds each), the
stair's landing there left to the room designer. Two of the lab's three fresh
runs re-solve differently under rounds 4 and 6; the liked shrine and the third
do not. The owner's comparison page holds all of it. The default went on,
and came back off the same day: the owner, reading the page, "The results
still don't look particularly clean in comparison to the lab".

**Why not clean yet** (measured the same day, the three recorded answer sets
replayed, every change also run on the lab's liked shrine and its three
fresh runs). The relate answers put every upward stair against opposite
walls of its two rooms -- `n` in the room below, `s` in the room above: a
stair climbing from the room below into the room beyond, which stands in the
middle of the building. The lab's brief put its stairs at the outer wall,
turning back over the room below ("arrives at the north end of the
hallway"). The solver carves each stair hall out of a storey before
dividing it, offering a stair the two ends and the middle of each wall of
the region its storeys share; a stair in the middle of a storey leaves
pieces no room can take whole, and on the ground and below its hall
swallows them (`_absorb` caps a landing only above the ground) at no cost
to the score, a hall being exempt from size and proportion -- engine A's
basement stair stood end-on mid-way along the north wall, its hall 10 by
5. Sixteen variants were measured: charging the swallowed floor moved it
into stores; holding a stair to a wall of every storey made two of the
three worse; every pace of a wall as a stair's place, with the swallowed
floor charged at 2 a pace, cleaned one of the three and half of another,
tripled the solve (8 s to 24 s) and re-solved the liked shrine worse (its
genkan a strip down the west side); freeing the plan's sides helped one;
making each stair's two walls agree was refused on every seed for two. A
side-by-side placement of A's two ground-floor stairs, forced, scored 290.8
against the solver's own 206.9: the score itself prefers the swallowed
hall. Laid out with no stair holes, the same specs tile every storey
cleanly, and each stair fits inside both rooms it joins (checked alone;
placed together in tilings chosen blind to the stairs, A fits all three, B
two, C one) -- the mockups on the owner's comparison page. The next design
is the owner's call (`UNBUILT_WORLD.md` §2.43, stairs that stand in their
rooms).

## The live runs

Scratch chat 165's inn: the Taproom of the Eel and Lamp and the Rooms to Let
over it, planned by the Writers' Room and built in play by the room designer.
OpenRouter GLM 5.2, reasoning off.

The first, before the review's fixes, called the tier's two calls directly on
a copy of the play database: sort 4.6 s, relations 2.0 s, solve 1.2 s, about
$0.006; 3 of 8 fixtures not where asked, none unplaced; the stair a spiral by
the solver's tower rule; and, written onto its own plan rows, four box-bed
records for three beds and the stair's foot pinned four paces from the stair.

The second, after them, ran the tier's own path (`lay_out_buildings`, the
story's switch on) on a scratch database holding the inn's plan with its rooms
as stubs nobody has described: sort 2.2 s (1,264 tokens in, 701 out),
relations 1.9 s (2,287 in, 472 out), solve 0.9 s, 5.0 s in all, about $0.005.
Accepted with no refusal; 2 of 7 placed fixtures not where asked (the hearth
and the barrel rack, both left unpinned on the walls asked), none unplaced,
none restored; three box beds written as `bed_boxes`, `bed_boxes_2` and
`bed_boxes_3`; the stair's foot and its head marked on the stair's own landing
cells. The second call named the stair straight. The scene the next beat reads
holds the building on its plan, and the layout lint finds nothing in it; the
hearth laid along its asked wall shares a cell with the pinned bar, which the
designer's own check is there to show.

The third, after the second review's fixes, asked no model: the same path on
the same scratch inn, each call answered with the second run's saved answer,
so only the tier's code differs. The solver laid exactly what it laid in the
second run. The beds are `bed_boxes`, `bed_boxes_2` and `bed_boxes_3`, each
named "box beds" -- the second call's name for the group, in the plural; the
card now asks for the name of one of them, which a replay cannot show -- and
the plan's "three box beds along the wall" stands in the solve's record.

## Tests

`tests/test_a_planned_building_is_laid_out_by_relations.py` (the tier, the
bridge, the beat after the solve through interpret, resolve and commit, the
scene the beat and the design job read, the registry and frontier races, the
re-plan and the derived neighbour, the story switch across a restore),
`tests/test_names_carry_no_owner.py` (the sort card), `tests/test_layout_solver.py`
(the L), `tests/test_body_cells.py` (the whole rectangle),
`tests/test_site_plan.py` (the converter), `tests/test_room_lint.py` (a pinned
anchor's wall share).
