# 10 — Prior art for a deterministic view composer, and whether to build one

Research note. Two questions: has anyone built a per-observer point-of-view
perception system, and has anyone built a high-quality non-LLM prose composer
driven by world state. Answered against what this engine actually has, with
fresh read-only measurements on `engine.db` (60 chats, 2,296 turns, 9,351
views, 5,570 episodic memory rows). Every measurement below was taken this
session; every literature claim is marked verified or recalled.

---

## 0. Verdict first

**Build the deterministic composer. Move the model off the runtime path and put
it offline, authoring a rule-validated variant bank the composer selects from.
Do not spend the effort on lexical variation — spend it on the discourse-planning
stage the engine has never had.**

Concretely, four commitments:

- **Layer A (`build_percepts`) deterministic**, exactly as note 03 designs it.
  This is where every measured quality win lives.
- **Layer B realises from a template/variant bank, not from a live model.**
  The bank is generated *offline* by a model writing entity-agnostic templates,
  each validated by a rule-based parser before it is committed to the repo
  (the ASPIRO pattern, §10.6 — measured at ~2 BLEU below full fine-tuning and
  +28 BLEURT, with zero training and inspectable, diffable, version-controlled
  output). Runtime selection is deterministic: filter by satisfied
  preconditions → rank by specificity → break ties by least-recently-used →
  seeded random among survivors.
- **Build the missing pipeline stage.** The engine composes online, one
  fragment per event as the event arrives, with no buffering, no aggregation,
  and no memory of what this observer was told last beat. Every serious
  post-mortem in this literature names that, not word choice, as the cause of
  wooden output.
- **Ambient invention moves to the narrator**, which stays a model, is the only
  human-facing surface, and already has its own four-turn prose history for
  register continuity.

The reasoning, in the order that decides it:

1. **Every firewall win comes from Layer A, and none of it requires deleting
   the model.** A model that only ever receives the gated percept list cannot
   leak an unearned identity, because the name is not in its input. The
   measured baseline defects — 3.3% of views carrying unearned identities,
   5.7% self-narration, 93.7% delivered-line recall — are all admission
   failures, all fixed by structured admission, none of them fixed by
   rule-based *rendering*. Note 03 §5 already says the boundary "stops
   depending on N model calls behaving"; that is true of admission, and
   admission is a pure function either way.

2. **The stated blocker — that templates would destroy retrieval — is real but
   misdiagnosed, and I can now say exactly what it is.** Measured on the
   engine's own production embeddings (§2): a hard template with real content
   in the slot is *indistinguishable* from model prose in embedding space.
   The engine's own retired deterministic memory formatter scores mean pairwise
   cosine 0.5331 with **0.0%** near-duplicate collisions; model prose scores
   0.5403 with **0.0%**. The entire 14.7% within-bank collision rate is one
   contentless sentence. Retrieval discrimination tracks CONTENT variety, not
   SURFACE variety. This removes the plan's Phase-3 hard coupling as a *risk*
   (it remains worth doing on its own merits) — and it also removes the plan's
   stated *justification*, which was that the model is already templated. It is
   not: 88.3% of view sentences are hapax within their own bank.

3. **What a rule composer would actually lose is narrower than "prose quality"
   and larger than zero.** No human reads a perception view (§3). The cost is
   not ugliness; it is (a) incidental physical detail the narrator can no
   longer render because the view no longer carries it, and (b) register
   mirroring in character agents. Measured: roughly half the content words in
   a novel view sentence are not in the world model (§4), and the detail the
   owner explicitly wants kept — the swaying tails — is mostly the model
   *re-realising the engine's own contact records in better English* (§5).
   That is a realisation gap, and realisation gaps are exactly what the prior
   art can close — but only partly, and the residue is real.

4. **The monotony objection is aimed at the wrong layer, and the literature is
   unusually unanimous about it** (§10). James Ryan ran precisely the proposed
   fix — hand-writing "several thousand templates" with "stylistic variants for
   most templates" — and reported the output was still "quite repetitive", with
   his own diagnosis being *"there is no reasoning at the level of discourse,
   since events are recounted in an online manner, as they transpire."*
   Ehud Reiter, the field's leading critic of rule-based NLG, does not list
   repetitiveness among its problems at all. And in a controlled ablation
   (STORYBOOK, §8.5), **lexical variation made readers rate the text slightly
   worse**, while removing the discourse history made it statistically
   indistinguishable from no linguistic processing at all. Note 03 §2.6 ranks
   "deterministic lexical variation" as a leverage point; on this evidence it
   is close to the least valuable thing to build.

5. **Keeping a model on the runtime path buys less than it looks and costs a
   specific, measured risk.** On *sparse* inputs — which a perception-scrubbed
   observer view is by definition — the dominant data-to-text error class is
   not getting facts wrong but inventing facts that cannot be checked:
   1.01 NOT_CHECKABLE per output against 0.11 INCORRECT (Kasner & Dušek, ACL
   2024, §10.7). That is Sonder's entire threat model, restated as an
   empirical finding about the class of model being proposed. Meanwhile the
   model is not even a reliable *source* of diversity: post-training
   diversity collapse is determined at training time and cannot be recovered
   by temperature, and structured output narrows it further.

6. **The cost being bought is in the prompt, not the call.** ~7,400 tokens of
   perception rulebook × ~4.06 calls per turn. Moving the model offline
   removes all of it.

**The one experiment that would settle it**, and it should be run before the
build rather than after: replay ~200 beats, render each view three ways
(rules-only, rules + offline variant bank, stored model view), and **score the
downstream consumer, not the prose** — does the character agent ground the same
citations and react to the same facts (`_ground_observation_citations`,
agents/character.py:817), and does the narrator's output survive a blind read.
Note 03 §4 C specifies this as the "expensive tier"; it should be the *first*
tier, because it is the only measurement that discriminates between the options.

**The honest negative, stated up front** (§10.4): the strongest argument
against this branch is not that the prose will be wooden. It is
Wardrip-Fruin's *Tale-Spin effect* — a composer that renders only *outcomes*
produces a surface illusion of system simplicity over a much better
simulation, and readers misdiagnose the engine, not the prose. Sonder's entire
value proposition is a rich hidden layer. The composer must render sensation,
partial knowledge and inference-in-progress, not just what happened. That is
what the design already intends; it is also the thing most easily lost in
implementation, and it deserves to be a stated invariant rather than an
assumption.

---

## 1. What is actually open, stated precisely

`PerceptionOutput.views` is `dict[str, Optional[str]]` (schemas.py:2670) —
**prose is the model's entire contribution**. `observations` are re-derived
from the scrubbed prose; the declared act's rendering is already deleted and
rebuilt from structured data (`_strip_onset_rendering` /
`_inject_onset_sequence`). The channel layer is code:
`hear_level`/`sight_level`/`visual_level_between`/`scent_level`, the light
stack, `entity_arc`, `containment_conceals`, `crossing_visible_from`,
`corridor_sightlines`, `proximity_rel`, all behind one gate `_delivery_ok`;
163 top-level functions in `world/spatial.py`.

So the open problem is **surface realisation from a typed IR, per observer, in
second person** — and any prior-art system must be judged on that, not on its
gating.

Three things make most prior art a partial fit, and they should be stated
before the survey rather than after it:

- **Three consumers, none of them human.** A view is (a) a character agent's
  private context, (b) minted into episodic memory retrieved by embedding
  (commit.py:5510), (c) the narrator's source. Classical IF and MUDs generate
  for a reader. See §3 and §8.
- **The world is generated at runtime.** TADS/Inform quality comes
  overwhelmingly from an author having written "the brass lantern" by hand.
  Sonder's rooms and entities are made during play. See §7 for how much of the
  prior art's quality is actually authored text.
- **The sensory model is finer than the classical systems in some dimensions
  and coarser in others.** See §6.

**A useful counterweight, measured:** the composer is *not* generating from a
bare symbol table. Across live scenes there are 392 rooms, **100% of which
carry a `desc`** (median 363 chars, p90 717), and 536 entities, 88% with a
`description` (median 113 chars) — all produced by the mapping stage, which
keeps its model call. The composer has a prose paragraph per room and a phrase
per object to quote, aggregate and re-anchor. That is a materially better
starting position than "procedural text generator with no lexicon".

---

## 2. Retrieval discrimination: measured, and the plan's reasoning is wrong in
## a way that helps

`search_memories` (memory.py:1719) fuses by RRF over **four** rankings —
semantic (w 1.0), cue-vector (1.15), lexical keyword (1.1), exact phrase/entity
(1.25) — plus one per aspect. It was never purely embedding-based, and the
lexical and exact-phrase legs *reward* stable entity naming, which a composer
is better at than a paraphrasing model.

### 2.1 The global monotony figures overstate the problem by ~3×

| grain | verbatim-duplicated sentence share |
|---|---|
| global (any view, any chat) | 71.5% |
| within one chat | 24.9% |
| within one (chat, observer) bank — the retrieval grain | **11.7%** |
| within bank, excluding engine injector sentences | **8.8%** |

Abbreviation-aware splitter, sentences ≥15 chars; the naive `[.!?]` split used
earlier breaks on "Dr." and inflates counts, but correcting it moves 72.0% →
71.5%, so the headline figure is not a splitter artifact. What it *is*: the
corpus replays the same opening scenario ~12 times across chats. 35,087
duplicate instances are cross-chat-only, and the top cross-chat duplicates are
all establish-turn sentences from repeated dev runs of one alley scene.
Retrieval is keyed `(chat_id, char_id)`; cross-chat duplication cannot touch it.

**88.3% of view sentence instances are hapax within their own bank.** Per
story — the only grain a character or its memory bank ever sees — the model
produces overwhelmingly novel text. Note 06's within-bank verbatim-twin rate of
14.6% (vs 76.7% global) is the same correction at row level.

### 2.2 Templating does not collapse embeddings — contentlessness does

Stored production vectors (`perplexity/pplx-embed-v1-4b`, 2560-d, on 100% of
rows). Within-bank pairwise cosine:

| population | n pairs | mean cos | ≥0.95 |
|---|---|---|---|
| both rows = "You are in an unspecified area." | 9,939 | **0.9817** | **97.3%** |
| neither row is that boilerplate | 69,644 | 0.5403 | **0.0%** |
| all within-bank pairs | 87,100 | 0.5772 | 11.1% |

The entire within-bank collision rate is one sentence: 826 rows across 33
banks, worst bank holding 85 of them.

**The natural experiment.** The engine already shipped a deterministic memory
formatter — the retired `"I chose to attempted <declared act verbatim>"`
template, 1,861 rows still in the bank: a fixed prefix with one content slot.

| population | mean cos | ≥0.95 |
|---|---|---|
| deterministic "I chose to" template family | 0.5331 | **0.0%** |
| model-prose family | 0.5403 | **0.0%** |
| short memories <120 chars (excl. boilerplate) | 0.4668 | 0.0% |
| "You are in \<named room\>" family | 0.7795 | 0.0% |
| consecutive turns, same bank (excl. boilerplate) | 0.5944 | 0.0% |

A hard template with real content in the slot is indistinguishable from model
prose. Even 120-character memories separate cleanly. Consecutive turns in the
same room with the same people separate cleanly.

### 2.3 And the pathology is already the engine's own

`"an unspecified area"` is a literal the engine writes into the per-observer
payload's `room_name` when the observer's position resolves to no room
(agents/perception.py:2362, 2388, 2695, 3422, 3446, 3474); the model
transcribes it. 100% of rooms in live scenes have both a name and a `desc`, so
this is a **position-resolution defect**, not a prose defect, and a composer
inherits it byte-for-byte. Fixing it is independent of this branch and worth
more to retrieval than the entire composer.

**Consequence for the plan.** Phase 3 (mint memory from the IR) stops being a
hard prerequisite that gates the composer, and becomes a good idea on its own
terms. The plan's justification for Phase 2 — "the model's output is already
templated, there is little discrimination to lose" — is wrong at the grain that
matters, and should be replaced by the correct argument: *templating does not
cost retrieval as long as content varies.*

---

## 3. Who reads a view: nobody

`agents/narration.py:646-649` — the narrator's prose source is the **player's**
perception view, plus `event_order`, plus its own previous four turns of prose
(frame-filtered, for rhythm). Every other view goes to a character agent and to
the memory bank. The only place a raw view is displayed is the pipeline
inspector (`static/js/chat.js:962`), a debug panel.

So the register problem is not aesthetic. It is exactly two things:

1. **What the narrator can no longer render.** The narrator cannot describe a
   swaying tail the view did not mention.
