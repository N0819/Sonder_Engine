# The Writers' Room — current plan

**Status:** plan, agreed with the owner on 2026-09-02 and 2026-09-03. Nothing
in this note is built unless § 3 says so. It compiles the decisions taken in
conversation on those two days against the two design documents it sits on:

- `DESIGN_WRITERS_ROOM_V2.md` (the owner's proposal; kept outside the repo in
  the owner's downloads at the time of writing, and the source for every
  section number cited below as "v2 § n").
- [`DESIGN_STORY_PLANNER_AND_DRAMATURGE.md`](DESIGN_STORY_PLANNER_AND_DRAMATURGE.md)
  (the original; still the authority for the plot package, evidence,
  Charter and mystery-integrity material v2 § 0 says remains useful).

The register of unbuilt work for the room is [`../UNBUILT.md`](../UNBUILT.md)
§ 2.26; the mapping retirement is § 2.26's Phase B, § 3.5 P6/P7 and § 4.3
Gap 5 there. When this note and `UNBUILT.md` disagree, fix `UNBUILT.md`
first.

## 1. What the room is

One persistent Writers' Room with two peer author agents and one narrow
subagent (v2 § 0):

- **The Story Planner** is the long-range world planner: prepared horizon,
  continuity, narrative *possibilities* (a field of actors, preparations,
  clocks and contingencies, never a sequence of scenes the player must
  perform — v2 § 3.2), locations, institutions, people, factions, material
  requirements, generation schedule.
- **The Dramaturge** is the dramatic intelligence: theme, tension, mystery,
  revelation, pressure, legibility, whether a situation is worth
  encountering.
- **The Charter Planner** stays a bounded subagent beneath the Planner. It
  turns one location requirement into one coherent populated place and is
  not a third peer (v2 § 3.4).

Four properties the room keeps whatever else changes:

1. **It runs outside the turn.** No room agent is in the roleplay pipeline.
   A publication completed mid-turn is visible no earlier than the next
   turn (v2 § 7.1, § 7.3). At rest it makes zero provider calls.
2. **The boundary is a package, not a chat.** A versioned, frame- and
   branch-scoped change package with truths, participants, evidence,
   pressures, clocks, requirements, operations, dependencies and provenance
   (v2 § 10), published atomically after validation (v2 § 7.2).
3. **Authority is budgeted, not switched.** The user grants standing budgets
   (so many major characters, institutions, settlements; ask before
   changing an established history) and the room consults only for the
   missing authority (v2 § 6.2). "Surprise me" is a sealed envelope whose
   boundaries, not contents, are approved (v2 § 6.3).
4. **It may author circumstances, never outcomes.** Live agency stays free;
   a derailment is canonical input the room plans *from*, never around
   (v2 § 3.2, § 7.5).

## 2. The division of labour, as settled on 2026-09-03

This is the part the v2 document did not say and the owner decided:

> The Writers' Room is responsible for the story *existing*. The Director
> renders causality at high fidelity around players and major characters.
> Charter simulates everything else off screen.

Three tiers, and every seam below is one of the three joints between them:

