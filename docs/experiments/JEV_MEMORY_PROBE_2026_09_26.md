# Jev as a memory judge: the first probe

Status: EVIDENCE, 2026-09-26, two beats. Instrument: `tools/jev_memory_probe.py`,
run against a copy of `engine.db` in the worktree. Design context:
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
  that, and there the union of generators is the better shape.

The reference is Jev's own judgement, so this measures whether a net keeps
what the judge would keep, not whether the judge is right.

## Limits

Two beats, one character, one story, 122-row banks: a direction, not a
measurement. No labeled answer key was available, so every "on point" above is
a reading. Aspects used the captured `active_concerns` for "what is still
unsettled", which approximates the live `unresolved_items`.
