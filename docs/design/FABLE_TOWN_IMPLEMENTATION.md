# FABLE_TOWN_IMPLEMENTATION — the plan for towns generated from lore, lived in before arrival, and preplanned past the walls

**Status: first production vertical slice built 2026-08-22.** Planned/live
graph composition, fringe materialization and deterministic frontier growth;
qualitative one-call town closure; coarse-plus-recent presim; bounded physical
history interventions; citation-grounded post-run history; local social
judgment, commitments, abstract markets/caravan freight, institutional orders,
author diagnostics, opt-in creation/greeting presim, and additive lorebook-
scoped mid-story location generation now ship. Added locations deterministically
namespace collisions and presimulate only their own new Charter slice. The
graphical structure editor, route access
credentials and richer long-run calibration remain follow-up work. This document turns
[`DESIGN_TOWN_GENERATION.md`](DESIGN_TOWN_GENERATION.md) into a build order,
and disagrees with it in four places, each argued below. Written 2026-08-21
against the `offscreen-charter-prototype` branch, with every load-bearing
claim checked against source; citations are `file:line` as of this branch.

Related: [`DESIGN_INSTITUTIONS_AND_UPKEEP.md`](DESIGN_INSTITUTIONS_AND_UPKEEP.md)
(the simulator), [`DESIGN_LIVING_WORLD.md`](DESIGN_LIVING_WORLD.md) §D (the
obligation ledger), [`DESIGN_PLACE_PURPOSE.md`](DESIGN_PLACE_PURPOSE.md),
[`DESIGN_PRESTORY_MEMORY.md`](DESIGN_PRESTORY_MEMORY.md).

---

## 0. Verdict, and the four disagreements that shape the plan

The design note is right about the big things: the simulator is finished and
has no input; structure is cheap and prose is expensive; presim's product is
not memory. The plan below keeps its staging spine. It is wrong or silent
about four things that change the build:

1. **A frontier edge cannot be "an edge that names no room yet" in the
   scene.** `prune_dangling_exits` (`persist/commit_room_registry.py:406`)
   drops, at every commit, any `adjacent` edge whose `to` is not a room in
   the scene — deliberately, because a dangling exit is offered to the
   Director and narrator as real and then resolves against nothing. A
   literal no-destination edge would be pruned the first beat after it was
   authored. The frontier must live structure-side (registry payload), and
   the scene must only ever see edges whose destination exists — which the
   **fringe materialization** rule in §2.3 provides.

2. **The note says the skeleton is registry-side (§5.3) and never says how
   the charter keeps walking it.** `advance_snapshot` *replaces* the
   charter's scene with the live scene whenever the live scene has rooms
   (`world/charter_runtime.py:233-247`, the replace at 236). The live scene
   at any moment is the resolved handful of rooms, so the moment play
   begins, a registry-side-only skeleton vanishes from the graph the
   planner, `reach_map` and `errands` walk, every post at a planned room
   becomes unplannable, and `registry_warnings`'s place check
   (`world/charter_runtime.py:150-160`) flags every planned place as "not a
   room in this frame". The fix is a **composed travel graph** (§2.2):
   skeleton nodes merged under live rooms by shared `room_uid`, live
   definitions winning. This is the single largest piece of new machinery
   in the plan and the note does not contain it.

3. **`tail_hours` as a second duration changes nothing.** Decay is a pure
   function of the one continuous run; the last 96 hours of a 720-hour
   simulation hold exactly what they would hold if you called them "the
   tail". What actually differs between the durable layer and the episodic
   layer is *resolution*, and the engine already has the dial:
   `active_places` (`world/charter_run.py`, the practices gate) and the
   window size. So presim takes **one horizon and a resolution schedule**
   (§3.5): coarse windows and no active places for the body of the run,
   fine windows and active places for the final stretch. The
   decay-constant-derived default for that stretch is kept — that part of
   the note is right.

4. **The finding's first table row overstates.** `converse` calls `see` for
   every co-present pair every window (`world/charter_talk.py:230`), and
   `see` writes a fresh full-strength first-hand claim
   (`world/charter_mind.py:64`). So a body's claim about a person it keeps
   *meeting* survives any horizon; the 92-hour figure applies only to
   people it stops seeing. What a long presim actually leaves is:
   acquaintance among the co-circulating (refreshed), politics
   (`world/charter_politics.py` — verified: no function in the module
   decays regard, standing or blame per hour; only `attribute_blame` and
   practice effects move regard), the institution's books
   (`ARCHIVE_FLOOR = 0.05`, `world/charter_roster.py:42`), `stood`/
   `travelled`/`watch`, and the `world_events` record — and **no episodes**:
   news decays at `NEWS_DECAY_PER_HOUR = 0.014` to the 0.08 floor in
   ≈ 65.7 h (`world/charter_news.py:52`, `world/charter_mind.py:36`), and
   retelling cannot resurrect it because `hear_claim` only accepts a claim
   *stronger* than what is held and retold strength is the teller's
   decaying copy × `RETOLD_RETENTION` (0.6) × regard
   (`world/charter_mind.py:100-121`, `world/charter_talk.py:39`) — the
   chain is monotone downward. The note's conclusion (durable relationships
   and records, no episodes) stands; its mechanism needed the correction,
   because "nobody remembers a face after four days" would have argued for
   a fix the engine does not need.

