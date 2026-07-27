# Sonder Engine — Design

## What this document is

The architectural record: what the engine is for, what is actually built, what
is partly built, what is not built, and what should be built next.

**The honesty rule.** The previous edition of this file grew past 1,500 lines
and drifted far enough from the code that `CLAUDE.md` had to warn readers to
verify it before trusting it — which made it a liability rather than a
reference. This edition was written by checking claims against source, and it
carries a conformance table precisely so drift becomes visible instead of
buried.

Every "Built" claim below was verified against code, not against another
document. Where verification was partial, it says so. When you change
behaviour, change the status row in the same commit; a row that is wrong is
worse than a row that is missing. The previous edition is in git history.

`AGENTS.md` is the operational guide (edit routing, invariants, workflow).
`docs/PIPELINE.md` is the stage-by-stage execution reference. `docs/DATABASE.md`
is the schema and change checklist. This file is the *why*, the status, and the
roadmap — do not duplicate the other three here.

---

## Thesis

The engine produces long-form interactive fiction by **simulating people and a
world honestly, and letting story be the residue rather than the target**. No
agent is trying to be entertaining.

One layer computes what objectively happens. One computes what each mind could
register of it. One predicts what each person does given their psychology. One
renders the player's slice as prose. Secrets, betrayal, dramatic irony and false
belief are authored nowhere — they fall out of the simulation the moment the
bookkeeping is honest enough to make *absence of knowledge* computable.

The north star is **coherence without omniscience, not realism**. Realism is
expensive and often anti-dramatic. What the engine guarantees is narrower and
more valuable: a world that holds together *and* contains no mind that knows
more than it should. That second property is the soil dramatic irony grows in,
and it is the thing a single context window structurally cannot provide.

The player **is** the protagonist. No agent models the player's interior — the
player's own mind supplies it live, every turn. The engine exists to give that
mind a believable, causally honest, selectively ignorant world to act in, and to
hand the player the dials to shape it.

### The two principles everything else serves

1. **Structure over instruction.** Anything you want guaranteed must be
   *impossible to violate*, not merely instructed against. A prompt cannot
   un-write its own context.
2. **Auditability.** Every numeric change should be event-linked, every
   scheduled effect seeded and logged, every resolution recorded. Silent drift
   is the failure mode being prevented at every layer.

