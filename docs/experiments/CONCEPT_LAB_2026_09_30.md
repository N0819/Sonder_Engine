# Concept lab, 2026-09-30: a synthetic bank against the concept proposal

The owner's proposal, in one conversation (2026-09-30): one memory per turn
("What I experienced / What I did"), with a start mood the character reads
and an end mood the recall math uses; conclusions kept in per-character
CONCEPTS (person, place, thing, event, idea) with a summary the character
maintains and claims that cite memories; concept TAGS on memories so gating
needs no model at recall; a concept LIST in the payload so the character can
ponder a concept deliberately; and concepts the character invents and tags
itself. Nothing here is built into the engine. This is the evidence for
deciding whether to.

Instrument: `tools/concept_lab/` -- `bank.json` (30 hand-written merged
memories of one character, Maren Oakes, an archivist; 16 labelled concepts,
one of them met unnamed first; 12 conclusions with citations, two of them
changes of mind), `probes.json` (10 recall probes, 8 later-beat situations),
`lab.py` (one subcommand per test, every answer cached). The labels were
written with the memories, before any model saw them. Jev: OpenRouter
`typesafe/jev-1.13`. Character model: NanoGPT `z-ai/glm-5.2`, the owner's
default route, under PROTOTYPE prompts in `lab.py` -- not the shipped bare
card. Cost: $0.03 of OpenRouter (all Jev); 62 character calls on NanoGPT.

## 1. Tagging at formation (Jev)

30 memories x 16 concepts, each asked yes/no, scored against the labels
(147 true tags), threshold 0.5:

| wording | precision | recall |
|---|---|---|
| A "Does this memory involve {name (gloss)}?" | 0.86 | 0.80 |
| A without the gloss | 0.82 | 0.73 |
| B "Does {name (gloss)} come into this memory -- is it there, spoken of, or on your mind in it?" | 0.85 | **0.82** |
| code only: `about` (bodies present, heard speaker) | 1.00 | 0.50 (people only) |

By kind under B: person 0.92/0.96, place 0.76/0.96, thing 0.87/0.81,
**event 0.82/0.64, idea 0.83/0.66**. The misses are the implicit ones: "who
held the sluice shut" on the beats where the mayor merely lies or the fire
report is read. The one-line gloss is worth ~7 points of recall -- a concept
needs its summary in the question, not its name alone. Code's `about` is
exact but finds half the people, because the other half are talked about,
not present (Tomas, the mayor). Threshold sweep for B: 0.4 -> 0.83/0.84,
0.6 -> 0.85/0.78.

## 2. Gating by tags (code only)

Each memory carries 4.9 labelled concepts (Jev-A tags: 4.5). If every
memory in the 8-turn recent window brought its concepts up, a beat would
surface **14.1 of 16** on average (max 16). In a focused story the window
alone gates almost nothing. The trigger has to be narrower: this beat's
scene (present bodies, names in what reached the mind) plus the OLDER
memories recall chose, not the whole window.

## 3. MEMORY_CHARS 500 vs 1500 (Jev recall grading, production `grade_net`)

On the synthetic bank the question is moot (merged rows 488 chars on
average, 672 at most): both settings put all 10 targets at rank 1. So it was
re-run on **chat 159's real turns** (the Doctor, episode + self rows merged
into the proposed shape, 23 turns, 316-2,513 chars, most over 900), eight
probes whose answer sits in the "What I did" half, past character 500:

| MEMORY_CHARS | rank 1 | kept (grade >= 0.6) | target grades |
|---|---|---|---|
| 500 | 6/8 | 7/8 | 0.51-0.96 |
| 1500 | 6/8 | 8/8 | 0.77-0.99 |

The grader often finds the right turn from its first 500 characters, because
the experience half sets up the topic. Where only the act half holds the
answer the full row helps: "what I said I would do if she didn't tell me"
rank 11 (0.51) -> 6 (0.77); "what the things behind the door are doing"
rank 6 -> 4 (0.81 -> 0.99). A modest, real gain for merged rows.

## 4. The character invents concepts, tags memories, keeps summaries

15 beats, two memories each, plus up to two older memories that "come back"
(stand-in for recall); the character sees its concept list and the full
entries of concepts tagged on anything shown. Scored by mapping each
invented concept to a label with a Jev choice question (noisy: it mapped
"The 1909 flood" onto "who held the sluice shut" in run 2).

| | run 1 (prompt as drafted) | run 2 (+ one clause) |
|---|---|---|
| concepts created | 46 | **32** |
| new per beat after beat 7 | 2-5 | **0-2** |
| tags per memory (labels: 4.9) | 6.1 | **4.97** |
| labelled concepts found | 14 of 16 | 13 of 16 |

Run 2's clause: "A concept is something you expect to come back to across
many moments -- a person, a place, a thing, a matter still open. One
happening is a memory, not a concept: tag it to the concepts it touches
instead of making it one."

