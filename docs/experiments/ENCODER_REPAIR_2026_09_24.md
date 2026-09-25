# Jev-targeted check and repair of the prose encoder — 2026-09-24

The prose contract encodes a beat in one call, and one call can stop short,
skip an act or write a ledger wrong. On the owner's own traffic, 3 of about
16 resolve calls encoded 0-2 events of a 2,852-5,104 character account; the
owner's latest roll of chat 154 turn 4398 (capture 3998) encoded ONE event
for a 23-sentence departure, so the TARDIS came out `sealed` and nothing the
Doctor said or did after his first act was recorded.

`agents/director_repair.py` (behind `prose_contract_repair`, off by default)
checks the draft and has the encoder repair what a confident check found.
The owner's design: Jev finds the missing events and the ledgers that are
missing or wrong for the sequence of events, builds a targeted encoder for
them -- with the completed ledgers in its context -- and arranges what it
recovered in chronological order.

## The pass

1. The prose is split into sentences (`sentences`: Codex's lossless splitter,
   with a straight quote opening only when it closes in its paragraph), and
   **code** attributes each event to the sentences its own text comes from
   (`attribute`: character-trigram share, plus any sentence the event holds
   as one unbroken run).
2. **Code** finds what is certain: writes the engine's own schema or reader
   would discard (`native_failures`, Codex's preflight on flat events).
3. **Jev** judges, each question carrying its own material:
   - per sentence: an occurrence none of its events (or its neighbours') records;
   - per event and record it writes nothing to (and per part of that
     record): a change of that record's kind;
   - per existing write: wrong for its event.
   "What a record holds" is the encoder card's own contract (the opening of
   `encoder.<channel>`), not the routing question.
4. Only a finding at its threshold builds a job; consecutive missing sentences
   are one job; an uncited sentence between two missing ones joins them.
5. For each flagged write Jev also says whether its change happens at
   another event, and which; when both answers are sure, code moves it
   there and its fix job follows it.
6. The `director_repair` calls answer every job by id -- recovering events
   and mending writes as two calls in parallel -- with the whole draft, the
   numbered prose and the roster of minted things in front of it, and every
   job quoting the sentences that decide it: a flagged mistake is the
   prose's to settle, not the draft's or the check's. A job left unanswered
   or empty is asked once more, alone. Writes to records a call was not
   granted are dropped.
7. Jev places each recovered group among the events of its sentence and its
   neighbours; below 0.5 the encoder's `after`, then sentence order.
8. Only the repaired writes are checked again. Nothing aborts the turn; a
   user's Stop still propagates.

## Data

Eight hand-labeled beats from non-NSFW stories, drafts FROZEN as captured
(the draft call is the baseline call, so the captured answer is exactly what
the pass receives):

| beat | stage | sentences | draft events | labeled defects |
|---|---|---|---|---|
| owner 3975 (154/4398 roll 3) | interpret | 7 | 7 | beach route; the doors' clunk has no sensory event |
| owner 3994 (154/4398 roll 4) | interpret | 5 | 4 | none |
| owner 3979 (154/4398 roll 3) | resolve | 19 | 17 | 1 missing sentence; 4 wrong transit writes; the spark has no sensory event |
| owner 3998 (154/4398 roll 4) | resolve | 23 | 1 | 7 missing sentences (early stop) |
| owner 3880 (154/4398 roll 2) | resolve | 16 | 1 | 12 missing sentences (malformed prose, one empty speech event) |
| r122b 3871 (time-travel test story) | interpret | 6 | 1 | 1 missing sentence |
| r153a 3881 (replay of chat 153) | resolve | 17 | 8 | the ship breaks free and no transit is written |
| r122a 3905 (time-travel test story) | resolve | 20 | 8 | 1 missing sentence; 1 premature pose |

Labels are one reader's; ambiguous items (a cry as a sensory event, an
invitation as an obligation, "It watches.") are excluded from scoring. Jev is
`typesafe/jev-1.13`; the repair runs on the owner's routing (`z-ai/glm-5.2`,
OpenRouter) with reasoning off -- see Limits for the owner's current setting.

