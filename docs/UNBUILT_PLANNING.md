# Unbuilt work — Story planning and authoring

Part of the [unbuilt-work register](UNBUILT.md). Entries are grouped by status
and retain their original stable ids. Delete an entry in the same commit that
lands it.

## 1. Known defects

<a id="unbuilt-1-134"></a>

### 1.134 What the campaign-3 plan/structure/tools wave left open (2026-09-05)

Fourteen findings from the five 2026-09-05 play runs were worked as one lane
(the plan, the structures and the Writers' Room's own tools). What landed is
in the commit; this records the parts that were deliberately not built, and
who owns them.

**PR10 -- a residential structure with nobody in it.** The rush run reported
that "no beat can put anybody there". Audited: **that half is wrong**, and the
audit is the point (§ 1.126's rule -- an empty field is not a dead field).
`commit_background.track_background_presences` mints a background presence
from any `state_diff.entities` row whose `kind` is not in
`_INERT_ENTITY_KINDS`, so a Director that declares a person in a room *does*
put one in the world. What is genuinely missing is the one that made the flats
empty: **the establish invents nobody for a dwelling it has just declared.**
That is a clause in `director_establish.txt` (both packs) -- a residential
structure the establish declares carries the people who live in it, or the
establish says it does not -- and it belongs with the light/establish work. Not
built here.

**PQ13(b) -- an arrival is met by being perceived.** A published arrival at a
room nobody occupies now WARNS at preview (`_preview_arrival`), which is the
half the authoring surface owns. The other half stands: *a knock is a sound,
and the sound field already crosses a closed door*, so an arrival should be
able to reach the rooms in earshot as a hearing percept and leave the body
outside, rather than requiring somebody to open the door before the arrival
exists. That needs a channel from the arrival op into `sensory_events` and the
admission gates in `agents/perception.py`; it is a perception change, not an
authoring one.

**PR12 -- a planned source reaches the plan, not yet the minted entity.**
`plan_entity` now carries `light_source`, `light_shape`, `light_height`,
`steadiness` and `sound_source` through the same closed tables the World
Browser validates against; they are stored on the plan and handed to the
Director in `plan_figure`. What remains is the deterministic half: when
`agents/director_floors.py` binds a minted entity to a plan (`ent["plan_ref"]
= ...`), the plan's `sources` should be copied onto the entity, so a roar the
Room authored is a roar the field reads without the model having to restate
it.

**PM12 -- the naming register is evidence, not a rule.** `propose_town` is now
handed the story's registered names and told the law it proposes must produce
names that stand beside them. That is a clause; whether a generated law should
be DERIVED from the story's existing names (a phonology read off the cast
rather than proposed beside them) is a larger question and is not answered
here.

**PS6(a) -- the double-reported overlap is collapsed at the tool, not at the
lint.** `room_tools._one_row_per_contradiction` reports one row per unordered
pair, which is what a reader asking "how many things are wrong" wants. The
lint itself (`world/spatial_lint.py`) still emits `rooms_overlap_when_placed`
once per ordering, because it walks the pair from each end; deduping there is
the geometry lane's call.

**PX24 -- a mandate's width.** A grant can now name the ask that earned it
(`grants[].request`, passed through `_apply_grants` to the seam that has
accepted it since 2026-09-04), so a grant earned by one request lapses with
it. What no code can judge is whether the CAPABILITIES a grant lists are the
ones the player's sentence asked for -- that is a reading, and it stays the
Planner's, under the standing clause "only what they said, never what would be
convenient".

## 2. Roadmap

<a id="unbuilt-2-9"></a>

### 2.9 Predictive staging

Build the Story Planner inside a cross-system Writers' Room agent set. It
maintains a bounded prepared horizon, pre-staging lore and structure for
likely-next locations without redirecting a player who chooses an unpredicted
route, and delegates coherent populated-location construction to a narrow
Charter Planner subagent. It is primarily a latency and continuity win, which
is why it ranks below the integrity work. The combined Planner/Dramaturge
authority, Charter Planner hierarchy, collaboration, sealed-plot and
acceptance-test design is
[`design/DESIGN_STORY_PLANNER_AND_DRAMATURGE.md`](design/DESIGN_STORY_PLANNER_AND_DRAMATURGE.md).

<a id="unbuilt-2-26"></a>

### 2.26 Writers' Room and Dramaturge

**Phase A (engine seams) landed 2026-09-03/04, per
`design/DESIGN_WRITERS_ROOM_PLAN.md` § 5:** items 1 (planned entities: view,
settle, reservation), 2 (surface-only mint, planning need, deterministic
fill by enrolment; the ambient charter deleted), 3 (`compile_world_context`
replacing the mapping stages; the filing a structured write through
`canon_provenance.promote`), 4 (the offscreen hand retired) and 5 (ONE
planning-need ledger, `world/planning_needs.py`, written by the compiler and
by the surface-only mint alike, with its drain job). Residuals: § 2.26a (the
compiler's half) and § 2.33 (the plan tier's half).

**Phase C, the agents (2026-09-04, `design/DESIGN_WRITERS_ROOM_PLAN.md` § 5
Phase C, first half):** the Dramaturge is seated (`agents/dramaturge.py`,
role `dramaturge`): pure planning over the player-visible stream with lore
search and lookup as its one tool, proposing typed direction
(`story/room_proposals.py`) under the creativity dial (`surprise` 0..4, a
mandate limit; unset, it proposes nothing) and a pacing budget
(`beats_per_proposal`, default 6). The deliberation loop
(`agents/story_planner.deliberate`, `DELIBERATION_ROUNDS` = 2) has the
Planner judge each proposal for naturalness -- accept and implement through
a package, refuse with the contradiction named, or send back for revision
-- and returns a disagreement to the player after the rounds. The bounds
rework landed with it: steps and calls per reply are safety ceilings (40,
200), the wall splits by regime (600s interactive with the status row
rewritten every step; 600s per pass in the background, resuming under the
same mandate up to `TASK_PASSES_CAP` = 12 passes), and SPEND is the stop
(`calls_per_reply` default 60 / ceiling 200, `calls_per_hour` default 240 /
ceiling 1200, mandate limits the Planner cites). Left from this half: no
proposal card (the exchange is thread lines and the status row's
`proposal` entries); the Dramaturge's and the fold's judgement are
unmeasured on a live model; a verdict the Planner does not name a
`proposal_uid` for leaves the proposal pending into the next round; the
local drama, nudge and region-event operations and firing clocks are the
other half (fork C2).

