"""Typed HTTP boundary for the World Browser: the room index and the
per-room slice, read through `story/room_slice.py` -- the ONE reader the
Writers' Room's `inspect_rooms`, the frontier and the browser all share, so
a host and the Planner cannot be shown two different worlds -- and, since
2026-09-04, three NARROW writes so a host edits a field rather than a blob.

Reads (under ``/api/chats/{cid}/rooms``; ``frame_id`` absent or null is the
present, else a frame row of this chat, 404 otherwise -- the same contract
`app._era` gives the attire route):

* ``GET  ?frame_id=`` -> ``{frame_id, location, groups, bodies, vocab}``.
  ``groups`` is ``{cast, reachable, unreachable, retired}``, each a list of
  index rows in the index's own order (hops, then id); ``cast`` is every
  room a cast member stands in (hops 0); ``reachable`` every other room the
  walk from the cast reaches, live or planned; ``unreachable`` every
  unretired room it does not; ``retired`` the spent ids. Every row is the
  index row plus ``holder_name`` (the entity's display name when the room
  is the inside of a body), ``holder_room`` (where that body stands, for
  nesting) and ``occupants`` (the names `positions` place here).
  ``bodies`` is every body the scene knows -- cast, player, promoted
  presence, and a body the attire ledger dresses but nothing places -- each
  ``{name, kind, char_id, room, room_name, station, pose, attire}`` with the
  ledger AS STORED (`body_rows`). ``vocab`` is every closed set the browser
  offers as a select, read from the engine's own constants so a menu cannot
  drift from the code (`vocabulary`).
* ``GET  /{room_id}?frame_id=`` -> the slice plus ``holder_name``,
  ``record`` (the room's stored editable fields: name, desc, notes, light,
  size, exposure, region, anchors, adjacent -- the slice renders prose
  capped and exits derived, and an editor needs what is STORED) and
  ``stationable`` (the anchors a station may name here, authored and the
  implicit `door:<to>` ones -- `world.spatial.effective_anchors`, the same
  set `normalize_scene_stations` keeps); 404 when no room of that id is
  known to the story.

Writes, each host-only and era-scoped exactly like the reads, each refused
with 409 while any pipeline of the chat runs (the same guard `world_put`
and the position route hold), each reading the scene through
`story.scene.get_scene`, applying the change under the SAME normalisers the
commit path runs (`normalize_scene_barriers`, `normalize_scene_bearings`,
`normalize_scene_stations` -- `world/spatial_merge.merge_scene_with_diff`'s
tail), writing it through `wset` as `attire_put` does, and reconciling the
`room_registry` projection through `persist.commit
.sync_room_registry_with_scene` -- the rule every scene writer keeps
(`AGENTS.md`):

* ``PATCH /{room_id}`` with a body of ONLY the changed fields. ``name``,
  ``desc``, ``notes`` are text (an empty ``name`` is refused: the id needs a
  label); ``light`` / ``size`` / ``exposure`` are refused outside their sets
  with a message naming the set, and an empty string CLEARS the field
  (absent means the engine's default, which is what the word means);
  ``region`` is free text folded to a region id, empty clearing it;
  ``exits`` and ``anchors`` are FULL replacement lists for this room. An
  exit is ``{to, barrier, dir?}``; a doorway is one object, so the far
  room's reciprocal edge is written too -- created when missing, its
  barrier set when it stands (every barrier but `one_way_window`, which is
  asymmetric by design), its ``dir`` the opposite bearing, and REMOVED when
  the exit is (`_mirror_symmetric_barriers` in `world/spatial_merge.py` is
  the merge's statement of the same rule; `Design.md`'s "One doorway, one
  barrier"). Fields an edge carried that the browser does not edit
  (`distance`, `passage_from`, ...) survive on the edge that keeps its
  ``to``. Anchors are ``{anchor_id: {desc, dir?, height?, footprint?,
  opacity?}}``; an anchor without an id is keyed by its folded desc; the
  geometry words are refused outside `HEIGHTS` / `FOOTPRINTS` / `OPACITIES`.
  Returns the fresh slice (as the GET shapes it) so the card re-renders
  without a second fetch.
* ``PATCH /{room_id}/entities/{entity_id}`` for a thing standing in the
  room: ``kind``, ``description`` (text), ``portable`` (bool),
  ``light_source`` (a `LIGHT_LEVELS` word, empty clearing it), ``lit`` (bool
  -> ``state.lit``; null clears), ``room`` (a live room id to move the
  thing's position row to; a thing placed only as an anchor is not moved --
  the anchor editor is where it lives). Returns the fresh slice.
* ``PUT  /bodies/{name}/station`` with ``{at, near}``: ``at`` must be an
  anchor the body's room holds (`effective_anchors`; the refusal names
  them) or null; ``near`` names bodies standing in the same room. Returns
  the body's row.

Attire is NOT written here: the browser's attire editor sends the whole
ledger to `app.attire_put`, which re-derives every entry
(`story.attire.rederive_entry`) -- one writer, one derivation.

Host-only by construction: nothing here is in `GUEST_ALLOWED_API_PATHS`.
The slice is author knowledge -- planned stubs, package operations, another
body's whole attire ledger -- and reaches no mind (`story/room_tools.py`).
"""

