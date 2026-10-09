# Story Planner and Dramaturge — an author-side writers' room over a living world

**Status: the argument; the agents now exist.** The Story Planner
(`agents/story_planner.py`, with the Charter Planner as one scoped call,
`CHARTER_PLANNER_TOOL`), the Dramaturge (`agents/dramaturge.py`) and the
plot package with its lifecycle (`story/plot_packages.py`) were built
2026-09-03/04 to the plan in
[`DESIGN_WRITERS_ROOM_PLAN.md`](DESIGN_WRITERS_ROOM_PLAN.md), which is the
implementation authority; the `Design.md` rows are "The Story Planner is a
bounded tool-using loop over the facade" and "The Dramaturge proposes
direction and builds nothing". The unfinished work is registered in
[`../UNBUILT.md`](../UNBUILT.md) §§2.9 and 2.26 (no proposal card, the
Planner's tool discipline unmeasured live, mandates per era not per package,
the frontier a count not a ranking). This note argues for the product and
authority shape; where it and the plan disagree, the plan won. Since the
owner's ruling of 2026-10-08 the Dramaturge suggests in every story on its
pacing, with no grant (§ 4.6).

The Charter-specific data seams in
[`FABLE_TOWN_IMPLEMENTATION.md`](FABLE_TOWN_IMPLEMENTATION.md) §5 are the
technical precursor. This document widens them into one conversational
Writers' Room agent set with broad sway over the story. It also separates the
**Charter Planner** as a narrow subagent beneath the Story Planner. Its whole
job is to turn a location requirement into one coherent populated location;
it is not a third authorial voice and does not own plot.

The earlier **Geographer** name in
[`../experiments/WORLD_METABOLISM_FIRE_RATES.md`](../experiments/WORLD_METABOLISM_FIRE_RATES.md)
described the physical-planning half of this job. **Story Planner** supersedes
that name because the job also plans lore, institutions, generation timing and
continuity. Geography remains one capability, not a third agent.

---

## 0. Verdict

Build one persistent, intercommunicating **Writers' Room** agent set after
Charter is integrated and stable. It presents two principal author-side agents:

- The **Story Planner** maintains the world and campaign plan: future
  locations, routes, people, histories, generation timing, continuity and the
  material requirements of approved plots.
- The **Dramaturge** authors dramatic situations: mysteries, conspiracies,
  conflicts, secrets, clocks, evidence, reversals and campaign-scale plot
  structures.

Whenever a proposal requires populated-location construction, the Story
Planner delegates it to one internal specialist:

- The **Charter Planner** turns a bounded location brief into a coherent
  populated place: structure, institutions, posts, bodies, naming law,
  material conditions, local history and presimulation. It returns that work
  to the Story Planner for integration with the wider story.

```text
Writers' Room
├── Story Planner
│   └── Charter Planner subagent
└── Dramaturge
```

Story Planner and Dramaturge are specializations, not authority silos. Both
may propose coordinated changes across every story system under the host's
mandate. Their distinction is the question they lead with: the Planner asks
*what must exist and remain coherent?*; the Dramaturge asks *what situation is
worth encountering?* The Charter Planner alone is deliberately narrow.

The host can chat with either separately or with both in a writers' room. Their
conversation produces typed proposals. A proposal changes no story until the
host approves it or grants an explicit standing mandate whose scope is stored
and inspectable.

Once approved, a plan may influence lore, characters, memories and prehistory,
scene and spatial state, time, Charter, Living World policy, scheduled events,
Background Life configuration and other story systems. “Sway over everything”
does not mean untyped database mutation: the Writers' Room uses each system's
authoring or commit facade, applies a multi-system change atomically, records
the authority that permitted it, and exposes the diff to the host.

The result is **broad authorship over simulated reality**:

```text
host's premise and constraints
        ↓
Story Planner ↔ Dramaturge
        ↓ as needed
Charter Planner for populated-location construction
        ↓ typed, reviewable proposal
approved story plan / plot package
        ↓
lore + structure + Charter + scheduled circumstances
        ↓
Director adjudication + Background Life + character agency
        ↓
events, memories and consequences nobody pre-wrote
```

An overarching plot is permitted. A railroad is not required. The agents may
author the murder, culprit, motive and evidence that existed before play; they
may not silently change the culprit after the player forms a theory, decide
what a live character chooses, or force the player through a prescribed scene
sequence.

---

## 1. Why these agents exist

Charter answers a question the original off-screen design treated as an
illusion: *what was the world doing while nobody watched?* It can advance large
populations of bounded but coherent minds cheaply, and Background Life can
render one of those people with richer intelligence when attention reaches
them.

That still leaves two authoring questions:

1. **What should be prepared before attention reaches it?**
2. **What larger dramatic situation might the player encounter?**

Without a planner, the engine either generates too late, generates too much,
or waits for the player to state every location explicitly. Without a
dramaturge, Charter can produce authentic institutional history and emergent
pressure, but it has no author-side hand able to deliberately construct a
murder mystery, political conspiracy or thematic campaign.

Raw model generation is not the answer to either. A model asked at the doorway
to invent a town and its history produces retroactive evidence, pays the full
cost at contact, and has no durable account of why its facts are compatible.
A model asked every turn to keep a plot alive tends to steer characters,
retcon established truth and spend continuously.

These agents instead work intermittently, ahead of contact, through stored
plans. They spend model calls on authorship and leave continued existence to
the simulation.

---

## 2. Three layers that must not collapse

### 2.1 Authorship

The Story Planner and Dramaturge are **not fictional minds**. With host
permission they may read objective state, private Charter minds, diagnostics,
unrevealed lore and sealed plot truth. The information firewall governs what
they may cause to enter a fictional mind, not what an authoring tool may inspect.

Their outputs are author claims. They become canonical only through an
approved cross-system change set. The set may deliberately author a mind,
memory, relationship or event when its mandate permits that act; the stored
provenance must distinguish authored prehistory, explicit retcon and events a
mind actually lived. Broad authority must not erase the difference between
those origins.

### 2.2 Simulation

Charter, the Living World, scheduled events, carriers, the spatial model and
the Director determine what happens after authorship establishes initial
circumstances. This layer owns causal state, not dramatic intent.

### 2.3 Rendering and cognition

Background Life and character agents make situated choices from the particular
past and present each person owns. Narration renders the player's legitimate
slice. No plot note, diagnostic, hidden solution or author conversation may
enter these payloads unless it has become information through a fictional
channel.

