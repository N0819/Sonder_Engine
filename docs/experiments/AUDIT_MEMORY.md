# Audit record — the memory subsystem

Status: EVIDENCE. Written 2026-08-19, immediately after the `mind/memory.py`
split ([`docs/design/SPLIT_MEMORY.md`](../design/SPLIT_MEMORY.md)) landed, per
that plan's closing note: "Both belong to the audit that follows the split."
This is that audit.

Method, because the findings are only as good as it: every section of
[`docs/guides/MEMORY.md`](../guides/MEMORY.md) was walked against post-split
source by three parallel readers (§1–4+13, §5–7, §3+8–9), every number in the
doc checked at its file:line; retrieval was then exercised against a **copy**
of the owner's live database (9,608 memories, 422 summaries, 2,311 lore
entries, 66 chats) with the real configured embeddings provider
(`openrouter:3:perplexity/pplx-embed-v1-4b`, 2,560 dims, live and matching the
whole corpus); and every live finding below was re-derived by an adversarial
pass instructed to refute it before it was allowed in. `engine.db` itself was
opened read-only throughout and never run against; everything that writes ran
on `/tmp` scratch copies via `ENGINE_DB`. External literature was surveyed in
parallel; it appears in §4 with sources.

Line numbers are as of the split-day revision (post `mind/memory_*`).
Findings are **flagged, never fixed** — nothing in this audit changes
behaviour. Corpus numbers are a snapshot of 2026-08-19 and go stale the moment
anyone plays a turn; treat them as evidence for the shape of a claim.

---

## 1. Confirmed defects

### 1.1 `_kw_scores` discards BM25 — confirmed, but its blast radius is HALF what the split plan recorded

`mind/memory_common.py` `_kw_scores` orders by `rank` (which *is* bm25()) and
throws the score away for a positional decay, `1.0 - i / max(len(rows), 1)`. A
single weak match scores 1.0, the best match in a field of fifty also scores
1.0, and the decay slope depends on *how many* rows matched, never on how well.

**The carried defect statement — "it is the keyword half of both
`search_memories` and `search_lore`" — is stale.** Verified by repo-wide grep:
the only production consumer is `search_lore`
(`mind/memory_lore_entries.py:260`). `search_memories` uses its own
`_lexical_memory_ranking` (`mind/memory_retrieval.py:30`), which feeds only the
id ORDER into RRF — and RRF discards magnitude for all four of its rankings by
construction. Since `_kw_scores`' positional decay is order-preserving
(`ORDER BY rank`), an order-only consumer is unharmed. Character-memory
keyword ranking is therefore NOT damaged by this defect.

Where the magnitude *is* consumed — `search_lore`'s
`0.65 * cosine + 0.35 * keyword` blend (`memory_lore_entries.py:283`) — the
damage was measured by counterfactual: same queries, `_kw_scores` versus a
true normalized BM25 magnitude (`-bm25/max`), over the live books.

| corpus | trials | top-1 changed | top-10 membership changed | mean swaps /10 |
|---|---:|---:|---:|---:|
| mixed small/medium books (chats 40, 27) | 36 | 11% | 17% | 0.19 |
| large books (192/197, ~311 entries, chats 65/67) | 32 | 6% | **59%** | 1.06 |

So on a large lorebook, more than half of all queries hand the mapping stage a
different lore set than true keyword relevance would — about one entry in ten
swapped — while the top hit usually survives (short queries produce heavy
genuine BM25 ties, which caps how often a magnitude fix can move rank 1; the
adversarial pass verified the sign convention, the normalization and the
patch mechanics, and sampled the tie structure). Real, bounded, and worth
fixing: the fix is ~3 lines (return normalized `-bm25` instead of the
position decay), and `tests/test_lore_blind_scoring.py` already knows how to
patch the seam.

### 1.2 Stale-dimension vectors — the premise has EXPIRED for memories; what survives is a latent hole in `search_lore`

