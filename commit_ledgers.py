"""The two world-KV debt ledgers -- pending obligations and world pressure:
same shape, same overdue/stall discipline.

Extracted verbatim from commit.py, which re-exports every name here.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

from db import wget, wset
from commit_common import _normalized_fact

# ---- Obligation ledger ----
#
# The world-KV `pending_obligations` ledger tracks open narrative debts --
# demands, promises, announced actions, unanswered questions -- registered by
# director_resolve's `obligations` ops and applied here deterministically
# (mirroring the standing_intentions machinery). Each entry:
# {id, who, what, kind, opened_turn}. director_resolve's payload surfaces
# pending_obligation_view, whose must_discharge_this_beat flag plus the
# prompt's hard rule forbid re-deferring an obligation past its window.

OBLIGATION_OVERDUE_AGE = 2   # beats after which an open obligation must discharge
OBLIGATION_CAP = 12

def pending_obligation_view(chat_id, turn_idx):
    """Payload-ready view of the obligation ledger: each entry with its
    deterministically computed age and must-discharge flag."""
    view = []
    for entry in (wget(chat_id, "pending_obligations", []) or [])[:OBLIGATION_CAP]:
        if not isinstance(entry, dict):
            continue
        try:
            age = max(0, int(turn_idx) - int(entry.get("opened_turn", turn_idx)))
        except (TypeError, ValueError):
            age = 0
        view.append({
            "id": entry.get("id"),
            "who": entry.get("who"),
            "what": entry.get("what"),
            "kind": entry.get("kind", "demand"),
            "age_beats": age,
            "must_discharge_this_beat": age >= OBLIGATION_OVERDUE_AGE,
        })
    return view

def _find_obligation(ledger, op):
    """Index of the ledger entry an op targets: exact id first, then a
    fuzzy same-debtor/overlapping-text fallback (models routinely echo the
    text but not the id)."""
    oid = str(op.get("id") or "").strip()
    if oid:
        for i, entry in enumerate(ledger):
            if str(entry.get("id") or "") == oid:
                return i
    who = _normalized_fact(op.get("who"))
    what = _normalized_fact(op.get("what"))
    if not what:
        return None
    for i, entry in enumerate(ledger):
        entry_who = _normalized_fact(entry.get("who"))
        entry_what = _normalized_fact(entry.get("what"))
        if who and entry_who and who != entry_who:
            continue
        if entry_what and (what in entry_what or entry_what in what):
            return i
    return None

def commit_obligations(ctx, nonce):
    """Apply director_resolve's obligation ops to the pending_obligations
    ledger. Deterministic: open appends (deduped -- re-demanding an open
    debt is not a second debt), discharge/refuse removes. The commit-side
    reminder: any entry still open past OBLIGATION_OVERDUE_AGE after this
    beat's ops was re-deferred against the prompt's hard rule -- warn, and
    leave it flagged for the next beat's payload."""
    cid = ctx.chat.id
    turn = ctx.turn
    res = ctx.director_resolve or {}
    ops = res.get("obligations") if isinstance(res.get("obligations"), list) else []
    ledger = [
        dict(entry)
        for entry in (wget(cid, "pending_obligations", []) or [])
        if isinstance(entry, dict) and entry.get("what")
    ]

    opened = discharged = 0
    for op in ops:
        if not isinstance(op, dict):
            continue
        op_kind = str(op.get("op") or "").strip().lower()
        if op_kind == "open":
            what = str(op.get("what") or "").strip()
            if not what or _find_obligation(ledger, op) is not None:
                continue
            ledger.append({
                "id": f"obl:{turn.idx}:{opened}",
                "who": str(op.get("who") or "").strip(),
                "what": what,
                "kind": str(op.get("kind") or "demand").strip() or "demand",
                "opened_turn": turn.idx,
            })
            opened += 1
        elif op_kind in ("discharge", "refuse"):
            idx = _find_obligation(ledger, op)
            if idx is None:
                ctx.add_warning(
                    f"obligation {op_kind} matched no open ledger entry: "
                    f"{(op.get('id') or op.get('what') or '')!r}"
                )
                continue
            ledger.pop(idx)
            discharged += 1

    overdue = []
    for entry in ledger:
        try:
            age = turn.idx - int(entry.get("opened_turn", turn.idx))
        except (TypeError, ValueError):
            age = 0
        if age >= OBLIGATION_OVERDUE_AGE:
            overdue.append(entry)
            ctx.add_warning(
                f"Obligation re-deferred past its window: {entry.get('who')!r} "
                f"still owes {entry.get('what')!r} (opened turn "
                f"{entry.get('opened_turn')}, age {age} beats). It MUST be "
                "discharged or explicitly refused on-page next beat."
            )

    if len(ledger) > OBLIGATION_CAP:
        ledger = ledger[-OBLIGATION_CAP:]
    wset(cid, "pending_obligations", ledger)
    return {"opened": opened, "discharged": discharged,
            "open": len(ledger), "overdue": len(overdue)}

