#!/usr/bin/env python3
"""Live view of the model benchmarks, over HTTP.

    python tools/bench_live.py <log-dir> [--port 8010]
    ->  http://localhost:8010

Same shape and same reasoning as tools/maze_live.py: it re-reads the harnesses'
own output files on every request, so it costs the runs nothing and cannot
disturb them. Nothing is cached and nothing is written.

Each panel comes from whichever file owns it. Completed turns and the summary
come from the turn harness's stdout; per-call latency, role and model are
scraped from the engine's own `llm_call` log lines, which is the only place
retries and fallbacks are visible -- a call served by the fallback appears
under the fallback's name, which is how you can see a primary quietly failing.

Auto-refreshes every 4 seconds. Read-only, local-only, and safe to leave open.
"""

from __future__ import annotations

import argparse
import glob
import html
import http.server
import json
import os
import re
import time

LLM_CALL = re.compile(
    r"llm_call role=(?P<role>\S+) model=(?P<model>\S+).*?"
    r"response_tokens=(?P<out>\d+).*?duration=(?P<dur>[\d.]+)s "
    r"success=(?P<ok>\w+)")
TURN_LINE = re.compile(r"^\s{2}turn\s+(\d+)\s+([\d.]+)s\s+warnings\s+(\d+)(.*)$")

# What each file is, in the order a reader wants them.
PANELS = [
    ("final10b.log", "10-turn run — fastest-reliable config"),
    ("creation-mapping.log", "world-building depth — mapping_stage"),
    ("creation-director.log", "world-building depth — director_resolve"),
    ("bench-roles.log", "role-targeted candidate sweep"),
    ("contract-director.log", "real contract — director_interpret"),
    ("contract-character.log", "real contract — character"),
    ("bench-moe.log", "raw speed sweep"),
    ("avail.log", "endpoint availability"),
]


def _read(path, limit=400_000):
    try:
        with open(path, "r", errors="replace") as fh:
            data = fh.read()
    except OSError:
        return None
    return data[-limit:]


def _calls(text):
    out = []
    for line in text.splitlines():
        m = LLM_CALL.search(line)
        if m:
            out.append({"role": m.group("role"), "model": m.group("model"),
                        "out": int(m.group("out")),
                        "sec": float(m.group("dur")),
                        "ok": m.group("ok") == "True"})
    return out


def _plain(text):
    """Everything that is not a JSON log line -- the harness's own report."""
    keep = []
    for line in text.splitlines():
        if line.startswith("{") and "llm_call" in line:
            continue
        keep.append(line)
    return "\n".join(keep).strip()


def render(logdir):
    now = time.strftime("%H:%M:%S")
    parts = [f"""<!doctype html><meta charset=utf-8>
<meta http-equiv=refresh content=4>
<title>bench live</title>
<style>
 body{{background:#101315;color:#e5e5de;font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;margin:0;padding:18px 22px}}
 h1{{font-size:15px;letter-spacing:.14em;text-transform:uppercase;color:#7c8388;font-weight:600;margin:0 0 14px}}
 h2{{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:#5cbe94;margin:22px 0 6px;font-weight:600}}
 .idle h2{{color:#7c8388}}
 pre{{white-space:pre-wrap;margin:0;background:#171b1e;border:1px solid #2e3438;padding:9px 11px;overflow-x:auto}}
 table{{border-collapse:collapse;margin-top:6px;font-size:12px}}
 td,th{{padding:2px 12px 2px 0;text-align:left;border-bottom:1px solid #232a2d}}
 th{{color:#7c8388;font-weight:600}}
 .n{{text-align:right;font-variant-numeric:tabular-nums}}
 .bad{{color:#de8062}} .good{{color:#5cbe94}} .dim{{color:#7c8388}}
 .miss{{color:#5c6367;font-style:italic}}
</style>
<h1>Sonder bench &mdash; live &middot; {now} &middot; refreshing every 4s</h1>"""]

    for name, label in PANELS:
        path = os.path.join(logdir, name)
        text = _read(path)
        if text is None:
            parts.append(f'<div class=idle><h2>{html.escape(label)}</h2>'
                         f'<p class=miss>not started</p></div>')
            continue
        calls = _calls(text)
        body = _plain(text)
        age = time.time() - os.path.getmtime(path)
        live = age < 90
        cls = "" if live else "idle"
        flag = " &middot; <span class=good>live</span>" if live else \
               f" &middot; <span class=dim>idle {int(age)}s</span>"
        parts.append(f'<div class="{cls}"><h2>{html.escape(label)}{flag}</h2>')

        if calls:
            agg = {}
            for c in calls:
                slot = agg.setdefault((c["role"], c["model"]),
                                      {"n": 0, "s": 0.0, "t": 0, "f": 0})
                slot["n"] += 1
                slot["s"] += c["sec"]
                slot["t"] += c["out"]
                slot["f"] += (0 if c["ok"] else 1)
            total = sum(v["s"] for v in agg.values()) or 1
            rows = ["<table><tr><th>role</th><th>model</th><th class=n>calls"
                    "</th><th class=n>sec</th><th class=n>share</th>"
                    "<th class=n>tok/s</th><th class=n>fail</th></tr>"]
            for (role, model), v in sorted(agg.items(),
                                           key=lambda kv: -kv[1]["s"]):
                rate = v["t"] / v["s"] if v["s"] else 0
                fail = (f'<span class=bad>{v["f"]}</span>' if v["f"]
                        else '<span class=dim>0</span>')
                rows.append(
                    f'<tr><td>{html.escape(role)}</td>'
                    f'<td class=dim>{html.escape(model)}</td>'
                    f'<td class=n>{v["n"]}</td>'
                    f'<td class=n>{v["s"]:.1f}</td>'
                    f'<td class=n>{v["s"]/total*100:.0f}%</td>'
                    f'<td class=n>{rate:.0f}</td>'
                    f'<td class=n>{fail}</td></tr>')
            rows.append("</table>")
            parts.append("".join(rows))
            last = calls[-1]
            parts.append(f'<p class=dim>{len(calls)} calls &middot; last: '
                         f'{html.escape(last["role"])} '
                         f'{last["sec"]:.1f}s</p>')

        if body:
            parts.append(f"<pre>{html.escape(body[-6000:])}</pre>")
        parts.append("</div>")

    return "".join(parts).encode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logdir")
    ap.add_argument("--port", type=int, default=8010)
    args = ap.parse_args(argv)

    logdir = os.path.abspath(args.logdir)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            payload = render(logdir)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"watching {logdir}\n  ->  http://localhost:{args.port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
