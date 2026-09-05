# Reading the world by region

**Status:** partly built (2026-09-04, `world/regions.py`): the region as a
FIELD on every room, derived and never named, the registry of what the regions
are, the index grouped by region, the briefs naming it, the in-pieces
contradiction and the one-shot backfill. Still argument: `inspect_regions`
(§5), the `region` argument on `inspect_rooms`, and a writer for a region's
brief. Written 2026-09-04, after measuring what the Story Planner actually
pays to look at a world.

*Built, 2026-09-04, later still -- and one ruling in §6 reversed.* The owner
asked for regions as THE grouping the index, the coming World Browser and the
planner all use, and for the grouping to cover the room this note had no
answer for: a live room the Director minted. §2 held that membership was
already recorded, and it was -- for PLANNED rooms. A minted room has no
`planned.structure`, and chat 115's second lift car was minted. So the
built shape is one field, `region`, on every room (`scene.rooms[id].region`;
`room_registry.payload.region`, kept on retirement), derived at commit by
rules that never read a name: a planned room's is its structure, a minted
room's is inherited from the room it was reached from (the occupied room
deciding a disagreement, a disagreement with no occupied neighbour left
empty), an inside reports its holder's room's, a `zone` is folded once into a
region and stays the frame-split trigger it was, a Director-written `region`
is a declaration and is kept. Nothing is invented: a room joined to no
regioned room has none, and the index shows `region: null` rather than
hiding it (§5's residue rule, honoured).

The reversal is §6's first line. There IS a `regions` world key now:
`{region_id: {name, brief}}`, frame-scoped like the scene, with every planted
structure read through as a region rather than copied in -- a structure is
still the only spelling of a planned room's membership, so the collision §6
warned about does not arise, and the key exists to name what a folded zone or
a declared region is, which no structure can. Its `brief` is where §3's
authored intent could live; nothing writes it yet, and the bible argument
stands as the alternative. `room_index` rows carry `region` and the index is
grouped by it (regions ranked by their nearest room, so the cast's comes
first; hops then id within); `room_slice` carries `region` and
`region_name`; `planned_room_brief` and `planned_context` name it;
`inspect_contradictions` reports `region_in_pieces` -- one region's live rooms
in two components no edge or planned edge joins, a reachability fact. Measured
on a copy of the owner's database at the backfill (schema v36): 590 rooms in
105 scene rows, 194 regioned and 396 empty after, 0 before; 32 folded-zone
entries across 13 frame registries; 7 planted structures. `tests/test_room_regions.py`.

*Update, 2026-09-04, later the same day.* The two-tier read landed, but keyed
by DISTANCE rather than by region: `story/room_slice.py` gives `inspect_rooms`
an index of every room the story knows (live, planned, retired; holder; hops
from the cast) plus the full slice of every room within `FRONTIER_DEPTH_HOPS`,
and `room_ids` opens any room by id. Measured on the same chat 114: 12,109
characters flat (13,076 after the old cap) became 7,815 -- 5,474 of index for
51 rows and 2,284 of neighbourhood for 3 rooms -- under the cap with nothing
dropped. What this note argues for and is still unbuilt is the grouping BY
STRUCTURE: the index is O(rooms) at ~107 characters a row, so a story with
several hundred planned rooms will start losing the farthest index rows to the
cap, which is the point at which `inspect_regions` (O(regions)) earns its place
on top of the index rather than instead of it. §7's build order stands; item 3
becomes "a `region` argument on `inspect_rooms`, filtering the index and the
slices alike".

## 1. Where the cost actually is

Measured against the owner's database, not estimated:

| | rooms | chars | approx tokens |
|---|---|---|---|
| chat 63's live scene, raw | 24 | 48,704 | 12,176 |
| the same scene through `inspect_rooms` | 24 | 10,647 | 2,661 |
| chat 114's **planned** rooms, flat briefs | 50 | 11,572 | 2,893 |
| the same 50 as a region index | 50 | ~720 | ~180 |

Two things fall out of that table.

**The projection is already doing its job on the live scene** — 4.6x, and the
raw blob would blow the 12,000-character tool cap on the four largest stories
anyway. Nothing here is a complaint about that.

**The pressure has moved to the planned side.** Chat 114 has two live rooms and
fifty planned ones. A story the room has been working on grows its planned set
without bound while its live scene stays small, so the flat read grows and the
scene read does not. That is the number to attack, and it is the one a region
index attacks best: **its cost is O(regions), not O(rooms)**, so it stops
growing at exactly the point the flat read starts hurting.

## 2. The region already exists, and membership is already recorded

Nothing needs inventing for the grouping itself.

`world/structure.py` has structures — a key, a name, the charters that live in
them, a naming grammar, a planned ceiling. And every planned room already
carries its structure: `room_registry`'s payload holds `planned.structure`, and
`skeleton_rooms` reads exactly that to pull one skeleton back out.

In chat 114 that is 49 of 50 planned rooms already assigned, across two
regions (`moonlit_shore_district` 31, `uminchi_guesthouse` 18) with a single
straggler. So the index is **derivable today**, from data the planting path
already writes.

## 3. What is computed and what is authored

The split matters more than the feature, because getting it wrong is how this
codebase ends up with two ledgers for one fact (the P1/P2 `planning_needs`
collision, merged after both forks built their own).

**Computed, never stored.** What a region *contains*: how many rooms planned
and how many rendered, its charters, the open planning needs inside it, the
packages whose scope names it, the clocks due in it, its distance from the
player in hops. All of that is already somewhere; a second copy would be a
second thing to keep true. This is `composer.observations_from_render`'s rule
one level up — a second representation must not be able to widen what the
first one said.

**Authored, and it belongs in the bible.** What a region is *for*, and its
plot notes. `story/room_bible.py` is already the room's own memory of what the
player asked for, what was promised and planted, and what was decided against
and why. A region's standing intent is exactly that, keyed by structure rather
than free-floating. Nothing new to store, nothing new to roll back.

## 4. Relevance should be derived, not declared

The tempting version is a `plot_relevant` flag the Planner sets. It should not
be one.

A declared flag goes stale silently: the region the story left three chapters
ago keeps its flag until something thinks to clear it, and nothing ever does.
Derive it instead, from signals that cannot go stale because they *are* the
state:

- how far the player stands from it, in hops;
- open planning needs inside it;
- packages in scope, and clocks due there;
- proposals that name it;
- whether anything in it has been rendered yet.

The Planner's own note is then a tiebreaker on top of a computed ordering, not
the ordering itself. That is the same reasoning that made the voice gate
demand-driven rather than salience-driven: a model's judgment about what
matters is worth having *beside* a deterministic answer, never instead of one.

## 5. The read becomes two-tier

`inspect_regions` returns the index: one row per region with its name, the
authored summary and plot note, the computed contents, and its relevance
ordering. Roughly 180 tokens for chat 114's fifty rooms, against 2,893 flat.

`inspect_rooms` grows a `region` argument and keeps everything else. Expanding
one region of thirty rooms costs what that region costs, not what the world
costs, and the Planner asks for it only when the plan it is writing needs the
inside of that place.

Two details that decide whether this is honest:

- **The unassigned residue is surfaced, not hidden.** A room in no region is
  precisely a room the Director minted with no plan behind it — already a
  planning need. The index says how many there are and lists them; it must
  never quietly drop them, because that is the one class the room exists to
  notice.
- **A story with no regions degrades to one.** Chats 63, 64, 59 and 38 carry
  zero rooms with a structure — they predate the concept. The index must show
  a single implicit region holding everything rather than showing nothing,
  or the tool reads as broken on every story written before this lands.

## 6. What not to do

- **No `regions` world key.** The grouping is in the registry and the intent
  is in the bible; a third home is the collision this section exists to warn
  about.
- **No hand-authored membership.** The Planner naming which rooms are in a
  region would be a second spelling of `planned.structure`, and the two would
  disagree the first time a plan was revised.
- **Do not let the index replace the frontier.** `frontier_report` answers
  "what stands immediately ahead of the player", which is a different question
  from "how is this world organised". Both are cheap; neither substitutes.

## 7. Build order

1. `region_index(cid, frame_id)` in `world/structure.py` — pure, derived,
   testable with no model, including the implicit-region fallback and the
   unassigned count.
2. The bible gains a per-region note, read by the index and written the way
   every other bible entry is.
3. `inspect_regions` in `story/room_tools.py`, and a `region` argument on
   `inspect_rooms`.
4. The Planner's card learns the habit: read the index first, expand a region
   only when the plan needs its inside. One clause, and worth watching for a
   few replies rather than assumed — the card already carries a "small steps,
   few of them" instruction that this should sit under rather than beside.
