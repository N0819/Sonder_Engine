"""Planning needs -- what the world was asked for and nobody has planned.

ONE ledger, two writers. The world-context compiler
(`agents/mapping.compile_world_context`) never invents: where the mapping
model used to stage a room for a door the plan had not drawn, the compiler
records that the beat reached for material the plan does not hold, and the
Director renders the SURFACE of it -- what a body walking through the door
perceives -- and no more. And a Director mint with no plan behind it
(`persist/commit_background.track_background_presences`) commits the
surface it saw -- appearance, position, what it did -- and files the same
kind of need with that surface attached, so the plan authored behind it
never contradicts what a body already saw (v2 § 7.4, the causal-exposure
rule). The record here is the typed need the Writers' Room answers (v2
§ 9.3: "a missing location is an authoring need rather than an excuse to
hide world generation inside retrieval"); until the room exists, a
deterministic fill answers what it can -- a person-need by enrolment into a
real charter (`world/charter_enrol.py`) -- and a thing- or room-need stays
open.

A need is a fact about the beat, so it is written at COMMIT, from the
committed diff, never from a stage that may be rerolled. It is frame-scoped
like the scene it was raised in, capped, and deduplicated on the IDENTITY of
what was asked for -- a person or thing by its name, a room by the room it
was asked for -- so a rerun of the beat, a second beat at the same unplanned
door, and the same unplanned stranger met twice each file one need.

Record shape::

    {uid, kind: room|person|thing, reason, subject, identity,
     surface: {...what the beat committed...},
     status: open|filled|closed, filed_turn, filed_at,
     presence?, fill?, filled_turn?, closed_reason?}
"""

from __future__ import annotations

import hashlib
import time

#: The closed set of things a beat can want planned. A request for anything
#: else is filed as a `thing` with its declared kind kept on the surface.
NEED_KINDS = ("room", "person", "thing")

#: Why a need was raised -- each one a place the engine used to invent, and
#: each one now a record instead.
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
    # The Director rendered a person or thing nobody planned: no charter
    # body bound, no authored plan reserved. The surface is what was seen.
    "rendered_unplanned",
    # The town could not berth a newcomer: every house is at the berth
    # ceiling, so a dwelling is owed (`charter_enrol.enrol_person`).
    "berth_ceiling",
)

NEED_STATUSES = ("open", "filled", "closed")

#: Open needs kept per frame. Past it the OLDEST open need is closed as
#: stale: a need nobody answered while sixty-four newer ones were filed is
#: a need the story walked away from (the next visit raises it again), and
#: an unbounded queue of them would be read into every drain forever.
PLANNING_NEEDS_CAP = 64

#: A committed surface's prose fields are capped so a ledger read on every
#: beat stays a ledger.
SURFACE_CHARS = 600

#: The world key. Frame-scoped (core/db.FRAME_SCOPED_WORLD_KEYS).
PLANNING_NEEDS_KEY = "planning_needs"

PLANNING_NEEDS_JOB_KEY = "planning_needs"


def _text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def need_identity(kind, subject):
    """What deduplicates a need: a person or thing by its name, a room by
    the room it was asked for -- the subject's own identity, casefolded."""
    return "%s:%s" % (str(kind or "").casefold(), _text(subject, 120).casefold())


def need_uid(identity, frame_id=None):
    material = "%s|%s" % (identity, frame_id if frame_id is not None else "")
    return "need_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _subject_of(kind, entry, surface):
    subject = entry.get("subject")
    if not subject:
        if kind == "room":
            subject = surface.get("room") or surface.get("name")
        else:
            subject = surface.get("name")
    return _text(subject, 120)