from __future__ import annotations

import copy
import json
from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException

from core import db
from core.db import q, transaction, wset
from persist.commit import sync_room_registry_with_scene
from story import room_slice as rooms
from story.attire import GARMENT_STATES, REGIONS as ATTIRE_REGIONS
from story.character_schema import character_name, persona_name
from story.scene import get_scene, persona_of
from world.spatial import (
    _BEARINGS, _VALID_BARRIERS, FOOTPRINTS, HEIGHTS, LIGHT_LEVELS, OPACITIES,
    ROOM_SIZES, effective_anchors, normalize_bearing, normalize_room_id,
    normalize_scene_barriers, normalize_scene_bearings,
    normalize_scene_stations, opposite_bearing, room_of,
)
from world.weather import EXPOSURES

router = APIRouter(prefix="/api/chats/{cid}/rooms", tags=["world-browser"])

#: The display groups, in the order the browser lists them.
GROUPS = ("cast", "reachable", "unreachable", "retired")

#: The room fields the browser edits as text. `name` is required non-empty.
TEXT_FIELDS = ("name", "desc", "notes")

#: The room fields that are a word from a closed set the engine owns, each
#: with its set. An empty string clears the field.
ROOM_ENUMS = {"light": LIGHT_LEVELS, "size": ROOM_SIZES, "exposure": EXPOSURES}

#: The anchor geometry words and their sets (`world/spatial_fov.py` owns them).
ANCHOR_ENUMS = {"height": HEIGHTS, "footprint": FOOTPRINTS, "opacity": OPACITIES}

#: The barrier that is asymmetric BY DESIGN and is never mirrored onto the far
#: room's edge (`_mirror_symmetric_barriers` holds the same exception).
_ASYMMETRIC_BARRIER = "one_way_window"


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


def _require_idle(cid: int):
    """The pipeline reads and rewrites the scene throughout a turn; a field
    edit underneath a running one would be corrupted or silently overwritten
    by the commit. `app._require_chat_idle`'s rule over the same registry
    (`agents.runtime.ABORTS`), stated here because `web.app` imports this
    module and cannot be imported back at module load."""
    from agents.runtime import ABORTS
    if any(key[0] == cid for key in list(ABORTS)):
        raise HTTPException(
            409,
            "This chat still has an active pipeline. Abort it and wait for "
            "the aborted response before editing the world.")


def _holder_name(scene, holder):
    """The display name of the body a room is inside of -- the scene
    entity's `name` when it has one, else the id the room recorded."""
    if not holder:
        return None
    entity = (scene.get("entities") or {}).get(str(holder))
    if isinstance(entity, dict) and str(entity.get("name") or "").strip():
        return str(entity["name"]).strip()
    return str(holder)


def _is_body(scene, who):
    """`cast_rooms`'s rule: a position row keyed by a scene entity of an
    inanimate kind places a thing; a row with no entity record behind it, or
    an animate one, is a body."""
    from llm.schemas import _ANIMATE_ENTITY_KINDS
    ent = (scene.get("entities") or {}).get(str(who))
    kind = (str(ent.get("kind") or "").strip().casefold()
            if isinstance(ent, dict) else "")
    return not kind or kind in _ANIMATE_ENTITY_KINDS


def group_rows(index_rows, scene):
    """Sort index rows into the four display groups, each keeping the
    index's order, and decorate every row for display. Pure over its inputs
    so the grouping is testable without a request."""
    # The names beside a cast room are BODIES, by the rule `cast_rooms` counts
    # the cast with: a position row keyed by a scene entity of an inanimate
    # kind places a thing (the slice lists it under `things`), and a row with
    # no entity record behind it, or an animate one, is a body.
    occupants = {}
    for who, room in (scene.get("positions") or {}).items():
        if not str(room or "") or not _is_body(scene, who):
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


