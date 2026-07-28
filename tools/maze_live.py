"""Live view of a running maze arm, over HTTP.

    python tools/maze_live.py <runs.jsonl> [--log run.log] [--port 8009]
    ->  http://localhost:8009

Re-reads the harness's own output on every request, so it costs the experiment
nothing and cannot disturb it. Nothing is cached and nothing is written.

The maze comes from the results file's `meta` header -- its recorded `edges`,
its start and its goal. An earlier version of this viewer hardcoded the 9x9
kruskal seed, which is the same defect `render_maze_runs.py` had: the route
drawn was real while the walls under it were invented, and every wall the
viewer showed was a guess that happened to be right for one arm.

Walls are drawn as the CELL's own borders. A shared wall is drawn by both cells
that touch it, so a corridor reads as a continuous line rather than as a dotted
seam -- worth knowing before "simplifying" it to one border per edge.
"""
from __future__ import annotations

import argparse
import html
import http.server
import json
import os
import re
import socketserver
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools.maze_experiment as M


def load_maze(runs_path):
    """Walls, grid, start and goal from the arm's own meta header."""
    meta = None
    with open(runs_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") == "meta":
                meta = row
                break
    if meta is None:
        raise SystemExit(
            f"{runs_path}: no `meta` header. The viewer will not guess a maze "
            "-- drawing real routes against invented walls is how this went "
            "wrong before.")
    grid = int(meta["grid"])
    start = tuple(meta.get("start") or (0, 0))
    goal = tuple(meta.get("goal") or (grid - 1, grid - 1))
    if meta.get("edges"):
        walls = {(r, c): set() for r in range(grid) for c in range(grid)}
        for a, b in meta["edges"]:
            a, b = tuple(a), tuple(b)
            walls[a].add(b)
            walls[b].add(a)
    else:
        # Pre-`edges` arms: regenerate, and say so rather than implying the
        # walls were recorded.
        M.MAZE_SEED = int(meta.get("seed") or M.MAZE_SEED)
        M.GRID, M.GOAL, M.START = grid, goal, start
        walls = M.build_maze(grid=grid, algo=meta.get("algo", "dfs"),
                             braid=float(meta.get("braid") or 0.0))
    M.GRID, M.GOAL, M.START = grid, goal, start
    return walls, grid, start, goal, meta


def read_log(path, grid):
    """Where he is and how it is going, scraped from the harness's stdout."""
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return {}
    # Per RUN: beat numbers restart each run, so a flat route indexed by beat
    # lines one run's beat up against another's position.
    parts = re.split(r"\n  run (\d+)/\d+", text)
    runs, cur = {}, None
    for i in range(1, len(parts), 2):
        found = re.findall(r"at (r\d{4}) \| \d+ of", parts[i + 1])
        if found:
            runs.setdefault(int(parts[i]), []).extend(found)
            cur = int(parts[i])
    route = runs.get(cur or 0, [])
    done = re.findall(r"beats=(\d+) moves=(\d+) idle=(\d+) unique=(\d+) "
                      r"backtracks=(\d+) reversals=(\d+) reached=(\w+)", text)
    lat = [float(x) for x in
           re.findall(r"role=character_[a-z]+[^\n]*?duration=([0-9.]+)", text)]
    rev = sum(1 for i in range(1, len(route) - 1)
              if route[i + 1] == route[i - 1] and route[i + 1] != route[i])
    return {"run": cur, "route": route, "rev": rev, "done": done,
            "stalls": text.count("STALLED"),
            "lat": round(sum(lat[-20:]) / max(1, len(lat[-20:])), 1)}


def grid_html(route, walls, grid, start, goal, optimal):
    first = {}
    for i, rid in enumerate(route, 1):
        first.setdefault(rid, i)
    here = route[-1] if route else None
    out = [f'<div class=maze style="--n:{grid}">']
    for r in range(grid):
        for c in range(grid):
            rid = M._rid((r, c))
            open_to = walls.get((r, c), ())
            cls = ["cell"]
            # A wall on every side with no passage through it. Both cells
            # draw their shared wall, so the line stays continuous.
            if (r - 1, c) not in open_to:
                cls.append("wn")
            if (r + 1, c) not in open_to:
                cls.append("ws")
            if (r, c - 1) not in open_to:
                cls.append("ww")
            if (r, c + 1) not in open_to:
                cls.append("we")
            label = ""
            if rid in first:
                cls.append("seen")
                label = str(first[rid])
                if rid == here:
                    cls.append("here")
            elif rid in optimal:
                cls.append("opt")
            if (r, c) == goal:
                cls.append("goal")
                label = label or "✦"
            elif (r, c) == start:
                cls.append("start")
                label = label or "▲"
            out.append(f'<div class="{" ".join(cls)}">{label}</div>')
    return "".join(out) + "</div>"


PAGE = """<!doctype html><meta charset=utf-8>
<title>@@TITLE@@</title>
<meta http-equiv=refresh content=4>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{--pa:#EDEFF2;--pn:#F7F8FA;--ink:#141A21;--dim:#5C6875;--ln:#C6CDD6;
--wall:#2B3642;--tr:#C0651B;--trs:#F2DCC6;--goal:#1E7A67;--rt:#9AA6B4;--al:#A32B38}
@media(prefers-color-scheme:dark){:root{--pa:#0E1319;--pn:#161D25;--ink:#DFE5EC;
--dim:#8593A2;--ln:#2A343F;--wall:#B7C6D6;--tr:#E8963F;--trs:#3A2A18;
--goal:#43BFA4;--rt:#3E4C5A;--al:#E4707C}}
:root[data-theme=dark]{--pa:#0E1319;--pn:#161D25;--ink:#DFE5EC;--dim:#8593A2;
--ln:#2A343F;--wall:#B7C6D6;--tr:#E8963F;--trs:#3A2A18;--goal:#43BFA4;
--rt:#3E4C5A;--al:#E4707C}
*{box-sizing:border-box}
body{margin:0;padding:2rem 1rem;background:var(--pa);color:var(--ink);
font:400 16px/1.6 "Iowan Old Style",Palatino,Georgia,serif}
.wrap{max-width:44rem;margin:0 auto;display:flex;flex-direction:column;gap:1.25rem}
.eb{font-family:ui-monospace,monospace;font-size:.68rem;letter-spacing:.15em;
text-transform:uppercase;color:var(--dim)}
h1{margin:0;font-size:1.6rem;font-weight:600}
.strip{display:flex;flex-wrap:wrap;gap:.4rem}
.st{flex:1 1 6rem;background:var(--pn);border:1px solid var(--ln);border-radius:2px;
padding:.55rem .7rem}
.st .k{display:block;font-family:ui-monospace,monospace;font-size:.6rem;
letter-spacing:.12em;text-transform:uppercase;color:var(--dim)}
.st .v{font-family:ui-monospace,monospace;font-size:1.3rem;font-variant-numeric:tabular-nums}
.warn .v{color:var(--al)}
/* The maze frame is the outer wall. Cells carry the interior ones. */
.maze{display:grid;grid-template-columns:repeat(var(--n),minmax(1.7rem,1fr));
max-width:30rem;margin:0 auto;background:var(--pn);
border:3px solid var(--wall)}
.cell{aspect-ratio:1;display:grid;place-items:center;
border:0 solid var(--wall);font-family:ui-monospace,monospace;font-size:.66rem;
color:var(--dim)}
.wn{border-top-width:3px}.ws{border-bottom-width:3px}
.ww{border-left-width:3px}.we{border-right-width:3px}
.opt::after{content:"·";color:var(--rt);font-size:1.2rem}
.seen{background:var(--trs);color:var(--tr);font-weight:600}
.here{background:var(--tr);color:var(--pa)}
.goal{box-shadow:inset 0 0 0 2px var(--goal);color:var(--goal)}
.start{color:var(--dim)}
table{border-collapse:collapse;width:100%;font-size:.82rem;background:var(--pn)}
th,td{padding:.35rem .6rem;border-bottom:1px solid var(--ln);text-align:left}
th{font-family:ui-monospace,monospace;font-size:.6rem;letter-spacing:.1em;
text-transform:uppercase;color:var(--dim);font-weight:500}
td{font-family:ui-monospace,monospace;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
footer{color:var(--dim);font-size:.78rem}
</style><div class=wrap>
<div><div class=eb>@@EYEBROW@@</div>
<h1>Live — run @@RUN@@, beat @@BEAT@@</h1></div>
<div class=strip>@@STATS@@</div>
@@GRID@@
<div class=scroll>@@TABLE@@</div>
<footer>Refreshes every 4s. Numbers are the beat a chamber was first entered;
the filled cell is where he stands, <b>▲</b> the entrance, <b>✦</b> the goal,
<b>·</b> the optimal route where he has not been. Optimal is @@OPT@@ moves.
</footer></div>"""


def build_handler(walls, grid, start, goal, optimal, meta, log_path, title,
                  eyebrow):
    cells = grid * grid

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            d = read_log(log_path, grid)
            route = d.get("route") or []
            stats = [("Beat", len(route)),
                     ("Chambers", f"{len(set(route))}/{cells}"),
                     ("Reversals", d.get("rev", 0)),
                     ("Call", f"{d.get('lat', 0)}s"),
                     ("Stalls", d.get("stalls", 0))]
            strip = "".join(
                f'<div class="st{" warn" if k == "Stalls" and v else ""}">'
                f'<span class=k>{html.escape(k)}</span>'
                f'<span class=v>{html.escape(str(v))}</span></div>'
                for k, v in stats)
            rows = "".join(
                f"<tr><td>{i}</td><td>{b}</td><td>{m}</td><td>{u}/{cells}</td>"
                f"<td>{bk}</td><td>{rv}</td>"
                f"<td>{'YES' if rc == 'True' else '—'}</td></tr>"
                for i, (b, m, idl, u, bk, rv, rc)
                in enumerate(d.get("done") or [], 1))
            table = ("<table><tr><th>run<th>beats<th>moves<th>rooms<th>back"
                     "<th>rev<th>reached</tr>" + rows + "</table>") if rows \
                else ""
            page = PAGE
            for token, val in (
                    ("@@TITLE@@", title), ("@@EYEBROW@@", eyebrow),
                    ("@@RUN@@", d.get("run", "?")), ("@@BEAT@@", len(route)),
                    ("@@OPT@@", len(optimal) - 1), ("@@STATS@@", strip),
                    ("@@GRID@@", grid_html(route, walls, grid, start, goal,
                                           optimal)),
                    ("@@TABLE@@", table)):
                page = page.replace(token, str(val))
            body = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs_jsonl", help="the arm's --out file (for its meta)")
    ap.add_argument("--log", default=None,
                    help="harness stdout to scrape for position; defaults to "
                         "the results file with .log in place of .jsonl")
    ap.add_argument("--port", type=int, default=8009)
    ap.add_argument("--title", default=None)
    ap.add_argument("--dump", metavar="PATH",
                    help="write one render to PATH and exit, instead of "
                         "serving. For checking the walls draw correctly "
                         "without a running arm.")
    a = ap.parse_args()

    walls, grid, start, goal, meta = load_maze(a.runs_jsonl)
    optimal = [M._rid(c) for c in M.shortest_path(walls, start, goal)]
    optimal_set = set(optimal)
    log_path = a.log or re.sub(r"(_runs)?\.jsonl$", ".log", a.runs_jsonl)
    origin = (f"authored {meta['svg']}" if meta.get("svg")
              else f"{meta.get('algo')} seed {meta.get('seed')}")
    eyebrow = f"{grid}×{grid} {origin} · {os.path.basename(a.runs_jsonl)}"
    title = a.title or f"Maze live — {os.path.basename(a.runs_jsonl)}"

    if a.dump:
        # Same grid_html and same PAGE the server uses, so a dump that looks
        # right is evidence about what the server will show.
        page = PAGE
        d = read_log(log_path, grid)
        route = d.get("route") or []
        for token, val in (
                ("@@TITLE@@", title), ("@@EYEBROW@@", eyebrow),
                ("@@RUN@@", d.get("run", "?")), ("@@BEAT@@", len(route)),
                ("@@OPT@@", len(optimal) - 1), ("@@STATS@@", ""),
                ("@@GRID@@", grid_html(route, walls, grid, start, goal,
                                       optimal_set)),
                ("@@TABLE@@", "")):
            page = page.replace(token, str(val))
        open(a.dump, "w", encoding="utf-8").write(page)
        print(f"wrote {a.dump}")
        return

    handler = build_handler(walls, grid, start, goal, optimal_set, meta,
                            log_path, title, eyebrow)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", a.port), handler) as srv:
        print(f"live view on http://localhost:{a.port}  "
              f"({grid}×{grid}, optimal {len(optimal) - 1}, log {log_path})",
              flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()
