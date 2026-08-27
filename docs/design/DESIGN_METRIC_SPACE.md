# Metric space, extended bodies, and instruments

Status: ARGUMENT. Nothing here is built. Written 2026-08-26 from a design
conversation while standing up a starship story, because the shape of the ask
turned out to be mostly reuse and the reuse is not obvious.

The ask arrived as starships — several vehicles at real distances, navigation,
weapons fire that can miss and hit something else, ships with sections rather
than points, crew who read instruments. **That is a goal in its own right**, and
the sections below are written to serve it.

It is not ONLY that, and the difference decides whether the mechanism is built
generally or console-shaped. Every mechanism here is answered equally by a
boulder rolling down a hill, and the boulder earns its place in this document as
the TEST rather than the replacement — it is how you check that a decision made
for a bridge did not quietly require one:

    a boulder comes loose             a change of motion, adjudicated once
    gravity keeps acting on it        a STANDING force, nobody declares it
    it rolls                          stored velocity, propagated (§ 10)
    somebody sees it coming           ordinary perception, no instrument
    somebody shouts                   speech, and that is the scene (§ 7)
    it arrives in four seconds        time-to-contact, which is the drama

A starship bridge is the same six lines with an instrument between the third and
the fourth. Both are wanted. The rule the pairing enforces: if a decision here
only makes sense WITH a console in it, it has been written for the instance and
not the class — and the starship gets a better engine out of the check than it
would have got on its own.

---

## 1. The thesis: two regimes, meeting at the vehicle

Do NOT unify the spatial model. Interiors are TOPOLOGICAL — the question is
"can I walk there, and what is between us" — and rooms-with-adjacency is
genuinely the right shape for it. Open space is METRIC — position, range,
bearing, closing rate. Forcing either into the other makes both worse, and the
engine already does the topological half well.

They meet at the vehicle, and the machinery exists: `room_registry` carries
`parent_entity`, so a room can BELONG to an entity. A vehicle is therefore an
entity with a position in the metric space whose interior is rooms — the same
shape as the bodies-as-places work, at a different scale. Several vehicles in a
space is several entities with positions, each with an interior.

## 2. The number is already parsed, and then destroyed

`world/spatial_routing._DISTANCE_UNIT_METERS` already reads `km`, `m`, `miles`,
`feet`, `paces` into metres. `normalize_edge_distance` then collapses the result
onto one of four `DISTANCE_TIERS` and DISCARDS THE VALUE.

So the engine can already read "42,000 km" and deliberately forgets it. That is
the seam, and starting there is additive rather than disruptive: keep the tier
for every existing reader — sight and sound gates keep working untouched — and
carry the metres alongside for anything that wants to compute. Nothing has to be
rewritten for the first step; a number simply stops being thrown away at the
door.

Measured, read-only over the corpus 2026-08-26: live edge distances are `near`
242, `close` 69, `immediate` 54, `adjacent` 32 — and ZERO `far`, ZERO `remote`.
Live barriers are `open`, `closed_door`, `open_door`, `wall`, `one_way_window`,
`membrane` — no `window`. The ranged half of the existing model is BUILT AND
UNEXERCISED, which is a different risk from missing: the code paths exist, carry
tests, and have never met a story. Expect the first one to find things.

## 3. A ship is a body with regions, and the region set must stop being global

`story/attire.REGIONS` is a hardcoded 8-tuple of human anatomy — head, torso,
arms, hands, waist, groin, legs, feet — and scene entities carry no regions at
all today.

The shape wanted for ship sections already exists and is nailed to one species.
A body has named regions; each carries coverage, state and exposure;
`body_region` is already one of the sixteen `PERCEPT_KINDS`; `exposed_regions`
already derives what is uncovered. A saucer, a stardrive, two nacelles, a bridge
and an engineering hull are the same object: regions with their own state, some
covered, some exposed, each separately hittable.

**So the change is that the region set becomes a property of the body**,
defaulting to the human tuple. That is the brief's own "categories to file into,
not vocabulary tables" applied to anatomy, and it buys ship sections,
non-humanoid characters and vehicles in one move.

