# Design: Charter supersedes off-screen life, and bubbles replace the ladder

**Status: RULING 2026-09-05; § 4.1 BUILT 2026-09-17; the TRIGGER and the
PLAYERLESS BEAT rebuilt the same day on two further rulings; the ladder not
yet removed.** The owner: "can we just agree that offscreen life is entirely
superseded by charter and design as such? to replace the villain ladder we
will do causality bubbles." This note records the ruling, states the one
boundary it must not cross, and lists what comes out and what has to exist
first. Bubbles now split, couple, uncouple and rejoin (§ 3, § 4.1);
§ 4.2-4.4 and therefore § 5 are still open, and § 6 is still a claim to
measure -- nothing in the corpus has run a bubble in play yet.

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
themselves. They get a FRAME, and the frame is played when it matters.

**BUILT 2026-09-17.** `world/spatial_bubbles.py` holds the three decisions;
`world/spatial_frames.py` holds the drivers (`open_couple`, `close_couple`,
`detect_couple`, `is_bubble_frame`, and `perform_split(bubble=True)`), and
`detect_and_reconcile` is the one commit-time entry point they all come out
of. `tests/test_causality_bubble_detectors.py` is the decisions,
`tests/test_couple_invariants.py` the couple's contract, and
`tests/test_causality_bubbles_wired.py` the lifecycle end to end. The
paragraph below is the argument as it was written, kept because the
prototype's reasoning is what the build followed:

    bubble_split_decision   the non-persona sibling of `detect_split`: a major
                            character walks away with no player attached
    couple_decision         a live channel now joins two frames
    uncouple_decision       the channel is gone; the couple should end

The predicate is `comms_link` and nothing else, which is the reason the design
is cheap: a channel already decides liveness, direction, where a handset is
and who overhears it, so joining two frames is the existing question asked
across a pair of scenes rather than a new notion of "far". Nothing in the
decision module has side effects; the drivers live beside every other write
to a frame.

**Three things the build had to add that the prototype did not know about,
each because the live code had moved under it.**

  * **A channel answered for a ghost.** `_comms_delivers` matches a carrier
    by NAME before it consults `positions`, and `comms_link`'s same-room
    guard is skipped when an endpoint has no room -- so a handset written
    into both frames at a split, and positioned in only one of them,
    delivered a voice to a body that was not in the scene at all. Harmless
    inside one frame, which is exactly what a split stops being. `comms_link`
    now refuses an endpoint named but unplaceable.
  * **A shout crossed a locale, and it always had.** Two rooms with no edge
    between them report `separated`, and `hear_level` gives `separated` a
    shout as a `fragment` -- right for two rooms in one building, wrong for a
    bridge and a market a continent apart, which is what a declared `zone`
    means. `spatial_rel` now reports `remote` between two declared locales,
    which is opaque to sight, scent and a shout alike. The couple gets its
    physical separation from that rule rather than from one of its own, and
    the fix is not a couple's: it was wrong in an ordinary two-zone scene
    before any frame was split.
  * **A bubble could never close.** `detect_merge` reads `zone_groups` and
    `_all_party_names`, which are the primary player and the personas
    stationed in a frame -- a bubble has neither by construction, so its zone
    set was empty and its party rooms were empty and the one-way merge could
    not fire. The bodies a bubble answers for are its CAST, and
    `_bubble_rejoined` asks the same two questions of them.

**Why this is the right replacement.** A ladder prices an absent character by
how important they are; a bubble prices them by whether their thread is being
told. The villain who matters is the one the story is about to touch, and
that is what a frame and a channel already know.

### 3b. The trigger is RANGE, and a bubble has a beat of its own

Two owner rulings, 2026-09-17, both taken after the first live run of the
feature and both replacing something § 3 had assumed.

**"Whenever they are outside the player causality bubble, even if it happens
mid beat."** The original trigger was a declared `zone`, inherited from
`detect_split` -- and a zone is a LABEL, so the engine could only notice a
departure somebody had thought to name. Measured, `google/gemini-3.8-flash`,
the Millbrook story: a courier took an errand across the water, walked out of
the tap room, and got no bubble, because the road she walked down carried no
zone. A second run produced one only because the landing had been authored
with a zone by hand.

