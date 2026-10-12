# Play test: Hollowmere Funicular (2026-10-12)

A fresh 15-beat story written to exercise the Saltmarsh follow-up wave
(`8bc07614`..`385e499b`): carried kit at the opening, documents read, a
conveyance, walks "toward" places, a role-holder whose name is public while
what he did is secret, and the Writers' Room with a free hand. Scratch chat
196 in the job's play db (turns 4658-4686), driven in-process by the
Saltmarsh harness (`drive.py`), every beat written after reading the page
before it.

**Setup.** Player Ilse Varga, a telegraph line inspector with a satchel, a
lantern and sealed orders; companion Mattias Brenn, the funicular's
brakeman, whose sister keeps the silent upper instrument. The Room was told
the town's names in common (the stationmaster Oskar Lind, the lineman Karl
Wessel) and one secret (Mattias saw Wessel on the path with wire-cutters).
`room_free_hand` on for the story; `layout_solver_tier` restored to on (my
own shrine test had left it off, so Saltmarsh ran without it); the Room on
low reasoning, as the owner's own db.

**Numbers.** Median beat 56 s (26-81; the first, with the opening, 418 s).
305 model calls, one failed -- a runaway, recovered by the varied fresh
ask. $4.78 on OpenRouter.

## What the wave did live

- **The opening's carriage** (§1.199): the satchel and lantern were minted
  `held_by` Ilse and the oil can `held_by` Mattias, and they were carried.
  Everything she carried rode the car up and walked the path with her.
- **A set-down at a fixture**: beat 1's `to_id: "workbench"` resolved to the
  winding house's own fixture, and the lantern stood at it.
- **A conveyance is a vehicle**: the opening minted the funicular car as a
  vehicle docked at the lower platform, not as a room between the two. The
  interior room was minted when Ilse boarded, the car went in transit up the
  lower track, docked at the top and opened to the platform.
