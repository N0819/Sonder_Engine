"""Deterministic, privacy-conscious exports of persisted pipeline history.

The engine already persists completed stage outputs as immutable variants.
This module turns that existing record into a portable diagnostic artifact;
it does not add rows, intercept provider calls, or alter pipeline execution.

Hash-only traces are safe(r) to share but cannot replay stage payloads.
Full traces require an explicit opt-in because structured stage output can
contain story text, private character reasoning, and retrieved lore.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterator

from core.db import q


TRACE_FORMAT = "sonder.pipeline-trace"
TRACE_VERSION = 1


class PipelineTraceError(ValueError):
    """Raised when a trace cannot be exported, validated, or replayed."""


@dataclass(frozen=True)
class TraceValidation:
    """Integrity and materialization findings for one trace."""

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors


def _canonical_json(value: Any) -> str:
    """Return the stable JSON representation used for every trace digest."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PipelineTraceError(
            f"trace value is not canonical JSON: {exc}"
        ) from exc


def _json_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _trace_digest(trace: dict) -> str:
    unsigned = {key: value for key, value in trace.items()
                if key != "trace_sha256"}
    return _json_digest(unsigned)


def _decode_variant_content(raw: str, *, variant_id: int) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PipelineTraceError(
            f"variant {variant_id} contains invalid JSON"
        ) from exc


def export_pipeline_trace(
    turn_id: int,
    *,
    include_content: bool = False,
    include_all_variants: bool = False,
) -> dict:
    """Build a stable trace from one turn's already-persisted variants.

    By default, story-bearing fields are represented only by SHA-256 hashes.
    Set ``include_content`` explicitly to make the artifact replayable.
    ``include_all_variants`` preserves reroll history; otherwise only the
    currently active variant of each step is exported.
    """
    turn = q(
        "SELECT id,chat_id,idx,player_input,frame_id FROM turns WHERE id=?",
        (turn_id,),
        one=True,
    )
    if not turn:
        raise PipelineTraceError(f"turn {turn_id} not found")

    player_input = turn["player_input"] or ""
    turn_data = {
        "source_turn_id": int(turn["id"]),
        "source_chat_id": int(turn["chat_id"]),
        "idx": int(turn["idx"]),
        "frame_id": turn["frame_id"],
        "player_input_sha256": _json_digest(player_input),
    }
    if include_content:
        turn_data["player_input"] = player_input

    steps = []
    step_rows = q(
        "SELECT id,key,label,ord,stale FROM steps "
        "WHERE turn_id=? ORDER BY ord,id",
        (turn_id,),
    )
    for step in step_rows:
        variant_rows = q(
            "SELECT id,content,created,active FROM variants "
            "WHERE step_id=? ORDER BY id",
            (step["id"],),
        )
        active_ids = [
            int(row["id"]) for row in variant_rows if bool(row["active"])
        ]
        exported_variants = []
        for variant in variant_rows:
            if not include_all_variants and not bool(variant["active"]):
                continue
            content = _decode_variant_content(
                variant["content"],
                variant_id=int(variant["id"]),
            )
            record = {
                "source_variant_id": int(variant["id"]),
                "active": bool(variant["active"]),
                "created": float(variant["created"]),
                "content_sha256": _json_digest(content),
            }
            if include_content:
                record["content"] = content
            exported_variants.append(record)

        steps.append({
            "source_step_id": int(step["id"]),
            "key": step["key"],
            "label": step["label"],
            "ord": int(step["ord"]),
            "stale": bool(step["stale"]),
            "active_variant_ids": active_ids,
            "variant_count": len(variant_rows),
            "variants": exported_variants,
        })

    trace = {
        "format": TRACE_FORMAT,
        "version": TRACE_VERSION,
        "privacy": {
            "content": "included" if include_content else "sha256-only",
            "all_variants": bool(include_all_variants),
            "note": (
                "Full traces may contain story text, private character "
                "reasoning, and retrieved lore."
            ),
        },
        "turn": turn_data,
        "steps": steps,
    }
    trace["trace_sha256"] = _trace_digest(trace)
    return trace


