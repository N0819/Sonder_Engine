# DESIGN_INSTITUTIONS_AND_UPKEEP — how a simulated crew actually runs the ship

Status: **Deterministic vertical slice built; realism extensions remain.**
Written 2026-08-21 against alpha 9.7.1. The pure simulator lives in
`world/charter_*`; `world/charter_runtime.py` supplies explicit authoring
storage, frame-scoped epoch catch-up, guarded atomic landing, stable consequence
minting, destination residue, and per-presence context. Extends
[`DESIGN_LIVING_WORLD.md`](DESIGN_LIVING_WORLD.md) and
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

## 12a. The seam: there is no handoff, only a change of author

A background body that walks on screen, gets voiced by the scene manager, and
walks off again must not have a hole in its life where the model held it. The
obvious design — hand control to the model, take it back, reconcile — is the
wrong one, and the reason is that it invents a boundary the system does not
need.

> **The body never leaves the simulation.** Its needs keep draining, its
> feeling keeps resolving, its position keeps being its position. What changes
> for a stretch is only WHO WRITES ITS CONDUCT. There is nothing to bring
> back, because nothing went anywhere.

Versu reached the same arrangement and states it in one line: *"The same
architecture is used for player choice — except the Action Instances are sent
directly to the user-interface, rather than to the Decision Maker."* One
affordance set; either the utility selector picks from it or something else
does; the machinery underneath cannot tell which, and must not be able to.

*Landed 2026-09-03: the FIGURE half of the seam grew the dealings a player
actually attempts -- order, request, bargain, promise, trade, give -- each
answered from the body's own ledgers (commitments, economy, marks) rather
than by the voice alone; `charter_author.FIGURE_ACTS`, `tests/test_figure_acts.py`.*

**What it requires.**

1. **Affordances are the shared vocabulary of conduct.** `charter_practice`
   currently computes utilities and calls the winner. The effects must be
   callable from outside as well, so an AUTHORED act lands through the
   identical path a chosen one would — not a parallel "apply the model's
   result" function, which is how the two paths drift.
2. **The voiced body keeps ticking.** Being on screen does not suspend hunger.
   Needs, feeling and decay advance as normal; only the conduct slot is
   authored.
3. **Commit is the reduction point**, exactly as it already is everywhere
   else: model output is provisional until deterministic commit code
   validates it, and what survives becomes acts and `world_events` rows on
   the same path the simulation's own acts take.
4. **The gate is already the author-switch.** `commit_background.pick_background_reactor`
   is deterministic, model-free, and already decides who speaks this beat. It
   does not need to become a mode flag; it IS one.

**One ledger, many producers.** The charter must not own a private event list
that gets translated into engine events — a mapping table between two
vocabularies is a visible seam that drifts, and it duplicates work already
done. `story/carriers.py` reads `world_events` directly
(`SELECT * FROM world_events WHERE chat_id=? AND frame_id IS ?`), so a
charter that MINTS `world_events` rows is witnessed, carried, gossiped and
told by machinery that already exists and never learns the charter is there.
The engine solved this once already: the Director, its six specialists and the
player's own declaration all emit the same `state_diff`, and commit applies it
uniformly.

**Non-determinism is not the problem it looks like.** Player and major-
character conduct is an INPUT, not derived state. The engine already replays
model output from `steps`/`variants` rows — that is what rerun-from-stage is.
So charter state is `f(recorded events, seed)`, and a free agent writing
events threatens replay no more than a player typing does.

**Two failure modes, both with existing answers.**

- *The model invents what the simulation cannot express* — a brother the
  ledger has never heard of. `world/background_claims.py` is the answer
  already built for this: commit invention as CLAIMS, not facts. The brother
  attaches to that presence as a claim, survives to the next time it is
  voiced (which is most of what "seamless" means in practice), and can later
  be ratified or contradicted.
- *The model contradicts what the body actually did* — says it has been on the
  road all week when the ledger has it standing a watch. This is the wardrobe
  problem in another costume, and takes the same answer: an assertion outside
  what the state licenses is dropped with a notice, and `charter_log.scene_ledger`'s
  `can_bring_up` IS the licence. That field is capped and salience-ranked for
  the same reason the attire gate exists — a payload large enough to restate
  gets restated.

