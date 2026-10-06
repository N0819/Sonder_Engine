"""How often recall would bring a successor in, from a replayed link graph (2026-10-05).

Reads `links_replay_<chat>_<char>.json` (links_replay.py) and applies the SHIPPED
pull rule (`mind.memory_links.successors_of`: every row that changed a recalled
row, newest first, then the newest row its links reach), at a few points in the
story T: of the mind's linkable rows older than the 8-turn recent window, how
many would bring at least one row the recent window does not hold, and how far
forward the newest brought row lies.

Usage: .venv/bin/python tools/concept_lab/links_pull_rate.py <chat_id> <char_id> [T ...]
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

RECENT = 8


def main(chat_id, char_id, points):
    from mind.memory_links import successors_of
    engine = os.environ.get("CONCEPT_LAB_ENGINE_DB") or str(lab.ROOT / "engine.db")
    src = sqlite3.connect(f"file:{engine}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    rows = {r["id"]: dict(r) for r in src.execute(
        "SELECT id, turn_idx, event_key, encoded_at_seconds FROM memories WHERE chat_id=? AND char_id=? "
        "AND kind='episodic' AND category IN ('episode','self') AND event_key<>'' "
        "AND turn_idx IS NOT NULL", (chat_id, char_id))}
    answers = lab._load(f"links_replay_{chat_id}_{char_id}.json", {})
    links = [tuple(map(int, k.split("|"))) for k, a in answers.items() if lab._p_yes(a) >= 0.5]
    for at in points or (40, 80, 120, 170):
        newer_of = {}
        for new, old in links:
            if new in rows and old in rows and rows[new]["turn_idx"] < at:
                newer_of.setdefault(rows[old]["event_key"], []).append(rows[new])
        older = [r for r in rows.values() if r["turn_idx"] < at - RECENT]
        pulls, jumps = 0, []
        for r in older:
            brought = [s for s in successors_of(r, newer_of) if s["turn_idx"] < at - RECENT]
            if brought:
                pulls += 1
                jumps.append(max(s["turn_idx"] for s in brought) - r["turn_idx"])
        print(f"T={at}: {len(older)} older linkable rows | would bring a successor: {pulls} "
              f"({pulls / max(1, len(older)):.0%}) | mean jump to the newest brought {sum(jumps) / max(1, len(jumps)):.0f} turns")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), [int(x) for x in sys.argv[3:]])
