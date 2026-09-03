"""Planning needs -- what the world was asked for and nobody has planned.

The world-context compiler (`agents/mapping.compile_world_context`) never
invents. Where the mapping model used to stage a room for a door the plan
had not drawn, the compiler records that the beat reached for material the
plan does not hold, and the Director renders the SURFACE of it -- what a body
walking through the door perceives -- and no more. The record here is the
typed need the Writers' Room answers (v2 § 9.3: "a missing location is an
authoring need rather than an excuse to hide world generation inside
retrieval"); until the room exists, a deterministic fill answers it.

A need is a fact about the beat, so it is written at COMMIT, from the
committed diff, never from a stage that may be rerolled. It is frame-scoped
like the scene it was raised in, capped, and keyed so a rerun of the same
beat cannot raise the same need twice.
"""

from __future__ import annotations

import hashlib

#: The closed set of things a beat can want planned. A request for anything
#: else is filed as a `thing` with its declared kind kept on the surface.
NEED_KINDS = ("room", "person", "thing")

#: Why a need was raised -- each one a place the mapping model used to
#: invent, and each one now a record instead.
NEED_REASONS = (
    # The player's declared destination is neither a scene room nor a
    # planned one. The scene commit still mints the destination (a declared
    # destination always exists); the PLAN behind it is what is missing.
    "declared_destination_unplanned",
    # The Director's location query named a place neither the scene nor
    # the plan can answer for.
    "location_query_unmatched",
    # The player's declaration presumed content that does not exist yet
    # (`flow.generation_requests`): the player owns the declared existence,
    # the room owns what was left unstated.
    "generation_request",
)

#: How many open needs one frame keeps. Beyond it the oldest fall off:
#: a need nobody answered for sixty-four beats is a need the story walked
#: away from, and the next visit raises it again.
PLANNING_NEEDS_CAP = 64

#: The world key. Frame-scoped (core/db.FRAME_SCOPED_WORLD_KEYS).
PLANNING_NEEDS_KEY = "planning_needs"


def _need_id(kind, reason, subject, frame_id):
    material = "%s|%s|%s|%s" % (kind, reason, str(subject or "").casefold(),
                                frame_id if frame_id is not None else "")
    return "need_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def planning_need(kind, reason, *, subject, surface=None, turn_idx=0,
                  frame_id=None):
    """One typed need. ``subject`` is what the beat called the thing (a
    room id, a query, a request's subject); ``surface`` is whatever the beat
    committed about it -- the stub's name and exits, the request's stated
    specifics -- so the plan that answers may not contradict it."""
    kind = str(kind or "").strip()
    declared_kind = kind
    if kind not in NEED_KINDS:
        kind = "thing"
    reason = str(reason or "").strip()
    if reason not in NEED_REASONS:
        raise ValueError("unknown planning-need reason %r" % reason)
    subject = " ".join(str(subject or "").split())
    if not subject:
        raise ValueError("a planning need names what was asked for")
    need = {
        "need_id": _need_id(kind, reason, subject, frame_id),
        "kind": kind,
        "reason": reason,
        "subject": subject,
        "surface": dict(surface) if isinstance(surface, dict) else {},
        "status": "open",
        "raised_turn": int(turn_idx or 0),
    }
    if declared_kind and declared_kind != kind:
        need["surface"]["declared_kind"] = declared_kind
    return need


def normalize_planning_needs(stored):
    """The ledger as read: a list of well-formed needs, nothing else."""
    out = []
    seen = set()
    for entry in (stored or []) if isinstance(stored, list) else []:
        if not isinstance(entry, dict):
            continue
        need_id = str(entry.get("need_id") or "")
        if not need_id or need_id in seen:
            continue
        if entry.get("kind") not in NEED_KINDS:
            continue
        if entry.get("reason") not in NEED_REASONS:
            continue
        seen.add(need_id)
        out.append(dict(entry))
    return out


def record_planning_needs(cid, needs, *, frame_id=None):
    """Append this beat's needs to the frame's ledger. Returns the number
    newly recorded. A need already open under its id is left as it was:
    a rerun of the beat, or a second beat at the same unplanned door, is
    the same need, not a second one."""
    from core.db import wget_for_frame, wset_for_frame

    fresh = normalize_planning_needs(list(needs or []))
    if not fresh:
        return 0
    ledger = normalize_planning_needs(
        wget_for_frame(cid, PLANNING_NEEDS_KEY, frame_id, []) or [])
    open_ids = {n["need_id"] for n in ledger}
    added = 0
    for need in fresh:
        if need["need_id"] in open_ids:
            continue
        ledger.append(need)
        open_ids.add(need["need_id"])
        added += 1
    if added:
        ledger = ledger[-PLANNING_NEEDS_CAP:]
        wset_for_frame(cid, PLANNING_NEEDS_KEY, ledger, frame_id)
    return added


def open_planning_needs(cid, *, frame_id=None):
    """Every need still open in the frame, oldest first."""
    from core.db import wget_for_frame

    return [n for n in normalize_planning_needs(
        wget_for_frame(cid, PLANNING_NEEDS_KEY, frame_id, []) or [])
        if n.get("status") == "open"]


def close_planning_need(cid, need_id, *, frame_id=None, answered_by=""):
    """Mark one need answered. Returns True when a need changed."""
    from core.db import wget_for_frame, wset_for_frame

    ledger = normalize_planning_needs(
        wget_for_frame(cid, PLANNING_NEEDS_KEY, frame_id, []) or [])
    changed = False
    for need in ledger:
        if need.get("need_id") == need_id and need.get("status") == "open":
            need["status"] = "answered"
            if answered_by:
                need["answered_by"] = str(answered_by)
            changed = True
    if changed:
        wset_for_frame(cid, PLANNING_NEEDS_KEY, ledger, frame_id)
    return changed
