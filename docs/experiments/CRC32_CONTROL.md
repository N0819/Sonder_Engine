# The crc32 floor, and what it says about the LongMemEval number

Status: EVIDENCE. Run 2026-08-19/20 against private copies of the LongMemEval
bank (`chat_id=79`, `char_id=73`, 10,960 rows, 470 positive probes and 30
ground-truth negatives; conversion and provenance in
[`tools/longmemeval_to_bank.py`](../../tools/longmemeval_to_bank.py)). Six arms,
one process each, same rows, same probe file, same `k=16`, same frozen pass
rule. `engine.db` was opened read-only and never written.

---

## 1. The result

| arm | positives hit / 470 | | what varies |
|---|---:|---:|---|
| **real embeddings** — `openrouter:3:perplexity/pplx-embed-v1-4b`, 2560d | **399** | 84.9% | production |
| crc32 **16384** | 337 | 71.7% | width only |
| **no vector channel at all** — BM25 + exact cue | **338** | **71.9%** | vectors switched off |
| crc32 **4096** | 336 | 71.5% | width only |
| crc32 **1024** | 323 | 68.7% | width only |
| **crc32 256** — the shipped fallback | **289** | **61.5%** | width only |

Read the two bold rows in the middle first, because they are the finding:

**The crc32 fallback does not score a floor. It scores 49 probes BELOW the
floor.** Turning the vector channel off entirely — leaving BM25 over
`memory_retrieval_fts` and the exact-cue ranking to run alone — hits 338 of
470. Putting the shipped hash vector back in hits 289. The hash is not a weak
retriever whose contribution is small; on this bank it is a *negative*
contributor that displaces good keyword candidates out of the payload through
RRF fusion, where the two vector rankings carry 2.15 of the 4.5 total ranking
weight (`mind/memory_retrieval.py:500-503`).

So the honest arithmetic for interpreting the benchmark is:

- **Lexical floor** (no retrieval intelligence whatsoever, just word overlap
  through BM25 and exact phrase match): **338 / 470 = 71.9%**.
- **Production**: 399 / 470 = 84.9%.
- **What embeddings actually buy: +61 probes, +13.0 points.** Paired: 330 hit
  in both arms, 69 only with real embeddings, 8 only without, 63 in neither.
- **What the fallback costs when it fires: −49 probes, −10.4 points**, i.e. an
  install whose embeddings provider is down retrieves *worse than one with no
  vector ranking at all*. Paired against the no-vector arm: 268 both, 70
  only-no-vector, 21 only-crc32, 111 neither.

The number to quote beside "LongMemEval 399/470" is **338**, not 289. 289 is
what a specific broken configuration scores; 338 is what the questions give
away for free.

### The gap by question type

Where retrieval earns its keep, and where it does not. `n` is the count of
positive probes of that type; each cell is hits.

| question_type | n | no vector | crc32 256 | crc32 1024 | crc32 4096 | crc32 16384 | **real** | real − no-vector |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| temporal-reasoning | 127 | 83 | 69 | 81 | 83 | 84 | **98** | +15 |
| multi-session | 121 | 79 | 69 | 77 | 84 | 84 | **104** | **+25** |
| knowledge-update | 72 | 61 | 58 | 62 | 62 | 62 | **68** | +7 |
| single-session-user | 64 | 56 | 43 | 48 | 51 | 52 | **58** | +2 |
| single-session-assistant | 56 | 52 | 45 | 49 | 51 | 50 | **56** | +4 |
| single-session-preference | 30 | 7 | 5 | 6 | 5 | 5 | **15** | +8 |
| **all** | 470 | 338 | 289 | 323 | 336 | 337 | **399** | **+61** |

Two things fall out, and they point in opposite directions.

**Single-session questions are nearly free.** `single-session-assistant` is
52/56 on word overlap alone and 56/56 with embeddings; `single-session-user` is
56/64 against 58/64. A question about one session shares that session's
vocabulary, so it is a lexical question wearing a retrieval question's clothes.
Those 120 probes are 26% of the benchmark and contribute 6 of the 61 probes
embeddings buy.

