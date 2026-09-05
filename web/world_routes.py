"""Typed HTTP boundary for the World Browser: the room index and the
per-room slice, read through `story/room_slice.py` -- the ONE reader the
Writers' Room's `inspect_rooms`, the frontier and now the browser all share,
so a host and the Planner cannot be shown two different worlds.

Transport only, and READ-ONLY: the two routes here shape `room_index` and
`room_slice` for display and write nothing. The write paths stay where they
are -- `web/app.py`'s `world_put` (the raw world editor), `attire_put` (the
attire ledger, re-derived on the way in) and `chat_char_position_put` (a
cast member's room) -- because each of those carries a rule the browser must
not duplicate (registry reconciliation, three-representation re-derivation,
room-id validation against the scene).

Routes (under ``/api/chats/{cid}/rooms``; ``frame_id`` absent or null is the
present, else a frame row of this chat, 404 otherwise -- the same contract
`app._era` gives the attire route):

* ``GET  ?frame_id=`` -> ``{frame_id, location, groups}`` where ``groups`` is
  ``{cast, reachable, unreachable, retired}``, each a list of index rows in
  the index's own order (hops, then id). ``cast`` is every room a cast
  member stands in (hops 0); ``reachable`` every other room the walk from
  the cast reaches, live or planned; ``unreachable`` every unretired room it
  does not; ``retired`` the spent ids. Every row is the index row plus
  ``holder_name`` (the entity's display name when the room is the inside of
  a body), ``holder_room`` (where that body stands, for nesting) and
  ``occupants`` (the names `positions` place here).
* ``GET  /{room_id}?frame_id=`` -> the slice plus ``holder_name``; 404 when
  no room of that id is known to the story.

Host-only by construction: nothing here is in `GUEST_ALLOWED_API_PATHS`.
The slice is author knowledge -- planned stubs, package operations, another
body's whole attire ledger -- and reaches no mind (`story/room_tools.py`).
"""

from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, HTTPException

from core import db
from core.db import q
from story import room_slice as rooms

router = APIRouter(prefix="/api/chats/{cid}/rooms", tags=["world-browser"])

#: The display groups, in the order the browser lists them.
GROUPS = ("cast", "reachable", "unreachable", "retired")


@contextmanager
def _era(cid: int, frame_id):
    """Scope the scene read to one era, as `app._era` does for the attire
    route: validate that the frame is this chat's, then set the ambient
    `active_frame_id` so `get_scene` lands on that era's blob."""
    if frame_id is not None:
        row = q("SELECT id FROM frames WHERE id=? AND chat_id=?",
                (int(frame_id), int(cid)), one=True)
        if row is None:
            raise HTTPException(404, f"Frame {frame_id} not found")
    token = db.active_frame_id.set(
        int(frame_id) if frame_id is not None else None)
    try:
        yield
    finally:
        db.active_frame_id.reset(token)


def _chat_or_404(cid: int):
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")
    return dict(chat)


def _holder_name(scene, holder):
    """The display name of the body a room is inside of -- the scene
    entity's `name` when it has one, else the id the room recorded."""
    if not holder:
        return None
    entity = (scene.get("entities") or {}).get(str(holder))
    if isinstance(entity, dict) and str(entity.get("name") or "").strip():
        return str(entity["name"]).strip()
    return str(holder)


def group_rows(index_rows, scene):
    """Sort index rows into the four display groups, each keeping the
    index's order, and decorate every row for display. Pure over its inputs
    so the grouping is testable without a request."""
    # The names beside a cast room are BODIES, by the rule `cast_rooms` counts
    # the cast with: a position row keyed by a scene entity of an inanimate
    # kind places a thing (the slice lists it under `things`), and a row with
    # no entity record behind it, or an animate one, is a body.
    from llm.schemas import _ANIMATE_ENTITY_KINDS
    entities = scene.get("entities") or {}
    occupants = {}
    for who, room in (scene.get("positions") or {}).items():
        if not str(room or ""):
            continue
        ent = entities.get(str(who))
        kind = (str(ent.get("kind") or "").strip().casefold()
                if isinstance(ent, dict) else "")
        if kind and kind not in _ANIMATE_ENTITY_KINDS:
            continue
        occupants.setdefault(str(room), []).append(str(who))
    groups = {key: [] for key in GROUPS}
    for row in index_rows:
        row = dict(row)
        holder = row.get("holder")
        row["holder_name"] = _holder_name(scene, holder)
        row["holder_room"] = rooms.holder_room(scene, holder) if holder else None
        row["occupants"] = list(occupants.get(row["id"], []))
        if row["status"] == rooms.STATUS_RETIRED:
            groups["retired"].append(row)
        elif row["hops"] == 0:
            groups["cast"].append(row)
        elif row["hops"] is None:
            groups["unreachable"].append(row)
        else:
            groups["reachable"].append(row)
    return groups


@router.get("")
def rooms_index(cid: int, frame_id: int | None = None):
    _chat_or_404(cid)
    with _era(cid, frame_id):
        scene = rooms.read_scene(cid)
        index = rooms.room_index(cid, frame_id, scene)
    return {
        "frame_id": frame_id,
        "location": str(scene.get("location") or ""),
        "groups": group_rows(index, scene),
    }


@router.get("/{room_id}")
def rooms_slice(cid: int, room_id: str, frame_id: int | None = None):
    _chat_or_404(cid)
    with _era(cid, frame_id):
        scene = rooms.read_scene(cid)
        row = rooms.room_slice(cid, frame_id, room_id, scene)
    if row is None:
        raise HTTPException(404, f"No room '{room_id}' in this story")
    row["holder_name"] = _holder_name(scene, row.get("holder"))
    return row