def normalize_need(entry, frame_id=None):
    """One well-formed record from whatever was stored or offered."""
    entry = entry if isinstance(entry, dict) else {}
    declared_kind = str(entry.get("kind") or "").strip().casefold()
    kind = declared_kind or "person"
    if kind not in NEED_KINDS:
        kind = "thing"
    reason = str(entry.get("reason") or "").strip()
    if reason not in NEED_REASONS:
        reason = "rendered_unplanned"
    surface_in = entry.get("surface") if isinstance(entry.get("surface"), dict) \
        else {}
    surface = {}
    for key, value in surface_in.items():
        if isinstance(value, (list, tuple)):
            items = [_text(v, 120) for v in value if _text(v, 120)]
            if items:
                surface[str(key)] = items
        elif isinstance(value, dict):
            surface[str(key)] = dict(value)
        else:
            text = _text(value, SURFACE_CHARS)
            if text:
                surface[str(key)] = text
    if declared_kind and declared_kind != kind:
        surface.setdefault("declared_kind", declared_kind)
    status = str(entry.get("status") or "open").casefold()
    if status == "answered":
        status = "filled"
    if status not in NEED_STATUSES:
        status = "open"
    subject = _subject_of(kind, entry, surface)
    identity = str(entry.get("identity") or "") or need_identity(kind, subject)
    out = {
        "uid": str(entry.get("uid") or entry.get("need_id") or "")
        or need_uid(identity, frame_id),
        "kind": kind,
        "reason": reason,
        "subject": subject,
        "identity": identity,
        "surface": surface,
        "status": status,
        "filed_turn": entry.get("filed_turn", entry.get("raised_turn")),
        "filed_at": float(entry.get("filed_at") or 0.0),
    }
    if entry.get("presence"):
        out["presence"] = _text(entry.get("presence"), 120)
    fill = entry.get("fill")
    if isinstance(fill, dict) and fill:
        out["fill"] = dict(fill)
    elif entry.get("answered_by"):
        out["fill"] = {"by": str(entry["answered_by"])}
    if entry.get("filled_turn") is not None:
        out["filled_turn"] = entry.get("filled_turn")
    if entry.get("closed_reason"):
        out["closed_reason"] = _text(entry.get("closed_reason"), 200)
    return out


def planning_need(kind, reason, *, subject, surface=None, turn_idx=0,
                  frame_id=None):
    """One typed need, unfiled. ``subject`` is what the beat called the
    thing (a room id, a query, a request's subject); ``surface`` is whatever
    the beat committed about it -- the stub's name and exits, the request's
    stated specifics -- so the plan that answers may not contradict it."""
    reason = str(reason or "").strip()
    if reason not in NEED_REASONS:
        raise ValueError("unknown planning-need reason %r" % reason)
    subject = " ".join(str(subject or "").split())
    if not subject:
        raise ValueError("a planning need names what was asked for")
    return normalize_need({
        "kind": kind, "reason": reason, "subject": subject,
        "surface": surface if isinstance(surface, dict) else {},
        "filed_turn": int(turn_idx or 0),
    }, frame_id=frame_id)


def normalize_planning_needs(stored, frame_id=None):
    """The ledger as read: a list of well-formed needs, one per uid."""
    out, seen = [], set()
    for entry in (stored or []) if isinstance(stored, list) else []:
        if not isinstance(entry, dict):
            continue
        need = normalize_need(entry, frame_id=frame_id)
        if not need["subject"] or need["uid"] in seen:
            continue
        seen.add(need["uid"])
        out.append(need)
    return out


def planning_needs(cid, frame_id=None):
    from core.db import wget_for_frame

    return normalize_planning_needs(
        wget_for_frame(cid, PLANNING_NEEDS_KEY, frame_id, []) or [],
        frame_id=frame_id)


def save_planning_needs(cid, needs, frame_id=None):
    from core.db import wset_for_frame

    wset_for_frame(cid, PLANNING_NEEDS_KEY,
                   normalize_planning_needs(list(needs or []), frame_id=frame_id),
                   frame_id)


def open_planning_needs(cid, frame_id=None, kind=None):
    """Every need still open in the frame, oldest first."""
    return [n for n in planning_needs(cid, frame_id)
            if n["status"] == "open" and (kind is None or n["kind"] == kind)]


