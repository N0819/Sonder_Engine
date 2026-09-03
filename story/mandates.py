"""Mandates: what the player has allowed the Writers' Room to do, as state.

The conversation is intent; the grant is state (v2 § 2.2, § 6.4; plan § 6
item 6). The player tells the Story Planner in words what it may do -- how
big, to whom, how often -- and the Planner writes that back here as a typed
row: a sentence kept as the player said it, a scope, the CAPABILITIES it
permits in the room's own closed vocabulary, the LIMITS it carries, and when
it lapses. The panel shows the standing list and revokes; the Planner cites
a mandate when it declines or asks. Silence is never permission: a story
starts with no mandate at all, which is the zero-harm floor -- nothing the
room authors reaches the world until the player has said what it may.

WHERE A MANDATE BITES. A package the Planner authored (`provenance.created_by`
in `plot_packages.AGENT_AUTHORS`) validates and publishes only under active
mandates that together cover everything it does -- each operation kind is
its own capability, and the three authority flags a package may carry are
three more (`plot_packages.package_requirements`). A package the host
drafted by hand needs no grant: it is the host's world. Revocation therefore
prevents every later write, the queued fill job included (v2 § 14.1),
because the job publishes through the same seam.

The rows ride the frame-scoped `room_mandates` world key
(`room_conversation.ROOM_MANDATES_KEY`) in the shape that module reads, so
archive, checkpoint, branch and frame split carry them like the plans they
license.
"""

from __future__ import annotations

import hashlib
import time

from core.db import wset_for_frame

#: THE CLOSED VOCABULARY of what a grant can permit. The first nine are the
#: package operation kinds (`plot_packages.OPERATIONS`), one capability each;
#: then the three authority flags a package may carry; then the two kinds of
#: standing work the Planner does unasked once permitted.
MANDATE_CAPABILITIES = (
    "plan_rooms", "plan_entity", "post_artifact", "schedule_event",
    "file_lore", "answer_need", "close_need", "request_location",
    "presimulate",
    "create_people", "author_prehistory", "schedule_harm",
    # Reach the web (`story/room_research.py`): a query leaves the machine,
    # so the player grants it in so many words.
    "research",
    # Answer open planning needs and keep the prepared frontier out of band
    # (the fill job), within `limits.fills_per_hour`.
    "identity_fills",
    # Author a SEALED package -- work the player will not read until revealed.
    "surprise",
)

#: The limits a grant may carry, each a number. `fills_per_hour` is read by
#: the fill job; `calls_per_reply` and `calls_per_hour` are the SPEND the
#: room may make (the loop's own ceilings are safety only, 2026-09-03:
#: "the bounds may potentially be too strict"); `surprise` is the
#: Dramaturge's creativity dial and `beats_per_proposal` its pacing; the
#: rest are ceilings the Planner is told to honour and cites when it
#: declines.
MANDATE_LIMITS = ("fills_per_hour", "calls_per_reply", "calls_per_hour",
                  "surprise", "beats_per_proposal",
                  "packages", "rooms", "people", "hours", "turns")

#: SPEND. Tool calls the room may make in one reply and in one story hour,
#: when a grant names no number, and the engine's ceilings a grant may not
#: raise past. The loop's own step and call counts are safety ceilings an
#: order of magnitude above these; a mandate's number is the real stop.
CALLS_PER_REPLY = 60
CALLS_PER_REPLY_CAP = 200
CALLS_PER_STORY_HOUR = 240
CALLS_PER_STORY_HOUR_CAP = 1200

#: THE CREATIVITY DIAL (`surprise`): 0 holds to the target the player
#: stated and proposes only what serves it; 4 is wildly inventive, a turn
#: nobody asked for. A grant that names the dial without a number gets the
#: middle. The Dramaturge runs at all only under a grant that carries the
#: dial: a story begins with it unset, and it proposes nothing.
SURPRISE_DEFAULT = 2
SURPRISE_MAX = 4
#: PACING: the Dramaturge is asked at most once every this many beats,
#: when no grant names another number; it may not be asked more often than
#: every beat.
BEATS_PER_PROPOSAL = 6
BEATS_PER_PROPOSAL_MIN = 1

