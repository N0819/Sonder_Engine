# Maze experiment: the arm registry

Every arm of the spatial-learning experiment, what question it was run to
answer, and what changed between it and the arm before. Findings live in
[`SPATIAL_LEARNING_EXPERIMENT.md`](SPATIAL_LEARNING_EXPERIMENT.md); routes
live in [`MAZE_RUNS.md`](MAZE_RUNS.md). This file exists so that no result is
ever compared against a baseline it does not belong to.

That is not hypothetical. Two mistakes on this experiment came from exactly
that: `shortest_path` bound its endpoints as default arguments, so every
resized maze silently measured the distance to the 6×6 corner, and
`render_maze_runs.py` hardcoded the 9×9 seed, so any other arm's real routes
were drawn against invented walls. Both produced numbers that looked fine.

## Reading an arm

Each results file (`--out`) opens with a `meta` line carrying grid, algo,
braid, seed, goal, optimal, the models, the commit and the exact argv. Rebuild
its document with:

```bash
python tools/render_maze_runs.py <runs.jsonl> -o docs/MAZE_RUNS.md
```

Arms recorded before that header existed are marked *pre-header* below; their
maze parameters here are the reconstruction, and the renderer will refuse them
until a `meta` line is added by hand.

## Fixing code mid-experiment

A Python process cannot reload its own modules, so a bug found at beat 60 used
to mean choosing between finishing an arm you know is wrong and throwing away
hours of accumulated memory to fix one line. Neither is a good trade, and the
second is why `--state` exists.

```bash
# run with a checkpoint (rewritten after every beat, costs nothing unused)
python tools/maze_experiment.py ... --state /tmp/arm.json --out /tmp/arm.jsonl

# stop it, fix the code, then carry on from the beat after the last completed one
python tools/maze_experiment.py ... --state /tmp/arm.json --resume /tmp/arm.json
```

Everything the character *is* — memory, mind models, `chat_chars.state`, route
knowledge, his position — already lives in the run's SQLite database, so resume
only has to rescue this process's own bookkeeping: which run and beat, the
route so far, finished-run metrics, and the RNG stream. It refuses to resume
onto a different maze, since that would carry one maze's route knowledge into
another.

A beat inserts its turn row before any stage runs and checkpoints only once it
completes, so killing the process in between — exactly what stopping to fix
code does — leaves a turn for a beat that never happened. Resume discards those
rather than colliding on them.

## Standing constraints

- **Maze size is capped at 10×10.** Larger grids cost hours per arm for
  little extra signal — the 12×12 has nearly double the junctions of the 9×9
  at the same mean trap depth, so it tests endurance rather than navigation.
  The one 12×12 arm below predates the cap and is being finished because it
  carries a matched pre-fix baseline that nothing else can supply.
- **One variable per arm** wherever possible. Where an arm bundles two, it
  says so and says what that costs.
- Character is the only *deliberating* role (`x-ai/grok-4.20`); director,
  perception, mapping and utility transform rather than decide and run on
  `inception/mercury-2`. Reasoning `low` throughout. See the experiment doc §5.

---

## Arms

| # | maze | question | code state | status |
|---|---|---|---|---|
| A1 | 6×6 dfs | does anything carry across runs at all? | pre-header | done — retention proven, run 2 replayed the exact 20-move optimum from a wiped context |
| A2 | 9×9 kruskal | does it hold at triple the junctions? | pre-header | done — the baseline table in the experiment doc |
| A3 | 9×9 kruskal, affordances ablated | how much of A2 was the visited-exit markers? | pre-header | done |
| A4 | 9×9 kruskal + frontier arm | does `no_new_ground_that_way` break dead-end corridors? | pre-header | done |
| A5 | 9×9 kruskal + sight arm | do corridor sightlines help? | pre-header | done — best arm; reached the goal |
| **A6** | **12×12 kruskal** | does it scale, and does `worked_before` stop the run-3 drift? | `f8678f2^` → killed at 70 beats | **baseline** for A7 (bearings absent) |
| **A7** | **12×12 kruskal** | same maze, bearings fix present | `f8678f2` | stopped at run 2 — cost |
| **A8** | **9×9 kruskal** | replication of A2's maze with everything since | `f8678f2` | **running** |
| **A9** | **9×9 kruskal** | can a cheaper character model do the job? | `e005100` | **running** |

