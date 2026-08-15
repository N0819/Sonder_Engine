# Maze runs — index

Move-by-move traces, **one document per arm**. Each is the record of runs that
happened once and cannot be reproduced: the models are not deterministic and
the character's accumulated memory is itself part of the experiment, so a
rendered arm is evidence, not a build artifact.

This file used to BE a trace, and rendering a second arm onto it destroyed the
first — the sight arm's traces were replaced by A8's and had to be recovered
from git. `render_maze_runs.py` now refuses to overwrite an existing document
for that reason.

| arm | maze | character model | outcome | document |
|---|---|---|---|---|
| A5 | 9×9 kruskal | grok-4.20 | 2/5 reached; run 2 exact optimal, then drift | [A5-9x9-sight-arm.md](maze/A5-9x9-sight-arm.md) |
| A8 | 9×9 kruskal | grok-4.20 | 2/5 reached; **run 5 exact optimal**, no drift | [A8-9x9-grok.md](maze/A8-9x9-grok.md) |

Arms, their questions and what each may legitimately be compared against are
registered in [`MAZE_ARMS.md`](MAZE_ARMS.md); the findings are in
[`SPATIAL_LEARNING_EXPERIMENT.md`](SPATIAL_LEARNING_EXPERIMENT.md).

## Rendering a new arm

```bash
python tools/render_maze_runs.py <runs.jsonl> \
    -o docs/experiments/maze/A9-9x9-trinity.md \
    --note "one line saying what this arm was testing"
```

Name the file for the arm — number, maze, character model. Then add its row to
the table above. The maze is rebuilt from the `meta` header the harness writes
into the results file, so a document can always be regenerated from its own
JSONL, and never from another arm's.
