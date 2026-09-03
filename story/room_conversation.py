"""The Writers' Room conversation, its Planner seam, and the mandate and status rows the panel shows beside it.

THREE THINGS LIVE HERE, and the split between them is the point.

* The CONVERSATION (`room_messages`): one thread per story and era, the
  player talking with the Story Planner and, through it, the Dramaturge.
  It is AUTHOR-SIDE state, not story state (v2 § 11.2, "conversation is not
  authority"): it is carried by a branch and by a portable archive, and it
  is deliberately NOT in the turn checkpoint, so rerolling a beat does not
  unsay what the player told the room after it.
* The MANDATES (`ROOM_MANDATES_KEY`, frame-scoped world row): the standing
  grants the player has given the room in words, written back as typed
  state by the Planner (v2 § 6.4, § 2.2 "conversation is intent; typed
  operations are state"). The panel reads and revokes them; nothing here
  grants one -- a grant is the Planner's to write, and silence is never
  permission.
* The STATUS (`ROOM_STATUS_KEY`, frame-scoped world row): the spoiler-safe
  projection of what the room has in motion -- what is moving, never what
  it is (v2 § 5.3, § 7) -- and the questions the room is waiting on.

The PLANNER SEAM. `PLANNER` is the one callable the reply route invokes:
``PLANNER(cid, frame_id, text) -> {"reply": str, "dramaturge": str | None,
"mandates": [...], "status": {...}}``. The Story Planner agent (Phase B of
`docs/design/DESIGN_WRITERS_ROOM_PLAN.md`) seats itself by assigning it, or
by `seat_planner(fn)`. Until then `unseated_planner` answers: it keeps the
player's note and says, in one line, that nobody is seated -- an honest
placeholder, never a pretend Planner. The panel can tell the two apart
(`planner_seated()`), so it never dresses the placeholder as an agent.

This module lives under `story/` because the conversation is authoring
material like an authored event or a greeting: it is about the story,
consulted by an author-side agent, and it is neither a turn commit
(`persist/`) nor a mind (`mind/`). The routes in `web/room_routes.py` are
transport over it and hold no policy.
"""

from __future__ import annotations

import time

from core.db import q, qtx, transaction, wget_for_frame, wset_for_frame

#: Who can speak in the thread. `player` is the host at the keyboard;
#: `planner` and `dramaturge` are the two agents; `room` is the engine's own
#: notice (the unseated line, a revocation receipt) -- a line nobody wrote.
ROLES = ("player", "planner", "dramaturge", "room")

#: One message's ceiling. A brief to the room is a few paragraphs at most;
#: anything past this is a pasted document, and the room reads documents
#: through the lore it is handed, not through its chat box.
ROOM_MESSAGE_CHARS = 4000

#: How many messages one story-and-era thread keeps. Past it the OLDEST fall
#: off at the next write: the thread is a working conversation, not a record
#: of authority (v2 § 11.2), and a proposal re-anchors on current state, not
#: on what was said two hundred messages ago.
ROOM_HISTORY_KEPT = 200

#: How many messages one read returns, newest last. The panel shows the tail
#: and asks for more by `before`.
ROOM_PAGE = 60

#: Frame-scoped world keys (core/db.FRAME_SCOPED_WORLD_KEYS). Both are
#: WRITTEN by the Planner and READ here; `revoke_mandate` is the one write
#: this module makes to either, because revocation is the player's act.
ROOM_MANDATES_KEY = "room_mandates"
ROOM_STATUS_KEY = "room_status"

#: The shape of one mandate, as the Planner writes it and the panel shows it:
#:   {"uid": str, "text": str (the sentence granted, as the player said it),
#:    "scope": str (where it applies: a place, a book, "this story"),
#:    "capabilities": [str] (what it permits, in the room's own op vocabulary),
#:    "limits": {str: number | str} (cost/size ceilings the grant carries),
#:    "granted_turn": int, "expires_turn": int | None,
#:    "status": "active" | "revoked" | "expired",
#:    "revoked_turn": int | None}
MANDATE_STATUSES = ("active", "revoked", "expired")

#: The shape of the status row, as the Planner writes it:
#:   {"line": str (one spoiler-safe sentence, what is in motion),
#:    "in_motion": [{"uid": str, "kind": str, "label": str,
#:                   "state": str}] (labels are spoiler-safe by contract:
#:                   the Planner writes "a matter at the harbour", never
#:                   the truth behind it),
#:    "questions": [{"uid": str, "text": str}] (what the room is asking),
#:    "updated_turn": int}

#: The one line the placeholder says. English is the message id: the panel
#: renders every text node through the UI catalog (`el()` -> `t()`), so this
#: reaches a Japanese reader in Japanese as long as the same literal is in
#: the catalog -- `static/js/writers_room.js` carries it for the harvester,
#: and `tests/test_room_routes.py` holds the two spellings together.
UNSEATED_LINE = ("The Story Planner is not seated yet. Your note is kept for "
                 "it; nothing has been planned.")