The layers meet at stored, typed seams. They do not share a prompt. The
Writers' Room may sway all three layers through their public authoring
surfaces, but no private author diagnostic or hidden plot premise becomes
fictional knowledge merely because an agent used it to design a change.

---

## 3. The Story Planner

### 3.1 Responsibility

The Story Planner maintains the story's **prepared horizon and campaign
continuity**: enough plausible world exists ahead of likely movement that
arrival can be immediate and grounded, without generating an exhaustive globe.
It is also the integrator for every world-facing requirement the Dramaturge or
host introduces.

It plans:

- Likely-next locations and alternate travel directions.
- Connections, routes, travel scale and access constraints.
- Location purposes and the institutions needed to fulfil them.
- Lore requirements and conflicts with existing canon.
- Named figures or Charter populations required by an approved plot.
- Generation and presimulation jobs, their priority and cost budget.
- Which planned material remains provisional and may still be discarded.
- Continuity between prepared locations, existing structures and live rooms.

It is allowed to be genre-aware through lore and the host's story brief. Core
generation remains genre-agnostic: the plan can ask for a haunted abbey or a
generation ship, while structure and Charter still operate on places, routes,
bodies, posts, material needs, claims and events.

### 3.2 Predictive staging

Predictive staging is a performance and continuity optimization, never a claim
that the engine knows where the player will go.

The Planner may rank candidates using only author-side evidence:

- Exits and routes visible from the current prepared horizon.
- Player-authored travel declarations and standing destinations.
- Known character projects that name places.
- Approved plot requirements.
- Host instructions and campaign boundaries.

It should prepare a small frontier, not a single predicted destination. A
player taking an unprepared direction is an ordinary miss: generate on demand,
show progress honestly, and update the Planner's assumptions. Never redirect
the player to protect staged work.

### 3.3 What it reads

The Planner may read:

- The selected lorebook tree and story canon.
- Existing structures, room identities and route graphs.
- Charter definitions, warnings and public/private author diagnostics.
- Approved plot packages and their location requirements.
- The story clock, prepared frontier and generation-job state.
- Objective world events needed to avoid contradictory prehistory.

It does not need raw provider reasoning, narrator prose as ground truth, or a
fictional mind's uncommitted chain of thought.

### 3.4 Cross-system sway

All writes are proposals until approved or covered by a standing mandate. An
approved Planner proposal may coordinate changes across:

- Lore entries through the ordinary lorebook route.
- A normalized `story_plan` containing structure directives, Charter emphasis,
  named figures, constraints and generation budgets.
- Planned structure and frontier rows through the lived-location generation
  operation.
- Validated consequence fuses when a future objective circumstance is part of
  the approved plan.
- Generation jobs, including their source plan revision and cancellation key.
- Character creation, attachment, history routing and time-skip participation.
- Authored memories or initial beliefs when the host is explicitly authoring a
  past rather than asking the simulation to produce one.
- Story clock, Living World and Background Life configuration.
- Scene and world state needed to establish an approved starting condition.
- Plot-package fields when it is acting jointly with the Dramaturge.

The production generation operation remains
`world.charter_runtime.generate_lived_location`. The Planner must call that
operation or its future public authoring facade; it must not reproduce its
closure, collision, lore-scoping or presimulation logic.

### 3.5 Hard limits on broad authority

Broad sway is not indistinguishable mutation. The Story Planner cannot:

- Change live state outside a validated atomic authoring operation.
- Present an authored memory as witnessed history without marking its authored
  origin.
- Put a private plan diagnostic or sealed truth into a mind as an accidental
  side effect.
- Rewrite something the player already witnessed without an explicit retcon
  proposal naming the contradiction and its blast radius.
- Author the player's declaration or interior.
- Duplicate the closure, identity, collision or presimulation logic of the
  production lived-location operation.

### 3.6 The Charter Planner subagent

The Charter Planner is invoked by the Story Planner when a proposal needs a
new or substantially expanded populated location. It receives a bounded brief,
not the entire writers' room conversation:

- Location purpose, genre and lore scope.
- Required connections and already-reserved room identities.
- Required institutions, figures, plot roles and artifacts.
- Population and simulation budget.
- Historical horizon and opening circumstance.
- Canon, safety and naming constraints.

It produces:

- A qualitative location plan suitable for deterministic closure.
- Structure and frontier requirements.
- Charter definitions, posts, bodies and material flows.
- Identity reservations and bindings for existing people.
- Presimulation parameters and an author-facing validation report.

Its work lands only through
`world.charter_runtime.generate_lived_location`. It never independently changes
the campaign plan, invents a murder solution, decides why the story should
visit the place, or negotiates with the host. If it discovers an impossible
requirement, it returns the conflict to the Story Planner, which may resolve it
with the Dramaturge or host.

The name is distinct from `world.charter_plan`, the deterministic watch and
staffing planner inside an already-created institution. The Charter Planner
subagent is an authoring-time model role over location generation; the module
is runtime simulation code.

---

## 4. The Dramaturge

### 4.1 Responsibility

The Dramaturge constructs and tends **dramatic situations**. It may work at
several scales:

- A local complication or opportunity.
- A mystery with a fixed hidden solution.
- A relationship or institutional conflict.
- A multi-location conspiracy.
- An overarching campaign plot.
- A thematic collection of pressures with no expected resolution.

It may also inspect current state and say that no intervention is needed. A
world already producing meaningful pressure should not receive another plot
merely because the agent was called.

### 4.2 A plot is state, not a scene list

The canonical form of a plot is a set of truths, participants, evidence,
pressures, clocks and unresolved questions. It is not a sequence of required
scenes.

The Dramaturge may author:

- Prehistory that is already true when the package activates.
- Secrets and their initial holders.
- Motives, institutional interests and material stakes.
- Physical evidence with an origin and location.
- Scheduled circumstances and escalation clocks.
- Contingent opportunities triggered by objective state.
- Questions the scenario is intended to explore.
- Consequences that become possible if their prerequisites occur.

It may not author in advance:

- The player's choice or emotional response.
- A live character's eventual decision.
- The success of an unattempted act.
- A confession, betrayal, reconciliation or death that still depends on
  future volition, unless the host explicitly authors it as an objective future
  event and accepts the corresponding loss of agency.
