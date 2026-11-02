"""The world-pressure ledger: the world-KV `world_pressures`, one entry per
ongoing process the world must advance or visibly hold.

It shared this module with the pending-obligations ledger until 2026-11-01,
when the owner retired that one ("obligations caused hyperfixation"). Its
channel had left the Director on 2026-10-02 -- what a mind owes is that mind's
own to keep, in its own notebook (`commit_background.owed_to`, a character's
`still_waiting_for`) -- and once the encoder's stray writes were stripped
(`director_prose.RETIRED_CHANNELS`, review 2026-11-01 lane L7b) nothing opened
an entry. Its commit domain, its world key and its channel went with it; an old
story's `pending_obligations` rows are read by nothing and ride its archive and
checkpoints verbatim (docs/guides/DATABASE.md).

Extracted verbatim from commit.py, which re-exports every name here.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import re

from core.db import wget, wset_if_changed
from core.pipeline_context import note_step_decision
from persist.commit_common import _normalized_fact

# ---- World pressure (F5 -- THE WORLD ACTS) ----

# Consecutive beats a pressure may sit HELD (explicitly or by silence) before
# it is flagged must_tick_this_beat in the resolve payload -- the DW-2
# "significance floor" pointed at ongoing processes: the world must either
# escalate or its stillness must be a repeated, visible choice, never a
# default. 2 held beats -> the 3rd beat's payload demands a tick.
WORLD_PRESSURE_STALL_AGE = 2

#: How many open pressures the ledger carries. Applied as `ledger[-CAP:]`,
#: which drops the oldest, and the oldest is the
#: one whose held-streak has had longest to grow, so the entry the next
#: payload would have flagged must_tick_this_beat is the first one deleted --
#: the Enterprise Array failure (a probed artifact nothing ever answered)
#: reintroduced by array slice, one cap-width later.
#:
#: The NUMBER is the owner's call. Every eviction is written to the turn's
#: decision log (`evicted_by_cap`, with the subject, level and held streak),
#: so an ongoing process that stops being tracked is distinguishable from one
#: the Director resolved.
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


def _positioned_body_named(scene, subject):
    """The positioned body a pressure's subject is about, or None.

    A subject names a body by its whole name, or by its last name where that
    last name belongs to exactly one positioned body ("Captain Hale's
    approach" against a positions key of "Captain Edmund Hale"). One shared
    surname is nobody: two Cranes in the room and the subject is about
    neither for this purpose. Words shorter than three letters never match.
    """
    subject_cf = " %s " % re.sub(r"[^a-z0-9]+", " ", str(subject or "").casefold())
    if not subject_cf.strip():
        return None
    keys = [str(k) for k in ((scene or {}).get("positions") or {})
            if str(k).strip()]
    for key in keys:
        folded = re.sub(r"[^a-z0-9]+", " ", key.casefold()).strip()
        if folded and f" {folded} " in subject_cf:
            return key
    by_last = {}
    for key in keys:
        words = [w for w in re.split(r"[^a-z0-9]+", key.casefold()) if len(w) >= 3]
        if words:
            by_last.setdefault(words[-1], []).append(key)
    for last, owners in by_last.items():
        if len(owners) == 1 and f" {last} " in subject_cf:
            return owners[0]
    return None


def _find_pressure(ledger, op):
    """Index of the ledger entry an op targets: exact id first, then a fuzzy
    overlapping-subject fallback (models routinely echo the subject but not
    the id)."""
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

    # REPORT-ONLY: a tick on a pressure whose subject is a positioned body
    # counts only when that body's position changed this beat. The Director
    # ticked "Captain Hale's approach continues toward Clara" on fifteen
    # beats running while the captain's position never changed (scratch play
    # 2026-09-14, chat 9); each tick reset the streak, so the must-tick floor
    # never fired. The floor stays a warning until its false-positive rate is
    # measured (the owner's 2026-09-06 ruling on guards over valid output).
    _sd = res.get("state_diff") if isinstance(res.get("state_diff"), dict) else {}
    _moved = {str(k).strip().casefold() for k in (_sd.get("positions") or {})}
    # Parsed only on a beat that ticks: the scene is the largest row a story
    # has and this domain runs inside the write lock on every beat (review
    # 2026-11-01, persist_scene_entities E1).
    _scene_now = None
    for op in ops:
        if not isinstance(op, dict) \
                or str(op.get("op") or "").strip().lower() != "tick":
            continue
        if _scene_now is None:
            _scene_now = wget(cid, "scene", {}) or {}
        _idx = _find_pressure(ledger, op)
        _subject = str((ledger[_idx].get("subject") if _idx is not None
                        else None) or op.get("subject") or "")
        _body = _positioned_body_named(_scene_now, _subject)
        if _body and _body.casefold() not in _moved:
            ctx.add_warning(
                f"World pressure ticked without movement: {_subject!r} is "
                f"about {_body}, and {_body}'s position did not change this "
                "beat. A pressure about where a body is going advances by "
                "the body moving.")

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
        # An ongoing process leaving the ledger here did NOT resolve: no op
        # ended it and no beat showed it ending. Recorded per entry so the
        # decision log separates the two; see WORLD_PRESSURE_CAP.
        for entry in ledger[:-WORLD_PRESSURE_CAP]:
            try:
                held = max(0, int(entry.get("held_streak") or 0))
            except (TypeError, ValueError):
                held = 0
            note_step_decision(
                "world_pressure_ledger", str(entry.get("subject") or "?"),
                "evicted_by_cap",
                "ledger held %d open pressures against cap %d; this was the "
                "oldest. id=%s level=%s opened_turn=%s held_streak=%d%s -- "
                "unresolved, and no longer tracked or flagged."
                % (len(ledger), WORLD_PRESSURE_CAP, entry.get("id"),
                   entry.get("level"), entry.get("opened_turn"), held,
                   " (WAS STALLED)" if held >= WORLD_PRESSURE_STALL_AGE
                   else ""))
        ledger = ledger[-WORLD_PRESSURE_CAP:]
    wset_if_changed(cid, "world_pressures", ledger)
    return {"opened": opened, "ticked": ticked, "held": held,
            "resolved": resolved, "unaddressed": unaddressed,
            "stalled": stalled, "open": len(ledger)}
