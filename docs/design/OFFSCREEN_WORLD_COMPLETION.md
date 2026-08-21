# Completing the illusion of an off-screen world

Status: **8.0 development roadmap.** **Direction amended 2026-08-21 — read
this first.** The ordering below was written when fidelity above the
deterministic spine was understood to be bought with model calls. It is now
bought with code: see
[`OFFSCREEN_WORLD_ARCHITECTURE.md`](OFFSCREEN_WORLD_ARCHITECTURE.md) §1.1 and
[`DESIGN_LIVING_WORLD.md`](DESIGN_LIVING_WORLD.md) §8.1. The remaining work
here is still wanted and still correctly ordered; what changed is what it is
allowed to cost, and therefore how deep it may go. Two caveats on this file
specifically: [`../UNBUILT.md`](../UNBUILT.md) §1.57 records that two of its
per-item tags overstate what is built, so re-verify against source before
planning on top of a row; and `UNBUILT` §2.8's `offscreen_log` migration is
now **blocking** rather than deferred, because a simulation that reads its own
past is the first thing that computes over that history.

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
- The full `character_agent` rung end to end: explicit per-character opt-in,
  bounded private-reason candidate selection, a fail-closed private context,
  one character call, one Director adjudication, and one atomic guarded
  landing.
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

### 2. Build crowds and persistent fixtures — **PARTIAL** (four of five steps)

Tagged **BUILT** here from 2026-08-10 until 2026-08-18, on the strength of five
ordered steps of which two were not in the tree. Step 1 — "a stationary crowd
blob visible to ordinary perception" — landed 2026-08-18, when
`composer.room_content_percepts` began minting the crowd (and the courier, and
the posted notice) as `ambient` percepts from the per-observer dicts perception
had been computing and dropping. **Step 2 is still absent**: persistent
location fixtures — a barkeep, a vendor, a guard, an attendant, a regular
belonging to a LOCATION and re-meetable across visits — have no implementation
anywhere. Background presences are scene-scoped and are a different thing.
Steps 3–5 are real. This item's own §2 carries the warning that applies to it:
"The module shipped pure and correct and could not occur … Worth remembering
when reading any other 'built' line in this document."

For steps 3–5, see
[`DESIGN_CROWDS.md`](DESIGN_CROWDS.md) §7a for what the building
corrected in the design. `world/crowds.py` is pure; `StateDiff.crowd_ops` is how a
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

### 3. Complete the information-carrier network — **BUILT** (2026-08-10)

Built: explicit copying (`state_diff.telling_ops`, refused unless the speaker
holds the report, spoke this beat and shares the room); deterministic
subtractive degradation at each copy (`world/degradation.py` — count, then place,
then name, with the name last so a rumor stays useful near its source);
bounded fan-out (`carriers.TELL_FANOUT_CAP`) and an exhaustion cap so a claim
with nothing left stops travelling; durable claimant and provenance on told
reports; anonymous crowd carriers that move because the crowd moves; and
malicious or invented claims entering through the same physics, keyed `claim:`
so they never reach `world_events`.

Couriers landed (2026-08-10): `story/couriers.py` puts a held report on an anonymous
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

Caravans and artifact carriers landed last (2026-08-10), which closes this
item. A caravan is a `kind` on the courier object plus a stop list — same
route, clock, perception surface and interception ops — that DWELLS at each
stop (charged in simulation time) and trades news both ways there: it tells
the standing crowd what it carries and picks up the crowd's talk, standing
public surfaces and posted notices, each through the ordinary degradation.
An artifact (`story/artifacts.py`, `StateDiff.artifact_ops`) is a claim made
physical: posted where the poster's body is from what the poster holds (an
invented claim posts like a spoken lie), acquired ONLY by explicit reading
(verbatim, provenance `read` — a copy is not a mouth), and destructible —
a torn-down bill refuses reads, vanishes from perception, and teaches a
passing caravan nothing. The wording ceiling is one small out-of-band call
(`schedule_artifact_wording`), landed only while the bill still stands;
the floor is whole with no model. `tools/caravan_drive.py` plays all three:
delivery late and garbled, a bill read, a bill torn down first.

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

