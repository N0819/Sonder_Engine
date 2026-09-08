"""The room index and the per-room slice: ONE reader of the world's rooms
that the Writers' Room's tool, the frontier, and (next) a web route and a
browser all read through, so they cannot disagree about what a room is.

Why one reader. `inspect_rooms` used to dump every live room and every
planned brief in one flat list, and it filed a room carrying `parent_entity`
under `containment` rather than as a room -- while `room_frontier` reported
the player as standing in exactly that room. Measured live (chat 115): the
frontier said the player was in `room_elevator_interior`, the tool listed
no such room, and the Planner drew the only conclusion the two reads left
it and planned a second lift car beside the one the cast stood in. The
class is two readers deriving "what rooms are there" separately; the fix is
this module, which both now call.

Two pure readers, both ``(cid, frame_id, scene=None)`` -- the scene is read
through `story.scene.get_scene` when not given, and passed in by a caller
that already holds it. Neither writes anything.

``room_index(cid, frame_id, scene=None)`` -> ``list[dict]``, one row per
room the story knows, each::

    {"id": str, "name": str,
     "status": "live" | "planned" | "retired",
     "holder": str | None,     # `parent_entity`: the body this room is the inside of
     "region": str | None,     # the part of the map (world/regions.py); an
                               # inside reports its holder's room's
     "hops": int | None}       # BFS distance from the nearest room a cast
                               # member occupies; None when unreachable

* ``live`` is a room in the frame's scene; ``planned`` a `room_registry` row
  carrying a ``planned`` payload the scene has not reached; ``retired`` a
  registry row with `retired_turn_id` set -- included so a reader knows the
  id is spent, never as a place.
* ``hops`` counts over the edges a body could cross
  (`world.spatial._ROUTE_MEMORY_BARRIERS` -- passable, plus a closed door;
  directional where an edge says so) UNION `world.structure
  .planned_topology` (the plan's edges, undirected: a stub is a room the
  Director furnishes on entry). A room that is the inside of a body is
  joined to the room its HOLDER stands in and to nothing else: one hop out
  of it is the holder's room, nothing routes through it, and a cast member
  standing inside a body is at hops 0 like anyone else. The cast is every
  body the scene's `positions` place.
* GROUPED BY REGION: regions ordered by the nearest room in each (so the
  cast's region comes first), and within a region by ``hops`` then ``id``,
  unreachable rows last in their region. Rooms in no region are one group
  under the same rule, so a story with no regions is ordered exactly as it
  was: ``hops`` then ``id``, cast rooms first by construction.

``room_slice(cid, frame_id, room_id, scene=None)`` -> ``dict | None``, the
whole of one room (None when no room of that id is known)::

    {"id", "name", "status", "holder", "region", # as in the index row
     "region_name": str | None,                  # the region's name from its registry
     "description": str,                         # the room's prose, capped at DESCRIPTION_CHARS
     "exits": [{"to", "name", "barrier", "dir", "status"}],
     "occupants": [{"name", "station", "attire"}],
     "things": [{"id", "name", "kind", "plan_ref"?}],
     "planned_stub": {"name", "purpose", "access", "exits", "structure"?} | None,
     "plan_here": {"planned_entities": [{"uid", "kind", "name", "rendered"}],
                   "needs": [{"uid", "kind", "subject"}],
                   "package_ops": [{"package", "title", "status", "index", "op"}]}}

* ``exits`` come from `world.spatial.effective_adjacent` for a live room
  (the undirected graph: an edge the neighbour declared counts) and from
  `world.structure.planned_room_brief` for a planned one; each carries the
  far room's ``status`` (None when the id is known to nothing).
* ``occupants`` are the bodies `positions` place here; ``station`` is the
  body's `scene.stations` slot and ``attire`` its `scene.attire` entry, both
  AS STORED (None when absent).
* ``things`` are the scene entities standing here by a position row or as
  an anchor of the room, bodies excluded (a body is an occupant, and a cast
  member routinely carries both a position row and a scene entity under one
  name); ``plan_ref`` rides a thing the Director's identity floor bound.
* ``planned_stub`` is the plan's brief while the room is still the plan's
  prose-free stub (live or not yet in the scene); None once developed.
* ``plan_here`` is the author layer's claims on the room: the planned
  entities whose brief puts them here, the open planning needs whose
  identity or surface names the room, and every operation in an unsealed,
  unretired package that names the room (`plot_packages.operation_rooms`
  over `plot_packages.ROOM_FIELDS`, the one declaration of which fields of
  an operation hold a room id). Sealed packages are what
  `read_package reveal` is for and contribute nothing here; ids and
  one-line names only.

Author-layer reading: everything here is objective truth for the room's
author, and nothing here reaches a mind (`story/room_tools.py`'s
docstring). `story` may import `world`
(`docs/design/DESIGN_MODULE_LAYOUT.md`); nothing here imports `agents`.
"""

