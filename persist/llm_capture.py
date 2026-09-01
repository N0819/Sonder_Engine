"""Content-addressed capture of what the engine SENT and what came back.

The engine already records, per step, what each provider call COST -- role,
model, tokens, duration (`PipelineContext.llm_calls`, persisted by
`runtime._with_engine_notes`). That ledger's own comment states the boundary
this module crosses on purpose: "Diagnostic only -- roles, model ids, token
counts and durations, never content."

Content is the half a turn cannot be reconstructed without. The step outputs
are persisted as variants, so what a stage ANSWERED survives; what it was
ASKED does not, and neither does the reasoning of the six specialist sub-calls
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
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from core.db import get_setting, q, qi


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


def record_exchange(*, turn_id: int | None, step_key: str, role: str,
                    requested: str = "", served: str = "",
                    system: str = "", payload: Any = None,
                    response: Any = None, reasoning: str = "",
                    started: float = 0.0, duration: float = 0.0,
                    ok: bool = True, error: str = "") -> None:
    """Record one provider exchange against a turn, in call order.

    `seq` is assigned per turn at insert time, which is what makes a
    chronological reading possible across the Director's fan-out: the six
    specialists run concurrently and finish out of order, so wall-clock start
    is the only ordering that reflects what actually happened.

    A diagnostic must never fail the call it is describing, so everything here
    is swallowed.
    """
    if not turn_id or not capture_enabled():
        return
    try:
        row = q("SELECT COALESCE(MAX(seq),0) AS s FROM llm_capture "
                "WHERE turn_id=?", (int(turn_id),), one=True)
        seq = int(row["s"]) + 1 if row else 1
        if not isinstance(response, str):
            try:
                response = json.dumps(response, ensure_ascii=False)
            except Exception:
                response = str(response)
        qi("INSERT INTO llm_capture(turn_id,seq,step_key,role,requested,served,"
           "started,duration,ok,error,system_hash,payload_hashes,response_hash,"
           "reasoning_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (int(turn_id), seq, str(step_key or ""), str(role or ""),
            str(requested or ""), str(served or ""),
            float(started or time.time()), float(duration or 0.0),
            1 if ok else 0, str(error or "")[:400],
            put_blob(system),
            json.dumps(_payload_hashes(payload), ensure_ascii=False),
            put_blob(response), put_blob(reasoning) if reasoning else None))
    except Exception:
        return


def exchanges_for_turn(turn_id: int, *, include_bodies: bool = False) -> list:
    """Every captured exchange for one turn, in the order the calls started."""
    rows = q("SELECT * FROM llm_capture WHERE turn_id=? ORDER BY seq",
             (int(turn_id),))
    out = []
    for row in rows or ():
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
        out.append(entry)
    return out


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


def vacuum_blobs() -> int:
    """Delete blobs no capture row references any more."""
    try:
        before = q("SELECT COUNT(*) AS n FROM llm_blobs", one=True)["n"]
        qi("DELETE FROM llm_blobs WHERE hash NOT IN ("
           "SELECT system_hash FROM llm_capture WHERE system_hash IS NOT NULL "
           "UNION SELECT response_hash FROM llm_capture "
           "WHERE response_hash IS NOT NULL "
           "UNION SELECT reasoning_hash FROM llm_capture "
           "WHERE reasoning_hash IS NOT NULL)")
        after = q("SELECT COUNT(*) AS n FROM llm_blobs", one=True)["n"]
        return int(before) - int(after)
    except Exception:
        return 0
