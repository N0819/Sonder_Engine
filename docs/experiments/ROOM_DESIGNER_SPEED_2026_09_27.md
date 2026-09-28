# The room designer's steps: what code and Jev take (2026-09-27)

The prose contract's room designer (`agents/director_rooms.py`) is a tool
loop: each step the model returns tool calls, code runs them, and the
results come back in the next step. It was the slowest single part of a
place-entering turn. This measures what its steps were spent on, moves every
step that did not need a model to code and to the decision model (Jev), and
measures the loop again -- on the case that found it and on five recorded
cases from three other stories.

Route throughout: NanoGPT, plain `z-ai/glm-5.2`, `reasoning_effort` `off`
(the owner's `z-ai/glm-5.2:thinking` at `medium` took 162-174 s a loop on
the same case and met the 150 s wall). One run at a time -- NanoGPT is not
asked for parallel runs. Jev (`typesafe/jev-1.13`, OpenRouter) is the only
paid call, a few hundredths of a cent a design. Scripts:
`$CLAUDE_JOB_DIR/tmp/express/rooms_fast/` (`trace_full.py` for the yard,
`trace_case.py` for any recorded designer call, `read_trace.py`,
`room_quality.py`, the three `complete_probe*.py`).

## 1. Where the steps went

The yard: the betrayal replay's turn 4 (capture 186), a place the Director
invented ("the snow of the yard, beside the narrow grave"), size `small`,
joined to nothing yet. Two whole loops of the old designer:

| run | wall | steps | how it ended |
|---|---|---|---|
| earlier trace | 48.5 s | 8 | step cap |
| `base1` | 42.2 s | 8 | step cap, check "clean" |

`base1` step by step: steps 1-2 inspected the infirmary and the central
passage, and step 3 inspected them again with the barracks (9.6 s before
anything was drafted); step 3 drafted the yard whole -- description, light,
surface, three fixtures -- in 11.3 s; step 4 looked at the plan it had just
been shown; step 6 submitted and was refused, because the check it had never
run named three things: `small` against a 6x5 extent the engine reads as
`medium`; the yard's doorway on the passage's south wall, on the barracks
door's cells; and the yard, placed south of the passage, laid over the
barracks. Steps 7-8 fixed them and the cap stopped it. Its final check read
clean only because the engine had dropped the bearing from BOTH doorways on
that wall -- the barracks lost its direction, and the check cannot see a
bearing that is not there.

## 2. What moved to code and to Jev

- `surroundings`: the standing rooms around the place, already drawn the way
  `inspect_rooms` draws them.
- `placing`, for an invented place: the floor area its size word covers
  (`small` is 13-24 square paces) and `doorways_that_fit` -- every free wall
  of those rooms where the doorway joins the world, tried against the
  engine's own layout check at the size's square and its two longest shapes,
  and rejected if any bearing anywhere is lost. 0.1-0.3 s. A wall with any
  neighbour on it is never offered, a solid one included, because the lint
  does not lay out a room behind a wall (the infirmary's east wall "fitted"
  the yard over the dugout until that was added).
- The check after every step that changes the draft; each check first sets
  the size word to the one the extent measures.
- `drop`: a doorway can be taken out of the draft. Without it the second
  new-loop run circled five steps round a second doorway it could not take
  back -- its notes say "removing the edge", its calls could not.
- The re-fit: when the check says a new place stands where it cannot, it
  hands back the doorways that fit the place as drafted (the second run's
  6x5 yard no longer fitted the walls tried at 4x4).
- Jev's stop, below.

## 3. The stop: probing the questions

Two noul questions per owed room, the state being the passage and the
room's record (`_record_text`: name, description, fixtures, ways out, light
and surfaces). Probed before wiring on the yard (the finished draft, and
with the grave taken out, a bare shell, the grave only in the description, a
flagpole the prose names and nobody stands at) and on eight recorded designer
runs, each finished and with what the prose puts in it taken out.

- "Is everything the passage says is part of this place in the record?"
  hedged at 0.52-0.56 whatever the draft held. Dropped.
- "Could someone with only the record picture every part?" 0.40-0.68,
  useless. Dropped.
