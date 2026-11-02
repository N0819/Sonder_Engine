"""The living world's two deterministic floors: the consequence fuse and the
place that owes a history.

Approach B's fuse mint (`mint_consequences`) turns a Director-adjudicated
`state_diff.consequences` declaration into a `scheduled_events` row that the
mechanics sweep fires on the story clock (`mechanics._fire_due_events`), and
the residue assembler reads what fired at a room being re-entered
(`fired_consequences_at`, `routines.residue_for`). Approach D's obligation
ledger (`record_obligations`, `owed_history`, `attach_owed_history`) keeps
what fired at a lore place nobody has generated yet, for the mapping seam to
hand to the place when it becomes rooms. Approach A's pure functions live in
``routines.py``; physical carriers in ``carriers.py`` and ``couriers.py``.

NO SETTING GATES EITHER. This module used to carry the author-selectable
ladder over five approaches -- `off`/`floor`/`ceiling` per approach, clamped by
the `offscreen_life` ceiling -- and the rung tables the off-screen tiers spent
at. The ladder was emptied on 2026-09-20 (7140b9cc): a world whose fires do not
burn down, whose causes do not land and whose unvisited places owe nothing is
not coherent at any setting, so B and D became unconditional and the
antagonist ladder was superseded by causality bubbles. The empty tables, the
config reader and the gates over them were RETIRED on 2026-11-01 with the paid
off-screen tiers they served (the owner: "living world is supposed to be
superseded by charter and writers room"); see ``world/offscreen.py``'s
docstring for what replaced the tiers. ``docs/design/DESIGN_LIVING_WORLD.md``
is the argument; §9 there records the author's constraints verbatim.

WHO MAY LEARN WHAT, AND BY WHAT ROUTE (the epistemic contract, enforced
structurally — each rule names the structure that holds it):

  * A consequence fuse firing is LAYER-1 FACT: it happened, at a location,
    at a clock time, whether or not anyone was there to see it. The row is
    Director-caused (``state_diff.consequences`` is adjudicated output) and
    deterministically fired, so it carries ``disposition: resolved_fact`` —
    the provenance tier that invented gossip will NOT carry.
  * Nobody LEARNS of a fired fuse merely because it is true. The firing
    writes no notice unless the player is standing at its location when it
    fires (walking in on it — §0.2's in-progress surface). Every other
    delivery is at contact: the residue assembler and the gap skeleton read
    fired rows only for the location being entered or the subject being
    asked about. There is no broadcast path to write to — that is the
    structure, not a rule someone must remember.
  * A place's accumulated obligations are real durable state, written as
    fuses fire — BEFORE anyone asks, so a later rumour has a truth to be a
    distortion of — but they are knowledge held by NOBODY. Their single
    consumer is the mapping seam at generation time (``owed_history``),
    where the place itself is made to show its aftermath. Arrival is the
    earning event; no character payload reads this ledger, and a test pins
    that no agent module but mapping names it.
  * Nothing here privileges the player. A fuse's fields are properties of
    the EVENT — what, where, when, who caused it, what was publicly visible
    — never of who it might matter to. There is no priority, importance or
    reputation field, and propagation must compute interest from the
    event's own properties (the author's constraint: the player earns
    reputation downstream of propagation, or is correctly nobody).

CARRIER-READY BY SHAPE. Information moves by carriers along routes, never by
timer alone. Every fuse payload and obligation row therefore
already carries {what, where, a time, origin, originator, witnessed,
disposition} — the pickup surface a courier needs — and the payloads are
JSON, so a route-bound {carrier, route} pair extends them without
migration. A non-empty witnessed surface reaches a body physically present
when it lands (or arriving while it still stands); that envelope follows the
holder's actual scene movement and only their private agent reads it.
"""

from __future__ import annotations

import json

from world.mechanics import stable_event_key


# ---------------------------------------------------------------------------
# Approach B floor: the fuse mint. Deterministic validation of an
# adjudicated declaration; firing lives in mechanics._fire_due_events.
# ---------------------------------------------------------------------------

CONSEQUENCE_KIND = "consequence"

#: At most this many fuses land per turn, however many were declared. Every
#: beat minting fuses turns a quiet story into a ratchet; most beats must
#: mint nothing (the ``pick_background_reactor`` shape).
MINT_CAP_PER_TURN = 2

#: Due bounds, clamped rather than refused (a legitimate intent badly
#: quantified should land at an honest distance, not vanish). Below one
#: in-story hour a consequence is this beat's own business and belongs in
#: the state_diff proper; past thirty in-story days it is a plot, and plots
#: belong to standing intentions and authored events. The declared value is
#: kept on the payload so the clamp is visible after the fact.
DUE_MIN_SECONDS = 3600.0
DUE_MAX_SECONDS = 30 * 86400.0

_WHAT_MAX = 140
_WITNESSED_MAX = 200


def _squeeze(text, cap):
    return " ".join(str(text or "").split())[:cap]