The carried defect — "a vector at an old dimension competes on the keyword
term alone" — describes a corpus state that no longer exists. Measured: **all
9,608 memory rows and all 422 summary rows are on
`openrouter:3:perplexity/pplx-embed-v1-4b` at dim 2560**, matching the live
provider; zero stranded rows. Lore: all 2,311 entries are at dim 2560. The
rebuild machinery (§9 of MEMORY.md) plus the startup reconciler (see drift
item 2.1) have done their job.

What the audit confirms instead is the **class** hole that would make the
defect return silently in lore only: `search_lore` checks vector
compatibility by DIMENSION alone (`len(qv) != len(vec)`,
`memory_lore_entries.py:280`), never by model key — unlike `search_memories`,
which requires `embedding_model == model_key AND embedding_dim == dimensions`
(`memory_retrieval.py:407`). Two different models at the same dimension would
be cosine-compared as compatible, producing garbage similarity with **no
"blind" warning**, since the warning keys on dimension too. This is latent
today and armed: 840 of 2,311 live lore entries carry a NULL
`embedding_model` stamp, so even a model-key check added later cannot
classify them without a backfill. (The `lore_fts` rowid join is correct —
`content_rowid='id'`, `core/db.py:250` — that part was checked and holds.)

### 1.3 Stopword-grade cue material has captured the "exact match" ranking

This is the audit's largest NEW finding. It was found by retrieval quality,
first misattributed to entities, and re-derived by the adversarial pass — the
corrected numbers below are the verified ones.

Live rows carry retrieval cues like key phrases `"the"`, `"her"`, `"you"`,
`"'; said '"` and entities `"She"`, `"And"`, `"Uhmm"`, `"Time And Relative"`.
Measured on the live corpus: **76.1% of all 9,608 memories carry at least one
stopword-grade KEY PHRASE, and 31.3% a stopword-grade entity.** Most of the
stock is legacy: the current `_extract_entities`
(`mind/memory_write.py:83`) has a 37-word blocklist and a sentence-initial
decline rule — but re-extracting all 9,608 contents through today's extractor
still junk-stamps **9.9%** of rows (quote-initial interjections like "Oh"/
"Uhmm" bypass the sentence-start guard because the preceding character is a
quote mark, not `.!?`), and `_extract_key_phrases` appends entities into
key_phrases, so entity junk becomes key-phrase junk.

The junk reaches ranking through three doors at once:

- **`_exact_cue_score` uses bare substring matching**
  (`memory_retrieval.py:55-67`): a stored key phrase `"the"` is "literally
  present in the query" for any English query. Measured with the real scorer
  on one real probe query: **467 of 657 rows (71%) of a live bank score ≥0.7
  "exact match"** — every one a key-phrase fire at the FULL 1.0 tier ("the"
  alone fires on 417 rows). Those all enter the exact ranking: the
  HIGHEST-weighted RRF list (1.25), the one list that is uncapped (sem/cue/lex
  are `[:60]`; exact is not), with ties ordered by insertion order — so the
  signal MEMORY.md §5 documents as the strongest and rarest is, on this bank,
  a near-bank-wide arbitrary-order boost. The bare-substring class was found
  and fixed once already in this codebase (`_durable_dialogue_category` grew
  word boundaries after "compromised" matched as a promise); this is the same
  class, live, in retrieval.
- **`cue_embedding` is built from those phrases/entities** (`_memory_cues`),
  diluting the second-highest-weighted ranking (1.15).
- **FTS mirrors them**, wasting keyword-match slots.

Two counterfactuals, reported with their limits: word-boundary matching alone
changes a mean 0.75/16 top-16 slots (it is the wrong fix — `\bthe\b` still
matches "the"); a stopword-FILTERED scorer churns a mean **7.33 of 16 slots**
across the 12 live probes, i.e. the current junk fires are deciding roughly
half the payload — but on this small probe set hits moved 10→8, so the net
direction of that particular fix is NOT established. What is established is
the mechanism (71% fire rate on a signal designed to be rare) and the sharpest
live failure it plausibly produces (§3.2): a first-meeting memory that cannot
reach top-16 **even when retrieval is restricted to its own ten-turn window**,
carrying gist "the player: Uhmm my name is Hinami…" and poisoned cues.