| tier | owns | mints |
|---|---|---|
| **Plan** (Writers' Room, authoring time) | what a thing is *for* and what is true of it before anyone sees it: identity, role, past, ties, what it carries, where the world's clock has put it | plans: rooms, people, creatures, artifacts, settlements, plots |
| **Render** (Director, simulation time, inside the causality bubble) | what the player and the major characters perceive and do this beat, and the objective outcome | *renders* of plans: the high-fidelity scene object of a planned room, body or thing when it comes into view — bounded by the plan, never a second author of identity |
| **Simulate** (Charter, simulation time, outside the bubble) | bodies walking, working, sleeping, meeting, trading, fighting, on the town graph and the day cycle | nothing; it *moves* what the plan put there |

Consequences the owner accepted with the split:

- **The Director mints only as a render.** A Director mint that names a role
  or a name a present plan already holds *is* a render of that plan (the
  identity floor from step 2 of the September plan already does this for
  charter bodies). A Director mint with **no plan behind it** renders the
  *surface* (a scarred guard with a limp) and files a typed **planning
  need**; the room fills the plan behind that surface by the next turn,
  under the causal-exposure rule (v2 § 7.4): it may not name a scarred guard
  and give him no scar. Nothing about *who* the guard is was ever the
  Director's to decide; nothing about what he *looked like* was ever the
  room's to contradict.
  **Carve-out (owner, 2026-09-03): the Director still mints CONTAINMENT
  rooms on the fly.** A body the beat puts another body inside is a place
  the moment it happens — the spatial hand's `state_diff.rooms` with
  `parent_entity` — and no plan can hold it in advance, because it exists
  only while the containment does. It is not a plan gap: the compiler
  classifies a destination that is a scene entity or its interior as
  `contained`, never `unplanned`, and a room whose committed record carries
  `parent_entity` files no planning need. The rule is the one the engine
  already has: where a body walks is its own; where the world puts it is
  the Director's.
- **A body the town says is at the forge cannot be rendered at the inn.**
  Charter's position ledger is part of the plan the Director receives. If
  the story needs the smith at the inn, that is a planning revision through
  the room, not a Director convenience.
- **The ambient charter dies.** `charter_runtime.ensure_ambient_bodies` and
  `AMBIENT_CHARTER` exist because 84 of 98 tracked background presences
  once had no charter body. Under plan-and-render a fill *enrols* a person
  into a real charter (the institution whose post the role names, else the
  households charter, else a minimal households charter minted for a story
  with no town; a visitor is a guest of the inn's charter with a departure
  the town can run). There is no third tier for a placeholder to occupy.
- **The offscreen specialist dies.** It ran on 1 of 40 replay turns. Its
  channels split three ways: `crowd_ops` and `courier_ops` to charter (a
  crowd is a charter projection already; a courier is a body walking a
  route with news); `offscreen_plan_ops` to the character frames / the
  room's planning (the Director does not own psychology); `telling_ops`,
  `ratified_claims`, `contradicted_claims` to the social hand (they are
  speech consequences and already in `SPEECH_WRITTEN_CHANNELS`,
  `agents/director_scopes.py`). Retire it with the mapping agent, not
  alone, because `courier_ops` waits on charter carriers.
- **Off-screen major characters** get character frames / causality bubbles
  (a playerless frame running the ordinary plan) so they form memories
  normally. **Time skips** are the one case with no beats to rule, and are
  charter's: ask each major character present what they intend for the
  skip (silence is sleep), a deterministic feasibility floor on the town
  graph (place exists, reachable at the walk rate, phase permits, standing
  to be there), temporary enrolment into a charter under an explicit,
  reversible projection of the card (intention → errand, drive → which
  needs win), then a **rich** memory mint at the end — the pre-story
  historian's shape (10–16 first-person episodes of 45–180 words, each its
  own row with valence, arousal, consequence, lesson) with the licence
  narrowed from *invention* to *texture*, the count scaled to the skip's
  length, summary tier, off-screen origin mark, and psychology advanced
  deterministically from the same inputs. The owner's requirement, verbatim
  in spirit: not "one line of I did x"; memories have details and are
  personal.
- **Creatures and look laws are room-authored data**, not engine special
  cases (§ 4).

## 3. What is already on main that the room stands on

Landed 2026-09-02 → 2026-09-03 (the five-step plan, the day cycle, the
charter-interaction forks, the replay-defect forks). Named so the room's
authors read the seam and not the design:

- **Planned rooms are furnished on entry** — the template for every
  plan-and-render seam: `structure.rooms_to_develop`, `planned_room_brief`,
  `protect_planned_edges`, `settle_developed_stubs`, the Director payload's
  `planned_rooms` and the card clause "a room you are handed as planned
  exists and is yours to furnish". Measured on the replay: 39 of 39 planned
  rooms survive turn 0 with every edge (4 of 19 before).
