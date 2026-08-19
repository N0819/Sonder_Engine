# Greeting minds — what an opening passage may put inside a head

**Status: built with this note.** Schema: `llm/schemas.py`
(`GreetingMind`, `GreetingBeliefSeed`, `GreetingStanceSeed`,
`GreetingAffectSeed`, `GreetingInterpret.minds`). Prompt: both packs'
`greeting_interpret`. Routing: `story/greetings.py` (`_seed_minds` and its
helpers, `EXTRACTOR_VERSION = 2`). Promotion claim:
`persist/commit_background.promote_background_character` reading the chat's
`greeting_minds` world key. Tests: `tests/test_greeting_minds.py`, plus the
worked-example validation already in `tests/test_schemas.py`.

## The gap

`GreetingInterpret` had one substantive field, `knowledge_seeds`, for one
person, the card's owner. A greeting is not a list of facts one person knows.
Read against the live corpus (46 greetings across 32 cards, read in full
before this schema was shaped), an opening passage routinely establishes:

- **An emotional state at the moment the story opens** — nearly every
  greeting. A man backed against a wall with a raised wrench and red-rimmed
  eyes; a researcher whose heart skips when she sees a stranger's finger on
  the elevator button; a flat voice "betraying the internal glee in her
  mind". Nothing read this; every card-launched character opened in whatever
  mood their sheet's `initial_state` happened to author, which is the
  temperament of a life, not the temperature of this scene.
- **A stance toward the person in front of them** — the majority. One card's
  fourth greeting opens weeks into a warm acquaintance with the player
  ("grown close", a named attraction, first-name rights); its second opens
  the first day they have met, and knows one fact about them. The engine has
  exact vocabulary for this — the trust/warmth/fear axes
  `relationship_events` records — and the launch seeded none of it, so both
  greetings started the relationship at zero.
- **Beliefs, including false ones and convictions.** "The east lock was iced
  over two days ago." "There is no malice behind the containment
  procedures." A commander who "is not prepared to discuss whether" — a
  conviction he will defend, not merely a fact he holds. And the generative
  case the firewall exists for: a mimic reproducing a dead woman's voice so
  that whoever hears it will believe someone is hurt in the commissary. The
  distance between what a mind holds and what is true is the seed of every
  deception downstream, and the extraction had no way to record it.
- **Other people present.** Two armed guards who have been told to stay
  alert and have "read the files"; a pursuing Dalek; a dead colleague whose
  fate the character knows. The extraction was structurally per-card: one
  mind, however many the passage put in the room.
- **Assertions about the player's own character** — what they just lived
  through ("your lungs burn", chased through an alley), what they know, and
  even standing relationships.

The world half of this is settled and stays settled: `start_story` stores
the greeting prose as the chat's scenario and `director_establish` builds
rooms, positions, entities and attire from the same passage one turn later
with the engine's full payload. This note is only about minds.

## The shape: one extraction, many minds

`GreetingInterpret.minds` is a list of `GreetingMind`, one per person the
passage puts on the page, keyed by `who` — the name the passage uses, or the
literal `{{PLAYER}}` token for the player's slot. Each mind carries four
channels, and only these four:

| channel | schema | routes to | why this store |
|---|---|---|---|
| `knowledge_seeds` | `GreetingKnowledgeSeed` (unchanged) | that character's private memory (`add_memories_batch`) | episodic knowledge; salience capped under the consolidation floor so it decays like lived experience |
| `beliefs` | `GreetingBeliefSeed` | self/world → `interior.beliefs`; about another person present → `mind_models` via `theory_of_mind.apply_mind_model_updates` | the two stores the runtime already revises; a seeded belief must be revisable by the same machinery that revises every other belief |
| `stances` | `GreetingStanceSeed` | relationship graph + one `relationship_events` row per nonzero axis, provenance `greeting` | the axes are exactly `RELATIONSHIP_AXES`; the ledger row is why the stance can later explain itself |
| `affect` | `GreetingAffectSeed` or `null` | `active_state.affect.surface` (and the legacy flat mood/valence/arousal projection) | the moment's emotion; the card's `initial_state` remains the **baseline**, so a greeting's terror decays back toward the authored temperament |

Everything in a channel is a **starting point, not a rule**: seeded beliefs
sit in the ledger as learned (never `authored`) entries, so `_within_cap`
evicts them before sheet-authored ones and nothing re-seeds them; seeded
stances are positions the story is free to move; seeded affect decays toward
the card baseline like any other surface state.

### Beliefs about other minds go through the theory-of-mind gate

A greeting saying the character believes something about *another person*
("she believes {{PLAYER}} is the courier") is a hypothesis about a mind, and
it is seeded through `apply_mind_model_updates` rather than written by hand
— which means the engine's own epistemics bound it: an `identity` claim caps
at 0.35, a `trait` at 0.45, a `stated_fact` at 0.9, exactly as if the
character had formed the belief in play. A greeting cannot mint a certainty
about another mind that play itself could not have reached in one step.

### Convictions

`GreetingBeliefSeed.protected` marks a conviction — an entry
`apply_belief_updates` will weaken at half step, the same flag
`psychology.self_model.protected_beliefs` sets. Two bounds, both enforced at
the write (a stored extraction can bypass the schema, so the schema alone is
never the boundary — the salience cap taught this):

- confidence is capped at **0.85**: a seed may be held firmly, never
  unshakeably. The weakening step is absolute, so any seeded belief remains
  revisable; the cap only keeps authored scaffolding from starting *above*
  where lived reinforcement would have to earn its way to.
- at most **2** protected entries per mind, first listed kept. Protection
  halves revision; a greeting that armors a whole worldview has authored an
  unrevisable character, which is a card-psychology decision
  (`protected_beliefs`), not an opening-passage one.
