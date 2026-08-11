# 06 — Quality baseline: what "current quality" measurably is

The acceptance bar for the deterministic composer is exact: **same quality as
the current engine, just faster.** This note makes that bar falsifiable. It
reports the measured quality of the existing model-generated perception
corpus — 2,296 turns, 9,357 stored non-empty views, 62 chats — against the
typed entitled-fact set, plus the retrieval-discrimination and latency
baselines a composer must meet or beat. No number below is a similarity score
against stored model prose; every fidelity metric is grounded in structured
entitlement (delivery gates, recognition ledgers, concealment, spatial
hearing), per the branch's own verification plan (03 §4).

**Harness** (new files, no engine file edited):

- `tools/perception_quality.py` — Metric A: fact fidelity, both directions.
  `score_view(view_text, entitlement)` is a pure function; a composer is
  scored by rendering its view for the same (turn, observer) and calling the
  same function. CLI: `python tools/perception_quality.py --db <corpus>`.
- `tools/perception_retrieval.py` — Metric B: view template stats, memory-bank
  spread/collision from the stored play-time embeddings, lexical-proxy
  self-retrieval MRR, and the marked hook for real embeddings.
- `tools/perception_judge.py` — Metric C: blind-judge scaffold (structure
  only; no model burned). Judges score against the fact sheet, never against
  stored prose, and `CalibratedJudge` refuses verdicts until a measured
  false-positive-rate calibration passes.
- `tools/perception_latency.py` — Metric D: perception model calls per turn
  and share of turn wall-clock, from `turns.created`/`variants.created`.
- `tests/test_perception_quality.py` — 20 fast-tier tests pinning both
  directions of every metric on synthetic data (no DB).

All database access is `file:...?mode=ro`; nothing was written to the corpus.

---

## Era segmentation (read this before the numbers)

The corpus spans engine versions. The identity floor (`_scrub_unknown_
identities`) first fires in stored warnings at **turn_id 1503** (data-derived:
first `"scrubbed unearned identity"` engine note; 828 of 2,296 turns at or
after it). Everything is reported twice:

- **all_turns** — the whole corpus, i.e. what the memory banks and archives
  actually absorbed over the project's life;
- **identity_floor_era** (turn_id ≥ 1503) — the closest available proxy for
  "what the current engine delivers". This is the composer's comparison
  segment.

Caveat from the branch coordinator applies: this harness ran on a worktree
based on a divergent release commit. Metric A *reuses engine checkers as
code*, so its exact counts should be re-derived on the correct tree before
shipping gates (symbols listed at the end). Metrics B and D read only stored
corpus data and are base-independent.

---

## A. Fact fidelity (the ship gate)

Scored: **7,822 views** (of 9,357 stored; skips accounted below). Checkers are
the engine's own, run as metrics. "Views" columns count views with ≥1 hit.

### Leak direction (information present without entitlement)

| Violation class | all_turns (7,822 views) | identity_floor_era (3,249 views) |
|---|---|---|
| Unearned identity in view (vs pre-beat `known` ledger) | 524 views, 580 names | 107 views, 107 names |
| … still unearned after the beat (conservative) | 511 views | 104 views |
| … where the observer even HAS a ledger entry | 56 views | 8 views |
| Self-narration (perceiver narrated in third person) | 576 views, 1,116 sentences | 186 views, 329 sentences |
| Invented dialogue (quote nobody spoke this beat) | 31 views | 7 views |
| Undeclared player speech in the player's own view | 83 views | 32 views |
| Unentitled dialogue line present verbatim (hear gate = none) | 34 views, 52 lines | 8 views, 16 lines |
| Concealed-from-observer line present verbatim | 0 | 0 |

Readings:

- **The floor era still leaks identity at ~3.3% of views** (107/3,249) by
  today's own rule. The samples reproduce the documented live defect class —
  the chat-38 case AGENTS.md's `observer_name_scrub` docstring describes
  (canonical names reaching a mind through prose channels the roster scrub
  did not cover) is exactly what these hits look like: the leaked names are
  co-present cast the pre- AND post-beat ledger does not grant. A composer
  whose Layer A picks labels at admission scores **zero here by
  construction**; that is the headline fidelity win available.
- **Self-narration at 5.7% of floor-era views** is the second-largest class.
  Stored views passed the checker of their day; today's checker (pronoun-
  continuation-aware, added later) still fires on them. Same yardstick will
  be applied to the composer, which cannot self-narrate by construction.