## What each change measured (Jev only, 3 runs a beat)

| change | missing event | missing ledger | wrong write |
|---|---|---|---|
| first battery: items named by reference, routing questions as definitions | P 0.22 R 0.32 @0.5 | P 0.23 R 0.25 @0.5 | P 1.00 R 0.06 @0.8 |
| each question carries its sentence / event / write | P 0.72 R 0.55 @0.5 | P 0.07 R 0.33 @0.5 | P 1.00 R 0.83 @0.8 |
| "is it already written" decided by code; encoder contract as definition | P 0.69 R 0.56 @0.5 | P 0.46 R 0.50 @0.5 | P 0.94 R 0.83 @0.8 |
| a record's parts asked by their own definitions | P 0.67 R 0.50 @0.5 | P 0.46 R 0.67 @0.5 | P 1.00 R 0.78 @0.8 |

One battery (8-236 questions) took 0.2-1.3 s, median 0.36 s. Jev's
probabilities rarely pass 0.8, so the thresholds are 0.5 for a missing event
and a missing ledger -- a false alarm costs only a job the repair declines --
and 0.8 for a wrong write, where a correct write sent to be fixed can come
back changed.

Asking the encoder to cite the sentences itself was tried first and dropped:
with `sources` last in the event schema GLM 5.2 opened the beat with an empty
event holding every citation (3 of 3), and with it first it cited nothing (0
of 22 real events). Code's attribution put all 17 events of capture 3979 on
their own sentence.

## The whole pass (24 runs: 8 beats x 3)

| | |
|---|---|
| labeled missing sentences covered after repair | 50 / 66 |
| labeled wrong writes changed | 10-12 / 18 |
| labeled missing ledgers written | 2 -> 4 / 9 (before / after parts shipped whole) |
| false alarms handed to the repair and declined by it | every one |
| repair calls per beat | 1 (the one-retry never fired) |
| wall per beat | median 4.1 s, max 21-25 s (checks 0.25-1.9 s) |

**Corrected 2026-09-25:** the first report said 60/66. That count credited a
missing sentence to any recovered event stamped with its job's sentences, and
a job covering a sixteen-sentence run stamps all sixteen on each event it
returns -- one run recovered two events and was counted as covering six
sentences. Counted by the events' own text (code's attribution), it is 50/66.

The owner's latest roll (3998) went from 1 event to 9-10 in 3 of 3 runs: the
Doctor's two lines with the questions they leave open, his hand leaving the
lever, his turn to the doors, the figure on the beach minted as a person
standing in the surf, the floor's shudder as a sensory event, and the TARDIS
`in_transit` with no invented destination or route. Jev placed the group after
the first event at 0.99.

## After the first report (2026-09-25): the repair's framing, and Jev saying what is wrong

The owner asked whether the repair call was told a mistake was made and to
compare against the original prose. It was not, in so many words: the prose
was in its payload and the encoder core calls the prose authoritative, but
the repair section never said the correction comes from the prose; only an
event job quoted its sentences; a write Jev flagged arrived with no reason.
And the owner: "I don't think it would be particularly hard to get jev to
flag which ledger is wrong." Six versions, the same 24 runs each, scored by
the events' own text:

| version | what changed | missing sentences | wrong writes changed | missing ledgers | median wall |
|---|---|---|---|---|---|
| v1 | the pass as first reported | 50/66 | 10/18 | 4/9 | 4.1 s |
| v2 | every job quotes its sentences; the prose decides a flagged mistake, not the draft or the check | 46/66 | 6/18 | 5/9 | 4.5 s |
| v3 | an event job's own "the draft already records it" clause, strengthened; any skipped job retried | 44/66 | 10/18 | 5/9 | 8.1 s |
| v4 | v3's clause back to v1's; two repair calls in parallel; Jev asked WHAT is wrong as one six-way choice | 41/66 | 9/18 | 5/9 | 5.5 s |
| v5 | each way of being wrong asked as its own yes/no; a write on the wrong event moved by code | 48/66 | 11/18 | 4/9 | 5.7 s |
| v6 | only "does it belong at another event, and which" kept; a moved write keeps its fix job | 50/66 | 8/18 | 5/9 | 4.8 s |

