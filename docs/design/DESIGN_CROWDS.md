# Proposal — crowd blobs

A crowd is one object with many people in it. Background NPCs emerge from it
when someone interacts; otherwise it is a single row that moves, thins, splits
and murmurs, and costs the same as one presence no matter how many people it
contains.

The user's idea. This is the design and the argument for it, with the parts
that are already in the tree marked, because two of them are.

---

## 1. The engine already wants this

`scene.py:1129` caps `max_reactors` at 3 and says why `[read]`:

> *"past that, a crowd is better represented as one chorus presence than as
> several individually-voiced extras."*

Stated intent, never built. And `commit.py:3007` already carries the word in
the other sense `[read]` — `_bodies_answering_to(identity, scene) > 1` →
`continue  # genuinely a crowd` — where "crowd" means *do not merge these two
presences, there really are several bodies*. A disambiguation flag, not an
entity.

So the concept exists twice as prose and nowhere as an object.

## 2. Why it is the right shape, and not just a cheaper one

The economics match the offscreen design exactly: `O(places)` rather than
`O(people)`. But cost is not the strongest argument, because the engine has no
shared call budget. Three better ones:

**It fixes a budget the engine actually enforces.** `max_managed` defaults to 6
and is hard-capped at 8 `[read]`. Chat 57 spent three of those six slots on one
Dalek, split three ways by its article. A market square with forty people
cannot be represented at all today: it either eats the whole manager budget or
it is silently absent. **A crowd must not consume a managed-presence slot** —
if it does, it has solved nothing.

**It gives a place life without inventing cast.** Re:Zero's book carries 29
location entries and 14 character entries, and the 14 are Great Spirits and
Witches — no ordinary living person in the book at all `[measured]`. The Royal
Capital, Priestella's watergate, the road to the Watchtower need *populace*,
and populace is exactly what a lore-heavy book never supplies. A crowd blob is
the object that makes a place feel inhabited without minting cast nobody
authored.

**It is the honest resolution tier for people you are not talking to.** The
offscreen design already argues that nothing offscreen gets full resolution. A
crowd extends that to people who are *on* screen but not in the scene: present,
audible, consequential to atmosphere, and not individually simulated.

## 3. The object

```
crowd = {
  uid,                       # stable, minted once; never a display name
  room_uid,                  # where it is
  band,                      # "a handful" | "a dozen or so" | "a few dozen" | "a throng"
  composition,               # "dockworkers and late ferry passengers"
  heading,                   # None | room_uid it is moving toward
  mood,                      # one word; drives the murmur, never a line
  since_turn,
}
```

**Density is NOT a field.** Band is how many; density is how close together,
and it is a function of the band and the ROOM — forty across a market square
is loose and walkable, the same forty in a gate passage is a crush. Storing it
would be a second source of truth that drifts the moment the crowd moves, and
the proposal's own rule about resolution applies here for the same reason:
recomputed, not stored. §5a derives it from vocabulary that already exists.

**The count is a BAND, not an integer.** Deliberate, and it is the decision
everything else rests on. An exact number invites arithmetic nobody can
honour — the moment two sources disagree about whether 37 people became 34,
there is a contradiction with no resolution, and this project's rule is that
contradiction becomes a dispute rather than an average. Bands also make
splitting free (§5) and are what prose actually needs: nobody writes "thirty-
seven dockworkers".

**`uid`, never a name.** Five ledgers already key beings by display name and it
is one defect, not five. A crowd is a new writer, and a new writer into the
wrong key space is the exact thing 0c exists to stop. Whatever 0c decides is
the identity spelling, crowds use it from birth rather than being migrated
later.

## 3a. Crowds are not the only source of background people

A crowd is one way a place gets populated and it must not become the only one.
A tavern has a barkeep and drinkers; a vendor stall has a vendor. Those are
**fixtures** — they belong to the place, and they should be the same people
next visit.

Two sources, and the difference is durability rather than mechanism:

| | fixture | emergence |
|---|---|---|
| belongs to | the location | the crowd |
| on return | the same person | a different stranger |
| named | may be | never, until they speak |
| minted | when the place is first generated | when someone interacts |

**A fixture is part of what a place IS**, so it is generated with the place and
lives with it. The mapping agent already generates rooms; a room whose lore
says "tavern" should acquire a barkeep the same way it acquires a hearth. This
also gives the lore-heavy case somewhere to land: the Re:Zero book has 29
locations and no ordinary people, and a tavern with nobody behind the bar is
the failure the whole feature is about.

**An emergence is a stranger.** No continuity is promised and none should be
implied. Coming back to the square and finding the same dockworker would be a
claim about persistence that nothing recorded.

The rule that keeps them apart: **a fixture may be re-met; an emergence may
not.** If the story needs someone to be there again, they were a fixture and
should have been minted as one.

