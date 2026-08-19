# Measurement backlog — what has not been measured, and what must not be retried

Moved out of [`docs/UNBUILT.md`](../UNBUILT.md) on 2026-08-19. These are not
defects. Each is either a measurement nobody has run yet, or a negative result
with the protocol for retrying it — evidence, which is what `docs/experiments/`
is for. The register keeps a pointer at its §7.

Two rules carried over from the register: an unrun experiment is unfinished
work rather than a broken thing, and a negative result is only useful if the
retry protocol travels with it.

---

## 1. Measurements the engine is waiting on

Measurements the design notes name as the thing that would settle a question. An
unrun experiment is unfinished work, not a broken thing.

- **The gods expand the maze** —
  [`DESIGN_MAZE_EXPANSION.md`](DESIGN_MAZE_EXPANSION.md). Designed, not built;
  depends on nothing not already in the engine. Needs a second SVG whose western
  7×7 is byte-identical to `maze7x7-a11.svg`, an explicit `--expand` flag so
  `--resume`'s fingerprint guard is overridden rather than weakened, a
  deterministic seam check, and an interlude variant carrying the announcement.
  The question is the one never asked: **can a mind revise a map it already
  trusts?** Two arms from one snapshot, one announced and one silent.
- **A14 — one configuration end to end without intervention.** The A11–A13 rows
  cannot support a clean before/after performance claim because the configuration
  changed underneath them. The only thing missing from that table.
- **The psychology-as-pressure re-measure** — the same maze arm with (a) and (b)
  only, re-counting *"Given his X"* per beat, *"torn between"* per beat, and
  violations of a stated value. Gates §6.6's proposal (c).
- **A village-scale run** — several characters, thirty turns, ordinary places. A
  different instrument from the maze, which is saturated and stopped producing
  new findings after A13. §1.2, §1.3 and the `circling` watch item are the ones
  most likely to bite it.
- **A town-scale place-purpose fixture** — 20 named rooms, 3 affordance sites.
  Measure beats from hunger onset to reaching food, with and without
  `recalled_places`. It works if the number falls and the route still reads like a
  person walking rather than a solver.
- **The running ablation** — a map with a genuine long corridor and a `large`
  hall, run twice by one character, once with `sprint_reach` ablated. It works if
  beats-to-goal falls while **moves**-to-goal does not.
- **The surface-comfort property test** — a body parked on a bed for 30 beats ends
  with stamina up, `charge` unchanged, absorption below 0.25, and at least one
  departure-capable want intact. If any of the four fails, the anti-attractor
  design is wrong and no amount of constant-tweaking fixes it.
- **Prompt efficacy for crowds, tellings and projects.** The first playthrough
  with the model side unauthored (`tools/model_playthrough.py`; artefacts in
  `demos/vale-model-played-14-*`) handed every 8.0 mechanism an explicit
  occasion across 11 Director resolves, on two independent models. Reached for
  and correctly encoded: `courier_ops` (both), `artifact_ops` (one) — and those
  were refused for a structural reason since fixed, not a bad encoding, so
  those two prompts land. Never declared once, by either model, on any
  occasion: `crowd_ops` (a packed market square, then listening to it),
  `tell_ops` (telling a named character what the player saw), `project_ops` (a
  stated multi-stage intention). The gap is now isolated — the same commit path
  drove all three to 100% acceptance under `demos/ashen-quest-51-*`, where a
  human wrote the ops. When rewriting those clauses: a bare prohibition
  inverts, and naming a concrete occasion is what works. Re-run the harness
  afterwards and compare; the artefacts are checked in.
- **`make test-browser` for the early-narration render** (`126009c`).
  Playwright is not installed on the machine it was written on, so it was
  checked with `node --check` and a stub DOM instead.
- **Full narrator token streaming.** Only the conservative half landed —
  render on the narrator `step` event. Streaming the tokens themselves would
  put the first word at ~75% of a turn instead of 100%, but the narrator
  re-runs on a fidelity or craft rewrite on roughly a quarter of turns, so it
  needs a re-stream or a visible "revising" state first.

