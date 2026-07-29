# Long-term goals (projects)

**Status: designed, not built.** Nothing in the engine implements this yet.
Written down while the measurements that motivate it are fresh; see
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

## Not yet decided

- Where projects persist (`interior.projects`? a status on an intention?)
  and therefore the full `docs/DATABASE.md` checklist, or whether they can
  be derived from existing rows the way `en_route` is.
- How appraisal expresses the bias without recreating the 1.0-vs-0.8 loss.
- Whether the world can *assign* a project (a commission) or only offer one.
- What a character does when both slots are full and the world insists.