- **The opening commit keeps the plan** — `seed_scene_from_plan` and
  `structure.planned_room_ids`; a room minted under a planned name lands on
  the planned room; a frontier stub is named for the axis it leaves on and a
  planned name is reserved (`structure.mint_frontier`).
- **Closure invariants** in `world/charter_generate.py` — population as a
  closure input (`POPULATION_TOLERANCE`), one seat per head post
  (`HEAD_SEATS`), `BERTH_CEILING`, a historian budget that holds
  (`HISTORIAN_TOKENS_PER_RESIDENT` and its siblings). The Charter Planner's
  "plan suitable for deterministic closure" (v2 § 3.4) is this closer.
- **Prehistory walks the planted skeleton** and is anchored on the story's
  day (`presim_registry(scene=, story_day=)`).
- **The day cycle** — `world/day_cycle.py` (closed phase table, per-story
  `day_length_hours`), outdoor light from the sun, charter homecomings.
- **Charter bodies are people you can deal with** — `charter_author.FIGURE_ACTS`
  (greet/ask/tell/accuse/tend/order/request/bargain/promise/trade/give),
  the identity floor (`director_floors._bind_minted_entities_to_present_figures`),
  `agents.common.present_charter_figures` with the ledgers' `answers`
  shown to the Director, `charter_runtime.presence_view` for the voice,
  worn and handed things following their holder, private berths,
  promotion proposals at named thresholds.
- **The provenance seam** — `mind/canon_provenance.promote`: the
  deterministic structured write the mapping agent's lore filing retires
  onto (v2 § 9.4's `commit_world_facts`).
- **Room geometry** — `world/spatial_fov.py` (footprints, heights, opacity,
  shadowcast, `sightlines` payload), prototype; extend only after the
  replay's station/cover write rate is measured (34/40 stations, 0/40
  cover, sightlines not persisted — unmeasured).
- **The dispatch-keyed Director** — a hand runs when the ruling reaches it;
  replay: 17 → 8 model calls per turn, unique roles per turn 8.7 → 5.3.
- **The plot package and the facade** (Phase B.1–B.2, 2026-09-04) —
  `story/plot_packages.py` (the store and lifecycle; `OPERATIONS`, the
  closed table that IS the author layer) and `story/room_tools.py` (the
  tool table the Story Planner will be handed; `tool_manifest`,
  `run_tool`). A package lands only through existing seams and is visible
  from the next turn.

## 4. In flight (2026-09-03), and how the room will author them

Both are engine schemas now and room packages later; the room writes files
into the same schema the fixtures use.

- **The look law.** Planner-authored pools per population (stature, build,
  complexion, hair, age band, marks) dealt deterministically per body, as
  the naming law deals names; occupation as what is *worn and marked* from
  the post/upkeep tables; silhouette and face tiers graded by light; the
  stranger descriptor from the surface alone; the Director's render-on-view
  settled back onto the body once. Motivation: every townsperson in the
  replay was "an indistinct figure" because no charter body carried any
  appearance text.
- **Creatures as charter data.** A creature is an institution whose upkeep
  is fed from other institutions' bodies or stock, whose triggers are
  authored, and whose evidence is left in the world. Op classes the engine
  owns: harm model (condition well/hurt/dead/missing), predation as a seeded
  encounter contest, prey table, senses and footprint (a shut door holds
  against a wolf, not a bandit), spoor as artifacts (`story/artifacts.py`),
  authored triggers/ops (`charter_trigger`, `charter_intervene`: relocate
  lair, flee, dormant, boldness dial, tribute bargain), institution shape
  (succession, sentries, hoard), and **mobilisation** — a watch shock when
  a body with standing holds a threat claim above a credence threshold,
  raised by harm news or by a player's `tell`. Contest weights, encounter
  odds, kill-rate ceiling, credence threshold, duration and crew fraction
  are authored per charter, never engine constants. Fixtures: wolf pack,
  bandit band, dragon with tribute. Design note to land with it:
  `DESIGN_CREATURES_AS_CHARTER.md`. Fidelity ceiling in pure code: a
  creature whose behaviour changes in response to what the town does and
  is legible from what it leaves behind. The novel move, deception and
  speech stay the bubble's.

