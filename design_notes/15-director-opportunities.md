# 15 — Director and mapping opportunities after the derivation layer and composer

STATUS: COMPLETE. Investigation only; no source file modified. Worktree:
`perception-spatial` (spatial derivation + composer both applied on top of
`9463d07`). Method: source read with file:line cites; corpus measured
read-only against `engine.db` (2,296 turns; 2,232 active `director_resolve`
variants; 416 real mapping model calls; 61 live scenes; aggregates only).
Token figures below are chars/4 estimates over stored JSON unless stated.

Ranking axis: seconds saved per turn at 1000 tps. Per-call output-token
figures are given alongside, because the owner's Cerebras config understates
what the same contract costs on a slower model (at 64 tps multiply the
seconds by ~15.6).

Measured baseline (owner's live config): `director_resolve` 3.25 calls/turn,
15.5 s/turn (~21% of turn); resolve proper 1.0 call/turn at 8.1 s,
~7,133 response tokens generated vs ~1,151 stored. Stored field means:
`state_diff` 405, `resolved_event` 193 (re-measured here: 191),
`dialogue_log` 187 (re-measured: 185), `changes_asserted` 62, `summary` 36,
rest ≤26. Mapping: ~1.0 step/turn but only 0.18 real model calls/turn
(corpus; benchmark saw 0.12) — see §2.

One framing fact first, so the ranking reads honestly: every trim below
operates on the STORED slice of resolve's output (~1,151 of ~7,133 response
tokens). The other 84% is generation the contract never stores (reasoning,
retries, JSON overhead) and no field trim touches it. The Director's latency
is dominated by that, not by contract fields. The single real
token-transcription win found this pass is in MAPPING, not the Director.

---

## 0. Already landed (verified, for orientation)

`dice` and `fiction_frame` are gone from the resolve output contract
(`prompts.py:2930-2975` lists neither; `schemas.py:1917-1930` keeps both
fields engine-stamped/tolerated for archive compat). These are the two
dead-field removals measured earlier today (~0.02 s combined). No further
action.

## 1. Ranked findings

### R1. Mapping's `relevant_lore` content echo — the dice pattern at its largest scale
**~0.49 s per real mapping call; 0.06–0.09 s/turn at 1000 tps; ~7.6 s/call
at 64 tps. Plus a durable lore-fidelity fix. Kind: prompt-ask change +
engine-side join. No schema change.**

- `prompts.py:3565-3567` asks the mapping model to emit
  `relevant_lore:[{id,book_id,keys,content,category,why_relevant}]` —
  including the full `content` of entries the engine just handed it as
  `candidate_lore` (`agents/mapping.py:109`). The engine still holds every
  candidate in the same function (`hits`, `agents/mapping.py:59`), so the
  join by `id` is free and in-memory.
- Measured over all 416 real mapping calls, 855 relevant_lore entries:
  **738 (86.3%) echo `content` byte-identical to the candidate row; 50
  (5.8%) are truncations; 66 (7.7%) differ** — and of the different ones,
  median length is 59% of the true entry (40/66 clearly abridged), i.e. the
  model is silently SHORTENING lore in the echo. 1/855 cited an id not in
  candidates. `keys` is likewise echoed verbatim in 829/854.
- The mutated 13.6% is not harmless: the echo is what downstream actually
  consumes. `agents/common.py:1379` (`lore_for`) feeds it into the
  Director's payloads (`agents/director.py:616,4169`), and
  `commit.py:6888` → `:4581/:4647` writes it into `lore_cache`, which
  `mapping_quick` then re-serves **with no further model call** for every
  subsequent cached turn (`agents/mapping.py:192-204`). An abridged echo
  therefore poisons the served copy of that entry until the next real
  mapping call replaces it. Engine-side join is strictly more faithful.