Shields need nothing new either: a shield over the saucer is a covering over a
region, and the coverage machinery already derives what is exposed when it
drops.

## 4. Geometry is a DETERMINISTIC backend, for the reason perception is

`agents/perception.py` has no model role in `providers.ROLES` and imports no
model seam at all. CLAUDE.md states why: the deterministic floor must not depend
on a model cooperating.

Geometry gets the same treatment, for the same reason — **the Director cannot
argue with it.** It cannot decide the shot did not cross the freighter, because
the line did. A ballistics layer a model can talk out of its verdict is not a
floor, it is a suggestion.

The ownership line that falls out:

  * GEOMETRY owns: what the line crossed, at what range, with what energy, into
    which region. Pure, total, no I/O, no model.
  * THE DIRECTOR owns: whether the shot was taken, what it was aimed at, what it
    MEANS, and what happens next.

Geometry proposes; the Director disposes. Same as everywhere else in the engine.

## 5. The miss needs no new mechanism

Characters never decide their own success — they declare, and the Director
resolves. A phaser shot is a declaration exactly as a punch is, and whether it
lands is already somebody else's call.

So "weapons should be able to miss" requires nothing. What is genuinely missing
is the geometry to answer WHAT ELSE THE LINE CROSSES, because a miss has to go
somewhere and nothing today can say what was behind the target.

## 6. The trig, minimally

  * range, bearing, closing rate — bearing math already lives in
    `world/spatial_orientation.py`
  * ray against volume, for what a line meets and in which region
  * CONES, for sensor arcs and firing arcs

Cones are worth building for a reason beyond this document: the brief's aperture
item (`look around` widening what perception returns) is BLOCKED on "there is no
cone", and sensor coverage wants the same math. Three consumers, one primitive.

## 7. THE ARCHITECTURAL MOVE: do not render a battle, render a bridge

The most important line here.

**The narrator must never receive geometry.** It receives what the crew
EXPERIENCE, which is three things the engine already renders well:

  * the tactical picture as an INSTRUMENT READOUT — mediated, fallible, and
    possibly wrong;
  * the ship's own body — the deck heaving, lights failing, a console blowing
    out. That is `sensation`, already built;
  * PEOPLE SAYING THINGS. A damage report is `speech`, and it is the best of the
    three, because it is a character telling you something you cannot see.

The simulation stays deterministic and cheap; the prose stays what this engine
is already good at.

This is also the guard against the failure that would kill the idea outright:
becoming a WARGAME THE STORY HAS TO NARRATE. State it as a constraint rather
than an intention — the sim emits percepts and consequences, never prose, and
the Director remains the author of what matters.

## 8. Instruments are percepts, and the firewall is the point

A crew member does not perceive the tactical situation. They perceive a CONSOLE.
The chain:

    objective    contact at 42,000 km, bearing 210 mark 15, closing 400 m/s
    console      renders that into a readout
    delivery     the readout arrives as a percept, with its own fidelity
    the mind     reads the readout, never the world

A damaged sensor DEGRADES it. A spoofed one LIES. An officer looking elsewhere
misses it entirely. That is the firewall generating drama rather than
restricting it, which is the stated reason the gap is kept — and it makes a
wrong tactical picture a first-class story object instead of a bug. A tactical
officer who reads a sensor ghost and recommends arming weapons is exactly the
scene the firewall exists to make possible.

Concretely: `PERCEPT_KINDS` is a closed set of sixteen. An instrument readout is
the seventeenth, and the composer's existing fidelity machinery does the rest.

## 8a. THE STATION IS THE CHANNEL, and it already exists

Bearing and range are not broadcast to everyone aboard. They arrive AT A POST,
and whoever is standing at that post reads them. That single decision makes
instrument delivery firewall-shaped by construction rather than by a guard
bolted on afterwards.