def vocabulary(cid, frame_id):
    """Every closed set the browser offers, from the engine's own constants.
    `regions` is the map's known regions (`world.regions.region_registry`,
    for a datalist -- a region is free text that folds to an id, not a
    closed set); every other key is a set the engine refuses values outside
    of."""
    from world.regions import region_registry
    registry = region_registry(cid, frame_id)
    return {
        "light": list(LIGHT_LEVELS),
        "size": list(ROOM_SIZES),
        "exposure": list(EXPOSURES),
        "barriers": sorted(_VALID_BARRIERS),
        "dirs": list(_BEARINGS),
        "heights": list(HEIGHTS),
        "footprints": list(FOOTPRINTS),
        "opacities": list(OPACITIES),
        "regions": [{"id": rid, "name": str(entry.get("name") or rid)}
                    for rid, entry in sorted(registry.items())],
        "attire_regions": list(ATTIRE_REGIONS),
        "garment_states": list(GARMENT_STATES),
    }


def _cast_ids(cid):
    """``{folded name: char_id}`` for the registered cast of the story."""
    out = {}
    for row in q("SELECT cc.char_id AS id, COALESCE(cc.sheet, ch.sheet) AS sheet "
                 "FROM chat_chars cc JOIN characters ch ON ch.id = cc.char_id "
                 "WHERE cc.chat_id=?", (cid,)):
        try:
            name = character_name(json.loads(row["sheet"] or "{}"))
        except (TypeError, ValueError):
            continue
        if name:
            out[name.strip().casefold()] = int(row["id"])
    return out


def body_rows(cid, chat, scene):
    """Every body the scene knows, for the Bodies tab: the bodies `positions`
    place (by `cast_rooms`'s rule), the player whether placed or not, and any
    body the attire ledger dresses that nothing places (offscreen, but
    dressed). Ordered player first, then by name."""
    rooms_ = scene.get("rooms") or {}
    positions = scene.get("positions") or {}
    stations = scene.get("stations") if isinstance(scene.get("stations"), dict) else {}
    poses = scene.get("poses") if isinstance(scene.get("poses"), dict) else {}
    attire = scene.get("attire") if isinstance(scene.get("attire"), dict) else {}
    player = str(persona_name(persona_of(chat)) or "").strip()
    cast = _cast_ids(cid)

    names = []
    seen = set()

    def add(name):
        key = str(name).strip().casefold()
        if key and key not in seen:
            seen.add(key)
            names.append(str(name))

    if player:
        add(player)
    for who, room in positions.items():
        if str(room or "") and _is_body(scene, who):
            add(who)
    for who in attire:
        add(who)

    out = []
    for name in names:
        key = name.strip().casefold()
        room = room_of(scene, name)
        room_def = rooms_.get(room) if room else None
        if key == player.casefold():
            kind = "player"
        elif key in cast:
            kind = "cast"
        else:
            kind = "presence"
        out.append({
            "name": name,
            "kind": kind,
            "char_id": cast.get(key),
            "room": room or None,
            "room_name": (str(room_def.get("name") or room)
                          if isinstance(room_def, dict) else room),
            "station": stations.get(name),
            "pose": poses.get(name),
            "attire": attire.get(name),
        })
    out.sort(key=lambda b: (b["kind"] != "player", b["name"].casefold()))
    return out


@router.get("")
def rooms_index(cid: int, frame_id: int | None = None):
    chat = _chat_or_404(cid)
    with _era(cid, frame_id):
        scene = rooms.read_scene(cid)
        index = rooms.room_index(cid, frame_id, scene)
        bodies = body_rows(cid, chat, scene)
        vocab = vocabulary(cid, frame_id)
    return {
        "frame_id": frame_id,
        "location": str(scene.get("location") or ""),
        "groups": group_rows(index, scene),
        "bodies": bodies,
        "vocab": vocab,
    }


