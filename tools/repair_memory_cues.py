#!/usr/bin/env python3
"""Run the one-shot junk-cue stock repair (mind.memory.repair_memory_cues).

Dry-run by default; pass --apply to write. Point ENGINE_DB at the database
to repair -- rehearse on a COPY first, and never run this while the engine
is serving turns (it is O(bank) and talks to the embeddings provider).

    ENGINE_DB=/path/to/engine.db python3 tools/repair_memory_cues.py --apply
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat", type=int, default=None)
    parser.add_argument("--character", type=int, default=None)
    parser.add_argument("--apply", action="store_true",
                        help="write repairs (default is a dry run)")
    args = parser.parse_args()
    if not os.environ.get("ENGINE_DB"):
        raise SystemExit("set ENGINE_DB explicitly, so which database is "
                         "being repaired is a stated choice")
    from mind import memory

    def progress(count, kind):
        print(f"  repaired {count} {kind}...", flush=True)

    report = memory.repair_memory_cues(
        args.chat, args.character, dry_run=not args.apply, progress=progress)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("dry_run"):
        print("dry run -- nothing written; pass --apply to repair")
    if report.get("stopped_early"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
