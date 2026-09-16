# The opening is planned before the Director runs

Status: BUILT 2026-09-16 (this note and the code landed together; the
conformance row is in `Design.md`, the residuals in `docs/UNBUILT_PIPELINE.md`
§ 1.163). Owner rulings that shaped it are quoted where they bind.

## 1. The defect

Two launches open a story, and neither plans the ground it opens on.

- **A scenario chat** (`POST /api/chats`, then the first `POST
  /api/chats/{cid}/turns`) inserts the row and runs the establishment plan.
  The Story Planner runs only if the player opened the Writers' Room first
  and typed a mandate. Chat 126 did: the room drafted a three-room package at
  turn -1 in 21 calls, asked for `request_location` to make the parlor an
  institution, nobody answered, the package was never published, and the
  opening minted its own rooms -- one of them a back room nobody had seen,
  written as a described room with a guessed `light: dim`
  (`tests/test_opening_room_stubs.py` carries that half of the story).
- **A greeting quick start** (`story/greetings.start_story`) extracts minds,
  optionally runs the lived-location generator (the town planner, from lore
  and the UI brief), plants what it made, and runs the same establishment
  plan with the greeting as the scenario.

Neither says WHICH room the opening is in. `agents/director._opening_rooms`
guesses by string-matching planned room names against the scenario text
(`structure.planned_rooms_named_in`), and nothing derives the rooms a passage
itself implies -- a parlor's reception and its treatment room -- from the
passage. The plumbing to be planned before the first beat already existed:
`plot_packages._latest_turn_idx` answers -1 for a story with no turn, so a
package published then is visible to turn 0, and `scene.seed_scene_from_plan`
opens the scene inside whatever the registry holds. What was missing was
anybody running the planner at that moment, and a channel for placement.

## 2. What runs now

One step, `story_planner.run_opening_plan`, before the first turn row exists,
on both launches:

```text
scenario chat:   turn_new(idx 0) -> run_opening_plan -> INSERT turn 0 -> establishment plan
greeting start:  minds -> [lived location] -> run_opening_plan -> INSERT turn 0 -> establishment plan
```

It runs the Story Planner in a new regime, `opening`, under an engine-minted
mandate, with a task carrying the passage (scenario or greeting), the present
bodies (player and attached cast), and the planted structures if a location
was generated. The planner reads with its ordinary tools and writes one
package: `plan_rooms` for the rooms the passage implies, as prose-free stubs
joined to the planted town where there is one; `place_at_opening` for where
each present body stands; a `director_note` saying what the plan means. It
publishes at turn -1. The establishment plan then runs with `planned_rooms`
(as before) and `opening_placements` (new) in the establish payload, and the
establish stage furnishes the occupied rooms and places bodies where the plan
put them.

The result is recorded once, whatever happened, in the world row
`opening_plan` ({published, calls, steps, stopped, notes, placements, error,
at, trace}), and the planner's line goes to the room thread. `trace` is one
row per tool call -- the step, the tool, and a refusal or error when there
was one -- because a planner exchange is captured against a TURN
(`persist/llm_capture`, keyed on `turn_id`) and this stage runs before turn 0
exists, so without it the opening plan's calls leave no trace at all. It
rides the loop's advisory `on_event` seam, so it cannot change what the room
does. The launch never fails
because the plan did: a raise inside the planner is caught, recorded, and the
opening runs as it always did.

## 3. The four decisions (owner, 2026-09-16)

1. **A standing opening mandate, and no questions.** The step mints one
   mandate (`story/opening_plan.mint_opening_mandate`) scoped to the opening,
   covering `plan_rooms`, `director_note` and `place_at_opening`, expiring
   with turn 0. In the `opening` regime the planner's `questions` are dropped
   and no `grants` are read: a planner that cannot decide publishes what it
   has and says what it left out in the note. This is the exact stall chat
   126 hit, removed. The mandate carries no `plan_entity`, `create_people` or
   `request_location`.
2. **A hard budget with a silent fallback.** `OPENING_STEPS` (10) and
   `OPENING_WALL_SECONDS` (150), one pass, no resumption. Nothing validates
   in time: the establish runs as today and `opening_plan.stopped` says why.
3. **Rooms only at the opening; a charter is an OPTION, never assumed.**
   "The planned rooms being a charter needs to be an option, not something
   the planner immediately assumes." The opening mandate does not permit
   `request_location`; the planner card says so in the OPENING paragraph;
   the explicit option is the lived-location control on the greeting screen
   (and, later, the same control on the new-chat screen -- § 6). If the
   passage implies an institution the planner writes that into the director
   note, and the Room can promote it on any later turn.
