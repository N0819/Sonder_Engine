# spatial.py
"""Spatial reasoning with entity-aware scene merging and containment validation."""

import copy
import re
from typing import Optional

_BARRIER_ALIASES = {
    "": "wall",
    "none": "open",
    "no_barrier": "open",
    "no barrier": "open",
    "open_space": "open",
    "open space": "open",
    "archway": "open",
    "threshold": "open",
    "doorway": "open",
    "open_doorway": "open",
    "open doorway": "open",
    "open_doorframe": "open",
    "open doorframe": "open",
    "counter": "open",
    "open_counter": "open",
    "open counter": "open",
    "curtain": "open",
    "curtained_doorway": "open",
    "curtained doorway": "open",
    "door": "open_door",
    "open door": "open_door",
    "shoji_open": "open_door",
    "shoji open": "open_door",
    "shoji_door": "closed_door",
    "shoji door": "closed_door",
    "closed door": "closed_door",
    "locked_door": "closed_door",
    "locked door": "closed_door",
    "locked": "closed_door",
    "padlocked_door": "closed_door",
    "padlocked door": "closed_door",
    "padlocked": "closed_door",
    "sealed_door": "wall",
    "sealed door": "wall",
    "sealed": "wall",
    "bolted": "wall",
    "bolted_door": "wall",
    "bolted door": "wall",
    "solid_wall": "wall",
    "solid wall": "wall",
}

_VALID_BARRIERS = {
    "open",
    "open_door",
    "closed_door",
    "wall",
    "separated",
    "unknown",
}

def normalize_barrier(value: str | None) -> str:
    """Normalize model-generated barrier names into engine vocabulary."""
    barrier = str(value or "").strip().casefold()
    barrier = _BARRIER_ALIASES.get(barrier, barrier)

    if barrier not in _VALID_BARRIERS:
        return "wall"

    return barrier

def normalize_scene_barriers(scene: dict) -> dict:
    """Normalize every adjacency barrier in a scene in place."""
    if not isinstance(scene, dict):
        return scene

    for room in (scene.get("rooms") or {}).values():
        if not isinstance(room, dict):
            continue

        adjacency = room.get("adjacent")
        if not isinstance(adjacency, list):
            room["adjacent"] = []
            continue

        for edge in adjacency:
            if not isinstance(edge, dict):
                continue
            edge["barrier"] = normalize_barrier(
                edge.get("barrier")
            )

    return scene

# ---------------------------------------------------------------------------
# Compass bearings: allocentric orientation truth on adjacency edges.
#
# A bearing (n/ne/e/se/s/sw/w/nw) is the world's canonical, OBSERVER-FREE
# direction of an exit. Egocentric left/right is never stored -- it is DERIVED
# per observer from (their facing, the edge's bearing) at read time (see
# relative_bearing + spatial_frames.infer_facing), exactly as per-observer
# identity is derived from `known`. "Left" is a fact about an observer, not the
# world; storing it would be the same category error as writing a perceiver's
# knowledge into objective scene state. Vertical up/down stays on edge.vertical;
# this is the horizontal compass only. Absence of a bearing degrades to exactly
# the pre-bearing behavior -- no direction asserted, never a guess.
# ---------------------------------------------------------------------------

_BEARINGS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
_BEARING_DEG = {b: i * 45 for i, b in enumerate(_BEARINGS)}

_BEARING_ALIASES = {
    "n": "n", "north": "n",
    "ne": "ne", "northeast": "ne",
    "e": "e", "east": "e",
    "se": "se", "southeast": "se",
    "s": "s", "south": "s",
    "sw": "sw", "southwest": "sw",
    "w": "w", "west": "w",
    "nw": "nw", "northwest": "nw",
}

# Observer-relative words are NOT authorable allocentric truth. A model that
# emits one as a bearing gets it DROPPED (-> None), never coerced into a
# compass point -- the engine derives left/right elsewhere and must not let a
# model smuggle an egocentric claim into objective edge state. "up"/"down"
# belong to edge.vertical, so they are rejected here too.
_EGOCENTRIC_WORDS = {
    "left", "right", "ahead", "forward", "forwards", "front", "infront",
    "behind", "back", "backward", "backwards", "rear", "aside", "beside",
    "sideways", "port", "starboard", "onward", "onwards", "up", "down",
}

_OPPOSITE_BEARING = {
    "n": "s", "s": "n", "e": "w", "w": "e",
    "ne": "sw", "sw": "ne", "nw": "se", "se": "nw",
}

# Egocentric sectors at 45-degree steps clockwise from straight ahead.
_REL_SECTORS = ("ahead", "ahead_right", "right", "behind_right",
                "behind", "behind_left", "left", "ahead_left")
_LEFT_SECTORS = {"left", "ahead_left", "behind_left"}
_RIGHT_SECTORS = {"right", "ahead_right", "behind_right"}


def normalize_bearing(value) -> Optional[str]:
    """A model-supplied edge bearing collapsed to the 8-way compass, or None
    when it is absent, unrecognized, or an OBSERVER-RELATIVE word (left/right/
    ahead/...) that is not allocentric truth."""
    raw = str(value or "").strip().casefold()
    if not raw:
        return None
    key = re.sub(r"[^a-z]", "", raw)
    if key in _EGOCENTRIC_WORDS:
        return None
    return _BEARING_ALIASES.get(key)


