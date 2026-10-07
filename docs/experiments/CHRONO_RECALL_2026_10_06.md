# The question chooses its search: routed chronological recall, measured

Status: EVIDENCE, 2026-10-06. The owner, 2026-10-06: "we can have alt search
engines specialized for different lookups", "With jev we don't even need the
llm to think about the question type or field", and "build it in a worktree
and either build a synthetic database or update a database to have
everything needed and test a character model against it." Built in
`mind/memory_routes.py` on branch `chrono-recall`; the design and the prior
art are `docs/design/DESIGN_CHRONOLOGICAL_RECALL.md`. Replicated the same day
on 82 questions, three runs a side (§8): the planted answer reached the packet
on 8 questions only with routing and none only without (exact McNemar p =
0.008), and ten questions are marked wrong in every run -- four classes, now in
`docs/UNBUILT_CHARACTERS.md`. The runs' decisions are training data (§9).

## 1. What was built

A ponder -- the lookup tool's, the next-beat ponder a reply asks for, and the
question a mind hears -- is routed inside `memory_jev.jev_ponder_packet`, so
every path gets it with no call site changed:

- **The router** (one decision-model request, run beside the ponder's own
  grade): what the question asks the memory for (anything / the first time /
  the last time / just before / just after), what a first or last time is OF
  (meeting someone / hearing of / being somewhere / something done or
  happening), whether it asks about something that already happened at all,
  and -- only when there is somebody to choose -- whom it is about, among the
  people it names that the mind knows and the one asking.
- **The searches**, over the rows the ponder's net already read:
  `met` (the who-was-there tag decides; rows no tag can reach -- a seeded past
  -- are asked whether the person is there), `heard_of` (the first row saying
  the name), `place` (the first row made there), each moment code finds
  confirmed once against the question; and the WALK -- the rows nearest the
  question in time order, a named person's or an asked-about place's own
  earliest (latest) rows held beside them, the first the model is sure of
  taken (`WALK_FLOOR` 0.8); for just before / just after, the row the model is
  surest shows the moment (a near tie to the earlier), and code reads the
  turns on the side asked.
- **The answer**: the moment marked in the story's words (`in_time`: "the
  earliest moment I remember with Oren Dask") and the turns around it
  (`SPAN_TURNS` 3), beside the graded ponder's own picks -- routing only adds.

## 2. The test bank: Saltmere

