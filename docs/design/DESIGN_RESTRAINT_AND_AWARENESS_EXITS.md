# Restraint and awareness: the exits, and the vocabulary

Status: LANDED 2026-08-18 (four commits: the restraint relation, the
restraint exits/view/vocabulary, the widened restraint selector, the widened
awareness kinds). This note is the argument; `AGENTS.md`'s routing rows for
"Going under and waking up" and "Being restrained and getting free" are the
maintained authority.

## The two gates that had never fired

Two deterministic floors were built, documented, tested — and keyed on one
exact spelling of a free string that no beat ever wrote.

* `restraint_map` selected `kind='restraint'`. Measured read-only against
  the owner's live database: **zero** rows spelled `restraint`; 21 spelled
  `physical_restraint`, 3 spelled `restrained`, 24 active across 15 chats.
  The movement block for bound bodies had never once run.
* `awareness_map` selected `kind='awareness'`. Nine active rows carry a
  kind of `unconscious` (6), `asleep` (1), `sleep` (1) or `consciousness`
  (1) with an empty state; chats 24 and 25 hold `unconscious` rows on
  subjects with no canonical awareness row at all.

An agent fixed the restraint selector (a8b1f0f) and the owner reverted it
(30bc3d6), correctly: landing the selector alone switched on a movement
block for 24 live bodies while restraint had **no ending path** — no view
handing the Director a `condition_id` to close, none of the deterministic
exits awareness has. **A gate that can be entered and not left is worse
than no gate.** The order of this work follows from that sentence: exits
first, entrance last.

## What the live rows actually are

The design was drawn from the 24 restraint rows themselves, not from the
shape of the existing code. Classified by hand, then re-measured through
the new record logic (all 24, exactly):

| shape | rows | examples |
|---|---|---|
| unattended bindings | 10 | metal cuffs / bolted interview chair, chats 77–80 — one scenario family, six rows redescribing the same cuffs on one body |
| live grips by a named body | 6 | `restrained_by: "Dr. Moon"` (a hand on an arm), `blocked_by: "The Doctor"` (an arm across a doorway), `enveloped_by: "Elyndra's entrance"` |
| holds naming no holder | 8 | embraces whose own description says "no actual restraint … beyond the intimate proximity"; **the subject** gripping a console lever (`type: "grip"`); a row whose entire state is the string `"active"` |

A flat restrained-yes/no reading — what the reverted commit implemented —
immobilises all 24, including the embraced, the lever-holder, and the
fieldless row. The corpus is the argument that restraint is a **relation**:
an agent, a means, a subject — and that the rungs name different physics.

## The design

### Restraint is a relation with two persistence classes

`RESTRAINT_LEVELS = (held, bound, pinned, encased)` already existed. What
the code never honoured is what each rung *is*:

* **Standing** (`bound`, `encased`, and `pinned` by a mass): holds with
  nobody attending it. A knot stays tied when the tier walks away. Blocks
  self-relocation until something ends it.
* **A hold** (`held`, and `pinned` by a body): a live relation between two
  bodies. It blocks only while its named holder is co-present and
  conscious; it **ends by itself** when that stops being true; and a hold
  that names no holder the scene can vouch for blocks nobody — a two-body
  relation missing one endpoint is a description, not a mechanism.

Records read the rung from the fields beats actually write
(`restraint_type`, `type`; no live row carries `level`) and the holder from
the fields beats actually write (`restrained_by`, `blocked_by`, `held_by`,
`enveloped_by`), with the holder resolvable from inside a phrase ("Dr.
Moon's hand"). Level tokens are read from token-shaped fields **only**,
never from prose fields — a cue scan on prose is negation-blind, and a live
description saying "not a binding restraint" contains the word "restraint".
Empty evidence reads `held` (claims least), not the old `bound` (claimed
most on nothing). Per-subject collapse is strongest-wins, because
restraints are additive facts, unlike awareness levels, which are exclusive
states of one mind and collapse newest-wins.

### Which endings are the engine's, and which are the Director's

From the brief's list — a person unties you, you work free, the material
fails, the holder is knocked out, you are carried away still bound:

| ending | whose | mechanism |
|---|---|---|
| the holder lets go / leaves / goes down | engine | `_restraint_exits` rule 1: a hold whose holder is **positively** in another room or below waking has physically ended. Unknown positions keep the hold (absence of data is not departure); an unresolvable holder is never auto-ended (ending what cannot be verified is adjudication) |
| a completed release the prose asserts | engine (encoding only) | rule 2: `_RELEASE_CUE` over `resolved_event` only — the Director adjudicated the release when it wrote the sentence; the floor encodes it. Declared acts are attempts; dialogue is a plan |
| untying as a decision, working free, material failing, contested escapes | Director | the `active_restraints` payload block names each condition_id, holder, liveness, and duration, and the body specialist's sheet now carries a RELEASE IS YOUR JOB contract mirroring WAKING IS YOUR JOB |
| carried away still bound | neither ends it | the movement floor's carried-exemption: containment is the restrainer moving them |
| time passing | nobody | a rope stays tied all night. Deliberately **no clock exit**, unlike sleep |

There is also deliberately **no player-declaration exit**, unlike awareness
rule 1: an awareness gate takes the player's view and their next move (a
chat that cannot be played), while a restrained player still perceives,
speaks, struggles, and plays — blocking their walk with a warning is
legitimate adjudication of objective causality, and the warning now names
the condition_id to release.