`spatial_bubbles.in_range_rooms` replaces it with the set the Director is
already shown: `spatial.attended_rooms` -- where the human party stands, the
rooms one step off them, and the far end of any live two-way channel reaching
those. **A body in the payload is in the beat; a body outside it is outside
the beat.** Nothing has to be labelled for that to be true, and the split's
sixth refusal ("an open channel already reaches them") stopped being a clause
at all: a live channel's far end is IN the range, so the case is reached by
construction. `_bubble_rejoined` asks the same predicate backwards, which it
must -- a trigger and a release in two vocabularies is a body that leaves on
one rule and can only return under another.

`detect_split` keeps the zone rule, deliberately. It answers whether two
PLAYERS have separated, a split that restores permanent bidirectional memory
visibility when it is undone, and a declared locale is the positive evidence
that one is intended.

*What range costs that zones did not:* an undrawn adjacency now reads as
distance. A freshly minted room with no `adjacent` is an island to
`nearby_rooms`, so a body standing in it is out of the beat immediately --
consistent with the rule, since the Director's payload does not carry that
room either, and survivable because the release is the same predicate: the
mapping that draws the doorway ends the bubble on the next commit. Pinned by
`TestWhatRangeCostsThatZonesDidNot`.

**"Yes -- build the playerless beat."** Until that ruling a bubble was a
PAUSE. Measured in the same run: a courier crossed to the far shore and stood
on the landing for three player beats, her frame's scene byte-identical each
time, and formed not one memory. `agents/offscreen_beat.py` gives every live
bubble a beat of its own, scheduled out of band from the commit tail on the
same terms as memory consolidation. It runs the ordinary pipeline minus the
two stages that exist because somebody is watching:

  * `director_interpret` makes no model call. There is no declared line to
    read, and a stage asked to read an absent player's input is asked to
    invent one -- the single thing the engine forbids anybody to author.
    `offscreen_interpretation` writes the same shape deterministically: every
    player-owned field empty, and `flow.reactors` naming the minds whose beat
    it is.
  * No narrator, and no background reactors. Narration is the player-facing
    slice and nobody is reading it; a page describing her beat is a page that
    could be shown.

Everything else is hers as it is anybody's -- her perception from her own
scene, her character step from her private memory, the Director resolving
objective outcome, and a commit that stamps her memories with her own frame.

*The cost is the argument against it, and § 6 was right:* a live bubble costs a
character call and a Director resolve every beat, whether or not anything is
happening to her, and EVERY live bubble runs.

