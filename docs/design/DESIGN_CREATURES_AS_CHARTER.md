# Creatures as Charter

**Status:** built 2026-09-03 (`world/charter_harm.py`, `world/charter_creature.py`,
`world/charter_predation.py`, the widened `charter_intervene`, `charter_trigger`
and `charter_decide`; fixtures in `tests/charter_worlds.py`; measured below).
Residuals in `docs/UNBUILT.md` §2.32.

## 0. The class, stated once

**A creature is an institution whose upkeep is fed from other institutions'
bodies or stock, whose triggers are authored, and whose evidence is left in
the world.**

That is the whole of it. A pack, a band of robbers, a solitary hoarder with a
tribute bargain and a thing that feeds on fear are one schema with different
tables, exactly as a ship's watch bill and an abbey's hours are one schema
(`docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md` §9, `tests/test_charter_genre.py`).
Nothing in `world/` knows what a wolf is; the nouns live in the fixtures.

What Charter already had, and this rests on: bodies with needs that drift by
the hour; institutions with places, posts and upkeeps; movement over the
town graph with routes and shut doors that hold; encounters between bodies
sharing a place; witnessing by presence; news that travels by carrier and
gossip; grievances, blame and standing; commitments; an economy of lots and
markets; authored triggers over objective changes; authored physical
interventions. What it had no producer for was **harm** -- `harm_done` was in
`WITNESSABLE`, `GRIEVANCE_KINDS`, `DEFAULT_SIGNALS` and `TRIGGER_EMITTABLE`,
and the only thing in the repository that could emit one was an authored
rule.

## 1. The tiers, and why this is the off-screen one

Off screen a creature is *needs and routes*. It eats on a schedule it did not
choose, moves on the graph everybody walks, and leaves what it leaves. On
screen it is the Director's to render from the same state (its hunger, its
last kill, where it was going), and a tactic nobody authored -- stalking,
ambush, defending the lair against a hunt -- is a causality bubble's, never
this module's. The room plans it; Charter runs it; the Director renders it.

The test for "boring" this is built against: a creature's behaviour must
**change in response to what the town and the player do**, and must be
**legible from what it leaves behind**. A schedule that eats every forty hours
fails it. A pack that moved its den because the reeve's watch met it, and is
now taking sheep from the far pasture where the watch is thin, passes it.

## 2. The harm model (`charter_harm`)

One closed field on a body, `condition` in `CONDITIONS = (well, hurt, dead,
missing)`, enforced at `normalize_body` so a corpse cannot reach a watch bill
however the record arrived.

| | what it does |
|---|---|
| `hurt` | capability × `HURT_CAPABILITY` (0.5); `health` need knocked to at most `HURT_HEALTH_LEVEL` (0.5); `HURT_RELUCTANCE` (0.75) on the planner's axis; heals on `HURT_RECOVERY_HOURS` (72), reported as `body_recovered` where the body stands |
| `dead` | unavailable for good; post vacated; berth freed; `succession` if the post was a head |
| `missing` | as dead, and in no room (`place` cleared); the berth is kept |

**Succession through politics.** A head post (nobody reports past it and
somebody reports to it -- `charter_generate._head_posts`'s rule, restated in
`charter_harm.head_posts` because the generator carries model calls) passes
to the living body of highest `politics.standing`, which becomes its
`home_post` so the planner's own preference for a body's ordinary duty
carries the office. One register event, `succession`.

**The event.** `harm_done` at the place, `actor` the party that did it (a body
key of the institution's own, or the qualified `charter/body` of a body
elsewhere), `subject` the victim, `outcome` the condition. It is NEWS to whoever
stood there (`charter_news.witness`), a GRIEVANCE against the actor
(`charter_practice.grievance_against`), fear in every judgment formed from it
(`charter_social.DEFAULT_SIGNALS`), and a change a rule may fire on. A dead
or missing body is in no room (`charter_talk.co_present`): it witnesses
nothing and is told nothing.

## 3. The creature record (`charter_creature`)

