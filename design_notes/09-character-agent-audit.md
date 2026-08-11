# Character agent audit — what determinism can take without touching depth

Optimization audit of `character_step` and its psychology stack, on the
constraint that **nothing here may reduce output quality or internal
simulation fidelity**. Corpus: the read-only snapshot at `engine.db`
(2,296 turns), opened `mode=ro`. All token figures are chars/4 and say so.
No live model calls were made.

**Era caveat.** Stored character variants are POST-normalization
(`_normalize_character_output`, `_ground_observation_citations`,
`norm_sequence` all run before storage — `agents/character.py:3201-3222`),
and the corpus spans several contract versions. Every load-bearing number
below is therefore re-measured on the **recent era only**: turn id ≥ 1932,
chats 64–69, n = 404 character-call results — the span that includes the
owner's live benchmark chat (64).

---

## The headline shape

| | recent era, per character LLM call |
|---|---|
| Stored result size | mean 9,694 chars |
| Model-authored portion | **~1,974 tok** (chars/4) |
| Engine-written portion (stored beside it) | ~437 tok |
| Character calls per turn (stored results) | **1.01** (332 of 399 turns exactly 1) |

At 64 tok/s, ~1,974 output tokens ≈ **31 s of pure generation per call**,
× 1.0–1.5 calls ≈ the measured 40.7 s/turn. That closes the books on the
`director_resolve` question: **the character stage does NOT have resolve's
84%-discard profile.** The throughput math (64 tps × ~31 s ≈ 2,000 tok)
matches the stored size, so there is no large hidden reasoning-token or
discard overhead — what the model writes, the engine keeps. The waste here
is a set of specific fields, not a lost majority.

Every 64 output tokens removed = 1 second per call.

---

## Confirmed waste, ranked by seconds saved

### 1. The invisible second call: correction retries and JSON repairs — up to ~8–15 s on affected turns, **instrument before touching**

`character_step` re-issues the ENTIRE call (full payload + full ~2,000-tok
output) when the deterministic repetition screen trips
(`agents/character.py:3163-3171`), and `complete_validated_json` adds a
temperature-0 repair call on validation failure plus candidate-walking
(`agents/common.py:1306-1337`). **None of these appear anywhere in stored
data** — a retry that succeeds is indistinguishable from a first draft.

What IS measurable:

- Floor: 14 "repetition retained after contextual review" engine notes in
  404 recent calls — retries that fired AND failed again — so the retry
  rate is **≥ 3.5%**, true rate unknown.
- The owner's live benchmark measured **1.25–1.50 provider calls/turn**
  while the stored corpus holds **1.01 results/turn**. If that 0.25–0.5
  gap is retries/repairs (it is the only mechanism I can find that makes a
  provider call without a stored result; reaction+interaction double-runs
  are excluded by `already_reacted`, `agents/loops.py:514-531`), retries
  are costing **~8–15 s/turn on the sessions where they fire** — the
  single largest number in this audit, and the least certain.

