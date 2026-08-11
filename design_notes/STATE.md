# Session state — 2026-08-11

Handoff written before a context compact. Everything below is on disk.

## The goal and the bar

Make perception a **pure function of spatial data, zero LLM calls**. Nathan's
thesis: the mapping stage and Director only ever *change spatial data*; they
never determine perspective, because perspective is computed entirely by code.

**Acceptance bar, his words:** "same quality as original Sonder, just faster."
A phase that cannot clear "no measurable quality regression" gets stopped and
reported, not shipped with a caveat. The Director keeps its LLM and all
creative authority — only mechanical burden is in scope.

## Branches and worktrees

| Path | Branch | Tests | Contents |
|---|---|---|---|
| `Sonder_Perception` | `perception-spatial` | **5,690** | the main line: commit `9463d07` + merged spatial + composer, uncommitted |
| `Sonder_BodyParts` | `body-parts` | 5,527 | extra body parts feature, complete, orthogonal |
| `Sonder_Spatial` | `spatial-derivation` | 5,652 | already merged into main line |
| `Sonder_Composer` | `composer` | 5,614 | already merged into main line |
| `Sonder_Perception_build1/2` | `wave2-build1/2` | — | already merged; leak fixes and the bypass |

`Sonder_Engine` is Nathan's live repo — **never write to it**. `dev` is at
`73a3059` and in sync with origin. Nothing has been pushed. Nothing is on `dev`.

Read-only 2.1 GB corpus snapshot: `Sonder_Perception/engine.db` (2,296 turns,
9,351 views). Open `mode=ro`. Never write to any engine.db.

## What has landed (all uncommitted except 9463d07)

- **Phase 0 floor repairs** — whisper attenuation, `across` size gate,
  `visible_adjacent_rooms` asymmetry.
- **Leak-class fixes** — L2 (`spatial_rel_between` had zero production callers,
  so both enclosure guards in `hear_level` could never fire; now the
  body-to-body relation builder wired into six delivery sites), L3, L6, L7, L8.
  25 tests.
- **Director slimming** — `dice` and `fiction_frame` asks removed from the
  resolve contract; fields kept declared (LenientModel drops undeclared keys).
- **Quality harness** — `tools/perception_quality.py`, `_retrieval`, `_judge`,
  `_latency`, plus the measured baseline in note 06.
- **`PERCEPTION_NO_LLM`** — env-gated bypass of the single model seam all three
  perception passes share. Default off, byte-identical unset.
- **Spatial derivation layer** — `effective_anchors`/`_station`/`_facing`/
  `_room_size`, `normalize_edge_distance`, S2a view-cone (subtract-only, pinned
  by a 1,200-combination property sweep), G4 senses gate with a contentless
  `trace` tier, `sound_bearing`, G2 salience. 76 tests.
- **The composer** — `agents/composer.py`. Layer A `build_percepts` (the
  information boundary; canonical names ride no field, so the firewall is
  testable by string containment), Layer B `render_view` (percepts + mode only;
  **no scene parameter exists**, pinned by test). Three render modes: character
  = full standing state, player = delta with full re-render on look/examine
  intent, memory = `render_episode` with events first. 38 tests.

## Key measurements (all mine, against his corpus/config)

- Perception: **3.75 calls/turn**. Stage cost **3.30 s/turn on Cerebras**
  (~890 tps) vs **39.79 s/turn on `zai-org/glm-5.2`** (~44 tps). Bypass = 0.61
  s/turn. On an ordinary model perception is ~36% of the turn.
- Turn composition (his config, 8 turns, chat 64): `character_major` 40.7 s/turn
  (52%), `director` 3.25 calls/turn 15.5s (21%), narrator 8.7s, perception 6.6s.
- `director_resolve` generates ~7,133 response tokens and stores ~1,151 — 84%
  never lands. **Unmeasured: whether a narrower contract shrinks the reasoning.**
- `mapping_quick` output is **98% `relevant_lore`**; `scene_patch` is 1.1%. The
  prompt asks the model to echo lore `content` it was given (`prompts.py:3566`).
  Mapping fires only ~0.12 model calls/turn — caching absorbs most of it.
- Memory embeddings (his production vectors): retired deterministic formatter
  **0.24% collisions @0.95** vs model prose **1.03%**. Templating does not
  collapse retrieval; contentlessness does.

## Corrections I made — do not re-introduce

1. **The 72% duplication figure was the wrong grain.** At the grain retrieval
   uses (chat × perceiver) it is **13.6%**, with 96.3% of distinct sentences
   hapax. The argument "the model is already templated, little to lose" is
   INVALID. Do not repeat it.
2. **Parts of the prior-art research were fabricated** — Wardrip-Fruin's
   Tale-Spin framing, MINSTREL Remixed figures, ASPIRO, Reiter's position, the
   NOT_CHECKABLE 9:1 figure, the Left 4 Dead quotations. Verified and sound:
   positional bias (arXiv:2412.15241), BERT-flow (Li et al. EMNLP 2020), RARE.
   Treat Curveship/Angband/TADS claims as leads to verify by reading source.
3. **I claimed zero metered TEE spend; that was wrong** — ~310k in / 27k out
   went through the pay-per-use `TEE/glm-5.2` before the redirect landed.
4. **The repetition is not mainly engine re-injection.** Removing the top 200
   sentence types moves the global rate 72.0% → 68.3%. It is diffuse.

## Licence rules for anything adopted

Sonder is MIT. **Angband is GPL — no code, no structure, principle only.**
**TADS 3 is proprietary and prohibits derivatives — read prose only.**
Curveship reported ISC but UNVERIFIED; check the repo before adopting code.
Both build agents reported **nothing external used**. A `CREDITS.md` should be
compiled from the "Credits and provenance" sections of notes 12 and 13.