**The asymmetry that should stay.** A charter body's witnessing is coarse:
place plus a public surface. A character's is `agents/perception.py`, a
stricter instrument with a firewall to defend. Those are different questions
at different resolutions, not one question done twice, and collapsing them
would cost either fidelity or a great deal of money. The seam to watch is
PROMOTION, where a body crosses from the coarse instrument to the strict one:
if it arrived holding a claim it could not legitimately have perceived under
`perception`'s rules, promotion is where that leaks into a real mind. That is
the first test to write when this wires up.

**Amendment (2026-08-21, prototype): built, and wrong in one claim.** The
author-switch exists: `charter_practice` names every affordance, `offers`
hands the action instances outward (Versu's line, verbatim), `enact`'s
`conduct` and `charter_author.authored` land an authored act through the
IDENTICAL builders — pinned by a test in which a run re-authored with its own
chosen conduct is equal, charter and events both, to the run that chose. An
act outside the licence is refused with a reason and changes nothing. Figures
(`charter_figure`) make the player and major characters claim SUBJECTS —
seen, told about, decaying, wrong — never rostered, never blamed, and never
holding a mind here; a figure's own acts (`greet`/`ask`/`tell`/`accuse`/
`tend`) touch only what a body could receive, with tellings arriving through
`charter_mind.hear_claim`, the one uptake door. Promotion
(`charter_promote`) converts the query-over-ledger past into
`prepare_memory`-vocabulary rows under one selection rule — it changed a
tracked ledger, the routine survives only as its aggregate — and the
firewall tests came first: unheard blame does not cross, the register does
not cross, register-fact events do not cross.

**Amendment (2026-08-21, public scene evidence): built.** The missing reverse
bridge now turns player and major-character conduct into claims a Charter body
can actually own. The social specialist receives an engine-authored list of
exact speech/action sources once per resolved beat and may add only speech-act
direction plus verbatim spans from the quote. Deterministic grounding restores
the source's actor, target, quote/action surface, volume and concealment; a
failed annotation therefore loses nuance but never the factual source. Commit
then asks the ordinary sight/hearing primitives separately for every unbound
Charter body and inserts the claim only in witnesses. Exact quotes and full
frames remain firsthand; `hear_claim` strips them on retelling while retaining
coarse request/offer/etc. direction. The claim is ordinary news, so the
existing gossip, reporting-line, carrier, Scene Life and promotion paths need
no parallel history and gain no broadcast shortcut.

Where §12a was WRONG: point 4. `pick_background_reactor` decides who
SPEAKS, not who ACTS; the gate alone was never an author-switch. The production
seam now supplies exact `action_instances` beside the one-body view and accepts
only an exact typed `charter_act` echo. Commit rechecks that allowlist and calls
`charter_author.authored`, so the on-screen act uses the same builders and
effects as simulated conduct. The model's prose has no mutation authority.

The background lifecycle is now continuous. Unbound bodies derive into
background-presence records with stable `{charter,body}` references and exact
temperament; no duplicate identity is stored merely because the player entered
the room. Scene life may author the body while it is encountered, and leaving
requires no reverse conversion because Charter owned its state throughout.
Promotion alone changes ownership: `charter_promote.promotion_handoff` copies
felt state, vitals vocabulary, temperament, selected channelled memories and
aggregate service evidence into the card/memory/active-state stores. Charter
then removes its coarse interior and retains only a scene-position-synchronised
institutional projection. It may roster that person or record their absence;
it may never again move, tire, feel, converse or choose for them.

And the layer §12a assumed was working was not. Its premise — "a charter
that MINTS `world_events` rows is witnessed and gossiped by machinery that
exists" — held for witnessing and failed for gossip, four separate ways,
every one invisible until a test called the consumer: a retold news claim
was rebuilt in body-claim shape and arrived unable to be articulated; `ask`
chose its subject by enumerating the other head's holdings (634 of 2,413
asks named a subject the asker did not hold); affordances kept firing for
up to two hours after a pair parted, including a first-hand GREET across
rooms; and `report_up` promoted every claim kind into the register, so
witnessed events joined the institution's books as pseudo-people named
`news:…`. With those fixed the channel still measured dead — 244
witnessable events in a famine month, ZERO spread second-hand — for two
structural reasons: nobody off the watch ever left their room (no
circulation, no rumour; `charter_move.errands` is the fix, and the
`(origin, place)` path cache persisting across a run is what makes it
cost lookups), and the tell slot always went to the freshest co-presence
claim