The fix must therefore come with its own measurement (§4.1): fix extraction at
mint, repair the stock (cues are re-derivable from `content`, cue vectors
re-embed in one bounded batch), and evaluate any scorer change against a
labeled probe set before shipping it.

### 1.4 `record_dispute` applies a gist-matched dispute to EVERY matching row

MEMORY.md §13 claims gist matching "is accepted only when it resolves
unambiguously inside the character's own bank." The code
(`mind/memory_read.py:262-292`) resolves ref → exact gist → loose substring
and then stamps the dispute (and the +0.2 importance raise) on **all** hits
with no ambiguity check. A short legacy gist substring-matching five rows
re-reads all five. Own-bank only, so no firewall exposure, and disputes have
fired once in production ever (one live row) — but the documented property
does not exist in code. Either refuse multi-hit gist resolution or weaken the
doc's sentence; the code's own docstring promises only "exactly-then-loosely",
so the smaller honest change is the code one.

### 1.5 The `kind` vocabulary is not enforced at mint, and rows have escaped it

MEMORY.md §1: kinds are `episodic / dialogue / inference / semantic /
relationship / promise / intention`. Live data holds two values outside that
list: **`episode` (253 rows)** and **`belief` (1 row)**. Consequences are not
cosmetic, because two consumers test `kind` by exact string:

- ranking's belief weighting fires on `kind == "inference"` only
  (`memory_retrieval.py:466`), and
- `reconcile_inference_confidence` selects `kind='inference'`
  (`mind/memory_inference.py`),

so the `belief` row (chat 19 — provenance `inferred`, confidence 0.55) is
permanently invisible to belief revision AND to belief-weighted recall: a
belief that can never be revised or demoted. One row today; the class is "any
mint path that supplies a kind verbatim." Three LIVE mint sites emit
`kind: "episode"` today — greeting seeds (`story/greetings.py:327`),
drive-shift memories (`persist/commit_memory.py:1232`) and promotion memory
seeds (`persist/commit_background.py:1622`, minted with `turn_idx` NULL, so
the "all at turn 0" shape of the 253 rows will drift as promotions occur).
Their practical effect is benign today (padding, contrast and category
mapping read `category`, and `_default_category` maps unknown kinds to
"episode"), but every future `kind`-equality predicate inherits the hazard.
A `kind not in KINDS → coerce + warn` at the upsert would close the class.

### 1.6 Minor, for the register

- `_exact_cue_score` is recomputed 3× per candidate row per query (sort key,
  filter, bonus loop — `memory_retrieval.py:423-424,478`). Linear waste, not
  a bug.
- `_upsert_memory`'s UPDATE arm resets `archived=0` — a re-minted event key
  resurrects an archived row into the recent buffer. Plausibly intended
  (re-minting means the event recurred); flagged because nothing documents it.

---

## 2. Doc drift — MEMORY.md is stale, the code is right

Each of these should be a one-commit doc edit; none is a behaviour problem.

1. **§9 "It is not called at startup" is now false.** `web/app.py:230`'s
   `_startup_engine` runs `_reconcile_embedding_bank()`, which calls
   `start_rebuild_if_needed()` on a daemon thread. The reversal is deliberate
   and documented in code (39 measured HTTP-429 write fallbacks, each writing
   a permanent `cheap:crc32:256` stamp a transient failure should not earn).
   §9's surrounding argument — "doing that silently … is the wrong default.
   The host is told and decides" — was never rebutted in the doc and now
   reads as the design when it is the superseded design. The `PUT
   /api/agent_models` half of the claim is still true.
