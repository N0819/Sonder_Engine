#!/usr/bin/env python3
"""Run N real turns through the whole pipeline and time every stage.

`tools/model_bench.py` measures one call in isolation, which is necessary and
not sufficient: a turn is nine stages, some of them fan out per character, and
the pipeline's wall clock is not the sum of anybody's tokens-per-second. The
interaction loop alone can issue several calls in sequence, perception issues
one per perceiver, and a model that needs a repair pass pays for two calls
where the row says one.

So this drives the real thing -- `agents.runtime.run_pipeline`, every stage,
real commits -- and reports where the time actually goes.

    python3 tools/turn_bench.py --chat 60 --turns 10
    python3 tools/turn_bench.py --chat 60 --turns 10 --label granite --json out.json

ALWAYS ON A COPY. The database is copied to a temp file and `ENGINE_DB` is
pointed at the copy before the engine is imported, because these turns commit
for real -- memories, scene state, relationships, the lot. Running this against
a database somebody is playing would write ten turns of benchmark fiction into
their story.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Player inputs shaped like ordinary play: a mix of speech, action, a question
# that demands an answer, and one deliberate silence -- the four shapes that
# route through different branches of `build_plan`. A benchmark that only ever
# sends speech never exercises the reaction loop or the silent-beat guard.
SCRIPT = [
    "You look around the room, taking stock of what is here.",
    '"How long have you been waiting?" you ask.',
    "You cross to the window and test the latch.",
    "",
    '"Something is wrong. Tell me what you heard."',
    "You sit down heavily on the edge of the bed.",
    '"We should go before it gets any later," you say, standing.',
    "You listen carefully at the door.",
    "",
    '"Whatever happens next, stay close to me."',
]


def _prepare_db(source):
    workdir = tempfile.mkdtemp(prefix="turn-bench-")
    copy = os.path.join(workdir, "bench.db")
    shutil.copy(source, copy)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(source + suffix):
            shutil.copy(source + suffix, copy + suffix)
    os.environ["ENGINE_DB"] = copy
    return workdir, copy


class _CallCapture:
    """Harvest the engine's own `llm_call` log records.

    Stage timing says which STEP was slow; this says which ROLE and which
    MODEL, which is the only attribution that can decide a config. The engine
    already logs role, model, token counts and duration per call -- reading its
    own instrumentation beats wrapping the provider, because it counts the
    retries and repair passes too, and those are exactly what a fast-but-sloppy
    model costs you.
    """

    PATTERN = None

    def __init__(self):
        import logging
        import re
        self.calls = []
        _CallCapture.PATTERN = re.compile(
            r"llm_call role=(?P<role>\S+) model=(?P<model>\S+).*?"
            r"response_tokens=(?P<out>\d+).*?duration=(?P<dur>[\d.]+)s "
            r"success=(?P<ok>\w+)")
        self._logging = logging
        outer = self

        class _H(logging.Handler):
            def emit(self, record):
                try:
                    text = record.getMessage()
                except Exception:
                    return
                if "llm_call" not in text:
                    return
                m = _CallCapture.PATTERN.search(text)
                if m:
                    outer.calls.append({
                        "role": m.group("role"), "model": m.group("model"),
                        "out_tokens": int(m.group("out")),
                        "seconds": float(m.group("dur")),
                        "ok": m.group("ok") == "True"})

        self._handler = _H()

    def __enter__(self):
        self._logging.getLogger().addHandler(self._handler)
        return self

    def __exit__(self, *exc):
        self._logging.getLogger().removeHandler(self._handler)
        return False

    def summary(self):
        by_role = {}
        for c in self.calls:
            slot = by_role.setdefault(
                (c["role"], c["model"]),
                {"calls": 0, "seconds": 0.0, "out": 0, "failures": 0})
            slot["calls"] += 1
            slot["seconds"] += c["seconds"]
            slot["out"] += c["out_tokens"]
            slot["failures"] += (0 if c["ok"] else 1)
        return by_role


def run(chat_id, turns, script=None, verbose=False):
    from core import db
    import time as _t
    from agents.runtime import run_pipeline

    script = script or SCRIPT
    rows = []
    capture = _CallCapture()
    capture.__enter__()
    for n in range(turns):
        player_input = script[n % len(script)]
        with db.transaction():
            last = db.q("SELECT * FROM turns WHERE chat_id=? "
                        "ORDER BY idx DESC LIMIT 1", (chat_id,), one=True)
            idx = (last["idx"] + 1) if last else 0
            frame_id = last["frame_id"] if last else None
            tid = db.qi(
                "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                "VALUES(?,?,?,?,?)",
                (chat_id, idx, player_input, _t.time(), frame_id))

        # A `step` event carries the step's own `content`, so it fires on
        # COMPLETION: the elapsed time since the previous event belongs to the
        # step being announced, not to the one before it. Attributing it the
        # other way put the 131s mapping call under `director_interpret` and
        # made the slowest stage in the turn look like the second-slowest.
        stages = {}
        last_at = _t.perf_counter()
        turn_start = last_at
        failed = None
        try:
            for event in run_pipeline(chat_id, tid, frame_id=frame_id):
                kind = event.get("type")
                if kind == "step":
                    now = _t.perf_counter()
                    key = event.get("key") or "?"
                    stages[key] = stages.get(key, 0.0) + (now - last_at)
                    last_at = now
                elif kind in ("error", "aborted"):
                    failed = str(event)[:200]
        except Exception as exc:
            failed = f"{type(exc).__name__}: {exc}"[:200]
        total = _t.perf_counter() - turn_start

        warns = []
        for s in db.q("SELECT id,key FROM steps WHERE turn_id=?", (tid,)):
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
                warns.extend(str(w) for w in (notes.get("warnings") or []))

        rows.append({"turn": idx, "seconds": round(total, 2),
                     "stages": {k: round(v, 2) for k, v in stages.items()},
                     "warnings": len(warns), "failed": failed,
                     "input": player_input[:48]})
        line = f"  turn {idx:>3}  {total:>7.2f}s  warnings {len(warns):>3}"
        if failed:
            line += f"  FAILED {failed[:80]}"
        print(line, flush=True)
        if verbose and stages:
            for k, v in sorted(stages.items(), key=lambda kv: -kv[1]):
                print(f"            {v:>6.2f}s  {k}", flush=True)
    capture.__exit__()
    return rows, capture


def render_roles(capture):
    by_role = capture.summary()
    if not by_role:
        return
    total = sum(v["seconds"] for v in by_role.values())
    print("\n  model time by role (the number a config decision turns on)")
    print(f"    {'seconds':>8} {'share':>6} {'calls':>6} {'tok/s':>7} "
          f"{'fail':>5}  role / model")
    for (role, model), v in sorted(by_role.items(),
                                   key=lambda kv: -kv[1]["seconds"]):
        rate = v["out"] / v["seconds"] if v["seconds"] else 0
        print(f"    {v['seconds']:>8.1f} {v['seconds']/total*100:>5.1f}% "
              f"{v['calls']:>6} {rate:>7.1f} {v['failures']:>5}  "
              f"{role} / {model}")


def render(rows, label):
    good = [r for r in rows if not r["failed"]]
    print(f"\n=== {label} ===")
    if not good:
        print("  every turn failed")
        return
    secs = [r["seconds"] for r in good]
    print(f"  turns completed   {len(good)}/{len(rows)}")
    print(f"  median turn       {statistics.median(secs):.2f}s")
    print(f"  mean turn         {statistics.fmean(secs):.2f}s")
    print(f"  fastest / slowest {min(secs):.2f}s / {max(secs):.2f}s")
    print(f"  total wall clock  {sum(r['seconds'] for r in rows):.1f}s")
    print(f"  warnings          {sum(r['warnings'] for r in rows)}")
    agg = {}
    for r in good:
        for k, v in r["stages"].items():
            agg[k] = agg.get(k, 0.0) + v
    print("\n  where the time goes (total across completed turns)")
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1]):
        share = v / sum(agg.values()) * 100 if agg else 0
        print(f"    {v:>7.1f}s  {share:>5.1f}%  {k}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--chat", type=int, required=True)
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--label", default="run")
    ap.add_argument("--json", default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        sys.exit(f"no database at {args.db}")
    workdir, copy = _prepare_db(args.db)
    print(f"copied {args.db} -> {copy}")
    try:
        from core import db
        db.configure(copy)
        rows, capture = run(args.chat, args.turns, verbose=args.verbose)
        render(rows, args.label)
        render_roles(capture)
        if args.json:
            with open(args.json, "w") as fh:
                json.dump({"label": args.label, "turns": rows,
                           "calls": capture.calls}, fh, indent=2)
            print(f"\nwrote {args.json}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