def validate_pipeline_trace(
    trace: Any,
    *,
    require_content: bool = False,
) -> TraceValidation:
    """Validate envelope integrity and the active-variant replay contract."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(trace, dict):
        return TraceValidation(("trace root must be an object",), ())
    if trace.get("format") != TRACE_FORMAT:
        errors.append(f"unsupported trace format {trace.get('format')!r}")
    if trace.get("version") != TRACE_VERSION:
        errors.append(f"unsupported trace version {trace.get('version')!r}")

    expected_digest = trace.get("trace_sha256")
    if not isinstance(expected_digest, str):
        errors.append("trace_sha256 is missing")
    else:
        try:
            actual_digest = _trace_digest(trace)
        except PipelineTraceError as exc:
            errors.append(str(exc))
        else:
            if actual_digest != expected_digest:
                errors.append("trace_sha256 does not match the artifact")

    turn = trace.get("turn")
    if not isinstance(turn, dict):
        errors.append("turn must be an object")
    else:
        player_hash = turn.get("player_input_sha256")
        if not isinstance(player_hash, str):
            errors.append("turn.player_input_sha256 is missing")
        if "player_input" in turn and isinstance(player_hash, str):
            if _json_digest(turn["player_input"]) != player_hash:
                errors.append("turn.player_input_sha256 does not match")
        elif require_content:
            errors.append("turn.player_input is required for replay")

    steps = trace.get("steps")
    if not isinstance(steps, list):
        errors.append("steps must be a list")
        return TraceValidation(tuple(errors), tuple(warnings))

    seen_keys: set[str] = set()
    prior_order: tuple[int, int] | None = None
    for index, step in enumerate(steps):
        prefix = f"steps[{index}]"
        if not isinstance(step, dict):
            errors.append(f"{prefix} must be an object")
            continue

        key = step.get("key")
        if not isinstance(key, str) or not key:
            errors.append(f"{prefix}.key must be a non-empty string")
        elif key in seen_keys:
            warnings.append(f"step key {key!r} appears more than once")
        else:
            seen_keys.add(key)

        try:
            order = (int(step["ord"]), int(step["source_step_id"]))
        except (KeyError, TypeError, ValueError):
            errors.append(f"{prefix} has invalid ord/source_step_id")
            order = None
        if order is not None:
            if prior_order is not None and order < prior_order:
                errors.append("steps are not in deterministic (ord,id) order")
            prior_order = order

        if step.get("stale"):
            warnings.append(f"step {key!r} is marked stale")

        active_ids = step.get("active_variant_ids")
        if not isinstance(active_ids, list):
            errors.append(f"{prefix}.active_variant_ids must be a list")
            active_ids = []
        if len(active_ids) != 1:
            errors.append(
                f"step {key!r} has {len(active_ids)} active variants; expected 1"
            )

        variants = step.get("variants")
        if not isinstance(variants, list):
            errors.append(f"{prefix}.variants must be a list")
            continue
        active_exports = [
            item for item in variants
            if isinstance(item, dict) and item.get("active") is True
        ]
        if len(active_exports) != 1:
            errors.append(
                f"step {key!r} exports {len(active_exports)} active variants; "
                "expected 1"
            )
        elif active_ids and (
            active_exports[0].get("source_variant_id") != active_ids[0]
        ):
            errors.append(f"step {key!r} active variant id does not match")

        for variant_index, variant in enumerate(variants):
            variant_prefix = f"{prefix}.variants[{variant_index}]"
            if not isinstance(variant, dict):
                errors.append(f"{variant_prefix} must be an object")
                continue
            content_hash = variant.get("content_sha256")
            if not isinstance(content_hash, str):
                errors.append(f"{variant_prefix}.content_sha256 is missing")
            if "content" in variant and isinstance(content_hash, str):
                try:
                    actual = _json_digest(variant["content"])
                except PipelineTraceError as exc:
                    errors.append(f"{variant_prefix}: {exc}")
                else:
                    if actual != content_hash:
                        errors.append(
                            f"{variant_prefix}.content_sha256 does not match"
                        )
            elif require_content and variant.get("active") is True:
                errors.append(
                    f"{variant_prefix}.content is required for replay"
                )

    if not steps:
        warnings.append("trace has no persisted pipeline steps")
    return TraceValidation(tuple(errors), tuple(warnings))


def replay_pipeline_trace(
    trace: dict,
    *,
    strict: bool = True,
) -> Iterator[dict]:
    """Replay saved stage events without importing runtime or calling a model.

    This reproduces the persisted event sequence and payloads, not the stage
    computations themselves. It is intended for deterministic diagnostics,
    visualizer tests, and bug reports.
    """
    validation = validate_pipeline_trace(trace, require_content=True)
    if validation.errors and strict:
        raise PipelineTraceError("; ".join(validation.errors))

    turn = trace.get("turn") if isinstance(trace, dict) else {}
    turn_id = turn.get("source_turn_id") if isinstance(turn, dict) else None
    yield {
        "type": "trace_start",
        "turn_id": turn_id,
        "warnings": list(validation.warnings),
        "valid": validation.valid,
    }

    steps = trace.get("steps", []) if isinstance(trace, dict) else []
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        variants = step.get("variants")
        if not isinstance(variants, list):
            continue
        active = next(
            (
                variant for variant in variants
                if isinstance(variant, dict) and variant.get("active") is True
                and "content" in variant
            ),
            None,
        )
        if active is None:
            if strict:
                raise PipelineTraceError(
                    f"step {step.get('key')!r} has no replayable active variant"
                )
            continue
        yield {
            "type": "step_start",
            "key": step.get("key"),
            "label": step.get("label"),
            "replayed": True,
        }
        yield {
            "type": "step",
            "key": step.get("key"),
            "label": step.get("label"),
            "step_id": step.get("source_step_id"),
            "variant_id": active.get("source_variant_id"),
            "variants": step.get("variant_count"),
            "content": active["content"],
            "replayed": True,
        }

    yield {
        "type": "done",
        "turn_id": turn_id,
        "replayed": True,
        "valid": validation.valid,
    }


def dump_pipeline_trace(trace: dict) -> str:
    """Serialize a trace with deterministic formatting and a trailing newline."""
    return _canonical_json(trace) + "\n"


def load_pipeline_trace(path: str | os.PathLike[str]) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineTraceError(f"could not load trace {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineTraceError("trace root must be an object")
    return value


def write_pipeline_trace(
    path: str | os.PathLike[str],
    trace: dict,
) -> None:
    """Atomically replace ``path`` so interrupted exports are never partial."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(dump_pipeline_trace(trace))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