2. **§5 "access_count is bumped for everything returned"** — only when the
   caller passes `record_access=True` (`memory_retrieval.py:583`); the mind's
   two call sites do, host/tool searches do not. (This is also why
   `tools/salience_replay.py`'s copy-first rule exists in its current form.)
3. **§5 mood congruence** reads a blended valence — `0.75 * encoding_valence
   + 0.25 * valence` (`_ENCODED_SHARE`, `memory_retrieval.py:185`) — not the
   raw `valence` the formula in the doc states. §2 documents the two-axis
   schema; §5's formula predates it.
4. **§6 "four stuck signals" — there are five.** `barren_goal`
   (`agents/character.py:855`) was added ahead of `goal_held` and its comment
   calls it the signal that caught the live case. The unbidden payload also
   carries `memory_ref`, `temporal_status`, `memory_form`,
   `non_authoritative` beside the documented keys (no id, no score — the
   spirit of "no id" holds for numeric row ids; the stable ref is there
   deliberately).
5. **§2 salience formula omits the length cap**: code is
   `0.45 + min(len, 400)/1600` (`persist/commit_memory.py:188`), so the
   length term tops out at 0.25 — which is what keeps the episode floor at
   ~0.70. The doc's uncapped formula would put every episode near the cap.
6. **§2 `_is_empty_view` matches four markers, not two** — the language packs
   add "nothing in particular reaches you this beat" and a Japanese
   equivalent.
7. **§2 "consolidation runs in a thread pool"** — the live turn path now
   schedules it out-of-band (`schedule_memory_consolidation` →
   `core/jobs.py`; `persist/commit.py:435,488`). The thread-pool form
   survives only for restore/import. The invariant (consolidation failure
   cannot roll back a turn) holds in both forms.
8. **§2 dialogue marker list reads as exhaustive and is a subset** — packs
   also hold bare `promise`, `i'll return`, `call me`, `the truth is`,
   `i betrayed`, `i hate you`, `i'll kill` and friends, per language pack.
9. **§8 archiving says "salience < 0.72"**; the code (correctly, per §13)
   reads `max(salience, effective_importance) < 0.72`
   (`mind/memory_summaries.py:635-651`). §13 states it right; §8 should say
   "the higher of the two".
10. **§12 corpus snapshot** is two weeks stale (6,463 → 9,608 rows; 145 →
    420-ish dialogue). The doc already warns its numbers rot; the shapes all
    still hold.
11. **`docs/design/SPLIT_MEMORY.md`'s defect note 1** (and the identical
    sentence wherever it was carried) should be corrected per §1.1 above:
    `_kw_scores` is the keyword half of `search_lore` only.
12. **UNBUILT §1.16's entry half is stale**: greeting seeds no longer "enter
    memory at salience 1.00" — `_seed_salience` clamps to 0.7
    (`story/greetings.py:218-226`). The 105 legacy rows the entry describes
    are real and still never age out (§3.4); the register entry should shrink
    to the data-repair half.

Everything else checked — and that is most of the document — is accurate at
source: the §5 weights/scale/bonuses to the digit, `_RRF_SCALE = 12.0`,
`_ASPECT_WEIGHT = 0.55`, `_RECALL_LIMIT = 16`, MMR 0.82/0.18, k+2 padding,
chronological return; §3's payload fields, absorption budgets 12/16/2 →
8/8/1 → 4/4/0, the no-defaults seam and its mutation-tested rules (the seam
test file was executed, 25 passed); §6's contrast formula term-for-term with
the 0.9 coverage gate and no writes; §7's floor/decay arithmetic and
firewall note; §8's windows, cutoffs on every summary surface, origin-on-drift
thresholds; §9's rebuild/refuse-fallback/vector-addressing behaviour and
append-only `memory_vectors`; §13's importance/dispute/remember_lines/support
mechanics minus the ambiguity claim in §1.4.

---

## 3. Live-corpus findings

Setup: probes ran through the real `search_memories` (production seam, real
provider embeddings) against a copy of the live database. The main instrument
is 12 hand-written paraphrase probes against the largest bank (chat 63, char
35 — the Doctor, 657 memories, turns 0–166), each naming a distinctive event
in deliberately shifted vocabulary, scored on whether the target row reaches
the k=16 payload a character would actually receive.

