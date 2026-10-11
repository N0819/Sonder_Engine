"""Content-addressed capture of what the engine SENT and what came back.

The engine already records, per step, what each provider call COST -- role,
model, tokens, duration (`PipelineContext.llm_calls`, persisted by
`runtime._with_engine_notes`). That ledger's own comment states the boundary
this module crosses on purpose: "Diagnostic only -- roles, model ids, token
counts and durations, never content."

Content is the half a turn cannot be reconstructed without. The step outputs
are persisted as variants, so what a stage ANSWERED survives; what it was
ASKED does not, and neither does the reasoning of the five specialist sub-calls
that have no step rows of their own. Both are needed to read a turn in order.

WHY CONTENT-ADDRESSED, and not a log file. A single beat sends ~104KB of sheet
text across its seven calls and ~107KB of payload, so a naive per-call log is
~200KB/beat. But the sheet is identical on every beat until a prompt is edited,
and most payload keys (`scene`, `cast`, lore) barely move between beats. Storing
each distinct blob once under its SHA-256 and referencing it by hash collapses
that to the part that actually changed, while an export rehydrates by hash and
is byte-exact. The hash is also what makes `hash_only` mode useful rather than
merely safe: it proves WHICH sheet was sent without the sheet leaving the
machine, which is the posture `persist/pipeline_trace.py` already takes.

OFF BY DEFAULT. With `llm_capture_enabled` unset nothing here runs and the
"never content" promise above holds exactly as written. Turning it on is a
deliberate act, and `hash_only` -- the default once on -- keeps it true of the
bodies while still giving a complete, ordered skeleton of the turn.

BEFORE THE FIRST TURN. A row is filed under a turn, and a story with none --
the player planning with the Writers' Room before the launch -- used to record
nothing; so did the layout tier, which runs at the launch and in a background
job, outside any step. Those calls are held by story (`llm_capture_pending`)
and filed under the first turn anything is recorded against
(`_file_pending`); until then `pending_exchanges` reads them.
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import time
from typing import Any

from core.db import get_setting, q, qi, transaction


#: Largest single blob stored, in bytes. One pathological payload -- a lore
#: dump, a a scene blown up by a runaway loop -- must not be able to dominate
#: the store. Above this the body is truncated and the record says so; the
#: hash is still of the FULL text, so the record remains honest about what was
#: sent even when it cannot show all of it.
MAX_BLOB_BYTES = 256 * 1024

#: How many turns of capture to keep, per chat. Bounded in BEATS rather than
#: days on purpose: a chat left alone for a month should not lose the history
#: of its last session, and a chat played hard for a week should not accrete
#: forever.
RETAIN_TURNS = 200


def capture_enabled() -> bool:
    """Whether to record anything at all. Default off -- see the module note."""
    try:
        return str(get_setting("llm_capture_enabled", "") or "").lower() in (
            "1", "true", "yes", "on")
    except Exception:
        return False


def capture_bodies() -> bool:
    """Whether to store blob BODIES, or only their hashes. Default hash-only."""
    try:
        return str(get_setting("llm_capture_bodies", "hash_only")
                   or "").lower() in ("full", "1", "true", "yes", "on")
    except Exception:
        return False


def blob_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def put_blob(text: str, *, store_body: bool | None = None) -> str | None:
    """Store one blob if it is new, and return its hash.

    Idempotent by construction: the hash IS the key, so re-sending the same
    sheet on every beat of a chat writes one row the first time and nothing
    afterwards.
    """
    if text is None:
        return None
    text = str(text)
    digest = blob_hash(text)
    if store_body is None:
        store_body = capture_bodies()
    body = None
    if store_body:
        raw = text.encode("utf-8")
        body = (raw[:MAX_BLOB_BYTES].decode("utf-8", "ignore")
                if len(raw) > MAX_BLOB_BYTES else text)
    try:
        qi("INSERT INTO llm_blobs(hash,bytes,body) VALUES(?,?,?) "
           "ON CONFLICT(hash) DO UPDATE SET body=COALESCE(excluded.body,body)",
           (digest, len(text.encode("utf-8")), body))
    except Exception:
        return digest
    return digest


def get_blob(digest: str) -> str | None:
    if not digest:
        return None
    row = q("SELECT body FROM llm_blobs WHERE hash=?", (digest,), one=True)
    return row["body"] if row else None


def _payload_hashes(payload: Any) -> dict:
    """Hash each TOP-LEVEL payload key separately.

    Per-key rather than per-payload because that is where the dedup lives: a
    beat changes `events` and the player's line, and leaves `scene`, `cast`
    and the lore block byte-identical to the beat before. Hashing the whole
    payload as one blob would store all of it again for a one-key change.
    """
    if not isinstance(payload, dict):
        return {}
    out = {}
    for key, value in payload.items():
        try:
            text = (value if isinstance(value, str)
                    else json.dumps(value, ensure_ascii=False, sort_keys=True))
        except Exception:
            continue
        digest = put_blob(text)
        if digest:
            out[str(key)] = digest
    return out


#: The columns a captured call fills after its key (`turn_id` in
#: `llm_capture`, `chat_id` in `llm_capture_pending`) and its `seq`.
_COLUMNS = ("step_key", "role", "requested", "served", "started", "duration", "ok",
            "error", "system_hash", "payload_hashes", "response_hash", "reasoning_hash",
            "response_format", "reasoning_effort", "max_tokens", "finish_reason")


def _values(*, step_key: str, role: str, requested: str = "", served: str = "",
            system: str = "", payload: Any = None, response: Any = None,
            reasoning: str = "", started: float = 0.0, duration: float = 0.0,
            ok: bool = True, error: str = "", response_format: str = "",
            reasoning_effort: str = "", max_tokens: int | None = None,
            finish_reason: str = "") -> tuple:
    """One call's column values, in `_COLUMNS` order, its texts stored as
    blobs (`put_blob`, `_payload_hashes`)."""
    if not isinstance(response, str):
        try:
            response = json.dumps(response, ensure_ascii=False)
        except Exception:
            response = str(response)
    try:
        max_tokens = int(max_tokens) if max_tokens is not None else None
    except (TypeError, ValueError):
        max_tokens = None
    return (str(step_key or ""), str(role or ""),
            str(requested or ""), str(served or ""),
            float(started or time.time()), float(duration or 0.0),
            1 if ok else 0, str(error or "")[:400],
            put_blob(system),
            json.dumps(_payload_hashes(payload), ensure_ascii=False),
            put_blob(response), put_blob(reasoning) if reasoning else None,
            str(response_format or ""), str(reasoning_effort or ""),
            max_tokens, str(finish_reason or ""))


def _insert(table: str, key: str, owner: int, seq: int, values: tuple) -> None:
    qi(f"INSERT INTO {table}({key},seq,{','.join(_COLUMNS)}) "
       f"VALUES({','.join('?' * (len(_COLUMNS) + 2))})", (owner, seq, *values))


def record_exchange(*, turn_id: int | None, step_key: str, role: str,
                    requested: str = "", served: str = "",
                    system: str = "", payload: Any = None,
                    response: Any = None, reasoning: str = "",
                    started: float = 0.0, duration: float = 0.0,
                    ok: bool = True, error: str = "",
                    response_format: str = "", reasoning_effort: str = "",
                    max_tokens: int | None = None,
                    finish_reason: str = "") -> None:
    """Record one provider exchange against a turn, in call order.

    The four shape fields are HOW the call was made, beside what it sent and
    what came back: the `response_format` type the provider layer actually
    put on the wire (`json_schema`, `json_object`, or empty), the reasoning
    effort it sent, the `max_tokens` it sent, and the finish reason it got
    (`providers.request_shape`). They exist because two specialist calls
    hung for 22 minutes on 2026-09-14 and the capture could not say whether
    a grammar was on the wire. Empty is a real answer -- the call never
    posted, or the provider did not say -- and is stored as such.

    `seq` is assigned per turn at insert time, so it is only the order calls
    were STARTED in if the caller inserts them in that order --
    `runtime._with_engine_notes` sorts by `started` before flushing, and that
    is where the guarantee lives. It matters because the five specialists run
    concurrently and finish out of order, so completion order is not the order
    anything happened in.

    A diagnostic must never fail the call it is describing, so everything here
    is swallowed.
    """
    if not turn_id or not capture_enabled():
        return
    try:
        _file_pending(int(turn_id))
    except Exception:
        pass
    try:
        row = q("SELECT COALESCE(MAX(seq),0) AS s FROM llm_capture "
                "WHERE turn_id=?", (int(turn_id),), one=True)
        seq = int(row["s"]) + 1 if row else 1
        _insert("llm_capture", "turn_id", int(turn_id), seq, _values(
            step_key=step_key, role=role, requested=requested, served=served,
            system=system, payload=payload, response=response,
            reasoning=reasoning, started=started, duration=duration, ok=ok,
            error=error, response_format=response_format,
            reasoning_effort=reasoning_effort, max_tokens=max_tokens,
            finish_reason=finish_reason))
    except Exception:
        return


def _hold_pending(chat_id: int, **fields) -> None:
    """Hold one call made for a story that has no turn yet, in the order the
    story's calls were recorded (`llm_capture_pending`)."""
    row = q("SELECT COALESCE(MAX(seq),0) AS s FROM llm_capture_pending "
            "WHERE chat_id=?", (int(chat_id),), one=True)
    seq = int(row["s"]) + 1 if row else 1
    _insert("llm_capture_pending", "chat_id", int(chat_id), seq, _values(**fields))