### From the alpha 8.4.4 measurements

All four are named by
[`WORLD_METABOLISM_FIRE_RATES.md`](WORLD_METABOLISM_FIRE_RATES.md)
or by the work that shipped in that release. Ordered by expected value.

- **Why 3 of 31 characters have ever formed a PROJECT.** `tools/fire_rates.py`
  reports `has ever held a project 9.68% (3/31)`, mean 0.03 against a cap of 2,
  and the row's own note says the tier is unreachable if that is zero.
  `CLAUDE.md` records projects as what made NPCs pass the maze without altering
  their drives, and as the tier carrying "go home, take the injured one to a
  doctor" — an NPC walking somewhere for a durable reason is the oldest
  spontaneous-event engine there is. Whether the gap is the adoption
  deliberation refusing, probation lapsing, or the prompt never reaching is
  unmeasured. **Smallest number in the corpus with the largest documented
  effect; measure this before enriching anything in the world layer.**
- **Why the Director never declares a crowd, courier or caravan.** Every
  off-screen row reads `no chances` — the precondition never arose. The ops
  exist and are contracted. Unreachable, unread, or never applicable to the
  stories played so far? Those have entirely different fixes, and the answer
  decides whether a pre-planning sidecar is the right shape or a second inert
  layer on top of the first.
- **Whether `sensory_channels` changes the prose.** It is wired, tested and
  firewall-argued, and payload-to-behaviour coupling is model-mediated. Same
  beat, same model, before and after, is the only thing that settles it.
- **Whether touch/smell scarcity is delivery starvation or story mix.** A
  checkpoint replay counting beats where the scene held standing player
  contacts or substances while `observations["player"]` carried no touch span.
  Gates the substrate half of any further sensory work.

---

## 2. Prompt caching: measured, and deliberately not acted on

*(Register §1.25 until 2026-08-19. Close condition unchanged: run
`tools/cache_latency.py` first. If warm calls are not reliably faster on the
models actually in use, this closes as "measured, not worth it" and the prompt
is left alone.)*

Measured 2026-08-03 while benchmarking nano-gpt subscription models. Not fixed:
the fix is one line, and the evidence that it is WORTH making is incomplete in
a specific way described below.

**The defect.** `prompts.DEFAULT_PROMPTS["character"]` opens

    "You are the decision process of {name}, not a narrator..."

with `{name}` at **byte 32 of a 55,558-character prompt**. A provider caches a
PREFIX — the hit runs from the start of the message to the first byte that
differs — so two characters in the same beat share only the ~8 tokens before
the name, and the other ~13,880 tokens of byte-identical contract are
re-ingested cold, per character, per turn. Every other system prompt in the
engine has zero template variables and is already maximally cacheable
(`director_resolve` 13,794 tok, `perception` 5,885, `narrator` 5,488,
`director_interpret` 4,205, `mapping_stage` 3,122). `variant_seed` is already
last in every payload, so the nonce is not implicated.

**Measured across 14 subscription models** (`tools/cache_probe.py`, two calls
per arm: the same prompt as `Elyndra` then as `Hinami`, which is what a real
multi-cast beat does). `relocated` moves the name clause to the end of the
prompt; `split` leaves the wording untouched and sends the contract as its own
message:

| model | as-is | relocated | split |
|---|---|---|---|
| `zai-org/glm-4.7` | 1% | **99%** | **99%** |
| `mistralai/mistral-large-3-675b` | 0% | **99%** | **99%** |
| `google/gemma-4-26b-a4b-it` | 43% | **98%** | 0% |
| `moonshotai/kimi-k2.5` | 0% | **98%** | 1% |
| `moonshotai/kimi-k2.6` | 0% | 0% | **98%** |
| `inclusionai/ling-3.0-flash` | 0% | 64% | 64% |
| nemotron 550b / super-120b, `Qwen3-Next-80B`, `glm-5.2`, `qwen3.5-397b`, `deepseek-v4-flash` | 0% | 0% | 0% |

