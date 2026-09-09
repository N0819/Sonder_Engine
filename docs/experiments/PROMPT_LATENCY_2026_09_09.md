# Where a turn's model time actually goes — 2026-09-09

Corpus: the 2,006 rows of `llm_capture` in the owner's `engine.db`, joined to
`llm_blobs` for real system/payload/response byte counts. Calls were clustered
into turn-runs by a 90s gap rule (a `turn_id` spans reruns and rerolls made
hours apart, so `turn_id` alone is not a turn); a run counts only if it
contains both `interaction_loop` and `narrator`. **146 complete turn-runs.**
Token counts are bytes/4 throughout — a ratio, not a tokenizer.

Provenance for everything below: `llm_capture.duration` and `started` are
measured, not modelled. Every specialist inherits the `default` model
(`google/gemini-3.8-flash`), so cross-specialist comparison is one model
under different input sizes — that is what makes the cost fit legitimate.

## 1. The turn

| | seconds |
|---|---|
| model wall clock, median | **91.2** |
| model wall clock, mean | 118.8 |
| sum of call durations | 127.3 |
| **parallel speedup** | **1.07x** |

12.7 model calls per turn and they buy 7% of concurrency. The fan-out is
parallel *within* a stage, but the stage is serial in two phases — the prose
author runs alone, and only when it finishes do its specialists start. A
representative turn (4123):

```
   0.0 ->   4.1  (  4.1s)  director_interpret   director        <- prose author
   4.1 ->  18.0  ( 13.9s)  director_interpret   director_body   <- starts after
  24.3 ->  60.3  ( 36.0s)  interaction_loop     character_major
  60.4 ->  76.0  ( 15.6s)  director_resolve     director        <- prose author
  76.0 ->  86.3  ( 10.3s)  director_resolve     director_contact
  76.0 ->  79.5  (  3.5s)  director_resolve     director_body   <- these two do overlap
  86.9 -> 103.1  ( 16.2s)  narrator             narrator
```

Median wall per stage: `interaction_loop` 37.7s, `director_resolve` 23.4s,
`director_interpret` 10.7s, `narrator` 5.3s.

## 2. The calls

Mean over all runs, n > 20. IN is system + every payload blob.

| step / role | n | s | IN tok | OUT tok |
|---|---|---|---|---|
| interaction_loop / character_major | 159 | 39.7 | 32,359 | 2,520 |
| director_resolve / director (prose) | 225 | 16.9 | 15,611 | 1,160 |
| director_resolve / director_contact | 150 | 10.7 | 9,919 | 211 |
| director_interpret / director (prose) | 184 | 8.5 | 9,016 | 610 |
| narrator / narrator | 172 | 8.3 | 15,546 | 308 |
| director_interpret / director_contact | 126 | 7.6 | 9,443 | 77 |
| director_resolve / director_spatial | 128 | 7.5 | 9,217 | 161 |
| director_resolve / director_body | 151 | 6.5 | 9,349 | 85 |
| director_resolve / director_social | 84 | 4.7 | 3,892 | 222 |
| director_interpret / director_body | 145 | 4.4 | 9,102 | 49 |
| director_interpret / director_spatial | 105 | 4.4 | 8,027 | 55 |
| director_interpret / director_objects | 77 | 3.8 | 5,635 | 43 |
| director_resolve / director_objects | 114 | 3.7 | 6,069 | 56 |
| director_interpret / director_social | 124 | 2.7 | 3,236 | 46 |

**The specialists are prefill-bound, not decode-bound.** They emit 43-222
tokens. The four interpret specialists whose output is within 12 tokens of each
other (43-55) differ only in how much sheet they read, which fits

> **duration ~= 1.8s + 0.29s per 1,000 input tokens**

social 3,236 IN -> 2.7s; objects 5,635 -> 3.8s (fit 3.4); spatial 8,027 -> 4.4
(fit 4.1); body 9,102 -> 4.4 (fit 4.4). Contact is the one that does not fit
(7.6s against a fit of 4.5s) and is worth its own look.

So for a specialist, **shrinking the sheet is the whole lever** — its answer is
already almost nothing.

## 3. Most specialist calls answer nothing

| role | calls | non-empty | **empty** |
|---|---|---|---|
| director_objects | 191 | 24 | **87%** |
| director_body | 296 | 71 | **76%** |
| director_social | 208 | 91 | **56%** |
| director_spatial | 233 | 119 | **49%** |
| director_contact | 276 | 179 | **35%** |
| director_offscreen | 10 | 0 | **100%** |