### 3.1 Headline: retrieval is good — 10/12 paraphrase probes hit at k=16

Vocabulary-shifted queries ("the tool she conjured out of thin air", "how she
appears to my sense of time, a gap where a person should be", "my ship
singing to her") retrieved their target rows in the top-16 in 10 of 12 cases
on a 657-row bank, targets spanning turn 2 to turn 93 queried from turn 167.
The ranking machinery — RRF fusion, cue vectors, the bonus band — works, and
works on paraphrase, not just term overlap.

### 3.2 The two misses share one anatomy: right era, wrong row, junk cue material

Both misses were the two earliest-era targets (t2 introduction, t4 first
TARDIS entry). The failure is NOT era-blindness: for the introduction probe,
the returned top-16 contained five rows from turns 0–3 (the surrounding
minutes), and the window ranking put the correct life-chapter (turns 0–9)
first. The target rows themselves lost — and kept losing **even when search
was restricted to their own ten-turn window** — because their retrieval cue
material is degraded: gist "the player: Uhmm my name is Hinami…", entities
`["the player"]`, key phrases full of `"She"`/`"Uhmm"`/`"And"` (§1.3). A
realistic in-fiction query ("when Hinami first told me her name") hits both
targets at ranks 1–2, so the misses need both an adversarially name-free
query AND the junk cues; but a character asking "who was that, again" about a
half-remembered stranger is exactly the name-free case.

### 3.3 "the player" — fixed at source, 49 rows of residue still degrade recall

The dialogue recognition gate used to rewrite the protagonist to the literal
string "the player" and exempt it from the gate;
`persist/commit_memory.py:505`'s comment records the fix and measured "68
rows across the live corpus" at fix time. Today **49 rows** carry "the
player" (union across columns: 49 in content, 49 in gist, 32 in key_phrases,
20 in entities; chats 30–37, 59, 63, 64 among others). The 68→49 gap is not
reconcilable from the present database — most plausibly counted over a corpus
state including since-deleted chats/branches (inference, not measurement). A
second origin was found in the same residue class: several turn-0 seed rows
carry the phrase from authored greeting text predating
`story/greetings.py`'s `_substitute_player_slot`. The engine's out-of-fiction
word for the protagonist sits inside those minds' memories — including, in
three sibling chats, inside the very memory where the character learned the
player's name — and it is also retrieval-poisonous (§3.2). The fix holds for
new rows; the stock is repairable by a bounded rewrite (content/gist/cues
re-derived with the persona name through the same recognition gate) if the
owner wants those banks clean.

### 3.4 Greeting seeds: the mint is already repaired; 105 legacy rows remain

