# The bare character card, replayed against the full card (2026-09-27)

**Question.** The owner, 2026-09-26: "I truly want an as bare bones
character prompt as possible. That still basically does the same thing
thanks to jev... except the character is now mostly reasoning about being
the character it's been given." The bare card (`character_contract: bare`,
`DESIGN_JEV_CHARACTER_PASS.md` § The bare contract) asks the character only
for what a character can write -- what it is going for and what it resists,
what it does in order with a short why in its own words, how it carries
itself, what changed in it, what it makes of the people here, a note to
itself -- and the decision model (Jev) reads everything else back after the
call. Does it still do the same thing? And, asked on 2026-09-27, does the
owner's layout -- "(Character sheet) (Memories) (current event) (Character
prompt)", the situation carrying the mood, notes and mind models before
perception -- do better than the card as the system message with the
payload after it?

**Answer.** Yes, and faster. On 20 replayed beats the bare card did as much
as the full card and read as well or better, at a fifth of the call time
(median 19.8 s against 88.6 s) and a sixth of the output; what needed
fixing was the booking, which five rounds brought within reach of the full
card's except for beliefs (touched about three times as often). The why
must come last: put first, it swallowed the turn on 7 of 20 beats.

The owner's ORDER is better than today's layout, and where the card sits
decides what it costs. Sheet first with the card last read best of the
two in round five (two blind judges, 12 of the 17 beats they agreed on)
but ran past its turn and wrote inner states into acts twice as often. Kept
as the system message, with the sheet, the memories and the moment in the
owner's order after it (round six, "sectioned"), it ties the sheet-first
layout on mean rank for both of two fresh blind judges (1.90 each; today's
layout 2.20) with the fewest faults of the three (5 and 3, against 9 and 7
for sheet first and 6 and 5 for today's), no empty beat and no step that
held only a why. The recommendation is the sectioned layout. The time is
the same for all three: one run's speed on this route is not a property of
its card (round four's exact condition ran at a median 84 s once and 17 s
the next time).

Two engine defects were found and fixed on the way (a feeling named twice
in the feelings block; decision-model shards missing from the call ledger),
and one exposure is registered for the owner: under the bare contract, what
a character writes in `do` is what others perceive, so a motive written
there reaches them.

## Setup

- **Beats.** Copies of the four test stories' databases (`betrayal`,
  `homecoming`, `lie`, `rival`, played with capture on for the affect work),
  five evenly spaced `character_major` captures each: 20 beats, the same 20
  every round. Each beat's system prompt and payload are rebuilt from
  `llm_capture`/`llm_blobs`.
- **Arms.** Round one: the full card exactly as captured, against the bare
  card with the gated sections the payload calls for. Every later round: the
  bare card alone. The decision model asks its before-call question (does
  what just happened change what a recalled memory meant?), the character
  model answers, the decision model reads the reply back, and
  `compile_bare` types it exactly as `agents/character.py` does.
- **Models.** The character: GLM 5.2 thinking (`z-ai/glm-5.2:thinking`) on
  NanoGPT, the owner's subscription, one request at a time (the owner: "Nano
  may get upset with paralel runs"). The decision model: `typesafe/jev-1.13`
  on OpenRouter -- $0.25 over all six rounds, read off the balance ($5.29 to
  $5.04; the call ledger could not count it, see below).
- **Instrument.** `tools/character_bare_replay.py`; `--layout` and
  `--feelings` from round five (the captures predate the feelings block, so
  the replay computes each beat's feelings with the engine's own affect
  pass).
- **Reading.** Every round read side by side as fiction. Round five and six
  were also judged blind by two judges each (Claude; the owner's rule against
  Claude graders covers NSFW chats, and these four stories are not), who saw
  each beat's character brief, what reached
  the character, and the replies' conduct -- lines, acts, recalls -- in a
  shuffled order, and never which arm wrote which.

## The rounds

