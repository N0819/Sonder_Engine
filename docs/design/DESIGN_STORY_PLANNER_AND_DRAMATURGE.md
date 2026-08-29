# Story Planner and Dramaturge — an author-side writers' room over a living world

**Status: design draft; none of these agents exists.** The unfinished work is
registered in [`../UNBUILT.md`](../UNBUILT.md) §§2.9 and 2.26. This note argues
for the product and authority shape; it is not implementation authority.

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

The Planner may run ahead of contact in an out-of-band job. The job records the
base turn, frame, plan revision and source registry revision; landing refuses
stale work under the write lock, following Charter generation's existing
guard pattern.

The Dramaturge does not wake every turn to “keep things dramatic.” Typed clocks
and Charter consequences advance without it. A later review may inspect what
the simulation produced and propose a new package revision.

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