A scratch database with the owner's providers and settings (read-only from
the main checkout; routing untouched), Mara Vell's card from the engine's own
generator, the persona Wren, an opening played through the real pipeline
(672 s), and Mara's bank planted under it: 310 turns in the engine's
one-memory-per-turn form plus 106 inference rows and 20 seeded-past rows
(436 rows, real `pplx-embed` vectors), written by eight writer agents from a
bible with 25 planted answers at exact turns and distractors planted after
them (later rows that say "met Oren" in so many words; nine later echoes of
Oren's first line; plainer first lies than later ones). Code checked every
hard constraint (no name before it is learned, no one seen before their
first meeting, places, planted turns, time moving forward); five adversarial
readers then tried to break each planted answer against all 310 turns: 24
held, 2 were ambiguous and were fixed (the mill fire now ends inside its
turn; one answer widened), and the drift of Wren's pronouns in the last
chapter was corrected. The questions are asked at turn 312, after the
opening at 311, as Wren's line to Mara.

## 3. The router

Probed on the owner's decision model (OpenRouter `typesafe/jev-1.13`) with
the question alone as the state.

| | tuning set (48 en, 30 ja) | held-out set (50 en, 30 ja, written by an independent agent in other genres) |
|---|---|---|
| order right | 48/48, 30/30 | 46/50, 28/30 |
| chronological questions routed | 28/28, 17/17 | 25/26, 15/17 |
| content questions kept as content | 17/17, 13/13 | 19/22, 13/13 |
| kind right | 20/21, 12/13 | 17/20, 10/11 |

The first wording routed every chronological question but also a plan
("before the curfew tonight"), a direction ("after the toll road") and a
superlative ("the last person you'd trust"); a separate yes/no -- does it ask
about something that already happened -- took the content questions from
13/17 and 11/13 to all of them. The held-out misses fail safe: "How did you
and Captain Harrow meet?" (no "first") and "the morning of the hull breach"
stay content; three content lines route anyway ("Ever since Pont-Neuf you've
been jumpy", "Before you answer...", "the last person aboard I'd trust"),
where a search adds rows and marks a moment only if the model is sure of one.

## 4. Retrieval, without a character model

Wren's 26 questions, each heard by Mara (`build_character_memory_context`
with the question as the asked lane), routing off and on; the planted answer
counted when its row is anywhere in Mara's packet, the routed moment when the
marked row is the planted one.

| round | change | planted answer in the packet (24 answerable), off / on | marked moment right | unanswerable left unmarked |
|---|---|---|---|---|
| 1 | first build | 18 / 22 | 16 of 21 | 1 of 2 |
| 2 | tags decide `met`; a found moment is confirmed; a named person's earliest rows reserved; the surest moment for before/after | 18 / 24 | 17 of 21 | 1 of 2 |
| 3 | walk floor 0.8; near ties to the earlier; an act narrowed only by a person the question names, a place only when asked about being there | 18 / 24 | 19 of 20 | 2 of 2 |
| 4 | the review's fixes (§7) -- the code committed | 18 / 23 | 19 of 21 | 2 of 2 |

Round 4 is the committed code. Its one new miss is the decision model's
noise, not a rule: "what did you do right after Tobin told you about the
grain?" read the confession 0.97 and an earlier scene of his at the granary
0.91 on one asking, and close enough on the next to tie -- and a tie goes to
the earlier (the rule that keeps "right after the mill fire" on the fire,
0.92 against the dawn after it at 0.93). Its repeats agree to about +-0.03;
the two rules cannot both hold where the model itself cannot tell.

Each change answered a measured miss: "Oren's very first words" (the meeting
was not among the 40 Oren rows nearest the question -- every one a later "I
met Oren..."), "the first time you lied to Ilse" (a childhood row at 0.53
beat the lie at 0.95 under a bar of 0.5), "when did you first see the river
serpent?" (there is none; Wren's arrival was the first row with the one
asking in it, and the green lights on the river read 0.50 and 0.64), "when did
you last fix the Heron's rudder?" (the ferry's name read as a place). The one
remaining miss is "what happened right before you found Tobin in the loft?":
one discovery among dozens of near-identical night scenes of Tobin in the
boathouse; every wording tried ranked a later scene above it.

## 5. Chat 74, the miss that started this

On a copy of the owner's database, after the about backfill the server runs
at startup, the Doctor's own ponder from 2026-10-05 ("The night I first met
Hinami -- her very first words to me, the scene, where we were, what
happened"): routing off brought back turns 2, 54, 62, 61 and 40; routing on
routes it earliest / met / Hinami, refuses her first tagged row (the Doctor
landing beside her, no words yet, 0.15), walks her own rows, and marks turn
1 -- "Hick!", then "W-who are you?" -- at 0.91, with turns 2-4 beside it.