def opposite_bearing(bearing: Optional[str]) -> Optional[str]:
    return _OPPOSITE_BEARING.get(bearing)


def relative_bearing(facing: Optional[str], target: Optional[str]) -> Optional[str]:
    """The egocentric sector an absolute `target` bearing falls in for an
    observer whose absolute `facing` is given (one of _REL_SECTORS), or None if
    either bearing is unknown. Pure -- the single point where allocentric
    compass truth becomes observer-relative."""
    if facing not in _BEARING_DEG or target not in _BEARING_DEG:
        return None
    idx = round(((_BEARING_DEG[target] - _BEARING_DEG[facing]) % 360) / 45) % 8
    return _REL_SECTORS[idx]


def lateral_of(facing: Optional[str], target: Optional[str]) -> Optional[str]:
    """'left'/'right' when the target bearing is on that side of the observer,
    else None -- a pure fore/aft bearing (ahead/behind) returns None because
    the movement-derived ahead/behind buckets already own that axis. Used to
    refine an otherwise-'aside' exit into a side."""
    rel = relative_bearing(facing, target)
    if rel in _LEFT_SECTORS:
        return "left"
    if rel in _RIGHT_SECTORS:
        return "right"
    return None


def _find_edge(room: Optional[dict], to_id: str) -> Optional[dict]:
    """The adjacency edge from `room` to `to_id`, or None."""
    if not isinstance(room, dict):
        return None
    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and edge.get("to") == to_id:
            return edge
    return None


def travel_bearing(scene: dict, from_room: str, to_room: str) -> Optional[str]:
    """Absolute compass bearing of travel from from_room to to_room, taken from
    the forward edge's `dir`, or the reciprocal of the back edge's `dir`. None
    when no bearing is authored on that adjacency (heading unknown)."""
    rooms = scene.get("rooms") or {}
    fwd = _find_edge(rooms.get(from_room), to_room)
    if fwd is not None:
        b = normalize_bearing(fwd.get("dir"))
        if b:
            return b
    back = _find_edge(rooms.get(to_room), from_room)
    if back is not None:
        b = normalize_bearing(back.get("dir"))
        if b:
            return opposite_bearing(b)
    return None


def normalize_scene_bearings(scene: dict) -> dict:
    """Normalize every adjacency edge's OPTIONAL `dir` into the compass
    vocabulary (dropping observer-relative or unrecognized values), then
    reconcile reciprocals: A->B bearing d implies B->A opposite(d). Fill a
    missing reciprocal; on a CONTRADICTION drop BOTH sides -- never guess which
    was right. Global loop-consistency is deliberately NOT enforced: only
    per-edge-pair reciprocity, the only consistency an observer standing in a
    room can ever actually test through its doorways."""
    if not isinstance(scene, dict):
        return scene
    rooms = scene.get("rooms") or {}

    for room in rooms.values():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or "dir" not in edge:
                continue
            nb = normalize_bearing(edge.get("dir"))
            if nb:
                edge["dir"] = nb
            else:
                edge.pop("dir", None)

    for a_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            b_id = edge.get("to")
            if not b_id or b_id == a_id or b_id not in rooms:
                continue  # skip self-loops: back would be edge itself
            back = _find_edge(rooms.get(b_id), a_id)
            if back is None:
                continue
            fwd_dir, back_dir = edge.get("dir"), back.get("dir")
            if fwd_dir and back_dir:
                if opposite_bearing(fwd_dir) != back_dir:
                    edge.pop("dir", None)
                    back.pop("dir", None)
            elif fwd_dir and not back_dir:
                back["dir"] = opposite_bearing(fwd_dir)
            elif back_dir and not fwd_dir:
                edge["dir"] = opposite_bearing(back_dir)

    return scene

def room_of(scene: dict, name: str) -> Optional[str]:
    positions = scene.get("positions") or {}
    if name in positions:
        return positions[name]
    lname = (name or "").lower().strip()
    for k, v in positions.items():
        if k.lower().strip() == lname:
            return v
    norm = re.sub(r"[^a-z0-9]", "", lname)
    if norm:
        for k, v in positions.items():
            if re.sub(r"[^a-z0-9]", "", k.lower().strip()) == norm:
                return v
    return None

def has_visual(rel: dict) -> bool:
    if rel.get("same_room"):
        return True

    return normalize_barrier(rel.get("barrier")) in {
        "open",
        "open_door",
    }

def spatial_rel(
    scene: dict,
    a_room: Optional[str],
    b_room: Optional[str],
) -> dict:
    if not a_room or not b_room:
        return {
            "same_room": False,
            "barrier": "unknown",
            "distance": "remote",
            "note": "no known spatial channel between these entities",
        }

    if a_room == b_room:
        return {
            "same_room": True,
            "barrier": "open",
            "distance": "same",
        }

    rooms = scene.get("rooms") or {}

    for source, target in (
        (a_room, b_room),
        (b_room, a_room),
    ):
        room = rooms.get(source) or {}

        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue

            if edge.get("to") != target:
                continue

            return {
                "same_room": False,
                "barrier": normalize_barrier(
                    edge.get("barrier")
                ),
                "distance": edge.get("distance", "near"),
            }

    return {
        "same_room": False,
        "barrier": "separated",
        "distance": "far",
    }

_PASSABLE_BARRIERS = {"open", "open_door"}

