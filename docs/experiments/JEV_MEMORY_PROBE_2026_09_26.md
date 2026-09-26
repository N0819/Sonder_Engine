# Jev as a memory judge: the first probe

Status: EVIDENCE, 2026-09-26: two probe beats, then a 22-beat label set and 71
questions. Instruments: `tools/jev_memory_probe.py`, `tools/jev_net_recall.py`,
`tools/jev_net_labels.py`, `tools/jev_moment_affect.py`,
`tools/jev_question_recall.py`, run against a copy of `engine.db` in the
worktree. Design context:
[`DESIGN_JEV_CHARACTER_PASS.md`](../design/DESIGN_JEV_CHARACTER_PASS.md).

## What was asked

The owner's channels (2026-09-26): "How relevant is this memory to this current
situation?", "Are there any common factors like sense or smell?", "How much does
this memory match their current mood", "How much does it contrast", "Does this
memory contain useful information for this character's current situation?", and
deliberate recall -- "ask questions and get 5 highly relevant memories that
actually attempt to answer the character's question maybe from a pool of 50".

For one captured character call the tool rebuilds that beat's retrieval inputs
from the capture (the perception view as the query; goal, mood and concerns as
aspects; the turn cutoff), takes the reciprocal-rank-fusion net through the
production `search_memories` seam in fused order (the diversity pass replaced
for the process only), and asks Jev one `noul` per channel per memory, the
memory's own text quoted in the question and the character's own view, mood,
goal, concerns, drive and values in the shared state.

Beats: The Doctor (char 58), two branches of the same story, 122 visible
memories each -- chat 157 turn 4482 ("Are we going to explode?", the TARDIS
roaring in flight) and chat 154 turn 4433 ("Where are we?", the doors shut by
something unseen).

The labeled banks (`SYNTHETIC_BANK.md`, LongMemEval) could not be used: both
were built into scratch databases in August and no database on disk holds
them any more (checked: 14 files); the probe files keep only the answer keys.

## Speed and cost

- 610 questions (5 channels x 122 memories): **0.46-0.57 s**, 0 unanswered.
- Deliberate recall, 50 memories: 0.29-0.38 s.
- State 4.5-5.0 KB per request; one request per character.

## What the channels do

| channel | beat 4482: median / >=0.5 | beat 4433: median / >=0.5 | reading |
|---|---|---|---|
| situation | 0.73 / 100 of 122 | 0.61 / 89 of 122 | top picks right; over-grants, so ranking only |
| senses | 0.43 / 44 | 0.43 / 51 | engine roar -> the rotor memories (0.89, 0.87) |
| mood_match | 0.36 / 20 | 0.29 / 17 | selective; delight -> the grinning lever, the "smug cat" line |
| mood_contrast | 0.36 / 14 | 0.54 / 80 | sharp on 4482 (the crash against delight), over-broad on 4433 |
| useful | 0.54 / 76 | 0.38 / 41 | reassurance goal -> his readings of Hinami's alarm |

## Against today's packet (beat 4482)

Today's packet held 8 memories at net ranks 1, 3, 4, 5, 7, 9, 16, 55; **2 of 8**
are among Jev's top 15 situation + top 15 useful. Today's leaned on earlier
conversation topics (distances, a visit four years ago); Jev's on the crash,
the rotor, the lever and Hinami's alarm -- what the question turns on.

## Depth in the net

Some of Jev's strongest picks sit deep in the fused ranking: "The TARDIS
flinched..." (the crash's cause) at **42** with no search lane matching it
(bonuses alone), "can your ship take us to Kyoto?" (their destination) at 91,
the Kansai shrine at 49. Others at 82-116 are over-grants (the beach
introductions at 0.82-0.86). The query is the perception text, which spoke of
the rotor's noise and not the crash on the character's mind; before trusting a
100-200 net on large banks, a lane keyed to the character's current concerns
or decision is the thing to add.

## Deliberate recall