> **Amendment (2026-08-27, the crowds bridge —
> `DESIGN_BACKGROUND_PRESENTATION.md` §B3, `world/charter_crowd.py`):** for a
> **charter-backed crowd** the fixture/emergence distinction COLLAPSES, and
> "an emergence may not be re-met" is superseded for that species. A derived
> crowd's members are fully simulated registry bodies; the one who steps out
> persists in Charter with their ties, marks and diary whether or not anyone
> is looking, so the person who emerged last visit IS there next visit, and
> re-meeting them is correct rather than a claim nothing recorded. A fixture
> is simply a charter body with a post here. The table above still governs
> AUTHORED crowds, whose people exist only as a band — an authored emergence
> still promises no continuity, because there is no body behind it for the
> continuity to live in.

## 4. Emergence

When the player addresses the crowd, or the Director needs someone from it, a
person **emerges**: a new entity, minted with an id, with the crowd as its
origin. The band drops one step if it was already at the bottom, otherwise it
is unchanged — a throng minus one is a throng.

Two rules, both from defects already on the record:

**Emergence is one-way for anyone who speaks.** Once a line is attributed to
someone, they are a presence and cannot be re-absorbed, because the story now
has a record of them and `dialogue_log` will outlive the scene. Someone who
only *acted* — stepped aside, looked up — may re-absorb when the beat ends.
The test is whether anything durable now names them.

**A crowd may never emerge a named character.** It produces strangers. If the
Director wants Wilhelm van Astrea in the square, he arrives; he does not
materialise out of the extras, because a cast member emerging from a crowd is
indistinguishable in the record from one who was always there, and that is a
canon write nobody authored.

## 5. Movement and splitting

A crowd carries `heading` and moves between rooms on the same spatial graph
everyone else uses — no second pathfinder.

**Splitting is band-preserving, not count-preserving.** "A few dozen" splitting
toward two exits gives "a dozen or so" and "a dozen or so". No arithmetic, no
conservation bookkeeping, no drift. Two crowds where there was one, each with
its own uid and origin recorded.

The illusion the user is after comes from this being cheap enough to do often:
a market thins toward the gate as the ferry docks, a knot peels off toward the
shouting. That reads as a living crowd and costs two rows.

## 5a. Caught in one: a membrane with a current

A crowd you can be caught in is not set dressing, it is **terrain**. It moves
you in the direction it is going, it makes passage complicated rather than
impossible, and you can attempt to get out. That is the user's design and it
turns out to need less new machinery than it looks like, because the engine
already has half of it.

**Density is derived from the band and the room, and both scales exist.**
`room.size` is already a field with the vocabulary tiny / small / medium /
large / huge / vast, already ranked by `_ROOM_COST` at `spatial.py:3980`
`[read]`. So:

    density = band_rank - size_rank        >= +1  crush
                                              0  packed
                                           <= -1  loose

Which produces the user's case without anything being special-cased. A few
dozen (3) in a gate passage (small, 2) is +1, a crush. Pushed through into the
square beyond (large, 4) the same crowd is -1, loose — and the escape that was
impossible in the gateway is simply available, because the geometry changed
and nothing else did.

That is the property worth having: **the crowd did not decide to release you,
the room did.** A crush that thins when it reaches open ground is what a real
one does, and it costs a subtraction.

**Density maps onto barrier vocabulary that exists.** `world/spatial.py` folds
barrier words into a known set and asks two independent questions: is it
passable, and does sight pass. `membrane` is already `passable` and already
NOT in `_SIGHT_BARRIERS` — you can push through it and you cannot see through
it — and its own comment glosses it as *"a curtain, a tent flap, a body's soft
wall"* `[read]`. The vocabulary anticipated bodies.

    loose   ->  open      : walk through, see across
    packed  ->  membrane  : push through, cannot see across
    crush   ->  membrane  : as packed, and the current is strong (below)

So a crowd needs no new passability class. What it needs is the part the
barrier layer has never had:

**DRIFT — a barrier with a heading.** Every barrier in the engine is inert; it
permits or refuses. A crowd imposes its own movement on whoever is inside it.
That is the genuinely new concept and it should be named as one rather than
smuggled in as a special case of passability, because passability answers
"may I" and drift answers "what happens if I do nothing".

**Escape is a declared action with a real failure.** You may push crosswise,
grab a rail, shout for the person you came with. The Director resolves it
against density, against what you are carrying or holding, against whether you
are trying to keep hold of a companion. Not a die roll — a judgement about the
beat, which is what the Director is for. But it has to be able to FAIL, or the
attempt is theatre and the crowd was never terrain.

Three constraints, each from a scar already on the record:

**Drift is an ARRIVAL and the record must say so.** `_guard_approach_is_not_
arrival` exists because a beat describing approach and a beat placing you
somewhere are different things, and conflating them wrote positions nobody
declared. A crowd carrying you is precisely an arrival the player did not
declare. It goes through the commit path and appears in the state diff like
any other move. A crowd that moved someone quietly is that same defect with a
new cause — and this one would be worse, because the player would have a
reason to believe they had moved themselves.

**The spatial layer answers "may I"; the Director answers "what happened".**
Density decides passability and sight deterministically. Whether the press
carries you this beat, and how far, is a resolution and resolutions have an
owner. Splitting it that way keeps the deterministic half testable.

