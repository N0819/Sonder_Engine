# 23 — Conduct and reflection

(22 is the deliberation-surface experiment, shelved unproven on the
`character-experiment` branch; this number is taken so the two are never
confused.)

## The structural finding

The character loops run BEFORE `director_resolve`. So a mind wrote its
memory of a beat — `remember_lines`, `belief_updates`, `mind_model_updates`,
`relationship_updates`, `memory_effects` — from its PRE-RESOLUTION view:
from what it meant to do, before it knew whether the act landed or how
anyone answered. `perception_outcome` then handed every mind a scrubbed
view of the resolved beat, and nothing ever re-asked it. Live example:
Elyra's mind-model update about Hinami was authored before Hinami collapsed
onto her. Salience — the thing retrieval searches on forever after — tracked
what a character *meant* to do.

## The design

**CONDUCT** stays where it was, pre-resolve: perceive, appraise, weigh,
decide, act. The Director adjudicates what it declared. Its sheet is the
monolith minus the writing law (a byte-identical recomposition of shared
segments — the Director's specialist-sheet precedent, pinned by test), its
decision procedure's "update mind models" step becomes its reading half, and
a note says where the updates went.

**REFLECTION** is new, after `perception_outcome`, beside the narrator: one
pipeline step (`reflection_loop`), inner fan-out per mind that acted, each
call reading that character's OWN scrubbed outcome view and observations,
its OWN declared conduct, its OWN ledgers exactly as conduct received them
(the conduct-time stash), and nothing else. Never the Director's resolution,
never another mind's view. Nothing between it and commit reads it, so its
wall-clock cost is what it exceeds the narrator by.

A mind is not a set of independent channels: reflection is not a specialist
of conduct. It is the same mind at a later moment, with the one thing the
earlier moment could not have — the outcome.

## The engine detects, the mind answers

The unifying mechanism, taken from the Assistant repo's cognition suite and
from this engine's own numbered beat events:

- **The expectation gap is computed by code.** Conduct already declares
  `appraisal.expectation` and the selected candidate's `expected_outcome`;
  nothing ever compared them to the outcome. Now the engine does —
  stemmed-content containment of expectation in outcome view, pronouns
  dropped (the two texts systematically disagree about person), delivered
  as a MEASURE with the compared texts beside it, never a verdict. The
  model's own surprise introspection is measurably unreliable
  (self-reported novelty: 0.65 mid-plateau, 0.15 at the actual climax). A
  prediction a model grades itself against is not a prediction.
- **The gap is the occasion dispute and ponder never had.** `ponder` fired
  0 times in 3,083 stored results; the diagnosis is emission-side — every
  clause of its instruction was a brake, it was absent from the output
  contract and the schema example, and nothing ever invited it.
  `memory_disputes` (15 of 3,083, 0.5%) proves contract presence is
  necessary but not sufficient: what both lack is a moment that ASKS.
  Reflection's gap block asks: did this contradict a belief? re-read a
  memory? raise a question your own past might answer? Ponder emits from
  reflection as a typed field with neutral language; its existing delivery
  plumbing (`memory_ponder` → next conduct's `deliberate_recall`) is
  untouched.
- **Refusing to update is a real act.** With reflection as its own moment,
  a mind that declines to revise a disconfirmed belief can SAY so —
  `held_beliefs [{claim, why_held}]` — instead of the refusal being
  indistinguishable from never noticing. The engine changes nothing on a
  hold; the record is the point. This is the firewall's own argument (a
  mind acting on a false belief is generative) given a place to happen.
- **Regret gets a home.** `choice_review {verdict, why}` — satisfied,
  regret, mixed, vindicated — is the mind's stance toward its own CHOICE,
  distinct from liking the event. Persisted to `cstate.last_choice_review`
  and surfaced to the next conduct call, so hindsight carries forward as
  self-knowledge.
- **Agency attribution and theory of mind move to the moment that knows.**
  `mind_model_updates` now form from how the other actually answered;
  memory encodes at outcome, with salience from the outcome.

## What moves, what stays, what falls back

The seven fields (`schemas.CHARACTER_REFLECTION_FIELDS`) move; appraisal,
affect, wants, sequence, interaction, salience stay conduct's. Commit's
per-character overlay prefers the reflection result for exactly the moved
fields (plus a reflection-set ponder); with the split off, on any stored
turn, or when a reflection call fails (fail-open, warned), the conduct
result stands unchanged — byte-identical default, `character_reflection`
setting, off.

## Measured (baseline: one monolithic call, 16.4k-token sheet, ~10k-token
payload, output 4.1–9.9k tokens tracking wall clock)

- conduct sheet 15.6k tok (−4%); reflection sheet 2.0k tok (−87% vs the
  monolith); reflection payload ≈4.2k tok on the live climax beat's shapes
  (dominated by the outcome view + observations — the cargo it exists to
  read).
- conduct output sheds the moved fields: measured 1,374 chars/beat of
  11,873 (12%) across 190 recent live results — that 12% leaves the
  player's critical path entirely, since reflection runs beside the
  narrator.
- the split's primary win is cognitive correctness, not latency: memory
  written from outcome, iterating theory of mind, computed surprise. The
  latency claim to verify live is "conduct −12% output, reflection hidden
  behind the narrator"; `tools/deliberation_ab.py --experiment reflection`
  is the instrument.

## Residuals

- The conduct sheet is still 15.6k tokens. The next real prompt-size lever
  is scene-conditional chunking (the prose-author precedent), which is a
  separate run.
- A resumed turn whose conduct was rehydrated rather than re-run reflects
  with a degraded self-slice (the in-memory stash does not survive resume);
  outcome and conduct still arrive, and the payload tolerates absence.
- `fire_rates.py` reads conduct-result fields; post-split, the moved fields
  live on reflection results and need a second reader there before any
  fire-rate claim about them is made.
- Salience: reflection does not yet re-author the episode's salience
  number; commit still takes conduct's. Moving it requires touching the
  memory mint, deliberately deferred.