def passable_route_exists(
    scene: dict,
    from_room: Optional[str],
    to_room: Optional[str],
) -> bool:
    """True when to_room is reachable from from_room by walking only
    through passable doorways (barrier open / open_door), across any
    number of intermediate rooms.

    spatial_rel answers the DIRECT-adjacency question; this answers the
    traversal question the director_resolve movement backstop needs for a
    legitimate multi-room walk ("cross the corridor into the far office").
    Adjacency is treated as traversable in BOTH directions -- an open
    doorway declared from either side can be walked through either way
    (the nearby_rooms undirected-reachability precedent).

    A route requiring a still-closed door, wall, or unknown barrier does
    NOT count: only edges already passable this beat make a path. Callers
    that want a door opened this beat to count must pass a scene that
    already carries the beat's diff.
    """
    if not from_room or not to_room:
        return False
    if from_room == to_room:
        return True

    rooms = scene.get("rooms") or {}
    neighbors: dict[str, set] = {}
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            target = edge.get("to")
            if not target:
                continue
            if normalize_barrier(edge.get("barrier")) not in _PASSABLE_BARRIERS:
                continue
            neighbors.setdefault(room_id, set()).add(target)
            neighbors.setdefault(target, set()).add(room_id)

    seen = {from_room}
    frontier = [from_room]
    while frontier:
        room_id = frontier.pop()
        for nxt in neighbors.get(room_id, ()):
            if nxt == to_room:
                return True
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return False

def hear_level(
    rel: dict,
    volume: str,
    vouched: bool = False,
    proximity: str | None = None,
) -> str:
    volume = str(volume or "normal").strip().casefold()
    barrier = normalize_barrier(rel.get("barrier"))
    distance = rel.get("distance")

    if rel.get("same_room"):
        # A whisper (mutter) only fully reaches someone WITHIN REACH; it carries
        # as a fragment to others merely near, and is lost across a large room.
        # proximity None (unknown) preserves the pre-Phase-2 behavior: same room
        # -> full. Only an explicit 'near'/'across' tier downgrades a whisper.
        if volume == "mutter":
            if proximity == "across":
                return "none"
            if proximity == "near":
                return "fragment"
        return "full"

    if barrier == "unknown" or distance == "remote":
        if not vouched:
            return "none"

        if volume in ("loud", "shout"):
            return "fragment"

        return "none"

    if barrier in ("open", "open_door"):
        if volume in ("normal", "loud", "shout"):
            return "full"

        if volume == "mutter":
            return "fragment"

        return "none"

    if barrier == "closed_door":
        if volume in ("loud", "shout"):
            return "full"

        if volume == "normal":
            return "fragment"

        return "none"

    if barrier in ("wall", "separated"):
        return "fragment" if volume == "shout" else "none"

    return "none"

def can_perceive(rel: dict, volume: str = "normal") -> bool:
    return hear_level(rel, volume) != "none"

def nearby_rooms(
    scene: dict,
    center_room_ids,
    hops: int = 1,
) -> dict:
    """Rooms within `hops` adjacency steps of any of center_room_ids.

    Stage payloads currently serialize the entire scene.rooms dict into
    every LLM call regardless of relevance, so a large, mostly-explored
    building bloats every turn's context even though only the handful of
    rooms near where characters actually are matters for that turn's
    reasoning. This only trims what gets sent to a model -- deterministic
    checks (spatial_rel, hear_level, the passable-route validation in
    director_resolve) operate on the full, unfiltered scene in-process
    and must keep doing so; callers must filter only the payload copy,
    never the scene used for those checks.

    Adjacency is treated as undirected for this purpose (an edge declared
    from either side counts), since asymmetric declarations do happen and
    the question here is reachability for context purposes, not the
    perception-specific forward/reverse distinction visible_adjacent_rooms
    makes for what's visible through an open doorway.
    """
    rooms = scene.get("rooms") or {}

    neighbors: dict[str, set] = {}
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            target = edge.get("to")
            if not target:
                continue
            neighbors.setdefault(room_id, set()).add(target)
            neighbors.setdefault(target, set()).add(room_id)

    included = {r for r in (center_room_ids or []) if r}
    frontier = set(included)

    for _ in range(max(0, hops)):
        next_frontier = set()
        for room_id in frontier:
            next_frontier |= neighbors.get(room_id, set()) - included
        if not next_frontier:
            break
        included |= next_frontier
        frontier = next_frontier

    return {rid: rooms[rid] for rid in included if rid in rooms}

def rooms_adjacent(scene, room_a, room_b):
    """Undirected: is room_b a declared neighbor of room_a (edge from either
    side)? Used to tell a real step (A->adjacent B) from a teleport/gap-cross."""
    if not room_a or not room_b:
        return False
    rooms = scene.get("rooms") or {}
    for a, b in ((room_a, room_b), (room_b, room_a)):
        room = rooms.get(a) or {}
        for edge in room.get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("to") == b:
                return True
    return False


