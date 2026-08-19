"""The durable per-mind place graph, and the route/dead-end experience one
committed beat of standing somewhere earns a character.

Extracted verbatim from commit.py, which re-exports every name here.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

from world.spatial import (_PASSABLE_BARRIERS, normalize_barrier,
                     normalize_bearing, opposite_bearing,
                     passable_path, rooms_adjacent, visible_adjacent_rooms)


#: The edges a remembering mind records as routes: a way through, now or by
#: opening it. This is `spatial_barriers._ROUTE_MEMORY_BARRIERS`, spelled
#: from the facade's exports only because `world/spatial.py` does not yet
#: re-export the predicate; the two are pinned byte-identical by
#: tests/test_world_model_route_memory.py, and the moment the facade line
#: lands this local spelling should collapse into the import. The full
#: judgement (locked doors, `unknown`, why neither `_SIGHT_BARRIERS` nor
#: `_PASSABLE_BARRIERS` alone is right) lives on the canonical set.
_ROUTE_MEMORY_BARRIERS = frozenset(_PASSABLE_BARRIERS) | {"closed_door"}


# How much of a body's own route it carries. Bounded because it rides
# chat_chars.state, and because a route from four hundred beats ago is not
# something anyone recalls as a route.
VISITED_ROOMS_CAP = 60

# How far back a satisfied intention credits the route, and how much weight one
# room can accrue. Bounded because a goal closed after forty beats says little
# about the room walked through on beat one, and because a route that worked
# ten times should not become impossible to abandon when the world changes.
ROUTE_CREDIT_WINDOW = 25
ROUTE_CREDIT_CAP = 5

# How many places one mind's durable map may hold. Unlike VISITED_ROOMS_CAP
# this is not a recency window -- the graph is the thing that must survive a
# long walk -- but it is still a MEMORY, and an unbounded one would grow with
# every campaign forever. Eviction is by (last_turn, visits): the places
# forgotten first are the ones least revisited and longest unseen, which is
# forgetting, and forgetting is the point.
PLACE_GRAPH_NODE_CAP = 400


def update_place_graph(graph, scene, here_rid, turn_idx, came_from=None,
                       visible=None):
    """Fold one committed beat of standing in a room into this character's
    durable place graph ({"nodes": {rid: ...}, "edges": {rid: {rid: ...}}} on
    chat_chars.state.place_graph).

    Firewall discipline, in order of temptation:

    * Nodes/edges come ONLY from (a) the room the character is standing in --
      its doorways are perceivable from inside, whichever side declared the
      edge; (b) the step they just took (`came_from`, guarded by
      rooms_adjacent so a teleport/carry mints no walked edge); (c) the
      `visible` list, which is `visible_adjacent_rooms` output for a room
      they actually stood in. A room seen through a doorway contributes its
      NAME and its visible closedness and nothing else: `_onward_exits`
      returns counts and bearings, never destinations, so the neighbour's own
      doorways are structurally unavailable here -- do not "fix" that by
      reading scene["rooms"][neighbour]["adjacent"], which would quietly turn
      the remembered map into the objective one.
    * The standing room is also the ONLY place objective state may correct
      the graph: a remembered doorway of THIS room that present perception
      shows absent or walled is stamped `disproven` (both directions, since a
      doorway is one doorway). A room absent from the scene entirely -- moved
      on from, retired, destroyed -- keeps its nodes and edges untouched: the
      character learns a place is gone by standing where it was, not by the
      registry telling their memory.
    * Nothing here reads another character's state, and nothing writes
      anything the character did not walk, see, or step through.

    `basis` is "walked" (stood there) or "seen" (looked into it). "told" is an
    accepted value that this writer will not produce, and that is a decision
    rather than a gap: the approved design derived hearsay edges from
    `stated_fact` place claims, and implementing it showed that deriving
    CONNECTIVITY from free text means text-mining it -- the non-deterministic
    derivation this engine refuses everywhere else. A testimony writer needs a
    structured claim naming the two places and the direction, not a parser over
    prose. The affordance ledger one layer over DOES write `told`
    (`world/place_purpose.py`, mirroring `stated_fact` hypotheses onto nodes
    resolved by name): testimony can say what a place you already know is FOR;
    it cannot mint the place. Recorded in `docs/UNBUILT.md` 6.5, not 1.52 --
    this is a design note residual, not an open defect.
    Mutates and returns the normalized graph.
    """
    graph = graph if isinstance(graph, dict) else {}
    nodes = graph.get("nodes")
    nodes = nodes if isinstance(nodes, dict) else {}
    edges = graph.get("edges")
    edges = edges if isinstance(edges, dict) else {}
    graph = {"nodes": nodes, "edges": edges}
    if not here_rid:
        return graph
    here_rid = str(here_rid)
    turn_idx = int(turn_idx or 0)
    rooms = (scene or {}).get("rooms") or {}

    def _node(rid, name=None, basis="seen"):
        rec = nodes.get(rid)
        if not isinstance(rec, dict):
            rec = {"basis": basis, "visits": 0, "first_turn": turn_idx}
            nodes[rid] = rec
        if basis == "walked":
            rec["basis"] = "walked"          # never downgraded
        rec.setdefault("basis", basis)
        if name:
            rec["name"] = str(name)
        rec["last_turn"] = turn_idx
        return rec

    def _confirm(a, b, bearing=None, taken=False):
        side = edges.get(a)
        if not isinstance(side, dict):
            side = {}
            edges[a] = side
        rec = side.get(b)
        if not isinstance(rec, dict):
            rec = {}
            side[b] = rec
        rec.pop("disproven", None)
        rec["last_confirmed"] = turn_idx
        if bearing:
            rec["bearing"] = bearing
        if taken:
            rec["taken"] = True
            rec["basis"] = "walked"
        else:
            rec.setdefault("basis", "seen")
        return rec

    here_room = rooms.get(here_rid) or {}
    here_node = _node(here_rid, name=here_room.get("name"), basis="walked")
    if came_from or not here_node.get("visits"):
        here_node["visits"] = int(here_node.get("visits") or 0) + 1

    # Every doorway of the standing room, from either side's declaration.
    # DOORWAY means a route-memory edge, not merely "not a wall": the old
    # `!= "wall"` reading minted a walkable graph edge through a `window`,
    # `bars`, a `one_way_window` and even a `separated` non-adjacency --
    # everything you can see and cannot walk -- and `_frontier_hops` then
    # rendered the false edge to its owner as a specific remembered distance
    # (docs/UNBUILT.md 1.6). Narrowing this filter is also the retraction
    # path: a glass edge remembered from before is no longer in `doorways`,
    # so the contradiction pass below stamps it `disproven` the next time
    # the character stands here.
    doorways = {}
    for e in here_room.get("adjacent") or []:
        if isinstance(e, dict) and e.get("to") \
                and normalize_barrier(e.get("barrier")) \
                in _ROUTE_MEMORY_BARRIERS:
            doorways.setdefault(str(e["to"]), normalize_bearing(e.get("dir")))
    for oid, other in rooms.items():
        oid = str(oid)
        if oid == here_rid or oid in doorways or not isinstance(other, dict):
            continue
        for e in other.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == here_rid \
                    and normalize_barrier(e.get("barrier")) \
                    in _ROUTE_MEMORY_BARRIERS:
                doorways.setdefault(
                    oid, opposite_bearing(normalize_bearing(e.get("dir"))))
                break
    for to_rid, bearing in doorways.items():
        _confirm(here_rid, to_rid, bearing=bearing)
        far = (edges.get(to_rid) or {}).get(here_rid)
        if isinstance(far, dict):
            far.pop("disproven", None)

    # Contradiction correction -- standing room only. A doorway remembered
    # here that present perception does not show is disproven, both ways.
    for to_rid, rec in list((edges.get(here_rid) or {}).items()):
        if to_rid in doorways or not isinstance(rec, dict):
            continue
        rec["disproven"] = turn_idx
        far = (edges.get(to_rid) or {}).get(here_rid)
        if isinstance(far, dict):
            far["disproven"] = turn_idx

    if came_from and str(came_from) != here_rid \
            and rooms_adjacent(scene, came_from, here_rid):
        _confirm(str(came_from), here_rid, taken=True)

    for item in visible or []:
        if not isinstance(item, dict):
            continue
        rid_seen = str(item.get("room_id") or "")
        if not rid_seen or rid_seen == here_rid:
            continue
        rec = _node(rid_seen, name=item.get("room_name"), basis="seen")
        onward = item.get("onward_exits")
        if onward == 0:
            rec["closed"] = True
        elif isinstance(onward, int) and onward > 0:
            rec.pop("closed", None)
        # The NODE above is sight's to give: a room seen through glass is a
        # place the character now knows exists. The EDGE is not -- sight
        # crosses a window/bars/one-way pane that a body never will, and
        # this unconditional confirm was the third writer minting a walkable
        # remembered route through them (`visible` is `visible_adjacent_rooms`
        # output, which walks `_SIGHT_BARRIERS`). Only a route-memory doorway
        # earns the edge.
        if rid_seen in doorways:
            _confirm(here_rid, rid_seen, bearing=doorways.get(rid_seen))

    overflow = len(nodes) - PLACE_GRAPH_NODE_CAP
    if overflow > 0:
        order = sorted(
            (rid for rid in nodes if rid != here_rid),
            key=lambda rid: (
                int((nodes[rid] or {}).get("last_turn") or 0)
                if isinstance(nodes[rid], dict) else 0,
                int((nodes[rid] or {}).get("visits") or 0)
                if isinstance(nodes[rid], dict) else 0))
        evicted = set(order[:overflow])
        for rid in evicted:
            nodes.pop(rid, None)
            edges.pop(rid, None)
        for side in edges.values():
            if isinstance(side, dict):
                for gone in [b for b in side if b in evicted]:
                    side.pop(gone, None)
    return graph


def record_spatial_experience(st, sc, here_room, turn_idx):
    """Everything one committed beat of standing somewhere earns a character:
    the route window, the exits of rooms stood in, visibly-closed chambers,
    and the durable place graph. Mutates and returns `st`.

    `visited_rooms` stays a bounded RECENCY window (the loop detectors need
    it), but it is no longer allowed to bound knowledge: `known_exits` used
    to be pruned to rooms still inside the window, which erased spatial
    knowledge past VISITED_ROOMS_CAP -- and worse than erased it, since
    _frontier_beyond read a room with no recorded exits as "never stood
    there, everything past it is potentially new". Forgetting made stale
    ground look PROMISING, on maze runs that sit exactly on the cap.
    Durability now belongs to place_graph, and the legacy keys follow its
    memory (bounded by the same eviction) rather than the window's.

    Persistence decision (docs/guides/DATABASE.md checklist): all of this rides the
    chat_chars.state JSON blob, which checkpoints snapshot/restore whole
    (checkpoints.snapshot_state/restore), chat_archive exports/imports
    verbatim, and the branch path copies row-for-row -- so no schema, remap,
    or archive change is needed. Room ids are frame-scoped scene rids, which
    those paths preserve as-is.
    """
    if not here_room:
        return st
    visited = [
        r for r in (st.get("visited_rooms") or [])
        if isinstance(r, str) and r
    ]
    came_from = visited[-1] if visited else None
    if came_from == here_room:
        came_from = None
    else:
        # A body that RAN crossed several rooms this beat, and has been in
        # every one of them. Recording only where they stopped would leave
        # holes in their map exactly where their feet went, and worse than
        # holes: the place graph would mint no walked edge at all (came_from
        # is not adjacent), so a corridor they had sprinted end to end would
        # keep reading as untrodden and pull them back down it.
        #
        # Reconstructed rather than trusted from the Director: the rooms
        # between are a deterministic fact about the scene, and asking a model
        # to list them is asking it to be right about geometry -- which is the
        # thing it is measurably worst at (see A11's bearing errors).
        #
        # A move with NO passable route is a teleport, a carry, or a vehicle,
        # and mints nothing: the character learns a place by being carried
        # through it about as well as a parcel does.
        crossed = passable_path(sc, came_from, here_room) if came_from else []
        for room in (crossed[:-1] if crossed else []):
            if room and (not visited or visited[-1] != room):
                visited.append(room)
        visited.append(here_room)
        if crossed and len(crossed) > 1:
            came_from = crossed[-2]
    st["visited_rooms"] = visited[-VISITED_ROOMS_CAP:]
    # The exits visible FROM a room they actually stood in. Not oracle
    # knowledge: standing in a room is how you see its doorways. ROUTE-MEMORY
    # edges only, the same filter the place graph applies: this legacy ledger
    # recorded every declared adjacency including solid `wall` edges, and
    # `_annotate_known_exits` merges it into the same BFS adjacency the graph
    # feeds -- so without the filter here, a wall or a pane of glass simply
    # re-entered the remembered map through the older door (docs/UNBUILT.md
    # 1.6's scope note). Overwritten wholesale on each standing, so a stale
    # wall edge written before this filter heals on the next visit.
    known = st.get("known_exits")
    if not isinstance(known, dict):
        known = {}
    room = (sc.get("rooms") or {}).get(here_room) or {}
    known[here_room] = sorted({
        str(e.get("to")) for e in (room.get("adjacent") or [])
        if isinstance(e, dict) and e.get("to")
        and normalize_barrier(e.get("barrier")) in _ROUTE_MEMORY_BARRIERS
    })
    # Which of those neighbours he could SEE were closed -- the same fact
    # visible_adjacent_rooms reports live, written down so the frontier test
    # can tell "a door I have not taken" from "a route I have not taken".
    try:
        visible = visible_adjacent_rooms(sc, here_room) or []
    except Exception:
        visible = []
    dead = st.get("known_dead_ends")
    dead = set(dead) if isinstance(dead, list) else set()
    for item in visible:
        if isinstance(item, dict) and item.get("onward_exits") == 0:
            dead.add(str(item.get("room_id")))
    st["known_dead_ends"] = sorted(dead)
    st["place_graph"] = update_place_graph(
        st.get("place_graph"), sc, here_room, turn_idx,
        came_from=came_from, visible=visible)
    # Legacy keys bounded by the graph's memory, not the recency window.
    remembered = set(st["place_graph"]["nodes"]) | set(st["visited_rooms"])
    st["known_exits"] = {k: v for k, v in known.items() if k in remembered}
    st["known_dead_ends"] = [r for r in st["known_dead_ends"]
                             if r in remembered]
    return st