Recommendation, in order: (a) add one warning line when a correction retry
or JSON repair fires (an `_engine_notes` entry costs nothing and rides the
existing channel) and re-measure; (b) if confirmed, consider making the
correction retry a **bounded delta** — the current design deliberately
re-solves the whole decision ("solve the decision as a whole instead of
whack-a-mole phrasing", `agents/character.py:3117-3122`), so a cheaper
retry that regenerates only `sequence`/`response_candidates` while pinning
the already-valid psychology fields is a QUALITY question the owner must
judge, not a free win. I am not sure a partial retry preserves coherence
between the new line and the already-emitted appraisal; say so out loud
before building it.

### 2. Dice-class transcription: `active_state.stress` and `.hedonic` numbers — ~0.5 s/call, **provably discarded, nothing lost**

The prompt's required JSON demands
`"stress":{"activation":0.0,"load":0.0,"coping_mode":"","overloaded":false}`
and `"hedonic":{"pain":0.0,"pleasure":0.0,"source":"","released":false}`
(`prompts.py:1746-1748`). Commit reads exactly TWO of those ten fields:

- `hedonic.released` — `commit.py:5856,5891` (the discharge declaration,
  rightly the character's own; true on 21 of 289 recent emissions);
- `stress.coping_mode` — `commit.py:5901` (pass-through label).

Everything else is recomputed wholesale by
`psychology_runtime.resolve_hedonic`/`resolve_stress`
(`commit.py:5885-5902`) from the model's own **appraisal** plus prior
state, and the model's numbers never reach `st["active_state"]`
(`commit.py:5916-5929`). Measured: 289/404 recent calls emit both dicts,
~55 tok combined, of which the consumed signal is ~10–15 tok.

Fix: shrink the template to `"stress":{"coping_mode":""}` and
`"hedonic":{"released":false}`. `LenientModel` and the `StressState`/
`HedonicState` defaults (`schemas.py:2275-2301`) already tolerate the
missing keys, and old providers emitting the full shape stay valid.
Nothing-lost argument: the discarded numbers cannot influence state by
construction; the model still RECEIVES its full committed stress/hedonic
in `self.active_state` next beat, so its self-knowledge is untouched.
This is exactly the resolve-`dice` precedent. ~30–40 tok ≈ **0.5 s/call**.

### 3. `considered_responses` — ~0.8 s/call, **unread, duplicates response_candidates; small CoT risk**

Documented in the schema itself as "internal deliberation scratch --
nothing downstream reads it (it exists for inspecting a character's
reasoning in the step/variant viewer)" (`schemas.py:2836-2843`); grep
confirms no consumer outside two offline tools, one of which
(`tools/agency_bench.py:192`) deliberately excludes it. The structured
deliberation lives in `response_candidates`, which IS consumed (the
`selected` candidate feeds the move ledger `agents/character.py:186-190`,
the repetition screen, and settled-want normalization). Recent era: 61.4%
emit it, mean 53 tok, and 137/404 calls emit BOTH fields — the same
options written twice.

Fix: drop `"considered_responses":[]` from the required JSON
(`prompts.py:1734`) and from DECISION PROCEDURE step 4's phrasing; keep
the schema field so legacy output stays valid. Honest quality note: a
freeform pre-list is plausibly chain-of-thought that seeds better
candidates. I judge the risk small because `response_candidates` already
forces the same deliberation with more structure — but it is a judgment,
not a measurement. A cheap A/B on stored payloads would settle it.

### 4. `active_state.goal` — ~0.3 s/call, **overwritten 99.5% of the time, one reader needs a change**

Commit replaces the emitted goal string with the enacted want's own text
whenever `wants` + `enacted_want` are valid — `commit.py:5913-5915` — which
in the recent era is **402 of 404 calls** (mean 21 tok discarded). The
committed goal the whole engine routes on is the want text, not this field.

Two consumers of the RAW variant field exist and must be handled before
the template drops it:
- `_recent_self_moves` reads `result.active_state.goal` off stored
  variants (`agents/character.py:191-192`) — derivable identically from
  `wants[enacted_want].want`;
- the commit fallback for the 0.5% of beats with malformed wants
  (`commit.py:5915`) — should fall back to the PREVIOUS goal rather than
  empty if the field goes away.

Smaller and slightly fiddlier than #2/#3; fine to defer.

### 5. Appraisal prose scratch (`goal_relevance`, `expectation`, `uncertainty`, `emotion`) — ~2.0 s/call, **engine-unread but likely load-bearing; A/B first, do not cut blind**

None of the four is read by any engine code: `affect.appraise` consumes
`goal_impacts` + the six numeric axes + `somatic_impact`/`memory_echo`
(`affect.py:456-560`), `resolve_stress` consumes
novelty/controllability/coping/norm + goal_impacts
(`psychology_runtime.py:262-296`), and the emotion TAG is derived
deterministically from goal impacts (`_emotion_for`), not from the
model's `emotion` string. Combined recent-era cost: ~130 tok/call.

**But**: these are the appraisal-theory deliberation that precedes the
numbers, and the numbers are demonstrably real — the six axes sit at
template defaults in only 0–2% of recent emissions, which is a mechanism
that fires, not scaffolding. Cutting the prose may degrade the numeric
axes and `goal_impacts` it leads up to; that is precisely the
internal-simulation quality this audit is forbidden to spend. Verdict:
flagged, not recommended. If the owner wants the 2 s, run a
`contract_bench`-style A/B on stored payloads first (the repo's own
precedent for contract changes under narrative pressure).

### 6. Not worth calling optimizations (the 0.02 s class)

- `salience` (4 tok): consumed (`commit.py:5571`) — keep.
- `mood` (11 tok): fallback when `affect.surface.label` is absent — keep.
- Empty-scaffold zeros: `memory_modulation` is fully empty in only 8% of
  recent calls (39 tok when empty), `somatic_impact` in 4% (14 tok).
  ~4 tok/call amortized; an "omit when empty" license risks contract
  degradation for nothing. Leave it.
- Zero-delta `relationship_updates`: 2% of rows. Real product otherwise.

---

## The psychology-duplication verdict (hypothesis 2)

**Mostly refuted, narrowly confirmed.** The division of labor is already
right: the model authors the *appraisal* (its legitimate, private input)
and `psychology_runtime`/`affect`/`theory_of_mind` deterministically own
persistence, bounds, decay, absorption, and caps. The model is NOT asked
to re-report beliefs, associations, charge, saturation, strain, load,
absorption, or hypothesis selection — those are computed. The one real
duplication is finding #2 above: ten stress/hedonic fields requested where
two are read, worth ~0.5 s/call. There is no larger prize here, and that
is a compliment to the existing architecture, not a failed audit.

Also checked and clean under hypothesis 1 (discarded/overwritten output):
sequence `event_id`s are engine-assigned (`assign_event_ids`), the
`speech`/`speech_volume`/`action`/`actions` mirrors are engine-written
projections of `sequence` (`agents/common.py:1863-1888`), and
`observations_used` is engine-rebuilt as `present + past`
(`agents/character.py:944-949` — "The model never needs to emit this field
again"). The prompt asks for none of them, so no output tokens are being
spent — they are storage duplication only (~437 tok/call stored, ×3 copies
inside each `interaction_loop` step via `rounds[].result` +
`character_results` + `combined_declarations`, `agents/loops.py:915-937`).
Zero latency cost; flag for a storage pass someday, not this one.

## Call count (hypothesis 4)

Already lean. Recent era: 1.01 stored results/turn; interaction loop mean
1.06 calls with 89% of loops at exactly one; reaction loop ran on 92 of
2,164 turns corpus-wide. The early-exit/deferral machinery is doing its
job. The only call-count lever is the invisible retry/repair traffic
(finding #1).

## Payload (hypothesis 5)

Deprioritized per the brief (output dominates at 16 ms/tok). One
observation worth keeping: the heavy payload sections — annotated exits,
verdicts, move ledgers, en_route, recalled places — are all deterministic
derivations from committed state, i.e. the engine already does this the
right way; none of them buys back output tokens if trimmed. No large
unused payload section was identified from the code path; I did not
attempt token-level payload measurement because payloads are not stored.

---

## Judged too risky to touch, and why

- **`appraisal.goal_impacts`, the six numeric axes, `somatic_impact`,
  `memory_modulation`** — the sole legitimate input to drive strain,
  rupture, stress, hedonics, affect, and project service. Axes are
  non-default in 98–100% of recent emissions: live signal.
- **`response_candidates`** (170 tok where emitted) — the deliberation
  record the move ledger, repetition screen, and inhibition/norm_conflict
  texture read; this IS the internal simulation.
- **`mind_model_updates`, `belief_updates`, `association_updates`,
  `relationship_updates`, `remember_lines`, `memory_disputes`,
  `memory_effects`** — the products the engine exists to elicit
  (inference is the product, not the risk).
- **`manifest` + tell `because`** — only the model knows the private
  ground; `ground_tells` derives one deterministically ONLY as a fallback.
- **Evidence citations everywhere** — they are the firewall's audit trail;
  `_ground_observation_citations` depends on them.
- Anything under CLAUDE.md's psychology warning: these fields fail
  silently fifty beats later. Every recommendation above is a field the
  engine PROVABLY discards (2, 4) or provably never reads (3, 5); nothing
  proposed removes an input to any deterministic psychology floor.

## Could not verify

- **Raw model output vs stored output** — variants are post-normalization,
  so whether models still emit legacy `observations_used` (or the
  sequence mirrors) is unknowable from the DB. If they do, a one-line
  "do not emit observations_used" is free; unmeasurable until logged.
- **Retry/repair frequency** (finding #1) — needs one counter.
- **Whether the prose scratch fields carry CoT value** (findings #3, #5)
  — needs an A/B, not an opinion.
- **glm-5p2-fast reasoning-token overhead** — throughput math says ≈none,
  but only provider-side token accounting can confirm.

## Bottom line

| Action | s/turn saved (at 1.0–1.5 calls) | Risk |
|---|---|---|
| Instrument retries/repairs, then bound them | unknown; potentially the 0.25–0.5 extra calls/turn ≈ 8–15 s where they fire | measure first |
| Drop stress/hedonic numbers (keep `released`, `coping_mode`) | 0.5–0.9 s | ~zero (provably discarded) |
| Drop `considered_responses` | 0.8–1.2 s | small (CoT), A/B cheap |
| Derive `active_state.goal` from enacted want | 0.3–0.5 s | small (two readers to update) |
| Trim appraisal prose scratch | 2.0–3.0 s | REAL — A/B before believing it |

Safe-today total: **~1.6–2.6 s/turn** of the 40.7 s. The honest read is
that this stage's output is ~85–90% genuine product; the big remaining
lever is not any field but the invisible second calls.
