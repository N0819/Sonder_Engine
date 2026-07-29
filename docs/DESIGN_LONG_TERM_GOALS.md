# Long-term goals (projects)

**Status: v1 built.** `affect.apply_project_ops` / `affect.serves_priority`
(lifecycle, cap, weights), `character_schema.character_projects` (authored),
`commit.py` (seeding, ops, persistence in `interior.projects` /
`interior.former_projects` on `chat_chars.state`), `agents/character.py`
(payload `self.projects` / `self.former_projects`, destination fallback in
`_destination_from_goals`), prompt contract (`project_ops`, PROJECTS block).
Tests: `tests/test_projects.py`. Goal-slot currency (the last Decided
bullet): `affect.goal_slot_currency`,
`agents/character._annotate_goal_currency`, tests in
`tests/test_goal_currency.py`. Boundary review is prompt-normative in v1,
not engine-gated — see below. Measurements that motivated it:
[`MAZE_ARMS.md`](MAZE_ARMS.md) A11–A13 for the raw observations and
[`DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](DESIGN_PSYCHOLOGY_AS_PRESSURE.md) for
the prior art this revives.

## The gap

The engine has three tiers of wanting, and the space between the first two
is empty:

| tier | lives in | horizon | how it ends |
|---|---|---|---|
| drive | `psychology.drive` | permanent | only a rupture window moves it |
| **— nothing here —** | | | |
| intention | `interior.intentions` | a scene, a task | satisfied, abandoned, or swept as dormant |
| want | `active_state.wants` | one beat | re-derived from the room in front of them |

A drive is eternal and placeless: it cannot name a room, so it cannot be
walked to. An intention names a room and is *built* to be completable and
abandonable, which is correct for a task and wrong for a life's work. There
is nothing that is durable but not eternal — no **project**.

## What the absence measured

Four failures, all the same shape, all from characters who wanted the right
thing and stopped:

- **Satisfied by one instance.** `ia4` — "walk the proved line to the shrine
  at Chamber 0603" — was marked `satisfied` by the character the beat after
  he first arrived. True once, therefore never steering again. (A13 run 4.)
- **Decayed by barren stretches.** A courier's shrine commission decayed
  after ~150 beats yielding nothing. The intention system was *right* by its
  own rules; a goal returning nothing is spent. But the world had not
  withdrawn the job. (A12.)
- **Abandoned with the tactic.** `i1`/`i2` died when the theory they served
  stalled, taking the underlying aim with them. (A13.)
- **Out-competed every beat.** Beat wants are re-authored from perception,
  so a nine-room journey needs the same intent to win nine consecutive
  independent auctions against whatever happens to be in the room. Measured
  trail toward a destination the character chose himself: `9 9 7 8 9`.
  (A13 run 4.)

## Properties, derived from those failures rather than invented

1. **Not discharged by one instance.** Satisfaction requires an explicit
   criterion, or the project is per-occasion and re-arms at its boundary.
   "Every run ends at the shrine" is a project; "reach the shrine" is a task
   wearing the word.
2. **Tolerant of barren stretches.** The dormancy sweep that correctly
   spends intentions must not touch a project. A hundred beats of nothing is
   a normal week inside one.
3. **Not an entry in the beat auction.** A project must *bias* appraisal —
   raising the score of wants that serve it — rather than competing as a
   want itself. Competing is precisely how the shrine lost: at intention
   weight 0.8 against drive-serving wants at 1.0, every time.
4. **Reviewed at boundaries, not per beat.** Run ends, scene changes, major
   events. This is what makes a project "deliberately not based on immediate
   wants and hypotheses in the moment": it is structurally not re-asked when
   the character walks into an interesting room.

## The cap

**A character may hold one or two projects. Never more.**

Scarcity is what makes the tier mean anything. Characters today carry seven
live intentions, and with seven there is no answer to "what is this person
about right now" — the list is a soup and whatever the room offers wins by
default. With a cap of two there is always an answer.

The cap also gives adoption a price. Taking on a third project requires
giving one up, which makes it a real decision with a cost rather than an
addition to a list. And the giving-up must be a **legible act with a stated
reason** — never silent eviction — because that is the one revision a
character currently cannot perform: they can disprove a belief about the
world (a `disproven` edge) and have no mechanism at all for revising a
belief about themselves or their own project. A displacement is exactly that
revision, made visible.

Open: whether the second slot should be reserved for a project of a
different *kind* (one about the world, one about the self), or whether two
of a kind is allowed. Two spatial projects at once may simply reproduce the
oscillation this tier exists to fix.

## Decay should be reasoned, not silent

This applies to ordinary intentions too, not only to projects, and it may be
the more valuable half.

Today decay is bookkeeping. `affect.py`:

```
_INTENT_DORMANT_AFTER = 30    # turns without progress -> dormant
_INTENT_STALL_AFTER   = 2     # barren attempts at full progress -> dormant
```

When either trips, `intent["status"]` is set to `dormant` and the reason is
appended to a `warnings` list — which is **log output**. The character is
never told. The aim stops steering and nothing in their mind records that it
stopped, or why.

So a character cannot think *"this isn't working out."* They can only
discover, some beats later, that they no longer want something. That is
precisely the shape of the A11/A12 failure: a courier walked sixteen optimal
rooms to the shrine's threshold and turned away, because the goal underneath
had been spent by a sweep he was never party to.

The decay itself is right — an aim yielding nothing for thirty turns SHOULD
lose its grip, and a character who never gives up is not a character. What
is wrong is that the giving-up happens *to* them rather than *by* them.

Proposed shape, the same legible-not-silent move used for
`ground_fully_known` and `en_route`:

- As an intention approaches decay, surface the fact in the payload rather
  than flipping the status underneath: *this aim has returned nothing for N
  beats.*
- Let the character answer it. Renew it, revise it into something narrower,
  or abandon it **with a stated reason** — which is the self-revision they
  currently cannot perform at all.
- Only sweep silently as a backstop, when the character has been offered the
  question and has not answered it.
- Revisit the constants once the question exists. Thirty turns is short for
  an aim a character would describe as theirs, and two barren attempts is
  very short; but a longer fuse is only safe if the character can see it
  burning.

Open: whether a renewed intention should cost something, so that renewal is
a decision rather than a reflex. Without a cost, "renew" is always the
cheapest answer and nothing is ever given up.

## Relationship to work in flight

`en_route` (see `agents/character.py`, payload) is the same missing axis at
the short end: holding an aim across nine beats rather than across five
runs. If both land, the character has continuity at both horizons and
nothing in between is left to re-derive from scratch.

This also revives psychology proposal (c) — a derived inclination that
*relocates* salience — declined twice on the grounds that it would let
authored text override lived conduct. The cap and the boundary-review rule
may answer that objection: a project does not overwrite what a character has
lived, it competes for two slots and must be given up out loud to be
replaced.

## Decided in v1

- **Persistence:** `interior.projects` + `interior.former_projects` on the
  `chat_chars.state` blob — the `place_graph` precedent: checkpoints,
  `chat_archive`, and branching carry that blob verbatim, so no schema,
  remap, or archive change. Not derivable: durability across evidence decay
  is the *defining* property, and anything derived from decaying rows
  inherits their decay. Note `commit.py` rebuilds `interior` from scratch
  each beat, so both ledgers are carried through `_interior_out` explicitly.
- **The bias:** a want or goal-impact whose `serves` names a held project id
  scores at **drive weight (1.0)** — `affect.serves_priority`. The scarcity
  cap is what makes that weight safe to grant; seven intentions at 1.0
  would just move the soup up a tier.
- **Assign vs offer:** the world (Director, another character, the harness
  prompt) can only *offer*; adoption is always the character's own
  `project_ops.adopt`. The two exceptions are author-level, not world-level:
  cards author projects in `psychology.projects` (seeded at commit, deduped
  against live *and former* so a project given up never silently re-seeds),
  and the maze harness may hand-write `interior.projects` exactly as it
  hand-writes beliefs.
- **Both slots full and the world insists:** the adopt is refused
  deterministically with a warning; the engine never evicts. Refusing — or
  displacing one out loud and feeling the cost — is the character moment.
- **Boundary review:** prompt-normative in v1 — and measured NOT to hold
  (A15 run 5: nine perfect beats, then mid-run drift with no moment that
  re-asked). v2 is engine-gated: `affect.project_boundary` detects the
  boundaries the engine can actually see — arrival at the room a project's
  own text names (over the character's own place-graph names), an intention
  entering satisfied/abandoned/blocked this commit, and the scene or frame
  changing against the `scene_marker` persisted last beat. Commit stores a
  one-beat `interior.project_review = {turn, why}` (self-clearing, since
  `_interior_out` is rebuilt each commit) and the payload shows
  `self.project_review = {why}` for the following beat. Deliberately NOT
  detectable, absent rather than faked: "run end" (a harness concept with
  no engine row) and "major Director event" (events carry no uniform
  salience field). The flag invites `project_ops`; the engine never applies
  one.
- **Drift legibility (v2, the mid-run half):** commit keeps a per-project
  `last_served_turn` ledger (`affect.projects_served_this_beat`): a beat
  serves a project when a want or goal-impact `serves` resolves to its id,
  or when the beat goal names the same room the project's text names, over
  the character's own place-graph names. Text similarity was measured and
  rejected for the substance channel — it scored the chalk-circle detour
  (0.2) above "walk the proved line to the shrine" (0.167). The payload
  reads the ledger back as `adrift: <beats>` after 8 unserved beats
  (`agents/character._annotate_project_drift`, read-side, non-mutating).
  Escalation is wording, never mechanism: past a dozen beats the prompt
  calls it "a choice you have not admitted — serve it, or displace it with
  the reason stated". A project still never decays; noticing is the
  character's half of that bargain, and the resident clause holds — under
  the threshold the payload says nothing, and a resting project is not
  nagged.
- **Second-slot kind:** not enforced. `about: world|self` is declared, and
  one structural fact already prevents the two-spatial oscillation worry:
  `_destination_from_goals` resolves exactly one destination, goal first,
  then intentions, then projects — two room-naming projects cannot both
  route. Measure before legislating further.
- **Decay legibility (v1 of the section above):** an active intention idle
  for two-thirds of the fuse carries `fading: <beats>` in the payload
  (`agents/character._annotate_fading`), with prompt text framing it as a
  question to answer — renew by acting, revise, or abandon with a stated
  reason. The sweep is unchanged and remains the backstop.

- **Adoption governance (v3): the deliberation is mechanical.** "Can a mind
  reliably deliberate that this is worthy as a project?" — answered by
  making `satisfied_when` the test, with a measured discriminator:
  `adopt` **requires** a criterion, and a criterion that *restates the
  project text* is refused as circular (`_CRITERION_RESTATES_SIM = 0.4`;
  measured gap: circular/task criteria score 0.5–0.75 against their own
  project text — "understand the symbols"/"when I understand the symbols"
  0.75, "fetch the physician"/"the physician is here" 0.5 — while genuine
  external conditions score 0.125–0.25: "the keepers withdraw the
  commission" 0.125, "spring comes and the village still stands" 0.25).
  The same gate therefore catches a task wearing the word, because a
  task's completion restates the task. What it cannot catch — an insincere
  but external criterion — is what probation is for.
- **Probation (v3): time filters instead of judgement.** A runtime
  adoption starts `probation: true`: it weighs at **intention** level
  (0.8) — adoption alone buys no appraisal power — and it may **lapse
  quietly** (to `former_projects`, `end: "lapsed"`, auto-stated why, no
  ceremony) once unserved for `_LAPSE_AFTER = 24` beats, three times the
  drift threshold, so a lapse is never the first notice. It
  **establishes** — probation flag removed, drive weight, lapse-immune —
  after being *served* on ≥ 3 distinct beats over ≥ 12 turns
  (`settle_probation`, fed by the service ledger). Establishment by
  *surviving N boundary reviews* was considered and rejected: the measured
  failure mode of this tier is inattention, so passive survival would
  establish the exact pathology. Both floors are needed — service alone
  lets a three-beat enthusiasm establish same-day; age alone is
  establishment by neglect. Authored and harness-written projects carry no
  probation flag: the author's deliberation already happened, which is
  what keeps a live `pa1` untouched by the change. The stated-reason
  displacement floor now applies exactly where it belongs: to projects a
  character has actually lived by.
- **The goal slot functioning as an ungoverned project: built, as
  goal-slot currency.** Measured: "Compare chalk circle patterns across
  chambers" survived a run boundary and a process restart in
  `active_state.goal`, with no cap, criterion, or visibility — partly a
  *consequence* of the en_route continuation-default, which makes goals
  sticky by design. Turn-370 live data showed the shipped machinery
  bending it back, so the decision was: measure before governing, with
  the trigger for building goal-slot aging set at a non-serving goal
  surviving `adrift >= 12` AND a boundary review without re-deriving
  toward the project. **The trigger then fired** (live, turns 377–385):
  pa1 unserved since turn 369 (`adrift` 15 at the turn-384 commit), a
  boundary review at 384 ("your task ia1 closed this beat"), and the goal
  still "Run east to Chamber 0206 along the proved line" — a room whose
  visit tail read `… 0306 0206 0205 0206 0306 0206`, the spent claim
  tethering him back to the room it named because one step out of 0206
  re-made 0206 the destination. Built as the same legible-not-forced
  shape as the rest of the tier: commit stamps `goal_since` /
  `goal_room` / `goal_room_reached` on the slot
  (`affect.goal_slot_currency` — word-keyed: verbatim re-emission
  carries a stamp, any re-wording is re-authoring and resets it), the
  payload reads them back as `goal_reached` {room, beats_ago} and
  `goal_held` <beats> (`agents/character._annotate_goal_currency`,
  read-side, non-mutating, `_GOAL_HELD_AFTER = 12`), and
  `_destination_from_goals` declines to route on a SPENT claim exactly
  as it already declines one naming the room he stands in — intentions
  and projects speak instead. Division of labor: room-naming goals are
  governed by reach (tenure never nags a journey en_route is carrying);
  room-less goals by tenure, suppressed while the enacted want serves a
  live intention or project (those tiers' own clocks burn instead) but
  NOT by a self-declared `serves:"drive"` label. The goal text itself is
  never rewritten, and a restart survives WITH its tenure, so the marker
  is present on the first beat after — which is exactly when the slot
  was measured presenting a dead scene's want as current. Tests:
  `tests/test_goal_currency.py`.

## Not yet decided

- Whether a renewed intention should cost something, so renewal is a
  decision rather than a reflex.
- Whether displacement should feed the drive-strain ledger (giving up a
  drive-serving project is plausibly a strain event).
- Whether drive and project both weighing 1.0 needs revisiting. Current
  position: no — the weight is an *appraisal* weight, not a want-selection
  weight, so raising it cannot conjure the missing project-serving want;
  the drift failure was absence, and absence is fixed by legibility.
  Putting projects *above* the lived drive would also reopen the objection
  that killed psychology proposal (c) twice: authored text outranking
  lived conduct. Revisit only if a measured run shows a project-serving
  want being *emitted and then losing* to a drive want, which is a
  different failure from the one observed.