### 5. Build the full `character_agent` rung — **BUILT** (2026-08-10)

The paid producer and the landing path landed beside the candidate selector.
`offscreen.schedule_agent_ticks` runs from the commit tail (`persist/commit.py`, next
to `schedule_profile_ticks`) after the turn's facts are durable; a turn
starting never cancels the job, and a failure is a warning rather than a
rollback. One reduced off-screen turn per selected candidate: the fail-closed
`offscreen.agent_context` (an allowlist, `AGENT_CONTEXT_KEYS`, on a signature
with no `scene` parameter to forget to leave out), one character call
proposing an attempt (`agent_proposal`, word-bounded), one Director call
resolving it against the objective scene (`agent_adjudication`, which refuses
a whole verdict whose `moved_to` is not a room the world contains), and
`land_agent_tick`.

Three gates compose before any model is asked, each failing toward not
spending: a world epoch; `living_world_allows(..., "antagonist_ladder",
"ceiling")`, which composes the chat's `offscreen_life=character_agent`
ceiling through `LIVING_WORLD_REQUIRES` so no second copy of that rule exists
to drift; and `full_agent_candidates`, which needs the card opt-in
(`simulation.offscreen_agent`) plus a private reason — that mind's own active
plan, or carried evidence newer than its own last paid tick.

The required safeguards below, checked against source:

- **`max_offscreen_actors` remains a hard cap** — enforced.
  `schedule_agent_ticks` reads it from `dialogue_config`, returns no job at
  zero, and passes it as the selector's `cap`.
- **No call occurs merely because a character exists** — enforced. Opt-in plus
  a private reason, and `full_agent_candidates` reads no player position, no
  objective event payload, and no omniscient scene content.
- **One base turn, frame, and epoch guard every job** — enforced. No epoch id,
  no job; the job carries `base_turn=turn_idx`; the producer thread pins
  `active_frame_id` to the scheduling turn's frame.
