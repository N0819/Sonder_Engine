# Design: the gods expand the maze

**Status:** designed, not built. Depends on nothing that is not already in the
engine; the work is in the harness and in one deterministic guard.

Every arm so far has asked the same question: *can a character learn a space
from nothing?* Vesk has now answered it several times over, and the answer is
bounded by how many bugs were in the way rather than by anything about him.

The more interesting question is the one we have never asked. **Can a mind
REVISE a map it already trusts?**

That is the harder cognitive act and the commoner one in play. A player returns
to a town after a fire. A corridor is bricked up. The tavern's back door now
opens on a stair that was not there. A character who can only learn from a
blank slate is a character who must be wiped every time the world moves.

---

## 1. The move

Keep the character. Keep his database, his place graph, his memories, his
beliefs about which chamber has no west exit. Then, in fiction:

> **The gods have expanded the maze, and offer you greater reward.**

Where the shrine stood, new sections open. The 7×7 he knows becomes the
western wing of something larger. His map is not wrong — it is *incomplete in
a way it does not know about*, which is a different and much more interesting
epistemic state than ignorance.

## 2. Why the in-fiction framing is load-bearing

It is not decoration, and it is not flavour. It is the fix for a failure we
have already measured.

When the run boundary was a bare teleport, he inferred *"the maze layout
sometimes differs from memory"* — a correct induction from a Director that had
lied about geometry — and thereafter discounted his own true map. That belief
cost more than the bug that caused it. The interlude
(`tools/maze_experiment.py:run_interlude`) exists because of it.

An unannounced expansion would teach exactly the same lesson, and this time the
engine would be the one lying. **A world that changes must say it changed**, or
every subsequent contradiction is evidence that memory is not worth keeping.

The announcement also does something the bare change cannot: it makes the
character's response *legible*. A character told the maze has grown and who
then goes to look is curious. One who runs his old route first, confirms it,
and then explores is methodical. One who ignores it is task-fixated. Those are
different characters, and without the announcement they are indistinguishable
from one confused character.

## 3. What it measures that nothing else does

| | learn from blank | revise a known map |
|---|---|---|
| frontier | everywhere | only at the seam |
| his existing map | absent | correct and load-bearing |
| failure mode | wandering | trusting the old route past the point it stops being optimal |

The measurement is **beats to first new chamber**, and then **whether the old
route degrades gracefully**. A character who has genuinely revised will use the
known wing as a fast corridor — sprinting it, now that running exists — and
spend his deliberation at the seam. A character who has merely memorised will
keep running the old optimal path to a shrine that has moved.

That second failure has a name in play: it is the NPC who keeps going to the
tavern that burned down.

## 4. The three ways to do it wrong

**Rewriting the rooms he knows.** Do not move a wall he has walked past.
Expansion must be strictly additive at first, because additive change tests
revision while contradiction tests something else — recovery from a false
belief — and mixing them makes neither readable. Contradiction is a *later*
arm, and a good one: brick up a corridor he relies on and watch whether
`disproven` does its job.

**Letting the announcement carry the map.** The gods say the maze has grown
and that the reward is greater. They do not say where, how big, or which way.
The moment the announcement contains topology it stops being a prompt and
becomes the answer — and the arm measures nothing.

**Relocating the goal silently.** If the shrine moves, his `routes_that_worked`
now point at a room that no longer rewards him, and he has no way to know. The
goal moving is fine; the goal moving *unannounced* reproduces the reality-break
this design exists to avoid.

## 5. Implementation sketch

1. **A second SVG** whose western 7×7 is byte-identical to `maze7x7-a11.svg`,
   with new sections east. `maze_from_svg` already refuses anything malformed,
   and `maze_fingerprint` will correctly call it a different maze — so
   `--resume` must be given an explicit `--expand` to accept the substitution
   rather than having its guard weakened.
2. **A deterministic seam check** in the harness: assert that every room the
   character has walked keeps its id, its exits, and its features. If the
   expansion perturbs known ground, the arm is measuring contradiction and
   should say so rather than discovering it later.
3. **An interlude variant** — the same shape as `run_interlude`, carrying the
   announcement and nothing else. It is his own experience: he was told.
4. **`place_graph` needs no change.** New rooms are simply absent from it, so
   the seam reads as frontier the moment he sees it, and `_frontier_hops` will
   point him at it. This design is largely a test OF the place graph rather
   than a change to it.

## 6. Keeping him

His database is the experiment. It lives at
`~/sonder-maze-characters/` rather than in `/tmp`, because a character worth
running future arms against should not be one `tmpwatch` away from gone, and
never in the repo (`*.db` is correctly gitignored — his memories are content,
not code).

Snapshot before each new arm, named for the arm it precedes. A character who
has been through an expansion cannot be un-expanded, and the pre-expansion
state is the only baseline the post-expansion numbers mean anything against.

## 7. The experiment that would settle it

Two arms from the same snapshot. One expands the maze with the announcement,
one expands it silently. Measure beats-to-first-new-chamber, and whether a
belief of the form *"the maze rearranges itself"* appears in either character's
reasoning within ten beats.

The prediction is that the silent arm produces that belief and then navigates
worse **in the wing it already knew** — which, if it holds, is the cleanest
possible demonstration that an unexplained world change damages more than the
part of the map it touched.