def _file_pending(turn_id: int) -> None:
    """File the calls a story held before it had a turn under the first turn
    anything is recorded against, in the order they started -- every one of
    them before anything recorded after. One read when nothing is held,
    which is every story but one just launched."""
    if not q("SELECT 1 FROM llm_capture_pending LIMIT 1", one=True):
        return
    chat = q("SELECT chat_id FROM turns WHERE id=?", (int(turn_id),), one=True)
    if not chat:
        return
    with transaction():
        held = q("SELECT * FROM llm_capture_pending WHERE chat_id=? ORDER BY seq",
                 (int(chat["chat_id"]),))
        if not held:
            return
        row = q("SELECT COALESCE(MAX(seq),0) AS s FROM llm_capture "
                "WHERE turn_id=?", (int(turn_id),), one=True)
        base = int(row["s"]) if row else 0
        for n, h in enumerate(held, start=1):
            _insert("llm_capture", "turn_id", int(turn_id), base + n,
                    tuple(h[c] for c in _COLUMNS))
        qi("DELETE FROM llm_capture_pending WHERE chat_id=? AND id<=?",
           (int(chat["chat_id"]), max(int(h["id"]) for h in held)))


def record_chat_exchange(chat_id, *, step_key: str, turn_idx=None, **fields) -> None:
    """Record one provider call made for a story outside any step and any
    Room scope -- the layout tier's and the room designer's, in the job that
    builds the rooms in view, and the tier's at the launch -- under the turn
    `turn_idx` names (the turn a job works for), else the turn in play, as a
    Room call is (`latest_turn_id`), or held until the story has one. A
    diagnostic never fails the call it describes."""
    if chat_id is None or not capture_enabled():
        return
    try:
        cid = int(chat_id)
        turn_id = (_turn_at(cid, turn_idx) if turn_idx is not None else None) \
            or latest_turn_id(cid)
        if turn_id:
            record_exchange(turn_id=turn_id, step_key=step_key, **fields)
        else:
            _hold_pending(cid, step_key=step_key, **fields)
    except Exception:
        return


