# Off-screen life, reactivation, and villain ticks — design

> Status: **design / step 2 built, alpha 6.9** — `BehaviorController`'s
> ladder is now consumed, as the chat-level `offscreen_life` ceiling on
> `dialogue_config` (`scene.OFFSCREEN_LIFE_LADDER`), settable in the NPC
> dialogue panel and gated in `commit.prepare_mapping_commit` and
> `commit.commit_mapping`. Nothing ticks a plan yet; `reactive` and
> `character_agent` are permission the later steps land behind. Two things
> wiring it turned up: the engine was ALREADY emitting ungated off-screen
> ticks on every scene change, and the shipped `stochastic` rung costs a model
> call where step 3 below specifies none. Both recorded in
> [`UNBUILT.md`](UNBUILT.md) §2.8. Steps 1 and 3-6 remain unbuilt. Registered as
> [`UNBUILT.md`](UNBUILT.md) §2.7 and §2.8, which those roadmap numbers now
> point at; this document keeps the argument. Treated here as **one mechanism at
> three cadences** rather than two features.
>
> One precedent that did not exist when this was written:
> `background_claims.py` is exactly the "commit invention as claims, not facts"
> mechanism decision 3 asks for, built for background presences.

## The problem

A dormant cast must feel like it kept living without costing anything to keep
alive. The architecture's central cost claim is that **cost scales with dramatic
density, not story length** — turn 2000 in a quiet room costs what turn 2 cost,
and dormant characters are free. Any design that advances every dormant
character every turn is `O(cast × turns)` and breaks that claim outright.

So the real question is not "how do I simulate the tavern while the player is
away". It is **"how does the world appear to have moved without anyone having
computed it — except where the drama genuinely earns the computation?"**

## Two mechanisms, not one

### A. Read-time generation (the default, for almost everyone)

Do not advance anything. Generate the gap **at the moment of re-contact**,
constrained by standing intentions, elapsed clock, and whatever world events
actually fired. Cost becomes `O(re-contact)` — bounded by how much the player
actually looks at, which is exactly the shape the cost thesis wants.

This is the same operation whether the subject is a person or a place:

- Re-meeting a character → gap-history + delta-summary (reactivation).
- Re-entering a room → what changed here since turn N.

**Build one generator over "what changed about X since turn N, given these
standing intentions and this elapsed time", and both cases are that generator
with different subjects.** Resist building them as separate subsystems; they
will diverge and then disagree.

### B. Scheduled ticks (the exception, for the few who earn it)

Read-time generation has a hard limit: **it only works when the gap is observed
at re-contact.** It fails whenever off-screen activity must *cause* something
the player meets **before** meeting the character — a burned village, a missing
artifact, guards on a road that was clear last week. The player hits the
consequence first and the cause never ran, so you end up reasoning backwards
from evidence. That is retconning wearing simulation's coat.

The sharper statement, and the reason this half exists at all:

> **You cannot lose a race that was never run.**

A villain with a clock the player can fail to beat requires the clock to tick
whether or not anyone is watching. That is the whole dramatic payload, and lazy
evaluation structurally cannot deliver it.

## The ladder

`schemas.py` already declares the exact tiering and **consumes it nowhere**:

```python
class BehaviorController(str, Enum):
    inert = "inert"
    deterministic = "deterministic"
    reactive = "reactive"
    stochastic = "stochastic"
    character_agent = "character_agent"
```

| Controller | Off-screen behaviour | Cost |
|---|---|---|
| `inert` | Nothing happened. Gap generated at re-contact, or not at all | Free |
| `deterministic` | Scheduled effects only — arrival, expiry, news latency | Free (already built, `mechanics.py`) |
| `reactive` | Responds to triggers that fire, no autonomous plan | Near-free; gated |
| `stochastic` | Seeded draw against standing intentions at scene boundaries | Cheap, no LLM |
| `character_agent` | Real agent tick advancing a plan and writing consequences into the world | Paid — bounded count only |

**The cost thesis is not violated by ticking a villain.** A villain *is* dramatic
density. Paying for one to three plan-advancing agents is precisely what the
model permits; paying for the whole dormant cast is what breaks it. Ticking must
therefore be an **opt-in per-character property with a bounded count**, never a
property of dormancy in general. `BehaviorController` is that opt-in.

## What already exists

More leverage than the feature's size suggests:

- **`standing_intentions`** — live, frame-scoped world key, already staged by
  the director into both `director_interpret` and `director_resolve` (capped at
  12). Off-screen intent is *already plumbed into the director's context*.
  Nothing advances it. That is the entire gap.
- **`mechanics.py`** — the deterministic half is built: timed arrivals, expiry,
  dock edges, **news latency**, seeded and idempotent via `stable_event_key`.
