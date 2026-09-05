# Design: who says what a place has become, when nobody lives there

**Status: DESIGN, 2026-09-05, not built.** From the owner, in the same
conversation as the ruling in `DESIGN_OFFSCREEN_SUPERSEDED.md`: "I feel like
the planner might reason how a place has changed over time or may have had
history if it is not populated or sparsely populated."

## 1. The hole this fills

The ruling says Charter supersedes off-screen life. That is right where there
are people to simulate and silent where there are not. A ruin, a road, a
drowned cellar, a station nobody kept, a hill: Charter has no body to walk and
no upkeep to drift, so nothing advances, and the place is exactly as the
player left it however long they were gone. Worse, it has no PAST either --
the only account of what a room used to be is whatever prose happened to be
narrated near it.

So the division is not "simulation versus authorship". It is:

> **Where there are people, simulation says what a place has become. Where
> there are none, authorship does. The sparser the population, the more the
> Planner has to say, and the two must never answer for the same fact.**

A hamlet of three is the interesting middle, and it is not a problem: Charter
moves the three and lets their mill's upkeep fall, and the Planner says what
the empty mill has become since the last miller died.

## 2. The trigger already exists, and it is free

`world/gaps.py` answers one question structurally -- *what changed about X
between turn N and now* -- as a RECORD, never prose, and **a room is already a
valid subject kind** (`subjects.resolve_subject`, `k == "room"`). `gap_for` is
deterministic and free at every tier, and `interim_for` produces the gap at
the moment of contact, which is exactly the moment a place is walked back
into.

That gives the trigger for nothing: **ask the Planner where the free skeleton
comes back empty.** A gap record that says nothing happened is not a failure;
it is the engine reporting that no simulated cause touched this place, which
is precisely the condition under which authorship is the only possible source.
Three asks, and no others:

  1. **First contact** with a room the story has never described.
  2. **Return** after an absence whose gap record is empty or thin.
  3. **A filed `setting_fact` need** (`world/planning_needs.py` already has the
     reason, and `commit_mapping` already files it when a fact has no answer).

Never every beat. The cost of this is a model call, so the trigger is the
budget, exactly as the charter's ten seconds is its budget.

## 3. What it may write, and it is not prose

Three kinds, each with a home that already exists, because a fact nothing can
act on is the defect this repo has measured most often (a concealment written
as free text was no channel at all; a barrier described in a sentence was not
a barrier):

  * **History** -- what this place was, what happened here. Lore rows, the
    room's `notes`, and a region's `look` (`regions.set_region_look`; a
    `describe_region` tool is already registered as unbuilt and is the obvious
    seam).
  * **Change since** -- decay, growth, weather scars, traces of passage.
    Entities minted or edited, an anchor added or REMOVED (the removal channel
    landed 2026-09-05), a room's `light`/`exposure` moved, the backdrop brief
    re-keyed because the room genuinely changed.
  * **The absence itself** -- why nobody is here. That is a story fact, it is
    usually the best hook in an empty room, and today nothing can say it.

## 4. Four boundaries, each earned

  1. **It must not invent people.** A person is `plan:person` and, once
     standing, Charter's. Two hands answering "who is here" is measured (the
     road run's PD8: interpret asked for an NPC the plan already held).
  2. **It must not contradict what the player saw.** The ledgers own the
     present. The Planner authors the PAST and the CHANGE SINCE; where the two
     disagree the ledger wins and the disagreement is reported, which is the
     layout lint's own discipline.
  3. **A history claim carries its time.** The engine has a clock, and "the
     mill burned" with no date competes with the present tense forever.
  4. **It is asked, and it cites.** The citation contract built for the recap
     on 2026-09-05 applies unchanged: a claim about a place either cites the
     rows it read or is a proposal.

## 5. Why the Planner and not the Director

The Director owns objective causality for THIS beat and is already the most
expensive stage in the engine (two Director stages are about two thirds of a
turn's wall clock, measured across five play runs). A place's history is not
this beat's causality, it is out-of-band authorship with no deadline, and the
Planner is the agent that already reasons about the world beyond the frontier
and already writes rooms through packages. Putting it there costs a turn
nothing.

## 6. What argues against it

  * **It is the strongest hook in the engine and the easiest to overuse.** A
    room whose history is always interesting is a world with no ordinary
    places in it. The trigger must stay stingy, and "nothing has changed" must
    be an acceptable answer the Planner is allowed to give.
  * **Authored change and the backdrop cache fight.** Every re-keyed brief is
    an image redrawn; a place that changes on every visit is expensive in a
    way the note about the brief already measured.
  * **It cannot be verified by anyone.** A simulated change has a cause in the
    ledger; an authored one has only the sentence that made it. The citation
    rule limits the damage and does not remove it.
  * **The sparse case will drift toward the dense one.** Once a place has a
    history it tends to acquire people, and then Charter owns it and the
    Planner must stop answering. The handover needs a rule, and the honest one
    is the same as the trigger: the Planner is asked only where the free
    skeleton is empty.