#: Rows kept per frame, active and lapsed together; past it the oldest
#: lapsed rows fall off. An active mandate is never dropped by the cap.
MANDATES_CAP = 32
#: The sentence as the player said it, and the scope, as `normalize_mandate`
#: caps them.
MANDATE_TEXT_CHARS = 600
MANDATE_SCOPE_CHARS = 200
DEFAULT_SCOPE = "this story"

#: The identity-fill line. A grant that names no `fills_per_hour` gets the
#: default; a grant may lower it or raise it up to the engine's ceiling,
#: never above.
FILLS_PER_STORY_HOUR = 4
FILLS_PER_STORY_HOUR_CAP = 12


def _text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _uid(cid, text, scope, granted_turn, index):
    material = "%s|%s|%s|%s|%s" % (cid, text.casefold(), scope.casefold(),
                                   granted_turn, index)
    return "mandate_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]


def _key():
    from story.room_conversation import ROOM_MANDATES_KEY
    return ROOM_MANDATES_KEY


def _load(cid, frame_id):
    from story.room_conversation import mandates
    return mandates(cid, frame_id)


def _save(cid, frame_id, rows):
    from story.room_conversation import normalize_mandate
    rows = [normalize_mandate(r) for r in rows]
    lapsed = [r for r in rows if r["status"] != "active"]
    while len(rows) > MANDATES_CAP and lapsed:
        oldest = lapsed.pop(0)
        rows = [r for r in rows if r is not oldest]
    wset_for_frame(cid, _key(), rows, frame_id)
    return rows


def _turn_now(cid):
    from story.room_conversation import current_turn_idx
    return current_turn_idx(cid)


def grant_mandate(cid, frame_id, *, text, capabilities, scope=DEFAULT_SCOPE,
                  limits=None, expires_turn=None, turn_idx=None):
    """Record one grant the player made in words. Refuses an empty sentence,
    no capability, or a capability outside `MANDATE_CAPABILITIES` -- the
    vocabulary is closed so a grant means exactly one thing to the checks
    that read it. Returns the stored row."""
    text = _text(text, MANDATE_TEXT_CHARS)
    if not text:
        raise ValueError("a mandate keeps the sentence the player granted")
    wanted = []
    for cap in capabilities or ():
        cap = str(cap or "").strip()
        if cap not in MANDATE_CAPABILITIES:
            raise ValueError("no such room capability %r; the capabilities are %s"
                             % (cap, ", ".join(MANDATE_CAPABILITIES)))
        if cap not in wanted:
            wanted.append(cap)
    if not wanted:
        raise ValueError("a mandate permits at least one capability")
    clean_limits = {}
    for key, value in (limits or {}).items() if isinstance(limits, dict) else ():
        if str(key) not in MANDATE_LIMITS:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number < 0:
            continue
        clean_limits[str(key)] = int(number) if number == int(number) else number
    if "fills_per_hour" in clean_limits:
        clean_limits["fills_per_hour"] = min(
            int(clean_limits["fills_per_hour"]), FILLS_PER_STORY_HOUR_CAP)
    if "calls_per_reply" in clean_limits:
        clean_limits["calls_per_reply"] = min(
            int(clean_limits["calls_per_reply"]), CALLS_PER_REPLY_CAP)
    if "calls_per_hour" in clean_limits:
        clean_limits["calls_per_hour"] = min(
            int(clean_limits["calls_per_hour"]), CALLS_PER_STORY_HOUR_CAP)
    if "surprise" in clean_limits:
        clean_limits["surprise"] = max(0, min(int(clean_limits["surprise"]),
                                              SURPRISE_MAX))
    if "beats_per_proposal" in clean_limits:
        clean_limits["beats_per_proposal"] = max(
            BEATS_PER_PROPOSAL_MIN, int(clean_limits["beats_per_proposal"]))
    granted_turn = int(_turn_now(cid) if turn_idx is None else turn_idx)
    rows = _load(cid, frame_id)
    # THE SAME SENTENCE IS ONE GRANT. A model re-emits a grant on every step
    # of a reply it is still working (measured: two rows for one sentence,
    # chat 111, 2026-09-03); the store, not the loop, is where a grant is
    # made idempotent, so every writer gets the same answer.
    clean_scope = _text(scope, MANDATE_SCOPE_CHARS) or DEFAULT_SCOPE
    for existing in rows:
        if existing["status"] == "active" \
                and existing["text"].casefold() == text.casefold() \
                and existing["scope"].casefold() == clean_scope.casefold():
            return dict(existing)
    row = {
        "uid": _uid(cid, text, _text(scope, MANDATE_SCOPE_CHARS) or DEFAULT_SCOPE,
                    granted_turn, len(rows)),
        "text": text,
        "scope": _text(scope, MANDATE_SCOPE_CHARS) or DEFAULT_SCOPE,
        "capabilities": wanted,
        "limits": clean_limits,
        "granted_turn": granted_turn,
        "expires_turn": int(expires_turn) if expires_turn is not None else None,
        "status": "active",
        "revoked_turn": None,
        "granted_at": time.time(),
    }
    rows.append(row)
    _save(cid, frame_id, rows)
    return dict(row)