```
creature:
  prey:            ordered over PREY_CATEGORIES (stock, unposted, posted, figure)
  senses:          {range_rooms}
  footprint:       spatial_fov.FOOTPRINTS; can_open_doors
  contest:         {capability, group_bonus, posted_weight, unposted_weight, caution}
  encounter_odds:  per hunting body per window, before hunger and boldness
  kill_ceiling:    bodies per window, per institution
  stock_lots:      lots per raid; take: missing rather than dead
  fed:             {upkeep, per_body, per_lot}
  spoor:           {body, stock, tracks, hours}
  active_phases:   day_cycle phases; empty = always
  boldness:        0..1, the dial rules turn
  hoard_holder:    where taken lots go
  bargains:        [{with, good, holder, lots, every_hours}]
```

Every number is the creature's own. The engine defaults are what an
unwritten field reads as, and each is named: `DEFAULT_PREY` (stock, unposted,
posted -- `figure` is never a default; a scene-owned person is the Director's
to endanger), `DEFAULT_SENSE_RANGE_ROOMS` 2 (capped by `SENSE_RANGE_CAP` 8),
`DEFAULT_ENCOUNTER_ODDS` 0.5, `DEFAULT_KILL_CEILING` 1, `DEFAULT_STOCK_LOTS` 1.0,
`DEFAULT_SPOOR_HOURS` 72, `DEFAULT_BOLDNESS` 0.5, `DEFAULT_CONTEST`
(capability 1.0, group_bonus 0.5, posted 1.0, unposted 0.4, caution 0.2),
`DEFAULT_FED` (per_body 0.6, per_lot 0.25), `SPOOR_CAP` 32.

**Hunger** is the fed upkeep's distance from full. It scales the odds
(`attack_odds = odds × (0.5 + hunger) × (0.5 + boldness)`), and a creature
that catches nothing starves the ordinary way: the upkeep crosses its floor,
the `sustenance` need fed by it goes unserviced, bodies go under. The famine
spiral `charter_needs` documents, applied to the hunter.

**Footprint and doors** decide the graph the creature walks
(`creature_neighbors`): the passable graph, plus shut doors when it can open
them, minus rooms its footprint does not fit (`FOOTPRINT_MIN_ROOM`: large
needs medium, run needs large; an unsized room fits everything). The walk is
planned on the whole graph and `charter_move._advance` re-checks each edge
against this map and HOLDS the body -- a shut door holds a wolf exactly as it
holds a townsperson, and no second mover was written.

**The contest** is two capabilities and a seeded draw. The creature bodies
standing at the place bring `capability` each (halved when hurt). The target
brings its posted or unposted weight (halved when hurt) times
`1 + group_bonus × (bodies beside it)`. A posted body beside an unposted one
makes the place guarded for both. `caution` is the win chance below which the
creature turns away -- measured before it existed: twenty attacks on a
two-body watch, twenty losses, and the pack never once turned away.

## 4. The round (`charter_predation`)

`charter_run.step` advances one institution and reads nothing outside it.
Predation is cross-institutional by definition, so it is a **round** run after
every charter in a registry has stepped one window (`run_registry`):

1. **Tribute** (§7) is collected or defaulted first.
2. **Senses.** A hunting body that notices prey within `range_rooms` on its
   own graph walks toward it (`hunt_moves`), if it is not already going
   somewhere and nothing is where it stands.
3. **Encounters**, by place: where creature bodies stand with prey, the draw
   against `attack_odds`; the target is the first category of the prey table
   the place holds (`_prey_here`); stock counts only in whole lots
   (`STOCK_WHOLE_LOT` 1.0 -- measured, ninety-five "raids" on a pen that
   never held a whole head).
4. **The outcome lands in each institution's own vocabulary**: harm through
   `apply_harm` in the victim's charter, a lot through `charter_economy.take_stock`
   (a new event kind, `stock_taken`, witnessable), the creature's fed upkeep
   restored, a losing attacker hurt by the guard it lost to, the kill ceiling
   counted per institution per window.
5. **Spoor** (§5). 
6. Every event is **carried**, not applied where it was minted: it rides
   `charter["carried_events"]` into the institution's next window, where
   `step` treats it as that window's happening -- witnessed by presence,
   appraised, deposited as a change for rules, remembered by whoever stood
   there, and returned as produced ONCE, there. One window of lag, the lag
   triggers and judgments already carry.

**Byte-identity.** A registry of one ordinary charter run through
`run_registry` is byte-identical to `charter_run.run` on the same seed
(`tests/test_charter_creature.py`), because the stepper keeps the same caches
and seeds per window. `charter_runtime.presim_registry` and `advance_snapshot`
take the interleaved path only when a creature is in the registry; a town
without one is advanced by exactly the code it always was.

