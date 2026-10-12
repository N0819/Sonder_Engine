# Observation: the owner's "Home 6" (chat 168, 2026-10-12)

The owner's own five-turn story in `engine.db`, read for every flaw "both in
layout and in pipeline" (owner, 2026-10-12): Hinami wakes at night in her room
on the second floor of the Shrine of the Golden Fox while Tamamo rests in her
roost above. Played 04:44-04:54; every page read as fiction first, then every
stage of every turn against each other, then the laid-out site plan.
`engine.db` was opened only with `mode=ro`.

**How the fixes below were measured without copying `engine.db`.** The chat
was exported through the portable archive with a read-only connection handed
to `core.db` for the one thread (`engine.db`'s size and mtime unchanged), and
imported into a 3 MB scratch database holding `engine.db`'s own settings and
providers -- so the Director ran on the same DeepSeek v4.1 Flash. The import
was checked identical (resolve prose, pages, positions, rooms), and every
batch ran on a fresh copy, latest turn first.

## What the owner experienced (worst first)

1. **Tamamo spoke to Hinami and Hinami never heard her** (turn 4590). At the
   shut shoji: "Hinami? It is late." -- addressed to her. Hinami's whole view
   that turn was one line of interoception.
2. **Tamamo slid Hinami's door open behind her and nothing told her**
   (turn 4591): "a soft rasp of paper and a dry tick of wood" lived only in
   the Director's prose, and the cold of the hallway reached the futon.
3. **The Director decided the player's mind**: "the silence of someone who
   heard and chose to lie where she is" (4590); "the breath of someone well
   down in sleep", "Hinami's breath catches" (4591) -- while she declared
   waking, staring at the ceiling and turning over.
4. **The Room planted two strangers inside a home it had just called "a house
   two people live in"**: a fill at the first beat put Sanae in the main hall
   and Kaede in the upper hallway outside Hinami's door, `known_by` empty.

## Fixed in the wave after (2026-10-12)

- **A paper door is heard as paper** (1). The engine had always held the
  answer -- an edge's `material` moves a door one rung more open for sound
  alone, so a paper screen is heard like bars -- but no card asked for it and
  the mirror that copies a doorway's barrier and name to its other side left
  it behind: every shoji in every story was heard as oak. The cards now ask
  (encoder rooms, the spatial chunk, room vocabulary, the establish, the room
  author, the plan's field), and the mirror and the plan's reciprocals carry
  it. Two establish rerolls of the opening wrote `material` on 20 of 20 door
  edges (every shoji paper, the outer doors wood, the warded door metal),
  against none before. A normal voice through a paper door is now `full` where
  wood gives a `fragment`. **Tamamo's whisper still does not cross**: a
  whisper through a shut door stays breath-private by the owner's ruling of
  2026-09-26, paper or not, and three paces in it falls 1 dB under the
  indoor floor.
- **A line keeps its addressee** (1). The re-stamp that sets a declared
  line's tags from its declaration also erased the target the encoded row had
  given it ("Hinami? It is late." was logged aimed at no one).
  `director._restamped_target` keeps the row's target where the declaration
  named none; on the original turn's data it restores "Hinami".
- **A door worked is heard** (2). `spatial_sound_field.door_events`: a
  doorway that went shut-to-open or open-to-shut between the pre-beat scene
  and the scene the commit will write sounds `faint` at itself in both its
  rooms, read from the typed barrier and never the prose. Recomposing turn
  4591 on the copy, Hinami's view ends "a door opening" and the new page reads
  "Behind you the door to the hallway stands open."
- **A mind's inner life is its own** (3). The resolve card's other-minds
  bullet: whether a mind sleeps or wakes, what it heard or noticed and why it
  keeps still are never the Director's to decide. Resolve rerolls on the copy:
  0 of 6 decided Hinami's inner state, against 2 clear and 1 mild of 6 before
  (and the two original beats).
- **A sketch plants only strangers, where strangers are met** (4). The fill
  was the one-call sketch, which has no `known_by`, no lore, and only the
  player's own lines -- the Room's "a house two people live in" never reached
  it -- while the frontier asks for two people ahead in every story. Replaying
  that fill on the copy, before: 4 of 4 planted the shrine's "household"
  inside it. The sketch card now plans only someone the story's people would
  not already know, standing where a stranger could be met and never inside
  where they live, and hands anyone else to the full planner by `escalate`.
  With the final wording -- where nothing in reach is such a place, plant no
  one or escalate -- 3 of 3 replays were right: one sketch planted no one,
  and two escalated to the full planner, which put strangers outside (a
  villager under the camphor tree and a student on the lantern path; two
  travellers on a mountain path it built below the torii). The two earlier
  wordings still let a sketch stand outsiders in the main hall or the hallway
  3 of 7 times, its reach holding only the house. All eight escalations were
  right, at three to fourteen minutes of the Room's background time each.

## The layout wave (the owner's follow-up, 2026-10-12)

The owner, reading the generated shrine: "windows are bieng made as fixtures
instead of being actual windows. there are no genned stairs as far as i can
tell and, i think tatami should be a floor description rather than a
fixture, and shoji door being placed ontop of the door is weird anddoors
should have a description and material type field, etc etc, and perhaps in
the in engine ui should be adjusted to look kind of like the layout lab we
made." Asked, the owner chose a stairwell room per storey and the lab's own
plan view. Each fix was measured by replaying the shrine's recorded layout
answers (`engine.db` captures 5674-5676, read only) through the real path on
a copy -- the solve stayed the same, every room's site and extent unchanged
-- and, for the cards, by live calls on that copy.

- **A door is its edge** (4e4d102e). The sort had made up nine door and stair
  "fixtures", each minted as an anchor on its own door's cell; a mark now
  pins only a fixture the plan lists, and a door's own words live on its edge
  as `desc` beside `material`. Marks 9 to 0. Three live sorts with the new
  card still listed 10, 13 and 16 such marks: the bridge's drop is what holds.
- **A window is in its wall** (34438d08). A window with ground the solve laid
  beyond it is a `window` edge onto that ground; every other one a record in
  its room's `windows`, never an anchor. Window anchors 4 to 0; Hinami's east
  window now looks onto the camphor tree, and two opening reruns read
  "Through the window facing the moonrise is The Sacred Camphor Tree".
- **What covers a floor is the floor** (e1935082). The sort answers each
  room's `floor`; three live sorts filed no tatami fixture (the recorded one
  filed two) and answered tatami for exactly those two rooms. `tatami` and
  `wood` read as timber for sound.
- **A stair is a room of its own** (e8019559). Each of the solver's stair
  halls is a planned room the tier makes, replacing the plan's stair edge:
  6 halls for the shrine's 3 stairs. It also settles the "unconfirmed" bullet
  of §1.205 -- the second storey stood over unwritten stair space.
- **The World Browser draws a storey as the lab does** (33a517e6), the whole
  building the plan holds on one frame, the rooms nobody has come near yet
  faint; rendered from the re-laid shrine. Found on the way: the pipeline
  drawer's map had never drawn (c0f595de).

Residuals: `docs/UNBUILT_WORLD.md` §1.209 (floor words the sound tables do
not hold) and §1.210 (what the stair halls left open).

## Open, registered

The rest of what the chat showed is registered in four entries:
`docs/UNBUILT_WORLD.md` §1.205 (the opening re-authors the planned layout),
`docs/UNBUILT_PERCEPTION.md` §1.206 (words in the view that break),
`docs/UNBUILT_PIPELINE.md` §1.207 (prose the world does not hold) and §1.208
(two frames, a lagging station, a full mind).

## Corrections to the first report

- "Five of eleven rooms unplaced" was five *fixtures*: the layout tier's
  `moved`/`unplaced` counts are anchors. All eleven rooms were laid out.
- The interaction loops on turns 4590 and 4591 were legitimate: after her own
  frame's beat, Tamamo stood in the player frame's hallway.