- Concealment held at zero in both eras — the concealment redaction path,
  whatever its documented paraphrase holes, left no verbatim concealed line
  in any wrong view. The composer must preserve this zero.

### Under-grant direction (entitled information missing)

| Metric | all_turns | identity_floor_era |
|---|---|---|
| Entitled `full` dialogue lines (hear-gate-derived) | 6,003 | 3,028 |
| … missing verbatim from the receiving view | 481 (**recall 92.0%**) | 191 (**recall 93.7%**) |
| … missing AND same-room under both pre/post scenes (high confidence) | 423 | 164 |
| Same-room spoken-volume lines missing | 362 / 5,146 (93.0% recall) | 161 / 2,659 (93.9% recall) |
| Player's own view, same-room lines missing | 58 / 3,115 (98.1%) | 35 / 1,509 (**97.7%**) |
| Lines not gateable (speaker/observer room unresolvable) | 3,158 | 1,639 |

Readings:

- The player-view number independently reproduces the audit's earlier
  finding (30 of 1,549 same-room lines lost pre-floor): here 35 of 1,509
  floor-era same-room lines are absent from the player's view (2.3%).
- **NPC views lose far more than player views**: floor-era same-room recall
  is 93.9% overall but 97.7% for the player — the heard-line floor protects
  every view, yet NPC views still miss ~1 in 16 entitled lines. Missing
  lines are overwhelmingly `normal` volume (188 of 191), so this is NOT the
  known whisper-gate defect (D1) inflating entitlement.
- **Composer ship gate, restated from the plan and now quantified:** 100%
  delivered-line recall by construction beats a 93.7% baseline by 6.3
  points; zero identity/self-narration/invented-dialogue violations beats
  nonzero baselines in every class. "Same quality" is therefore not the
  right floor for Metric A — the composer should be *strictly better*, and
  anything below these baseline numbers is a regression twice over.

### Coverage, stated plainly

- 1,535 stored views (16.4%) were not scored: 1,374 belong to view keys
  whose character row no longer exists in the snapshot's `chat_chars`/
  `characters` tables (1,328 of them are char ids deleted from `characters`
  after play — no name to score against), 91 are `extra:<pid>` other-player
  views (no per-player ledger model in this harness), 70 are name-keyed
  background-presence views. These views still count in Metrics B and D.
- 87 scored views (14 floor-era) predate the `known` ledger entirely;
  identity checks were skipped there, not passed.
- 3,158 dialogue-line deliveries could not be gated because the speaker or
  observer resolves to no room (mostly unregistered presences speaking, and
  ledgers keyed by uid/alias forms the position map does not carry). They
  are excluded from recall denominators, never counted as hits or misses.
- Hearing is gated on the pre-turn checkpoint scene with the resolve
  `state_diff.positions` overlaid; a "high confidence" miss must also be
  same-room in the raw pre-turn scene. Mid-beat multi-hop movement can still
  misgate individual lines in both directions.

---

## B. Retrieval discrimination

Baselines the composer's shadow-minted bank must meet or beat, from the real
banks (`memories`, episodic kinds, non-archived; embeddings are the stored
play-time vectors — `perplexity/pplx-embed-v1-4b`, 2560-d, present on 100%
of rows).

### View templating (the substrate memory is minted from)

| Metric | Value |
|---|---|
| Stored non-empty views | 9,357 |
| First sentence appears in another view | **73.0%** (6,827) — reproduces the known figure |
| Sentences duplicated verbatim | **74.4%** of 87,185 (prior probe: 72.0% of 77,585 — different sentence splitter, same story) |
| Most common opening | 899 views (the "unspecified area" boilerplate) |
| Distinct openings | 3,894 |

### Memory bank