**There is no cap, and that is a third ruling** (owner, same day: "I don't
think a character should ever freeze unless they've been made dormant"). A cap
on how many bubbles advance per beat is a freeze wearing a number -- the third
absent character stands still indefinitely while the first two live, and
nothing in the fiction explains why. It shipped as `OFFSCREEN_BEAT_CAP = 2`
for one afternoon and came out.

So cost scales with the absent cast, and **the lever is DORMANCY**: a
character nobody is telling a story about is made dormant, Charter moves them
for free, and what they did while dormant becomes memory on the way back. That
tier is § 3c, and it is NOT BUILT -- until it is, the lever is only its first
half: a dormant character gets no bubble, so they cost nothing and remember
nothing, which is the gap § 3c exists to close.

### 3c. Dormancy is the cheap tier, and it must not cost a memory

**NOT BUILT. Owner ruling, 2026-09-17**, in the same breath as the no-cap one:
"we should have charter start handling dormant characters and generate a
memory log to add to their old ones when they are undormanted through an llm
call so they don't have gaps in memory over any period of time."

This is what makes § 3b affordable. With no cap, an absent character costs a
beat a turn forever; the answer is not a ceiling but a second tier, and the
ruling names it. Three parts, and only the third is genuinely new.

**1. A dormant character is handed to Charter.** § 2's boundary already says
Charter owns WHERE a person is and WHAT THEY DID, and that a lone figure
somewhere is expressible today: `transfer_person(..., to_charter=None)` makes
a hermit, "employed nowhere, still a person". What does not exist is the
handoff for an ORDINARY authored character. `bind_promoted_character` runs the
other way -- a Charter body promoted INTO a character keeps its institutional
projection and loses its Charter cognition -- so a character written from a
card has no body in the town at all, and making her dormant today simply stops
her. The seam is one line: `persist/commit_mechanics.py`'s `set_char_status`
call, which every `cast_changes` transition passes through, sleeping and
waking alike.

**2. While dormant, Charter moves her, free.** The advance is already
unconditional and holds no provider seam
(`DESIGN_INSTITUTIONS_AND_UPKEEP.md` § 7a), so this part is arithmetic the
engine is doing anyway.

**3. On waking, one LLM call turns what Charter recorded into MEMORY.** This
is the new thing, and it is the point: today a character who sleeps for two
hundred beats wakes with an unexplained hole where that time was.
`gaps.gap_for` already assembles the free, deterministic record -- moves and
events, no model -- and `gaps.interim_for` already hands it to a waking
character as PAYLOAD. Payload is not memory: it informs one beat and is gone,
and nothing about it survives into what she can recall next week. The call
turns that record into rows on her own ledger.

**Four things to get right, and the first two are the firewall:**

  * **The log is HERS, not the world's.** Charter's record of a window holds
    what happened to everyone in the institution. What may become her memory
    is where SHE was, what SHE did, and what reached her there -- the same
    subtraction `gap_for` already performs by subject. A wake-up call handed
    the institution's window would give a returning character a week of
    everybody else's business, which is the largest single leak this engine
    could ship.
  * **Charter must not gain a mind on the way.** § 2 is not negotiable:
    knowledge, memory and psychology stay in the character machinery. So the
    log is WRITTEN by the character tier, from Charter's record, at the
    moment of waking -- never stored in `minds`, which would be a second
    representation of a mind the engine already owns.
  * **Bounded by the gap, not by the beats.** Two hundred dormant beats must
    not produce two hundred rows. The consolidation tier already has the
    shape for this (`maybe_consolidate_character_memory` writes windows), and
    a dormancy is exactly one window: a handful of rows proportional to what
    actually happened, not to how long it took.
  * **Provenance is `witnessed`, and the rows are hers.** She was there. The
    only honest alternative would be to mark them as reconstructed, and the
    engine has no such provenance -- inventing one would be a fifth value for
    every reader of that column to learn.

**Where it runs:** out of band, like every other model call the commit tail
schedules. A character waking on a beat must not make the player wait for a
summary of her own fortnight; she acts on `interim_for`'s free record that
beat, exactly as she does today, and the ledger catches up behind her.

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

     > **Done, 2026-09-17.** A bubble opens for cast who walked into a zone
     > with no human in it and no voice reaching them. A live channel opens a
     > COUPLE -- a third frame kind holding the fused view, where the beat is
     > played, routed to by `turn_new` so the client goes on naming the frame
     > it always named. The couple never sets `merged_turn_idx` on either
     > member, and every memory a coupled beat forms is stamped with its own
     > subject's member frame, so the two ledgers never share an era.
     >
     > **There is no uncouple DRIVER, and the absence is the design.** The
     > bubble's sixth refusal is "a live channel already reaches them", so a
     > call ending lifts the refusal by itself. Nothing latches, which is why
     > nothing can be left latched -- and the same fact means a call does not
     > destroy and re-make a bubble: the same frame is simply un-fused,
     > holding the cast and the ledger it held before anybody picked up.
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
  * **Nothing in the corpus has run a bubble yet.** Still true after the
    build: the decisions are exercised against constructed scenes and against
    real rows in a test database, and not once against a story. So the next
    thing is a play run, not a deletion -- and the two costs to measure there
    are the one § 6 opens with (a played frame is a whole beat) and the one
    the build added (`open_couple` copies every frame-scoped key of the home
    member into the couple, and `close_couple` copies them back, per call).
