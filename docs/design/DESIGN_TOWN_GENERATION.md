# Design: a town generated from lore, and lived in before you arrive

**Status: production vertical slice built; remaining sections are proposals.**
The shared lived-location operation now performs lore-scoped qualitative
planning, deterministic closure, structure planting, Charter presimulation,
citation-grounded history and additive mid-story generation. The graphical
structure editor, access credentials and deeper calibration remain unbuilt;
[`FABLE_TOWN_IMPLEMENTATION.md`](FABLE_TOWN_IMPLEMENTATION.md) records the
implemented boundary. No schema change was required: both halves land on
stores that already ship (`world_states.charters`, `lore_entries`,
`world_events`).

Written 2026-08-21 against alpha 9.7.1, at `7fb55d1`.

Reference corpus: the Re:Zero World Info book already used as
`story/lore_structure.py`'s worked example — 300 entries, 354k characters,
6 sections, 9 subsections, 168 leaves, 116 `[›]` children. It is the reference
here for the same reason it is there: it is a real authored corpus at a real
size, with a real tree, and it is regular enough to reason about without being
so regular that the design only works on it.

Related, and none of it overridden:
[`DESIGN_INSTITUTIONS_AND_UPKEEP.md`](DESIGN_INSTITUTIONS_AND_UPKEEP.md) is
the simulator this stands on;
[`DESIGN_LIVING_WORLD.md`](DESIGN_LIVING_WORLD.md) §D is the obligation ledger
this deliberately does *not* duplicate;
[`DESIGN_PLACE_PURPOSE.md`](DESIGN_PLACE_PURPOSE.md) owns what a place is
*for*; [`DESIGN_PRESTORY_MEMORY.md`](DESIGN_PRESTORY_MEMORY.md) owns the same
question one tier up, for full characters.

---

## 1. The three halves, and why they are one feature

**Generation** turns authored lore into a running institution: a place, the
conditions it owes, the duties that serve them, and the people who stand them.

**Presimulation** runs that institution forward before the player first walks
in, so the people have somewhere to have been.

**Structure** preplans the graph they both need: rooms that exist, connect
and have a purpose long before anyone has described them.

They are one feature because each is nearly worthless alone. A generated town
nobody has lived in is a stage set — every relationship at its default, every
condition at full, every body rested and idle, which is exactly the "everyone
was waiting for you" feeling the whole off-screen programme exists to kill. And
a presimulation with nothing to simulate is a no-op: `schedule_charter_ticks`
already returns `None` with `charter_skip = "no_charters"` for every story on
disk today, because **no charter generator exists.** `charters_put` takes a
hand-authored registry, and hand-authoring a thousand-body town is not a
feature anybody will use twice.

---

## 2. What already exists (so the plan does not re-propose it)

| Piece | Where | State |
|---|---|---|
| Lore tree recovery from World Info titles | `story/lore_structure.py` — `parse_structure`, `classify_title` | **built** |
| Local-vs-global knowledge scoping | `lore_structure.derive_knowledge` → `(tag, range, locations)` | **built** |
| The institution primitives | `world/charter_model.py` — `normalize_upkeep` / `_post` / `_body` | **built** |
| Deterministic advance over any window | `charter_runtime.advance_snapshot` | **built** |
| Out-of-band epoch catch-up, guarded landing | `charter_runtime.schedule_charter_ticks`, `land_snapshot` | **built** |
| Author-facing validation | `charter_runtime.registry_warnings` | **built** |
| Read/write route | `GET`/`PUT /api/chats/{cid}/charters` | **built** |
| A place accruing history while unvisited | `living_world.owed_history`, consumed only at `agents/mapping.py:66` | **built** (floor) |
| Charter people on the physical carrier rail | `story/carriers.py` → `charter_runtime.carrier_entries` | **built** |
| Conditional edges, for checkpoints and access control | `world/spatial_barriers.py` | **built** |
| What a place is *for* | `world/place_purpose.py` | **built** (v1) |
| Cross-frame room identity, with a free-form `payload` | `room_registry` (`core/db.py:839`) | **built** |
| **A preplanned low-resolution room graph** | — | **absent. This document, §5.** |
| **A generator that writes a charter from lore** | — | **absent. This document.** |
| **A presim horizon and its trigger** | — | **absent. This document.** |

The honest summary: the simulator is finished and has no input. This feature is
the input.

