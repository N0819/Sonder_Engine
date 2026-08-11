"""Perception quality baseline — Metric D: what the composer actually buys.

Measures, from the stored corpus only:

  * perception model calls per turn — approximated by the number of stored
    non-empty, non-residue views per turn across the three perception stage
    keys (each such view was one per-observer provider call; residue views
    for non-awake minds are deterministic and cost no call);
  * perception's share of turn wall-clock — from the only timing data the
    corpus exposes: `turns.created` and `variants.created` (unix floats).
    A stage's duration is approximated as the gap between its variant's
    creation and the previous step's variant creation (the first stage is
    anchored to the turn row). This includes orchestration overhead and is
    therefore an approximation, stated as such.

Sample discipline: timing uses only turns where every non-stale step has
exactly one variant (no rerolls/reruns, which reorder creation times), with
monotonic non-negative gaps, and no gap above a stall ceiling (a turn left
overnight measures the player, not the engine).

The database is opened read-only.

Run:
    python tools/perception_latency.py --db /path/to/engine.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PERCEPTION_KEYS = ("perception_establish", "perception_act",
                   "perception_outcome")
RESIDUE_LEADS = ("Darkness.", "A thick, floating dark.",
                 "You are under, below waking.")
STALL_CEILING_SECONDS = 900.0


def _is_residue_view(view):
    text = str(view or "").strip()
    return any(text.startswith(lead) for lead in RESIDUE_LEADS)


def perception_calls_per_turn(con):
    rows = con.execute(
        "SELECT s.turn_id, s.key, v.content FROM steps s "
        "JOIN variants v ON v.step_id = s.id AND v.active = 1 "
        "WHERE s.stale = 0 AND s.key IN (?,?,?)", PERCEPTION_KEYS).fetchall()
    per_turn = defaultdict(int)
    total_views = 0
    residue_views = 0
    for turn_id, key, content in rows:
        try:
            views = (json.loads(content).get("views") or {})
        except Exception:
            continue
        for view in views.values():
            if not view or not str(view).strip():
                continue
            total_views += 1
            if _is_residue_view(view):
                residue_views += 1
            else:
                per_turn[turn_id] += 1
    turn_count = con.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    calls = list(per_turn.values())
    return {
        "turns": turn_count,
        "views_total": total_views,
        "views_residue_no_call": residue_views,
        "estimated_model_calls": sum(calls),
        "estimated_calls_per_turn":
            round(sum(calls) / turn_count, 2) if turn_count else None,
        "calls_per_turn_median": statistics.median(calls) if calls else None,
        "calls_per_turn_max": max(calls) if calls else None,
        "note": "one stored non-residue view == one per-observer provider "
                "call; residue views are deterministic (no call)",
    }


def stage_durations(con, stall_ceiling=STALL_CEILING_SECONDS):
    """Per-turn stage gaps from variants.created, on clean turns only."""
    rows = con.execute(
        "SELECT s.turn_id, s.key, s.ord, COUNT(v.id) AS n, "
        "MIN(v.created) AS created "
        "FROM steps s JOIN variants v ON v.step_id = s.id "
        "WHERE s.stale = 0 GROUP BY s.id ORDER BY s.turn_id, s.ord").fetchall()
    turn_created = dict(con.execute(
        "SELECT id, created FROM turns").fetchall())
    turns = defaultdict(list)
    dirty = set()
    for turn_id, key, ord_, n, created in rows:
        if n != 1:
            dirty.add(turn_id)
        turns[turn_id].append((ord_, key, created))
    usable = 0
    perception_seconds = 0.0
    total_seconds = 0.0
    shares = []
    per_turn_perception = []
    for turn_id, steps in turns.items():
        if turn_id in dirty or turn_id not in turn_created:
            continue
        steps.sort()
        prev = turn_created[turn_id]
        durations = {}
        ok = True
        for ord_, key, created in steps:
            gap = created - prev
            if gap < 0 or gap > stall_ceiling:
                ok = False
                break
            durations[key] = durations.get(key, 0.0) + gap
            prev = created
        if not ok or not durations:
            continue
        turn_total = sum(durations.values())
        turn_perception = sum(durations.get(k, 0.0) for k in PERCEPTION_KEYS)
        if turn_total <= 0:
            continue
        usable += 1
        total_seconds += turn_total
        perception_seconds += turn_perception
        shares.append(turn_perception / turn_total)
        per_turn_perception.append(turn_perception)
    return {
        "turns_usable_for_timing": usable,
        "turns_excluded": len(turns) - usable,
        "stall_ceiling_seconds": stall_ceiling,
        "perception_seconds_total": round(perception_seconds, 1),
        "turn_seconds_total": round(total_seconds, 1),
        "perception_share_of_wallclock_pct":
            round(100 * perception_seconds / total_seconds, 1)
            if total_seconds else None,
        "perception_share_median_pct":
            round(100 * statistics.median(shares), 1) if shares else None,
        "perception_seconds_per_turn_median":
            round(statistics.median(per_turn_perception), 2)
            if per_turn_perception else None,
        "perception_seconds_per_turn_mean":
            round(perception_seconds / usable, 2) if usable else None,
        "note": "gaps between variant creation times; includes "
                "orchestration overhead; single-variant turns only",
    }


def run_latency_baseline(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return {
        "db": str(db_path),
        "calls": perception_calls_per_turn(con),
        "wallclock": stage_durations(con),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="engine.db")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    result = run_latency_baseline(args.db)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
