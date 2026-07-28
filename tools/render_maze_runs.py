"""Render a maze experiment's actual movements as markdown.

Reads the --out JSONL a run wrote and emits, per run, the maze with each room
labelled by the beat it was first entered plus a move-by-move table annotated
with what each move was (on route, revisit, reversal, dead end, stayed put).

    python tools/render_maze_runs.py <runs.jsonl> > docs/MAZE_RUNS.md

Generated rather than written by hand so it cannot drift from what happened.
Assumes the 9x9 kruskal seed the experiment used; pass a different grid/algo by
editing the constants if the maze changes.
"""
import json, sys
sys.path.insert(0, ".")
import tools.maze_experiment as M

M.GRID = 9; M.GOAL = (8, 8)
W = M.build_maze(grid=9, algo="kruskal")
OPT = [M._rid(c) for c in M.shortest_path(W, (0, 0), (8, 8))]
OPTSET = set(OPT)
CELL = {M._rid(c): c for c in W}
DIRS = {(-1, 0): "north", (1, 0): "south", (0, -1): "west", (0, 1): "east"}
NAMES = M.scene_rooms(W, goal=(8, 8))


def grid(path, mark_optimal=False):
    """Maze with walls; cells labelled by first visit order (or . / *)."""
    order = {}
    for i, r in enumerate(path, 1):
        order.setdefault(r, i)
    lines = ["+" + "---+" * 9]
    for r in range(9):
        mid, bot = "|", "+"
        for c in range(9):
            rid = M._rid((r, c))
            if rid in order:
                n = order[rid]
                glyph = f"{n:>3}" if n < 100 else " ##"
            elif mark_optimal and rid in OPTSET:
                glyph = "  *"
            elif (r, c) == (8, 8):
                glyph = "  X"
            else:
                glyph = "   "
            mid += glyph + (" " if (r, c + 1) in W.get((r, c), ()) else "|")
            bot += "   +" if (r + 1, c) in W.get((r, c), ()) else "---+"
        lines += [mid, bot]
    return "\n".join(lines)


def annotate(path):
    """Move-by-move with what each step was."""
    rows, seen = [], {path[0]}
    for i in range(1, len(path)):
        a, b = path[i - 1], path[i]
        if a == b:
            rows.append((i, b, "—", "stayed put"))
            continue
        (ar, ac), (br, bc) = CELL[a], CELL[b]
        d = DIRS.get((br - ar, bc - ac), "?")
        notes = []
        if b in OPTSET and a in OPTSET and OPT.index(b) == OPT.index(a) + 1:
            notes.append("**on route**")
        elif b in OPTSET:
            notes.append("rejoins route")
        if b in seen:
            notes.append("revisit")
        if i > 1 and b == path[i - 2]:
            notes.append("reversal")
        if len(W[CELL[b]]) == 1:
            notes.append("DEAD END")
        seen.add(b)
        rows.append((i, b, d, ", ".join(notes) or "—"))
    return rows


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: render_maze_runs.py <runs.jsonl>")
    runs = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
    out = []
    out.append("# The maze runs, move by move\n")
    out.append("Actual movements from the sight arm — the configuration that "
               "reached the goal. Same maze, same seed, same models for all five "
               "runs; only the character's accumulated memory differs.\n")
    out.append("Numbers in each grid are the beat a room was **first** entered. "
               "`*` marks the optimal route where he never went, `X` the shrine.\n")
    out.append("## The maze\n")
    out.append(f"9×9 Kruskal, 81 rooms, 21 junctions, 25 dead ends, "
               f"optimal **{len(OPT)-1} moves**.\n")
    out.append("```\n" + grid([], mark_optimal=True) + "\n```\n")
    out.append("Optimal route:\n\n```\n" + " ".join(OPT) + "\n```\n")

    for d in runs:
        p = d["visited"]
        out.append(f"\n---\n\n## Run {d['run']} — "
                   f"{'reached the shrine' if d['reached'] else 'did not arrive'}"
                   f" ({d['moves']} moves, optimal {len(OPT)-1})\n")
        out.append(f"`backtracks {d['backtracks']}` · `reversals "
                   f"{d['reversals']}` · `idle {d['idle_beats']}` · "
                   f"`rooms seen {d['unique']}/81`\n")
        out.append("```\n" + grid(p) + "\n```\n")
        rows = annotate(p)
        out.append("| beat | to | dir | |\n|---:|---|---|---|")
        for i, b, dirn, note in rows:
            out.append(f"| {i} | `{b}` | {dirn} | {note} |")
        out.append("")
    print("\n".join(out))


main()
