# Observed: Home 10 (chat 173), 2026-10-12 late

The owner played Home 10 on the server started at 21:54, after commit
a5bc0582 (windows, the lab-style editor) and before 03ec924e (doorway-clear
furniture), while the assistant kept editing the working tree the server ran
from. Three turns: the opening (4623), Tamamo's beat in the bubble frame the
opening split off for her (4624, frame 12 "Bubble — Tamamo": empty input and
no page by design, created 10 ms before the player's turn), and the player's
"You yawn as you open your eyes stretching out a bit as you look around."
(4625).

Method: a read-only workflow (engine.db opened `mode=ro`, no model calls):
six investigators -- turn mechanics, the opening and the Writers' Room,
layout and world state, version skew, the page as fiction, the characters'
minds -- each finding then put to a skeptic told to refute it from the rows
and the code. 45 findings, none refuted, several corrected; merged here into
15. Spot-checked by hand: the bubble frame and the commit order, the
checkpoints taken before 4624 committed, `_extract_balanced_object`'s
first-object rule, and the room designer's recorded TypeError.

The 45 verified findings merge into 15. They are ranked by what the player met first, then by whether they still happen on HEAD 03ec924e after a restart. Only item 4 comes from the version skew. The server that caused it (pid 1984990, started without `--reload`) is still running.

## On the page

**1. Tamamo was split into her own bubble while still within earshot, so her walk past Hinami's door happened offscreen.** High; recurs on HEAD.
- Saw: page 2 says "Nothing moves…". The present frame holds no Tamamo, so a call from Hinami's room would reach nobody.
- Origin: the opening commit (v56296) split her by counting rooms (`attended_rooms(hops=1)`). The sound model says the opposite: it carries her voice to Hinami at full strength. That contradicts the module's own premise that a split means "not within earshot" (`world/spatial_bubbles.py:39`).
- In turn 4624 the encoder put her in the court, though the prose kept her in the Hall. The rejoin check reads only where a beat ends (`world/spatial_frames.py:1516`), so she never rejoined. Her clock now runs 40 s ahead of the present.
- Fix: decide split and rejoin with the same sight and sound models perception uses, and check at every step of a beat. A bubble lives only as much time as its parent has lived. The room in the state change must be the room in the prose.

**2. The look-around re-tells the opening and never mentions the chest, the table or the lamp.** Medium; recurs.
- Origin: in the dark, perception sends the room's notes and the futon she is touching labelled as "sight" (`agents/composer.py:963`, v56306). It sends nothing of what she knows about her own room. The narrator card then asks for a full map of the room (`language_packs/en/cards/system_prompts/prompts/narrator.txt:59`).
- Fix: darkness takes away sight, not knowledge, and each percept is labelled by the sense that actually carries it. A look reports only what it newly found.

## Broken turns

**3. Rerolling, editing or deleting the yawn (turn 2) would wipe out Tamamo's beat.** High; recurs.
- Saw: nothing yet, but the buttons are live. Checkpoint 2 was taken at 23:15:10, before turn 4624 committed at 23:16:02. Restoring it puts her back in the roost and deletes memory 30833, while 4624's turn rows stay.
- Origin: at turn creation the bubble beat took turn number 1 ten ms before the player's line took number 2. `_other_frame_has_advanced_past` (`web/app.py:974`) compares turn numbers, not commit order.
- Fix: a checkpoint can be restored only if every lower-numbered turn had committed when it was taken.

**4. The version skew killed the room designer on the running server.** High; the TypeError does not recur on HEAD, but the underlying class does.
- Saw: the Hall and the Court stay undescribed, and every room design on this process fails. Read-time furniture placement uses the old rules.
- Origin: `spatial_fov` was loaded at 21:54 from a5bc0582. `director_rooms` was loaded later from the edited tree and calls `anchor_cells(…, raw=True)`, which the old `spatial_fov` does not accept.
- Capture 6096's "invalid JSON" was repaired locally and is not what failed.
- Fix: one process runs one version of the code. Fingerprint the code at startup, refuse turns when it changes, and record the fingerprint on every turn.

**5. Tamamo's character answer was cut off at its first closing brace.** Medium; recurs.
- Her notebook, note, tells and changes (capture 6087) were dropped with no warning. `_extract_balanced_object` (`llm/llm_quality.py:64`) kept only the first JSON object; the local repair would have kept everything.
- Fix: never take an object out of the rest of its own answer, and report anything discarded.

**6. Controls the player cannot use.** Medium; recurs.
- For 28 s after page 2, reroll, delete, edit and branch would have returned a 409 telling the player to "Abort it". No Abort control reaches the bubble's beat (`web/app.py:717`).
- On ordinary beats it is worse: the bubble's beat takes a higher turn number, so the newest page can never be rerolled while a bubble exists.
- The bubble's own thread shows '…' as its text, next to buttons the server refuses.
- Fix: background work must say what it is and offer a way out. Show only the controls the server would accept.

## A wrong world

**7. The grounds split the court in two and cut off the storehouse.** High; recurs.
- Saw: the mountain path runs from the great doors straight through the court. From the doors' half of the court, a walk to the storehouse is blocked at 0 paces.
- Origin: the launch layout code, not the model; replaying captures 6079–6081 on HEAD gives identical geometry.
  - Any path with no stated start becomes the approach to the front door (`world/layout_solver.py:2069`).
  - The bridge carves the court around it (`world/layout_bridge.py:2080`), points doorways at a third place or at nothing, and never lays the storehouse's path.
  - `refusals()` (`world/layout_bridge.py:1397`) checks none of this.
- Fix: lay what the plan joins, or refuse the layout. Both sides of every doorway must meet across one wall and every place must be one connected floor; otherwise fall back.

**8. The opening furnished planned rooms without seeing what the plan already held.** High; recurs.
- Saw: Hinami's futon lies under a waist-high bed, and that bed hides her only door from her. Tamamo's view lists two nests.
- Origin: director_establish (v56293) gets `planned_room_brief` (`world/structure.py:1851`) with no fixtures and no room size, yet its card tells it to furnish the room. The merge then keeps both sets. This is the known UNBUILT §1.205.
- Fix: any stage that furnishes a planned room is given the plan's fixtures and the room's size, and describes those fixtures instead of inventing new ones.

**9. Tamamo grieves for a daughter who is asleep just off the same hall.** Medium; recurs.
- Saw: she whispers "Come when you can, little one", and her goal and memory 30833 now treat Hinami as away.
- Origin: the Room's opening package put "Hinami is home" only in a note for the Director, with no `known_by` fact for Tamamo (capture 6075). Her card's worry about Hinami's visits reached her three times (capture 6087).
- Lesser faults in the same mind:
  - her own ladder was marked "UNTRIED";
  - her walk never entered her map;
  - the door she opened came back to her as news;
  - her opening memory had no date.
- Fix: placing a body is incomplete until the minds who would know about it are told. The launch settles any card worry the opening already answers. A walk earns every room it crosses, every sound records who made it, and memory clocks are compared by frame lineage.

**10. What Tamamo's ward-reading found was stored nowhere.** Medium; recurs.
- Saw: nothing. The slack wards, the dimmed ward-stone and the four-toed tracks exist only in the Director's prose (v56309).
- Origin: the encoder wrote the act as a pose only. The repair pass's false claim that it was "already encoded" was accepted (`agents/director_repair.py:1341`). Examined things also need full sight to be delivered (`agents/perception.py:576`).
- Fix: what a reading finds must be written into the world. A refusal is checked against the event it cites. A reading is delivered through the sense that made it.

**11. Travel clothes in bed, and zōri on the torso.** Medium; recurs.
- Origin: the opening card treats the authored outfit as authoritative whatever the body is doing (`language_packs/en/cards/system_prompts/prompts/director_establish.txt:50`). In turn 4624's commit, taking off and putting back on Tamamo's zōri placed them by name, which defaults to the torso (`story/attire.py:161`). The notice telling the Director which garments are guessed also misreports authored ones.
- Fix: a garment keeps its place and description through removal. A notice about the clothing record is computed from the record.

**12. One stair, many records that disagree.** Medium; recurs.
- Saw: the plan's ladder on the west wall was laid on the north wall. Its foot and head sit on different cells, and the upper stair hall overlaps the roost.
- Origin:
  - the stair's wall is dropped (`world/layout_bridge.py:548`);
  - doorway offsets are written one way (middle/(w−1)) and read another (start/(along−w));
  - a doorway's width reaches only one side;
  - the solver and `doorway_clearance` disagree about stair openings;
  - the brief reads the `fixed` sides backwards;
  - since 03ec924e the designer reads raw seed positions that the world no longer uses.
- Fix: one record of each doorway's opening and one placement rule, read the same way by every reader.

**13. Perception loses track of which frame the player is in.** Medium; recurs.
- Origin: `_composer_prev_ledger` (`agents/perception.py:4148`) reads "the previous turn" across all frames. Here that was the bubble's turn, so v56306 treated everything as first seen. The bubble also composed a "player" view, because an observer with no room is let through by `agents/composer.py:2504`.
- Saw: hidden on page 2. In a scene with a companion, she would be announced as arriving.
- Fix: an observer's previous record is its own. A frame composes nothing for a body it does not hold. A missing room is treated as closed.

## Slow or confusing setup

**14. A slow, silent launch, and a request that can only be answered yes.** Low; recurs.
- Saw: no story text for about 90 s after Begin. The reply to the first line appeared before the opening above it.
- Origin: `turn_new` (`web/app.py:6599`) re-ran the opening Planner pass over ground already published at 22:51, and posted a stale "Go ahead.". The opening's events are thrown away (`:6678`) instead of streamed. "The room asks" requests a grant but cannot record a no.
- Fix: a launch stage checks whether its work already exists. Every beat is streamed. Every answer to an engine question can be recorded.

**15. The engine's own records misled this investigation.** Low; recurs.
- Turn 2's events row reads "Hinami attempts to Hinami yawns…" (`agents/director.py:7182`).
- The designer filed the TypeError as the rooms' own failure, logged only at INFO (`agents/director_rooms.py:2773`).
- `_check` treats its own exception as a clean result.
- A repaired answer is captured as failed (ok=0).
- The Room's calls before launch are not captured.
- Fix: one record per beat; engine faults reported as faults; checks that cannot run say so; capture switched on inside `run_planner`.

**Refuted:** none. The skeptics' corrections are already included above.

## Do now
1. Restart the play server now, and again after every engine edit. Five fixtures will move under the characters, but nothing stored needs repair.
2. Don't reroll, edit or delete turn 2 of Home 10, or turn 2 of chats 167 and 170.
3. Home 10 cannot measure the doorway fix. A fresh story on HEAD will still run into items 7, 8 and 12.

## Fixes by class
- Order by commit, not by turn number: 3, 6, 13.
- Perception decides frames: 1.
- One record per fact: 7, 8, 11, 12.
- Knowledge reaches minds only through a channel: 2, 9, 10.
- One code version per process, and records that tell the truth: 4, 5, 15.
- The launch skips work already done and shows what it is doing: 14.

## Owner questions
1. May a bubble beat be limited to the time its parent has lived? That would limit the no-freeze ruling.
2. May the opening take off parts of an authored outfit when it puts a body in bed?
3. Should a body placed in its own home arrive already knowing its rooms? And who records who lives there: code at placement, or the Room?
4. When the code changes under a running server, should it refuse turns or only warn?