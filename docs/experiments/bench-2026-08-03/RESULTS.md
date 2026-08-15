# Model benchmarking — nano-gpt subscription, 2026-08-03

Raw logs in this directory. Tools: `tools/model_bench.py`, `contract_bench.py`,
`scale_probe.py`, `creation_probe.py`, `agency_bench.py`, `character_puzzles.py`,
`director_shootout.py`, `cache_probe.py`, `turn_bench.py`, `stability_run.py`.

Catalogue: 658 models, **303 subscription-included**. Cost is flat on the
subscription, so nothing here is chosen for being small or cheap.

---

## 1. The headline: two live 10-turn runs

| | all-Qwen | per-role config |
|---|---|---|
| turns | 10 | 8 |
| median turn | **286.0s** | 340.1s |
| range | 50–653s | 274–650s |
| warnings / turn | 10.0 | 11.1 |
| **failed turns** | **3 (30%)** | **0** |

The per-role config is 19% slower and dropped nothing. A 30% turn-failure rate
is not a speed trade — a failed turn loses the beat.

Baseline before any change (chat 60, 1 turn, previous config): **328.7s**, of
which `mapping` on `deepseek-v4-flash-0731:thinking` was **131.75s — 40% of the
whole turn** to emit a room id, an occupant list and an exit list.

## 2. Where a turn's time actually goes

Measured across 89 live calls:

| role | calls | share |
|---|---|---|
| narrator | 24 | **42%** |
| director | 15 | **30%** |
| character_bg | 7 | 18% |
| perception | **42** | **8%** |

Perception is the most FREQUENT role and the cheapest. Narrator and Director
are the cost. Any optimisation aimed at perception is aimed at 8% of the turn.

## 3. The methodological finding that invalidated four rankings

**A small-payload benchmark does not predict real-contract behaviour.** Every
pair re-tested against the engine's own prompt and validator inverted:

| model | toy short call | real contract | |
|---|---|---|---|
| `granite-4.1-8b` | 1.36s, 2/2 | **13.59s, 1/2** | 10× worse |
| `ministral-14b` | 1.88s, 2/2 | **16.11s**, 2/2 | 8.5× worse |
| `kimi-k2.5` vs `k2.6` | 2.5 faster 5× | **2.6 faster 3×** | inverted |
| `Qwen3.6` director | 3.95s | **47.4s live** | 12× worse |

The last one is the sharpest: the contract bench sent a **927-character**
payload; live director calls carry **27,254 tokens**. Six times too small, and
it mis-ranked the most expensive role in the pipeline.

**`model_bench.py`'s short-call number is retired as a ranking device.** It is
a smoke test for "does this emit JSON at all". `contract_bench` and live turns
decide order.

Also: run-to-run variance is large enough to invert a ranking.
`nemotron-3-super-120b` measured 479.8 tok/s and 133.2 tok/s on two runs of the
same tool — 3.6× apart. Two trials is not enough for anything decisive.

## 4. Reasoning variants

Not one cleared the bar.

| evidence | |
|---|---|
| `deepseek-v4-flash:thinking` on mapping | **131.75s** |
| `glm-4.7-flash` (thinks by default) | 1.75s → **34.16s**, 13.7 tok/s |
| `Gemma-4-31B-Pantheon-Reasoning-1.1` | **1/2 schema** |
| `Qwen3.5-27B-Opus-Reasoning-Distilled` | **1/2 schema** |
| `nemotron-3-ultra-550b:thinking` (recorded, earlier) | placeholder `"..."` skeletons; perception collapse mid-run |
| `glm-5.1` vs `glm-5.2` | **0/2** vs 2/2 |

**Why:** Sonder computes the world-reasoning deterministically and asks the
model for a declaration. Mapping, perception and narration receive conclusions
already drawn, so reasoning there re-derives what the payload states. The
exception is `character`, the one role where the engine computes nothing about
what a mind should want — and the only place a capability gradient appeared.

The sharper form: it is not reasoning that hurts, it is **fixed** reasoning.
`kimi-k2.5` allocated effort in proportion to difficulty (1.61s on a toy call,
35.8s on a real problem — a 22× ratio, the largest measured) and was the only
model to solve every agency trial.