The channel exists: `scene.stations` maps a subject to `{at, near}`, and `at` is
what a body is stationed at. Measured read-only over the corpus 2026-08-26 —
112 station rows, `at` SET on 58 of them (52%), and the values are already
exactly the right kind of thing: `chair`, `desk`, `console`, `bed`,
`irori_hearth`, `gravel_garden`. A duty station is a station with instruments
attached; the engine has been tracking "this person is at that thing" all along.

So the delivery chain is:

    geometry     produces objective facts about the space
    the station  renders the slice IT is instrumented for
    stations.at  decides who receives that slice
    the mind     reads its own console, and nobody else's

Which gives, for free and without a single new rule:

  * TACTICAL gets bearing, range, closing rate, weapons state. CONN gets heading
    and velocity. SCIENCE gets composition and scan returns. OPS gets power and
    systems. They are DIFFERENT SLICES of one objective picture, and no station
    receives another's.
  * Someone in Ten Forward receives NONE of it, and is dependent on being told.
  * LEAVING YOUR POST CUTS YOU OFF. A body that stops being `at` the console
    stops receiving what the console shows, which is correct and which no
    special case has to implement.
  * An officer can therefore be WRONG about the tactical picture in a way that
    is legible — they were not at a station, or their station shows the degraded
    return, or they left before the update.

This is also the honest answer to "how does the captain know". He does not, by
sensor; he knows because an officer at a post TOLD him. Which is the `speech`
percept doing the work, and it is why bridge scenes are written as conversations
rather than as readouts in the first place.

One defect to fold in while here: the corpus already holds a raw id
(`b6bcffc15f864d2b`) sitting in an `at` value where a station name belongs — the
same id-leaking-into-a-name-field class as the background-presence ledger's
`a23653c914bf40a8`. Whatever fixes one should be pointed at the other.

## 8b. EXTENSIONS DEFINE WHAT A SYSTEM DOES; the engine defines what happened

There is no universal answer to what a phaser does to a nacelle, and the engine
should not pretend to have one. A submarine's sonar, a sailing ship's rigging, a
scrying pool and a starship's shields are all the same SHAPE — a system with
state, a way of failing, and a readout somebody stands at — and nothing else
about them is shared. Hard-coding one setting's semantics is the vocabulary-table
mistake at a larger scale.

The extension surface is already strong enough to carry this, which was not
obvious: `agents/runtime.register_step` plus `_extension_splices` let an
extension add a PIPELINE STAGE and place it; `director_scopes.
_extension_specialist_call` lets one add a DIRECTOR SPECIALIST with its own
scoped channels; and `_extension_character_payload`, `_extension_director_payload`
and `_extension_narration_payload` let one add to what each role receives.
An extension can already be a participant rather than a decoration.

### The line, and it is the same line as everywhere else

    THE ENGINE OWNS   where things are, what a line crossed, at what range,
                      into which region, and WHO PERCEIVED IT.
                      Deterministic, un-arguable, universal.

    AN EXTENSION OWNS what that MEANS in this setting: what absorbs, what
                      breaks, what a system does when it fails, what a console
                      displays and in what units.

Geometry is un-arguable for the reason § 4 gives, and perception is un-arguable
because it is the firewall. Everything BETWEEN those two — the damage model, the
failure modes, the instrument's vocabulary — is setting-specific and belongs to
whoever is writing the setting.

### The guard that makes this safe

An extension-defined readout MUST be composed from what the engine already
delivered to that station, and must not be able to reach past it. Otherwise a
system definition becomes an information-expansion hole: a console that "shows"
a cloaked ship because the extension's damage model happened to know about it.

So the contract is subtractive in the same direction as everything else. The
engine hands a station its slice; the extension decides how to RENDER that slice
and what it means; it cannot ask for a slice the station was not given. An
extension may make a readout WORSE — noisier, stale, wrong — and that is a
feature. It may not make one better-informed than the sensor.

This also keeps the failure mode of a broken extension bounded, matching what
`_extension_splices` already guarantees for the plan: any failure at all leaves
the engine's own behaviour exactly as it was, so a bad system definition costs a
readout rather than a turn.

### What an author actually writes