## 5. The phases

Ordered by dependency. Each phase is a fork or a few; each lands on main
with `make check` green and a row in `Design.md`.

### Phase A — engine seams, no room agent yet

Everything here is deterministic and measurable on the Harrowmere replay
without a room in the loop. It is the widened "step 5".

1. **Planned entities** — *landed 2026-09-03* (`world/planned_entities.py`;
   `UNBUILT.md` § 2.33). A `planned_entities` ledger with a brief, the same
   three functions the room handoff needed: a view that puts the plans in
   view into the Director's resolve payload (charter bodies as the first
   plan source, through the position ledger), a settle that writes the
   render back, and a reservation so a mint naming a planned identity is a
   render of it. Measure: replay duplicates (7 mints / 6 shadows → 0).
2. **Surface + planning need** — *landed 2026-09-03* (`world/charter_enrol.py`;
   the ambient charter is deleted). A Director mint with no plan behind it is
   surface-only and files a typed planning-need record (room, person,
   thing; with the committed surface attached). A deterministic fill
   answers it *today* by enrolment into a real charter (§ 2), so the
   ambient charter is deleted along with every branch that names it; the
   room replaces the deterministic fill with an authored package in Phase B
   without the seam moving.
3. **`compile_world_context` replaces `mapping_stage` / `mapping_quick`**
   (v2 § 9.2, § 9.5). The deterministic compiler assembles what the two
   model stages assembled: the planned brief, geometry and sightlines,
   nearby rooms, owed history, retrieved lore — and emits a planning need
   for a creative miss instead of inventing (v2 § 9.3). The mapping agent's
   *filing* half moves onto `canon_provenance.promote` as a structured
   write; its *creative* half becomes the planning need. Measure: the
   replay's 21 `planned_context` calls and 12 hits become 0 calls.
4. **Retire the offscreen hand** as in § 2, once charter carriers cover
   couriers.
5. **Planning-need queue and job** — *landed 2026-09-03*. The record type, its frame/branch
   scoping, and a `core/jobs.py` job that drains it — the deterministic
   fill now, the room's job later.

### Phase B — the room, minimal

*Landed 2026-09-04, all four items: the store and facade (`story/plot_packages.py`, `story/room_tools.py`), the Planner (`agents/story_planner.py`), the mandates (`story/mandates.py`), the frontier and fill job (`story/room_frontier.py`). Residuals in `docs/UNBUILT.md` § 2.26.*

1. **Package store and lifecycle** (v2 § 10, § 7.2): draft → validating →
   published → active → resolved → retired; pinned base world revision;
   rebase-or-conflict on intervening history; atomic publish with the short
   transaction *after* the long model calls; next-turn visibility.
2. **Authoring facade tools** (v2 § 8) as code over existing seams: scan and
   search lore with stable ids and citations; inspect structures, routes,
   rooms, reserved identities, charters, bodies, events, clocks, plans,
   contradictions and dangling references; request charter generation and
   presimulation; draft operations; preview the cross-system diff;
   validate; publish. No direct SQL.
3. **The Story Planner agent** with Charter Planner delegation and
   just-in-time fill jobs answering Phase A's planning needs (rooms,
   people); the prepared frontier (v2 § 3.3) as reserved identities and
   planned rooms along likely directions.
4. **Budgets and consultation** (v2 § 6.1, § 6.2), including a line for
   *identity fills* — every unprepared stranger is a room job, and frontier
   depth is what keeps it small.

### Phase C — the Dramaturge and plots

