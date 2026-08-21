# DESIGN_INSTITUTIONS_AND_UPKEEP — how a simulated crew actually runs the ship

Status: **Draft. Proposed, nothing built.** Written 2026-08-21 against alpha
9.7.1. Extends [`DESIGN_LIVING_WORLD.md`](DESIGN_LIVING_WORLD.md) and
[`OFFSCREEN_WORLD_ARCHITECTURE.md`](OFFSCREEN_WORLD_ARCHITECTURE.md); it does
not override them, and every invariant there holds here unchanged.

Audience: whoever wants background characters to hold a *functioning
institution* together off screen — a starship's watch bill, a hospital's night
shift, a kitchen brigade, a monastery's hours, a garrison's rota — without the
engine learning what a reactor is.

The rule this note extracts, stated first so it cannot be buried:

> **Simulate the institution's ATTEMPT, never its outcome.** A charter wants
> every upkeep in band and tries to put a competent body on every post. The
> ship runs properly because something is *trying* to run it and mostly
> succeeding — not because a rule asserts that it runs. Every interesting
> thing this produces is a gap between the attempt and the bodies available:
> the only engineer is injured, two posts need the same hands, the man on
> watch is not speaking to his relief.

---

## 1. The question, and the failure mode it has to beat

A deterministic background simulation can move people through routines and
drift their relationships. That is not the same as *operating* something. If
the crew walks to the engine room on schedule and nothing is modelled about
whether the engine is tended, the ship is a stage set and the crew is doing
cosplay. The player who investigates finds nothing underneath.

The opposite failure is worse and more tempting: writing a starship
simulator. The moment the engine knows what a reactor is, it has a genre, and
every other story pays for it in dead weight.

So the design problem is exactly this: **produce competent institutional
behaviour, in engine vocabulary, with no genre knowledge anywhere in the
engine.**

## 2. What this inherits and must not break

From `DESIGN_LIVING_WORLD.md` and `world/routines.py`, unchanged:

- **Ticks produce state, never prose.** Nothing here narrates. No "meanwhile"
  is injected, ever.
- **Nobody learns of a fact merely because it is true.** A fired consequence
  is layer-1 fact at a location; learning is a separate, channelled question.
- **Cost scales with what the player reaches**, not with how alive the world
  is. `routines.py` never ticks at all — posture is recomputed from the clock
  at the moment of contact, so a hundred quiet turns cost nothing and write
  nothing. That is the standard to beat, not merely to match.

From `OFFSCREEN_WORLD_ARCHITECTURE.md` §1, which is the whole genre answer
already stated:

> The engine owns universal concepts such as time, location, contact,
> evidence, plans, consequences, belief, and authority. Lorebooks and the
> Director decide whether those facts mean politics, magic, romance, combat,
> trade, horror, or something else.

This note adds five universals to that list and nothing else.

## 3. The five primitives

None of these names a genre. All of them are named by the lorebook.

**Upkeep** — a named condition that must stay in a band, and drifts out of it
when unattended. `{key, band, drift_per_hour, tags}`. The engine knows a
number leaves a range. It does not know the number is coolant temperature.

**Post** — a duty slot: a place, a competence requirement, and a time window.
`{key, place_ref, requires[], window}`. Deliberately NOT called a station:
`scene.stations` already means a body's within-room position, and a second
spelling of a word is how this repo gets hurt.

**Competence** — what a character can service, as tags with a level.
`{tag: level}`. Genre-neutral because the tags are authored: `engineering:2`,
`triage:1`, `plainchant:3`.

**Watch** — the assignment of bodies to posts over a window. The charter's
output, not an author's input.

**Charter** — the institution itself: the upkeeps it owes, the posts that
service them, the roster it believes it has, and its standing priority when
it cannot fill everything. This is the agent.

## 4. The core idea: the charter is an agent, the people are not its parts

A charter has a goal (all upkeeps in band), a means (assign competent bodies
to posts), and a constraint it does not control (the bodies are people, with
drives, injuries, grudges, and projects of their own).

Each planning window the charter:

1. reads which upkeeps are drifting and how near their band edge they are;
2. ranks posts by that urgency against its standing priority;
3. assigns the bodies it *believes* are available and competent;
4. records what it could not fill, and why.

