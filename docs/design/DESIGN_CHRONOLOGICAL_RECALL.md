# Chronological recall: first, last, before, after

Status: PARTLY BUILT, 2026-10-06 (branch `chrono-recall`). The question is
the owner's ("what would we need for chronological?", "a complete scan is too
expensive", "could we have RRF change itself depending on the type of question
asked?"); the evidence is a verified literature sweep (§2) and one measured
miss (§1). What was built is not §3's shape: the owner moved it the same day
("we can have alt search engines specialized for different lookups"; "With
jev we don't even need the llm to think about the question type or field"),
so the decision model reads the question and a SEARCH built for its type runs
beside the graded ponder -- rather than the question choosing lanes inside
one fusion. Built: the router, the met / heard-of / place searches, the
verified walk, just-before / just-after (`mind/memory_routes.py`); measured in
`docs/experiments/CHRONO_RECALL_2026_10_06.md`. Not built: the typed-act
search, the summary timeline, comparison questions ("was it before or after
X?"), and §5's known-names gap.

## 1. The miss

Asked "what were her very first words to me?", the Doctor of chat 74 pondered
and got turns 15, 22, 56, 57 and 63, never turn 1, and took turn 15's line as
the first (`docs/experiments/CHARACTER_LOOKUPS_2026_10_05.md` §4). Nothing was
broken: the ponder net is the 50 rows most RELEVANT to the question, fused by
RRF over semantic, cue, keyword, recency, importance and ABOUT lanes
(`mind/memory_jev.memory_net`), and Jev keeps the best five. "First" is not a
property of a memory's content but its position among all the memories that
match; no lane favours the oldest rows, and the earliest match fell outside the
fifty. A complete scan answers it and is ruled out on cost (the owner).

## 2. What others have done (verified 2026-10-06)

A five-angle sweep, a synthesis and a fact-check of its eight load-bearing
claims against their sources (four held as written, four in part and were
corrected). In short: **date questions are largely handled; order questions
anchored to a person, place or event are open in shipped systems; where exact
answers exist, code computes the order over structured fields.**

- **Code applies the order; the model says what to look for.** REMem (ICLR
  2026, https://arxiv.org/abs/2602.13530): typed lookups with time bounds,
  ordering and limits, run by the store. Test of Time, exact match, REMem /
  full context / top-10 RAG: first-last 92.0 / 81.1 / 74.6, before-after 97.4 /
  72.0 / 43.1, ordering 92.9 / 46.3 / 26.6 -- and plain BM25 scored 92.3 on
  first-last. Prog-TQA (https://aclanthology.org/2024.lrec-main.1270/):
  filter programs (FilterBefore/After/First/Last) over timestamped facts.
  TimeChara (https://arxiv.org/abs/2405.18027): narrow the model to "where on
  the timeline is this, was the character there?", compare in code: GPT-4o
  64.5% -> 82.2%.
- **Time as its own list beside similarity.** LongMemEval
  (https://arxiv.org/abs/2410.10813): a date range parsed from the question
  raised temporal recall 11.3% / 6.8% on average with GPT-4o -- and the 8B
  parser invented ranges and pruned out answers. Hindsight
  (https://arxiv.org/abs/2512.12818): a temporal list inside RRF, fired only
  when the question carries a time constraint; its docs prefer hard filters to
  weights, which "only nudge continuous scores and cannot guarantee ordering".
- **Find a row by relevance, then read its neighbours in order.** ES-Mem
  (±3 events), Chronos (±1 turn), SegTreeMem, EM-LLM. This is
  `expand`/`continue`; it cannot reach a distant first occurrence.
- **Per-person and per-place timelines.** MemForest, HingeMem: segments and
  trees per entity and per scene, kept in time order.
- **Small, ordered evidence for the reader.** LoCoMo had the evidence in the
  top 5 for 89.2% of temporal questions and still scored F1 21.3: reading,
  not retrieval, failed. Shown the right passages in source order, models
  order them at about 90% (SORT).
- **Closest to us, and sobering:** EMemBench (https://arxiv.org/abs/2601.16690),
  interactive-fiction game logs with turn order: memory layers that gain 17-35
  points on LoCoMo's temporal questions lose 7-14 here (Qwen3-32B); humans
  with the log open score 76.0, and their errors are ours -- before and after
  swapped, an adjacent segment picked, "first" read as "any time".

## 3. Proposal: the question chooses its lanes

RRF stays; WHICH lists it fuses and which get reserved places depend on the
question's type. Every memory already carries what the order needs: its turn
(all rows), where (90%), and who it saw (the `about` tag, now only bodies seen
in full).

| Type | Added to the fusion | Model calls beyond today's ponder |
|---|---|---|
| content (today) | nothing | none |
| first / last, with a person or place | that person's or place's earliest (or latest) rows, matched by tag or name, with reserved places among the fifty; the picks returned in turn order | none |
| before / after an event | ponder finds the event by relevance; code takes the rows just before or after its turn (`expand`/`continue`) | none |
| first / last, content only ("when did I first feel afraid here?") | a time list over the rows matching the question's cues, with a reserve | none |
| a qualified first ("the first time she spoke of her mother") | the person's rows in turn order; Jev yes/no on a FIXED handful from the right end, saying so if none match | one bounded request |

The type comes from a TYPED decision, never from cue words (the engine's
no-word-lists rule): in the lookup the model passes it as an argument
(`order`, `with`, `before`/`after`) at no cost; for the reply's next-beat
ponder, Jev answers one choice question (about half a second).

## 4. The rules the evidence sets

- **Routing adds, never removes.** A type adds a list or reserves places;
  no route ever filters a row out, and "unsure" is today's fusion. (LongMemEval's
  parser deleted answers by inventing ranges.)
- **Code decides the order; the model only finds the anchor.** Jev answers
  "is this the moment?", never "which came first?". Model-written comparison
  logic hurt the smaller model in TReMu (https://arxiv.org/abs/2502.01630).
- **The operator is an explicit field.** Before/after confusion was ~18% of a
  sampled 100 of REMem's errors.
- **A summary may orient, never decide eligibility.** Summary-level pruning
  reached the target event 4.3% of the time in EgoCITE's measurement of EgoRAG.
- **Two clocks.** Turn order is when the mind perceived or was told; for a row
  about something it was told, that answers "when did I first hear of it".
  Seeded pasts tie at `PRESTORY_TURN_IDX` and order by row id.
- **A plain turn-ordered list is a strong baseline**; validity intervals in the
  Zep style recovered less temporal evidence than a flat log on MemForest's
  held-out set.

## 5. Before building

- **The known-names map.** 65 of the 149 minds with memories on the owner's
  database have no entry, so no tag turns on for them (UNBUILT_CHARACTERS
  §6.17); person routes fall back to names and similarity until it is fixed.
- **Room naming.** A renamed or re-keyed room splits a place's history; check
  on real banks before trusting "the first night at the inn".
- **Measure on our own banks.** EMemBench shows gains elsewhere do not carry to
  turn-level order. A question set with known answers -- first meeting, last
  time seen, right before / after an event -- from the owner's chats, against
  plain ponder, beside the 30 content questions of 2026-09-29 for regressions.
  EMemBench's and Huet et al.'s templates (https://arxiv.org/abs/2501.13121,
  https://github.com/ahstat/episodic-memory-benchmark) fit these rows.
