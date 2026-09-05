"""Regions: which part of the map a room belongs to, derived and never named.

ONE FIELD, ``region``, on a room -- ``scene.rooms[room_id].region`` while
the room is live, ``room_registry.payload.region`` for as long as the
registry remembers the room -- and one small registry of what the regions
ARE, ``{region_id: {name, brief}}``, under the frame-scoped world key
`REGIONS_KEY`. Nothing here reads a room's name to decide anything.

Why a fourth spelling was needed. The engine held three half-answers to
"which part of the map is this": `zone` on a room (Director-authored, a
frame-split trigger meaning "a genuinely disconnected locale", silent when
empty -- 141 of 566 live rooms carried one on 2026-09-04), ``structure`` on a
PLANNED room (`room_registry.payload.planned.structure`, `world/structure.py`),
and the footprint of a `region_event` (`world/region_events.py`). None of
them covered a live room the Director minted, which is how chat 115 came to
hold a Director-minted lift car beside a planned one with nothing anywhere
saying they were the same part of the map. The room index
(`story/room_slice.room_index`) sorted by distance and had nothing to group
by. Argument: `docs/design/DESIGN_ROOM_REGIONS.md`.

THE DERIVATION, every rule deterministic and none of them a name match:

* a PLANNED room's region is its structure -- a structure IS a region; its
  key is the region id and its name the region's name, so the planted
  structures are the registry's seed and are never stored twice;
* a room the Director MINTS inherits, at commit, the region of the room it
  was reached from: the room it shares an edge with, in the same diff or
  already standing; when candidates disagree, the occupied room the beat
  stands in wins; when no joined room has a region, the room has none --
  the engine invents nothing;
* an INTERIOR room (`parent_entity`) has no region of its own and reports
  its holder's room's region, because the holder can move and a stored
  region would be the stale tag `infer_vehicle_zones` refuses to leave on a
  ship;
* a Director-written `zone` on a room with no region is FOLDED: it becomes
  a region id (normalized as room ids are) and a registry entry named as
  the zone was written. `zone` itself stays what it was -- the frame-split
  trigger in `world/spatial_frames.py` -- because "a separate locale" and
  "a part of the map" are two classes, and a district is the second
  without being the first;
* a Director-written `region` is a declaration that the room opened onto
  another part of the map: kept, normalized, and entered in the registry
  under the name it was written with;
* a RETIRED room keeps its region; the registry payload holds it.

Readers derive, never store: `room_region` answers for any room from the
scene and the registry, `room_pieces` names a region whose live rooms are
not joined by any path (the planner's "possible duplicate" signal), and
`backfill_regions` is the one-shot migration that gave existing scenes the
field on the schema bump that introduced it.
"""

from __future__ import annotations

import json

from world.spatial import normalize_room_id, room_of

#: The registry of what the regions are, ``{"version", "items": {region_id:
#: {"name", "brief"}}}``. Frame-scoped like the scene whose rooms it
#: describes (`core.db.FRAME_SCOPED_WORLD_KEYS`); a spatial split seeds the
#: away frame's copy from the parent's (`world/spatial_frames.py`).
REGIONS_KEY = "regions"
REGIONS_VERSION = 1


def normalize_region_id(text):
    """A region id is spelled the way a room id is (`normalize_room_id`),
    so a structure key, a folded zone and a declared region all land in
    one namespace. A spelling the room-id fold leaves empty (a name with no
    Latin letters or digits) keeps its own whitespace-collapsed text rather
    than collapsing every such region onto ``""``."""
    raw = " ".join(str(text or "").split())
    return normalize_room_id(raw) or raw


def normalize_regions(stored):
    stored = stored if isinstance(stored, dict) else {}
    items = stored.get("items") if isinstance(stored.get("items"), dict) \
        else {}
    out = {}
    for key, value in items.items():
        rid = normalize_region_id(key)
        if not rid:
            continue
        value = value if isinstance(value, dict) else {}
        entry = {"name": str(value.get("name") or key),
                 "brief": str(value.get("brief") or "")}
        # `look`: the visual register of this part of the map -- what a
        # picture of any room in it should share (the backdrop brief reads
        # it: `dressing/backdrops.room_brief`). Present only when set, so an
        # entry with no look keeps the shape every reader already pins.
        look = " ".join(str(value.get("look") or "").split())
        if look:
            entry["look"] = look
        out[rid] = entry
    return {"version": REGIONS_VERSION, "items": out}