| Round | What changed | Beats | Median | Mean | Past 60 s | Output tokens | Reasoning chars | Lines | Acts | Ponders | Words spoken | Empty beats | Why-only steps | Dispute shown |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1, full card | -- | 20 | 88.6 s | 93.4 s | 14 | 6,616 | -- | 1.65 | 1.80 | 0.05 | 29.8 | 0 | -- | -- |
| 1, bare | the bare card (d99a0807) | 20 | 19.8 s | 25.7 s | 1 | 1,171 | 2,246 | 1.20 | 1.50 | 0.80 | 29.6 | 0 | 3 | 13 |
| 2 | booking tightened (aeef908a) | 20 | 20.3 s | 32.8 s | 3 | 1,433 | 3,373 | 1.15 | 1.35 | 0.85 | 31.5 | 0 | 1 | 13 |
| 3 | the why first; dispute floor 0.7 | 20 | 17.5 s | 19.9 s | 0 | 1,222 | 2,351 | 0.65 | 0.80 | 0.60 | 19.9 | 7 | 10 | 4 |
| 4 | the why last; `act_private` gone (416eace6) | 20 | 59.4 s | 59.4 s | 10 | 3,938 | 13,612 | 1.80 | 1.70 | 1.00 | 46.4 | 0 | 0 | 3 |
| 4 again | round four's condition, lie + betrayal | 10 | 16.9 s | 37.8 s | 2 | 1,020 | 2,356 | 1.00 | 1.00 | 0.90 | 30.2 | 1 | 1 | 2 |
| 5, today's layout | each beat's feelings given | 20 | 21.1 s | 36.6 s | 5 | 1,627 | 4,284 | 1.20 | 1.40 | 0.75 | 25.6 | 0 | 2 | 3 |
| 5, sheet first | the owner's layout, feelings given | 20 | 24.0 s | 37.6 s | 4 | 1,734 | 4,800 | 1.60 | 1.20 | 0.80 | 37.1 | 1 | 1 | 4 |
| 6, sectioned | the card as the system message, then the owner's order | 20 | 17.3 s | 28.3 s | 2 | 1,378 | 3,031 | 1.45 | 1.35 | 0.80 | 34.2 | 0 | 0 | 4 |
| 7, notebook | sectioned, with the notebook | 20 | 31.3 s | 50.6 s | 4 | -- | -- | 1.05 | 1.20 | 0.85 | -- | 0 | -- | -- |

Lines, acts, ponders and words are per beat; output tokens and reasoning
characters are medians. Input stayed at 15-16k tokens in every bare round
(the full card: 20.7k).

What the reply filed, over the 20 beats (the full card: what its own model
wrote; the bare card: what `compile_bare` typed from the decision model's
read-back):

| Round | Memory effects | Intention ops | Belief touches | Readings of people | Associations | Relationships |
|---|---|---|---|---|---|---|
| 1, full card | 11 | 15 | 12 | 30 | 7 | 11 |
| 1, bare | 165 | 57 | 41 | 34 | 13 | 12 |
| 2 | 20 | 26 | 30 | 34 | 14 | 14 |
| 3 | 20 | 20 | 34 | 23 | 11 | 12 |
| 4 | 19 | 39 | 34 | 31 | 11 | 13 |
| 5, today's layout | 20 | 22 | 34 | 26 | 12 | 13 |
| 5, sheet first | 18 | 30 | 37 | 31 | 15 | 15 |
| 6, sectioned | 19 | 25 | 35 | 27 | 13 | 14 |

## Round one: the bare card against the full card

The bare card answered in a fifth of the time (median 19.8 s against 88.6 s;
14 of the full card's 20 calls ran past a minute, 1 of the bare card's) and
wrote a sixth of the output (1,171 tokens at the median against 6,616). The
decision model's two passes took 0.4 s each at the median, about 140
questions a beat.