def egocentric_frame(scene, observer):
    """Classify the observer's current room's exits into egocentric buckets
    from their movement-derived orientation. Deterministic and authored-data
    free (see spatial_frames.infer_came_from for how orientation is set).

    Returns {behind, ahead, aside, left, right, unclassified, above, below} --
    each a list of adjacency edges -- plus 'ahead_entity' (an entity id) when
    focus is on an entity.

    Two reference frames, facing taking precedence when available:
      * FACING KNOWN + edge has a `dir` bearing: the edge is placed by
        relative_bearing(facing, dir) -- ahead / behind / left / right (diagonal
        sectors collapse to the lateral side). This is authoritative: it stays
        coherent even when the observer TURNS in place (facing a doorway they
        came through makes it 'ahead', not stale 'behind').
      * Otherwise: the movement fallback -- the room the observer came from ->
        BEHIND, the focused edge -> AHEAD, an edge with no usable facing/bearing
        -> ASIDE (topological only; a side is NEVER guessed).
    Vertical up/down always -> above/below first. With NO movement history AND
    no facing (scene open, fresh teleport) every exit is UNCLASSIFIED and
    callers must assert no egocentric direction.

    Pass-through inference: with a came_from but no facing, entering a room with
    a single non-vertical, non-behind, un-sided exit makes that exit AHEAD
    ('onward') -- the corridor case that otherwise reads as an unplaceable
    'aside'."""
    rooms = scene.get("rooms") or {}
    orientation = _ci_get(scene.get("orientation") or {}, observer) or {}
    room = rooms.get(room_of(scene, observer)) or {}
    edges = [e for e in (room.get("adjacent") or [])
             if isinstance(e, dict) and e.get("to")]

    came_from = orientation.get("came_from")
    facing = orientation.get("facing")
    focus = orientation.get("focus") or {}
    focus_edge = focus.get("ref") if focus.get("kind") == "edge" else None
    has_history = came_from is not None or facing is not None

    b = {"behind": [], "ahead": [], "aside": [], "left": [], "right": [],
         "unclassified": [], "above": [], "below": []}
    for e in edges:
        vert = str(e.get("vertical") or "").lower()
        if vert == "up":
            b["above"].append(e)
            continue
        if vert == "down":
            b["below"].append(e)
            continue
        if not has_history:
            b["unclassified"].append(e)
            continue
        rel = relative_bearing(facing, normalize_bearing(e.get("dir"))) \
            if facing else None
        if rel == "ahead":
            b["ahead"].append(e)
        elif rel == "behind":
            b["behind"].append(e)
        elif rel in _LEFT_SECTORS:
            b["left"].append(e)
        elif rel in _RIGHT_SECTORS:
            b["right"].append(e)
        elif focus_edge and e["to"] == focus_edge:
            b["ahead"].append(e)
        elif came_from is not None and e["to"] == came_from:
            b["behind"].append(e)
        else:
            b["aside"].append(e)

    # Pass-through: one behind + exactly one UN-SIDED lateral exit -> onward.
    # Only WITHOUT a facing: with a facing known, an un-beared exit's direction
    # is genuinely unknown (it stays 'aside'/topological) -- we do not guess it
    # 'ahead'. Also suppressed once a bearing placed any exit left/right.
    if facing is None and came_from is not None and not b["ahead"] \
            and len(b["aside"]) == 1 and not b["left"] and not b["right"]:
        b["ahead"] = b["aside"]
        b["aside"] = []

    if focus.get("kind") in ("entity", "target") and focus.get("ref"):
        b["ahead_entity"] = focus["ref"]
    return b


def spatial_digest(scene, observer):
    """Human-readable egocentric exits for the narrator: the observer's
    egocentric_frame with each edge rendered as {room, barrier}, grouped by
    bucket. The narrator binds egocentric direction words strictly to these
    buckets (see the narrator prompt's SPATIAL FRAME license). A digest with
    only 'unclassified' (or empty) means the observer has no movement history,
    so the narrator must assert no direction -- topological phrasing only."""
    rooms = scene.get("rooms") or {}
    frame = egocentric_frame(scene, observer)

    def ref(edge):
        rid = edge.get("to")
        return {"room": (rooms.get(rid) or {}).get("name") or rid,
                "barrier": edge.get("barrier")}

    out = {}
    for bucket in ("behind", "ahead", "left", "right", "aside",
                   "above", "below", "unclassified"):
        refs = [ref(e) for e in frame.get(bucket) or []]
        if refs:
            out[bucket] = refs
    if frame.get("ahead_entity"):
        # ref is an entity id (look up its name) or already a character name.
        ent = (scene.get("entities") or {}).get(frame["ahead_entity"]) or {}
        out["ahead_entity"] = ent.get("name") or frame["ahead_entity"]
    return out


# ---------------------------------------------------------------------------
# Within-room position (Phase 2): named anchors + entity stations.
#
# Rooms may carry an OPTIONAL `anchors` map {anchor_id: {desc, dir?}} naming the
# features prose already references (the bar, the hearth, a corner table); a
# doorway is implicitly an anchor via its edge. Entities may carry an OPTIONAL
# station in scene['stations'] {name: {at: anchor|None, near: [names]}}. From
# these we DERIVE proximity (within_reach / near / across) and a co-located
# entity's LEFT/RIGHT -- both read-only, never stored egocentric. Absent
# stations/anchors, everything degrades to "same room, unspecified" (near) with
# no side, i.e. exactly the pre-Phase-2 behavior.
# ---------------------------------------------------------------------------

def _station(scene: dict, name: str) -> dict:
    """The station record for `name`, tolerating case/alias keys the way
    room_of does. {} when none."""
    stations = scene.get("stations") or {}
    if name in stations and isinstance(stations[name], dict):
        return stations[name]
    ln = (name or "").lower().strip()
    for k, v in stations.items():
        if isinstance(v, dict) and str(k).lower().strip() == ln:
            return v
    return {}


