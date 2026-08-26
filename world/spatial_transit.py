# spatial_transit.py
"""parent_entity-linked rooms: derived dock edges, inferred body enclosures, and
nesting-aware ambient scope."""

from typing import Optional

from world.spatial_barriers import (_AMBIENT_BARRIERS, neighbor_map,
                                    normalize_barrier)
from world.spatial_identity import _ci_get


# ---------------------------------------------------------------------------
# Moving rooms / transit: derived dock edges.
#
# The interior<->exterior doorway of a parent_entity-linked room (an elevator
# car, a ship cabin, a carried container) is NOT a static fact: it is derived
# from where the entity currently IS (its exterior position) and its transit
# state (docked/sealed/in transit, hatch open/closed). Storing it as an
# ordinary adjacency edge -- which the establish/mapping prompts historically
# forced at creation -- meant nothing ever updated the edge when the entity
# moved or sealed, leaving a stale portal to the departure room (live
# instance: an elevator narrated as sealed and descending whose room kept an
# open_door edge onto the smoke-filled hallway it left). These functions
# recompute that doorway deterministically from the entity's own structured
# state, joining the infer_vehicle_zones/infer_companion_carry family of
# mechanical follow-throughs: the model authors WHAT the entity is doing
# (state.transit / state.link, its position); code derives the adjacency.
#
# Pure function of the scene, idempotent, run from merge_scene_with_diff so
# every consumer (commit preparation, mid-turn perception merges) sees the
# same derived edges without any reader changes.
# ---------------------------------------------------------------------------

# Phases during which an entity's interior has NO doorway to the outside
# world (beyond an optional route_room -- the shaft/ocean/sky it moves
# through). "arriving" keeps the hatch shut against the destination until
# the director docks it.
_TRANSIT_CLOSED_PHASES = {"sealed", "in_transit"}

def _transit_state(entity) -> Optional[dict]:
    """entity.state.transit if present and well-formed:
    {phase: docked|sealed|in_transit|arriving, hatch: open|closed|locked,
     destination_room?, eta_seconds?, route_room?}."""
    if not isinstance(entity, dict):
        return None
    state = entity.get("state")
    transit = state.get("transit") if isinstance(state, dict) else None
    return transit if isinstance(transit, dict) else None

# What an entity's enclosure is MADE of, which decides what it still lets
# through. `enclosure` sits beside portable/container as a structural fact: a
# glass case and a strongbox are both closed, and only one of them is opaque.
#
# It used to describe only the CLOSED state, on the assumption that an open way
# in is an open way to look in. That holds for a lid or a door and fails for
# every soft or draped opening, where the way in is opaque in both states --
# `membrane` is that case, and the one enclosure whose OPEN doorway is not
# see-through.
CONTAINER_ENCLOSURES = ("opaque", "transparent", "barred", "membrane")


def _is_body_entity(scene: dict, eid: str, ent: dict) -> bool:
    """Is this entity a body rather than a vehicle, room-sized object or box.

    Asked of the scene alone so the dock-edge derivation stays a pure function.
    Bodies are the things that WEAR something and the things that have a SIZE
    relative to their own baseline; a lift car, a ship and a crate have
    neither. Checked across every scene on disk when this was written, the
    split was exact: every vehicle/structure/container interior scored false
    on both, and every body scored true on `attire`.

    `container: true` is deliberately NOT the test -- it is absent on plenty of
    real vehicles, so it misclassifies them as bodies.
    """
    keys = [eid]
    if isinstance(ent, dict):
        keys.append(ent.get("name"))
        keys.extend(ent.get("aliases") or [])
    for source in ("attire", "scales"):
        table = scene.get(source) or {}
        if not isinstance(table, dict):
            continue
        for key in keys:
            key = str(key or "").strip()
            if key and _ci_get(table, key) is not None:
                return True
    return False


def _interior_rooms_of(scene: dict, eid: str) -> list:
    """Every room this entity's id is the `parent_entity` of, in scene order.

    The ROOM's own claim is the authority, exactly as `apply_transit_dock_edges`
    reads it: `entities[eid]["interior_rooms"]` is a convenience index kept in
    step by `sync_entity_interior_rooms`, never a second truth.
    """
    target = str(eid or "").strip()
    if not target:
        return []
    rooms = (scene or {}).get("rooms") or {}
    if not isinstance(rooms, dict):
        return []
    return [rid for rid, room in rooms.items()
            if isinstance(room, dict)
            and str(room.get("parent_entity") or "").strip() == target]