Across six versions the totals moved within +-9 of 66 and +-3 of 18 -- eight
beats and three runs cannot separate them. What the versions did show:

- **Quoting the prose changes what a fix writes, when a fix is answered.**
  In v1 every run wrote the beach route back into all four of 3979's transit
  writes, copied from the draft's others; in v2's one run that answered them,
  none survived. But a repair told each job is a flagged mistake added events
  for false alarms it used to decline, until the event job's own "when the
  draft does record it, say why in `none`" was restored (v2 -> v4). Worded
  more strongly (v3), it declined the one real sixteen-sentence gap in
  3998 in one run of three.
- **Jev says WHICH write is wrong (precision 1.00, recall 0.78 at 0.8) and
  WHERE a misplaced change belongs -- not WHICH condition fails.** Asked as a
  six-way choice it answered 0.24-0.65 and called the transits' wrong value a
  wrong subject; asked as five yes/no questions it said yes to nearly all of
  them (0.52-0.80) for every flagged write; asked which record a change
  belongs in, it named one even for writes filed in the right one. Asked
  which event, it named e5 for the time-travel story's premature pose at
  0.99-1.00 in every run -- code moved it and the repair refined it there --
  and gathered 3979's stray transit writes on the event where the ship
  commits at 0.89-0.94.
- **The repair call skips jobs.** One run answered three of nine and skipped
  the four transit fixes between them; retrying every skipped job, and
  splitting event recovery from write mending into parallel calls, is what
  v4-v6 carry.
- **No wording fixed the beach route.** Every version wrote it back in most
  runs; the engine floor is the reliable fix (see Limits).

## 2026-09-25: the grammar, the declared acts, and the answers dropped in pieces

The owner asked what else would improve accuracy, then "Go ahead" on the two
first tried: the draft without the enforced grammar, and a code check that
every act the cast declared reached an event.

### The grammar truncates the draft

Thirteen captured encoder payloads (the eight labeled beats and five long
resolves of the time-travel test story and the chat 153 replay) re-sent in
three arms interleaved in one process -- `json_schema` (the grammar every
call carried until now), `json_object` (the engine's fallback for a model
that refuses one) and no `response_format` at all -- reasoning off, the
owner's OpenRouter routing, three samples each; the schema and no-format arms
run twice, the second time with the serving host recorded. Coverage is
against the best any sample reached on that beat; an early stop is under
half of it.

| arm | calls | early stops | a declared act left uncited | mean coverage | labeled recall (runs 1, 2) | median / p90 |
|---|---|---|---|---|---|---|
| no format | 78 | 2 | 0 | 0.78 | 0.90, 0.89 | 10.3 / 19.0 s |
| `json_schema` | 78 | 18 | 11 | 0.70 | 0.82, 0.83 | 8.8 / 17.1 s |
| `json_object` | 39 | 14 | 5 | 0.63 | 0.71 | 7.5 s |

By host (run 2): BaseTen stopped early in 5 of 16 schema calls and 2 of 17
without; Fireworks in 2 of 19 and 0 of 19. The grammar costs completeness on
every host, and BaseTen is the weakest either way. Without it, 2 of 78
answers were malformed and the validator re-asked (one took 145 s).