Step 4 is the entire dramatic yield. A charter that fills every post produces
a ship that runs and a story that says nothing. A charter that cannot fill
the reactor watch because its only rated engineer is in medical produces:
a drifting upkeep, a consequence fuse with a due time, a chief with a problem,
and — when the player finally arrives — a ship with a real reason to be in
the state it is in.

**Why this and not a rota.** A scripted rota makes the crew a clock: reliable,
inert, and unable to fail interestingly. Free agent choice makes the ship die
of stupidity. The charter is the middle: institutions are exactly the thing
humans invented so that individually unreliable people produce reliable
outcomes, and modelling that directly is both more accurate and cheaper than
modelling either extreme.

**Coupling to psychology, in one direction only.** A post may *feed* a
character's project tier (`DESIGN_LONG_TERM_GOALS.md`,
`affect.apply_project_ops`) — "keep this reactor alive" is exactly the shape
of a project: durable, place-naming, not completable by one instance. The
charter proposes; the character's own psychology disposes. The charter must
never write a character's wants directly, or the crew becomes puppets and the
psychology layer is a decoration.

**Amendment (2026-08-21, prototype): feeling is the character tier's own
model, called earlier.** Two affect experiments settled how a background
body feels. A `mood` scalar built at this tier from pressure, blame and
regard measured r = 0.994 against `pressure` — a duplicate signal — and
stays out of planning (`charter_needs.mood`). `charter_feel` instead calls
`mind/psychology_runtime.resolve_hedonic`/`resolve_stress` per body per
window over channelled inputs (own needs; the state of the body's own place;
transient events there), with per-body temperament (`charter_temper`) drawn
in the card's own vocabulary — `interoception` and `stress_profile` — so a
promotion is a copy, never a translation. Measured on the twin-town famine:
r(pressure, strain) runs 0.07–0.72 by crisis phase where mood held ≥ 0.98,
and 240 bodies at identical saturated pressure carry strain 0.161–0.485.
One consequence channel only: strain wears rest
(`charter_needs.advance_needs`), never a term in the planner — the mood
lesson, kept. Deterministic project-minting for background bodies was
REFUSED: adoption is a deliberation the model owns, so the background tier
records the evidence instead (`stood`, windows actually stood per post) and
hands it to the promotion call that can deliberate honestly.

## 5. Competence is a BELIEF, not a stat

The charter must not know who is competent. It knows who it *believes* is
competent, and that belief is a facet like any other — with evidence, a
strength, and the capacity to be wrong or stale.

This is not firewall pedantry; it is where a large fraction of the good
material comes from:

- the roster is out of date, so the charter assigns someone who transferred
  out two months ago and the post silently goes unfilled;
- a competent person is *believed* incompetent because the one time anyone
  saw them work, they failed;
- someone conceals a competence, and the institution never asks them.

A charter with ground truth about its people produces a smoothly running
machine. A charter with beliefs about its people produces an institution.

The same applies to upkeep: the charter knows the last *reported* reading,
not the true one. A gauge nobody has read in six hours is a belief with a
decayed strength, which is why the disaster is a surprise to the crew and
legible in hindsight to the player.

## 6. Recompute what you can; commit only what branches

`routines.py` gets its cost profile by being a pure function of the clock: a
room's posture at time T needs no history, so a hundred quiet turns write
nothing. Upkeep cannot be purely that, because it is **path-dependent** — a
condition that went out of band and was repaired late is not recoverable from
the clock alone.

The split, and it is the load-bearing performance decision:

- **Recomputable from (clock, last known state):** an upkeep's drift while
  nothing intervened; a post's expected occupant under an unchanged watch; a
  routine's posture. Costs nothing, stores nothing, derived at contact.
- **Must be committed to `world_events`:** every *branch* — an upkeep leaving
  its band, a post going unfilled, a repair, an injury, a reassignment, a
  charter failing to fill. These are few, and they are exactly the events
  worth remembering.

So the storage grows with **incidents, not with time**. A year of a
well-run ship is a handful of rows. A bad week is a hundred.