**`as-is` is 0% on every model that caches at all.** Four recover 98–99% when
the name moves. Live confirmation from a 10-turn run: overall cache hit rate
**18.9%** (46,784 of 247,374 prompt tokens), with `character`, `director` and
`narrator` calls all at **0** while `perception` — which fires 7x in seconds
and stays warm — hit 5,440–5,696 per call.

**Why it is not fixed.**

1. **A cache hit is not a speed win, and may be a loss.** On
   `gemma-4-26b-a4b-it` relocation took a call from **33.1s to 4.0s**. On
   `kimi-k2.6` the 98%-cached arm ran **5.3s → 34.6s**, 6.5x SLOWER. `glm-4.7`
   improved modestly (10.6s → 7.3s); `ling-3.0` got slower. Cache support,
   cache benefit and raw latency are three independent properties, and only
   the first has been measured properly. `tools/cache_latency.py` (cold call 1
   vs warm calls 2-5, fixed output length) exists to settle it and has not been
   run to completion.
2. **There is no universal layout.** `kimi-k2.5` wants `relocated` and gets 1%
   from `split`; `kimi-k2.6` is the exact inverse; `gemma` wants `relocated`
   and gets 0% from `split`. Any fix has to be verified per model rather than
   adopted as a general improvement.
3. **Byte 32 of a system prompt is high-salience real estate.** "You are
   {name}" opening the contract may be doing real work for character
   adherence, and moving it is exactly the class of change CLAUDE.md warns
   about: nothing errors, and a character reads subtly wrong fifty beats later.
   `split` avoids this — same tokens, same order, only the message boundary
   moves — which is why it is the preferred shape where it works.

**What to do when this is picked up.** Run `tools/cache_latency.py` first. If
warm calls are not reliably faster on the models actually in use, this entry
closes as "measured, not worth it" and the prompt is left alone. If they are,
prefer `split` over `relocated` (no wording change), verify per model, and
A/B on a long story with `tools/stability_run.py` — a character-adherence
regression will not show up in a test suite.

**Related, unfixed:** caching is a property of the MODEL and the layout jointly,
and nothing in the model-selection process accounts for it. `Qwen/Qwen3.6-35B-A3B`
cached 0 of 188 live calls; `nex-agi/nex-n2-pro` cached 63 of 79. On a pipeline
this prefill-dominated (27k-token director payloads), that may outweigh every
latency difference measured in `bench-2026-08-03/RESULTS.md`.

**Update 2026-08-08 — the switch this entry needed now exists, and the wrong
file was nearly used to settle it.** Prompt caching is a per-provider checkbox
in ⚙ API (`prompt_cache_enabled_for`, `PUT /api/providers/{pid}/prompt_cache`),
so arm 1 above — "is a cache hit actually faster on the models in use" — can now
be A/B'd on a real story rather than only in `tools/cache_latency.py`.

Two traps found while building it, both worth writing down because both produce
a confident wrong answer:

- **`bench-2026-08-03/*.log` cannot answer this question.** All 62 cache
  reads across its 267 timed calls come from ONE model, `nex-agi/nex-n2-pro`,
  and none of the logged models is a Claude. The engine's breakpoint is gated on
  `_model_is_anthropic`, so it never marked any of them — those `cached_tokens`
  are the provider's own implicit caching. Splitting that file cached-vs-uncached
  compares one model against all the others, and duly produces a spurious 2x
  "caching penalty" at 1200+ response tokens (83.70s vs 42.36s, n=8). The real
  measurement is the `tools/cache_probe.py` table above, which controls for
  model by construction.
- **The live config caches nothing.** As of 2026-08-08 no configured role runs a
  Claude model (`minimax/minimax-m3`, `moonshotai/kimi-k2.6`, `x-ai/grok-4.20`,
  `inception/mercury-2`), so the engine's marking is inert on this install and
  the new checkbox changes nothing until a role points at a Claude. Note that
  `kimi-k2.6` — currently `default` and `character_mid` — is the model whose
  98%-cached arm ran **6.5x slower** in the table above.