def _anchor_dir(scene: dict, room_id: str, anchor_id) -> Optional[str]:
    """Compass bearing of an anchor within its room, or None."""
    if not anchor_id:
        return None
    anchors = ((scene.get("rooms") or {}).get(room_id) or {}).get("anchors") or {}
    a = anchors.get(anchor_id)
    return normalize_bearing(a.get("dir")) if isinstance(a, dict) else None


def proximity_rel(scene: dict, observer: str, target: str) -> Optional[str]:
    """Within-room proximity tier between two entities: 'within_reach' | 'near'
    | 'across', or None when they are not co-located. within_reach: same anchor,
    or a mutual 'near' station link. across: distinct anchors in a room flagged
    size 'large' (a great hall, a warehouse). Otherwise 'near' -- the safe
    default for an ordinary same-room pair, including when no stations exist."""
    o_room = room_of(scene, observer)
    t_room = room_of(scene, target)
    if not o_room or o_room != t_room:
        return None
    o_st, t_st = _station(scene, observer), _station(scene, target)
    o_at, t_at = o_st.get("at"), t_st.get("at")
    if (o_at and t_at and o_at == t_at) \
            or target in (o_st.get("near") or []) \
            or observer in (t_st.get("near") or []):
        return "within_reach"
    size = str(((scene.get("rooms") or {}).get(o_room) or {}).get("size") or "").lower()
    if o_at and t_at and o_at != t_at and size == "large":
        return "across"
    return "near"


def _ci_get(mapping, name):
    """Case/whitespace-tolerant dict lookup, matching room_of's key tolerance,
    so an orientation/station keyed 'Hinami' still resolves for a caller passing
    'hinami'. Returns None on miss."""
    if not isinstance(mapping, dict) or not name:
        return None
    if name in mapping:
        return mapping[name]
    ln = str(name).lower().strip()
    for k, v in mapping.items():
        if str(k).lower().strip() == ln:
            return v
    return None


def _relative_sector(scene: dict, observer: str, target: str) -> Optional[str]:
    """The egocentric sector (one of _REL_SECTORS) of a CO-LOCATED target
    relative to the observer's facing, from the target's anchor bearing. None
    without a facing and a beared target anchor -- never guessed. Also None when
    observer and target share the SAME anchor: the observer stands AT it, so the
    anchor's room bearing is not the target's direction from them (they are side
    by side). Approximation: the target anchor's absolute room bearing is taken
    as its direction from an observer near room centre."""
    o_room = room_of(scene, observer)
    if not o_room or o_room != room_of(scene, target):
        return None
    facing = (_ci_get(scene.get("orientation") or {}, observer) or {}).get("facing")
    if not facing:
        return None
    o_at = _station(scene, observer).get("at")
    t_at = _station(scene, target).get("at")
    if o_at and t_at and o_at == t_at:
        return None
    return relative_bearing(facing, _anchor_dir(scene, o_room, t_at))


def entity_side(scene: dict, observer: str, target: str) -> Optional[str]:
    """'left'/'right' for a CO-LOCATED target relative to the observer's facing.
    None without a facing and a beared anchor. Stays consistent when the
    observer turns (facing flips the sides)."""
    rel = _relative_sector(scene, observer, target)
    if rel in _LEFT_SECTORS:
        return "left"
    if rel in _RIGHT_SECTORS:
        return "right"
    return None


# Sectors that fall in an observer's rear arc -- the within-room blind spot.
_REAR_SECTORS = {"behind", "behind_left", "behind_right"}


def entity_arc(scene: dict, observer: str, target: str) -> Optional[str]:
    """'front' or 'rear' for a CO-LOCATED target relative to the observer's
    facing -- the within-room analogue of behind_rooms. A target in the REAR arc
    (behind / behind-left / behind-right of where the observer faces) is in the
    blind spot: the observer gets NO NEW VISUAL detail from them (a silent
    approach or gesture is unseen) though sound still carries. Someone WITHIN
    REACH is never a blind spot (they are at arm's length beside you) -> 'front'.
    None when facing or the target's anchor bearing is unknown -- with no basis,
    nothing is gated (the fail-open default for FOV)."""
    if proximity_rel(scene, observer, target) == "within_reach":
        return "front"
    rel = _relative_sector(scene, observer, target)
    if rel is None:
        return None
    return "rear" if rel in _REAR_SECTORS else "front"


def _sector_label(sector: Optional[str]) -> Optional[str]:
    """Collapse an 8-way sector to a coarse egocentric label for prose:
    ahead / behind / left / right (diagonals fold to their lateral side)."""
    if sector == "ahead":
        return "ahead"
    if sector == "behind":
        return "behind"
    if sector in _LEFT_SECTORS:
        return "left"
    if sector in _RIGHT_SECTORS:
        return "right"
    return None