# ---------------------------------------------------------------------------
# The turn debug artifact
# ---------------------------------------------------------------------------

TURN_DEBUG_FORMAT = "sonder.turn-debug"
TURN_DEBUG_VERSION = 1


def export_turn_debug(turn_id: int, *, include_content: bool = True) -> dict:
    """One turn, in the order it actually happened.

    `export_pipeline_trace` above answers "what did each stage decide", which
    is the replayable record. This answers a different question -- "what
    happened, in order" -- and needs three sources the trace does not join:

      * `llm_capture`, for what was SENT and the reasoning that came back.
        Nothing else holds either, and for the Director's six specialists
        nothing else holds anything at all: they are sub-calls inside
        `director_resolve` with no steps and therefore no variants.
      * the steps' own variants, for what each stage ANSWERED.
      * `_engine_notes`, for what the deterministic layer did -- the warnings
        it raised and the decisions it made, including the times it correctly
        DECLINED, which is the half that leaves no other trace.

    Ordered by wall clock, because the Director fans out: the six specialists
    run concurrently and finish out of order, so the order they were STARTED
    in is the only one that describes the turn.
    """
    turn = q("SELECT id,chat_id,idx,player_input,created FROM turns WHERE id=?",
             (turn_id,), one=True)
    if not turn:
        raise PipelineTraceError(f"turn {turn_id} not found")

    events: list[dict] = []

    from persist.llm_capture import exchanges_for_turn
    for row in exchanges_for_turn(turn_id, include_bodies=include_content):
        payload = row.get("payload") if include_content else None
        if isinstance(payload, dict):
            decoded = {}
            for key, blob in payload.items():
                if blob is None:
                    decoded[key] = None
                    continue
                try:
                    decoded[key] = json.loads(blob)
                except Exception:
                    decoded[key] = blob
            payload = decoded
        response = row.get("response")
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except Exception:
                pass
        events.append({
            "at": float(row.get("started") or 0.0),
            "kind": "call",
            "seq": int(row.get("seq") or 0),
            "step": row.get("step_key") or "",
            "role": row.get("role") or "",
            "model": row.get("requested") or "",
            "duration": float(row.get("duration") or 0.0),
            "ok": bool(row.get("ok", 1)),
            "error": row.get("error") or "",
            "sent": {"system": row.get("system"),
                     "system_sha256": row.get("system_hash"),
                     "payload": payload,
                     "payload_sha256": row.get("payload_hashes") or {}},
            "received": {"output": response,
                         "output_sha256": row.get("response_hash"),
                         "reasoning": row.get("reasoning"),
                         "reasoning_sha256": row.get("reasoning_hash")},
        })

    for step in q("SELECT id,key,label,ord FROM steps WHERE turn_id=? "
                  "ORDER BY ord,id", (turn_id,)) or ():
        variant = q("SELECT id,content,created FROM variants WHERE step_id=? "
                    "AND active=1 ORDER BY id DESC LIMIT 1",
                    (step["id"],), one=True)
        if not variant:
            continue
        content = _decode_variant_content(variant["content"],
                                          variant_id=int(variant["id"]))
        notes = content.pop("_engine_notes", {}) if isinstance(content, dict) else {}
        events.append({
            "at": float(variant["created"] or 0.0),
            "kind": "step",
            "step": step["key"],
            "label": step["label"],
            "ord": int(step["ord"] or 0),
            "output": content if include_content else None,
            "output_sha256": _json_digest(content),
            "warnings": (notes or {}).get("warnings") or [],
            "decisions": (notes or {}).get("decisions") or [],
            "llm_calls": (notes or {}).get("llm_calls") or [],
        })

    # Steps and calls share one clock. Ties keep calls ahead of the step that
    # contains them, which is the order they happened in.
    events.sort(key=lambda e: (e["at"], 0 if e["kind"] == "call" else 1,
                               e.get("seq", 0)))

    captured = sum(1 for e in events if e["kind"] == "call")
    return {
        "format": TURN_DEBUG_FORMAT,
        "version": TURN_DEBUG_VERSION,
        "turn": {
            "turn_id": int(turn["id"]),
            "chat_id": int(turn["chat_id"]),
            "idx": int(turn["idx"]),
            "player_input": (turn["player_input"] or "") if include_content
                            else None,
            "created": float(turn["created"] or 0.0),
        },
        "content_included": bool(include_content),
        # Says so rather than looking complete: with capture off, every `call`
        # event is absent and the artifact holds only what the steps recorded.
        "calls_captured": captured,
        "capture_was_on": captured > 0,
        "timeline": events,
    }


def export_chat_debug(chat_id: int, *, include_content: bool = True,
                      limit: int = 50) -> dict:
    """The same, for a whole chat's most recent turns, oldest first.

    `limit` is named rather than buried: a long chat's full debug export is
    unbounded, and silently returning the last N would read as "this is the
    whole chat". The artifact reports the bound it applied.
    """
    rows = q("SELECT id FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT ?",
             (int(chat_id), int(limit))) or ()
    turn_ids = [int(r["id"]) for r in rows][::-1]
    total = q("SELECT COUNT(*) AS n FROM turns WHERE chat_id=?",
              (int(chat_id),), one=True)
    return {
        "format": TURN_DEBUG_FORMAT,
        "version": TURN_DEBUG_VERSION,
        "chat_id": int(chat_id),
        "turns_total": int((total or {"n": 0})["n"]),
        "turns_exported": len(turn_ids),
        "limit": int(limit),
        "turns": [export_turn_debug(t, include_content=include_content)
                  for t in turn_ids],
    }