def _planted_structures(cid):
    """``{structure_key: name}`` for every planted structure -- the
    registry's seed. Structures are stored frameless (`STRUCTURES_KEY`):
    a plan is the story's, not an era's."""
    from core.db import wget_for_frame
    from world.structure import STRUCTURES_KEY, normalize_structures

    items = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})["items"]
    return {key: str(value.get("name") or key) for key, value in items.items()}


def region_registry(cid, frame_id=None):
    """``{region_id: {name, brief}}`` for the frame: the stored registry
    with every planted structure standing in it as a region. Read-through
    seeding, so a structure is never written twice; a stored entry for a
    structure's key (a brief the room wrote) wins over the seed."""
    from core.db import wget_for_frame

    out = {}
    for key, name in _planted_structures(cid).items():
        rid = normalize_region_id(key)
        if rid:
            out[rid] = {"name": name, "brief": ""}
    stored = normalize_regions(
        wget_for_frame(cid, REGIONS_KEY, frame_id, {}) or {})["items"]
    for rid, entry in stored.items():
        out[rid] = dict(entry)
    return out


def ensure_regions(cid, frame_id, entries):
    """Enter every ``{region_id: name}`` in ``entries`` that the frame's
    registry lacks. Never rewrites a standing entry: a name or brief the
    room authored is not overruled by a zone the Director spelled later.
    Returns the ids added. Writes only when something is missing."""
    from core.db import wget_for_frame, wset_for_frame

    wanted = {normalize_region_id(k): str(v or k) for k, v in
              (entries or {}).items() if normalize_region_id(k)}
    if not wanted:
        return []
    standing = region_registry(cid, frame_id)
    missing = {rid: name for rid, name in wanted.items() if rid not in standing}
    if not missing:
        return []
    stored = normalize_regions(
        wget_for_frame(cid, REGIONS_KEY, frame_id, {}) or {})
    for rid in sorted(missing):
        stored["items"][rid] = {"name": missing[rid], "brief": ""}
    wset_for_frame(cid, REGIONS_KEY, stored, frame_id)
    return sorted(missing)


def set_region_look(cid, frame_id, region_id, look):
    """Write a region's `look` -- the visual register a picture of any room
    there shares -- into the frame's registry, entering the region by its id
    when the registry lacks it. An empty `look` removes the field. Returns
    the stored entry.

    THE SEAM, NOT YET A TOOL: nothing in the Room calls this (the only
    registry writer at commit is `ensure_regions`, which enters names). A
    HOST writes it from the World Browser's room card, through
    `web/world_routes.region_patch`; the Room tool that would write it is
    registered in `docs/UNBUILT.md`.
    """
    from core.db import wget_for_frame, wset_for_frame

    rid = normalize_region_id(region_id)
    if not rid:
        return None
    stored = normalize_regions(
        wget_for_frame(cid, REGIONS_KEY, frame_id, {}) or {})
    entry = dict(stored["items"].get(rid) or {})
    if not entry:
        seed = region_registry(cid, frame_id).get(rid) or {}
        entry = {"name": str(seed.get("name") or region_id), "brief": ""}
    text = " ".join(str(look or "").split())
    if text:
        entry["look"] = text
    else:
        entry.pop("look", None)
    stored["items"][rid] = entry
    wset_for_frame(cid, REGIONS_KEY, stored, frame_id)
    return dict(entry)


def region_name(registry, region_id):
    """The region's name, or its id when the registry has no entry."""
    entry = (registry or {}).get(region_id) if region_id else None
    return str(entry.get("name") or region_id) if isinstance(entry, dict) \
        else (str(region_id) if region_id else None)


# ---------------------------------------------------------------------------
# Reading a room's region
# ---------------------------------------------------------------------------

def scene_rooms(scene):
    return {str(rid): room for rid, room in ((scene or {}).get("rooms") or {}).items()
            if isinstance(room, dict)}


def scene_anchors(scene):
    out = {}
    for rid, room in scene_rooms(scene).items():
        for aid in (room.get("anchors") or {}):
            out.setdefault(str(aid), rid)
    return out