def sync_entity_interior_rooms(scene: dict) -> bool:
    """A room that names a parent entity is that entity's interior. Index it.

    ONE FACT, WRITTEN TWICE, and only one of the two spellings was ever
    derived. `rooms[rid]["parent_entity"]` is what the dock rewrite, the
    ambient scope and the enclosure gates all read; `entities[eid]
    ["interior_rooms"]` is what `infer_body_enclosures`, the Director's
    place-aware scopes, the room-registry rename pass and the destruction
    guard read. Nothing kept them in step, so a room authored with
    `parent_entity` and nothing else was an interior to half the engine and
    not an interior to the other half -- and the half that missed it includes
    the ONE function that makes a body's inside opaque by default. An
    interior nobody indexed therefore kept a see-through doorway, which is a
    leak outward: the room outside looked straight into the enclosure.

    ADD-ONLY. A stale id in `interior_rooms` names a room that may simply be
    absent this beat (retired, sealed away, not yet minted), and that list is
    read as a protection set at commit -- pruning here would let one merge
    unprotect a room another pass is about to restore. Idempotent; mutates.

    SCOPED TO BODIES, which is the class the missing index actually harmed.
    `interior_rooms` is not only an index: `agents/director_scopes` gates a
    Director specialist on it and `persist/commit_scene_state` folds it into
    the set of rooms the mapping stage may not prune. Filling it for an
    entity whose interior nobody had indexed is therefore a behaviour change,
    not a repair, and it must be one somebody asked for. Measured read-only
    against the author's live corpus: 53 rooms carry `parent_entity`, 15 of
    them across 13 chats were unindexed, and all 15 belong to non-bodies --
    lift cars, turbolifts, a ship, a police box. Indexing those would have
    switched a Director specialist on in five stories and made six stories'
    interiors permanently un-prunable, silently. A body's interior is the one
    that leaks when it is missed, because the enclosure default that makes
    flesh opaque reads this list and is itself body-scoped; so this derives
    exactly as far as that leak reaches, and every scene already on disk is
    left byte-identical. The wider "both spellings of one fact should agree
    for every entity" pass is a separate change with its own consequences
    (docs/UNBUILT.md).
    """
    rooms = (scene or {}).get("rooms") or {}
    entities = (scene or {}).get("entities") or {}
    if not isinstance(rooms, dict) or not isinstance(entities, dict):
        return False
    changed = False
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        owned = _interior_rooms_of(scene, eid)
        if not owned:
            continue
        if not _is_body_entity(scene, eid, ent):
            continue
        listed = ent.get("interior_rooms")
        if not isinstance(listed, list):
            listed = []
        known = {str(r) for r in listed}
        missing = [rid for rid in owned if str(rid) not in known]
        if missing:
            ent["interior_rooms"] = list(listed) + missing
            changed = True
    return changed


def _interior_entry_room(scene: dict, eid: str, ent=None):
    """The room a body entering this entity's interior arrives in, or None.

    The same precedence `apply_transit_dock_edges` already uses to decide
    which interior room carries the doorway, read rather than rewritten: a
    sole interior room IS the dock; otherwise the remembered `dock_exit`
    marker; otherwise whichever room still holds an edge out of the interior;
    otherwise the first one the scene lists, so the answer is deterministic
    rather than absent.
    """
    interior_ids = _interior_rooms_of(scene, eid)
    if not interior_ids:
        return None
    if len(interior_ids) == 1:
        return interior_ids[0]
    rooms = (scene or {}).get("rooms") or {}
    same = set(interior_ids)
    for rid in interior_ids:
        if (rooms.get(rid) or {}).get("dock_exit"):
            return rid
    for rid in interior_ids:
        for edge in (rooms.get(rid) or {}).get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("to") not in same:
                return rid
    return interior_ids[0]