**Phase B, the panel (2026-09-04, `design/DESIGN_WRITERS_ROOM_PLAN.md` § 6
items 5 and 6):** the popout panel is built in both shapes -- docked right
(opaque chrome, width-resizable, collapsing to its tab) and floating (the
prose plate, draggable, corner-resizable, opacity slider) -- with the
persistent per-story, per-era thread (`room_messages`), the mandates list
with revocation, and the spoiler-safe status line. Open from this half:
the Dramaturge visibility setting
(shown / summarised / hidden) is a per-viewer preference with no server
side; there is no proposal card (v2 § 11.1) -- an actionable reply is a
Phase B2 shape; no browser-tier test covers the drag and resize gestures
(the Playwright harness has no comparable panel to extend); the panel
refreshes by watching the story view's identity once a second while open
(`ROOM_WATCH_MS`), not by an event the turn pipeline emits.
**Phase B items 1 and 2 landed 2026-09-04:** the plot-package store and
lifecycle (`story/plot_packages.py`: draft/validating/published/active/
resolved/retired, pinned base with rebase-or-conflict, long operations
prepared before a one-transaction publish, next-turn visibility, superseding
truths, sealed projection) and the authoring facade (`story/room_tools.py`:
one tool table, fifteen read and ten write tools, every write through a
package). **Items 3 and 4 landed 2026-09-04:** the Story Planner is seated
(`agents/story_planner.py`: a bounded tool-using loop over the facade, the
Charter Planner as one scoped call per reply, the fill job under the
`identity_fills` mandate, the frontier measured every commit in
`story/room_frontier.py`) and the grant is state (`story/mandates.py`: a
closed capability vocabulary, `plot_packages.authority_errors` at validation
and at publish, the fill budget per story hour). Phase B is complete except
for what follows. Residuals of this entry rather than a section of their own:

- **No proposal card** (v2 § 11.1). An actionable reply is prose plus the
  standing list and the status line; what a package would add, who led it,
  its estimated cost and approve/revise/reject actions are not a card yet.
  The projection the card would show already exists (`package_projection`).
- **The Planner's tool discipline is unmeasured on a live model.** Every
  bound is proven against a scripted provider; how many steps a real reply
  spends, how often it publishes without validating, and whether it records
  grants the player did not make are the first things to measure in play.
- **A mandate is per era and never per package.** `authority.mandate_uid`
  is honoured (a named mandate must be active) but nothing ties a grant to
  one package's lifetime; `limits.packages` / `rooms` / `people` are shown to
  the Planner and cited, not enforced by code -- only `fills_per_hour` is.
- **The frontier is a count, not a ranking.** v2 § 3.2's predictive staging
  (exits, declared destinations, projects that name places) is not read;
  the measure is planned stubs within `FRONTIER_DEPTH_HOPS` and unrendered
  person plans anywhere, and the Planner is told what is short.
- **The region tier has the field and the grouping, not yet the index of
  its own.** `world/regions.py` (2026-09-04) gives every room a derived
  `region` and groups `room_index` by it, and `inspect_contradictions`
  reports a region in pieces (the chat 115 second-lift-car shape). What
  `design/DESIGN_ROOM_REGIONS.md` §5 still asks for: `inspect_regions`, one
  row per region at O(regions) so a story with several hundred planned
  rooms stops losing its farthest index rows to the 12,000-character cap;
  a `region` argument on `inspect_rooms` filtering index and slices alike;
  and a writer for the registry's `brief` (the field exists, nothing authors
  it -- the design note argued the intent belongs in the bible, and the
  registry gained the field instead when the owner asked for one). Measured
  on a copy of the owner's database at the backfill: 396 of 590 rooms have
  no region a rule can reach -- the residue is Director-minted rooms in
  stories with no plan and no zone, and it is surfaced as `region: null`,
  never hidden.
- **The World Browser's editors stop where the ledgers stop** (2026-09-04,
  the attire-editor residual closed the same day: the Bodies tab edits the
  ledger as stored, a spanning garment carried through every region,
  through `PUT /attire`; the room's measurement -- extent, shape, an L's
  parts -- the region's `look`, and the layout lint's rows beside their
  field landed later the same day). What the field editors still do not
  reach, and Raw JSON does: an exit's `distance`, `passage_from` and
  `vertical` (kept verbatim on an edited edge, never shown; the passage
  record that would make a doorway one object is § 2.37's and is not
  built, so an edge declared from the far side alone stays read-only on
  this room's card); an anchor's fields beyond desc / bearing / the three
  geometry words; a region's `name` and `brief` (only its `look` is edited,
  and only from a room that is in the region -- a region with no live room
  in the frame has no card to be reached from); the layout lint's rows are
  SHOWN and never fixed (rows, never fixes: `wall_overfull` names the wall,
  and the host moves an anchor or widens the extent); a corner anchor's
  wall has no pace count (a corner is one cell); an entity's `aliases`, `plan_ref` and the rest
  of its `state` beyond `lit`; a body's pose (shown on the Bodies tab, not
  edited -- `poses` is the body specialist's channel and an authoring
  surface for it wants the pose vocabulary, `_POSE_FIELDS`, as a form);
  moving the PLAYER (the cast editor's rule: the player's position is the
  story's business); creating or retiring a ROOM (a planned room is the
  Writers' Room's, a live one is minted by a beat -- the browser edits what
  exists); and `wearing` order, which is derived from the regions and so
  has no independent edit. A `covered_zones` (displacement) editor per
  garment is the largest attire gap: the ledger carries it and the editor
  preserves it, but offers no control.