## Note 15 landed — headline is a BUG, not a saving

`prompts.py:3565-3567` asks the mapping model to echo back lore `content` the
engine already handed it. Measured over 855 entries in 416 real calls:
**86.3% byte-identical, 5.8% truncated, 7.7% rewritten** (median 59% of true
length). The mutated **13.6% poisons `lore_cache`**, which `mapping_quick`
re-serves with **no model call for ~99.9%** of later mapping steps. So a
corrupted lore entry is cached and reused indefinitely. The fix — join from
`hits`, already in memory at `agents/mapping.py:59` — is a fidelity repair
first and a ~485 tok/call (38% of mapping's model-written output) cut second.

My earlier 2,096-token headline was OVERSTATED: `mapping_quick` is zero-LLM on
its cached path (1,879/1,881 steps) and `candidates` is engine-written
(`mapping.py:138`). Both are storage artefacts. Real saving is 0.06-0.09 s/turn
on Cerebras, ~7.6 s/call at 64 tps.

Also: `why_relevant` has zero code consumers (`lore_for`'s allowlist drops it).

**R2, the live dice pattern:** `agents/director.py:4949-4950` overwrites
`dialogue_log` `volume`/`visibility`/`conceal_from` from the original
declarations every beat; the model transcribes ~42 tok of which ~35 is
discarded. Trimming also deletes the documented whisper-mistag class.

**`resolved_event` is NOT a free win** — 11 external consumers remain
(background.py ×4, commit.py across 6 roles incl. open X7, importers.py:784,
Director self-policing, UI). Privatisation still needs the note-04 §2 migration.

**Mapping layout tension, settled — and it humbles the spatial work:**
derivation is a floor and amplifier, not a substitute. `effective_station`
rescues only **2.0% of 470 station-less live bodies**, all near-only; the size
hint rescues 24/175 rooms; `effective_facing` derives **0** on standing scenes.
So KEEP every layout ask (~0.015 s/turn) and land the G6 warning. Keep
free-form `distance` parsing too — all 28 live surface forms normalise sanely
(252 near / 249 adjacent / 8 far); a closed enum saves <0.005 s/turn and loses
metric precision.

All proposals are prompt-ask trims. Zero schema-field removals — rejected on
LenientModel round-trip plus archive/trace/checkpoint carriage.

## Note 14 (verification) and note 16 (the fixes) — both landed

Verification said DON'T SHIP on three items. All three are fixed and
re-measured; see `design_notes/16-blocking-fixes.md`. Floor-era, same
scorer and corpus both sides:

| | model | composer was | now |
|---|---|---|---|
| identity-leak views | 107 | 69 | **22** |
| self-narration views | 131 | 0 | **0** |
| delivered-line recall | 94.3% | 98.4% | **99.6%** |
| player same-room lines missing | 6 | **33** | **0** |

The "self-narration 0 → 33" that appeared when the repair pass was disarmed
was the CHECKER, not a regression: all 33 were fragments of delivered lines
cut mid-quote, and all 33 were the same views the repair had been deleting
a line from. `tools/perception_quality.py` now uses the quote-safe stripper
so the metric stops rewarding whatever destroys the evidence.

Also landed this pass: mapping's lore content echo replaced by an engine
join (fidelity fix — 13.6% of echoes were mutated and poisoned
`lore_cache`), the dialogue_log delivery-metadata ask trimmed, the G6
room-size warning, and the prose pass (tone grammar, capitalization,
arrival-before-speech, presence fused to one sentence, dim bodies counted).

**The perception model is now gone entirely** (note 16 addendum): the flag,
the env var, the 4-wide fan-out and the model path inside all three stage
functions are deleted — `agents/perception.py` is 1,028 lines lighter and
imports no model seam at all. Re-replayed and re-scored after the deletion:
every metric byte-identical to the flagged version, 4,261 stage executions,
0 errors. 92 tests migrated across 17 files, none deleted for convenience;
payload assertions became view assertions, which is the stronger test.

That migration found two more defects, both fixed: a body seen at `shapes`
was labelled "an indistinct figure" even when the observer KNOWS them (dim
light was costing acquaintance, not just detail — 570 → 439 views), and
stranger labels were cut mid-phrase ("the tall woman in a long").

`make check` green at **5,723**. Nothing committed, nothing on `dev`.

**Not done on purpose:** the 94.2% templated-opening figure. Character-mode
views render full standing state every beat BY DESIGN (a stateless
character agent's view is its whole context); player views are deltas. That
figure needs re-measuring split by mode before anyone changes rendering.

## Open decisions (Nathan's, not mine)

- Whether anything lands on `dev`. Nothing has.
- Whether `resolved_event` becomes a private reasoning field consumed by
  nothing. Recommended; costs ~0.19s to keep.
- Whether to build the offline/lazy variant bank. **Recommended NOT to**, on the
  0.24%-vs-1.03% measurement. Revisit only if verification shows a deficit.
- Director reasoning-effort A/B via `tools/contract_bench.py` — the largest
  unmeasured director lever (~6,000 tokens/turn that never reach storage).

## Standing disciplines earned this session

- **Never let a default masquerade as a measurement.** `proximity_rel` returns
  `near` both as a measurement and as its fallback, and the fallback dominates
  (6.7% of bodies carry an anchored station). `measured_proximity_rel` is the
  pattern.
- **Every guard subtracts.** The senses gate is the sole exception, and only
  when acuity is explicitly authored on a card.
- **Derive or default, never author per beat.** `stations` was requested since
  Phase 2 and appears on 6.7% of bodies.
- **A model masking a defect is why the defect survives.** Fifteen defects, nine
  leak-class, all pre-existing; the perception LLM had been implementing rules
  the code never did.