def infer_body_enclosures(scene: dict) -> bool:
    """Default a BODY's interior to an opaque way in. Idempotent; mutates.

    The `membrane` enclosure only helps if something declares it, and the
    Director does not reliably do so -- observed live, on a fresh interior
    authored after the prompt asked for it. Relying on a model to remember a
    safety property every time is the wrong shape for this engine: flesh is
    opaque whether or not anyone remembered to say so.

    So an interior belonging to a body defaults to `membrane` when nothing was
    declared. An explicit `enclosure` always wins -- including `transparent`,
    so a deliberately see-through case stays authorable -- and vehicles,
    cabins and containers are untouched, keeping their see-through open
    doorway.
    """
    entities = scene.get("entities") or {}
    changed = False
    for eid, ent in entities.items():
        if not isinstance(ent, dict) or not ent.get("interior_rooms"):
            continue
        if str(ent.get("enclosure") or "").strip():
            continue                      # authored: never override
        if not _is_body_entity(scene, eid, ent):
            continue
        ent["enclosure"] = "membrane"
        changed = True
    return changed


def _open_enclosure_barrier(ent):
    """The doorway barrier for an OPEN entity interior.

    `open_door` for everything that opens by swinging a lid or a hatch aside,
    which is the historical behaviour and stays the default. A `membrane`
    enclosure is the exception: passable in both states and never see-through,
    so entering one hides its occupant instead of exposing them.
    """
    enclosure = str((ent or {}).get("enclosure") or "").strip().casefold()
    if enclosure == "membrane":
        return "membrane"
    return "open_door"


def _closed_enclosure_barrier(ent):
    """The doorway barrier for a CLOSED entity interior.

    Opaque is the default and the old behaviour. Transparent yields a window --
    a body sealed inside is visible to the room and can see out, without being
    reachable. Barred yields bars, which also carries sound.
    """
    enclosure = str((ent or {}).get("enclosure") or "").strip().casefold()
    if enclosure == "transparent":
        return "window"
    if enclosure == "barred":
        return "bars"
    return "closed_door"


def _link_state(entity) -> Optional[dict]:
    """entity.state.link if present and well-formed: a traversable link
    (portal, gate, wormhole) {rooms: [a, b], phase: open|closed} that, when
    open, derives an edge between two arbitrary rooms."""
    if not isinstance(entity, dict):
        return None
    state = entity.get("state")
    link = state.get("link") if isinstance(state, dict) else None
    if not isinstance(link, dict):
        return None
    rooms = link.get("rooms")
    if not isinstance(rooms, list) or len(rooms) != 2:
        return None
    return link

def _entity_exterior_room(scene: dict, eid: str, entity: dict) -> Optional[str]:
    """The room the entity itself currently occupies -- tolerating positions
    keyed by entity id, display name, or an alias (the same read tolerance
    merge_scene_with_diff's remove_entities path already applies)."""
    positions = scene.get("positions") or {}
    candidates = [eid]
    if isinstance(entity, dict):
        candidates.append(entity.get("name"))
        candidates.extend(entity.get("aliases") or [])
    for cand in candidates:
        cand = str(cand or "").strip()
        if cand and cand in positions:
            return positions[cand]
    return None