**Separation is written to BOTH sides.** Being cut off from a companion in a
crush is the best thing a crowd can do, and it is a silent state change for
the other character, who can no longer see you. `known` and the presence
ledger are per-observer for exactly this reason; recorded on one side only is
how a character goes on addressing someone who is no longer there.

This also answers the first falsifier in §7 before it is run: a crowd you can
be caught in cannot be routed around, because it is in the way.

## 6. Where it sits in the offscreen design

A crowd is a **low-resolution gap subject** — `kind: crowd` alongside
`character` and `room` (and `faction`, per the amendments). Its gap is
deterministic and needs no model call: *it moved, it thinned, it dispersed, it
doubled*. That is the whole low tier, which the proposal already says is
assembled from state the engine has.

It can also carry claims without a speaker. "The market has been quiet since
the flood" is a thing a place asserts through its population, and it goes
through the same provisional-claim path as anything else offscreen invents.

## 7. What would falsify this

- **Crowds are never addressed.** If the player and Director both route around
  them and nobody ever emerges anyone, this is set dressing that could have
  been a sentence of prose. Measurable: emergences per crowd-turn.
- **Emergence produces people nobody wants.** If emerged strangers are
  immediately abandoned and clutter the presence ledger, the one-way rule is
  wrong and everything should re-absorb.
- **Bands read as vague rather than atmospheric.** If narration keeps asking
  for a number, the band was the wrong primitive and the count should be real.
- **It absorbs the cast.** If authored characters start being represented as
  crowd members because it is cheaper, the feature is eating the thing it was
  meant to support. Watch for a fall in named presences after it lands.

## 7a. Built, 2026-08-10 — and what the building changed

All five steps are in the tree. `world/crowds.py` is the pure module (bands, derived
density, terrain, drift, splitting, emergence); `StateDiff.crowd_ops` is how a
Director says it; `commit.commit_crowds` is the one persistence boundary;
`agents.common.crowds_for_room` is the per-observer surface; and
`tools/crowd_drive.py` walks the whole chain against a scratch database.

Three things the argument above got wrong, found by building it:

**`spatial._ROOM_COST` is not a size rank.** §5a says it is. It collapses tiny,
small, `""` and medium all to 1, because it prices WALKING rather than
describing extent — reusing it would have made a crush in a broom cupboard read
the same as one in a hall. `crowds.ROOM_SIZES` is a real rank, and a test
asserts the two differ.

**A heading spent in the beat that declared it makes drift unreachable.** The
obvious order — apply the Director's ops, then advance — moves the crowd inside
the same commit, so `crowds_for_room` reports `drift: null` on every turn that
will ever be perceived. The whole of §5a becomes machinery the Director is
asked to resolve and can never be shown. The order is inverted: last beat's
flow is spent first. A heading therefore lives for exactly one beat of
perception, which is also the honest reading of "a market thins toward the
gate" — you watch it happen.

**Emergence needed almost no new machinery.** §4 reads as though a person must
be minted. `commit.track_background_presences` already discovers anyone given a
dialogue line or an entity def, so emergence records only what that path cannot
know: that they came out of the crowd. Building a second writer would have been
building a second identity space, which is what §3's `uid` rule exists to stop.

Splitting needed one extra disambiguator. Band-preserving means both halves
share band, composition and room, so their uid material was identical to the
parent's but for the turn — and a split on the minting turn collided. The
recorded origin breaks the tie.

§7's falsifiers are all still unrun: they need a playthrough, and
`tools/fire_rates.py` is where emergences-per-crowd-turn should be read.

## 8. Build order

1. **A crowd that exists.** Sits in a room, visible to perception as one body,
   emerges nobody, moves nowhere. Answers the only question that matters
   first — *does a room with a crowd in it read as more alive than the same
   room without one* — and is cheap to delete if the answer is no.
2. **Fixtures** (§3a). Independent of crowds and arguably more valuable: a
   tavern with nobody behind the bar is the failure this feature exists to fix,
   and a fixture is a persistent entity rather than a new mechanism.
3. **Density as terrain** (§5a). Presenting a crowd to the spatial layer as a
   barrier. No movement of the crowd yet — a stationary crush in a gateway is
   already the whole mechanic, and it is the version where being caught can be
   tested without also debugging a moving object.
4. **Movement**, then **splitting**.
5. **Emergence** last. It is the part that writes durable rows, and it should
   not land until the cheap half has earned it.

The order is deliberate: 1 and 2 are additive and reversible, 3 changes what
the spatial layer answers, and 5 changes what is in the ledger forever.

**Drift lands with step 3, not later.** I argued first for stop-only on the
first pass — a refusal is easy to get right and an undeclared arrival is where
this project's history says positions get invented. That is overruled, and on
reflection correctly: a crowd that can only stop you is a wall with better
prose, and the whole point is that it takes you somewhere. The risk is real
and the answer is not to defer it but to make the arrival loud — through the
commit path, in the state diff, adjudicated rather than computed.