- Token math per real call (model-written stored output ≈ 1,280 tok:
  relevant_lore 551, scene_patch 453, staged_lore 143, notes 72, npc 28):
  `content` is 409 tok/call and the `keys`/`category`/`book_id` echoes ~76
  more. Asking for `{id, why_relevant}` only saves **~485 tok/call ≈ 38% of
  mapping's model-written output** ≈ 0.49 s at 1000 tps. At 0.18 real
  calls/turn: ~0.088 s/turn (0.058 at the benchmark's 0.12 calls/turn).
  Cache hit rate measured: **1,879 of 1,881 `mapping_quick` steps were
  cached (99.9%)**; the per-turn figure depends entirely on that rate, the
  per-call figure generalises.
- Do NOT cut: `staged_lore` (genuinely authored new lore) and the
  relevance JUDGEMENT itself (which entries to surface). `why_relevant`
  specifically has **zero code consumers** (`lore_for`'s allowlist drops
  it; only `lore_cache` stores it unread) — it is authored judgement
  retained solely for author inspection of the step. Keep or drop on
  taste; it is 56 tok/call ≈ 0.01 s/turn (negligible).
- Blast radius: prompt text + a join loop in `agents/mapping.py` (content
  from `hits` by id; keep model fields as fallback for an id not in
  candidates, warn). `relevant_lore` is a bare `list[dict]`
  (`schemas.py:2694`) so no schema change; archives/traces carry old
  echoed copies unchanged; replay unaffected (same dict shape).
- Also confirmed while here: `out["candidates"] = hits`
  (`agents/mapping.py:138`) is ENGINE-written — the 2,457-token
  `candidates` share of stored mapping output is bookkeeping, not model
  output. And `mapping_quick`'s cached path makes **no model call at all**
  (`"cached": True`, `agents/mapping.py:194-204`); its stored 2,144
  tok/step are engine-written. Any "mapping output cost" read off stored
  variants without separating these is a storage artefact.

### R2. `dialogue_log` delivery metadata — the live dice pattern in the Director
**~0.03–0.04 s/turn at 1000 tps (~35 of 42 tok/beat). Kind: prompt-ask
trim; schema untouched. The correctness win outweighs the seconds.**

- The contract asks for `volume, visibility, conceal_from` on every
  dialogue_log entry (`prompts.py:2930-2932`), plus a whole
  carry-concealment instruction (`prompts.py:2176-2179`). But for every
  DECLARED line — player sequence or a character's own sequence, built at
  `agents/director.py:3928/:3958` from `e.get("volume")` etc. — the engine
  re-stamps all three from the original declaration and discards the
  model's transcription: `speech_concealment` at
  `agents/director.py:4880-4890`, overwrite at `:4949-4950`. The comment
  at `:4868-4879` records the measured failure this defeats (a declared
  whisper transcribed back as volume:'normal'). `DialogueLogEntry.volume`
  and `SpeechElement.volume` are the same enum authored twice, and the
  second authoring is discarded wherever the first exists.
- The model's tags survive only on lines it legitimately originates
  (voiced background presences, simple creatures — no declaration to
  re-stamp from). Honest contract wording: "the engine re-stamps
  volume/visibility/conceal_from on declared lines from the declaration
  itself; supply them only for lines you originate."
- Safety of the trim, verified: a declared line whose quote body the model
  altered misses the re-stamp key, but the authority loop above drops
  invented cast/player lines and `:4959-4979` deterministically re-appends
  the true declaration with its true tags — so defaulted tags on a
  paraphrased transcription cannot leak a whisper; the paraphrase itself
  is removed.
- Measured: 2.66 dialogue_log lines/beat; the three fields cost 41.8
  tok/beat (volume distribution: normal 5,327, mutter 320, loud 128,
  whisper 120, shout 31). Assuming ~80-90% of lines are declared, the trim
  saves ~33-38 tok/beat. `tone` and `intended_target` stay — tone is
  genuine authorship (and the dedup tiebreak, `:4996`), intended_target
  drives the comm-medium delivery rescue.

### R3. Audience adjudication in `resolved_event` prose — droppable ask, conditional
**≤ ~0.05 s/turn at 1000 tps (bounded by 28% × 191 tok). Kind: prompt
instruction rewording. Condition: only after `PERCEPTION_NO_LLM` defaults
on. The real gain is consistency, not seconds.**

- Note 01 measured 28% (13/47) of the Director's unhomed residual as
  perception adjudication written into prose — "who heard what through
  which wall, what a desk now occludes … per-perceiver routing, asserted
  by the wrong stage" (`design_notes/01-corpus-measurement.md:88,137`).
- The composer path never consumes `resolved_event`
  (`agents/perception.py:4098` comment; note 13 §Wiring): hear_level with
  measured proximity, `visual_level_between` + the S2a view cone,
  `sound_walk_level`, `sound_bearing`, and `infer_focus`'s salience snap
  now compute everything those prose rulings used to assert. On the MODEL
  path, perception still reads the prose, so the instructions cannot be
  touched until the flag flips.
- Instructions that currently request the adjudication (confirmed):
  `prompts.py:2042-2044` (a runner "arrives LOUDLY: they are heard further
  off" — propagation is `sound_walk_level` + the alarm snap now),
  `prompts.py:2589` ("A crowd seen through a doorway is a shape and a
  sound; its words do not cross" — barrier gating is engine-side),
  `prompts.py:2793-2823` (the LIGHT block's per-perceiver halves: "knows
  they are being approached without knowing by whom", "must not recognize
  them by sight alone" — recognition and visual grade are engine-side).
- STATED CAUTION: each of these blocks also carries outcome CAUSALITY that
  is the Director's real job (an act needing sight fails in a dark room; a
  winded runner fights worse). Only the "narrate who perceives what" half
  is droppable. This is a careful prompt edit, not a deletion — and no
  contract field is involved (checked: nothing in
  `prompts.py:2930-2975` asks for sound propagation or attention
  direction; focus/salience is wholly engine-derived in
  `world/spatial_frames.py`).

### R4. `dialogue_order` — still asked, still derivable, still negligible
**~0.007 s/turn (7.0 tok/beat measured). Kind: prompt-ask trim + code
projection; schema field stays.** Still in the contract
(`prompts.py:2930`); sole consumer is a model-path perception payload hint
(`agents/perception.py:3647`, the composer path ignores it); a
deterministic guard polices it for phantom speakers
(`agents/director.py:4837-4866`) and note 04 measured 92.6% redundancy
with dialogue_log order. Correct to fold into the next prompt edit (it
also deletes the guard); not an optimization. Do not pad it into one.

### R5. `resolved_event` as a private reasoning field — still blocked
**Potential ~0.19 s/turn (191 stored tok), NOT claimable now. Kind: field
semantics change with real blast radius.** The composer removed the
largest consumer class — per-perceiver view surgery
(`_redact_concealed_from_event`, `_surface_translate_event`) is bypassed
whenever the flag is on, and those were the only firewall-surface
consumers. But 11 external consumer sites remain in this tree:

1. `agents/perception.py` model path (payload assembly `:3560-3604,
   :3646,:3681`; surgery `:3079ff,:3116ff`; `_inverted_motion_check`
   `:2246` runs on both paths, tripwire-only on the composer's
   `:4086,:4793`).
2. `agents/background.py:123,:522,:727,:878` (presence earshot slices).
3. `commit.py:1487,:1768` (attire keyword scans).
4. `commit.py:2824` (S3-A8 entity copy-forward salience).
5. `commit.py:3421-3570,:3726-3730,:3965` (background reactor salience +
   name mention — **X7 is still open**: raw prose, no concealment gate).
6. `commit.py:3548,:3721` (`settle_claims` adoption inference).
7. `commit.py:4500,:4512` (mapping_commit LLM payload).
8. `commit.py:5749` (intention evidence pool).
9. `commit.py:6347` (events row archive).
10. `commit.py:6538` (`resolve_authored_events`).
11. `importers.py:784` (promotion evidence pack).

Plus the Director's own prose-policing (authority checks
`agents/common.py:2918,2998,3072,3300,3435` via
`agents/director.py:4325-4502`; restraint/unconsciousness/destruction
scans `:1479-2199`; reconciliation `:3309ff`; fallback `:4702-4717`;
establish alias `:696`), the step-inspector UI
(`static/js/chat.js:954,1107`), and opaque archive/trace carriage. The
narrator still consumes it nowhere (`agents/narration.py:390` is a
comment). Verdict: the note-04 §2 migration (consumers → `beat_events`
subjects) is still the price of privatizing the field; the composer paid
the perception share of it, nothing else. Note 04 §3.5's position (keep
the prose as private CoT even then) stands unchallenged by anything
measured here.

### R6. Findings that are NOT the dice pattern (checked and cleared)

- **`effective_facing`**: no prompt anywhere asks a model to author
  facing (`llm/prompts.py` greps clean — `:624,:655,:692,:3270` all describe
  derived values). Pure derivation; nothing to remove.
- **`effective_anchors`**: door pseudo-anchors were never asked for;
  authored anchors win collisions. The mapping anchor ask
  (`prompts.py:3546-3549`) stays — see §2.
- **`effective_station` / `effective_room_size`**: both are
  fallback-ordered, authored-wins (note 12 §1). Derived-as-fallback, not
  derived-always; the asks stay — measured in §2.
- **Sound/attention**: no resolve output field asks for either; the
  prose-level instructions are R3's subject.
- **Declared-mover `positions`** (note 04 §3.2.7): unchanged by this
  branch; still a valid earlier finding, not re-opened here.

## 2. The mapping layout question, settled with numbers

The tension: note 07 wanted mapping OBLIGATED to author layout (+ G6
coverage warning); the derivation layer now manufactures placement data.
Should mapping be asked for less?

**No. Derivation is a thin floor and an amplifier of authored data, not a
substitute. Keep every layout ask; land the G6 warning.** Measured on the
61 live scenes by running the derivation functions themselves:

- **Stations**: 511 positioned bodies; 41 (8.0%) have an authored
  station. Of the 470 without one, `effective_station` rescues **10
  (2.0%), all near-only** (contact-derived mutual `near` — no `at`
  placement at all on standing scenes; crossing-derived door placements
  are transient and only exist mid-movement). **90% of live bodies still
  have no placement.** The "everyone in a great hall reads `near`"
  problem is still only fixable by authored stations/size.
- **Size**: 392 rooms, 217 (55%) authored. Of the 175 bare rooms the
  keyword hint rescues 24; 151 default to `medium`. And size is MORE
  consequential post-derivation (S2a's placement-unknown fallback caps
  large-room sight at `shapes`; far/remote edges cap sight) — an
  unauthored size is now a wrong perception grade, not just flat prose.
- **Anchors**: 179 rooms (46%) authored; door pseudo-anchors give 205
  previously-anchor-less rooms their first positional vocabulary (only 8
  rooms have none at all). That is derivation doing its job — but
  contact-DERIVED stations require an *anchor-backed* partner to seat a
  body (note 12 §S1b), so every authored anchor now yields more derived
  value, not less. Amplifier, not replacement.
- **Facing**: 54 bodies persisted; `effective_facing` derives **0** on
  standing scene blobs (the focus/crossing arms need in-turn transient
  data). In-turn coverage is better than this figure but was not
  measurable statically — flagged as suspected-better, needs a
  turn-replay test.
- **Cost of keeping the ask**: `scene_patch` is 453 tok (12%) of a real
  mapping call's model output, and real calls run 0.18/turn → the entire
  layout ask costs ~0.015 s/turn at 1000 tps. With R1 landed, asking for
  MORE layout coverage is nearly free. G6's warning (flag rooms sized by
  keyword, note 12 §4) is one `effective_room_size`-vs-authored
  comparison at the mapping/commit seam.