def room_layout(scene: dict, observer: str) -> dict:
    """An egocentric map of the observer's CURRENT room, for a deliberate
    look-around/survey: {anchors:[{desc, side}], exits:{bucket:[{room,barrier}]},
    facing_known:bool}. Each anchor's `side` (ahead/behind/left/right, or None
    when facing/bearing is unknown -> describe it topologically) comes from the
    observer's facing vs the anchor's compass dir; exits reuse the egocentric
    digest. This is the DATA a convincing 'you look around' renders from -- the
    features, which way they lie, and where the ways out are."""
    o_room = room_of(scene, observer)
    room = (scene.get("rooms") or {}).get(o_room) or {}
    facing = ((scene.get("orientation") or {}).get(observer) or {}).get("facing")
    anchors = []
    for aid, a in (room.get("anchors") or {}).items():
        if not isinstance(a, dict):
            continue
        side = _sector_label(relative_bearing(facing, normalize_bearing(a.get("dir")))) \
            if facing else None
        anchors.append({"desc": a.get("desc") or aid, "side": side})
    return {"anchors": anchors, "exits": spatial_digest(scene, observer),
            "facing_known": bool(facing)}


def anchor_bearing_of(scene: dict, name: str) -> Optional[str]:
    """Compass bearing of the anchor the entity is currently stationed at,
    within its room; None if it has no station anchor or that anchor has no
    dir. Lets a character deterministically turn to FACE a co-located person by
    that person's anchor direction (see spatial_frames.infer_facing)."""
    room = room_of(scene, name)
    if not room:
        return None
    return _anchor_dir(scene, room, _station(scene, name).get("at"))


def normalize_scene_stations(scene: dict) -> dict:
    """Station hygiene, run at merge. Drops a station whose entity has no
    position; blanks an `at` naming an anchor absent from the entity's CURRENT
    room (so a room change auto-clears a stale anchor); drops `near` entries not
    co-located in the same room; then symmetrizes surviving `near` links. This
    makes a room move self-heal a character's within-room position with no
    separate commit inferer -- the old anchor and old near-links simply fail
    their membership tests once the position changes."""
    stations = scene.get("stations")
    if not isinstance(stations, dict):
        return scene
    positions = scene.get("positions") or {}
    rooms = scene.get("rooms") or {}

    for name in list(stations.keys()):
        st = stations.get(name)
        my_room = _ci_get(positions, name)
        if not isinstance(st, dict) or my_room is None:
            stations.pop(name, None)   # tolerant: a case-variant of a positioned name survives
            continue
        anchors = (rooms.get(my_room) or {}).get("anchors") or {}
        if st.get("at") and st["at"] not in anchors:
            st["at"] = None
        st["near"] = [n for n in (st.get("near") or [])
                      if _ci_get(positions, n) is not None and _ci_get(positions, n) == my_room]

    for name, st in list(stations.items()):
        for other in list(st.get("near") or []):
            o = stations.setdefault(other, {"at": None, "near": []})
            if isinstance(o, dict) and name not in (o.setdefault("near", [])):
                o["near"].append(name)
    return scene


def spatial_facts(scene: dict, observer: str, source_names) -> list:
    """Deterministic, authoritative one-line spatial statements for a beat, from
    the observer's frame -- GROUND TRUTH a weak narrator must not contradict
    (it need NOT recite them; restraint still governs how much is said). Covers
    exit directions and co-located people (proximity tier, side, rear blind
    spot). Empty when nothing is derivable. This is scaffolding against weak
    models flipping 'behind' to 'ahead' or swapping who is where."""
    facts = []
    digest = spatial_digest(scene, observer)
    dir_word = {"behind": "behind you", "ahead": "ahead of you",
                "left": "to your left", "right": "to your right",
                "above": "above you", "below": "below you"}
    for bucket, word in dir_word.items():
        for ref in digest.get(bucket) or []:
            facts.append(f"{ref['room']} lies {word}.")
    tier_word = {"within_reach": "within arm's reach beside you",
                 "near": "a few steps away", "across": "across the room"}
    for name in source_names or []:
        if name == observer:
            continue
        tier = proximity_rel(scene, observer, name)
        if tier is None:
            continue
        clause = f"{name} is {tier_word.get(tier, 'nearby')}"
        if entity_arc(scene, observer, name) == "rear":
            clause += ", behind you and out of your sight (you hear, not see, them)"
        else:
            side = entity_side(scene, observer, name)
            if side:
                clause += f", on your {side}"
        facts.append(clause + ".")
    return facts


def visible_adjacent_rooms(
    scene: dict,
    room_id: str,
    extra_rooms: dict | None = None,
) -> list[dict]:
    if not room_id:
        return []

    all_rooms = dict(
        scene.get("rooms") or {}
    )

    if extra_rooms:
        all_rooms.update(extra_rooms)

    visible = []
    seen = set()

    # Forward adjacency: the current room explicitly points to another.
    current_room = all_rooms.get(room_id) or {}

    for edge in current_room.get("adjacent") or []:
        if not isinstance(edge, dict):
            continue

        barrier = normalize_barrier(
            edge.get("barrier")
        )

        if barrier not in (
            "open",
            "open_door",
        ):
            continue

        adjacent_id = edge.get("to")

        if (
            not adjacent_id
            or adjacent_id not in all_rooms
            or adjacent_id in seen
        ):
            continue

        room_data = all_rooms[adjacent_id]
        notes = (
            room_data.get("notes")
            or room_data.get("desc")
            or ""
        )

        if not notes:
            continue

        visible.append({
            "room_id": adjacent_id,
            "room_name": (
                room_data.get("name")
                or adjacent_id
            ),
            "barrier": barrier,
            "description": notes[:800],
        })
        seen.add(adjacent_id)

    # Reverse adjacency: another room explicitly points back to the
    # current room. Do not include unrelated rooms with arbitrary open
    # edges.
    for other_id, room_data in all_rooms.items():
        if (
            other_id == room_id
            or other_id in seen
            or not isinstance(room_data, dict)
        ):
            continue

        for edge in room_data.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue

            barrier = normalize_barrier(
                edge.get("barrier")
            )

            if (
                edge.get("to") != room_id
                or barrier not in (
                    "open",
                    "open_door",
                )
            ):
                continue

            notes = (
                room_data.get("notes")
                or room_data.get("desc")
                or ""
            )

            visible.append({
                "room_id": other_id,
                "room_name": (
                    room_data.get("name")
                    or other_id
                ),
                "barrier": barrier,
                "description": notes[:800],
            })
            seen.add(other_id)

            break

    return visible

