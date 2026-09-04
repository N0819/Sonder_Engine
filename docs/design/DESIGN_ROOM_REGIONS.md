# Reading the world by region

**Status:** argument, not built. Written 2026-09-04, after measuring what the
Story Planner actually pays to look at a world.

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