- **The secret is the act**: the Room's common lore named Agathe Brenn,
  Oskar Lind and Karl Wessel with their posts; the sighting stayed a truth
  only Mattias holds; the Room planted Lind and Wessel as people. Wessel kept
  his name all run, and lied about his morning ("not past the hut since
  first light").
- **The free hand**: every Room planner call after beat 1 carried it (8 of
  8); the Dramaturge proposed three directions and the Room drafted and
  published packages without asking.
- **A runaway is asked differently**: Mattias's character call ran away on
  turn 4664; the fresh ask, "with varied sampling", came back valid in 3.2 s.
- **PA12**: beat 13's "starts back down the path toward the telegraph office"
  was declared not arriving, and the floor walked her 2 paces to the doorway
  ("Approach under way").
- **Reads**: the cabinet's terminals and wire (beat 8), the line-tester's
  needle (beat 9) and the logbook twice (beats 7 and 15, the second fuller)
  were answered on the page; a written name in a reading arrived quoted.

## Found, and fixed during the run

- **4c860c50: a follow boards with the one it follows.** Beat 3: the
  brakeman declared his own follow of the inspector, both were seated in the
  car, and the follow carry wrote him her walk room on top of his seat; the
  merge read it as stepping back out, the car climbed without him, and he was
  split into a scene of his own. The walk floor also let the player's span
  seat him through `containment`.
- **66184310: a beat that moved a walker is not a silence.** Beat 14: the
  beat took Ilse into the telegraph office while the lineman's walk held the
  interpretation's movement field, and her pending approach to the platform
  walked her back out of the office the page had her reading in.

## Found, not fixed (registered; the wave after, below, says what became of each)

1. **A read answered by the record of the act** (beat 2). She broke the seal
   and read her orders; the resolve described "a single sheet, dense with
   type" and the encoder, with the examined part routed (0.92), wrote
   `read: yes`. Nothing said what the orders say. `docs/UNBUILT_PERCEPTION.md`
   §1.201.
2. **What a read finds named the reader** (beats 7 and 14). The logbook's last
   sent entry was authored "CONFIRMED -- line nominal -- Varga" at 08:31,
   hours before the player arrived, and the page later called it "her own
   morning confirmation". Same entry, §1.201.
3. **The missing woman was at her post** (beats 14-15). The brief says
   Agathe has not answered since noon; the Room planted her as the
   instrument's keeper, the town simulator stood her body at her post, and
   she was voiced there, confused ("I know what Karl's bell sounds like").
   `docs/UNBUILT_PLANNING.md` §1.202.
4. **An approach the encoder does not record as one** (beats 6 and 10).
   "Heads across the platform toward the telegraph office" wrote no movement
   at all; "up the mountain path toward the lineman's hut" arrived on the
   path. The PA12 floor fires only on a declaration marked not arriving.
   `docs/UNBUILT_WORLD.md` §1.203.

## Seen, recorded here only

- A set-down written as a station alone (beat 9: the line-tester "set on the
  shelf" stayed held as well) -- the inventory card's own rule. (It was not:
  the narrator staged it; see the wave after.)
- Rendering: "You are in Inside the funicular car" (an interior's minted
  name); "Mattias Brenn the car climbs the steep track" (an observable with
  its own subject, prefixed with the actor); "the grey-haired solid
  grey-haired medium solid ruddy heavy person" (a label built twice over).
- The car docked at the top on the beat whose page still had it climbing.
- The generated companion card wrote `known_by` as slugs (`mattias_brenn`,
  `agathe_brenn`), so those history entries stay private forever; the card
  warning said so at creation.
- The Room's pre-story reply ended at its wall with no text, having settled
  its grant, a published package, lore and two planted people.

## The wave after (2026-10-12)

The owner approved eight follow-ups to the findings above. Each was measured
on a copy of the scratch db, every turn rerolled from its own checkpoint (see
the last section for why that has to be said). Design.md carries a row for
each one that landed.

**Landed.**

- **What a read finds is the thing's state** (finding 1). The orders' gist
  had gone into the envelope's *description*, which no reading delivers -- her
  view said only "seal: broken; read: yes". `entities__examined` now authors
  a perceived detail in state, and says a description is what any eye takes
  in at a glance. Interpretation rerolls of turn 4660: what the orders say in
  state 4 of 4, in the description 0 of 4. Resolve rerolls, which inherit the
  stored interpretation's description and so find the record complete: 1 of 4.
- **A mind's past is its own** (finding 2). The resolve card: a record may
  carry any hand the world supplies, never the hand of a mind that did not
  make it. Four resolve rerolls of turn 4669: none signed the log with her
  name.
- **A walk is recorded by where it is going** (finding 4). Core's movement
  line no longer says `to_room` "is where the walk ends". Beat 6 ("heads
  across the platform toward the telegraph office") 6 of 6 toward the office,
  not arriving -- 0 of 4 wrote any movement before. Beat 10
  ("up the mountain path toward the lineman's hut") writes the approach on
  every reroll, 6 of 6 against 1 of 4, but decides the walk on only 2 of 6:
  three arrive on the path with the approach as a trailing row that
  `_final_movement` drops by design, and one marks the path itself not
  arriving. Arrival controls: 7 of 8 under a first wording, 4 of 4 under the
  final one (the miss was a step down from a docked car written as a
  position, and "or already stands in" was cut for it). Two residuals stay in
  §1.203.
- **A tie may name a person the room plans** (the half of finding 3 that was
  real). Preview accepted only registered characters and the player in a
  plan's `known_by`, so the lineman, whose plan said he courts her, could not
  be written as knowing her. It now takes a person the room plans, before or
  in the package. Five replays of the turn-20 fill (from checkpoint 21, that
  fill's own draft removed, the later beats deleted): none planned Agathe;
  of 18 new people 8 named another planned person, every tie seeded both
  ways, but all in two of the five replies -- and in another a retired
  lineman's truths read "He knows Karl Wessel" with Wessel left out. So
  preview now asks when a plan's brief names, whole, a person the story holds
  and neither side lists the other: on the replays' own plans it fired on
  that lineman alone (none of the six others), and on the original turn-20
  plan it names the lineman's brief, "He courts Agathe Brenn".
- **Rendering**: an interior is named by the pack ("Inside %s" was English in
  every story); a label no longer takes a body's appearance for its noun ("the
  grey-haired solid grey-haired ..." was two writers filing a description as
  `role_hint`).
- **A card's `known_by` written as identifiers reaches its person.**
- **A stopped Room reply says what it settled**, by its packages' titles and
  with no model call, in the story's language -- and the panel's own reply
  now runs in the story's language at all (it read the English planner card
  in a Japanese story).

**Withdrawn.**

- **Finding 3 was a misreading of my own brief.** It says Agathe "has not
  answered the bell since" noon -- never that she is missing -- and the
  story's secret, Wessel walking away from the poles with wire-cutters at
  eleven, explains a dead instrument with its keeper sitting at it. The
  turn-20 fill planted her at her post "so that the head of the line has its
  keeper standing there", a valid reading, though it did undo the pre-story
  note that she "deliberately holds no place". A planner clause about missing
  people was drafted and removed before landing: no live case shows that
  class. For when one does, a read-only survey of the Room's operations found
  that `plan_entity`'s `where` only *starts* a body (the town routine walks it
  home or to its post on the next advance); what holds a body away is
  `charter_ops depart` with a `place` (until `arrive`), `move_body` with
  `berth` for a person with no post, or `die` with condition `missing`
  (nowhere, for good) -- never `arrival`, `errand`, `summons`,
  `scheduled_consequence`, the post ops or a `hurt` incident -- and a hold
  must go in a second package, since preview checks it against a body that
  only exists once the plan publishes.
- **The set-down "written as a station" was the narrator's.** The world kept
  the line-tester in her hand at her own station; only the page said "She set
  the instrument on the shelf beside the sounder", and the player's next beat
  unclipped it and stowed it. Measured over the db's whole history, a floor
  reading "a new station while held is a set-down" would have been wrong on
  3 of the 4 distinct beats it fired on; the one real case is registered as
  §1.204.

**A measurement that measured the wrong world.** A stage rerun restores its
own turn's checkpoint and deletes every later one, and `ensure_checkpoint`
then rebuilds a missing checkpoint from whatever world is current -- with no
error. The first batch for finding 4 rerolled turn 4660 before 4667 and
4675, so both ran against the world before 4660 (the encoder walked her up
from the lower station), and was discarded. The same ordering had produced
two numbers in the wave before: Saltmarsh turn 4646's resolve rerolls (4 of
4, remeasured 3 of 4 in full) and half of its looks (4 of 4, remeasured 3 of
4), both corrected in Design.md and §1.200. Every batch since runs each
chat's turns latest first, on a fresh copy.

**Cost.** $3.27 on OpenRouter for every measurement above: about fifty
stage rerolls and five Room fills of 7-10 minutes each.