Measured on this hardware 2026-08-21 (scratch benchmark, not in the tree): a
full per-turn sweep of 1,000 agents × 100 facets — decay, forget, propagate,
conflict-detect — is **193 ms in plain Python**, and 500,000 facets is 845 ms.
For scale, Talk of the Town reported ~60 s per turn at that second figure on
2016-era research Python, and named its own cause: string-valued facets
mutated through hand-authored per-attribute graphs. Ticking the
population is affordable; the reason to derive instead is storage and replay
clarity, not CPU. Note also that the naive SQLite spelling of the same sweep
was **18–20× slower**: hold the working set in memory and persist deltas,
and never make the tick a SQL workload.

## 7. Institutions are a fuse source, not a new delivery system

`world/living_world.py` already owns the consequence-fuse mint, its per-turn
cap, and the layer-1 semantics that keep a fired fuse from teaching anyone
anything. An upkeep crossing its band **is** a consequence fuse: a thing that
becomes true at a location at a due time, before anyone asks.

So this proposal adds a **producer**, not a pipeline. Charters mint fuses
through the existing path, inherit the existing cap, and reach the player
through the aftermath/in-progress shapes `DESIGN_LIVING_WORLD.md` already
defines. Nothing new is needed to deliver any of it.

## 8. Fidelity, as a ladder under the existing ceiling

`scene.OFFSCREEN_LIFE_LADDER` remains the only permission ladder and this
adds no second vocabulary. Charters degrade down it:

- **inert** — no charter runs. Upkeep is frozen; the world is scenery.
- **deterministic** — charters plan, upkeep drifts, fuses mint. No randomness,
  no model. *This rung alone is enough to run a ship.*
- **reactive** — charters replan when a fuse fires or a body becomes
  unavailable.
- **stochastic** — seeded variation in drift, in who shirks, in whether a
  repair holds. Reproducible from `world_events.seed`; still no model.
- **character_agent** — a specific person deliberates about their post from
  their own knowledge. Paid, rare, and reserved for people who matter.

Highest fidelity is not "every rung on for everybody." It is **uniform
existence, variable resolution**: every body has a charter position and
accumulates a real past, and the ones near an active focus are resolved
finely. Depth is not concentrated near the player — *resolution* is.

## 9. Genre is a binding, not a branch

The engine ships the five primitives. A lorebook binds them. Three bindings,
to show that nothing in the engine moved:

**Starship.** Upkeeps: `reactor_thermal` (band, drift 0.02/h, tags
`[engineering]`), `hull_integrity`, `life_support_scrub`, `watch_bridge`.
Posts: `engine_watch` at the reactor room requiring `engineering:2`,
rotating 4-hourly. Competences: `engineering`, `navigation`, `medical`.
Charter priority: life support > reactor > navigation > everything.

**Hospital night shift.** Upkeeps: `ward_observations`, `drug_cupboard_audit`,
`bed_capacity`. Posts: `charge_nurse`, `on_call_registrar`. Competences:
`triage`, `prescribing`. Priority: observations > audit.

**Monastery.** Upkeeps: `the_hours_are_sung`, `the_fire_is_kept`,
`the_copying_advances`. Posts: `cantor`, `hebdomadary`, `scriptorium_desk`.
Competences: `plainchant`, `latin`, `illumination`. Priority: the office
above all, which is the whole characterisation of the institution expressed
as one ordering.

The third one is the test of the abstraction. If a monastery and a starship
are the same five primitives with different nouns, the engine learned nothing
about spaceflight.

## 10. The starship, worked

The question was: how do we ensure they operate it properly? Concretely, over
one simulated week with the player elsewhere:

The charter holds four upkeeps and six posts. Each planning window it ranks
posts by band proximity, consults its **believed** roster, and assigns. Bodies
accept unless their own state refuses — asleep past exhaustion, in medical,
or holding a project that outranks the post.

Ordinary week: every post filled, every upkeep held in band, **zero rows
written**, because nothing branched. The ship ran and the simulation cost
nothing, which is the correct outcome for a boring week and the thing a
tick-everything design gets wrong.