# ---- World pressure (F5 -- THE WORLD ACTS) ----

# Consecutive beats a pressure may sit HELD (explicitly or by silence) before
# it is flagged must_tick_this_beat in the resolve payload -- the DW-2
# "significance floor" pointed at ongoing processes: the world must either
# escalate or its stillness must be a repeated, visible choice, never a
# default. 2 held beats -> the 3rd beat's payload demands a tick.
WORLD_PRESSURE_STALL_AGE = 2
WORLD_PRESSURE_CAP = 8


def world_pressure_view(chat_id, turn_idx):
    """Payload-ready view of the world-pressure ledger: each open ongoing
    process (a scan in progress, an alerted authority, a spreading fire, an
    artifact probed and not yet answering) with its escalation level, how
    long it has sat unticked, and the deterministic must-tick flag."""
    view = []
    for entry in (wget(chat_id, "world_pressures", []) or [])[:WORLD_PRESSURE_CAP]:
        if not isinstance(entry, dict):
            continue
        try:
            held = max(0, int(entry.get("held_streak", 0)))
        except (TypeError, ValueError):
            held = 0
        view.append({
            "id": entry.get("id"),
            "subject": entry.get("subject"),
            "note": entry.get("note"),
            "level": entry.get("level", 0),
            "beats_since_tick": held,
            "must_tick_this_beat": held >= WORLD_PRESSURE_STALL_AGE,
        })
    return view


def _find_pressure(ledger, op):
    """Index of the ledger entry an op targets: exact id first, then a fuzzy
    overlapping-subject fallback (models routinely echo the subject but not
    the id) -- the same convention as _find_obligation."""
    oid = str(op.get("id") or "").strip()
    if oid:
        for i, entry in enumerate(ledger):
            if str(entry.get("id") or "") == oid:
                return i
    subject = _normalized_fact(op.get("subject"))
    if not subject:
        return None
    for i, entry in enumerate(ledger):
        entry_subject = _normalized_fact(entry.get("subject"))
        if entry_subject and (subject in entry_subject
                              or entry_subject in subject):
            return i
    return None