So a role now names its format (`providers.response_format_for`: the host's
per-role choice in the models panel, else a measured default, else the
`default` row, else the engine's choice), and the encoder's measured default
is no format (`ROLE_DEFAULT_FORMATS`). Two calls keep the grammar whatever
the role says (`providers._role_json_mode`):

- **the repair.** Sent free (v7 below), GLM 5.2 answered a sixteen-sentence
  event job by re-encoding the whole beat in the draft's `events` shape,
  after a paragraph of reasoning and with a brace dropped seven levels into a
  transit patch; 3 of 30 repairs failed validation outright and the pass fell
  to 31 of 66 labeled sentences. Its answers bind to jobs by id, so the shape
  is the contract.
- **every rung that rebuilds a broken answer** (`llm_quality.REBUILD_FORMAT`):
  the first attempt had its chance at a complete answer; the rebuild owes a
  valid one.

### Declared acts, found by code

`director_repair.declared_gaps`: every `event_inputs` entry no event names
as its `source_event_id`, located by its own words -- a line's text, an act's
`observable`, then its `attempt`, the player's `raw_text`. On the 40 captured
drafts it held for 3 (3998, and two resolves of the time-travel story that
encoded one event of 14 and 28 sentences), all real; all 7 uncited
declarations landed on the sentence that tells them. A located gap is a
missing-event finding at 1.0 whatever Jev scored, and its job carries the
declaration so the repair writes it under that `source_event_id`; whatever
the pass leaves uncarried is recorded (`declared_left`) and said. Once the
grammar is gone the draft rarely leaves one (0 of 78 above), so this is the
floor for the calls that still do.

### Answers dropped in pieces

Reading why the time-travel story's 26-sentence job lost both its declared
acts found a defect in every version above: the repair answers one job in
pieces -- ten answers all `j1`, or `j1`, `j1b` ... `j1h` -- and
`apply_answers` bound the first piece and dropped the rest as repeats or
unknown ids. Across the 198 whole-pass runs that answered, 30 split an answer
and 192 of 844 returned events were dropped (v4: 70 of 133). Part of what
this document called the repair "stopping short" was the engine discarding
what it wrote. `merge_answers` now joins the pieces of a job in order, the
first piece's `after` placing the group; an id with a digit after a job's id
is another job's, never a piece.

### The pass again, and the new pipeline

| | missing sentences | wrong writes changed | missing ledgers | median wall |
|---|---|---|---|---|
| v6 (the pass as last reported) | 50/66 | 8/18 | 5/9 | 4.8 s |
| v7: the repair sent no grammar | 31/66 | 12/18 | 6/9 | 6.8 s |
| v8: the repair keeps the grammar; declared acts | 43/66 | 9/18 | 6/9 | 5.0 s |

v8 is inside the band the six earlier versions spanned (41-50), and ran before
the merge fix: 7 of its 30 runs split an answer and lost 17 of 115 events.
Declared acts were recovered in 3 of 3 runs of 3998 and of the 14-sentence
resolve, and 1 of 3 of the 28-sentence one -- the two losses were split
answers.

The pipeline as it now runs (a fresh draft with no format, then the pass),
on the same ten beats: the first sample of each and two more completed before
the OpenRouter account ran out of credit (HTTP 402, `in_flight_budget_exhausted`).
On those 12, labeled recall went 74/89 in the draft to 81/89 after the pass;
early stops 1 of 10 to 0; a declared act uncarried 1 to 0 (the one draft
that stopped, a chat 153 replay resolve, went from 3 events to 9 with all
four of its missing declarations); the draft took a median 9.4 s and the
pass 4.2 s.

### Duplicates

An event re-telling part of another -- same source, its sentences within the
other's, its text held in the other's -- was found in capture 3979 (its four
doubles) and in about 3 of 213 fresh drafts. The same signal fires on a line
a character speaks inside narration ("Kansai," "come on, come on, come on."),
which is its own event by the encoder's rules, so it would need speech held
out, and at that rate no check was built.

## Tested live, 2026-09-25, with the credit back

**The pipeline as it runs, all 30 samples** (ten beats, three each, reasoning
off): the draft with no format covered 196/216 labeled sentences (0.91), with
no early stop in 24 labeled runs and no declared act uncarried in 30 -- and
after the pass, the same 196/216. On drafts this complete the pass recovered
no labeled sentence: it applied 64 jobs, declined 74, left none unanswered,
and the one known wrong write -- capture 3979's beach written as the ship's
route, 5 writes over 3 runs -- survived it every time. Its median cost was
5.5 s a beat, the draft's 11.0 s.

**The pass on the frozen drafts again (v9, merge fix in):** 48/66 missing
sentences, 10/18 wrong writes, 5/9 ledgers, median 5.9 s; 0 of 141 returned
events dropped (v8: 17 of 115). Declared acts were recovered in 8 of 9 runs;
the ninth stopped inside the repair -- 3998's sixteen-sentence job answered
five events in, before the Doctor's closing line -- so a job whose answer
carries fewer of its declared acts than it was given is now asked once more,
and the fuller of the two answers is kept.

**Chat 154 turn 4398 rerolled from `director_resolve`** on copies of the
owner's database, their own routing, the repair on:

| encoder reasoning | rolls | a turn | the draft call | declared acts carried | the TARDIS |
|---|---|---|---|---|---|
| `medium` (as it was set) | 2 | 221, 223 s | 157, 163 s | 8 of 8 | in transit, no invented destination or route, both |
| `off` (the owner's call, set in their database) | 12 | 44-115 s, median about 59 | 5-16 s | all | in transit 10, sealed 2 (the prose had not launched it); once the departure beach written as the destination, an ETA of 5 s |

Both pages read as the beat: the Doctor's two lines in order, the lever let
go, the sealed doors behind Hinami. What the rolls found:

- **The figure on the beach is not in the world.** Before any change, 4 of
  the first 6 rolls minted it and none placed it -- 3 by an encoder that had
  not been granted `positions`, 1 by the repair, which is never given it --
  and a body is stood by `positions` and nothing else, so it was nowhere.
  Code now closes both: a thing the answer mints and neither positions nor
  transfers implies `positions` for the draft (`implied_tools`), and a
  repair holding `entities` holds `positions`. The draft's rule fired once;
  the widened answer still left the figure unplaced, calling it "only a
  scanner image". Two wordings of the `entities` part's own test ("a body
  heard over a speaker has a place") extended to a body shown on a screen
  were tried on 6 more rolls: none minted the figure at all -- each recorded
  it as the scanner's state -- so both were dropped. Open.
- **A destination equal to the place the ship is leaving** joins the route
  written that way (3979). The own-interior floor does not cover it, and the
  repair's checks did not flag it.

## Limits

- **The merge fix is measured on frozen drafts only** (v9); the pipeline's
  own fresh drafts rarely leave a job big enough to split.
- **The format measurement is one model on one route**: GLM 5.2 through
  OpenRouter (BaseTen, Fireworks, Parasail). The owner's replay route
  (NanoGPT) and the encoders tried before (DeepSeek v4.1 Flash, Ling 3.0
  Flash) are not measured; the measured default follows the role, so a host
  moving the encoder to another model inherits it and can set it back.
- **The repair call stops short too** -- less than it looked. The first runs
  skipped a 16-sentence event job beside a fix, and one job came back with 1
  event where the next run gave 25; hence the one retry. Some of those "1
  event" answers were a job answered in pieces with every piece after the
  first dropped (above), fixed by `merge_answers`; how much short-stopping
  remains is unmeasured since.
- **A repair copies the draft's own mistakes.** Shipped the transit part,
  the fixes of 3979 still wrote `route_room: moonlit_beach` -- the other
  transit writes in the draft said so -- and the re-check judged them wrong
  at 0.80-0.86. The own-room destination is dropped by the engine floor;
  a route equal to where the ship set off from is not, and a floor for it is
  the owner's decision (listed in DESIGN_PROSE_CONTRACT.md).
- **Two labeled defects are never flagged:** the Doctor's half of "Together
  they push" (0.32) and the transit a ship breaking free leaves unwritten
  (0.37-0.39, even asked by the transit part's own definition).
- **Duplicated events are not checked** -- rare, and the signal found for
  them also fires on lines spoken inside narration (above).
- **The owner's current routing reasons at `medium` for
  `director_specialist`.** The repair call uses that role, so on it every
  repair call -- like the draft itself, 62-137 s on the owner's last reroll --
  would run minutes, not the 1.5-23 s measured here.
- One labeler, eight beats: the versions above differ by less than the
  noise. The next step is more labeled beats -- enough to tell a +-5 of 66
  apart -- and a live play with the setting on.