def holder_room_of(scene, holder, anchored=None):
    """Where the body a room is inside of stands: by identity, by anchor,
    or by a bare position row under the holder's name. None when the
    scene does not place the holder."""
    anchored = scene_anchors(scene) if anchored is None else anchored
    where = room_of(scene, str(holder)) or anchored.get(str(holder))
    if not where:
        where = ((scene or {}).get("positions") or {}).get(str(holder))
    return str(where) if where else None


def room_region(scene, room_id, registry_regions=None):
    """The region a room reports. A live room reports its own ``region``;
    an interior room reports its holder's room's, through as many holders
    as it takes; a room the scene does not hold (planned, retired) reports
    what the registry remembers (``registry_regions``: ``{uid: region}``,
    `registry_room_regions`). None when nothing says."""
    rooms = scene_rooms(scene)
    registry_regions = registry_regions or {}
    anchored = None
    seen = set()
    rid = str(room_id or "")
    while rid and rid not in seen:
        seen.add(rid)
        room = rooms.get(rid)
        if room is None:
            value = registry_regions.get(rid)
            return str(value) if value else None
        if room.get("parent_entity"):
            if anchored is None:
                anchored = scene_anchors(scene)
            rid = holder_room_of(scene, room["parent_entity"], anchored) or ""
            continue
        value = room.get("region")
        return str(value) if value else None
    return None


def _payload(row):
    try:
        payload = json.loads(row["payload"] or "{}")
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def registry_row_region(payload):
    """The region one registry payload records: its own ``region``, else
    the structure a planned room belongs to."""
    payload = payload if isinstance(payload, dict) else {}
    own = payload.get("region")
    if own:
        return normalize_region_id(own)
    planned = payload.get("planned")
    if isinstance(planned, dict) and planned.get("structure"):
        return normalize_region_id(planned["structure"])
    return None


def registry_room_regions(cid):
    """``{room_uid: region}`` for every registry row that records one --
    planned rooms by structure, live and retired rooms by the payload the
    commit wrote."""
    from core.db import q

    out = {}
    for row in q("SELECT room_uid, payload FROM room_registry WHERE chat_id=?",
                 (cid,)):
        region = registry_row_region(_payload(row))
        if region:
            out[str(row["room_uid"])] = region
    return out


def planned_structure_of(cid):
    """``{room_uid: structure_key}`` for every live planned registry row
    whose plan names a structure."""
    from world.structure import _planned_specs

    out = {}
    for uid, (_name, spec) in _planned_specs(cid).items():
        key = str(spec.get("structure") or "")
        if key:
            out[uid] = normalize_region_id(key)
    return out


# ---------------------------------------------------------------------------
# Deriving a room's region
# ---------------------------------------------------------------------------

def _undirected_edges(rooms):
    """``{room_id: {room_id}}`` over every declared edge of every room,
    both ways, whatever its barrier: a region is inherited across a door
    that is shut as readily as one that is open, because the room was
    still built on that side of it."""
    graph = {rid: set() for rid in rooms}
    for rid, room in rooms.items():
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict) and edge.get("to") in rooms:
                to = str(edge["to"])
                graph[rid].add(to)
                graph[to].add(rid)
    return graph


def inherit_regions(rooms, eligible, priority=(), graph=None):
    """Give every room in ``eligible`` that has no region the region of the
    rooms it is joined to, outward from the rooms that have one, in passes,
    until nothing more can be said. Mutates ``rooms``; returns
    ``[(room_id, region, from_room)]`` in assignment order.

    A pass looks at each eligible room's regioned neighbours. A neighbour in
    ``priority`` (the rooms the beat's bodies stood in) decides on its own:
    where a body walked from is where the room was reached from. Otherwise
    the neighbours must agree; a room joined to two regions and standing in
    neither is a boundary the engine does not resolve, and it is left
    empty for a Director to say which side it is on. Interior rooms are
    never assigned (they report their holder's).
    """
    graph = _undirected_edges(rooms) if graph is None else graph
    priority = {str(p) for p in priority if p}
    pending = sorted(str(r) for r in eligible
                     if r in rooms and not rooms[r].get("region")
                     and not rooms[r].get("parent_entity"))
    assigned = []
    while pending:
        settled = []
        for rid in pending:
            named = {}
            for other in sorted(graph.get(rid, ())):
                region = rooms[other].get("region") if not rooms[other].get(
                    "parent_entity") else None
                if region:
                    named[other] = str(region)
            if not named:
                continue
            chosen = None
            standing = sorted(o for o in named if o in priority)
            if standing:
                # Several occupied neighbours that disagree: the one the
                # most bodies stand in is the one the beat is in; ties
                # fall to the first id, so a reroll gets the same answer.
                chosen = standing[0]
            elif len(set(named.values())) == 1:
                chosen = sorted(named)[0]
            if chosen is None:
                continue
            settled.append((rid, named[chosen], chosen))
        if not settled:
            break
        for rid, region, source in settled:
            rooms[rid]["region"] = region
            assigned.append((rid, region, source))
        done = {rid for rid, _r, _s in settled}
        pending = [rid for rid in pending if rid not in done]
    return assigned