def _merge_room(existing: dict, incoming: dict) -> dict:
    """Merge an incoming room redeclaration into an already-known room.

    A director/mapping model redeclaring a room to add or change one
    adjacency edge has no reliable way to also echo back every other edge
    it didn't touch. Replacing the whole room (the old behavior) silently
    drops every edge the model didn't re-mention -- observed live when
    generating a west wing connection wiped out an existing corridor's
    links to the entrance hall and stairwell. Adjacency is merged by
    upserting on `to`: an incoming edge with the same target updates it
    (so barrier/distance changes still work), edges not mentioned survive.
    Explicit removal goes through `remove_adjacent`, not silence.
    """
    merged_room = dict(existing)

    for field in ("name", "desc", "notes", "parent_entity"):
        if incoming.get(field):
            merged_room[field] = incoming[field]

    existing_edges = {
        edge.get("to"): dict(edge)
        for edge in (existing.get("adjacent") or [])
        if isinstance(edge, dict) and edge.get("to")
    }

    for edge in (incoming.get("adjacent") or []):
        if isinstance(edge, dict) and edge.get("to"):
            existing_edges[edge["to"]] = dict(edge)

    merged_room["adjacent"] = list(existing_edges.values())

    for key, value in incoming.items():
        if key in ("name", "desc", "notes", "parent_entity", "adjacent"):
            continue
        merged_room[key] = value

    return merged_room

def _dedupe_adjacent(edges):
    """Collapse adjacency edges that target the same room, keeping the LAST
    occurrence for each target (matching _merge_room's upsert-by-'to').

    _merge_room already dedupes, but ONLY for a room present in the incoming
    diff. A room the model doesn't re-declare this turn is carried through the
    merge verbatim, so a duplicate 'to' edge introduced once -- e.g. when
    rename-remapping rewrites two edges onto the same target -- otherwise
    persists frozen across every subsequent turn. That leaves a room
    simultaneously walled off from AND open-doored to the same neighbor
    (barrier 'wall' and 'open_door' at once), which makes perception's spatial
    cues incoherent. Deduping every room on every merge heals it. First-seen
    'to' order is preserved; malformed edges (no 'to') pass through untouched."""
    seen, order, extras = {}, [], []
    for edge in edges or []:
        if isinstance(edge, dict) and edge.get("to"):
            if edge["to"] not in seen:
                order.append(edge["to"])
            seen[edge["to"]] = edge  # last wins, matching _merge_room
        else:
            extras.append(edge)
    return [seen[t] for t in order] + extras

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
      exterior room, barrier open_door (an existing edge to that room keeps
      its authored barrier/distance when no hatch state overrides it);
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
            if is_open and a in rooms and b in rooms and a != b:
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

        hatch = str((transit or {}).get("hatch") or "open").casefold()
        phase = str((transit or {}).get("phase") or "docked").casefold()
        # (target, barrier); barrier None = preserve whatever was authored.
        if transit is None:
            target, barrier = exterior, None
        elif phase in _TRANSIT_CLOSED_PHASES:
            target = str(transit.get("route_room") or "") or None
            barrier = "closed_door"
        elif phase == "arriving":
            target = str(transit.get("destination_room") or "") or exterior
            barrier = "closed_door"
        else:  # docked, or an unrecognized phase read conservatively as docked
            target = exterior
            barrier = "closed_door" if hatch in ("closed", "locked") else "open_door"

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

