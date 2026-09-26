# spatial_transit.py
"""parent_entity-linked rooms: derived dock edges, inferred body enclosures, and
nesting-aware ambient scope."""

from typing import Optional

from world.spatial_barriers import (_AMBIENT_BARRIERS, neighbor_map,
                                    normalize_barrier)
from world.spatial_identity import _ci_get, PositionsIndex, room_of_record


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

    THE ENGINE'S OWN PERSON RECORD IS ALSO EVIDENCE, and leaving it out made a
    body's standing depend on its WARDROBE. `agents/common.mint_cast_entities`
    writes `kind: "person"` for every cast member and the player, from the
    positions table, under the sheet's own spelling -- "a cast member is a body
    whether or not the opening wrote one" -- so that row is the engine saying
    what this is, not a model's free text. Without it an unclothed character
    scored false on both tests and `resolve_placement_target` classified her as
    an ANCHOR: a room fixture. Measured live (`google/gemini-3.8-flash`, the
    Millbrook run, 2026-09-17): a courier was handed a letter and the ferry
    fare, the Director emitted both transfers correctly, and both landed on the
    tap-room floor -- "possession: 'letter' reached 'char_lysa_fen''s room, but
    its exact placement needs a station naming a room anchor." She then spent
    the night waiting for payment she was holding, and crossed the water
    without the letter she was sent with. A person can hold a thing in their
    hand whatever they have on.

    `kind` is read HERE and nowhere else in this function on purpose. The word
    is free text a model writes, and the risk it carries is the reverse of this
    one -- a crate called a `person` -- which costs a crate that can hold
    something, against a person who could not.
    """
    if str((ent or {}).get("kind") or "").strip().casefold() == "person":
        return True
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

    EVERY HOLDER, since 2026-09-04. This was scoped to bodies for a month,
    because a body's interior is the one that LEAKS when the index is missed
    -- the enclosure default that makes flesh opaque reads this list and is
    itself body-scoped -- while widening it was a behaviour change nobody had
    asked for. Somebody has now asked, and the two readers that made it a
    behaviour change were measured rather than feared:

    * `agents/director_scopes` gates the destruction specialist on this list
      OR on a `kind` already in (vehicle, building, structure, ship, boat).
      So every holder the widening reaches whose kind names it is ALREADY
      through that gate and changes not at all; the delta is holders tagged
      `object`. Re-measured on the live corpus: 15 rooms across 14 chats gain
      an index, and the specialist newly switches on in exactly five stories
      (23-27), all of them the same shelter elevator tagged `object`. The
      original measurement predicted five and was right.
    * `persist/commit_scene_state` folds the list into the rooms mapping may
      not prune. That is the behaviour an interior WANTS: a room inside a
      holder is not a stray the map should reclaim while the holder stands.

    What the month of body-scoping cost is now visible: nothing indexes an
    interior for a holder that is not flesh, so `apply_transit_dock_edges` could
    move a body's inside and not a vehicle's. Chat 114's TARDIS console room
    was minted with neither spelling and its doorway was welded to the beach.

    ADD-ONLY still. A stale id in `interior_rooms` names a room that may
    simply be absent this beat (retired, sealed away, not yet minted), and
    that list is read as a protection set at commit -- pruning here would let
    one merge unprotect a room another pass is about to restore. Idempotent;
    mutates.
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

def _entity_exterior_room(scene: dict, eid: str, entity: dict, *,
                          index=None) -> Optional[str]:
    """The room the entity itself currently occupies: `room_of`'s answer for
    the record this pass already holds, so positions keyed by entity id,
    display name or alias resolve with the same case/space/script tolerance
    every other spatial reader gets.

    This walked the same three labels with exact-string `cand in positions`
    (review 2026-09-07, B18), which is `room_of` answered a second time and
    more narrowly: a car filed under `lift_car` against the id `Lift_Car` had
    no exterior room, so nothing derived its interior's doorway.

    `index` is the caller's one folded read of `positions` when it is asking
    this for every entity in the scene."""
    return room_of_record(scene, eid, entity, index=index)

def evict_self_contained_entities(scene: dict) -> list:
    """Nothing is inside itself. Returns the evictions, as (entity, from, to).

    A thing with an interior can be CARRIED, and a carried thing's position is
    derived from its holder (`derive_contained_positions`) -- so a holder who
    walks into that thing's own interior takes it in with them, and the record
    left behind says the ship is parked in its own console room. Measured in the
    owner's own story (chat 151, 2026-09-20): "The tardis followed them into the
    tardis." A police box was recorded `held` by a body (the binding defect
    `causal_program.bind_items` carried until the same day), that body stepped
    through its doors, and `positions.the_tardis` became
    `tardis_console_room` -- a room whose `parent_entity` is `the_tardis`.

    IT IS A PARADOX AND NOT A PREFERENCE, which is why this evicts rather than
    reports and waits: every reader downstream is entitled to assume the
    containment graph is acyclic. `_hiding_holders` is cycle-safe because a
    cycle there was already known to be possible; the POSITION graph had no
    equivalent, so `apply_transit_dock_edges` would go on deriving a doorway
    from an exterior room that is the interior it leads out of, and
    `containment_chain` would walk forever but for its own guard.

    WHERE IT GOES IS ITS OWN DOORWAY'S ANSWER. The dock room's exterior edge is
    the way out of the thing, so it is also where the thing is: a box whose door
    opens onto the beach is on the beach. That is a derivation, not a guess, and
    it is the same answer the dock pass already computed for the door. With no
    exterior edge to read -- an interior nothing has docked -- the position is
    DROPPED rather than invented, which leaves the thing unplaced and is the
    honest floor: unplaced is recoverable and a wrong room is not.

    Transitive, because the one-level test is the easy half: a car on a ferry's
    vehicle deck inside the car is the same error one hop out.
    """
    rooms = scene.get("rooms") if isinstance(scene, dict) else None
    positions = scene.get("positions") if isinstance(scene, dict) else None
    if not isinstance(rooms, dict) or not isinstance(positions, dict):
        return []
    entities = scene.get("entities") or {}
    index = PositionsIndex(positions)
    evicted = []
    # A ROOM IS NOT ADJACENT TO ITSELF, and this is where that gets cleaned up
    # because it is the same corruption one step on: with a thing inside its own
    # interior, `apply_transit_dock_edges` derives the doorway FROM that
    # interior, so the door comes to lead into the room it leads out of.
    # Measured in the owner's scene: `tardis_console_room.adjacent` read
    # `[{to: "tardis_console_room", barrier: "open_door"}]`, which is a way out
    # that arrives where it started. Dropped rather than repaired, because
    # nothing in the record says where it USED to point and a guess would be a
    # room nobody chose.
    for rid, room in rooms.items():
        if not isinstance(room, dict):
            continue
        adjacency = room.get("adjacent")
        if not isinstance(adjacency, list):
            continue
        kept = [e for e in adjacency
                if not (isinstance(e, dict) and str(e.get("to") or "") == str(rid))]
        if len(kept) != len(adjacency):
            room["adjacent"] = kept
    for eid, ent in list(entities.items()):
        if not isinstance(ent, dict):
            continue
        here = _entity_exterior_room(scene, str(eid), ent, index=index)
        if not here or here not in rooms:
            continue
        if not _encloses(scene, str(eid), here, rooms, entities, index):
            continue
        # The way out of the room it is wrongly inside of. It only has to be a
        # room this entity does NOT enclose -- any OTHER thing's interior is an
        # ordinary place to be, which is what makes the nested case work: a car
        # evicted from its own cabin belongs on the ferry's vehicle deck, and an
        # earlier version of this refused every room carrying a `parent_entity`
        # and stranded it.
        out = ""
        for edge in ((rooms.get(here) or {}).get("adjacent") or []):
            if not isinstance(edge, dict):
                continue
            to = str(edge.get("to") or "")
            if to and to in rooms and not _encloses(
                    scene, str(eid), to, rooms, entities, index):
                out = to
                break
        for key in [k for k, v in positions.items()
                    if str(v) == here and _same_entity(scene, str(k), str(eid))]:
            if out:
                positions[key] = out
            else:
                positions.pop(key, None)
            evicted.append((str(key), here, out))
    return evicted


def _encloses(scene, eid, room_id, rooms, entities, index) -> bool:
    """Is `room_id` inside `eid` -- directly, or through any chain of holders?

    Walks outward from the room through each enclosure's own exterior room, so
    the answer covers a nested mover. Cycle-guarded by the visited set, because
    the thing this function exists to find IS a cycle.
    """
    seen = set()
    while room_id and room_id in rooms and room_id not in seen:
        seen.add(room_id)
        holder = str((rooms.get(room_id) or {}).get("parent_entity") or "")
        if not holder:
            return False
        if _same_entity(scene, holder, eid):
            return True
        room_id = _entity_exterior_room(
            scene, holder, entities.get(holder) or {}, index=index)
    return False


def _same_entity(scene, a, b) -> bool:
    """Two spellings of one entity, by the scene's own subject identity."""
    if str(a) == str(b):
        return True
    try:
        from world.spatial_identity import same_subject
        return bool(same_subject(scene, str(a), str(b)))
    except Exception:
        return False