def _turn_at(chat_id: int, turn_idx) -> int | None:
    """The id of the chat's turn at index `turn_idx`, or None."""
    try:
        row = q("SELECT id FROM turns WHERE chat_id=? AND idx=? ORDER BY id DESC "
                "LIMIT 1", (int(chat_id), int(turn_idx)), one=True)
    except Exception:
        return None
    return int(row["id"]) if row else None


@contextlib.contextmanager
def recording_outside_a_step(chat_id, step_key: str, *, turn_idx=None):
    """Record every provider call made inside, for chat `chat_id` under
    `step_key` (`record_chat_exchange`).

    WORK OUTSIDE A STEP RECORDED NOTHING. A step arms the exchange sink every
    provider call notes itself on (`pipeline_context.note_step_exchange`);
    a background job runs with it cleared (`core/jobs.py`), and the launch
    runs before any step -- so the layout tier and the room designer, which
    build the rooms ahead of every beat, were in no capture at all: the
    owner's database, capture on with full bodies, held ten step keys and
    none of theirs. A call a step is already recording is left to that step;
    off, nothing is recorded and nothing is copied."""
    from core.pipeline_context import current_exchange_sink
    if current_exchange_sink.get() is not None:
        yield
        return

    def sink(entry):
        record_chat_exchange(chat_id, step_key=step_key, turn_idx=turn_idx, **{
            k: v for k, v in entry.items() if k != "step_key"})
    token = current_exchange_sink.set(sink)
    try:
        yield
    finally:
        current_exchange_sink.reset(token)