- **What the map editor still does not do** (2026-09-04, the owner's ruling
  of the same day landed the Rooms tab as a map: `web/world_routes.py`
  `grid_view`/`map_view`, `static/js/world_browser.js` "The map editor",
  `DESIGN_ROOM_FIDELITY.md` §10; on 2026-09-05, after the owner's "This
  room editor feels very incomplete", §11 of the same note landed the
  overlays, dragging the player and a presence between rooms, dragging a
  far-declared doorway (the passage record, § 2.37, now built), dragging
  things, creating and removing rooms, doorways, anchors, things and
  presences from the map, resizing the extent by its sides, the shape and a
  composite's parts on the map, door positions and dragging on the
  structure map, regions from the card, poses, and one-step Undo). What
  remains, each a decision or a measured gap rather than a missed step:
  **Proximity reads cell distance only for a PINNED pair** (the `cell`
  field, `DESIGN_ROOM_FIDELITY.md` §10). `_cell_proximity` fires when at
  least one body carries an authored `cell` and both stand on a cell; two
  bodies at two ANCHORS derive cells too, and reading their distance would
  change the anchor-tier answers that sixteen test files pin (`near` for
  two anchors in a medium room, `across` only from `large`). The owner's
  condition for touching proximity was byte-identity for unpinned pairs, so
  the rule stops there; widening it to derived cells is a decision about
  those pins, not a bug. **The station editor's `at` select lets a cell
  go** -- choosing an anchor by name is read as "stand at it", so a host who
  wants "at the bar, THIS end" drags on the map rather than picking from the
  menu; the map writes both. **A thing has no wall `offset`** -- it is
  placed by `cell` alone (a thing is not a feature of a wall; an anchor is),
  so a thing dragged onto a wall cell is pinned there, not attached to the
  wall. **A corner anchor has no `offset`** (a corner is one cell; the
  field is kept on the record and moves nothing). **Undo is ONE step and
  only for a drag** -- a write from the card clears it, since the card's own
  value is then what the server holds; a deeper history is a decision about
  where it would live. **A passage's `state` has no reader** (§ 2.37).
  **A body dropped in a neighbour's cells that are also a doorway's** is
  stationed at that door anchor, which is the honest reading and looks odd
  when the host meant "just inside". **A structure-map drag re-bears only
  the doorway that placed the room** (`layout_rooms`' `parents`); a room
  reached by two doorways keeps its second bearing, and the lint says so if
  the two now disagree. **Measured on the L test room**: a doorway on the
  inner wall of the notch (an `e`-facing rim cell of the west part) lays the
  neighbour INTO the notch, where it overlaps the room's own east part and
  `room_field` skips it silently -- the neighbour is then absent from the
  map with no row saying why; the lint's `rooms_overlap_when_placed` runs
  per component from `layout_rooms` and does not see a room colliding with
  the room it hangs off, so this is a gap in the lint as much as in the map,
  and a composite's inner walls widen the class.
- **The naturalness guard is a clause plus the structural floor, not a
  refusal over prose** (2026-09-04). The owner's phrasing was "refuse ops or
  notes naming what a character will think, feel or decide". What is built:
  the floor -- no kind in `plot_packages.OPERATIONS` writes a mind, a memory,
  a relationship or a view, and `director_note` writes nothing
  (`tests/test_room_minds.py`, `tests/test_plot_drama.py`) -- and ONE clause
  in both packs' `story_planner` cards plus the `director_note` field text:
  the room places what a character MEETS, never what a character CONCLUDES,
  and a note says what a placed thing is and is for, never how a character
  will take it. No regex or keyword check reads `director_note.text` or any
  prose field, by the repo rule that a guard over free prose fails in
  whichever direction its missing word points (`CLAUDE.md`, 2026-08-29's
  four). Whether a deterministic refusal is wanted on top is the owner's
  call after watching a few beats of the Planner under the clause; the seam
  it would sit on is `_shape_director_note` and the `shape` step of each
  kind, and it would need a vocabulary the engine owns, which it does not
  have for "what a character will think".
- **`inspect_minds` reads the present cast only.** `scene.active_cast`
  returns the members in the live scene; a dormant (away) member's mind is
  as legible and is not listed, so a plan that would invite an absent
  character's drive has to wait for their return to read it. Widening the
  read to the away roster is one argument.
- **The fill job is queued from the commit tail, not from a threshold
  crossing.** Every commit with an open need or a short frontier and a
  grant submits one job (deduped per chat, capped per story hour); there
  is no separate low-water trigger.

- **The story bible is built** (2026-09-04, `story/room_bible.py`, plan § 6
  item 7): seven sections, every entry with a source the code verifies,
  unpaid setups never evicted, reversals keeping both lines, folded out of
  band on the Planner's role (`prompts/bible_fold`) and deterministically on
  publish and resolve, served in both agents' system block and to no mind.
  Left: the fold is one model call and its judgement of "what a writer
  would regret" is unmeasured live; a thread that outruns the hard cap
  (`PLANNER_HISTORY_HARD_CAP` = 60 lines) before a fold lands loses its
  oldest lines from the Planner's context until the fold reads them (the
  lines themselves stay in the thread).
- **The Planner's live measure (chat 111, 2026-09-03, three replies):**
  47s / 61s / 19s; the first two runs each found a defect class (calls under
  a misspelled key dropped silently; a grant written once per step; drafts
  refused with a message naming neither the kind's key nor its fields; an
  empty package validating clean and being reported as prepared), each fixed
  at its class; the third published a three-room, two-person package in five
  steps and eleven calls.
  On GLM 5.2 (Fireworks, the same grant): 66s and 32s failing -- a step
  drafting a whole package ran past the token ceiling and its truncated JSON
  read as "done"; six steps were the bare floor and the model spent three
  reading -- then 51s, nine steps, eighteen calls, previewed, validated and
  published. Ceilings after the runs: 10 steps, 40 calls, 8000 tokens per
  step, 180s -- superseded 2026-09-04 by the bounds rework above (safety
  ceilings 40 / 200, spend the stop, 600s per regime). Prompt caching held
  on Fireworks (5-7k cached tokens per step) and read 0 on Gemini through
  OpenRouter.
- **Research is grantable and unmeasured.** `story/room_research.py`
  (2026-09-03) gates `web_search` and `fetch_page` on a `research` mandate
  and files results only as `web_reference` lore; the capability, the
  disposition and the three `file_lore` fields (`disposition`, `source_url`,
  `fetched_at`, cited first in `source_notes`) were wired at merge. Budgets
  are per beat, not per reply, because a tool has no notion of the reply it
  serves; when the Planner's loop hands tools a reply context, the ledger
  should key on it. Thread notices are a fixed prefix plus the query, so the
  prefix is in the catalog and the query is shown as sent. No live measure
  yet.