It did the same amount -- 1.2 lines a beat against 1.65, 1.5 acts against
1.8, 29.6 words spoken against 29.8 -- and read as fiction, side by side, as
well as the full card or better on most beats. Anselm, the surgeon, noticed
the letter his captain had pocketed unread; Wren's lines came out of her own
payload; at `lie` 98 Margit owned what she had said where the full card had
her deny it, and at 126 stayed silent against her own want. It shared the
full card's two faults: an act that assumed its own success (Isolde's long
stretch at `rival` 168), and acts that stated their outcome.

What it got wrong was the booking, not the character. Asked of each
delivered memory in turn, the decision model found one that shaped the act
in 8 of the 16 a beat offered: 165 memory effects where the full card wrote
11, with intentions 57 against 15 and beliefs 41 against 12. And two lines
went "to you" -- perception labels the observer "you", and the addressee
question offered it.

## Rounds two to four: the booking, and where the why goes

**Round two** (aeef908a) asked one memory-effect question a beat -- acted
on, pushed against, or none -- and memory effects fell from 165 to 20. An
aim's standing now moves only on something that just happened (intentions
57 to 26), and beliefs are asked as "clearly bear this out, cast doubt on
it, or overturn it" (41 to 30). The addressee is asked per person present,
so a line can go to several ("Luca -- with me. Anselm, go.": 3 such lines),
and never to the speaker (0).

`act_private` -- does the act's text carry anything a stranger could not
see? -- flagged every act of rounds one and two (30 of 30, 27 of 27), where
about a third carried a motive or an inner state. A check that fires on
valid output measures nothing, and it was retired (416eace6).

The dispute section shipped whenever the decision model gave a recalled
memory a yes-share of 0.5 -- 13 of 20 beats. No share reached 0.8 (the
highest was 0.77); at a floor of 0.7 the section ships on 3-4 beats a round.

**Round three** put each step's `why` before its `say`/`do`/`ponder`, and 7
of 20 beats came back with no conduct at all: the model wrote its whole
deliberation into the first `why` and stopped. The acts that did come were
cleaner (about 2 of 16 carried something inner, against about 9 of 27 in
round two), but a shape that can swallow the turn cannot ship.

**Round four** put the why last again: no collapse, and the fullest conduct
of any round (1.8 lines, 1.7 acts, 1.0 recalls, 46 words spoken a beat).
Read beside round two it is mostly more rather than worse -- Emil takes the
stretcher's front rail himself; Margit asks herself whether "true in the
letter, and aimed to blind him in the spirit" was the first lie of her life
-- though a man alone speaks aloud twice, and a few acts slip into the
imperative ("Pull back from the doorway..."), which the renderer's name
peeling does not mend.

## Round four's slow half was the provider

Round four ran at a median 59.4 s, 10 beats past a minute, its slow half
reasoning 13-27k characters where round two's reasoned 1-7k. Between the
two the card changed by a few words and the dispute floor rose -- so round
four's exact condition was run again on the ten `lie` and `betrayal` beats,
where it had been slowest (8 of 10 past a minute, median 84 s). The second
time: median 17 s, 2 of 10 past a minute. The same card and payloads
reasoned several times longer in one run than in the next. Timing on this
route is a distribution, not a number: a comparison needs repeated runs, and
one round's speed, fast or slow, is not a property of its card.

The two beats that ran slow twice without feelings, `lie` 35 and 75 (84 s
and 141 s), ran 22 s and 20 s with each beat's feelings given. That points
at the feelings shortening the deliberation, and is two beats.

## Round five: the owner's layout

Both arms carried each beat's feelings, computed by the engine's affect
pass. Today's layout sends the card as the system message and the payload
after it; the owner's sends the character sheet as the system message, then
what the character remembers and holds -- memories, knowledge,
relationships, readings of people, beliefs, aims, what it said and did
lately, its last choice and its own notes, oldest to newest -- then what is
happening now with its feelings, then the card, last.

**The time is the same**: median 21.1 s against 24.0 s, mean 36.6 s
against 37.6 s -- inside the spread round four showed. NanoGPT cached
nothing more for the sheet-first prefix (median 229 cached tokens against
10).

