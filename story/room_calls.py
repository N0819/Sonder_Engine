"""The one call site for a Writers' Room model call, so the room is as
readable as a beat is.

Every pipeline stage and every Director specialist passes through
`llm/llm_quality.complete_validated_json`, which hands the exchange to
`core.pipeline_context.note_step_exchange` and from there to
`persist/llm_capture.py`. The room's agents do not: the Planner, the
Dramaturge and the story bible each call `providers.chat_complete`
directly, which is the right seam for a JSON-shaped call that validates
itself -- and is why, measured across all five play runs of 2026-09-05,
the two agents a host most wants to read were the only ones leaving no
payload behind at all. The flat run put it plainest: "`llm_capture`
records `agents/runtime.py` only, so what the Planner was SENT -- the one
thing the brief asks for per stage -- is unreadable for the Room."

So this module is that seam, and it is deliberately THIN: it makes the
same call, times it, and records it. It adds no retry, no repair, no
schema and no policy, because a room call that behaved differently from
the call it replaced would be a change to the room rather than a way of
reading it.

WHAT A CALL IS FILED UNDER is `persist/llm_capture.room_capture`'s
business, not this module's: the scope in force names the chat and the
phase, and a call outside a scope records nothing. That is what lets the
Planner's tool loop -- several frames below the seam that knows which
chat is being planned -- be captured without being handed a chat id.
"""

from __future__ import annotations

import json
import time


def room_call(role, system, payload, *, max_tokens=None, phase="",
              json_mode=True):
    """One JSON-shaped Room call, recorded. Returns the raw provider text.

    A drop-in for ``providers.chat_complete(role, system,
    json.dumps(payload), json_mode=True, max_tokens=...)``: same arguments,
    same return, same exceptions. ``payload`` is the dict the caller would
    have serialised, kept as a dict so capture can hash it PER KEY -- which
    is where the dedup lives, because a room reply's `story`, `bible` and
    tool table do not change between the steps of one reply.

    A FAILED call is recorded too, with the error and the time it burned.
    A call that raised is the one a reader most wants and the one a
    return-value-shaped recorder never sees.
    """
    from llm import providers
    from persist.llm_capture import record_room_exchange

    user = (payload if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False))
    started = time.time()
    kwargs = {"json_mode": bool(json_mode)}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    try:
        raw = providers.chat_complete(role, system, user, **kwargs)
    except Exception as exc:
        record_room_exchange(
            role=role, system=system, payload=payload, response=None,
            started=started, duration=time.time() - started, ok=False,
            error="%s: %s" % (type(exc).__name__, exc), phase=phase,
            requested=_requested(role))
        raise
    record_room_exchange(
        role=role, system=system, payload=payload, response=raw,
        reasoning=_reasoning(), started=started,
        duration=time.time() - started, ok=True, phase=phase,
        requested=_requested(role))
    return raw


def _requested(role):
    """The model of record for this role, so an export reads without a join."""
    try:
        from llm import providers
        return str((providers.agent_models().get(role) or {}).get("model") or "")
    except Exception:
        return ""


def _reasoning():
    """The reasoning trace the provider returned, when it returned one.

    Diagnostic only, exactly as it is for a stage: a reasoning block is a
    model talking to itself and has been through none of the checks the
    answer has, so nothing downstream may read it as content.
    """
    try:
        from llm.providers import last_reasoning
        return last_reasoning.get() or ""
    except Exception:
        return ""
