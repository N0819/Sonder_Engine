# Off-screen world — the architecture

Status: **accepted direction; implementation in progress.** This document is
the durable half: the invariants, the seven parts of the architecture, and the
shapes deliberately rejected. Its status half — what is built, what is next,
and the completion gate — lives in
[`OFFSCREEN_WORLD_COMPLETION.md`](OFFSCREEN_WORLD_COMPLETION.md), and is not
repeated here.
Scope: living world, off-screen life, crowds, durable social continuity, and
the remaining ideas worth carrying forward from the original architecture.
Authority: `Design.md`, `docs/guides/PIPELINE.md`, and `docs/guides/DATABASE.md` remain the
maintained specifications. This proposal orders work and defines completion;
it does not override those documents.

## 1. Outcome

Sonder should create a convincing illusion that the world continues beyond the
current room without simulating every person on every turn. The completed
architecture has one cheap deterministic spine and spends model calls only when
dramatic density justifies them:

1. a **world epoch** identifies meaningful off-screen opportunities;
2. routines, scheduled consequences, crowds, and tracked plans advance as
   structured state;
3. information travels through witnessed carriers and routes, never because the
   engine knows it;
4. important opted-in characters may deliberate from their own knowledge;
5. re-contact turns prior structured state into present evidence and character
   memory, not omniscient recap prose.

The result should outperform a raw model call in the areas structure can
actually improve: causality, continuity, character agency, epistemic integrity,
rollback, and durable memory. It must remain genre-agnostic. The engine owns
universal concepts such as time, location, contact, evidence, plans,
consequences, belief, and authority. Lorebooks and the Director decide whether
those facts mean politics, magic, romance, combat, trade, horror, or something
else.

## 2. Non-negotiable invariants

### 2.1 One authority ceiling

`scene.OFFSCREEN_LIFE_LADDER` is the only permission ladder:

`inert → deterministic → reactive → stochastic → character_agent`

Living-world mechanism settings choose *which* state producers an author wants;
the off-screen ladder limits how much authority any of them may spend. A second
agent-specific vocabulary must not be invented. Per-character configuration is
an override beneath the chat ceiling, never a way to exceed it.

### 2.2 Minds receive only earned information

An off-screen character may use:

- its sheet and durable psychology;
- its own memories and beliefs;
- its own last-known place and off-screen trail;
- authored standing intentions or plans;
- information delivered through a built carrier path.

It may not receive the player's current position, recent actions, private
perception, objective world events it did not witness, or another character's
private state. Distance from the player may choose **spend**, but never content.

### 2.3 State, never cutaway prose

Off-screen work produces structured state: positions, absences, closures,
conditions, plans, due times, relationships, claims, and memories. It never
injects “meanwhile…” narration. The player earns off-screen information through
aftermath, present perception, investigation, or a fallible speaker.

### 2.4 One persistence boundary

Primary facts commit through `commit.py` under the turn transaction. Slow model
work runs out of band through `jobs.py`, carries a base turn/frame/epoch, and
lands only after rollback and idempotence checks. No background job may hold a
database transaction across a provider call.

Checkpoint support is a prerequisite for every new durable concept. Epochs,
plans, carriers, relationships, event ledgers, negotiation state, and memories
must be included in pre-turn snapshot/restore, frame scoping, branch remapping,
portable export/import, and cleanup as applicable. A background result validates
both base turn and epoch/frame before landing. No new writer ships on the
assumption that checkpoint coverage can be added later.

### 2.5 Seeded, logged, inspectable

Every stochastic decision has a stable seed and a stored record. Every
mechanism reports opportunities as well as fires. “0%” without a denominator is
not a measurement. A user-facing causal inspector may eventually explain which
epoch, plan, event, carrier, and memory produced an outcome without exposing
that information inside the fiction.

## 3. The architecture

### 3.1 World epoch: the shared clock edge

The engine needs a first-class, frame-scoped epoch rather than equating “scene
boundary” with `director_establish`. An epoch is derived from already-canonical
state and recorded once per frame:

- the opening canonical scene;
- crossing a coarse simulation-time bucket;
- changing the player's top-level location rather than merely moving between
  rooms in one venue;
- an explicitly scheduled event becoming due.

Ordinary conversational turns do not create epochs. The epoch record contains a
stable id, frame id, base turn, elapsed time, reasons, and seed. It is checkpoint
and branch state, so rerolling the same boundary replays rather than inventing a
second history.

All off-screen producers consume this one trigger. This replaces the dead
`director_establish` gate and the unrelated every-three-turn profile cadence.

### 3.2 Cheap deterministic spine

The deterministic spine remains useful even with every model-assisted feature
disabled:

- **A — routine and residue:** derive how familiar places differ on return;
- **B — scheduled consequences:** causes mint bounded fuses that fire later;
- **D — place obligations:** facts at ungenerated locations wait for contact;
- **crowds and fixtures:** represent population and habitual activity as blobs
  and roles, promoting individuals only when interaction earns identity;
- **reactive plans:** advance authored stages when typed time/event/location
  predicates become true.

These are state machines, not prose generators. They should be replayable and
near-free at rest.

### 3.3 Structured event and relationship spine

