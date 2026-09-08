"""What feeds the bodies of a stored town, and what nothing feeds.

The measurement A25 (review 2026-09-07, owner's ruling 2026-09-08) is scored
on: how many stored `needs` rows name the upkeep that feeds them before and
after the town-wide derivation, and what the author is told about the ones
that still name nothing.

Measured on bench.db chat 114 on 2026-09-08: 0 of 66 before, 0 of 66 after,
four charters warned -- the town produces `meals`, `linens` and `iced_fish`
and consumes none of them, so nothing in it makes what anybody eats. That is
the ruling's outcome and the reason the warning exists; a run that reports a
derivation for every charter is the sign that a second, unapproved clause has
crept back into `charter_needs.feeding_upkeep` (it scored 66 of 66).

Run it against a COPY of a story database, never a live one::

    ENGINE_DB=/path/to/copy.db .venv/bin/python tools/bench/charter_fed_by.py \\
        --db /path/to/copy.db --chat 114

It only reads: one `world` row per chat, decoded and normalized in memory.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def _load(db_path, chat_id):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select value from world where key='charters' and chat_id=?",
            (chat_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        raise SystemExit(f"no charters row for chat {chat_id}")
    return json.loads(row[0])


def _fed(registry):
    counts = {}
    for key, item in (registry.get("items") or {}).items():
        held_rows = (item.get("state") or item).get("needs") or {}
        named = sum(
            1 for held in held_rows.values()
            for name, need in (held or {}).items()
            if name == "sustenance" and str((need or {}).get("fed_by") or ""))
        counts[key] = (named, len(held_rows))
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--chat", type=int, required=True)
    args = ap.parse_args(argv)

    from world.charter_runtime import normalize_registry, registry_warnings

    stored = _load(args.db, args.chat)
    print("BEFORE (as stored):")
    for key, (named, bodies) in sorted(_fed(stored).items()):
        print(f"  {key}: {named}/{bodies} bodies name a sustenance hand")

    started = time.perf_counter()
    registry = normalize_registry(stored)
    elapsed = time.perf_counter() - started
    print(f"\nAFTER normalize_registry ({elapsed * 1000:.0f} ms):")
    for key, (named, bodies) in sorted(_fed(registry).items()):
        state = registry["items"][key]["state"]
        hands = sorted({
            str(need.get("fed_by") or "")
            for held in (state.get("needs") or {}).values()
            for name, need in held.items()
            if name == "sustenance"} - {""})
        print(f"  {key}: {named}/{bodies} bodies name a sustenance hand "
              f"{hands}")

    print("\nregistry_warnings:")
    for line in registry_warnings(registry):
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