def _record(room):
    """The room's stored editable fields, for the card's inputs."""
    room = room if isinstance(room, dict) else {}
    anchors = room.get("anchors") or {}
    if isinstance(anchors, (list, tuple)):
        anchors = {str(a): {"desc": str(a)} for a in anchors if str(a)}
    return {
        "name": str(room.get("name") or ""),
        "desc": str(room.get("desc") or room.get("description") or ""),
        "notes": str(room.get("notes") or ""),
        "light": str(room.get("light") or ""),
        "size": str(room.get("size") or ""),
        "exposure": str(room.get("exposure") or ""),
        "region": str(room.get("region") or ""),
        "anchors": {str(aid): dict(a) for aid, a in anchors.items()
                    if isinstance(a, dict)},
        "adjacent": [dict(e) for e in (room.get("adjacent") or [])
                     if isinstance(e, dict) and e.get("to")],
    }


def _decorated_slice(cid, frame_id, room_id, scene):
    row = rooms.room_slice(cid, frame_id, room_id, scene)
    if row is None:
        return None
    row["holder_name"] = _holder_name(scene, row.get("holder"))
    room = (scene.get("rooms") or {}).get(room_id)
    if isinstance(room, dict):
        row["record"] = _record(room)
        row["stationable"] = [
            {"id": str(aid), "desc": str((a or {}).get("desc") or aid),
             "implicit": bool((a or {}).get("implicit"))}
            for aid, a in effective_anchors(scene, room_id).items()]
    else:
        row["record"] = None
        row["stationable"] = []
    # Each thing's stored editable fields, and HOW it is placed here: by a
    # position row (movable) or as one of the room's anchors (the anchor
    # editor's business).
    entities = scene.get("entities") or {}
    for thing in row.get("things") or []:
        ent = entities.get(thing["id"])
        ent = ent if isinstance(ent, dict) else {}
        thing["record"] = {
            "kind": str(ent.get("kind") or ""),
            "description": str(ent.get("description") or ""),
            "portable": bool(ent.get("portable")),
            "light_source": str(ent.get("light_source") or ""),
            "state": ent.get("state") if isinstance(ent.get("state"), dict) else {},
        }
        thing["placed"] = "position" if room_of(scene, thing["id"]) else "anchor"
    return row


@router.get("/{room_id}")
def rooms_slice(cid: int, room_id: str, frame_id: int | None = None):
    _chat_or_404(cid)
    with _era(cid, frame_id):
        scene = rooms.read_scene(cid)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    if row is None:
        raise HTTPException(404, f"No room '{room_id}' in this story")
    return row


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def _refuse_outside(field, value, allowed):
    """400 naming the set, when a value is not one of its words."""
    if value not in allowed:
        raise HTTPException(
            400, f"{field} must be one of: {', '.join(allowed)} (got '{value}')")


def _enum_value(field, raw, allowed):
    """A closed-set field's value from the body: '' or None clears (returns
    None), anything else must be one of the set's words."""
    value = str(raw or "").strip().casefold()
    if not value:
        return None
    _refuse_outside(field, value, allowed)
    return value


def _live_room_or_400(scene, room_id):
    room = (scene.get("rooms") or {}).get(str(room_id))
    if not isinstance(room, dict):
        known = ", ".join(sorted(scene.get("rooms") or {})) or "(none)"
        raise HTTPException(
            400, f"No room '{room_id}' in this scene. Known rooms: {known}")
    return room


def _edge_to(room, to_id):
    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and str(edge.get("to")) == str(to_id):
            return edge
    return None