Two smaller disagreements are argued where they land: presim triggers at
**generation**, not at first approach (§3.4, against note §8.1), and the
generator's model call must emit **timescales, not rates** (§4.2, against
the note's silence — an authored `drift_per_hour` from a model is exactly
the "authored number that fails silently" class CLAUDE.md documents).

---

## 1. The finding, re-verified with the shipped constants

| Store | Constant | Time to floor, unrefreshed | Refreshed by |
|---|---|---|---|
| Person-claim in a head | `PERSONAL_DECAY_PER_HOUR = 0.010`, floor `0.08` (`charter_mind.py:33,36`) | (1.0 − 0.08)/0.010 = **92 h** | `see` on co-presence, every window (`charter_talk.py:230`) |
| News-claim in a head | `NEWS_DECAY_PER_HOUR = 0.014` (`charter_news.py:52`) | **65.7 h** | nothing — retelling is monotone-losing |
| Institutional roster | decay 0.004/h, `ARCHIVE_FLOOR = 0.05` (`charter_roster.py:30,42`) | never erased; unstakeable below `TRUST_FLOOR = 0.2` | `observe` on a stood post |
| Regard / standing / blame | no per-hour decay (whole of `charter_politics.py`) | **persists** | — |

So the two-layer model is confirmed with one amendment: **the episodic layer
is the only thing a long presim loses.** Acquaintance, politics, books,
service records and the objective event log all survive. That is the correct
product and the plan designs to it: the long stretch buys the durable layer,
the short high-resolution stretch buys the episodes a scene manager can use
(`known_news`, `charter_news.py:262`; `can_bring_up`, `charter_log.py:290`).

