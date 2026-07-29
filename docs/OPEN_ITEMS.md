# Open items

Known defects and unfinished work, carried out of the alpha 6.0 session.
Newest first. Delete an entry when it lands — this file is a worklist, not a
history; the history is `CHANGELOG.md` and the git log.

## 0a. The Director can put words in a character's mouth

**Found:** live, alpha 6.0.2 session. **Not fixed.**

A character agent declared silence — empty sequence, `stop_reason: "natural
silence"`, no `dialogue_log` entry — and the Director's `resolved_event` said
"<the character> adds a further comment" anyway. Perception rendered a speech
event with no content, and the narrator, having nothing to quote, dressed the
absence as inaudibility: the character "murmurs something" whose "words don't
quite carry". Read as a muffling bug; was a fabrication.

The player side of this boundary has a guard (`_check_player_act_authority`).
Characters have none, so nothing anywhere objects when the Director authors
conduct for a mind that owns it.

The fix is the mirror of the player check, at `director_resolve`: speech
attributed to a character who declared none this beat is stripped and warned.
It generalises past this case — it catches every content-free "X says
something", whatever produced it.

## 0. Watch: arousal now has a ceiling where it had a floor

**Found:** alpha 6.0.1, while fixing the satisfaction stand-down.

Withdrawing the false stand-down exposes the somatic lift that was underneath
it (`novelty * 0.12 + max(pain, pleasure) * 0.12`). A body at saturated,
unreleased appetite now climbs to the arousal ceiling in about five beats and
pins there until release.

That is probably right — a high-arousal label over high arousal is coherent
where the old behaviour was not, and the arc has a designed exit — but it is
the same missing-equilibrium shape as the bug it replaced, pointing the other
way. Watch whether a long unreleased stretch reads as sustained or as stuck.

## 1. Nothing validates the geometry of an asserted doorway

**Found:** live, alpha 6.0 session. **Priority: do this before any
multi-location story with several characters.**

The scene merge accepts an adjacency a model asserts, with no check that the
two rooms *could* be adjacent. Measured: `r0204 <-> r0303` in the maze scene —
a diagonal in a grid maze, geometrically impossible by construction — sat in
the world model for hundreds of turns and was walked as a real doorway.

`_shield_standing_bearings` (b78af46) protects the bearings of *existing*
edges. Nothing guards the creation of a *new* one.

Why it matters beyond mazes: a Director inventing a connection between two
locations is exactly what happens in a village or a household when a model
reaches for a shortcut, and a fabricated doorway becomes part of every
character's map and every route computed over it. The maze at least has
coordinates to check against; a general scene may not, so the honest fix may be
"require a stated basis for a new edge" rather than a geometric test.

## 2. `survival.py`'s sleep-recovery branch is dead

**Found:** while fixing waking (65da9ce).

`tick_vitals(..., asleep=)` is derived from `scene.contained[x]["mode"] ==
"asleep"` (`spatial.py:3878`) — a **containment** mode ("carried", "pocket",
…), never an awareness level. So the set is always effectively empty: **nobody
has ever recovered stamina by sleeping.**

Consequence already paid: natural waking had to be keyed on the simulation
clock (eight hours) rather than on the rest a body actually needed, because
"rested" is not currently computable. Fix the source and the better rule
becomes available.

## 3. A character cannot revise a bearing they learned wrong

**Found:** run 6 of A13, after the live scene was healed.

`disproven` fires when a doorway fails to exist. Nothing fires when a doorway
exists but the character remembers the wrong heading for it. After the bearing
corruption was fixed in the world, one character kept oscillating in exactly
the pockets whose bearings had been wrong while he learned them — the world was
corrected, his map of it was not.

Related to the broader gap: a character can revise a belief about the world and
has almost no mechanism for revising a belief about themselves. Project
displacement (58b9f1c) is currently the only one.

## 4. JSON validation stalls cost beats

Six-plus across one experiment arm: `mind_model_updates` missing required
fields, `sequence` emitted as a non-list, occasionally prose instead of JSON.
Model-side, and the harness skips the beat and continues — but each one is a
lost turn, and in a story it would be a character who simply did nothing.
Worth deciding whether a bounded retry belongs at the character step.

## 5. `circling` fires on routine movement in familiar space

Flagged during the fully-known-map work (171b53e) and not chased. Honest for a
maze; likely wrong for a resident crossing their own home several times in a
scene. Watch it in the first multi-character story run.

## 6. Watch: nine payload keys is an attention budget

`projects`, `en_route`, `adrift`, `ends_in`, `ground_fully_known`,
`goal_reached`/`goal_held`, `fading`, `project_review`. Each is something a
model must notice and act on, and attention is finite — at some point adding
the tenth marker makes the ninth less likely to be read. Not a problem yet. It
becomes one silently.

## Next experiment

A village-scale run: several characters, thirty turns, ordinary places. It is a
different instrument from the maze and will find a different class of defect —
the maze is saturated and stopped producing new findings after A13. Items 1, 2
and 5 above are the ones most likely to bite it.