def assign_regions(scene, *, structures, minted=(), occupied=(),
                   inherit_all=False):
    """Stamp ``region`` on the rooms of ``scene`` by the rules in the
    module docstring. Pure over the database: ``structures`` is
    `planned_structure_of`'s map. Mutates the scene in place and returns
    ``{"assigned": [(room, region, why)], "registry": {region_id: name},
    "dropped": [room]}`` -- the registry entries the caller must enter
    (folded zones and declared regions, named as written) and the interior
    rooms whose stored region was removed.

    ``minted`` are the rooms this beat created, the only ones that inherit
    at commit; ``inherit_all`` is the migration's setting, which lets every
    unregioned room inherit once. ``occupied`` are the rooms the beat's
    bodies stood in before it.
    """
    rooms = scene_rooms(scene)
    assigned, registry, dropped = [], {}, []
    for rid in sorted(rooms):
        room = rooms[rid]
        if room.get("parent_entity"):
            # An inside has no region of its own: it reports its holder's,
            # and a stored one would go stale the moment the holder moved.
            if room.pop("region", None) is not None:
                dropped.append(rid)
            continue
        declared = room.get("region")
        if declared:
            norm = normalize_region_id(declared)
            if norm != declared:
                room["region"] = norm
            if norm:
                registry.setdefault(norm, " ".join(str(declared).split()))
            else:
                room.pop("region", None)
            continue
        structure = structures.get(rid)
        if structure:
            room["region"] = structure
            assigned.append((rid, structure, "planned"))
            continue
        zone = room.get("zone")
        if isinstance(zone, str) and zone.strip():
            folded = normalize_region_id(zone)
            room["region"] = folded
            registry.setdefault(folded, " ".join(zone.split()))
            assigned.append((rid, folded, "zone"))
    eligible = set(rooms) if inherit_all else {str(r) for r in minted}
    for rid, region, source in inherit_regions(rooms, eligible, occupied):
        assigned.append((rid, region, "reached from %s" % source))
    return {"assigned": assigned, "registry": registry, "dropped": dropped}


# ---------------------------------------------------------------------------
# What does not agree with itself
# ---------------------------------------------------------------------------

def room_pieces(cid, scene, registry_regions=None):
    """Regions whose live rooms are not all joined: ``[{"kind":
    "region_in_pieces", "region", "pieces": [[room ids], ...]}]``.

    A reachability fact, never a name comparison. Two live rooms of one
    region between which no path runs -- over every declared edge of every
    live room whatever its barrier, plus the plan's topology -- are two
    rooms the story says belong to one place and has never joined, which is
    what a Director-minted room standing beside the planned room it
    duplicates looks like from the map (chat 115's second lift car). One
    row per region, its rooms grouped by the piece they stand in, so the
    planner can look at the pieces and say which is which. Interior rooms
    are a fact about their holder and are not pieces of anything.
    """
    from world.structure import planned_topology

    rooms = {rid: room for rid, room in scene_rooms(scene).items()
             if not room.get("parent_entity")}
    graph = _undirected_edges(rooms)
    for rid, others in planned_topology(cid).items():
        graph.setdefault(str(rid), set())
        for other in others:
            graph.setdefault(str(other), set())
            graph[str(rid)].add(str(other))
            graph[str(other)].add(str(rid))
    component = {}
    for start in sorted(graph):
        if start in component:
            continue
        stack = [start]
        component[start] = start
        while stack:
            node = stack.pop()
            for other in graph.get(node, ()):
                if other not in component:
                    component[other] = start
                    stack.append(other)
    by_region = {}
    for rid in sorted(rooms):
        region = room_region(scene, rid, registry_regions)
        if region:
            by_region.setdefault(region, {}).setdefault(
                component.get(rid, rid), []).append(rid)
    out = []
    for region in sorted(by_region):
        pieces = sorted(by_region[region].values(), key=lambda p: (-len(p), p))
        if len(pieces) > 1:
            out.append({"kind": "region_in_pieces", "region": region,
                        "pieces": pieces})
    return out