A system definition, declaratively where possible:

  * the system's regions and what they cover (§ 3 — a per-body region set);
  * its state, as vitals-shaped values with thresholds (§ 9);
  * what an incoming effect of a given category and magnitude does to it;
  * what its readout shows, to which station, in what units;
  * how it degrades — because a system that only works or is destroyed is a
    switch, and the interesting states are all in between.

The engine supplies the CATEGORY of what happened — a ranged energy transfer of
magnitude M into region R at range D — and the extension supplies the rest. That
is "categories to file into, not vocabulary tables" applied to physics.

## 8c. A WARP CORE IS AN UPKEEP, and that model is already written

The strongest reuse in this document, and the least obvious.

An author wanting a warp core that runs on managed resources — something with a
level, something that falls if nobody tends it, somebody posted to tend it, and a
crew that has to act — is describing the CHARTER's own model exactly:

    upkeeps   a value with an OPERATING FLOOR, a fail rate and a restore rate.
              `world/charter_generate.FAIL_HOURS` (days 72h, a_week 168h,
              weeks 336h, a_season 720h) against `RESTORE_HOURS` (hours 6h,
              a_shift 12h, days 72h), and `_rate()` turning a span into a
              per-hour slope. Falls untended, climbs when worked.
    posts     the assignment: which job tends which upkeep, at which place.
    bodies    the people who hold the posts.