def expire_mandates(cid, frame_id, turn_idx=None):
    """Active rows whose `expires_turn` has passed become `expired`.
    Returns the uids that lapsed."""
    turn = int(_turn_now(cid) if turn_idx is None else turn_idx)
    rows = _load(cid, frame_id)
    lapsed = []
    for row in rows:
        if row["status"] == "active" and row.get("expires_turn") is not None \
                and int(row["expires_turn"]) < turn:
            row["status"] = "expired"
            lapsed.append(row["uid"])
    if lapsed:
        _save(cid, frame_id, rows)
    return lapsed


def active_mandates(cid, frame_id, turn_idx=None):
    expire_mandates(cid, frame_id, turn_idx)
    return [r for r in _load(cid, frame_id) if r["status"] == "active"]


def coverage(cid, frame_id, needed, *, turn_idx=None):
    """Whether the standing active mandates together permit ``needed``
    (a set of capabilities). Returns ``{"ok", "cited": [uids], "missing":
    [capabilities]}``: the mandates that contributed, and what no mandate
    covers. A need of nothing is covered by nothing."""
    needed = [str(c) for c in dict.fromkeys(needed or ())]
    if not needed:
        return {"ok": True, "cited": [], "missing": []}
    cited, covered = [], set()
    for row in active_mandates(cid, frame_id, turn_idx):
        hit = [c for c in needed if c in row["capabilities"] and c not in covered]
        if hit:
            cited.append(row["uid"])
            covered.update(hit)
    missing = [c for c in needed if c not in covered]
    return {"ok": not missing, "cited": cited, "missing": missing}


def citation(cid, frame_id, uids):
    """The mandates by uid, as the Planner cites them: uid and sentence."""
    by_uid = {r["uid"]: r for r in _load(cid, frame_id)}
    out = []
    for uid in uids or ():
        row = by_uid.get(str(uid))
        if row:
            out.append("%s (%s: %r)" % (row["uid"], row["status"], row["text"]))
    return "; ".join(out)