- A required order in which clues must be encountered.
- A replacement solution chosen to reward or defeat the player's theory.

### 4.3 Circumstance versus conclusion

The Charter precursor's rule remains the default for autonomous intervention:
**circumstance in, never conclusions**. The Writers' Room's broader authoring
mode may establish conclusions as backstory or apply an explicit retcon, but
only when the host's mandate authorizes that class of change and the proposal
labels it honestly.

The Dramaturge may create a drought, damage an upkeep, delay a caravan, place
an incriminating object, establish a past murder, schedule an arrival or give
an institution incompatible material obligations. Those are world
circumstances.

During live autonomous play it does not directly increase hatred, write blame,
make somebody believe the wrong suspect, or declare that pressure caused a
betrayal. People acquire beliefs through channels and reach conclusions through
their own bounded or full cognition. In an authoring conversation, however,
the host may explicitly ask it to establish a pre-existing feud, false belief
or betrayal; that becomes marked authored history with whatever supporting
events and memories the approved change set contains.

An explicitly authored backstory may seed initial beliefs and relationships
through the same story-import and generation paths available to a human
author. That is initial authorship, not a licence to rewrite a live mind after
play begins.

### 4.4 What it reads

The Dramaturge may read:

- Canon, objective state and the event spine.
- Charter minds, politics, commitments, practices and material conditions.
- Character sheets and durable memory when the host grants author-level access.
- Existing plot packages, including sealed truth.
- Planner proposals and prepared-horizon diagnostics.
- Unresolved promises, plans, obligations, shortages and relationships.
- Host-authored themes, safety constraints and forbidden subjects.

This omniscience is authorial. None of it may be copied into a mind or onto the
page merely because the Dramaturge saw it.

### 4.5 Cross-system sway

An approved Dramaturge proposal may write:

- A plot package.
- Lore and prehistory through ordinary authoring routes.
- Validated physical interventions and consequence fuses.
- Requests to the Story Planner for locations, routes, institutions, bodies or
  artifacts required by the package.
- Activation conditions and author-facing diagnostics.
- Character, relationship, memory and belief prehistory when the mandate
  authorizes it and the origin is preserved.
- World, scene, Charter, clock and configuration changes needed to establish an
  approved scenario.
- Style, tone and narration guidance at the authoring layer.

It may sway live systems by changing their inputs and circumstances. Directly
replacing a completed Director resolution, Background Life response or
character choice is an explicit edit/retcon operation, never the invisible
default behavior of an active plot.

### 4.6 When it runs: on its pacing, in every story (owner ruling, 2026-10-08)

> "It was never meant to be surprise only, it was meant to suggest story
> directions." — the owner, 2026-10-08

As built on 2026-09-04 the Dramaturge ran only under a grant whose limits
carried a numeric `surprise`. Measured on a copy of the owner's database on
2026-10-08: none of its 68 grants across 33 stories carried one -- eleven
held the `surprise` capability and ten the total grant, and neither sets a
number -- so it had never run in any story: 0 calls, 0 `room_proposals`
rows, and `mandates.SURPRISE_DEFAULT` read by nothing. The gate made the
Room's dramatic half wait on a word nobody knew to say, which is the second
of the engine's two goals -- a world that does not feel static -- failing
without a sound. As built now:

- **Its turn comes on pacing alone.** Every `beats_per_proposal` beats
  (`mandates.BEATS_PER_PROPOSAL` = 6 unless a grant names a number) of the
  frame's OWN play, counted from the last pass, or from the frame's opening
  before the first (`room_proposals.pass_due`): a thirty-beat story is asked
  at beats 6, 12, 18, 24 and 30. A story already past one interval with no
  pass on record -- every story written before the ruling -- is asked at
  its next commit. The player's own ask through the Planner (`to_dramaturge`)
  still runs at once.
- **The dial tunes it and never licenses it.** `mandates.surprise_dial` is
  the number a standing grant names (the most inventive wins), else
  `SURPRISE_DEFAULT` = 2, the middle of the 0-4 scale. A grant's
  `beats_per_proposal` is the player's word on how often, with or without a
  dial beside it; the most frequent wins.
- **A pacing of 0 is off.** No grant is needed for the Dramaturge to
  suggest, so a grant is the player's one way to stop its own passes:
  `beats_per_proposal` 0 (`mandates.BEATS_PER_PROPOSAL_OFF`) wins over any
  number another standing grant names, and the player's ask still runs. A
  grant may carry limits and no capability -- it permits nothing -- so the
  Planner can record "suggest nothing I did not ask for" as the player said
  it. Until the review of 2026-10-08, 0 was clamped to every beat: a pass and
  a deliberation at every commit for the player who asked for none. A grant
  that permits nothing is no licence to work, so it never lifts the spend a
  licence set; a spend number it names only lowers what stands
  (`mandates.spend_limits`; third review, R3-3: the off switch, a dial or a
  pace had left the room uncapped).