from __future__ import annotations

import json

from story.attire import entry_for as attire_entry_for

#: Characters of a room's description a slice carries. A browser opening a
#: room wants the prose; a neighbourhood of a dozen rooms wants it bounded.
DESCRIPTION_CHARS = 600

STATUS_LIVE = "live"
STATUS_PLANNED = "planned"
STATUS_RETIRED = "retired"


def read_scene(cid, frame_id=None):
    """The frame's scene through the engine's own reader.

    `frame_id` PINS THE FRAME. `get_scene` routes by the ambient
    `active_frame_id`, which the Writers' Room routes never set and the
    streamed worker thread starts with empty -- so every Room reader that
    took an explicit frame (plans, packages, needs, the registry) read that
    frame while the scene beside them was the PRESENT frame's, and the
    apply functions then wrote frame X from a scene that was not X's. None
    keeps the ambient frame, which is what a route inside `_era` wants.
    """
    from core.db import active_frame_id, q
    from story.scene import get_scene
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if frame_id is None:
        return get_scene(cid, chat) or {}
    token = active_frame_id.set(frame_id)
    try:
        return get_scene(cid, chat) or {}
    finally:
        active_frame_id.reset(token)


def _text(value, limit):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _rooms(scene):
    """The scene's rooms, dict-valued only (`world.regions.scene_rooms`)."""
    from world.regions import scene_rooms
    return scene_rooms(scene)


def containment(scene):
    """``{room_id: holder}`` for every room that is the inside of a body
    (`parent_entity`). Such a room is a fact about the holder: it is joined
    to the holder's room and to nothing else, and is never a place the plan
    holds, a route passes through, or a frontier gap."""
    return {rid: str(room["parent_entity"])
            for rid, room in _rooms(scene).items() if room.get("parent_entity")}


def _anchored(scene):
    """``{entity_id: room_id}`` for every anchor a room declares -- the
    second way a thing is placed (the first is a `positions` row).
    `world.regions.scene_anchors`, which the region of an inside is read
    through as well."""
    from world.regions import scene_anchors
    return scene_anchors(scene)


def holder_room(scene, holder, anchored=None):
    """Where the body a room is inside of stands: by identity, by anchor,
    or by a bare position row under the holder's name
    (`world.regions.holder_room_of`, the one answer both readers use)."""
    from world.regions import holder_room_of
    return holder_room_of(scene, holder, anchored)


def _registry(cid):
    """Every `room_registry` row of the story: ``{uid: {name, holder,
    planned (the spec or None), retired (bool), region}}``."""
    from core.db import q
    from world.regions import registry_row_region
    out = {}
    for row in q("SELECT room_uid, name, parent_entity, payload, retired_turn_id "
                 "FROM room_registry WHERE chat_id=?", (cid,)):
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        planned = payload.get("planned") if isinstance(payload, dict) else None
        out[str(row["room_uid"])] = {
            "name": str(row["name"] or row["room_uid"]),
            "holder": str(row["parent_entity"]) if row["parent_entity"] else None,
            "planned": planned if isinstance(planned, dict) else None,
            "retired": row["retired_turn_id"] is not None,
            "region": registry_row_region(payload),
        }
    return out


def _region_of(scene, rid, registry):
    """The region a room reports: the scene's answer for a live room (an
    inside answering with its holder's room's), the registry's for a
    planned or retired one (`world.regions.room_region`)."""
    from world.regions import room_region
    return room_region(scene, rid, {
        uid: row["region"] for uid, row in registry.items() if row.get("region")})


def group_by_region(rows):
    """Order index rows by region, then by distance within it. A region's
    rank is its nearest room's hops -- the cast's region first, a region no
    reachable room stands in last, ties by region id -- and within a region
    the order is hops then id, unreachable last. Rooms in no region form
    one group under the same rule, which is what keeps a story with no
    regions in exactly the order it had. Sorts in place; returns rows."""
    rank = {}
    for row in rows:
        key = row.get("region")
        hops = row.get("hops")
        here = (0, hops) if hops is not None else (1, 0)
        if key not in rank or here < rank[key]:
            rank[key] = here
    rows.sort(key=lambda r: (
        rank[r.get("region")], r.get("region") or "",
        r["hops"] is None, r["hops"] or 0, r["id"]))
    return rows


