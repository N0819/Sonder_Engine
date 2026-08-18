# The living world — five state-producers, each with a floor and a ceiling

Status: **deterministic/reactive floors A–E landed**: A, B and D's original
floors, C's physical first-person carrier envelopes, E's bounded typed-plan executor, the settings surface for all five (the
`LIVING_WORLD_*` ladder in `world/living_world.py`, declared/built split per the
`OFFSCREEN_LIFE_BUILT` idiom), and the §6 profile-rung output-shape fix.
**C's crowd/message/degradation layers and E's adaptive ceiling remain held for later phases**, behind the
epistemic-leak audit — see §9, which also records the author's constraints on rumor
propagation verbatim, because they are design commitments the phase-1
shapes were built to honour. The question this document answers: *a high fidelity but low cost illusion of the world moving around
you* — several genuinely different routes to it, each rated on **two axes
kept deliberately separate: cheapness and fidelity**. Cheap does not win by
default; the frontier is the deliverable, including the options that are
expensive and excellent. Sources: the architecture document ("Cost and
performance", "Lifecycle and reactivation", "Design principles"),
[`PROPOSAL_2026-08-06.md`](../archive/PROPOSAL_2026-08-06.md) §1 and its
[amendments](../archive/PROPOSAL_2026-08-06_AMENDMENTS.md),
[`OFFSCREEN_LIFE_DESIGN.md`](OFFSCREEN_LIFE_DESIGN.md),
[`BACKGROUND_LIFE_DESIGN.md`](BACKGROUND_LIFE_DESIGN.md), the crowd-blob
proposal, and the bg-life modules as they stand on `main`
(`world/gaps.py`, `world/offscreen.py`, `world/subjects.py`, `mind/canon_provenance.py`,
`world/background_claims.py`, `core/jobs.py`) `[read]`.

Evidence marking follows the proposal: `[read]` code opened, `[measured]` a
query against a live database, `[estimate]` a number nobody has measured.

---

## 0. Three rules that shape everything below

### 0.1 The binding constraint is latency in the player's path — not spend

A turn starting must never wait on, or cancel, offscreen work. That is the
one cost that is never paid. Money spent **off the critical path** is money
the author is willing to spend — this engine is not under the budget
pressure its heavier siblings are — so every rating below prices calls
honestly and then notes where they run. The seam already exists and is
already pinned: `core/jobs.py` runs work between turns, `base_turn`-stamped, and
a turn starting never cancels a tick — cancelling would make the world's
aliveness inversely proportional to player engagement, which inverts the
feature (amendment 4) `[read]`.

### 0.2 Offscreen events are never told, only encountered

Stated by the author, and it prunes the space rather than decorating it: an
offscreen event has exactly **two legitimate surfaces** and no third.

1. **Aftermath.** The player arrives after it happened and reads it off
   changed state: the door forced, the stall gone, the man absent, the mood
   in the room, a notice on the board, a name on a fresh grave.
2. **In progress.** The player walks in on it mid-occurrence and it resolves
   in front of them on the normal turn path — which includes someone *in the
   scene telling them something*, because a telling is an event happening
   now, with a speaker who can be wrong, not a report from the engine.

This kills a class outright: "meanwhile, across the city…" cutaways, digest
summaries surfaced to the player, interim-filler recaps, any prose injected
because the engine knows something the player does not. It is also the only
class the architecture could never have hosted anyway — a "meanwhile" needs
the narrator to hold the world record, and the narrator receives only the
protagonist's perception object. The firewall and the aesthetic point the
same way, which is usually the sign a rule is right.

**The consequence: ticks produce state, never prose.** Positions, closures,
absences, claims, moods, due-times, revised plans. Prose is authored at the
moment of contact by machinery already being paid for — perception filters
the state, the Director stages it, the narrator renders the player's slice.
So fidelity at tick time is a property of the **state and the trail**, and
cost scales with **what the player actually reaches**, not with how much
world exists. A city can churn for a hundred turns and cost nothing until
someone opens a door.

### 0.3 What a model call buys, and what it cannot be replaced by

The floor and the ceiling of every approach differ on one thing only.
**Deterministic state is plausible motion**: things happened, on schedule,
within bounds — seeded, replayable, free, and never wrong in a way prose can
be, because it asserts almost nothing. **Model-produced state is motivated
motion**: things happened *for reasons that cohere and chain* — a faction
acting in character rather than at random, a consequence begetting a
second-order consequence no table anticipated, relationships shifting in
ways that survive later investigation. The player detects the difference at
contact, in three specific ways:

- **Chaining.** The fire raises grain prices; the prices start the bread
  queue; the queue is where the recruiter works. Tables give one hop.
- **Retrospective legibility.** An aftermath the player *investigates* holds
  up, because each step was chosen by something reading real information —
  the trail tells one story from any direction it is walked.
- **Character.** The garrison commander's response to the theft is *his*,
  not the generic one. At the seeded tier everyone responds identically
  because nobody responds at all; things merely proceed.

And one case where the model is not an upgrade but a necessity:
**adaptation.** A plan responding to information that did not exist when the
plan was written is not derivable from any track. When news of the player's
interference reaches the villain, the next move requires psychology. That is
a model call, it is event-triggered rather than cadenced — so its cost
scales with dramatic density, the architecture's own thesis — and even it
produces *state* (a revised plan, a new due-time), never prose.

(One more paid class exists — novel particulars at first contact: the dead
man's face, the innkeeper's name — but it is paid at contact on the
render/mapping path already being paid, and moves no money offscreen.)

### 0.4 The measurement debt, stated before any design is trusted

Not one line of the background-life machinery has run against a real story
`[read]`: the seeded stochastic rung, the profile rung, `interim_for`
delivery, the claims lane (0 of 29 opportunities `[measured]`), the
`subject_last_seen` ledger. This project's costliest recurring discovery is
mechanisms assumed live that never ran — disputes 0 of 181, a psychology
tier absent from 14 banks, a "seeded" tick whose seed no RNG consumed. So
the honest first move under any ranking is **one instrumented story before
new machinery**, reporting against real denominators: ticks drawn per
eligible boundary; gap deliveries per re-contact; whether any tick's content
ever reached a payload the player's turn consumed; claims recorded per
scene-manager firing. The proposal §2B gate applies. The approaches below
are designed so the first increment of each doubles as instrumentation of
the substrate it stands on.

---

Each approach below carries a **floor** (deterministic, seeded, free) and a
**ceiling** (model-assisted, off the critical path), rated separately —
because the author asked for the frontier, and because they are usually the
same mechanism spending at two depths, not two mechanisms.

## 1. Approach A — routine and residue: the world's default motion

**Floor.** Every place and fixture gets a *routine* — a pure function from
the simulation clock and lore tags to expected state — plus seeded jitter so
regularity never becomes clockwork, plus entropy (fires burn down, food
spoils, dust settles). The tick is a deterministic recompute; the residue is
the diff between the room as last seen (`subject_last_seen` anchors it
`[read]`) and the room as the routine says it now stands. At re-entry the
diff enters the **Director's staging payload as present-tense facts** — the
chairs are up, the hearth cold, the market a handful where it was a throng —
capped at two or three, under BACKGROUND_LIFE §5's texture-not-beats clause.
The crowd proposal slots in whole: a crowd band as a function of clock and
routine is this approach's most visible output, density stays derived
(band − room size), and the zero-content assertion — *sound through a wall,
too muffled to carry words* — is the same approach at its fidelity floor:
present perception of an adjacent in-progress event, asserting continuation
while asserting nothing.

**Ceiling — the ensemble tick.** One out-of-band call per *familiar,
inhabited* location per long cadence (scene boundary or in-world day),
advancing that location's **social state as structured state**: which
fixtures are feuding, who stopped speaking to whom, what the regulars are
worried about, what the barkeep is short of. Output is fields, not prose —
short attribute strings are state. This buys the thing
BACKGROUND_LIFE §2.1 names as what makes a place feel inhabited:
**indifference** — a tavern whose ongoing life does not revolve around the
player, encountered as changed alignments and moods on return, with reasons
recoverable by asking.

**Cheapness.** Floor: zero calls at tick and at rest; ~100–300 payload
tokens on re-entry turns `[estimate]`. Ceiling: ~1 call per tracked location
per cadence — with 2–3 familiar places, roughly one call every few turns,
all off-path `[estimate]`.

**Fidelity.** Floor: high texture, no plot — time visibly passes, returns
always differ, nothing is ever commented on. Ceiling: familiar places gain
*continuing stories*; the felt difference is between a town with weather and
a town with neighbours.

**How it fails, from the chair.** *The changelog*: the narrator dramatizes
every delta and a quiet return reads like a diff report — the cap and the
texture clause must ship with it, not after. *The clockwork*: perfect
regularity reads as mechanism — the seeded jitter is what keeps a rhythm
from being a schedule. Ceiling adds *soap-opera drift*: an ensemble advanced
every day without an anchor caricatures itself (the self-feeding-digest
failure BACKGROUND_LIFE §3.11 already names); the frozen blurb is the
anchor, and cadence should be lazy — tick on return-horizon, not on wall
clock.

**Substrate.** Mostly exists: the clock, `subject_last_seen`,
`gaps._skeleton`, `scheduled_events`, the room graph; `world/place_purpose.py`
likely carries "what a place is for" (read before building). New: routine
tables (small, pure), the residue-diff assembler, the payload seam; the
ensemble tick needs a schema and a jobs producer.

## 2. Approach B — scheduled consequence: the world as a delay line

**Floor.** Causes mint their consequences *at cause time*, as fuses:
`{what, where, due_clock, provisional}` rows in `scheduled_events`, which
already exists with a runtime writer `[read]`. News of the fire reaches the
capital in a week; the patrol doubles three days after the theft. Minting is
deterministic for known kinds (`world/mechanics.py` already does transit and news
latency `[read]`) plus a small structured field on a commit-time model
output already running. Firing is deterministic. **A fired fuse is state**:
when the player arrives, the patrol *is* doubled, the notice *is* posted.
Locations must resolve to node ids on the write path (the "quiet office"
gate), dues are bounded, every write is provisional — the Director ratifies
at the beat where the player meets it (amendment 5's
arrival-is-resolution).

**Ceiling — consequence chaining.** When a *significant* fuse fires, one
out-of-band call asks: given this consequence and this local state, what
second-order fuse does it mint? Fire → grain prices → bread queue → the
recruiter working it. This is the single thing tables are worst at — depth
of causality — and it is bounded by a significance flag, so quiet fuses
chain nothing.

**Cheapness.** Floor: zero marginal calls; ~50–150 tokens on an existing
output `[estimate]`; at rest zero — fuses are rows, not processes. Ceiling:
~1 call per significant fired fuse, off-path, rare by construction
`[estimate]`.

**Fidelity.** Floor: the world *reacts* — to the player and to itself — with
realistic latency, which is the tell of honesty (the villain who learns of
the burned outpost three days late is the engine's best argument for
itself). Ceiling: the world's causality acquires depth — an investigated
aftermath has layers, and second-order consequences are the ones players
retell.

**How it fails, from the chair.** *The consequence that ignored the week*: a
fuse minted at turn N fires into a world the player changed at N+4 —
base-revision checking at fire time plus ratify-at-delivery is the guard,
the same `base_turn` discipline `core/jobs.py` and `land_profile_ticks` already
implement `[read]`. *Escalation spam*: every beat minting fuses turns a
quiet story into a ratchet — cap mints per turn, TTL the untriggered, let
most beats mint nothing (the `pick_background_reactor` shape: a
deterministic gate returning none, most turns, correctly).

**Substrate.** `scheduled_events` + `world/mechanics.py` are the delay line;
`canon_provenance` the provisional wrapper. New: the minting seam, the
fire-time revision check, and (ceiling) the chaining producer. Small.

## 3. Approach C — the rumor ledger: information is the thing that moves

**Floor.** Simulates neither bodies nor scenes but **what is known where**.
Committed events emit news items from their *witnessed surface only* — what
perception says was publicly visible; concealed acts emit nothing, so the
firewall is structural, not instructed. Items propagate along the place
graph at finite speed on B's delay line and **degrade by subtraction as they
travel**: seeded, deterministic drops of specificity — a name becomes "a
stranger", a count becomes "several" — never additive paraphrase, so
distortion cannot invent and therefore cannot contradict. The ledger is
state. It surfaces only through the two legitimate doors: **diegetic
speech** (the barkeep passes on what has reached his room — an in-progress
event with a speaker who can be wrong, riding scene-manager/NPC payloads
already running) and **artifacts** (a notice, a wanted bill — aftermath
state a room simply contains). Every surfaced item routes through
`background_claims` with claimant credence `[read]`, so wrongness is
diegetic: the drunk's version reads as a drunk's version.

**Built first physical slice `[read]`.** `carriers.advance_carriers` emits only
the non-empty public `witnessed` surface of a newly promoted `world_events`
row, and only into the frame-specific state of a registered character whose
body is at that location. The envelope then moves because that holder's scene
position moves; another character in the destination receives nothing by
proximity. Only the holder's private agent payload sees it, so transmission to
a listener must occur on-page through the existing speech/perception/memory
path. This supplies E's knowledge firewall now. Anonymous crowds/messages,
explicit copying, graph fan-out, and subtractive degradation at each copy are
extensions to this minimum physical floor; do not relabel objective event
existence as knowledge to skip them.

**Ceiling — authored artifacts.** When an item propagates to a
surface-bearing location, one small out-of-band call mints the artifact's
actual text — the proclamation's wording, the bill's clumsy woodcut caption
— stored as an artifact object (state) and encountered by reading it. The
*speaker-side* coloring of a rumor needs no new spend at all: the scene
manager call that voices the room is already running at contact, and giving
it the ledger item is a payload change. Ledger distortion itself stays
deterministic and subtractive on purpose — that is a correctness argument,
not a cost one (see failure modes).

**Cheapness.** Floor: zero calls — emission is a projection of committed
perception data, propagation a graph walk, degradation a seeded function;
~50–150 payload tokens at surfaces `[estimate]`. Ceiling: ~1 small call per
minted artifact, off-path, uncommon `[estimate]`.

**Fidelity.** Floor: the strongest single felt signal in the whole
document — **the player's own deeds precede them, sometimes garbled.** Walk
into a town three days after the bridge fight and someone has heard —
wrongly, in a way that is visibly a rumor and not visibly a bug, because the
wrong version is a *vaguer* version. Ceiling: the world's paperwork exists
and reads in-voice; proclamations become props the player keeps.

**How it fails, from the chair.** *"How did he know that"* — spooky
prescience — is the fatal version, structurally excluded by emitting only
witnessed surfaces at latency; any breach is a bug in the emission
projection, findable by test. *The town of criers*: every NPC reciting news
— cap items per location per window, let credence gate who repeats what.
*Bug-shaped wrongness*: additive distortion would produce a *different*
story rather than a fainter one, and different reads as engine error — hence
subtraction-only at the ledger, with in-character coloring confined to
contact time where the Director can adjudicate it.

**Substrate.** Needs B's delay line, the visibility-posture data already on
declarations `[read]`, `background_claims`, and a new (small, deterministic)
emission-and-degradation module. The claims lane it rides has fired 0 of 29
times `[measured]` — see it fire in the instrumented run before trusting it
with this.

## 4. Approach D — places that owe a history: the lorebook edge

**Floor.** Solves the named problem: lorebook locations the mapping agent
has never generated — Re:Zero's 29 places with no ordinary living person
among them `[measured]` — feeling changed and affected *before first
arrival*. Amendment 8 already gives them identity (`kind: place`, keyed on
the lore entry `[read]`) and the rule: **do not simulate; accumulate
obligations.** Under §0.2 this is cheaper than either prior framing assumed:
an unvisited place needs no prose and no generation, only **accumulated
state and a plausible trail** — fuses that fired there (B), rumors that
passed through or originated there (C), routine posture from its lore tags
(A: season, market cycle, garrison rhythm) — all provisional rows against
its `entry_uid`. When the mapping agent finally generates the room — a cost
already paid at arrival — it generates a room that **owes a history**, with
the obligation list as constraint, and the player reads the backlog as
*aftermath in the present tense*: the burned wing already rebuilt in cheap
timber, the garrison doubled, the offerings swept away.

The cheap half can land first: **reference before arrival.** Surface distant
lore places into payloads whose calls already run, so speech names them —
and the mention *creates* a claim the room must later honour, under the same
claims machinery. The bar is measured: ≤4.3% of place-marked lore entries
are ever named in prose today `[measured]` — the rare feature with a clean
before/after number.

**Ceiling — obligation-aware pre-generation.** When signals accumulate that
a place is likely-next (the architecture's predictive staging, §2.9), spend
the mapping generation *early, out of band*: first arrival becomes instant,
and a generation under no time pressure can honour more obligations, better.
The call was going to be paid at arrival anyway; the ceiling moves it off
the player's path and buys quality with the slack.

**Cheapness.** Floor: zero while unvisited — obligations are rows written by
A/B/C's machinery; arrival costs what arrival already cost. Ceiling: the
same call, earlier; waste bounded by the staging heuristic's miss rate
`[estimate]`.

**Fidelity.** Floor: **the map has no edge.** Places never seen are spoken
of as having weather, trouble, recent history; arriving confirms the talk —
or diegetically contradicts it, since rumors carry credence. Ceiling: no
first-visit generation stall, and richer honoring of the debt.

**How it fails, from the chair.** *The room that recites its homework*:
generation straining under fourteen obligations produces an arrival
paragraph that reads like a briefing — cap obligations per place, rank by
credence and recency, let the rest silently expire as things that turned out
not to matter. *TTL eating the truth*: `CLAIM_TTL_TURNS = 8` deletes claims
about subjects the player was never near — amendment 7's open consequence;
the countdown must pause while a subject is offscreen, and that lands before
this approach writes anything it means to keep.

**Substrate.** `subjects.resolve_subject` already resolves `place`;
`canon_provenance` already spells it; `background_claims` is the ledger.
New: the obligation feed (a routing rule, not a mechanism), the
mapping-payload seam at generation, and (ceiling) the staging trigger.

## 5. Approach E — the antagonist ladder: where the fidelity money goes

The one to three characters whose plans must advance whether or not anyone
watches — you cannot lose a race that was never run. Three rungs, and unlike
the other approaches the rungs differ in *kind*, so they are rated
separately. All of them: opt-in per character with a bounded count, out of
band, seeded and logged, provisional until adjudicated, and firewalled — the
actor's offscreen perception **is the rumor ledger at their location** (C),
so they know what has reached them, at latency, and nothing else. Sometimes
wrong about where you are, occasionally beaten by slow information: the
engine's thesis, in one character.

**Rung 1 — the tracked plan (floor; reactive executor built `[read]`).** A
present character's explicit declaration may be Director-adjudicated into at
most six typed stages. Commit checks that the stored basis came from that
character's result on the same beat; absent minds cannot be assigned an
objective. Time or fired-event triggers advance the stage deterministically and
may mint only the consequence effect adjudicated when the plan opened — zero
calls at firing. This is a clock with a knife, not yet a schemer: assumption
intersection and adaptive track revision still wait on C.

**Rung 2 — `reactive` (built `[read]`).** This is the authority ceiling used by
the tracked-plan floor above: triggers execute authored stages without an
autonomous decision. It is frame-scoped and checkpointed, capped at eight
plans/six stages and three fires per epoch. A crossed stage deadline creates an
epoch even inside an hour bucket. It cannot inspect undelivered player state,
revise an objective, or invent an effect at firing.

**Rung 3 — the full `character_agent` tick (the ceiling, costed as
asked).** The proposal's §1.0.1a reduced turn, per acting character per
cadence tick: a coarse world summary assembled free from state (their slice
of the rumor ledger); **one call** — declaration from psychology; **one
call or seeded dice** — Director adjudication; commit as durable state
(moves, standing-intention writes, fuses into B, and — the honest, expensive
answer to OFFSCREEN_LIFE's open question — **provenance-tagged memory of
the gap**, so re-contact dialogue carries their actual offscreen
experience). Per the proposal: 3–4 calls per acting character per tick
`[read]`; at a scene-boundary or ~3-turn cadence with the cap at 2–3
actors, amortized worst case ~2–4 calls per player turn, **all off the
critical path** `[estimate]`. At rest (player idle): zero, because cadence
is turn-indexed, not wall-clock — deliberately, so an idle story does not
simmer.

**What the player notices at the ceiling that the floor cannot give.** The
plan *changes*: feints, reprioritization, mistakes. Aftermath survives
interrogation — every step was chosen by a mind reading real information,
so the trail tells one story from any direction. At re-contact the
antagonist's talk carries a real remembered week, and their theory of mind
about the player has moved on actual evidence. The compressed version:
**rung 1 lets you lose to a scheduler; rung 3 lets you lose to a schemer.**
That difference is the single highest-fidelity purchase in this document.

**How it fails, from the chair.** *Victory by declaration*: guarded
structurally — only the Director-adjudicated path may commit consequences;
everything below describes intent (proposal §1.0.1, already enforced in the
built rungs' record shapes `[read]`). *The prescient villain*: guarded by
ledger-as-perception; hand this machinery the player's location once and
the architecture's named failure mode is rebuilt. *The unfair loss*: a race
lost without an evidence trail reads as the engine cheating — **E without B
and C is worse than no E**; rumors, prices, patrols and refugees are what
make the loss a tragedy instead of a gotcha. *The tier that never fires*:
commit metrics and `tools/fire_rates.py` now retain offered/accepted ops,
considered/fired stages, and effect opportunities/mints; `character_agent`
remains permission with no behavior. E's adaptive ceiling therefore stays
behind the measurement and carrier gates regardless of budget.

**Substrate.** Built floor: `offscreen_plans`, `offscreen_epoch`, the same-beat
grounding check, B's consequence validator, and the checkpoint-safe
`world_events` objective spine. Still new: C, the assumption
intersection check, per-character opt-in, reduced-turn producer, adaptive
adjudication seam, and offscreen memory commit. The genuinely novel work in
this document, and the least of it is code.

---

## 6. What this retires or restates

- **Narrated elsewhere** — cutaways, meanwhiles, engine recaps: dead under
  §0.2, and structurally impossible through the narrator anyway. Not rated.
- **The profile-summary rung as built** (`offscreen.profile_summary_record`
  `[read]`): its model call is legitimate under §0.1 — its *output shape* was
  not. It produced a prose summary, and prose has no player-legitimate
  surface. **Fixed in phase 1**: the call now fills bounded state fields
  (`{doing, at, manner}`, word-capped on the write path), the stored `tick`
  string is composed by code from those fields, and prose reaches the player
  only at contact through the character's own mouth. Let the instrumented run
  still report whether its contribution over the deterministic skeleton is
  felt at all before deciding its future.
- **Interim filler / digest recaps** (BACKGROUND_LIFE §3.9): the fabricated
  gap-summary is a told-not-encountered surface. What survives is aftermath
  state (the presence's `last_seen_clock`, the fuses that fired at their
  station) rendered at contact by the presence's own next line.
- **The gap generator survives whole** — `gap_for`'s record was always
  state, never prose `[read]`; §0.2 is an argument for the shape it already
  has. What changes is which consumers are legitimate: character payloads
  (a mind's own trail) yes; anything player-facing only through A–D's
  surfaces.

## 7. The parallelism contract (named problem 2, already decided)

Every approach and every ceiling obeys the same three rules, all already
decided or built: offscreen work runs **out of band** (`core/jobs.py`, from the
commit tail, never on the turn path `[read]`); an in-flight tick is **never
cancelled by a turn starting** (amendment 4, pinned by test); and every
offscreen write is **provisional, so arrival is the resolution event, not
the collision** (amendment 5, `canon_provenance` `[read]`). State-not-prose
makes the contract almost trivial to honour — a mutation row cannot race a
paragraph — and it is what lets the ceilings spend freely: the only
unaffordable place for a model call is in front of the player, and none of
these ever stand there.

---

## 8. The frontier, and a recommendation

Two axes, kept separate as asked. On-path cost is zero for every row — that
is the contract, not a rating.

| Approach | Cheapness (floor → ceiling) | Fidelity (floor → ceiling) |
|---|---|---|
| **A** routine & residue | free → ~1 call / familiar place / cadence | time passes, returns differ → familiar places have continuing lives |
| **B** scheduled consequence | free → ~1 call / significant fuse | the world reacts, with honest latency → causality has depth, consequences chain |
| **C** rumor ledger | free → ~1 small call / artifact | your deeds precede you, garbled and credenced → the world's paperwork exists |
| **D** obligated places | free → arrival call paid early | the map has no edge → no arrival stall, richer honored history |
| **E** antagonist ladder | ~2 calls / dramatic event → ~2–4 calls / turn amortized, capped actors | a losable race against a scheduler → a losable race against a schemer, with memory |

**Reading the frontier.** The floors of A–D are one economy, not four
features — A moves recurring state, B caused state, C known state, D banks
all three for the unvisited map — and together they are the zero-call answer
the author asked to have weighed: my estimate, unmeasured and marked as
such, is that they carry on the order of 80% of the achievable illusion
`[estimate]`. But the remaining 20% is not the same *kind* of thing, and it
is disproportionately what players remember: motivated, chaining, adaptive
consequence — the part of a world that can outplay you. The floors are the
best fidelity-per-token in the document; **E's ceiling is the best fidelity
per dollar**, because it is the only purchase that changes what the world
*is* (capable of authored opposition) rather than how finely it is drawn.

**Build order** (floors first because they are the substrate the ceilings
condition on, not because cheap wins):

1. **A floor** — landing it is mostly delivery discipline over ledgers
   already written, so it doubles as the §0.4 instrumented run.
2. **B floor** — the delay line everything else propagates on.
3. **C floor** — the biggest felt win; needs B, and needs its claims lane
   observed firing.
4. **D floor** — reference-before-arrival any time (it has its own measured
   baseline, ≤4.3%); obligation-honoring once B and C are writing.
5. **E rung 1, then rung 3** for one antagonist, once B+C exist to make
   losses legible — then the ceilings of A–D in whatever order play
   demonstrates the appetite for, which is a measurement, not a guess.

**If one thing is best:** the combined floors, because they make the world
continuous for free and nothing else works without them. **If one purchase
is best:** the full character-agent tick for a single antagonist — rung 3 —
because a world that can genuinely move against you is the illusion every
other approach can only imply.

---

## 9. The author's constraints, verbatim — phase-2 commitments

Recorded after approval, unparaphrased on purpose: these are design
commitments, and paraphrase is how a commitment erodes. The phase-1 shapes
(B's fuse payloads, D's obligation rows) were built to honour them — every
event record already carries `{what, where, a time, origin, originator,
witnessed, disposition}`, the pickup surface a carrier needs, extensible
with `{carrier, route}` without migration.

### 9.1 Information travels by carriers along routes, never by timer

> rumors of the player can spread but they need a realistic simulated
> pathway, it can never be assumed that an npc a town away suddenly knows
> what a player did in another town, We should have simulated info routes a
> player could potentially intercept like traders or what not.

> or maybe an antagonist is spreading malicious rumors.

A carrier is a thing in the world — a trader, a courier, a caravan — with a
position and a path, which the player can **intercept, follow, question,
outrun, or silence**. Propagation delay must be a *consequence of the
route*, never a configured constant. **This document's §3 delay-line
propagation is therefore insufficient as written**: the delay line survives
as the clock the carriers move on, but C's floor must model carriers, not
timers.

### 9.2 An injected rumor obeys the same physics

> but that needs to spread not instantly apply

An antagonist is a **source, not a broadcast**: their claim enters the
network at a point in space and time and travels like everything else.
**Intent buys carriers, not teleportation** — reach (money, couriers, a
guild, a pulpit) buys more carriers and better routes, never an exemption
from the delay. That keeps one rule for all information, and it makes the
antagonist counterable by play: a lie on a courier can be intercepted,
outrun, or beaten to the destination by the truth.

### 9.3 The player earns importance; nothing grants it

> and the player cannot be given extra importance unless they earn it.
> Background npcs cannot assume the player is more important than other
> rumours unless they have genuinely earned reputation.

A rumor's propagation priority is a function of **the rumor** — novelty,
scale, consequence, relevance to the carrier — never of its subject.
Reputation is earned, tracked, starts at nothing, and is **downstream** of
the carrier network, not an input to it. Carriers select by their own
interest. **The null result is the feature**: most player actions die where
they happened — the load-bearing test is that an ordinary deed has *not*
reached the next town after fifty turns. Corollary: an NPC who has never
received a rumor about the player behaves exactly as if the player is
nobody — no hedging, no "you seem familiar"; unearned recognition is the
same defect class as the Kadoman leak. Phase-1 consequence, honoured:
nothing in A, B or D writes a player-reputation value, and no fuse or
obligation carries a priority/importance/significance field (pinned by
test).

### 9.4 The network is a world simulation, not a player-reputation system

> which means rumors must not be player centric, they can be based off
> world events the player hasn't even witnessed and other character
> interactions.

Rumor traffic is world events generally — a bridge out, a betrothal, a feud
between strangers — and the player is one possible subject among many,
usually minor. This **retires §3's framing** of "the player's own deeds
precede them" as the ledger's purpose: it is one story the network tells,
not what the network is for. It also closes the epistemic loop for the
player: the carrier network is the third legitimate surface beside
aftermath and walking-in — diegetic and lossy, somebody told you, they may
be wrong, and you know who. The player learns what happened elsewhere
because something carried it to them, never because the engine knows it.

### 9.5 Invented gossip enters as claims, never as facts

> or even made up background character interactions.

Texture that was never simulated — two vendors feuding, somebody's cousin's
wedding — is legitimate carrier traffic, entering through
`background_claims` + the provisional tier: hearsay with a claimant, a TTL,
no canonical standing until the Director ratifies. A generated rumor must
be **indistinguishable in form** from a witnessed one — same record, same
carrier physics, same route; only the provenance tier differs (phase 1
already writes `disposition` on every fuse and obligation for exactly this)
— and repetition is not evidence: ratification is the only door into canon.
This is also the claims lane's first real producer; its measured 0-of-29
may be absence of reason rather than defect.

### 9.6 Truth is layered: the event is real, knowledge of it is a claim

> This also means world events can genuinely happen without the player
> without them ever visiting a location but hearing about what happened to
> it from rumor via background or other characters

Layer 1: B's fired fuses and D's obligations are **genuine state**, at a
location and a time, whether or not anyone looks — which is why D
*accumulates* durable rows as fuses fire rather than minting history at
arrival: a rumor needs a truth to be a distortion of, and arrival must be
able to contradict the telling. (This supersedes §2's blanket "every write
is provisional" for the fuse substrate: a Director-adjudicated cause fired
by deterministic code is `resolved_fact`; provisionality stays on
model-produced records.) Layer 2: what reaches anyone is a carrier's
account — degraded, attributed, possibly stale, possibly malicious — held
as `told`-provenance memory with a claimant, against `witnessed` at
arrival. The two can disagree, and going and looking is the only
reconciliation. Neither layer may write into any character's knowledge as
a side effect of being true: truth propagates only by route.