## 5. Spoor: the stationary carrier, one tier down

A landed predation leaves a record standing at the place for the creature's
authored `spoor.hours`: what a kill leaves, what a raid leaves, what its
passing leaves. A body of ANY other institution standing where it lies reads
it (`read_spoor`): a claim in its own head, provenance `read`, keyed by the
spoor so two readers hold the same fact and can compare it. The creature does
not read its own; nobody reads the same spoor twice; expired spoor is swept.
Nobody learns of a kill because it happened -- they saw it, were told, or
came upon what it left.

In play, `land_snapshot` turns the registry's standing spoor into artifacts
(`story/artifacts.post_spoor`, `SPOOR_STANDING_CAP` 8 apart from the notice
cap), so a carcass reaches the room's `notices` in perception exactly as a
posted bill does, and comes down when the registry no longer holds it.

## 6. Authored rules and ops

`charter_trigger` change rows gain `side` (`SIDES`: `dealt` when the actor is
one of ours, `suffered` when the subject is), matchable in `where`, read from
the body index alone. Two ops move the INSTITUTION rather than a body
(`INSTITUTION_OPS`), fired by `fire_institution_rules` -- a second pass under
the same firewall as `fire_triggers` (change rows and a body index, nothing
inside a head), so the per-body pass keeps its signature and return shape:

- `intervene` schedules any `charter_intervene.INTERVENTION_OPS` row for the
  next window: `relocate` (every berth moves to a named room or the nearest
  fitting one that is not a work place), `creature_dial` (turn `boldness` or
  `encounter_odds`), `need_shock`, `drift_dial` (whose end now RESTORES the
  drift it found rather than zeroing it -- "dormant for three days" was
  dormant for good), `upkeep_shock`, `watch_shock`.
- `settle_commitment` settles every open undertaking of a kind into one of
  `SETTLE_STATES`.

So a creature file says, in one row each: a member killed → move the lair;
hunted → boldness down, then move on; fed → dormant N hours; left hungry
under a bargain → repudiate it. Each op is closed, normalized, and refused
with a notice.

## 7. Institution shape: bargains, hoards, succession

