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
  after beat -- and intentions 1.5-2 times (22-30 against 15).
- Acts that state their own outcome, in both cards.
- Not carried yet: adopting a project; material effects.
- The default switch -- the owner's.

## Reproducing

The stories' databases live in the job's scratch directory and go with it;
the instrument does not. On copies of any captured story:

    python tools/character_bare_replay.py --db COPY.db --beats 5 --arms bare \
        --layout sectioned --feelings --out DIR

Route the story's `character_major` role to the model under test first, and
check the decision model's credit.
