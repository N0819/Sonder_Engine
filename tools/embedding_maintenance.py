#!/usr/bin/env python3
"""The embedding repairs that exist, made runnable.

A vector is only comparable with a vector from the same model. A row embedded
by a retired model scores 0.0 on every semantic ranking forever and looks
exactly like a row that simply does not match, so a bank silently splits into
two eras and nothing anywhere says so. The engine repairs the live tables on
its own -- `start_rebuild_if_needed` offers a rebuild when a story opens, and
retrieval warns once per situation -- but two repairs have no way in at all:

  * `rebuild_checkpoint_embeddings` carries a completed rebuild BACK through a
    story's saved states. A checkpoint stores each vector verbatim, so one
    written before a rebuild holds the old vectors and restoring it undoes the
    rebuild -- measured live, one reroll put 637 of 642 rows back on the crc32
    fallback. It re-embeds nothing: a vector is a pure function of the memory,
    the same memory recurs unchanged across dozens of checkpoints, so the fix
    is substitution. 99,442 saved memories across 1,040 checkpoints in 98
    seconds and zero API calls, when it was last run by hand.

  * `backfill_lore_embedding_stamps` decides what embedded each unstamped lore
    entry, once, and records it. `lore_entries` gained
    `embedding_model`/`embedding_dim` long after it gained vectors, so every
    row written before that carries bytes and no provenance, and can never be
    judged stale or fresh -- it is outside the reconciliation system
    `memories` has always been in. Measured on the owner's corpus: 1,160 of
    2,586 rows. It embeds nothing either; `cheap_embed` is a pure function of
    the text, so "is this the fallback" is answered by recomputing and
    comparing bytes, with the provider face-down.

Both were built, documented and tested, and neither had a caller anywhere in
the tree. That is what this file is: the entry point, not new machinery.

    python3 tools/embedding_maintenance.py status
    python3 tools/embedding_maintenance.py status --chat 59 --json
    python3 tools/embedding_maintenance.py checkpoints              # dry run
    python3 tools/embedding_maintenance.py checkpoints --apply
    python3 tools/embedding_maintenance.py checkpoints --chat 59 --apply
    python3 tools/embedding_maintenance.py lore-stamps             # dry run
    python3 tools/embedding_maintenance.py lore-stamps --apply

`status` never writes. `checkpoints` and `lore-stamps` write only with
`--apply`; without it they report what they would do and change nothing.
Point at another database with `ENGINE_DB=/path/to/other.db`.

Unlike `tools/fire_rates.py` this DOES import the engine -- substituting a
vector needs `_memory_vector_key`, and reimplementing that join here is how
the two spellings drift apart. So it opens the real database for writing, and
should not be run against a story the server currently has open.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mind import memory  # noqa: E402


def _report(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key in sorted(payload):
        print(f"{key:>22}  {payload[key]}")


def cmd_status(args):
    """What is comparable right now, before anything is written."""
    payload = {
        "memory_bank": memory.embedding_bank_status(args.chat) or {},
        # Deliberately whole-corpus: lorebooks are shared between stories, so
        # "is my lore reachable" is not a per-chat question.
        "lore": memory.lore_embedding_health() or {},
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    for section in sorted(payload):
        print(f"[{section}]")
        _report(payload[section], False)
        print()


def cmd_checkpoints(args):
    seen = {"n": 0}

    def _progress(rewritten, scanned):
        # A thousand checkpoints is a minute of silence otherwise.
        if rewritten and rewritten != seen["n"] and rewritten % 50 == 0:
            seen["n"] = rewritten
            print(f"  ... {rewritten} rewritten, {scanned} scanned",
                  file=sys.stderr)

    _report(memory.rebuild_checkpoint_embeddings(
        args.chat, dry_run=not args.apply, progress=_progress), args.json)


def cmd_lore_stamps(args):
    if not args.apply:
        # The backfill has no dry run of its own -- deciding IS the operation,
        # and it is meant to happen once -- so the dry run is the health
        # report of exactly the rows `--apply` would stamp.
        print("dry run: nothing written. `unstamped` is what --apply would "
              "decide and record.", file=sys.stderr)
        _report(memory.lore_embedding_health() or {}, args.json)
        return
    _report(memory.backfill_lore_embedding_stamps(), args.json)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def _command(name, help_text):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--json", action="store_true",
                       help="machine-readable output")
        return p

    p_status = _command("status", "what is comparable right now")
    p_status.add_argument("--chat", type=int, default=None)
    p_status.set_defaults(func=cmd_status)

    p_ckpt = _command(
        "checkpoints", "carry a completed rebuild through saved states")
    p_ckpt.add_argument("--chat", type=int, default=None,
                        help="one story; omit for every story")
    p_ckpt.add_argument("--apply", action="store_true",
                        help="write; without it, report and change nothing")
    p_ckpt.set_defaults(func=cmd_checkpoints)

    p_lore = _command(
        "lore-stamps", "record what embedded each unstamped lore entry")
    p_lore.add_argument("--apply", action="store_true",
                        help="write; without it, report and change nothing")
    p_lore.set_defaults(func=cmd_lore_stamps)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
