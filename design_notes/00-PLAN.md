# Deterministic perception — consolidated plan

Synthesis of `01-corpus-measurement.md`, `02-spatial-fov-gaps.md`,
`03-composer-design.md`, `04-leaner-director.md`. Branch `perception-spatial`.

**Goal.** Perception becomes a pure function of spatial data — zero LLM calls.
The mapping stage and Director only ever *change spatial data*; they never
determine perspective, because perspective is computed entirely by code.

**Not in scope.** The Director keeps its model call. It is doing a creative
job. The only question asked of it here is whether it can carry less
mechanical burden at equal quality.

---

## Verdict

Feasible. Three findings decide it, and two of them were surprises.

**1. The substrate is already there — ~83%, by two independent methods.**
Engine telemetry over 1,885 turns: 82.8% of self-declared persistent changes
are already evidenced in the same call's `state_diff`. Independent clause-level
classification (n=50 random turns, 323 assertions): 83.4% homed — `state_diff`
22.6%, declared sequences 24.0%, `dialogue_log` 36.7%.

The residual's *composition* matters more than its size. The largest category
(28% of residual) is **perception adjudication written into prose** — the
Director ruling on who hears what, occlusion, sensory judgments. That is not
missing spatial data; it is the Director doing perception's job, and under this
design it is **deleted, not homed**. A further 13% is `contact`, where
`contact_ops` already exists and simply goes unused. So ~41% of the residual
either disappears by design or uses a field already present. The slice needing
genuinely new structure is ~10% of all assertions.

**2. The prose-register objection was mostly wrong.** The stated blocker was
that model prose gives episodic memory retrieval discrimination templates would
destroy. Measured on the corpus, and independently reproduced:

| | |
|---|---|
| Perception views | 9,351 |
| First sentence **not** unique | **73.0%** |
| All sentences duplicated verbatim | **72.0%** (of 77,585) |
| Most common opening | `"You are in an unspecified area."` — 899 views |

The model's output is already templated. There is little discrimination to
lose. `commit.py:5511` documents the endgame in the memory bank: 356 rows
across five stories, 7.3% of the whole bank and a third of one story's, all the
identical sentence at salience 0.47.

This holds **only** with the coupled change in Phase 3 below.

**3. The model has been covering for the deterministic floor.** See
`spatial.py:1034-1044`: the same-room branch of `hear_level` attenuates only
`mutter`, so `whisper` — the quietest volume the Director can assign
(`prompts.py:232`) — returns `full` at any in-room distance. The enclosure
branches at `:1010` and `:1032` handle `("mutter","whisper")` correctly as a
pair, so this is an inconsistency inside one function.

It has been invisible because the perception prompt states the rule correctly
(*"whisper: ONLY same-room perceivers in close proximity"*) and the model
applied a rule the code does not. It is **not** invisible in production:
`deterministic_micro_perception` (`loops.py:112`) passes volume straight to
`hear_level` with no model in the loop, so a whispered NPC line in a character
micro-round reaches the whole room verbatim, today, on `dev`.

This is the branch's thesis in miniature, and its central risk: remove the
model and every such gap becomes a live leak. It is also the strongest argument
for the branch — nothing else would have found it.

---

## Plan

### Phase 0 — Repair the deterministic floor (independent of this branch)

These are defects on `dev` now, on the no-LLM path. They should land on `dev`
regardless of whether the rest of this plan proceeds.

- **D1** `hear_level` same-room branch ignores `whisper` (`spatial.py:1040`).
  Information-boundary defect. Highest priority.
- **D2** `proximity_rel` gates `across` on `size == "large"` exactly
  (`spatial.py:1375`) while the size vocabulary includes `huge`/`vast`
  (`:5280`) — the largest rooms never yield `across`, so a mutter that should
  vanish leaks a fragment.
- **D3** `visible_adjacent_rooms` forward loop drops descriptionless
  neighbours; the reverse loop does not.
- **D4** two graded-sight authorities (`sight_level` room-ambient vs
  `visual_level_between` per-body) that can disagree.
- **D6** `spatial_facts` at perception is env-gated OFF (`SPATIAL_SCAFFOLD`).
  Under this branch it is the spine, not a scaffold.

Each needs a focused regression test first, per `AGENTS.md`.

### Phase 1 — The Director emits the beat as typed events

`DirectorResolve.beat_events`, in the vocabulary the engine already consumes
with zero LLM (`ActionElement`/`SpeechElement`, `schemas.py:839-881`), extended
with three types:

- `outcome` — resolution of a declared act, linked via the existing
  `ActionElement.event_id`
- `display` — involuntary expressive surface of a body acted upon
- `world` — environment events, with subject/room/channels

Every element carries subject identity, visibility/`conceal_from`, and channel,
at one-subject-per-event grain. Add `sound: {desc, loudness}` per gap **G1** —
without it the floor has no non-visual event surface, because `observable` is
written for a sighted bystander.

**Keep `resolved_event` as a private reasoning field consumed by nothing.**
Ordered first in the contract, excluded from every payload. The branch goal
holds — perception never sees it — while the model keeps whatever reasoning
benefit the prose provides. This repo has repeatedly measured structured
contracts degrading under narrative pressure (zone tagging; `stations` at 0/45
live scenes; dialogue-log volume mistags; a 17.2% manifest miss rate), so
forcing structure *is* a real cost. Estimated net ≈ +100–150 output tokens per
beat, bought back by deleting the per-perceiver view calls.