- **The bench ran live 2026-09-03** (chat 114, four runs, Planner and
  Dramaturge on Gemini 3.7 Flash; `tmp/live/room_live.py` around
  `tools/room_bench.py`). What it found is fixed (Design.md "A planned
  person or thing is rendered", the room half; `SILENT_LINE`; the Planner's
  live-mind ground). What it left, measured:
  - **An accepted proposal with no package is never picked up again.**
    Three of four accepted proposals across the runs were accepted without a
    package in the same reply (the card asks for one) and stayed `accepted`
    forever; nothing re-tasks the Planner with them. `schedule_room_work`
    should hand accepted-unimplemented proposals back as a task, or the
    deliberation should treat accept-without-package as revise.
  - **The Dramaturge proposed a live mind's conduct in every run** ("the
    Doctor gestures toward the blue box") although its card forbids it; the
    Planner now sends such a proposal back and the restated circumstance
    (the box standing ajar, light spilling) was accepted. One model, one
    story; the card's sentence may want the complement stated (what the
    world can make true) rather than the prohibition alone.
  - **The Planner names room ids to the player** (`coastal_lane` in
    backticks) against its card. A prompt question. (It also called
    `inspect_clock` five times per reply though the clock cannot move
    within one; since 2026-09-04 that call, and `inspect_packages`, echo
    the payload key they already ride under, and an identical call whose
    answer is still in view echoes the step to look at, so the repeat
    costs a call and no characters.)
  - **A walk into a room no edge reaches was accepted as a step** (run 1:
    beach to a room planned off the terrace); the hand invented the edge.
    The bench now reports `walk_adjacent`; whether the Director should
    refuse or route the teleport is the approach seam's question.
  - **The terrace's planned exits churn every beat**: `protect_planned_edges`
    restores terrace -> lounge/dining/garden, then `prune_dangling_exits`
    drops them as undefined because the fringe materialises only around
    occupied rooms. Three warnings per beat, no behaviour; the two seams
    should agree on which planned neighbours become stubs.
  - **No prompt caching on Gemini through OpenRouter** (0 cached tokens on
    every call, 6-13k system tokens per step); Fireworks caches.
  - The critic is one model's opinion (five 4s and 5s on every run) and
    scored the run with the identity defect as highly as the run without;
    its `contradictions` list, not its scores, is the useful signal.
- **Phase C's operation set landed 2026-09-04** (`story/plot_packages.py`,
  `world/charter_surgery.py`, `world/region_events.py`): the five local-drama
  kinds (arrival, errand, incident, summons, scheduled consequence), the six
  nudge kinds (author surgery on an institution, each recorded under the
  charter's `authored`), `region_event` (footprint, profile in time, per-room
  effects through existing seams), and package clocks that FIRE from the
  commit tail (`fire_due_clocks`) landing what rode them under the mandate
  re-checked at that hour. `schedule_harm` now gates every operation that
  can hurt a body. What that half left open, as residuals here:
  - **A front and a decay are approximations.** A `front` advances one ring
    of hops per `1/rate` hours over the footprint's own graph; it does not
    consume passable edges the way the living-world fuse machinery does, and
    a `decay` revisits the whole footprint at falling intensity rather than
    spreading by co-presence. The plan's contagion-by-encounter and the
    creature fork's condition model are the fuller shape.
  - **No rebuilding afterwards.** A ruined room stays a ruin; the plan's
    "rebuilding as a town project" (an upkeep restoring a room over hours)
    is not built, and displacement rehouses a body at its own institution's
    standing workplace or commons, never at another charter's berths.
  - **Harm in a region is a stable draw, not a contest.** Who is hurt is
    drawn per body against `fraction × intensity`, capped at
    `HARM_BODIES_PER_HOUR` = 12 per wave; the creature fork's contest
    (capability, posted, weights) is not consulted.
  - **A body's inside is refused, not explained.** The Planner's read tools
    report containment on the holder and refuse the room; nothing yet tells
    the Planner why a plan it reads as sensible was refused beyond the
    message.
  - **Fired operations are not undone by anything but a rewind.** A retire
    after a fire keeps what landed, as retire has always done.