**The conduct reads better.** Two blind judges agreed on 17 of the 20
beats, and on 12 of those preferred the sheet-first reply (judge one 15 of
20 overall, judge two 12 of 20). Reading it unblinded agrees: Emil's cover
story for the letter in Luca's hands ("That's mine, lad -- my girl's
letter"); Anselm stopping his surgery at the attempt where today's layout
ran on to the bandage; Aurel pondering the nine-year-old ruling he fears he
got wrong; Margit exact about what she said -- "whether 'not in this room'
was a lie or an evasion" -- where today's layout had her confess a lie the
story's facts do not support; Celestine keeping her standing rule with
Isolde before she sings a rival composer's line.

**It keeps its turn less well.** The same judges found twice the faults in
the sheet-first replies -- 14 and 13 against 7 and 4 -- mostly running past
the point where someone else must answer (6 beats against 2-3, both judges
the same six: Margit's three speeches at `lie` 98, Celestine's whole exit to
supper at `rival` 79, Aurel laying out his dockets at `lie` 3 before he has
seen who is in the room; today's layout's two were the whole surgery in one
beat at `betrayal` 139 and a conversation begun with a stranger at
`homecoming` 5) and acts carrying what no watcher could see (4 beats against
0, both judges the same four: "circles the junction ... -- the gap he knows
the enemy watches"). And one sheet-first beat, `homecoming` 25,
came back with no conduct: the reasoning settled on Aldo walking to the
boat and saying "let me look at her", the sequence was empty, and the note
said he had.

## Round six: the card kept as the system message

Round five changed two things at once: the ORDER (the sheet, then what is
held, then the moment) and the CARD's place (out of the system message, to
the end of the user message). Round six separates them: the card stays the
system message, and the user message carries the owner's three sections in
his order -- "WHO YOU ARE", "WHAT YOU REMEMBER AND HOLD", "WHAT IS HAPPENING
NOW" -- with each beat's feelings. Two fresh blind judges ranked all three
layouts, beat by beat, shuffled (today's and sheet first are round five's
replies, ranked afresh beside the new ones):

| Layout | First place (judge three / four) | Last place | Mean rank | Faults (judge three / four) |
|---|---|---|---|---|
| Today's layout | 2 / 3 | 6 / 7 | 2.20 / 2.20 | 6 / 5 |
| Sheet first, card last | 10 / 9 | 8 / 7 | 1.90 / 1.90 | 9 / 7 |
| Sectioned, card as system | 8 / 8 | 6 / 6 | 1.90 / 1.90 | 5 / 3 |

The two judges named the same best reply on 16 of 20 beats: sheet first 9,
sectioned 6, today's layout 1. The owner's order is what the judges
preferred; the card's place is what the faults follow. Sheet first wins
more beats outright and loses more too, and runs on most: 8 overlong calls
across the two judges, against 5 for today's layout and 2 for sectioned.
Both judges put its overruns at `lie` 98 (three speeches where one would
wait for an answer) and `rival` 79 (the whole exit to supper) last; the
whole extraction and dressing in one beat, at `betrayal` 139, was today's
layout again. Sectioned keeps the order's gains with the fewest faults of the
three, and in round six no beat came back empty and no step held only a
why. It is not clean: its `do` at `betrayal` 3 still says the route "leads
through the gap he has already marked for the dead drop" -- the observable
floor below is needed under any layout. Median 17.3 s, 2 beats past a
minute; inside the spread, so no faster, and no slower.

Building it into the engine is small: the first request and its
same-request re-asks (the empty-object and truncation rungs of
`complete_validated_json`) take the rendered sections as the user message,
while the repair and fallback rungs keep wrapping the payload dict as
`original_request`; the section builder moves from the tool into
`agents/character_bare.py`.

## Round seven: the notebook