4. **The planner picks the room.** When the passage is ambiguous the planner
   places the player and says why in the note. The establish stage's string
   match survives only as the fallback for a story that has no placements.

## 4. The seams

| What | Where |
|---|---|
| The capability, the mandate, the keys, the placements reader | `story/opening_plan.py` (`OPENING_CAPABILITIES`, `mint_opening_mandate`, `opening_placements`, `OPENING_PLAN_KEY`, `OPENING_PLACEMENTS_KEY`) |
| The placement operation | `story/plot_packages.py` (`place_at_opening`: shape, preview, apply; `ROOM_FIELDS`; the shape line) |
| The vocabulary | `story/mandates.MANDATE_CAPABILITIES` (`place_at_opening`) |
| The regime and the runner | `agents/story_planner.py` (`run_opening_plan`, `OPENING_STEPS`, `OPENING_WALL_SECONDS`; `run_planner(regime="opening")` drops questions and grants) |
| The card | `prompts/story_planner.txt` (OPENING) |
| The two launches | `story/greetings.start_story` (before the turn insert), `web/app.turn_new` (idx 0, before the insert) |
| The reader | `agents/director.director_establish` (`opening_placements` in the payload; `_opening_rooms` reads the placed rooms first; a placed body the model positioned elsewhere is moved back, with a warning) and `prompts/director_establish.txt` (WHERE THE OPENING STANDS) |
| The record | world rows `opening_plan`, `opening_placements`; the room thread |
| Tests | `tests/test_opening_plan.py` |

`place_at_opening` is a SHORT operation: `{who, room, at?}`. `who` is the
player or an attached cast member by name (checked against
`reserved_identities(...)["cast"]` and the persona); `room` must be a room the
world holds or the package plants (the same `_room_known` every room field
uses, and the same in-package ordering `plan_rooms` gets); `at` is free text
the establish hands on as a station hint. Applying it writes the
`opening_placements` row; nothing else lands, because where a body stands at
the opening is the establish stage's to write into the scene.

Why not `arrival`: it moves charter bodies and planned entities through
charter surgery, and the player and the cast are neither.

## 4a. What the first five live runs found (2026-09-16)

Five quick starts from one greeting, before anything was tuned. None
published. Three defects, all in this note's own work:

- **The budget cut the plan off one call from the end.** Chat 127 spent 17
  calls over the full 10 steps, drafted every operation, validated clean,
  wrote "the opening package is drafted and ready" -- and stopped on `steps`
  without calling `publish_package`. `OPENING_STEPS` is 24 and
  `OPENING_WALL_SECONDS` 360 now; the shape of the work is read, open, draft
  once per operation, validate, publish, and the model does one operation per
  draft call.
- **A placement drafted before the rooms it names could never validate.**
  `preview_package` taught itself about planted rooms only from `plan_rooms`
  operations it had already walked past, so chat 131's two
  `place_at_opening` at `reception` were refused with "exists nowhere and
  this package does not plant" while the same package planted `reception`
  two operations later. The planner then spent 17 calls drafting, removing
  and re-drafting rooms that were right from revision four. A package lands
  in ONE transaction, so its rooms are now known to the whole preview before
  any operation is read.
- **Nothing recorded what the room was doing.** See `trace` above.

One failure in the five was neither: a provider read timeout of 10s killed
the plan and the establish call together (chat 130).

## 5. Measures

- **Chat 126's scenario, replayed fresh:** Hinami placed in a planned
  reception room by the plan, the treatment room a stub, furnished on the
  beat she looks through the door. (To measure after landing.)
- **The stall class:** `opening_plan.stopped` never `questions`; a package
  with `request_location` cannot publish under the opening mandate
  (`tests/test_opening_plan.py`).
- **Latency:** `opening_plan.calls` and the wall on the two launches, against
  chat 126's 21 calls and three minutes for a plan that never landed.

## 6. What is left

- The new-chat screen has no lived-location control; the charter option is
  explicit only on the greeting screen today.
- The fan-out of the opening (`docs/UNBUILT_PIPELINE.md` § 1.163) is still
  the destination: with rooms planned and bodies placed, the establish
  stage's remaining work is row-shaped.
- The Japanese planner and establish cards do not carry the two new
  paragraphs (english-first mandate, 2026-09-09).