---

## 3. The slow turn: where 216 seconds actually went

*(Register §1.40 until 2026-08-19. Everything actionable landed; what is kept
here is the method, because the harness is still blind to the same class. One
residual — a restore racing a mid-flight consolidation call — stayed in the
register.)*

Measured 2026-08-12, on chat 71 turn 10 (played live 07:01:32–07:05:09,
216s from `interaction_loop` to `commit` against harness predictions of
roughly a third of that). Diagnosed from the persisted `steps`/`variants`
timestamps, the turn's own stored stage outputs, and an offline reproduction
against a copy of the database — not from the harness. Three findings, one
per anomalous stage, and none of them is corpus size:

- **`commit` 45.8s (harness 4–8s): ~29.5s of it is the first
  autobiographical consolidation, reproduced and timed.** Turn 10 is the
  first beat where `memory.maybe_consolidate_character_memory` fires
  (`current_turn_idx - last_turn >= 10` with `last_turn=0`), and
  `_write_consolidated_window` runs on the **`utility`** role — which is
  configured nowhere and is not in `providers.ROLE_FALLBACKS`, so it falls
  through to `default` (NanoGPT `zai-org/glm-latest`). Reproduction against
  a copy of the live database, real providers: consolidation of the
  34-memory window took **29.47s, 27.38s of it the one LLM call**
  (`llm_call role=utility … duration=27.38s`). The rest of the commit window
  is a handful of paced embedding calls (measured: 2.69s for a 4-text batch
  that ate one 429 penalty; 0.93s single) plus sub-second deterministic
  work. Mapping was `{"skipped": "nothing new to commit"}` — no mapping LLM
  call, no lore embeddings, so the chat's lore volume (7 entries) and the
  2,152-entry database total are both irrelevant. The consolidation runs
  synchronously inside the commit stage's wall clock even though it is
  post-transaction and reconstructible; every other post-transaction spend
  (offscreen ticks, artifact wording, promotion) already went out-of-band.
- **`director_resolve` 105.5s (harness 22–50s): the 8.2 code, not a stale
  build.** The stored resolve output carries `orchestration.prose_scope`
  (granted/gated_out), which exists only at `ab3daad` — `40755ee` has no
  `_prose_author_scope` — so the 06:58 process was running the merged 8.2
  tree (merge landed 06:51:40) and the delegation-leak/lean-core fixes
  explain **none** of the gap. What the record shows instead: an intimate,
  physically busy beat dispatched **5 of 6 specialists** (`"ran": true` for
  body, social, contact, objects, spatial), the reconciliation self-repair
  fired an extra sequential core call (`"repaired": true`) — and it bought
  nothing (`state_diff still does not encode it after self-repair` warnings,
  `channels_replaced: []` on every specialist). The harness's 22–50s band
  was earned on beats with narrow dispatch and no repair pass.
- **`narrator` 29.5s (harness 6–15s): payload is windowed (LIMIT 4 prose
  turns, scene-scoped fields — nothing O(corpus)); the multiplier is the
  bounded rewrite ladder** (`_generate_narration` fidelity-correction and
  craft passes: up to 3 calls). Inference from code structure, not
  measurement — the live per-call log lines died with the process, before the
  per-call ledger landed.

**Nothing on the turn path scales with corpus.** Measured on the 2.1 GB
copy: a full-corpus `memories_fts` MATCH is 2.3ms, the chat-scoped vector
fetch 0.5ms; the resolve/narrator payloads are scene-scoped and windowed;
mapping skips when nothing is staged. The 2.1 GB database and the DB-wide
lore/memory totals are red herrings for turn latency.

**Why the harness is blind, and what answers it.** A fresh run of ≤10 turns
(idx 0–9) can never reach the consolidation cadence, rarely trips wide
specialist dispatch or a repair/rewrite retry, and, at the time this was
measured, nothing on the live path persisted how long a stage took, so a slow
live turn left only stage-total timestamps behind. `tools/stability_run.py` exists for
exactly this: it drives real turns against the longest stories on a copy
and parses per-role `llm_call` durations. Run it against long chats either
side of any latency-relevant change.