- **Suggesting needs no grant; acting on a suggestion still does.** A
  proposal is typed intent and changes nothing. The Planner implements an
  accepted one only through a package, a package the Planner drafted
  validates and publishes only under standing mandates that cover every
  operation in it (`plot_packages.authority_errors`, read at both), and a
  background task reads no grants, so the deliberation cannot license itself.
  Carrying an accepted proposal out is acting: when the grants do not cover
  what it needs, the Planner's card has it accept the proposal, ask the
  player for that grant by name and open no package that cannot validate.
  The floor under the clause is code: a background task retires, when it
  ends, every draft ITS OWN `new_package` calls opened that the grants do
  not cover, with the refusal as its note (`story_planner._retire_stranded`,
  `run_planner`'s `opened`). Without it, each accepted proposal in a story
  with no grants left a draft that could never publish -- shown in motion,
  counted against `PACKAGES_CAP` (32), past which the room could open
  nothing, the player's own asks included. Its first form diffed the package
  ledger, so it also retired a draft a panel reply opened while the task ran,
  and the grant the player then gave for it lapsed on arrival (second
  review, A).
- **The player's ask waits until a pass takes it.** The pacing pass and the
  asked one share one job key, and a job in flight absorbs a second submit,
  so an ask made while a pacing pass ran -- minutes, with its deliberation --
  was never read. The Planner now keeps the brief on the `room_proposals`
  row before it queues anything (`room_proposals.ask_brief`); a pass takes
  every brief waiting at its start, answers what was asked while it ran with
  one more pass when it is done, and a commit queues a pass while one waits.
  A brief is the conversation's, not the beat's: a restore leaves the
  waiting ones as they stand, as it leaves the thread. A pass whose provider
  fails hands back the briefs it took and had not answered, marked with the
  beat it failed at, and a commit takes them up again at the pacing -- the
  default pace when the passes are off -- not at every commit, unless the
  player asks again (`room_proposals.briefs_due`; third review, R3-7: the
  ask was lost for good).
- **A reroll cancels the pass that read it, and asks again.** A same-beat
  reroll does not move the turn index, so the rewind guard cannot see it; a
  pass still running filed the discarded beat's direction into the rerolled
  timeline. `restore_checkpoint` cancels the Dramaturge pass, the fill and
  the direction follow-up (each reads the beat and writes rows the restore
  rolls back) -- ONLY when the job READ a beat the restore discards
  (`core.jobs.cancel_from`; second review, B: rerolling beat 7 had cancelled
  beat 6's deliberation, and nothing asked it again). What a job read is its
  read horizon, not the beat it was queued from (third review, R3-1): the
  follow-up and the pass loop until nothing is left, and each round reads
  the beats played since, so a job queued at beat 3 read beat 4 and a reroll
  of beat 4 left it writing what it built on the discarded beat. The stream
  raises the horizon before it reads (`dramaturge.player_visible_stream`,
  `core.jobs.read_through`), and so does a deliberation, to the newest beat
  and the beats its proposals were written from. A job the restore spares
  finishes the unit it is in and reads none of the beats being played again
  -- their old narration stands until the replay replaces it -- unless the
  replayed beat's own commit joins it, which hands it that beat. Each asks
  `core.jobs.is_cancelled` before every write -- proposals, judgements,
  revisions, tool calls, thread lines, the status row, spend. A cancelled
  pass hands back the briefs it had taken and NOT YET ANSWERED, its one
  write: once the Dramaturge's line is in the thread -- which no restore
  takes back -- handing the ask back had it answered twice (second review,
  C). A submit never joins a cancelled job still finishing its call
  (`core.jobs.submit`, second review, F): the rerolled beat's own commit
  used to join the dying pass and was never asked. The pass's record rolls
  back with the row, so THE REROLLED BEAT IS ASKED AGAIN, as itself: one
  more pass per reroll of a pacing beat, an owner question. WHAT A SPARED
  JOB WROTE STANDS (third review, R3-2): the next beat's snapshot is taken
  as it starts, and the pass queued a beat earlier can still be filing then,
  so a reroll of that next beat rolled its suggestions back while its note
  stood in the thread, and its pacing stayed spent. The restore puts back
  (`room_proposals.keep_spared`) the proposals filed from beats it keeps --
  `filed_turn` is the newest beat the pass read -- as their pass filed them,
  due at once when they answer the player's ask; a refusal reached by a
  deliberation that began at a kept beat; and the passes that had their
  turn. A verdict that acted -- a package, a grant asked for, a return --
  rolled back with the world and the status row, and is judged again at its
  bound. WHAT A JOB BUILT ON A DISCARDED BEAT IS GIVEN BACK (fourth review,
  R4-1): the pass record stood whenever the pass had recorded before the
  snapshot, so a pass that read the next beat lost its suggestions to that
  beat's reroll with its pacing spent, and an asked pass lost the player's
  ask. The row keeps a log of passes (`pass_log`), each landed with the
  newest beat its answer was read from (`land_pass`); the restore keeps the
  log as it stood less every pass recorded at a discarded beat or read from
  one, and a pass it cancels before it answered gives itself back
  (`give_back_pass`) -- before the restore's transaction or after, either
  way holds. A suggestion names the player's asks it answers (`asks`): one
  the restore drops hands them back, one that stands keeps a cancelled pass
  from handing them back twice, and a fresh re-ask in the same words is
  never put behind a failed copy. A beat in play -- its line sent, nothing
  yet answering it -- is read by no reader of the stream, so a pass that
  came round while the next beat ran is simply spared. The follow-up's
  reading is not kept, since what it concluded rolls back. And a spared
  deliberation returns to the player only what it left pending, never a
  verdict the restore rolled back (R4-2).
- **The deliberation waits for the story to near the suggestion** (owner,
  2026-10-08: "Can we do lighter weight planning potentially? And save heavy
  plans for when the actors near them?"). The Planner's deliberation is six
  calls and more, and it ran in the pacing pass's own job over directions
  the story might never come near. A pacing pass now files its suggestions
  and stops. At each commit of the player's frame while one is pending, the
  direction follow-up (`story_planner.run_direction_follow_up`, its own job)
  asks the decision model one question per suggestion not yet deliberated,
  of the narrated beats it has not read that were played AFTER the beats the
  suggestion was written from: does the passage bring the story near what
  this direction is about (`jev_questions.direction_neared`: the title, what
  it wants true and why now)? A yes (`DIRECTION_NEAR_FLOOR` = 0.5) makes it
  due, and the follow-up deliberates it then. Asked of its own beats, a new
  suggestion's answer confirmed itself (third review, R3-4); a beat whose
  turn row stood without its narration yet was marked read off the player's
  line alone, and so was a beat whose decision call failed (R3-6): a beat
  counts as read only once narrated and answered. NOTHING IS DROPPED: a
  suggestion that has waited `room_proposals.DIRECTION_WAIT_INTERVALS` = 2
  pacing intervals of the frame's own beats (12 at the default pace) is
  deliberated anyway, and the decision model unconfigured or unreachable,
  that bound alone decides. A PLAYER'S ASK IS NEVER LAZY: what its pass
  files is due at once (`due` "asked") and the follow-up is queued from the
  pass. Every deliberation runs in that one job, one at a time, so two never
  judge a proposal together; it takes up whatever came due while it ran,
  and reads the beats that passed meanwhile. A deliberation TAKES what it
  judges (`taken_turn`): a proposal a failed or cancelled one left pending
  is not taken again at the next commit -- a dead provider would be asked at
  every one -- but waits its bound again from there.
- **The spend stop holds, and so do its own caps.** A grant's
  `calls_per_hour` stops the pass at the commit tail and again inside the
  job; the Dramaturge keeps `DRAMATURGE_STEPS` = 3, `DRAMATURGE_LORE_CALLS`
  = 4, `DRAMATURGE_PROPOSALS_PER_PASS` = 3 and 120 seconds a pass, and the
  deliberation `DELIBERATION_ROUNDS` = 2.
- **Never a live bubble's.** A causality bubble's beats carry no player line
  and no narration (`agents/offscreen_beat.py`) and the Room's rows are its
  era's, so a pass queued there read an empty stream and spent the era's
  pacing. A bubble's commit queues none; a pass asked from its panel -- a
  viewer can switch to its frame -- reads, paces and speaks in its era's
  frame; and the pacing counts the frame's own beats with the same helper
  as the fill's back-off, so a bubble's interleaved rows do not bring it
  early. One residual (review F6, left): the panel watches the bubble's own
  thread, so the lines that pass speaks in the era's thread are not the ones
  it shows.
- **A failed pass has had its turn.** The pass is recorded before the
  Dramaturge is called, so a provider that refuses is asked again at the
  pacing and not at every commit -- which, with no grant in the way, would be
  every commit of every story. The player's asks it took wait again, on the
  same back-off.

**What the player sees.** A pass leaves the Dramaturge's `note` in the
thread (its card asks for a spoiler-safe line), the pending proposals' kind
and title on the status row while the Planner weighs them, and the Planner's
judgement as its own line; the row is restated once the judgements land. With
no grants an accepted proposal stays `accepted` with no package, and the
question the Planner asks for the grant sits on the status row. The row's
questions record who asked each (`room_conversation.QUESTION_SOURCES`):
the engine's own asks -- the fill waiting on a grant, the proposals the room
could not settle -- come first, at most `ENGINE_QUESTIONS_CAP` = 3 of them
so half the row of six stays the Planner's, and the engine withdraws the
fill's once a grant arrives or nothing is wanted. The returned proposals are
ONE standing ask naming each returned proposal the player has not answered,
once (`story_planner.ask_returned`; second review, E: a new question per
deliberation had filled the row and cut the player's own). A background
task's list replaces only what THAT task asked -- a fill its last fill's, a
deliberation its own over the same proposals, every round and pass of it
adding to one list -- and a deliberation's questions leave once every
proposal it judged has settled; an accepted proposal waiting on a grant has
not (second review, D: keyed by "the last task", round 2 and the next fill
wiped the grant ask round 1 made). A reply restates the row, and a reply
that says nothing about the questions leaves them standing. Before this,
every task replaced the row -- and a grant scoped to a question lapses when
the question leaves it (`mandates.request_open`) -- and then, for a day,
every task only added, so six of them filled the row and cut the engine's
asks. The opening and the location pass, which run when nobody can answer,
clear the Room's questions as they always did and keep the engine's (second
review, G: the prelude's question had stood into the story). A pass that
finds nothing keeps the questions, and keeps the line only while something
is in motion: the line says what is in motion, and a deliberation's line
outlived the package it described; a retired draft takes its line with it
too (second review, H). With no line standing beside something in motion,
the row says "The room has something in motion." (`IN_MOTION_LINE`, en and
ja; third review, R3-8: a pacing pass's suggestion stood beside "nothing in
motion" for up to two pacing intervals). A `quiet` proposal never waits on
the Planner, so it is never in motion and the cap may drop it.

**The first live pass** (2026-10-08, a copy of chat 166, Brackwater, at beat
30; the Dramaturge on GLM 5.2 and the Planner on DeepSeek V4.1 Flash, both
through OpenRouter, the play database's own routing). The commit tail queued
the pass on pacing alone, at dial 2 under the story's total grant (which
names no number). The Dramaturge read the lore once and filed two proposals
for ONE direction -- the drowned man's coat on the Gale table has something
in its unopened pockets that changes what the receipt means -- as a
`pressure` in the step that also searched lore and again, rewritten, as a
`revelation` after the result came back, so the kind-and-title identity did
not catch it. Its note was not spoiler-safe ("it just needs a hand in a
pocket"), the revelation's `wants_true` scripted two live minds ("neither is
going to name it before she does"), and both `scale` sentences were cut at
the 60-character field cap. The Dramaturge's card now states the class the
double filing is an instance of: each proposal is a different direction, and
one circumstance seen two ways is one proposal, filed once. The Planner read
for six steps (rooms, plans, events, needs, the same lore query four times)
and had not judged when the experiment's eight-call budget stopped it. Two
Dramaturge calls (~12 s, ~8k prompt and ~0.5k answer tokens each, no
reasoning) and six Planner calls (10-21 s, 21-28k prompt tokens, 3-6k answer
tokens of which ~90% reasoning) cost an estimated $0.055.

---

## 5. The plot package

A **plot package** is the durable contract between authorship and simulation.
It must be portable through archive, branch and restore; revisioned; and
separate from both lore prose and live state.

The exact schema belongs to implementation design. The conceptual shape is:

```json
{
  "uid": "plot:...",
  "title": "The Bell Without a Ringer",
  "status": "proposed|approved|preparing|active|resolved|abandoned",
  "revision": 3,
  "scope": {
    "frame_id": null,
    "locations": [],
    "earliest_time": null,
    "latest_time": null
  },
  "authority": {
    "mandate_uid": "mandate:...",
    "may_create_people": true,
    "may_author_prehistory": true,
    "may_schedule_harm": false
  },
  "premise": "author-facing summary",
  "truths": [],
  "questions": [],
  "participants": [],
  "knowledge_seeds": [],
  "evidence": [],
  "pressures": [],
  "clocks": [],
  "opportunities": [],
  "planner_requests": [],
  "constraints": [],
  "spoiler_policy": "open|sealed",
  "provenance": {}
}
```

### 5.1 Truths

A truth is an author-established fact with a stable id. In a mystery, the
culprit and actual sequence are truths. Approved truth is immutable during
ordinary Dramaturge revisions. Correcting an author error creates a visible
superseding revision; it does not silently mutate the solution.

### 5.2 Questions

Questions describe dramatic uncertainty without promising an answer: *Will
the guild protect its own?* or *Can Mara keep both obligations?* They are for
the writers' room and never become premises inside a character mind.

### 5.3 Evidence

Evidence is not a clue merely because the Dramaturge labels it one. It must
have:

- A physical record, artifact, event, testimony or observable condition.
- A causal origin.
- A location or carrier.
- Initial holders, if any.
- A reason it bears on one or more truths.
- An admission path by which a player or character could discover it.

A mystery should normally have redundant evidence paths. One lost object or
dead witness must not make the authored situation unknowable unless that
fragility is itself an approved constraint.

### 5.4 Pressures and clocks

A pressure names a standing conflict in circumstances. A clock schedules or
conditions future opportunities. Neither is permission to narrate an outcome.

Clocks use story time and stable ids. A due clock creates a validated
circumstance or offers an intervention to the appropriate simulation owner.
It does not call the Dramaturge every turn.

### 5.5 Opportunities

An opportunity is a possible intervention guarded by typed prerequisites. It
may expire unused. Activation cannot depend on matching free prose or on a
private fact the activating system is not authorized to read.

---

## 6. Planner–Dramaturge collaboration

### 6.1 Conversation is presentation; proposals are state

The agents may speak naturally in the UI, but their operational exchange is a
typed message:

- `request_location`
- `request_institution`
- `request_person_role`
- `request_route`
- `request_artifact`
- `report_feasibility`
- `report_canon_conflict`
- `report_cost`
- `propose_revision`
- `accept_dependency`
- `decline_dependency`

Free-form conversation alone never creates canon. Every actionable conclusion
must appear in the proposal diff shown to the host.

### 6.2 Shared authority, different leads

Story Planner and Dramaturge share the Writers' Room's authorized tool and
proposal surface. Neither is barred from a system because of its name. The
agent leading a proposal is responsible for assembling one coherent
multi-system change set; the other reviews from its specialization.

The Story Planner normally leads feasibility, continuity, world preparation
and location generation. The Dramaturge normally leads dramatic intent, hidden
truth and scenario structure. “Normally” is routing, not authority. A host may
ask either agent to begin any authoring task, and that agent may consult the
other or invoke the appropriate subagent.

The one hard delegation boundary is populated-location construction: the Story
Planner invokes the Charter Planner and remains accountable for integrating its
result. The Dramaturge requests the location through the Story Planner rather
than treating the Charter Planner as a third peer.

Examples:

- The Dramaturge requests a creditor institution; the Planner chooses or
  creates a feasible institution and location.
- The Planner reports that a witness could not have travelled between two
  places in the stated time; the Dramaturge revises the chronology or declines
  the location.
- The Planner offers three plausible towns; the Dramaturge may propose a route
  revision for dramatic reasons, and the Planner checks whether the revised
  world remains coherent.

### 6.3 Bounded deliberation

Inter-agent conversation is capped by rounds, tokens and wall-clock budget.
Failure to agree returns the disagreement to the host. The agents may never
call each other recursively until consensus.

The canonical assembly is deterministic: current proposal, Planner review,
Dramaturge review, Charter Planner result where requested, and unresolved
conflicts. Because the two principal agents share the mandate, one may continue
after the other fails, but the proposal must report the missing review and may
not claim joint agreement.

### 6.4 Approval and mandates

Default mode is proposal-and-approval. A host may grant a standing mandate,
for example:

> Prepare up to two likely-next settlements, within this lorebook, without
> creating harm to registered characters or activating a plot.

A mandate is structured state with scope, capabilities, cost limits,
expiration and revocation. Silence is never permission. A broad request such
as “invent an overarching mystery and surprise me” is valid authorization, but
its boundaries must still be materialized before hidden work begins.

**A grant is scoped to the request that earned it, and lapses with it**
(built 2026-09-05, `story/mandates.py`). A mandate may name the ask it
answers, and when that ask ends the licence ends: the package retired or
resolved, the question off the room's status row, or the request closed
outright. Renewal is an explicit act and a new row, because a licence that
renews itself is a licence nobody granted twice. A grant naming no request
is standing, which is what every grant was before this. The measured case
(flat run, PE14): a grant for a courier survived the player withdrawing the
courier in words, because a grant is state and a retraction in words is not.

**A total grant means every kind, resolved when it is used.** “Full
authority” must not be written down as the list of kinds that existed on the
turn it was said; a list cannot know about tomorrow's kind, and chat 114's
turn-5 grant refused an operation kind added afterwards until the player
happened to say the word again (F11/F15). The total grant is therefore one
MEMBER of the capability vocabulary, resolved against the capability being
asked for at the moment it is asked. An enumerated grant still covers
exactly what it enumerated: the fix is about what “everything” means, not
about widening ordinary grants.

---

## 7. Sealed scenarios and spoilers

The host may be the player and may want genuine surprise. A sealed scenario
stores hidden plot truth without displaying it in ordinary writers' room chat.

The host approves the visible envelope:

- Genre, tone and intended scale.
- Forbidden content and protected characters.
- Permitted locations, institutions and kinds of harm.
- Expected duration and generation budget.
- Whether the scenario may follow the player between locations.
- Whether failure, permanent loss or an unsolved ending is allowed.

The hidden package is then generated inside that envelope. The UI exposes:

- A non-spoiler readiness report.
- Validation and solvability warnings without their secret answers.
- The package revision and every authorized mutation.
- An explicit **Reveal sealed plan** action.

Secrecy is a presentation rule, not an excuse for unauditable state. The
package remains inspectable in diagnostic exports and can be revealed by the
host. It is never encrypted against the owner of the local database.

Once activated, sealed truths obey the same immutability rule as open ones.
The Dramaturge cannot move the culprit or manufacture evidence in response to
the player's guesses unless the package explicitly describes a causally valid
actor destroying or planting evidence through live simulation.

---

## 8. Worked workflows

### 8.1 Wandering into an unbuilt world

1. The prepared horizon exposes three plausible onward routes.
2. The Planner ranks all three and prepares a shallow structure for two within
   budget.
3. The player commits to one route.
4. The Planner deepens that destination through
   `generate_lived_location`; Charter presimulates its people and institutions.
5. Arrival resolves planned rooms through the ordinary mapping seam.
6. The unused frontier remains provisional and may be aged out.

The player is never told that an unchosen route does not exist. The engine is
also never required to pretend it was fully simulated.

### 8.2 Murder mystery

1. The host asks for a sealed local mystery and approves its envelope.
2. The Dramaturge establishes an immutable victim, culprit, motive, event
   sequence, knowledge distribution and redundant evidence plan.
3. The Planner supplies feasible locations, institutions, travel times,
   artifacts and Charter roles.
4. Validation proves that every claimed witness and carrier could have been
   where the package says, and that at least one discovery path survives.
5. Approved prehistory is planted; Charter advances the aftermath.
6. When the player arrives, the guard, witness and suspect are existing Charter
   people with actual intervening histories.
7. Background Life renders them from what they presently know. They may lie,
   flee, accuse wrongly or change plans.
8. The player may solve, mishandle or ignore the mystery. No agent repairs the
   plot behind them.

### 8.3 Overarching campaign

The Dramaturge authors a constellation of truths, factions, artifacts,
pressures and questions across several possible locations. The Planner
prepares only the next reachable portion. Later sections materialize as the
player's route and the simulation make them relevant.

The campaign package may evolve by adding future circumstances. It may not
rewrite events already witnessed or invalidate earned memories merely to
restore an intended arc.

### 8.4 Rough drafting

The writer discusses a premise with both agents, approves a plan, then plays,
observes or branches key scenes. An export can assemble:

- Objective chronology.
- Candidate scene list.
- Character-specific experience and memory.
- Relationship and commitment changes.
- Plot truths and their revelation paths.
- Prepared but unused material.
- Unresolved questions and pressures.
- Alternate branches worth drafting.

The export is a drafting dossier, not automatically a finished manuscript.

### 8.5 Time skips

The Planner ensures required places and institutions exist for the declared
interval. The Dramaturge may seed approved circumstances or clocks. Charter
advances the world and participating people at lower resolution.

Major-character memories derive from simulated events and delivered knowledge,
not from the Dramaturge's plan text. Resolution may be coarse; causal and
epistemic integrity may not be.

---

## 9. Integration boundaries

### 9.1 Charter

Charter supplies lived populations, institutional history and cheap continued
motion. The Story Planner delegates new populated-location design to the
Charter Planner subagent. The Writers' Room authors Charter inputs and
interventions through `charter_runtime`; direct carried-state edits are exposed
as explicit author surgery, not disguised as simulation.

### 9.2 Background Life

Background Life renders an existing on-screen person with higher situational
intelligence. It receives that person's own history and current view, never the
plot package. The Dramaturge may know that the guard is the culprit; the guard
agent receives that only if the guard's own state legitimately contains it.

### 9.3 Character agents and promotion

Promotion raises the resolution of an existing person. Plot participation is
not, by itself, permission to create a replacement character or overwrite the
promoted mind. A promoted body carries its Charter identity, claims,
relationships, commitments and simulated past. The Writers' Room can later
author or retcon that character under an explicit mandate, using the same
cross-system provenance rules as any other character edit.

### 9.4 Director

The Director adjudicates the live beat. It may receive objective circumstances
that an approved plot caused to exist; it does not receive author goals such as
“make this clue suspicious” or “keep the culprit hidden.”

### 9.5 Lore and canon

Approved prehistory and durable setting facts write canon through the ordinary
lore route. Proposals, rejected alternatives and private agent discussion are
not lore.

### 9.6 Memory and information carriers

An **active plot** never mints memory merely because its hidden truth says a
person should know something. Evidence reaches minds through sight, hearing,
conversation, artifacts, reports, couriers and other existing carriers, and
memory retains that provenance. An approved authoring change may seed memory
or knowledge as prehistory or retcon; the row then records that authored origin
instead of claiming a simulated delivery.

### 9.7 Branching, restoration and rerolls

Plans and mandates are checkpointed and archived. Generation and activation
use stable ids and revision guards. A restored branch must not inherit an
agent job based on a later revision or another frame.

---

## 10. Cost model

No Writers' Room agent belongs in the normal turn pipeline. At rest the set
costs nothing.

Calls occur only when:

- The host opens a conversation or requests a proposal.
- The prepared frontier falls below a configured threshold.
- An approved plot reaches a planning boundary that cannot be resolved from
  its stored package.
- A generation job requires qualitative authoring.
- The host explicitly requests a review or revision.
- The Dramaturge's pacing comes round (§ 4.6).

The Planner may run ahead of contact in an out-of-band job. The job records the
base turn, frame, plan revision and source registry revision; landing refuses
stale work under the write lock, following Charter generation's existing
guard pattern.

The Dramaturge does not wake every turn to “keep things dramatic.” Typed clocks
and Charter consequences advance without it. A later review may inspect what
the simulation produced and propose a new package revision. It does wake on
its pacing, every `beats_per_proposal` beats of play (§ 4.6) -- with no
grant, since 2026-10-08 -- and a pass is the Dramaturge's one to three
calls. The Planner's deliberation, which on the first live pass was the
larger share (six calls of reading before a verdict), waits until a beat
brings the story near the suggestion, one decision-model question a
suggestion a commit, or until its bound.

Budgets are first-class:

- Provider-call and token ceiling.
- Concurrent generation-job ceiling.
- Maximum prepared locations and bodies.
- Maximum active plot packages and clocks.
- Maximum inter-agent rounds.
- Wall-clock deadline and cancellation.

---

## 11. User experience

### 11.1 Three conversations

The UI offers:

- **Planner chat** for world preparation and continuity.
- **Dramaturge chat** for plots, mysteries and dramatic analysis.
- **Writers' room** containing the host and both agents.

Every chat distinguishes discussion from action. An actionable response carries
a proposal card showing:

- What would be added, changed or scheduled.
- Which agent led and reviewed each part, and whether the Charter Planner was
  invoked.
- Canon and feasibility warnings.
- Estimated model and simulation cost.
- Spoiler posture.
- Approve, revise, reject and save-draft actions.

### 11.2 Current-state summaries

The agents retain durable author-side conversation and accepted constraints,
but every new proposal re-anchors on current canonical state. Conversation
history is not authority and cannot override a later branch, restore or host
edit.

**A summary states what the ledgers say and cites the rows it read** (built
2026-09-05, `story/room_citations.py`). A recap is the room's most useful
reply and its most dangerous one, because it reads as the engine talking:
measured, one said a character was “feigning sleep”, one that an errand had
been dispatched that never was, one that an offer had been declined where
the ledger holds only a contact and a transfer. The class is not lying — the
room reads ledgers and renders them as motives, and nothing between the
reading and the rendering asked which row said so.

So a claim carries the rows it came from, and the engine checks them against
the ledger of what that reply actually read. The two consequences are the
point. A PROPOSAL IS NOT AN ASSERTION: the room stays entirely free to
suggest, invent and speculate, and none of that needs a row — what it may
not do is let the two wear the same clothes. And AN UNCITED CLAIM IS
DEMOTED, NOT DELETED: it keeps its sentence and loses the authority it was
borrowing. Nothing here reads the room's English; the room enumerates its
own claims and the check is a set membership test over ids the engine
itself served.

### 11.3 Roleplay versus drafting posture

The same agents support two presentation postures:

- **Roleplay:** sealed truth, minimal author diagnostics, surprise preserved.
- **Drafting:** full plot visibility, branch comparison and export tools.

This is a UI distinction over the same stored contracts, not two simulation
architectures.

---

## 12. Failure behavior

- If the Planner fails, the current world remains playable. Unprepared travel
  falls back to ordinary on-demand generation.
- If the Dramaturge fails, no plot mutation lands. Existing packages continue
  through deterministic clocks and simulation.
- If one writers' room agent fails, the other may report its own analysis but
  any proposal it completes must report that the complementary review did not
  occur; it cannot present one voice as joint agreement.
- If validation finds a canon, route, identity, authority or solvability
  conflict, approval is blocked until the host resolves or explicitly waives a
  warning class that is safe to waive.
- If an out-of-band job races a turn, restore, author edit or newer plan
  revision, stale work is discarded.
- Partial multi-surface writes roll back together. A plot cannot land its
  culprit without its evidence and report success.
- Unknown operation kinds are warnings and no-ops, never best-effort prose
  interpretations.

---

## 13. Build sequence

This is sequencing, not a second worklist; `UNBUILT.md` remains the register.

### Phase A — shared authoring substrate

- Plot-package and mandate schemas.
- Revisioned proposal storage.
- Proposal diff, approval and atomic application.
- Spoiler policy and sealed-plan viewer.
- Archive, branch, checkpoint and deletion behavior.

### Phase B — Story Planner

- Prepared-horizon state and diagnostics.
- Typed location/institution/generation requests.
- Predictive ranking with a bounded frontier.
- Charter Planner subagent and its bounded location brief/result contract.
- Out-of-band generation jobs with stale-landing guards.
- Planner chat and proposal cards.

### Phase C — Dramaturge

- Inspect existing state for latent pressures.
- Author physical Charter interventions and consequence fuses.
- Produce open plot packages with no sealed mode.
- Coordinate explicit cross-system authored changes while preserving their
  provenance.
- Validate that no hidden plot field accidentally enters cognition or
  narration.

### Phase D — scenario architecture

- Mystery truths, evidence graphs and solvability checks.
- Multi-location and campaign packages.
- Planner–Dramaturge typed collaboration.
- Writers' room UI and bounded joint deliberation.

### Phase E — sealed roleplay and drafting tools

- Sealed scenarios and reveal controls.
- Drafting dossier export.
- Branch comparison and unused-material review.
- Time-skip participation and memory-generation integration.

Do not begin Phase B until Charter's generation, identity, promotion and
archive lifecycle is stable enough to be a dependency rather than a moving
target.

---

## 14. Acceptance tests

### 14.1 Authority and firewall

- A proposal changes no story before approval.
- Revoking a mandate prevents every later write, including queued jobs.
- A hidden solution marker appears in no character, Background Life, Director
  or narrator payload.
- A Dramaturge-authored secret reaches only its seeded holder until a real
  carrier moves it.
- An authored memory, judgment or recognition change records its mandate and
  authored/retconned provenance; it cannot masquerade as simulated learning.
- An active plot cannot silently replace a live Director, Background Life or
  character decision.

### 14.2 Identity and continuity

- A Planner-requested role filled by an existing cast or lore person creates
  one body, not a duplicate under another seed spelling.
- A Charter person used by Background Life and later promoted retains one
  identity and one history.
- Archive, restore and branch preserve package ids while isolating later
  revisions.

### 14.3 Mystery integrity

- The culprit and truth sequence remain byte-stable after activation.
- Every evidence item has a causal origin, location/carrier and discovery path.
- Removing one non-critical clue leaves at least one valid solution path in a
  package that promised redundancy.
- A player's incorrect accusation creates consequences but does not change the
  solution.
- A live actor may causally destroy evidence; the deletion is an event, not a
  Dramaturge edit.

### 14.4 Planning and cost

- Prepared locations never replace or rename live rooms.
- A player choosing an unpredicted route is not redirected or blocked.
- A stale generation job cannot land after a turn, restore or plan revision.
- At rest, both agents make zero provider calls.
- One thousand Charter minds continue to scale according to the Charter audit
  budget; adding a dormant plot package does not change the sweep cost beyond
  its empty typed checks.

### 14.5 Failure and atomicity

- Failure after planting one part of a package rolls back every part.
- One failed writers' room agent does not erase the shared mandate, but the
  surviving agent must report that the complementary review did not occur.
- A failed Charter Planner cannot leave a partly planted location or be
  bypassed by the parent reimplementing location generation ad hoc.
- An interrupted sealed-plan generation leaves either the previous revision or
  a resumable draft, never half a mystery presented as ready.

---

## 15. Open design decisions

These questions must be answered before their phase, and remain in
`UNBUILT.md` rather than becoming implied commitments here:

1. Whether plot packages live in a dedicated table or a frame-scoped world-KV
   record with an indexed summary.
2. Whether a standing mandate may autonomously activate a package or only
   prepare it for one-click approval.
3. How solvability is defined for mysteries whose witnesses and evidence can
   genuinely disappear through simulation.
4. Whether the Dramaturge may propose harm to an existing registered character
   by default, or only under an explicit per-story capability.
5. How author-side chat is compacted without letting a summary become authority.
6. Whether time-skip participation for major characters requires individual
   opt-in or may be covered by a story-level mandate.
7. Which parts of a drafting dossier are deterministic extraction and which,
   if any, receive a model-written synthesis.
8. Whether Story Planner and Dramaturge are separate provider roles or two
   prompt/persona projections over one shared model configuration.

---

## 16. The one-breath contract

The Writers' Room gives Story Planner and Dramaturge shared authorial sway over
the whole story, distinguished by continuity and dramatic perspective rather
than system ownership; the Story Planner delegates coherent populated-location
construction to its narrow Charter Planner subagent; all three produce typed,
reviewable change sets through ordinary system facades; Charter makes people
and institutions continue to exist; Background Life and character agents
decide from their own histories when encountered; and a sealed or open plot
survives only in the form the simulation can honestly carry.
