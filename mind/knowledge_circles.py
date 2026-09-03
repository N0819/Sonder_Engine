"""Knowledge circles a character joins or leaves DURING the story.

A lore entry's compartment (`lore_entries.circles`, inherited from the
book's `default_circles`) says WHO may know it, and a character's sheet says
which compartments they are inside (`knowledge.circles`). The sheet is
authored once, so until this module a character initiated into an order at
turn sixty knew its rites only if somebody edited the card -- and a card
edit is not an event inside the story (CLAUDE.md: authoring is not
retraction, and not admission either).

Membership is STORY STATE here: one frame-scoped world row, keyed by the
character's stable identity, holding every circle the story granted or
withdrew and the turn it happened. `effective_circles` overlays it on the
sheet for the knowledge gate (`agents/character` → `knowledge_for_character`).
The sheet still says where a character began; the story says where they
have gone since.

THE SEAM IS ONE FUNCTION PAIR, `join_circle` / `leave_circle`, and it is a
CHANNEL in the firewall's sense: membership is how a mind comes to know a
compartment's lore by standing rather than by living, so the act that grants
it must be an act in the world -- an initiation the Director resolved, an
enrolment a package published, a promotion into an institution that declares
a circle. Nothing here decides that an act happened; it records that one
did. A world key rather than `chat_chars.state`, for three reasons: the gate
reads a SHEET, not a chat_chars row; a world row rides archive, checkpoint,
branch and frame split with no handling of its own; and a body promoted from
a charter has a circle before it has a chat_chars row.
"""

from __future__ import annotations

from core.db import wget_for_frame, wset_for_frame

#: The world key (frame-scoped; core/db.FRAME_SCOPED_WORLD_KEYS).
CIRCLES_KEY = "knowledge_circles"

#: Circles one character may hold at once through the story. Past it the
#: OLDEST still-held membership is left behind: a mind inside forty
#: compartments is a sheet that should have been authored, not a story.
CIRCLES_PER_CHARACTER_CAP = 24

#: How a grant is spelled: a body walked in, a body was let in, a package
#: said so. Recorded for an audit; the gate does not read it.
VIA_KINDS = ("initiation", "enrolment", "package", "author")


def identity_key(sheet):
    """The stable key a sheet's identity answers to: its uid when it has one,
    else its name, casefolded. Neither may be rekeyed by a card edit."""
    identity = (sheet or {}).get("identity") if isinstance(sheet, dict) else {}
    identity = identity if isinstance(identity, dict) else {}
    uid = str(identity.get("uid") or "").strip()
    if uid:
        return uid
    from story.character_schema import character_name
    return str(character_name(sheet or {}) or "").strip().casefold()


def _circle(name):
    return " ".join(str(name or "").split()).casefold()


def story_circles(cid, key, frame_id=None):
    """Every membership row the story holds for ``key``, oldest first:
    ``{circle, since_turn, via, status: member|left, left_turn}``."""
    stored = wget_for_frame(cid, CIRCLES_KEY, frame_id, {}) or {}
    rows = stored.get(str(key)) if isinstance(stored, dict) else None
    return [dict(r) for r in (rows or []) if isinstance(r, dict) and r.get("circle")]


def _save(cid, key, rows, frame_id):
    stored = wget_for_frame(cid, CIRCLES_KEY, frame_id, {}) or {}
    if not isinstance(stored, dict):
        stored = {}
    stored[str(key)] = rows
    wset_for_frame(cid, CIRCLES_KEY, stored, frame_id)


def join_circle(cid, key, circle, *, turn_idx, via="initiation", frame_id=None):
    """Record that the character ``key`` is now inside ``circle``. Idempotent
    for a circle already held; a circle left earlier is re-entered as a new
    row (the leaving stays on the record). Returns the row."""
    circle = _circle(circle)
    if not circle:
        raise ValueError("a circle has a name")
    via = via if via in VIA_KINDS else "author"
    rows = story_circles(cid, key, frame_id)
    for row in rows:
        if row["circle"] == circle and row.get("status", "member") == "member":
            return row
    row = {"circle": circle, "since_turn": int(turn_idx or 0), "via": via,
           "status": "member", "left_turn": None}
    rows.append(row)
    held = [r for r in rows if r.get("status", "member") == "member"]
    while len(held) > CIRCLES_PER_CHARACTER_CAP:
        oldest = held.pop(0)
        oldest["status"] = "left"
        oldest["left_turn"] = int(turn_idx or 0)
    _save(cid, key, rows, frame_id)
    return row


def leave_circle(cid, key, circle, *, turn_idx, frame_id=None):
    """Record that ``key`` is no longer inside ``circle``. Returns True when a
    held membership ended; False when none was held (including one the sheet
    authored -- the sheet is not the story's to edit, see `effective_circles`)."""
    circle = _circle(circle)
    rows = story_circles(cid, key, frame_id)
    changed = False
    for row in rows:
        if row["circle"] == circle and row.get("status", "member") == "member":
            row["status"] = "left"
            row["left_turn"] = int(turn_idx or 0)
            changed = True
    if changed:
        _save(cid, key, rows, frame_id)
    return changed


def effective_circles(sheet_circles, cid, key, frame_id=None):
    """The compartments a mind is inside NOW: the sheet's, plus every circle
    the story granted and has not withdrawn. A story may add to a sheet and
    may withdraw what it added; it may not strip a sheet-authored circle,
    because that is the card's statement of who the character has always
    been and its retraction is a card edit."""
    out = [str(c).strip() for c in (sheet_circles or ()) if str(c or "").strip()]
    seen = {_circle(c) for c in out}
    for row in story_circles(cid, key, frame_id):
        if row.get("status", "member") != "member":
            continue
        if row["circle"] not in seen:
            out.append(row["circle"])
            seen.add(row["circle"])
    return out
