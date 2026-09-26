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
  of the same question whose answers did not name her. This is HyDE, which
  `UNBUILT_CHARACTERS.md` §2.25 REJECTED on 2026-08-20 for breaking more hits
  than it rescued; +3 to +5 points here, with breakage unmeasured, does not
  reopen it.
- Tuning is worth about 6 points at 50: similarity finds rows ABOUT a
  question's subject; Jev's answers are often inferential. A pool of 50 holds
  60% of the best five at best.
- Beside the fused order the production call passes `here` and `in_sight`,
  which are ROOMS (+0.09, +0.05); omitted here, and nothing in them resolves a
  description of a person to a name.

## Graded blind: today's packet against Jev's

The owner: "how would you grade how relevant the recall is now compared to
what it was with the @100 filter vs the pure @24 rrf?" and "79% doesn't mean
it's bad it may actually be a massive improvement." Instrument:
`tools/jev_packet_compare.py`. For the 21 labelled beats with a previous
beat, four packets, each excluding the recent buffer the character already
gets (last 4 turns, up to 12 rows):

- `old`: production recall as shipped, `search_memories(view, k=24)` with the
  production aspects and diversity pass;
- `new`: the fitted net of 100 (weights fitted without that beat, primed by
  the previous beat's packet from the previous beat's own net), then Jev's top
  24 by the larger of `situation` and `useful`;
- `new_dedup`: the same without rows within cosine 0.90 of a kept row;
- `ideal`: Jev's top 24 over the whole bank.

The union of the four, shuffled under opaque ids, went to two judges that are
not Jev, each grading every row 0-3 (0 nothing to do with this moment, 1
loose background, 2 bears on what is happening or what they are trying to do,
3 they would be poorer without it): the `utility` model (GLM 5.2), and seven
Claude graders reading by hand, three beats each. Per beat:

| judge | packet | mean | graded 2+ | graded 3 | graded 0 |
|---|---|---|---|---|---|
| GLM | old | 1.14 | 6.4 (28%) | 1.9 | 5.3 |
| GLM | **new** | **1.84** | **15.5 (64%)** | **5.6** | **0.9** |
| GLM | ideal | 1.75 | 14.2 (59%) | 5.0 | 1.3 |
| Claude | old | 1.16 | 6.0 (26%) | 0.9 | 3.4 |
| Claude | **new** | **1.74** | **15.1 (63%)** | **2.8** | **0.2** |
| Claude | ideal | 1.66 | 14.2 (59%) | 2.5 | 0.9 |

- The two judges agree within one grade on 98% of 1,052 rows (Spearman 0.69,
  kappa 0.58 at 2+); both give the new packet about 2.5 times the relevant
  rows and a fraction of the irrelevant ones.
- **Both score the net-of-100 packet slightly above the whole-bank ideal.** The
  21% of Jev's picks the net misses are mostly older rows Jev likes more than
  either judge does; the new packet's median row is 20 beats old against 42
  for the ideal and 35 for today's.
- Old and new share 4.4 of 24 rows; dropping near-duplicates changed 0.4.