**The `distance` vocabulary question**: keep parsing free-form; do not
close the vocabulary. Live corpus: 509/530 edges (96%) carry a distance in
28 surface forms, and `normalize_edge_distance` maps **every one of the
28** to a sane tier (252 near / 249 adjacent / 8 far / 0 remote; `'0'`,
`'1'`, `'2m'`, `'1 step'` → adjacent; `'50m'` → far; `'transit'` → the
`near` default). Nothing falls through wrongly. A closed enum would save
~1-2 tok/edge at ~0.3 authored edges/beat (<0.005 s/turn — negligible),
would LOSE information the parser gets free (metric values distinguish
20 m from 75 m; a forced tier does not), and contract churn is the known
compliance risk (the `stations` lesson). The one cheap improvement is
prompt-side: name the four tiers and "or meters" as PREFERRED forms
without forbidding the rest — zero-risk wording, no contract change.

## 3. Summary table

| # | Finding | Kind | s/turn @1000tps | Per-call tokens | Condition |
|---|---|---|---|---|---|
| R1 | mapping `relevant_lore` content echo → engine join | ask-trim + join code | 0.06–0.09 (0.49 s/call; 7.6 s/call @64tps) | ~485/mapping call | none; also fixes 13.6% mutated-echo lore poisoning |
| R2 | dialogue_log volume/visibility/conceal_from on declared lines | ask-trim | 0.03–0.04 | ~35/beat | none (re-stamp + re-append already authoritative) |
| R3 | perception-adjudication prose instructions | prompt rewording | ≤0.05 | ≤54/beat | composer flag default-on; keep the causality halves |
| R4 | `dialogue_order` projection | ask-trim + projection | 0.007 (negligible) | 7/beat | fold into next prompt edit only |
| — | `why_relevant` (no code consumer) | ask-trim | 0.01 (negligible) | 56/mapping call | author-inspection value; taste call |
| R5 | `resolved_event` privatization | field semantics | 0.19 potential, blocked | 191/beat | note-04 §2 consumer migration (11 sites) |
| — | close the `distance` vocabulary | rejected | <0.005 | ~1-2/edge | loses metric info; churn risk; parser covers 100% of corpus |
| — | drop layout asks because derivation exists | rejected | — | — | derivation rescues 2% of stations, near-only; keep asks + land G6 |