The owner's shape for the pair (2026-09-03), which is the product-owner /
engineer shape rather than author / reviewer:

- **The Dramaturge is pure planning.** Its input is the player's input and
  the narration output — the player-visible stream, which is spoiler-safe
  by construction and cheap — plus its own standing plans, the genre, and
  how much the player asked to be surprised. It thinks: *what would be a
  good progression of this story, from what I know of fiction, the chosen
  genre, and how far I am licensed to surprise?* It proposes direction:
  pressure, reversal, revelation, a turn nobody asked for. It holds **one
  tool, and it reads**: lore search and lookup (`search_lore`, `read_lore`,
  bounded per proposal), because the setting bible is the one thing it
  cannot propose without — a heresy trial needs a faith to exist — and it
  is now almost solely an author's reference (owner, 2026-09-03: the story
  and its history exist as the physical map of rooms and people; lore is
  what the map cannot hold). It never inspects the live world and never
  writes it; the Planner fetches everything else it asks for and cites it
  back. Its output is intent, not a package.
- **A creativity dial, per story and named.** From holding to a target the
  player stated (a mandate the room was given) to wildly inventive. The
  dial is a setting the user turns, not a property of the agent.
- **The Story Planner judges naturalness, then plots the implementation.**
  Its criterion is that the result *feels like something that happened
  within the world*. It carries the tools, the citations and the budget,
  and it does not blindly implement a Dramaturge proposal: it answers with
  geography, identity, causal history and cost ("that character is dead",
  "that town is three days' walk", "that would retcon a sealed truth with
  realised evidence"). The Dramaturge answers back on whether the natural
  version is still worth encountering. That is the deliberation loop
  (v2 § 5), bounded in rounds, ending in a package or in a disagreement
  returned to the user.
- **The Planner's intervention toolkit, used sensibly.** Beside the local
  ops below, the Planner may **nudge a charter body of its choice**: an
  errand toward a place or a figure, a need or drift shock, a trigger
  armed on that body, a claim *delivered through a channel* (a carrier, a
  letter, a rumour at the market), a commitment opened. A nudge is a
  pressure the body's own state answers — it biases the decide seam the
  way a project biases appraisal — never a puppet string; a body whose
  ledgers say no still says no, and the Planner reads why. What the Planner
  may **not** do is write a body's mind directly, or touch a major
  character at all except by arranging circumstances that reach them
  through a channel (an arrival, news, a summons): the firewall is the
  same for authors as for models. "Sensibly" is a budget: nudges per story
  hour, named and per story, alongside the pacing budget.

**Local drama is a first-class op set, not a side effect of exploration**
(owner, 2026-09-03: "drama shouldn't purely be from exploration"). The room
runs outside the turn and publishes for the next beat, which is close
enough to be *local*: the package's `pressures`, `clocks` and
`opportunities` (v2 § 10) need concrete ops that reach the player's
locale through existing seams, and the room may use them without a
planning miss having occurred:

- **an arrival** — a courier, caravan, visitor or creature reaches a named
  place on a clock (`story/couriers.py`, charter routes, a creature
  trigger), carrying news, a letter or a grievance;
- **an errand aimed at a figure** — a charter body is sent to find the
  player or a major character (the clerk fetches you to the reeve; the
  innkeeper's child knocks), through the post's own reporting line;
- **an incident at a place** — a charter shock (`charter_intervene`:
  need, upkeep, watch) or an authored trigger fires where the player
  stands, and the bodies there act on it: a brawl, a collapse, a theft,
  an alarm;
- **a summons or invitation** — a commitment opened toward the player
  (`charter_commitment`), so refusing it has a ledger;
- **a placed artifact** — a letter under the door, a mark on a wall, a
  body in the alley (`story/artifacts.py`), read by whoever reads it;
- **a scheduled consequence** — a fuse the living-world floor fires at a
  location (`world/living_world.py`, `world/mechanics.py`), noticed only
  by who is there.

Every one of these authors a *circumstance that arrives*; the Director
rules what happens when it does, and no op writes the player's conduct
or a major character's mind. The Dramaturge's dial governs how much of
this the room reaches for; a **pacing budget** (pressures per story
hour, named and per story) keeps it from becoming weather.

Then: sealed envelopes and surprise authorization (v2 § 6.3), spoiler-safe
status (v2 § 5.3), plot packages with truths, evidence, clocks and
pressures, mystery integrity (v2 § 4.3, and the original design note),
derailment replanning (v2 § 7.5).

**Region events** (owner, 2026-09-03: "big disaster events like large
regions of a story map being damaged at once or sequentially over time").
One op class with a footprint, a profile in time, and per-room effects
that are all existing ops:

- **Footprint:** a set of rooms named directly, a lorebook scope (the
  destruction domain's cascade already walks scope + registered rooms,
  `persist/commit_destruction.py`), a graph radius from an epicentre, or a
  spatial `zone`.
- **Profile:** *at once* (every room in the footprint on one beat), a
  **front** (a due event that advances over passable edges at an authored
  rate per window — fire along a street, flood from the river, a siege
  line — through the living-world fuse machinery, `world/mechanics.py`
  `_fire_due_events` and `world/living_world.py`), or a **decay** (a
  plague: a contagion trigger on co-presence, the creature fork's
  condition model spreading by the encounter odds).
- **Per-room effects**, each one op: **damage** as a state short of ruin
  (burning / flooded / collapsed / blocked — a hazard the composer
  renders, geometry marks impassable or as cover, and charter routes
  avoid like a known threat); **destruction** (retire-not-delete, ruin
  kept, `commit_destruction`); **shocks** to every charter serving an
  upkeep there (`charter_intervene`); **harm** to bodies present by the
  contest (creature fork); **displacement** — bodies whose berth is gone
  relocate to another charter's berths or the commons (the creature
  fork's relocation op, applied to victims: refugees are an enrolment);
  **artifacts** left (rubble, the dead, a notice); **news** by carrier;
  **weather** where the event is one (`weather.room_exposure`).
- **Afterwards:** rebuilding as a town **project** — an upkeep that
  restores a damaged room over hours, staffed from the posts, so a burned
  street is a thing the town is seen doing something about; the
  head-seat rule re-elects the dead; grievances and politics follow.

The player's bubble sees it when it arrives: a fuse notice fires only
where the player stands (the living-world floor's own rule), and the
Director renders the beat; off screen, charter and the harm model carry
it. The room authors it as a package with a clock; the Planner judges
naturalness; and **the player has to allow these as things** (owner,
2026-09-03). The default budget for region events is zero: the room asks
every time until the player grants a scope — which kinds, what scale,
which characters and places are protected, whether permanent loss is
acceptable — through the **harm and permanent-loss budget** (v2 § 6.2) or
a sealed envelope (v2 § 6.3). Silence is not authorization. The same
default holds for a nudge that would harm and for any local op that is
irreversible; ordinary local drama (an arrival, an errand, a summons)
runs under the pacing budget once the room is enabled at all. Prerequisites: the creature fork (harm,
relocation, mobilisation) and Phase A.1 (planned entities, so displaced
bodies have somewhere to be).

### Phase D — the room authors the data tiers

Room-written creature files and look laws (§ 4); time-skip plans and the
skip memory mint (§ 2); lore curation out of band (`curate_lore`, v2 § 9.4);
character cards where the psychology authoring rules (drive non-empty,
values as trade-offs — `CLAUDE.md`) become package *validation* rather
than warnings, the eleventh surface after the ten `character_card_warnings`
already runs on.

## 6. Open decisions for the owner

Each changes what a phase builds; none blocks Phase A.

1. **Frontier depth and the identity-fill budget.** How many reserved
   identities and planned rooms the Planner keeps ahead of the player, and
   the per-hour ceiling on fills. Both are caps and will be named.
2. **Same-turn fills.** Phase A answers a planning need deterministically
   in the same commit (enrolment). When the room exists, does a
   same-beat need still get the deterministic fill (and the room refines
   it next turn), or wait a turn for the room? Recommended: keep the
   deterministic fill as the floor; the room refines.
3. **Skip-minted memories distinguishable from frame-minted ones.**
   Recommended yes, by origin and credence, so a character can say "I
   think I spent most of that week at the forge" and an audit can tell the
   two resolutions apart.
4. **`mapping_quick` too.** Phase A.3 retires both mapping stages; if the
   quick stage's cheap movement classification is wanted as a deterministic
   pre-pass, it survives as code, not a call.
5. **The user experience** — settled in shape (owner, 2026-09-03), and
   BUILT in both shapes on 2026-09-04 (`static/js/writers_room.js`,
   `web/room_routes.py`, `story/room_conversation.py`; the Planner seam is
   `room_conversation.PLANNER`, a placeholder until Phase B seats the
   agent): the
   room is **a popout panel in the main UI**, opened from a small tab on
   the right edge of the play view, so the story and the conversation
   about it are on one screen (the Dramaturge's input *is* the
   player-visible stream). Built in two steps: first **docked right**,
   resizable in width from a drag handle and collapsing to its tab (the
   existing slide-in drawer on narrow viewports); then a **float mode**
   that undocks it into a draggable, corner-resizable window over the
   story. Dock state, geometry and opacity persist per viewer (local
   storage, defaults when blocked). Two rendering rules the page already
   has decide the look, and the panel reuses them rather than inventing
   a third: **docked, it is opaque chrome** (`static/styles.css` "OPAQUE
   CHROME": every surface directly over the page background is opaque,
   so an ambient colour meant for the story never washes the frame);
   **floating, it is the prose plate** (`body.has-backdrop .prose`: the
   translucent plate at `--bd-panel`, the 3px backdrop blur, the
   four-way text outline, and the same weather gate that drops the blur
   while streaks move behind it). The float sits over the story column
   the way the prose does, so it earns the prose's treatment; the opacity
   slider drives `--bd-panel` for the panel alone, above the readable
   floor the prose rule already assumes. Its own script and routes, loaded
   after the chat script, sharing only auth and theme helpers, so it
   stays out of the turn pipeline's scripts. (An earlier note here said
   a separate tab; superseded the same day.) In it the player talks with the Story
   Planner (and through it, or directly, with the Dramaturge), reads the
   spoiler-safe status of standing plans (v2 § 5.3: what is in motion,
   never what it is), and sees the room's questions when it asks. **It
   looks like a simple LLM chat interface** (owner): one conversation,
   the Planner answering, the Dramaturge's contributions shown or
   summarised as the visibility setting allows (v2 § 5.2); the standing
   mandates and the plan status are the only things beside the chat. No
   forms for budgets or events — those are sentences. Detail (how a
   sealed plan is represented, what the status line shows) is Phase B
   work.
6. **Budgets are set by talking.** Event and op scale — what the room may
   do, how big, to whom — is granted by telling the Story Planner what
   you allow it and the Dramaturge (v2 § 6.2). The conversation is the
   intent; the grant is **state**: the Planner writes it back as a typed
   mandate (v2 § 2.2 "conversation is intent; typed operations are
   state"), frame- and branch-scoped, shown as a standing list the player
   can read and revoke, and cited by the Planner when it declines or asks.
   Defaults for a new story are the zero-harm floor above; everything
   else is granted in words.

7. **The room's memory: the story bible.** Measured on the first live runs
   (chat 111, 2026-09-03): the Planner reads the last 30 thread lines and
   nothing older, rebuilds its whole payload every step, and keeps no
   memory of a reply once the thread rolls past it. Its typed state
   (mandates, packages, status, needs) IS a compaction of intent -- but only
   of the part that has a typed home. What rolls off is exactly what a
   writer regrets losing: what the player asked for and in what words, what
   the room promised, what it planted meaning to pay off, what it decided
   against and why. Recommended design, the **story bible** (`room_bible`,
   frame-scoped, shown in every payload, read later by the Dramaturge too):
   - **Typed state first.** Anything that can be a mandate, a package truth,
     question or clock, a planning need or a lore entry goes THERE, and the
     bible holds a pointer. The bible is for what has no typed home: intent,
     promises, setups, taste, rejections.
   - **Sections, not a summary.** `wants` (what the player asked for, in
     their words, and their hard nos; a reversal keeps both lines), `promises`
     (what the room said it would do and has not; one with no package behind
     it after a while becomes a question), `setups` (planted and unpaid, with
     where the evidence lives -- the Chekhov ledger; an unpaid setup never
     falls off), `open_loops` (questions the story raised and what would
     answer them), `paid` (payoffs landed, one line each, so nothing is
     planted twice), `decided` (decisions and rejected alternatives with the
     reason, so the room does not re-propose or contradict itself), `voice`
     (genre, tone, the creativity dial as the player stated it).
   - **Particulars, not gists.** An entry is a sentence carrying names,
     turns, room ids and the player's phrase, with a `source` (message ids,
     a package uid, a lore id) and a `since_turn`. Code refuses an entry
     with no source or a source that does not exist. Same rule as character
     memory: detailed and personal, never "the player wanted things".
   - **When it fires.** Out of band (`core/jobs.py`, keyed `room_bible`),
     never in a reply's wall clock: when the thread holds a batch of lines
     older than the window not yet folded, one bounded model call is asked
     what in those lines a writer would regret forgetting, under the schema
     above; a publish or resolve adds its line deterministically with no
     call. A line leaves the window only after the fold.
   - **Author memory, never mind memory.** The bible is served to the room's
     agents and to no mind; it is not a channel. Caps to name: bible chars
     shown, entries per section, the fold batch, the fold call's tokens.
   - **Caching, the same measurement.** The tool table was 10.3k of a 13k
     payload and identical on every step; it now rides the system block,
     which the provider seam marks cacheable, and the per-step message fell
     to 3-10k. The bible belongs beside it: stable within a reply, so the
     per-step message is only the transcript, the budget and the thread.
     `cached_tokens` read 0 on every live call (Gemini through OpenRouter);
     the block is arranged for the providers that honour it.

## 7. Measures

The Harrowmere replay (`../../demos/harrowmere-replay-2026-09-03/COMPARISON.md`)
is the baseline every phase reports against, on the same brief, seed and 40
first-person inputs:

| measure | baseline (09-02) | replay (09-03) | target |
|---|---|---|---|
| Director-minted people / duplicating a present post-holder | 10 / 8 | 7 / 6 | 0 / 0 (Phase A.1–A.2) |
| duplicate rooms | 8 | 6 | 0 (landed with fork J; confirm) |
| planned rooms surviving turn 0 | 4 of 19 | 39 of 39 | hold |
| `planned_context` model calls : hits | 23 : 15 | 21 : 12 | 0 : — (Phase A.3) |
| model calls / turn (median) | 17 | 8 | ≤ 7 with mapping retired |
| charter observations acquired | 0 | 213 claims / 27 turns | hold |
| stranger descriptors that are the fallback | all | all | 0 at full light (look law) |
| offscreen hand calls | 38 turns | 1 turn | 0 (retired) |

## 8. What not to do

- Do not start the room agent before Phase A.1–A.3 land: without planned
  entities and the planning-need record there is nothing for it to answer
  and its output has nowhere to go.
- Do not extend the geometry grid before the station/cover rate is measured
  on a run that persists `sightlines`.
- Do not give the Director a plan-authoring channel "for now"; the whole
  argument of § 2 is that the render and the plan have different authors.
- Do not model a creature, a look, or a skip as an engine special case; each
  is a file in a schema the room will write (§ 4).