**At 48 rows** (the owner: "as we start using jev to decrease the character
prompt by offloading, we might be able to increase memory count without
destroying coherency"). `RETRIEVAL_COST.md` section 6 found conduct peaks at
k=24 and traced the decline to the rows past 24 -- "they compete for the
attention the relevant ones need". Those were RRF rows. The same four packets
at 48 (`build --size 48`), graded blind by GLM, per beat:

| packet | rows | graded 2+ | graded 0 |
|---|---|---|---|
| today, first 24 | 23.1 | 5.2 | 5.6 |
| today, rows 25-48 | 23.3 | 5.4 | 7.0 |
| Jev, first 24 | 24 | 13.7 | 1.3 |
| **Jev, rows 25-48** | 24 | **11.2** | **2.3** |
| **Jev, all 48** | 48 | **24.9** | **3.6** |

Jev's second 24 rows are more relevant than today's first 24, and a 48-row
Jev packet carries fewer distractors than today's 24-row one. By section 6's
own mechanism the knee should move out; only a conduct replay can say whether
it does. (The same judge grades a little harder in the larger sheets: the
new packet's first 24 earn 13.7 here against 15.5 among 24-row sheets.)

## Mood as a Jev job

The owner: "We can make mood a category job for jev and even have it emit
multiple. and yes this should include nsfw and niche moods", "mood likely
needs a rather large context input like recent moods recent chat memories,
and opinions of the person they are interacting with", "some moods are
combinations of moods ... we can reduce category count by breaking down
moods that are actually mixes of moods", and "some moods can be broken down
into spectrums which jev can also answer." Instrument:
`tools/jev_mood_probe.py`, on captured character calls; the reference is the
mood the character model reported on the same call (`state.active.affect`).
Explicit chats are used under the owner's 2026-09-26 permission ("we aren't
playing with censored models atm"); nothing from them is quoted here.

Two ways of asking, both multi-mood because every option is graded alone:
**labels**, 121 of them (the lexicon's 67 plus niche and intimate moods it
lacks), and **bases**: Plutchik's eight primaries plus desire, five spectrums
(pleasure, arousal and dominance -- the PAD space -- then playful/serious and
open/guarded), and two questions for the quieter layer beneath (how strong,
which base). Code names what co-occurs from Plutchik's dyads ("optimism (joy
with anticipation)"). Sixteen questions against 121.

Context sizes: A identity and this beat's perception; B + the mood the
character came in with and its last three; C + its recent memories; D + its
standing with and readings of the people around it.

**Round two**, one call per beat: The Doctor, 38 beats (SFW); Mirelle
Sulmirath, 70 beats (explicit story). Correlation with the character's own
reported mood (bases: the pleasure and arousal spectrums):

| | Doctor valence | Doctor arousal | Mirelle valence | Mirelle arousal |
|---|---|---|---|---|
| bases, A | 0.16 | 0.36 | 0.51 | 0.65 |
| bases, B | 0.59 | **0.81** | **0.90** | **0.92** |
| bases, D | 0.65 | 0.69 | 0.82 | 0.91 |
| 121 labels, D | **0.71** | 0.73 | **0.01** | 0.68 |

- **Recent moods are the context that matters**: A to B is the jump every
  time; memories and opinions (D) then move the numbers by about a tenth
  either way.
- **Sixteen questions nearly match 121 labels, and are selective.** The label
  list grades 13-17 labels "clearly" on every call and its valence collapses
  on the second character; the bases grade 1-3.
- **The quieter layer needs its own question.** Round one, which asked only
  "how much fear do you feel", found a negative base on 9 of 61 negative
  undercurrents the character reported; the two undercurrent questions point
  the right way on 23 of 32.
- **Intimate moods need explicit words.** Round one's "aroused" was graded
  "clearly" on all 68 SFW calls and "dominant" on 27: Jev read them as
  stirred up and commanding. Renamed ("sexually aroused", "sexually
  dominant", ...), no intimate label and no desire grade fires on any of the
  38 SFW beats. On the explicit story, against the character's own words
  (marked by the `utility` model), the desire base finds 98% of the beats
  that report sexual or romantic desire at 72% precision -- and a beat can
  hold desire its report does not name.

**The reference is mostly inertia.** The character prompt says "Begin from
`self.active_state` and propose the feelings you now carry, including feelings
that persist", and the reports do: the mood the character came in with
agrees with its report better than Jev does (valence r 0.72 and 0.95; the
second character's reported valence moves by a standard deviation of 0.05 a
beat). Jev still tracks how a beat MOVES the mood (r 0.37-0.46 on the change
in valence), and carrying the mood forward while moving it about a fifth of
the way toward Jev's reading beats pure persistence on every axis, fitted
leave one out: error 0.172 -> 0.139 and 0.055 -> 0.043 (Doctor valence,
arousal), 0.027 -> 0.020 and 0.049 -> 0.044 (the second character). So the
shape that fits is code carrying the mood and Jev supplying the push -- how
`psychology_runtime` already treats stress. How much a beat SHOULD move a
character is a judgement this reference cannot make, since the reference
anchors on its own previous answer.

## The affect pass, built and run

The owner: "We can also probably do math with moods, the cumulative effects
of events and memories average into an overall mood with multiple
dimensions. Anyways design test and build", then "We can also probably do a
pass after the character turn finishes to see how their actions speech and
thoughts affect their mood." Built: `mind/affect_appraisal.py` (the questions)
and `mind/affect_mix.py` (OCC emotions, the PAD mood, habituation), not wired.
Instrument: `tools/jev_affect_probe.py`, on the 98 captured beats that carry
per-event perception -- The Doctor 38, Mirelle 60 -- one call per beat. Arms:
`E` the beat's events; `M` + the memories recall delivered; `C` + the
character's unsettled concerns, appraised like events; `P` the pass after the
turn, on the character's own speech, actions and held-back want.

**Event emotions against an independent reader.** The `utility` model (GLM on
NanoGPT, which never saw Jev's answers) named the likely emotion per event
from OCC's list. The mix's strongest emotion per event agrees modestly: the
same sign 63% for the Doctor (shuffled 43%), the same family 31% and 36%
(shuffled 21% and 23%). Many disagreements are other readings of one event:
the reader calls her brushing off sand "relief" (he had feared her hurt), the
mix "satisfaction".

**The mood as its own trajectory** -- started from the first beat's mood and
never again shown the character's reports -- tracks the Doctor's reported
valence at r 0.42 (sign 89%) and Mirelle's arousal at r 0.54, and the change
from beat to beat at r 0.30-0.45, as the whole-beat reading did.

**Undercurrents come from concerns, not events.** On 21 of the 32 Doctor beats
whose own report carries a negative undercurrent ("worry" beneath delight),
no event of the beat produced a negative feeling; appraising the character's
unsettled concerns alongside finds one on 32 of 32 -- but also adds one where
none was reported (5 of 6 Doctor beats, 11 of 60 of Mirelle's), and every
share of the SURFACE mood they are given costs its tracking: valence r 0.39,
0.33, 0.27, 0.19 at concern weights 0, 0.25, 0.5, 1. So concerns name the
undercurrent and do not move the surface (`CONCERN_WEIGHT = 0`).

**Memories as context** -- recall's delivered rows, today's packet -- are
mixed: Mirelle's change r 0.38 -> 0.45, the Doctor's 0.30 -> 0.17. That packet
is the one graded above at about a quarter relevant; the Jev packet is the
one to test.

**The pass after the turn** helps a little and harms nothing that matters:
the Doctor's valence sign 89% -> 95%, Mirelle's arousal r 0.54-0.56 ->
0.59-0.61. But the event questions read a character's own acts with a
self-serving tilt: "gratification" (pride with joy) is the strongest emotion
for 175 of 459 acts, remorse for 2; "who brought this about" for the Doctor
praising her line returns her, so his own speech reads as gratitude; a held
back want reads as pride or desire, rarely as a cost. Own acts need their own
questions -- acting against a value (dissonance), what restraint costs, and
whether saying a feeling eased it (affect labelling) or fed it (venting).

## The affect pass, round two (same day)

The owner: "Perhaps our questions need refinement. also i imagine mood has
way more dimensions than what you have mentioned", "Yes mood is a high
dimension object. What we are really answering is spectrums of moods as
coordinates as well as some moods that truly stand as their own", and "it
will take quite a few questions to get all of these spectrums and individual
mood values." Built in fedf5cb3: the event battery separates how good the
event is now from what it makes likely ahead, asks about a fear and a hope
each on its own, and names the event's own actor as an answer to "whose
doing"; own acts get five questions of their own; the mood is twelve bipolar
spectrums (one five-step question each) and eleven standalone moods (one
graded question each), read directly; and code turns each emotion into a
push on the coordinates it moves.

Same 98 beats. Two requests per beat: `V`, the events and concerns
appraised and the mood read directly; `VP`, the pass after the turn. The
`utility` model (GLM on NanoGPT), blind to Jev's answers, rated all 23
coordinates from the same state.

| r against the `utility` model's rating | direct reading | derived by the math | direct, settled with inertia |
|---|---|---|---|
| mean of 20 coordinates | **0.64** | 0.30 | 0.52 |
| pleasure | **0.88** | 0.31 | 0.66 |
| tension | **0.82** | 0.58 | 0.65 |
| safety | **0.82** | 0.36 | 0.81 |
| hope | 0.67 | **0.73** | 0.63 |
| desire | **0.87** | 0.76 | 0.79 |
| engagement | **0.55** | 0.11 | 0.38 |
| amusement | **0.65** | 0.02 | 0.47 |
| anger | **0.70** | -0.18 | 0.63 |
| guilt | **0.64** | -0.18 | 0.33 |

- **Jev's direct reading is the estimator.** It leads on 18 of the 20
  coordinates that varied, and tracks the characters' own reported valence at
  r 0.67 (arousal 0.48). The derived mood is weakest exactly where OCC has
  little to say: engagement, awe, amusement, guilt and anger are reached
  through one or two OCC emotions, and clarity and nostalgia through none.
- **The derived path still carries what the reports carry**: arousal r 0.57
  against the reports, the best of the three -- the reports anchor on their
  previous answer and so does the math.
- **Unmeasured, not absent**: grief, disgust and jealousy did not vary in
  these two stories, for Jev or the reader.
- **Coordinates Jev reads together** (|r| >= 0.8 across beats): pleasure with
  safety 0.88, openness 0.87, hope 0.83 and anger -0.82; playfulness with
  amusement 0.87. In these stories they move together; whether any pair is
  one axis needs a story where they part.
- **The negativity bias was too strong**, as the owner judged ("I think
  that's your negativity bias being way too strong"). The derived valence
  against the reports, The Doctor and Mirelle: r 0.26 and 0.08 at a
  negativity weight and negative-decay factor of 1.5 and 1.5; 0.33 and 0.11
  at 1.0 and 1.0; 0.37 and 0.12 at 0.75 and 1.0. Both now default to 1.0.
- **Own acts keep a self-serving tilt** with their own questions: the
  strongest emotion of 459 acts is pride on 376, frustration on 82, shame on
  1; the act eased the feeling 28% of the time and stoked it 41%.
- **Concerns stopped discriminating.** Round one's concerns added a negative
  feeling where none was reported on 16 of 66 beats; with the refined
  questions ("what does this make likely ahead", "does it bear on a fear") a
  line framed "Still unsettled for you" produces one on 65 of 66 -- and on 32
  of the 32 beats that report one. They still name the undercurrent; they no
  longer say when there is one. A concern needs its own gate: does it weigh
  on you now.
- **Events against the reader's labels**, 182 events: the same family 36%
  (shuffled 23%), the same sign 87% (shuffled 69%).

## The affect pass, round three: a coordinate system for every mood

The owner: "Also I think there is non romantic and sexual desire to
consider", "We are trying to cover all moods and make a coordinate system out
of them", "some moods are really just spectrums some aren't, so there is some
simplification but simplification is not the goal", "and some moods may be
purely memory related", "or their undercurrents at least."

Built (the design note, "The coordinate system"): fourteen spectrums -- the
twelve plus timid/bold (approach against avoidance) and wanting to be
alone/wanting company -- and thirty standalone moods: desire in three
(romance, sexual desire, craving), the Cowen and Keltner categories no
spectrum holds, the hostile and self-conscious moods, numbness, and six whose
object is the past. Per event, "how strongly does this stir you" and "which
of these does it stir most" (every standalone mood, or none of them) replace
the single desire question; each recalled memory is asked the same "which of
these"; each concern "how much is this weighing on you right now"; the
undercurrent is what memories and concerns stirred.

Same 98 beats. `V` now carries the memories today's recall delivered (554,
on 91 beats) and the 274 concerns as items of their own: about 116 questions
a request, 11,320 in all (about $0.09). The rater re-rated all 44 coordinates
blind and listed any mood no coordinate covers.

- **The direct reading still leads**: mean r 0.51 over the 35 coordinates
  that varied (derived 0.27, settled 0.37); on the twelve spectrums both
  rounds share, 0.62 against round two's 0.67, with memories now in both
  readers' context and 44 coordinates rated at once.
- **Desire splits where it varies.** Sexual desire r 0.90 read directly, 0.86
  derived; romance 0.39 (0.52 settled; the rater's own spread is small, sd
  0.15); craving -0.32 read directly -- a wording fault (below).
- **The new spectrums read weakly**: timid/bold 0.43, wanting company 0.34
  (derived 0.02 and 0.16).
- **What an event stirs gives the derived mood coordinates OCC never
  reached**: amusement 0.02 -> 0.27, engagement 0.11 -> 0.36, clarity none ->
  0.41. Anger, guilt and embarrassment stay inverse derived, on references
  that barely move (sd 0.05, 0.03, 0.06).
- **Nine moods never varied** for either reader: contempt, disgust, jealousy,
  envy, sadness, numbness, grief, regret, homesickness. These two stories
  hold little loss, hostility or rivalry; unmeasured, not absent.
- **Jev is twice as liberal as the rater**: 4.4 of 30 standalone moods graded
  clearly or more per beat against 2.1 -- far from round one's 13-17 of 121
  labels.
- **Memories stir the scene's own moods, not the past's**: sexual desire 38%
  of all memory feeling, curiosity 17%, tenderness 16%, amusement 9%, awe 7%,
  resolve 6%; the unease of a past that will not let go 1%, and no other
  past-directed mood in the top ten. "None of these" is never chosen (mean
  share 0.00-0.01), so the plain remainder by tone never fires. Whether some
  moods are memory's own (the owner) cannot be tested on a packet that holds
  little past; that is the Jev packet's test.
- **Today's packet repeats**: the owner's habituation at the placeholder knobs
  dulls 287 of 554 recalls (mean multiplier 0.47), each a memory recalled on
  most of the beats before it.
- **Memory costs the derived mood a little**: valence r against the reports
  0.26 from events alone, 0.23 with memories. Concerns change nothing there,
  by design.
- **The concern gate does not discriminate.** Jev weighs every concern --
  mean 0.69 and 0.70 for the two characters, none under a third -- so gated
  concerns still give a negative feeling beneath on 60 of the 66 beats whose
  report carries no negative undercurrent (63 ungated; 32 of 32 where it
  does). The reference cannot settle it: these are the concerns each
  character listed itself as active, and a report names one undercurrent.
  Nor is what they stir only negative -- the Doctor's most frequent
  undercurrent is curiosity (24 beats).
- **Coverage**: the rater named a mood no coordinate covers on 86 of 98
  beats, nearly all flavoured compounds of coordinates that exist (a
  practitioner's craft pride is proud, in command and absorbed). Two classes
  recurred: anticipation or savouring, and an urge to reassure or ease
  someone.
- **Two wordings misfired.** "Being moved or touched" tracked sexual desire
  at r 0.93 in the explicit story: "touched" read as physical. Craving, "a
  strong want for something, other than romance or sex", took in the
  Doctor's wanting to know: Jev 0.50 against the rater's 0.02, while the
  rater's craving (26 of Mirelle's beats, a hunger to consume) Jev filed as
  sexual desire.

## Round four: the wording the data found

Round three's faults, fixed and re-run on the same 98 beats by both readers:

- **Being moved**, now "a swell of feeling at something tender or
  meaningful": Jev's reading no longer moves with sexual desire (r 0.93 ->
  0.58); against the rater 0.66 -> 0.67.
- **Compassion**, now "feeling for someone's pain and wanting to ease it":
  0.37 -> 0.55.
- **Anticipation** added (thirty-one standalone moods): 0.55 read directly,
  and it left the rater's uncovered list. That list still names something on
  84 of 98 beats -- a practitioner's craft pride, watchfulness, and the urge
  to reassure the compassion wording was meant to hold.
- **The rest held**: mean r 0.50 over the 36 coordinates that varied; valence
  against the reports 0.69; Jev grades 5.1 of 31 standalone moods clearly or
  more per beat, the rater 2.6.

**Craving took a probe of its own**: one question per beat under four
wordings, against both raters' craving -- which barely moves with its own
wording (The Doctor 0.02 and 0.00, Mirelle 0.39 and 0.38):

| craving worded | The Doctor | Mirelle | r, round-three rater | r, round-four rater |
|---|---|---|---|---|
| "a strong want for something, other than romance or sex" | 0.51 | 0.31 | -0.36 | -0.34 |
| the same, "(wanting to know is curiosity)" added | 0.74 | 0.30 | -0.39 | -0.38 |
| "an appetite to have or consume something" | 0.20 | 0.72 | **0.88** | **0.88** |
| "a hunger for something to have, take or consume" | 0.17 | 0.69 | **0.90** | **0.90** |

Jev reads an option by its words. Naming what craving excludes pulled the
Doctor's curiosity in further; naming only the appetite put craving where the
rater does. The pack now says "an appetite to have or consume something".
Jev answered the unchanged round-three wording with round three's means
exactly, so a one-question probe (98 questions) is enough to choose between
wordings.

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
