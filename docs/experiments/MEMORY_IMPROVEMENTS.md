# Memory retrieval improvements — what was built, and what the measurements actually say

Status: EVIDENCE. Written 2026-08-19/20, implementing the accepted proposals of
[`AUDIT_MEMORY.md`](AUDIT_MEMORY.md) (§1.3, §4.1–4.3, §4.6) with the audit's
own discipline: the probe set was frozen **before** any ranking or extraction
change, every change carries a before/after on the same instrument, and the
arms that measured worse are recorded beside the ones that shipped. All
numbers are against a copy of the owner's live database, snapshot 2026-08-19
(9,608 memories), real provider embeddings
(`openrouter:3:perplexity/pplx-embed-v1-4b`, 2560 dims). Nothing here ran
against `engine.db` itself.

The deliverable is the honesty of this file, not the size of the wins. Two of
the audit's predictions came true and are documented as such: the naive
repair flipped probes to miss almost exactly as §4.1 warned, and the
behavioural layer did not simply follow the retrieval layer.

---

## 1. The instrument (frozen first)

`tools/memory_probe_harness.py` runs labeled probes through the production
`search_memories` seam against a database copy. Pass is deterministic: any
target row id in the payload the character would receive — k=16 plus the
chronological-neighbour padding, which MEMORY.md documents as up to two rows
but which the brake actually admits up to six of (the `k + 2` check sits
inside the inner neighbour loop; a pre-existing defect present at baseline,
found by adversarial verification, recorded in UNBUILT §1.57). Per-probe
`neighbor_only` reports a hit that arrived only via padding; measured, that
count is ZERO on every probe in every state, so no verdict in this file
rests on it. Query
vectors are disk-cached so reruns compare code, never embedding jitter; a
fallback query embedding aborts the run rather than measuring the wrong
retrieval.

Two frozen probe banks, committed with their baselines in the branch's first
commit and never edited after (verifiable:
`git log 0cef5a3..HEAD -- tools/memory_probes/tuned* tools/memory_probes/heldout*`
is empty):

- **Tuned**: chat 63 / char 35 (the Doctor, 657 rows) — 26 positive paraphrase
  probes spanning turns 0–166, 8 negative probes grep-verified absent.
  Authored by the implementing agent from bank contents.
- **Held-out**: chat 44 / char 42 (Lilaeve Voss, 335 rows) — 14 positive,
  7 negative. Authored by a **separate agent** so the implementing agent never
  saw that bank's contents; only its pass/fail counts ever entered the tuning
  loop, and only at decision boundaries (never during scorer iteration).

