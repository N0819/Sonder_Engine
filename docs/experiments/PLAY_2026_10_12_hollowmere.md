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

## Found, not fixed (registered)

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
  shelf" stayed held as well) -- the inventory card's own rule.
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