**What landed against this (2026-08-12):**

- **Consolidation is out-of-band** (`commit.schedule_memory_consolidation` →
  `core/jobs.py`, beside the offscreen ticks): deduped per chat, abandonable
  between characters, silent-per-character on failure, cancelled
  cooperatively by `restore_checkpoint`. The ~29.5s leaves the commit
  stage's wall clock entirely. `tests/test_consolidation_out_of_band.py`.
- **`utility` inherits `mapping`** in `providers.ROLE_FALLBACKS` before
  falling to `default` — the settings guidance has always paired
  "mapping/utility" as the cheap mechanical lane, so an unset utility now
  lands on the fast model the host already picked instead of their most
  expensive one. The settings-panel role notes say so.
  **Reverted 2026-08-13** (`providers.ROLE_FALLBACKS` is now empty; every
  unset role follows `default`). It fixed the cost by means of an
  inheritance no host could see, and the same mechanism was lying to hosts
  on the six Director specialists. The defect this bullet was answering —
  the call sitting inside the commit window — is fixed by the out-of-band
  scheduling above and stays fixed; an unset `utility` on a slow default
  now costs money and background time, not the player's wall clock. If a
  background lane returns to the turn's critical path it needs its own role
  **set**, not a fallback re-added under it.
- **Reconciliation repair goes to the CHANNEL'S OWNER on the orchestrated
  path** (`agents/director.py` `_route_repair_omissions` /
  `_specialist_repairs`): an omission in a delegated channel is re-asked of
  its owning specialist — one scoped ~1s call, same beat view, same
  entitlement slice, additive merge — and only player claims and
  undelegated categories still buy the full-core `resolve_repair` call.
  Detection unchanged; monolithic path byte-identical. Found and fixed
  beside it: `_CATEGORY_CHANNELS` was keyed on raw category spellings while
  every reader looks up `_normalize_omission_category` output, so contact/
  substance/pose manifest entries could never reach the scope backstop; and
  a repair delta's `stations` were silently dropped by
  `_merge_repair_into_diff`.
- **The per-call ledger** — `_engine_notes.llm_calls` on each saved variant,
  `{step_key, role, requested, served, in, out, cached, duration, kind}` per
  call, offered by `providers._log_usage` and attributed by contextvar so the
  specialist fan-out and the parallel groups land on the right step — is what
  turns the narrator question below from an inference into a lookup.

**Correction (2026-08-12, live variants v26625/v26634/v26643, turn 2354):
the "empty specialists" reading of these rerolls was wrong.** Two separate
investigations read `channels_replaced: []` as "the specialists assembled
nothing" — but that field counts AUTHOR content that lost to ownership, and
a compliant lean author leaves delegated channels empty, so `[]` is the
healthy state. The merged diffs on all three rerolls carry the specialists'
encodings (`attire.Hinami.remove` the jacket, `contact_ops`
remove(stomach)+add(waist), the entity shed, an inventory drop, a station);
a granted channel's post-assembly content can only be the specialist's,
because assembly assigns `container[key] = owned` unconditionally. What
actually broke was the deterministic EVIDENCE CHECKER
(`_evidence_present`): each class gated on the manifest's free-text
`subject` naming one particular kind of thing (the wearer for attire, a
participant for contacts, a `positions` key for a placement) while the
model words subjects freely ("lightweight travel jacket", "contact_end",
"prior hand-to-stomach contact") — so coverage flickered reroll to reroll
with the wording, 5 of 11 live manifest items read as omissions against
diffs that encoded them, the Tier-2 repair fired on the false positives,
answered "already_encoded", lost that verdict to an exact-subject
disposition match, and false "objective state may be stale" warnings
shipped. Fixed: attire also checks garment handles inside wearer entries;
structured manifest endpoints bypass the contacts subject gate (they ARE
the subject); a `cross` op covers its ended endpoint via
`crossed_target_part`; a within-room drop filed under `positions` is
covered by its station; disposition matching carries the same substring
tolerance as every other subject comparison in the seam; and each
specialist's dispatch record now carries `channels_filled` so the next
investigation can see assembly working. Replayed against the live diffs:
9/11 covered (was 6/11) — the two residuals are genuine part-noun
disagreements between the model's own manifest and its encoding
(waist/hip, fingers/hand), correctly detected and deliberately not folded
by a synonym table (`_same_appendage` is structural by design).
`tests/test_resolve_reconciliation.py` (live-shape fixtures),
`tests/test_director_orchestration.py`
(`test_a_specialist_encoded_beat_buys_no_repair_and_no_warning`).