- **`room_done_missing`** -- does the passage mention a part of this place
  the record never mentions: 0.28-0.39 on the finished yard, 0.69-0.74 on
  the missing flagpole; on the recorded runs it caught the carved initials
  the lighthouse rail's record never mentions (0.61-0.65 on the "finished"
  rail -- the question working) and hedged at 0.50-0.54 on the finished
  osteria. A tighter wording ("other places the passage mentions do not
  count") let the initials through at 0.49. Kept the first.
- **`room_done_unlisted`** -- does the passage place someone at a feature
  that is not a fixture: 0.88-0.94 on every stripped yard, 0.27-0.35 on the
  finished one. A wording listing prepositions ("beside it, on it, behind it
  or in it") held the finished workshop; the class alone ("at a particular
  feature") did not, and is what ships.

In the loop, `room_done_unlisted` at 0.5 held a finished yard three steps
(`fast5`, 0.54-0.56, most likely on "at Anselm Ferro's shoulder"), and the
note, repeated each step, was chased: the designer wrote "This is where Luca
stands at Anselm Ferro's shoulder" into the grave-side fixture -- a body's
place in room text, which the rooms chunk forbids. A third form, a CHOICE
of which listed fixture the passage places someone at (plus "another" and
"none"), named the right fixture on every finished room (p(another) at most
0.04, 0.38 on the harbour wall) but missed two stripped rooms by finding A
feature rather than every one. What ships: `room_done_missing` at 0.5,
`room_done_unlisted` at 0.6 (`ROOM_DONE_BARS`), and the note said ONCE,
with "if the record already holds it, submit; where a person stands is never
written into a room's text". At those bars every stripped draft is held and
every finished one let through but the osteria.

## 4. The loop again

Every new-loop run, in the order they were made; the code changed between
rounds, and a run marked † hit a defect found by that run and fixed after
it (below). Each case's own prose, payload and pre-beat scene.

| case | kind | old loop | new loop (wall, steps) |
|---|---|---|---|
| the yard (betrayal #186) | invented, small | 48.5 s / 8, 42.2 s / 8 | 15.3/1, 67.6/8 †(no `drop`), 11.3/1, 17.1/1, 38.2/5 †(the 0.5 bar, the note chased), 33.2/4 (a crowded wall), 14.3/1, 19.4/2, 11.0/2, 25.5/2 |
| harbour café (`rival` #45) | invented, small | 43.1 / 6 | 18.1/1, 14.2/1, 23.6/2 †("one of" -- hung off the stage door), 13.4/1 †(joined to nothing), 23.4/2, 54.5/4 †(drafted under a second id) |
| the workshop (`homecoming` #71) | invented, small | 33.0 / 4 | 23.6/2, 28.9/2, 26.0/2 |
| schoolhouse classroom (`lie` #8) | invented, small | 44.9 / 8 | 19.4/2, 23.8/3, 34.1/5 |
| stage + osteria (`rival` #82) | planned + invented | 121.6 / 8, **not clean** | 20.0/2, 35.6/3, 80.1/8 †(size fight, not clean), 89.2/6, 54.6/5 |
| lighthouse rail (`homecoming` #29) | planned | 26.2 / 4 | 24.4/3, 25.8/2, 155.9/7 †(seven stubs developed, the wall), 15.1/2, 12.6/1 |

Without the † runs: the yard 11-33 s (median 16), the invented places
13-34 s, the rail 12-26 s, the stage pair 20-89 s -- against 26-122 s for
the old loop, which ended unclean once. Every new run but the two † that
say so ended clean. The stage pair is the heavy case (two owed rooms, a
passage that walks through four others) and its spread is the widest.

The rail's two extra steps in its first run were a doorway the model wrote
on both rooms with the same side; the sentence saying a place's doorways
are written on the place itself sat under invented places only, so the
planned rail never read it. It now sits in the general doorway instruction.

What the later rounds found, each fixed and pinned by a test:
- **Code fought the model over a planned room's size.** The merge keeps a
  planned room's measurements whatever the draft says; the size agreement
  read the DRAFT's extent, so on the stage it wrote `huge` for a 12x10 the
  merge never took while the designer wrote `large` for the 10x8 it did --
  four steps, the cap, and an unclean end (80.1 s). Sizes are now read off
  the extent the world holds, and a drafted extent the plan overrules is set
  back with a line saying why.
- **The offered doorways read as an order.** Told to take "one of" them, a
  designer hung a harbour café off the theatre's stage-door vestibule --
  where the cast had been standing -- when the old loop had built a harbour
  road to it. They are now where a place CAN join those rooms, never where
  it must.

- **An island passed as clean.** Told a place joins the world where it
  lies, a designer drafted the café joined to nothing, and the merge would
  have opened it onto the rehearsal room the cast stood in
  (`connect_orphan_new_rooms`, the engine's floor). The check now names a
  new place the DRAFT joins to nothing (`no_way_in`), unless it is an inside
  or carries a `zone`.
- **The same place under a second id.** The Director reserved `harbour_caf`
  (the id fold drops the accent); the designer drafted `harbour_cafe`, was
  told `harbour_caf` was owed, drafted it too, and left the stray. A new id
  carrying an owed place's name is now drafted as that place.
- **Plan stubs drawn empty read as work.** One rail run developed seven
  planned rooms nobody had entered and redrafted the harbour wall whole
  (81.7 s for the first step, then the wall). Stubs are no longer drawn in
  `surroundings`; the rooms chunk's "furnish a planned room in view" clause,
  which licenses it, is left to the owner (UNBUILT_WORLD §2.38).

Pre-existing gaps surfaced too: a step's calls past its sixth were dropped
without a word, and a designer that sent eight believed it had drafted the
corridor and the auditorium -- they are named back as not run; and an
overfull wall came as "needs 7, has 5", which sent one designer widening
the wrong side twice -- the check now gives the wall's length, which side
of the extent that is, and each fixture's paces.

## 5. Did speed cost the rooms?

`room_quality.py` on the owed rooms (description characters, fixtures --
every one with height and footprint in every run, old and new):

| case | old | new |
|---|---|---|
| yard | 749 chars, 3 fixtures | 691-944 chars, 2-3 fixtures, also `quiet` and `floor` set |
| café | 752, 4 | 1,198, 6 |
| workshop | 715, 4 | 693, 4 |
| classroom | 679, 4 | 668, 3 (no slate boards; the prose names none) |
| stage | 1,134, 6 | 840, 3 (its doorways stay the plan's) |
| osteria | 556, 4 | 984, 3 |

The stage is thinner: three stations on a 10x8 stage against six, and one
later run left it a single fixture. Jev held it (0.80 / 0.73 -- the beat's
prose walks through three other rooms, whose features read as the stage's)
and the model submitted; a stage's wings and rear wall are the kind of
thing only a longer look adds. The later café runs vary in where they put
the café (a lane, the rehearsal room) where the old loop built a harbour
road: a place the world has no street for is the designer's judgement, and
the check can only say that it joins something. Watch both on real play.

OpenRouter spend for all of it: about $0.01 (Jev); the designer ran on
NanoGPT.
