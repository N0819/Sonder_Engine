# Buildings from relations: the layout solver as a tier of the plan

Status: first slice built 2026-10-08; ON by default since 2026-10-10 -- the
host's `layout_solver_tier` setting, or the same switch on one story, turns
it off. The bridge lane (below) laid the owner's shrine plan with no
refusal but not yet cleanly; with the shrine's lore refined for placement
and the Room's sides weighed as wishes, two of three answer sets laid its
ground floor out room for room as the lab did, and the owner: "It's ok enough now". What is
left is `UNBUILT_WORLD.md` §2.43.

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

**The switch.** On unless turned off: for one story, by that story's own
`layout_solver_tier` world key (`LAYOUT_TIER_STORY_KEY`, read first, and kept
across a reroll or a restore as a dial the author set,
`persist.checkpoints.SETTING_PROVENANCE`), or for every story by the host's
setting of the same name (`LAYOUT_TIER_SETTING`). A story's `off` holds even
where the host's is on, and its `on` where the host's is off. The owner's
ruling of 2026-10-10, "Bridge lane now, then on": on by default once the
bridge lays a real Room plan cleanly -- off again the same day when it did
not yet, and on once the owner judged the refined shrine ("It's ok enough
now").

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

**The architect's brief, written first** (2026-10-10, the owner: "the
brief is a good idea too"). One call on the room role writes how the
building stands as a whole -- where each room lies, the wall each stair runs
along, the room it rises from and the room it arrives in -- from the plan,
the sides it fixes and the story's lore (`prose_contract.layout_brief`,
`director_layout._briefed`); both calls below read it as `brief`, beside the
lore, and the run record keeps it. It is the lab's own step: the liked
shrine was laid out from lore rewritten for placement, and most stories'
lore says what a room holds and seldom where it stands. Measured on the
shrine's twelve recorded answer sets, replayed through the same code: the
brief raised the stairs whose two walls agree -- what lets the solver lay
them in a band at a wall -- from 1 of 9 to 3 of 9 on the raw lore and from 5
of 9 to 7 of 9 on the refined; the floor the stair halls swallow did not
move much either way. It fails open: no brief, the two calls read the lore
alone.

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
`offset` on the plan's edges; each stated measurement filed against the
solved one (`planned.layout.stated`). Superseded on 2026-10-12, after the
owner read chat 168's shrine: each window is in its wall -- a record of its
room's `windows`, or a `window` edge onto the ground beyond it -- and never an
anchor; and each stair is a room of its own on every storey it joins, the
solver's hall planted as a room the tier makes (`structure.LAYOUT_MADE_KEY`),
replacing the plan's own stair edge (the owner's choice: "Its own stairwell
room per storey"; Design.md, "A window is in its wall" and "A stair is a
room of its own"). Until then each stair was the plan's own vertical edge,
pinned (`cell`) where each room meets it, and the halls, stores and voids
were not rooms: a tier that invents rooms was refused once (98827d9f,
reverted -- a void made a loft where a window belonged). Stores and voids
still are not. Zones are not carried: an anchor is the engine's
only floor place, and a zone holding a cushion would read as two fixtures on
one cell to the designer's check.