- **`pick_background_reactor` (`commit.py`)** — the exact gating pattern to
  copy: a deterministic, LLM-free check returning `None` for the large majority
  of turns, so the expensive path is entered only when something earned it.
- **Seeded-draw pattern (`director_resolve`)** — `random.Random(composite_seed)`
  recording `seed/roll/dc/outcome/margin`. Reuse verbatim for `stochastic`.
- **`offscreen_log`** — frame-scoped world key already reserved.

## Decisions to lock before building

### 1. Cadence: scene boundary or in-world clock, never per turn

Cheaper, and dramatically better. A villain who advances once per in-world day
reads as a schemer; one who advances every beat reads as noise. The architecture
already has the two-clock structure (per-turn and per-scene) to hang this on.

### 2. The tick must respect the firewall in both directions

**This is where it will go wrong if it goes wrong.** The temptation is to hand
the villain agent the player's location and recent actions, because "the villain
reacts to you" is the fun part. Doing so builds the architecture's own named
failure mode — the spookily prescient antagonist — and it will read as the
engine cheating, because it is.

A ticking character advances on **its own** knowledge, updated only through
legitimate channels. `mechanics.py`'s news latency is exactly that pipe: the
villain learns the player burned their outpost three days late, the way they
actually would. An antagonist who is genuinely working against you, sometimes
wrong about where you are, and occasionally beaten by information arriving too
slowly is the engine's best argument for itself, in one character.

### 3. Every generated gap commits its claims to the world record

Independently generated gaps contradict each other. Re-meet A on turn 80 and her
gap says she spent the week at the shrine; re-meet B on turn 95 and his says he
was with her in the city. Neither generation was wrong alone — they never met.

This is why off-screen state belongs to **mapping**, not to the characters. Each
gap generation and each tick must write its claims into the record so the next
one is constrained by it. Get the ordering right in the first version and it
stays cheap; retrofit it after a dozen reactivations and you are reconciling
contradictions that are already canon.

### 4. Ticks are seeded and logged, like every other stochastic effect

The doc's determinism discipline matters most here, because a villain tick is
the one whose outcome a player will want to contest, reroll, or branch against.
Same rule as resolution dice and scheduled events: seeded, logged, replayable.
Stochastic-unlogged ticks are forbidden.

## Reactivation negotiation — build it second

Roadmap item 7 decomposes, and the halves have very different difficulty:

- **Gap-history + delta-summary** — the valuable 80%. It is mechanism A above
  with a character as its subject.
- **The negotiation protocol** — refusal budgets that deplete asymmetrically
  (identity-violation counts half, preference counts full), refusals that must
  articulate the violation, and *stalemate eats canon* as terminator. Genuinely
  novel persisted state with no pattern in the codebase to copy.

Nothing forces them to ship together. Shipping the proposal **without** the right
of refusal delivers most of the value; add negotiation once you have seen where
proposals actually go wrong. Building the budget system first means designing a
dispute protocol before knowing what characters dispute.

## Suggested build order

1. **The gap generator** — one function over "what changed about X since turn N".
   Subject-agnostic: character or room.
2. **Wire `BehaviorController`** — per-character, defaulting to `inert`. Nothing
   ticks yet; the ladder just becomes real and settable. **Half done**: the
   ladder is real and settable per CHAT, as a ceiling, defaulting to whatever
   the engine was already doing rather than to `inert` — a setting that
   changes a running story the moment it appears is not a setting anyone can
   trust. The per-CHARACTER half, which is the one this document calls the
   opt-in, is still open.
3. **`stochastic` at scene boundaries** — seeded draws against standing
   intentions. No LLM, so the cadence and write-back can be proven cheaply.
4. **`character_agent` ticks** — the villain. Deterministic gate first, then one
   bounded call. Enforce the count cap and the knowledge firewall here.
5. **Reactivation proposal** — gap generator applied at re-contact.
6. **Negotiation** — refusal budgets, tagging, stalemate-eats-canon.

Steps 1–3 are cheap and prove the shape. Step 4 is where the drama lives. Steps
5–6 can trail well behind.

## Open questions

- What promotes a character to `character_agent` — author choice only, or can
  the engine propose it when a dormant character accrues enough standing
  intention weight?
- Does a ticking character accrue **memory** of its off-screen actions, or only
  world consequences? (Memory is the honest answer and the expensive one.)
- How does a tick interact with **frames**? A villain in a past era ticking
  forward is either a paradox source or a very good feature; `paradox.py` should
  probably have an opinion before this ships.
- Should the player be able to *see* the tick log in god-mode? Consistent with
  "omniscience relocated outside the diegesis to the user", the answer is
  probably yes, with a spoiler gate.