Activate `world_events` as the durable event ledger rather than adding more
ad-hoc logs. An event has stable identity, subject/location, time, cause,
witnesses, provenance, disposition, and optional consequence references.
`scheduled_events` remains the future/due queue; a fired entry produces or
updates a `world_events` fact.

Add a relationship-event ledger rather than repeatedly overwriting a summary.
Current relationship state is a projection of events plus authored anchors.
This makes rivalry, trust, obligation, estrangement, and reconciliation durable
without hard-coding genre-specific meanings.

Repeated independent references to the same provisional particular may raise
its canon confidence. Automatic locking must require distinct evidence paths,
not repeated self-reference by one model-generated digest.

### 3.4 Information carriers

Rumor and news are not timers that grant knowledge. A carrier is a witnessed
fact attached to a person, crowd, message, or route. It moves only when a
mechanical opportunity exists, and arrival creates character-owned evidence
that may be wrong, partial, or stale.

Carrier implementation precedes any antagonist adaptation to player-caused
events. Until then, a full off-screen agent may advance only an already-authored
plan from its own state; it cannot react to facts merely present in the world
record.

### 3.5 Reactive and full-character rungs

The reactive rung reads typed plans with bounded predicates and performs no
model call. A plan stage may wait on elapsed time, a cited event id, a known
location fact, or completion of a prior stage. Its effects go through the same
validated consequence writer as Director-authored fuses.

The `character_agent` rung is a reduced off-screen turn, never the normal
multi-agent scene loop:

1. assemble a fail-closed private context from the character's own knowledge;
2. one character call declares an attempt or plan revision;
3. one Director adjudication resolves success and structured consequences;
4. validate and land world events, plan changes, and autobiographical memory.

The author opts a character in beneath the chat ceiling. Selection is bounded
by `max_offscreen_actors`, importance × distance, due plans, and event pressure.
No cadence call is spent merely because a character exists.

### 3.6 Re-contact and long-term memory

Re-contact is settlement, not recap generation. The engine computes the gap
from committed event, plan, relationship, and location records. The returning
character receives a capped private delta plus evidence references. The
Director stages only currently observable aftermath.

Invented specifics created to bridge a gap remain provisional until contact or
other evidence ratifies them. Derived facts do not get duplicated into canon.
Full-agent actions create autobiographical memories with stable event keys so
later recall survives context compression, restoration, and long stories.

Negotiation is built after proposal quality is measured. A character may dispute
a proposed gap on identity/knowledge grounds; disputes cite the offending
claim, remain bounded, and cannot rewrite objective adjudicated events. If no
settlement is possible, disputed invention is discarded rather than promoted.

### 3.7 Coherence work is event-triggered

Do not run periodic whole-world reviews. Queue narrow coherence checks when:

- two claims about one subject conflict;
- a significant consequence fires;
- a returning subject's gap crosses multiple event chains;
- independent references make a provisional particular eligible for locking;
- a plan's assumptions are invalidated.

A long-gap user resume digest is a UI/tooling surface over existing records,
never a narrator payload. Personal-lore resonance and belief-revision salience
belong in retrieval/ranking once the underlying evidence is durable.

## 4. Build order and gates

The phase list that stood here duplicated
[`OFFSCREEN_WORLD_COMPLETION.md`](OFFSCREEN_WORLD_COMPLETION.md), which carries
the same work as numbered items with per-item BUILT/PARTLY tags and dated
measurements. Two copies of a build order drift, and this one drifted first.
**Read the completion document for what is done and what is next.** The phase
gates it inherits are unchanged in substance: an instrumented story showing
eligible epochs and real fires before continuity work counts as landed; a
mechanism with no opportunities reporting "no chances" rather than 0%; and a
long absence producing consistent observable aftermath without omniscient
exposition or unbounded standing cost.

## 5. Cost budget

- No off-screen model call on an ordinary turn merely because time advanced a
  few seconds.
- At most `max_offscreen_actors` selected actors per epoch.
- Profile rung: at most one bounded call per selected medium-resolution actor.
- Full agent: at most one character declaration plus one Director adjudication
  per selected due actor.
- Consequence chaining and coherence: event-triggered, not cadenced.
- Contact rendering reuses the normal Director/perception/narration path.

The optimization target is **cost proportional to dramatic density**, not cast
size, map size, or story length.

## 6. Explicitly rejected shapes

- a second off-screen simulation loop with separate canon;
- ticking every character every turn;
- “meanwhile” narration or private narrator omniscience;
- giving antagonists player state for dramatic convenience;
- prose-only plans whose ownership or triggers cannot be validated;
- automatic core-personality rewrites;
- per-agent rollback independent of the world's checkpoint;
- blind whole-beat parallelism as a substitute for causality;
- genre-specific combat, romance, magic, economy, or faction engines in core.

## 7. Definition of architectural completion

The gate is stated once, in
[`OFFSCREEN_WORLD_COMPLETION.md`](OFFSCREEN_WORLD_COMPLETION.md) §"Architectural
completion gate", together with the measurement that says how far off it is.
The one clause worth repeating here, because it is the clause most often
skipped: **"code exists" is not completion.** Every model-assisted mechanism
needs at least one real-story denominator and one observed fire.