---

## 3. Generation: the lore tree already answers most of the question

### 3.1 What a location leaf is

`derive_knowledge`'s central argument — quoted here because the generator
inherits it rather than re-deciding it — is that **section placement, not
keyword guessing, decides whether a fact is local.** `[›] Lugunica Currency`
is local knowledge about Lugunica because its author filed it under
`[🏰] Dragon Kingdom of Lugunica`, and nothing else in the file says so. The
module measured the alternative and rejected it: `guess_category` calls
Lugunica Currency a `mechanic`, and calls Costuul, Flanders, the Kararagi
City-States and the Holy Kingdom of Gusteko `mechanic`/`myth` — four real
places that would have lost their locality.

The generator therefore takes as input exactly what `derive_knowledge` already
returns `local` for. **No new classifier.** A location leaf plus its `[›]`
children *is* the specification of a town: the place, and the facts that are
true there and not elsewhere.

### 3.2 The mapping, leaf to charter

A charter is five primitives. The generator's whole job is filling them:

- **`place`** ← the location leaf. One leaf may become several rooms; room
  identity stays `room_registry`'s, and the scene blob stays the runtime
  authority. Nothing here is a second place model.
- **`upkeeps`** ← the conditions the leaf's children imply an institution owes.
  A child naming a granary, a well, a watch, a shrine, a smithy is a condition
  somebody keeps up. `normalize_upkeep` wants `drift_per_hour` (what neglect
  costs) and `service_per_hour` (what one competent body restores).
- **`posts`** ← the duties that serve them, with `serves` naming the upkeeps
  and `requires` naming the competence. `reports_to` names another *post*, not
  a person, which is what lets the generated hierarchy survive reassignment.
- **`bodies`** ← the people. Named figures in the lore seed a few; the rest are
  minted by `charter_identity`'s naming profile, which already exists and
  already refuses two bodies that would display the same name.
- **`priority`** ← the ordering of upkeeps under scarcity. This is the one the
  generator must not leave empty and must not guess flatly:
  `normalize_charter` appends unranked upkeeps in key order rather than
  dropping them, so a bad ranking is silent and a missing one is invisible.

The supply chain falls out of `draws_on`, which `normalize_upkeep` already
carries: *a baker with a full oven and no flour works at the rate the flour
permits.* A lore book that says a town imports its grain has, in that sentence,
specified a `draws_on` edge. This is where two-town trade routes come from
without inventing a trade model.

### 3.3 What generation must refuse

1. **It must not invent an institution the lore does not name.**
   `charter_runtime`'s docstring already states the rule — *"merely enabling
   off-screen life does not invent an institution; a stored registry with at
   least one item is the opt-in"* — and generation is a *widening* of what
   counts as authoring, never a removal of the opt-in. A lore book with no
   Locations section generates nothing and says so.
2. **Generated bodies are not cast.** They are Charter bodies. Promotion to a
   full character with a sheet, memory and psychology stays the existing
   deliberate act (`persist/commit_background.py`, `promote_after_addressed`).
   A thousand-body town must not be a thousand-character import.
3. **It must run through `registry_warnings`, not around it.** Every failure
   that function names — an upkeep served by no post, a display name belonging
   to two bodies, an institution with no bodies — is a failure a *generator*
   will produce far more often than a human author will. The generator's
   output is validated by the same code that validates a hand-written one, and
   warnings surface where the Institutions block now shows them
   (`static/js/settings.js`).

### 3.4 Where the model is and is not

Generation is **one call per town**, not per body — the same shape as the
mapping seam. The model reads the location leaf and its children and returns a
charter skeleton; `normalize_charter` then decides what that means. Body
minting, name assignment, post assignment, priority closure and the initial
watch are all deterministic afterwards. A thousand bodies costs one call
because nine hundred and ninety of them are `charter_identity`'s work, not a
model's.

---

## 4. Presimulation, and the finding that shapes it

### 4.1 The mechanism already exists

`advance_snapshot(registry, elapsed_seconds=..., epoch_id=..., base_turn=...)`
advances a whole registry over an arbitrary window and returns
`(advanced, rows, produced)`. Presim is *that function, before turn 0*, with a
chosen horizon instead of an elapsed epoch. `MAX_CATCHUP_HOURS = 720.0` is
already the ceiling; `DEFAULT_WINDOW_HOURS = 4.0` is already the step.

