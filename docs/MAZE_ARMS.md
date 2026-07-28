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
| **A7** | **12×12 kruskal** | same maze, bearings fix present | `f8678f2` | **running** |
| **A8** | **9×9 kruskal** | replication of A2's maze with everything since | `f8678f2` | **running** |

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

### A8 — the 9×9 replication

Reproduces A2's maze exactly (81 rooms, 21 junctions, 25 dead ends, 16 false
branches 3+ deep, optimal 20) against the current tree. It bundles two changes
versus A2 — `worked_before` outcome feedback and the bearings fix — so it is
not single-variable. It is still worth running because the two act on
different things and the A2 table separates them: bearings change how
efficiently unknown ground is cleared, whereas the run-3-to-5 *drift* in A2
was a route-retention failure, which bearings cannot explain. If the drift is
gone, `worked_before` is the credible cause.
