# Completing the illusion of an off-screen world

Status: **8.0 development roadmap**

Sonder's safe simulation spine is mostly built, but the illusion is not yet
complete. The engine can advance off-screen facts without granting minds
omniscience. It still needs stronger information circulation, adaptive actors,
populated places, and convincing revelation when the player returns.

```text
World epochs, events and typed plans (built)
                    |
                    v
       Carriers and social history
                    |
                    v
      Adaptive off-screen characters
                    |
                    v
       Re-contact aftermath and memory
                    |
                    v
       A world that visibly continued
```

## What is already built

- A frame-scoped world epoch derived from meaningful time, location, opening,
  due-event, and reactive-plan boundaries.
- Seeded dormant-character ticks and bounded out-of-band profile-state work.
- Typed reactive plans whose pre-adjudicated stages fire without a model call.
- A checkpoint-, archive-, import-, and branch-safe `world_events` objective
  history.
- Deterministic floors for routine residue, scheduled consequences, physical
  witnessed information carriers, place obligations, and authored antagonist
  plans.
- A first safe carrier slice: a registered character physically present at a
  public event can acquire its witnessed surface; the report follows that
  holder's real movement and is visible only to that holder's private agent.
- Explicit per-character opt-in and bounded, private-reason candidate selection
  for future full off-screen character work.
- Opportunity and fire-rate instrumentation for the new mechanisms.

The last point is important: mechanisms are not complete merely because their
symbols and tests exist. They must produce opportunities and observable fires
in real stories.

## Remaining work, in required order

### 1. Exercise the built floors in a real instrumented story

The current live corpus reports no post-implementation opportunities for world
epochs, reactive plans, profile jobs, public event surfaces, or carried-report
acquisition. These are not failed fires; the recorded denominator is still
`no chances` because the corpus predates the new commit-result shapes.

Run a controlled story that:

1. leaves characters and an authored plan behind;
2. crosses meaningful simulation-time or top-level-location boundaries;
3. fires a consequence with a public witnessed surface;
4. lets a legitimate witness carry that report;
5. returns to encounter the resulting state.

Inspect both opportunities and fires. Confirm that an unreached character
remains ignorant, rerolling replays rather than duplicates history, and the
player learns only through aftermath, present perception, investigation, or a
fallible speaker.

### 2. Build crowds and persistent fixtures — **BUILT** (2026-08-10)

All five steps are in the tree; see
[`PROPOSAL_CROWDS.md`](PROPOSAL_CROWDS.md) §7a for what the building
corrected in the design. `crowds.py` is pure; `StateDiff.crowd_ops` is how a
Director says it; `commit.commit_crowds` is the persistence boundary;
`agents.common.crowds_for_room` is the per-observer surface;
`tools/crowd_drive.py` walks the chain. Crowds are also the first anonymous
information carrier (§3), which closes the last line of this item.

The module shipped pure and correct and could not occur: perception read the
world key faithfully and nothing ever wrote it. Worth remembering when reading
any other "built" line in this document.

Places need structured inhabitants instead of population implied only by prose.
Two related forms are required:

- **Fixtures** belong to a location and may be re-met: barkeeps, vendors,
  guards, attendants, and regulars.
- **Crowds** are bounded population blobs. They represent many unnamed people
  at approximately the cost of one presence and do not consume ordinary
  managed-character slots.

Build in this order:

1. a stationary crowd blob visible to ordinary perception;
2. persistent location fixtures;
3. derived crowd density as terrain, including adjudicated drift and
   separation;
4. movement and splitting on the existing spatial graph;
5. one-way emergence of an individual stranger when interaction earns an
   identity.

Crowds should also become possible information carriers, but they must not
absorb authored cast or create persistent strangers nobody interacted with.

### 3. Complete the information-carrier network — **PARTLY BUILT**

Built: explicit copying (`state_diff.telling_ops`, refused unless the speaker
holds the report, spoke this beat and shares the room); deterministic
subtractive degradation at each copy (`degradation.py` — count, then place,
then name, with the name last so a rumor stays useful near its source);
bounded fan-out (`carriers.TELL_FANOUT_CAP`) and an exhaustion cap so a claim
with nothing left stops travelling; durable claimant and provenance on told
reports; anonymous crowd carriers that move because the crowd moves; and
malicious or invented claims entering through the same physics, keyed `claim:`
so they never reach `world_events`.