Cost re-verified from the branch's own record: ~8.0 s of CPU for a
1000-body town over a simulated month (note §4.1, after the `reach_map` and
`assignable` fixes; `tools/charter_audit_scale.py` is the harness — keep
measuring there, per `AGENTS.md`'s charter row).

---

## 2. Architecture: where the skeleton lives, and how it meets the live scene

### 2.1 Three homes, one graph, no schema change

- **`room_registry` rows are the durable identity of planned rooms.** One
  row per planned room, `payload` carrying the skeleton fields (schema at
  `core/db.py:839`; free-form `payload TEXT`, `parent_entity` already
  nests). The registry is the cross-frame ledger of room identity — exactly
  the right home for rooms that exist before any frame has entered them.
  Archive/branch/checkpoint coverage is already built:
  `persist/chat_archive.py:67,1010` carries the table, `web/app.py:5444`
  remaps its turn FKs on branch. **One new test, not new plumbing**: a
  checkpoint restore and an archive round-trip must preserve planned rows
  and their payloads (restore reconciliation
  `sync_room_registry_with_scene`, `commit_room_registry.py:329`, only
  touches rooms named in a scene, so planned rows pass through — pin that).

- **A `structures` world-KV key holds the grammar and extent** — the part
  that is not per-room: node kinds, what may connect to what, depth,
  frontier axes, the owning charter key. World KV rides every existing
  persistence path for free.

- **The live scene holds only resolved rooms plus the materialized fringe**
  (§2.3). The scene blob is served whole into mapping and Director payloads
  (`agents/mapping.py`, `payload["scene"]`), so a 200-room skeleton must
  not live there: structure would ride every prompt and every commit.

### 2.2 The composed travel graph (new: `world/structure` (new))

New module, sibling vocabulary to `world/spatial.py` but deliberately not a
`spatial_*` sibling — it is not scene physics, it is pre-scene planning:

- `normalize_structure(stored)` — grammar/extent/charter-binding, total.
- `skeleton_rooms(cid, structure_key, frame_id)` — read planned rows for
  one structure from `room_registry`, return a `world.spatial`-shaped
  `{"rooms": {uid: {"name", "adjacent": [{"to", "barrier"}]}}}` graph.
- `composed_scene(skeleton, live_scene)` — merge: live rooms override
  skeleton nodes of the same `room_uid`; skeleton edges to planned nodes
  are kept; live edges win where both define the same pair. Pure, cheap,
  cacheable per (structure revision, scene revision).
- `mint_frontier(structure, from_uid, axis, seed)` — deterministically mint
  one new planned node from the grammar at a frontier edge. Same
  determinism discipline as `charter_move._roll`
  (`world/charter_move.py:43-63`): seeded, never `hash()`.

**One change inside `charter_runtime.advance_snapshot`** (the replace at
`charter_runtime.py:236` becomes a compose): when the registry item's state
names a `structure`, `state["scene"] = composed_scene(skeleton, live_scene)`
instead of the bare live copy. Everything downstream —
`charter_space.travel_rooms` reading `adjacent` via `passable_path`
(`world/charter_space.py:31`, `world/spatial_routing.py:655`), `reach_map`
(`charter_space.py:65`), `errands` (`charter_move.py:102`), the planner's
reach filter (`charter_plan.py:87`) — works unmodified, because the note's
central observation is verified true: none of them reads anything but
`adjacent` and each edge's `barrier`.

That last clause is the one the note under-states: **`passable_path` reads
barriers too** (`spatial_routing.py:680`, `_PASSABLE_BARRIERS = {open,
open_door, membrane}` at `world/spatial_barriers.py:430`). A checkpoint
modelled as `closed_door` is a *wall* to the charter — worse than
`REACH_LIMIT`, it makes everything behind it permanently unstaffable. So:
**skeleton edges are always emitted passable** (`open_door`), with the
access constraint recorded as data (`access` in the payload) for the mapping
seam to realize as a real conditional barrier at resolution. What happens
after resolution mints a genuinely closed door across a staffed path is an
open question (§8, Q1) — "staff have keys" is true in the fiction and
unrepresented in the engine.

`registry_warnings`'s room check (`charter_runtime.py:150-160`) takes the
composed graph instead of the bare scene at both call sites
(`web/app.py:4583,4598`), so planned places validate instead of
false-positiving.

### 2.3 Fringe materialization: how planned rooms reach the scene

The rule, stated once: **the scene holds what is at hand; the registry holds
what exists.** At commit, after positions land, a new deterministic pass
(`materialize_planned_fringe`, in the `commit_room_registry` domain) ensures
every planned neighbor of an occupied room exists in the scene as a **stub**:
`{name, adjacent, planned: true, purpose}` — no desc, no entities, ~150
bytes. Consequences, each on existing rails:

- Exits to planned rooms are real scene edges to real scene rooms, so
  `prune_dangling_exits` never fires on them, the narrator can honestly say
  the corridor continues, and a frontier reads as an opening, not a wall.
- Entry resolves the stub through the ordinary mapping seam: the stub's uid
  is in `prev_scene.rooms`, so `dedup_minted_rooms`'s same-scope slug match
  (`commit_room_registry.py:132`) redirects mapping's freshly minted full
  definition onto the planned uid, and the scene merge overwrites stub with
  prose. **Resolution is not a state machine; it is the redirect working.**
- One real gap to close: `dedup_minted_rooms` consults the *registry* alias
  index only for anchored-entity books (`commit_room_registry.py:195-205`) —
  open-location rooms dedup only against the current scene. A planned room
  not yet materialized (player asks about the granary from two rooms away)
  could be re-minted beside its registry row. Fix the class, not the
  instance: extend the registry consult to the location/canon book for
  open-location mints. That also hardens ordinary (non-town) re-mints.
- `resolution` is **derived, not commanded**: `_prepare_room_registry`
  (`commit_room_registry.py:223`) flips the row's payload to
  `resolved` in the commit where the scene room first carries prose. A
  stored flag someone must remember to flip would drift; a flag derived
  from "does the room have a description" cannot. (`_apply_room_registry`
  currently writes payload only on insert — the flip is the one payload
  UPDATE this plan adds.)

Mapping needs to know what it is resolving. The seam already exists and is
already the precedent: `attach_owed_history` at `agents/mapping.py:66-67`.
Beside it, a `planned_context` block enters the mapping payload when the
target room is planned: `{name, purpose, structure, access, adjacent
names}` — short and structural, never prose, per the note's §5.5 discipline,
which this plan keeps verbatim: **a planned room gets a name and a purpose;
prose is minted only at the seam, where the style guide, lore hits and
`owed_history` apply.**

### 2.4 Frontier

A frontier is a payload field on a planned (or resolved) row: edge labels
naming no destination. On approach — the player enters a room whose row
carries frontier labels — the same fringe pass calls
`mint_frontier` to convert each label into a fresh planned row + edge, and
materializes it as a stub. The extent field bounds total planned rows per
structure (`max_planned`), so unbounded exploration never becomes unbounded
storage; storage grows with *approach*, the same shape as "storage grows
with incident".

---

## 3. Presim

### 3.1 Mechanism

`charter_run.run` (`world/charter_run.py:466`) is the whole engine; presim
is that function before the story clock starts. It is **not**
`advance_snapshot` re-used as-is: `advance_snapshot`'s first touch of an
item only stamps `last_elapsed_seconds` and advances nothing
(`charter_runtime.py:223-227`), and its window arithmetic is anchored to
epoch elapsed time. New in `charter_runtime`:

- `presim_registry(cid, frame_id, *, horizon_hours, active_tail_hours,
  tail_places, seed)` — for each item: run coarse
  (`window_hours = 8–12`, `active_places = []`) for
  `horizon_hours − active_tail_hours`, then fine (`window_hours = 1–4`,
  `active_places = tail_places`) for the tail; set `last_elapsed_seconds`
  to now so the ordinary epoch machinery takes over seamlessly; compose
  scheduled rows for the produced events with honest due times
  (`now_seconds − seconds_before_now`, §3.3).
- `land_presim(...)` — the `land_snapshot` transaction shape
  (`charter_runtime.py:370-415`) minus the epoch guard (there is no epoch;
  the trigger is an explicit authoring act and the route holds
  `_require_frame_idle`), keeping the rewound-turn guard and the
  `expected_revision` guard — a concurrent author edit must win over a
  presim in flight, same as over a tick.

Horizon ceiling stays `MAX_CATCHUP_HOURS = 720.0` (`charter_runtime.py:28`).
The tail default is derived, as the note proposes:
`(1.0 − PERSONAL_FLOOR)/PERSONAL_DECAY_PER_HOUR` rounded up to a window
(≈ 96 h), so the constant's meaning survives retuning.

### 3.2 What presim runs over

The composed graph (§2.2). This is the note's §5.6 payoff and the reason
Stage 0 precedes Stage 2: a presimmed guard's `stood` record and
`travelled` count name planned rooms nobody has described, `life_of`
(`charter_log.py:100`) reads them back, and the Director resolves them if
the player follows.

### 3.3 The event backlog

Presim events ride the existing rail: `_scheduled_row`
(`charter_runtime.py:184`) → `scheduled_events` → the mechanics sweep →
`world_events`. Two properties to pin with tests rather than assume:

- **Volume**: `charter_run` emits only crossings and changes (the "only the
  change is an event" rule, enforced twice in `charter_run.step`), so a
  quiet presimmed month is a handful of rows. The famine-month measurement
  (244 events) is the *bad-week* bound.
- **Pre-story time**: rows carry `due_at ≤ now`, possibly `≤ 0` for a town
  generated at chat creation. `fired_consequences_at`
  (`world/living_world.py`) and the sweep compare floats and tolerate it,
  but nothing has ever run with negative clocks — a regression test drives
  one presim event through fire → `world_events` → carrier pickup and
  asserts dating stays coherent. If anything assumes non-negative time,
  fix it there, not by lying about `due_at`.

### 3.4 Trigger: at generation, not at first approach

Against note §8.1. Arrival-triggered presim races the arrival turn: the job
is ~8 s and out-of-band, first approach is exactly when its output is
needed, and "the town is generated but blank for the first two beats" is
the everyone-was-waiting failure wearing a scheduler. Generation is already
the arrival-adjacent act — an author (or, later, the planner agent) creates
the town when it becomes relevant — so presim runs inside the generation
job, after `charters_put` lands and before anything reads the registry.
The turn-400 town is thereby handled with no new trigger: generate at turn
400, presim ends at now, and `schedule_charter_ticks`
(`charter_runtime.py:418`, called from `persist/commit.py:536`) advances it
every epoch thereafter exactly as it advances everything else. This also
answers note §8.4: **no new `offscreen_life` rung.** Presim never rides the
epoch gate at all; post-generation ticking rides `deterministic` as today.

And note §8.3 (how many towns) becomes moot: presim cost is paid per
explicit generation act, not per scene creation.

### 3.5 Acceptance, falsifiable (kept from note §7 stage 2, sharpened)

After presim of the Aldermere-scale fixture with an incident authored into
the tail (levels tuned so a floor crossing lands inside the last 96 h — no
model, no randomness beyond the seed):

1. `regard_map` is non-uniform and at least one blame entry exists.
2. `known_news` is non-empty for a body co-present with the tail incident
   and empty for every body for any event older than the tail.
3. At least one post's `watch` names a body that was not its original
   (someone was replaced), and `stood` shows the replacement's service.
4. Byte-determinism: same seed, same registry in, same registry out.

---

## 4. Generation

### 4.1 Input: exactly what `derive_knowledge` calls local

Kept from the note §3.1 unchanged — it is verified right. The generator's
input is a location leaf plus its `[›]` children from `parse_structure`
(`story/lore_structure.py:78`), locality decided by section placement via
`derive_knowledge` (`lore_structure.py:195`). No new classifier.

### 4.2 One model call, and what it may not author

New module `world/charter_generate` (new) and one prompt key
(`llm/prompts.py` + `llm/schemas.py` registration). **Not a pipeline
stage** — no `runtime.STEP_HANDLERS`/`STEP_LABELS`/`SCHEMA_MAP`/
`pipeline_context` entries; the four-registry checklist in
`agents/README.md` governs turn stages, and this is an authoring-time call
behind `POST /api/chats/{cid}/charters/generate` (route beside
`charters_get`/`charters_put`, `web/app.py:4583,4598`).

The model reads the leaf + children and returns a **skeleton**, not a
charter: upkeeps with qualitative durabilities, posts with
`serves`/`requires`/`reports_to`, named-from-lore bodies, a naming profile,
a priority ranking, room intents, a grammar. Deterministic closure then
produces the real registry:

- **Rates from timescales.** The model says `fails_untended: "days" |
  "a_week" | "weeks" | "a_season"` and `one_body_restores_in: "hours" |
  "a_shift" | "days"`; closure derives
  `drift_per_hour = (LEVEL_MAX − floor) / hours(fails_untended)` and
  `service_per_hour` likewise. A model-authored raw float is the
  psychology-fields failure class again: no error, no warning, a town that
  starves or never can, discovered fifty windows later. Timescales are
  checkable by a human reading the JSON; rates are not.
- **Bodies minted deterministically** from a per-post population spec,
  named by `materialize_body_names` (`world/charter_identity.py:119`),
  needs seeded by `seed_needs` (`world/charter_needs.py:91`), roster by
  `seed_roster` (`world/charter_roster.py:45`). A thousand bodies stay one
  model call.
- **Berths within reach.** Closure places each minted body's `berth`
  within `REACH_LIMIT = 8` (`world/charter_space.py:28`) of the places its
  competence serves — the deep-facility answer is local sub-populations
  who live where they work, which `normalize_body`'s separate `home`/
  `berth` field (`charter_model.py:151`) already exists for.
- **Starting state from lore, simulation only for the recent past** (note
  §8.2, adopted): a sacked-eight-years-ago town is authored as depressed
  levels, standing/blame seeds and a thinned roster, never as 70,000 hours
  of simulation. Precedent for authored seeds is already in the tree: the
  playtest fixture hand-seeds `watch`/`stood`/`minds`/`politics`
  (`tools/charter_town_playthrough.py:130-141`). The rule that keeps this
  honest at generation scale: **politics, watch, stood and levels may be
  seeded; minds are seeded sparsely or not at all** (let presim's `see`/
  `converse` build acquaintance — it is what they are for), and **no lore
  content is ever copied into a mind** — a body's *competence* may derive
  from an esoteric entry (a property of the body, note §6.4, kept
  verbatim), a *claim* may not.

### 4.3 What generation refuses (note §3.3, kept, plus one)

The three refusals stand: no institution the lore does not name (a book
with no location leaves generates nothing and says so — the opt-in stays
`charters_put`); generated bodies are Charter bodies, not cast (promotion
stays `promotion_bundle`/`bind_promoted_character`,
`charter_runtime.py:850,870`); everything flows through
`registry_warnings`, not around it.

Plus the one the note asks for in §5.7: **`structure_warnings`** (new, in
`world/structure` (new)), run beside `registry_warnings` at generation and on
every `charters_put` that names a structure: the skeleton is connected;
every post's place is reachable within `REACH_LIMIT` from at least one
body's berth over the composed graph; every planned row is prose-free; no
frontier label collides with a real edge. Verified claim behind it:
`registry_warnings` (`charter_runtime.py:98-161`) checks only charter shape
and place-name membership; unreachability today surfaces solely as a single
`post_unfilled`/`out_of_reach` event at run time (`charter_plan.py`'s
reason taxonomy; one event ever, because only the change is an event) —
visible in principle, invisible in practice.

---

## 5. The two agent seams

Both are **data seams, not callback seams**: the future agent writes stored
state through a route; the engine consumes it deterministically. That is
what makes them free at rest (one `wget`/dict-read returning nothing),
replayable (the influence is inspectable stored JSON, in checkpoints and
archives for free), and — for the dramaturge — automatically consistent:
`land_snapshot`'s `expected_revision` guard (`charter_runtime.py:397-403`)
already discards any tick that raced an author edit, and an agent writing
through `charters_put` *is* an author edit.

### 5.1 The story-planning agent: authors inputs, never states

**The cut line: the planner is an author.** Everything it produces enters
through surfaces that already exist for authors, and therefore inherits
every gate those surfaces already have. Its quadrant:

| It wants | It writes | Which then flows through |
|---|---|---|
| The past | lore entries (existing lorebook entry routes; `Locations` placement per `parse_structure`) | `derive_knowledge` locality → generation → the mapping seam at arrival |
| The future | consequence fuses: a validated mint shaped like `mint_consequences` (`world/living_world.py:339`), `disposition: "authored_fact"`, same `DUE_MIN/MAX` clamps and location gate | fires on the clock → `world_events` → witnessed by presence → `record_obligations` (`living_world.py:489`) → `owed_history` → the mapping seam |
| What exists | `story_plan` world-KV: structure directives + charter emphasis, consumed **only** by `charter_generate` and the skeleton builder | Stage 0/1 machinery |
| Who exists | charter-skeleton hints inside `story_plan` (named figures, institutional emphasis) | generation closure + `registry_warnings` |

The second row is the strongest argument for this cut and costs zero new
delivery machinery: a planner that wants "the bridge fails before the
player crosses the pass" mints a fuse; it fires whether or not anyone is
there; bodies present come to know it (`witness`, `charter_news.py:203`,
gated by the `WITNESSABLE` allowlist); the place accrues it
(`record_obligations` is deliberately not settings-gated — layer-1 truth
accumulates regardless); and first arrival finds the aftermath through
`attach_owed_history` at `agents/mapping.py:66`. Every link already ships.

**Forbidden, and why each:** any mind store (charter `minds`,
`chat_chars.state`, memory rows) — knowledge without a channel; scene room
prose for unentered rooms — a resolved room that bypassed the mapping seam
(note §5.5); `owed_history` directly — the ledger's provenance is *fired
events* (`living_world.py:544` and the module contract: its only consumer
is the mapping seam, pinned by test); charter runtime state after
generation (politics/roster/watch) — that is the dramaturge's argued-over
territory, and the planner reaching it would be two agents with one pen;
narration, obviously.

**What it reads:** the lore tree, `GET /charters` (registry + warnings),
`world_events`, the `structures` KV. It is an author-tier tool; omniscient
*reading* is its job. The `DUE_MAX_SECONDS` 30-day clamp
(`living_world.py:329`) is kept as-is: a plot longer than thirty days is
lore ("the levy falls due in spring") or a fuse the planner re-arms when
the earlier one fires — the clamp's own comment says plots belong to
authored events, and the planner is exactly the author it meant.

**The hook itself:** `charter_generate` takes `plan=None`; the route reads
the `story_plan` KV and passes it. Absent key ⇒ `None` ⇒ the generator
derives everything from lore alone. That is the entire at-rest cost.

### 5.2 The dramaturge agent: circumstance in, never conclusions

**The cut line: the dramaturge may touch what the *world* does, never what
anyone believes, feels, decides or is owed socially.** Drama then
propagates legitimately — the same physics presim already obeys.

Mechanism: `normalize_charter` gains an `interventions` list (defaulting
`[]` — the at-rest cost is one empty-list check in `run`). Each entry is a
scheduled, deterministic op; `charter_run.run` slices the ones due within
the advancing span and applies them via a new pure module
`world/charter_intervene` (new) (`apply(charter, due_ops) →
(charter, events)`), exactly parallel to how `conduct` already enters
`step` (`charter_run.py:52`) and how `charter_author.authored`
(`charter_author.py:99`) lands outside-written acts through inside
machinery. Applied ops are removed from the carried list; the whole thing
replays as a pure function of (registry, seed). The agent writes the list
through the existing `PUT /charters` — no new route.

Evaluating the candidate surfaces the requirement names:

- **Upkeep drift rates — legitimate.** `drift_per_hour` is world physics; a
  drought is `{"op": "drift_dial", "upkeep": "water_drawn",
  "drift_per_hour": 0.06, "from_hours": ..., "until_hours": ...,
  "cause": "drought arc"}`. No mind is touched; the consequence enters
  heads only when a floor crossing mints an `upkeep_out_of_band` event and
  `witness` finds bodies standing there.
- **Body availability — legitimate through needs, marginal as a flag.**
  `{"op": "need_shock", "body": ..., "need": "health", "delta": -0.5,
  "surface": "..."}` drops a need level; `advance_needs` then stands the
  body down through the same `body_unable` path a famine uses
  (`charter_run.py`, the unable/recovered block), and *recovery is
  simulated rather than scripted* (`RECOVERY_MARGIN` hysteresis,
  `charter_needs.py:70`). A raw `available=false` flip is refused: it
  creates a fact with no path back and no cause on the record.
- **A physical incident — legitimate, and the one allowlist extension this
  plan makes.** `{"op": "upkeep_shock", "upkeep": ..., "delta": -0.4,
  "place": ..., "surface": "smoke over the granary roof"}` drops a level
  and emits an `incident` event carrying the authored surface. `incident`
  joins `WITNESSABLE` (`charter_news.py:39`) — correctly, because it *is*
  a public state of the place a body standing there perceives; the
  allowlist's own rule ("register facts stay out") is what the entry
  satisfies, not what it bends. The surface enters heads only via
  presence, degrades on retelling like everything else.
- **Scheduled consequence fuses — legitimate**, same validated mint as the
  planner's (§5.1), same disposition. The dramaturge's slower hand.
- **`priority` ordering under scarcity — refused as a silent knob.** The
  priority list *is* the institution's characterisation
  (`charter_model.py:337-344`: "the whole characterisation of an
  institution is this ordering"). Rewriting it from outside is not a
  firewall violation in the knowledge sense — priority is not a belief
  store — but it is the adjacent sin: an outside hand rewriting an agent's
  values with no cause in the record, a personality transplant that
  invalidates every read the author has made of that institution. If a
  decree story is wanted, it must arrive as an *authored institutional
  event* (a first-class op that mints a register fact with a stated cause,
  visible in the chronicle) — deferred until something needs it.
- **`charter_practice` affordances — refused as a write surface.** Opening
  a quarrel by fiat scripts two interiors ("you two now feud"). The
  machinery already produces quarrels *from circumstance*: scarcity →
  failures → `attribute_blame` → blame said aloud → quarrel practices
  spawn (`charter_practice.py`, `opportunities`/`enact`). The dramaturge
  raises the pressure; the people supply the drama. That is the firewall's
  generative gap doing its job, and it is also simply better drama.
- **Direct regard/standing/blame writes — refused.** Same verdict as the
  bulk-seed-minds path in note §6.3, one store over: politics is the
  *residue of events* (`attribute_blame`, practice effects), and writing
  the residue without the events fabricates a social history no one lived.

**What the dramaturge reads:** `GET /charters` (including minds and
politics) and the `charter_log` diagnostics (`summarize`, `life_of`,
`scene_ledger` — a small read-only diagnostics route is a later
convenience). This is author-tier omniscient reading and it is fine,
stated precisely: `charter_log`'s invariant is that no *mind* receives a
diagnostic (`charter_log.py:1-24`), and the dramaturge's write surface is
incapable of putting one in a mind — every op is circumstance that still
has to propagate through witnessing. An author who reads a private belief
and arranges circumstance to exploit it has produced dramatic irony, which
is the product (CLAUDE.md: "inference is the product, not the risk" —
here, at the author tier).

**Every op carries `cause`** — an author-facing string for the chronicle
and the refused-ops log, never anything a mind receives. The op vocabulary
is closed and normalized; an unknown op is a warning and a no-op, the
`registry_warnings` posture (never silently rewrite).

---

## 6. The firewall argument for presim at volume

Presim fires orders of magnitude more events than live play. What stops
volume becoming leakage is that **every aperture between an event and a
player is capped and channelled, and volume upstream widens none of them**:

1. An event enters a head only by presence at its place, and only if its
   kind is in the `WITNESSABLE` allowlist (`charter_news.py:39,203`).
   `_scheduled_row` gives a non-empty public surface only to those kinds
   (`charter_runtime.py:192`); everything else stays a register fact.
2. A head holds at most `RECALL_CAP = 48` claims (`charter_mind.py:29`),
   decay prunes continuously, and `hear_claim` is the one uptake door —
   presim uses `witness`/`converse`/`cross_charter_gossip`
   (`charter_runtime.py:276`), all of which route through it. **No stage in
   this plan writes `minds` in bulk**: generation seeds sparsely or not at
   all (§4.2), interventions cannot touch minds at all (§5.2), and the
   plan adds no third writer.
3. What reaches the player at arrival is capped where it exits, not where
   it is made: `residue_facts` cap 3 (`charter_runtime.py:484`),
   `place_view` at most 3 ledgers (`charter_runtime.py:479`),
   `can_bring_up` at most 3 items per presence (`charter_log.py:290`),
   `owed_history` honour cap 4 (`living_world.py`,
   `OBLIGATION_HONOR_CAP`), carriers carrying only each body's own sparse
   mind (`carrier_entries`, `charter_runtime.py:510`; the AGENTS.md
   carrier row's whole contract). A 244-event famine month and a 6-event
   quiet month present identically-sized apertures.
4. The diagnostics (`charter_log`) never enter a mind, and the trace is
   returned beside events, not folded in (`charter_run.py:466` docstring) —
   presim producing enormous traces changes nothing canonical.
5. Generation reads lore the player may not know; the boundary is the
   note's §6.4 rule, kept: esoteric lore may shape a body's *competence*
   and a structure's *shape*, never a claim in a head. Lore *knowledge*
   questions ("does the innkeeper know the currency") stay answered by the
   existing knowledge-scoping fields at prompt time, not by copying lore
   into charter minds — charter minds hold claims about bodies and news,
   and this plan keeps it that way.

The one deliberate surface addition — the dramaturge's `incident` surface
entering `WITNESSABLE` — is argued in §5.2 and is an *instance of the
allowlist's own rule*, not an exception to it.

---

## 7. Build order

Each stage ends green under `make check` plus the CI-equivalent venv run,
with the named tests; no stage depends on a later one.

**Stage 0 — composed graph and planned rooms** (no model, no simulation).
New `world/structure` (new) (`normalize_structure`, `skeleton_rooms`,
`composed_scene`, `mint_frontier`, `structure_warnings`,
`plant_structure` writing registry rows); `charter_runtime.advance_snapshot`
compose instead of replace (`charter_runtime.py:236`); `registry_warnings`
call sites pass the composed graph. Verify: `tests/test_structure` (new) —
graph connected; `passable_path` crosses a 30-room skeleton; planned rows
carry no prose (lint); `mint_frontier` deterministic under seed;
`composed_scene` lets live rooms win; a charter with posts on planned rooms
plans a full watch; archive/checkpoint round-trip preserves planned rows.

**Stage 1 — fringe and resolution on entry.**
`materialize_planned_fringe` in the commit domain; the open-location
registry consult in `dedup_minted_rooms`; the derived `resolution` flip in
`_prepare_room_registry`/`_apply_room_registry`; `planned_context` in the
mapping payload beside `attach_owed_history` (`agents/mapping.py:66`).
Verify: integration test — stub appears when adjacent becomes occupied;
`prune_dangling_exits` emits no warnings over a fringe scene; entering a
stub resolves onto the same `room_uid` with no duplicate row; a mapping
mint naming the planned room from afar redirects onto the row.

**Stage 2 — generation.** `world/charter_generate` (new), prompt + schema
registration, `POST /api/chats/{cid}/charters/generate`, deterministic
closure (rates-from-timescales, minting, berth placement, priority
closure), warnings surfaced in the Institutions block
(`static/js/settings.js`). Verify with a stubbed model:
`tests/test_charter_generate` (new) — fixture leaf + children → registry
passing `registry_warnings` and `structure_warnings` with zero rows; a
no-locations book generates nothing and says so; every post reachable from
some berth; Aldermere's hand-authored fixture
(`tools/charter_town_playthrough.py:93`) as the golden shape a generated
town is compared against.

**Stage 3 — presim.** `presim_registry` + `land_presim` in
`charter_runtime`; run inside the generation job; the resolution schedule
(§3.5). Verify: the four acceptance assertions of §3.5 on the fixture;
byte-determinism; the pre-story-clock rail test (§3.3); cost pinned in
`tools/charter_audit_scale.py` (presim of the 1000-body fixture stays
within the same order as the measured 8 s).

**Stage 4 — the seams.** `interventions` in `normalize_charter` +
`world/charter_intervene` (new) + the `run` slice; `story_plan` KV read in
`charter_generate`; the planner-grade fuse mint with
`disposition: "authored_fact"`; `incident` into `WITNESSABLE`. Verify:
`tests/test_charter_intervene` (new) — an op due mid-run applies exactly once,
replays byte-identically, is discarded-with-warning when malformed; refused
ops (mind writes, regard writes, priority) warn and no-op; a `need_shock`
body recovers through the ordinary hysteresis; an `upkeep_shock` surface
reaches exactly the co-present heads and no others; empty list is
byte-identical to today's behaviour (the free-at-rest pin).

Doc obligations per the repo's rules: `UNBUILT.md` rows deleted in the
landing commits, `Design.md` conformance rows added in the same commits,
`make map` regenerated, and the AGENTS.md Institutions row extended with
the structure/intervention invariants.

---

## 8. What this plan cuts from the design note, and why

- **Frontier-as-dangling-edge** (§5.2): reshaped into registry-side
  frontier labels + fringe materialization — `prune_dangling_exits` makes
  the literal reading impossible (§0.1).
- **`{horizon_hours, tail_hours}` as two durations** (§4.3): replaced by
  one horizon + a resolution schedule; the decay-derived default survives
  on the schedule's fine stretch (§0.3).
- **Presim at first approach** (§8.1): replaced by presim at generation
  (§3.4).
- **The "nobody remembers anyone" reading of the finding** (§4.2's framing):
  corrected — acquaintance among the co-circulating survives by `see`
  refresh; only episodes die (§0.4). No mechanism change follows; the
  correction prevents a wrong one.
- **A per-structure model call for the grammar as its own step** (§5.4's
  "the part a model writes, once, per structure"): folded into the single
  generation call. Two calls with a hand-off invite drift between grammar
  and charter; one call emitting both, closed deterministically, cannot
  disagree with itself.
- **Consolidation** (§4.4): stays cut, agreed, for the note's own reason —
  it is a second memory system and `DESIGN_PRESTORY_MEMORY.md` owns the
  first. Revisit after that lands.
- **A new `offscreen_life` rung for presim** (§8.4): unnecessary once
  presim is an authoring-time act (§3.4).

---

## 9. Risks, ranked

1. **The composed-graph seam is the load-bearing novelty.** It touches
   `advance_snapshot`, `registry_warnings`, both charter routes, and every
   future reader that assumes "the charter's scene is the live scene."
   Mitigation: `composed_scene` is pure and exhaustively unit-tested before
   anything consumes it; the AGENTS.md invariant "the live scene owns the
   room graph" is preserved by construction (live wins on every collision)
   and the row is updated to say so.
2. **Per-epoch cost of a large registry.** `schedule_charter_ticks`
   deep-copies, normalizes, and `registry_revision`-hashes the whole
   registry every epoch (`charter_runtime.py:92-95,213-216`), and
   `land_snapshot` rewrites the full JSON into world KV. Measured presim
   cost (8 s/month) says nothing about a 1000-body registry's *per-turn*
   serialization tax. Unresolved until measured; mitigations if it bites:
   revision over stored bytes instead of normalize+dumps, and skipping
   advance when the epoch delta is under one window. **Open.**
3. **Access-controlled depth vs. charter reach.** Skeleton edges ship
   passable with `access` as data (§2.2), but the first live resolution
   that mints a real `closed_door` across a staffed path strands every body
   behind it — correct physics for strangers, wrong for staff with keys.
   Options, none chosen here: an institution-passability overlay in
   `charter_space` (new machinery in the pure package), mapping guidance to
   prefer `open_door` + guarded-by-presence for staffed checkpoints, or
   accepting the strand as story. **Open, and it will surface in the first
   SCP-shaped structure.**
4. **The open-location dedup gap** (§2.3): until fixed, a distant mention
   can mint a duplicate beside a planned row. Class fix specified; small.
5. **Pre-story clock times on the event rail** (§3.3): unexercised
   territory; a dedicated rail test in Stage 3 before anything depends on
   it.
6. **Model-authored intervention surfaces** enter heads as claim text. The
   exposure equals the existing `_event_surface` phrases plus degradation
   on retelling; bounded, but the dramaturge prompt (when that agent is
   built) must hold the note's own discipline — name the distinction, never
   the instance.
7. **Frame semantics of a cross-frame skeleton.** Planned rows are
   registry-side (cross-frame) while charters are frame-scoped: a temporal
   frame fork shares the structure but not the institution's state. That
   is probably right — buildings outlive eras, staffing does not — but
   nothing has tested a structure across a frame fork. **Open, low
   urgency.**

## 10. Open questions, honestly unresolved

1. Staff-passable access edges after resolution (risk 3).
2. The per-epoch registry tax at 1000 bodies (risk 2) — measure in
   `tools/charter_audit_scale.py` before Stage 3 lands.
3. Whether `purpose` on a planned room should speak
   `place_purpose.AFFORDANCES`' closed vocabulary or stay a free
   structural token. They answer different questions (`place_purpose` is a
   character's expectation lexicon, ~30 exact tokens by rule,
   `world/place_purpose.py`; `purpose` here feeds the grammar and the
   mapping seam) — kept separate in this plan, with the relation
   documented, but a shared subset ("a room whose purpose is `well`
   assumes `water`") is tempting and should be decided deliberately, not
   drifted into.
4. Whether charters over one structure should nest (a facility's charter
   and a wing's) — `DESIGN_INSTITUTIONS_AND_UPKEEP.md` §14.4's question,
   which deep structures will re-ask. This plan generates one charter per
   structure and waits.