def _apply_exits(scene, room_id, room, exits):
    """Replace the room's exits and keep every doorway one object: the far
    room's reciprocal edge is created, re-barriered, re-beared or removed to
    agree. Fields the browser does not edit survive on an edge that keeps
    its `to`."""
    if not isinstance(exits, list):
        raise HTTPException(400, "exits must be a list of {to, barrier, dir}")
    scene_rooms = scene.get("rooms") or {}
    known = set(scene_rooms)
    prior = {str(e.get("to")): e for e in (room.get("adjacent") or [])
             if isinstance(e, dict) and e.get("to")}
    fresh, seen = [], set()
    for raw in exits:
        if not isinstance(raw, dict):
            raise HTTPException(400, "exits must be a list of {to, barrier, dir}")
        to = str(raw.get("to") or "").strip()
        if not to:
            raise HTTPException(400, "an exit needs a room to lead to")
        if to == str(room_id):
            raise HTTPException(400, "a room cannot exit into itself")
        if to in seen:
            raise HTTPException(400, f"exit to '{to}' is listed twice")
        seen.add(to)
        barrier = str(raw.get("barrier") or "").strip().casefold() or "open"
        _refuse_outside("barrier", barrier, sorted(_VALID_BARRIERS))
        direction = None
        if str(raw.get("dir") or "").strip():
            direction = normalize_bearing(raw.get("dir"))
            if direction is None:
                _refuse_outside("dir", str(raw.get("dir")), list(_BEARINGS))
        edge = dict(prior.get(to) or {})
        edge["to"] = to
        edge["barrier"] = barrier
        if direction:
            edge["dir"] = direction
        else:
            edge.pop("dir", None)
        fresh.append(edge)
    room["adjacent"] = fresh

    # The far side. A planned room the scene does not hold has no edge list
    # to mirror onto; the plan's own topology already names the doorway.
    for to in set(prior) - seen:
        far = scene_rooms.get(to)
        if isinstance(far, dict):
            far["adjacent"] = [e for e in (far.get("adjacent") or [])
                               if not (isinstance(e, dict)
                                       and str(e.get("to")) == str(room_id))]
    for edge in fresh:
        to = edge["to"]
        if to not in known:
            continue
        far = scene_rooms[to]
        if not isinstance(far, dict):
            continue
        back = _edge_to(far, room_id)
        if back is None:
            back = {"to": str(room_id)}
            far.setdefault("adjacent", []).append(back)
        if edge["barrier"] != _ASYMMETRIC_BARRIER \
                and str(back.get("barrier") or "") != _ASYMMETRIC_BARRIER:
            back["barrier"] = edge["barrier"]
        if edge.get("dir"):
            back["dir"] = opposite_bearing(edge["dir"])
        else:
            back.pop("dir", None)


def _apply_anchors(room, anchors):
    """Replace the room's anchors: `{id: {desc, dir?, height?, footprint?,
    opacity?}}`, an empty id keyed by the folded desc, geometry words
    refused outside their sets."""
    if isinstance(anchors, list):
        anchors = {str(a.get("id") or ""): a for a in anchors if isinstance(a, dict)}
    if not isinstance(anchors, dict):
        raise HTTPException(400, "anchors must be a mapping of id -> {desc, dir, ...}")
    out = {}
    for aid, raw in anchors.items():
        if not isinstance(raw, dict):
            raise HTTPException(400, f"anchor '{aid}' must be an object")
        desc = " ".join(str(raw.get("desc") or "").split())
        key = normalize_room_id(str(aid or "")) or normalize_room_id(desc)
        if not key:
            raise HTTPException(400, "an anchor needs a description or an id")
        if key in out:
            raise HTTPException(400, f"anchor '{key}' is listed twice")
        anchor = {"desc": desc or key}
        if str(raw.get("dir") or "").strip():
            direction = normalize_bearing(raw.get("dir"))
            if direction is None:
                _refuse_outside("dir", str(raw.get("dir")), list(_BEARINGS))
            anchor["dir"] = direction
        for field, allowed in ANCHOR_ENUMS.items():
            value = _enum_value(field, raw.get(field), allowed)
            if value:
                anchor[field] = value
        # Whatever else the engine wrote on the anchor rides through.
        for field, value in raw.items():
            if field not in ("id", "desc", "dir", *ANCHOR_ENUMS) and value is not None:
                anchor.setdefault(field, value)
        out[key] = anchor
    room["anchors"] = out


def _write_scene(cid, chat, before, scene):
    """The one way a route here lands a scene: normalised as the commit
    path normalises, written through `wset` under the ambient era, the
    registry projection reconciled against what the blob held before."""
    normalize_scene_barriers(scene)
    normalize_scene_bearings(scene)
    scene.setdefault("stations", {})
    normalize_scene_stations(scene)
    with transaction():
        wset(cid, "scene", scene)
        sync_room_registry_with_scene(cid, chat.get("lorebook_id"), before, scene)


@router.patch("/{room_id}")
def room_patch(cid: int, room_id: str, body: dict = Body(...),
               frame_id: int | None = None):
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send an object of the changed fields")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        room = _live_room_or_400(scene, room_id)
        for field in TEXT_FIELDS:
            if field in body:
                text = str(body.get(field) or "").strip()
                if field == "name" and not text:
                    raise HTTPException(400, "A room needs a name")
                room[field] = text
                if field == "desc":
                    room.pop("description", None)
        for field, allowed in ROOM_ENUMS.items():
            if field in body:
                value = _enum_value(field, body.get(field), allowed)
                if value:
                    room[field] = value
                else:
                    room.pop(field, None)
        if "region" in body:
            from world.regions import normalize_region_id
            region = normalize_region_id(str(body.get("region") or ""))
            if region:
                room["region"] = region
            else:
                room.pop("region", None)
        if "exits" in body:
            _apply_exits(scene, room_id, room, body.get("exits"))
        if "anchors" in body:
            _apply_anchors(room, body.get("anchors"))
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return row


