"""Authored (player-scheduled) future events -- P4 of the awareness/authorial
design.

A player narrating a FUTURE beat ('the elevator crashes next turn') is authoring
a world event with no in-fiction actor yet. Before this it was silently dropped
(the model resolved only the current input), so the player had to re-narrate it
by hand the following turn -- observed live in the Elevator Adventure (turn 15's
"(crashes next turn)" -> hand-typed "BOOOM!" on turn 16).

These helpers give it a durable home in the existing `scheduled_events` table
(kind 'authored_event'), fired by TURN INDEX (a discourse unit, not sim-clock
time), delivered to the next beat's Director with a resolve-now contract, and --
the point -- NOT dropped: an event the resolution did not cover is re-queued
(bounded) rather than lost, which is the deterministic floor the standing
back-burner concern about weak models dropping player-narrated world events
asked for. Coverage is judged by omission-detection (content-token overlap),
never a keyword list.
"""

from __future__ import annotations

import hashlib
import json

from db import q, qi

# A due event the resolution keeps failing to enact is re-queued at most this
# many times, then marked 'stale' with a warning -- so a mis-scheduled or
# un-resolvable beat cannot loop forever.
MAX_REQUEUES = 2
# Fraction of the summary's distinctive tokens that must appear in the resolved
# prose for the event to count as enacted this beat.
_COVERAGE_RATIO = 0.5


def _event_id(cid, turn_idx, idx, summary):
    digest = hashlib.sha256(
        f"{cid}:{turn_idx}:{idx}:{summary}".encode("utf-8")).hexdigest()[:20]
    return f"authored:{digest}"


def mint_authored_events(cid, turn_idx, scheduled_assertions):
    """Persist flow.scheduled_assertions as pending authored_event rows.
    due_at = turn_idx + max(1, due_in_turns). Stable ids (INSERT OR REPLACE)
    keyed by the minting turn so a rerun of the same turn never double-schedules.
    Returns the count minted."""
    minted = 0
    for i, assertion in enumerate(scheduled_assertions or []):
        if not isinstance(assertion, dict):
            continue
        summary = str(assertion.get("summary") or "").strip()
        if not summary:
            continue
        try:
            due_in = max(1, int(assertion.get("due_in_turns")))
        except (TypeError, ValueError):
            due_in = 1
        eid = _event_id(cid, turn_idx, i, summary)
        payload = json.dumps({
            "summary": summary, "source": "player",
            "minted_turn_idx": int(turn_idx), "requeues": 0,
        }, ensure_ascii=False)
        qi("INSERT OR REPLACE INTO scheduled_events"
           "(event_id,chat_id,due_at,kind,location_id,payload,seed,status)"
           " VALUES(?,?,?,?,?,?,?,?)",
           (eid, cid, float(int(turn_idx) + due_in), "authored_event", None,
            payload, f"authored:{cid}:{turn_idx}:{i}", "pending"))
        minted += 1
    return minted


def due_authored_events(cid, turn_idx):
    """Pending authored events due at or before turn_idx -- {event_id, summary}
    each, for delivery to the Director this beat."""
    out = []
    for row in q(
        "SELECT event_id, payload FROM scheduled_events WHERE chat_id=? "
        "AND kind='authored_event' AND status='pending' AND due_at<=? "
        "ORDER BY due_at", (cid, float(turn_idx))):
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            payload = {}
        summary = str(payload.get("summary") or "").strip()
        if summary:
            out.append({"event_id": row["event_id"], "summary": summary})
    return out


def resolve_authored_events(cid, turn_idx, resolved_text):
    """After the beat resolves: mark each DUE authored event 'fired' if the
    resolved prose covers it (content-token overlap), else re-queue to the next
    turn (bounded) so the player-narrated future beat is never silently dropped.
    Returns (fired, requeued, dropped). Idempotent per (turn, event)."""
    from agents.common import _content_tokens
    rtoks = set(_content_tokens(resolved_text or ""))
    fired = requeued = dropped = 0
    for ev in due_authored_events(cid, turn_idx):
        row = q("SELECT payload FROM scheduled_events WHERE chat_id=? AND event_id=?",
                (cid, ev["event_id"]), one=True)
        try:
            payload = json.loads(row["payload"]) if row else {}
        except (TypeError, ValueError):
            payload = {}
        stoks = set(_content_tokens(ev["summary"]))
        covered = bool(stoks) and len(stoks & rtoks) / len(stoks) >= _COVERAGE_RATIO
        if covered:
            qi("UPDATE scheduled_events SET status='fired' "
               "WHERE chat_id=? AND event_id=?", (cid, ev["event_id"]))
            fired += 1
            continue
        requeues = int(payload.get("requeues", 0)) + 1
        if requeues > MAX_REQUEUES:
            qi("UPDATE scheduled_events SET status='stale' "
               "WHERE chat_id=? AND event_id=?", (cid, ev["event_id"]))
            dropped += 1
        else:
            payload["requeues"] = requeues
            qi("UPDATE scheduled_events SET due_at=?, payload=? "
               "WHERE chat_id=? AND event_id=?",
               (float(int(turn_idx) + 1), json.dumps(payload, ensure_ascii=False),
                cid, ev["event_id"]))
            requeued += 1
    return fired, requeued, dropped
