"""Dramaturge proposals: intent as state, and the deliberation's ledger.

The Dramaturge (`agents/dramaturge.py`) proposes DIRECTION -- a pressure, a
reversal, a revelation, an arrival, an opportunity, or that nothing is
needed -- and never a package. A proposal is typed state (v2 § 4.2, § 6.1:
"conversation is presentation; proposals are state"): what it wants to be
true, why now, what it must not contradict, at what scale. The Story
Planner judges it (`agents/story_planner.deliberate`), and the verdict is
recorded here beside it, so the exchange the panel shows or summarises has
a ledger behind it and the room never re-proposes what it has refused.

Statuses: `open` (awaiting the Planner), `revised` (sent back and revised
by the Dramaturge, awaiting the Planner again), `accepted` (the Planner
found it natural and is implementing), `implemented` (a package landed for
it), `refused` (with the contradiction named), `withdrawn` (the Dramaturge
gave it up after a critique), `returned` (rounds exhausted; the
disagreement is the player's to settle).

The row rides the frame-scoped `room_proposals` world key. It is author
state: served to the room's agents and the panel, to no mind.
"""

from __future__ import annotations

import hashlib
import time

from core.db import wget_for_frame, wset_for_frame

PROPOSALS_KEY = "room_proposals"

#: The closed set of things a proposal can be. A schema the engine owns:
#: the Planner's judgement and the panel's label read it. `quiet` is the
#: Dramaturge saying the story needs nothing from it now, which is a
#: proposal too (v2 § 4.1) and is recorded so the pass counts.
PROPOSAL_KINDS = ("pressure", "reversal", "revelation", "arrival",
                  "opportunity", "quiet")
PROPOSAL_STATUSES = ("open", "revised", "accepted", "implemented", "refused",
                     "withdrawn", "returned")
#: Statuses that still await the Planner.
PENDING_STATUSES = ("open", "revised")
#: Rows kept per frame, pending and settled together; past it the oldest
#: SETTLED rows fall off. A pending proposal is never dropped by the cap.
PROPOSALS_CAP = 24
#: Each prose field of a proposal.
PROPOSAL_TEXT_CHARS = 600
#: How many times one proposal may be revised before it is returned.
PROPOSAL_REVISIONS_CAP = 2


def _text(value, limit=PROPOSAL_TEXT_CHARS):
    return " ".join(str(value or "").split())[:limit]


def _identity(kind, title):
    return "%s:%s" % (kind, _text(title, 200).casefold())


def _uid(identity, frame_id):
    material = "%s|%s" % (identity, frame_id if frame_id is not None else "")
    return "prop_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]


def normalize_proposal(entry, frame_id=None):
    entry = entry if isinstance(entry, dict) else {}
    kind = str(entry.get("kind") or "").strip().casefold()
    if kind not in PROPOSAL_KINDS:
        kind = "pressure"
    status = str(entry.get("status") or "open")
    if status not in PROPOSAL_STATUSES:
        status = "open"
    title = _text(entry.get("title"), 200)
    identity = str(entry.get("identity") or "") or _identity(kind, title)
    out = {
        "uid": str(entry.get("uid") or "") or _uid(identity, frame_id),
        "identity": identity,
        "kind": kind,
        "title": title,
        "wants_true": _text(entry.get("wants_true")),
        "why_now": _text(entry.get("why_now")),
        "must_not_contradict": _text(entry.get("must_not_contradict")),
        "scale": _text(entry.get("scale"), 60),
        "dial": int(entry.get("dial") or 0),
        "status": status,
        "revision": int(entry.get("revision") or 0),
        "filed_turn": int(entry.get("filed_turn") or 0),
        "judgements": [dict(j) for j in (entry.get("judgements") or [])
                       if isinstance(j, dict)][-6:],
        "package_uid": str(entry.get("package_uid") or ""),
        "sources": [str(s) for s in (entry.get("sources") or []) if str(s)][:8],
    }
    if entry.get("brief"):
        out["brief"] = _text(entry.get("brief"))
    return out


def _row(cid, frame_id):
    stored = wget_for_frame(cid, PROPOSALS_KEY, frame_id, {}) or {}
    if not isinstance(stored, dict):
        stored = {}
    rows = [normalize_proposal(p, frame_id) for p in (stored.get("proposals") or [])
            if isinstance(p, dict)]
    return {"proposals": rows,
            "last_pass_turn": stored.get("last_pass_turn"),
            "passes": int(stored.get("passes") or 0)}


def _save(cid, frame_id, row):
    rows = [normalize_proposal(p, frame_id) for p in row.get("proposals") or []]
    settled = [p for p in rows if p["status"] not in PENDING_STATUSES]
    while len(rows) > PROPOSALS_CAP and settled:
        oldest = settled.pop(0)
        rows = [p for p in rows if p is not oldest]
    row["proposals"] = rows
    wset_for_frame(cid, PROPOSALS_KEY, row, frame_id)
    return row


def proposals(cid, frame_id=None):
    return _row(cid, frame_id)["proposals"]


def pending_proposals(cid, frame_id=None):
    return [p for p in proposals(cid, frame_id) if p["status"] in PENDING_STATUSES]


def get_proposal(cid, frame_id, uid):
    for p in proposals(cid, frame_id):
        if p["uid"] == str(uid):
            return p
    return None