### The vocabulary, at every layer it can drift

The class failure — a word a model may write that a reader silently narrows
— is answered three times, because each answer covers a different tense:

1. **The writer** (future rows): the body specialist's conditions chunk now
   publishes `kind:'restraint'`, `level ∈ {held|bound|pinned|encased}` with
   a choose-by-what-survives-the-holder-leaving rule, the requirement that
   a hold name its holder, and the instruction not to file embraces or a
   body's own grip as restraint. Both language packs.
2. **The reader** (standing rows, and models that drift anyway): family
   predicates. Restraint matches a family of restraint *words* by
   word-splitting (`physical_restraint`, `restrained`); awareness matches
   **whole kinds only**, because its family members are level words and
   word-splitting would read `preparing_for_sleep` — a live row describing
   a body awake at a futon — as `sleep`.
3. **The ending** (round-trip): an ending re-emits the row's **own** kind
   under the same condition_id, and every overlay recognises the family, so
   a row entered under any spelling can be left under it.

### Awareness kinds: answering the previous agent, not overriding them

The reasons for declining to widen were (a) reading the level off the kind
is an inference, and (b) gating a mind wrongly costs more than not gating
it, since a gated mind runs no character step.

(a) fails for the rows in question: `unconscious` *is* a level word — the
model filed the level in the kind slot, which is spelling, not psychology.
It holds for `consciousness` (the faculty, not a state — the live row is
`partial_consciousness`, a body coming to) and `preparing_for_sleep`, which
therefore stay unread. (b) was true, and the exits dissolved it: the
widening landed after `_awareness_exits`, so a wrongly-gated player is
freed by their own next declaration and a sleeper by a rouse or the clock,
and every widened row reaches the Director each beat with its condition_id.

## Measured impact at switch-on

Restraint (all 24 rows classified through the shipped logic):

* **10 rows block unconditionally** — the cuffs/chair rows of chats 77–80,
  where the player is strapped to an interview chair *in the fiction*.
  Faithful, releasable, and the six chat-80 redescriptions are outvoted
  correctly under strongest-wins.
* **6 rows block through a live holder** and end by themselves when the
  holder is gone or under.
* **8 rows block nobody** (embraces, lever grips, the fieldless row).

Awareness (all 9 kind-spelled rows): chats 23/27 unchanged (newer canonical
dazed rows win); chats 24/25 unchanged today — their subjects are branch
uids no perceiver name matches, a standing identity-fold gap this work
neither opens nor closes; chats 40/44 gate the player for at most one beat
on resume, until their first input fires the declaration exit — the exact
escape hatch chat 40 lacked when its incident happened; chat 59
(`preparing_for_sleep`) and chat 44's `consciousness` row deliberately
still gate nothing.

## Residuals — known, and deliberately not landed here

* **The chats-24/25 uid gap.** Condition subjects written as scene-entity
  uids match no perceiver's display name, so those rows are inert under
  any selector. The fix is identity folding (`same_subject` /
  `normalize_scene_subjects` territory), not selector widening, and
  folding `world_conditions` subjects touches commit, restore, and
  branch-remap paths — its own change with its own tests.
* **Partial release granularity.** Rule 2 ends every record on a released
  subject; one-cuff-of-two is the Director's to re-impose, and the warning
  says so. Prose attribution cannot pick which of six redescriptions a
  sentence meant.
* **`_RELEASE_CUE` precision is designed, not corpus-measured.** There are
  zero historical release sentences to measure against (no restraint has
  ever ended). The cues are completed-release verbs with the transitive
  object held in a lookahead; the known hazard ("releases a breath") is
  tested. Re-measure once live beats exist.
* **Restraint synonym and holder-field tables are English.** Same standing
  gap as `_RESTRAINT_SYNONYMS` had before this work; owner decision 2
  (route recognizers through the packs) covers the class.
* **`consciousness` rows stay unread forever** under this design. If a
  model starts writing them at volume, the fix is the prompt, not the
  predicate — the word does not say which way the body is crossing.