Positive probes name one distinctive event in deliberately shifted vocabulary;
negatives name genre-plausible events verified absent (several deliberately
topically adjacent — discussed but never happened — to make the abstention
floor's job honest). 55 probes total; the audit's 12 were evidence, this is
the benchmark it asked for.

## 2. Headline table

Positive probes hitting the k=16 payload, per state. Every flip is named;
"stock" is the corpus as-is, "repaired" is after `tools/repair_memory_cues.py
--apply`.

| state | tuned /26 | held-out /14 | total /40 |
|---|---|---|---|
| baseline (branch start, stock) | 24 (miss p10_auto_doors, p24_meet_mom) | 10 (miss h01, h05, h11, h12) | 34 |
| + exact-list cap at 60 | 24 (same misses) | 12 (**+h01, +h05**) | 36 |
| + extractor fixes + tiered scorer, stock | 24 (miss p01, p10 — **+p24, −p01**) | 13 (**+h11**, miss h12 only) | **37** |
| + stock repair (the full stack) | **25** (miss p18 — **+p01, +p10, −p18**) | 12 (**−h14**; miss h12, h14) | **37** |

Read the last two rows carefully, because they are the branch's most
important honesty point. **The code changes alone are worth +3 on the
held-out bank with zero held-out regressions.** The stock repair then trades
+1 tuned (including p01, the audit §3.2 flagship first-meeting anatomy, and
p10, which no other state ever hit) for −1 held-out (h14). Equal totals. The
tuned bank says run the repair; the held-out bank says it is a wash; by this
project's own rule the held-out bank is believed, so the honest claim is:
**the repair is data hygiene with a neutral net probe effect, not a measured
retrieval win.** It removes 2,000+ stopword-grade cue items per large bank
(2,391 items across 536 of chat 63's 657 rows), which is what the exact-match
ranking runs on, and it is what p01/p10 needed — but h14's targets moved out
when their cue vectors were rebuilt from cleaner text. Both facts are true;
neither is hidden. Running it is the owner's call; nothing in the shipped
code depends on which state the corpus is in (see §5 on the abstention
threshold, which was re-calibrated to hold in both).

h12_mock_terror never hit in any state and is the honest residual of the
held-out bank.

## 3. What was built and measured better

1. **`exact_rank` capped at 60** like its sibling rankings (it was the only
   uncapped list, at the highest weight, firing on 71% of a measured bank).
   Held-out +2, tuned unchanged, no probe regressed anywhere.
2. **Extraction at mint** (audit §4.1 step 1), pack-driven: quote marks and
   speaker-label colons open utterances (closing the quote-initial bypass that
   junk-stamped "Oh"/"Uhmm"), capitalized stopwords and content-word-free
   candidates are never entities ("Dr", "No", "But She"), key phrases no
   longer inherit the entity list wholesale, quoted spans must carry a content
   word, and the quote pair itself comes from the language pack (「…」 now
   works in Japanese). Measured over all 9,608 live contents: rows
   junk-stamped on re-extraction **20.2% → 0.0%**, judged by the ONE shipped
   judge (`memory_write._junk_cue`: empty, bare stopword, whole-item
   casefolded block-list match, or no content-word token) over both
   extractors. An earlier version of this claim said 18.8% → 0.0% and was
   REFUTED by adversarial verification: it had been judged by two different
   judges, each lenient for its own side, and the loophole (the frequency
   key-phrase path carried no `_junk_cue` gate, so lowercase block-list
   words like "one" and "nothing" were still stamped on 6.0% of rows —
   items the stock repair immediately strips) was a real mint/repair drift,
   fixed at the class before this report shipped.
3. **The tiered exact scorer** (audit §4.1 step 3, gated on measurement as
   instructed): the full 1.0 tier is reserved for distinctive stored phrases
   (≥3 content-bearing tokens — quoted utterances); frequency-counter
   unigrams/bigrams that coincide with query words drop to 0.6 and never
   enter the exact RRF list (word overlap is BM25's job); entity and location
   matching gain word boundaries and keep the scalar bonus but not the list
   (a production query is the beat's whole view, which contains the cast's
   names by construction, so entity fires are near-bank-wide and their
   in-list rank degenerates to tie order).
4. **The stock repair** (`repair_memory_cues`, audit §4.1 step 2):
   subtractive — removes what `_junk_cue` condemns, refills from content only
   when subtraction emptied a non-empty list, never rewrites a clean
   model-supplied cue (stored rows do not record cue provenance, so
   junk-detection is the only discriminator that cannot destroy model
   signal). Re-embeds both vectors on `rebuild_embeddings`' rules (batched,
   fallback-refusing, idempotent). Plus two deterministic repairs: escaped
   `kind` spellings folded back (the one live `belief` row was invisible to
   belief weighting and confidence reconciliation forever — audit §1.5), and
   the pre-clamp salience-1.0 opening seeds capped to today's 0.7 mint
   ceiling so they can finally age out (§3.4).
5. **The abstention floor** (`recall_confidence`, audit §4.3 item 3) — §5
   below.
6. **§4.2 both halves**: `_kw_scores` returns normalized BM25 magnitude
   (its one production consumer, `search_lore`'s 0.65/0.35 blend, consumes
   magnitude; the audit's counterfactual measured the positional decay
   changing the top-10 lore set on 59% of queries against large books — that
   counterfactual is cited, not re-run here), and `search_lore` compatibility
   is now model key AND width, with the same NULL-stamp-at-live-width
   carve-out the rebuild machinery already holds so legacy rows stay
   reachable and the stamped world converges to the strict rule.

## 4. What was built, measured worse, and rejected

Recorded because reverting was the right outcome, and so nobody retries these
without new evidence:

- **Importance-first tie-break** in the exact list: tuned 24→23, held-out
  10→9. Importance concentrates on the same early-era seed rows whose junk
  cues fire the signal.
- **Newest-first tie-break**: tuned 24→21, held-out 10→13 — three probes each
  way, a lottery, not a rule. Insertion order stays until a tie-break wins on
  both banks; the tie mass itself is the disease and shrank with the cue
  fixes.
- **The repair without the scorer**: tuned 24→21, held-out 12→11. The audit
  predicted this trap (§4.1: a naive fix flipped 2 of 12 to miss) and it
  reproduced almost exactly: with junk removed, the surviving exact fires were
  coincidental frequency bigrams on 3–20 arbitrary rows at the full 1.25
  weight.
- **Scorer tiering without the list restriction**: tuned 22/26 — necessary
  but not sufficient.
- **A mid-sentence-recurrence rule for entity extraction** (instead of the
  block-list vocabulary): disqualifying — inference contents lead with their
  subject, so it dropped the name "Hinami" from 396 live rows.
- **QPP estimator variants** (top-1, top-4 lift, NQC, top-gap): none
  separated topically-resonant negatives from hits at zero false abstention
  on both banks; NQC looked good on one bank (6/7) and useless on the other
  (1/8) — a per-bank scale artifact, not a signal.

## 5. The abstention floor, measured the way the brief demanded

`recall_confidence` is the WIG-shape query-performance signal the audit
specified: (mean of top-16 best-vector scores − bank mean) / bank standard
deviation, free with the full scan, per-query self-calibrating, never an
absolute cosine floor. It fails OPEN (small bank, low model coverage,
degenerate distribution, fallback query vector → "no signal", never
"empty"). When it fires, `build_character_memory_context` adds
`nothing_comes_back_clearly: true` beside the recalled rows; the rows are
still delivered — suppressing them is a behaviour change nothing has
measured.

Threshold **1.7**, and the calibration story matters more than the number:
1.8 was calibrated on the repaired stock and then measured on the unrepaired
stock — where one genuine hit scored lift 1.724 and would have been flagged.
1.7 sits below every positive-probe hit measured in **both** corpus states.

| measure | unrepaired stock | repaired |
|---|---|---|
| false abstention on positive hits | **0/37** | **0/37** |
| abstention on positive misses | 0 | 0 |
| true abstention on negatives | **0/15** (hn3 sits at 1.7205, a hair above the threshold) | 1/15 (hn3, 1.657) |

**The modesty is the finding — on the unrepaired stock the floor currently
buys nothing at all**, and that is stated rather than rounded up. 13–15 of
15 negatives name events that were
*discussed* in the bank but never happened (the dragons that were bantered
about, the meal that was demanded and never eaten), and a score distribution
cannot tell topical resonance from answer presence. The floor catches only
the emptiest queries. Sharper teeth need row-level evidence — the audit's
own cross-encoder note — not a better threshold. An adversarial margin note:
the gap between the threshold and the lowest measured real hit is 0.024
lift; that thinness is a property of the signal and is stated rather than
tuned away.

### The organic ponder set (independent, arrived after the freeze)

The corpus contains exactly three character-authored deliberate-recall
(`ponder`) queries from real play — chats 72 and 74, neither the tuned nor
the held-out bank. They were evaluated as a third set, never folded into the
frozen ones:

| query (paraphrased) | old code | new code | floor (new code) |
|---|---|---|---|
| what do I know about Tamamo-no-Mae / the nine-tailed mother (c72 t41) | 2 of 6 target rows in k=4, plus junk-cue rows | **3 of 6 targets; whole payload is the right rows** (t5–6 nine-tails, t40–41 the name) | lift 1.91, no abstain — correct |
| what does the rapid bell-ringing remind me of (c72 t45) | scene rows only; no associate exists in the bank | same | **abstains (lift 1.46) — correct**: the honest answer is "nothing", and this is the floor's first validation on real play |
| signs she is pushing past tiredness tonight (c74 t58) | target hit + junk t2/t8 rows | target hit + cleaner payload (t49–58 rows) | lift 1.31, **would falsely abstain** — the evidence is diffuse across a session, which the distribution reads as weak |

Consequence, decided rather than fixed under pressure: the floor stays on the
passive view lane only. Extending it to the ponder lane — where a false "I
don't remember" answers a question the payload actually contains — needs its
own per-lane calibration. Directed name-free association (the audit's hardest
class) is where the new code showed its clearest organic improvement.

## 6. The behavioural layer — measured, and honestly a mixed picture

`tools/benchmark_memory_temporal.py` was generalized off its hardcoded story
(`--cases-file`), and nine deterministic-scored cases were authored for chat
63 at turn 166. Before = branch-start code on the pristine snapshot; after =
HEAD on the repaired copy; same instrument in both arms; real character-model
calls (`glm-5p2-fast`), 2 repeats per case.

| measure | before | after |
|---|---|---|
| answer checks passed | 12/18 | 11/18 |
| grounded-citation rate | 0.78 | 0.83 |
| historical cases with any relevant evidence delivered | 16/16 | 16/16 |
| raw-memory MRR | 0.257 | 0.135 |

The pass-rate difference is inside model noise — the same arm disagrees with
itself between its own repeats on two cases — and the instrument's own
docstring says single passes cannot separate an arm from its noise. The
deterministic sub-metric is the real signal, so it was decomposed with a
no-model-call retrieval grid over the 2×2 of code × data:

| question-relevant rows delivered (sum over 8 historical cases) | stock | repaired |
|---|---|---|
| old code | 18 | 15 |
| new code | 10 | 11 |

**A code-caused trade, named plainly:** under the production *view-shaped*
query (a ~1,000-character scene description with the question appended), the
old junk-wide exact list was accidentally acting as a question-keyword
booster — single query words firing stored single-word phrases at full tier.
The new scorer classifies those as the lexical leg's job, and the lexical
query is dominated by the view's own tokens, so marginal question-relevant
rows (previous ranks 12–15) dropped out of four cases while scene-relevant
recall took their slots. Every case still delivered *some* relevant evidence
(16/16), first_meeting stayed at rank 2, and answer quality did not move
outside noise — but anyone reading the probe table's +3 should also read
this table's −8.

Read against the answers themselves, the trade's behavioural bite in this
run was smaller than the row counts suggest: both after-arm "sake" failures
are substantively CORRECT answers ("she showed no reaction… unaffected,
confirming her non-human physiology") that the deterministic term list did
not credit and that the character sourced from the autobiographical summary
with zero raw sake rows delivered — the summary layer carried what raw
recall dropped. The term list was NOT retro-fitted to rescue the score;
adjusting an instrument after reading its output is the exact practice this
file exists to refuse. One after-arm "tea" repeat returned an unparseable
answer (model noise), which is also left as the failure it scored as.

The interpretation this project's design supports: passive recall now favours
what the *beat* resembles (its stated job), summaries carry era-level facts
past the marginal-row churn, and the designed channel for directed questions
— ponder — is where the new code measurably improved (§5). The candidate
repair, **not built** because it needs its own measurement round: carry the
newest heard utterance as its own retrieval aspect (the same fix
`search_memories`' aspects already embody for mood and goal — a short facet
cannot compete inside a long string).

**Conduct remains unverified.** Retrieval improved on recollection-shaped
queries; whether a character *acts* on what reaches the payload was measured
only through these eighteen noisy answer checks. The audit §5 gap — the
memory maze, UNBUILT §2.17 item 1 — still stands, and nothing in this file
should be read as closing it.

## 7. Adversarial verification, and what it changed

Two agents were sent to refute this file before it shipped — one attacking
the measurements, one the code — because the failure mode to fear is a
harness that agrees with the change when both came from the same author.

**Confirmed independently**: probe frozenness (git history), both baselines
(recomputed from per-probe fields AND re-run from a detached worktree at the
baseline commit), every current number, run-to-run determinism (byte-equal
payloads across double runs on both DBs), the pass rule's honesty (padding
decided zero probes anywhere), the firewall envelope of every new read path,
transaction atomicity of the repair, and zero false abstention — including
against six fresh unseen paraphrases the verifier authored (min lift 2.28,
none abstained), which the frozen calibration could not have overfit to.

**Refuted and corrected before shipping**: the junk-rate before/after had
been judged by two different judges (§3 above carries the honest number,
20.2% → 0.0% under the one shipped judge, and the mint/repair drift the
refutation exposed is fixed); the abstention payoff table overstated
true-abstention on the unrepaired state (0/15, not 1/15); a `\w`
word-boundary silently killed the entity cue for Japanese banks (fixed with
a CJK regression test); the 0.8 exact tier had been dropped from the exact
list without a stated decision (admitted back, measured as a payload no-op
on all 55 probes in both states); and the neighbour-padding brake's k+2
bound was found to be k+6 in practice — pre-existing, equal at baseline,
zero effect on any verdict, now recorded in UNBUILT §1.57 instead of being
quietly fixed under deadline (fixing it shrinks payloads and needs its own
probe run).

Findings acknowledged but deliberately not acted on: `_distinctive_phrase`
counts pack-regex tokens, stopwords included ("in the kitchen" reaches the
full tier) — the probes tuned this behaviour and a stricter content-word
count is untried; the lore blind warning fires per-search rather than
once-per-situation (pre-existing posture); and `_congruence_valence`'s
malformed-dict guard is dead code on a branch nothing reaches (pre-existing).

## 8. Not built, and why

- **The §2.16 window-first router** — refused per the brief and the audit's
  measured 6/12-vs-10/12; UNBUILT §2.16 now records the verdict.
- **§4.3 items 1–2** (windows as first-class RRF candidates; the
  deterministic turn range as a temporal boost) — the stretch was spent on
  the behavioural run and the organic ponder set instead, which changed two
  shipping decisions (the abstention threshold and the ponder-lane refusal);
  both items remain live proposals with the audit's evidence behind them.
- **The §3.3 "the player" content rewrite** (49 rows) — the cue-side damage
  those rows did is handled (their junk cues repair away, and p01/h11 — the
  audit's two miss anatomies — both hit in the shipped states), but the
  out-of-fiction phrase still sits in their `content`/`gist` prose. A
  faithful rewrite must run the recognition gate per row (persona sheet,
  hearer's known map, appearance labels) against text the gate never shaped;
  that is authoring work with firewall consequences and deserves its own
  measured change rather than a tail-end patch.
- **§4.4 belief versioning, §4.5's rejected list** — untouched, per the
  audit's own ranking and the brief's scope.
- **MEMORY.md §2 doc-drift edits** from the audit — not applied here; this
  branch deliberately changed behaviour and its own docs only.

## 9. Owner actions this branch leaves open

1. Decide on `tools/repair_memory_cues.py --apply` (server stopped, copy
   rehearsed): +1 tuned / −1 held-out on probes, unambiguous cue hygiene,
   and the kind/seed repairs ride along. §2's table is the whole argument
   both ways.
2. `backfill_lore_embedding_stamps` + an embeddings rebuild remain the path
   that moves the 840 NULL-stamp lore rows onto the strict compatibility
   rule.
3. The behavioural maze (UNBUILT §2.17 item 1) is still the missing
   instrument for the question that matters most.