## 5. Problem solving (`agency_bench`) — 4 problems, 2 trials

Each has a goal, an obvious path the payload states cannot work, and an
unsignposted way through. Scored on declared conduct only; considering an
option is not taking it.

| model | solved | blocked | novel | median |
|---|---|---|---|---|
| `kimi-k2.5` | **8/8** | 0 | 1 | 35.8s |
| `nex-n2-pro` | 7/8 | 0 | 0 | 12.7s |
| `nemotron-3-ultra-550b` | 7/8 | 0 | **3** | 18.7s |
| `glm-5.2` | 6/6 (2 unusable) | 0 | 0 | 25.0s |
| `Qwen3.6-35B-A3B` | 6/8 | 0 | 1 | 6.3s |
| `ling-3.0-flash` | 6/8 | **1** | 1 | 5.8s |

Solve rate rises with capability (6→6→7→7→8) but so does latency (5.8s→35.8s).
`nemotron` found **three routes the scenarios did not anticipate** against 0–1
for everything else — the only measure that kept climbing, and arguably the one
that matters, since a solve rate saturates against problems somebody authored.

**The discriminating scenario was `occupied mouth`** — a taper clenched in the
teeth, hands full, someone must be warned. Room constraints everybody reads; a
constraint on the character's OWN BODY gets overlooked. `ling` spoke clearly
anyway. That is not a cleverness gap, it is a self-modelling gap, and it is
why the engine needs the mouth-occupied prompt clause rather than trusting
inference.

## 6. World-building depth (`creation_probe`, `mapping_stage`)

One door opened; everything past it invented. Scored on fields the engine can
ACT on — anchors, barriered/directed exits, exposure, entity state — not prose
length. Over-creation penalised.

| depth | rooms | anchors | barriered exits | entities | grounded | time | model |
|---|---|---|---|---|---|---|---|
| **18.8** | 2.5 | **7.0** | 3.0 | 0.0 | 3.0 | 26.2s | `ministral-14b` |
| 14.9 | 1.0 | 2.5 | 1.0 | **1.5** | **5.0** | 7.4s | `nex-n2-pro` |
| 10.7 | 1.0 | 2.0 | 1.0 | 0.0 | 4.0 | **3.5s** | `Qwen3.6` |
| 10.4 | 1.5 | 1.0 | 2.0 | 0.0 | 3.0 | 8.8s | `qwen3-coder-30b` |
| 0.0 | — | — | — | — | — | 14.4s | `granite-4.1-8b` |

**`exposure` was set 0 times in 10 replies by any model.** Every invented room
silently defaults to `enclosed`, so a courtyard behind that door gets no
weather and nothing warns. That is a prompt gap, not a model gap.

`director_resolve` created 0 rooms — correct, not a failure. Room creation
belongs to `mapping_stage`, which runs earlier in the plan.

## 7. Context length disqualifies the obvious candidates

A live character call is **17,561 in + 8,817 out ≈ 26k tokens**. That rules out
42 of 303 subscription models outright — including every model in the catalogue
built for interactive fiction:

| model | context |
|---|---|
| `LatitudeGames/Wayfarer-Large-70B` (AI Dungeon's own IF model) | 16,384 |
| `Sao10K/L3.3-70B-Euryale-v2.3` | 20,480 |
| `anthracite-org/magnum-v4-72b` | 16,384 |
| `EVA-UNIT-01/EVA-Qwen2.5-72B` | 16,384 |

The RP finetune ecosystem is built around 16k. This engine needs 26k for one
character call. The survivors at ≥64k are modern base models with prose
finetunes (`Gemma-4-31B-*`, `Qwen3.5-27B-*` at 262k).

Prose finetunes also lose on speed, badly, at the role that needs them:
`Gemma-4-31B-Novelist` generates at **10.6 tok/s**, `Qwen3.5-27B-Writer-V2` at
11.5. Narrator is 42% of the turn.

## 8. Firewall / leak testing (`scale_probe`, 5 perceivers)

**All five models CLEAN 2/2.** No sentinel crossed between views with five
bodies in two rooms.

This is not a model-selection input. Firewall integrity is an ENGINE invariant
— in production the scrub runs regardless, so this measures how much work the
scrub has to do, not whether the gap holds. See `AGENTS.md` § Information
boundaries.

Related correction: an earlier claim in this session that one config was "6×
noisier" compared **chat 60 (1 cast) against chat 9 (3 cast)**. Identity scrubs
scale with how many bodies could be misnamed. Warning counts are not comparable
across stories of different sizes.

## 9. Reliability

- `inclusionai/ling-3.0-flash` — three distinct failure modes: HTTP 503 under
  load, silent non-service across a whole 10-turn run (fallback served every
  call), invalid JSON once. Fast, not dependable.
- `glm-5.1` — 0/2 schema while `glm-5.2` passes.
- `Salesforce/Llama-xLAM-2-70b-fc-r` — HTTP 400, never measured. The
  function-calling-tuned model was the most promising untested Director
  candidate.
- Availability (8 sequential calls): `Qwen3.6` 8/8, `ling-3.0` 8/8,
  `Qwen3-Next-80B` 7/8.

**The rate limit is per ACCOUNT.** Running two benchmarks concurrently produced
a wall of 429s that read as model unreliability and was entirely self-inflicted.
Any row measured during a concurrent window is suspect.

## 10. Prompt caching — the largest untested lever

Live cache hit rate across a 10-turn run: **18.9%** (46,784 cached of 247,374
prompt tokens).

| role | payload | cached |
|---|---|---|
| perception (repeat calls) | ~8,800 | **5,440–5,696** |
| **director** | **27,254** | **0** |
| character | 17,612 | **0** |
| narrator | 6,942 | **0** |

Perception caches because it fires 7× in seconds and stays warm. Director fires
~2× a turn, minutes apart, and the cache expires — a TTL property no prompt
change fixes.

**`character` is different and fixable.** `{name}` sits at **byte 32** of a
55,558-character prompt, so the cacheable prefix is ~8 tokens and the other
~13,880 tokens of identical contract are re-ingested cold per character per
beat. Every other prompt has zero template variables:

| prompt | chars | vars | stable prefix |
|---|---|---|---|
| **character** | 55,558 | 1 @ byte 32 | **~8 tok** |
| director_resolve | 55,176 | 0 | ~13,794 |
| perception | 23,543 | 0 | ~5,885 |
| narrator | 21,955 | 0 | ~5,488 |
| director_interpret | 16,821 | 0 | ~4,205 |

`variant_seed` is already last in every payload, so the nonce is not the
problem.

Run since, across 14 models: the `as-is` layout caches **0% on every model that
caches at all**, and `relocated`/`split` recover 98–99% on five of them. Two
things that reading stops short of, both of which is why nothing was changed —
a cache hit is not necessarily a speed win (one model went 33.1s → 4.0s, another
5.3s → 34.6s), and there is no universal layout (`kimi-k2.5` wants `relocated`,
`k2.6` wants `split`). Full record and the decision procedure in
[`../UNBUILT.md`](../../UNBUILT.md) § 1.25.

The probe also nearly produced a false negative: its first run was against a
model that caches nothing at all (0 of 188 live calls), which reads exactly like
a layout that does not help. **Caching is a joint property of the model AND the
layout**, and nothing in this selection process accounts for it.

## 11. Open questions

- **Narrator quality is unmeasured.** 42% of turn time, assigned on speed
  alone. The largest gap in this whole exercise.
- `director: low` reasoning was set on argument, never A/B'd against `off`.
- `character_puzzles.py` (cognition + the assert-vs-hedge firewall test) built,
  never run.
- Whether `kimi-k2.6` keeps `k2.5`'s 8/8 agency score.
- Whether a cache HIT is a latency win. `tools/cache_latency.py` (cold call 1
  vs the median of warm calls 2–5, fixed output length) is written and not yet
  run. It is the gate § 1.25 names: if warm calls are not reliably faster on
  the models in use, that entry closes as "measured, not worth it" and the
  prompt is left alone.