def apply_transit_dock_edges(scene: dict) -> bool:
    """Rewrite every parent_entity room's exterior adjacency to match
    f(entity position, entity.state.transit), and every state.link entity's
    derived portal edge to match its phase. Returns True when anything
    changed. Idempotent; mutates `scene` in place.

    Per entity with interior rooms:
    - docked (or no transit state) + hatch open  -> edge to the entity's
      exterior room, barrier open_door -- or membrane, when the entity's
      `enclosure` says the way in is opaque even standing open (an existing
      edge to that room otherwise keeps its authored barrier/distance when no
      hatch state overrides it);
    - docked + hatch closed/locked -> same edge, barrier closed_door;
    - sealed / in_transit -> exterior edges severed (a closed_door edge to
      transit.route_room only, when one is set -- the shaft/ocean/sky);
    - arriving -> closed_door edge to transit.destination_room.

    Which interior room carries the doorway is remembered via a `dock_exit`
    marker stamped on any interior room seen with an exterior edge (rooms
    carry arbitrary extra keys through merges untouched -- the zone-field
    precedent), so sealing and later re-docking restores the door to the
    same room. An entity's sole interior room is always the dock room.

    Only the canonical FORWARD edge (interior -> exterior) is kept; stale
    reverse edges from plain world rooms into the interior are stripped.
    Rooms that are themselves another entity's interior are never stripped
    -- a nested mover (a car on a ferry's vehicle deck) manages its own
    dock edge through its own entity's rewrite, which is what makes the
    model compose for nesting.
    """
    rooms = scene.get("rooms") or {}
    entities = scene.get("entities") or {}
    changed = False

    interiors: dict[str, list] = {}
    for rid, room in rooms.items():
        if isinstance(room, dict) and room.get("parent_entity"):
            interiors.setdefault(room["parent_entity"], []).append(rid)

    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue

        # --- traversable links (portals): derived edge between two rooms ---
        link = _link_state(ent)
        if link:
            a, b = (str(link["rooms"][0] or ""), str(link["rooms"][1] or ""))
            is_open = str(link.get("phase") or "open").casefold() == "open"
            for room in rooms.values():
                if not isinstance(room, dict):
                    continue
                adjacency = room.get("adjacent") or []
                kept = [e for e in adjacency
                        if not (isinstance(e, dict) and e.get("via_link") == eid)]
                if len(kept) != len(adjacency):
                    room["adjacent"] = kept
                    changed = True
            # `isinstance` on the room, not just `a in rooms`: this is the
            # one room WRITE in this function, and every read above it skips a
            # malformed record rather than raising. A non-dict room here took
            # the whole merge down instead.
            if (is_open and a != b and isinstance(rooms.get(a), dict)
                    and b in rooms):
                rooms[a].setdefault("adjacent", []).append({
                    "to": b, "barrier": "open_door",
                    "distance": str(link.get("distance") or "near"),
                    "via_link": eid,
                })
                changed = True

        interior_ids = interiors.get(eid)
        if not interior_ids:
            continue
        same = set(interior_ids)
        transit = _transit_state(ent)
        exterior = _entity_exterior_room(scene, eid, ent)

        # A container is not "in transit" -- a jar with a lid has a hatch and
        # no journey -- so the lid is read from state.hatch as well as from a
        # transit blob. Transit wins when both are present, since a vehicle
        # sealing for a journey is the stronger statement.
        entity_state = ent.get("state") if isinstance(ent.get("state"), dict) else {}
        hatch = str(
            (transit or {}).get("hatch")
            or entity_state.get("hatch")
            or "open"
        ).casefold()
        phase = str((transit or {}).get("phase") or "docked").casefold()
        # (target, barrier); barrier None = preserve whatever was authored.
        if transit is None and not entity_state.get("hatch"):
            # Nothing declared about the way in: keep whatever was authored
            # (barrier None), UNLESS the enclosure itself settles the question.
            # A membrane is opaque by construction, so an authored `open_door`
            # onto one is a description the enclosure contradicts -- and
            # preserving it is what let a body walk into an interior and stay
            # in plain view of the room outside.
            target = exterior
            barrier = (_open_enclosure_barrier(ent)
                       if str(ent.get("enclosure") or "").strip().casefold()
                       == "membrane" else None)
        elif transit is None:
            # A static container: the lid alone decides the doorway.
            target = exterior
            barrier = (_closed_enclosure_barrier(ent)
                       if hatch in ("closed", "locked")
                       else _open_enclosure_barrier(ent))
        elif phase in _TRANSIT_CLOSED_PHASES:
            target = str(transit.get("route_room") or "") or None
            barrier = "closed_door"
        elif phase == "arriving":
            target = str(transit.get("destination_room") or "") or exterior
            barrier = "closed_door"
        else:  # docked, or an unrecognized phase read conservatively as docked
            target = exterior
            barrier = (_closed_enclosure_barrier(ent)
                       if hatch in ("closed", "locked")
                       else _open_enclosure_barrier(ent))

        # No authoritative exterior at all (entity has no recorded position)
        # outside an explicitly closed phase: there is nothing to derive the
        # doorway FROM, and severing on missing data would cut off a cabin
        # whose authored edge is the only truth available. Leave it alone --
        # only an explicit sealed/in_transit state severs without a target.
        if target is None and phase not in _TRANSIT_CLOSED_PHASES:
            continue

        for rid in interior_ids:
            room = rooms[rid]
            adjacency = [e for e in (room.get("adjacent") or [])
                         if isinstance(e, dict)]
            interior_edges = [e for e in adjacency if e.get("to") in same]
            exterior_edges = [e for e in adjacency if e.get("to") not in same]
            if exterior_edges and not room.get("dock_exit"):
                room["dock_exit"] = True
                changed = True
            is_dock = bool(exterior_edges) or bool(room.get("dock_exit")) \
                or len(interior_ids) == 1
            new_adjacency = list(interior_edges)
            if is_dock and target:
                prev = next((e for e in exterior_edges if e.get("to") == target),
                            exterior_edges[0] if exterior_edges else None)
                if barrier is None:
                    resolved_barrier = normalize_barrier(
                        (prev or {}).get("barrier") or "open_door")
                else:
                    resolved_barrier = barrier
                new_adjacency.append({
                    "to": target, "barrier": resolved_barrier,
                    "distance": (prev or {}).get("distance") or "near",
                })
            if new_adjacency != adjacency:
                room["adjacent"] = new_adjacency
                changed = True

        # Strip stale reverse edges from plain world rooms into this
        # entity's interiors (the canonical edge is forward-only; spatial_rel
        # and visible_adjacent_rooms both resolve either direction). Another
        # entity's interior room is exempt -- see docstring (nesting).
        for orid, oroom in rooms.items():
            if orid in same or not isinstance(oroom, dict) \
                    or oroom.get("parent_entity"):
                continue
            adjacency = oroom.get("adjacent") or []
            kept = [e for e in adjacency
                    if not (isinstance(e, dict) and e.get("to") in same)]
            if len(kept) != len(adjacency):
                oroom["adjacent"] = kept
                changed = True

    return changed