Cost is known rather than guessed: a 1000-body town over a simulated month
measured **~8.0s** after the `reach_map` and `assignable` fixes earlier in this
branch's history. That is off the turn path, once, at scene creation. Against a
single character model call at ~22.5s, a month of town history is cheap.

### 4.2 The finding: at shipped rates, a month of presim leaves almost nothing

This is the part that must be designed rather than discovered, so it is stated
plainly.

| Store | Rate | Time from first-hand certainty to forgotten |
|---|---|---|
| A body's claim about a person (`charter_mind`) | `PERSONAL_DECAY_PER_HOUR = 0.010`, floor `0.08` | (1.0 − 0.08) / 0.010 = **92 h ≈ 3.8 days** |
| A body's claim about an event (`charter_news`) | `NEWS_DECAY_PER_HOUR = 0.014`, floor `0.08` | ≈ **65.7 h ≈ 2.7 days** |
| The institution's roster belief (`charter_roster`) | archive floor `0.05` | slower, but bounded |
| Regard / standing / blame (`charter_politics`) | **no per-hour decay** | **persists** |

So a 30-day presimulation, run at the rates that ship today, produces a town
where **nobody remembers a single episode older than about four days.** Run the
horizon out to `MAX_CATCHUP_HOURS` and the episodic layer is uniformly empty at
arrival; you will have spent eight seconds to produce the same blank heads you
started with, plus a lot of `world_events` rows nobody holds.

This is not a bug in the decay rates. They are correct for their designed
purpose: a body circulating through `charter_move.errands` meets more people in
a window than it can carry, and forgetting the weakest is what keeps
`RECALL_CAP = 48` from being a quadratic disaster. A person *should* forget a
face in a week.

It does mean **presim's product is not memory.** What survives a long horizon
is:

- **Politics** — regard, standing, blame. Who is trusted, who is resented, who
  is owed. This is durable by construction and is the most valuable thing a
  presim can produce.
- **The institution's own books** — the charter's `reported` ledger, its
  roster, its `watch`. What the institution has written down survives what any
  individual recalls, which is the correct asymmetry and is exactly §5's
  argument for keeping the two stores separate.
- **Bodies as they now are** — where they live, what they are competent at, who
  stands which post, who was stood down by needs and has not recovered.
- **`world_events` rows** — the objective record, held by nobody, available to
  be *encountered*.

That is a defensible and rather good model of history: people carry how they
feel about each other and what they are currently doing, institutions carry
records, and the episodes themselves are gone unless something wrote them down.
It is close to true of real towns. But it has to be chosen.

### 4.3 Two horizons, therefore, not one

**A long horizon (weeks to a month) for the durable layer.** Run it to
establish politics, wear, standing, who has replaced whom. Accept that the
episodic layer decays away, and do not pretend otherwise.

**A short tail (the last 2–4 days) for the episodic layer.** The final stretch
before arrival is what any head can still hold, and it is where the news a
scene manager can actually use comes from — `known_news(minds, holder)` is that
manager's raw material, and it will be empty for anything older.

Concretely: `presim: {horizon_hours, tail_hours}`, with the tail defaulting to
about 96 h — just above the 92 h a first-hand claim survives — so the tail is
defined by the decay constant rather than by a number somebody liked. If the
constants change, the default follows them; that is worth a derived default
rather than a literal.

### 4.4 The alternative worth considering, and why it is deferred

The other way to make a long horizon pay is a **consolidation step**: the
Charter equivalent of autobiographical memory, turning decayed episodic claims
into durable disposition before they cross the floor. `charter_log.summarize`
and `life_of` are already pure summarizers over an event list, so the raw
material and the summarizer both exist.

It is deferred because it is a second memory system, and this repo has one
already, one tier up, with a proposal attached
([`DESIGN_PRESTORY_MEMORY.md`](DESIGN_PRESTORY_MEMORY.md)). Building a parallel
one for Charter bodies before that lands is how the two drift. Revisit after.

---

## 5. Preplanned structure: a graph before it is a place

### 5.1 The observation this rests on

`charter_space.travel_rooms` calls `passable_path(scene, a, b)` and reads
nothing else. `reach_map` walks the same graph. `charter_move.walk` and
`errands` move bodies along it. **Not one of them reads a room's description,
its entities, its lighting or its attire.** They read `adjacent`.