def file_proposal(cid, frame_id, *, kind, title, wants_true, why_now,
                  must_not_contradict="", scale="", dial=0, turn_idx=0,
                  brief=None, sources=()):
    """The Dramaturge's intent, as a row. Refuses an unknown kind, no
    title, or (for anything but `quiet`) nothing it wants true. The same
    kind and title while pending or accepted is the same proposal, returned
    as it stands -- a model re-emits a proposal on every step of a pass it
    is still working."""
    kind = str(kind or "").strip().casefold()
    if kind not in PROPOSAL_KINDS:
        raise ValueError("no such proposal kind %r; the kinds are %s"
                         % (kind, ", ".join(PROPOSAL_KINDS)))
    title = _text(title, 200)
    if not title:
        raise ValueError("a proposal has a title the panel can show")
    wants = _text(wants_true)
    if kind != "quiet" and not wants:
        raise ValueError("a proposal says what it wants to be true")
    row = _row(cid, frame_id)
    identity = _identity(kind, title)
    for existing in row["proposals"]:
        if existing["identity"] == identity and existing["status"] in (
                "open", "revised", "accepted"):
            return dict(existing)
    record = normalize_proposal({
        "kind": kind, "title": title, "wants_true": wants,
        "why_now": why_now, "must_not_contradict": must_not_contradict,
        "scale": scale, "dial": dial, "status": "open",
        "filed_turn": int(turn_idx or 0), "brief": brief,
        "sources": list(sources or ()), "filed_at": time.time(),
    }, frame_id)
    row["proposals"].append(record)
    _save(cid, frame_id, row)
    return record


def judge_proposal(cid, frame_id, uid, *, verdict, reason, contradiction="",
                   round_no=1, turn_idx=0, package_uid=""):
    """The Planner's verdict: `accept` (natural; being implemented),
    `refuse` (with the contradiction named), or `revise` (sent back to the
    Dramaturge). Returns the row, or None for an unknown uid."""
    verdict = str(verdict or "").strip().casefold()
    if verdict not in ("accept", "refuse", "revise"):
        raise ValueError("a verdict is accept, refuse or revise")
    row = _row(cid, frame_id)
    for p in row["proposals"]:
        if p["uid"] != str(uid):
            continue
        p["judgements"].append({
            "round": int(round_no), "verdict": verdict,
            "reason": _text(reason), "contradiction": _text(contradiction),
            "turn": int(turn_idx or 0)})
        p["judgements"] = p["judgements"][-6:]
        if verdict == "accept":
            p["status"] = "accepted"
            if package_uid:
                p["status"] = "implemented"
                p["package_uid"] = str(package_uid)
        elif verdict == "refuse":
            p["status"] = "refused"
        else:
            p["status"] = "revised" if p["revision"] < PROPOSAL_REVISIONS_CAP \
                else "returned"
        _save(cid, frame_id, row)
        return dict(p)
    return None


def revise_proposal(cid, frame_id, uid, *, wants_true, why_now,
                    must_not_contradict=None, turn_idx=0):
    """The Dramaturge answers a critique: the proposal, re-stated, goes back
    to the Planner as `open` with its revision counted. Past
    `PROPOSAL_REVISIONS_CAP` it is `returned` instead."""
    row = _row(cid, frame_id)
    for p in row["proposals"]:
        if p["uid"] != str(uid):
            continue
        if p["revision"] >= PROPOSAL_REVISIONS_CAP:
            p["status"] = "returned"
        else:
            p["revision"] += 1
            p["wants_true"] = _text(wants_true) or p["wants_true"]
            p["why_now"] = _text(why_now) or p["why_now"]
            if must_not_contradict is not None:
                p["must_not_contradict"] = _text(must_not_contradict)
            p["status"] = "open"
        _save(cid, frame_id, row)
        return dict(p)
    return None


def settle_proposal(cid, frame_id, uid, status, *, package_uid="", turn_idx=0):
    """Move a proposal to a terminal status: `implemented` (with its
    package), `withdrawn` or `returned`."""
    if status not in ("implemented", "withdrawn", "returned"):
        raise ValueError("a proposal settles as implemented, withdrawn or returned")
    row = _row(cid, frame_id)
    for p in row["proposals"]:
        if p["uid"] != str(uid):
            continue
        p["status"] = status
        if package_uid:
            p["package_uid"] = str(package_uid)
        p["judgements"].append({"round": 0, "verdict": status, "reason": "",
                                "contradiction": "", "turn": int(turn_idx or 0)})
        _save(cid, frame_id, row)
        return dict(p)
    return None


def record_pass(cid, frame_id, turn_idx):
    """One Dramaturge pass ran at this beat (whatever it proposed)."""
    row = _row(cid, frame_id)
    row["last_pass_turn"] = int(turn_idx or 0)
    row["passes"] = int(row.get("passes") or 0) + 1
    _save(cid, frame_id, row)
    return row


def last_pass_turn(cid, frame_id):
    value = _row(cid, frame_id).get("last_pass_turn")
    return int(value) if value is not None else None


def projection(proposal):
    """The spoiler-safe face of a proposal for the status row: its kind,
    its title (the Dramaturge's to keep spoiler-safe) and its state --
    never what it wants true."""
    return {"uid": proposal["uid"], "kind": "proposal",
            "label": "%s: %s" % (proposal["kind"], proposal["title"]),
            "state": proposal["status"]}