_AMBIENT_BARRIERS = {"open", "open_door"}

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
    reach room_id -- its connected component through open/open_door
    barriers (either edge direction) in the current derived graph -- and
    whether that component reaches any room that is not an entity
    interior. With dock edges applied, a sealed vehicle's interior scopes
    to just itself (open_to_world False); docked with an open hatch it
    scopes out to the exterior. An unknown room is treated as open (no
    filtering on missing data)."""
    rooms = scene.get("rooms") or {}
    if not room_id or room_id not in rooms:
        return ({room_id} if room_id else set()), True
    graph: dict[str, set] = {}
    for rid, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            to = edge.get("to")
            if to not in rooms:
                continue
            if normalize_barrier(edge.get("barrier")) in _AMBIENT_BARRIERS:
                graph.setdefault(rid, set()).add(to)
                graph.setdefault(to, set()).add(rid)
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

def merge_scene_with_diff(
    scene: dict,
    diff: dict | None,
) -> dict:
    diff = diff or {}
    # A scene is a nested mutable structure.  A shallow copy allowed
    # downstream normalization and deterministic backstops (zone stamping,
    # adjacency edits, overlays, attire) to mutate the caller's supposedly
    # pre-diff scene through shared child dictionaries/lists.  That made
    # before/after comparisons order-dependent and could contaminate rollback
    # preparation.  Scene merges are correctness boundaries, so pay the small
    # cost of a real copy here.
    merged = copy.deepcopy(scene)

    merged["rooms"] = dict(merged.get("rooms") or {})
    merged["entities"] = dict(merged.get("entities") or {})
    merged["positions"] = dict(merged.get("positions") or {})

    incoming_rooms = diff.get("rooms") or {}
    incoming_entities = diff.get("entities") or {}
    incoming_positions = diff.get("positions") or {}
    incoming_stations = diff.get("stations") or {}

    if isinstance(incoming_rooms, dict):
        for room_id, incoming_room in incoming_rooms.items():
            if not isinstance(incoming_room, dict):
                continue
            existing_room = merged["rooms"].get(room_id)
            merged["rooms"][room_id] = (
                _merge_room(existing_room, incoming_room)
                if isinstance(existing_room, dict)
                else incoming_room
            )

    if isinstance(incoming_entities, dict):
        merged["entities"].update(incoming_entities)

    if isinstance(incoming_positions, dict):
        merged["positions"].update(incoming_positions)

    # Stations (within-room position) are a sibling of positions, merged per
    # entity so a diff touching only `at` keeps the entity's `near` list, and
    # vice versa. Hygiene (phantom-anchor blanking, non-colocated pruning,
    # symmetrization) runs below via normalize_scene_stations.
    if isinstance(incoming_stations, dict) and incoming_stations:
        merged["stations"] = dict(merged.get("stations") or {})
        for name, st in incoming_stations.items():
            if isinstance(st, dict):
                cur = dict(merged["stations"].get(name) or {})
                cur.update(st)
                merged["stations"][name] = cur

    for removal in diff.get("remove_adjacent") or []:
        if not isinstance(removal, dict):
            continue
        room = merged["rooms"].get(removal.get("room"))
        target = removal.get("to")
        if not isinstance(room, dict) or not target:
            continue
        room["adjacent"] = [
            edge for edge in (room.get("adjacent") or [])
            if not (isinstance(edge, dict) and edge.get("to") == target)
        ]

    for entity_id in diff.get("remove_entities") or []:
        entity = merged["entities"].pop(entity_id, None)

        if not entity:
            continue

        names = {
            entity_id,
            str(entity.get("name") or ""),
            *(entity.get("aliases") or []),
        }

        for name in names:
            if name:
                merged["positions"].pop(name, None)

    occupied_rooms = set(merged["positions"].values())

    for room_id in diff.get("remove_rooms") or []:
        if room_id in occupied_rooms:
            continue
        merged["rooms"].pop(room_id, None)

    # Derived dock/portal edges are a function of the merged scene, not an
    # authored fact -- recompute them here so every consumer of a merge
    # (commit preparation, perception's mid-turn merges) sees the same
    # correct doorways. Runs before barrier normalization, which then
    # canonicalizes whatever the rewrite emitted.
    apply_transit_dock_edges(merged)

    # Collapse duplicate same-target adjacency edges across EVERY room, not
    # just the ones re-declared this turn -- otherwise a duplicate frozen into
    # an untouched room (a neighbor that is both walled and open-doored) leaks
    # incoherent spatial cues into perception forever. See _dedupe_adjacent.
    for room in merged["rooms"].values():
        if isinstance(room, dict) and room.get("adjacent"):
            room["adjacent"] = _dedupe_adjacent(room["adjacent"])

    normalize_scene_barriers(merged)
    # Optional compass bearings on edges: canonicalize each `dir` and reconcile
    # reciprocals so either room can derive a consistent left/right. Runs after
    # dedupe (so only surviving edges are reconciled) and barrier normalization.
    normalize_scene_bearings(merged)
    # Within-room station hygiene: prune stale anchors/near-links (auto-heals a
    # room move) and symmetrize proximity. Runs after positions are final.
    if merged.get("stations"):
        normalize_scene_stations(merged)
    return merged

def normalize_room_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")

def would_create_containment_cycle(placements: dict, subject_id: str, destination_id: str) -> bool:
    current = destination_id
    visited = set()
    while current:
        if current == subject_id:
            return True
        if current in visited:
            return True
        visited.add(current)
        placement = placements.get(current) or {}
        current = placement.get("container_id")
    return False

def validate_operations(scene: dict, operations: list) -> list:
    """Validate world mutation operations before atomic commit."""
    known_ids = set((scene.get("entities") or {}).keys())
    known_ids.update((scene.get("rooms") or {}).keys())
    created_ids = set()
    errors = []

    for operation in operations:
        op = operation.get("op")
        if op == "create_entity":
            entity = operation.get("entity") or {}
            entity_id = str(entity.get("entity_id") or "")
            if not entity_id:
                errors.append("Created entity has no entity_id")
            elif entity_id in known_ids or entity_id in created_ids:
                errors.append(f"Duplicate entity ID: {entity_id}")
            else:
                created_ids.add(entity_id)
        elif op == "move_entity":
            entity_id = operation.get("entity_id")
            destination_id = operation.get("destination_id")
            if entity_id not in known_ids | created_ids:
                errors.append(f"Unknown moved entity: {entity_id}")
            if destination_id not in known_ids | created_ids:
                errors.append(f"Unknown movement destination: {destination_id}")
            if entity_id == destination_id:
                errors.append("An entity cannot contain itself")
    return errors