# 08 — Latency benchmark: what perception's model call costs on a slow model

**Question.** Note 01's corpus measurement put perception at 13.4% of turn
wall-clock — but that corpus was generated with perception on Cerebras
`gpt-oss-120b`, one of the fastest inference providers there is. Perception
fans out one call per perceiver, so it is the stage most exposed to per-call
latency. What does it cost on a slow model, and what does deleting the model
call buy?

**READ THIS FIRST — latency only.** The bypassed arms (C, D) produce **worse
fiction**: with `PERCEPTION_NO_LLM=1` the views are the minimal deterministic
composites (room name/notes + gated dialogue + injected declared sequence),
not the planned composer. Nothing in this note is a quality result. It
measures one thing: wall-clock.

**Method.** `tools/turn_bench.py` (real pipeline, real commits, engine's own
`llm_call` telemetry), chat 64 (171 stored turns, 4 attached characters),
8 scripted turns per arm, every arm starting from an identical temp **copy**
of the read-only snapshot (`ENGINE_DB` pointed at the copy before engine
import — verified; the snapshot's chat 64 still holds exactly 171 turns).
Branch `wave2-build2` in `Sonder_Perception_build2`.

The bypass built for arms C/D is real, reusable work: env-gated
`PERCEPTION_NO_LLM=1`, one seam (`perception_llm_disabled()` gating
`_per_observer_model_views` in `agents/perception.py`), default OFF and
byte-identical when unset, read at call time. It returns no model views, and
each pass's existing deterministic machinery does the rest — establish and
outcome fall to `_fallback_perception_views` through their existing
pre-filtered call sites (the perception.py fallback-is-not-a-gate warning is
respected: nothing new is handed to it), act builds views from
`_ensure_environment` + the injection/scrub backstops. `PerceptionOutput`
contract intact; observations still derived from the final scrubbed views.
Pinned by `tests/test_perception_no_llm.py` (16 tests). This is literally the
composer's zero-LLM skeleton.

Arms:

| arm | perception model | bypass |
|---|---|---|
| A | cerebras `gpt-oss-120b` (owner's config) | off |
| B | nanogpt `zai-org/glm-5.2` (TEE, non-thinking) | off |
| C | nanogpt `zai-org/glm-5.2` | **on** |
| D | cerebras `gpt-oss-120b` | **on** |

**Incident that truncated arm C.** Mid-arm-C the **Fireworks account hit its
monthly spending limit** (HTTP 412 "account suspended") — narrator and the
`default` role route through Fireworks, so turns 174+ failed at narrator/
character. Arms A, B, D completed 8/8 before this; arm C has **3 clean
turns** (171–173). The failures are unrelated to the bypass — on the failed
turns the bypassed perception stages themselves still ran fine (0.1–0.4s) and
made zero model calls. Per the run rules I stopped the run rather than retry.

---

## Headline numbers

| | A: baseline | B: slow model | C: slow + bypass | D: baseline + bypass |
|---|---|---|---|---|
| turns completed | 8/8 | 8/8 | **3/6** (Fireworks 412) | 8/8 |
| median turn | 59.7s | **110.3s** | 24.1s | 49.0s |
| mean turn | 75.1s | 110.1s | 56.2s | 87.8s |
| perception stage s/turn (act+outcome) | 3.3s | **39.8s** | **0.6s** | 0.6s |
| perception share of stage wall-clock | 4.4% | **36.1%** | ~0% | 0.7% |
| perception LLM calls | 30 (3.75/turn) | 30 (3.75/turn) | **0** | **0** |
| perception per-call mean / max | 1.75s / 2.66s | **20.1s / 40.1s** | — | — |

- **On the slow model, perception is the single most expensive stage after
  the interaction loop**: 36.1% of stage wall-clock (perception_outcome 22.2%
  + perception_act 13.9%), vs 4.4% on Cerebras in the same script. The
  owner's corpus figure of 13.4% was indeed an artifact of running perception
  on the fastest provider available.
- `zai-org/glm-5.2` per perception call: median 19.3s, p90 33.9s, max 40.1s —
  ~11x `gpt-oss-120b`'s 1.75s mean. Two sequential passes per normal turn
  (act, outcome) put two of those latencies in series on every turn.

## The delta — what deleting perception's model call buys

**C vs B, matched turns** (same script inputs, same starting DB state):

| turn | B total | C total | B perception stages | C perception stages |
|---|---|---|---|---|
| 171 | 40.0s | 24.1s | 22.9s | 0.5s |
| 172 | 173.6s | 123.8s | 54.1s | 0.9s |
| 173 | 40.2s | 20.6s | 13.4s | 0.4s |

On a slow model the bypass removes **~13–54s per turn — a 39.8s/turn
average, >98% of perception's stage time** — collapsing the stage to a
deterministic ~0.5s/turn. Median turn drops from 110.3s to ~24s on the clean
matched turns. That is the answer to "what does deleting perception's model
buy on a slow model": **roughly a third of the entire turn**, and more on
turns where the interaction loop is quiet.

**D vs A** (Cerebras): per-stage saving is 3.3s → 0.6s per turn (~2.7s/turn).
The turn-total comparison is noise-dominated — interaction_loop and
director_resolve vary by ±100s turn-to-turn (D's median came out 10.7s lower,
its mean 12.7s *higher*, both movements far larger than the 2.7s/turn signal;
8-turn samples cannot resolve it). On a fast provider the per-stage number is
the only clean read, and it is small. Both the owner's original "perception
is cheap" reading and the correction are right: cheap on Cerebras, dominant
on a slow model.

The bypass's own cost is sub-second: arm D's perception stages total 4.9s
across 8 turns (deterministic scrub/injection work only).

## Fan-out and concurrency — the first-class finding that didn't happen

Fan-out here was 3.75 perception calls/turn (30 calls / 8 turns): 2 passes
per normal turn with ~1.9 awake, co-located perceivers per pass. The 4
attached characters were mostly gated out by scene position/awareness this
segment — a crowded co-located scene would fan to 5 perceivers × 2 passes,
so treat 3.75/turn as the *low* end for this chat.

**NanoGPT did not rate-limit or serialise.** Reconstructing arm B's call
intervals from the engine telemetry: peak 3 perception calls in flight
(worker cap is 4), and overlapping calls averaged 19.9s vs 23.4s for the two
solo calls — no inflation under concurrency. The parallel speedup
(summed call time / stage wall) was 1.90x against a per-pass width of ~1.9 —
i.e. **the fan-out ran fully parallel at the width this scene produced**.
Caveat: concurrency never exceeded 3, so behaviour at wider fan-outs
(crowded rooms, `_PERCEPTION_FANOUT_WORKERS` = 4) is untested here. The
"perception is cheap because its calls run in parallel" argument survives at
this width — but note that parallelism cannot rescue the two *serial* passes
per turn: even perfectly parallel, a slow model charges 2 × per-call latency
(~40s at glm-5.2's median) to every turn's critical path.

## Spend

From the engine's own telemetry (input = system+user tokens, per arm):

| arm | model | calls | in tok | out tok |
|---|---|---|---|---|
| A | cerebras gpt-oss-120b (perception) | 30 | 308k | 47k |
| A | cerebras zai-glm-4.7 + fireworks glm-5p2-fast | 49 | 955k | 164k |
| B | nanogpt zai-org/glm-5.2 (perception) | 30 | 310k | 27k |
| B | cerebras + fireworks (other roles) | 52 | 1,021k | 124k |
| C | cerebras + fireworks (other roles; truncated) | 22 | 420k | 50k |
| D | cerebras + fireworks (all roles) | 47 | 910k | 206k |

Totals: ~3.9M input / ~0.6M output tokens across all four arms, of which the
TEE model consumed 310k in / 27k out (single-digit dollars at typical TEE
rates; exact prices are not in the logs). One extra ~50-token probe call
verified the model id before arm B. The Fireworks 412 mid-run is itself a
spend datum: that account was already at its monthly ceiling and these runs'
~25 narrator calls/arm contributed the final straw.

## What this means for the composer branch

The composer replaces exactly the calls arm C deleted. On a fast provider it
buys ~3s/turn; on a slow one it buys **~40s/turn and the largest
non-interaction stage in the pipeline** — and it does so uniformly, where
the LLM path's cost scales with the user's provider choice and per-pass
perceiver count. `PERCEPTION_NO_LLM=1` is now the permanent zero-LLM floor to
measure the composer against: the composer must beat arm C's *fiction*, not
its latency, because its latency is already the composer's.

**Repeat: arms C and D read as worse fiction.** The deterministic fallback
views are minimal by design. No quality conclusion may be drawn from this
note.

---

*Artifacts: bypass + tests on branch `wave2-build2` (uncommitted, per task);
raw per-turn JSON and run log in the session scratchpad (`bench/arm{A,B,D}.json`,
`bench/armC.json` reconstructed from the verbose log, `bench/run.log`).
Benchmark fiction was written only to turn_bench's temp copies; the snapshot
DB is unmodified (mode=ro reads only, chat 64 still 171 turns).*