**Two residuals stayed in the register rather than here**, because both are
open defects rather than measurements: the `narrator` 29.5s attribution is still
an inference the per-call ledger can now settle on the next slow beat, and the
restore/consolidation race is a real window the synchronous design did not have.
Both are `docs/UNBUILT.md` §1.40.

---

## 4. `contract_bench`'s specialist payloads

*(Register §1.47 until 2026-08-19. A tool caveat, not a defect: it makes the
specialists benchable at all, which they were not.)*

`tools/director_shootout.py` was written because `contract_bench` sent a
927-character payload and reported a model at 3.95s that took 47.4s in a live
turn — the bench was sending about 4,400 system tokens against a real
director's 27,000, and mis-ranked the most expensive role in the pipeline.

The six specialist payloads added in alpha 8.4.4 are synthetic two-character
scenes and have exactly that flaw at smaller magnitude. They make the
specialists benchable at all, which they were not; they should be rebuilt from
a real chat the way `director_shootout` builds its own before anyone ranks a
model for a tiering decision on them.

---

## 5. Two negative results with retry protocols

*(Register §1.12's last two bullets until 2026-08-19. Both were BUILT,
MEASURED and REVERTED. Neither may be retried without the stated protocol.)*

### The observation text repeats the view and cannot be trimmed away

Each
atom's `observed.text` is a span of the same scrubbed prose the character
already has in `perception.view` — measured on chat 72, 737 B of atom text
against a 757 B view, 97% byte-identical. Shortening it to an opening-words
locator was built, measured and **reverted**: a rendered atom is front-loaded
with its attribution, so an eight-word window spends itself on
`Hinami says in a nostalgic voice:` and cuts the clause that carried the beat
(`"He never saw my ears or tails."` arrived as `"He never ..."`). The
duplication is the price of the atom being *addressable* — `present_evidence_used`
cites it, and the model paraphrases it into `fact`. Any future attempt must
keep the content and drop the frame, not the reverse, and must be measured
against `tools/benchmark_memory_temporal.py --case anomaly_now --case boundary`
before it ships. ~464 B per character per beat; the smallest item in the
payload and the only one with a proven mechanism of harm.

### A gist reads like a conclusion — the fidelity ladder is BUILT, MEASURED and NOT SHIPPED

Delivering the far half of the recall slate as its gist alone
is psychologically right and costs nothing in content: gists of the target
memories carry 100% of the scored term groups the details do, and the
benchmark's content checks were 20/20 in both arms. It still regressed, and
not where anyone was watching. With half the slate condensed, the character
stopped consulting the PRESENT: asked "the anomaly is flaring right now,
isn't it?", the arm with the ladder cited a present observation 14/30 against
25/30 without it (Fisher p≈0.006), answering a question about now entirely
from memory. The mechanism is that a full episode is discursive and obviously
past, while a one-line gist is answer-shaped — so condensed memory
out-competes a prose view for a question the view should have owned. Worth
~3.3 KB per character per beat (−11% of the memory context). Any retry must
restore the present lane's weight FIRST and prove it on `--case anomaly_now
--repeats 20`; keying the ladder better will not help, because the ladder's
key is not what fails. Two keys were tested and both are unusable anyway:
retrieval rank puts the row a question actually needed at rank ≥10 a third of
the time (88 scored retrievals), and `importance` does not separate at all
(median 0.69 on needed rows against 0.68 on the rest of the bank).
