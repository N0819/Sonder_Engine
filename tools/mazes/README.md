# Authored mazes

Maze SVGs the experiment harness can run directly:

```bash
python tools/maze_experiment.py --svg tools/mazes/maze7x7-a11.svg --agent random
```

**These files are experimental apparatus, not assets.** An arm's results are
only interpretable against the maze it ran on, so a file here must never be
edited in place once an arm has used it — add a new one. `maze_fingerprint`
hashes the walls, so an edited file will at least stop `--resume` from carrying
one maze's route knowledge into another, but nothing can repair a rendered arm
whose maze changed underneath it.

## Format

The `<line>`-per-wall SVG that [mazegenerator.net](https://www.mazegenerator.net/)
emits. `maze_from_svg` infers cell size from the coordinate spacing, so any
offset and scale works, but:

- Only orthogonal segments. A diagonal is rejected.
- **Exactly two gaps in the outer border**, the entrance and the exit. They
  become start and goal — reading order (top edge, then bottom, then left, then
  right) decides which is which. To swap them, move a gap in the source file.
- The exit must be reachable from the entrance. An unsolvable maze parses
  perfectly well and would read as a total learning failure.

Path-based or `<rect>`-based maze SVGs need a different parser and are refused
rather than half-parsed.

## Files

| file | grid | optimal | shape |
|---|---|---|---|
| `maze7x7-a11.svg` | 7×7 | 28 moves | corridor maze — 4 junctions, 6 dead ends, 57% of rooms on route |

Arms are registered in [`docs/MAZE_ARMS.md`](../../docs/MAZE_ARMS.md), which
also explains what each maze's shape does and does not measure. The parse of
each file here is pinned by `tests/test_maze_svg.py`.