def pending_exchanges(chat_id: int, *, include_bodies: bool = False) -> list:
    """Every call a story holds because it has no turn yet, in order -- the
    record of a story nobody has launched (`llm_capture_pending`)."""
    rows = q("SELECT * FROM llm_capture_pending WHERE chat_id=? ORDER BY seq",
             (int(chat_id),))
    return [_read_row(row, include_bodies) for row in rows or ()]


def exchanges_for_turn(turn_id: int, *, include_bodies: bool = False) -> list:
    """Every captured exchange for one turn, in the order the calls started."""
    rows = q("SELECT * FROM llm_capture WHERE turn_id=? ORDER BY seq",
             (int(turn_id),))
    return [_read_row(row, include_bodies) for row in rows or ()]


def _read_row(row, include_bodies: bool) -> dict:
    entry = {k: row[k] for k in row.keys()}
    try:
        entry["payload_hashes"] = json.loads(entry.get("payload_hashes")
                                             or "{}")
    except Exception:
        entry["payload_hashes"] = {}
    if include_bodies:
        entry["system"] = get_blob(entry.get("system_hash"))
        entry["response"] = get_blob(entry.get("response_hash"))
        entry["reasoning"] = get_blob(entry.get("reasoning_hash"))
        entry["payload"] = {k: get_blob(v) for k, v
                            in entry["payload_hashes"].items()}
    return entry


def prune(chat_id: int) -> int:
    """Drop capture for all but the most recent RETAIN_TURNS turns of a chat.

    Blobs are left alone: they are shared across turns and chats by design, so
    deleting one because a turn aged out would strip it from every other
    record referencing it. `vacuum_blobs` is the separate, safe collector.
    """
    try:
        rows = q("SELECT id FROM turns WHERE chat_id=? ORDER BY idx DESC "
                 "LIMIT -1 OFFSET ?", (int(chat_id), RETAIN_TURNS))
        ids = [int(r["id"]) for r in rows or ()]
        for tid in ids:
            qi("DELETE FROM llm_capture WHERE turn_id=?", (tid,))
        return len(ids)
    except Exception:
        return 0


def referenced_blob_hashes() -> set:
    """Every blob hash a live capture row still points at.

    FOUR REFERENCE SITES, NOT THREE (review 2026-09-07 A68). Three of them are
    columns -- `system_hash`, `response_hash`, `reasoning_hash` -- and the
    fourth is the whole reason this store is small: `_payload_hashes` hashes
    each TOP-LEVEL PAYLOAD KEY separately and files the map as JSON in
    `payload_hashes`, so the payload blobs (the larger half of a beat: scene,
    cast, lore) are referenced from inside a JSON value that no SQL column
    predicate reaches. The collector's `NOT IN` over the three columns
    therefore collected every payload blob of every captured call, and
    `exchanges_for_turn(include_bodies=True)` -- the debug reader, the export
    -- got `None` back for each of them: a capture that says which sheet was
    sent and cannot say what it was asked.

    Computed in Python rather than in the predicate because the reference
    lives in a JSON document, which is where SQL stopped being the right
    tool; and returned rather than inlined so a caller can ask the question
    without deleting anything.
    """
    live = set()
    # a call a story holds before its first turn references blobs too
    # (`llm_capture_pending`), and its hold can outlast a vacuum
    rows = list(q("SELECT system_hash, response_hash, reasoning_hash, "
                  "payload_hashes FROM llm_capture") or ())
    rows += list(q("SELECT system_hash, response_hash, reasoning_hash, "
                   "payload_hashes FROM llm_capture_pending") or ())
    for row in rows:
        for column in ("system_hash", "response_hash", "reasoning_hash"):
            digest = row[column]
            if digest:
                live.add(str(digest))
        try:
            payload = json.loads(row["payload_hashes"] or "{}")
        except (TypeError, ValueError):
            # An unreadable map is not licence to collect what it referenced:
            # nothing here can prove those blobs are dead.
            continue
        if isinstance(payload, dict):
            live.update(str(v) for v in payload.values() if v)
    return live