105 rows corpus-wide sit at salience ≥0.99 — 104 at turn ≤1, uniformly
third-person knowledge seeds ("Dr. Moon knows the site is experiencing a
Euclid-class containment breach…"), above the 0.72 archive threshold forever.
**UNBUILT §1.16 is stale on its entry half**: `_seed_salience` now clamps
seed mint salience to 0.7 (`story/greetings.py:218-226`), so new seeds cannot
enter at 1.0 and — being below 0.72 — DO age into the archive. What §1.16
still correctly describes is the existing 105 legacy rows, which never age
out. (One deliberate 1.0 mint remains live: the drive-shift memory,
`persist/commit_memory.py:1232` — plausibly intentional for a life-defining
event; noted, not indicted.) Measured intrusion on a seeded bank (chat 58, 6
seeds, 182 rows): 0–1 seed rows in the top-16 across three neutral
beat-shaped queries — presently mild, and the third-person phrasing means
that when one surfaces it reads as narration, not memory. The remaining work
is a data repair over the 105, plus the §1.16 register update.

### 3.5 The summary index is empty over the opening era for most banks

Of 74 banks holding ≥20 in-play memories: **5 have no first-hand summary
window at all, 41 have a leading hole** (first window starts >5 turns after
the bank's first memory), 28 are covered from the start. The chat-38 repair
documented in MEMORY.md §8 was applied to chat 38; the corpus-wide state is
still mostly pre-repair. Anything built on windows-as-index (§4.3) inherits
this floor until `backfill_memory_summary_windows` is run per bank — which
exists, is host-exposed, and per MEMORY.md checkpoint-propagates.

### 3.6 UNBUILT §2.16 measured: window-first routing LOSES to flat retrieval on the live corpus

The proposal's strong form — rank windows, then rank raw memories inside the
winning window — was emulated exactly (window ranked by cosine against the
probe query over the bank's 16 contiguous first-hand windows; raw search then
restricted to that window's turn range via the seam's own `since_turn_idx`):

| arm | hits /12 |
|---|---:|
| flat `search_memories`, k=16 (today's behaviour) | **10** |
| window containing target ranked top-1 | 7 |
| …ranked top-1 or top-2 | 8 |
| strong form: search inside top-1 window | 6 |
| strong form: top-2 windows, k=8 each | 7 |

Errors compound multiplicatively — P(right window) × P(right row inside it)
— and the second factor is not 1 even when the first is: the intro target's
window holds only 53 rows, 17 were returned, and the target episode rows were
not among them (the FACT surfaces — the inference row "Her name is Hinami"
appears at position 11 — but the episodes themselves are shadowed by their
poisoned cue material, §3.2). So window routing cannot rescue precisely the
failures it would be built for: they are row-representation failures, not
era-finding failures. Caveat stated plainly: one bank, 12 probes — treat
these numbers as directional, alongside the literature's independent
identical result (§4.3), not as a standalone effect size. The adversarial
pass verified the in-window restriction was genuine (seam-level
`since_turn_idx`, all returned turns inside the window, MMR padding unable to
escape it) and reproduced the flat-arm probes it re-ran.

---

## 4. Improvement proposals

Ranked by expected effect on reliable character memory against cost. Each
carries its evidence. External sources were surveyed 2026-08-19; the
mechanisms below cite the specific result that justifies (or kills) them.

### 4.1 Fix the cue-material pipeline (extraction, stock repair, then the scorer) — highest expected effect, and it must carry its own measurement

The live-corpus evidence (§1.3, §3.2) says the binding constraint on recall
quality today is not the ranking arithmetic — which checked out to the digit —
but the QUALITY OF THE CUE MATERIAL the ranking runs on. In dependency order:

1. **Extraction at mint**: stopword/shape filtering in
   `_extract_entities` (close the quote-initial bypass — 9.9% of re-extracted
   rows still junk-stamp today) and stop `_extract_key_phrases` inheriting
   entity junk. Language-pack driven, like every other recognizer in the
   family.
2. **One-shot stock repair**: re-derive key_phrases/entities from content for
   rows where they came from the extractor (never over model-supplied ones),
   re-embed the cue vector for repaired rows, and rewrite the 49 "the player"
   rows through the recognition gate with the persona name (§3.3). O(bank),
   off the turn path, same discipline as `rebuild_embeddings`.
3. **Then the scorer — gated on measurement.** The naive fixes are measured
   wrong or unproven: word-boundary matching alone changes almost nothing
   (`\bthe\b` still matches), and a stopword-filtered scorer reshapes ~7/16
   of the payload while flipping 2 of 12 probes to miss. Since 71% of a real
   bank currently fires the "exact" signal, ANY fix here redefines half the
   payload; it needs a labeled probe set (grow
   `tools/benchmark_memory_temporal.py`, per §2.17's own instruction) before
   it ships. Cheap interim hardening that does not need the set: cap
   `exact_rank` at 60 like its siblings, and break score ties by something
   less arbitrary than insertion order.

This is also the literature's emphasis: LongMemEval found index-key quality
(fact-augmented key expansion, +9.4% recall / +5.4% accuracy) the single
cheapest retrieval win — and the engine's cue vector IS its key-expansion
mechanism, currently fed noise. (arXiv:2410.10813)

### 4.2 `_kw_scores` magnitude + `search_lore` model-key check — small, measured, do together

Return normalized BM25 instead of the positional decay (§1.1: fixes the
59%-of-queries membership churn on large books), and make `search_lore`'s
compatibility check match `search_memories`' model+dim rule, with a stamp
backfill for the 840 NULL `embedding_model` lore rows (§1.2). Both are
contained in `memory_common.py` / `memory_lore_entries.py`; the second is
insurance whose premium is ~5 lines.

### 4.3 UNBUILT §2.16 — verdict: refuse the router, keep the range; build the floor it actually needs

**Do not build the strong form.** Two independent lines of evidence agree:

- *Measured here* (§3.6): window-first routing scores 6–7/12 against flat
  retrieval's 10/12 on the live corpus, and the window containing the target
  only ranks first 7/12 — the compounding is real.
- *Measured in the literature*: RAPTOR's own ablation found flat "collapsed
  tree" retrieval consistently beat layer-by-layer traversal
  (arXiv:2401.18059); MemTree, whose entire contribution is a hierarchical
  memory tree, deliberately flattens it at retrieval time and searches all
  nodes as one pool (arXiv:2410.14052). Traversal pays off for token
  efficiency at corpus sizes far beyond a character bank, not for accuracy.
  The failure mode the papers name is the one §2.16's own blocker note
  predicted: a summary is a lossy proxy, and committing to a region before
  seeing leaf evidence shadows every row inside the regions not chosen.

What the evidence DOES support, in place of the router:

1. **Windows into the flat pool.** RAPTOR's actual win came from *what got
   indexed* (summary nodes capture theme-level facts no single row contains;
   57% of retrieved nodes were non-leaf on the narrative corpus), not from
   traversal. The engine already ranks windows and sends the top 2 beside raw
   recall — one step short of entering them into the same RRF fusion as
   first-class candidates and letting MMR police redundancy. That reproduces
   "the query picks its own granularity" inside machinery that already
   exists.
2. **The turn range as a temporal BOOST, not a route.** A window's
   `start/end_turn_idx` is deterministic and contractual — no dependence on
   the summary prose describing its own range, which the §2.16 blocker
   rightly distrusts. LongMemEval measured +11.3% on temporal queries for
   the analogous mechanism (time-scoped candidate boosting). The engine
   already has the seam: the `_temporal_mode` cue bonus. "When the query
   carries a temporal cue, add a scalar bonus to raw memories whose turn
   falls inside the top-ranked windows' ranges" is a ~20-line change that
   uses the index shape §2.16 wanted without the routing it feared.
3. **The missing "nothing convincing" floor is buildable, and not as a
   cosine threshold.** §2.16's second blocker — the 0.45–0.55 cosine band
   has no absolute floor — is a named problem in IR with a standard answer:
   query-performance prediction (NQC/WIG), which reads the score
   *distribution* against a per-query whole-corpus baseline instead of the
   magnitude. The engine scans every row anyway (no ANN), so the bank-wide
   mean/σ of each vector leg is free with the scan it already pays for;
   "top-k mean lift below ~1σ over the bank baseline" is a deterministic,
   per-query-calibrated emptiness signal. That floor is worth building
   regardless of §2.16 — it is also the abstention gate ("I don't remember")
   that every long-memory benchmark reports as a top failure class, and for
   a character, confabulated recall is a character break. If it ever needs
   sharper teeth, a small local cross-encoder over the fused top-16 is one
   ~130ms non-LLM batch — but start with the free one.
   (QPP: Zhou & Croft; Adaptive-k arXiv:2506.08479 measured that
   largest-gap heuristics fail exactly when scores compress, so gap-cutting
   is only good for shrinking k, never for deciding emptiness.)
4. **Run the window backfill corpus-wide first** (§3.5): 46 of 74 banks have
   no usable index over their opening era, and §2.16's own "fallback when
   the index is empty" concern is 62% of the corpus today. The tool exists.

### 4.4 Belief rows: versioning instead of overwriting — medium cost, high fiction value

`reconcile_inference_confidence` is sound (verified §7) but overwrites
`confidence` in place; a character cannot cite *when* they stopped believing
or what superseded what. The strongest cross-system pattern in the survey is
bi-temporal invalidation (Zep/Graphiti: `valid_from` / `invalidated_at` /
`superseded_by`, invalidate-never-delete), and the freshness result that
matters here is deterministic: code that picks current-vs-superseded by
stored version markers beat LLM freshness judgment by 10.8–21pp, and
graph-memory products scored 7–18% on conflict benchmarks where deterministic
aggregation hit 82–93% (arXiv:2606.01435). This engine's commit philosophy
*is* that paper's thesis; the change is three columns on inference rows and a
richer `i_now_read_this_differently` — dramatic material ("I was so sure,
then") more than bookkeeping. Note `disputed` already implements the pattern
for episodic re-readings; this extends it to belief confidence.

### 4.5 Considered and NOT recommended, with reasons

- **Per-character knowledge graphs / HippoRAG-style PPR**: the wins are on
  multi-hop association across documents; a bank of first-person rows with
  entity exact-match already in the fusion has little headroom, extraction
  costs LLM calls per turn, and Mem0's own graph variant bought ~2% over its
  base (arXiv:2504.19413). If multi-hop recall ever measures as a gap, one
  SQL hop of entity co-mention expansion is the cheap form.
- **MemGPT-style self-edited memory**: hands a model write authority the
  deterministic commit boundary exists to withhold.
- **Recency-decay-on-last-access (Generative Agents)**: collides with a
  deliberate, documented refusal — `access_count` is written and read by
  nothing because retrieval-strengthens-retrieval is a popularity loop
  (MEMORY.md §13), and this engine chose consequence-driven importance
  instead. The refusal is the better design for fiction; noted so the idea
  is on record as rejected rather than unconsidered. (Its cousin — letting
  `memory_effects`-confirmed *influence* raise importance — is already
  built.)
- **An ANN index**: nothing in this audit moves MEMORY.md §10's conclusion;
  the measured scan costs and the pre-ranking firewall filters both stand.
- **Replacing the k=16 flat recall with summaries**: LongMemEval measured
  compression *hurting* QA relative to raw-log retrieval (information loss);
  raw rows as the retrieval value is the right call and stays.

### 4.6 Small repairs worth batching with 4.1

- Coerce/validate `kind` at the upsert (§1.5), and decide what the one
  `belief` row should be (it is an inference; one UPDATE).
- Data-repair the 105 legacy salience-1.0 seed rows (the mint is already
  clamped to 0.7, §3.4) and update UNBUILT §1.16's entry half, which now
  describes a closed hole.
- Compute `_exact_cue_score` once per row (§1.6); the `exact_rank` cap moved
  into §4.1's interim hardening.
- MEMORY.md edits per §2 of this audit, including rescoping §9's startup
  claim and §1.1's blast radius; UNBUILT §1.16 as above.

---

## 5. What this audit did NOT establish

Stated so absence is not read as clearance:

- No behavioural (conduct-level) evaluation was run — §2.17 item 1's memory
  maze remains the missing instrument. Everything here measures whether the
  right rows reach the payload, not whether the character then acts on them.
- Contrast/unbidden recall, ponder, and the consolidation prompt itself were
  verified against spec but not exercised against the live corpus.
- The probe set is 12 hand-written queries against one bank plus 3 against a
  second; it is evidence, not a benchmark. `tools/benchmark_memory_temporal.py`
  is the reusable instrument and should absorb any probe that gets reused.
- Checkpoint-restore embedding rollback (§9's 637-of-642 case) was not
  re-exercised; the startup reconciler now guards it and the code paths were
  read, not run.
