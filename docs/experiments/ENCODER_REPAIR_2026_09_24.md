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

## Limits

- **The repair call stops short too.** The first runs skipped a 16-sentence
  event job beside a fix, and one job came back with 1 event where the next
  run gave 25; hence the one retry. On the malformed 3880 it still returned
  4-39 events across runs.
- **A repair copies the draft's own mistakes.** Shipped the transit part,
  the fixes of 3979 still wrote `route_room: moonlit_beach` -- the other
  transit writes in the draft said so -- and the re-check judged them wrong
  at 0.80-0.86. The own-room destination is dropped by the engine floor;
  a route equal to where the ship set off from is not, and a floor for it is
  the owner's decision (listed in DESIGN_PROSE_CONTRACT.md).
- **Two labeled defects are never flagged:** the Doctor's half of "Together
  they push" (0.32) and the transit a ship breaking free leaves unwritten
  (0.37-0.39, even asked by the transit part's own definition).
- **Duplicated events are not checked.** Capture 3979 carries three acts
  written twice (the spark, the vibration, the tilt).
- **The owner's current routing reasons at `medium` for
  `director_specialist`.** The repair call uses that role, so on it every
  repair call -- like the draft itself, 62-137 s on the owner's last reroll --
  would run minutes, not the 1.5-23 s measured here.
- One labeler, eight beats: the versions above differ by less than the
  noise. The next step is more labeled beats -- enough to tell a +-5 of 66
  apart -- and a live play with the setting on.