The Doctor asked the two original lines (the player's, "What was the very
first thing I ever said to you?" and "what did I tell you about Kaa Sama?"),
his step alone on the same copy:

| arm | his first-words answer |
|---|---|
| lookups off, routing off (as the owner plays) | right: "Hick... and then 'W-who are you?'" |
| lookups off, routing on | right |
| recall emptied, lookups on, routing off | right, after two ponders (the second "the young woman I landed on"), 91 s |
| recall emptied, lookups on, routing on | stalled -- no lookup this time ("that's the bit that tells you whether I was paying attention"); the Kaa Sama line after it pondered and answered word for word |

Read honestly: with the about backfill the server now runs at startup, his
ordinary recall already reaches her first words -- the turn-1 row calls her
"the young woman", and only the tag ties it to her -- so routing is not what
repairs chat 74 in play. It repairs the ponder itself: the same question
asked of his memory comes back with the moment marked instead of without it.
Whether a mind calls the lookup at all is the model's own, here as on
2026-10-05.

## 6. The character

Wren's 26 questions asked of Mara, one fresh beat each at turn 312, on the
owner's character route (NanoGPT `z-ai/glm-5.3:thinking`, reasoning medium,
the owner's `tes` preset card) with the owner's decision model: Wren's line
built as the Director would interpret it, the engine's own deterministic
perception run on it, then Mara's step (`compute_step`), nothing committed.
Four arms, 104 answers, graded blind by three readers each (the arms under
shuffled letters, the planted rows beside the question), the majority kept.
The arms ran on round 3's code -- before the review's fixes, which round 4
shows leave retrieval where it was.

| arm | lookups | routing | correct | first/last (16) | before/after (4) | content (4) | nothing to find (2) | invented details | median seconds | prompt tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| A | off | off | 18 (+3 partly) | 12 | 1 | 3 | 2 | 6 | 28 | 22.0k |
| B | off | on | **23** (+2 partly) | **15** | 2 | 4 | 2 | **1** | 25 | 22.6k |
| C | on | off | 19 (+4 partly) | 12 | 2 | 3 | 2 | 4 | 21 | 26.3k |
| D | on | on | **22** (+2 partly) | **15** | 3 | 3 | 1 | 3 | 22 | 23.5k |

- **Routing turned 5 more answers right with lookups off (the owner's
  play) and 3 with them on, and cut invented details from 6 to 1.** The
  difference is where the order lived: the first night at the inn (A wrong,
  B right), the last visit to the mill (A wrong, B right), the first noises in
  the loft (A wrong, B right), what Mara did right after Tobin's confession
  (A, B and C wrong, D right).
- **The lookups went almost unused**: no lookup at all with routing on, one
  ponder and five expands across 26 questions with it off. The heard
  question's own lane already held the answer -- routed, the moment marked --
  in 21 and 22 of 26 packets; as on 2026-10-05, a mind looks things up when
  its packet lacks them.
- **The one harm**: "what happened right before you found Tobin in the loft?"
  -- §4's remaining miss -- marked a later night, and arm D told that night.
  Arm A got it wrong too (with invented details); arm C got it right.
- **Errors routing did not touch**: all four arms dated finding Tobin to "the
  storm night" (when he slipped in, 35 turns earlier) -- the moment was
  marked right in B and D, and Mara still merged the two nights in the telling.
- **The cost**: 0.6k prompt tokens a question for the marked moment and its
  turns, no measurable time (the router's request runs beside the ponder's
  grade; a routed ponder took 0.4-1.3 s in §4). OpenRouter, where the decision
  model runs: about $0.99 for every probe, retrieval round and character call
  in this document together.

## 7. Reviewed

Three adversarial readers (correctness, the engine's rules, failure modes and
cost), each finding put to a skeptic: 21 of 26 findings held -- several the
same defect seen through two lenses -- and all are fixed in the commit, among
them a module global swapped under parallel minds (now a
parameter), a place answer marked with a person, a first-heard moment
confirmed with a question that sets "only talked about" aside, a Japanese
name matched inside another word ("オレン" in "オレンジ"), a lookup's mark
leaking into a later lookup, a found moment lost to a cut by time, and a
first meeting only HEARD never asked about (a tag is sight alone since
b824a8a2). Five were refuted, the word-list concern among them. Every rule
has a test that fails without it: 31 deliberate breaks, 30 caught; the one
left is equivalent (a marked row is always delivered first, so a later
lookup sees it as a pointer carrying only its own mark).

## 8. Replicated: 82 questions, three runs a side

The owner, on §6: "22 vs 23 feels like it could be noise, how might we
strengthen this?" -- and the lookups are "mostly meant as an aditional tool
incase the character decides it needs more info to make a deciision", so the
comparison that matters is routing on against off with lookups off (A
against B). §6 was thinner than its table looks. Question by question, B
was right where A was not on 5 and A where B was not on none -- an exact
McNemar p of 0.06 on one run an arm -- and the lookup arms (B against D)
split 2 to 1, p = 1.0. The graders were not the noise: all three agreed on
102 of 104 answers (Fleiss κ 0.96). What was missing was questions and
repeats.

So the measurement was repeated where it is cheap and carries no character
model's sampling -- retrieval -- on three times the questions:

- **56 new questions** over the same bank, written in five lanes (people,
  places, acts, just before/after, controls), each lane's questions read
  against all 310 turns by an adversarial reader who tried to find an earlier
  first or a later last, then checked by code against the bank's `seen` and
  `location` (three dropped: one by its reader, two by code -- each a "first
  met" that was really an act). With the original 26: 54 first/last (20 acts,
  15 places, 13 meetings, 6 first-heard), 15 just before/after, 13 content
  (two use "first" in a sense that is not time -- "whose orders do you put
  first"), 5 with nothing to find, 4 answered by the seeded past ("how did
  you and Ilse meet?", "how far back do you and Aldous go?").
- **Three runs a side**, routing on and off, each on a fresh copy of the
  bank, every question in one fixed order; `tools/chrono_bench/run.py score`
  compares the sides question by question.

| | routing on | routing off |
|---|---|---|
| planted answer in the packet (77 answerable) | 73, 73, 72 | 65, 65, 65 |
| marked moment right | 47, 47, 45 | -- |
| marked moment wrong | 9, 10, 12 | -- |
| nothing to find, left unmarked (5) | 4, 4, 4 | 5, 5, 5 |

- **The packet difference is not noise.** Taking each question's majority
  across its three runs, 8 questions had the planted answer only with routing
  and none only without: exact McNemar p = 0.008. The runs agreed with each
  other on every question but one (Q14, one run in three), so the decision
  model's own variation (about ±0.03 a memory) barely moves retrieval: the
  noise in §6 was the character's and the sample's, not Jev's.
- **The marks are where the harm is.** Ten questions are marked wrong in
  every run (one more, "the last words you said to Oren", in two of three).
  Nine of the ten have an answer, and in eight of those the planted row is
  still in the packet -- so a mind is pointed away from an answer it holds,
  which is how §6's one harm happened. They fall in four classes:
  - *just before / just after: the wrong moment* (5 of 15 such questions).
    The moment is the row the model is surest of among the 24 nearest the
    question, and a lookalike wins when the moment's own row is not the most
    distinctive: the morning after the storm anchored on turn 5 (rain on the
    first crossing), the chest carried to the chapel house on the mill-fire
    night, "the evening before Oren left on the Moth" on turn 166, the night
    before the first frost on 299 (inside the answer, not the frost), and §4's
    loft night (252).
  - *who the question is about*: "when did you meet Tobin's mother?" routes
    to Tobin and marks his first meeting -- a question nothing answers,
    answered; "how far back do you and Aldous go?" marks a story turn where
    the answer is the seeded past.
  - *which place*: "the chapel of the Drowned Saint itself, not Ilse's chapel
    house" marks turn 237; "when were you last up in the loft yourself?"
    routes as an act with Tobin and marks a night he comes DOWN the ladder.
  - *the moment told about*: "the last lie you told Ilse" marks 211, the
    inference that thinks back on it, not 210, the lie (the span still holds
    210). The decision model reads a memory that only talks about an act as
    the act -- the same reading §9's disputes show 34 times.
- **Not yet measured**: whether the wrong marks mislead a character as often
  as the extra packet hits help one. §6 says they mostly do not (invented
  details fell from 6 to 1 with routing), on the 26 questions that had two
  wrong marks; on these 82 the character run is the next measurement -- arms
  A and B, about $1.10 of the decision model a run of both (§6's calls cost
  about $0.0067 each) -- and the four classes above are its candidates to fix
  first.
- **The cost**: the six retrieval runs and a smoke test took $0.79 of
  OpenRouter credit (about $0.0016 a routed or unrouted ponder; $0.50 was the
  estimate), leaving $2.57.

## 9. The runs as training data

The owner, the same day: "The best option would probably be to finetune a
small decision model maybe 4 or 9b parameters specifically for sonder. but
for now using jev is fine" -- then "build a training data file for the day we
decide to do a fine tune". §8's runs were the first to keep their decisions
(`decisions.capture`, `docs/guides/DECISION_TRAINING_DATA.md`): 76 MB of
requests, 15,228 distinct (state, question) examples, and -- because the bank
plants its answers -- gold on every moment check the readers' verification
covers: 413 `memory_moment`, 37 `memory_heard`, 13 `memory_anchor`.

- **The teacher, where gold can say**: Jev agreed with 379 of 413 moment
  checks, 37 of 37 first-heard checks and 10 of 13 anchors.
- **The labels, where the teacher disagreed**: all 43 disagreements (with the
  router's) went to three blind judges, shown only the state, the question and
  its options. 40 labels stood; the misses were Jev's -- a memory that only
  talks about an act read as the act (Bram: "Pin's quiet. You've done it
  already?" as the rudder being fixed), "lantern" as the Lantern Inn, the mill
  seen from mid-river as being at it, a thought back on a lie as the lie
  (which is §8's wrong mark on "the last lie you told Ilse"). 3 were
  relabelled, all router tuning labels that said "no one in particular" for a
  question naming someone.
- **What a character's beat asks**: one Saltmere beat, captured whole, was 11
  requests and 474 questions (memory grades 124, moods 40, then the act,
  change, impact and speech checks), 0.6 MB. Gold reaches only the memory and
  route checks among them.

## 10. How the found moment is shown: tested, and not the bottleneck

The owner: "Have we tried adjusting how we give the results to the llm? Or I
mean how we present" -- then, "Maybe it exist in its own section with a
header 'Potentially answers question'". It had not been tried. The mark was
one field (`in_time`) on one memory in a payload of about 86,000 characters,
and where recall had already delivered the found row the mark went on
recall's copy: of the 173 marks in §8's runs, 82% sat outside the question's
block -- among the 30 recalled memories (69%) or the recent turns (12%) --
while the turns around the moment went to the question's block, so the label
"what came just before it is beside it" was false there. And every row a few
hours either side of a moment three weeks back read "about 3 weeks ago". Time
is exact underneath (turn order and `encoded_at_seconds`); `memory_time`
rounds the gap to NOW on purpose, so the order the search computed was lost
only in the handoff.

Tested on frozen requests. Each question's real character request (routing
on, lookups off) was captured once, stopping before the call; three
presentations were built by code from the same frozen payload and sent to
the owner's character route (NanoGPT `z-ai/glm-5.3:thinking`, temperature
0.8) through the engine's own call (`agents.common._agent_json`), with no
read-back; three blind graders per answer as in §6, unanimous on 385 of 410.

- **A**: as the engine sends it.
- **B**, the owner's: the found moment and its turns moved into ONE section,
  `potentially_answers_question`, right after the question's block, in time
  order, each row's place against the found moment in the clock's coarse
  words ("about 2 hours before the found moment").
- **C**: B under an asserting header, `answers_question`.

| run | correct | partly | wrong | invented details |
|---|---|---|---|---|
| A1 | 61 | 12 | 9 | 17 |
| A2 | 58 | 12 | 12 | 20 |
| B1 | 60 | 12 | 10 | 24 |
| B2 | 61 | 13 | 8 | 21 |
| C1 | 56 | 16 | 10 | 22 |

- **No measurable difference**: 121 against 119 correct of 164 (B ahead on
  10 questions, A on 9; sign test p = 1.0). Two runs of the SAME payload
  flipped 13 to 15 questions; A and B differed on 16 of the 59 routed
  questions -- the presentation moved answers no more than re-rolling did.
  On the 23 questions the router left unrouted, where A and B were the same
  payload, 3 differed.
- **Leanings, none significant**: just before / just after, 18 against 14 of
  30 for the section (4 questions to 1 -- the class where the split was
  worst); the hedged header 60 against the asserting one's 56; invented
  details 45 against 37 (more in B on 15 questions, A on 9, p = 0.31), all on
  routed questions -- a section may invite elaboration around what it holds.
- **Where the misses are**: 12 questions no run of any presentation got
  right, and every cause is upstream of presentation. The wrong moment found
  (the loft night, the chest carried to the chapel house, the evening before
  the Moth); questions never routed (two just-befores, and "how did you and
  Ilse meet?"); plain misses (where Tobin was hidden, anything named after
  Petra, the first curfew load, the first missing bread, the last food given
  Tobin); and "when did you first meet Tobin?", which all five runs tell as
  the storm night with the right memories in front of her -- §6's two nights
  told as one, which no presentation reached.
- **Cost**: freezing the 82 requests took about 7.7M tokens of
  decision-model input (about $0.32: a beat asks the decision model eight
  requests before the character is called, not one), and the 410 character
  calls about 9-10M input tokens of the owner's subscription. The harness,
  the frozen requests, the answers and the grading journal are kept outside
  the repo in the main checkout's ignored output folder
  (chrono_bench_presentation_2026-10-06).

So the presentation stays as it is, and the work goes upstream, to the
classes in `docs/UNBUILT_CHARACTERS.md`. The one thing presentation still
owes is honesty: the label promises "beside it" where the layout does not
deliver it.