def _statuses(scene, registry):
    """``{room_id: status}`` for every id the story knows. The scene wins:
    a room the frame holds is live whatever the registry says of it."""
    out = {}
    for uid, row in registry.items():
        if row["retired"]:
            out[uid] = STATUS_RETIRED
        elif row["planned"] is not None:
            out[uid] = STATUS_PLANNED
    for rid in _rooms(scene):
        out[rid] = STATUS_LIVE
    return out


def room_graph(cid, scene, extra_edges=None):
    """``{room_id: {room_id}}``: the graph `hops` are counted over, and the
    ONE answer to "what can the story walk between". The edges a body could
    cross (`_ROUTE_MEMORY_BARRIERS` -- passable, plus a closed door, which a
    body simply opens; directional where an edge says so) UNION the plan's
    topology (undirected: a planned stub is a room the Director furnishes on
    entry). A contained room is joined to its holder's room in both
    directions and has no other edge in either direction -- it is where the
    world put a body, not a way anywhere.

    EVERY NODE IS AN ID. `planned_context` renders the plan's edges by NAME
    for a reader, and a walk over names reached nothing planned.

    ``extra_edges`` is an iterable of ``(a, b)`` pairs a caller holds that
    the world does not yet: the adjacency a draft package's own `plan_rooms`
    declares, joined undirected like the plan's. It is the only thing a
    second reader ever needed of its own, which is why there is no second
    reader: `room_tools._t_inspect_route` and `plot_packages._reach_warning`
    each rebuilt this walk and each answered differently -- the route graph
    left a contained room out of the world's edges but kept it in the plan's,
    and the reach check undirected a one-way chute and joined an inside to
    every room its holder's edges name (B21, review 2026-09-07).

    A CLOSED DOOR IS NOT A WALL. This counted over `passable_neighbors`,
    which means "passable THIS BEAT", so a house whose rooms are joined by
    shut doors read as a house of unreachable rooms and the Room's map put
    most of it beyond the frontier (PX15, masque run, 2026-09-05). The
    question a hop count answers is what the story can REACH.
    """
    from world.spatial import _ROUTE_MEMORY_BARRIERS, neighbor_map
    from world.structure import planned_topology

    contained = containment(scene)
    graph = {}
    for k, vs in neighbor_map(scene, _ROUTE_MEMORY_BARRIERS,
                              directional=True).items():
        if str(k) in contained:
            continue
        graph.setdefault(str(k), set()).update(
            str(v) for v in vs if str(v) not in contained)
    for rid, others in planned_topology(cid).items():
        if rid in contained:
            continue
        for other in others:
            if other in contained:
                continue
            graph.setdefault(rid, set()).add(other)
            graph.setdefault(other, set()).add(rid)
    for a, b in (extra_edges or ()):
        a, b = str(a), str(b)
        if a in contained or b in contained or not a or not b:
            continue
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)
    anchored = _anchored(scene)
    for rid, holder in contained.items():
        graph.setdefault(rid, set())
        where = holder_room(scene, holder, anchored)
        if where and where != rid:
            graph[rid].add(where)
            graph.setdefault(where, set()).add(rid)
    return graph


def room_hops(cid, scene, starts, graph=None):
    """``{room_id: hops}`` by breadth-first search from every room in
    ``starts`` (each at 0) over `room_graph`. Rooms the search never
    reaches are absent."""
    graph = room_graph(cid, scene) if graph is None else graph
    hops = {str(s): 0 for s in starts if s}
    frontier = sorted(hops)
    depth = 0
    while frontier:
        depth += 1
        nxt = []
        for node in frontier:
            for other in sorted(graph.get(node, ())):
                if other not in hops:
                    hops[other] = depth
                    nxt.append(other)
        frontier = nxt
    return hops


def cast_rooms(scene):
    """The rooms the cast occupies: every room a `positions` row places a
    BODY in. A position row keyed by a scene entity of an inanimate kind (a
    vehicle standing in a shaft, a crate on a floor) places a thing, not a
    cast member, and is not a place the cast is; a row with no entity record
    behind it, or an animate one, is a body."""
    from llm.schemas import _ANIMATE_ENTITY_KINDS
    scene = scene or {}
    entities = scene.get("entities") or {}
    out = set()
    for who, room in (scene.get("positions") or {}).items():
        if not str(room or ""):
            continue
        ent = entities.get(str(who))
        kind = str(ent.get("kind") or "").strip().casefold() if isinstance(ent, dict) else ""
        if kind and kind not in _ANIMATE_ENTITY_KINDS:
            continue
        out.add(str(room))
    return sorted(out)


