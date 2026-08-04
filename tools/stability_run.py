#!/usr/bin/env python3
"""Does a change hold up on a LONG story, not a fresh one.

Ten turns on a young chat proves a config starts. It does not prove it survives
a bank of 939 memories, 161 turns of play order, four characters whose
consolidation windows have already rolled several times, and a scene blob that
has accumulated every entity anybody ever mentioned. Those are the conditions
that actually break things, and they only exist in a story somebody has played.

So this drives real turns against the LONGEST stories in the corpus and records
what a stability question actually needs answered:

  * turns that failed outright -- the only hard failure
  * engine warnings per turn, by category, so a rise can be attributed
  * per-role latency and per-role model, read from the engine's own llm_call log
  * memory context size, because on a long bank that is what grows
  * cache read/write totals, since a packaging change is meant to move them

Always on a COPY of the database. These turns commit for real.

    python3 tools/stability_run.py --chats 59,38 --turns 5 --label before
    python3 tools/stability_run.py --chats 59,38 --turns 5 --label after
    python3 tools/stability_run.py --compare before.json after.json

The comparison is the point. A single run tells you almost nothing; two runs of
the same chats either side of one change tell you whether the change was safe.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ordinary play, mixed shapes: speech, action, a question, and a silence --
# the four branches `build_plan` routes differently.
SCRIPT = [
    "You take a slow look around, marking what has changed.",
    '"Tell me what you have been keeping from me," you say.',
    "You cross the room and rest a hand on the nearest surface.",
    "",
    '"We are not finished," you say, and wait.',
]

CALL = re.compile(
    r"llm_call role=(?P<role>\S+) model=(?P<model>\S+) "
    r"system_tokens=(?P<sys>\d+) user_tokens=\d+ "
    r"response_tokens=(?P<out>\d+) cached_tokens=(?P<cr>\d+) "
    r"cache_write_tokens=(?P<cw>\d+) duration=(?P<dur>[\d.]+)s "
    r"success=(?P<ok>\w+)")

# Warning families, so a rise can be attributed rather than merely noticed.
FAMILIES = (
    ("identity", r"unearned identity|scrubbed"),
    ("no channel", r"no sensory channel|unreachable"),
    ("self-narration", r"self-narration"),
    ("invented dialogue", r"invented dialogue|dropped .*dialogue"),
    ("citation", r"ungrounded|dropped unsupported|citation"),
    ("narrator fidelity", r"narrator|prose appears"),
    ("resolve", r"Resolve reconciliation|state_diff"),
    ("pressure", r"World pressure"),
)


class Capture:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        import logging
        outer = self

        class H(logging.Handler):
            def emit(self, record):
                try:
                    text = record.getMessage()
                except Exception:
                    return
                m = CALL.search(text)
                if m:
                    outer.calls.append({
                        "role": m.group("role"), "model": m.group("model"),
                        "sys": int(m.group("sys")), "out": int(m.group("out")),
                        "cached": int(m.group("cr")), "cwrite": int(m.group("cw")),
                        "sec": float(m.group("dur")),
                        "ok": m.group("ok") == "True"})
        self._logging = logging
        self._h = H()
        logging.getLogger().addHandler(self._h)
        return self

    def __exit__(self, *a):
        self._logging.getLogger().removeHandler(self._h)
        return False


def _prepare(source):
    workdir = tempfile.mkdtemp(prefix="stability-")
    copy = os.path.join(workdir, "bench.db")
    shutil.copy(source, copy)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(source + suffix):
            shutil.copy(source + suffix, copy + suffix)
    os.environ["ENGINE_DB"] = copy
    return workdir, copy


def run_chat(chat_id, turns):
    import db
    from agents.runtime import run_pipeline

    rows = []
    for n in range(turns):
        text = SCRIPT[n % len(SCRIPT)]
        with db.transaction():
            last = db.q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx DESC "
                        "LIMIT 1", (chat_id,), one=True)
            idx = (last["idx"] + 1) if last else 0
            frame = last["frame_id"] if last else None
            tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,"
                        "frame_id) VALUES(?,?,?,?,?)",
                        (chat_id, idx, text, time.time(), frame))
        t0 = time.perf_counter()
        failed = None
        try:
            for event in run_pipeline(chat_id, tid, frame_id=frame):
                if event.get("type") in ("error", "aborted"):
                    failed = str(event)[:160]
        except Exception as exc:
            failed = f"{type(exc).__name__}: {exc}"[:160]
        total = time.perf_counter() - t0

        warns = []
        for s in db.q("SELECT id FROM steps WHERE turn_id=?", (tid,)):
            v = db.q("SELECT content FROM variants WHERE step_id=? AND active=1",
                     (s["id"],), one=True)
            if not v:
                continue
            try:
                blob = json.loads(v["content"])
            except (TypeError, ValueError):
                continue
            notes = blob.get("_engine_notes") if isinstance(blob, dict) else None
            if isinstance(notes, dict):
                warns += [str(w) for w in (notes.get("warnings") or [])]
        fam = collections.Counter()
        for w in warns:
            for name, pat in FAMILIES:
                if re.search(pat, w, re.I):
                    fam[name] += 1
                    break
            else:
                fam["other"] += 1
        rows.append({"chat": chat_id, "turn": idx, "seconds": round(total, 1),
                     "warnings": len(warns), "families": dict(fam),
                     "failed": failed})
        flag = "  FAILED" if failed else ""
        print(f"    chat {chat_id} turn {idx:>4}  {total:>7.1f}s  "
              f"warn {len(warns):>3}{flag}", flush=True)
    return rows


def summarise(label, rows, calls):
    ok = [r for r in rows if not r["failed"]]
    fam = collections.Counter()
    for r in rows:
        fam.update(r["families"])
    by_role = {}
    for c in calls:
        slot = by_role.setdefault(c["role"], {"n": 0, "s": 0.0, "out": 0,
                                              "sys": 0, "cached": 0,
                                              "model": c["model"]})
        slot["n"] += 1
        slot["s"] += c["sec"]
        slot["out"] += c["out"]
        slot["sys"] += c["sys"]
        slot["cached"] += c["cached"]
    return {
        "label": label,
        "turns": len(rows),
        "failed": len(rows) - len(ok),
        "median_turn": statistics.median([r["seconds"] for r in ok]) if ok else None,
        "warnings_total": sum(r["warnings"] for r in rows),
        "warnings_per_turn": (sum(r["warnings"] for r in rows) / len(rows)
                              if rows else 0),
        "families": dict(fam),
        "prompt_tokens": sum(c["sys"] for c in calls),
        "cached_tokens": sum(c["cached"] for c in calls),
        "cache_hit": (sum(c["cached"] for c in calls)
                      / max(1, sum(c["sys"] for c in calls)) * 100),
        "by_role": by_role,
        "rows": rows,
    }


def render(s):
    print(f"\n=== {s['label']} ===")
    print(f"  turns            {s['turns']}   failed {s['failed']}")
    print(f"  median turn      "
          f"{s['median_turn']:.1f}s" if s["median_turn"] else "  median turn      --")
    print(f"  warnings/turn    {s['warnings_per_turn']:.1f}"
          f"  (total {s['warnings_total']})")
    print(f"  cache hit        {s['cache_hit']:.1f}%   "
          f"({s['cached_tokens']:,} of {s['prompt_tokens']:,} prompt tokens)")
    if s["families"]:
        print("  warning families")
        for k, v in sorted(s["families"].items(), key=lambda kv: -kv[1]):
            print(f"    {v:>4}  {k}")
    print("  by role")
    for role, v in sorted(s["by_role"].items(), key=lambda kv: -kv[1]["s"]):
        hit = v["cached"] / v["sys"] * 100 if v["sys"] else 0
        print(f"    {v['s']:>7.1f}s  {v['n']:>3} calls  cache {hit:>4.0f}%  "
              f"{role} / {v['model'].split('/')[-1]}")


def compare(a, b):
    print(f"\n=== {a['label']}  ->  {b['label']} ===")

    def line(name, x, y, fmt="{:.1f}", lower_better=True):
        if x is None or y is None:
            print(f"  {name:<20} --")
            return
        d = y - x
        arrow = "same"
        if abs(d) > 1e-9:
            good = (d < 0) if lower_better else (d > 0)
            arrow = ("better" if good else "WORSE")
        print(f"  {name:<20} {fmt.format(x):>9} -> {fmt.format(y):>9}   {arrow}")

    line("failed turns", a["failed"], b["failed"], "{:.0f}")
    line("median turn (s)", a["median_turn"], b["median_turn"])
    line("warnings/turn", a["warnings_per_turn"], b["warnings_per_turn"])
    line("cache hit %", a["cache_hit"], b["cache_hit"], "{:.1f}",
         lower_better=False)
    fams = set(a["families"]) | set(b["families"])
    print("  warning families")
    for f in sorted(fams):
        x, y = a["families"].get(f, 0), b["families"].get(f, 0)
        mark = "" if y <= x else "   WORSE"
        print(f"    {f:<20} {x:>4} -> {y:>4}{mark}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--chats", default="59,38")
    ap.add_argument("--turns", type=int, default=5)
    ap.add_argument("--label", default="run")
    ap.add_argument("--json", default=None)
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = ap.parse_args(argv)

    if args.compare:
        a = json.load(open(args.compare[0]))
        b = json.load(open(args.compare[1]))
        render(a)
        render(b)
        compare(a, b)
        return 0

    workdir, copy = _prepare(args.db)
    print(f"copied {args.db} -> {copy}")
    try:
        import db
        db.configure(copy)
        rows = []
        with Capture() as cap:
            for chat_id in [int(c) for c in args.chats.split(",") if c.strip()]:
                n = db.q("SELECT COUNT(*) c FROM turns WHERE chat_id=?",
                         (chat_id,), one=True)["c"]
                m = db.q("SELECT COUNT(*) c FROM memories WHERE chat_id=?",
                         (chat_id,), one=True)["c"]
                print(f"  chat {chat_id}: {n} existing turns, {m} memories",
                      flush=True)
                rows += run_chat(chat_id, args.turns)
        s = summarise(args.label, rows, cap.calls)
        render(s)
        if args.json:
            with open(args.json, "w") as fh:
                json.dump(s, fh, indent=2)
            print(f"\nwrote {args.json}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