- **The Director note and the opening's plan landed 2026-09-04**
  (`plot_packages.director_note` / `active_director_notes`, the preview's
  reach warning, `director._opening_planned_rooms`; `tests/test_director_
  notes.py`). Residuals:
  - **A note's scope is adjacency, not sight.** "In or beside" is one hop
    over the scene's adjacency and the plan's topology; a note about a room
    two hops out (chat 115's planned lift car, from inside the live lift)
    applies only if the Planner names the live room too or names none. The
    Planner prompt says when to write one, not how wide to scope it.
  - **The reach warning is a preview line the Planner reads, not a gate.**
    Nothing stops a publish past it, by design; whether a live Planner
    reads the hop count and re-plans has not been measured.
  - **Not measured live:** whether an opening handed `planned_rooms` places
    itself in the planned room by id rather than minting a like room (chat
    114's 49-room brief is 63,544 bytes on an empty scene; the cost is
    known, the behaviour is not).
- **Lore filed by the room carries the `model` basis** because
  `canon_provenance` admits `deterministic|model|unavailable` and the room's
  entries are author claims through a model role; an `authored` basis is an
  eighth-disposition question for that module, not this one.
- **`inspect_events` reads the omniscient `events` row** by design (the room
  is an author); it is the only reader of that row outside the pipeline, and
  it is not served to any mind.
- **`retire_package` keeps what landed.** A package that planted rooms and
  bodies and is then retired leaves them in the world; there is no
  un-publish, because the world's own seams have no un-plant.

Build the cross-system Writers' Room agent set described in
[`design/DESIGN_STORY_PLANNER_AND_DRAMATURGE.md`](design/DESIGN_STORY_PLANNER_AND_DRAMATURGE.md):
two principal conversational specializations, Story Planner and Dramaturge,
sharing broad authorial sway over every story system through reviewable,
atomic change sets. The Story Planner delegates coherent populated-location
construction to its narrow Charter Planner subagent; the Dramaturge can author
local mysteries through overarching plots, open or sealed, as state the
simulation may genuinely disturb rather than a required sequence of scenes.

The design depends on a stable Charter identity/generation/promotion/archive
lifecycle and therefore follows the current Charter integration work. Its
shared substrate is proposal storage, explicit/standing mandates, provenance
for authored history and retcons, atomic cross-system application, sealed-plan
presentation, and bounded inter-agent deliberation. Neither principal agent is
confined to a subsystem; their names describe perspective and usual lead, not
exclusive authority. At rest the whole set makes zero provider calls.

<a id="unbuilt-2-26a"></a>

### 2.26a Phase A's residuals: the compiler, the filing and the retired hand

Landed 2026-09-04 (`agents/mapping.compile_world_context`,
`world/planning_needs.py`, `persist/commit_mapping` without a model, the
offscreen hand retired). What it deliberately does not do:

- **A planning need has no answerer yet.** The compiler records the need
  and the Director renders the surface; nothing fills the plan behind it.
  Phase A.5 (the queue and the `core/jobs.py` job with a deterministic fill)
  and Phase B (the Writers' Room's just-in-time job) are the answer. Until
  then a need stays `open` on the frame's ledger and falls off after
  `PLANNING_NEEDS_CAP` newer ones.
- **The reactive-plan rung is inert.** `offscreen.apply_plan_ops` reads
  `offscreen_plan_ops` from a character's own result, and no character
  prompt or schema writes that field yet; the Director's diff no longer
  carries the channel. The character frames are the intended writer.
- **Couriers and crowds are ops on the social hand, not charter's.** Charter
  simulates both, but raising a crowd or sending a rider is still a Director
  op the social hand encodes; a charter-owned dispatch (a body walking a
  route with news as a charter errand) is the direction the plan names.
- **Nothing proposes lorebooks during a turn.** The mapping model's
  `book_ops` are gone; `_apply_mapping_book_ops` survives for the authoring
  package (v2 § 9.4 `apply_authoring_change`). A new subject files into the
  canon book until then.
- **`shadow_profile` and `standing_intentions` have no writer.** Both were
  the mapping model's; the world keys survive for their readers
  (`world/offscreen.py` reads standing intentions) and stay empty.
- **The classification is measured on stored interpretations, not live.**
  Replayed over the Harrowmere replay's 39 stored `director_interpret`
  outputs against the audit's per-turn room ledger: the compiler agrees
  with the retired quick stage's escalation on 31 beats and disagrees on 8,
  and every one of the 8 is the old stage escalating to a model call on a
  DESCRIPTIVE location query about a room the scene already held ("Ford Inn
  cellar cool storage beer casks provisions Harrowmere" beside a known
  `inn_cellar`) -- the two-seeds-for-one-room class, which the compiler
  answers from the destination or the room's own spelling inside the
  query. It raises needs on 13 of 39 beats: 12 `generation_request` (the
  interpreter's captured declarations, kept as records) and one
  `declared_destination_unplanned` (t38's `upland_road`, which the plan did
  not hold). A live replay under the compiler is the next measurement.

<a id="unbuilt-2-30"></a>

### 2.30 The replay closer's residuals (2026-09-03)

What the fixes for replay defects N2, N9, N10 and N11 deliberately left:

- ~~**A frontier stub named for its axis is a label, not a place name.**~~
  **CLOSED 2026-09-05** by `docs/design/DESIGN_FRONTIER_SPACES.md`. The
  label was never the whole problem: a stub is now a SPACE HELD OPEN rather
  than a room spent, marked `provisional` with the axis it stands for, and a
  later plan fills it by identity (`plan_rooms`' `claims: {room, axis}`,
  listed for the Room by `inspect_structures.frontiers`). Claiming renames
  the room in place — same uid, old name kept as an alias, and the plan's own
  spelling tables now read aliases so the old word still resolves — unless
  the story has been in it, in which case the claim takes the purpose, the
  geometry and the onward axes and leaves the name. That closes the
  duplicate-room class of the replay outright: `bridge_road_2`,
  `upland_road`, `slate_lane_2`, `market_square_2` and `_3` were every
  duplicate room of that run, and each was a plan built beside a stub
  standing for the same place. A stub also inherits its axis, so the world
  no longer stops one ring past whatever a plan drew (measured: one room per
  beat walked, 21 rooms over 20 beats on a one-axis road; bounded by
  `max_planned`, no new cap). `tests/test_structure_frontier_claims.py` (24).
  Left open and named to the owner in the note: a per-axis chain-depth cap
  (recommended, not chosen — caps are the owner's), a durable "was ever
  occupied" mark for a room, and `memories.location` still being a room's
  NAME with no alias path in `memory_retrieval`.
- **The boundary rule refuses "Westfield".** A fragment ending in a
  consonant cluster does not join a consonant-initial one, which refuses
  "Brgaron" and also "west"+"field"; the law still names everyone (the next
  fragment in seeded order joins, or the middle is dropped), and a law whose
  every start and end refuse each other is joined as written. The rule reads
  the Latin range only; a kana law is untouched.
- **The historian's per-resident allowance is an estimate.** 220 tokens
  covers a 40-word summary with three citations and two turning points with
  a margin; the ceiling holds by the retry, not the estimate, and the retry
  halves the residents rather than the prose. The per-resident recent-life
  call in `charter_history.py` (7,000 fixed) was not touched.
- **Berths are dealt round, not read.** A post serving ten houses puts its
  bodies one to each in turn; nothing reads a household's composition, so a
  house of one holder and four members is the closer's, not the planner's.

<a id="unbuilt-2-33"></a>

### 2.33 Planned entities and enrolment — residuals (2026-09-03)

Landed as Phase A items 1, 2 and 5 of the Writers' Room plan. What it
deliberately does not do:

- **An authored plan has no writer but the API.** `add_planned_entity` is
  the seam the Writers' Room will publish through; nothing in play files
  one yet, so the ledger holds only what a test or a tool wrote. Charter
  bodies are the first and, in play, the only plan source.
- **A thing-need and a room-need are filed and never answered.** The drain
  job answers person-needs by enrolment; a dwelling owed, or a thing with
  no plan, waits for the room. `PLANNING_NEEDS_CAP` (64 open) closes the
  oldest as stale rather than growing forever.
- **Enrolment reads the post's forms, not its situation.** A role naming
  a post whose seats are all held enrols the person as a householder and
  says so; nothing considers whether the town should GROW the post (a
  second watch at the bridge). That is a planning revision, the room's.
- **A guest's departure is a disappearance.** `depart_guests` marks the
  body departed and unavailable at `GUEST_STAY_HOURS`; no event, no news,
  no walk to the gate. The room's own plans can extend or end a stay by
  editing the body; nothing in play does.
- **The minimal households charter berths the newcomer where they stood.**
  A story with no town has no house to offer, so `berth = place` and a
  room-need is filed; until the room answers it, the room they were first
  seen in is listed as their home (`charter_dwellings`), which is at least
  the truth about where they sleep.
- **The seen surface wins by phrase, not by understanding.** `reconcile_
  surface` adopts a pool value the description names; a description that
  contradicts a dealt axis in other words leaves the dealt value standing,
  and the render is settled beside it either way.
- **A planned thing binds by name alone.** The floor never binds a minted
  object to a planned thing by kind or description; a plan the Director
  renders under another name is a second thing until the room reconciles
  them.
- **Measured on the replay's registry at its end state**, as fork H's
  measurement was: six of seven mints bind, the seventh (the bridge
  watchman: the watchman post's three seats held) enrols as a householder.
  The live rate under a new run is unmeasured.

<a id="unbuilt-2-35"></a>

### 2.35 What the 2026-09-04 debug runs left open

Evidence: [`experiments/DEBUG_RUN_2026_09_04.md`](experiments/DEBUG_RUN_2026_09_04.md)
(two runs on copies, thirty-five findings; eight classes fixed the same day,
pinned in `tests/test_played_scene_classes.py`). Open, each an owner decision:

- ~~**"Full authority" is a snapshot (F15).**~~ CLOSED 2026-09-05. The total
  grant is now one MEMBER of the capability vocabulary
  (`mandates.TOTAL_CAPABILITY`, spelled `everything`) rather than a snapshot
  of the rest of it, and `mandates.permits` resolves it against the
  capability being asked for at the moment it is asked -- so a kind added
  after the grant is covered, and an ENUMERATED grant still covers exactly
  what it listed. Every reader of a row's capabilities goes through
  `permits`, so there is no second answer (`coverage`, `fill_limit`,
  `_most_permissive`). `tests/test_mandate_scope_and_totality.py`.
  Remaining, and the owner's: the Planner has to WRITE `everything` when a
  player says it in words -- `agents/story_planner.py` is handed
  `MANDATE_CAPABILITIES` and now sees the member, but nothing tells it that
  "full authority" is that member rather than a list.
- **A pose `detail` is a side channel for perception (F18).** "watching the
  arrival" on a body behind a closed door reached that mind as its own
  interoception and was cited as present evidence of an event in another
  room. Clause first (a detail describes the BODY, never what it perceives)
  or the composer delivers only posture it can verify.
- **Two minds fought over one door and the world kept neither answer (F22).**
  One held it open, one latched it, the narrator rendered both, the scene
  kept it open. A barrier is one object; the resolve owes it one answer a
  beat, and the reconciliation should catch "latched" prose against an
  `open_door` edge as it catches the reverse. Since 2026-09-05 the doorway
  IS one object (`scene.passages`, § 2.37), with a `state` field carried for
  exactly this and read by nothing yet; the reconciliation is still open.
- **The planner calls `inspect_clock` every step (F10).** Half answered the
  same day: a tool whose answer rides a payload key (`inspect_clock` ->
  `clock`, `inspect_packages` -> `packages`; `payload_key` in
  `story/room_tools.TOOLS`) now echoes the key instead of re-reading, and an
  identical call whose answer is still in view echoes the step to look at
  (`agents/story_planner.py`), so the repeat costs a call and no characters.
  Still the owner's: whether payload-key tools should leave the manifest the
  model sees, or the card should say so -- the `story_planner` card does not
  yet.
- **The reachability warning's unit is the package (F30):** a road at two
  hops carries a depot at three without a word. Defensible; the owner should
  know the unit.
- **Two model tics measured, not fixed:** Gemini doubled quotation marks on
  two beats and eight quote-matching guards fired falsely (F29 -- FIXED
  2026-09-05, § 1.48); the characters cited no delivered observation on most
  beats (F14).

What the 2026-09-05 geometry run left open
([`experiments/DEBUG_RUN_2026_09_05.md`](experiments/DEBUG_RUN_2026_09_05.md),
four chats on an export-built scratch db; F36, F42, F43 fixed the same
day in `tests/test_played_scene_classes.py`). Each is an owner decision, or a
patch in a file another hand was editing that day:

- **A transit interior's doorway is derived, and the derivation says nothing
  when it overrides the Director (F37).** `world/spatial_transit.
  apply_transit_dock_edges` severs an interior room's exits when the carrier's
  `transit.phase` is `in_transit`/`sealed` with no `route_room`, and strips
  any edge the same beat's diff wrote on that room, silently. Chat 115 (copy):
  the objects hand answered "is this lift going down or up?" with `phase:
  in_transit, destination_room: null`; the lift lost its only exit, the next
  beat's Director minted a phantom corridor, the movement was refused as
  `separated`, the orphan room stayed in the scene, and the story fell down a
  shaft. Patch: the rewrite returns the edges it stripped and the merge
  warns once ("edges on an interior room are derived from its carrier's
  transit record; write the record, not the room"); whether a phase change
  with no destination should be refused is the owner's.
- **A new edge written from one side only leaves the far room without the
  doorway (F38).** `_mirror_symmetric_barriers` mirrors a BARRIER onto an
  existing reciprocal and, by design, mints no reciprocal for a new edge
  ("no reciprocal edge to mirror onto"). Chat 114 (copy), turn 4: the
  spatial hand minted `beach_far_end` with `adjacent: [{to: beach}]` and
  wrote nothing on the beach, so the mover was refused ("no passable route
  ... barrier=separated") for a beat. The passage record (§ 2.37) answers
  it; until then the patch is one branch: when BOTH rooms exist (scene or
  diff) and the reciprocal is absent, append it with the same barrier.
  `world/spatial_merge.py` edge code; test on the chat-114 shape.
- **The commit does not yet hand the Director the light notice the merge
  writes (F40's second half).** The engine half landed 2026-09-05 with the
  F40 ruling: a `sheltered` room whose declared word outranks the sky and
  which holds no light source of its own keeps its word, and
  `merge_scene_with_diff(light_report=...)` composes one line per such room
  asking for the source to be written
  (`spatial_light.unsourced_light_rooms`). Nothing passes the list yet.
  `persist/commit_scene_state.py` should pass `_light_report` beside
  `_crossing_report` and drain it through `ctx.tell_director`, which is how
  every other merge report reaches the Director.
- **The narrator originates the light (F41).** Chat 115 (copy), turn 5:
  the player asserted the lift's light had gone out; the resolve realised
  the claim as "observes the console under the interior lamp" (room `lit`,
  the lamp `lit`); the narrator wrote "the dark hides the controls
  completely". No fidelity check reads the light words. A clause or a
  check; the owner's.
- **Two writers, two vocabularies for an anchor's `dir` (F44).** The
  Director writes `dir: "c"` (the console at the centre of chat 114's
  room) and the merge keeps it; the World Browser refuses it ("dir must be
  one of n..nw"). Either the schema admits a centre or the merge folds "c"
  to no bearing. `web/world_routes.py`, reserved that day.
- **The hands write the level and not the shape (F45).** A scenario built
  to elicit geometry (a corridor that "turns sharply south", "a circular
  room") produced 0 of 4 rooms with `extent`/`shape`; a torch "throwing a
  tight beam" got `light_source: lit` and no `light_shape`/`pointed_at`; a
  candle that "gutters" got `state.guttering: true` and no `steadiness`; a
  ticking clock got `state.operating: true` and no `sound_source`. The
  source-class clause yields the level word and the hands invent their own
  switch words, which no field reads. Prompt work (the clause should say the
  switch IS `lit`/`running` and the wobble IS `steadiness`); the owner's.
- **A carried light recorded by position lights from the room's default
  cell (F46).** The house run: the torch moved with its bearer as a
  POSITION (`positions.hand_torch: corridor`), never as `held`; the field
  placed it at the room's entry and the bearer, six cells on, "stood in the
  dark" holding a lit torch. The objects hand's inventory floor is the fix
  the owner asked about before; the engine half would be: an unstationed
  portable source in a body's room with no holder takes the room centre,
  as a body does.
- **The Room cannot author geometry (F47).** NARROWED 2026-09-05, and half
  of it is built. `plan_rooms` now takes `extent {w, d}`, `shape` and
  `exposure` on a room and `vertical: up|down` on an edge, each normalized
  by the world's own reader (`spatial.normalize_extent`, `SHAPES`,
  `weather.EXPOSURES`, `spatial.normalize_vertical`) and each FAIL-OPEN --
  an unreadable value is no value and the room is what it is today. The
  preview shows what the plan measured, so a host can see when a
  measurement did not survive. `story/plot_packages.py`
  (`_plan_geometry`, `_plan_edge`), `tests/test_room_authors_geometry.py`.
  WHAT REMAINS, and it is `world/structure.py`'s: a planned room is rebuilt
  field by field at two further points -- `plant_structure`'s `normalized`
  dict and `skeleton_rooms`'s scene room -- so the three ROOM-LEVEL fields
  are dropped between the plan and the scene. Both need
  `extent`/`shape`/`exposure` carried through (three lines each; the edge
  dicts already survive whole, so `vertical` reaches the scene today).
  `parts` is deliberately not added: a composite room is authored by the
  map editor, and a plan that could draw one could draw an unreachable one.
- **An unstationed target is seen through the observer's own corner
  (F48).** `body_visibility` with no cell for the target falls back to the
  room relation; the house run delivered Mab's acts to Wren at the L's far
  bar with the parlour doorway behind the corner (`visual_level` was `none`
  with Mab stationed, `shapes` unstationed). Patch in `world/spatial_fov.py`
  (reserved that day): an unstationed body takes the room centre for sight
  as it does for light and sound, so the observer's shape is consulted.
- **The declared word is a floor, so a lone source cannot show (F50).** A
  parlour "relieved only by a single candle" declared `dim` composes
  uniformly dim: the floor equals the candle's peak, the falloff never
  quantises, the sentence cannot fire. Either the Director writes `dark`
  for a room lit by one thing, or the floor yields where a source stands.
- **A region the registry never named is entered as its id (F56).**
  `PATCH /regions/{id}` on `uminchi_guesthouse` created the entry with
  `name: "uminchi_guesthouse"`. `world/regions.py`, reserved that day.
- **A door anchor the hand writes lands by seed, not at the doorway it
  names (F58).** The spatial hand added `parlour_door` ("the open doorway
  leading into the corridor", `dir: n`) to a room whose doorway sits at
  `offset 0.9`; the seed put the anchor three cells from the door the
  engine's own implicit `door:corridor` anchor marks, and a body stationed
  "at the sill" spoke from three cells away. `stationable` already lists the
  implicit anchor; the hands do not use it. Prompt, or fold a hand-written
  anchor whose desc names an exit onto that exit's implicit anchor.
- **A refused walk leaves nothing behind (PC7, BUILT 2026-09-05, both
  halves).** `spatial.merge_scene_with_diff` consumes
  `state_diff.movement_refused` -- `[{subject, to_room}]` -- and subtracts
  that body's position, station and pose from the beat; `director._refuse_movement`
  writes one record per body at the moment the `Blocked movement` branch pops
  the position, for the declarer and for each `stranded` companion the same
  beat sent to the same destination. Manor turn 13's committed pose
  ("standing on the flagged floor of the long gallery" for a body refused
  entry to the gallery) cannot recur. **The SECOND half landed the same day**
  (PE2, PC7(b)) with the rule it belongs beside. A shut door is a CONTEST
  wherever it stands on the route, which is what the adjacent branch has
  always said and what the multi-hop branch refused to say on the objection
  that it "cannot attribute the contest to one specific door on a multi-hop
  path": `director_movement.declared_walk_leg` follows the walk edge by edge
  and attributes it. A route no doorway reaches is still a WALL and still
  refused whole; a route whose only impassable edges are `closed_door` is
  contested, so the resolve owns the crossing as it does at one hop, and where
  the resolve does not assert it the walk commits its passable PREFIX and
  stops at the door -- with the pose and station written for the room it did
  not reach dropped (`_strip_unreached_placement`), and every body the same
  beat sent to that destination out of the mover's own room stopping where the
  mover stopped. Measured cases closed: PE2 (four of six declared inter-room
  moves in an ordinary flat), PC7's turn 13. **What is NOT closed is F28's own
  remainder, PA12**: a declaration marked `arrives=false` for a step the
  player wrote as taken. The prefix rule was scoped to ARRIVING declarations
  deliberately, so that `scene.approach` and the approach-leg rule stay the
  one seam answering how far a non-arriving walk got; PA12 needs either the
  interpret's reading of such a sentence or a leg the approach guard derives
  when the beat placed the body nowhere.
- **One whisper, two grades in one beat (F61).** The act stage's
  deterministic floor grades speech through `hear_level`'s edge model (same
  room, whisper, near -> fragment); the outcome's delivery grades it through
  the field (signal/noise -> full). Same line, same bodies, two answers.
  The act floor should hand `hear_level` the field the outcome hands it.
- **The social hand's crowd op is not the schema's (F62).** "crowd op
  rejected: unknown crowd op 'open'" -- the throng the market scenario named
  never existed and the square had no crowd noise for the run. The warning
  is right; the clause should name the ops.
- **The Japanese pose sentence is half English (F59).** "youはatthe kitchen
  tablethe chairの上にseated": subject, posture and prepositions untranslated
  and unspaced. `language_adapters/japanese.py`, beside the note's known ja
  gaps. FIXED 2026-09-05 for every engine-owned slot in the sentence, and
  the class is now visible to the suite -- § 1.48. What survives is the
  authored prose the sentence carries, which is the owner decision below.
- ~~**The export bench captures no Writers' Room call.**~~ BUILT 2026-09-05,
  with one half outstanding. `persist/llm_capture.py` now has the room half
  of the recorder -- `room_capture`/`enter_room_capture` (the scope, armed
  by `story/room_conversation.converse` and `converse_stream`),
  `record_room_exchange`, `is_room_step`/`room_phase` -- and
  `story/room_calls.room_call` is the one seam a Room model call makes,
  recording what was SENT, what came back and the reasoning, under the same
  content-addressed dedup and the same off-by-default rule. A call is filed
  against the TURN IN PLAY under `room:<phase>` and `export_turn_debug`
  marks it `origin: "room"`, so one export reads in order: this beat
  happened, then the room said this about it (`room_calls_captured` counts
  them). `story/room_bible._call` goes through it;
  `tests/test_room_is_captured.py`.
  WHAT REMAINS, and it is `agents/`'s: `story_planner._call`,
  `dramaturge._call` and the two loops' own calls still reach
  `providers.chat_complete` directly, so the Planner and the Dramaturge are
  captured only once those three lines route through `room_call`; and
  `schedule_room_work`'s fill and pass jobs need a `room_capture(cid,
  "fill"/"dramaturge")` around their bodies, since `core/jobs.py` clears an
  inherited scope by design for every OTHER contextvar and a job's calls
  otherwise belong to no reply.
- **A Room reply's tool events carry no name and no result.** Measured in
  two runs: `{"tool": null, "args": null}` in the flat run's event stream
  and `result_head: None` on all 20 of the lighthouse run's calls, so a
  host watching the panel sees nothing and a harness has to read the tool
  names out of `run_planner`'s return. `agents/story_planner.py`'s
  `room_tool` events; the capture above answers the model calls and not
  these.
- ~~**The Room can plan a room above you but cannot say how you get up to
  it (PA7).**~~ CLOSED 2026-09-05. `plan_rooms.adjacent` takes
  `vertical: up|down`, read through `spatial.normalize_vertical`, and a
  vertical word arriving in `dir` or `bearing` is MOVED there rather than
  discarded -- up is not a bearing, which is the whole of what the
  lighthouse's sealed loft edge said. An edge dict survives the plant whole,
  so this one reaches the live scene today, and the far side's `down` is
  derived by `effective_adjacent` as it always was.
- ~~**A grant outlives the request it was granted for (PE14).**~~ CLOSED
  2026-09-05 on the engine side. A mandate may name the ASK it answers
  (`grant_mandate(request=)`), and it lapses when that ask ends: the package
  retired or resolved, the question off the room's status row, or
  `close_request` called outright. `expire_mandates` sweeps it on every read
  of the standing grants and stamps `lapsed_reason`, and `renew_mandate` is
  the explicit renewal -- a NEW row citing the one it renews, because a
  licence that came back to life in place would leave no record that anyone
  asked for it twice. A grant naming no request is standing, as every grant
  was before this. `story/mandates.py`,
  `tests/test_mandate_scope_and_totality.py`. Remaining, and the Planner's:
  pass `request` when it records a grant, and offer to close the request
  when the player withdraws one in words.
- **`plan_rooms` still cannot name a region, and should not.** The road run
  asked for `extent`, `shape`, `exposure` and `region`; the first three
  landed. A structure IS a region (`world/structure.skeleton_rooms` sets
  `region` from the structure key), so a per-room region field on the
  operation would be a second answer to a question that already has one.
  What the run actually wanted -- creating, splitting and altering regions
  -- is § 2.26's region tier, and is unbuilt.
- **The recap cites what it read (BUILT 2026-09-05), and the room has to be
  told to.** `story/room_citations.py` holds the contract and the check: a
  ledger of every row a reply actually read (filled at `room_tools.run_tool`,
  the one call site), and `check_claims`, which marks a claim `supported`
  only when every row it cites was read this reply. A claim citing nothing,
  or citing a row nobody served, is DEMOTED to a proposal -- it keeps its
  sentence and loses the authority it was borrowing -- and `converse` and
  `converse_stream` return the verdicts as `citations`. Measured cases it is
  for: "feigning sleep", the servant who was never sent, the salve "she
  declined". WHAT REMAINS, and it is two other owners': the Planner must
  emit `claims` in its reply envelope and be given `room_citations.
  CONTRACT_TEXT` in its system block (`agents/story_planner.py`), and the
  panel should show an unsupported claim as a proposal
  (`static/js/writers_room.js`, `web/room_routes.py` passes the envelope
  through untouched). Until the first of those lands every reply reads as
  `stated_nothing`, which is honest and is not a pass.
