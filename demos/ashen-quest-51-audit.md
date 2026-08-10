# ashen-quest-51: off-screen world audit

51 turns · persona **Corin** · cast **Sera, Bryn, Wren** · villain **Maelor**, dormant and off-screen for the whole quest

Played through the real pipeline by `tools/quest_drive.py`. Every model output
is hand-authored and goes through `validate_llm_output_strict` exactly as a
model's would; every mechanism that fires is the engine's own. That is the
honest limit of this artefact: it shows the engine **carries** a crowd op, a
telling, a plan — not that a model would **write** one.

- `ashen-quest-51-story.json` — the export, checkpoints stripped (1.7 MB, was
  6.5 MB; checkpoints were 74% of it and reconstruct nothing an importer
  needs). Verified by importing it through the production-wired
  `ChatArchiveService` into an empty database: **51 turns, 111 memories,
  4 cast, 7 world events**.
- `ashen-quest-51-transcript.md` — the played story, with what fired inline.

## What fired

    turn  6  crowd declared
    turn  8  epoch: time
    turn  9  world event recorded | a public surface | the crowd took it up
             | an absent mind stirred | epoch: due_event
    turn 11  a plan opened
    turn 17  a plan's stage fired | an absent mind stirred | MAELOR THINKS
    turn 18  world event recorded | a public surface | an absent mind stirred
    turn 20  crowd declared | somebody witnessed it | the crowd took it up
    turn 25  world event recorded | a public surface | somebody witnessed it
             | the crowd took it up | MAELOR THINKS
    turn 28  crowd steered toward the gate
    turn 50  crowd declared | the room remembered the absence
    turn 51  somebody was told

## Off-screen life (`tools/fire_rates.py`)

    world epoch opportunity                  9.80%    5/51
    seeded tick batch wrote events          80.00%     4/5
    profile candidate selected              60.00%     3/5
    full-agent candidate selected           60.00%     3/5
    reactive plan op accepted              100.00%     1/1
    reactive stage fired                    33.33%     1/3
    reactive effect minted                 100.00%     1/1
    public event surface emitted           100.00%     7/7
    character acquired carried report        3.63%   7/193
    a report was passed on                  50.00%     1/2
    a crowd op was accepted                100.00%     4/4
    a crowd moved on the graph             100.00%     1/1
    a crowd took up public talk              6.02%    5/83
    destination residue delivered           12.50%     1/8

    a courier or caravan op was accepted     no chances
    a caravan traded news at a stop          no chances
    an artifact op was accepted              no chances

The three `no chances` rows are honest: this story never sends a rider, never
routes a caravan, and never nails anything to a wall. See
`tools/courier_drive.py`, `tools/caravan_drive.py` and the artifact tests for
those. A rate with no denominator is reported as no chances rather than as 0%,
because a mechanism that was never offered an opportunity has not failed.

**`a crowd moved on the graph` is the first observation of that mechanism in a
played story.** It previously read `0/78` — moves measured against every crowd
standing anywhere. A crowd with no heading was never a chance to move, so the
denominator is now crowds that were *carrying* a heading at the top of the
beat, counted before `advance_crowds` spends them. The mechanism was healthy
the whole time; the measurement was diluting it to nothing. This is the
project's most expensive recurring discovery — a mechanism assumed live that
was not running — with its sign flipped, and it is the reason the story now
declares a heading at all.

## Payload scan (`tools/payload_scan.py`)

505 captured stage payloads, read as a model would read them.

    what a reader would trip on : nothing

    counted, and by design:
      324  adjacency edge with a null destination
             perception's leak-fold: barrier kept, destination withheld
      116  somebody standing in a room the payload does not carry
             _contextual_rooms trims rooms for cost; positions stay whole

    blinded edges that were folds     : 324
    blinded edges that were inventions: 0   (must be 0)

Both counted rows are the design rather than defects, and are printed rather
than suppressed so the claim can be checked. A `to: null` adjacency is an open
doorway whose destination the observer has not earned — the barrier is kept
because a closed door is plainly there to anyone standing in the room, and a
payload that omits it says the room has no way out. The scan distinguishes a
fold from an invention by checking the payload is a strict subset of the
world; a blinded edge in a payload that already carried every room would have
hidden nothing, and there are none.

### What the scan found the first time it ran

Three defects, none of which failed a test:

1. **A trait map written `{"wary": 0.7}` lost its name.** Expansion of a
   name-keyed map required *every* value to be a dict, so the shortest way to
   write a trait fell through to the single-profile branch and became one
   anonymous trait carrying `wary` as a stray key. 42 character payloads
   carried a psychology whose `traits` list was non-empty and named nobody —
   a sheet that reads as populated is the exact silent-failure shape
   `persona_warnings` exists for. Fixed in `character_schema`, which now
   discriminates on whether the map's keys are the profile's own *fields*.

2. **The capture shared one filename across threads.** Perception runs once
   per perceiver and the off-screen rungs run on daemon threads, so writers
   clobbered each other: **209 of 505 payloads were overwritten before anyone
   read them**, and five were left unparseable. Every payload audit before
   this one read 59% of what the engine actually hands models.

3. **A crowd heading declared as `{"op": "set", "room": ..., "heading": ...}`
   is refused.** That shape does not steer the crowd standing in the room — it
   tries to *mint* one, and is rejected for having no composition. Two drives
   were declaring drift that never happened and saying nothing about it. The
   refusal is the design working: a crowd may only be named by a uid the
   engine minted.
