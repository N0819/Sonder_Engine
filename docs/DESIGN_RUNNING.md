# Design: running

**Status:** built (`79f1ad8`), with its central rule corrected once — see §3,
which is the part of this document worth reading.

A character could only ever move one room per beat. That makes a courier whose
whole craft is speed indistinguishable from someone strolling, and turns any
distance into a queue of identical beats.

Multi-room movement was already legal and already validated before any of this:
`passable_route_exists` exists precisely to bless *"a legitimate single-beat
traversal, not a teleport"*. Nobody was allowed to **ask** for it.

---

## 1. The mechanism

`spatial.sprint_reach(scene, room_id, known_rooms=None)` reports, per passage
out of a room:

```json
{"bearing": "n", "path": ["r0501", "r0502", "r0503"], "rooms": 3,
 "stops": "junction"}
```

`path` is every room crossed in order, ending where the run stops. It is the
whole list and not the destination, because a body that runs through three
chambers **has been in three chambers** — see §4.

It reaches the character as `perception.sprint_reach` and the Director as
`declaration["sprint_reach"]`, so a declared run resolves against a figure the
engine computed rather than the Director's sense of how fast a person is. The
Director may narrate falling *short* of the listed reach for a stated reason —
winded, hurt, carrying something — but never exceeding it.

## 2. Room size makes it distance, not room count

`SPRINT_BUDGET = 3` small rooms. A `large` hall costs two of them, a `vast` one
the whole beat. Deliberately coarse: the engine is not simulating gait, it is
answering *"does a body cross this much ground in one beat"* well enough that
the answer is never absurd.

## 3. The bound: decision, not sight — and why the first version was wrong

**The original rule stopped a run at a bend**, on the reasoning that you cannot
see round a corner, so a run bounded by sight could never carry a body through
ground they had not already seen. That sounded like it made the firewall
argument fall out for free. It was wrong, and it was wrong in a way worth
recording because the wrong version is the more appealing one.

It was measured wrong first. Arm A11's census: of 96 runnable passages, 72
allowed exactly one room, 22 allowed two, 2 allowed three, and `winded` **never
fired anywhere in the maze**. The budget and the whole room-size cost path were
dead code. A character on 43% of beats was offered a "run" worth one saved beat,
and declined every time — correctly.

The cause was not the maze being unusual. Pure straight-line geometry there: of
196 (room, direction) pairs, 100 offer no straight room at all, 64 offer one, 22
offer two, and only **ten** offer three. The longest straight corridor in the
whole maze is four rooms. That is not a quirk — it is a perfect maze, 39 of its
49 rooms are two-exit corridor cells, and a corridor cell is usually a *bend*.
Winding is what makes a maze a maze.

So the rule had bound the feature to terrain that mazes do not contain.

**The correction: a run continues while there is exactly ONE way onward,
whatever the bearing.** Following a corridor round a bend is not a choice —
there is one way on and you take it. What genuinely requires stopping is a
**junction**, because running through one is choosing without looking.

Measured against the same maze:

| | sight-bounded (wrong) | decision-bounded |
|---|---|---|
| 1-room runs | 72 | 18 |
| 2-room | 22 | 14 |
| 3-room | 2 | **64** |
| mean | ~1.3 | **2.48** |
| `winded` fires | never | 64 times |

**The firewall argument survives, and is cleaner.** A character enters an unseen
room every time they walk through a doorway, and perceives it by being in it —
so "entering ground you have not seen" was never the hazard. What sight was
really standing in for was *not choosing blind*, and a bend offers no choice.
State this wherever the rule is implemented: the next reader will reach for the
sight bound for the same appealing reason, and the docstring has to answer them.

Still stopping a run, because these are the world stopping you rather than a
decision: `dead_end`, `darkness`, `door` (a closed door does not open itself),
and `winded`.

**One asymmetry the correction introduces, and the implementation keeps.** The
RUN may cross ground the runner has not seen — they perceive it by being in it.
The **offer** may not describe such ground: decision-bounded reach handed raw
to a character would report the winding geometry of passages they never walked,
unearned map smuggled in as an affordance. So the character-facing view
(`agents/character.sprint_offers`) passes `known_rooms` — the straight
sightline plus the engine's remembered-ground union (place-graph nodes +
visited window) — and truncates with `stops: "unknown"` where its warrant runs
out; a body's offered reach grows as it learns the ground. The Director's
resolve ceiling passes nothing and sees the scene as it is, which is what lets
an open-ended declaration ("run on until something stops me") resolve past the
runner's own knowledge legitimately. The payload edge also drops offers under
two rooms: a 1-room "run" is a step with a different verb, and A11 measured 72
of them teaching the character that runs are trivial.

## 4. The rooms crossed must be remembered

A multi-room move leaves `came_from` non-adjacent to where the body stopped, and
the place graph mints walked edges only from adjacent steps. Without handling,
a corridor sprinted end to end would record **nothing**: no nodes for the rooms
crossed, no walked edges, and the whole corridor still reading as untrodden —
pulling the character back down it. Holes in the map exactly where the feet
went.

`spatial.passable_path` reconstructs the rooms between deterministically rather
than asking the Director to list them. Asking a model to be right about geometry
is the thing A11 measured it being worst at.

A move with **no** passable route mints nothing. That is a teleport, a carry, or
a vehicle, and a character learns a place by being carried through it about as
well as a parcel does.

## 5. It is an offer, and that has a cost

The character prompt frames running as available, never required. There are good
reasons to walk: to arrive able to fight or speak, to keep quiet, to look at
what you pass, because you are hurt or spent, because haste is not who you are.

**But an offer competes with the selection criterion, and loses.** The character
prompt's core directive is *"predict the smallest plausible next behavior"*, and
a multi-room run is by definition not the smallest. Measured in A11: the
character saw `sprint_reach` on 72 separate beats, parsed it correctly every
time, and took a multi-room run **zero** times in 152 turns — reasoning, at the
moment of declining, *"the prompt asks for the smallest plausible next
behavior."*

The resolution is not to weaken the directive, which exists for good reasons.
It is that **a run to its stopping point is one beat-sized behaviour** — the
smallest unit of running is the whole reach, not the first room.

A second contributor, worth knowing when authoring: this character's sheet said
*"never breaking stride"*, and he consistently read that as an argument
**against** running — stride as steady pace, sprinting as a stride-breaking
burst. Speed-as-identity, phrased that way, generates walking. The sheet has
since been re-authored: an explicit `psychology.drive` whose expression is that
he runs, and values as ordered trade-offs ("speed over thoroughness") — see
[`DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](DESIGN_PSYCHOLOGY_AS_PRESSURE.md) (a), a
prohibition names no counterweight inside itself.

## 6. Risks

**Narrated distance drifting from committed distance.** The Director could
describe a longer run than it commits. `path` is the engine's, and the resolved
position must be its last element.

**Running as the default.** If every character runs everywhere, the beat stops
being a unit of attention. The counter is that running is louder, arrives
winded, and sees less of what it passed — properties the Director is told to
apply, not merely permitted to.

**A junction passed at speed.** If the rule is ever relaxed to run *through*
junctions, the character is choosing without looking, and every navigation
affordance downstream is being fed a choice they did not make. Do not.

## 7. Experiment that would settle it

A map with a genuine long corridor and a `large` hall, run twice by the same
character: once with `sprint_reach` present, once ablated. The mechanism works
if beats-to-goal falls while **moves**-to-goal does not — that is running
buying time rather than the character taking a different route. If moves fall
too, something else changed and the measurement is not about running.