### A6 / A7 — the bearings pair

The only clean single-variable pair in the set: same maze, same seed, same
models, same everything, differing solely in whether a visible onward exit is
named by bearing or only counted. A6 was stopped at 70 beats of run 1 when the
cause was found, so the pair is complete only for the opening stretch.

A6's failure is the one A7 exists to retest. Between beats 41 and 53 he
oscillated in the `0505`/`0504`/`0605` pocket, and the Director answered him
four separate times with *"moves west into Chamber 0504 and stops, as no
further west exit exists"* — he had been given `onward_exits: 1` for that
chamber with no bearing, and read it as a promise to continue west. The one
other way out went north.

Matched-beat comparison through beat 20:

| | A6 (no bearings) | A7 (bearings) |
|---|---|---|
| immediate reversals | 4 (22%) | 2 (11%) |
| rooms found | 12 | 14 |

A6 in full, before it was stopped: 70 beats, 31 rooms, 18 reversals (26%).

At 47 beats, the fullest matched comparison the pair reached:

| | A6 (no bearings) | A7 (bearings) |
|---|---|---|
| immediate reversals | 10 (22%) | **3 (7%)** |
| rooms found | 22 | **26** |
| new-ground rate | 47% | **55%** |
| beats in the `0505` pocket | 19 of 70 | 0 of 47 |

Reversals fell by two thirds while discovery ROSE, which is the signature
worth having: not a more cautious character, but one no longer spending beats
re-deciding what sight had already settled. The pocket figure is weaker
evidence than it looks — he routed elsewhere entirely and never faced that
trap, so he did not resist it.

**A7 was stopped during run 2, on cost.** Final: run 1 85 beats / 33 rooms /
24% reversals; run 2 29 beats / 8 rooms / 37% reversals, locked. 114 character
calls and 60 minutes of generation time for those two runs. A 12×12 costs
roughly triple a 9×9 per run and, at the same mean trap depth, buys endurance
rather than navigation — which is why the standing cap is 10×10. The bearings
result above was already banked; run 2 was buying nothing but a demonstration
of the circling lock, which is now reproduced far more cheaply as a unit test.

### A9 — the cheap-character arm

Same maze as A8, same support models (`inception/mercury-2`) at the same
reasoning (`low`), differing only in the character: `arcee-ai/trinity-large-thinking`
in place of `x-ai/grok-4.20`. Character is the sole deliberating role, so it is
the only one where model choice should show, and it is also the expensive one
— if a cheaper model navigates comparably, that is the whole cost profile of a
session.

Reasoning is deliberately NOT matched: trinity runs at `medium` against grok's
`low`. Trinity is a thinking model and reasoning-dependent, so pinning it to
`low` would measure a handicap rather than the model. The arm therefore answers
"is trinity good enough at the setting one would actually use" and not "is
trinity better than grok at equal effort" — a different and less useful
question, since nobody would run it at low.

A first launch had to be discarded: `--reasoning default=low` leaves
per-role entries already in `engine.db` standing, so `perception` was running
at `high` while A8 ran it at `low`. Perception is the character's entire input,
so that would have made the two arms incomparable while looking like a clean
model swap. Every support role is now pinned explicitly.

Early latency is far more variable than grok's steady 25–35s — observed 7s to
79s per call — so the throughput question needs a full run to answer, not a
sample.

### A8 — the 9×9 replication

Reproduces A2's maze exactly (81 rooms, 21 junctions, 25 dead ends, 16 false
branches 3+ deep, optimal 20) against the current tree. It bundles two changes
versus A2 — `worked_before` outcome feedback and the bearings fix — so it is
not single-variable. It is still worth running because the two act on
different things and the A2 table separates them: bearings change how
efficiently unknown ground is cleared, whereas the run-3-to-5 *drift* in A2
was a route-retention failure, which bearings cannot explain. If the drift is
gone, `worked_before` is the credible cause.
