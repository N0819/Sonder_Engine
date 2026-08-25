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

Two bounds keep "never dropped" from becoming "never ends". Rows are keyed by
the ASSERTION rather than by the minting beat, so a rerun -- or the Director
re-emitting a due event it was asked to fold in -- lands on the one live row
instead of a fresh copy with a fresh budget. And a due event whose referent
this beat's committed diff RETIRED goes stale at once rather than spending the
budget: a future whose subject has ended cannot be enacted by any later beat,
which is the rule the delay line already applies to a fuse whose cause
un-happened (world/mechanics.py).
"""

from __future__ import annotations

import hashlib
import json

from core.db import q, qi

# A due event the resolution keeps failing to enact is re-queued at most this
# many times, then marked 'stale' with a warning -- so a mis-scheduled or
# un-resolvable beat cannot loop forever.
MAX_REQUEUES = 2
# Fraction of the summary's distinctive tokens that must appear in the resolved
# prose for the event to count as enacted this beat.
_COVERAGE_RATIO = 0.5

# Op verbs that mean "this row stops standing". A scheduled assertion whose
# referent the beat RETIRED has been answered -- negatively -- and re-queueing
# it puts a finished thing back in front of the Director. The delay line
# already states this rule for the other half of the same table: a fuse whose
# cause un-happened is "cancelled loudly, never fired" (world/mechanics.py).
_RETIRING_OPS = ("remove", "clear", "detach", "drop", "delete", "end")


def _retired_text(state_diff):
    """Every word this beat's committed diff spent RETIRING something.

    Channel-agnostic on purpose: any `remove_*` channel, and any op dict whose
    `op` retires, contributes its own strings. Naming the channels would tie
    the rule to today's diff shape and to whichever ledger the live case
    happened to be about; the rule is that a referent ENDED, not which ledger
    held it.
    """
    if not isinstance(state_diff, dict):
        return ""
    out = []

    def _collect(value):
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, dict):
            for key, inner in value.items():
                if key != "op":
                    _collect(inner)
        elif isinstance(value, (list, tuple)):
            for inner in value:
                _collect(inner)

    for channel, value in state_diff.items():
        if str(channel).startswith("remove_"):
            _collect(value)
        elif isinstance(value, list):
            for item in value:
                if (isinstance(item, dict)
                        and str(item.get("op") or "").strip().casefold()
                        in _RETIRING_OPS):
                    _collect(item)
    return " ".join(out)



def _event_id(cid, summary):
    """Identity of an authored assertion: the chat and the ASSERTION, never
    the beat that minted it.

    Two mints of the same text are ONE scheduled event, which is what makes a
    re-mint idempotent instead of multiplying. Whitespace and case are
    normalised so a re-emission that only reflows the string is still the same
    assertion.

    Keyed on `turn_idx`, one assertion could exist as three pending rows, each
    with its own untouched re-queue budget -- measured three identical copies
    at one beat and two at another, the earliest minted nine beats before.
    """
    key = " ".join(str(summary or "").casefold().split())
    digest = hashlib.sha256(f"{cid}:{key}".encode("utf-8")).hexdigest()[:20]
    return f"authored:{digest}"


def mint_authored_events(cid, turn_idx, scheduled_assertions):
    """Persist flow.scheduled_assertions as pending authored_event rows.
    due_at = turn_idx + max(1, due_in_turns). Ids are keyed by ASSERTION, not
    by beat, and a row already pending under that id is left exactly as it
    stands -- so a rerun of a turn AND a later beat re-emitting a due event as
    a fresh assertion both dedupe onto the one live row. Returns the count
    minted; an absorbed echo mints nothing."""
    minted = 0
    for assertion in (scheduled_assertions or []):
        if not isinstance(assertion, dict):
            continue
        summary = str(assertion.get("summary") or "").strip()
        if not summary:
            continue
        try:
            due_in = max(1, int(assertion.get("due_in_turns")))
        except (TypeError, ValueError):
            due_in = 1
        eid = _event_id(cid, summary)
        # IDEMPOTENT RE-MINT. A due event is handed back to the Director as
        # `due_authored_events`, and the interpret prompt asks it to fold that
        # into THIS beat -- so a still-standing assertion is routinely
        # re-emitted in `flow.scheduled_assertions` on later turns. Keyed by
        # the minting turn, every echo became a NEW row with a fresh re-queue
        # budget.
        #
        # A live row absorbs its own echo: `due_at` and the requeue count are
        # left exactly as they stand, so an assertion ages out on the budget it
        # was minted with rather than being reset by the fold-in it caused. A
        # row that has already fired or gone stale is NOT live, so scheduling
        # the same thing again later legitimately re-arms it.
        live = q("SELECT status FROM scheduled_events WHERE chat_id=? "
                 "AND event_id=?", (cid, eid), one=True)
        if live and str(live["status"] or "") == "pending":
            continue
        payload = json.dumps({
            "summary": summary, "source": "player",
            "minted_turn_idx": int(turn_idx), "requeues": 0,
        }, ensure_ascii=False)
        qi("INSERT OR REPLACE INTO scheduled_events"
           "(event_id,chat_id,due_at,kind,location_id,payload,seed,status)"
           " VALUES(?,?,?,?,?,?,?,?)",
           (eid, cid, float(int(turn_idx) + due_in), "authored_event", None,
            payload, f"{eid}:{turn_idx}", "pending"))
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


def resolve_authored_events(cid, turn_idx, resolved_text, state_diff=None):
    """After the beat resolves: mark each DUE authored event 'fired' if the
    resolved prose covers it (content-token overlap), 'stale' if this beat's
    committed diff RETIRED what it names, else re-queue to the next turn
    (bounded) so the player-narrated future beat is never silently dropped.
    Returns (fired, requeued, dropped). Idempotent per (turn, event)."""
    from agents.common import _content_tokens
    rtoks = set(_content_tokens(resolved_text or ""))
    # What the beat ENDED, judged by the same overlap that judges what it
    # enacted -- one comparator, two answers.
    xtoks = set(_content_tokens(_retired_text(state_diff)))
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
        # FORECLOSED, not merely unenacted. An assertion is a claim on a
        # world the beat it comes due in may already have ended: if that
        # beat's own committed diff retires what the assertion names, no later
        # beat can enact it, so spending the re-queue budget only re-delivers
        # a finished thing to the Director. Coverage is tested first, so a
        # beat that retires a thing BY enacting the assertion still fires.
        # Subtractive: this can only end an event sooner, never create or
        # extend one, and it needs no cooperation from any model.
        if stoks and len(stoks & xtoks) / len(stoks) >= _COVERAGE_RATIO:
            qi("UPDATE scheduled_events SET status='stale' "
               "WHERE chat_id=? AND event_id=?", (cid, ev["event_id"]))
            dropped += 1
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