`charter_runtime` already emits `upkeep_out_of_band` ("X fell below its
operating floor") and `upkeep_restored` ("X returned to its operating band") as
events. That is a deuterium reserve, an antimatter containment, a plasma
manifold — a value with a floor, decaying over a week, restored over a shift by
whoever is posted to it, announcing itself when it crosses.

An engineering department is an institution. It was built for villages and it
does not care.

### Which makes J1 a dependency, not a neighbour

Every charter that ships is EMPTY — five for five, `posts=0 bodies=0
upkeeps=0`. That defect was registered as a background-population problem. It is
not only that. **It is the resource-and-labour model this section depends on,
shipping inert in every story ever run**, which is also why nothing has ever
noticed: an upkeep that does not exist cannot fall below a floor, and the epoch
that would tick it has fired zero times.

So the ordering is forced. Player-commanded system management is not buildable
on an institution that cannot hold a member or a task.

### Player command is an action against a post

"The crew manages and collects through player command" resolves cleanly:

  * the player ORDERS — a declaration like any other, addressed to a character;
  * the character DECIDES whether and how, from its own psychology, exactly as
    with any other order (a Klingon security chief and a nervous engineer answer
    the same order differently, which is the point);
  * the Director ADJUDICATES it into work against a post;
  * the upkeep MOVES at its restore rate, over the hours that work takes;
  * the crossing announces itself when it crosses.

None of that is new machinery. The one new thing is that a station's readout
(§ 8a) shows the upkeep's level — so the player learns the antimatter is low
because someone at engineering says so, not because the engine told them.

### What the extension supplies, and what it must not

The extension defines the SYSTEM: the regions it occupies, its resources and
their floors, what work restores them, what it does when it falls, what its
readout shows and in what units. The engine supplies decay, assignment, the
clock, and delivery.

The extension must NOT define who knows the level. That is § 8a and § 8b: the
station receives the slice, and an extension may render it worse but never
better-informed. A warp core that tells the whole ship it is failing has skipped
the officer whose job it was to say so, and that officer was the scene.

## 8d. A SHIP IS A HIERARCHY OF INSTITUTIONS — and mostly one institution, deep

The Charter already carries hierarchy, in two dimensions, and neither is
obvious from the outside:

    posts     carry `reports_to` and `authority`. `charter_runtime` VALIDATES
              the chain: a superior must be a real post, and a post may not
              report to itself. That is a command tree, already enforced.
    upkeeps   carry `requires` and `depends_on`. That is a dependency graph
              between resources: a warp core requires plasma flow requires
              deuterium, and a floor crossed at the bottom propagates.

So the first answer is that a starship is mostly ONE institution with a DEEP
POST TREE, not many institutions stacked. Engineering is not a separate
organisation from the ship — it is a subtree under the chief engineer, who
reports to the first officer, who reports to the captain. `reports_to` is
already exactly that, and modelling each department as its own charter would
duplicate the tree the posts already describe.

### Where a SECOND charter genuinely belongs

When loyalties differ, not when departments do. Aboard one hull:

  * the ship's own crew;
  * a visiting diplomatic delegation with its own chain and its own aims;
  * a civilian science team, funded elsewhere, reporting elsewhere;
  * prisoners in the brig, who are an institution's SUBJECTS rather than its
    members.

Those are separate charters because they answer to different authorities and
want different things — and `cross_charter_gossip` is then precisely right: "a
Charter is an ownership boundary, not a soundproof wall", one representative per
institution per occupied place, trading a claim each. Two delegations in Ten
Forward is the case that function was written for, and nobody has ever run it.

The test for whether something is a department or an institution: **does it have
its own aims that can conflict with the ship's?** Engineering cannot. A
delegation can.

### `authority` is what makes player command work

An order is not a request, and the difference is a field that already exists. A
post's `authority` is what distinguishes:

  * the captain ordering the warp core taken offline — obeyed, and the argument
    happens afterwards if at all;
  * a science officer ASKING engineering for the same thing — a favour,
    negotiated, possibly refused;
  * a lieutenant ordering the captain — refused, and the refusal is the scene.

The character still decides, from psychology, exactly as with any declaration.
Authority does not compel; it changes what refusing COSTS, which is the correct
model of a chain of command and the reason a Klingon security chief accepts a
refusal without resentment while still having recommended the aggressive option.

### The consequence for J1

If the hierarchy is where a ship's structure lives, then an empty charter is not
missing decoration — it is missing the ENTIRE COMMAND STRUCTURE. No posts means
no `reports_to`, which means no chain, which means no authority, which means
every order is a request and every crew member is a peer. That is a description
of what these stories have actually been doing.

## 9. Ship state is probably vitals plus conditions

Hull, shields, power and life support look like `vitals`, which are name-keyed
in the scene rather than restricted to bodies. A hull breach venting atmosphere
is a `condition` with a tick interval, and `world/mechanics.py` already runs
those on a cadence; `world/survival.py` already reads `parent_entity` for
atmosphere.

So ship state may need almost no new machinery — mostly a decision that a
vehicle is a legitimate subject for the mechanisms that exist.

## 10. Risks and open questions

**TURN SCALE.** A battle happens in seconds; the unclaimed-beat floor is ten
(`world/mechanics.UNCLAIMED_BEAT_SECONDS`). Probably right — a beat IS one
tactical exchange — but it means declared durations matter more here than
anywhere, which ties this to the fiction-time work rather than leaving it
independent.

**DECIDED 2026-08-26, by the engine's owner:**

  1. **THE NARRATOR RENDERS PLAYER PERSPECTIVE, NOT TRUTH.** Settled, and it is
     the strong version. Nobody sees the objective picture, the narrator
     included. If the sensors are wrong the prose is wrong, and the player finds
     out when the torpedo arrives. The alternative leaks omniscience into
     narration and silently suspends the firewall for anything at range, which
     is exactly where the firewall was going to earn its keep.

  2. **VELOCITY IS DECLARED; PROPAGATION IS DERIVED.** Position is neither fully
     continuous nor fully declared, and the split is on WHO SETS MOTION rather
     than on who computes it.

     The Director declares a velocity -- "closing at 400 m/s" -- as an ordinary
     adjudicated statement it owns and can change. Geometry then propagates it
     deterministically for as long as it stands, with no further Director
     involvement.

     Both halves of the ask:
       * NOBODY TRACKS POSITIONS. The Director never says "now they are at
         41,600 km"; that is derived. This was the stated advantage of going
         continuous, and it survives.
       * NOTHING MOVES THAT NOBODY SET MOVING. No drift through a conversation
         the scene wanted to hold.

     Three troubles avoided, and the third is why the shape matters:
       * a fully continuous world moves when the story wanted to hold;
       * a physics tick that moves things is a SECOND AUTHOR over objective
         causality, and this engine is single-ownership-per-domain throughout;
       * advancing position by velocity x elapsed recomputes from a MOVING
         DENOMINATOR, so rerolling a beat with a different duration moves
         everything -- the identical coupling that made the memory backfill
         wrong (see UNBUILT 1.85). A STORED velocity rolls back with its beat;
         a recomputed position does not.

     CORRECTED SAME DAY, by the owner, and the correction improves it: an
     object in motion stays in motion. The first draft of this decision called
     zero velocity the natural resting state and motion the thing requiring
     declaration. That is backwards. VELOCITY IS JUST STATE AND ZERO IS NOT
     SPECIAL -- a hull "at rest" relative to a star has velocity zero IN THAT
     FRAME, which is itself an achievement somebody is actively working at.

     So the rule is that the Director declares CHANGES to motion -- force, not
     velocity. Absent a force, stored state persists, which is what a stored
     value does anyway; the propagation half was already right and only its
     default was described wrongly.

     AND STATION-KEEPING IS AN UPKEEP (§ 8c). Holding position is continuous
     work against something, held by a post, with an operating floor. Lose the
     ability to do that work and nothing stops -- the hull keeps whatever
     velocity it had. "Hold position" is still a real order; it is an order to
     SPEND EFFORT, not a request for the universe's default.

     THE PAYOFF, and it is the best argument in this document for building any
     of it. A damaged ship drifting toward something is a threat NOBODY
     AUTHORED, assembled entirely from parts that already exist:

         propulsion takes damage       a condition on a region (§ 3, § 9)
         station-keeping upkeep falls  nobody can do the work (§ 8c)
         velocity is no longer zeroed  stored state simply persists
         geometry propagates it        deterministic, un-arguable (§ 4)
         the conn console shows it     an instrument percept at a station (§ 8a)
         an officer says it aloud      speech, and THAT is the scene (§ 7)

     Weapons need an author to point them. DRIFT GENERATES STAKES ON ITS OWN,
     and legible ones: the numbers say four minutes, so the tension is real
     rather than asserted. It also happens to be the case this engine is best
     at, because the interesting part is not the physics -- it is five people
     on a bridge disagreeing about what to do with four minutes.

  2a. **SOME FORCES ARE STANDING, and belong to the PLACE.** The boulder makes
     this visible where the starship hides it. Gravity is not declared per beat
     by anyone; it is a property of being on a slope, and it acts whether or not
     the Director mentions it. So the model is not only "stored velocity
     persists" — a place may carry forces that continuously modify motion within
     it, and those are authored ONCE as part of what the place IS, not as an act.

     Current, drift, wind, a decaying orbit, a slope. Each is the same shape: a
     standing property of a region that changes velocity over time, and which no
     character can order away — only work against, which is § 8c's upkeep again.

  2b. **AN INSTRUMENT IS ONE DELIVERY PATH, NOT THE PATH.** § 8a is right about
     a bridge and would be wrong as a general rule. On a hillside nobody reads a
     console: they SEE the boulder and they HEAR it, through ordinary perception
     with ordinary gates — sight lines, light, distance, noise. The geometry
     produces the same facts either way; what differs is the channel that
     carries them, and instrumentation is simply the channel available when the
     thing is too far to see.

     This matters for what gets built: the metric facts must be deliverable
     through the EXISTING percept channels first, with the instrument kind as an
     addition for range. Building instruments first would make a console the
     price of entry for physical causality.

  2c. **TIME-TO-CONTACT IS THE DRAMATIC UNIT, at both scales.** Four minutes on
     a bridge, four seconds on a hillside — the same geometry output, and in
     both cases it is what the scene is actually about. That makes it the first
     thing the layer should compute and the first thing it should deliver, and
     it ties this work to declared durations rather than leaving it independent.

**STILL OPEN, and deferred deliberately:**

  3. Do metric spaces NEST -- system, then orbit, then surface? This is where
     the design gets expensive, and it wants deeper thought than a passing
     answer. Do not design for nesting speculatively; find out whether a story
     needs it first.