def mint_consequences(cid, scene, frame_id, turn_id, turn_idx,
                      elapsed_seconds, declarations, player_room=None):
    """Validate declared consequences into scheduled_events rows.

    Deterministic; no model, no I/O beyond subject resolution. Returns
    ``(rows, warnings)`` — rows in the shape the sweep's schedule op
    inserts, warnings for every declaration refused and why (a dropped
    fuse must be sayable, or minting failures look like a quiet world).

    The location gate is ``subjects.resolve_subject``: ``where`` must
    resolve to a generated room (kind ``room``, id ``room_uid``/scene id)
    or an ungenerated lorebook place (kind ``place``, id ``entry_uid``) —
    the 'quiet office' rule, applied at the write path. ``origin`` is
    where the CAUSE happened (this beat's stage), an event property; it is
    never read to decide anything about the player.
    """
    from world.subjects import resolve_subject

    rows, warnings = [], []
    if not isinstance(declarations, (list, tuple)) or not declarations:
        return rows, warnings
    now = float(elapsed_seconds or 0.0)
    for i, decl in enumerate(declarations):
        if len(rows) >= MINT_CAP_PER_TURN:
            warnings.append(
                f"consequence cap: {MINT_CAP_PER_TURN} per turn; "
                f"{len(declarations) - i} more dropped")
            break
        if not isinstance(decl, dict):
            warnings.append(f"consequences[{i}] is not an object; dropped")
            continue
        what = _squeeze(decl.get("what"), _WHAT_MAX)
        if not what:
            warnings.append(f"consequences[{i}] has no 'what'; dropped")
            continue
        where_raw = str(decl.get("where") or "").strip()
        res = resolve_subject(cid, scene, "place", where_raw, frame_id)
        if not res:
            warnings.append(
                f"consequences[{i}] 'where' {where_raw!r} resolves to no "
                f"room or lore place ({res.reason}); dropped — a fuse at a "
                "location the world does not contain is the 'quiet office' "
                "row")
            continue
        where_id = res.subject.id
        where_kind = res.subject.kind
        try:
            declared_due = float(decl.get("due_seconds"))
        except (TypeError, ValueError):
            warnings.append(
                f"consequences[{i}] due_seconds "
                f"{decl.get('due_seconds')!r} is not a number; dropped")
            continue
        due = min(max(declared_due, DUE_MIN_SECONDS), DUE_MAX_SECONDS)

        originator_raw = str(decl.get("originator") or "").strip()
        originator, originator_display = "", ""
        if originator_raw:
            who = resolve_subject(cid, scene, "character", originator_raw,
                                  frame_id)
            if who:
                originator = who.subject.id
            else:
                originator_display = originator_raw[:80]

        payload = {
            "frame_id": frame_id,
            "what": what,
            "where": where_id,
            "where_kind": where_kind,
            # The publicly visible surface at cause time — what phase 2's
            # carriers may pick up. Empty means the cause was not publicly
            # witnessed, and an unwitnessed event emits nothing.
            "witnessed": _squeeze(decl.get("witnessed"), _WITNESSED_MAX),
            "origin": {"room": str(player_room or ""),
                       "turn": int(turn_idx),
                       "elapsed_seconds": now},
            "originator": originator,
            **({"originator_display": originator_display}
               if originator_display else {}),
            "declared_due_seconds": declared_due,
            "base_turn": int(turn_idx),
            # Layer-1 provenance: Director-adjudicated cause, deterministic
            # firing. Phase 2's invented gossip rides the same rail with
            # ``provisional`` instead, and the field is what keeps the two
            # from ever being confused.
            "disposition": "resolved_fact",
        }
        rows.append({
            "event_id": stable_event_key(
                CONSEQUENCE_KIND, cid, frame_id, where_id, turn_id, i),
            "chat_id": cid,
            "due_at": now + due,
            "kind": CONSEQUENCE_KIND,
            "location_id": where_id,
            "payload": json.dumps(payload, ensure_ascii=False),
            "seed": f"{CONSEQUENCE_KIND}:{cid}:{turn_idx}",
            "status": "pending",
        })
    return rows, warnings


def fired_consequences_at(cid, room_id, since_seconds, until_seconds,
                          cap=2):
    """Fired fuses at one location inside a clock window, oldest first.

    The contact-time reader: the residue assembler calls this for the room
    being entered. It reads ``what`` only — the payload's origin and
    originator stay in the row for phase 2's carriers, not for narration.
    """
    from core.db import q

    out = []
    for row in q(
        "SELECT payload FROM scheduled_events WHERE chat_id=? AND "
        "status='fired' AND kind=? AND location_id=? AND due_at>? AND "
        "due_at<=? ORDER BY due_at",
        (cid, CONSEQUENCE_KIND, str(room_id), float(since_seconds),
         float(until_seconds)),
    ):
        try:
            payload = json.loads(row["payload"] or "{}")
        except Exception:
            continue
        what = str(payload.get("what") or "").strip()
        if not what:
            continue
        # Bound first: appending and then checking returned one item for
        # `cap=0` (the `[-0:]` class `crowds.talk_view` also closed).
        if len(out) >= max(0, int(cap)):
            break
        out.append(what)
    return out