The owner, the same day: "A hypothesis is basicaly a note that can be
updated or refuted"; "I needs stable core where a characters keeps track of
what it thinks about things and other people and how it thinks they think";
"there should be a general note taking system for things the llm wishes to
keep track of"; "There should also be an active concerns section that has a
method of resolution". Built as the notebook (`mind/notebook.py`,
`DESIGN_JEV_CHARACTER_PASS.md` § The notebook) and replayed on the same 20
beats in the sectioned layout with feelings, each beat's notebook rebuilt
from what its capture held (13 of the 20 held notes about people, 2-3
subjects each; all 20 held 3-7 concerns; none a project).

A network outage mid-run lost four `lie` beats to DNS failures and a
stalled stream, and one `rival` beat took 340 s; the `lie` beats were run
again and all 20 stand. What the characters wrote, and where it landed:

| What | Count |
|---|---|
| New notes about people | 7 (6 of them what someone thinks: second-order) |
| New notes about things | 1 |
| Held notes revised by id | 10 |
| Held notes nudged by what the beat bore out | 8 (all borne out) |
| Held notes struck | 0 |
| Concerns ended / new | 28 / 30 (mostly rewordings, now carrying what settles them) |
| Reminders kept | 4 |
| Intentions (commitments with no end to name) | 6 |
| Projects adopted | 0 |