# ---------------------------------------------------------------------------
# Nesting-aware ambient scope (movement/space Phase 1, item 5).
#
# Read-only helpers over the SCENE's containment structure (rooms'
# parent_entity + derived dock edges) -- deliberately NOT the lorebook
# graph: a currently_within link is retrieval bookkeeping and must never
# be read as perception authorization. These answer "whose ambience can
# legitimately reach this observer right now?" so location-scoped
# information does not leak into a sealed nested interior (the port must
# not color the inside of a sealed elevator).
# ---------------------------------------------------------------------------


def containment_chain(scene: dict, room_id: str) -> list:
    """Rooms from room_id outward through entity containment: the room
    itself, then -- for each enclosing parent_entity -- that entity's
    exterior room, and so on. [{'room': rid, 'entity': enclosing_eid|None}]
    ordered innermost-first. Cycle-safe."""
    chain = []
    seen = set()
    rooms = scene.get("rooms") or {}
    entities = scene.get("entities") or {}
    current = room_id
    while current and current not in seen:
        seen.add(current)
        room = rooms.get(current)
        eid = room.get("parent_entity") if isinstance(room, dict) else None
        chain.append({"room": current, "entity": eid})
        if not eid:
            break
        current = _entity_exterior_room(scene, eid, entities.get(eid) or {})
    return chain

def ambient_scope(scene: dict, room_id: str):
    """(rooms, open_to_world): the set of rooms whose ambient signal can
    reach room_id -- its connected component through `_AMBIENT_BARRIERS`
    (open, open_door and bars; sound carries through a cage, which is the
    whole reason that barrier exists) in either edge direction, in the
    current derived graph -- and
    whether that component reaches any room that is not an entity
    interior. With dock edges applied, a sealed vehicle's interior scopes
    to just itself (open_to_world False); docked with an open hatch it
    scopes out to the exterior. An unknown room is treated as open (no
    filtering on missing data)."""
    rooms = scene.get("rooms") or {}
    if not room_id or room_id not in rooms:
        return ({room_id} if room_id else set()), True
    graph = neighbor_map(scene, _AMBIENT_BARRIERS, known_rooms_only=True)
    seen = {room_id}
    queue = [room_id]
    while queue:
        current = queue.pop()
        for nxt in graph.get(current, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    open_to_world = any(
        not (isinstance(rooms.get(rid), dict)
             and rooms[rid].get("parent_entity"))
        for rid in seen
    )
    return seen, open_to_world