def room_index(cid, frame_id, scene=None):
    """One row per room the story knows -- live, planned or retired -- with
    its holder and its distance from the cast. The contract is in the
    module docstring."""
    scene = read_scene(cid, frame_id) if scene is None else (scene or {})
    rooms = _rooms(scene)
    registry = _registry(cid)
    statuses = _statuses(scene, registry)
    hops = room_hops(cid, scene, cast_rooms(scene))
    rows = []
    for rid, status in statuses.items():
        room = rooms.get(rid) or {}
        reg = registry.get(rid) or {}
        holder = room.get("parent_entity") or reg.get("holder")
        rows.append({
            "id": rid,
            "name": str(room.get("name") or reg.get("name") or rid),
            "status": status,
            "holder": str(holder) if holder else None,
            "region": _region_of(scene, rid, registry),
            "hops": hops.get(rid) if status != STATUS_RETIRED else None,
        })
    return group_by_region(rows)


# ---------------------------------------------------------------------------
# The slice
# ---------------------------------------------------------------------------

def _things_by_room(scene, occupants):
    """``{room_id: [thing rows]}``: every scene entity standing in a room by
    a position row or as one of its anchors, bodies excluded."""
    from llm.schemas import _ANIMATE_ENTITY_KINDS
    from world.spatial import room_of

    anchored = _anchored(scene)
    out = {}
    for eid, ent in (scene.get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        where = room_of(scene, str(eid)) or anchored.get(str(eid)) or ""
        if not where:
            continue
        label = str(ent.get("name") or eid).strip()
        if str(ent.get("kind") or "").strip().casefold() in _ANIMATE_ENTITY_KINDS:
            continue
        if any(label.casefold() == str(who).strip().casefold()
               for who in occupants.get(where, ())):
            continue
        row = {"id": str(eid), "name": label, "kind": ent.get("kind") or ""}
        plan = ent.get("plan_ref")
        if isinstance(plan, dict) and plan.get("uid"):
            row["plan_ref"] = str(plan["uid"])
        out.setdefault(where, []).append(row)
    return out


def _plan_here(cid, frame_id, room_ids):
    """``{room_id: plan_here}`` for the rooms asked about, each read once."""
    from story.plot_packages import operation_rooms, packages
    from world.planned_entities import planned_entities
    from world.planning_needs import need_identity, open_planning_needs

    wanted = {str(r) for r in room_ids}
    out = {rid: {"planned_entities": [], "needs": [], "package_ops": []}
           for rid in wanted}
    for plan in planned_entities(cid, frame_id).values():
        where = str((plan.get("brief") or {}).get("where") or "")
        if where in out:
            out[where]["planned_entities"].append({
                "uid": plan["uid"], "kind": plan["kind"], "name": plan["name"],
                "rendered": bool(plan.get("rendered"))})
    identities = {need_identity("room", rid): rid for rid in wanted}
    for need in open_planning_needs(cid, frame_id):
        rid = identities.get(need["identity"])
        if rid is None:
            surface_room = str((need.get("surface") or {}).get("room") or "")
            rid = surface_room if surface_room in out else None
        if rid is not None:
            # THE REASON IS THE FIELD THAT SAYS WHAT THE NEED IS.
            # `kind` is a closed set of three (`NEED_KINDS`) and the register
            # carries five reasons, so everything that is neither a room nor
            # a person is filed as a `thing` -- which is what the Room was
            # shown, with the subject beside it. Measured on the owner's live
            # stories 2026-09-06: 8 of 9 open needs are `setting_fact`, whose
            # subject is a SENTENCE by nature ("A Euclid-class containment
            # breach has occurred at Site-17"), so the Room read nine props
            # to author and eight of them were facts about the world. The
            # record has always carried the reason; only the two summaries
            # dropped it.
            out[rid]["needs"].append({"uid": need["uid"], "kind": need["kind"],
                                      "reason": need["reason"],
                                      "subject": need["subject"]})
    for pkg in packages(cid, frame_id).values():
        if pkg["status"] == "retired" or pkg["spoiler_policy"] == "sealed":
            continue
        for index, op in enumerate(pkg["operations"]):
            # THE ROOMS AN OPERATION NAMES ARE THE PACKAGE MODULE'S ANSWER,
            # never a key list of this module's own: the two disagreed, and
            # neither read a creature's lair (REVIEW_2026-09-07 B20).
            for rid in operation_rooms(op) & wanted:
                out[rid]["package_ops"].append({
                    "package": pkg["uid"], "title": _text(pkg["title"], 80),
                    "status": pkg["status"], "index": index, "op": op["op"]})
    return out


def room_slices(cid, frame_id, room_ids, scene=None):
    """`room_slice` for several rooms, the scene-wide work done once. Ids
    the story does not know are skipped; the order is the caller's."""
    from world.regions import region_name, region_registry
    from world.spatial import effective_adjacent
    from world.structure import planned_room_brief

    scene = read_scene(cid, frame_id) if scene is None else (scene or {})
    rooms = _rooms(scene)
    registry = _registry(cid)
    statuses = _statuses(scene, registry)
    wanted = [str(r) for r in room_ids if str(r) in statuses]
    if not wanted:
        return []
    regions = region_registry(cid, frame_id)
    positions = scene.get("positions") or {}
    occupants = {}
    for who, room in positions.items():
        occupants.setdefault(str(room), []).append(str(who))
    things = _things_by_room(scene, occupants)
    stations = scene.get("stations") if isinstance(scene.get("stations"), dict) else {}
    attire = scene.get("attire") if isinstance(scene.get("attire"), dict) else {}
    briefs = planned_room_brief(cid, scene, wanted)
    plans = _plan_here(cid, frame_id, wanted)

    def name_of(rid):
        room = rooms.get(rid) or {}
        return str(room.get("name") or (registry.get(rid) or {}).get("name") or rid)

    out = []
    for rid in wanted:
        room = rooms.get(rid) or {}
        reg = registry.get(rid) or {}
        status = statuses[rid]
        holder = room.get("parent_entity") or reg.get("holder")
        exits = {}
        if status == STATUS_LIVE:
            for edge in effective_adjacent(scene, rid):
                if not isinstance(edge, dict) or not edge.get("to"):
                    continue
                to = str(edge["to"])
                exits.setdefault(to, {"to": to, "name": name_of(to),
                                      "barrier": edge.get("barrier"),
                                      "dir": edge.get("dir"),
                                      "status": statuses.get(to)})
        for edge in (briefs.get(rid) or {}).get("exits") or ():
            to = str(edge.get("to") or "")
            if to and to not in exits:
                exits[to] = {"to": to, "name": name_of(to),
                             "barrier": edge.get("barrier"), "dir": edge.get("dir"),
                             "status": statuses.get(to)}
        region = _region_of(scene, rid, registry)
        out.append({
            "id": rid, "name": name_of(rid), "status": status,
            "holder": str(holder) if holder else None,
            "region": region,
            "region_name": region_name(regions, region) if region else None,
            "description": _text(room.get("desc") or room.get("description"),
                                 DESCRIPTION_CHARS),
            "exits": list(exits.values()),
            # `entry_for`: the occupant's name comes off `positions`, whose
            # spelling of a body need not match the wardrobe's -- a bare
            # `.get` blanked the attire column for a dressed body (2026-09-07
            # B5).
            "occupants": [{"name": who, "station": stations.get(who),
                           "attire": attire_entry_for(attire, who) or None}
                          for who in occupants.get(rid, [])],
            "things": things.get(rid, []),
            "planned_stub": briefs.get(rid),
            "plan_here": plans[rid],
        })
    return out


def attire_summary(entry):
    """The attire ledger's own summary of itself -- its `wearing` and `state`
    lists -- without the per-region garment table. The slice carries the
    ledger AS STORED for a reader that renders a body (a browser); a reader
    that plans a neighbourhood (the room tool, under `TOOL_RESULT_CHARS`)
    wants what a body has on and how, not every region's garments. Measured
    on chat 115: five slices with the ledger whole were 13,580 characters,
    over the 12,000 cap on their own. None when the body has no entry."""
    if not isinstance(entry, dict):
        return None
    return {"wearing": list(entry.get("wearing") or []),
            "state": list(entry.get("state") or [])}


def room_slice(cid, frame_id, room_id, scene=None):
    """The whole of one room, or None when no room of that id is known.
    The contract is in the module docstring."""
    rows = room_slices(cid, frame_id, [str(room_id)], scene)
    return rows[0] if rows else None