The notes read as the characters' own. Aldo revises his three notes on
Wren and the stranger ("She's confident and eager -- she read the tide
right. She can handle the Tern. He needs to let her."); Anselm rewrites his
on Varga ("not the action of a man who intends transparent investigation
... I am not bound") and adds what he now thinks Varga is doing; Celestine
revises her readings of the young composer and of Isolde and adds three of
what Tomas is about ("too specific to be mere flattery; I mean to test
every word of it"); Emil gives each worry what would end it ("until Anselm
confronts him directly or the watching stops") and strikes the burial --
"settled -- spoke at the grave".

Three things needed fixing, all fixed before this was committed:

- **The kind question read a plan as someone's goal.** "Must be seen at
  the site before briefing" was filed as a forecast about "Pietro's death
  and today's plan" at 0.9. The options named "someone", which took in the
  character itself. Probed on Jev (`tmp` probes, 9 and then 13 notes with
  their expected kinds): the old wording scored 4 of 9; naming ANOTHER
  person for the person kinds, and saying what separates the rest -- a
  worry is what the world will settle, a commitment what you will keep at
  until it is done, a note to keep a fact or one errand of your own --
  scored 11 of 13, where the next best scored 9.
- **Concerns ballooned**: rewording a concern is how it carries what settles
  it, and the characters wrote paragraphs, plans inside. Capped
  (`CONCERN_CHARS` 240, `UNTIL_CHARS` 120).
- **New entries came with invented ids** ("n5a1", "new1"): handled as new,
  but one could have landed on a real reminder's `r1`. The card now says a
  new entry has none.

The payload got smaller: the notebook replaces four renderings of the same
stores, a median 1,218 characters a beat (from 3,352 smaller to 1,028
larger, the larger where there were no notes to replace and the concerns
gained ids). The conduct was thinner than round six's on the same beats --
21 lines and 24 acts against 29 and 29 -- inside the spread repeated runs
of one condition have shown (1.0-1.8 lines a beat), so one run does not
say whether the notebook costs conduct; the beats that wrote the most in
their notebooks kept or gained conduct, and the largest drops came on beats
that wrote nothing in it. Median 31.3 s, 4 beats past a minute, the
outage's among them.

## Round eight: the notebook carried forward, and the conduct question

Two things round seven could not say. Whether the notebook costs conduct:
each condition was run again on the same 20 beats (sectioned, feelings).

| Run | Lines | Acts | Median call |
|---|---|---|---|
| Without the notebook (round six) | 29 | 29 | 17.3 s |
| Without the notebook (again; 1 beat failed) | 29 | 23 | 35.9 s |
| With the notebook (round seven) | 21 | 24 | 31.3 s |
| With the notebook (again) | 31 | 31 | 37.6 s |

The spread inside each condition is wider than the gap between them: no
cost measured. (The slower medians are the provider's, as in round four.)

And what a mind does with a notebook it keeps: the `--chain` replay walks
one character's captures in order, each beat's compiled output applied the
way commit applies it, so the notebook it reads is the one it wrote. Margit
(`lie`, 18 captures, 16 read back -- two beats failed on the provider) wrote
20 new notes, revised 21 by id and had 21 nudged; Anselm (`betrayal`, 16)
wrote 6, revised 6, changed a reminder 12 times, had 8 nudged, and took up
one project. Four findings:

- **Notes drifted into a log.** "I released him and sent him out the back.
  He did not answer about Wat..." is a record of what happened, which memory
  already keeps; a note is what the character thinks. The card says so now,
  in one line.
- **The note check confirmed nearly everything**: 27 of the 29 nudges were
  "bore it out", several on beats that bore nothing out -- Kit sitting down
  and laying his hands on his knees bore out that Holt had accused Margit of
  lying; three unintelligible fragments of Luca's speech bore out that he
  had brought the patrol news first. First read as the reply's doing (the
  check was asked after the call, with the character's reply and reasoning
  in the state) and moved before the call; round nine showed that was not
  the cause (below).
- **One concern appeared twice, cut at two lengths** ("...he believes I
  lied. I..." and "...he believes I lied. H..."). The notebook view derived a
  concern's id from its whole words; the read-back held concerns cut at 300
  characters -- and "settled when" pushes a concern past that -- so a longer
  concern could never be struck or rewritten by its own id: each rewrite
  added a copy and the held one came back cut. One reader of a concern's
  words now (`notebook.concern_text`), and the concerns are held whole.
  (Concerns are also kept once by the notebook's identity for one; nothing
  close to a similarity threshold would do: two different worries scored
  0.40-0.46 on the engine's similarity, and one true paraphrase 0.455.)
- **A commitment adoption refused was lost**: Anselm's "count the hits" had
  a criterion restating it, which adoption refuses as a task, and nothing
  kept it. What adoption would refuse as circular or crowded out is kept as
  an intention now, what would finish it in its words
  (`affect.adoption_refusal`, the one reader adoption itself uses).

## Round nine: the chains again, with the restorations

The same two chains on fresh database copies, run from a snapshot of the
code: the note check before the call, concerns kept once, a refused
commitment kept as an intention, and the old card's restorations below.

| Chain | Beats read back | Lines | Acts | New notes | Revised | Nudged (all "bore it out") |
|---|---|---|---|---|---|---|
| Margit, round eight | 16 of 18 | 19 | 16 | 20 | 21 | 21 (20) |
| Margit, round nine | 10 of 18 | 15 | 11 | 9 | 5 | 7 (7) |
| Anselm, round eight | 16 of 16 | 21 | 17 | 6 | 6 | 8 (7) |
| Anselm, round nine | 16 of 16 | 28 | 19 | 7 | 14 | 14 (14) |

- **The note check still confirmed everything**: 21 of 21 nudges, and 49 of
  its 57 checks chose "bore it out", before the call. So the reply was not
  the cause. Read against hand labels of those 57 checks (one labeller;
  16 gave a new reason to believe the note, 34 told the mind nothing new, 6
  gave a reason to doubt it, 1 unclear), the check agreed on 24 of 56 and
  called 28 of the 34 nothing-new beats confirmation. Asked of the same
  notes against the beat's events alone, the same wording agreed on 40 of
  56 and called 9 of the 34 confirmation, catching 14 of the 16 real ones;
  two rewordings -- "a new reason to believe this", "how sure are you now"
  -- scored 33 and 30. The whole state carries the note itself, in the
  notebook, and the memories that first supported it, and the decision
  model reads them as confirmation. The check now reads the moment alone
  (`moment_text`); not yet replayed in a chain.
- **Margit's chain lost 8 of 18 beats** (round eight: 2): one provider
  silence, and seven where GLM answered `{}` twice running after an ordinary
  amount of reasoning (446-4,396 tokens), its thinking ending as the good
  ones do ("Let me write the JSON."). Anselm's chain lost none. **Not the
  card**: the exact prompt that came back `{}` was sent four times under
  each condition -- as sent: 2 answered, 2 provider silences; without the
  JSON schema: 1 answered, 2 empty, 1 silence; without the restored
  sections: 2 answered, 1 empty, 1 silence; round eight's card exactly: 3
  answered, 1 empty. GLM thinking on NanoGPT sometimes ends after its
  reasoning with no answer -- `{}` under the schema, nothing without it --
  the same failure as its silences, and on that payload it failed 10 of 16
  calls in every condition. (The schema path injects instructions of its
  own into the system prompt, which the model quoted -- "please default to
  using {"answer":"$your_answer"}", "Ensure to always use "```"" -- and it
  reasoned longer with them on one beat's prompt, 928-7,198 tokens over 5
  calls against 1,024-1,864 over 2 without: too few to say.) The replay
  tool now counts a provider that returns nothing as a failed attempt and
  makes three.
- **The restorations fired.** The speech budget shipped on every beat read
  back, tell variety and tell payoff on 24 of 26, an owed answer on 6, a
  silence on 3; offers and crisis never came up in these captures. Margit's
  11 acts all turned her toward someone -- rightly: every one faces Kit or
  Holt; Anselm's 19, mostly hands at a wound, turned him toward someone once
  (a glance up at Luca) and "cut Luca off" twice, both times by turning and
  walking away while Luca talked -- which does not stop anyone finishing,
  and an interruption truncates the other's line. Probed on those 27 acts
  plus five made-up ones, asking what STOPS someone finishing, with a plain
  "No one.", wrongly flagged 6 real acts where today's wording flagged 11;
  both caught the four made-up interruptions and both still read a
  walk-away as one. Adopted. The body echo came out unpleasant
  on 24 of 25 echoes (-0.16 to -0.93) and about nothing on the other; the
  full card, which never explained the field, wrote small positive
  strengths (0.01-0.4) on 129 of the 135 echoes in the four stories'
  captures, 0 on the rest, whatever the memory.
- **Notes still drift into a log** despite the card line: "Back from the
  captain's quarters -- no iodine in his hands, a half-written letter
  instead" was checked on six beats running.
- No commitment was refused, so the intention fallback was not exercised;
  no concern appeared twice.

## The old card, reviewed: what the bare card had dropped

The owner: "review the old contract, what have we abandoned from it that
might still be beneficial?" Read clause by clause against the bare path:

| The full card | The bare path before | Now |
|---|---|---|
| silence as the other's act, an answer owed, offers, the speech budget, crisis, tell variety, tell payoff (said every beat) | the payload carried each key, unexplained | seven gated sections, each shipped when its key is present (129-243 characters) |
| an act's `look` (the facing, or a sweep) | never set: facing came only from inference | `act_look`, asked of every act |
| an act that cuts someone off (`interrupts`) | speech only | `act_interrupts` over those who spoke |
| a recollection felt in the body (`somatic_echo`) | 0.0 on every beat | `echo_body`, signed |
| a crisis tell no subtler than 0.4 | unenforced | the ceiling held in code |
| mood as coordinates, labels and ledgers in `self.active_state` | sent beside `self.feelings` | stripped: the mood given once |
| a commitment with no slot | lost | kept as an intention |
| a reply the read-back could not read "files nothing" | untrue: the note and notebook writes are kept | the warning says what is kept |

Left for the owner, each a behaviour the full card had and the bare card
does not: navigation and spatial-frame guidance (the frame, exits and run
offers reach the payload under engine key names with no section); learning
an association's breaking (`extinguish`) or a new one -- the read-back only
reinforces a held cue that fired; the self-repetition clause (recent lines
and moves as continuity, "do not reset an offer, question, or conversational
job"); and material effects. None of the restorations is replayed yet.

## What the replay found in the engine

- **A feeling named twice** (fixed, 5d967d68). Where the moment stirred
  nothing, the feelings block's `now` falls back to the strongest past or
  unsettled feeling, and `beneath` listed it again -- on 6 of round five's
  20 beats.
- **Decision shards unrecorded** (fixed, c38ec2f6). A battery over 64
  questions is asked in shards on worker threads, and the call ledger is a
  ContextVar the workers did not inherit: the after-call pass never reached
  it, in the replay or in a live turn's usage.
- **What `do` says, others see** (open, register §6.17). Under the bare
  contract an act's text is its observable: `compile_bare` sets the
  observable to the model's `do` unless the decision model judged the whole
  act inner, and perception hands it to every observer, name-peeled. A
  motive written into `do` reaches them as something they saw. The full
  card has the same dependency with a field of its own (`observable`); the
  bare card merges the two, so the floor leans on the model's cooperation
  -- the thing the firewall says a leak must never do. Both judges found it
  in 4 of the 20 sheet-first replies and in none of today's layout's; round
  two's reading found it in about a third of the acts.
- **A turn that loses its conduct** (open, register §6.17). In 70 why-last
  replies, two beats lost everything they meant to do: one returned an
  empty sequence with a note claiming a line never said (the note is kept
  and shown next beat, so the character would remember saying it), and one
  a single step holding a `why` and an addressee but no act -- Margit's
  intended look at Kit. Three more steps held only a why beside real
  conduct. None in round six's 20.
- **A player one open stair away, unperceived** (a lead, register §1.169).
  At `rival` 168 (turn idx 16) the scene before the beat had the player,
  Tomas Rell, on the stage and Isolde in the orchestra pit, the pit steps
  open between them, and the scene after it had him in the rehearsal room
  behind a closed door; her perception carried two standing rows and no
  trace of him, neither there nor leaving. Every reply -- the full card's in
  the story itself, and all three layouts here -- spoke to him from memory.
  One round-five judge and one round-six judge flagged it as speaking to
  someone absent.
- **Concerns past the fourth were lost on every bare beat** (fixed with the
  notebook). The holding kept four and the compiled state kept only those,
  so a mind with seven concerns -- the replay's held three to seven -- lost
  three each beat. Every concern is now kept; the six the notebook shows are
  the ones checked.

## Open

- The layout: the sectioned one, recommended -- the owner's call, then
  built into the engine (above).
- The observable: a floor for what `do` carries (see above). Proposed:
  split `do` at its clause boundaries, ask the decision model outward or
  inner of each clause (the `act_seen` question, which reads correctly), and
  give observers only the outward ones; `attempt` keeps the whole text for
  the Director.
- A turn that loses its conduct: a card clause ("a step is always something
  you do") or a repair check -- the owner's call, since either is a guard on
  an answer that is sometimes valid.
- Beliefs are still touched about three times as often as the full card's
  model touched them (34-37 against 12) -- held beliefs re-confirmed beat
  after beat -- and intentions 1.5-2 times (22-30 against 15). The note
  check's move before the call is the likely fix for beliefs too; the
  belief revise gate needs rethinking first (register §6.17).
- Acts that state their own outcome, in both cards.
- The notebook: the confirmation share with the check before the call (re-run
  the chains); no note struck in play yet.
- The restorations above, unreplayed; and the four the owner decides.
- The default switch -- the owner's.

## Reproducing

The stories' databases live in the job's scratch directory and go with it;
the instrument does not. On copies of any captured story:

    python tools/character_bare_replay.py --db COPY.db --beats 5 --arms bare \
        --layout sectioned --feelings --notebook --out DIR

One character's captures in order, its notebook carried forward:

    python tools/character_bare_replay.py --db COPY.db --chain "Margit Oldis" \
        --layout sectioned --feelings --out DIR

Route the story's `character_major` role to the model under test first, and
check the decision model's credit.