2. **Register mirroring in character agents.** Models tend to mirror the
   register of their context. Note 03 §2.7 names this ("character models mirror
   the register of their inputs"); it is asserted, not measured, and it is the
   single most important unmeasured quantity in this branch.

Volume: 2,290 player views (median 1,028 chars) vs 7,061 NPC views (median
678). NPC views are 75% of perception calls — and NPC views are the ones with
no human-facing consequence at all.

---

## 4. How much of the prose is derivable from world state? About 60%.

Content-word coverage of novel (non-quoted) view sentences against the chat's
own scene lexicon (room `name`+`desc`, entity `name`+`description`+`state`,
attire, that chat's character sheets — mean 466 distinct words per chat):

| lexicon | median coverage | ≥0.8 | <0.5 |
|---|---|---|---|
| the chat's own scene + cards | **0.56** | 20.7% | 40.5% |
| control: a random *other* chat's lexicon | 0.20 | 2.7% | 85.0% |

Independently: over 300 random turns, **60.1%** of view sentences share ≥25% of
their content words with that beat's typed data (dialogue quotes + `observable`
surfaces + `state_diff`).

Both are lower bounds (the first uses the final scene blob, not the per-turn
scene, and excludes lore notes and beat events). They converge on: roughly
**60% of the model's sentences are grounded in typed data, and roughly 40% of
its vocabulary is general English it brings itself** — manner adverbs, sensory
adjectives, abstract nouns.

**Sizing the gap.** All view narration is 950,351 tokens over 10,046 word
types; **1,798 types cover 90% of tokens**, most of them entity and room nouns
the world model already supplies. The manner layer specifically is 338 distinct
`-ly` adverbs of which **77 cover 90%** (slightly, faintly, slowly, barely,
gently, softly, briefly, lightly, dimly, firmly, sharply, steadily, brightly,
rhythmically, lazily, weakly, quietly, heavily…). The lexicon a composer must
ship itself is a few hundred entries keyed on typed intensity, motion kind and
fidelity. That is a build, not a research problem.

---

## 5. The incidental detail the owner wants to keep is mostly already typed

5,875 view sentences mention tails; 1,575 distinct forms; 703 hapax and
non-injector. Reading them:

| model sentence (hapax) | what it renders |
|---|---|
| "Her tail is coiled firmly around your calf, a steady weight of warmth and pressure." | one settled surface contact record |
| "Her calf holds the coil of your tail with continuous pressure and shared heat." | the same record from the other party |
| "Her palm keeps sliding against your bare hip in firm, rhythmic pulses of pressure, movement, and friction, while her tail remains coiled around your calf." | one **moving** contact + one **settled** contact, aggregated into a single sentence — and "pressure, movement, and friction" is verbatim `_SENSATION_FORMS[("moving","either")]`, reordered |
| "Her tail drifts lazily, barely touching your thigh." | a light/momentary contact |
| "Her tail, now relaxed, sways gently, and her ears are upright." | pose/state change |
| "Your nine tails bristle behind you, fanning wide, each hair standing on end." | an involuntary **display** — not typed today; exactly the `display` event type Phase 1 proposes |

Two conclusions:

1. **The model is largely re-realising the engine's own injected sensation
   clauses in better English.** Same fact, two renderings:
   - model: `the wool blankets pressing against your cheek`
   - today's `contact_sensation` (spatial.py:4911): `your cheek registers the
     wool blankets against it: steady pressure, weight and shared warmth,
     continuous while the contact holds`

   Four times longer, clinical, one fixed surface per cell (`_SENSATION_FORMS`
   has exactly **two** entries for surface contacts), and it would repeat every
   beat the contact holds. That is the register problem in one line, and the
   information content is identical.

2. **What the model adds on top is aggregation and manner.** Fusing two or
   three contact/state facts into one sentence with a subordinate clause, and
   choosing an adverb the engine has the intensity for but no lexicon to
   express. Both are named stages of the classical NLG pipeline (§9).

### A worked beat (turn 2331, chat 67, idx 50)

Model's player view:

> You are in the dim guest room. The strange slate casts a faint glow on your
> face, the light catching the soft feather clip near your left fox ear. The
> weight of the map settles over you as you collapse onto the straw mattress,
> the wool blankets pressing against your cheek. Your body shakes with violent
> tremors, tears spill unchecked as you bury your face into the wool. A broken
> whisper escapes your lips: "Kaa sama…" The air carries a faint scent of
> lavender and dried herbs, and a soft creak of old timber settles through the
> floorboards.

Typed inputs that beat: `sequence[0].observable` = "begins to weep, body
shaking violently"; `sequence[1]` speech "Kaa sama…" volume=mutter
tone=grief-stricken; room light=dim; a slate entity with `light_source`; attire
(feather clip) and body region (left fox ear); contacts (mattress, blankets,
cheek); room `desc` scent.

Composable: six of seven clauses. Not composable: *"a soft creak of old timber
settles through the floorboards"* — pure ambient invention with nothing behind
it. That is the 40% of §4, made concrete: one sentence per beat.

---

## 6. Where today's Layer B actually stands: string surgery, the classical anti-pattern

The engine already has renderers. They do not realise from a structure; they
patch English strings, and the corpus's ugliest sentences are theirs:

- `_observable_predicate` (common.py:3842) peels the actor's name tokens off a
  model-written surface, guesses predicate-vs-independent-clause by testing
  capitalisation, and glues on a subject. Live artifact:
  `"Cmdr. Vale Maintain eye contact with Vorne without looking away."`
- `_fix_you_agreement` (common.py:3810) re-inflects verbs *after* substituting
  "you" for a third-person subject — by table for copulas, by undoing the
  third-person `-s` otherwise, with a closed list of non-verb `-s` words to
  stop it producing "You alway". This function exists only because the subject
  was swapped in text rather than in a phrase spec.
- `_inject_dialogue` (common.py:3601) carries a comment recording **226
  occurrences across 71 turns** of `"you hear her says"` — a bare-infinitive
  agreement bug that a phrase-spec realiser structurally cannot produce.
- `_unknown_actor_label` (common.py:2115) is referring-expression generation by
  truncation: strip the actor's own name tokens from the appearance summary,
  cut at a linking participle, cap at five words, trim dangling function words.
  It is **not contrastive** — two strangers sharing an appearance head get the
  same label. Live artifact: `"the beautiful young woman appearing reaches
  out…"`.
- `contact_sensation` (spatial.py:4911) is the one genuinely good one: it
  computes number agreement (`_part_is_plural` → register/registers), pronoun
  agreement (it/them), possessive framing, and selects a lexical family from
  (relation_kind, motion_kind, side). And it still has one surface per cell.

**Attribution of the repetition, since this was disputed.** Classifying every
duplicated sentence type by engine-injector signature:

| | share of duplicate mass | share of top-500 types' mass |
|---|---|---|
| model prose | **88.9%** | 69.2% |
| injector: visible-actor (`You see …`) | 3.1% | 11.0% |
| injector: environment (`You are in …`) | 2.8% | 10.9% |
| injector: appearance paste | 2.7% | 3.8% |
| injector: attire paste (`; wearing:`) | 1.9% | 4.8% |
| injector: `contact_sensation` | 0.5% | 0.2% |

The engine's injections dominate the **head** — 30.8% of the most-repeated mass,
and they are the conspicuous ones (`You see A beautiful young woman…` — the
capital A mid-sentence is the string-interpolation tell). They are **11.0% of
the mass**. The bulk of repetition is the model repeating itself across
dev-replayed chats. Both halves of this matter: the ugly head is fixable
independently of the composer, and the tail is not really a defect.


---

## 7. Sense propagation: the strongest prior art, and where Sonder is already ahead

**Strongest system: TADS 3 / adv3.** Nothing else in classical IF is close. But the
useful finding is not that it is sophisticated — it is *what its own author did
with it*.

### 7.1 The architecture, verified from adv3 source

`sense.t` defines `class Sense` with four property slots — `thruProp`,
`sizeProp`, `presenceProp`, `ambienceProp` — instantiated for sight/sound/
smell/touch. Only sight has an `ambienceProp` (`brightness`), because sight
uses *reflected* energy and therefore needs a two-pass calculation (flood
ambient, then compute paths) where the other three need one. Taste is
deliberately absent: "you can taste something if and only if you can touch it."

Five transparency levels, one lattice shared by all senses, from `adv3.h`:
`transparent` (no loss), `distant` (loss of detail from distance), `attenuated`
(energy loss only — tinted glass), `obscured` (detail *and* energy loss — dirty
glass), `opaque`. Materials carry four `xxxThru` values; the library ships
`adventium` (opaque to all — the default material of the universe), `paper`
(sound/smell through), `glass` (sight only), `fineMesh`, `coarseMesh`.

**The consequential decision is that composition collapses:**
`transparent + x → x`, `opaque + x → opaque`, *everything else → opaque* —
"we can't have two levels of attenuation or obscuration without losing all
detail". The payoff is stated in `thing.t`: "there will never be more than a
single obstructor in a path". So `SenseInfo` needs one `obstructor` field and
"you can't see it because of X" always has a unique X. **TADS bought
narratability by throwing away physical fidelity.**

Orthogonal to transparency is per-sense `size` (large/medium/small), giving
three perception tiers rather than two: full detail, detected-but-not-detailed,
absent. `SenseConnector` (a `MultiLoc` mixin) is how sound crosses rooms —
*not* the exit graph; a door that should carry sound must be or contain one.
`DistanceConnector` returns `distant` unconditionally.

### 7.2 The two mechanisms worth taking outright

**`Occluder` — a subtractive final pass.** It registers on a notify list and
runs `finishSensePath` *after* the whole sense table is built, forcing
`tmpTrans_ = opaque` on anything it occludes. The source states the invariant:
"occlusion always takes precedence over 'inclusion' — if an object is occluded
just once, then it won't be in view, no matter how many times it's added back
into view by other connectors." Inform's Scopability extension reaches the same
conclusion from the other end with one line at the lowest visitor level
(`if (item hasnt scopable) return;`).

*Sonder adoption:* Layer A's concealment already subtracts, but the ordering is
not an invariant. Make it one: admission runs, then a single occlusion pass
runs last, and no admission rule may re-add. That is a five-line change to
`build_percepts` and a test.

**`SensoryEmanation.displaySchedule` — edge-sensitive perception.** A
continuous sound or odour carries a list of intervals controlling how often it
re-announces itself; `displayCount` increments per mention and **resets to nil
when the object leaves sense scope**. The source rationale: "When a sound or
odor is continually present without variation for an extended period, it tends
to fade into the background of our awareness."

*Sonder adoption:* this is exactly the mechanism note 03 §2.2 wants for
standing contacts and constant environment, and it is better specified than
"re-stated at intervals or on change". The reset-on-leaving-scope detail is the
part that is easy to miss and matters: a contact that breaks and re-forms
should announce itself again. `contact_sensation` currently has no notion of
how many beats it has been saying the same thing.

**`presence` vs `path` — two axes, not one.** From `sense.t`: "the 'presence'
doesn't have any effect on whether or not an object can be sensed. Only the
sense path matters for that… Presence only determines whether or not an object
is *actively* calling attention to itself." Scope is built from
`sensePresenceList`, not from the sense table.

*Sonder adoption:* Sonder has no such split. Everything admitted is rendered.
Salience-driven omission (the plan's biggest anti-template move) is really the
presence axis, and naming it that way makes it a property of the percept
(`presence: volunteered | available`) rather than an ad-hoc render-time
decision.

### 7.3 Where Sonder is already ahead — plainly

- **Composition.** TADS collapses two obstructions to opaque *by design*.
  Sonder's `hear_level` composes barrier, material shift, volume, proximity
  tier and conduction through an enclosing body and can still return
  `fragment`. Sonder models a chain; TADS refuses to.
- **Knowledge.** TADS 3's default is a **single global flag**:
  `seenProp = &seen`, with the source comment "if anyone's ever seen something,
  then we consider that to mean everyone has seen it." Per-NPC knowledge
  requires inventing a property name per character *on every object in the
  game*. Sonder's per-observer `known` ledger is a different order of thing.
- **Recognition.** TADS has none. A character's `theName` is identical for
  every observer. There is no disguise model.
- **Contact, substance, scale, containment, interoception.** Nothing in the
  survey has these. TADS's touch sense is a boolean that fails at `distant`.

### 7.4 The honest negative, and it is strong

TADS's own author cut this model. Michael J. Roberts, on the Mercury prototype
(tads3.livejournal.com/8607.html, Aug 2012):

> The Adv3 sense model with its partial transparencies and so forth is a huge
> source of Adv3's complexity, and also takes a heck of a lot of computing
> horsepower. I figured if the library is supposed to be lighter weight, this
> is the number one thing to cut in terms of the cost/benefit tradeoff…
> when it came to actual practice, most of the uses for the more advanced
> Adv3 features were essentially special cases anyway.

Eric Eve's adv3Lite shipped that decision — transparency became boolean, and
`SenseRegion` reduced cross-room sensing to per-sense booleans
(`canSeeAcross`/`canHearAcross`/`canSmellAcross`/`canTalkAcross`) with per-sense
size tiers. adv3 itself disables its sense cache during the entire action phase
because "it would be difficult to keep the cache coherent" there.

Lima mudlib made the same trade in the opposite direction *deliberately*:
barrier-modelled sound propagation through the containment tree with per-container
vetoes (`contents_can_hear()` / `environment_can_hear()`), and a scalar for
light, with the design doc saying why — "doing a **good** job of implementing a
complex multi-level light system isn't particularly simple, and in our opinion
adds little to the game."

**Does this condemn Sonder's sense model? No, and the reason matters.** In every
system surveyed the sense model exists to gate *one human player's* interaction,
so a distinction nothing consumes is pure cost. In Sonder it gates what N
independent LLM minds may know, and each distinction is consumed by a mind that
would otherwise act on information it never received. The lesson survives in a
narrower form: **grade the channels that carry dramatic weight and use a boolean
plus an escape hatch elsewhere** — and be suspicious of any graded distinction
you cannot name a beat that turned on.

### 7.5 The one classical mechanism that most directly fixes a known Sonder defect

**Lost Souls' `Message_Alternate`** (closed source, documentation public at
wiki.lostsouls.org). Its `message()` broadcasts an *unrendered descriptor*,
rendered inside each target. The descriptor carries `Message_Senses` — a
bitmask with **role-relative** variants
(`Message_Sense_Visual | Message_Sense_Kinesthetic_For_Source |
Message_Sense_Tactile_For_Participants`; the same event requires a different
sense depending on the observer's role in it) — and `Message_Alternate`, "an
alternate message that may be delivered if the main message cannot be delivered
due to `Message_Senses`. **This is a complete message descriptor in itself**",
recursively, each with its own senses and its own alternate.

*Sonder adoption:* `_surface_translate_event` (agents/perception.py:3079)
currently fails closed by replacing an entire event with one fixed sentence —
the design note calls this "admitted over-redaction". A `Percept` carrying an
`alternate: Percept | None` chain is the correct structure: the visual form,
then the auditory form, then the tactile form, each a full percept with its own
gate. Cheap, and it turns a known over-redaction into graded degradation.

Four unrelated codebases independently converged on *deliver the event,
subtract the attribution*: DikuMUD's `PERS(ch, vict)` (returns `"someone"`
when `CAN_SEE` fails — and because names are **only** obtainable through
`PERS`, it is structurally impossible to write a template that leaks a name
past the gate), Discworld's blindness output, PennMUSH's `full_invis`, and Lost
Souls. That convergence is the strongest single signal in the survey, and it is
the discipline Sonder's Layer A already implements — but *not* structurally:
`_scrub_unknown_identities` is a post-hoc scrub, not an unbypassable accessor.
Making the display label the only route to a name is the same win Diku gets for
free.

### 7.6 Versu — the negative that most directly vindicates the firewall

Richard Evans and Emily Short's Versu is the closest thing to Sonder in ambition,
and it explicitly abandoned per-agent world state. From the extended paper
(versu.com, §8.5, verbatim):

> **The world-state is shared amongst the agents. We do not, for memory reasons,
> give each agent his own separate representation of the world. Instead, we give
> them all access to the one authoritative world model. This means, of course,
> that misunderstandings etc cannot be implemented fully.**

Divergence in Versu lives in *appraisal* — characters interpret the same
observed action differently — never in what reached the mind. And Evans had
built the other thing first: his Brandom-derived social-practice work defines a
per-agent debate state where "one might not have heard an assertion if he
misheard, was out of earshot, or was not paying attention", and traded it away
for memory, under a constraint a Python engine on 2026 hardware does not face.

That is the strongest available argument that the firewall must be the default
rather than a per-fact exception, made by an author who shipped it the other way
and wrote down the cost.

### 7.7 Inform 7 — one idea worth stealing, and a documented refusal

Inform models `A can see B` as `light-where-A ∧ B-in-scope-for-A`, and
`A can hear B` as scope alone. The refusal is explicit (DM4 §24 fn 12):
"Hearing, taste and smell are **not modelled**", with the admitted consequence
(fn 15) that "light never spills over from one room to another". Inform 10.2
finally added audibility — for its dialogue system — and the runtime comment is
"this is the same test as visibility except that it does not require light".

The idea worth stealing is the **`real_location` / `location` invariant**
(`Light.i6t`): one variable is objective truth "whose definition has nothing to
do with light", the other is what the observer may be told; in darkness
`location = thedark`. They are reconciled once per turn against a four-way
transition table (light→light, light→dark, dark→light, dark→dark) with a
*distinct narration hook per transition*, plus a silent variant used at exactly
four points. **Narrate the change, not the state.** That is the salience-driven
omission rule the plan wants, expressed as a state machine rather than a
heuristic, and it generalises to every standing percept Sonder carries.

### 7.8 Licences — the task premise was wrong about TADS

| Component | Licence | Copyable? |
|---|---|---|
| TADS 3 VM, compiler, **adv3** | "TADS 3 Freeware Source Code License" — non-commercial, **derivative works prohibited** except ports | **No.** Read and reimplement. |
| adv3Lite (incl. `query.t`, `facts.t`) | MIT | Yes |
| Inform 7 | Artistic License 2.0 (since Apr 2022) | Yes |
| Inform 6 compiler + library | Dual: original Inform licence or Artistic 2.0 | Yes, via Artistic |
| Evennia core (`funcparser.py`, `rpsystem`) | BSD 3-Clause | Yes |
| Evennia `utils/verb_conjugation/` | **GPL-2** (dir-local licence + file header) | Only under GPL-2 |
| DikuMUD / CircleMUD / tbaMUD | Proprietary; must notify authors before publishing *or hosting* | **No** |
| LDMud driver | BSD-2 **plus** a non-commercial restriction — not OSI-open | **No** |
| Discworld mudlib, Lost Souls | Non-commercial / closed | **No** — spec only |
| Curveship (original Python) | **ISC** | **Yes** |
| curveship-js | GPL-3.0 | Only under GPL-3 |
| Ensemble / CiF | BSD-**4**-Clause with advertising clause | Technically, with burden |
| Talk of the Town | MIT — **but the belief layer is not in the repo** | Yes, for what's there |

The practically reusable code is Curveship (ISC), adv3Lite (MIT), Inform
(Artistic 2.0), and Evennia's BSD-3 modules. Everything from TADS 3 proper and
the Diku/LP/Discworld/Lost Souls lineages must be reimplemented from the
mechanism with the lineage credited in prose — which is cheap, because each of
these mechanisms is a few dozen lines.

---

## 8. Focalisation: Curveship is the architecture, and its firewall is better than its prose

**Strongest system for prose composition from a per-observer world model: Curveship.**
Not close. It is also the only one that is runnable, permissively licensed (ISC),
and architecturally isomorphic to what Sonder is building.

Versions: Curveship-py 0.5 (2011, Python 2) and 0.6.01 (2019–20, Python 3,
https://nickm.com/curveship/curveship-py-0601.zip). The successor curveship-js
(GPL-3.0) is a **deliberate regression** — its own README says it "does only
trivial referring expression generation (noun phrases only) and produces stock
sentences from templates". Study curveship-py.

### 8.1 The architecture, and why it is the same architecture

`world_model.py` splits `World` (the IF Actual World, authoritative, written
only by the Simulator) from `Concept` — docstring verbatim: *"An Actor's theory
or model of the World, which can be used in telling."* One Concept per actor,
plus one for `@cosmos`. `World.set_concepts()` builds each by deep-copying only
what that actor can see; thereafter `Action.do()` propagates per action:

```python
for actor in world.concept:
    if (actor == self.agent or world.can_see(actor, self.agent) or
        (hasattr(self, 'direct') and world.can_see(actor, self.direct))):
        aware.add(actor)
for actor in aware:
    world.concept[actor].act[self.id] = copy.deepcopy(self)
world.act[self.id] = self
```

That is `_observer_scene_payload` plus per-event admission, in 2011. Two details
Sonder should note:

- **Perception folds into the simulation loop per action, not per turn.**
  Montfort argues it explicitly (dissertation §5.2.1) so that "actors are
  represented as perceiving what is happening *during* a turn". Sonder's
  three-pass structure (establish/act/outcome) is the same instinct.
- **`@cosmos` is an Actor with a Concept**, so omniscient narration is just
  `spin['focalizer'] = '@cosmos'`. **This is the single best cheap idea in the
  survey for Sonder**: make the omniscient view a *composer configuration*, not
  a separate path, and every firewall leak becomes testable by **diffing two
  composer runs over one event log**. Sonder currently tests leaks by regex over
  prose.

The whole generator is three lines:

```python
reply_plan = reply_planner.plan(id_list, concept, discourse)   # content + order
section    = microplanner.specify(reply_plan, concept, discourse)  # tense, templates
output     = section.realize(concept, discourse)               # morphology, REG
```

1,466 lines of narrating logic plus a 1,023-entry irregular-verb table; 1,718
lines of world/knowledge model. That is the scale of the thing Sonder is
considering.

### 8.2 The spin dict — verified in full from `discourse_model.py`

```python
SPIN_DEFAULTS = {
    'dynamic': True, 'focalizer': '@focalizer', 'commanded': '@commanded',
    'narratee': '@focalizer', 'narrator': None,
    'order': 'chronicle',        # | retrograde | achrony | analepsis | syllepsis
    'speed': .75, 'frequency': [('default', 'singulative')],
    'time': 'during',            # before | during | after -> future/present/past
    'window': 'current', 'progressive': False, 'perfect': False,
    'time_words': False, 'room_name_headings': True, 'known_directions': False,
    'template_filter': None, 'sentence_filter': None, 'paragraph_filter': None,
}
```

**`narratee = '@focalizer'` is what makes Curveship second-person by default** —
precisely Sonder's target configuration. `spin/told_and_focalized_by_guard.py`
is the whole file: `{'narrator': '@guard', 'narratee': '@teller', 'focalizer':
'@guard', 'time': 'after'}`.

*Sonder adoption:* make `render_view`'s second argument a flat spin dict rather
than a bare `style_seed`. It keeps the function pure, makes every narratological
choice a named testable parameter instead of an emergent property of prompt
text, and it is what lets the same composer later render a flashback, a
memory-mint (past tense, first person — which Phase 3 needs anyway) and a view
from one code path. `render_episode(percepts)` in the plan is really
`render_view(percepts, spin={'narrator': self, 'narratee': None, 'time':
'after'})`.

### 8.3 The realiser — the borrowable core

`realizer.py` (850 lines) parses slot templates `[head/mods/kind]` into typed
Word objects. Kinds: `s` subject Noun, `o` object Noun, `a` Adjective, `v` Verb,
`here/now/this/these` Deictic; `[x's]` possessive; verb mods `ing` progressive,
`ed` anterior, `not`, `do` intensive, `1`/`2` number; noun mod `pro`.

`Verb.realize()` computes **person** (1 if the sole subject is the narrator, 2
if the narratee, else 3), **number** from the subject item, then indexes two
73-entry tables via `i = 24*person - 23; +8 past; +16 future; +2 progressive;
+4 perfect; +1 plural`, with regular morphology helpers falling back to the
1,023-entry irregular table.

`Noun.realize()`: `tag == '*'` → `discourse.spin['focalizer']`; tag equals
narrator or narratee → pronominalise; tag already a subject and in object
position → reflexive; otherwise `item.noun_phrase(discourse)` with
`discourse.givens` driving `a` → `the`. Unknown referent → the literal string
`'something'`.

`Deictic.realize()` swaps `now/then`, `here/there`, `this/that`, `these/those`
on `tense_rs == 'present'`.

Tense is derived, not hardcoded — Reichenbach (1947), ~15 lines:

```python
def determine_tense(event, ref, speech):
    tense_er = 'anterior' if event < ref else 'simple' if event == ref else 'posterior'
    tense_rs = 'past' if ref < speech else 'present' if ref == speech else 'future'
```

**This is the direct answer to Sonder's §6 string-surgery problem.** Set
`narratee = observer` and every reference to the observer becomes "you" with
correct agreement *by construction* — `_self_second_person`,
`_fix_you_agreement`, `_observable_predicate`'s capitalisation guess, and the
226-occurrence "you hear her says" bug all cease to be possible. Deictic
shifting is ten more lines and is the difference between prose that survives
retelling into memory and prose that does not.

**And Sonder already has the template.** Curveship's authored
`template='[agent/s] [shoot/v] [direct/o] in the chest'` is exactly what the
Director's `observable` field is — written per beat by a model instead of per
verb by a human. Marking its agent slot, or emitting
`{verb, object, modifiers}` alongside it, buys the whole transformation. That is
the highest-leverage single change in this report.

Cost of adopting: the irregular-verb table and the two 73-entry tense tables are
ISC and portable verbatim. Realistically ~600–900 lines of Python for
morphology + slot parsing + person/number/tense, which is smaller than the
twelve repair passes it replaces.

### 8.4 What it actually produces — real output, and the honest verdict

Four focalisations of one 20-action event log (`fiction/robbery.py`),
generated by running the system:

*Zero focalisation (`@cosmos`)* — ground truth, all 20 actions:
> The bank teller reads some deposit slips. / The burly guard is snoozing. /
> The twitchy man puts on a Dora the Explorer mask. / … / The burly guard shoots
> the twitchy man in the chest.

*Focalised on the robber* — the teller's desk work and the guard's snooze are
gone; the fake money (low prominence, seen across a room-view) is `something`;
the not-yet-known guard renders with a blanked agent:
> The twitchy man brandishes a gun-shaped object at the bank teller. / The bank
> teller laughs. / **Something sees the twitchy man.** / The bank teller puts
> **something** in the black bag.

*Same guard focalisation, `narrator: '@guard'`, `narratee: '@teller'`,
`time: 'after'`* — one flat dict change turns it first-person past with the
teller as "you":
> I was snoozing. / The twitchy man brandished a gun-shaped object at you. /
> I woke. / … / I shot the twitchy man in the chest.

*The most on-point artefact*: in `cplus.py` with `commanded = '@person'` (the
player character) but `focalizer = narratee = '@mime'` (a bystander), the player
walks west and manipulates a lamp, and the prose is **second person for the
mime**:
> `[> w`  You wave. The operagoer heads west.
> `[> turn the lamp on`  You wave.
> `[> e`  **Nothing special happened.**

A pure per-observer projection driving second-person prose, in a running
program, from 2011. `"Nothing special happened."` is `microplanner.acknowledge()`
— the deterministic fallback for an empty observer slice. Sonder returns `None`
here, which is better.

**The honest defects, all instructive:**

- **No third-person pronominalisation.** Pronouns fire *only* for narrator,
  narratee, and reflexives. `discourse.givens` drives article choice and never
  pronoun choice, and it never decays. Third-person retelling degenerates:
  "The operagoer headed east. The operagoer examined the foyer. The operagoer
  was unable to pick the hook up because the operagoer was not able to detach
  the hook." Montfort's own `NEXT_STEPS` lists pronoun resolution as unfinished.
  **This is a discourse-history defect, not a firewall defect** — and it is
  exactly the defect Sonder's `described_this_pass` referent tracker would have.
- **No sentence aggregation at all.** `Paragraph.merge()` exists and is never
  called. One paragraph per event. That is the machine-gun rhythm in every
  sample above, and it is the single biggest register cost.
- **Not deterministic.** Unseeded `random.choice` in `prepend_any_time_words()`,
  `microplanner.select()` and `Item.noun_phrase()`; two runs of the same fiction
  with the same spin differ. Trivially fixable — seed on `(event_id, spin_hash)`
  — but it means the released system is a *parametric* composer, not a
  deterministic one. Sonder's seeding discipline (`_untargeted_order`) is
  already better.
- **Several advertised features are stubs**: `order: 'syllepsis'` is
  byte-identical to `chronicle`; the `iterative` frequency branch is
  unreachable; `noun_phrase(length=...)` is never passed a non-zero length, so
  authored parenthesised adjectives are dead; analepsis emits hardcoded
  commentary ("Ah, let's remember …") and flashes back to the event it just
  narrated.
- **A real information leak of exactly the class Sonder audits for.**
  `Action.do()` grants awareness if the observer can see the agent **or the
  direct object**. So the guard's `Sense('see', '@guard', direct='@robber')`
  lands in the *teller's* Concept — she can see the robber, therefore she
  "learns" that an unseen entity perceived him. It renders as
  `"Something sees the twitchy man."` **A perception rule that grants awareness
  of an event because you can see its object is an engine failure, and Sonder
  should carry a regression test for it.** Check `_source_channels` and
  `_delivery_ok` against the case: does observing a target grant a channel to a
  *sensing* event performed on that target?

**Montfort's own evaluation is negative-ish and honest** (dissertation ch. 10):
two annotators, 14 texts, naturalness 1–10, agreement weak (r = 0.46, p = 0.1).
Highest-rated texts were human-authored IF; the system's chronological output
landed mid-pack — **tied with a cut-up rearrangement of human-authored
Anchorhead**. Both annotators rated retrograde tellings worst and "found the
retrograde narratives particularly difficult and unpleasant to read". Key
negative: *"using time words, by itself, does not help much in making a
randomly-ordered list of events sound natural."*

**Why it never took off**, mostly in his own words: no creative work was ever
made with it (*"The major limitation of the work done so far is that it does not
include the development of more original creative work"*); no documentation
(README: *"There is not a manual or other extensive documentation"*); ported IF
cannot use the feature; the shipped 0.6.1 zip crashes on launch (missing `logs/`
directory, `terminal_size()` needs a TTY). And one architectural self-criticism
Sonder should heed (§11.1): descriptive text hangs on **the thing seen, not the
seer**, which *"does encourage IF authors to write games in which all narrators
'see' existents in the same way."* Hang appearance on the projection.

### 8.5 STORYBOOK — the prose-quality ceiling, and the one controlled result in this literature

Callaway & Lester's STORYBOOK (IJCAI-01) produces by a wide margin the best
symbolic narrative prose in this literature, 25 years ago:

> Once upon a time, a woodcutter and his wife lived in a small cottage. The
> woodcutter and his wife had a young daughter, whom everyone called Little Red
> Riding Hood. She was a merry little maid, and all day long she went singing
> about the house.

It has **no focalisation and no knowledge model** — point of view is two input
lines. Its quality is bought with a hand-built ~200-state FSA producing exactly
two stories over a hand-authored ontology of ~500 concepts, at 45–90 s per
story, with much of the stylistic decision already made in the input. Read it as
evidence that *a deep pipeline preserves authored quality at scale*, not that a
generator invents quality. No code release, no licence.

**What is decisive is its ablation.** Five versions (full / no revision / no
lexical choice / no discourse history / neither), 20 readers, 8 per version,
graded on nine factors, mixed-procedure ANOVA. Result: **{full, no-lexical} ≫
{no-revision} ≫ {no-discourse-history, none}**, p < 0.001 combined, and
no-discourse-history was **statistically indistinguishable from no linguistic
processing at all**.

Two consequences for Sonder, and they point in opposite directions from the plan:

1. **The discourse history is the highest-value component in this entire
   survey**, and it is the one with a controlled result behind it. Its four
   fields per referent: `frequency`, `last_usage`, `recency` (distinct
   intervening referents, **counted within gender** so the pronoun-ambiguity
   test falls out of the same integer), `distance` (scenes/paragraphs/turns).
   The ablation excerpt shows exactly what its absence produces:
   *"Little Red Riding Hood had not gone far when Little Red Riding Hood met
   the wolf. 'Hello,' greeted the wolf, who was **the** cunning looking
   creature. The wolf asked, 'Where is Little Red Riding Hood going?'"* —
   both definiteness and pronominalisation broken. That is what Sonder's
   composer emits without one.
2. **Lexical choice made the text slightly WORSE.** The no-lexical-variation
   version was mildly preferred; readers found the increased variety harder to
   read. This is a direct empirical strike against note 03 §2.6's
   "deterministic lexical variation" as a leverage point, and it agrees with my
   own measurement (§2.2) that surface variation buys nothing in embedding
   space. **Build the referent tracker; do not build the synonym wheel.**

The variation mechanism that *is* worth keeping is the one nobody else has:
**thematic-role reordering** ("X gives Y the cookies" / "Y receives the cookies
from X"), which varies sentence shape without varying diction, and so does not
incur the cost that sank the lexical version.

### 8.6 Referring expressions: the one mechanism that is leak-proof by construction

Sonder's `_unknown_actor_label` is truncation, and it measurably fails
(§10.3 below). The prior art has two better answers.

**Expressionist** (James Ryan, UCSC, **MIT**, github.com/james-owen-ryan/expressionist)
is a probabilistic CFG whose nonterminals carry author-defined tagsets,
including *Preconditions* — raw predicates over game state — with markup
inherited up the derivation. The shipped Talk of the Town grammar contains a
**precondition-gated referring-expression ladder**, three sibling nonterminals:

```
"...when you do not know their name":     -> "A person whose name I don't know."
"...when you know their first name only": -> "named [[preoccupation first name]]"
"...when you know their last name only":  -> "with the last name [[...]]"
```

plus provenance-gated hedging — a name that arrived by hearsay licenses a
trailing `", is it?"`:

```json
{"expansion": ["[[Greeting word]]", ". ",
               "[speaker.belief(interlocutor, 'first name')]", ", is it?"]}
```
→ `"Hello. Marta, is it?"`

*This is the mechanism by which one event log becomes different prose per
observer, and it is leak-proof by construction*: the naming branch is
unreachable when the belief is absent, so the composer **cannot** emit "Marta"
for an observer who has not earned it. It is the structural version of what
Sonder enforces today with `_scrub_unknown_identities` after the fact.

The repo also contains **Reductionist**, the inverse parser: given surface text,
recover the derivation and its markup. That is a free test oracle for a
firewall — parse the composed view, read off which belief preconditions were
required, assert the observer holds them all.

**Dale & Reiter's Incremental Algorithm** (the standard REG reference) supplies
the piece both Curveship and `_unknown_actor_label` lack: a **contrast set**.
Iterate attributes in a fixed preference order, add an attribute only if it
rules out at least one remaining distractor, stop when the distractor set is
empty. Applied to Sonder: the distractor set is the other unrecognised bodies
the observer can currently perceive; attributes come from the appearance summary
already parsed. It fixes both measured failures at once — the 15.6% collision
rate (two strangers get the same label) *and* the truncation garbage
("the lean man in his late"), because attributes are selected as units rather
than sliced at a word count.

### 8.7 Two gaps nobody in this literature filled

1. **Nobody models the narratee's knowledge as distinct from the focaliser's.**
   Montfort names it and does not build it: *"The interactor's knowledge … is
   considered to be separate from the knowledge of the player character. The
   currently implemented Discourse Model is rather vestigial."* For dramatic
   irony — reader knows, character does not — this is the missing layer, and it
   is Sonder's natural extension, because the reader is just another observer
   with its own accumulation policy and the narrator already has its own inputs.
2. **Nobody builds intermediate focalisation** — a narrator who knows the union
   of two characters' perceptions, or one character's perceptions plus a
   privileged fact. Montfort: *"It would be possible to construct other
   Focalizer Worlds that correspond to sets of actors … although this has not
   yet been undertaken."* It falls out for free if focalisers are first-class
   objects rather than flags, which they would be in a `spin` dict.

---

## 9. Aggregation: the solved craft, and the ten rules worth taking

Roguelikes are the only body of work that has *actually shipped* deterministic
multi-event composition to millions of readers. **Strongest system: Angband's
`src/mon-msg.c`**, with Brogue CE second and DCSS third. All three were read
from source.

The framing that makes them comparable: every one is an ad-hoc implementation of
Reiter & Dale's pipeline — content determination → document structuring →
aggregation → lexical choice → REG → realisation — and **none does all six
well**. The gap Sonder can exploit is stated most simply as: *every one of these
systems aggregates on rendered strings, or at best on `(type, text)` pairs.*
Sonder has typed events and a per-observer projection at the point of
composition, so it can group by actor, by verb class and by causal chain, and
elide shared subjects. Those three are exactly what none of them can do, and
their absence is the entire diagnosis of Dwarf Fortress.

### 9.1 The ten rules

**R1 — Aggregate within a beat, not against the previous line.** Brogue's
collapse window is the whole current turn (`archiveEntry->turn ==
rogue.playerTurnNumber`, `IO.c:3466`); Angband's buffer is turn-scoped. DCSS,
NetHack and Dwarf Fortress compare only against the immediately previous
message, and are visibly worse for it — DF's ten consecutive
`You strangle The Cougar's throat!` lines survived its own repeat-collapser
because intervening events broke the run. Sonder composes a whole beat at once,
so it gets the wide window for free.

**R2 — Group by (type, visibility-flags), never by type alone.** Angband's stack
key includes `OFFSCREEN|INVISIBLE`, so a seen orc and an unseen orc can never
merge into one sentence. **Aggregation must not launder an information
boundary.** This is the single most firewall-load-bearing rule in the survey,
and it is not in note 03's `dedupe_key` design — a `dedupe_key` that ignores
fidelity would merge a `full` percept with a `fragment` one.

**R3 — Degrade the aggregate to the weakest channel among its members.**
Angband's `get_subject()`: unique → bare name; seen singular → `"The %s"`; seen
plural → `"%d %s"`; **unseen singular → `"It"`; unseen plural → `"%d monsters"`
— the species is dropped entirely.** R2 guarantees members are uniform, so this
is well-defined.

**R4 — Collapse identical events into a count, do not drop them.** `(x3)` /
`(many)` [Brogue], ` x3` [DCSS, CDDA], ` <3x>` [Angband]. NetHack alone drops,
and its own source flags the resulting bug. For Sonder this preserves honest
cardinality in a memory: "the door rattles three times" is a different episode
from "the door rattles".

**R5 — De-duplicate per (individual, event-code) *before* aggregating by type.**
Angband's `redundant_monster_message()` over a 400-entry per-turn history stops
"the orc is hurt. the orc is hurt." from two damage sources in one beat.
Sonder's twelve repair passes include four dedupe passes
(`_dedupe_view_sentences`, `_action_already_rendered`, `_contact_already_felt`,
`_authored_detail_already_present`) doing this *on prose*. Doing it on the IR is
one dictionary.

**R6 — Order by narrative role, not simulation order.** Brogue buffers combat
text purely so the player's blow precedes the monster's, with the reason in a
comment: *"otherwise player combat messages appear after monsters, rather than
before."* Angband runs three explicit passes over a delay tier so **deaths are
narrated last, unconditionally**:

```c
static int what_delay(int msg_code, int delay) {
    if (msg_code == MON_MSG_DIE || msg_code == MON_MSG_DESTROYED) return 2;
    else return delay ? 1 : 0;
}
```

A three-line discourse planner. DCSS shipped a bug fix for exactly this class
("The dart killed the bloat" must precede the bursting message). Sonder's plan
orders groups by `(suddenness, salience)` with chronology authoritative inside
the event chain; adding an integer discourse tier per percept kind is cheaper
and more predictable than a salience float.

**R7 — Cap the number of groups; collapse to a coarser taxonomy,
most-populous first.** DCSS's `_genus_factoring()` with `max_types = 4`:
repeatedly find the most-represented genus, collapse its species into one group
("4 orcs" replacing an orc warrior, two orc priests and an orc), bail when the
top genus has one member. Renders as
`"a hydra, 2 liches and an orc come into view."` **And never merge individuals
with proper names** — the source comment is *"Don't merge named monsters (ghosts
and the like). They're exciting!"* Sonder's analogue is crowds and background
presences; `world/crowds.py` exists and this is the rule it wants.

**R8 — N=1 and N>1 want different sentences AND different detail passes.**
DCSS emits the individual message verbatim for N=1 and a condensed list
otherwise, and *suppresses* its equipment-warning pass when N=1 because it is
redundant there. A detail pass that is useful for one item is noise for a list.

**R9 — A per-beat "already said this class of thing" latch.**
`rogue.heardCombatThisTurn` (declared with its own spec comment in `Rogue.h`,
reset in `playerTurnEnded()`) means the player gets at most one
`"you hear combat in the distance"` per turn. Same pattern for dungeon features
(`resetDFMessageEligibility()`) and NetHack's `dosounds()` returning after the
first ambient hit. **Two lines each, removes a whole category of spam.** This is
the mechanism that keeps Sonder's standing-contact and ambient percepts from
firing every beat, and it is simpler than the interval schedule.

**R10 — Separate "logged" from "shown".** NetHack dumplogs *before* filtering
and documents why; CDDA's cooldown hides a message from the sidebar without
removing it from the log; DF's `A_D`/`D_D` are different channels. **For Sonder
this is the memory/view split**: the episode may record what the view omits for
restraint, *provided* the episode never exceeds the percepts' fidelity. That is
a cleaner statement of note 03 §5's rule 2 than "same fidelity-degraded surface
forms".

### 9.2 Two rules that bear directly on known Sonder defects

**Put the visibility check *inside* the referring-expression function, as an
early return.** DCSS's `_mon_special_name()` (`monster.cc:2117`):

```cpp
if (!force_seen && !mon.observable() && !you.aware_of(mon)) {
    switch (desc) {
    case DESC_THE: case DESC_A: case DESC_PLAIN: case DESC_YOUR: return "something";
    case DESC_ITS: return "something's";
    ...
```

Every `monster::name()` routes through it; there is no code path that prints the
real name of an unobserved monster. DikuMUD gets the same guarantee because
names are obtainable *only* through `PERS(ch, vict)`. NetHack's `x_monnam()`
returns immediately on the unseen branch so no adjective can be appended
afterwards.

Sonder currently gets this property by **scrubbing composed prose**
(`_scrub_unknown_identities`), which is why the measured floor-era leak rate is
3.3% rather than zero. Layer A choosing the label at admission is the right fix
and the plan already says so — the sharper version is: **make the display label
the only accessor**, so no renderer can reach a canonical name at all. That is a
type-level guarantee, testable by grepping the renderer for roster access.

**Read gender only when pronominalisation is permitted.** Angband guards its
24-case `(gender × case)` switch behind
`use_pronoun = (seen && PRO_VIS) || (!seen && PRO_HID)`; Brogue forces neuter
gender 4 when the monster is unseen, so the pronoun cannot leak sex. DikuMUD is
the counter-example and has the bug: `$e/$s/$m` read `GET_SEX` with no
`CAN_SEE` check, so *"Someone draws his sword"* leaks the actor's gender.
**Sonder should check this today**: does an unrecognised actor's percept ever
carry a gendered pronoun derived from the sheet? `_unknown_actor_label` strips
name tokens but the surrounding renderers do not obviously strip pronouns.

### 9.3 Realisation details worth copying verbatim

- **Choose the article after the noun phrase exists.** NetHack's `just_an()` and
  DCSS's `article_a()` inspect the actual leading token; a proper name
  suppresses the article *unless an adjective intervened*; a unique upgrades
  a→the; "your" is relational (ally ⇒ *your*, else *the*). DCSS's
  `thing_do_grammar()` additionally downgrades to `DESC_PLAIN` when the string
  already begins with the/a/an/some. Sonder's `_appearance_as_prose` does
  article surgery with regexes and produces
  `"You see A beautiful young woman…"` — capital A mid-sentence — 700+ times.
- **Inline `[singular|plural]` markup expanded by a ~20-line state machine with
  an assert on malformed templates** (Angband):
  `MON_MSG(FREEZE_SHATTER, MSG_KILL, false, "freeze[s] and shatter[s]!")`,
  `MON_MSG(MORIA_DEATH, ..., "You hear [a|several] scream[|s] of agony!")`.
  Sonder has exactly this problem in `contact_sensation`'s `_part_is_plural`
  branching, solved ad hoc per site.
- **Discretise continuous quantities into a small named ladder, then pick the
  wording by ontology.** DCSS maps HP fraction to six bands →
  `almost dead|severely|heavily|moderately|lightly|not`, then chooses
  `damaged` vs `wounded` by whether the creature is living. Damage →
  `. ! !! !!!`. To-hit margin → `barely / closely / (nothing) / completely`.
  **This is the manner-adverb lexicon Sonder needs (§4), and the shape is:
  band the continuous value, then cross it with an ontology axis.** Do not let
  a small ladder carry a continuous simulation alone — that is Dwarf Fortress's
  six-verb problem.
- **Budget-aware referring expressions**: Brogue's `describedItemName(item, buf,
  DCOLS - strlen(buf))` tries the detailed name and falls back to the terse one
  when the rest of the already-assembled sentence has eaten the budget.
- **If you randomise wording, use a separate seeded stream.** Brogue has
  `RNG_SUBSTANTIVE` and `RNG_COSMETIC` with `assureCosmeticRNG`/`restoreRNG`
  around every presentation-time draw; Caves of Qud derives seven named streams
  by hashing `world_seed + name`. Sonder's `_untargeted_order` discipline is
  already this; extend it to the composer and key on event identity so the same
  event always words itself the same way.
- **Loud failure, not silent empties.** Qud emits
  `<undefined entity property X>` into the prose; DCSS emits
  `"NO PLURAL HANDS"` and `"buggy unseen surface"`. Given CLAUDE.md's warning
  about fields that fail invisibly, a composer that cannot render a legitimately
  perceived percept should emit a visible diagnostic or raise — never paraphrase
  around the gap.

### 9.4 The best per-observer emit API found anywhere: Cataclysm-DDA

`src/creature.h:1008` documents a contract that resolves person *and* visibility
by dispatch, so the call site cannot get either wrong:

```cpp
// add_msg_if_player      - only printed for avatar, not NPCs/monsters
// add_msg_if_npc         - only printed for NPCs, not players/monsters
// add_msg_player_or_npc  - printed for avatar or NPC, not monsters
add_msg_player_or_npc( _("You open the door."), _("<npcname> opens the door.") );
```

Base `Creature` methods are `{}` — **monsters produce silence**. `Character`
takes the player string unconditionally. `npc` takes the NPC string, substitutes
the name, and gates on `add_msg_if_player_sees(*this, …)`. One line at the call
site yields second person for the player, third person for a *seen* NPC, and
nothing for an unseen one.

Generalised, that is precisely Sonder's target signature:
`emit(percept, observer) -> Optional[str]`, with the template carrying a
second-person and a third-person variant and the projection selecting. DCSS's
`simple_monster_message()` adds the other half of the contract — **the emitter
returns a bool saying whether anything was actually said**, so the caller can
emit a degraded alternative. Combine the two and you have Lost Souls'
`Message_Alternate` chain with a Python-shaped API.

### 9.5 Dwarf Fortress: the negative example, diagnosed precisely

DF's combat log is the canonical wooden deterministic narration, and the causes
are specific:

- The determiner slot is **exactly three-valued** (`You` / `The ` / `Your`) with
  no pronoun inventory; the severity ladder is **six verbs** (tearing, tearing
  apart, shattering, fracturing, denting, bruising); quantity qualifiers are
  four; clause joining is two literals. **The string `badly` appears zero times
  in the 318 KB string dump — there are no adverbial intensifiers at all.**
- Agreement is resolved **by enumeration**: four whole pre-baked sentences
  (`You tangle together and fall over!` / `They tangle together and fall over!`
  / `…tumble forward!` ×2) rather than a two-field verb.
- **Clause order within a strike is anatomical depth order**, walked outside-in,
  one clause per penetrated layer — a loop over a geometry array. It leads with
  the fat.
- **Aggregation is a post-render string-equality check** on the `report`
  struct's `repeat_count`. Aggregating after rendering is the wrong side of the
  pipeline and accounts for most of the wall-of-text.
- **No pronominalisation is structurally possible** — there is no discourse
  model, and unnamed units render as race name, so N same-race combatants are
  literally indistinguishable ("Frogman, Frogman and Frogman").
- Per-observer views are **unrepresentable, not merely unimplemented**: the
  `report` struct has no observer field, no witness list and no per-observer
  text; two combatants read the same bytes.

**The counter-effect matters as much as the diagnosis.** The log is loved
anyway, and the way it is loved is that enthusiasts *rewrite* it into prose and
quote the rewrite. It is excellent source material and bad prose — which is
close to the right description of what a Sonder composer would produce for the
narrator, and an argument that the narrator (still a model) is the correct place
for the register to be repaired.

The one good idea DF has is `data/init/announcements.txt`: a **declarative
per-event-type routing table**, ~339 types × seven orthogonal flags, decoupled
from wording. The sharpest distinction in it is `UCR` vs `UCR_A` — *constitutive*
(this event may open a narrative thread) vs *incidental* (file it under an
ongoing thread but never let it start one). A death mid-fight joins the fight's
story; a death from thirst starts nothing. **DF's mistake is that neither ever
suppresses.** Sonder's percept kinds want exactly this table, with a third
verdict: drop.

### 9.6 Licences

Brogue CE **AGPL-3.0** (most restrictive here — ideas only). DCSS
**GPL-2.0-or-later**. Cataclysm-DDA **CC BY-SA 3.0**. NetHack **NetHack General
Public Licence** (copyleft, not GPL, not OSI-approved). Angband **dual GPLv2 /
Angband licence** — *except* `src/message.c`, which is **BSD 2-clause** (Elly,
Andi Sidwell, 2007) and is the only permissively licensed message queue in the
set. Caves of Qud and Dwarf Fortress are closed; all Qud code cited is from
unofficial decompilation and all DF internals from DFHack's reverse-engineered
`df-structures`.

**Note also a negative result**: a sweep of every Roguelike Celebration event
2016–2025 found **no talk on message logs, message composition, or text output
as a craft**. The design literature is Josh Ge's single Cogmind post
(gridsagegames.com/blog/2014/02/message-log/) plus source code. From that post,
the two implementable rules: messages are *"very short, like 4-5 words"*, and
*"always putting the most important word (usually the subject) first"* — the
latter being the same conclusion as note 03 §3's "guarantee the discriminative
content leads".

---

## 10. Monotony: the best answer found, and the honest negatives

### 10.1 The literature's answer is that the question is misframed

Three independent lines converge on the same diagnosis, and none of them says
"vary the words".

**James Ryan already ran the proposed fix and it failed.** For his generated
storyworld encyclopedias he hand-wrote *"several thousand templates"* with
*"stylistic variants for most templates"* — the surface-variation intervention,
at scale — and reported (*Curating Simulated Storyworlds*, UCSC 2018, pp. 346,
359–360):

> they are quite repetitive; this is in spite of me having written stylistic
> variants for most templates. More pointedly, though, they do not read well
> because I do not enact any discourse planning in their composition. When a
> new event happens, a text representation of it is composed and then appended.
> … the real issue is that there is no reasoning at the level of discourse,
> since events are recounted in an online manner, as they transpire.

**Boluk & LeMieux reach the same diagnosis for Dwarf Fortress Legends** —
*"the historical sequence appears strange and arbitrary, with no transitional
expressions or conjunctive adverbs to tie together the sentences"*, producing
*"a textual archive that reads more like The Silmarillion than Lord of the
Rings"* — i.e. an annal, not a narrative, because text is composed online,
event by event.

**Ehud Reiter does not list repetitiveness among rule-based NLG's problems at
all** (his list: corpus acquisition, combinatoric explosion in complex
narratives, maintenance). On lexical variation specifically he treats it as
"a truism of writing" and cites no reader-preference experiment; his one
empirical observation, from post-editing studies, is that human editors' variation
edits were mostly to **connectives and non-content words**.

**And there is a controlled result pointing the other way** (§8.5): in
STORYBOOK's ablation, the no-lexical-choice version was *mildly preferred* over
the full system, while removing the discourse history was catastrophic.

**Sonder's own numbers agree.** §2 shows 88.3% of view sentences are hapax
within their bank and that surface templating costs nothing in embedding space.
§6 shows the corpus's ugliest, most-repeated sentences are the engine's own
string interpolation. The engine does not have a word-choice problem. It has an
online-composition problem: `_inject_*` appends fragments as they arrive.

### 10.2 Compton's oatmeal, and the part everyone omits

The canonical formulation:

> I can easily generate 10,000 bowls of plain oatmeal, with each oat being in a
> different position and different orientation, and mathematically speaking they
> will all be completely unique. But the user will likely just see a lot of
> oatmeal. **Perceptual uniqueness is the real metric, and it's darn tough.**

The part usually dropped is her prescription, and it is a **tiered budget, not
uniform variety** (*Encyclopedia of Generativity*):

> Know your oatmealishness levels: Background/In-fill (just don't be empty!) ·
> Perceptual differentiation · Perceptual uniqueness · Characterful (test: would
> you write fanfic for this generated item?). Have a **few** pieces of
> characterful content, sprinkled with perceptually unique content, and maybe
> some infill in the background.

*Applied to Sonder:* stop trying to make 9,351 views distinct. Classify each
percept set into a tier and spend variation budget only where the tier earns it.
`"You are in an unspecified area."` is a legitimate tier-1 artifact; the defect
is that it fires when the beat deserved tier 3, and that it is minted into
episodic memory as though it were content. Both are fixable without touching
wording.

She also names the marketing trap in a way that applies directly to this
branch's framing: *"Did you say the Really Big Number? … Never listen to the
Really Big Number."* The 73% is a Really Big Number in reverse.

### 10.3 The best answer found: specificity-ranked selection over authored variants

**Four independent systems converged on the same algorithm.** That convergence
is the strongest empirical signal in the whole survey.

- **Left 4 Dead** (Elan Ruskin, GDC 2012), over 10,000 lines shipped:
  > There are a lot of ways you could score matched rules… **The scoring
  > function that worked best for us was the simplest one imaginable — the
  > number of criteria in a rule. The more criteria a rule has, the more
  > specific it is.** … among ties, they're all appropriate so you can choose
  > randomly between them for variety.

  And anti-repetition is expressed as **an ordinary criterion in the same
  language** — "this line hasn't been said already" sits alongside "map is the
  swamp" — not bolted on afterwards.
- **Yarn Spinner** ships the production-grade version, and this is the one to
  copy verbatim. Each candidate line carries conditions; a *saliency strategy*
  receives passed conditions, failed conditions, a **complexity score**
  (`always` = 0; otherwise 1 if marked `once`, plus the number of boolean
  operators, plus 1), and an id. The default strategy is *Random Best Least
  Recently Viewed*: **filter to candidates with no failed conditions → sort by
  complexity descending → sort by fewest previous selections → random among
  the remaining ties.**
- **Inform's Room Description Control**, per Emily Short: the author writes
  whole paragraphs tagged with the set of salient facts they cover, and the
  system selects the paragraph matching the most currently-salient facts.
- **Emily Short's Annals of the Parrigues** engine: *"the generator compiles a
  list of possible substitutions that match the present world model and then
  can optionally apply salience criteria to pick the option that reflects the
  greatest number of facts about the existing world model."*

*Sonder adoption:* this is a 30-line function and it is the single
best-evidenced design decision available. Its inputs already exist — Layer A's
percept fields are the conditions, and the per-observer projection is the world
state. Note that it makes the firewall part of the same mechanism: **a variant
whose conditions reference a fact the observer lacks is simply not a
candidate**, deterministically, with nothing to scrub.

**Two refinements with hard numbers behind them:**

**Anti-repetition must decay, not blacklist.** MINSTREL's original "use twice
then ban" exhausted its library after five or six stories. The rational
reconstruction (Tearse, Mawhorter, Mateas & Wardrip-Fruin, AAAI 2012) replaced
it with fractional decay of the boredom counter and measured outright failures
**18.7% → 3.4%** and mean transforms per successful match **141.3 → 56.8**:
*"This randomization produces much more sustainable variety than Turner's
original boredom mechanism."* A blacklist looks fine for the first hour of play
and then falls off a cliff — exactly the profile of a defect that surfaces
fifty beats later.

**Budget salience per beat, independent of how many variants qualify.** The
peer-reviewed Skyrim Radiant critique names the failure: *"numerous NPCs can
spout them at once… These cacophonies of congratulation become increasingly
common the more the player plays, as the Radiant AI has more to select from."*
As Sonder's percept vocabulary grows, the *rate* of qualifying content grows,
and unbudgeted firing turns variety into noise.

**And make salience relative to a running base rate.** Ryan's *salience
inflation*: *"Of the storyworld Diol's 32,233 character deaths, 3,107 are due
to murder — that is too high a rate, and the resulting onslaught of murder
after murder makes each one unremarkable."* A static salience table will not
survive 2,296 turns; the composer needs a per-event-type surprisal estimate
computed within the playthrough.

### 10.4 The Principle of Venom — where variation *does* pay

Emily Short, *Annals of the Parrigues* (pp. 94–96), and this is the one
lexical-variation rule with a defensible rationale:

> The [leaders/rulers/judges] prosecuted a young man on the charge of burglary.
> **This strategy produces a mild variation in prose but does nothing likely to
> surprise or interest the author of the sentence.** … The Principle of Venom
> recommends that we focus our variational efforts on the most **statistically
> implausible, meaning-bearing** words in the sentence: *The leaders prosecuted
> a young man on the charge of [burglary/murder].* Furthermore, the Principle
> of Venom suggests the use of a large, auto-generated corpus to supply the
> crime, rather than relying on the author's own imagination.

With a hard budget: *"the number of venomous elements that should exist in any
given sentence is maximally two, and in a longer conceptually-continuous
passage, maximally three or four."* She later enforced it numerically — the
generator *"refuse[s] to pick more than one rare or two uncommon words in a
given production"*, and tracks **"bloat", the ratio of words used to semantic
content**, as a tunable metric.

*Sonder adoption:* the venomous slot is not a synonym list; it is the
world-state fact. In "Her tail is coiled firmly around your calf", the venom is
`calf` and `coiled` — both from the contact record — not `firmly`. Vary the
percept content that reaches the sentence; hold the frame steady. Two venomous
elements per sentence, and track bloat as a metric in the replay harness.

Her related corpus finding is also directly usable: vague evocative adjectives
combine into mush; replace single adjectives with longer specific phrases; and
aim for a **"lumpy distribution"** — *"a grammar in which some combinations are
clear mismatches, but any given sticker could probably work with half to two
thirds of the other stickers."* A grammar where everything composes with
everything has no friction and therefore no meaning.

### 10.5 The honest negatives, and the one that should worry this project most

**BRUTUS** — the best-known "literary" story generator, and the most thoroughly
demolished. Wardrip-Fruin: *"Rather than out of control variation, they seem to
produce no variation at all… this grammar is so tightly structured that it is
nearly a sentence-level outline… the Brutus project takes on the rough shape of
a literary hoax."* But the constructive half matters more: its prose really was
the best of its era, and the reason is three cheap hand-authored layers on top
of an ordinary CFG — **polarity-tagged iconic features per entity**
(`university → positive: {clocktowers, brick, ivy, youth}; negative: {tests,
competition, intellectual snobbery}`), **polarity-tagged literary modifiers**
(`ivy → negative: {poisonous, tangled}; positive: {spreading, green, lush}`),
and **fixed-arity constraints** forcing the tricolon that makes a description
sound literary. Wardrip-Fruin's caveat is, in Sonder's architecture, a feature:
*"this sort of literary knowledge… might differ from character to character
within the same story."* **Polarity of iconic features is naturally
per-observer. The firewall generates prose colour for free.**

**MINSTREL** — Turner's own retrospective: *"Minstrel was a brittle program…
if you stray even slightly from those limits, things break."* The
reconstruction found **88% of its "imaginative" recalls came straight from the
hand-authored library**, and that the variation/coherence tradeoff is monotone
along one axis — more transformation, more novelty, more incoherence.

**TALE-SPIN** — with a correction worth knowing before citing it: the famous
mis-spun tales are **Meehan's own hand-written translations, not program
output**. He says so. The most-reprinted "output" of the most-cited story
generator is human prose.

**Skyrim's Radiant quests** are the sharpest refinement of the "boring events"
hypothesis. The generator varies WHO, WHERE and WHAT and holds WHY constant:
7 items × 29 locations = 203 genuinely distinct events, one motive, zero causal
antecedents — and it is still boring. *"Aesthetically, it is a complete quest,
but lacking in greater depths, like the reasons for stealing the item."*
**Combinatorial event variety is not semantic variety either.** What matters is
that events differ in ways that have antecedents and consequences.

**The negative that should worry this project most is Wardrip-Fruin's
*Tale-Spin effect*:**

> The Eliza effect creates a surface illusion of system complexity — which play
> (if allowed) dispels. **The Tale-Spin effect, on the other hand, creates a
> surface illusion of system simplicity — which the available options for play
> (if any) can't alter.**

> *Tom asked Wilma whether Wilma would tell Tom where there were some berries
> if Tom gave Wilma a worm. Wilma was inclined to lie to Tom.*
> **The empty space between those two sentences is undoubtedly one of the most
> interesting parts of this story, if only we could see it** … Looking only at
> the surface, the decision might as well have been made randomly.

Sonder's entire value proposition is a hidden layer — perception, belief,
deception, dramatic irony. **A composer that renders only outcomes will produce
Mumble on top of a much better simulation, and readers will conclude the engine
is shallow, not just the prose.** Wardrip-Fruin's prescribed fix is to persist
the inferences made during decision-making and produce a summary of them; the
Sonder-specific version is that the composer must render *sensation and partial
knowledge* — the fragment, the muffled voice, the unrecognised figure, the
contact felt but not seen — because those are the surface of the hidden layer.
That is what note 03 already intends. It should be an explicit invariant with a
test, not an assumption.

**And a related warning about the current baseline** — Ryan on Bad News, where
a human wizard and actor sat on top of Talk of the Town:

> when humans are in the loop, **the failings of underlying computational
> systems can be covered up quite easily**… **Where the simulation lacks, the
> wizard and especially the actor augment, filling in its modeling gaps and
> injecting causal links that are not there** … this makes genuine appraisal of
> the underlying simulation difficult.

**Read the perception LLM as the wizard-and-actor.** Note 00's own thesis in
miniature was that the model had been covering for a broken `hear_level`.
Removing it will not create a monotony problem — it will *expose* one that was
always there, along with every other gap the model was smoothing. That is an
argument *for* the branch, provided the exposure is budgeted for.

### 10.6 The hybrid that measures best, and it is not a runtime call

Three results, all measured, point at the same architecture: **use the model to
author templates offline; select among them deterministically at runtime.**

**T2G2** (Kale & Rastogi, Google, EMNLP 2020). Write **one trivial template per
slot** — so template count grows *linearly in slots*, not combinatorially in
slot combinations — concatenate the templates for the slots you actually want
to convey, then have a seq2seq model rewrite the stilted concatenation into
fluent prose. The model never chooses content.

| SGD | BLEU unseen | BLEU overall | **slot error rate unseen** | SER overall |
|---|---|---|---|---|
| pure neural | 14.9 | 26.2 | 0.7 | 1.0 |
| schema-guided | 15.8 | 26.2 | 0.4 | 0.8 |
| **T2G2** | **22.2** | **28.6** | **0.0** | **0.4** |

Slot error rate on unseen domains goes to **zero**, and fluency improves *most*
where the model has no domain knowledge — because the template scaffold carries
the semantics. Directly relevant: Sonder's domains are unseen by construction.

**Kasner & Dušek (ACL 2022)** is the refinement and is structurally what Sonder
should build: emit one trivial description per data item, then apply three
**general-domain** modules in sequence — **ordering, aggregation, paragraph
compression** — with no in-domain fine-tuning at all, precisely because
*"training on in-domain data leads to overfitting to the data representation
and repeating training data noise."* Those three modules are Reiter & Dale's
document-planning and aggregation stages, reimplemented with hard content
preservation.

**ASPIRO** (Vejvar & Fujimoto, 2023) is the offline-bank version, and it is the
one to copy. An LLM is prompted to produce **entity-agnostic templates**
containing `<subject>`/`<object>` placeholders — never finished text — and a
**purely rule-based parser** validates each one (exactly one subject, exactly
one object, no other placeholders) and re-prompts with the specific errors
named on failure. Measured: parsing errors 719 → 239 and 94 → 24 across
retry rounds; quality against a BART-BASE **fully fine-tuned on the entire
training set**:

| | BLEU | METEOR | BLEURT |
|---|---|---|---|
| BART-BASE, full fine-tune | **52.54** | 44.86 | 0.54 |
| ASPIRO | 50.63 | **45.13** | **0.82** |

~2 BLEU below full fine-tuning, **+28 BLEURT**, zero training — and templates
you can inspect, diff, version and commit. Their own stated requirement is one
Sonder already satisfies: *"within a production environment, the incorporation
of a backup template is a fundamental necessity."*

**Why offline beats a runtime realiser for this engine specifically:** it keeps
byte-identical determinism under rerun and reroll (note 03 §4 D), keeps the
replay harness meaningful, removes the per-beat NOT_CHECKABLE risk entirely
because no model sees a beat, costs nothing at play time, and still buys
model-quality wording. The cost is that the bank is fixed — it delivers
Compton's *perceptual differentiation*, not per-beat invention.

**If a runtime model is kept anyway**, the correct shape is
**grammar-constrained decoding with an input-dependent grammar**: compile, per
beat, a grammar whose terminal alphabet is restricted to the entities,
attributes and events Layer A certified this observer may know. A leak then
becomes not unlikely but *unrepresentable* — masked to −∞. That converts the
firewall from "the model cooperated" to "the automaton had no accepting path",
which is exactly the deterministic-floor property AGENTS.md demands. Tooling:
llama.cpp GBNF (MIT), XGrammar (Apache-2.0, the default structured-output
backend for vLLM/SGLang), Guidance (MIT, with token fast-forwarding that skips
forward passes through fixed template text). Avoid Outlines here — its 3–12 s
grammar compilation is disqualifying if you compile per beat.

### 10.7 The credible argument that deterministic composition is the wrong path

Stated fairly, it is narrower than "LLMs won":

> The pipeline's **content** stages — content determination, document planning,
> referring expression generation — remain correct, and are where the firewall
> lives. Its **surface** stages — aggregation, lexicalisation, realisation —
> are the most expensive to hand-author, the hardest to maintain, and the one
> place language models have a decisive, uncontested advantage. Hand-building a
> realiser in 2026 spends effort in the one place the market has solved.

That is essentially Reiter's own position, and he has the least incentive to
hold it: LLMs are *"very good at microplanning and surface realisation"* on
small inputs producing *"1 or 2 sentences"*, but for multi-paragraph output
*"more hallucinations, more omissions, more discourse/contextual/lexical
errors"*. His recommended hybrid is a language model as **post-processor over
rule-determined content**, because *"all of the content decisions are made by
the rules, so neural hallucination/omission is much less of a concern"* — plus
two practical rules: keep the rewriting simple, and always keep a fallback so
that if any problem is detected the system presents the rule-based text.

There is also an older, non-LLM version of the critique worth knowing: Cahill
et al. contested the pipeline's "consensus architecture" status **in 1999**, on
the grounds that stage boundaries leak — content determination, aggregation and
lexicalisation interact. That is the honest structural objection to note 03's
two-layer design, and it predates neural methods entirely.

**Three counterweights, each measured:**

1. **The error class is Sonder's threat model.** On sparse inputs — which a
   scrubbed observer view is by definition — NOT_CHECKABLE errors dominate
   INCORRECT ones roughly 9:1 (1.01 vs 0.11 per output on `wikidata`). The
   model does not get facts wrong; it invents facts you cannot check. For
   general data-to-text that is a nuisance; here it is the whole problem.
   Errors also scale with output length, and Sonder emits ~820-character beats,
   not one-liners.
2. **The model is a poor diversity source too.** Post-training diversity
   collapse *"is determined during training by data composition and cannot be
   addressed at inference time alone"*, and temperature cannot recover it.
   Structured output narrows it further. So the plausible outcome of keeping
   the model is a first sentence that repeats 55% of the time instead of 73%,
   is non-reproducible, occasionally fabricates a perception, costs money per
   beat, and cannot be regression-tested.
3. **Determinism is fragile even locally.** At temperature 0, 1,000 completions
   from an identical prompt produced **80 unique completions**, with divergence
   starting around token 103 — short outputs look reproducible and long ones
   are not, which is the worst possible failure mode for a golden-transcript
   test suite. A batch-size-1 local llama.cpp deployment with a fixed seed
   *can* be bit-reproducible, but changing thread count, GPU-layer split,
   KV-cache quantisation or the llama.cpp version breaks every stored
   transcript. That is a real recurring maintenance line.

**The deferred question nobody has answered, in the literature or here:**
no source anywhere measures reader preference for lexically varied versus
consistent generated prose. As a *retrieval* concern the 73% is defensible
(§2, §10.8). As a *reader-facing* concern it remains an assumption — and in
this engine no reader sees a view at all (§3).

### 10.8 Retrieval: two mechanisms that refine §2's measurement

My own measurement (§2.2) found that a template with real content in the slot
is indistinguishable from model prose in embedding space. Two published results
sharpen the condition under which that holds, and both matter.

**Sentence-embedding cosine tracks lexical overlap more tightly than humans do.**
On STS-B, BERT-induced cosine correlates with **edit distance** at ρ = −50.49,
while human gold semantic similarity correlates at only ρ = −24.61 — and
*"for sentence pairs with edit distance ≤ 4, BERT-induced similarity is
extremely correlated to edit distance."* So the safe regime is *large* content
deltas. The engine's retired `"I chose to attempted <verbatim declared act>"`
family sat at 0.0% collisions because the slot carried a whole sentence. A
composer emitting `"You are in the kitchen, alone."` versus `"You are in the
kitchen, and Mara is watching you."` — a few tokens apart, enormously different
as a memory — is in the dangerous regime. **The rule is not "templates are
safe"; it is "the varying part must dominate the invariant part."**

**A shared first sentence is over-weighted by the embedder.** Across eight
models spanning APE, RoPE and ALiBi position encodings, inserting text at the
*beginning* of a document drops cosine-to-original by up to **8.5% more than
mid-document and 12.3% more than at the end**; for APE models a 20%-length
insertion gives 0.819 at the beginning versus 0.968 at the end — a 15.4% gap.
The authors re-ran on randomly shuffled sentences and got the same result, so
this is a model artefact, not a corpus property. **A first sentence shared
verbatim across 73% of views is weighted more heavily than the sentences that
differentiate them.** That is an independent, mechanistic justification for the
plan's salience-driven omission of constant openings — stronger than the
aesthetic one.

**And the corpus-level result separates the two things everyone conflates.**
Across four corpora, retrieval performance tracks *similarity* (mean pairwise
cosine) and not *redundancy* (repeated facts): *"similarity drives retrieval
difficulty by increasing confusion among near-duplicates, whereas redundancy
can mitigate errors by providing alternative evidence paths."* Repeating the
same fact is harmless or helpful; repeating the same surface form is what
destroys retrieval. Sonder's defect is squarely the second kind — and the fix
follows: **deduplicate on surface form, never on content.**

Three consequences for the plan's Phase 3:

- **Embed the delta, not the boilerplate.** Strip invariant template spans
  before embedding; embed the slot fillers and discriminating clauses; keep
  full prose in a display column. This removes the cause rather than
  compensating downstream, and it follows directly from the two mechanisms
  above. No study measures this end-to-end — building that A/B would be an
  original contribution.
- **The RRF fusion already in `search_memories` is the right defence, and BM25
  is the load-bearing leg.** BM25's IDF term evaluates to ≈0 for a term
  appearing in every document, so **it assigns near-zero weight to boilerplate
  by construction**; dense cosine has no such mechanism. Measured, BM25
  degrades roughly half as fast as dense retrieval as corpus similarity rises.
- **Add recency and importance as ranking terms** (the Generative Agents
  weighting is relevance 3, importance 2, recency 0.5 — and note that its
  observation strings are themselves **deterministically templated from
  (subject, predicate, object) tuples**, with the model used only for
  importance rating and reflection). For 812 byte-identical rows, recency and
  importance are the *only* signals that can break the tie at all: identical
  text produces identical vectors, so the ranking is an 812-way exact tie
  broken by rowid. That is arithmetic, not a discrimination problem.

### 10.9 How to measure it, so this is not re-litigated by anecdote

**Expressive range analysis** (Smith & Whitehead, PCG 2010) is the method, and
its motivating sentence is Sonder's situation exactly: *"a generator that can
create tens of thousands of levels in a matter of minutes is useless if many of
those levels are effectively identical to each other."* Their protocol:
choose metrics that are **emergent, not the parameters you already control**;
sample ~10,000 outputs; plot a 2-D histogram of the generative space; then diff
the histogram per parameter change. Michael Cook's Danesh adds **ERA history**
— archive each run so you can compare heatmaps before and after every generator
change — which is regression-testing for diversity.

Emily Short has already specified the text-domain metrics: **component size**
(how long is the smallest atom of text?), **number of alternatives** (how many
other options did this phrase have?), and **world-model salience** (how many
facts did it have to match to be selected?), instrumented as `{X/Y/Z}` markup
emitted alongside every generated span. Her counter-intuitive finding is a
direct hazard for a weighted variant bank: **adding content can reduce perceived
variety** — a new branch chosen half the time with one option drops each of
eight existing options from 1/8 to 1/16. *Measure the realised output
distribution, not the corpus size.*

Improv's `phraseAudit` is the cheap complement: a per-phrase use-count map that
is **comprehensive — unused phrases appear with value 0** — *"meant as a tool to
help you find 'lumps' in your generator corpora."*

**And one check to run before writing any variation code**: Ryan's *beads on a
string* pathology — *"a modular architecture… is only half the battle: the
procedural content authored for that architecture must itself be modular as
well"*, because when chunk A deterministically feeds B, *"the monolithic
structure that was broken into these chunks is reconstituted."* **How many of
the composer's decision points have more than one live option under real
state?** If the 73% is because only one expansion is legal 73% of the time, no
amount of corpus growth fixes it — and Short's finding says it may get worse.

### 10.10 Licences for borrowable variation code and corpora

| Artifact | Licence | Note |
|---|---|---|
| `aparrish/pytracery` | Apache-2.0 | `pip install tracery`; faithful Python port with `base_english` modifiers |
| `sequitur/improv` | **MIT** | `lib/filters.js` is ~90 lines; `unmentioned` and `phraseAudit` port directly |
| `james-owen-ryan/expressionist` | **MIT** | authoring tool; markup-accumulating CFG |
| `james-owen-ryan/talktown` | **MIT** | Python; the Productionist idiom (preconditions as Python expressions) |
| YarnSpinner | MIT | saliency strategy — reimplement, don't link (C#) |
| `dhowe/RiTa` | **GPL-3.0** | copyleft; the lexicon is the value, the licence is the problem |
| `dariusk/corpora` | **CC0** | word/name/thing lists, no attribution needed |
| Theophrastus (Jebb tr.), Anglo-Saxon Chronicle (Giles/Ingram) | Public domain | Short's actual sources; regular phrasing makes extraction easy |
| Wikipedia-derived lists | CC BY-SA | attribution + share-alike propagate |
| llama.cpp GBNF · Guidance | MIT | constrained decoding |
| XGrammar · Outlines | Apache-2.0 | constrained decoding (Outlines: 3–12 s compile) |
| `kasnerz/zeroshot-d2t-pipeline` · `vejvarm/ASPIRO` | check per repo | the ordering/aggregation/compression pipeline and the offline bank generator |

---

## 11. What to build, in order

Everything below is justified above; nothing here is a hedge.

**Phase 0 — measure before building.**

1. `tools/expressive_range.py`: N≈10,000 composer samples over synthesised beat
   states; metrics = first-sentence entropy, component size, alternatives at
   selection, salience-match count, bloat (words ÷ facts conveyed); 2-D
   histogram; ERA history so each generator change is diffable. Plus a
   comprehensive per-variant use-count audit *including zero-count variants*.
   Wire into `make check` so a diversity regression fails the build the way a
   stale `CODE_MAP` does.
2. Run the **beads-on-a-string check** (§10.9): how many composer decision
   points have more than one live option under real state?
3. Fix the **position-resolution defect** that produces `"an unspecified area"`
   (§2.3). 826 memory rows, a 97.3% collision rate, and the single largest
   retrieval pathology in the engine — and it is independent of this branch.

**Phase 1 — the stage the engine has never had.**

4. **Buffer the beat, then plan it.** Stop appending fragments as events
   arrive. Collect all percepts, then run content determination → ordering →
   aggregation → referring-expression generation → realisation. This is the
   named root cause in every post-mortem in §10.1.
5. **Discourse tiers for ordering** (Angband's three-pass model, §9 R6) rather
   than a salience float alone, with the beat's causal chain authoritative
   inside its group.
6. **Aggregation with the firewall-safe grouping key** (§9 R2–R5): group by
   (source, channel, **fidelity**), degrade the aggregate to the weakest
   channel among its members, collapse identical percepts to a count,
   de-duplicate per (individual, percept-kind) first.
7. **A discourse history** — STORYBOOK's four fields per referent: frequency,
   last-usage, recency counted within gender/number, distance in beats. This
   is the highest-value component in the survey and the only one with a
   controlled ablation behind it (§8.5). It drives article choice, pronoun
   choice, and first-vs-subsequent mention. Keep it **separate from** the
   observer's knowledge state, as Curveship does — a person known for fifty
   beats but unmentioned this scene still wants a full noun phrase.

**Phase 2 — realisation.**

8. **Port Curveship's slot realiser** (ISC, §8.3): `[head/mods/kind]` slots,
   person derived from `narratee == observer`, number from the subject,
   Reichenbach tense derivation, deictic shifting, and the 1,023-entry
   irregular-verb table. Set `narratee = observer` and second person falls out
   by construction — deleting `_self_second_person`, `_fix_you_agreement`,
   `_observable_predicate`'s capitalisation guess, and the "you hear her says"
   class in one change.
9. **Make the Director's `observable` a slotted template**, or emit
   `{verb, object, modifiers}` alongside it. It is already Curveship's
   per-action template written per beat instead of per verb; marking the agent
   slot is the highest-leverage single change in this report.
10. **Replace `_unknown_actor_label` with Dale & Reiter's incremental
    algorithm** over a contrast set of the other unrecognised bodies this
    observer can currently perceive. Measured today: 15.6% exact label
    collisions and ~40% broken English from word-count truncation (§8.6, M15).
11. **Make the display label the only accessor** for a subject's name, so no
    renderer can reach a canonical name (§9.2). Type-level, greppable,
    and it is what makes DCSS and DikuMUD structurally leak-proof.
12. **Selection by specificity-ranked variants** (§10.3): filter by satisfied
    preconditions → rank by specificity → least-recently-used → seeded random,
    with **decaying** rather than blacklisting anti-repetition, a per-beat
    salience budget, and base-rate-relative salience.
13. **Generate the variant bank offline** with the ASPIRO loop (§10.6): a model
    writes entity-agnostic templates, a rule-based parser validates each one and
    re-prompts with named errors, and the accepted bank is committed to the
    repo as data. Register 3–6 sense-equivalent variants per (percept kind,
    channel, fidelity) cell — `_SENSATION_FORMS` currently has one.
14. **A manner/intensity lexicon** of a few hundred entries keyed on typed
    intensity × motion kind × fidelity, built the way DCSS builds its damage
    ladders: band the continuous value, then cross it with an ontology axis
    (§9.3). 77 adverbs cover 90% of the corpus's adverb tokens (M12).

**Phase 3 — the invariants that keep it honest.**

15. **Occlusion runs last and no admission may re-add** (TADS's `Occluder`,
    §7.2). A stated invariant with a test.
16. **`Percept.alternate` chains** (Lost Souls' `Message_Alternate`, §7.5) —
    the visual form, then the auditory, then the tactile, each a full percept
    with its own gate. This replaces `_surface_translate_event`'s admitted
    all-or-nothing over-redaction with graded degradation.
17. **Edge-sensitive re-announcement** (TADS's `displaySchedule`, §7.2 /
    Brogue's per-turn latch, §9 R9), with the counter **reset when the percept
    leaves scope** — so a contact that breaks and re-forms announces itself
    again.
18. **`@cosmos` as an observer** (§8.1): make the omniscient view a composer
    configuration rather than a separate path, so firewall leaks become
    testable by **diffing two composer runs over one event log** instead of by
    regex over prose.
19. **Add a regression test for Curveship's awareness bug** (§8.4): does
    observing a target grant a channel to a *sensing* event performed on that
    target? Curveship grants awareness if you can see the agent **or the direct
    object**, and it leaks.
20. **Check the gender-leak case** (§9.2): does an unrecognised actor's percept
    ever carry a pronoun derived from the sheet? DikuMUD has this bug;
    Angband and Brogue structurally cannot.

**Phase 4 — memory (the plan's Phase 3, refined).**

21. **Mint episodes from the IR**, and **embed the delta, not the composed
    prose** (§10.8). Strip invariant spans; embed slot fillers plus
    discriminating clauses; keep full prose in a display column; fill
    `key_phrases` and `entities` from typed fields so the lexical and
    exact-phrase RRF legs benefit.
22. **Suppress contentless episodes at write time** — a view whose percepts are
    all standing state carries no episode. Generalises `_is_empty_view`.
23. **Add importance and recency to the ranking** so cosine is one term of
    three, and collapse exact duplicates to a single row with a count.

**What NOT to build**

- A synonym wheel. Two independent results say it is worthless or negative
  (§8.5 ablation, §10.1), and Sonder's own embedding measurement says it buys
  nothing in retrieval (§2.2).
- A runtime model realiser, unless the Phase-0 consumer experiment says the
  rule path measurably degrades character behaviour. If one is kept, it must be
  grammar-constrained on a per-beat alphabet (§10.6), never free-form.
- A blacklist-style anti-repetition mechanism (§10.3).
- Anything that lets Layer B see the scene, `resolved_event`, or a canonical
  name (§8.4's "hang appearance on the projection, not on the thing seen").

---

## 12. The realisation toolkit: what to vendor, and the licence traps

Phase 2 needs English morphology — plurals, `a`/`an`, third-person `-s`,
determiner choice, modifier order. This is the most commoditised layer in the
report and the one with the most licence traps. Findings verified against
source and package metadata.

**Vendor `pattern.en`'s `inflect.py`. It is the highest value-per-line artefact
found.** 829 lines, **BSD-3-Clause** (© University of Antwerp); everything above
line 641 is pure `re` with zero imports. Its own header reports measured
accuracy against CELEX: **95% pluralize, 96% singularize**. The `a`/`an` table
is **14 rules in ~20 lines** and correctly handles *an hour / a unicorn / an MBA
/ a university / an honest man*; it ships a ~40-word `plural_prepositions` set
so *mother-in-law → mothers-in-law* pluralises the head. Copy the file with its
notice. Do **not** depend on the `pattern` package — 65 MB installed, dead since
2018, and the `Pattern` PyPI name now resolves to a 4 KB placeholder.

Graft on `inflect`'s numeric `a`/`an` branch: head-to-head on eight cases,
`inflect` scored 7/8 but gets **`a 8% increase`** wrong for want of numeral
handling, which is the one case SimpleNLG's otherwise-poor implementation gets
right (its `8|11|18` rule). Between them the coverage is complete.

**Do not port SimpleNLG.** It is unmaintained — last commit touching `src/` is
2020-06-07; open issue #83 ("Indefinite article not correctly chosen when it
precedes an adverb") has been untouched since Dec 2020. Two of its behaviours
are outright wrong for prose: `setCommaSepPremodifiers` defaults **on**,
producing *"the big, red ball"* (SimpleNLG-EnFr had to add a `NO_COMMA` feature
to suppress it), and coordination emits `a, b and c` with no Oxford-comma
option. And its third-person-singular rule `".*[szx(ch)(sh)]\b"` is a
**character class, not an alternation** — it matches any word ending in
`s z x ( c h )` and over-fires on words ending in `c` (*panic → panices*). It
works on common cases by accident.

Its scale is worth knowing as a target though: SimpleNLG does regular plurals in
**three regexes plus 91 lexicon overrides**, where `inflect` uses ~70 ordered
rules over **106 tables totalling ~1,174 items**. The ceiling is MORPHG
(~1,650 Flex rules, 99.97% type accuracy on CELEX) and it is non-commercial —
which is precisely why SimpleNLG v3 could not be used commercially. Do not chase
it.

**Determiner choice: use the perception layer, not a corpus model.** Minnen,
Bond & Copestake (CoNLL 2000, https://aclanthology.org/W00-0708.pdf) over
300,744 base NPs from the WSJ Penn Treebank: **bare 70.0% / `the` 20.6% /
`a`/`an` 9.4%**, with indefinite plurals essentially nonexistent (446 of 69,269).
Feature ablation: head noun alone 80.3%, head + determiner-present 81.7%, all
features **83.6%**. That 83.6% is the ceiling for *inferring* discourse status
from syntax. Sonder does not have to infer it — the per-observer `known` ledger
and the discourse history (Phase 1, item 7) answer "has this observer seen this
entity before in this scene?" directly. A rule keyed on that should beat the
corpus model comfortably, because the corpus model was approximating exactly
that signal.

**Modifier ordering: one float per adjective.** Malouf found **positional
probability alone scores 89.73%**, within two points of his best combined model
(91.85%), requiring "only one easy-to-calculate value be stored for each
possible adjective" — for an authored fiction lexicon that float is hand-assigned
in the sheet. The domain-robust alternative is Mitchell (ENLG 2009,
https://aclanthology.org/W09-0608.pdf): four prenominal positions, nine classes,
**89.63% token precision**, and it survives domain transfer at ~89% where
transitivity-graph methods collapse to 54–58%. Her reassuring distribution:
**88.90% of real prenominal sequences are just two modifiers**, 9.92% three —
the four-slot machinery almost never fires. Caves of Qud's `DescriptionBuilder`
signed-integer order axis (§9.3) is the same idea with free deduplication and
elision-as-threshold.

**Licence traps, all verified:**

| Artifact | Reality |
|---|---|
| **SimpleNLG's `default-lexicon.xml`** | **5,993 of 6,314 entries carry SPECIALIST EUIs** (`E0006419` = *a*). It is a SPECIALIST extract, not merely compatible. SPECIALIST is free *including commercially* but requires naming "the SPECIALIST NLP Tools with the release number and date", **a complete description of any modifications**, and no assertion of proprietary rights. SimpleNLG's own file carries no attribution header. |
| **`lemminflect`** | MIT code, **SPECIALIST-derived data** — same obligation. |
| **`inflect`** | MIT since 2.1.0 (2018-11-12); **AGPL-3.0 up to 2.0.1**. There is no `LICENSE` file in the repo (the grant is in `pyproject.toml`), so GitHub reports no licence. The Perl→Python relicensing chain is undocumented: Conway's `Lingua::EN::Inflect` is "same terms as Perl" and MetaCPAN reports `license: ['unknown']`. Cite both if you copy tables verbatim. |
| **`pynlg`** | **French-only.** `lexicon/feature/lexical/en.py` is 0 bytes; every test is `*_fr.py`; `EnglishLexicon.conjunction_coordination` returns `'et'`. Its `english-lexicon.xml` is **byte-identical (md5 93aaa48c…) to SimpleNLG-EnFr's MPL-1.1 lexicon**, redistributed under MIT with no MPL notice. Do not take its grant at face value. |
| **`num2words`** | LGPL-2.1 — the only copyleft in the candidate set. Use `inflect.number_to_words()` / `.ordinal()` instead. |
| **`mlconjug3`** | MIT-declared but ships **GPL-2+ Verbiste-derived** conjugation data, pulls scikit-learn and pins `numpy<2.0`, and applies ML to a problem with ~180 irregulars. Avoid. |
| **SimpleNLG-IT lexicon** | Code repo MPL-1.1 but `alexmazzei/SimpleLEX-IT` is **CC BY-NC-SA 3.0** (non-commercial); the two repos contradict each other. |
| **`pySimpleNLG`** | Runs clean on Python 3.12 — 179 tests, 4 skipped (2 being "aggregation not implemented"), 2 errors from `assertEquals` deprecation in the *test file*. Usable if you want a reference implementation to diff against. |

**The clean path**, sidestepping MPL derivation entirely: vendor `pattern.en`'s
`inflect.py` (BSD, ~600 usable lines) for plurals and `a`/`an`, graft `inflect`'s
numeric branch, take Curveship's verb and tense tables (ISC), and write the ~150
lines of remaining morphology and orthography rules **from the published
specification rather than by transcribing the Java**. Add a SPECIALIST
attribution line only if you end up touching SimpleNLG's lexicon or
`lemminflect`.

---

## 13. Verified vs recalled

**Verified from primary source this session** (source code read, or paper text
extracted): all corpus measurements in §2, §4, §5, §6 and M-series; Curveship's
module structure, spin dict, realiser slot grammar, `Noun.realize`,
`world_model.set_concepts`, authored action templates, ISC licence, and the
four focalisation transcripts (generated by *running* the system); adv3's
`sense.t` / `thing.t` / `adv3.h` transparency levels and `Occluder`; adv3Lite's
`SenseRegion`, size tiers and remote-description properties, and its MIT
licence; TADS 3's derivative-works prohibition; Roberts' Mercury blog post;
Evennia's FuncParser docs and the GPL-2 `verb_conjugation` sub-licence; DCSS's
`message.cc` merge rules, `description-level-type.h`, `_mon_special_name`,
`monster_info` allowlist and `_genus_factoring`; Brogue CE's `combatMessage`,
`foldMessages`, `monsterName`, `attackVerb` and `describeLocation`; Angband's
`mon-msg.c` and `MDESC_*`; NetHack's `x_monnam` and `pline` filter order;
Cataclysm-DDA's `add_msg_player_or_npc`; Generative Agents' templated
observation construction and retrieval weights `[0.5, 3, 2]`; the STORYBOOK
ablation; Ryan's dissertation quotations; Compton's oatmeal passage and
generativity tiers; Short's Principle of Venom; Ruskin's L4D specificity rule;
Yarn Spinner's saliency algorithm; the T2G2, ASPIRO, Kasner & Dušek, BERT-flow,
positional-bias and RARE numbers; the realisation-library licence audit in §12.

**Recalled or second-hand, flagged in place:** Boluk & LeMieux's Dwarf Fortress
chapter (quoted via Ryan's dissertation, chapter not obtained); Caves of Qud
internals (unofficial decompilation); Dwarf Fortress internals (DFHack's
reverse-engineered structures and community string dumps); Sil-Q's licence;
Lima and Melville mudlib licences; PennMUSH's `COPYRIGHT`; Aardwolf and Genesis
LPMud (unreachable); Isaac Karth's DiGRA 2018 paper (not retrieved).

**Explicit non-findings:** no talk on message-log design or text output as a
craft exists in ten years of Roguelike Celebration; no extension in either
canonical Inform repository implements sound or smell propagation between
rooms; **no study anywhere measures reader preference for lexically varied
versus consistent generated prose** — the 73% is a defensible engineering
concern for retrieval and an assumption everywhere else.