Couriers landed (2026-08-10): `couriers.py` puts a held report on an anonymous
body with a POSITION on a route computed over `spatial.passable_path` (the one
graph everyone walks), advanced on the simulation clock inside the
`information_carriers` commit domain — never a `due_seconds` fuse wearing a
courier's name. `StateDiff.courier_ops` is how a Director says it (`send`,
`question`, `silence`); perception's `couriers_for_room` shows a rider to a
body in his room, which is what makes intercept/follow/outrun real; silencing
him stops the delivery outright; a sealed `letter` crosses verbatim because it
is not retold, while `word` degrades one mouth at dispatch and one at
delivery. `tools/courier_drive.py` plays the same road twice — delivered
degraded in one run, silenced into nothing in the other.

Still unbuilt: caravan and artifact carriers (a minted physical notice/bill a
room contains), and multi-stop trader routes.

The original text of this item follows.

The registered first-person witness is the minimum epistemically safe floor,
not a complete rumor network. Add:

- anonymous crowd, trader, courier, caravan, message, letter, and artifact
  carriers;
- explicit copy or telling events rather than knowledge transfer by proximity;
- positions and movement over actual routes;
- bounded route fan-out;
- deterministic, subtractive degradation at each copy, such as a name becoming
  `a stranger` or an exact count becoming `several`;
- durable claimant and provenance information for told memories;
- malicious or invented claims entering through the same carrier physics as
  truthful reports.

An antagonist is a source, never a broadcast. Money, influence, couriers, or a
pulpit may buy more carriers and better routes, but never instantaneous
knowledge. The player must be able to intercept, follow, question, outrun, or
silence a route. Information about the player receives no special priority;
reputation is earned downstream of actual propagation.

### 4. Add durable social history — **PARTLY BUILT**

`relationship_events` is an append-only ledger carrying source, target, axis,
bounded magnitude, triggering event ids, turn, frame and provenance, and it
survives checkpoint, rewind, branch and archive/import. The scalar graph stays
the projection, and a test asserts it equals the sum of its own history.

Measured first: 98.8% of the 5,704 stance movements in the live corpus already
carried `trigger_event_ids`. The model had been saying why the whole time and
the seam discarded it. Evidence is MARKED rather than demanded — an
unevidenced movement is recorded as such, because refusing it would throw away
a feeling the character genuinely had and leave the graph wrong.

Still unbuilt: repeated-reference canon locking on independent evidence paths.

The original text of this item follows.

Current relationship state cannot reliably answer why a stance changed. Add a
`relationship_events` ledger containing:

- source and target;
- relationship axis and bounded magnitude;
- triggering event ids;
- turn, frame, and provenance.

Keep current relationship state as a derived projection of event history plus
authored anchors. Make triggering evidence mandatory for ordinary changes.

Also add repeated-reference canon locking based on independent evidence paths.
Repeated self-reference by one generated summary must not promote or lock a
claim.

### 5. Build the full `character_agent` rung

Candidate selection is built; the paid producer and landing path are not. Each
selected opted-in character needs one reduced off-screen turn:

1. assemble a fail-closed private context from that character's sheet,
   psychology, memories, beliefs, authored plans, last-known trail, and carried
   evidence;
2. make one character call that proposes an attempt or plan revision;
3. make one Director adjudication that resolves success and structured
   consequences;
4. atomically land world events, movement, plan changes, last-tick state, and
   stable autobiographical memories.

Distance and importance may select model spend but must never become prompt
content. The absent character receives no player position, recent action,
private perception, objective event it did not witness, or another mind's
state.

This is the highest-fidelity purchase in the design. The deterministic floor
lets the player lose to a scheduler; the full rung permits a coherent loss to a
schemer who adapted from incomplete, possibly stale information.

Required safeguards:

- `max_offscreen_actors` remains a hard cap;
- no call occurs merely because a character exists;
- one base turn, frame, and epoch guard every job;
- a reroll or restore cannot double-land work;
- only Director-adjudicated full-agent work may create new world consequences;
- off-screen output is structured state, never narrator prose;
- diagnostics remain spoiler-gated and outside the fiction.