- **A reroll or restore cannot double-land work** — enforced inside the
  landing transaction by three guards in order (the epoch must still be
  current, the story must not have rewound past the base turn, and the
  subject's own `last_epoch_id` must not already carry this epoch), and by
  stable identity where re-landing is legitimate replay: the fuse is
  `INSERT OR REPLACE` on a `stable_event_key`, the memory upserts on its own
  `event_key`, and the log batch dedupes on its seed.
- **Only Director-adjudicated full-agent work may create new world
  consequences** — enforced. The single permitted consequence comes from the
  Director's verdict and passes `living_world.mint_consequences` into
  `scheduled_events`; `world_events` is never written here, so this rung grows
  no second writer of what objectively happened.
- **Off-screen output is structured state, never narrator prose** — enforced.
  The attempt is bounded to `AGENT_ATTEMPT_MAX_WORDS`, the log record carries
  `{doing, at, manner}`, and both the tick line and the autobiographical
  memory are composed by code (`compose_agent_tick`, `compose_agent_memory`)
  so a reroll re-mints them byte-identically.
- **Diagnostics remain spoiler-gated and outside the fiction** — nothing
  enforces this, because no diagnostic surface exists to gate. `offscreen_log`
  has one CONSUMER, `gaps.interim_for` (`world/gaps.py:268`), which delivers a
  subject's own gap at contact under a provenance filter. It has three read
  SITES, and the difference matters to anyone grepping: the other two are
  `offscreen.append_offscreen_log`'s own read-modify-write
  (`world/offscreen.py:465`) and the frame fork/merge copying the key
  (`world/spatial_frames.py:906`, `:1053`), neither of which shows anybody
  anything. The conclusion survives the correction — one consumer, and it is
  not a diagnostic surface — but "exactly one reader" is not what the tree
  says. The spoiler-gated causal inspector is still §8's work.

Built is not fired. Measured on this tree's `engine.db` (2026-08-10),
`tools/fire_rates.py` still reports `no chances` for both full-agent rows —
0 of 97 recorded epochs carried an opportunity at all — so §1 remains the gate
on this item, for exactly the reason §2 records.

The original text of this item follows.

Each selected opted-in character needs one reduced off-screen turn:

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

### 7. Build and measure the five model-assisted ceilings — **PARTLY BUILT**

Ceilings remaining (C's artifact-wording ceiling and E's adaptive rung are
built; the rest expose only their deterministic or reactive floor):

- **Routine and residue:** advance the continuing social state of familiar
  places as structured fields.
- **Scheduled consequences:** let significant fired consequences mint bounded
  second-order consequences.
- **Rumor ledger:** — **BUILT** (2026-08-10): `artifacts.schedule_artifact_wording`
  mints durable authored notice wording out of band, landing only while the
  bill still stands.
- **Place obligations:** predict likely-next locations and perform
  obligation-aware generation out of band before arrival.
- **Antagonist ladder:** — **BUILT** (2026-08-10): `offscreen.schedule_agent_ticks`
  runs the full adaptive `character_agent` turn described in §5, one reduced
  Director-adjudicated turn per opted-in candidate per world epoch.

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

## Where the milestone stands — measured 2026-08-10

Against the list below, played by `tools/quest_drive.py` (51 beats, authored)
and `tools/model_playthrough.py` (14 beats, model-authored). Artefacts:
`demos/ashen-quest-51-*` and `demos/vale-model-played-14-*`.

Demonstrated: a place changing across an absence with no model call; a
scheduled and a reactive consequence firing; one witness learning while an
unreached mind stays ignorant; information arriving late, degraded and
sometimes not at all; an opted-in character adapting on evidence it legitimately
received; aftermath met before explanation.

The falsifier the list calls strongest — an ordinary event that does NOT spread
— holds hard: crowd uptake 6% (5/83), report acquisition 6% (14/233). Most
deeds go nowhere.

**Two bullets do not yet hold, and they are the release gates:**

- **The returning character remembers its own off-screen experience.** Not
  demonstrated. § 6 re-contact settlement is unbuilt. The recommendation on
  file is to defer it to 8.1 and say so in the notes rather than rush it.
- **Reroll, restore, branch, archive and import preserve or rewind the same
  history.** Import is verified — `demos/ashen-quest-51-story.json` was
  re-imported through the production-wired `ChatArchiveService` into an empty
  database (51 turns, 111 memories, 4 cast, 7 world events). Reroll, restore
  and branch have never been tested against off-screen state. This is a
  durability claim, so it wants testing rather than deferring.

Also outstanding for the architectural completion gate: three of the five
model-assisted ceilings (routine and residue as structured fields, second-order
consequences, place-obligation pre-generation) and § 4's repeated-reference
canon locking. And every model-assisted mechanism needs "at least one real-story
opportunity and observed fire" — see the prompt-efficacy entry in
`UNBUILT.md` § 7, which is where the three that no model has ever declared are
recorded.

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

- [`OFFSCREEN_WORLD_ARCHITECTURE.md`](OFFSCREEN_WORLD_ARCHITECTURE.md) — the
  durable half of this pair: invariants, the seven parts, rejected shapes.
- [`OFFSCREEN_LIFE_DESIGN.md`](OFFSCREEN_LIFE_DESIGN.md) — characters not in the
  room: the ladder, reactivation, villain ticks.
- [`BACKGROUND_LIFE_DESIGN.md`](BACKGROUND_LIFE_DESIGN.md) — extras in the room.
- [`DESIGN_LIVING_WORLD.md`](DESIGN_LIVING_WORLD.md) — the five routes A–E rated
  on cheapness × fidelity. **§8.1 amends the recommendation**: the two axes do
  not trade, so the last of the fidelity is bought with code rather than calls.
- [`DESIGN_INSTITUTIONS_AND_UPKEEP.md`](DESIGN_INSTITUTIONS_AND_UPKEEP.md) —
  draft, nothing built. What high-fidelity-through-code means in practice:
  five genre-neutral primitives letting a crew, a ward or a monastery hold a
  functioning institution together off screen.
- [`DESIGN_CROWDS.md`](DESIGN_CROWDS.md) — crowd blobs. Built; §7a records what
  the building changed.
- [`UNBUILT.md`](../UNBUILT.md) — the register.
- [`../archive/AGENT_HANDOFF_ARCHITECTURE.md`](../archive/AGENT_HANDOFF_ARCHITECTURE.md)
  — archived session handoff, kept for its known-traps list.
