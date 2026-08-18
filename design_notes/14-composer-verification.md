# 14 — Composer verification: full-corpus replay measurement

Status: **COMPLETE.** Every number below is measured unless explicitly
marked inferred/approximate. Scored with the identical code path the model
baseline used (`tools/perception_quality.py::score_view`; engine checkers
resolved on THIS tree), on entitlements rebuilt from the same stored
structured data. Zero live model calls were spent on the measurement run
(one stray `role=utility` call escaped during smoke testing —
`story/artifacts.py`'s lazy notice wording re-triggered by checkpoint restore —
before the harness hard-blocked `providers._session`; the full replay made
none).

## How it was measured

The full corpus (62 chats, 2,296 turns, snapshot `engine.db` opened
read-only, never written) was replayed through the REAL stage entrypoints
(`perception_establish/act/outcome`) under `PERCEPTION_NO_LLM=1`, one turn
at a time, on a scratch sqlite backup: each turn's checkpoint restored with
the engine's own `checkpoints._restore_checkpoint_body`, context seeded
from stored step outputs exactly as `agents/runtime.py` rehydrates them,
composer cross-turn ledger carried forward from the replay's own previous
composed turn (what the engine would do were the composer live).

Coverage: **4,521 unique (turn, stage) stage executions, 0 stage errors.**
2 turns have no checkpoint. 106 turns initially failed CHECKPOINT RESTORE
(not the composer) and were recovered with two replay-side repairs that
mirror live FK semantics; one of the two exposes a real engine defect —
**chat 18's checkpoints reference a deleted turn id in
`world_entities.created_turn_id`, so the engine's own `restore_checkpoint`
(reroll/recompute) would abort on that chat today.** Deserves its own
UNBUILT entry.

**Corpus stability caveat:** while the last scans were finishing, a live
server was started against THIS worktree's `engine.db` (uvicorn :8009,
11:07) and two chats (ids 68/69, 131 turns) were deleted through it — by
the host, via the normal delete route; verified NOT caused by the harness
(all harness access was `mode=ro`; the full-table comparison that caught it
also confirmed nothing else changed) and not by the test suite (conftest's
session guard held; the rows were present after the suite finished). Every
number in this note was measured on the full 62-chat / 2,296-turn corpus
before that deletion; a re-run on the current file will be smaller by those
131 turns. `engine.db` here is live, not frozen — future measurement runs
should copy it first.

Of the baseline's 7,822 scoreable (turn, stage, observer) keys: 6,768
scored with a non-empty composed view, 1,025 composed empty (§D3), 29 lost
to cast reconstruction. The same 1,535 stored views the baseline could not
score (deleted characters, `extra:` and background keys) are excluded here.
Replay fidelity limits, flagged: memories/lorebooks not restored per turn
(perception reads neither; lore only feeds a room-notes fallback), disguise
and awareness state came from the restored world exactly as live.

---

## A. Fact fidelity vs the model baseline — the scored table

"model" is the stored corpus re-scored on this tree (the correct-tree
re-derivation note 06 called for; leak metrics reproduce note 06 exactly;
its recall is ~1pp more favorable to the model than note 06's
divergent-base run — the same yardstick is applied to both columns).
Floor era = turn_id ≥ 1503.

| metric (floor era; 3,249 model / 3,235 composed views) | model | composer | verdict |
|---|---|---|---|
| unearned-identity views | 107 (3.3%) | **69 (2.1%)** | better; NOT the promised zero |
| self-narration views | 186 (5.7%) | **0** | zero post-scrub (see A2) |
| invented-dialogue views | 7 | **0** | zero post-scrub |
| undeclared-player-speech views | 32 | 30 | parity (A3 artifact) |
| unentitled-line leaks | 8 views / 16 lines | 8 / 16 | parity — same lines, same deliberate channels |
| concealed-line leaks | **0** | **0** | held |
| delivered-line recall | 94.95% | **98.51%** | +3.6pp |
| same-room line recall | 95.37% | **98.72%** | +3.6pp |
| player same-room lines missing | **6** / 1,509 | 33 / 1,509 | **REGRESSION — root-caused, A2** |

All-turns segment has the same shape (identity 204 v 524 views; recall
97.7% v 92.8%; player misses 77 v 28).

### A1. "Zero identity leaks by construction" is false as shipped

Two mechanisms, both verified on samples:

1. **The tripwires caught 957 unearned-identity admissions** (234
   floor-era) that Layer A let into the IR; the scrub cleaned the stored
   text, so they are absent from the 69. By the build note's own definition
   (a firing tripwire is an engine defect) these are 957 engine defects.
   Confirmed channels: **appearance/overlay prose naming third parties**
   (the orchestrator strips only the described body's OWN name tokens,
   `agents/perception.py:4296-4298`, while a scene-overlay appearance
   naming an entangled partner passes through), and act/contact surfaces
   scrubbed only against the stage roster.