Realistic combined near-term saving (R1+R2, unconditional): **~0.1–0.13
s/turn at 1000 tps** — honest and small on the owner's hardware; R1's
per-call figure (~0.5 s at 1000 tps, ~7.6 s at 64 tps, 38% of mapping's
model output) is the number that generalises, and R1's fidelity fix is
worth landing independent of latency.

## 4. Judged too risky / explicitly not proposed

- **Removing any schema field** (`dialogue_order`, `dice`,
  `fiction_frame`, `resolved_event`, `DialogueLogEntry.volume`):
  `LenientModel` drops undeclared keys on round-trip, and archives
  (`persist/chat_archive.py` carries steps/variants opaquely), pipeline traces
  (`persist/pipeline_trace.py` replays stored content), and checkpoint restore
  all carry historical values — a field removal breaks replay/rerun of
  every pre-change turn. Every proposal above is ask/wording + code
  projection; schemas untouched.
- **Trimming the LIGHT block wholesale** (R3): its causality halves are
  load-bearing Director work; only per-perceiver rulings are droppable,
  and only post-flag-flip.
- **Constraining `distance` to an enum** (§2): negative expected value.
- **Any change to `stations`/anchors/size asks**: derivation measured too
  thin to substitute (2% rescue, near-only).
- **Counting `mapping_quick` stored tokens as cost**: 1,879/1,881 steps
  are cached zero-LLM returns; treating their 2,144 stored tokens/step as
  model output would have manufactured a fake ~1.9 s/turn "finding".
  Same for `mapping_stage`'s engine-written `candidates` (2,457 tok/call).

## 5. Suspected, needs a test (not claimed above)

- In-turn `effective_facing`/crossing-derived station coverage (static
  scenes measure 0/2%; live turns should do better via focus/crossing
  arms) — needs a replay harness pass, not static blobs.
- The share of dialogue_log lines that are declared vs
  Director-originated (R2 assumes 80-90%; stored data is post-re-stamp so
  it cannot distinguish). A one-line counter in the re-stamp loop would
  measure it live.
- R3's true prose share on THIS corpus (28% came from note 01's 50-turn
  sample of unhomed residual, not from all resolved_event prose).
