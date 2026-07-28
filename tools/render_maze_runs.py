"""Render a maze experiment's actual movements as markdown.

Reads the --out JSONL a run wrote and emits, per run, the maze with each room
labelled by the beat it was first entered plus a move-by-move table annotated
with what each move was (on route, revisit, reversal, dead end, stayed put).

    python tools/render_maze_runs.py <runs.jsonl> [-o docs/MAZE_RUNS.md]

Generated rather than written by hand so it cannot drift from what happened.

The maze is rebuilt from the `meta` header the harness writes as line one of
the results file -- grid, algo, braid, seed, goal. It used to be hardcoded to
the 9x9 Kruskal seed, which silently rendered every other arm against the
WRONG walls: the routes were real but the maze under them was not, so every
annotation derived from it -- "DEAD END", "on route", the optimal overlay --
was fiction presented as measurement. Files written before the header existed
are refused rather than guessed at.
"""
import argparse
import json
import sys

sys.path.insert(0, ".")
import tools.maze_experiment as M


def load(path):
    """Runs plus the meta header, or a clear failure."""
    rows = [json.loads(line) for line in open(path) if line.strip()]
    meta = next((r for r in rows if r.get("kind") == "meta"), None)
    runs = [r for r in rows if r.get("kind") != "meta" and "visited" in r]
    if meta is None:
        raise SystemExit(
            f"{path}: no `meta` header -- written before the harness "
            "recorded one. Rebuilding the maze would mean guessing its "
            "grid/algo/seed, and a wrong guess renders real routes against "
            "invented walls. Re-run the arm, or hand-add a meta line.")
    return meta, runs


class Maze:
    """The walls, the optimal route and the room-id map for one arm."""

    DIRS = {(-1, 0): "north", (1, 0): "south", (0, -1): "west", (0, 1): "east"}

    def __init__(self, meta):
        self.g = int(meta["grid"])
        self.goal = tuple(meta.get("goal") or (self.g - 1, self.g - 1))
        M.MAZE_SEED = int(meta.get("seed") or M.MAZE_SEED)
        M.GRID, M.GOAL = self.g, self.goal
        self.walls = M.build_maze(grid=self.g, algo=meta.get("algo", "dfs"),
                                  braid=float(meta.get("braid") or 0.0))
        self.opt = [M._rid(c) for c in
                    M.shortest_path(self.walls, (0, 0), self.goal)]
        self.optset = set(self.opt)
        self.cell = {M._rid(c): c for c in self.walls}

    def grid(self, path, mark_optimal=False):
        """Maze with walls; cells labelled by first-visit order (or . / *)."""
        order = {}
        for i, r in enumerate(path, 1):
            order.setdefault(r, i)
        lines = ["+" + "---+" * self.g]
        for r in range(self.g):
            mid, bot = "|", "+"
            for c in range(self.g):
                rid = M._rid((r, c))
                if rid in order:
                    n = order[rid]
                    glyph = f"{n:>3}" if n < 1000 else " ##"
                elif mark_optimal and rid in self.optset:
                    glyph = "  *"
                elif (r, c) == self.goal:
                    glyph = "  X"
                else:
                    glyph = "   "
                open_e = (r, c + 1) in self.walls.get((r, c), ())
                open_s = (r + 1, c) in self.walls.get((r, c), ())
                mid += glyph + (" " if open_e else "|")
                bot += "   +" if open_s else "---+"
            lines += [mid, bot]
        return "\n".join(lines)

    def annotate(self, path):
        """Move-by-move with what each step was."""
        rows, seen = [], {path[0]}
        for i in range(1, len(path)):
            a, b = path[i - 1], path[i]
            if a == b:
                rows.append((i, b, "—", "stayed put"))
                continue
            (ar, ac), (br, bc) = self.cell[a], self.cell[b]
            d = self.DIRS.get((br - ar, bc - ac), "?")
            notes = []
            if (b in self.optset and a in self.optset
                    and self.opt.index(b) == self.opt.index(a) + 1):
                notes.append("**on route**")
            elif b in self.optset:
                notes.append("rejoins route")
            if b in seen:
                notes.append("revisit")
            if i > 1 and b == path[i - 2]:
                notes.append("reversal")
            if len(self.walls[self.cell[b]]) == 1:
                notes.append("DEAD END")
            seen.add(b)
            rows.append((i, b, d, ", ".join(notes) or "—"))
        return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_jsonl")
    ap.add_argument("-o", "--out", help="write here instead of stdout")
    ap.add_argument("--title", default="The maze runs, move by move")
    ap.add_argument("--note", default="", help="one line of arm context")
    a = ap.parse_args()

    meta, runs = load(a.runs_jsonl)
    mz = Maze(meta)
    st, traps = meta.get("maze_stats") or {}, meta.get("traps") or {}
    n_opt = len(mz.opt) - 1

    o = [f"# {a.title}\n"]
    if a.note:
        o.append(a.note + "\n")
    o.append("Numbers in each grid are the beat a room was **first** entered. "
             "`*` marks the optimal route where he never went, `X` the goal.\n")
    o.append("## The maze\n")
    o.append(f"{mz.g}×{mz.g} {meta.get('algo')}, braid {meta.get('braid')}, "
             f"seed `{meta.get('seed')}` — {st.get('cells', mz.g * mz.g)} "
             f"rooms, {st.get('junctions', '?')} junctions, "
             f"{st.get('dead_ends', '?')} dead ends, "
             f"optimal **{n_opt} moves**.\n")
    if traps:
        o.append(f"Traps: {traps.get('off_path')} rooms off-route, "
                 f"{traps.get('deep_traps')} false branches 3+ deep, worst "
                 f"{traps.get('max_depth')} rooms, mean "
                 f"{traps.get('mean_depth')}.\n")
    o.append(f"Code state: `{meta.get('commit') or 'unknown'}`"
             + (" (dirty tree)" if meta.get("dirty_tree") else "")
             + f" · `{' '.join(meta.get('argv') or [])}`\n")
    o.append("```\n" + mz.grid([], mark_optimal=True) + "\n```\n")
    o.append("Optimal route:\n\n```\n" + " ".join(mz.opt) + "\n```\n")

    for d in runs:
        p = d["visited"]
        o.append(f"\n---\n\n## Run {d['run']} — "
                 f"{'reached the goal' if d.get('reached') else 'did not arrive'}"
                 f" ({d.get('moves')} moves, optimal {n_opt})\n")
        o.append(f"`backtracks {d.get('backtracks')}` · "
                 f"`reversals {d.get('reversals')}` · "
                 f"`idle {d.get('idle_beats')}` · "
                 f"`rooms seen {d.get('unique')}/{mz.g * mz.g}`\n")
        o.append("```\n" + mz.grid(p) + "\n```\n")
        o.append("| beat | to | dir | |\n|---:|---|---|---|")
        for i, b, dirn, note in mz.annotate(p):
            o.append(f"| {i} | `{b}` | {dirn} | {note} |")
        o.append("")

    text = "\n".join(o)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"wrote {a.out} ({len(runs)} runs)")
    else:
        print(text)


main()