So a room can exist, be navigated, be posted to, be walked through, be somebody
in a presimmed body's history — all before anyone has said what it looks like.
The expensive half of a room is the half the simulation never touches.

That is the whole feature: **structure is cheap, prose is expensive, and they
do not have to be built at the same time.**

### 5.2 Three resolutions, one graph

- **`planned`** — a key, a display name, `adjacent` edges, and a purpose.
  Sufficient for `reach_map`, post assignment, `charter_move`,
  `place_purpose.affords_here` and the whole of presim. No description, no
  entities, no barriers beyond the edges themselves. Costs a few hundred bytes.
- **`resolved`** — what every room is today: generated at the mapping seam on
  first entry, with prose, entities, lighting and barriers. Costs one model
  call, paid exactly when somebody arrives.
- **`frontier`** — an **edge that names no room yet**. The expansion point.
  Walking it mints a fresh `planned` room from the structure's grammar, which
  then resolves on entry like any other. This is what makes the extent
  unbounded without making the preplan unbounded.

A frontier edge is an *opening*, not a wall — the engine's existing rule, and
the reason this must be modelled as an edge with no destination rather than as
an absent edge. An absent edge is a wall, and a facility whose unexplored
corridors read as walls is a facility with no exploration in it.

### 5.3 Where it lives — again, no schema change

`room_registry` already carries `payload TEXT NOT NULL DEFAULT '{}'` and
`parent_entity`. The skeleton's fields go in the payload:

- `resolution` — `planned` | `resolved`
- `purpose` — short and structural, feeding `place_purpose`, never prose
- `structure` — which preplanned structure this node belongs to
- `frontier` — edge labels that name no destination yet
- `grade` / `access` — the checkpoint fields, if the structure has them

`parent_entity` already nests, which is how an underground facility hangs off a
surface site. `world.scene` stays the runtime authority for live rooms and
`room_registry` stays the cross-frame identity ledger; the skeleton is
registry-side, which is the correct home for something that exists across
frames and has never been entered.

### 5.4 A structure is a grammar, an extent, and a charter

Stated generally, because the user's ask is "preplan any structure" and the
mechanism should not know what a town is:

- **Grammar** — what kinds of node this structure has, and what may connect to
  what. A containment wing reaches a checkpoint; a checkpoint reaches an
  elevator bank; residential does not open directly onto containment. This is
  the part a model writes, once, per structure.
- **Extent** — how far it goes, and in which directions. Depth is the
  interesting axis for the underground case: levels, with vertical links that
  are deliberately chokepoints. Horizontal extent is where frontier edges live.
- **Charter** — the staffing. §3's mapping applies unchanged: containment
  integrity, power, air and supply are `upkeeps`; guard, researcher, custodian
  and engineer are `posts` that `serve` them; personnel are `bodies`. An
  SCP-style facility is not a new subsystem — it is a preplanned graph with a
  charter over it, and both halves already have their machinery.

Access control needs no new model either: a checkpoint is a room whose edges
are conditional, and `world/spatial_barriers.py` already does conditional
edges.

### 5.5 The discipline: preplanning must not pre-describe

The failure mode is obvious and tempting. A generator that emits a planned room
with two sentences of atmosphere has produced a **resolved room that nothing
checked** — bypassing the mapping seam, the style guide, the lore hits and
`owed_history`, all of which exist to make a room's first description correct.

A planned room gets a name and a purpose. Both short, both structural, neither
prose. This is the same discipline the obligation ledger already keeps:
history accrues while a place is unvisited, and **arrival is the earning
event.**

### 5.6 What this buys presim

A presimmed body walks planned rooms. Its history therefore names places the
player has never seen — the guard who transferred up from Level 4 has a real
prior posting, and Level 4 is a node with edges and no prose until somebody
goes there. `charter_log.life_of` will name it; the Director resolves it if the
player follows.

That is the strongest single argument for building the skeleton before the
presim rather than after: a presim over a one-room town produces a body whose
entire life happened in the room you are standing in.

### 5.7 The catch worth naming now

`REACH_LIMIT = 8` — a charter will not roster a body onto a post more than
eight rooms away, on the stated grounds that *an institution does not roster a
body onto a post it cannot get to and back from.*