@router.patch("/{room_id}/entities/{entity_id}")
def room_entity_patch(cid: int, room_id: str, entity_id: str,
                      body: dict = Body(...), frame_id: int | None = None):
    from world.regions import scene_anchors
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send an object of the changed fields")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        _live_room_or_400(scene, room_id)
        entities = scene.setdefault("entities", {})
        entity = entities.get(str(entity_id))
        if not isinstance(entity, dict):
            raise HTTPException(404, f"No entity '{entity_id}' in this scene")
        placed_by_position = room_of(scene, str(entity_id))
        where = placed_by_position or scene_anchors(scene).get(str(entity_id))
        if str(where or "") != str(room_id):
            raise HTTPException(
                400, f"'{entity_id}' does not stand in '{room_id}'"
                     + (f" (it is in '{where}')" if where else ""))
        for field in ("kind", "description"):
            if field in body:
                entity[field] = " ".join(str(body.get(field) or "").split())
        if "portable" in body:
            entity["portable"] = bool(body.get("portable"))
        if "light_source" in body:
            value = _enum_value("light_source", body.get("light_source"),
                                LIGHT_LEVELS)
            if value:
                entity["light_source"] = value
            else:
                entity.pop("light_source", None)
        if "lit" in body:
            state = entity.get("state")
            if not isinstance(state, dict):
                state = entity["state"] = {}
            if body.get("lit") is None:
                state.pop("lit", None)
            else:
                state["lit"] = bool(body.get("lit"))
        if "room" in body:
            target = str(body.get("room") or "").strip()
            if not placed_by_position:
                raise HTTPException(
                    400, f"'{entity_id}' is placed as an anchor of '{room_id}', "
                         "not by a position; edit the room's anchors to move it")
            if not target:
                raise HTTPException(400, "A thing needs a room to move to")
            _live_room_or_400(scene, target)
            positions = scene.setdefault("positions", {})
            for key in [k for k in positions
                        if str(k).strip().casefold() == str(entity_id).strip().casefold()]:
                positions.pop(key)
            positions[str(entity_id)] = target
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return row


bodies_router = APIRouter(prefix="/api/chats/{cid}/bodies", tags=["world-browser"])


@bodies_router.put("/{name}/station")
def body_station_put(cid: int, name: str, body: dict = Body(...),
                     frame_id: int | None = None):
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {at, near}")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        positions = scene.get("positions") or {}
        folded = str(name).strip().casefold()
        key = next((k for k in positions if str(k).strip().casefold() == folded), None)
        room = str(positions.get(key) or "") if key is not None else ""
        if not room:
            raise HTTPException(400, f"'{name}' stands in no room, so has no station")
        anchors = effective_anchors(scene, room)
        at = str(body.get("at") or "").strip() or None
        if at is not None and at not in anchors:
            held = ", ".join(sorted(anchors)) or "(none)"
            raise HTTPException(
                400, f"'{room}' has no anchor '{at}'. Anchors here: {held}")
        near_raw = body.get("near")
        if near_raw is None:
            near_raw = []
        if not isinstance(near_raw, list):
            raise HTTPException(400, "near must be a list of names")
        near = []
        for other in near_raw:
            other = str(other or "").strip()
            if not other or other.casefold() == folded:
                continue
            other_key = next((k for k in positions
                              if str(k).strip().casefold() == other.casefold()), None)
            if other_key is None or str(positions.get(other_key) or "") != room:
                raise HTTPException(
                    400, f"'{other}' does not stand in '{room}' with '{key}'")
            if other_key not in near:
                near.append(other_key)
        stations = scene.setdefault("stations", {})
        if not isinstance(stations, dict):
            stations = scene["stations"] = {}
        stations[key] = {"at": at, "near": near}
        _write_scene(cid, chat, before, scene)
        rows = body_rows(cid, chat, scene)
    row = next((b for b in rows if b["name"].strip().casefold() == folded), None)
    return row or {"name": key, "room": room, "station": stations[key]}
