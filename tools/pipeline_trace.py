#!/usr/bin/env python3
"""Export, inspect, or replay a persisted Sonder Engine pipeline turn."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import db
from persist.pipeline_trace import (
    PipelineTraceError,
    dump_pipeline_trace,
    export_pipeline_trace,
    load_pipeline_trace,
    replay_pipeline_trace,
    validate_pipeline_trace,
    write_pipeline_trace,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Portable diagnostics for immutable pipeline step/variant history"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser(
        "export",
        help="export one persisted turn",
    )
    export.add_argument("turn_id", type=int)
    export.add_argument(
        "--db",
        default=os.environ.get("ENGINE_DB", "engine.db"),
        help="SQLite database path (default: ENGINE_DB or engine.db)",
    )
    export.add_argument(
        "-o", "--output",
        help="destination JSON path; omit to print to stdout",
    )
    export.add_argument(
        "--include-content",
        action="store_true",
        help=(
            "include replayable story-bearing payloads; without this flag "
            "only SHA-256 hashes are exported"
        ),
    )
    export.add_argument(
        "--all-variants",
        action="store_true",
        help="include inactive reroll history as well as active variants",
    )

    inspect = subparsers.add_parser(
        "inspect",
        help="validate a trace and print a compact summary",
    )
    inspect.add_argument("trace")

    replay = subparsers.add_parser(
        "replay",
        help="emit saved pipeline events as JSON Lines; never calls a model",
    )
    replay.add_argument("trace")
    replay.add_argument(
        "--lenient",
        action="store_true",
        help="emit available steps even when validation finds errors",
    )
    return parser


def _export(args: argparse.Namespace) -> int:
    if not Path(args.db).is_file():
        raise PipelineTraceError(f"database not found: {args.db}")
    db.configure(args.db)
    try:
        trace = export_pipeline_trace(
            args.turn_id,
            include_content=args.include_content,
            include_all_variants=args.all_variants,
        )
        if args.output:
            write_pipeline_trace(args.output, trace)
        else:
            sys.stdout.write(dump_pipeline_trace(trace))
    finally:
        db.close_connection()
    return 0


def _inspect(args: argparse.Namespace) -> int:
    trace = load_pipeline_trace(args.trace)
    validation = validate_pipeline_trace(trace)
    summary = {
        "valid": validation.valid,
        "replayable": trace.get("privacy", {}).get("content") == "included",
        "turn_id": trace.get("turn", {}).get("source_turn_id"),
        "turn_idx": trace.get("turn", {}).get("idx"),
        "steps": len(trace.get("steps") or []),
        "errors": list(validation.errors),
        "warnings": list(validation.warnings),
        "trace_sha256": trace.get("trace_sha256"),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if validation.valid else 1


def _replay(args: argparse.Namespace) -> int:
    trace = load_pipeline_trace(args.trace)
    for event in replay_pipeline_trace(trace, strict=not args.lenient):
        print(json.dumps(
            event,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "export":
            return _export(args)
        if args.command == "inspect":
            return _inspect(args)
        return _replay(args)
    except PipelineTraceError as exc:
        print(f"pipeline trace error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
