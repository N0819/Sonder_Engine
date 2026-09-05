# Design: Charter supersedes off-screen life, and bubbles replace the ladder

**Status: RULING, 2026-09-05, not yet migrated.** The owner: "can we just
agree that offscreen life is entirely superseded by charter and design as
such? to replace the villain ladder we will do causality bubbles." This note
records the ruling, states the one boundary it must not cross, and lists what
comes out and what has to exist first.

## 1. Why it is right

`world/offscreen.py` was written for a world with no simulator in it. Its own
docstring says so: "a high-fidelity, low-cost ILLUSION of a world that moves
-- never a simulation of one". Charter is now that simulation, and since
2026-09-05 it advances EVERY BEAT by the beat's own elapsed time, free,
deterministic, with no provider seam anywhere in the module
(`DESIGN_INSTITUTIONS_AND_UPKEEP.md` § 7a). An illusion maintained beside a
simulation is two answers to one question, and the engine's oldest scar is
exactly that shape.

The ladder's rungs, measured against what Charter now does:

  * **lazy** -- zero until contact. Kept, and it is what a bubble does better.
  * **stochastic** -- a seeded draw against standing intentions. Superseded:
    Charter walks the same bodies over the same graph deterministically, and
    a draw that guesses what a body did is worse than a walk that knows.
  * **profile** and **full agent** -- paid model calls that simulate an absent
    mind continuously. This is the villain ladder, and it is the part the
    owner is replacing.

## 2. The boundary, and it is not negotiable

**Charter owns WHERE a person is and WHAT THEY DID. It must never own what a
registered mind KNOWS, WANTS or REMEMBERS.** `world/charter_figure.py` states
the rule already and gives the reason: a figure has no mind in the charter,
because knowledge, memory and psychology live in the engine's own character
machinery, and copying any of it into `minds` "would be a second
representation of a mind the engine already owns, drifting from the first
from the moment it was made".

So "entirely superseded" is true of the WORLD half and false of the MIND
half, and the migration must say which half each rung was. Concretely: a
dormant antagonist may be moved, employed, delayed, robbed and gossiped about
by Charter; their beliefs, their drive and their memories stay where they are.

The mechanism for holding one already exists and needs no new object. A
registered character is projected into Charter as a BOUND body
(`charter_runtime`, "bound bodies are simulated here, and only here"), and a
person employed by nothing is expressible today -- `transfer_person(..., to_charter=None)`
makes a hermit, "employed nowhere, still a person". A lone villain in a cave
is a hermit with a place.

## 3. What replaces the ladder: causality bubbles

A major character who walks away does not get a cheaper simulation of
themselves. They get a FRAME, and the frame is played when it matters. The
prototype exists and is unwired -- three pure detectors written on the
`causality-bubbles` branch and never committed. They were salvaged when the
stale worktrees were cleared on 2026-09-05, into the archive
`~/.claude/worktree-salvage-2026-09-05/causality-bubbles-untracked.tar.gz`,
which holds a spatial-bubbles module and its two test files. NOTHING OF IT
IS IN THIS TREE, which is why no path here names one:

    bubble_split_decision   the non-persona sibling of `detect_split`: a major
                            character walks away with no player attached
    couple_decision         a live channel now joins two frames
    uncouple_decision       the channel is gone; the couple should end

The predicate is `comms_link` and nothing else, which is the reason the design
is cheap: a channel already decides liveness, direction, where a handset is
and who overhears it, so joining two frames is the existing question asked
across a pair of scenes rather than a new notion of "far". Nothing in the
module has side effects and nothing is wired.

**Why this is the right replacement.** A ladder prices an absent character by
how important they are; a bubble prices them by whether their thread is being
told. The villain who matters is the one the story is about to touch, and
that is what a frame and a channel already know.

## 3a. Charter is a TOOL OF THE PLANNER

**BUILT 2026-09-05.** Both halves: `story/room_tools.inspect_charters` is the
read side and the `charter_ops` package operation
(`world/charter_ops.py` -> `charter_runtime.author_charter_ops`) is the write
side. `tests/test_charter_ops.py`. The section below is the argument, kept as
written, with what landed marked at the end of each half.

The owner, closing the argument: "i think charter should be a tool to the
planner ultimately." That is the statement the other two notes were circling,
and it settles what "authorship" and "simulation" mean to each other.

**Charter is the physics of off-screen life. The Planner is the hand that
reaches into it.** Not a rival author, not a second world: an instrument, with
a read side and a write side, in the shape every other Room tool already has
(`story/room_tools.TOOLS` reads the world and packages write it).

**The read side must show the institution.** Measured, the caravanserai run:
`inspect_charters` returned no post, no watch, no station and 24 of 40 bodies,
so the Room asked to describe the house named the gate warden as its innkeeper
and invented three staff. A tool that hides the field the question is about is
worse than no tool, because it answers confidently. Posts, the watch, places,
stations and the whole roster belong in the read, paged rather than truncated.