# ---------------------------------------------------------------------------
# Approach D floor: the obligation ledger. Real state, accumulated as it
# happens, surfaced only where the place itself is generated.
# ---------------------------------------------------------------------------

OBLIGATION_KEY = "place_obligations"

#: Stored per place; the oldest fall off. Enough that ranking at honour
#: time has something to rank, small enough that the ledger cannot become
#: a shadow event log.
OBLIGATION_STORE_CAP = 12

#: Handed to generation per place. A room reciting fourteen obligations is
#: an arrival paragraph that reads like a briefing; the rest silently
#: expire as things that turned out not to matter (design doc §4).
OBLIGATION_HONOR_CAP = 4


def record_obligations(cid, fired_rows):
    """Fold fired consequence rows at ungenerated places into the ledger.

    Called from the commit sweep with this beat's fired fuses. Recorded
    WHENEVER a fuse fires at a place, because this is layer-1 truth
    accumulating whether or not anybody is ever told. Deliberately no
    turn-counted TTL: an unvisited place's clock is exactly
    the countdown amendment 7 warns must pause while nobody is near
    (``CLAIM_TTL_TURNS`` eating truth about subjects the player never met);
    the store cap is the only forgetting.
    """
    from core.db import transaction, wget, wset

    entries = []
    for row in fired_rows or []:
        payload = row.get("payload") if isinstance(row, dict) else None
        if isinstance(payload, str):
            try:
                payload = json.loads(payload or "{}")
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            continue
        if payload.get("where_kind") != "place":
            continue
        uid = str(payload.get("where") or "")
        what = str(payload.get("what") or "").strip()
        if not uid or not what:
            continue
        entries.append((uid, {
            "what": what,
            "event_id": str(row.get("event_id") or ""),
            "elapsed_seconds": float(row.get("due_at") or 0.0),
            "origin": payload.get("origin") or {},
            "originator": str(payload.get("originator") or ""),
            "witnessed": str(payload.get("witnessed") or ""),
            "frame_id": payload.get("frame_id"),
            "disposition": str(payload.get("disposition") or ""),
        }))
    if not entries:
        return 0
    with transaction():
        ledger = wget(cid, OBLIGATION_KEY, {}) or {}
        for uid, entry in entries:
            rows = ledger.setdefault(uid, [])
            if any(r.get("event_id") == entry["event_id"] for r in rows
                   if entry["event_id"]):
                continue  # a rerun fires the same stable id; fold, not stack
            rows.append(entry)
            del rows[:-OBLIGATION_STORE_CAP]
        wset(cid, OBLIGATION_KEY, ledger)
    return len(entries)


def owed_history(cid, entry_uid, cap=OBLIGATION_HONOR_CAP):
    """What one place owes, most recent first, capped for the honour seam.

    THE ONLY LEGITIMATE CONSUMER IS GENERATION of the place itself — the
    mapping payload, at the moment the place becomes rooms. Handing this to
    a character payload would be knowledge held without a route that
    delivered it: the accumulated history is true, and truth is not a
    channel (the Kadoman rule).
    """
    from core.db import wget

    ledger = wget(cid, OBLIGATION_KEY, {}) or {}
    rows = ledger.get(str(entry_uid)) or []
    out = []
    for row in reversed(rows[-max(0, int(cap)):]):
        if not isinstance(row, dict):
            continue
        out.append({
            "what": row.get("what") or "",
            "elapsed_seconds": row.get("elapsed_seconds"),
            **({"witnessed": row["witnessed"]} if row.get("witnessed")
               else {}),
        })
    return out


def attach_owed_history(cid, lore_hits):
    """Annotate location lore hits with what the place owes, for mapping.

    Returns copies; never mutates the input. NO SETTING GATES THIS SURFACE:
    a place you have never been owes what happened there whether or not a
    menu says so, and the debt was always recorded either way
    (`record_obligations` is ungated) -- the `place_obligations` switch only
    ever decided whether anybody was TOLD. It went unconditional on
    2026-09-20, and the `config` parameter that outlived it was retired with
    the ladder on 2026-11-01. Attached to location entries with an
    ``entry_uid``. Accrual stops by construction once a place is generated
    (``resolve_subject`` then answers ``room``, so new fuses land on the room
    id) — but old obligations stay attached until the ledger row is
    superseded; the mapping prompt scopes them to the generation moment.
    """
    out = []
    for hit in lore_hits or []:
        hit = dict(hit)
        uid = str(hit.get("entry_uid") or "")
        if uid and str(hit.get("category") or "") == "location":
            owed = owed_history(cid, uid)
            if owed:
                hit["owed_history"] = owed
        out.append(hit)
    return out