def vacuum_blobs() -> int:
    """Delete blobs no capture row references any more."""
    try:
        before = q("SELECT COUNT(*) AS n FROM llm_blobs", one=True)["n"]
        live = referenced_blob_hashes()
        # The live set goes into a temp table rather than a parameter list, so
        # the delete stays ONE statement over any number of references -- no
        # chunk size, and so no chance of a chunk boundary sparing or eating a
        # row.
        with transaction() as c:
            c.execute("CREATE TEMP TABLE IF NOT EXISTS _live_blobs("
                      "hash TEXT PRIMARY KEY)")
            c.execute("DELETE FROM _live_blobs")
            if live:
                c.executemany("INSERT OR IGNORE INTO _live_blobs(hash) "
                              "VALUES(?)", [(h,) for h in live])
            c.execute("DELETE FROM llm_blobs WHERE hash NOT IN "
                      "(SELECT hash FROM _live_blobs)")
            c.execute("DROP TABLE _live_blobs")
        after = q("SELECT COUNT(*) AS n FROM llm_blobs", one=True)["n"]
        return int(before) - int(after)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# The Writers' Room's own calls
# ---------------------------------------------------------------------------

#: The step key prefix a Room call is filed under: `room:planner`,
#: `room:dramaturge`, `room:bible`, `room:deliberate`. The prefix is what
#: `persist/pipeline_trace.py` reads to tell a Room call from a pipeline
#: stage, and it is the only thing that distinguishes them in the store --
#: deliberately, because they belong in ONE ordered reading.
ROOM_STEP_PREFIX = "room:"

#: The phase a Room call is filed under when its caller names none.
ROOM_PHASE_DEFAULT = "planner"

#: The scope one Room reply runs in: `{"chat_id", "phase", "turn_id"}`, or
#: None outside one. A ContextVar rather than an argument because the calls
#: it covers are made several frames below the seam that knows which chat is
#: being planned -- the Planner's tool loop, the Dramaturge's pass, a bible
#: fold -- and none of them should have to be handed a chat id to be
#: readable.
#:
#: It is INHERITED by a background job on purpose. `core/jobs.py` clears the
#: turn-scoped vars because a job outlives the turn that started it; a job
#: the room started (the identity fill, a Dramaturge pass) is still the
#: room's own work, and filing its calls anywhere else would split one
#: session's record in two.
_room_scope: contextvars.ContextVar = contextvars.ContextVar(
    "llm_capture_room_scope", default=None)


def room_scope():
    """The Room capture scope in force, or None."""
    return _room_scope.get()


def latest_turn_id(chat_id):
    """The turn a Room call is filed against: the chat's most recent one.

    WHY A ROOM CALL IS KEYED TO A TURN AT ALL. A pipeline stage belongs to
    the beat it runs in; a Room call does not -- the player opens the panel
    between beats and plans forward. But the store is per-turn
    (`llm_capture.turn_id` is a foreign key into `turns`), and more
    importantly a reader wants ONE ordered account: this beat happened, then
    the room said this about it. So a Room call is filed against THE TURN IN
    PLAY -- the beat the room was looking at when it ran -- and sorts after
    that turn's stages by wall clock, which is the order the two actually
    happened in.

    A chat with no turn yet HOLDS its calls until it has one
    (`_hold_pending`). This note used to call that the empty case rather than
    the planning case -- a chat has a turn from its greeting on -- and the
    prelude proved it the planning case: the player plans with the Room
    before the launch, and the owner's chat 165, a budget report's worth of
    Room work, had no turn and left no row.
    """
    try:
        row = q("SELECT id FROM turns WHERE chat_id=? ORDER BY idx DESC "
                "LIMIT 1", (int(chat_id),), one=True)
    except Exception:
        return None
    return int(row["id"]) if row else None