#: What a doorway IS, as against where it leads and whether it stands open:
#: the wall it is in and where along it, what it is called and made of, how
#: wide, how it is climbed. Deriving the dock edge from its holder changes the
#: target and the barrier, never these. The edge used to be rebuilt as {to,
#: barrier, distance}: in chat 154 turn 4398 the TARDIS doors shut, and the
#: console room's doorway lost its bearing.
_DOORWAY_OWN_FIELDS = ("dir", "offset", "name", "material", "width", "way",
                       "vertical")


def _doorway_own_fields(edge) -> dict:
    """The fields of `edge` that belong to the doorway itself, set ones only."""
    if not isinstance(edge, dict):
        return {}
    return {key: edge[key] for key in _DOORWAY_OWN_FIELDS
            if edge.get(key) not in (None, "")}


def _release_dock_passages(scene: dict, interior_ids) -> bool:
    """A MOVING ROOM'S DOORWAY HAS ONE WRITER, and it is the rewrite below.

    A passage record (`scene.passages`, DESIGN_ROOM_FIDELITY §5) makes a
    doorway ONE object keyed by the two rooms it joins, and
    `sync_scene_passages` writes both of its edges back from it on every merge
    -- AFTER this rewrite. For a doorway between an entity's inside and the
    world, the second room is wherever the entity happens to be, so a record
    keyed by it pins the door to one landing. Measured on the owner's chats
    156 and 157 (2026-09-25): a World Browser edit to the TARDIS's doorway on
    the beach minted one (`web/world_routes._ensure_passage`), and after the
    ship left, 157's console room -- a ship in no room -- still had a shut door
    onto the beach, and 156's opened onto the sea and the beach at once.

    So the record goes, and what it knew about the doorway ITSELF -- its
    name, material, width and climb (`_DOORWAY_OWN_FIELDS`) -- goes onto the
    inside room's edge and its `dock_doorway`, which carry the door to every
    place it docks after. A record joining two of the entity's own rooms is an
    ordinary inner doorway and stays. Returns True when anything changed."""
    passages = scene.get("passages") if isinstance(scene, dict) else None
    if not isinstance(passages, dict) or not passages:
        return False
    from world.spatial_orientation import normalize_vertical, opposite_vertical
    rooms = scene.get("rooms") or {}
    same = {str(rid) for rid in interior_ids}
    released = []
    for pid, record in list(passages.items()):
        pair = record.get("rooms") if isinstance(record, dict) else None
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        pair = [str(pair[0]), str(pair[1])]
        inside = [rid for rid in pair if rid in same]
        if len(inside) != 1:
            continue
        inside, outside = inside[0], next(rid for rid in pair if rid not in same)
        own = {key: record[key] for key in ("name", "material", "width")
               if record.get(key) not in (None, "")}
        vertical = normalize_vertical(record.get("vertical"))
        if vertical:
            # Stored as seen from rooms[0]; the doorway is kept from inside.
            own["vertical"] = vertical if pair[0] == inside \
                else (opposite_vertical(vertical) or vertical)
        room = rooms.get(inside)
        if own and isinstance(room, dict):
            for edge in room.get("adjacent") or []:
                if isinstance(edge, dict) and str(edge.get("to")) == outside:
                    edge.update(own)
            room["dock_doorway"] = {**_doorway_own_fields(room.get("dock_doorway")),
                                    **own}
        passages.pop(pid, None)
        released.append(pid)
    if not released:
        return False
    for room in rooms.values():
        for edge in (room.get("adjacent") or []) if isinstance(room, dict) else []:
            if isinstance(edge, dict) and edge.get("passage") in released:
                edge.pop("passage", None)
    if not passages:
        scene.pop("passages", None)
    return True


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
    same room. An entity's sole interior room is always the dock room. The
    doorway's own fields (`_DOORWAY_OWN_FIELDS`: its bearing, name and way)
    ride every rebuilt edge, and a `dock_doorway` stamp on the same room
    keeps them through a severed stretch, so the door comes back in the wall
    it left from.

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
    # One folded read of `positions` for the whole sweep (B18).
    index = PositionsIndex(scene.get("positions") or {})

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
        if _release_dock_passages(scene, interior_ids):
            changed = True
        transit = _transit_state(ent)
        # A THING CANNOT TRAVEL INTO ITS OWN INSIDE. A destination or route
        # that is one of this entity's own interior rooms is impossible by
        # construction -- the doorway derived from it would open the inside
        # onto itself -- so it is dropped, the way a thing standing inside
        # itself is evicted. Chat 154 turn 4398: the TARDIS set off with
        # `destination_room` its own console room, and would have docked in it.
        for field in ("destination_room", "route_room"):
            if transit and str(transit.get(field) or "") in same:
                transit.pop(field, None)
                changed = True
        exterior = _entity_exterior_room(scene, eid, ent, index=index)

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
            # A ROUTE IS A ROOM OR IT IS NOTHING. Words that name no room the
            # world holds -- a `new:` place nothing has built yet, an id a
            # model made up -- stay on the transit for the step that builds
            # the room, but a doorway onto them opens onto a room that is not
            # there: the rewrite drew `{"to": "the vortex"}` from a console
            # room whose ship stood in no room. The door opens once it exists.
            route = str(transit.get("route_room") or "")
            target = route if isinstance(rooms.get(route), dict) else None
            barrier = "closed_door"
        elif phase == "arriving":
            destination = str(transit.get("destination_room") or "")
            target = destination if isinstance(rooms.get(destination), dict) \
                else exterior
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
                edge = {
                    "to": target, "barrier": resolved_barrier,
                    "distance": (prev or {}).get("distance") or "near",
                }
                own = {**_doorway_own_fields(room.get("dock_doorway")),
                       **_doorway_own_fields(prev)}
                if own:
                    edge.update(own)
                    if room.get("dock_doorway") != own:
                        room["dock_doorway"] = own
                        changed = True
                new_adjacency.append(edge)
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
# A journey's two ends (the owner's ruling, 2026-09-25): where a vehicle sets
# off from is never where it arrives. Between them it is in the space it moves
# through -- its route room -- for as long as it likes, and in no room only
# when nothing has named that space, until the story brings it in.
# ---------------------------------------------------------------------------