def commit_world_pressure(ctx, nonce):
    """Apply this beat's world-pressure ops to the world-KV world_pressures
    ledger. Deterministic semantics:

    - open: registers an ongoing off-character process with threat/escalation
      potential (deduped by subject). Sources: director_resolve ops every
      normal beat, plus director_establish's openers on the opening turn.
    - tick: the process escalated ON-PAGE this beat -- level += 1, the
      held-streak resets.
    - hold: an explicit, deliberate no-advance -- the streak still grows, so
      a pressure cannot be held forever without tripping the must-tick flag,
      but no warning: holding is a legitimate choice when made visibly.
    - resolve: the process ended; the entry leaves the ledger.
    - SILENCE (an open entry no op mentions): treated as an implicit hold
      AND warned -- the exact failure mode this ledger exists for (the
      Enterprise Array: an actively scanned alien artifact produced zero
      world response across 12 beats because nothing forced the Director to
      even decline to act).

    After ops, any entry whose held-streak has reached
    WORLD_PRESSURE_STALL_AGE is warned as stalled; the next beat's payload
    flags it must_tick_this_beat and agents/director.py enforces that flag
    with a bounded correction retry."""
    cid = ctx.chat.id
    turn = ctx.turn
    res = ctx.director_resolve or {}
    ops = list(res.get("world_pressure") or []) \
        if isinstance(res.get("world_pressure"), list) else []
    if turn.idx == 0:
        est = ctx.director_establish or {}
        est_ops = est.get("world_pressure")
        if isinstance(est_ops, list):
            # Establishment may only OPEN pressures -- there is no prior beat
            # to tick or hold against.
            ops = [op for op in est_ops if isinstance(op, dict)
                   and str(op.get("op") or "open").lower() == "open"] + ops

    ledger = [
        dict(entry)
        for entry in (wget(cid, "world_pressures", []) or [])
        if isinstance(entry, dict) and entry.get("subject")
    ]

    opened = ticked = held = resolved = 0
    addressed = set()
    for op in ops:
        if not isinstance(op, dict):
            continue
        op_kind = str(op.get("op") or "").strip().lower()
        if op_kind == "open":
            subject = str(op.get("subject") or "").strip()
            if not subject or _find_pressure(ledger, op) is not None:
                continue
            ledger.append({
                "id": f"wp:{turn.idx}:{opened}",
                "subject": subject,
                "note": str(op.get("note") or "").strip(),
                "level": 0,
                "opened_turn": turn.idx,
                "last_tick_turn": turn.idx,
                "held_streak": 0,
            })
            opened += 1
        elif op_kind in ("tick", "hold", "resolve"):
            idx = _find_pressure(ledger, op)
            if idx is None:
                ctx.add_warning(
                    f"world_pressure {op_kind} matched no open ledger entry: "
                    f"{(op.get('id') or op.get('subject') or '')!r}"
                )
                continue
            entry = ledger[idx]
            addressed.add(id(entry))
            if op_kind == "tick":
                entry["level"] = int(entry.get("level") or 0) + 1
                entry["last_tick_turn"] = turn.idx
                entry["held_streak"] = 0
                if str(op.get("note") or "").strip():
                    entry["note"] = str(op.get("note")).strip()
                ticked += 1
            elif op_kind == "hold":
                entry["held_streak"] = int(entry.get("held_streak") or 0) + 1
                held += 1
            else:
                ledger.pop(idx)
                resolved += 1

    unaddressed = 0
    stalled = 0
    for entry in ledger:
        if id(entry) in addressed or entry.get("opened_turn") == turn.idx:
            continue
        # Silence is a choice, but never a silent one.
        entry["held_streak"] = int(entry.get("held_streak") or 0) + 1
        unaddressed += 1
        ctx.add_warning(
            f"World pressure unaddressed: {entry.get('subject')!r} "
            f"(id {entry.get('id')}) got neither tick nor hold this beat; "
            "recorded as an implicit hold."
        )
    for entry in ledger:
        if int(entry.get("held_streak") or 0) >= WORLD_PRESSURE_STALL_AGE:
            stalled += 1
            ctx.add_warning(
                f"World pressure stalled: {entry.get('subject')!r} has gone "
                f"{entry.get('held_streak')} beats without advancing. It is "
                "flagged must_tick_this_beat for the next resolve."
            )

    if len(ledger) > WORLD_PRESSURE_CAP:
        ledger = ledger[-WORLD_PRESSURE_CAP:]
    wset(cid, "world_pressures", ledger)
    return {"opened": opened, "ticked": ticked, "held": held,
            "resolved": resolved, "unaddressed": unaddressed,
            "stalled": stalled, "open": len(ledger)}