> **Built.** `inspect_charters` returns five sections per institution --
> `upkeeps` (level against floor, whether it is below it, its drift, what it
> depends on, the posts that serve it and who is tending it), `posts` (place,
> purpose, what it serves, what it requires, who it reports to, the fixture
> it is stood at, who holds it), `watch` (who is standing what) with
> `unfilled_posts`, `bodies` (place, within-room station from
> `charter_place.charter_placements`, berth, home post, duty stood,
> availability, condition, any walk or errand) and `roster` (the
> institution's BELIEFS, shown only where they differ from the bodies).
> Every section is PAGED: a page says how many rows it withheld and the exact
> call that returns them, and `section` + `cursor` returns them. The old
> 24-body cap is now the page size when one charter is named
> (`CHARTER_PAGE`), eight per charter in the all-charters overview
> (`CHARTER_OVERVIEW_ROWS`, so a story with several institutions still fits
> the 12,000-character result cap, which `fit_result` would otherwise
> satisfy by dropping every charter at once).

**The write side is `charter_ops`** (registered, not built): an errand
dispatched, an event staged against an institution -- an upkeep failing, a
post vacated, a supply cut, somebody arriving, leaving or dying -- each routed
through the functions Charter already owns (`charter_surgery.send_errand`,
`charter_runtime.transfer_person`, the upkeep ledger) and refused the way a
`positions` write is refused, by the same deterministic floor.

> **Built**, as a package operation the Planner writes -- not a Director
> channel; the Director half is still open (`docs/UNBUILT.md` § 1.124). One
> authored EVENT carries up to `CHARTER_OPS_CAP` = 12 ops from the closed set
> `errand | arrive | depart | die | fill_post | vacate_post | upkeep_fails |
> supply_cut`, each landing through the function Charter already owns
> (`send_errand`, `transfer_person`, `harm_body`, `assign_post`,
> `vacate_post`, `charter_shock`'s `upkeep_shock`, `adjust_stock`), and the
> whole event lands or none of it does. Every refusal names its reason: a
> body the town does not stand, a room no plan holds, an upkeep the
> institution does not owe, a good it never stocked, an institution the
> registry does not hold (which `transfer_person` would otherwise MINT -- a
> town founded by a typo), a body already dead, a field the kind does not
> take. **An authored event is an INPUT**: it must be expressible in the
> vocabulary Charter already owns, or it is prose again, which is the lesson
> of the concealment written as free text that was no channel at all.

Three things this does NOT change, and each is what makes the tool worth
having:

  * **The Planner directs; Charter computes.** The Planner says the granary
    burned. Charter says who therefore has nothing to tend, who notices, who
    is blamed, and who never hears about it. Section 2's rule stands: the
    Planner never says who reacts.
  * **The institution keeps its own beliefs.** A roster improves by
    OBSERVATION and decays otherwise (`world/charter_roster.py`), and no
    authored event may correct it by decree. A town that learns of a death
    when somebody sees the body is the whole material.
  * **The Director still reads Charter for the beat** -- carriers, figures,
    crowds -- and does not steer it. One subsystem, two readers, one author.

Each of the three is pinned by a test rather than by this paragraph
(`tests/test_charter_ops.py`): no op has a field for who reacts and a field
outside the schema is refused, so a reaction cannot be smuggled in as an
extra; a death leaves `roster[body].believed_available` true until
`charter_roster.observe` is called; and `charter_carriers`,
`present_charter_figures` and `charter_crowd.members_of` read the same
registry across an authored event and write nothing.

**Why this is the right shape.** Charter already refuses to hold a registered
mind, already believes rather than knows, and already advances for free every
beat. What it lacked was somebody with a reason to reach in. The Planner is
the agent that thinks in weeks and in consequences, and it has been reasoning
about a world it could not touch.

## 4. What has to exist before anything is deleted

  1. **Bubbles wired**: split, couple, uncouple, and a frame that can be
     played and rejoined. Until then, deleting the paid rungs leaves a
     dormant cast that does nothing at all.
  2. **Standing intentions rehomed.** The stochastic rung advanced them for
     free. Decide whether an intention belongs to the mind (and therefore
     waits for a bubble) or to Charter's own plan machinery. My
     recommendation: the mind's, because an intention is a want.
  3. **Reactive plans and due events** (`advance_reactive_plans`, the due-event
     epoch reason) are not ladder rungs and must not go with them; find them a
     home before the module is cut.
  4. **The epoch itself.** After the paid rungs go, its remaining jobs are the
     due-event trigger and the budget context Charter reads
     (`beat | time_skip | presim`). Keep it, or move those two and let it go.

## 5. What comes out, once (1)-(4) hold

`offscreen_life` as a permission ladder and its settings surface;
`resolution_for`, `derived_importance`, `subject_distance`; `stochastic_ticks`
and the offscreen log's stochastic rung; `profile_*` and every `agent_*`
scheduler and its jobs; `dormant_subjects` and `full_agent_candidates` as tick
sources. `docs/archive/PROPOSAL_2026-08-06.md` § 1.2 becomes archive in fact
as well as in folder.

## 6. What argues against it

  * **A bubble is a frame, and frames cost more than a tick.** The ladder's
    cheapest rung was zero and its dearest was one call; a played frame is a
    whole beat. The answer is that a bubble runs only when the thread is being
    told, but that is a claim to measure rather than assume.
  * **Charter is deterministic, and a villain is not.** A plan that surprises
    the player is exactly what the paid rung was buying. The bubble has to
    carry that weight, and if it cannot, something has to.
  * **Nothing in the corpus has run a bubble yet.** The detectors are pure and
    untested against live data, so the first thing after wiring them is a play
    run, not a deletion.