@contextlib.contextmanager
def room_capture(chat_id, phase: str = ROOM_PHASE_DEFAULT):
    """Arm Room capture for one reply, pass or fold.

    Everything inside records under `room:<phase>` against the turn in play,
    and nothing outside does. Costs one ContextVar set when capture is off,
    which is the default -- the turn id is not resolved until a call is
    actually recorded.
    """
    token = _room_scope.set({"chat_id": int(chat_id),
                             "phase": str(phase or "") or ROOM_PHASE_DEFAULT,
                             "turn_id": None})
    try:
        yield
    finally:
        _room_scope.reset(token)


def record_room_exchange(*, role: str, system: str = "", payload: Any = None,
                         response: Any = None, reasoning: str = "",
                         started: float = 0.0, duration: float = 0.0,
                         ok: bool = True, error: str = "",
                         phase: str = "", chat_id=None,
                         requested: str = "", served: str = "",
                         response_format: str = "", reasoning_effort: str = "",
                         max_tokens: int | None = None,
                         finish_reason: str = "") -> None:
    """Record one Writers' Room provider call.

    The same recorder, the same content-addressed blobs and the same
    off-by-default rule as a pipeline stage's. The dedup earns more here
    than anywhere: the Room's system sheet is the most stable large blob in
    the engine -- its tool table alone measured 15.6k characters on
    2026-09-04, byte-identical on every step of every reply -- so hashing
    stores it once per prompt edit rather than once per step.

    Why this was needed at all: `record_exchange` was called from
    `agents/runtime.py` and nowhere else, so every pipeline stage and every
    Director specialist was readable and the two agents the host most wants
    to read were not. All five play runs of 2026-09-05 said so; the
    caravanserai run put a number on it ("24 model calls of author-facing
    work left no payload to read").

    No-op outside a `room_capture` scope, and no-op when capture is off.
    A diagnostic must never fail the call it is describing, so everything
    here is swallowed.
    """
    scope = _room_scope.get()
    if scope is None and chat_id is None:
        return
    if not capture_enabled():
        return
    try:
        cid = int(chat_id if chat_id is not None else scope["chat_id"])
        turn_id = (scope.get("turn_id") if scope else None) or latest_turn_id(cid)
        step = str(phase or (scope or {}).get("phase") or ROOM_PHASE_DEFAULT)
        fields = dict(step_key=ROOM_STEP_PREFIX + step,
                      role=role, requested=requested, served=served,
                      system=system, payload=payload, response=response,
                      reasoning=reasoning, started=started,
                      duration=duration, ok=ok, error=error,
                      response_format=response_format,
                      reasoning_effort=reasoning_effort,
                      max_tokens=max_tokens, finish_reason=finish_reason)
        if not turn_id:
            # the Room planning with the player before the launch: held
            # until the story has a turn (`_hold_pending`)
            _hold_pending(cid, **fields)
            return
        if scope is not None:
            scope["turn_id"] = turn_id
        record_exchange(turn_id=turn_id, **fields)
    except Exception:
        return


def is_room_step(step_key) -> bool:
    """Whether a captured row is a Room call rather than a pipeline stage."""
    return str(step_key or "").startswith(ROOM_STEP_PREFIX)


def room_phase(step_key) -> str:
    """The phase of a Room call's step key (`room:planner` -> `planner`)."""
    key = str(step_key or "")
    return key[len(ROOM_STEP_PREFIX):] if is_room_step(key) else ""


def enter_room_capture(chat_id, phase: str = ROOM_PHASE_DEFAULT) -> None:
    """Arm Room capture for the REST OF THIS CONTEXT, with no reset.

    The pair to `room_capture` for a worker thread: the room's streamed
    reply arms its token and reasoning sinks inside the thread that makes
    the calls, because a ContextVar set in the generator would not be
    visible there and one set in the worker cannot leak back. Capture is
    armed the same way, beside them, for the same reason.
    """
    _room_scope.set({"chat_id": int(chat_id),
                     "phase": str(phase or "") or ROOM_PHASE_DEFAULT,
                     "turn_id": None})