# ---------------------------------------------------------------------------
# The one-shot migration
# ---------------------------------------------------------------------------

def backfill_regions(c):
    """Give every stored scene's rooms a region where one can be derived,
    once, on the schema bump that introduced the field (`core.db.init`).

    Planned rooms by structure, zones folded, and the rest by breadth-first
    inheritance from a regioned neighbour (`assign_regions` with
    ``inherit_all``); a room no rule reaches stays empty, because the
    engine does not invent a region. Folded zones are entered in each
    frame's registry. Runs on the raw connection the migration chain holds.
    Returns ``{"scenes", "rooms", "regioned", "empty"}`` for the caller's
    log -- and for the measurement that was taken before it shipped
    (`docs/design/DESIGN_ROOM_REGIONS.md`).
    """
    from core.db import _FRAME_KEY_SEP, parse_scoped_world_key

    counts = {"scenes": 0, "rooms": 0, "regioned": 0, "empty": 0}
    structures_by_chat = {}
    for row in c.execute("SELECT chat_id, room_uid, payload FROM room_registry "
                         "WHERE retired_turn_id IS NULL").fetchall():
        payload = _payload(row)
        planned = payload.get("planned")
        if isinstance(planned, dict) and planned.get("structure"):
            structures_by_chat.setdefault(row["chat_id"], {})[
                str(row["room_uid"])] = normalize_region_id(planned["structure"])
    rows = c.execute(
        "SELECT chat_id, key, value FROM world WHERE key=? OR key LIKE ?",
        ("scene", f"scene{_FRAME_KEY_SEP}%")).fetchall()
    for row in rows:
        try:
            scene = json.loads(row["value"])
        except (TypeError, ValueError):
            continue
        if not isinstance(scene, dict) or not isinstance(scene.get("rooms"), dict):
            continue
        counts["scenes"] += 1
        result = assign_regions(
            scene, structures=structures_by_chat.get(row["chat_id"], {}),
            inherit_all=True)
        rooms = scene_rooms(scene)
        counts["rooms"] += len(rooms)
        for rid in rooms:
            if room_region(scene, rid):
                counts["regioned"] += 1
            else:
                counts["empty"] += 1
        if not result["assigned"] and not result["dropped"] \
                and not result["registry"]:
            continue
        c.execute("UPDATE world SET value=? WHERE chat_id=? AND key=?",
                  (json.dumps(scene), row["chat_id"], row["key"]))
        if result["registry"]:
            _, frame_id = parse_scoped_world_key(row["key"])
            key = REGIONS_KEY if frame_id is None else \
                f"{REGIONS_KEY}{_FRAME_KEY_SEP}{frame_id}"
            stored = c.execute("SELECT value FROM world WHERE chat_id=? AND key=?",
                               (row["chat_id"], key)).fetchone()
            registry = normalize_regions(
                json.loads(stored["value"]) if stored else {})
            for rid, name in result["registry"].items():
                registry["items"].setdefault(rid, {"name": name, "brief": ""})
            c.execute(
                "INSERT INTO world(chat_id,key,value) VALUES(?,?,?) "
                "ON CONFLICT(chat_id,key) DO UPDATE SET value=excluded.value",
                (row["chat_id"], key, json.dumps(registry)))
    return counts


__all__ = [
    "REGIONS_KEY", "assign_regions", "backfill_regions", "ensure_regions",
    "holder_room_of", "inherit_regions", "normalize_region_id",
    "normalize_regions", "planned_structure_of", "region_name",
    "region_registry", "registry_room_regions", "registry_row_region",
    "room_pieces", "room_region", "scene_anchors", "scene_rooms",
    "set_region_look",
]