**Reconciliation becomes a hard correctness requirement, not dead weight.**
Drift moves from prose-vs-diff to events-vs-diff, and turns structural:
`changes_asserted` folds into a `state_ref` on events, so the beat is stated
twice rather than three times. Measured today: 28.8% of beats had omissions,
382 unresolved after self-repair.

Blast radius is enumerated in note 04 — 17 consumers with file:line. The
narrator is untouched (it renders views + `event_order`, and never consumed
`resolved_event`). Seven `persist/commit.py` text-matching sites become subject checks
and get *more* reliable.

### Phase 2 — The composer

New role module `agents/composer.py`, two layers with a typed seam:

- **Layer A — `build_percepts`.** The information boundary. Pure function of
  (per-observer projection + typed events + known/awareness) → ordered
  `list[Percept]`. Every admission decision happens on structured data
  *before any prose exists*: delivery gates, hear/sight/scent levels,
  containment, rear-arc, concealment, recognition labels.
- **Layer B — `render_view`.** Decision-free rendering, built from renderers
  already in production: `contact_sensation`, `_observable_predicate`,
  `substance_event_clause`, `_compose_residue_view`.

`perception.py` keeps its three stage entry points and the exact
`PerceptionOutput` contract (`schemas.py:2670`). `observations` project from
the IR instead of being regex-classified out of prose.

This is what makes the firewall *stronger*: the invariant becomes unit-testable
on an IR rather than asserted by regex over prose.

Must-have spatial gaps to close alongside: **G4** (perceiver senses never
consulted deterministically — a card with vision `absent` currently composes a
fully sighted view), **G2** (alarm/salience, derivable from G1 loudness +
targets), **G3** (`orientation_ops` — turning in place is unrepresentable),
**G5** (station-level `cover`), **G6** (layout coverage obligation on the
mapping stage, with a warning when absent).

### Phase 3 — Mint memory from the IR (mandatory, ships with Phase 2)

`commit.py:5510`, `episode_content = v` → `render_episode(percepts)`, same
fidelity-degraded fields as the view, subset-checked. Plus salience-driven
omission of constant openings.

**Shipping the composer without this degrades retrieval below today's
baseline.** It is a hard dependency, not a nice-to-have.

### Phase 4 — Delete the repair surface

All twelve repair passes die as *runtime repairs*, including the prose forms of
`_redact_concealed_from_event` and `_surface_translate_event`, whose documented
holes the composer closes structurally.

**Keep them as replay assertions and cheap tripwires.** Audit history says real
leaks are guards that cannot fire.

### Phase 5 — Director slimming (mechanical burden only)

Ranked, verified where marked:

1. **`dice` on the resolve contract** — *verified*. The engine builds dice
   itself from the interpret flow with a deterministic seed
   (`director.py:3859-3871`) and overwrites the resolve model's field
   unconditionally at `:4540`. The prompt still asks for it
   (`prompts.py:2972`). Pure transcription waste. Note the interpret-side dice
   *request* is load-bearing — only the resolve echo is waste.
2. **`fiction_frame` resolve echo** — *grep shows no consumer of the
   resolve-side echo*; `director.py:4128` reads it from the interpret flow, not
   from resolve. Reported 88% populated.
3. **`dialogue_order`** — 92.6% derivable from `dialogue_log`; sole consumer is
   a payload hint.
4. **`claim_dispositions`** — make exception-only.
5. **`world_pressure` explicit `hold`** — silence is already
   implicit-hold-with-warning.
6. **`changes_asserted`** — folds into events, but only *after* they land; it
   is the top omission detector today.

Kept, with reasons: the `state_diff` physical vocabulary, `dialogue_log`,
obligation/pressure content, `time`, `summary`, `fact_adjudications` (though
verdicts skew 890 confirmed / 10 contested / 0 false — a default-confirmed
contract is a later candidate).

---

## Open risks

- **Unknown unknowns of the D1 class.** One masked defect was found by
  inspection. There is no reason to think it is the only one. Phase 0 should be
  treated as a search, not a fixed list of five.
- **Prose inside structure.** ~15% of what counts as "homed in `state_diff`" is
  prose sitting in a structured field — `rooms.notes`, `world_facts`,
  `attire.state`, entity descriptions. Routable to a perceiver, but not
  computable. The composer still has to decide what to do with it.
- **Contract degradation under narrative pressure.** Measured repeatedly in
  this repo. Phase 1 should not delete the private prose field until a
  `contract_bench` A/B on stored payloads says it is safe.
- **FOV approximations become reader-visible.** Whole-room binary sight through
  openings (bodies beside a doorframe are seen — the one leak-shaped
  over-grant), distance-flat rooms where everyone is `near`, no entity
  occlusion at all, single-hop acoustics, hearing carrying no bearing. Model
  prose has been smoothing these over.

## Verification

Read-only replay of all 2,296 turns, reconstructing inputs from steps +
checkpoints. **Explicitly not** a diff against stored model prose — those views
contain the defects the repair passes exist to fix. Yardsticks:

- **A. Fact fidelity** against the typed entitled-fact set, scoring composer
  and model corpora with the engine's own checkers run as metrics. Ship gate:
  zero violations across all 9,351 views at 100% delivered-line recall.
- **B. Retrieval discrimination** on shadow-minted memory banks — pairwise
  cosine spread, 0.95-collision rate against the measured baseline,
  self-retrieval MRR.
- **C. Blind LLM-judge** against the fact set, never against model prose, with
  its own false-positive rate measured first.
- **D. Determinism/rerun/reroll invariants**, plus the latency win from
  deleting 3×N provider calls per turn.