def _clean(text, limit=ROOM_MESSAGE_CHARS):
    """A message: trimmed and capped, its paragraphs kept."""
    return str(text or "").strip()[:limit]


def _line(text, limit):
    """A label or a sentence of state: one line, whitespace collapsed."""
    return " ".join(str(text or "").split())[:limit]


def frame_belongs(cid, frame_id):
    """True for the present (None) or a frame row of this chat."""
    if frame_id is None:
        return True
    row = q("SELECT id FROM frames WHERE id=? AND chat_id=?",
            (int(frame_id), int(cid)), one=True)
    return row is not None


def _row(r):
    return {"id": r["id"], "role": r["role"], "text": r["text"],
            "turn_idx": r["turn_idx"], "frame_id": r["frame_id"],
            "created": r["created"]}


def _frame_clause(frame_id):
    if frame_id is None:
        return "frame_id IS NULL", ()
    return "frame_id=?", (int(frame_id),)


def messages(cid, frame_id=None, *, before=None, limit=ROOM_PAGE):
    """The thread's tail, oldest first; ``before`` pages back by id."""
    clause, args = _frame_clause(frame_id)
    limit = max(1, min(int(limit or ROOM_PAGE), ROOM_PAGE))
    sql = f"SELECT * FROM room_messages WHERE chat_id=? AND {clause}"
    params = [int(cid), *args]
    if before is not None:
        sql += " AND id<?"
        params.append(int(before))
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = [_row(r) for r in q(sql, tuple(params))]
    rows.reverse()
    return rows


def add_message(cid, frame_id, role, text, *, turn_idx=0):
    """Append one line and prune the thread to `ROOM_HISTORY_KEPT`.
    Returns the stored row. Refuses an unknown role and an empty line."""
    if role not in ROLES:
        raise ValueError("unknown room role %r" % (role,))
    text = _clean(text)
    if not text:
        raise ValueError("an empty line is not a message")
    clause, args = _frame_clause(frame_id)
    with transaction():
        mid = qtx(
            "INSERT INTO room_messages(chat_id,frame_id,turn_idx,role,text,created) "
            "VALUES(?,?,?,?,?,?)",
            (int(cid), None if frame_id is None else int(frame_id),
             int(turn_idx or 0), role, text, time.time()))
        stale = q(
            f"SELECT id FROM room_messages WHERE chat_id=? AND {clause} "
            "ORDER BY id DESC LIMIT -1 OFFSET ?",
            (int(cid), *args, ROOM_HISTORY_KEPT))
        for s in stale:
            qtx("DELETE FROM room_messages WHERE id=?", (s["id"],))
    row = q("SELECT * FROM room_messages WHERE id=?", (mid,), one=True)
    return _row(row)


def current_turn_idx(cid):
    row = q("SELECT MAX(idx) AS m FROM turns WHERE chat_id=?", (int(cid),), one=True)
    return int(row["m"] or 0) if row and row["m"] is not None else 0


# ---------------------------------------------------------------------------
# Mandates and status: read here, written by the Planner
# ---------------------------------------------------------------------------

def normalize_mandate(entry):
    entry = entry if isinstance(entry, dict) else {}
    status = str(entry.get("status") or "active")
    if status not in MANDATE_STATUSES:
        status = "active"
    limits = entry.get("limits") if isinstance(entry.get("limits"), dict) else {}
    return {
        "uid": str(entry.get("uid") or ""),
        "text": _line(entry.get("text"), 600),
        "scope": _line(entry.get("scope"), 200),
        "capabilities": [str(c) for c in (entry.get("capabilities") or [])
                         if str(c or "").strip()][:24],
        "limits": {str(k): v for k, v in limits.items()
                   if isinstance(v, (int, float, str))},
        "granted_turn": int(entry.get("granted_turn") or 0),
        "expires_turn": (int(entry["expires_turn"])
                         if entry.get("expires_turn") is not None else None),
        "status": status,
        "revoked_turn": (int(entry["revoked_turn"])
                         if entry.get("revoked_turn") is not None else None),
    }


def mandates(cid, frame_id=None):
    stored = wget_for_frame(cid, ROOM_MANDATES_KEY, frame_id, []) or []
    out = []
    for entry in stored if isinstance(stored, list) else []:
        m = normalize_mandate(entry)
        if m["uid"] and m["text"]:
            out.append(m)
    return out


def revoke_mandate(cid, uid, frame_id=None, *, turn_idx=None):
    """The player withdraws a grant. Returns the mandate as it now stands,
    or None for a uid the ledger does not hold. Revoking a revoked or
    expired mandate is a no-op that still returns it."""
    stored = mandates(cid, frame_id)
    found = None
    for m in stored:
        if m["uid"] == str(uid):
            found = m
            if m["status"] == "active":
                m["status"] = "revoked"
                m["revoked_turn"] = int(
                    current_turn_idx(cid) if turn_idx is None else turn_idx)
    if found is None:
        return None
    wset_for_frame(cid, ROOM_MANDATES_KEY, stored, frame_id)
    return found