"Empty" = every owned channel absent or `{}`/`[]`, ignoring `resolved_events`,
`phase_sources` and `notes`. Weighted by each role's mean duration that is
**~3,900 seconds of the corpus's ~21,150 seconds of model time — 18% — spent
returning nothing.** `director_scopes.py` already argues that a hand the
ruling does not name should not be called; the dispatch gate is admitting far
more than the ruling names.

## 4. The five sheets are the same sheet

Pairwise similarity of the five `core.txt` files: 0.88-0.93. 14 of 25 distinct
lines are common to all five — **7,387 chars (~1,846 tok) of identical text,
read 9-10 times per turn: ~18,000 input tokens of pure repetition per turn.**

Sheet sizes (chars): spatial 37,816, contact 32,316, body 31,749, objects
29,928, social 24,491. Largest single chunks: `rooms` 16,678, `entities`
13,994, `contact_ops` 12,440, `conditions` 11,871.

## 5. The specialist mostly re-types a ledger that already exists

`changes_asserted` (`llm/schemas.py:AssertedChange`) is already a flat typed
ledger — `category`, `subject`, `change`, plus `actor`/`actor_part`/`target`/
`target_part`/`action`/`intensity`/`rhythm`/`detail`/`substance`/`placement`/
`target_interior` — and `_CATEGORY_CHANNELS` in `director_scopes.py` is already
the code that routes a category to a channel. Today both exist only to *decide
which specialist to call*.

Measured against real captured pairs, what a specialist adds over the manifest
entry it was dispatched by:

| channel | already in the ledger | **not** in the ledger |
|---|---|---|
| `contact_ops` | actor, actor_part, target, target_part, detail, target_interior | **op, relation, motion, manner, erogenous** |
| `contact_action_ops` | actor, action, contact_ref, intensity, rhythm, detail | **op** |
| `substance_ops` | actor, actor_part, target, target_part, substance, placement, detail, target_interior | **op, source, source_part, amount, amount_band** |
| `inventory_ops` | detail | **op, object_id, from_id, to_id** |
| `public_evidence` | — | **source_id, salience, speech_acts** |

Turn 4162, verbatim. Prose author:

```json
{"category":"contact","subject":"Hinami",
 "change":"Hinami lifts her buttocks from the sand shelf, ending sitting contact.",
 "actor":"Hinami","actor_part":"buttocks","target":"sand_shelf","target_part":"surface"}
```

Contact specialist, 10.3s and 9,919 input tokens later:

```json
{"op":"remove","actor":"Hinami","actor_part":"buttocks",
 "target":"sand_shelf","target_part":"surface"}
```

One field. `op` — and the sentence it was derived from already said "ending".

This is the "is this fact stored twice?" question with a stopwatch on it, and
they *did* disagree in that same beat: the manifest filed "sand brushed from
her travel shorts" under `conditions` and routed it to `objects`, and the
contact specialist independently re-derived it as a fourth `contact_ops` entry
nobody asked it for. Its `phase_sources` also mapped `contact_ops.0` to
`event_id` 1 — the *pose* entry — so the event-id echo was off by one on this
beat. Worth a separate look; it is not what this note is about.

## 6. The character stage is 40% of the turn and is decode-bound

37.7s median, 2,520 output tokens, 32,359 input, and per
the 2026-08-14 cache measurement its prefix is effectively never cached.
Where its output goes:

| field | tok | % of output | filled |
|---|---|---|---|
| `appraisal` | 783 | 32% | 100% |
| `active_state` | 464 | 19% | 92% |
| `sequence` | 326 | 14% | 95% |
| `mind_model_updates` | 216 | 9% | 86% |
| `manifest` | 158 | 7% | 87% |
| everything else (21 fields) | ~466 | 19% | |

Six of the 27 declared fields were filled on 1% of calls or fewer
(`response_candidates`, `observations_used`, `action`, `considered_responses`,
`speech`, `present_evidence_used`) and three were never filled at all
(`memory_evidence_used`, `actions`, `follow_op`).

Stated without a recommendation attached, because 51% of this stage's output is
`appraisal` + `active_state` and that is the engine's product, not its fat —
see prove a cut with a test first before cutting a byte of it.