A deep facility with a twenty-room path from residential to containment
therefore generates **posts that nothing can ever reach**, and
`registry_warnings` will not catch it, because unreachability is a spatial fact
and that function validates charters. The generated town looks valid, presims
quietly, and produces a facility permanently unstaffed below Level 2.

Either the generator places posts within reach of the homes it assigns, or deep
structures need local sub-populations who live where they work — which is
probably the truer answer for an underground facility anyway, and is what
`normalize_body`'s separate `home` field is already for. Whichever, it needs a
warning of its own: this is a generator-shaped failure that no hand author
would produce.

---

## 6. The firewall, stated for this feature specifically

Presim generates a great deal that the player must not receive for free.

1. **A presim event is not player knowledge.** It enters `world_events` and
   reaches the player exactly as any other event does — by their being there,
   or by someone telling them. `story/carriers.py` already enforces this and
   already carries unpromoted Charter bodies. Presim changes only that there is
   a backlog; it introduces no new delivery path, and **must not**.
2. **`WITNESSABLE` stays an allowlist.** Its docstring is explicit that the
   rest are register facts a body in the room has no way to perceive, and that
   getting the list wrong is a leak. Presim will fire orders of magnitude more
   events than live play; the allowlist is what stops volume becoming leakage.
3. **A presimmed body's history is its own.** `charter_mind.hear_claim` remains
   the one uptake door — thinned by retention, scaled by regard, refused below
   the floor, never overwriting a stronger holding. Presim uses it. There is no
   bulk-seed path that writes `minds` directly, because a second uptake path
   with its own arithmetic is how the two authors drift apart.
4. **Generation reads lore the player may not know.** A location leaf can be
   `esoteric`; `derive_knowledge` already tags it. A generated body's
   *competence* may come from a fact the player has never heard — that is fine,
   because competence is a property of the body, not a claim in anyone's head.
   What must not happen is a generated body *holding* an esoteric claim merely
   because the lore entry that seeded its post was filed under Authority.

---

## 7. Staging

**Stage 0 — the skeleton.** A structure grammar and a preplanned graph in
`room_registry.payload`, with frontier edges. Verifiable with no model and no
simulation: the graph is connected, `passable_path` crosses it, planned rooms
carry no prose, and a frontier edge reads as an opening rather than a wall.

**Stage 1 — generation, no presim.** Lore tree → charter registry → the
existing `charters_put` path, validated by `registry_warnings`. Verifiable
entirely by the shape of what comes out, with no simulation involved. The
Institutions block already renders the result.

**Stage 2 — presim with the two horizons.** `advance_snapshot` before turn 0,
`{horizon_hours, tail_hours}`, tail defaulting off `PERSONAL_DECAY_PER_HOUR`.
The falsifiable acceptance test is not "feels alive": it is that after presim,
`charter_politics.regard_map` is non-uniform, `known_news` is non-empty for
bodies present at recent incidents and empty for old ones, and at least one
post is standing a body that is not its original.

**Stage 3 — the seam to play.** Generated towns become the input to the
existing scene-manager path, which already reads `scene_ledger` and
`known_news`. Nothing new; this stage is where the first two get exercised.

**Not in scope:** consolidation (§4.4), any second place model, any change to
promotion, and any new delivery path for off-screen news.

---

## 8. Open questions

1. **Who triggers presim?** Scene creation is the obvious point, but a town the
   player reaches on turn 400 wants presimming *then*, not at turn 0 —
   otherwise it has been ticking for four hundred turns or has been frozen. The
   `place_obligations` ledger solved the same problem by making **arrival the
   earning event** (`agents/mapping.py:66`), and that is probably the answer
   here too: presim at first approach, not at world creation.
2. **What horizon does the lore itself imply?** A book that says a town was
   sacked eight years ago is asking for a state, not a simulation of eight
   years. Presim should probably take a *starting state* from lore and simulate
   only the recent past on top of it.
3. **How many towns?** `CROSS_CHARTER_GOSSIP_CAP = 8` already bounds exchange
   between institutions sharing a place. The multi-town case is built; what is
   unanswered is whether presimming ten towns at scene creation is acceptable
   at ~8s each, or whether §8.1's arrival-triggered answer makes it moot.
4. **Does presim need its own `offscreen_life` rung?** Charter today runs at
   `deterministic` and above. Presim is more expensive and more consequential
   than a catch-up tick, and might reasonably want its own opt-in rather than
   riding the same gate.