def fill_limit(cid, frame_id, turn_idx=None):
    """The identity-fill line: fills allowed per story hour under the
    standing grants, or None when no active mandate permits fills at all.
    The most permissive grant wins, under the engine's ceiling."""
    limit = None
    for row in active_mandates(cid, frame_id, turn_idx):
        if "identity_fills" not in row["capabilities"]:
            continue
        own = row["limits"].get("fills_per_hour")
        own = FILLS_PER_STORY_HOUR if own is None else int(own)
        own = min(own, FILLS_PER_STORY_HOUR_CAP)
        limit = own if limit is None else max(limit, own)
    return limit


def _most_permissive(cid, frame_id, key, default, cap, turn_idx=None,
                     *, requires=None):
    """A numeric limit under the standing grants: the most permissive row
    wins, under the engine's ceiling; a row naming no number contributes the
    default. ``requires`` narrows to rows carrying that capability. None
    when no row qualifies."""
    limit = None
    for row in active_mandates(cid, frame_id, turn_idx):
        if requires and requires not in row["capabilities"]:
            continue
        own = row["limits"].get(key)
        own = default if own is None else int(own)
        own = min(own, cap)
        limit = own if limit is None else max(limit, own)
    return limit


def spend_limits(cid, frame_id, turn_idx=None):
    """What the room may spend: tool calls per reply and per story hour.
    Every active mandate carries spend, because every grant is a licence to
    work; with no active mandate the defaults stand (the room can still
    answer a question), so this never returns None."""
    per_reply = _most_permissive(cid, frame_id, "calls_per_reply",
                                 CALLS_PER_REPLY, CALLS_PER_REPLY_CAP, turn_idx)
    per_hour = _most_permissive(cid, frame_id, "calls_per_hour",
                                CALLS_PER_STORY_HOUR, CALLS_PER_STORY_HOUR_CAP,
                                turn_idx)
    return {"calls_per_reply": CALLS_PER_REPLY if per_reply is None else per_reply,
            "calls_per_hour": CALLS_PER_STORY_HOUR if per_hour is None else per_hour}


def spend_citation(cid, frame_id, key, turn_idx=None):
    """The active mandate that set ``key`` most permissively, for the
    Planner to cite when spend stops it; '' when the default is in force."""
    best, best_uid = None, ""
    for row in active_mandates(cid, frame_id, turn_idx):
        own = row["limits"].get(key)
        if own is None:
            continue
        if best is None or int(own) > best:
            best, best_uid = int(own), row["uid"]
    return best_uid


def surprise_dial(cid, frame_id, turn_idx=None):
    """The Dramaturge's creativity dial under the standing grants, or None
    when no active mandate carries it -- in which case the Dramaturge does
    not run. The dial is the grant: a player who names how much they want
    to be surprised has licensed the room to propose."""
    dial = None
    for row in active_mandates(cid, frame_id, turn_idx):
        own = row["limits"].get("surprise")
        if own is None:
            continue
        own = max(0, min(int(own), SURPRISE_MAX))
        dial = own if dial is None else max(dial, own)
    return dial


def beats_per_proposal(cid, frame_id, turn_idx=None):
    """The pacing budget: how many beats pass between Dramaturge passes.
    Read only from rows that carry the dial; the most frequent wins."""
    beats = None
    for row in active_mandates(cid, frame_id, turn_idx):
        if row["limits"].get("surprise") is None:
            continue
        own = row["limits"].get("beats_per_proposal")
        own = BEATS_PER_PROPOSAL if own is None else max(
            BEATS_PER_PROPOSAL_MIN, int(own))
        beats = own if beats is None else min(beats, own)
    return beats


def revoked_since(cid, frame_id, turn_idx):
    """Mandates revoked or expired at or after ``turn_idx`` -- what the
    Planner is shown so it honours a withdrawal on its next reply."""
    out = []
    for row in _load(cid, frame_id):
        if row["status"] == "revoked" and (row.get("revoked_turn") or 0) >= int(turn_idx):
            out.append(row)
        elif row["status"] == "expired" and (row.get("expires_turn") or 0) >= int(turn_idx) - 1:
            out.append(row)
    return out