- protection applies only to self/world beliefs. A belief *about another
  mind* routes through theory of mind, which has no protected tier — a
  greeting cannot make a first impression of somebody permanent.

### False beliefs need no flag

There is no `is_false` field. The extraction records what the mind holds;
`director_establish` records, from the same passage, what is; the gap
between them IS the false belief, represented the way the engine represents
every false belief — as a confident claim the world will contradict. A
truth flag would be a second copy of objective state inside a schema about
minds, which is the exact collapse the firewall forbids.

## What a greeting may NOT establish, and why

- **Projects and intentions — never.** A project must be adopted mid-play
  through the adoption deliberation, and an intention is built to be
  completed, abandoned, or swept — seeding either hands the character aims
  that decay into the courier-at-the-door failure, or a life's work they
  never arrived at. A greeting that establishes a drive-shaped situation
  does it through **memories and beliefs** ("I have been waiting three
  nights for a courier"), and the character's first step derives wants from
  those plus the card's drive — the tier that survives. The intention case
  was argued and refused rather than skipped: every corpus greeting whose
  aim looked intention-shaped ("get into the elevator", "make the stranger
  answer") is a *this-beat* want the first character step will re-derive
  from the seeded affect and beliefs anyway, and a pre-seeded intention
  would sit in the auction with authority the passage never had.
- **Psychology.** Traits, values, drive, coping are the card's; a flattened
  copy competes with the authored version. Unchanged from v1.
- **The scene.** Settled; owned by establishment. Unchanged from v1.
- **The player's affect, stance, or beliefs.** The player's mind is the
  human's. The engine has no store for it, and building one would put the
  engine in the business of telling the player what they feel — the one
  mind the simulation must never drive. A greeting's assertions about the
  player's interior ("your heart hammers") are delivered by the page itself.
- **A mind for an unattached presence, at launch.** Background presences
  are stateless by design; memory and psychology require promotion. Their
  extracted minds are not discarded and not seeded — they are **retained**
  (see below) and claimed at the one sanctioned moment a presence acquires
  a mind.

## `revealed_in_prose`, generalized

The flag means one thing everywhere: **the passage states it on the page,
so the player has legitimately seen it.** Enforcement is subtractive and
structural, never trusted to the model:

1. **Every fictional-mind store is private by construction.** Memories,
   `interior.beliefs`, `mind_models`, and the relationship graph are read
   only into that character's own context; no player-facing surface renders
   them. A `revealed_in_prose: false` item is therefore private because of
   *where it lands*, not because a flag was honored.
2. **The one player-readable store admits revealed items only.** A
   `{{PLAYER}}`-mind knowledge seed routes to the chat's
   `persona_private_history` (the panel the player can open), and only when
   `revealed_in_prose` is true — the store then holds nothing the page did
   not already deliver. An *implied* player-mind item is a model's guess
   about what the player-character knows, and a guess can embed another
   mind's secret in its phrasing ("I believe the tea is safe" reveals that
   the tea is worth having a belief about); routing it to a player-readable
   surface would let the extraction widen the page. Dropped, and the drop
   is recorded (see visibility).
3. **The existing `{{PLAYER}}`-naming guard stays**, deterministic, on
   knowledge seeds: a "secret" whose content names the player's slot is
   force-flagged revealed, because knowledge about the player's own conduct
   cannot be asymmetric against the player.
4. **The identity floor applies to every string that enters a mind.**
   Belief text, stance notes, and mind-model subject keys pass
   `_substitute_player_slot` with the same handle the memory seeds use: the
   persona's name only when `already_known`, otherwise the perception-built
   description. A stranger's greeting cannot hand the character the
   player's name through a stance target when the memory path already
   refuses to hand it through a memory.

On beliefs and stances the flag has no routing consequence today (both
routes are private); it is kept as provenance — the durable record of
whether the player was shown the item, which any future surface that
summarizes a mind must consult before rendering.

## Absence is not neutrality

`affect` is `null` unless the passage shows an emotional state; a null
seeds nothing and the card's `initial_state` stands, exactly as before this
change. The alternative — a zero-valence default — would silently overwrite
every authored opening mood with "calm", which is this codebase's
named failure mode (an empty field failing silently). The same rule holds
per channel: an empty list seeds nothing and falls through to whatever the
card authored.

**The half-filled mind is visible.** `start_story` writes a `greeting_minds`
world key recording, per extracted mind: who, what it resolved to (the
character, the player, or unclaimed), and per-channel counts of what was
seeded and what was refused with the reason (`unrevealed player-mind item`,
`unclaimed presence`, over-cap drops). It is snapshot into checkpoint 0
with everything else, so a rerun of turn 0 keeps the record true.

## Retained minds and promotion

Minds that resolve to nobody at launch (the guards, a porter) are stored in
`greeting_minds` verbatim — `{{PLAYER}}` token intact, so the record stays
persona-neutral — and marked unclaimed.
`promote_background_character` checks the record under the same
`_presence_identity` fold the presence ledger uses; on a match it seeds the
new character's memories, beliefs, stances, and affect exactly as launch
would have, and marks the mind claimed. Promotion is the moment the design
already designates for a presence to acquire memory and psychology; the
greeting's material waits for that moment rather than jumping the gate.

Residuals, registered rather than hidden:

- Attaching an *existing* card to the chat mid-play (`chat_add_char`) does
  not claim a retained mind; only promotion does. The attach path predates
  this design and adding a claim there touches recognition seeding this
  change should not.
- Quick start attaches one card, so "two attached characters in one
  greeting" cannot occur at launch today; the retained-mind record is the
  forward path if multi-card quick start ever ships.
- `revealed_in_prose` on beliefs/stances is provenance-only until a surface
  consumes it (point 4 above).