**Never a move made silently.** A fixture the solver stood off the wall the
model named, out of the corner it named, or against a wall when it asked for
the middle, is pinned where the solver stood it, its `dir` the wall it stands
against, and the move is listed; a designer dressing the room re-settles it
by its `cell`. One it could not place at all is written on the place the
model named and pinned nowhere. (Until 2026-10-13 a moved fixture was written
unpinned on the place the model named -- "capacity goes back to the model"
-- and the engine laid it again by its seed on the wall that could not hold
it: Home 11's closets on the genkan's doorway, its stove in the tub. The
owner, reading that map: "match layout lab ... stop overlapping
furnitures".) A window keeps the outside wall the solver found -- a window in
an inside wall is none -- and its move is listed. Every move and every
unplaced fixture is in the solve's record (`planned.layout`) and the log.

**A stair is climbed from its foot.** An enclosed straight stair's doorways
open off its flight or at the end their storey takes -- the foot below, the
head above (`layout_solver._stair_doorways`) -- and each hall records its
`flight`, which the plan draws the treads on (2026-10-13; 12 of 29 enclosed
stair doorways had opened onto the middle of a flight).

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
outside missing -- never a room's size, nor a side, below); a plan changed
underneath; a cancelled job. A side the solver put on another wall -- one
the Room planned, marked `planned`, or one only the model chose -- is listed
in the record (`planned.layout.sides`), as the survey counted four on the
shrine, and never refused; the plan's doorway moves to the wall the solve
chose (the owner's ruling of 2026-10-10, "sides are wishes, like the
lab"). Each writes nothing and
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
   Withdrawn the same day with the owner's ruling that the Room's sides are
   wishes (below): none is refused, and the solver weighs them as the lab
   did.
6. **A room joined to another block stands on the wall facing it at 60, not
   15**: on one answer set the basement stood off the cavern's wall in all
   20 seeds; after, 15 of 20 stood with no refusal.
7. **`LAYOUT_SOLVE_SEEDS` seeds (4)**: until 2026-10-15 each tried only
   where the one before fell short, one with every stair landed winning at
   once; since then every seed is solved and, of those standing with every
   stair landed, the one that turned the fewest asked sides is kept (`The
   lab's look, measured live`), else the first the bridge does not refuse. A
   solve of the shrine takes 7 to 9 s.

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
two, C one) -- the mockups on the owner's comparison page.

**The lore, refined** (the same day). A stairs-in-rooms prototype tiled
every storey cleanly but crowded its rooms and corridors with stairs, and
the owner judged the lab's shrine still the best -- then: "Perhaps the
lorebook needs some refinement". The lab's shrine was laid out from the
lore rewritten for placement, so placement was added to the shrine's seven
building entries -- a compass, which room lies beside which, where each
stair runs and arrives -- every original word kept, in order. The Writers'
Room planned the shrine fresh from it (scratch chat 169) in the lab's
arrangement: the genkan at the front, the main hall with both stairs in its
north wall, the kitchen east and the washroom west. Its three answer sets
were refused for a room planned `composite` with no parts (now its box) and
then for sides the solve turned -- two for the washroom east of the main
hall, as the lab's liked shrine had it too -- and the owner ruled that the
Room's sides, like its sizes, are wishes. All three then stand, two of them
with the ground floor room for room as the lab laid it out: both stairs in a
band along the back, the main hall, the washroom and the kitchen in a grid;
upstairs the staircase arrives at one end of a central hallway with the rooms
off it and the roof stair at its other end, the rooms in the other order from
the lab's (measured 2026-10-15; "The lab's look, measured live"). The owner's lorebook carries the refined
entries (2026-10-10, their prior text kept outside the repository).

## The grounds (2026-10-11)

The owner tried the shrine again (chat 167, "Home 5"): "it generated
something but it looks nothing like the layout lab". Two causes. The lore
stated no room's size in a form the calls passed on (fixed first, 1f6cbbe4,
with the sizes added to the owner's lorebook). And the lab's shrine stood in
its garden, its approach running from the front door to the torii, while the
engine laid the house out alone and left every outdoor place where the
Writers' Room's own estimates put it: a 60 by 60 garden, a 20 by 20 camphor
tree and a lantern path 40 long, each a box beside a house a fraction their
size. The owner's choice: "Tier lays out the grounds". Built behind its own
switch, off until the owner had judged it beside the lab, and ON since the
same day, the owner having seen the comparison: "I would like layout grounds
on" (`layout_grounds`, the host's setting or the story's world key, read as
the tier's own is, and turning them off; `director_layout.layout_grounds_enabled`).

**What is ground** (`layout_bridge._grounds_of`). The outdoor places of the
building's own structure its doors reach through other such places, nearest
first: at most `GROUNDS_MAX_PLACES` (12) within `GROUNDS_MAX_HOPS` (3) joins,
both named for the owner. A place is ground only where nothing else decides
it: not one of the building's rooms, not a frontier space the Room has yet to
claim, not a room the story has described, not standing on a plan already
decided, not the inside of something, and on the ground storey. The places
stay the plan's rooms -- the tier never invents or removes a room, and a body
can stand at a tree. Past three joins the places are the town's. Home 5's
plan held six outdoor places, every one within three joins of a door.

**What each IS, and where.** The sort call says what each place is in the
solver's own four words (its rule 5, "the grounds are open ground with things
in it"): `open` ground a body walks about on, a `way` from one place to
another, a `feature` -- one thing standing on the ground that a body stands
at -- and an `outbuilding`, a place with walls of its own standing apart. The
relate call gives each the solver's own relations: open ground lies `around`
the building or on a side of it; a way runs `from` the entrance or another
way, `to` the feature it leads to; a feature stands `across` a way it spans,
`flank`s it as a pair, runs `along` it as a row, stands `by` a place, a room
or the entrance -- on the side of it the description gives -- or on a `side`
of the building; an outbuilding stands apart on a side. Every word is held
to those sets (`hold_grounds`, `_ground_plan`). A place the first call left
unsaid is laid as the tier always laid it: open ground on its doorway's side
where the house opens straight onto it, and not at all further out.

**The doorways.** An outbuilding the plan joins to a room of the building is
a block of its own standing apart, reached by a walk between its door and
the house's -- and the walk is its own floor (2026-10-14), so the house door
opens onto it. One the plan joins only to open ground stands in that ground,
toward the end the plan bears it to, and opens onto it. A door of the house
onto a feature opens onto the ground the feature stands in (`door_to`), and
is written back as the doorway to the place the plan names, on the wall the
solve found. Every doorway onto the ground meets its other side across the
wall, the lab converter's own measure (`_ground_doorways`): on whatever
place a door opens onto, the cell across its threshold, on the wall facing
it -- and no pin at all where the place does not hold that cell, which the
floor then refuses; where two places of the ground the plan joins touch, the
middle of the side the plan states, else of the side they share most. Every
place's cells are read as the world reads them (`_world_cells`): a round
tree's circle, never its box's corner.

**As the world reads it** (`_ground_geometry`). The solver lays its ways and
features ON its open ground; as rooms of their own each cell is one place's
-- outbuilding, then feature, then way, then open ground. And the world reads
no side or part narrower than two paces (`EXTENT_MIN_PACES`, through
`spatial_fov.normalize_parts`): a one-pace band of garden written as a part
is read two deep, over the house beside it, and the garden's grid then sees
across the house's floor. So a thing the solver lays a pace across -- a gate,
a lantern -- is widened into ground no other place holds; open ground is
written as overlapping parts of two paces or more (`_cover`), and a sliver no
two-by-two block holds is no place's. A planned round thing keeps its shape
in its solved box. The Room's estimate is filed against each place's solve,
as a room's is.

**Re-plans and failures.** A house the Room re-plans gives its rooms' solve
back, but its ground's rows keep theirs; ground an earlier solve of the same
building laid (`_own_grounds`, read off the solve's own record) is laid again
with the house, never keeping it off its own plan. With the switch off it
does keep it off -- a new solve beside the old ground would read two frames
as one -- and the house is left as planned. Where the ground leaves every
seed refused, the places that fail are taken out and the rest solved again
(below, "Holding together"), and failing that the house is solved again from
the same two answers, with no further call, as the tier laid it before the
grounds (`lay_out`, `grounds_dropped` and `places_dropped` on the run's
record): the grounds never cost a house its layout.

**One solver change, by the lab's rule.** The lore puts the shrine's well
"east of the path near the entryway", and every answer said so -- by the
entrance, side e -- but the solver read `by` and dropped `side`, and its
search, ties broken west, laid the well west of the path in three runs of
three. A feature by something with a side given now takes ground on that
side of it wherever that side has any (`layout_solver`, the features' `by`).
The lab's liked shrine (`baselines/shrine_rewritten.json`) and its three
fresh runs, none of which asks for both, re-solve cell for cell.

**Measured** on fresh replicas of Home 5's plan (scratch chats 180-182), the
story's switches on, the room role on deepseek v4.1 flash as the owner's
engine.db routes it: three live runs, each laying the house and six ground
places in 35-46 s with no refusal, no place unplaced, no fallback, no two
rooms on one cell and no site-plan overlap or refusal; the first call sorted
the six as the lore describes them all three times. Replayed on the final
code from the saved answers (chats 183-185): the same, with the well east of
the path all three times.

| Place | Is | The Room's estimate | Solved, three runs |
|---|---|---|---|
| The Garden of Stone and Moss | open | 60 by 60 | 32-35 by 34-36, round the house, 12-13 parts |
| The Lantern Path | way | 8 by 40 | 3 by 10-11, from the genkan's door south |
| The Torii Gate | feature | 10 by 6 | 4-5 by 2, at the path's far end |
| The Sacred Well | feature | 5 by 5 | 2 by 2, round, by the entrance |
| The Sacred Camphor Tree | feature | 20 by 20 | 6 by 6, round, north of the house |
| The Latrine | outbuilding | 4 by 4 | 3 by 4, three paces apart to the west, its way to the washroom's door |

The arrangement is the lab's, the latrine west where the lore puts it
("behind the shrine's west end") rather than behind. The comparison page,
beside the lab's liked shrine and Home 5 as the engine holds it, is
`output/layout_home5_grounds_2026-10-11/compare.html` (not in the repository).

**Not yet.** A ground place the Room re-plans alone is not laid again, and a
place planned after the building was laid out is never laid: the house still
stands on its solve, so the building is refused as laid, and either needs a
pass that lays ground onto a plan its house already stands on. A way through
open ground meets it on one side only (below).

## Holding together (2026-10-13 and 14)

Home 10 (chat 173, the owner's fourth shrine): the mountain path was laid out
of the hall's front door THROUGH the court the hall opens onto, cutting the
court into two floors, and the storehouse stood apart, joined to a walk the
solver never lays ("only one door opens onto it"), so it was written with no
doorway at all. Replayed from its recorded answers, no answer the closed
vocabulary allows laid that plan: the fault was in code. And the class was
wider -- replayed the same way, every story with recorded answers wrote
grounds that did not hold together (Home 6 six breaches, Home 9 one, Home 11
two), and the tier's own farm fixture broke the contract its test claimed:
the well a pace off the kitchen's threshold, the privy's doorway on its own
block, north against north. Three adversarial reviews the next day (29
findings confirmed of 31, 28 of 29, then 26 of 26 -- nine of the third
round's in the second round's own fixes) reshaped what follows. Each finding
fixed has a test that fails with that fix alone reverted, checked by building
the tree so (the second round's 37 single-fix variants and the third's 31,
every one caught); one, a stranded ground's building refused for
good, is registered below rather than fixed.

**The floor** (`layout_bridge.ground_breaches`, from `refusals`). It reads the
scene the solve WOULD write -- the very plan rows `write_planned_layout`
writes (`structure.solved_plan_row`, `made_plan_row`), laid on the fringe's
own stubs (`solved_scene`; one rule, two readers, guarded by
`tests/test_the_grounds_floor_reads_what_is_written.py`, on the stair
fixture and on the farm's ground rows: a composite garden, a round oak's
cell pins, a window onto the ground, a way one side alone declares) --
through the world's own readers, and refuses a solve unless every place
handed to the solver is laid, each is one floor, and every level way between
two laid places with a ground place on either side has its doorways on
opposite walls, the cell beyond one a doorway cell of the other -- and every
laid place is reached from a room of the building through doorways that
meet. A window onto the ground is a sightline. The building's own rooms and
halls are the solver's to join and are not judged here; a room's doorway
onto a place of the ground is the floor's to judge (`refusals` leaves it to
the floor, which charges the place, never the house), and the floor is never
asked of a seed refused for the house. A refused solve is skipped like any
other, so the search takes the next seed. Where every seed is refused and
only the ground is at fault, the places that fail are taken out and the rest
solved again (`without_places`, up to `GROUND_DROP_ROUNDS`, 2, the owner's
ruling of 2026-10-13: "drop only the failing places"), the house alone
failing that. The places taken out are those of the seed whose refusals are
the ground's alone and that fails on the fewest places (`places_to_drop`),
read off the floor's own findings on each seed as the search made them.

**Which place is charged.** Where two places fail to meet, the more
particular gives way -- a thing, then a building apart, then a way, then open
ground (`_GIVES_WAY`) -- and of two as particular, the one less of the ground
hangs on, the ground the entrance opens onto weighing most of all (by id, the
court the entrance opens onto was charged for an orchard behind the house it
could not meet, and taken out with the lane and the shed). A room's door onto a place keeps the ground at its step for that
place -- the step, the pace past it, the paces either side of both, the
solver's aprons -- and a place standing on it that gives way before the
door's own place is charged instead (a lantern a pace below the entrance's
step left it a sliver no block held, and the court was charged and dropped
with every place reached through it; a band of open ground on the step was
never charged, and the whole ground was laid aside). Two places of the
ground that do not touch, with a thing, a way or a building between them
that touches both: what stands between them is charged -- never open
ground, which stands between nothing (a band beside the house touches the
ground before and behind it at the corners, and was charged round after
round while its going joined nothing). A place cut in two is charged to the
place whose own cells, given back, join its parts up -- most of them, then
the one the solver laid last (a building's block first, then the ways the
ground is laid round, the things, and last the walks and the ways that
branch), then the most particular; against a way, a building it was laid
over gives back nothing (a gate at the path's foot was charged for a walk
that cut the garden round the back of the house, and a storehouse for a lane
laid through it). Never a place the cut place hangs on: its going takes the
place too, and everything hung on that (a path cutting a pocket off the
garden it alone reaches was charged, and the garden and the oak went with
it). A thing on a way's line -- across it, or where it leads -- gets no
credit for the cells on the way's lanes, which carry on the way's own cut (a
gate at the path's foot was charged before the path, a round spent). A
charge to a third place -- the one on a door's ground, between two
places, or cutting one -- is void where a place the breach is about is charged
for a breach of its own: it goes, and the breach with it (a court not one
floor and its step taken by a garden band: both were dropped, though the
court's going answered both); the breach still refuses the seed. A
building apart charged for its own doorway goes with the place standing on
its step where another breach of the seed charges that place already (a
yard band held the court's step and the byre's doorstep, and the yard and
the byre were both dropped, where the yard's going answered both) -- never
where nothing else charges it, which cost places a building alone would not
have. A place
reached from no room is charged to itself only where nothing else explains
it: one that would be reached once the places
charged for a pair it does not belong to are taken out refuses the seed and
is taken out by nobody. A place no chain of joins from a room of the
building reaches once the others are out goes with them, and is named with
them (`places_dropped`, the run record, the log).

**What a place taken out keeps.** It takes no ground from the rest and asks
no door of its own: the room's way onto it opens through a door the room has
already -- the entrance, or its door onto another place -- and only a room
with none opens onto the ground the building stands in, or the first ground
left (`_door_already`; given a band of its own, Home 6's dropped well took
the garden's whole south side, and the path through it failed too; given a
door of its own, a thing dropped for want of a wall asked the house for one
more, and the whole building was refused). It goes back to what the Room
planned: no site, its own estimate of its size where the solve's record kept
one, and no doorway pin the solve gave it -- and this holds for every place
an earlier solve of the building laid that this write leaves out, dropped or
set aside with the whole ground when the house is laid alone (left on its
old site, the rest of the ground, or the house itself, was laid over it;
`lay_out_buildings`). An unsited stub is laid by the band rule over its
neighbours' cells, and the lint reports it.

**What an earlier solve wrote.** A way the solve made -- a stair hall's, a
window's onto the ground, a way one side alone declares -- is the solve's to
make again or take back, never the plan's: read as declared, a window the
first solve made had the re-solve lay a door for it, and the room was
written two windows on one wall; and a one-sided way was taken back by every
other solve, and its place dropped (`_edges_of`, `planned_layout`'s
`made_edges`). A ground's own estimate of its size is the solve's record of
it once a solve stands, or none -- read off the row, every re-solve filed the
last solve's size as the Room's. A doorway pin the solve gives as None is
written None, never taken off the row: a beat's stub takes only the fields
the row's edge holds, so a cell taken off the row stayed on the stub, where a
cell outranks an offset (laid round the house and then as a band, the
court's doorway stood on its far row, eleven paces from the hall's); a way
one side alone declares, made again, replaces its old pin the same way.

**The rules that let common plans hold**, each the class, never Home 10:

- The approach is the way the entrance opens onto, whatever an answer says.
  The entrance is chosen before the second call is asked, and the call is
  told it with its front: it opens onto a way or open ground before a thing,
  which stands at a door, or a building apart, reached by a walk of its own
  (`entrance_of`: a lantern joined to the hall, its id sorting before the
  path's, took the entrance, and the building was refused; a barn did, and
  was dropped on every seed). No answer moves it -- the relate card states
  the entrance as fact -- and neither does a drop: re-pointed after the call
  had answered against another front, the entrance turned into the wall the
  answer had given the ladder, and the lane and the shed were dropped;
  re-pointed off a place taken out, onto the garden beside it, it faced a
  band the garden lay on the far side of, and the whole ground went. A place
  taken out keeps it, its way opening through the entrance door.
- A way one room of the house opens onto, and nothing else, leaves from that
  door as the approach leaves the entrance's -- three wide, out to the plot's
  edge, clear of the approach (`from: door`): a path the plan joins to the
  hall's south wall, the entrance opening onto the garden whose id sorted
  first, had nothing to run from or between, and was dropped.
- Open ground whose room has no wall facing it is reached round the corner:
  where the door onto it steps into the ground round the house, the strip of
  that ground beside the house on the door's side is its, where it reaches its
  band and the ground round the house stays one floor without it (a garden
  behind a hall whose back wall is a stair hall was dropped with the shed and
  the oak hung on it). A side the plan's way does not face at all -- the far
  side of the house -- is not reached, and that ground gives way.
- A way the plan joins only to open ground leaves it past its far edge on the
  side the plan states -- the side its ground lies where it states none, the
  front only for ground round the building -- (`layout_solver.WAY_BEYOND`, 10
  paces), in line with the entrance where the entrance's step is that ground
  and no way across it, never over a building, another way or another
  ground, leaving on another side of its ground where it would run through
  one; it is laid before every thing, with ground round it (`LEAVING_GROUND`,
  3 paces), so what the answers relate to it has it to stand by, and its
  mouth -- the edge it leaves from and the pace inside it -- is no thing's.
- An outbuilding joined to open ground stands in it, toward the end the plan
  bears it to (a block's `toward`), and opens onto it; the bands open ground
  takes are measured from the building the entrance is in. One a room opens
  onto stands on the side the plan's way to it faces -- the answer's side
  only where the plan states none -- toward its room's end of that side, as
  the plan's bearings lay the rooms out from the entrance's, the answer's
  join sides read where the plan states none (stood on the answer's other
  side, a privy's walk ran round the house and cut the ground). Where neither
  names an end, on the entrance's side it never stands centred before the
  entrance: it stands toward the end the answer names across that side, else
  the end of the house its room stands at, else past a corner (centred
  there, a privy the hall opens onto stood three paces before the door, and
  the floor dropped it). Elsewhere it stands centred, as it always has: at
  the end an answer named, a privy crowded the byre at the garden's corner.
  Outbuildings stand `BLOCK_GAP` (2)
  paces apart where they would crowd -- never on one rectangle nor one pace
  apart, where a door opens onto ground the world reads as no place; a block
  standing below ground alone crowds nothing (moved off a cavern's
  footprint, the lab's latrine moved with the order its rooms were listed
  in).
- A thing the plan joins to a room of the building stands across a door of
  its own in that room (`at_door`; the plan's join wins over the answer's
  relation). `_place_doors` lays it after the room's other outside doors, on
  the wall asked where a cell stands `THING_DOOR_GAP` (2) paces clear of them,
  else on another wall: one door carrying two of the plan's ways met only one
  of them. Where the plan also joins the thing to a way, the door may move
  along its room's outside walls, or turn to another, so the thing stands
  within `REACH_MAX` (2) paces of the way, its own ground laid over the gap
  (`_things_at_doors`; the turn is filed under `sides`, "sides are wishes");
  and where nothing fits at the door on its wall, the door turns -- the plot
  reaching past every outside wall of its room for it (turned to a wall the
  plot reached five paces past, a round yew six across was dropped). Never into a
  pocket the room's furniture walls off from its other doorways, never onto
  a cell another doorway arrives at, never scored as reaching the way where
  its run would cross the house -- and a round thing's step is a cell its
  circle holds, as the world reads it (`spatial_fov`'s round shape: a large
  yew stood with its step on a corner its circle leaves out).
- The ground at a door is no thing's: the step of every door onto open
  ground, the entrance's among them, the pace past it and the paces either
  side of both are kept from every thing but the one at that very door, and
  from every walk but the one the door opens onto.
- A door onto open ground opens onto it (`_doors_onto_their_ground`): where a
  room's wall facing its ground is another room's -- a stair hall along the
  whole back of the house -- and the door turned to a wall whose step is
  ground beside the house no area holds, that ground is the area's, reaching
  it round the corner; where the step is another area's, the door moves to a
  wall cell of its room whose step is its own ground, clear of the room's
  other outside doors.
- Where the world asks it (`narrowest`, the bridge's), every thing is laid at
  least two paces each way -- save a thing across a way, laid a pace thick on
  the way's last row and written two (`_widened`) -- and every walk and
  branch way two paces wide where it fits (`_wide_route`): the world reads
  no place narrower, so a way
  laid a pace wide was written as nothing -- every branch way, and a covered
  walkway between two doors -- and a thing a pace deep was widened on writing
  onto the ground kept at a door, and dropped. The lab lays them as it always
  has, so its liked shrine re-solves cell for cell; whether it should draw
  what the world now holds is the owner's call.
- An outbuilding reached from a room owns its walk.
- A place is one thing: `flank` and `along` are read as `by`.
- A thing `by` a way stands beside it on the side the answer gives, at its
  `end` if one is given -- read as the way's far end, Home 11's well stood
  across the path's foot and the lab's fresh runs 2 and 3 stood their wells
  in their torii -- along the way, never past its end (a lantern by a lane's
  far end stood just beyond it, half a pace east of its line, and the gate
  across that end was dropped); a side along a way's own line, and any side
  of a doorstep, which stands against the wall, is only a side. A way that
  gives up its end to what it leads to gives up the rows too, so a thing
  laid across its far end stands on the way (Home 11's torii stood on a row
  the path had given up). What a thing stands by is what the plan joins it
  to: an answer's relation to something the plan does not join it to gives
  way to the plan's join -- by the entrance, of a thing joined to the way the
  entrance opens onto, is by that way at its near end -- and a side of the
  building answered of a thing joined to a way or a thing is that side of it
  (a lantern the plan joins to the path, answered by the entrance, stood
  touching no path). By the entrance onto open ground stays by the entrance,
  whose step's ground is kept clear (read as by the ground, a lantern went
  nineteen paces off). A thing the plan joins to open ground alone stands IN
  it (`in`): by what the answer names, since standing there keeps the plan's
  join -- by the entrance only where its step can lie in that ground, the
  entrance opening onto it or onto a way, never onto other open ground (kept,
  it pulled a lantern to the corner of a garden nearest a door onto the
  court, and the lantern was dropped); on a side answered only where its
  ground lies there; and as far from everything as that ground allows only
  where nothing was answered (a bench answered by the kitchen went to the
  plot's far corner, a lantern answered north of the house stood where no
  court was). `across` stays held to the
  plan's joins: across a way stands on the way's line, out of the ground.
- Open ground lies round the building where a thing at a door stands in it,
  never unwritten solver ground.
- Every doorway pin reads a place's cells as the world reads them.

**Measured**, replaying each story's recorded answers on a copy of its
database (the harness reproduces each live solve on the previous HEAD first:
Home 10 8 of 8 sites, Home 9 22 of 22, Home 11 21 of 21):

| Story | Breaches at HEAD | Breaches now | Sites laid | Seconds at HEAD | Seconds now |
|---|---|---|---|---|---|
| Home 10 (chat 173) | 3 | 0 | 8 of 8 | 1.7 | 1.1 |
| Home 9 (chat 172) | 1 | 0 | 22 of 22 | 9.8 | 7.1 |
| Home 11 (chat 174) | 2 | 0 | 21 of 21 | 29.7 | 21.3 |
| Home 6 (chat 168) | 6 | 0 | 21 of 22, the well dropped | 37.9 | 55.6 |

Home 6's plan joins the well to the kitchen and to the lantern path, which
its solved house puts five paces apart -- past `REACH_MAX` -- so the well gives
way, and the garden, the path, the torii and the camphor tree are laid
without it. The cost of a ground that does not hold is time: at most
`GROUND_DROP_ROUNDS + 1` times `LAYOUT_SOLVE_SEEDS` solves, and
`LAYOUT_SOLVE_SEEDS` more for the house alone where that fails too --
sixteen, the floor run once on each seed (its findings kept for
`places_to_drop`, which never runs it again). On two hundred random plans
shaped like the suite's fixtures (the second review's own generator):
they now lay 903 of 1,053 places, where the tree before this design laid 425
and the tree the third review read 882; they refuse no building whole (47
before) and lay every place of 119 plans (44). Two plans lay fewer places
than the reviewed tree -- both answered against a front they were never
shown -- and twenty-five more; the third round's own fixes were fuzzed and
bisected the same way before they stood. The third round changed none of the
four stories' written rows. The lab's liked shrine and fresh run 1 re-solve cell for cell
(`tests/test_the_grounds_hold_together.py` pins the shrine); fresh runs 2
and 3 now stand their wells beside the path.

**Not held yet.** A way through open ground -- an approach out of the front
door across the garden round the house -- meets the ground on one side only:
a way's doorway onto a place is one wall, so the garden on the far side of
the path reaches it only round the house (Home 11: three paces east of the
path, an 85-pace walk). Opening both sides needs either a doorway on more
than one wall or the lab's own model, the ways and things standing in one
grounds room; the owner's call. A walk with no two-pace route is laid a pace
wide, and the floor refuses the seed. An outbuilding standing apart on a side
another band holds -- the bands are measured from the building the entrance
is in -- opens into that band; and one joined to open ground that the plan
bears no way, or a diagonal way, stands centred on its side, for the front
before the entrance (stood past a corner instead, a byre at the court's far
end lost its doorway; one a room opens onto does stand past a corner there). A way down from an upper room to a thing of the ground
-- an outside ladder -- is laid nowhere and judged by nothing: the seed stands
with no doorway for it. Ground beside the house no area holds is given to
the area a door opens onto, however large that makes it. And the lab draws
walks and branch ways a pace wide where the world now holds them two.

From the third review, left: the plan's entrance is its entrance room's
first outside place by id, so where that is a garden beside the path the
lore calls the approach, the call is shown a front on the garden and the
path leaves by a door of its own -- the first call could say which place
the front door opens onto, a card change and the owner's call; an answer
that puts the entrance's own ground on another side than the front it was
shown then loses that ground (two generated plans of two hundred, whose
answers were written without the payload). A thing across a way's near end stands between
the way and the ground it leaves, and is dropped -- the world reads a thing
as a place, never as passable. The strip of the ground round the house that
a door's ground takes can hold another room's step onto the ground round the
house, which then opens into the band, and where two doors share the face
toward the band the grounds would have to cross. A building apart charged
in place of a band on its doorstep can spend a round where its own place is
a band whose going gives the strip back elsewhere. An outbuilding's walk
asks its room for a wall no other outside door holds, and a room with none
left drops the outbuilding. And ground the plan reaches only by a way one
side alone declared keeps the earlier solve's site on the building's plan
once the Room re-plans that side without the way: no join reaches it, and
the building is refused for good -- as it was before the floor; taking it off
needs the write to take back the solve's made way with it.

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

## The lab's look, measured live (2026-10-15)

The owner asked whether the engine's shrines now came out like the layout
lab's liked one, and then: "Can we adjust it so it produces mostly similar
examples and then do actual engine tests on it and other structures that we
just ask the room to make." Measured first, on the three shrines the owner
had played (Homes 6, 9 and 11) against the lab's liked shrine: no house came
out comparable as a whole -- a similarity of 0.44 to 0.51, where the lab's
own fresh run scores 0.82 -- and the causes sat in every stage but the
solver's core.

**The cards offered values to copy.** The relate card's template read
`"storeys": [{"level": 1, "smaller": true}]`, and two of three answers made
the full second floor "under the roof", which moved the stairs and the
corridor; `"count": 1` left no fixture or window of 249 with more than one;
`"order": 1` stood on 30 of 33 joins. Every `<...>` and `a|b` in both cards
now says when to give a field and what may go in it, and the cards say so.
Live, six shrine answers of six marked the roof storey smaller and no
other; the copied order is gone.

**What the plan or the lore puts outside the walls is laid outside them.**
Every shrine laid its latrine in the house, though each plan had joined it
to the washroom across an authored distance (`near`) no other join of the
house carried. A walled room whose every join on its storey the plan states
apart (`_stated_apart`) stands apart from the building -- unless the word is
the plan's habit, written on more than half the joins between its walled
rooms (`_apart_habit`, `APART_HABIT_SHARE`; the outdoors and a solve's own
stair rooms aside). The habit was first read as "one word on every join of
the structure", and the final live round showed why not: a plan wrote
`near` on every join between its rooms and `far` on one way out of doors,
so `near` was not its only word, and the rule took the kitchen, the store,
two halls and both bedrooms out of the house. Read over the rooms' joins,
it holds as one ten-room building; nothing changes on the owner's
database or on the six other live plans. A room so stated apart is, on the
ground, a building apart in the grounds, an enclosed place the first call
says nothing of read as one (`hold_grounds`); below the ground, where no
yard lies between, a block of its own past the wall it is entered through,
as the lab's shrine has its cavern. The first call can say the same where only the lore does
(`stands: beyond`, `stand_beyond`, before the second call reads the
building); a room joined twice keeps its place and the building names it
(`stands_within`).

**A yard filed as a part of the map of its own is still the building's
ground.** Two live shrines of two filed the torii, the path, the well, the
garden, the tree and the latrine as `shrine_grounds` beside the house's
structure -- the owner's three plans had filed them with the house -- and
the grounds walk, reading the house's structure alone, laid none of them.
The walk now also reads a part of the map the building's own rooms open
onto, which no walled room of another part of the map opens onto and which
holds no building of its own (`_ground_parts`). It changes nothing on the
owner's database (nine buildings) or on two hundred generated plans (903 of
1,053 places laid, as before).

**What the answers say reaches the spec.** A join's `order` is written from
the room whose wall it counts (it was dropped when the other room's id
sorted first); the solver now weighs doorways asked in an order along one
wall (`_order_cost`, `ORDER_COST` 20, a wrong side's cost); a window's
count is the first call's; and the lore of the ground the building stands
in reaches all three calls.

**Live.** Through the harness on the owner's routing (the Room re-planning
each shrine from the cloned setup): one run of Home 11's setup came out
comparable to the lab -- similarity 0.869, 35 of 53 claims, every one of
the fifteen structural checks -- and the rest at 0.40 to 0.54. Six read
stage by stage, every stage against the others, found the spread in the
solver more than the calls: asked sides traded away (the washroom asked
west of the hall laid east in most runs, as the lab's liked shrine also has
it), stated sizes read as a floor the furniture lifts (the twelve-mat hall
laid at 16 to 25 mats), straight flights laid end-on to the wall they were
asked along, and the first seed that stands kept over a better one. The
calls' share: a plural with no number counted one, a wall's door order and
a thing by a window left out where the lore gave them, and "behind the west
end" read as the west side -- each now a clause in its card.

**Levers, trialled offline.** Every live run keeps its brief, sort and
relate answers, so each can be relayed through `lay_out` on a changed tree
with no model -- the relay reproduces the live solve exactly -- and a lever
was kept only where the lab's liked shrine and its three fresh runs still
re-solve cell for cell. Nine answer sets (the six live runs and the owner's
three recorded launches), baseline mean similarity 0.503 and 24.2 claims:

- *Kept: the best seed that stands, not the first* (`solve_for`,
  `turned_sides`). Every seed is solved, and of those standing with every
  stair landed the one that turned the fewest asked sides is taken. The
  chosen seed changed on two of nine and both improved (0.418 to 0.582, 23
  to 31 claims; 0.409 to 0.464); none fell. Its price: every building now
  pays what only the worst case did, four solves, about +4 to +23 s a
  building.
- *Kept: a thing joined to a room across ground keeps the answer's
  relation* (`_joined_apart`): the well the plan put `near` the kitchen
  stood at the kitchen's door, touched no path, and was dropped; it now
  stands by the path east of the front door, as the lore and the answers
  have it, the kitchen's door opening onto the ground it stands in.
- *Kept: a way with a door at each end is the walk between them*: a walkway
  the plan joins to the washroom and the latrine was sent out of the garden
  past its far edge, and the latrine, the walkway and the torii were
  dropped; it is now laid door to door, ten paces, nothing dropped.
- *Dropped: a stated size as the target and the ceiling.* It moved the lab
  and laid no hall nearer its stated twelve mats (1 of 7 in band before
  and after): the division's size cost (3·|ln ratio|) is too weak against
  side costs of 20 to 60, and the outline is still sized from furniture, so
  a cap only moves floor elsewhere.
- *Dropped: a heavier asked side.* It moved the lab's liked shrine and
  still could not put the washroom west: of 600 divisions the search tries
  on the lab's own spec, none holds the washroom west and the genkan south
  together. The limit is the division generator, not the weight.
- *Held for the owner: a straight flight runs along the wall it is asked
  against.* A cost of 4 keeps the liked shrine and fresh runs 1 and 3 and
  turns fresh run 2's three stairs to exactly the liked shrine's (0.38 to
  0.77 against it); on the engine's answers it gains one claim on average
  and stands one front door in the back wall. A cost of 20 gained five
  claims on average and left two buildings refused on every seed.

Read with the six attributions, the spread is the solver's more than the
calls': its stair search places one shaft at a time from the middle spot,
so two flights asked into one wall block each other's moves, and in four
of five specs its own objective ranks a back-wall pick first that the
descent never reaches.

**Other buildings.** A hospital, a lighthouse and a manor, launched from
scratch and planned by the Room: none was laid out. The hospital went
through the location path, which cannot say a storey; the lighthouse's
lamp room is planned round off its stair alone; the manor holds 32 rooms.
Each is the owner's call (`UNBUILT_WORLD.md` §2.43).

## The arrangement-first core (2026-10-15 to 19)

After the lab's look round the owner asked: "Just what the hell do we have
to do to have sensible layouts?" Then, on the proposal below: "I suppose you
can go ahead and try. but I'd rather get it mostly right the first try
rather than resolved."

**Why the old search could not.** The lab's solver works in four steps:
- it places the stair halls first;
- it carves the floor left into pieces;
- it drops rooms into those pieces at random;
- it keeps the best of about 600 tries.

A side or a size the plan asks for is one cost among many, so the house
swings with the seed. Over 14 shrine runs it turned 36 of 87 asked sides.
It laid a stated twelve-mat hall at half or twice its size. It left a room
nobody could reach in 7 of 18 layouts, and stood upper rooms over roof in
10. The spread was the search's, not the calls'.

**The core (`world/layout_arrange.py`, `solve_arranged`).** It lays each
building in one pass, with the same house every time, in three steps:
- **The arrangement.** Each storey is divided as a slicing tree of the
  plan's own relations: who stands beside whom, on which side, and in which
  order along a wall. An asked side is a constraint of the division, and
  gives way only when no division can hold it. Asks give way in a fixed
  order (`RELAX_ORDER`), and are given back where they need not have gone
  (`_relaxed`).
- **The sizes.** A dynamic program over each division sizes every room. A
  room the lore sizes is held within `STATED_BAND` (15%) of that size; any
  other room is sized from what it holds (`room_target`). A service room
  keeps its size and a flexible room takes the spare floor. A stair hall is
  its flight and a landing.
- **The storeys stack.** The ground is laid first, then each storey on the
  one below:
  - every room above the ground stands over a room or a stair hall;
  - a storey under the roof is smaller;
  - a flight arrives where the floor above needs it;
  - below the ground a storey is dug: its rooms lie under the house's
    footprint, with earth where no room stands (`Layout.earth`).

Doors, windows, furniture and the grounds are then laid by the lab's own
code. The seam is `layout_solver.solve_with`, over `_prepare`, `_materialize`
and `_finish`. The lab's `solve()` is that same code with its own search,
and re-solves its baselines cell for cell.

**Never worse than today.** `layout_bridge.solve_for` lays a building with
the core once. The old four-seed search (`lab_solve_for`) lays it instead,
with a warning on the layout, where the core:
- raises;
- passes its work budget (`ARRANGE_WORK_BUDGET`, 2.0 million table entries
  a building, counted rather than clocked, so the fallback is deterministic);
- or is refused.

A layout refused only for its ground keeps the core's house, with its
failing places dropped by `lay_out`'s rounds (`FALL_BACK_ON_GROUND = False`;
the owner's page showed this setting).

**The review, and the three rounds that answered it.** Four reviewers read
the core: its code, its drawings as houses, seven buildings it had never
seen, and the tests. They found 31 faults, 11 of them high:
- whole buildings refused where the old search laid them: outdoor doors
  that could not all hold, a floor above larger than the ground, a skipped
  storey, room ids that changed the result;
- unsided joins that blew the dynamic program past a gigabyte;
- a byre crushed to 8 m² of its stated 36 by the ladder hall beside it;
- the hospital's main stair, which could not be climbed;
- two caverns laid on the cells of one wall;
- on the shrine, a main hall open on three sides with no outside wall.

Round 1, robustness:
- the fallback;
- a per-storey work budget with mid-solve narrowing (`NARROW_WORK`);
- an unsided join read as one variant;
- tables shared across a flight's ends and across relaxations;
- a tier for turning a door outdoors;
- the ground grown to carry a heavier floor above (`LOOKAHEAD_GROW`);
- ranked down-sets;
- a 126-case regression gate.

Round 2, stairs:
- Every stair can be climbed. A straight flight whose rooms reach the same
  end becomes a U (`layout_solver.STAIR_FALLBACK`, never an L).
- A stair hall may take a landing past `LANDING_MAX`, at `LANDING_OVER_COST`
  a cell, up to `LANDING_OVER_CEILING` times its least area, and only where
  that buys a size or a side.
- An upper room stands over what its stair serves (`OVER_COST`).
- A one-room tower storey rises sheer.

Round 3, the ground's shape. Here the owner chose that the outline may
step, rather than rooms leaving their asked sides.
- A ground room may leave a strip of open ground (a porch, a recess, an L)
  at `NOTCH_COST` a cell and `NOTCH_STEP_COST` a corner, with at most
  `GROUND_STEPS_MAX` corners. A strip never lies under a room of the storey
  above and never seals a landing. Such strips are kept in `Layout.notches`,
  and every reader treats them as open ground: doors and windows face them,
  and the grounds lie on them.
- On the engine path, an open join between rooms opens at most
  `OPEN_JOIN_MAX` (3) cells of wall.
- A heart room with no outside wall is priced (`HEART_DARK_COST`).
- A block stands against the room it joins, and slides along the wall off
  another block on the same wall.
- Where the lore puts a cavern beyond the basement's wall, the cavern takes
  that wall from a cellar stair asked on it.
- A door with no asked side faces the shortest way to what it serves.

**Measured.** The new core against the old search, on 14 shrine runs
relayed from their recorded answers through `lay_out` with no model, plus
the 4 lab specs where a count is out of 18:

| | new core | old search |
|---|---|---|
| sense checks failed per shrine layout (of 23) | 5.06 | 11.3 |
| asked sides turned (of 87) | 1 | 36 |
| lore claims passed (of 742) | 516 | 355 |
| similarity to the lab's liked shrine | 0.519 | 0.503 |
| Seal Cavern beyond the basement's north wall (of 14) | 11 | 12 |
| layouts with a room nobody can reach (of 18) | 0 | 7 |
| median seconds per shrine through `lay_out` | 2.4 | 37 |
| fuzz places laid (of 1,053) | 932 | 903 |

Seven new plans were written as the Room would write them: an inn, the inn
without its office, a townhouse, a farmhouse with its byre, a hospital wing,
a watchtower and a merchant's house. All seven lay, with a median of 4.8 s.
The owner read the drawings beside the lab's and the engine's: "it looks
much much nicer", and then "it's much better than it was before we started
this workflow". What is left is in `UNBUILT_WORLD.md` §2.43.

## Tests

`tests/test_a_planned_building_is_laid_out_by_relations.py` (the tier, the
bridge, the beat after the solve through interpret, resolve and commit, the
scene the beat and the design job read, the registry and frontier races, the
re-plan and the derived neighbour, the story switch across a restore),
`tests/test_names_carry_no_owner.py` (the sort card), `tests/test_layout_solver.py`
(the L), `tests/test_body_cells.py` (the whole rectangle),
`tests/test_site_plan.py` (the converter), `tests/test_room_lint.py` (a pinned
anchor's wall share), `tests/test_a_building_stands_in_its_grounds.py` (the grounds: which
places, what each is, one place a cell as the world reads it, every doorway's
other side, a side by something, the re-plan, the fallback, the switch),
`tests/test_what_stands_apart_is_laid_apart.py` (a room across ground stands
apart, below ground a block of its own, `stands: beyond`),
`tests/test_a_yard_filed_apart_is_still_the_buildings_ground.py` (a yard filed as
a part of the map of its own), `tests/test_the_layout_cards_offer_nothing_to_copy.py`
(no example value in a template, the clauses, the order's writer, a window's
count, the ground's lore), `tests/test_a_thing_across_ground_keeps_its_place.py`
(a thing joined across ground keeps the answer's relation) and
`tests/test_a_walk_runs_between_its_doors.py` (a way with a door at each end).

The arrangement-first core has four test files of its own. Each new or
rewritten test fails with its fix taken back.
- `tests/test_the_core_never_lays_worse_than_the_lab.py`: the fallback on a
  raise, a budget or a refusal; the door-turn tier; the grown ground; a
  skipped storey; a corridor's end; unsided joins within budget.
- `tests/test_a_storey_below_the_ground_is_dug.py`: earth below the ground,
  and a cavern beyond its wall.
- `tests/test_a_stair_is_climbed_and_its_landing_reached.py`: the U for an
  unclimbable flight, the priced landing, a landing nobody reaches, the desk
  under its window, doorways spread, the sheer tower, an upper room over
  what its stair serves.
- `tests/test_the_ground_may_step_and_the_heart_keeps_a_wall.py`: the
  outline steps, a notch as open ground for every reader, the heart's wall,
  the three-cell open join, the placing and sliding of blocks, the
  entrance's tie-break, the latrine door, the stair-head price.

Two tests pinned the old search and were rewritten:
- the four-seed loop is now the fallback's
  (`test_a_planned_building_is_laid_out_by_relations.py`);
- a woodpile the old geometry dropped is laid
  (`test_the_grounds_keep_their_doors.py`).