| Metric | Value |
|---|---|
| Episodic rows | 5,570 across 84 (chat, character) banks |
| Verbatim-twin rate, within-bank (what retrieval suffers) | **14.6%** (815 rows) |
| Verbatim-twin rate, global (the design note's 76.0% basis) | 76.7% |
| "You are in an unspecified area." exact rows | **812** — the pathology commit.py:5511 documented at 356 rows has more than doubled since |
| Near-duplicate collision rate @ cosine ≥ 0.95 (stored embeddings, within-bank) | **14.7%** (820 / 5,566) |
| Mean pairwise cosine within banks (spread; lower = more discriminable) | **0.5297** |

### Self-retrieval (lexical proxy)

Querying with a turn's stored view, does the memory minted from that view
outrank the rest of that character's bank? Char-trigram cosine, ties ranked
pessimistically (a verbatim twin displaces its original — that IS the
failure being measured). 800 seeded queries:

| Metric | Value |
|---|---|
| MRR (pessimistic) | **0.299** |
| Query's own memory ranked 1st | **25.1%** |
| Displaced by an exact-score tie (verbatim twin) | 13.1% of queries |

**Embedding availability, stated:** the corpus embedding model is an online
provider model; no offline equivalent exists here. Spread/collision above
use the stored vectors directly (real data, no new embedding needed). The
query-side MRR uses the lexical proxy; `perception_retrieval.embed_texts_hook`
is the clearly marked seam for re-running it in embedding space once a
provider is configured — do that with the SAME model id on both banks, or
compare nothing.

**Composer gate (03 §4 B, quantified):** composer bank must show within-bank
collision ≤ 14.7%, mean pairwise cosine ≤ 0.5297, self-retrieval MRR ≥ 0.299
(lexical leg, both sides). Given that a quarter of queries cannot even find
their own memory at rank 1 today, this bar is low; the IR-minted episode
renderer should clear it with room.

---

## C. Blind judge — scaffold only, no verdicts yet

Built, deliberately not run (no large-model budget spent):

- The judge is handed a **fact sheet** serialized from the same entitlement
  records Metric A scores against — entitled lines, unentitled lines,
  recognized vs unrecognized identities. It never sees stored model prose,
  so it cannot enshrine the corpus's known defects as a standard.
- `CalibratedJudge.verdict()` **refuses to run** until `calibrate()` has
  measured the judge's false-positive and false-negative rates on synthetic
  labeled cases (planted leak / planted omission / clean) and both are
  inside stated tolerances (defaults: FPR ≤ 0.10, FNR ≤ 0.20, ≥ 24 cases).
  An unparseable verdict counts as a false negative, and a lazy always-clean
  judge fails calibration — both are pinned by tests.
- Recommended use per 03 §4 C: ~200 stratified beats from BOTH corpora
  (stored views and composer views), judged blind to provenance, only after
  calibration passes.

---

## D. Latency — what is actually being bought

From stored timing data only (`turns.created`, `variants.created`; a stage's
duration is the gap to the previous variant's creation; turns with rerolls,
negative gaps, or stalls > 900 s excluded — 1,869 of 2,295 turns usable).

| Metric | Value |
|---|---|
| Perception model calls (≈ non-residue stored views) | 9,333 → **4.06 / turn** (median 3, max 13) — matches the reported ~4.08 |
| Perception seconds per turn | median **9.35 s**, mean 20.1 s |
| Perception share of turn wall-clock | **13.4%** aggregate; median turn 9.4% |
| Total perception wall-clock in corpus | ~10.5 hours of the ~78 usable hours |

Honest limits: variant timestamps include orchestration overhead; per-call
network/provider breakdown is NOT in the corpus and is not estimated here.
What the composer deletes is bounded above by these numbers: roughly 9–20
seconds and ~4 provider calls per turn, ~13% of wall-clock. It does not buy
back the Director's or narrator's time; if a bigger latency win is expected,
it has to come from the reduced token traffic those stages inherit, which
this corpus cannot measure.

---

## What was measured vs inferred

**Measured:** every table above, from the read-only snapshot. Metric A
counts come from running the engine's own checker functions over stored
views with entitlements rebuilt from stored structured data (dialogue_log,
checkpoints' scene + `known` ledger, interpret sequences, character/
background step outputs).

**Inferred/approximate, flagged:** the era boundary (first stored scrub
warning); calls/turn equating one non-residue view to one provider call;
stage durations from variant-creation gaps; hearing gated on checkpoint
scene + position overlay rather than a full mid-beat replay; residue views
detected by their fixed template leads.

**Not measured, and why:** embedding-space self-retrieval MRR (online-only
embedding model; lexical proxy + hook provided); judge verdicts (scaffold
only, by design); per-provider-call network latency (not in the corpus);
`extra:` other-player views and deleted-character views in Metric A (no
identity/ledger model available for them in the snapshot).

**Re-verify on the correct base:** Metric A executes these engine symbols —
`agents.common._scrub_unknown_identities`, `._scrub_invented_dialogue`,
`._scrub_undeclared_player_speech`, `._recognizes`, `._quote_body`,
`._contains_quote`, `.player_speech_lines`, `.character_scene_keys`;
`agents.perception._strip_self_narration`, `._dialogue_hear_level`;
`spatial.spatial_rel`, `.room_of`; `character_schema.character_name`. The
harness resolves them by name with graceful degradation and reports any
that are missing, so a re-run on the real branch tree is one command per
metric.