AND THE CIRCULATION HAD NOWHERE TO SEND ANYONE, which took a live run to
see. `charter_space.charter_places` is every place with a post or an upkeep
at it — where the institution's WORK is — and `errands` routed off-duty
bodies only there, so a room whose purpose is BEING IN it (a lounge, a
chapel, a park, a market square) was somewhere the population could never
go however social it was. Measured on chat 98: 7 work places against 45
rooms, and the run's author had to invent an upkeep nobody serves — a
condition the institution now owes forever and will report as failing —
purely to say that people sit somewhere. `commons` on the charter is the
predicate that was missing, `charter_space.commons_places` reads it beside
the market places `economy` already carried, and `frequented_places` is the
union circulation walks. A berth is deliberately not in it: it is somebody's
own place rather than a place people go, `homecomings` already routes there
without needing reach, and the set of distinct berths grows with the
population, so folding it in would multiply `reach_map`'s bodies x places
walk by the population itself.

The same run exposed a second thing in the same function: the nearest-place
fallback took `min((rooms, place))`, so where two candidates were the same
distance the ROOM ID decided — and on a hub-and-spoke graph, which is what a
hull or a settlement round a square actually is, every distance ties. Every
errand at seeds 3, 4 and 5 went to `arboretum`, the alphabetically first
workroom. A population that all walks to one room has not circulated, so the
tie is now broken by the same deterministic mixer the selection uses, folded
with the place: replay under a seed is identical, adjacent seeds decorrelate,
and a genuinely nearer room still wins.
 (`charter_talk.tellable` now prefers the remarkable — a happening, a
stranger — over the standing description of your own people). After: the
mill failure reached 107 heads, 101 of them second-hand; a traveller
present 16 hours became known to 96 of 240 heads, 74 second-hand, peaked
AFTER departure, went stale in every head the moment it moved, and was
forgotten everywhere within four days. That last number is the recognition
horizon, and `PERSONAL_DECAY_PER_HOUR` is its dial.

Two rates were caught lying on the way and are worth naming as a class.
`crc32(key|seed)` is linear over GF(2), so adjacent seeds XOR every
same-length key by one constant — the errand "rotation" selected the same
bodies at seed 7 and seed 8, and any threshold selection on that idiom
does the same (tie-BREAKS are safe; membership tests are not —
`charter_move._roll` now finalizes multiplicatively). And a missed ask
counted as an effect kept every conversation warm forever: the town
measured 0.9 acts per body per hour against the 0.147 the layer was tuned
at, so a dead question is silence again and situations can end. Cost,
honestly: circulation takes the 500-hand month from 8.0s to 16.7s — 459
of 500 bodies now move and every head runs at its claim cap — with the
30s guard holding and no single term over a quarter of the profile.

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
2. **What should the guided Charter authoring surface be?** The first vertical
   slice has a structured `/api/chats/{cid}/charters` endpoint with immediate
   validation warnings. It still needs a usable card/form, templates, and a
   decision about whether lore or place definitions may seed one. The
   psychology lesson applies in full: validation belongs in that surface from
   day one, not afterwards.
3. **What is the planning window?** Fixed hours, or event-driven replanning
   only? Event-driven is cheaper and more accurate; fixed is easier to test.
4. **Do charters nest?** A ship's charter and a department's. Probably, but
   nesting is where priority ordering stops being one list.
5. **Before any legacy-history import:** `UNBUILT` §2.8's open bullet. The
   stored `offscreen_log` is mixed across four legacy shapes. The built runtime
   avoids it entirely by owning typed current state and using the objective
   event spine. Any attempt to reconstruct a Charter from older off-screen
   prose must migrate that history first.