def file_planning_need(cid, need, frame_id=None, turn_idx=None):
    """File a typed need; returns ``(record, fresh)``. Deduplicated on the
    subject's identity: a need already open (or already filled) for the same
    person, thing or room is returned as it stands and not filed twice. Past
    `PLANNING_NEEDS_CAP` open needs, the oldest open one is closed as stale."""
    need = dict(need or {})
    if turn_idx is not None and need.get("filed_turn") is None:
        need["filed_turn"] = int(turn_idx)
    if not need.get("filed_at"):
        need["filed_at"] = time.time()
    record = normalize_need(need, frame_id=frame_id)
    needs = planning_needs(cid, frame_id)
    for existing in needs:
        if existing["identity"] == record["identity"] \
                and existing["status"] != "closed":
            return existing, False
    needs = [n for n in needs if n["identity"] != record["identity"]]
    needs.append(record)
    open_needs = [n for n in needs if n["status"] == "open"]
    while len(open_needs) > PLANNING_NEEDS_CAP:
        stale = open_needs.pop(0)
        stale["status"] = "closed"
        stale["closed_reason"] = "stale: past the open-need cap"
    save_planning_needs(cid, needs, frame_id)
    return record, True


def record_planning_needs(cid, needs, *, frame_id=None):
    """File this beat's needs onto the frame's ledger; returns the number
    newly filed. A need already open under its identity is left as it was:
    a rerun of the beat, or a second beat at the same unplanned door, is
    the same need, not a second one."""
    added = 0
    for need in list(needs or []):
        if not isinstance(need, dict):
            continue
        try:
            _record, fresh = file_planning_need(cid, need, frame_id=frame_id)
        except ValueError:
            continue
        if fresh:
            added += 1
    return added


def fill_planning_need(cid, uid, fill, frame_id=None, turn_idx=None):
    """Mark a need filled and record what filled it (a charter ref for a
    person, a plan uid for a thing, a room id for a room). Returns the
    record, or None for a uid the ledger does not hold."""
    needs = planning_needs(cid, frame_id)
    for need in needs:
        if need["uid"] == str(uid):
            need["status"] = "filled"
            need["fill"] = dict(fill or {})
            if turn_idx is not None:
                need["filled_turn"] = int(turn_idx)
            save_planning_needs(cid, needs, frame_id)
            return need
    return None


def close_planning_need(cid, uid, reason, frame_id=None):
    """Close a need unanswered, with the reason. A closed identity may be
    filed again. Returns the record, or None for an unknown uid."""
    needs = planning_needs(cid, frame_id)
    for need in needs:
        if need["uid"] == str(uid):
            need["status"] = "closed"
            need["closed_reason"] = _text(reason, 200)
            save_planning_needs(cid, needs, frame_id)
            return need
    return None


def drain_planning_needs(cid, frame_id=None, scene=None):
    """Answer what the deterministic fill can answer and leave the rest.

    A person-need still open (the commit could not enrol it -- no registry
    yet, a refused surface) is tried again by enrolment; a thing-need and a
    room-need stay open for the Writers' Room, which is the job's later
    owner. Returns ``{"filled": [...], "open": n}``; pure bookkeeping, no
    model call.
    """
    from world.charter_enrol import enrol_person

    filled = []
    for need in open_planning_needs(cid, frame_id, kind="person"):
        try:
            record = enrol_person(cid, need, frame_id=frame_id, scene=scene)
        except Exception:
            continue
        if record and record.get("ref"):
            fill_planning_need(cid, need["uid"],
                               {"ref": record["ref"], "how": record["how"]},
                               frame_id=frame_id)
            filled.append({"uid": need["uid"], "ref": record["ref"],
                           "how": record["how"]})
    return {"filled": filled,
            "open": len(open_planning_needs(cid, frame_id))}


def schedule_planning_needs(ctx):
    """Queue the drain out of band, beside memory consolidation: nothing
    here is a turn fact, and a need the commit could not answer is answered
    at leisure or left for the room. Returns the job, or None when there is
    nothing open."""
    from core import jobs

    cid = ctx.chat.id
    frame_id = getattr(ctx.turn, "frame_id", None)
    if not open_planning_needs(cid, frame_id):
        return None
    base_turn = getattr(ctx.turn, "idx", None)

    def _run(job):
        return drain_planning_needs(cid, frame_id=frame_id)

    return jobs.submit(cid, PLANNING_NEEDS_JOB_KEY, _run, base_turn=base_turn)