### 6. Finish re-contact settlement

Re-contact must be settlement from committed records, not freeform recap
generation. Derive a bounded gap from:

- objective world events;
- plan stages and consequences;
- location and movement history;
- carried and told information;
- relationship events;
- the returning character's autobiographical memories.

The returning character receives its own private delta and stable evidence
references. The Director receives only currently observable aftermath. The
Narrator receives only the player's resulting perception.

Invented bridge details stay provisional until contact or other evidence
ratifies them. Derived facts are not duplicated into lore.

Measure proposal quality before building the full negotiation protocol. If
needed, add bounded disputes only for identity, knowledge, and continuity
violations; objective adjudicated events cannot be negotiated away.

### 7. Build and measure the five model-assisted ceilings

All five living-world mechanisms currently expose only their deterministic or
reactive floor. Their ceilings remain unbuilt:

- **Routine and residue:** advance the continuing social state of familiar
  places as structured fields.
- **Scheduled consequences:** let significant fired consequences mint bounded
  second-order consequences.
- **Rumor ledger:** mint durable authored notices, proclamations, and other
  physical information artifacts.
- **Place obligations:** predict likely-next locations and perform
  obligation-aware generation out of band before arrival.
- **Antagonist ladder:** run the full adaptive `character_agent` turn described
  above.

Each ceiling must remain off the player's critical path and be triggered by
dramatic density, never raw cast size, map size, story length, or wall-clock
time.

### 8. Add coherence and inspection surfaces

Once the underlying records are durable, add event-triggered—not periodic—work
for:

- conflicting claims about one subject;
- significant consequence chains;
- returning subjects whose gaps cross multiple event chains;
- provisional particulars eligible for independent-evidence locking;
- plans invalidated by newly delivered information.

Add a spoiler-gated causal inspector that can explain which epoch, event, plan,
carrier, relationship delta, and memory produced an outcome. A user-facing
resume digest may summarize stored records outside the fiction, but it must
never become omniscient Narrator context.

## Minimum convincing 8.0 milestone

Before claiming that the illusion works, demonstrate one real story in which:

- a place changes across an absence without a model call;
- a scheduled or reactive consequence genuinely fires;
- one witness learns while another unreached mind remains ignorant;
- information follows a route and arrives late, degraded, or not at all;
- an opted-in character adapts only after legitimate evidence reaches them;
- the player encounters consistent aftermath before receiving an explanation;
- the returning character remembers its own off-screen experience;
- reroll, restore, branch, archive, and import preserve or rewind the same
  history correctly.

The strongest falsifier is an ordinary event that does **not** spread. If every
deed becomes news, if a distant NPC vaguely recognizes the player without a
route, or if a villain reacts before evidence arrives, the illusion has failed
even if the prose sounds plausible.

## Architectural completion gate

The off-screen-world architecture is complete only when:

- all five living-world mechanisms have a working, measured floor and ceiling;
- all five `offscreen_life` rungs are honest in the UI;
- epochs, events, plans, carriers, relationships, re-contact state, and memory
  survive checkpoint, reroll, branch, archive/import, and deletion as
  applicable;
- every mind remains bounded to legitimately acquired information;
- at least one real-story opportunity and observed fire exist for every
  model-assisted mechanism;
- the isolated full suite, browser suite, structure checks, and GitHub CI pass.

The optimization target throughout is cost proportional to **dramatic
density**, not cast size, map size, or story length. A quiet world should cost
nothing while retaining the ability to become consequential when causes,
information, and motivated actors intersect.

## Related documents

- [`PROPOSAL_ARCHITECTURAL_COMPLETION.md`](PROPOSAL_ARCHITECTURAL_COMPLETION.md)
- [`OFFSCREEN_LIFE_DESIGN.md`](OFFSCREEN_LIFE_DESIGN.md)
- [`DESIGN_LIVING_WORLD.md`](DESIGN_LIVING_WORLD.md)
- [`PROPOSAL_CROWDS.md`](PROPOSAL_CROWDS.md)
- [`AGENT_HANDOFF_ARCHITECTURE.md`](AGENT_HANDOFF_ARCHITECTURE.md)
- [`UNBUILT.md`](UNBUILT.md)