A **bargain** is a commitment in the creature's own ledger (kind `bargain`,
promisor the institution, beneficiary the partner) opened by the round on
the creature's authored `bargains`. While it stands, the creature does not
prey on that partner. Tribute is a transfer of lots on the bargain's cadence
from the partner's holder into the creature's `hoard_holder`, and it feeds
the creature `per_lot`. A partner that cannot pay **defaults** (an event in
the partner's charter); a creature whose fed upkeep crosses its floor under a
bargain **repudiates** it (an event at its lair). Both are commitment events
the town learns of only where somebody stood.

A **hoard** is stock: taken lots and tribute accumulate under `hoard_holder`
in the creature's own economy. An **alpha** is a head post: succession
passes it by standing (§2). **Sentries** are a watch, which is what a post
is.

## 8. Mobilisation: the town's answer

`charter_decide.mobilisation_calls` -- the only input is the caller's own
head. A post carrying `MOBILISE_AUTHORITY` ("mobilise" in `authority`), staffed
by an available body, reads that body's `known_news`; a claim of a
`THREAT_KINDS` kind (`harm_done`, `stock_taken`) naming a place and holding at
or above the institution's authored **credence** is a call. Strength already
carries regard for the teller and the retelling count (`hear_claim`), so a
stranger's warning is weaker than a neighbour's by construction, and a lie
that clears the bar is a mobilisation the liar is blamed for.

The call schedules a `watch_shock` for the next window. `apply_due` raises
`crew` temporary posts (`watch:<place>:<i>`) serving a temporary upkeep
(`guard:<place>`) that starts EMPTY under a HIGH floor and is put first in
`priority`, so the planner fills them first and pulls crew off their ordinary
posts -- whose upkeeps then drift and fail like any absence. `mobilisation_called`
is emitted where the office stands. At `until_hours` a `watch_stand_down`
removes the posts and the upkeep and emits `mobilisation_lapsed` with
`false_alarm` true when the round never marked `harm_seen` at that place --
and a false alarm lands one blame on the caller (`charter_run.step`), in the
counter a failed post lands in. A guarded place is guarded: posted bodies
there are what the contest weighs.

Authored per institution (`charter["mobilisation"]`), with named engine
defaults: `MOBILISATION_CREDENCE` 0.6, `MOBILISATION_HOURS` 48,
`MOBILISATION_CREW_FRACTION` 0.25, `MOBILISATION_CREW_CAP` 12; the watch
upkeep's `MOBILISATION_UPKEEP_FLOOR` 0.9, `_DRIFT` 0.05, `_SERVICE` 0.5.

## 9. The fixtures (`tests/charter_worlds.py`)

`with_wilds` hangs a wood, a small den, a large cave and a tiny burrow off
any town's edge room; `guarded_town` gives a town a pen with livestock, a
treasury with silver, a reeve with the authority to call the watch, and a
herding crew of three at the pen who report to the reeve; `wolf_pack`
(nocturnal, stock first, no doors, den moves when a member is hurt),
`bandit_band` (stock and stragglers, opens doors, takes rather than kills,
loses nerve and moves on when hunted), `dragon` (solitary, `run` footprint,
hoard, a silver-a-week bargain honoured until it goes hungry, sleeps three
days when fed).

## 10. Measured

Seed 3, 4-hour windows, day cycle anchored at midnight, `.venv` on the
owner's machine, 2026-09-03. Baseline cost is the town alone through `run`
and through `run_registry` (identical events).

| fixture | arm | hours | wall | kills (per week) | raids | mobilisations | notes |
|---|---|---|---|---|---|---|---|
| small_town (12) | alone, `run` | 48 | 0.06s | | | | 54 events |
| small_town | alone, `run_registry` | 48 | 0.05s | | | | 54 events, byte-identical |
| small_town | + pack | 720 | 2.6s | 7 (1.6) | 19 | 0 | 7 bodies gone; stock emptied by week 2 |
| small_town | + band | 720 | 2.4s | 10 (2.3) | 16 | 1 | 10 taken; treasury looted |
| small_town | + wyrm | 720 | 2.1s | 0 | 0 | 0 | tribute paid 5 weeks running, hoard 5 |
| big_town (1,004) | alone, `run` | 48 | 8.55s | | | | 0 events |
| big_town | alone, `run_registry` | 48 | 8.90s | | | | 0 events, byte-identical |
| big_town | + pack | 48 | 9.31s | 1 reported, 2 gone (3.5) | 1 | 0 | 6 spoor standing; 53 heads lived through it |
| big_town | + band | 48 | 9.30s | 4 (14.0) | 4 | 0 | 10 spoor standing |
| big_town | + wyrm | 48 | 9.30s | 0 | 0 | 0 | tribute paid, hoard 1 |

**The cost bound.** The owner's bound was that the cost must not grow by
more than the creature's own bodies would explain. On the thousand-body town
the stepper alone costs 4% over `run` (8.90s against 8.55s, the same events)
and a creature costs a further 0.4s per 48 hours (9.3s, +9% over `run`
alone). Four to five creature bodies among a thousand explain half a per
cent of that; the rest is the round's own work each window -- the company
index over every body, the senses walk, the spoor read -- and it is flat in
the number of creatures (all three arms cost the same). Before
`apply_harm(copy_state=False)` the pack arm cost 10.96s: a deep copy of the
town per kill was most of it. Whether 9% is within the bound is the owner's
call; it is named here rather than absorbed.

The small-town month arms cost 2-3s each; the town alone for a month was not
measured at that length (the 48-hour baseline is 0.06s).

## 11. What this deliberately does not do

- **Figures are never prey off screen.** The player and the major
  characters are the bubble's to endanger; a creature notices them
  (`figure` is a category) and does nothing about it here.
- **No tactics.** Stalking, ambush, lair defence are character-frame work.
- **Spoor stands in play until the Director removes it**; the registry's
  `until_hours` sweeps the record, and `post_spoor` takes the artifact down
  on the next landing, but a beat between sees a carcass the town has already
  forgotten.
- **Mobilisation reaches the reeve only through channels.** A posted herder
  who never leaves the pen never tells the reeve; the fixture's crew of
  three is what carries the news to the square in the social phases. A town
  whose offices never meet its posts does not mobilise, which is correct
  and is why the small-town month shows one call in three arms.
- **Between-creature predation** is allowed by the class (a band may prey on
  a pack) and untested.