| question | Jev top 5 | net top 5 |
|---|---|---|
| What went wrong with the TARDIS? | 4 on point (the scar, the flinch, "she's got a cough" from net #30, how she travels) | 3 on point, one off-topic at #5 |
| What do I know about Hinami? | substantive facts (her mother's nickname and shrine, "at least half human"); one near-duplicate | identity line "fox spirit" (#1, which Jev missed), two off-topic |
| How did I meet Hinami? | **all 5 from the meeting on the beach** | mostly off-topic ("Where is this ship of yours?") |
| Where is the TARDIS right now? | **wrong**: where it WAS (the crash onto the beach) | off too |

Jev judges whether a memory is about the question, not whether it is still
true -- the "is this already true?" weakness recorded for the Director, and the
same shape as retrieval's superseded-belief problem (current row first 8/18).
A "now" question needs code to prefer the newest of the relevant rows.

## Refinement round (same day)

**Graded questions beat yes/no.** Each channel asked as "how much ...?" on a
four-step scale (not at all / slightly / clearly / strongly), read as the
expected grade of the distribution Jev returns (`probabilities`, e.g.
`{"central": 0.51, "clear": 0.48, "slight": 0.01, "none": 0}`). On beat 4482
every channel spreads (p10 roughly halves: situation 0.45 -> 0.24, useful 0.32
-> 0.16) while the top picks stay (top-8 overlap 5-7 of 8); `useful` goes from
76 to 26 of 122 above 0.5. The counterfactual form "Would remembering this
change what you do or say next?" compressed everything to 0.42-0.58 and
drifted off topic -- not usable.

**A "what just happened" lane does not reach the inferential misses.** The
beat's own events as a separate aspect lane moved "The TARDIS flinched" from
net rank 42 to 49; the six picks below rank 50 stayed below it. "Are we going
to explode?" and the ship's damage share no surface; the link is inference.

**Backstory memories carry prose where names belong.** The two crash memories
come from the generated journey history, with `entities` "Just me and the
TARDIS" / "Me and the TARDIS, alone together" and `location` "The TARDIS console
room, caught in a vortex scar"; memories from play carry `["Hinami"]` and
"TARDIS Console Room". An entity lane could not match them, and the existing
exact-location "happened here" bonus already misses them. The fix belongs at
ingest.

**Breadth, graded (three more beats; a fourth, chat 120, was a sexual scene
and is excluded).** 100-610 questions in 0.29-0.85 s; deliberate recall
0.21-0.46 s. On The Doctor's "Where are we?" (154) the scar and the flinch lead
at 0.99 (net 18 and 31) and "What have I promised to do?" finds his promise to
take Hinami to Kyoto. On Sarah Moon's turn 1 (115, 20 memories) "What do I know
about Hinami?" scores at most 0.22 -- she has not met her yet, an abstention the
old score signal never gave (0 of 30); not yet calibrated, since a Doctor beat
with no promise to find still peaked at 0.70. Overlap with today's packet: 3 of
21 (154), 1 of 6 (122), 5 of 8 (115). Score levels vary by scene, so a packer
should work from ranks and per-channel quotas, never fixed thresholds.

## The net, measured on a big bank

The owner: "I feel that our RRF MMR Lexical hybrid system might not be as good
as it can be if we are shifting its role from primary recall to... recall net
with filtering by jev." Instrument: `tools/jev_net_recall.py`. The Doctor,
chat 63 turn idx 166 (evening at the shrine after Hinami has gone to rest),
649 visible memories.

Jev graded the WHOLE bank on `situation` and `useful` (graded form): **1,298
questions in 1.06 s**. Its top 30 by the larger grade are the reference -- what
the judge keeps. Share of the reference inside each net's first N:

| net | @50 | @100 | @150 | @200 | @300 |
|---|---|---|---|---|---|
| today's fused RRF ranking (no diversity pass) | 23% | 40% | 70% | 87% | 97% |
| union: round-robin over meaning, cue, keyword, recency, importance, goal/mood/unsettled aspects | 37% | 47% | 67% | 87% | 100% |

- A 100-200 net keeps 40-87% of what Jev would; near-complete needs ~300 here.
- The union helps most at small sizes. Every generator reached some pick first
  (meaning 8, recency 6, mood 6, unsettled 6, cue 3, goal 1). The fused ranking
  has no recency lane, so the character's own recent acts sat at 107-135, and
  its impressions of Hinami at 148, 184 and 465; recency and cue reach them in
  their first 6 and 43-77.
- Jev's picks include many near-duplicate scene descriptions (the shrine
  clearing, the hall): a packer's diversity pass is essential after the judge,
  where it belongs, rather than in the net.
- **Jev grading the whole bank took a second.** Up to around a thousand rows
  the simplest net is none: the judge reads everything. A net matters above
  that, and there the union of generators is the better shape. *(Corrected
  below, "What Jev costs": a second is right, but at $8 per million questions
  the whole bank on five channels costs about as much as the character call
  itself, so the net earns its place on cost well below a thousand rows.)*

The reference is Jev's own judgement, so this measures whether a net keeps
what the judge would keep, not whether the judge is right.

## The net, tuned to Jev: 22 beats

The owner: "Basically my goal is to contain everything jev would pick within a
net of a hundred", then "lets see how close we can get and then see how much
we have to increase it by for the whole thing." Instrument:
`tools/jev_net_labels.py` -- `label` caches Jev's grades of every row and every
generator's ranking, so each net below is scored offline; `channels`, `fit`
and `feedback` work from that cache. The Doctor, chat 63, 22 beats one every
four turns (idx 82-166), banks 308-649. Reference: each beat's top 30 by the
larger of the `situation` and `useful` grades.

**Jev's top 30 is a plateau, but a stable one.** Rank 1 grades 0.96-0.99,
rank 30 0.90-0.96, rank 60 0.84-0.93; 36-53 rows sit within 0.02 of the
rank-30 grade. Re-graded (three beats): the same wording keeps 93-97% of the
top 30 (Spearman 0.99-1.00); a paraphrase of both channels keeps 70-87% -- but
**every** row of the original top 30 is inside the paraphrase's own top 100.
So "everything Jev would pick" is well defined at 100, and the tail of any one
top 30 is partly its wording.

| net (topical top 30) | @50 | @100 | @150 | @200 | top 10 @100 | all 30 inside, median / p90 |
|---|---|---|---|---|---|---|
| today's fused RRF | 31% | 55% | 72% | 82% | 62% | 379 / 465 |
| union: round-robin over generators | 39% | 58% | 70% | 81% | 66% | 338 / 394 |
| fused + recency + primed, round-robin | 59% | 76% | 82% | 89% | 87% | 379 / 533 |
| every lane, equal weights | 58% | 77% | 88% | 92% | 88% | 299 / 388 |
| **fitted weights, leave one beat out** | **65%** | **81%** | **89%** | **92%** | **89%** | 344 / 420 |

(The fitted row predates the affect lanes of the next section; with them
available, `fit --target "topical top 30"` gives 65 / 81 / 88 / 92%, all 30
inside at a median 310.)

- **Lanes that did not exist:** `primed` (the previous beat's picks), `primed_nb`
  (every row by its nearest cosine to one of them), `here` (rows at the
  location of the latest memory), and `recency`. Consecutive beats four turns
  apart share 44% of their top 30 (17-63%); the primed lanes are how the net
  remembers what the mind was just holding.
- **Fitted** (coordinate ascent on weighted RRF, k from a grid, scored
  leave-one-beat-out): `what is still unsettled` 3.0-5.0, `primed_nb` 3.0-5.0,
  `primed` 1.5, `recency` 1.0, `what you are trying to do` 1.0, `semantic`
  0.25-1.0, k 5-30. Today's fused ranking, `cue`, `keyword` and the mood
  aspect earned **0**.
- **Realistic primed** -- the previous beat's packet as Jev would have chosen it
  from the previous NET, not from the whole bank: 77% at 100.
- **A Jev feedback round adds nothing.** Grading the net's first 30-60 and
  refilling to 100 with neighbours of the best: 80-82% at 100 for every split,
  against 81% without it. `primed_nb` already does this with the previous
  beat's picks, at no latency.
- **The misses** (150 over 21 beats, best round-robin net): 74 from the top
  30's last third, 27 from its first; 107 inside some lane's top 60; only 3
  have a near-duplicate (cosine >= 0.90) in the net. At cosine >= 0.90 a pair
  is one belief reworded; at 0.85-0.90, one place at another moment.

## Every channel, and a tag written once

The packet draws on five channels, not two. `channels` graded `senses`,
`mood_match` and `mood_contrast` over the same 22 banks (about 32,000
questions). Share of each channel's top 10 inside a net of 100:

| net | topical 30 | senses | mood match | mood contrast | packet |
|---|---|---|---|---|---|
| today's fused | 55% | 84% | 60% | **15%** | 53% |
| fitted to topical | 81% | 88% | 63% | **18%** | 67% |

**Mood contrast was invisible to every lane**, the valence lanes included.
Jev reads "the moment felt the opposite of how you feel" from what the moment
CONTAINED: for a warm, curious Doctor (valence 0.8) its picks are a
companion's fear of being erased, her distress at being stared at, a
crawlspace. The row's own `emotional_context` and `encoding_valence` hold the
character's own feeling at encoding ("protective encouragement"); the picks'
encoding valence (median 0.38) is indistinguishable from the bank's (0.42).

`tools/jev_moment_affect.py` tried two lanes. At read time, the affect
lexicon's labels of the opposite valence sign, embedded and ranked by meaning,
reached 35% alone. At **write time**, Jev tagged each of the 657 rows ONCE with
how its moment felt (a five-way choice, the state holding nothing but the
character's name; one batch), and the lanes became arithmetic against the
surface valence. That tag is situation-free, so it can be written at commit;
that it recovers situation-dependent picks says the contrast judgement rests
mostly on the memory's own feeling. Each lane alone, inside 100:

| lane alone | mood contrast | sore | irony | callback | tease | mood match |
|---|---|---|---|---|---|---|
| best of the old lanes | 24% | 32% | 34% | 38% | 55% | 61% |
| read time: opposite labels by meaning | 35% | 58% | 9% | 33% | 5% | 32% |
| **write time: moment tag, contrast** | **85%** | **95%** | 54% | 0% | 1% | 7% |
| **write time: moment tag, match** | 4% | 5% | 9% | **86%** | **75%** | 42% |

Refitted with those lanes, leave one beat out, against the packet (topical 12
plus the top 6 of senses, mood match and mood contrast):

| net | @50 | @100 | @150 | @200 | all inside, median |
|---|---|---|---|---|---|
| today's fused | -- | 53% | -- | -- | 404 |
| **fitted to the packet** | **55%** | **79%** | **86%** | **90%** | 272 |
| same, realistic primed | 54% | 77% | 82% | 87% | 352 |

Fitted weights: `moment_contrast` 5.0, `cue` 3.0, `primed` 3.0, `recency` 2.0,
`moment_match` 2.0, `semantic` 1.5, goal, mood and `here` 1.0, k 15; fused and
keyword 0. Per channel at 100: topical 72%, senses 84%, mood match 68%, mood
contrast **72%** (from 15%).

## The owner's "fun" channels

The owner: "fun categories for memories that character model can receive like.
'These memories may be ironic to bring up' 'Good teasing material.'" Four
graded channels (`SOCIAL_CHANNELS` in the probe), over the 22 banks: `irony`,
`tease`, `callback` (a line or moment shared with someone here, fun to bring
back) and `sore` (would touch a sore spot for someone here) -- the tact
channel the fun ones need beside them. 2,500 questions a beat, 2.7-4.3 s.

| channel | rank 1 / 5 / 20 grade (median) | rows >= 0.5 | reading |
|---|---|---|---|
| callback | 0.80 / 0.75 / 0.68 | 124 | **right**: "You just -- you POKED me", "'Doctor Who' is the question, not the answer -- bit of a running joke", "Captain can wait. TARDIS has better views." |
| sore | 0.83 / 0.64 / 0.47 | 15 | **right and selective**: her fear of being erased, her distress at being looked at, the merge unsettling her sense of self |
| irony | 0.83 / 0.71 / 0.61 | 77 | mixed: "The Doctor is running from something" during a quiet shared meal, but also plain contrasts |
| tease | 0.88 / 0.84 / 0.78 | 254 | flat: descriptions of her ears and tails; needs a question about what they SAID or DID |

Inside the fitted packet+fun net of 100: sore **94%**, callback 60%, tease
60%, irony **22%** -- irony is situational and no lane models it.

## Questions: can retrieval answer a ponder?

The owner: "can our RRF actually pull up question relevant answers in it's
current state? What might we need to adjust so it can?" The engine's
question-shaped recall is the ponder lane (`character.txt`: "a concrete
question whose answer matters to your next decision"), answered next beat by
`search_memories(query)` with no aspects, `max(4, recall_limit)` rows.
Instrument: `tools/jev_question_recall.py`.

Real ponders are rare: 17 in the database outside the excluded chats, five
distinct, all The Doctor's, on banks of 7-173. So 66 more were written by the
`utility` model from each chat-63 beat's own view, mood, goal and concerns,
under the ponder contract -- one each about something known, an earlier
moment this one resembles, and whether something changed recently. Answer
key: Jev grades the whole bank per question ("How much does this memory help
answer the question you are asking your own memory"); 61 of 71 have a row at
0.5 or more. The keys are peaked, unlike the packet's plateau: rank 1 / 5 /
10 median 0.82 / 0.56 / 0.48 for "known".

| ponder net (Jev's top 5 answers) | @8 | @24 | @50 | @100 | all 5 inside, median / p90 |
|---|---|---|---|---|---|
| **today, as shipped** (diversity pass on) | **23%** | **38%** | -- | -- | -- |
| today, fused order | 23% | 39% | 54% | 68% | 245 / 478 |
| question + why as an aspect | 23% | 41% | 55% | 69% | -- |
| + three hypothetical answers as aspects | 26% | 43% | 58% | 74% | -- |
| instruction-prefixed question | 21% | 36% | 50% | 64% | -- |
| keyword only | 15% | 27% | 40% | 50% | -- |
| **fitted weights, leave one beat out** | 27% | 46% | 60% | 75% | 149 / 352 |

- Today a ponder hands the character about **one of its five best answers at
  k=8 and two at k=24**.
- At a pool of 50: "known" 61-63%, "resembles" 59%, "recent" 39% -> 56% once
  recency is a lane. Hypothetical answers (written by the `utility` model with
  three of the character's own rows as a form guide) earned the largest
  weights. They bridge a description to a name only when the written answer
  uses the name: for "What do I actually know about this fox-eared woman?"
  the memory "my name is Hinami" sat at fused rank 119 and **first** in the
  hypothetical lane on the trial run, but 48th and 63rd on two regenerations
  of the same question whose answers did not name her.
- Tuning is worth about 6 points at 50: similarity finds rows ABOUT a
  question's subject; Jev's answers are often inferential. A pool of 50 holds
  60% of the best five at best.
- Beside the fused order the production call passes `here` and `in_sight`,
  which are ROOMS (+0.09, +0.05); omitted here, and nothing in them resolves a
  description of a person to a name.

## What Jev costs

Measured from Jev's own response (`usage.cost`): one 64-question request,
12,416 input and 3,513 output tokens, **$0.000521** -- about **$8 per million
questions** at 200 input and 58 output tokens each (a 970-question pass,
counted). The balance agrees: $20.08 -> $19.09 over roughly 110,000 questions.
Per character per beat:

| shape | questions | cost |
|---|---|---|
| net of 100, 5 channels | 500 | $0.004 |
| net of 100, 9 channels (with the fun four) | 900 | $0.007 |
| whole bank of 650, 5 channels | 3,250 | $0.026 |
| moment tag at commit | 1 per new memory | ~$0.00001 |
| a ponder over the whole bank of 650 | 650 | $0.005, about 1 beat in 332 |

## Limits

One character, one story, one label set: 22 beats and 71 questions from The
Doctor. Fitted weights are fitted to him, and leave-one-beat-out scoring
guards against fitting single beats, not against fitting one story; they need
a second story before they mean anything as constants. Every reference is
Jev's own judgement, so these numbers say what a net keeps of what the judge
would keep, not whether the judge is right; the probe's earlier readings
(four real ponders, the fun channels) are the check on that. Aspects used
the captured `active_concerns` for "what is still unsettled", which
approximates the live `unresolved_items`. The first two sections came from
two beats on 122-row banks and are a direction only.