2. **The surviving 69 floor-era leaks are dominated by `room_notes`**
   rendered verbatim by `environment_percept` (`agents/composer.py:312`)
   with no identity gate at admission and no tripwire coverage when the
   named character is not in the stage roster (verified: a player view
   carried a never-met character's name from a room note, zero warnings).
   119 of 204 all-turns leak views leak the same name the stored model view
   leaked — an inherited channel, now the dominant one.

### A2. BLOCKING: the armed prose guards destroy entitled quoted speech

`_strip_self_narration`, kept armed as a "free" tripwire
(`agents/perception.py:4240`), splits sentences INSIDE quoted spans and
deletes mid-quote sentences that name the perceiver. Verified end-to-end
(chat 10, turn 29): the stored composed player view is a 147-char fragment
ending mid-quote — everything after the perceiver's name in a delivered
168-char line is gone, reproducible by calling the stripper on the rendered
text. **167 of 382 self-narration fires dropped text containing quote
characters.** This — not hearing gates — is why the composer loses 33
floor-era player same-room lines where the model lost 6; the composer's
only recall regression is self-inflicted by a repair pass its own IR makes
unnecessary. It also cascades: the invented-dialogue tripwire then sees the
mangled quote, fails to match it against the spoken-lines ground truth, and
deletes the whole line (verified: a flagged "invented" line is a stored
dlog quote with its middle sentence stripped; ≥16 of 77 invented-dialogue
fires are this cascade). The remaining 215 self-narration fires are genuine
Layer A admissions (room notes and authored ambient events narrating the
perceiver — e.g. an establish-stage ambient event describing the
perceiver's own voice).

### A3. Metric artifacts, stated plainly

- All-turns "undeclared player speech" is worse (130 v 83) because the
  composer honestly renders ungated background lines as "You hear a voice
  say: …" and the checker, unable to attribute an unnamed voice to a cast
  member, blames the player. Floor era is parity (30 v 32). Not a leak.
- The 8/16 unentitled-line parity is the same lines both sides — the
  ubiquitous-bodiless-voice and open-group-continuity compatibility floors,
  deliberate spec carried over from the model path.

## B. Retrieval / memory (lexical proxy where marked)

| metric | model baseline | composer | |
|---|---|---|---|
| "You are in an unspecified area." memory rows | 812 | **0** | claim VERIFIED |
| eventless beats minting nothing | never (every view minted) | **982 of 3,462 outcome slots mint nothing** | claim VERIFIED (commit path checked: empty episode → no row) |
| verbatim-twin rate within bank | 14.6% | **0.4%** | 36× better |
| self-retrieval MRR (LEXICAL PROXY, 800 queries, tie-pessimistic) | 0.299 | **0.860** | 2.9× |
| own memory at rank 1 (proxy) | 25.1% | **82.6%** | |
| displaced by verbatim twin (proxy) | 13.1% | **0.4%** | |

Embedding-space collision/spread gates: NOT MEASURED — they require the
corpus's online embedding model; the harness's marked hook is the seam.

The view TEXT went the other way: 94.2% of composed first sentences are
non-unique (stored: 73.0%), 93.5% of sentences duplicated verbatim (74.4%),
mean 9.2 sentences/view. Retrieval is immune (episodes are deltas) but
every reader of the view — character-agent context, narrator input — now
gets heavily templated, staccato prose. This is note 13's fusion gap made
visible at corpus scale, and it bears directly on the owner's bar (§F).

## C. The specific build claims

1. **"Unspecified area" impossible — VERIFIED.** 0 occurrences in 7,064
   composed views; 0 episodes; and 745 of the 1,025 "composer empty where
   model had text" keys are exactly the model's old unspecified-area
   boilerplate — the composer's silence there is the fix working.
2. **Eventless beats mint nothing — VERIFIED** (982 non-events; commit.py
   `prepare_memory_commit` writes no row for a composed "").
3. **Appearance once per observer — MOSTLY HOLDS, not absolutely.** The
   old bug was one description pair repeated 481+249 times verbatim.
   Composed corpus: 849 beyond-first re-renders TOTAL across all
   descriptions and observers (225 floor-era), worst single case 34
   repeats. All at outcome; 505 player-side (look-verb `full_render`
   re-earns everything — "check"/"search" are look verbs and this corpus
   checks things constantly), 344 NPC-side (structural-change `force` from
   attire/overlay/scale diffs re-earning unchanged base descriptions).
   ~9% of views still carry a repeat render. Better by an order of
   magnitude; "once per observer" is overstated.
4. **Stranger labels distinct — VERIFIED where the machinery applies;
   a sibling class is not covered.** 0 numeric-suffix labels and 0
   colliding descriptor labels in 89 multi-descriptor views. BUT 282 views
   render two-plus co-present dim/degraded bodies as the identical fixed
   sentence "An indistinct figure is …" — referentially indistinguishable
   (and reading as a stutter). The claim as worded holds; the reader's
   problem it addresses does not fully go away.
5. **Flag unset ⇒ byte-identical — VERIFIED to the extent testable
   offline.** All three composer branches sit behind
   `perception_llm_disabled()`; the model-path return carries no
   `episodes` key, so commit's composer branch is structurally inert;
   full suite green at **5,690 passed** with the flag unset. (A live
   API-path byte-diff is not possible without spending model calls.)

## D. Under-grant gaps, quantified

| gap (note 13's own list) | measured cost on this corpus |
|---|---|
| micro-loop appended, not IR (episodes miss loop content) | **339 turns (131 era), 590 observer-views** whose episodes omit interaction-round content their views carry |
| last-overt-only acts | **349 turns (151 era), 511 overt act surfaces dropped (230 era)** — plus 29 inverted-motion warnings where the composed view contradicts the committed outcome direction (composer renders declared intent, not resolution; the model path rendered from `resolved_event`) |
| other-players' onset sequences | 19 turns |
| poses not composed | 75 turns have scene poses (all floor-era) |
| scales not composed | 105 turns (49 era) |
| contained-ledger not composed | 106 turns (42 era) |
| crowds / couriers / notices | **0 turns — this corpus never had them**; gap is free here, real for future stories |
| `source_manifest` tells/demeanor | **0 cast rows carry a manifest** — free here |
| scent | 1 cast row mentions a scent field; only reachable channel is authored ambient at establish — negligible here |
| sightlines/visible-rooms | 2,230 of 2,231 replayed turns are multi-room scenes (upper bound only; NOT precisely measured — visibility depends on barriers) |

### D3. The 1,025 empty composed views, characterized

Stored views at those keys: median 31 chars; **745 are the
unspecified-area boilerplate** (fix, not loss); the rest are mostly one-line
orientation filler; 99 contained a quote character, but only 8 entitled
lines (all-turns, 0 floor-era) were actually lost to empty views — already
counted in the recall table. The composer's "nothing reached this mind" is
overwhelmingly honest silence replacing fabricated filler.

## E. Prose-quality defects seen in samples (not scored by the harness)

- Tone grammar: adjectival tones render as "says with quietly
  authoritative in their voice", "with bright in their voice" — constant,
  reader-facing, from `_inject_dialogue`'s tone slot receiving adjectives.
- Dialogue sentences after a period can start lowercase ("… is close by.
  the fox woman says: …").
- Chronology oddities: a speaker's lines can render before their arrival
  sentence ("X says … X comes in.") because speech order keys precede the
  crossing percept.
- Staccato template repetition (§B) is the dominant texture difference.

## F. Verdict: DON'T SHIP YET — two composer-path fixes and a prose pass short

**Where it is better than the model, with numbers:** delivered-line recall
98.5% v 95.0%; identity leaks 2.1% v 3.3%; self-narration and invented
dialogue 0 v 5.7%/0.2%; concealed-line zero held; memory twins 0.4% v
14.6%; self-retrieval MRR 0.860 v 0.299 (lexical leg both sides); the
812-row unspecified-area pathology is dead; 4,521 real stage executions
with zero errors; and the entire corpus composed in ~8 minutes single-
threaded INCLUDING checkpoint restores — against a median 9.35s and ~4
provider calls of perception latency per turn. The architecture does what
it promised.

**What blocks shipping, ranked:**

1. **The armed prose guards must stop repairing composed output** (A2).
   They are the composer path's only mechanism for destroying entitled
   content, and they used it: 33 v 6 player-view line losses, 167
   quote-mangling strips, ≥16 cascade deletions. Detect-and-warn (or
   quote-aware stripping) on the composer path; taking the scrubbed text is
   not "free defense in depth", it is the regression.
2. **Authored prose surfaces need identity/self gating at admission**
   (A1): room notes, appearance/overlay descriptions, ambient events —
   scrub against the full chat identity space when the observer lacks
   recognition, at percept-build time. This closes both the 957
   tripwire-caught admissions and most of the surviving 69 (the roster gap
   means the tripwire cannot be the backstop here).
3. **The fusion/tone/capitalization prose pass** (B, E). The owner's bar
   is "same quality as the current engine, just faster." Information-wise
   the composer is strictly better; texture-wise a reader will notice
   94%-templated openings, staccato sentences and "with quietly
   authoritative in their voice" within minutes. A composer that says less,
   less gracefully, is not "same quality" even with cleaner information —
   this is exactly the trap the measurement brief warned about, and as
   built it is real.

Not blocking, but should be scheduled honestly: outcome views render
declared intent rather than resolved outcome (29 measured direction
contradictions, 511 dropped overt acts — needs the Phase-1 typed outcome
surface); episodes omit micro-loop content on 339 turns; the indistinct-
figure duplication (282 views); poses/scales/contained (~100 turns each).
Crowds/couriers/manifest/scent gaps cost nothing on this corpus.

**Measured vs inferred:** every count above is measured from the replay
and read-only corpus. Inferred/approximate, flagged as such: the
multi-room sightlines upper bound; look-verb attribution of player-side
appearance re-renders (mechanism verified in code, per-case intents not
enumerated); lexical-proxy MRR stands in for embedding MRR on both sides
equally. Not measured: embedding-space collision/spread, blind-judge
verdicts (no model budget), live narrator behavior on delta player views
(note 13 #7 — needs live runs).
