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


def room_max_tokens(fallback=40_000):
    """THE ONE NUMBER EVERY ROOM CALL ASKS FOR: the host's own output ceiling.

    The owner's 2026-09-04 ruling is that every response cap the Room owns is
    the same number, so a step that needs room has it and no single call is
    the one that truncates. This keeps that and fixes what the number WAS.

    A REASONING MODEL BILLS ITS THINKING AS OUTPUT -- `providers` says so
    beside its own clamp, from the maze arms: 11-13k tokens of deliberation
    and then nothing left for the answer. Every Room call is reasoning-heavy
    (the Planner reads the world through six or more tools before it writes
    an operation; the bible fold and the dramaturge each read a whole
    transcript), and all four were asking for 20,000 against a host ceiling
    of 40,000. So the Room thought its way through the problem and had no
    budget left to say what it had decided.

    Measured on the descent run, 2026-09-05: three of six Room calls on
    `gemini-3.8-flash` died as `ReasoningBudgetExhausted` with 15k-32k
    characters of reasoning trace and an empty answer, and the Room only
    completed a task when the ask was small enough to think about briefly. A
    seven-room sub-level took three attempts.

    Read per call, so the host's setting is the answer and a change takes
    effect on the next call. `providers._clamp_max_tokens` only ever LOWERS,
    so this is never a way past the ceiling: a host that sets 8,000 gets
    8,000.
    """
    try:
        from llm.providers import max_output_tokens
        return max(int(max_output_tokens()), 1)
    except Exception:
        return int(fallback)


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


# ---------------------------------------------------------------------------
# What a reply re-derives, and how often
# ---------------------------------------------------------------------------

class ReplyMemo:
    """The derived half of a Room agent's per-step payload, held for one
    reply and dropped the moment that reply writes.

    A Room reply is a LOOP of model calls -- up to
    `story_planner.PLANNER_STEPS_PER_REPLY` for the Planner,
    `dramaturge.DRAMATURGE_STEPS` for the Dramaturge -- and each step used
    to rebuild the same payload out of the database: the story row, the
    clock, the cast's minds, the thread, the mandates, the status row, the
    frontier, the packages, the standing proposals. Measured on the bench
    copies (review 2026-09-07, C21, `tools/bench/room_payload.py`): one
    Planner payload costs 17.3 ms on chat 114 (the 307-body charter town),
    most of it the cast summary and the frontier, and a forty-step reply
    spent 0.69 s rebuilding it against 0.02 s held -- 14.0 ms a payload and
    0.56 s against 0.02 s on chat 117's 123-beat descent. 97% off both.

    TWO THINGS MOVE THE DERIVED HALF, AND THE MEMO IS DROPPED BY BOTH.
    The first is the reply's own writes -- a tool that is not a pure read,
    a granted mandate, a rewritten status row, a filed proposal -- and each
    calls `wrote()`, which drops the whole memo so the next step re-derives
    all of it. The second is a BEAT LANDING UNDER THE REPLY: the room is
    not alone in the database, `room_conversation.converse_stream` runs the
    Planner in a daemon thread against no lock, and `story_planner`'s own
    `story_rewound_past` guard exists because the turn index moves
    mid-reply. So every step hands the memo `core.db.data_version()`
    through `at_version`, and a version that is not the one the memo was
    built at drops it exactly as a write does.

    WHY THE DATABASE'S OWN VERSION AND NOT THE TURN INDEX (the second C21
    skeptic, 2026-09-08, measured it): `web/app.py` inserts the turns row
    BEFORE `run_pipeline` and the scene commits at the END of that same
    index, so a turn-index key fires when the beat STARTS -- rebuilding
    from pre-commit data -- and is silent when the beat COMMITS, which is
    the mutation that matters. `data_version` moves on any OTHER
    connection's commit and never on this connection's own (connections are
    thread-local), so the beat's commit, a reroll recommitting the scene at
    the same index, a host edit in the world browser, an archive import and
    the Dramaturge filing a proposal all move it, and the reply's own writes
    do not -- which is why the explicit `wrote()` calls stay. A false
    positive costs one re-derivation. It is also cheaper than the turn
    index it replaces: 0.013 ms median on the bench copy of chat 114
    against 0.019 ms.

    Measured before this was held (review 2026-09-07, C21): a turn
    committed between step 1 and step 2 of a reply of pure reads left the
    next payload's `player_room` at "quay" while the scene said "shed", and
    its `clock.turn_idx` a beat behind, for the rest of the reply
    (`tests/test_room_payload_memo.py` holds it, and holds the same rule at
    the Dramaturge's loop).

    WIDEN THE MEMO, NEVER THE KEY. A caller that is unsure whether
    something wrote calls `wrote()`: a spurious drop costs one re-derivation,
    a missed one serves a stale world for the rest of the reply. That is why
    `room_tools.tool_only_reads` answers False for a tool it does not
    recognise.

    Per reply, never a module global: a memo that outlived its reply would
    serve one story's frontier to another's, and one turn's clock to the
    next. What it holds is SHARED AND READ-ONLY -- the payload is
    serialized, not mutated (the same contract `charter_runtime`'s registry
    cache states).
    """

    def __init__(self):
        self.writes = 0
        self._at = -1
        self._version = None
        self._parts = {}

    def wrote(self):
        """The reply changed the database; every part is re-derived next."""
        self.writes += 1

    def at_version(self, version):
        """The step's live `core.db.data_version()`. A writer on another
        connection -- the beat's commit above all -- moves the derived half
        through none of the reply's own writes, so a version that is not the
        one the memo was built at drops it (C21)."""
        if self._version is not None and version != self._version:
            self.wrote()
        self._version = version

    def part(self, key, build):
        if self._at != self.writes:
            self._parts = {}
            self._at = self.writes
        if key not in self._parts:
            self._parts[key] = build()
        return self._parts[key]


def memo_part(memo, key, build):
    """``build()`` once per reply through ``memo``, or straight through when
    there is none -- a direct caller, a single-shot pass, a test."""
    return build() if memo is None else memo.part(key, build)