def status(cid, frame_id=None):
    stored = wget_for_frame(cid, ROOM_STATUS_KEY, frame_id, {}) or {}
    stored = stored if isinstance(stored, dict) else {}
    in_motion = []
    for item in stored.get("in_motion") or []:
        if not isinstance(item, dict):
            continue
        in_motion.append({
            "uid": str(item.get("uid") or ""),
            "kind": _line(item.get("kind"), 60),
            "label": _line(item.get("label"), 200),
            "state": _line(item.get("state"), 60),
        })
    questions = []
    for qn in stored.get("questions") or []:
        if isinstance(qn, dict) and str(qn.get("text") or "").strip():
            questions.append({"uid": str(qn.get("uid") or ""),
                              "text": _line(qn.get("text"), 600)})
    return {
        "line": _line(stored.get("line"), 400),
        "in_motion": in_motion,
        "questions": questions,
        "updated_turn": int(stored.get("updated_turn") or 0),
    }


# ---------------------------------------------------------------------------
# The Planner seam
# ---------------------------------------------------------------------------

def unseated_planner(cid, frame_id, text):
    """The placeholder. It plans nothing, grants nothing, and says so."""
    return {"reply": UNSEATED_LINE, "dramaturge": None,
            "mandates": mandates(cid, frame_id), "status": status(cid, frame_id)}


PLANNER = unseated_planner


def seat_planner(fn):
    """Install the Story Planner. ``fn(cid, frame_id, text)`` returns the
    reply envelope; passing None unseats it."""
    global PLANNER
    PLANNER = fn or unseated_planner
    return PLANNER


def planner_seated():
    return PLANNER is not unseated_planner


def converse(cid, frame_id, text):
    """Store the player's line, ask the seated Planner (or the placeholder),
    store what came back, and return the whole exchange. A Planner that
    raises leaves the player's line stored and the failure reported as a
    `room` notice rather than a 500: the note was kept, and the panel says
    what happened."""
    text = _clean(text)
    if not text:
        raise ValueError("an empty line is not a message")
    turn_idx = current_turn_idx(cid)
    player = add_message(cid, frame_id, "player", text, turn_idx=turn_idx)
    replies = []
    try:
        answer = PLANNER(cid, frame_id, text) or {}
    except Exception as exc:  # the seam is a boundary; report, never 500
        answer = {"reply": None, "error": str(exc)[:400]}
    if answer.get("reply"):
        role = "room" if not planner_seated() else "planner"
        replies.append(add_message(cid, frame_id, role, answer["reply"],
                                   turn_idx=turn_idx))
    if answer.get("dramaturge"):
        replies.append(add_message(cid, frame_id, "dramaturge",
                                   answer["dramaturge"], turn_idx=turn_idx))
    return {
        "message": player,
        "replies": replies,
        "error": answer.get("error"),
        "mandates": (answer.get("mandates")
                     if isinstance(answer.get("mandates"), list)
                     else mandates(cid, frame_id)),
        "status": (answer.get("status")
                   if isinstance(answer.get("status"), dict)
                   else status(cid, frame_id)),
        "seated": planner_seated(),
    }


# ---------------------------------------------------------------------------
# Carriage: branch and archive
# ---------------------------------------------------------------------------

def dump_room_messages(cid):
    """Every line of every era, for the portable archive."""
    return [_row(r) for r in q(
        "SELECT * FROM room_messages WHERE chat_id=? ORDER BY id", (int(cid),))]


def restore_room_messages(cid, rows, *, frame_idmap=None, up_to_turn=None):
    """Insert carried lines into chat ``cid``. A line whose frame did not
    come across is DROPPED (its era does not exist here); a line after
    ``up_to_turn`` is dropped too (a branch inherits the conversation up to
    its point, not what was said after it). Inside the caller's
    transaction. Returns the number inserted."""
    frame_idmap = frame_idmap or {}
    n = 0
    for r in rows or []:
        if not isinstance(r, dict) or r.get("role") not in ROLES:
            continue
        text = _clean(r.get("text"))
        if not text:
            continue
        old_frame = r.get("frame_id")
        if old_frame is None:
            new_frame = None
        else:
            new_frame = frame_idmap.get(old_frame)
            if new_frame is None:
                continue
        turn_idx = int(r.get("turn_idx") or 0)
        if up_to_turn is not None and turn_idx > int(up_to_turn):
            continue
        qtx("INSERT INTO room_messages(chat_id,frame_id,turn_idx,role,text,created) "
            "VALUES(?,?,?,?,?,?)",
            (int(cid), new_frame, turn_idx, r["role"], text,
             float(r.get("created") or time.time())))
        n += 1
    return n