#: Phases in which a vehicle is between its places: it is where its route
#: is, or nowhere.
_UNDER_WAY_PHASES = {"in_transit", "arriving"}


def _keys_filing(table: dict, eid, entity) -> list:
    """Every key `table` (positions, stations) files this entity under --
    its id, name or an alias, with `_positions_lookup`'s case, spacing and
    script tolerance -- the id first."""
    from story.character_schema import fold_identity_key
    record = entity if isinstance(entity, dict) else {}
    labels = [str(label) for label in (eid, record.get("name"), *(record.get("aliases") or []))
              if label]
    folded = {label.strip().casefold() for label in labels}
    identities = {fold_identity_key(label.lower().strip()) for label in labels} - {""}
    keys = [key for key in (table or {})
            if str(key) in labels or str(key).strip().casefold() in folded
            or fold_identity_key(str(key).lower().strip()) in identities]
    return sorted(keys, key=lambda key: str(key) != str(eid))


def _same_room(a, b) -> bool:
    return bool(str(a or "").strip()) and \
        str(a or "").strip().casefold() == str(b or "").strip().casefold()


def settle_departures(before: dict, merged: dict) -> bool:
    """WHERE A VEHICLE SETS OFF FROM IS NEVER WHERE IT ARRIVES, AND UNDER WAY
    IT IS IN THE SPACE IT MOVES THROUGH until the story brings it in -- the
    owner's ruling, 2026-09-25, and its evening. `before` is the world the
    beat (or the causal step) started from, read for where the vehicle stood;
    `merged` is rewritten in place. Idempotent. Returns True when anything
    changed.

    - Setting off (`in_transit` or `arriving`), the room it stood in is kept
      as `transit.departed_from` for the whole journey.
    - A `destination_room` or `route_room` naming that room is dropped, and a
      destination's `eta_seconds` with it, so no timed arrival carries it
      back. A vehicle sealed and not yet away is bound for nowhere it stands.
    - Under way it stands in its `route_room` when the world holds one, and
      the route holds through every later write of the transit that does not
      name another, as the place it left does: silence is not a move into
      nowhere. In no room is the floor for a journey nothing has named a
      space for -- a thing in transit is between places by construction
      (`unplaced_mints_needing_a_room` already says so) -- and code never
      invents one. Nothing asks it to arrive: with no destination it stays
      in transit, beat after beat, until a write brings it in.
    - Docked, the journey is over: `departed_from` goes, and a vehicle docked
      with no room but a `destination_room` stands there, as the timed
      arrival already stands it. A position the story wrote itself stands.
      Docked with nowhere at all to be -- no position, no destination, no
      route -- is not an arrival, and a vehicle that was under way stays so.

    Measured on chat 154 turn 4398 (2026-09-25): with no grammar and no
    reasoning, fresh drafts still wrote the beach the TARDIS was leaving as
    its route (3 of 3 samples of capture 3979), and once in twelve rerolls as
    its destination with an ETA of 5 s; and its position stayed on the beach
    for the whole journey, in plain view of anyone standing there. The same
    evening, three branches of that departure: 154 built a room for the space
    the ship crossed and held for the beats after; 157 named none, its next
    beat wrote the ship docked in no room, and the beat after that set it off
    again with nothing remembering the beach."""
    entities = merged.get("entities") if isinstance(merged, dict) else None
    positions = merged.get("positions") if isinstance(merged, dict) else None
    if not isinstance(entities, dict) or not isinstance(positions, dict):
        return False
    rooms = merged.get("rooms") or {}
    stations = merged.get("stations") if isinstance(merged.get("stations"), dict) else {}
    earlier = before if isinstance(before, dict) else {}
    earlier_entities = earlier.get("entities") or {}
    changed = False
    for eid, ent in entities.items():
        transit = _transit_state(ent)
        if transit is None:
            continue
        phase = str(transit.get("phase") or "docked").strip().casefold()
        here = room_of_record(merged, eid, ent)
        prior = _transit_state(earlier_entities.get(eid)) or {}
        prior_phase = str(prior.get("phase") or "").strip().casefold()
        was_under_way = prior_phase in _UNDER_WAY_PHASES
        if phase == "docked":
            destination = str(transit.get("destination_room") or "")
            lands = isinstance(rooms.get(destination), dict) \
                and rooms[destination].get("parent_entity") != eid
            if here or lands or not was_under_way:
                if transit.pop("departed_from", None) is not None:
                    changed = True
                if not here and lands:
                    positions[eid] = destination
                    transit.pop("destination_room", None)
                    transit.pop("eta_seconds", None)
                    changed = True
                continue
            # NOTHING ARRIVES NOWHERE. An arrival is AT somewhere, and this
            # one names nowhere to be: no position, no destination the world
            # holds, no route it stood in. Chat 157 turn 4481: under way in no
            # room, the TARDIS was written `{"phase": "docked"}` -- the
            # Director's prose had read a ship in flight as "a ship that has
            # not landed clean" -- and docking erased the place it left, so
            # the next beat set it off with nothing remembering the beach. The
            # journey stays as it was, and keeps its ends below.
            transit["phase"] = phase = prior_phase
            changed = True
        stood = room_of_record(earlier, eid, earlier_entities.get(eid) or ent) \
            if earlier else None
        if phase in _UNDER_WAY_PHASES:
            # THE JOURNEY KEEPS WHERE IT BEGAN through every write of its
            # transit: a beat's diff is merged more than once, and each later
            # beat that touches the vehicle writes its whole `transit` again,
            # over a world where it is already in no room. Replayed live on
            # chat 154 turn 4398, the committed TARDIS had lost the beach it
            # left, and a later beat could have sent it straight back.
            carried = str(prior.get("departed_from") or "").strip() \
                if was_under_way else ""
            if not str(transit.get("departed_from") or "").strip() \
                    and (carried or stood or here):
                transit["departed_from"] = carried or stood or here
                changed = True
            origin = transit.get("departed_from")
            # AND THE SPACE IT IS CROSSING, the same way: a write that names
            # no route is silence, not a move into nowhere. Chat 157 turn 4482
            # wrote `{"phase": "in_transit"}` and nothing else, which on a
            # ship standing in its route room would have dropped it out of
            # the world. Naming another space moves it there.
            kept = str(prior.get("route_room") or "").strip() if was_under_way else ""
            if kept and not str(transit.get("route_room") or "").strip():
                transit["route_room"] = kept
                changed = True
        else:  # sealed, or a phase not yet under way: where it stands
            origin = stood or here
        for field in ("destination_room", "route_room"):
            if _same_room(transit.get(field), origin):
                transit.pop(field, None)
                if field == "destination_room":
                    transit.pop("eta_seconds", None)
                changed = True
        if phase not in _UNDER_WAY_PHASES:
            continue
        route = str(transit.get("route_room") or "")
        keys = _keys_filing(positions, eid, ent)
        if isinstance(rooms.get(route), dict) and rooms[route].get("parent_entity") != eid:
            for key in keys[1:]:
                positions.pop(key, None)
                changed = True
            key = keys[0] if keys else eid
            if positions.get(key) != route:
                positions[key] = route
                changed = True
            continue
        for key in keys:
            positions.pop(key, None)
            changed = True
        for key in _keys_filing(stations, eid, ent):
            stations.pop(key, None)
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