[Structural debt](#structural-debt) is an honest account of where the engine
currently falls short of principle 1. It is the most useful section here.

### What it fixes

Three failures recur in single-model storytelling, and they are one bug: a
single context window where everything is epistemically flat, so the model
conditions on all of it, because that is the only thing a model can do.

- An NPC references a fact it was never told.
- An NPC treats the player's private thought as spoken dialogue.
- An NPC reacts to something that happened while it was not present.

None is a discipline failure a model can be instructed out of, because the
forbidden information is *in the context*. The fix is to never place the
forbidden thing in the slot: **each mind runs in its own context containing only
what it legitimately earned, and a filter decides what crosses.**

---

## Status at a glance

Conformance against the founding architecture, re-verified against source at
alpha5.1.

| Founding commitment | Status | Evidence / gap |
|---|---|---|
| Firewall as plumbing — each mind gets only its perception object | **Built** | `agents/perception.py` emits per-observer views; characters receive their view, never the event stream |
| Two perception passes per turn (onset, outcome) | **Built** | `perception_act` before resolution, `perception_outcome` after |
| Player-leads loop; characters declare blind to each other | **Built** | Plan built from `director_interpret.flow`; character steps run in parallel |
| Memory provenance | **Built, exceeds spec** | Six kinds (`witnessed/heard/told/read/inferred/remembered`) against the specified three, plus `turn_idx`, bound at commit |
| Action visibility posture | **Built** | `visibility` + `conceal_from` + `targets` on every declaration; targets the model leaves empty are bound deterministically, because the seams that ask "does this land on someone?" all read that field |
| Two-store protagonist, never merged | **Built** | `private_voice_setting` appears only in `agents/narration.py` — verified absent from character and perception stages. `shadow_profile` is separate world state |
| Seeded, logged, replayable dice | **Built** | `director_resolve` uses `random.Random("{chat}:{turn}:{nonce}:{actor}:{attempt}")` and records `seed/roll/modifier/dc/outcome/margin` |
| Deterministic scheduling | **Built** | `scheduled_events.seed` written as deterministic strings; `stable_event_key` gives rerun idempotency |
| Per-character temperature | **Built** | `character_temperature(sheet)` passed to the provider call in `agents/character.py` |
| Narrator exemplar pool, event-amnesiac | **Built** | `exemplars` setting read in `agents/narration.py`; narrator receives the player view, not the event stream |
| Tiered cognition | **Built** | Model roles (`default`/`director`/`narrator`/`utility`) plus per-character `simulation.tier` |
| Theory of mind, cached and event-triggered | **Built** | `theory_of_mind.py`; `tom_triggers` on the flow |
| Event-grounded live psychology | **Built** | v4 character schema plus `psychology_runtime.py`: stress split into aversive strain and non-distressing drive, mixed pain/pleasure outside survival with a slow-integrating unresolved `charge`, protected beliefs, learned cue associations, and simulation-time recovery |
| Authored initial outfit with live story attire | **Built** | Character/persona `initial_outfit` is kept separate from stable body appearance and seeds `scene.attire` once; later clothing changes remain mutable story state |
| Checkpoint / rollback | **Built** | `checkpoints.py`; branching depends on it |
| Consolidation, salience-weighted hybrid retrieval | **Built** | `consolidate_character_memory`; keyword + embedding search in `memory.py` |
| Commit as sole persistence boundary | **Built** | `commit.py`; one outer transaction, any domain failure rolls the turn back |
| **Player action absolute** | **Built, then deliberately exceeded** | See [Player authority](#player-authority) — a considered product divergence, not drift |
| **Event-linked stance axes** | **Partial** | `trigger_event_ids` accepted but **optional**; relationships live in a `world` KV blob with no change log |
| **Canon lock** | **Partial** | `lore_entries.canon_locked` is settable via the API and chat-canon entries auto-lock after 20 turns; the specified repeated-reference lock rule is not implemented |
| **Scene-boundary coherence pass** | **Partial** | Validation and dedup exist throughout commit; the specified retcon protocol is not implemented as such |
| **Off-screen world ticks** | **Partial** | Deterministic scheduling and an `offscreen_log` exist; the world advancing meaningfully during absence is narrower than specified |
| **Player authority modes** | **Stub** | `PlayerAuthorityMode` enum exists in `schemas.py` and is **consumed nowhere** |
| **Predictive staging** | **Not built** | No pre-staging of lore or NPCs for likely-next locations |
| **Reactivation negotiation** | **Not built** | No gap-history / delta-summary proposal, refusal caps, or "stalemate eats canon" |
| **Session digest** | **Not built** | No end-of-session synthesis for resume |

---

## The engine as built

### The spine

Information flows one direction, enforced as plumbing rather than prompt:

```
        ┌──────────── player intent (up) ────────────┐
        │                                             ▼
PLAYER → PERCEPTION → CHARACTERS → DIRECTOR → PERCEPTION → NARRATION
(acts)   (filter the  (react,      (resolve   (filter the   & CHARACTERS
         player act)  blind to     to one     resolved      (render/remember)
                      each other)  state)     state)
```

**Eyes severed from hand.** Perception flows *down* to the player through the
narrator; intention flows *up* from the player to the director, never touching
the narrator. In a single model the narrator is both eyes and hand — it
describes the world *and* authors what you do — which is why such systems put
words in your mouth. Here the narrator is downstream of your eyes and has no
access to your hand. It can make you *feel* anything and *do* nothing. That
severance is what makes it safe to give the narrator a lush, interpretive voice:
flavour in the perception channel cannot leak into the action channel.

### Turn shape

Exact stage order lives in `docs/PIPELINE.md`. In brief:

**Opening turn** — `mapping_stage → director_establish → perception_establish →
narrator → commit`

**Normal turn** — `director_interpret → mapping_stage|mapping_quick →
perception_act → [reaction_loop] → [interaction_loop | parallel character:<id>]
→ director_resolve → background_react → perception_outcome → narrator → commit`

Every stage's output is stored as a `steps` row plus an immutable `variants`
row, with exactly one active variant. That dual representation is what makes
reroll, rerun-from-stage, manual editing and inspection possible — and it is why
the engine can be audited at all.

### Ownership

Authority ends sharply. No agent overrules another in-domain.

| Agent | Owns | Must never |
|---|---|---|
| **Director** (`agents/director.py`) | Objective causality: interpreting the declaration, resolving outcomes, the seeded dice | Own character psychology or narration; silently replace the player's declared content |
| **Perception** (`agents/perception.py`) | What each observer legitimately receives. Stateless by requirement | Invent intent, add meaning, contradict the event stream, or leak hidden state. It may subtract and degrade, never add |
| **Character agents** (`agents/character.py`, `agents/loops.py`) | The subjective: what I would attempt, what these signals mean to me | Decide their own success — capability is objective and lives in the world record |
| **Background presence** (`agents/background.py`) | At most one named unregistered presence, one stateless reaction per beat | Hold memory or psychology — that requires promotion to a real character |
| **Narrator** (`agents/narration.py`) | Sentence-level craft, pacing, the player-facing slice | Originate player conduct or reveal unperceived facts |
| **Mapping** (`agents/mapping.py`) | Lore routing, retrieval, canon staging | Know character interiority |
| **`commit.py`** | The sole persistence boundary | Trust model output — it is provisional until deterministic code validates it |

**Perception is stateless by requirement, not thrift.** A perception layer with
memory is a *bug*: remembered context could let last turn's knowledge bleed into
this turn's seeing, the exact leak it exists to prevent. The cheapest agent is
cheap *because* it must be amnesiac.

**Character agents are predictors, not role-players.** Role-play optimises "be
interesting" and volunteers the secret because the reveal is juicy. Prediction
optimises "be accurate", which means it must be free to be *boring* — to let the
coward stay hidden and nothing happen. That freedom is what makes the eventual
drama earned. The cost is that a predictor treats every fact in its context as
true and load-bearing, so context hygiene is non-negotiable.

### Information model

The load-bearing primitive is **provenance**. Humans tag a fact at encoding with
how and when they learned it, and the tag rides along on every later retrieval,
so the access list maintains itself for free. Models flatten all of that the
moment it is in the window. Binding `witnessed/heard/told/read/inferred/
remembered + turn_idx` at commit hand-installs that faculty — so "told to me as
a secret" and "just true" become structurally different stored objects, and
belief revision becomes possible.

Memory layers, per character:

| Layer | Nature | Cadence |
|---|---|---|
| Stable core | Traits with activation/inhibition cues, values, self-image, protected beliefs, coping patterns | Rare, evidence-gated |
| Stance / relationships | Trust, warmth, fear per target | Event-triggered (see [Structural debt](#structural-debt)) |
| Active state | Mood, goals, affect, stress activation/strain/load, independent pain and pleasure, and the unresolved charge they accumulate | Every turn; relaxes using simulation time. Charge outlives the level that built it and discharges only on the character's own declared resolution |
| Learned associations | Cue, appraisal bias, response tendency, strength | Evidence-gated reinforcement/extinction |
| Episodic | Witnessed events, provenance + salience | On commit; consolidated over time |
| Summaries | Autobiographical synthesis | Post-commit; reconstructible |

`affect.py` implements surface/undercurrent/baseline with exponential decay
toward baseline. `psychology_runtime.py` applies the same explicit-time
principle to stress and hedonic carry-over while keeping pain and pleasure as
independent current-event signals: a comforting touch can hurt a bruise and
still feel welcome. Survival vitals can supply a pain floor but are not required.
Stance axes must not erode on a clock; the grudge does not fade unless something
fades it.

### Persistence and source of truth

When representations disagree, resolve deliberately rather than updating every
copy blindly:

1. SQLite rows and `world` keys — durable runtime state
2. Active step variants — the inspectable result of the current turn
3. `PipelineContext` — in-memory working state for one execution
4. Pydantic schemas (`schemas.py`) — accepted structured model output
5. Prompts — desired behaviour, never overriding deterministic validation

**Physical-world authority.** The frame-scoped `world.scene` blob is the sole
runtime authority for live rooms, positions and entity state. `room_registry` is
the sole cross-frame ledger of room identity and retirement. `world_entities` is
a derived projection of the scene commit. `world_placements` is decommissioned;
`fiction_worlds`, `fiction_locations`, and `transit_edges` are deprecated
import-compatibility tables.

**Commit is atomic.** Slow provider work (lore and memory embeddings) happens
*before* the write lock; then all primary turn mutations commit inside one outer
transaction under a per-turn idempotency lock. Any domain failure rolls the whole
turn back. Only autobiographical consolidation runs afterward, because it is a
reconstructible derived cache.

### Cost

Cost scales with **dramatic density, not story length**. Turn 2000 in a quiet
room with two people costs about what turn 2 in that room costs, because nothing
conditions on the 1998 turns between except memory stores that are *reduced and
retrieved against, not replayed*. The hot path is flat; only the backing stores
grow, and they grow cold.

Every agent runs on a reduction, never a log — and the reduction is both cheaper
*and* leak-proof, because the context an agent does not need and the context it
should not have are largely the same context. Statelessness is the default;
persistence is a privilege earned only by agents modelling a continuous self.

---

## Player authority

**This is the engine's largest deliberate divergence from the founding
architecture, and it should be understood as a product decision rather than
drift.**

The founding design gives the player authority over *attempts*: the action you
chose always occurs as chosen, but whether it succeeds belongs to the director,
and facts about the world belong to mapping. This engine went further. It
distinguishes:

- **Contestable declaration** — "I try to take the key", "I lunge toward Mara".
  The motion begins; reactions and circumstance may alter the result.
- **Asserted declaration** — "I take the key", "the door collapses", "three
  hours pass". The effect is treated as *true*, and the director determines its
  consequences rather than whether it happened.

Assertion authority extends to world facts and time, not just the protagonist's
body. `flow.authority_claims` and `flow.scheduled_assertions` carry these
through the pipeline, with narrow carve-outs the director still refuses — most
importantly, a player claim about **another character's interior** is rerouted
to that character as an authorial *offer* it may decline, rather than enacted as
truth. Character agency survives player assertion.

**Why this is defensible.** The founding document's own closing principle is
that the engine is *a world, not a warden* — it "has no opinion on how the user
plays, because having one would mean simulating the taste that is the user's
whole contribution", and explicitly: *"the user can shackle themselves whenever
a story wants it — chosen limits make better play than enforced ones."* An
engine that maximises authorial power by default and offers restriction as an
opt-in is a direct reading of that principle, not a departure from it.

**The cost, stated plainly.** Broad assertion authority weakens the thing the
architecture is otherwise built to guarantee. If the player can assert that the
door collapsed, the world's causal integrity is partly the player's
responsibility rather than the engine's. The firewall still holds — no character
learns anything illegitimately — but "coherence without omniscience" becomes
coherence the player can override.

### Hard mode (planned)

The intended resolution is the mode set already named in `schemas.py`:

| Mode | The player controls |
|---|---|
| `actor_only` | The protagonist's attempts, speech, and immediate bodily conduct. Assertions become *claims* the director adjudicates and may refuse |
| `explicit_outcomes` | The above, plus declared completed effects on the protagonist's own actions |
| `world_author` | The above, plus external events, entities, time, and world assertions (**today's behaviour**) |

`PlayerAuthorityMode` exists as an enum and is consumed nowhere; the vocabulary
is in place and the enforcement is not. Hard mode is `actor_only` with the
director free to say no.

Two design notes worth settling before building it:

1. **A refused assertion must not silently vanish.** The player wrote it for a
   reason. The honest behaviours are to translate it into an attempt ("you reach
   for the key") or to surface the refusal explicitly. Silently dropping player
   text is the one thing the engine's authority contract has never done, and
   hard mode must not become the exception.
2. **Mode is per-chat, not global.** A story is chosen at its start, and the
   dial belongs beside prose pacing and NPC autonomy. Changing it mid-story is
   legitimate but should be recorded, since it changes what earlier turns meant.

---

## Beyond the founding design

Subsystems the original architecture never imagined, now load-bearing:

- **Temporal frames and paradox** (`frames.py`, `paradox.py`,
  `spatial_frames.py`). Alternate eras, travellers, per-frame cast status, fixed
  points, paradox detection. Most `world` keys are frame-scoped; cross-frame
  contracts deliberately are not.
- **Spatial model** (`spatial.py`, `scene.py`). Rooms, adjacency with bearings,
  egocentric frames (ahead/behind/came_from), barriers, hearing and visibility
  gating, zones and carry inference.
- **Deterministic mechanics sweep** (`mechanics.py`). Timed arrivals, expiry,
  dock edges, news latency — LLM-free, seeded, idempotent.
- **Scene backdrops** (`backdrops.py`). Generated images of the room, built from
  a whitelisted spatial projection that structurally excludes occupants. Cached
  per room-plus-visible-state; a branch reads its ancestors' images in place.
- **Lorebook hierarchy** (`memory.py`, `agents/mapping.py`). Nested books,
  inheritance modes, scope by world and location, link graph, canon locking.
- **Multiplayer and guest access** (`guest_access.py`).
- **Obligation ledger, background claims, authored events** — bookkeeping that
  keeps promises and unregistered presences coherent.
- **Import pipeline** (`importers.py`, `character_schema.py`). External card
  formats, heuristic and AI-reinterpreted paths, damaged-sheet repair on read,
  and a non-destructive v3 psychology gap-filler for older cards.
- **Per-story character cards** (`chat_chars.sheet`, `scene.active_cast`).
  Authors can tune an attached character for one story without mutating the
  reusable library resource or resetting that story's earned interior state.
  Names/uids stay fixed because they are identity keys throughout scene,
  recognition, memory, and relationship records.
- **Portable chat archives** (`chat_archive.py`). Versioned, typed export/import
  with embedded resources, reference remapping, and atomic restoration.
- **Portable pipeline traces** (`pipeline_trace.py`). Hash-only diagnostics by
  default, with explicit content-bearing offline replay artifacts.
- **Host authentication routes** (`auth_routes.py`, `guest_access.py`). Typed
  request/cookie transport separated from credential/session persistence.
- **Appearance system** (`static/themes.css`). Browser-local themes, independent
  story-text sizing.
- **Provider layer** (`providers.py`, `prompt_cache.py`, `llm_quality.py`).

---

## Structural debt

The honest account. These are not open bugs; they are places where the engine is
weaker than its own stated principles.

### 1. The positive guarantee is weaker than the negative one

The firewall is excellent at *keeping the forbidden thing out*. It is much
weaker at *making the correct thing reachable and preferred*. Both are supposed
to follow from "structure over instruction"; only the first has really been
internalised.

Two production failures found in one session, both of this shape:

- **A model authored an engine primary key.** The AI import path accepted
  `identity.uid` from model output. `scene.py` falls back to that field for the
  *scene entity id*, so when the model returned the character's own name, every
  import of one card collided into a single scene entity — two characters
  sharing one position, one set of clothes, one owner of the memories. Fixed by
  minting the key in code, which is what structure required from the start.
- **A character could not cite the present.** `observations_used` *instructed*
  the character to cite evidence, in a payload where only memory rows carried
  ids and the current beat was an uncitable prose string. Result: 15 citations
  of a previous turn and zero of the current one across one 61-turn chat — a
  character reliably answering the previous line. The firewall worked perfectly;
  what failed was that the permitted information had no structural affordance
  while the stale information did.

The second fix is itself half-instruction (a prompt rule plus a sentinel id),
which by this document's own standard is the losing move. **The structural fix
is for the current beat to carry a real, first-class event id at declaration
time, like every other observation.** Until then this is debt, not a fix.

**Rule to apply going forward:** whenever a prompt asks a model to prefer X over
Y, check whether the payload makes X *harder to reach* than Y. If it does, the
prompt will lose.

### 2. Stance changes are not auditable

The founding commitment is that every numeric change is event-linked with a
logged trigger. Reality: `apply_relationship_updates` accepts
`trigger_event_ids` but treats them as optional, with explicit handling for "a
routine trigger-less delta". Relationships live in the `world` KV blob, so there
is no change log — only the current value plus a `salient_event` string. There
is no way to answer "why does she distrust him?" from the record.

The founding design also specifies that a normal interaction moves an axis by no
more than ~0.05; the schema clamps at ±0.2.

### 3. Two import paths of very different quality

The heuristic (non-AI) import derives psychology from the card's `personality`
field. A v2 card that puts everything in `description` — common — can still
yield a sparse first pass. The character editor now exposes **Fill psychology
gaps**, which asks for a short account of formative pressures, triggers,
conflicts, coping, sensitivities, and recurring cues, then fills empty v3
psychology fields without replacing authored identity, appearance, goals, or
non-empty psychology. The initial heuristic path still needs better automatic
description fallback and sparse-import warning.

### 4. Documentation forcing functions are uneven

`docs/CODE_MAP.md` is well maintained because `make structure` fails on
staleness. No equivalent exists for hand-written docs, which is how the previous
edition of this file drifted. `docs/DATABASE.md` remains deliberately compact
for a schema with roughly 30 tables and a long migration chain, while
`AGENTS.md` routes every schema change through it.

---

## Roadmap

Ordered by value per unit of risk. Items 1–3 repay the debt above.

### 1. Give the present beat a real event id

Removes the last instruction-shaped patch from the character path. Declarations
already mint ids (`turn:<id>:character:<cid>:<n>:action`); the current beat's
perception should mint one the same way, so `observations_used` cites structure
rather than obeying a sentence. **Closes debt #1.**

### 2. Make stance auditable

Move relationships out of the KV blob into a `relationship_events` table: one
row per delta, with target, axis, magnitude, trigger event id and turn. Keep the
current graph as a derived projection, exactly as `world_entities` is derived
from the scene. Then make `trigger_event_ids` mandatory and tighten the clamp
toward the specified ±0.05. Makes "why does she distrust him?" a query, and the
grudge inspectable rather than merely persistent. **Closes debt #2.**

### 3. Teach the heuristic import to read `description`

No LLM required: fall back to `description` for `self_model.summary` and voice
notes when `personality` is empty, and warn specifically when a heuristic import
lands below a populated-field threshold. The opt-in v3 gap-filler mitigates
sparse old cards but does not remove the value of a better deterministic first
pass. **Closes debt #3.**

### 4. Hard mode — enforce `PlayerAuthorityMode`

Wire the existing enum: per-chat setting, adjudication of assertions in
`director_interpret`, and a refusal path that translates rather than discards
(see [Player authority](#player-authority)). This is the most interesting item
on the list, because it is the one that lets the engine's original thesis be
played *as written* without taking the dial away from anyone who prefers
otherwise.

### 5. Complete automatic canon lock

Age-based locking is built: chat-canon entries older than 20 turns lock
automatically, and locked entries reject in-place mapping updates. Add the
remaining specified rule so facts referenced multiple times lock before the age
threshold. Cheap, and it is what stops long-run lore drift.

### 6. Scene-boundary coherence pass

Established-earlier wins unless the later fact is load-bearing for an active
thread, in which case the older is retconned *with a logged entry*. The logging
is the point: a silent retcon is the failure mode.

### 7. Reactivation negotiation

Design note: [`docs/OFFSCREEN_LIFE_DESIGN.md`](docs/OFFSCREEN_LIFE_DESIGN.md).

The largest unbuilt subsystem, and the one that makes a large cast feel alive
rather than merely stored. It decomposes: gap-history plus delta-summary is the
valuable 80% and is the same generator as roadmap #10; the negotiation protocol
is the hard, novel half and can trail behind it. Mapping proposes the gap; the
character may refuse on integrity grounds only; refusals are capped and tagged
(identity-violation counts half, preference counts full); on exhaustion the last
proposal becomes canon. *Conservative defaults, costly exceptions.*

### 8. Predictive staging

Pre-stage lore and plausible NPCs for likely-next locations. Pure latency win,
no correctness implication, which is why it ranks below the integrity work.

### 9. Session digest

A short end-of-session synthesis that re-anchors on resume. Small, and it
directly addresses the "coming back after a week" experience.

### 10. Richer off-screen life

Design note: [`docs/OFFSCREEN_LIFE_DESIGN.md`](docs/OFFSCREEN_LIFE_DESIGN.md).

Deterministic scheduling exists; what is missing is the world visibly having
moved while you were away. Most of the cast needs no tick at all — the gap is
generated at re-contact, so cost stays `O(re-contact)`. The exception is the
character advancing a plan whose consequences the player meets *before* meeting
them: you cannot lose a race that was never run. `BehaviorController` already
exists in `schemas.py`, unconsumed, and is exactly that opt-in ladder.

### Further ideas, less certain

- **A conformance test for this document.** The status table above is prose. A
  test asserting each "Built" row still resolves to real code — symbol exists,
  module imports, field present — would make this file self-checking, the way
  `make structure` keeps `CODE_MAP.md` honest. Highest-leverage idea here: it
  prevents the exact failure that made this rewrite necessary.
- **A leak-injection suite.** Deliberately plant a forbidden fact in a
  character's world record and assert it never surfaces in that character's
  output across N turns. The firewall is the engine's central claim and is
  currently protected by construction plus targeted tests.
- **Salience-driven personal lore.** "This reminds you of a festival you walked,
  long ago" — fired on genuine resonance, silent otherwise. Fired every beat it
  is a tic; fired rarely and on-key it reads as soul.
- **Per-character retrieval depth** as an explicit dial beside tier and
  temperature — spend deep retrieval only on pivotal beats.
- **Belief-revision salience.** Provenance makes revision *possible*; making the
  moment of revision itself high-salience is what lets a betrayal recontextualise
  forty turns and land as betrayal rather than confusion.
- **Perception prose bound by the audibility layer.** Live data shows perception
  narrating "difficult to parse from this distance" while the deterministic layer
  had already ruled the speech fully audible. The deterministic layer is right;
  the prose should be constrained by it rather than free to contradict it.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| NPC says what it shouldn't | Forbidden fact in its context | Structural firewall: each mind gets only its perception object |
| NPC treats private thought as dialogue | Thought and speech entered the same window | Separate channels: speech → director event; thought → routed nowhere |
| NPC reacts to something it wasn't present for | Presence was a sentence, not a router rule | Perception routes the beat only to minds that were there |
| Narrator mentions what the player can't see | Narrator knows more than the player | Deny the narrator everything but the player's perception object |
| Character answers the *previous* line | Present beat unreachable; only the past was citable | Give the present a first-class id (roadmap #1) |
| Cast feels lifeless, nobody acts | Variance too low | Raise per-character temperature |
| A character is spookily prescient | Context leak | Firewall plus strict character context hygiene |
| World heals — door un-breaks, trap vanishes | Off-screen state dropped | Commit-up plus standing intentions with triggers |
| Secret-in-a-crowd is common knowledge | Visibility posture missing | Overt/concealed plus target on every declaration |
| A character names an act it could only have *felt* | The closed channel cost modality but not resolution — the act's verb crossed into touch as a paraphrase | Sensation crosses, the act's name does not; acuity sharpens detail within its own modality and never buys knowledge of the cause |
| Betrayal reads as confusion | Flat beliefs, no provenance | Provenance tags; revision as high salience |
| Trust silently erodes | Clock-driven numeric drift | Stance axes event-linked; only mood decays |
| Two characters share one position and one set of clothes | A model authored an identity key | Mint engine keys in code; never read them from model output |
| The world cannot tell the player "no" | `world_author` authority by default | Hard mode (roadmap #4) |

---

## Keeping this document honest

1. Change a status row in the same commit that changes the behaviour.
2. Prefer "Partial" with a precise gap over "Built" with a caveat buried in
   prose. The gap sentence is the useful part.
3. When a roadmap item ships, move it into the status table and delete it from
   the roadmap. Do not leave it in both.
4. If this file passes roughly 500 lines, something belongs in `AGENTS.md`,
   `docs/PIPELINE.md` or `docs/DATABASE.md` instead. Length is how the last
   edition died.

---

## In one breath

The player acts; perception filters the act so the present cast can react blind;
the director collapses the player's declaration and all reactions into one
resolved state, dice optional and seeded; perception filters that outcome per
mind; the narrator renders the player's slice — coloured by a voice-setting only
it can see — while each character commits a provenance-tagged, perception-
filtered memory of what it personally registered. The narrator renders
perception and never authors action, because intent runs straight to the
director and never through it. Every mind holds only what it earned.
Statelessness is the default; persistence is reserved for the agents being a
continuous self. No agent authors the story — it is the residue of honest minds
under honest causality. Omniscience exists nowhere inside the world, and only in
the player above it, who may hold as much or as little of it as they choose.