- **Over-invention is the failure.** Run 1 turned episodes into concepts
  ("The Mayor's Dinner", "Brine's Resignation", "Petra Leaves for the
  Ministry"), so its list became a second memory bank. The clause cut it by
  a third and made it level off. It did not end it ("The heritage board
  offer", "Brine's new study lock").
- **Tagging is good where the concept exists.** Run 1: Hesketh 1.00/1.00,
  Petra 1.00/0.92, the mayor 0.90/0.82, the key 0.88/0.88, the fire
  1.00/1.00. Retro-tagging older memories that came back happened
  unprompted from beat 2.
- **Summaries are the strongest result, and they drift.** Tomas and the
  mayor were rewritten nine times each and read as a mind's working
  understanding ("My younger brother. Drowned in 1909 after knocking on my
  door -- I did not open it. ... I am at peace with him now."). But the
  mayor's final summary says "*His father* was the mill clerk" -- the bank
  says young Brine was the clerk himself. A fact from nowhere, after
  repeated rewriting. Citations beside the summary, and a summary rewrite
  that sees what the claims cite, are what would catch it.
- An idea concept can fold into a person: run 2 kept no "door I did not
  open" concept; the guilt lives in Tomas's summary instead.

## 5. The concept list and pondering

Eight situations after the last memory (six where a concept not in the
scene is useful, two controls: the baker's flour prices, a student's
parish maps), two samples each, with the concept list (ids + names) and
without. Without it the character can still ponder in its own words.

| | pondered when useful | right concept | pondered in controls |
|---|---|---|---|
| with list | 12/12 | **12/12** | 2/4 |
| without list | 12/12 | 9/12 | 2/4 |

Both control ponders were the archive, by a student in the archive asking
for maps -- reasonable. The list makes the lookup EXACT; without it the
questions are good but broader (the new lockkeeper asking about the key on
the hook drew "what did I decide that night" -- the guilt, not the key).
Priming (listed concepts mentioned in conduct that nothing in the scene
called for, name/alias match): 12 with the list, 9 without; one stray
mention in the baker scene under each. No priming effect this test could
see. (The prompt invites pondering, so 12/12 in both is a ceiling, not a
rate to expect in play.)

## What this says about the proposal

1. **Tags at formation work for people and places; events and ideas need
   the gloss and still miss a third.** Code tags present people exactly;
   Jev wording B for the rest; the character's own tags agree with both
   where concepts line up.
2. **Gate on the scene and on recalled OLDER memories, not the recent
   window** -- the window surfaces 14 of 16.
3. **The concept list earns its place** (12/12 exact vs 9/12) at no
   measurable priming cost.
4. **Character-invented concepts need the clause and a check.** The clause
   is the first fix (46 -> 32); a Jev question at creation ("is this a thing
   you will come back to, or one happening?") is the obvious next candidate
   to measure, not yet tried.
5. **Summaries need their citations in view.** The one fabricated fact
   appeared in a summary rewritten nine times.
6. **MEMORY_CHARS 1500** is a modest gain on real merged rows.

Residuals: one bank, one character, one model; the invent prompt is a
prototype; the Jev mapping used for scoring is itself noisy; the recall
test ranks a 23-30 row net, not the production net of 100.

## 6. Addendum: "only what is in front of you", no citation (the owner's question)

The owner asked whether a rule -- rewrite a summary only from the current
events and memories shown -- could stand in for citations. Four more invent
runs, all with the run-2 clause: two as before (run2, run2b) and two adding
"When you rewrite a summary, build it only from what is in front of you this
beat -- the memories shown and the summary you already had. Never add a
detail you cannot see there." (run3, run3b). Every version of every summary
(379) was fact-checked against the bank by one reader per run, each flag
classed fabricated / misattributed / conflated, and the large ones re-checked
by hand. "Eleven years" read as time since the flood (it is Maren's years at
the archive) was flagged by three readers and not the fourth, so it is
excluded from every run below.

| run | rule | summary versions | flagged statements | distinct errors |
|---|---|---|---|---|
| run2 | no | 89 | 31 | ~12 |
| run2b | no | 94 | 32 | ~10 |
| run3 | yes | 99 | 26 | ~7 |
| run3b | yes | 97 | 11 | ~8 |

- **The rule helps and does not end it**: flags ~35% of versions without,
  ~19% with; distinct errors ~11 -> ~7.5.
- **The errors are misreadings more than inventions.** "The fire ... took
  most of the lock papers" became a fire AT THE LOCK HOUSE (three of four
  runs); "young Brine carried the order" became "Brine's order" or "his
  father was the clerk"; Petra the surveyor became an engineer (three runs);
  the one number in sight got attached to the wrong span ("eleven years",
  and in run2b an invented "fourteen years" in 15 versions plus "1923").
  Some are plain fabrications ("the same levee failed again", written two
  sentences before "the levee held").
- **Propagation is the multiplier.** Nearly every flag is a copy: an error
  enters one rewrite and every later version keeps it, because each rewrite
  starts from the summary it replaces and treats it as what is known. The
  run2b "fourteen years" is one error in fifteen versions.

What that points at, untested: the old summary is the error's carrier, so a
rewrite should be checked against something other than itself -- the
concept's tagged memories handed in at rewrite time, or a decision-model
check of each new or changed sentence against what was shown ("does
something shown support this?"), which is a deterministic floor that needs
no citation field.

## 7. The large bank: 240 memories, 54 concepts

Built because 30 memories could not test scale. `tools/concept_lab/bank_large.json`
(+ `bible_large.json`, `probes_large.json`, `bank_large_FACTS.md`,
`bank_large_CHANGES.md`): Ines Calder, a mountain railway town doctor, 56 story
days, seven threads that go quiet for weeks, two people met unnamed, and
look-alike pairs (Mira / Mila Brandt, the clinic / the old clinic, the lamp
fire / the bunkhouse fire, the heading collapse / the 1891 collapse / the
explosion, the gas log / Grete's ledger). Written by eight Claude agents from a
bible written first, one continuity pass (104 of 240 memories edited: one
currency, one calendar, one set of running totals), then four BLIND
relabellings: agreement with the writers' labels Jaccard 0.875 (persons 0.94,
places 0.76 -- the setting was the disagreement), 178 disputes adjudicated from
the text and applied. Merged rows average 888 chars; every "did" half starts
past character 459 on average. Probes: 40 recall (hidden-in-did, old,
look-alike, superseded, unnamed-person, multi-memory) and 20 situations (4
controls). Cost of every large-bank Jev run: $0.61 of OpenRouter.

**Tagging (wording B, 12,960 questions): precision 0.92, recall 0.81.** Person
0.98/0.95, thing 0.91/0.93, event 0.80/0.80, place 0.84/0.72, **idea
0.99/0.52**. Ideas are the weak class at scale: Jev almost never tags one
wrongly and misses half. Code (`about`) again 1.00/0.54 for people.

**Gating.** 5.8 concepts per memory; the 8-turn window would surface 25 of 54
(max 34). Confirms section 2.

**MEMORY_CHARS at this scale (40 probes, every probe graded over all 240):**

| | rank 1 | top 3 | top 10 | kept >= 0.6 | a trap ranked above the answer |
|---|---|---|---|---|---|
| 500 | 22 | 30 | 37 | 39 | 8 |
| 1500 | **28** | **36** | **39** | **40** | **6** |

Individual moves: a hidden "did" detail 26 -> 1, a superseded fact 34 -> 2;
two went the other way (4 -> 10, 3 -> 6). The weak kind is SUPERSEDED: in six
probes an outdated memory still outranks the current one (the debt figure).
Grading judges relevance, not which of two figures is newer; that is a job
for the concept summary or for recency, not for the grader.

**The character inventing concepts, 60 beats of four memories, both clauses
(run3).** 97 concepts for 54 labelled; 43 found, 11 never made (Teodor as a
person, the tunnel, the camp, the station, the pharmacy, Grete's ledger among
them -- folded into other concepts: "Tunnel camp", "Teo and me"). Creation
does not level off: 42 in the first quarter, then 15, 17, 23 -- about one a
beat forever, much of it minor patients ("Herr Pichler", "The cheese woman")
and single happenings. Where a concept exists its tags are precise (median
precision 0.97, recall 0.75). At this rate a 500-turn chat holds hundreds of
concepts, so the list cap and a creation check are not optional.

**Ponder with and without the list (20 situations, all 54 concept names in the
list).** Right concept 11 of 16 in both conditions; the exactness advantage of
the small bank did not survive 54 names. The list made the character ponder in
3 of 4 CONTROL scenes (the eggs, the weather, the stopped clock) against 1 of
4 without it. The name-match priming count (19 vs 10) is mostly legitimate
context (a doctor opening her casebook; Father Kurz's map when the question is
the old galleries); no unrelated leakage was seen on reading every flagged
reply. One reply without the list invented a fact to answer a question it did
not ponder ("your birthday is in November"; the bank has March).

## What the large bank changes

1. **MEMORY_CHARS 1500: now clearly worth it** (rank 1: 22 -> 28 of 40).
2. **Idea concepts need more than a yes/no tag** -- recall 0.52. The
   character's own tagging, or a tag carried from the claims that cite the
   memory, are the candidates.
3. **Superseded facts outrank current ones** in grading; the concept summary
   holding the current value, or recency in the pick, has to carry it.
4. **Character invention needs a creation check and a cap**: it does not
   level off at scale.
5. **The concept list's advantage shrinks with its length**, and it invites
   pondering where none is needed. A short list, chosen by relevance (the
   cap of 40 or lower), not every concept.

## 8. Round A: do concept summaries make the character think better?

`tools/concept_lab/round_a.py`, on the large bank, the 54 labelled concepts
SEEDED (as code would seed engine identities) so summary quality is measured
apart from creation noise. The character keeps summaries over 60 beats of four
memories; the concepts on its mind each beat are the ones the formation tags
(Jev wording B) put on the memories shown. Three ways of keeping them: **base**
("only what is in front of you", "keep only the current figure"), **mem** (+
each on-mind concept's three latest tagged memories), **check** (base, then Jev
drops each new sentence nothing shown supports).

**Final summaries, blind fact-check (54 per mode, modes shuffled per concept):**

| mode | errors | of them outdated | missing key facts | usefulness 0-3 | rated 3 | prompt per beat |
|---|---|---|---|---|---|---|
| base | 13 | 7 | 43 | 2.48 | 28 | 12k chars |
| check | 8 | 6 | 67 | 2.24 | 21 | 11k |
| mem | **2** | 1 | **28** | **2.72** | **40** | 60k |

The Jev sentence check dropped 339 sentences and costs more in lost truth than
it removes in error. Seeing a concept's own memories nearly ends error, at five
times the context. The errors left are mostly STALENESS ("moving in tomorrow"
after the move; the debt before the last payment), not invention.

**End to end: the 40 recall probes played as scenes**, packet = 8 recent + 10
best-graded older memories (MEMORY_CHARS 1500), summaries shown for up to 8
concepts gated by the delivered memories' tags and the scene's names; replies
judged blind (conditions shuffled per probe) against the answer memories.

With the answer memory in the packet (39 of 40 probes), no condition helps:
correct 35 (none) / 32 (base) / 34 (mem) / 35 (check); invented details 17 /
8 / 18 / 13. The memories carry their days, so the character got all seven
superseded probes right with no summaries at all.

With the answer memory REMOVED (recall missed it):

| | correct | partial | wrong | outdated | says it does not remember |
|---|---|---|---|---|---|
| none | **2** | 9 | 17 | 8 | 10 |
| base | **12** | 5 | 11 | 4 | 11 |
| mem | 10 | 6 | 14 | 3 | 8 |
| check | 9 | 5 | 13 | 4 | 11 |

Summaries rescue a quarter of recall's misses (2 -> 12 of 40) and halve the
outdated answers. By kind they rescue look-alikes (1 -> 4 of 7), superseded
facts (1 -> 4 of 7) and multi-memory answers (0 -> 2 of 6); they do not carry
fine details (a "did" detail, an old one, what an unnamed man said): 0-1
either way. That is the division of labour: summaries carry current state and
identity, recall carries detail.

**Gating was not arbitrary.** Tag-gated with a cap of 8, the needed concept
was in view on 38 of 40 probes (36 with the answer memory removed), at a cost
of about 2,800 chars on a 16,000-char packet (+17%).

**Recency tiebreak** (newer-first nudge on the grades): 0.02 halves traps
ranked above the answer (6 -> 3) but loses two top-3 hits (36 -> 34), the old
probes; larger nudges only lose more. A trade, not a fix.

**What Round A says:**
1. **Keep summaries; their job is the rescue.** Worth ~17% context when recall
   hits and a quarter of its misses when it does not.
2. **Base maintenance is the cost-effective mode.** Mem makes truer summaries
   but did not answer better (10 vs 12) at five times the context; check loses
   information. A cheaper mem (the concept's one latest memory) is the next
   candidate against staleness.
3. **When neither memory nor summary holds the answer the character still
   guesses** (11-17 wrong, only ~10 "I don't remember") despite the card's
   "do not make it up". That is the next lever for cognition: a ponder, or an
   honest gap, not a better store.

## 9. Round B: the owner's concern design

The owner's proposal: keep an ACTIVE CONCERN summary for each unresolved matter
that is live; retire it to memory when it resolves, under its name, so it comes
up when relevant; leave most concept modelling (people) to mind modelling.
Refined the same day: memories are TAGGED with the concerns open when they
formed, a resolved concern becomes that tag's concept, and its final summary is
shown whenever a tagged memory comes up; and the concern tags and summaries can
be used with Jev. `tools/concept_lab/round_b.py`, same bank, same 40 probes with
the answer memories REMOVED, all seven conditions judged blind together (four
judges, conditions shuffled per probe).

**The character keeping concerns** (60 beats of four memories): 60 opened, 57
resolved, 3 still open at the end; the list peaked at 17 around day 30.
**Premature resolution fragments threads**: "Pharmacy debt" was settled on day
6 and "Grete's debt" opened on day 28; the quinine crisis was retired three
times, Brenner twice, "Old mine workings" settled on day 33 and reopened.
Concern tags (Jev: "does this memory bear on this matter of yours?", asked of
every memory formed while it was open): 214 of 240 memories tagged, ~4 each.

| condition | correct | correct + partial | wrong | outdated | context |
|---|---|---|---|---|---|
| none | 2 | 12 | 14 | 7 | 16.0k |
| all-concept summaries (Round A base) | 9 | 18 | 11 | 4 | 18.9k (+18%) |
| **concerns: open shown, resolved retired to memory** | **8** | 15 | 13 | 4 | **17.0k (+6%)** |
| concerns + person summaries | 6 | 17 | 11 | 5 | 18.3k |
| concern tags: summaries shown when a tagged memory comes | 5 | 14 | 10 | 5 | 20.6k (+28%) |
| concern tags + person summaries | 5 | 15 | 11 | 6 | 21.9k |
| Jev chooses which concerns to show | 5 | 18 | 10 | 6 | 19.3k |

Judge variance: these judges gave base 9 correct where Round A's gave it 12, so
differences of about three are noise at n = 40.

- **The concern design matches full concept summaries at a third of the
  cost.** 8 correct against 9, +6% context against +18%. The retired record
  is a memory: it competes for recall like any row and arrives only when it
  answers.
- **Showing final summaries by tag did worse than retiring them** (5 correct,
  the most "absent"): tag counting always filled the cap of 8, and eight
  summaries of fragmented concerns crowd the packet. The Jev gate was choosier
  (5.4 shown) and tied base on correct + partial (18), not on correct.
- **Person summaries on top added nothing** (6 vs 8): mind modelling can hold
  people without costing the concern design anything measurable.
- **Concern labels do NOT belong in recall grading.** Regrading all 40 probes
  (answers present) with "part of: <concern>" on each row and the open concerns
  as what is unsettled: rank 1 28 -> 21, top 3 36 -> 25, top 10 39 -> 32; only
  traps above the answer improved (6 -> 4). The grader believes the label over
  the text -- the same failure "about Hinami" had (memory_jev.memory_line).
  Concern tags are for GATING what is shown, never for grading.

**What Round B says:** take the owner's design -- open concerns in view,
resolution retired to memory under the concern's name, people left to mind
modelling -- and fix what limits it: **premature resolution**. A thread settled
too early leaves a wrong final record and reopens as a stranger. The next
candidates: a Jev check on resolution ("is this truly settled, or only quiet?")
and reopening a retired concern by name instead of opening a new one.

## 10. Round C: fixing the concern lifecycle, superseded links, and Jev's question load

`tools/concept_lab/round_c.py`. Three borrowed mechanisms, adapted:

- **Merge on open** (Mem0's update-against-similar): a proposed concern is
  compared with its three most similar concerns, open or retired (word overlap
  here; the engine would use its vectors), and Jev asks whether it is the same
  matter; if so the old one is updated, or reopened with its history.
- **Resolution by commitment** (Klinger's current concerns): a resolve the
  character proposes is classed by Jev -- achieved / given up by you / only
  quiet for now / still live -- and only the first two retire it.
- **Superseded links** (Zep's invalidation, adapted so no label ever reaches
  the grader): each memory is compared with its five most similar older ones
  (TF-IDF here); Jev asks whether it changes something the older one states as
  true; a yes records `superseded_by`. At recall, a delivered memory whose
  successor was not delivered pulls the successor in beside it.

**Lifecycle.** 19 concerns in all (round B: 60); 12 retired, 7 open at the end,
at most 11 at once; of 32 proposed resolutions Jev let 14 through (13 still
live, 7 only quiet); 38 proposed concerns were merged into existing ones and 2
retired ones reopened. The debt to Grete correctly stayed open throughout. It
swung from fragmentation into OVER-MERGING: "Tunnel blasting and coming
injuries" absorbed 44 rewrites (the gas cover-up and the explosion with it),
"Camp illness" 29.

**Links.** 1,185 questions; 93 older memories marked superseded, 196 links;
17 of the 23 outdated memories behind the superseded probes chain to their
current answer. Precision on a 30-link sample (judged): 19 valid (63%); a
stricter threshold does not help (0.6: 14 of 21; 0.8: 6 of 7 but most real
links lost). A false link costs a slot, not a falsehood -- it pulls in a real,
newer memory.

**End to end, answer memories removed, one blind set:**

| | correct | correct + partial | wrong | outdated | context |
|---|---|---|---|---|---|
| none | 2 | 10 | 16 | 8 | 16.0k |
| full concept summaries | **10** | 17 | 9 | 4 | 18.9k |
| round B concerns | 8 | 16 | 11 | 4 | 17.0k |
| round C concerns (merge + resolution check) | **2** | 13 | 12 | 6 | 18.8k |
| round C concerns + links | 8 | **19** | 9 | 5 | 20.7k |

- **Merge-on-open wrecked the concerns**: no better than nothing. Twelve
  retired records, several of them whole threads squeezed into 400
  characters, gave recall little to find. Round B's 57 "fragments" were good
  memory units -- small, specific, recallable; fragmentation's real harm was
  only the few WRONG records ("Pharmacy debt" settled on day 6).
- **Links work**: on the same weak concerns, 2 -> 8 correct and the best
  correct + partial of any condition, by pulling in 11 of the missing answer
  memories.
- Next (round D): the resolution check WITHOUT merging (merge only to reopen a
  retired concern), plus links.

### Jev's question load (engine change, landed this session)

On chat 159 turn 23 (the latest beat on this code) the character pass made 18
Jev calls, ~300k input and ~81k output tokens. Rebuilding that beat's holding
with the engine's own `holding_from` (71 delivered memories): the read-back
asked ~369 questions, **284 of them the four `echo` details asked of every
memory -- and `character_bare.compile_bare` reads them for the one memory
`echo` picked** (`memory_modulation`). `mind/character_jev.py` now asks only
which memory in the read-back, and `ask_after` asks that memory's four details
in a small dependent request against the same state (`echo_questions`). Live
on the same beat: **89 questions in 2 requests, 0.6 s, the same information
reaching the engine**. Tests: `test_how_a_memory_comes_back_is_asked_of_the_
picked_memory_alone`; 16 test files around the batteries pass.

The next per-memory family is the before-call dispute check (one question per
delivered memory, 71 on that beat): it found a dispute on 2 of the last 30
character results in the owner's db, and none of the 71 on turn 23. A gate
question ("does what just happened change what anything you remember
meant?") with per-memory questions only on a yes is the candidate; it has to
be tested on the two positive beats first.

## 11. Round D: the resolution check without merging, plus links

Round C's mechanisms with merge-on-open removed (a proposed concern may only
REOPEN a retired one judged the same matter). 58 concerns (4 reopened); of 82
proposed resolutions Jev let 44 through (32 still live, 6 only quiet); 40
retired, **18 still open at the end, the open list peaking at 26** -- the check
holds back matters that have merely gone quiet ("Lotte's arrival and
situation", "Dispensary fire -- restocking" still open on day 56).

**End to end, answer memories removed, one blind set (four judges, six
conditions shuffled per probe):**

| | correct | correct + partial | wrong | outdated | invented | context |
|---|---|---|---|---|---|---|
| none | 2 | 13 | 13 | 9 | 12 | 16.0k |
| full concept summaries | 10 | 17 | 10 | 4 | 13 | 18.9k |
| round B concerns | 6 | 15 | 13 | 4 | 12 | 17.0k |
| round C concerns + links | 8 | 19 | 9 | 6 | 15 | 20.7k |
| round D concerns | 9 | 17 | 12 | 6 | 13 | 23.7k |
| **round D concerns + links** | **15** | **21** | 10 | **3** | **8** | 25.6k |

By kind (correct), round D + links against full summaries: superseded 6 vs 4
(of 7), look-alike 4 vs 3, multi-memory 4 vs 2; fine details stay recall's
(0-1 everywhere).

- **Concerns that end only when achieved or given up, plus superseded links,
  are the strongest design measured:** 15 of 40 correct where recall missed
  the answer, against 10 for full concept summaries and 2 for nothing; the
  fewest outdated answers (3) and the fewest invented facts (8).
- **It costs context: +59% (25.6k vs 16.0k)**, from 18 open concerns shown
  every beat and ~2 pulled successor memories per scene.
- The two pieces are complementary: the resolution check keeps retired records
  RIGHT (no "settled on day 6"), and links bring the current version of a fact
  when recall found only the old one.

**Next:** keep the gain, cut the cost -- (1) Klinger's other exit,
disengagement: a concern that has been only quiet for N story days retires as
"let go" (the owner's dormancy rule, like intentions); (2) show open concerns
by relevance rather than all of them (the Jev gate from round B, applied to
OPEN concerns only). Measure both against round D + links' 15.

## 12. How much do a smaller RRF net and a smaller keep hurt recall?

The owner's question: net 100 -> 60, Jev keeps 30 -> 24.

**Chat 63's cached labels** (`jev_net_labels.py` output from 2026-09-26, 22
beats, banks 308-649 rows; Jev's grade of every row cached, the fused RRF
order of that date): the share of Jev's whole-bank top-N that is delivered.

| of the whole-bank top | net 100 / keep 30 | net 100 / keep 24 | net 60 / keep 30 | net 60 / keep 24 |
|---|---|---|---|---|
| 5 | 70% | 70% | 54% | 54% |
| 10 | 62% | 62% | 46% | 46% |
| 30 | 56% | 56% | 37% | 37% |
| worst beat, top 10 | 40% | 40% | 20% | 20% |

**The large bank, embedded** (`tools/concept_lab/embed_bank.py`: the 240
merged memories written through `prepare_memories_batch`/`add_memories_batch`,
pplx-embed on mypc; each probe's net built by `memory_jev.memory_net`, the
production equal-weight RRF, scene as query and goal as aspect, recent window
excluded; kept by the cached whole-bank Jev grades; answers known):

| net / keep | answer delivered | every answer (multi) |
|---|---|---|
| 40 / 24-30 | 37 of 40 | 35 |
| 60 / 24-30 | 38 | 36 |
| 80 / 24-30 | 39 | 38 |
| 100 / 24-30 | 40 | 38 |
| 150+ | 40 | 40 |
| RRF alone, top 24 | 36 | -- |

- **Keep 24 costs nothing** in either measure: Jev grades rows independently,
  so what it values most tops whatever net it is given, and no beat's net held
  more than 24 of the reference.
- **Net 60 costs real recall, more the bigger the bank**: 2 of 40 on a
  232-row bank (both unnamed-person probes: the question says "Anton", the row
  "the man with the burned hand"; this lab bank carries no `about` tags), and
  a quarter to a third of the best rows on chat 63's 308-649-row banks.
- Recommendation: keep 24 is free to take; keep the net at 100 or scale it
  with the bank, not fixed at 60.

## 13. Round E and F: cutting the context the concern design costs

- **Round E, dormancy** (`DORMANT_AFTER = 30` memory-turns untouched, mirroring
  `affect.INTENT_DORMANT_AFTER`; a let-go concern can be reopened): 54
  opened, 39 retired (8 let go), 15 open at the end. **It cost about three
  correct** (11 vs round D + links' 14 in the same blind set): a let-go record
  says little ("it went quiet"), so a thread that paused lost its summary.
  Several stale concerns stayed open anyway, touched by small updates.
- **The relevance gate on OPEN concerns** (Jev per open concern: "does this
  matter bear on what is in front of you now?", at most 6 shown) **cost
  nothing**: round E 11 with or without it, at 21% less context.
- **Round F: round D + links + gate** (no dormancy), judged blind against
  round D + links and full summaries:

| answer memory removed | correct | correct + partial | wrong | outdated | context |
|---|---|---|---|---|---|
| full concept summaries | 12 | 17 | 12 | 4 | 18.9k |
| round D + links | 15 | 20 | 11 | 3 | 25.6k |
| **round D + links + gate** | **14** | **23** | **7** | **2** | **19.3k** |

**The design to carry forward**: the owner's concerns -- open concerns kept by
the character, retired to memory under their name only when ACHIEVED or GIVEN
UP (Jev checks each proposed resolution), reopened by name rather than
duplicated, open ones shown only when Jev finds them relevant (cap 6), people
left to mind modelling -- plus superseded links pulling a memory's successor
in at recall. Across the blind sets it scored 14-15 of 40 where recall had
missed the answer (full summaries 10-12, nothing 2), with the fewest wrong and
outdated answers, at +20% context over no concepts (full summaries +18%).

## 14. Disputes belong to conclusions -- and the disguise exception

The per-memory dispute check (one question per delivered memory, ~70 a beat)
fired once in the last 15 recorded character results. The owner: disputes are
rare because a dispute needs a CONCLUSION something can overturn, and the
models are consistent at knowing they lack information; dispute belongs with
conclusions, in the notebook -- "unless it's finding out someone was wearing a
disguise." A gate question tracked the per-memory check on 10 rebuilt beats
(0.57 and 0.75 on the two near-firing beats, 0.12-0.40 on the other eight) but
only one recorded dispute exists to test it against. The design proposed
instead:

1. Conclusions are checked where they live -- notes and beliefs, against the
   moment alone (`note_touched`, `belief_touched`, built). A memory re-read in
   a new light is already asked per change line (`rereading`).
2. Identity reveals are handled in code: `_memory_about` deliberately leaves a
   disguised body OUT of a memory's who-was-there tags (a masked stranger is
   never linked to the face under the mask), so nothing re-links the memories
   when the disguise falls. Record the true identity host-only at formation;
   when the mind learns the disguise (`disguise_known_to`), link those rows
   and ask the dispute question of exactly them, on that beat.
3. The per-memory dispute check for everything else goes.
Untested: needs a disguise thread in the bank and a leak check before the
reveal.

## 15. Sending Jev less: three cuts, each held to the noise floor

The owner: reduce what we send Jev and how many questions we ask, while still
getting the task done. Jev bills input only ($0.042 per million input tokens,
measured: 281,996 tokens for $0.011844). Chat 159 turn 23 cost ~337k input
tokens (~$0.014): the Director ~36k, the character pass ~300k.

Method: `tools/concept_lab/jev_equiv.py` rebuilds real captured beats (payload
+ the model's raw reply, through `character_bare.holding_from`), asks one
battery under variants, and compares answers question by question. The floor
is the same battery asked twice; a cut is taken only if it stays at the floor.

**Tried and refused**
- Dropping the memories from the read-back state (84% of its 19k chars):
  agreement 64.4% against the floor's 97.3% -- impact 57%, relationships 54%,
  norm 30%. Memories cut to 100 chars: 87.6%. The memories are context, not
  padding.
- Numbered memory pointers in options ("the memory marked [m12]"): 92.8%;
  Jev reads option text, it does not look the number up.

**Taken**
1. **Echo details asked of the picked memory only** (`echo_questions`): the
   four were asked of every delivered memory and read for the picked one.
2. **Memory options quoted to 50 chars** (`MEMORY_OPTION_CHARS`): the
   memory-menu questions (echo, which memory, what a line rests on, what
   shaped the act) each listed every memory at 160 chars -- 73% of the
   read-back's question text. At 50: the rest of the read-back agrees 97.4%
   (floor 97.1%); every memory pick stays in the full pick's top three (24 of
   24) -- the picks are near-ties (median margin 0.11) that any prompt change
   reorders.
3. **Recall graded on one question** (`memory_jev.QUESTIONS`): `situation`
   alone vs the pair on the 240-row bank's 40 probes: first 30 vs 28, top-24
   40 vs 40; on 5 real beats its top half matched the pair 96.2%, the pair
   against itself 96.2%.
4. **Dispute asked of claims only** (`DISPUTABLE_ORIGINS`: what the mind
   concluded or was told; the owner: dispute belongs to conclusions). A plain
   record of what happened holds nothing to overturn; the disguise reveal is
   the exception still to build.

**Chat 159 turn 23, one character pass, same estimator before and after:**

| family | questions | requests | ~input tokens |
|---|---|---|---|
| recall grading | 200 -> 100 | 4 -> 2 | 41,258 -> 20,629 |
| dispute | 71 -> 33 | 2 -> 1 | 15,386 -> 6,812 |
| read-back + echo | 369 -> 89 | 6 -> 3 | 94,124 -> 32,351 |
| moment checks | 28 | 1 | 2,889 |
| feelings (events + mood read) | 60 | 1 | 10,403 |
| **total** | **728 -> 310** | | **164,060 -> 73,084 (-55%)** |

**Not taken, the owner's call:** `decisions.MAX_QUESTIONS_PER_REQUEST = 64` is
ours, not TypeSafe's (it accepted 200 in one request, same latency). Each
request repeats its state, so 128 would save one state copy on recall grading
and the read-back (~6k tokens a pass). A larger cap must also bound OPTIONS:
60 questions of 55 options each hit Jev's output ceiling earlier today.

**Next candidates:** gate the per-person relationship axes (7 questions per
known person present) and the per-aim impact set (4 per aim) behind one
question each; the feelings pass's 54-question mood read each beat; the
Director's ~36k.

**Addendum, same day (owner: raise the limit, then test the rest; "we want
good recall and a dynamicish memory").**

- `MAX_QUESTIONS_PER_REQUEST` 64 -> 128, with a second ceiling,
  `MAX_OPTIONS_PER_REQUEST = 2400` (a batch closes at whichever it reaches
  first): 2,560 short options answered in one request, 3,300 long ones hit the
  output limit. Every battery of the pass now fits one request: **310
  questions, ~66.9k input tokens a pass, from 728 / ~164k (-59%)**, ~$0.0028
  a pass.
- **Gates on relationships and aims: refused.** On the 10 real beats the full
  questions found a relationship change for EVERY known person present (10 of
  10) and an aim the moment bore on 25 of 30 times; a gate would add 40
  questions to save 11, and it missed one real relationship change -- a less
  dynamic memory for more questions.
- **The mood read stays**: its 54 questions share the events' request (~3.5k
  tokens) and are what keeps the mood moving beat to beat.
- **Echo details against the moment alone: refused** -- 17 of 40 answers
  matched the full state, which matched itself 39 of 40.
- Left: the Director (~11% of a beat), which needs its own harness.

## 16. A real story with the bank planted: "Kessel Pass: the statement"

`tools/concept_lab/story_run.py` (setup / opening / turn / look) on a scratch
database outside the tree: the install's providers and settings (no host
credentials), the long-answer GLM roles on NanoGPT `z-ai/glm-5.2:thinking`
(the plain model went silent past the 30 s first-token watchdog on card
generation), the Director and room designer on plain GLM, the encoder on
Gemini 3.8 Flash, Jev on OpenRouter, full capture. Ines Calder and Teodor Lind
generated by the engine's card generator (every psychology field filled);
Ines's 240 merged memories planted as her pre-story past, each dated in its
text. The player: Klara Hess, a Ministry records clerk come to take Ines's
statement for the inquiry's final report, 29 November. 11 turns.

**Two engine defects found**

1. **A seeded past floods the recent window.** Pre-story rows are written at
   `turn_idx` 0 (as `compile_journey_history` writes them), and the 8-turn
   recent window counts turn 0 as recent: for a character's first eight turns
   its WHOLE seeded past is delivered as "recent" (here > 262k chars per
   character call, the capture's cap -- the recalled section was empty, 29
   chars) and recall never runs on it, because the net excludes the recent
   window. A journey history of a few dozen rows makes this a nuisance; a real
   seeded past makes it a flood. Turns 1-6 of this run were therefore no recall
   test. Moved to `turn_idx` -1 in the scratch db from turn 7; the fix (pre-story
   rows never count as recent) is the owner's call.
2. **A seeded past cannot be placed in time.** Every recalled pre-story row is
   labelled "at a time you cannot place against now", whatever its text says,
   and Ines said she found Petr's murmur entry "eight weeks ago" -- the row
   ("(20 November)") is nine days old.

**What memory did well** (from turn 7 on, recall doing the work: packets of
~71k chars, ~37k recalled + ~33k recent)
- The fever, every figure against the facts sheet: 26 cases, one death
  (Pavel Hruby, 19), first case 18 October, last 7 November two days after
  the well closed on the 5th, bunkhouses one, two and four on the upper well,
  16 of the first 19, mine water from Gallery Two sealed since 1891, Brenner's
  "mountain ague" and his later revision.
- The superseded debt: the peak, 284 crowns, AND the current 161, kept apart.
- The gas logs: green cloth cover, under Stoll's mattress in oilcloth, the
  black company book, Hale took both on the 17th at one-forty, her initials
  as witness -- and she kept Anton's name out of it, as she did in the bank.
- Petr: eleven, the soft systolic murmur at the left sternal border noted
  eight days before the operation, "query -- recheck", never rechecked.
- A line of thought held across two unrelated beats: "If she asks, I will show
  it" -> two beats later she brought down the first volume and showed only the
  two pages, protecting "the gas-log shorthand on the flyleaf" (a week-2
  detail).

**Where it failed**
- **Clash with memories she HAD:** the water carter became "Wirth, the same
  man with the bad knee" (Wirth is the postman with the bad knee; the
  carter's wife is Frau Wendt) and the carts cost "ninety-nine crowns"
  (eleven a week since 5 November: ~38). Both rows were in her packet -- the
  whole bank was, turn 6 -- so an overloaded packet misreads, not only a
  thin one.
- **Clash with a memory recall missed:** Petr's operation became a "bowel
  obstruction"; the bank has the appendix (26 October), not delivered. The
  routing failure the owner named: a gap filled that contradicts a memory
  the mind holds but was not shown.
- **The thought record is wiped by any reply that leaves it empty.** On 3 of
  10 character replies `want`/`held_back`/`hinge`/`unsure` (and the note)
  came back blank, and commit treats an empty record as "clear the old one";
  the five-entry notes log carried the line through, the continuity record
  did not.

**Jev:** $0.069 over 11 turns; ~$0.006-0.008 a beat with one major character
once recall was doing the work -- above the ~$0.003 one-pass estimate because
the planted rows carry no stored feelings, so every newly recalled one is
asked the three evoke questions with its full text (the catch-up cost the
feelings-at-formation commit measured on old banks). Seeding a past with its
feelings would remove it.

## 17. The same story, seeded the engine's new way

A fresh scratch story (`.../tmp/story2/story.db`), same cast and scenario; the
240 memories planted as the engine now writes a seeded past -- `turn_idx`
`PRESTORY_TURN_IDX` (-1), `encoded_at_seconds` negative from each memory's date
(the story opens on day 60), and `affect_pass.feel_seeded` at planting (240 of
240 felt, one batch). Run 1's probes replayed, then the story continued by hand
once a replayed input stopped fitting (below).

**Fixed, as measured on the first character beat (turn 3):** the memory packet
was 45k chars -- 36k recalled, 9k recent -- where run 1's was >262k, all
"recent", the recalled lane empty. Seeded rows carried real ages from the first
beat ("about 2 months ago", "about 3 weeks ago"), and she reasoned with them:
"The explosion was the fifteenth of November -- fourteen days ago. The last
fever case ... the seventh, roughly. Twenty-two days." Both exact.

**Recall, probe by probe**
- Fever: 26 cases, one death (Pavel Hruby, the 24th), the breach into the 1891
  galleries in October's second week -- right; the first case "the
  nineteenth" (the 18th) and "22 of 23 from the upper well, the one who didn't
  drank only beer" (the bank: 16 of the first 19) -- wrong.
- Petr: "an operation for a ruptured appendix" -- right, where run 1 (recall
  missing that row) said "bowel obstruction".
- Water: two carts a day from 5 November, eleven crowns a week -- right, where
  run 1 conflated the postman with the carter and billed an impossible 99
  crowns; the carter's name, "Hartmann", invented (the bank names only "Frau
  Wendt, the carter's wife") -- a gap filled, mildly at odds.
- Gas logs: Anton Reis, the black company log at 0.4 every shift, the green one
  under the mattress in oilcloth showing "they should have stopped twice in
  October", her letter to Voss of the 14th -- right; Hale took the book "the
  16th" -- wrong (the 17th, which run 1 had right).
- She kept Lotte out of a Ministry register, unasked -- her card's goal (keep
  Lotte and Mira from the husband) at work.

**The run's one confound was the test's, not the engine's.** Replaying run 1's
inputs, turn 3 had Klara "sit at the long table" -- but here nobody had opened
the door, so the Director placed her at a long table on Main Street, and Ines
heard every question through a closed door as fragments ("A muffled voice:
...Ministry... compensation... dressings...") and spent five beats demanding
plain answers. Correct perception; the firewall held. Klara entering fixed it
at once ("That is the first plain sentence you have said since you arrived"),
and the questions she had half-heard carried forward correctly.

**Still open:** the decision-continuity record came back empty on several
replies again (the owner's "active thought line"); the town plan gave the
schoolteacher no school ("he has to ask someone where his own school is");
Jev stayed at ~$0.005-0.009 a beat -- the evoke questions were not what drove
it.

## 18. Landed after §17: questions, volume, and one memory per turn

Measured on the same story (`tools/concept_lab/story_run.py`, the second
scratch run), each change verified live before it was committed.

- **Recall misses or misreadings?** Of the run's three wrong details, two were
  recall misses on a direct question: the day-18 rows recording the first fever
  cases were never delivered, so "the nineteenth" was inferred from the day-19
  row, and the day-48 row recording when Hale took the log was not delivered
  either. One was a misreading of a delivered row ("22 of 23" against the
  delivered "16 of the first 19").
- **A heard question is pondered** (`character_jev.heard_question`, owner's
  design). Jev sees only the lines the mind heard and asks "Is this a
  question?" of each. The surest one is pondered in its own lane
  (`asked_recall`) beside the mind's own ponder. Asked the same two
  questions, Ines answered both exactly: "The eighteenth, not the nineteenth …
  Jonas Mraz, nineteen, and Bela Horvat"; "The seventeenth … a receipt for the
  green log at twenty to two".
- **An unmarked line is spoken at a normal voice.** Every plain player line had
  been pitched, and pitched across a desk solves to a mutter, so it rendered as
  "says under their breath".
- **One memory per turn** (`commit_memory._turn_memory_text`), in the order it
  was lived: "What I witnessed: … What I did: … What happened: … How I came
  into it: <the start mood in words>".
  - The first version took everything from the end-of-turn view, so it read
    witnessed → result → did.
  - "What I witnessed" is now the act stage's own episode
    (`perception_act.witnessed`). "What happened" is the outcome's episode
    minus every percept the act stage held: matched by key, and by what it
    says (`composer.episode_signature`, counted), because the two stages mint
    one act under different event ids.
  - Verified live: Klara's call, then Ines turning back for the glove, then
    what followed, with nothing said twice.
  - The end mood is the row's feeling: both formed layers as one moment
    (`affect_pass.formed_for`), plus `encoding_valence`.
  - A heard line is a row of its own only when it is a promise. Speakers and
    addressees stay in `about`.
  - Jev's 50-character options skip the leading label.
  - The bare card's subjectless act is remembered with the mind's own name as
    its subject. "I tried to" in front of it read "I tried to lifts the latch",
    every bare beat since 2026-09-27.