Bad week: the rated engineer breaks an arm. The charter cannot fill
`engine_watch` at `engineering:2`; its priority says try `engineering:1`, and
the only such body is the cook. `reactor_thermal` drifts more slowly than it
would unattended but faster than in band, and a fuse is minted with a due
time forty hours out. It fires. Layer-1 fact: the reactor scrammed, in the
engine room, at that hour. **Nobody knows yet** — knowing is channelled.
The chief learns at the next watch handover, believes the cook is at fault
(a belief with weak evidence and a source), and tells the captain. The cook
tells someone else something different.

The player docks nine days later and finds: a scrammed reactor, a crew
divided about whose fault it was, an injured engineer, a cook who is not
speaking to the chief, and a captain's log with a version of events that the
evidence trail does not support. None of that was authored. All of it is
reconstructible, checkpointable, and true.

## 11. How we would know it works

A background simulation is testable in a way a model is not, and this is the
part that must be built with it rather than after:

- **Invariant tests over long seeded runs.** With a full, healthy, competent
  crew and no incidents injected, assert that no upkeep leaves its band across
  10,000 simulated hours. If the charter cannot run a ship under ideal
  conditions, the planner is wrong and it is a hard failure, not a feel
  problem.
- **Degradation tests.** Remove the only `engineering:2` body; assert the
  charter reports an unfillable post rather than silently succeeding, and that
  exactly one fuse mints for the drift.
- **Determinism tests.** Same seed, same inputs, byte-identical
  `world_events`. This is what makes checkpoint restore and branch honest, and
  it is why the `stochastic` rung must be seeded rather than random.
- **Cost tests.** A quiet week writes zero rows. Pin it; it is the whole cost
  model and it will rot silently.

## 12. What stays with the model

Nothing in sections 3–11 calls one. The model's jobs are unchanged and both
sit at the aperture:

- **Interpretation at contact** — what this state *means* when someone
  perceives it, which is the Director staging and the narrator rendering.
- **Promotion** — when a background body becomes someone the player talks to,
  its accumulated past is handed to a character call that now has a real
  history to think from.

The line: a charter can produce facts, causality and consequence. It cannot
produce meaning. It can strand a cook on the reactor watch and scram the
core; it cannot decide that this is the beat where the chief realises he has
been protecting the wrong person.

## 13. Rejected shapes, and why

- **A genre module** (`starship.py`). Every other story pays for it. Refused
  by the §1 invariant.
- **A scripted rota.** Cannot fail interestingly; makes the crew a clock.
- **Free agent choice with no institution.** The ship dies of stupidity and
  the player reads it as a bug, correctly.
- **Ticking every body every turn.** Affordable (§6) but it writes rows for
  nothing happening, and storage growing with *time* rather than *incident*
  is the thing that makes a long story expensive.
- **A charter with ground truth about its crew.** Produces a machine, not an
  institution, and quietly breaks the firewall.
- **Culling facts nothing can reach.** Explicitly refused: channels open later
  — a body gets promoted, a room becomes enterable, a record is found — and
  a fact with no channel today may have one in fifty beats. Deciding
  reachability in advance makes the world observer-relative, which is the
  collapse this engine exists to prevent.

## 14. Open questions

1. **Does the charter's belief about its own roster live in `mind_models`**
   (`DESIGN_OFFSCREEN_MIND_MODELS.md`, built) or in its own ledger? An
   institution is not a mind, but it holds beliefs with evidence and decay,
   which is exactly that machinery. Reusing it is attractive and may be a
   category error.
2. **How is a charter authored?** Lorebook entry, a new card kind, or derived
   from a place? This decides whether it is usable, and it is the surface
   most likely to fail silently — the psychology lesson applies in full, so
   whatever it is wants `character_card_warnings`-style validation from day
   one, not afterwards.
3. **What is the planning window?** Fixed hours, or event-driven replanning
   only? Event-driven is cheaper and more accurate; fixed is easier to test.
4. **Do charters nest?** A ship's charter and a department's. Probably, but
   nesting is where priority ordering stops being one list.
5. **Blocked first, and this is not optional:** `UNBUILT` §2.8's open bullet.
   The stored `offscreen_log` is mixed across four legacy shapes with nothing
   migrating what is already written, and its own entry calls it "a trap for
   the first thing that computes over the history." A charter reading its own
   past is precisely that first thing.