**`multi-session` and `single-session-preference` are where the model works.**
Multi-session: +25 probes, the largest single contribution. Preference: 7/30
lexical against 15/30 semantic — the only class where the floor is *low*, and
also the class where production is worst in absolute terms. A stated preference
("I prefer aisle seats") and the question that asks after it ("where do I like
to sit?") share almost no words, which is exactly the case the hash cannot
reach and the model half-reaches.

That last row is the one worth carrying forward: **half of the preference
questions are unanswerable by this retrieval stack**, and it is the question
class closest to what a character actually needs to recall about a person.

### Rank quality, not just membership

Mean best-target rank among each arm's own hits, and how many hits arrived only
as chronological-neighbour padding:

| arm | hits | mean best rank | neighbour-only |
|---|---:|---:|---:|
| no vector | 338 | 4.01 | 8 |
| crc32 256 | 289 | 4.28 | 12 |
| crc32 1024 | 323 | 3.74 | 10 |
| crc32 4096 | 336 | 3.66 | 10 |
| crc32 16384 | 337 | 3.61 | 9 |
| real 2560 | 399 | 3.65 | **2** |

Restricted to the 285 probes both the real and crc32-256 arms hit, real ranks
its target at mean 2.61 against crc32's 4.25. Where the hash finds the row at
all it finds it later, and it leans four times as hard on the padding.

### The four probes crc32 hits and production misses

There are four, 0.9% of the set, and they are not a defect in the ranking
stack. All four are *aggregation* questions — "how many days between", "how
many weeks in total", "how much did I spend" — whose targets are ordinary
sessions the query does not paraphrase, and whose only distinctive content is a
proper noun (`'The Nightingale'`, `'Sapiens'`) or a possessive (`my sister`,
`best friend`) present verbatim in the row. Lexical overlap catches that
directly; a whole-document vector dilutes it among 1,700 other characters of
text.

They are also near misses rather than blind spots. Re-running those four
queries at `k=100` in the real arm puts the best target at rank **12, 22,
23 and 38** — outside the payload, but in the neighbourhood:

| probe | crc32 rank | real rank at k=100 |
|---|---|---|
| `a3045048` | 6 | 23 |
| `gpt4_a1b77f9c` | 3 | 22 |
| `gpt4_4ef30696` | 3 | 12 |
| `ef9cf60a` | 13 | 38 (other target 47) |

I looked for a near-duplicate-distractor explanation and only half found one:
two of the four targets have a row at real cosine ≥ 0.9 elsewhere in the bank
(5 and 1 respectively), the other two have none, and bank-wide only 2.7% of
rows have any twin that close. So the four are a rank shuffle at the cut line
on questions whose evidence is lexically marked, not a class of question the
model cannot see. **I am not concluding that lexical retrieval wins anything
here**; four probes at the boundary is a difference this instrument cannot
resolve from noise, and it is reported because the brief asked to look, not
because it survives scrutiny.

---

## 2. What had to change in the instrument, and what did not

`memory_probe_harness.py` refused to score when the query embedding came back
`fallback`, and the refusal was right: a lexical hash vector measures a
different retrieval than the one players get, silently. But a null control
needs a retriever with no semantic capability, so the refusal blocked the one
experiment that could interpret the benchmark's number.

The fix is the distinction the engine had already reached elsewhere on the same
day. `rebuild_embeddings` writes a hash vector only when the hash is what this
install embeds onto — `want_fallback = target_key == "cheap:crc32:256"`
(`mind/memory_vectors.py:215`) — and `b467762` applied the same discriminator to
the import path: "a fallback is a failure only when the hash is not what this
install embeds onto." **Undeclared substitution is the defect; a declared mode
is not.** That is the whole of `docs/UNBUILT.md` §1.75.

So `--allow-fallback-queries` turns the refusal into a declared arm rather than
removing it:

- the default is unchanged and still aborts (verified: without the flag the run
  exits with the refusal, message unchanged apart from naming the flag);
- the pass rule is untouched and no frozen probe file was edited; the probe
  file I ran is byte-identical to the committed
  `tools/memory_probes/longmemeval_merged.json`, verified by comparison;
- every result the flag produces is stamped — the report carries
  `allow_fallback_queries`, each bank carries `query_model` and a
  `fallback_queries` count, and the run prints a banner — so a stored report
  can never be mistaken for a production number later;
- the query cache now stores the `fallback` flag with the vector. It did not,
  and rebuilt every cached entry as `fallback=False`. That was true of every
  entry the old code could write, since a fallback aborted before caching, and
  stops being true the moment a declared arm caches one. Without the fix, a
  *second* run of a crc32 arm would have handed `recall_confidence` a hash
  vector labelled real. Verified: cold and warm cache produce identical
  verdicts and identical `recall_confidence.available` on the same probes.

The width sweep is [`tools/cheap_embed_width_sweep.py`](../../tools/cheap_embed_width_sweep.py),
which substitutes the embedder and nothing else. `--verify` asserts its sketch
is byte-identical to `providers.cheap_embed` at 256 before it measures
anything; measured, `max |sketch(t,256) − cheap_embed(t)| = 0` over 400 real
documents.

### Method, so the arms are comparable

Both arms ran in one process each on my own copies of the bank, made with the
SQLite backup API from a read-only connection. The crc32 arm's rows were built
through the **production** path: blanking the `embeddings` role in the copy's
`agent_models` makes `embedding_model_key()` return `cheap:crc32:256`
(`llm/providers.py:2872-2877`), which is exactly the `want_fallback` condition
`rebuild_embeddings` reads, and it rebuilt all 10,960 rows onto the hash in 221
s with nothing monkeypatched. The real arm re-used the 500 cached query vectors
from the owner's concurrent run — merged into my own cache file rather than
written back to theirs, so a concurrent save could not drop their entries — and
made zero provider calls.

The one confound I could not remove: in the no-vector arm, MMR redundancy falls
back to Jaccard rather than cosine (`_memory_similarity`), because no row has a
comparable vector. That affects diversification within the selected set, not
which rows are candidates.

---

## 3. Is 256 the defect? Partly — and the honest answer is smaller than it looks

The hypothesis was that `cheap_embed`'s 0% paraphrase recall is a
dimensionality defect: a 1,200-character memory yields ~2,400 n-grams competing
for 256 signed buckets. **Nothing in the codebase argues for 256** — verified by
search; `cheap_embed` (`llm/providers.py:2862`) carries no comment at all, and
`_embed_with_retry` (`llm/providers.py:3254`) hard-codes the stamp and the
dimension a second and third time, so the width is not reachable even by
changing the default.

The saturation is real and severe. Measured over 1,200 real memory documents
from the bank (median 1,156 chars, median 2,308 n-grams, median 1,194
*distinct* n-grams):

| width | occupied buckets (median) | occupancy | distinct n-grams colliding | ‖v‖ retained |
|---:|---:|---:|---:|---:|
| 256 | 253 | **98.8%** | **76.6%** | 101.5% |
| 1024 | 689 | 67.3% | 43.5% | 100.0% |
| 4096 | 1024 | 25.0% | 15.8% | 99.7% |
| 16384 | 1150 | 7.0% | 4.2% | 100.4% |
| 65536 | 1188 | 1.8% | 0.9% | 100.1% |

The last column is the tell. A *signed* hash preserves the vector's norm in
expectation whatever the width — that is the property the trick is chosen for
(Weinberger et al. 2009, cited in [`../../Design.md`](../../Design.md)) — so
collisions never show up as a shrinking vector. They show up as rotation: the
magnitude is intact and points somewhere else. Anything watching for a
degenerate vector would see nothing wrong at 76.6% collision, which is part of
why 256 survived.

Cue texts (median 440 chars) are milder and still bad: 89.5% occupancy and
60.1% collision at 256. And the sketch's own geometry is visibly distorted —
correlating each width's pairwise cosines against the same sketch at 2²⁰
buckets over 400 document pairs gives Pearson **0.858** at 256, 0.959 at 1024,
0.988 at 4096, 0.998 at 16384. At the shipped width, three quarters of the
distinct n-grams in a memory have lost their own bucket.

So the mechanism was there. **The retrieval result says fixing it recovers the
damage and buys nothing beyond it.** 289 → 323 → 336 → 337 across 256 → 1024 →
4096 → 16384, and 337 is the no-vector arm's 338 to within one probe. The curve
does not saturate at some higher value the sketch was being denied; it
saturates *exactly at zero contribution*. Widening removes a self-inflicted
wound; it does not turn a character-n-gram sketch into a retriever.

That reading is confirmed independently of the probes. Over all 7,998,000
distinct pairs among 4,000 bank rows, the crc32 cosine and the real-embedding
cosine are uncorrelated: **Pearson r = 0.028, Spearman −0.027**. There is no
width at which a signal that is not there becomes visible.

**Recommendation, and it is a recommendation, not a change** — the width is a
stamped model key and that decision is the owner's. If the fallback is kept at
all, move it to **4096**: it costs nothing (the sketch is local NumPy; rebuilding
10,960 rows took 26–46 s at every width, against 221 s through the provider
path), the migration is already built and free because the stamp becomes
`cheap:crc32:4096` and every existing hash row correctly reads as stale, and it
converts a mode that *subtracts* 49 probes into one that is merely inert. The
better option is the one the arms actually argue for: when the embeddings role
cannot be resolved, **write no vector and no stamp rather than a hash**, and let
`sem_rank`/`cue_rank` come back empty — which the code already handles, since
`mind/memory_retrieval.py:453` drops non-positive scores from the rank lists.
That is 338 instead of 289, with no migration at all. I did not build it;
`embedding_bank_status`, `_warn_stranded_embeddings` and the repair queue all
key on the crc32 stamp existing (`mind/memory_write.py:443,566`), so removing it
is a wider change than it looks and belongs to whoever owns that lane.

---

## 4. The 30 negatives, arm by arm

`docs/UNBUILT.md` §1.76 already records the substantive finding from this bank
and does it properly, with a distractor-mass sweep showing that the same
question at the same answer nearly doubles its lift as the bank grows and that
positives and negatives drift together, one sigma apart, at every scale. My
run reproduces its headline independently — **0 true abstentions on 30
negatives** — and adds two things it does not cover: how much abstention would
cost if bought, and what the signal does in a declared crc32 arm.

| arm | negatives available | abstained | positives available | abstained |
|---|---:|---:|---:|---:|
| real 2560 | 30/30 | **0** | 470/470 | **0** |
| every crc32 arm | 0/30 | 0 | 0/470 | 0 |
| no vector | 0/30 | 0 | 0/470 | 0 |

In the real arm `lift_sigma` averages **6.21 on the negatives against 6.36 on
the positives**, an AUC of **0.528** — chance, stated as one number. The lowest
positive is 3.55 and the highest negative 9.01: the distributions are not
separated, they are superimposed.

**And buying teeth is ruinous at every price.** Sweeping the threshold on this
run's own numbers:

| abstains on … negatives | threshold | positives also silenced | of those, ones the payload had ANSWERED |
|---:|---:|---:|---:|
| 1 of 30 | 4.25 | 7 | 2 |
| 5 of 30 | 5.31 | 96 | 59 |
| 10 of 30 | 5.59 | 142 | 102 |
| 15 of 30 | 5.85 | 185 | 137 |

Half the negatives costs a third of the corpus, most of it recall that worked.
There is no operating point, which is the same conclusion §1.76 reaches from
the scale side.

**In the crc32 arms `recall_confidence` reports nothing, and that is correct
rather than meaningless.** `mind/memory_retrieval.py:743-745` returns
`available: False` on a fallback query vector — "a hash vector's geometry says
nothing about the bank; no signal". The production seam already made the
distinction the harness was missing, and my declared arm inherits it: the
control cannot measure abstention, and it says so rather than reporting a
number. The one curiosity in the other direction is that the raw top-1 fused
score separates negatives slightly better in the *lexical* arms (AUC 0.622 at
crc32-256 and 0.687 at 16384, against 0.600 real and 0.508 no-vector). I am not
proposing anything from that: it is one bank, the scales are not comparable
across arms, and the arm with the best separation is the arm that retrieves
worst.

The narrow claim: **on independent ground-truth negatives, the abstention floor
does not work, and no threshold on this statistic makes it work.** Sharper teeth
need row-level evidence — the audit's cross-encoder note — which is what §5 of
MEMORY_IMPROVEMENTS.md already concluded from much weaker evidence.

---

## 5. The 768 live crc32 vector pairs

Verified read-only against `engine.db`, 2026-08-20. `memory_vectors` holds
5,047 rows: 4,268 on `openrouter:3:perplexity/pplx-embed-v1-4b`, 11 on
`…pplx-embed-v1-0.6b`, and **768 on `cheap:crc32:256`**, all at dim 256, written
**740 on 2026-08-01, 1 on 08-11, 27 on 08-12** (local time) and none since. The
claim as given is exactly right.

**The live tables are clean of the hash.** None of the 9,608 `memories` rows or
422 `memory_summaries` rows carries `cheap:crc32:256`; the crc32 vectors exist
only in checkpoint history. (They do not all carry the *same* real key — see
the note at the end of this section.)

**Reach.** 844 of 2,331 checkpoints, across **26 chats**, reference them — 511
checkpoints (18 chats) via memory entries and 823 (19 chats) via summary
entries. That is **24,486 saved memory entries** and 1,994 summary entries,
every one of them in compacted `vkey` form, resolving to 753 distinct
addresses; the remaining 15 crc32 rows are referenced by nothing. Those 24,486
entries collapse to **741 distinct (char_id, document) memories**, which is the
number that matters — the same vector is stored once and pointed at from dozens
of turns, exactly as `compact_checkpoints` intends.

**What a rollback does.** `restore_checkpoint` → `_restore_checkpoint_body`
(`persist/checkpoints.py:355, 675`) resolves each entry's `vkey` through the
vector store, and `mind/memory_snapshot.py:283-290` takes the model key from
*the entry*, falling back to the stored one only when the entry carries none —
and every one of these entries carries `cheap:crc32:256`, so it restores as
crc32/256.
`apply_chat_memory_restore` then deletes the chat's live memories and reinserts
every saved one with its stored stamp, writing the hash over whatever real
vector was there. `persist/checkpoints.py:812-813` calls `start_rebuild_if_needed`
immediately afterwards inside a bare `try/except`, and with a real provider
configured that spawns the background rebuild, which re-embeds the damaged rows
and stamps them back. **So the live bank self-heals within a minute — and the
checkpoint blob is never touched, so every subsequent rollback to that turn
re-inflicts the damage and re-pays the re-embedding bill.** The worst cases are
chats 12 and 22, whose latest crc-carrying checkpoint is 100% crc32 entries
(280 and 340); most other affected chats are under 11% on their latest.

**`rebuild_checkpoint_embeddings` is safe to run and is the wrong tool here.**
Safe: `dry_run` defaults true, it re-embeds nothing, it skips entries already on
the live key, it leaves an unmatched entry exactly as it was rather than
blanking it, and it re-parses a blob to prove the same row count and key set
before rewriting. Wrong tool: it substitutes a vector *already earned by a live
row*, joined on `_memory_vector_key = (char_id, sha1(_memory_document))`.
Measured against the whole live corpus in the most generous configuration, **44
of 24,486 crc32 memory entries match** — 13 distinct documents, all in chats
69–74. The other 24,442 belong to characters that no longer exist live: chat
38's crc entries are all `char_id 37` and live chat 38 has no rows for 37 at
all; chat 12 has no live memories whatsoever. There is no earned vector to
substitute, and no better join fixes that.

One hazard worth knowing before running it broadly: repairing an entry writes
the vectors back **inline and does not pop `vkey`**, i.e. it un-compacts. At 44
entries that is ~1.2 MB and harmless. At a high match rate it would be ~660 MB,
which would silently undo the compaction that
[`MEMORY.md`](../guides/MEMORY.md) §9 exists to describe.

**What would actually repair the rest does not exist**, and I am not proposing
building it without a reason to: the text of all 741 distinct documents is
present in the checkpoint blobs, so a pass could re-embed them, write the
results into `memory_vectors` under fresh addresses and repoint the entries —
about 1,482 embedding calls, one time. That is precisely the re-embedding
`rebuild_checkpoint_embeddings` deliberately refuses to do, so it is a new pass
rather than a flag. Against that, the current behaviour is *self-healing on the
live side* and the affected characters are mostly gone. My recommendation is to
leave it, and to record it here rather than in `UNBUILT.md`, because the
measured consequence is "a rollback to one of 844 old checkpoints costs one
background rebuild", not "a story is broken".

### Found while verifying this, and separate from it

`engine.db`'s live `memories` are **not** all on one model key. 7,688 rows carry
`openrouter:3:perplexity/pplx-embed-v1-4b` (ids 4084–21240, chats 27–75) and
**1,920 carry `generic:7:perplexity/pplx-embed-v1-4b`** (ids 339–4083, chats
6–35) — the same model behind two provider *rows*, which
`embedding_model_key()` renders as two incomparable keys because it is
`{kind}:{id}:{model}`. The configured `embeddings` role right now is
`{"provider": 7, …}`, so as of this reading **7,688 of 9,608 live rows are
stranded** and score 0.0 on both vector rankings. This may be a deliberate
in-flight switch to a local embedder made tonight, and the repair is the
existing host-facing rebuild — `PUT /api/agent_models` deliberately starts
nothing ([`MEMORY.md`](../guides/MEMORY.md) §9). Flagging it because the arms
above put a price on the condition: on this benchmark, losing the vector
channel costs 61 of 470 probes.

---

## 6. Where a character-n-gram sketch could genuinely earn its place

One place, measured, and it is not retrieval.

Over all 7,998,000 distinct pairs among 4,000 bank rows, holding the real
2560-dim vector and the 256-dim hash for the same rows:

- as a **semantic** proxy the sketch is worthless — Pearson **0.028**, Spearman
  **−0.027** against the real cosine;
- as a **near-duplicate detector** it is essentially exact. Every one of the
  353 pairs at hash cosine ≥ 0.9 is a real near-duplicate (real cosine ≥ 0.85),
  mean real cosine **0.989**; of the 337 pairs at real cosine ≥ 0.95, the
  hash's top-337 by cosine is **99.1%** precise and 99.7% of them clear hash
  cosine 0.9.

That is the correct shape for a lexical signature: it cannot tell you what two
texts *mean*, and it can tell you with near-certainty when they are the same
text. The engine has questions of exactly that shape. `_memory_similarity`
falls back to Jaccard for MMR redundancy whenever two rows have no comparable
vectors; `contrast_memory` needs a distance that does not invert when coverage
is low; near-duplicate rows are the thing `event_key` idempotency and the
empty-view gate exist to catch. A sketch stored *beside* the real vector rather
than *instead of* it is also the only model-independent handle in the schema —
two rows from different embedding eras have nothing else to compare.

**I am deliberately not proposing any of that.** Each is a hypothesis; none was
measured end-to-end here, and BM25 over word tokens already covers the lexical
ranking job well enough that the sketch subtracts from it. The recorded answer
to "is crc32 worth anything else" is: *only as a duplicate detector, and only
if some duplicate-detection problem turns out to need one*. Today none does.

---

## 7. What I refused to conclude

- **That the four crc32-only wins mean anything.** Four of 470, all at the cut
  line, with the real arm's ranks at 12–47. Reported because looking was asked
  for; not treated as evidence of a class of question the model misses.
- **That widening `cheap_embed` is a fix.** It removes a harm and reaches
  exactly zero contribution. Calling it a fix would suggest the fallback then
  retrieves something, and it does not.
- **That the fallback's stamp should be removed.** It reads as the obvious
  conclusion from the 289-vs-338 result and it is not mine to draw:
  `embedding_bank_status`, `_warn_stranded_embeddings`, the repair queue and
  `rebuild_embeddings`' own `want_fallback` all key on that stamp existing.
- **That `recall_confidence` should be retuned.** No threshold on this
  statistic separates these negatives at any price worth paying; the failure is
  the statistic, not the number. `UNBUILT.md` §1.76 already owns that
  conclusion and reaches it from the scale side; §4 above only prices it.
- **That the 768 checkpoint vectors are a defect worth repairing.** They are a
  bounded, self-healing cost on 844 old checkpoints, and the tool that looks
  like the repair fixes 44 of 24,486.
- **That any of this generalises to the live corpus.** This bank is 10,960 rows
  of task-oriented user/assistant chat, 17× the largest real character bank
  (657), and the converter's own header says it is a weak test of everything the
  firewall touches. What it measures well is ranking. What it cannot say is
  whether a character recalls well.

---

## 8. The fix, and the third arm nobody had run

Added 2026-08-20, landing UNBUILT 2.21. Same bank, same 470 probes, same
k=16, same method as section 2 -- chat 79's 10,960 rows rebuilt onto
`cheap:crc32:256` through the production `rebuild_embeddings` path in 162 s,
with the `embeddings` and `default` roles blanked so
`embedding_model_key()` resolves to the hash for real.

| arm | what it does with the sketch | hits / 470 |
|---|---|---|
| A -- before | ranks on it AND deduplicates on it | **289** |
| C -- section 1's no-vector arm | drops it entirely; MMR falls back to Jaccard | **338** |
| **B -- shipped** | **refuses it as a RANKER, keeps it for MMR** | **346** |

**Arms A and C reproduced section 1's 289 and 338 EXACTLY**, on a bank rebuilt
three months of commits later. That is what makes arm B a comparison rather
than a coincidence, and it is the reason to re-run a control you already have
the number for.

**Arm B is the change, and it beats the arm this file recommended.** Section 1
established that switching the vector rankings off scored 338 against the
fallback's 289. What it could not separate was the one confound section 2
records: in that arm no row had a comparable vector at all, so
`_memory_similarity` fell back to Jaccard for MMR redundancy. Arm B keeps
`_vector` populated and refuses only the two query-versus-memory rankings, so
**the difference between B and C is exactly that confound and nothing else** --
one variable, eight probes, 338 -> 346.

Arm C is also the slow one, by a wide margin: it ran roughly twice arm B's
wall clock, because Jaccard re-tokenises two documents per candidate pair
while cosine reads two arrays that are already in memory. Worth noting only
because it means the sketch is not being kept at a cost.

So this is section 6's open hypothesis, measured end-to-end at last. That
section found the sketch worthless as a semantic proxy (r = 0.028) and
near-exact as a near-duplicate detector (99.1% precise against real cosine
0.95), named `_memory_similarity` as a place it might therefore earn its keep,
and then declined to propose it -- "none was measured end-to-end here". It is
now. Keeping the sketch for the question it can answer, while refusing it the
question it cannot, is worth more than either using it everywhere or throwing
it away.

**Scope, unchanged and worth repeating**, because the number is large and the
population is narrow. This is the arm where the sketch IS the configured
embedding -- an install that has never set a provider. Where a real provider is
configured and one call happened to fall back, the row and query keys already
disagreed, both scores were already 0, and the repair lane already had the
row. That path was correct before and is untouched; `tests/test_no_provider_retrieval.py`
pins it so a later simplification cannot widen the refusal into it and call it
the same fix. The `cheap:crc32:256` stamp is untouched too, for the four
readers section 7 lists.
