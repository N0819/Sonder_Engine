# spatial_geometry.py
"""Where a body stands and which way it faces: anchors, stations, facing,
proximity, sides and arcs, poses, room size, and the egocentric frame."""

import re
from typing import Optional

from world.spatial_orientation import (
    _LEFT_SECTORS,
    _RIGHT_SECTORS,
    normalize_bearing,
    normalize_vertical,
    opposite_bearing,
    opposite_vertical,
    relative_bearing,
    travel_bearing,
)

from world.spatial_barriers import effective_adjacent, normalize_barrier
from world.spatial_containment import (_NEVER_STATIONED_KINDS,
                                       containment_conceals,
                                       scale_changed_names)
from world.spatial_contacts import _clean_contact, _contact_key
from world.spatial_contacts import contact_endpoint_is_body
from world.spatial_identity import (_ci_get, _entity_named,
                                    _unique_entity_keyed, room_of,
                                    same_subject)


# How many beats a body stays visibly mid-crossing after stepping through a
# boundary sight does not pass. Going through a doorway is an act with duration
# -- the room behind watches it happen -- and collapsing it into the instant
# the position field changes made bodies blink out of the world. Two beats: the
# one they step through on, and one more still half in it.
THRESHOLD_CROSSING_BEATS = 2


def crossing_of(scene: dict, name: str) -> Optional[dict]:
    """This body's live crossing record, or None.

    {from: room left, to: room entered, beats: how many remain}. Written at
    commit by spatial_frames.infer_threshold_crossings; read here so every
    sight decision sees it through the one function that decides sight.
    """
    rec = (scene.get("crossings") or {}).get(str(name or ""))
    if not isinstance(rec, dict):
        return None
    try:
        beats = int(rec.get("beats") or 0)
    except (TypeError, ValueError):
        return None
    return rec if beats > 0 else None


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
    'aside'.

    Reads `effective_adjacent`, not `room["adjacent"]`. THIS FUNCTION WAS THE
    DEFECT'S ROOT READER: it and everything built on it (`spatial_digest`,
    `room_layout`'s exits, the Director's egocentric exits, a character's
    spatial frame, perception's rear arc) saw only the edges the observer's
    own room happened to declare, while ten other readers in this package
    treat the graph as undirected. A room that declared none -- the room a
    story starts in, always -- reported no exits at all beside a `room_layout`
    that listed its doorways as anchors in the same payload."""
    orientation = _ci_get(scene.get("orientation") or {}, observer) or {}
    edges = effective_adjacent(scene, room_of(scene, observer))

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


def spatial_digest(scene, observer, label_for=None):
    """Human-readable egocentric exits for the narrator: the observer's
    egocentric_frame with each edge rendered as {room, barrier}, grouped by
    bucket. The narrator binds egocentric direction words strictly to these
    buckets (see the narrator prompt's SPATIAL FRAME license). A digest with
    only 'unclassified' (or empty) means the observer has no movement history,
    so the narrator must assert no direction -- topological phrasing only.

    RENDERED FROM THE OBSERVER'S SIDE. An adjacency edge is one objective
    record read from two places, and this listed every edge the room declared
    with the barrier keyword the record carries -- so the blind side of a
    one-way window arrived as `{room: "Observation Room", barrier:
    "one_way_window"}`, naming the room a mind cannot see into and the
    mechanism it cannot know. Measured live (chat 78 t3): a restrained player
    whose own perception held nothing but two PA lines was narrated a figure
    "beyond the one-way window", and the phrase came from here.

    An edge that is a wall only from THIS side is not this side's exit, and is
    not rendered at all -- naming the room behind it with `barrier: "wall"`
    would leak the same fact in quieter words. Scoped to edges the resolution
    makes more restrictive than the record: an adjacency that declares no
    barrier at all already normalizes to `wall` for everyone, and dropping
    those would take real exits out of the payload every mind navigates by.
    `spatial_rel` is the one place that answers which side of a directional
    barrier a room is on (`sight_direction`); asking it here rather than
    re-deriving keeps that policy in a single function."""
    rooms = scene.get("rooms") or {}
    frame = egocentric_frame(scene, observer)
    # Local: world.spatial_light imports this module for `proximity_rel`, and
    # spatial_routing imports spatial_light, so a module-level import here
    # closes a cycle. Every other reader of both lives above them in the graph.
    from world.spatial_routing import spatial_rel
    here = room_of(scene, observer)

    def ref(edge):
        rid = edge.get("to")
        if here and rid \
                and spatial_rel(scene, here, rid).get("barrier") == "wall" \
                and normalize_barrier(edge.get("barrier")) != "wall":
            return None
        out = {"room": (rooms.get(rid) or {}).get("name") or rid,
               "barrier": edge.get("barrier")}
        # Which way the doorway itself faces. The buckets are EGOCENTRIC and
        # relative to the last move, so on a first beat -- no movement history
        # -- every exit lands in `unclassified` and carries no direction at
        # all, while `corridor_sight` beside it speaks in compass points. A
        # character holding both frames has to bridge them by guessing, and
        # does: read live from a thinking model's own trace, "two open exits:
        # one to Chamber 0001 (south) and one to Chamber 0100 (south)" -- the
        # same bearing given to two different exits, one of which was east.
        # And a beat later, "east is the intended exit, but it's not detailed
        # in spatial_frame; I need to infer it's ahead or something."
        #
        # The bearing is on the edge already. Omitted when the edge carries
        # none, since a scene without directions has none to give.
        bearing = normalize_bearing(edge.get("dir"))
        if bearing:
            out["bearing"] = bearing
        return out

    out = {}
    for bucket in ("behind", "ahead", "left", "right", "aside",
                   "above", "below", "unclassified"):
        refs = [r for r in (ref(e) for e in frame.get(bucket) or []) if r]
        if refs:
            out[bucket] = refs
    if frame.get("ahead_entity"):
        # ref is an entity id (look up its name) or already a character name.
        ent = (scene.get("entities") or {}).get(frame["ahead_entity"]) or {}
        ahead = ent.get("name") or frame["ahead_entity"]
        # THE ONE FIELD HERE THAT NAMES A BODY, and the only one that needs an
        # identity decision -- every other bucket names rooms. `positions` and
        # `stations` are keyed by CANONICAL name, so without a gate this hands
        # a character the identity of whoever is in front of them regardless of
        # whether they have any way to know it.
        #
        # Observed live: a character asked the person across the desk for her
        # name twice, in dialogue, and was refused both times, while her view,
        # her memories and her own claims all correctly said "the auditor".
        # `ahead_entity` said "Auditor Dana Rennick" from beat three. By beat
        # eight she used the surname aloud.
        #
        # `label_for` is `agents/common.observer_label_fn` -- perception's own
        # gate and its own `_unknown_actor_label`. Optional because the
        # narrator writes for the player, whose recognition is decided
        # elsewhere, and because this function is also called for internal
        # geometry where nothing is shown to a mind.
        out["ahead_entity"] = label_for(ahead) if label_for else ahead
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
    """Compass bearing of an anchor within its room, or None. Resolves through
    `effective_anchors`, so an implicit door pseudo-anchor bears too."""
    if not anchor_id:
        return None
    a = effective_anchors(scene, room_id).get(anchor_id)
    return normalize_bearing(a.get("dir")) if isinstance(a, dict) else None


# ---------------------------------------------------------------------------
# S1: the read-time derivation layer. Pure functions answering "where in the
# room is this body, which way does it face" from data the scene ALREADY
# persists -- edges, contacts, crossings, focus -- falling back to today's
# behaviour when nothing supports an answer. Nothing here is ever stored: a
# value that is never written needs no commit path, no restore path, no
# archive handling, and can never go stale in a checkpoint. Authored data
# always wins; the derivations are the fallback UNDER it.
# ---------------------------------------------------------------------------

_DOOR_ANCHOR_PREFIX = "door:"


def door_anchor_id(neighbor_room_id) -> str:
    """The id of the implicit pseudo-anchor a room's edge to `neighbor_room_id`
    contributes -- a doorway IS a named feature of the room at a known wall."""
    return f"{_DOOR_ANCHOR_PREFIX}{neighbor_room_id}"


_BARRIER_ANCHOR_DESC = {
    "open": "the opening",
    "open_door": "the open doorway",
    "closed_door": "the doorway",
    "window": "the window",
    "bars": "the bars",
    "membrane": "the curtained way",
    "wall": "the far wall",
}


def effective_anchors(scene: dict, room_id) -> dict:
    """S1a: the room's authored anchors plus one implicit `door:<to>`
    pseudo-anchor per adjacency edge (declared from either side), each
    carrying the edge's bearing when it has one.

    Every beared edge IS an anchor -- a doorway is a feature of the room at a
    known wall -- so the 54 live multi-occupant rooms with zero authored
    anchors gain at least one usable anchor wherever they have a beared edge,
    with zero authoring. Authored anchors always win an id collision; implicit
    ones are marked `implicit: True` and are never written anywhere.
    """
    rooms = scene.get("rooms") or {}
    room = rooms.get(room_id) or {}
    out = {}
    authored = room.get("anchors") or {}
    if isinstance(authored, (list, tuple)):
        # A bare list of names is the shape some older scenes and fixtures
        # carry: each is an anchor with no bearing and its id for a desc.
        authored = {str(a): {"desc": str(a)} for a in authored if str(a)}
    if not isinstance(authored, dict):
        authored = {}
    for aid, anchor in authored.items():
        if isinstance(anchor, dict):
            out[aid] = anchor

    def add(neighbor_id, barrier, bearing, vertical):
        aid = door_anchor_id(neighbor_id)
        if aid in out:
            return
        anchor = {
            "desc": _BARRIER_ANCHOR_DESC.get(normalize_barrier(barrier))
            or "the way through",
            "implicit": True,
        }
        if bearing:
            anchor["dir"] = bearing
        if vertical:
            anchor["vertical"] = vertical
        out[aid] = anchor

    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and edge.get("to"):
            add(edge["to"], edge.get("barrier"),
                normalize_bearing(edge.get("dir")),
                normalize_vertical(edge.get("vertical")))
    # An edge declared only from the neighbour's side is still a doorway in
    # THIS room; its bearing and verticality read reciprocally, the same rule
    # travel_bearing already applies.
    for other_id, other in rooms.items():
        if other_id == room_id or not isinstance(other, dict):
            continue
        for edge in other.get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("to") == room_id:
                add(other_id, edge.get("barrier"),
                    opposite_bearing(normalize_bearing(edge.get("dir"))),
                    opposite_vertical(normalize_vertical(edge.get("vertical"))))
    return out


def effective_station(scene: dict, name: str) -> dict:
    """S1b: the station `name` EFFECTIVELY holds, derived at read time.

    Resolution order, authored first:
      1. the authored/persisted station (`scene.stations[name]`) -- unchanged,
         always wins;
      2. contact-derived placement -- a standing contact is physical touch, so
         a partner backed by an anchored room feature seats the body there,
         and a co-located body partner becomes a mutual `near` link (two
         bodies in sustained contact are within reach by definition; the
         contacts ledger is one the Director reliably maintains);
      3. crossing-derived door placement -- a body with a live threshold
         crossing stands at the implicit door-anchor of the edge it entered
         through, and falls back to unplaced the moment the crossing record
         expires, so it can never go stale;
      4. nothing -> callers keep their current defaults.

    Never stored: this is an accessor, not a writer, so it reruns correctly
    under restore by construction. Unknown station keys (e.g. a future
    `cover`) pass through untouched.
    """
    authored = _station(scene, name)
    out = {k: v for k, v in authored.items() if k not in ("at", "near")}
    at = authored.get("at") or None
    near = list(authored.get("near") or [])
    room = room_of(scene, name)
    if room is None:
        out["at"] = at
        out["near"] = near
        return out
    me = str(name or "").strip().casefold()
    positions = scene.get("positions") or {}
    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        pair = (str(contact.get("actor") or "").strip(),
                str(contact.get("target") or "").strip())
        for mine, other in (pair, (pair[1], pair[0])):
            if not other or mine.casefold() != me:
                continue
            anchor = _anchor_for_entity(scene, room, other)
            if anchor:
                if not at:
                    at = anchor
            elif _ci_get(positions, other) == room and not any(
                    str(n).strip().casefold() == other.casefold() for n in near):
                near.append(other)
    if not at:
        rec = crossing_of(scene, name)
        if rec and rec.get("to") == room and rec.get("from") \
                and door_anchor_id(rec["from"]) in effective_anchors(scene, room):
            at = door_anchor_id(rec["from"])
    out["at"] = at
    out["near"] = near
    return out


def effective_facing(scene: dict, name: str) -> Optional[str]:
    """S1c: the bearing `name` is facing, derived at read time.

    `orientation.facing` when set (written by spatial_frames.infer_facing at
    commit -- unchanged, always wins); otherwise the bearing of the current
    focus target or edge, resolvable NOW through the derived anchors and
    stations above. This catches the window between a focus change and the
    next commit, and lifts scenes restored from checkpoints that predate
    infer_facing. Never guessed: no focus, no beared anchor -> None, and
    every egocentric consumer keeps asserting no direction.
    """
    rec = _ci_get(scene.get("orientation") or {}, name) or {}
    facing = normalize_bearing(rec.get("facing"))
    if facing:
        return facing
    focus = rec.get("focus") if isinstance(rec.get("focus"), dict) else None
    ref = focus.get("ref") if focus else None
    room = room_of(scene, name)
    if not ref or not room:
        return None
    if focus.get("kind") == "edge":
        return travel_bearing(scene, room, ref)
    if focus.get("kind") in ("target", "entity"):
        if room_of(scene, ref) != room:
            return None
        t_at = effective_station(scene, ref).get("at")
        if not t_at or t_at == effective_station(scene, name).get("at"):
            # Side by side at the same anchor: its room bearing is not the
            # target's direction from the observer. Never guessed.
            return None
        return _anchor_dir(scene, room, t_at)
    return None


#: How big a room is. Ordered, so the index is the rank, and the ONE statement
#: of the vocabulary -- `crowds.py` held it while `effective_room_size` here,
#: the function that grades the size, accepted any string at all. An authored
#: `enormous` was handed back as though it meant something and then read as
#: medium by every consumer (`_ROOM_COST.get` defaults to 1, `proximity_rel`
#: and `size_facts` test membership in literal tuples, `crowds.room_size_rank`
#: folds), so it was indistinguishable from an unsized room without ever
#: saying so.
ROOM_SIZES = ("tiny", "small", "medium", "large", "huge", "vast")
DEFAULT_ROOM_SIZE = "medium"


# Rooms whose NAME says "big" even when nobody authored `size`. Deliberately
# blunt and deliberately short: the hint only widens the `near`->`across`
# distinction, fails toward today's behaviour, and an authored size always
# wins. Token-matched, so "hallway" never reads as a hall.
_ROOM_SIZE_HINT_WORDS = frozenset({
    "hall", "ballroom", "cathedral", "warehouse", "hangar", "plaza",
    "arena", "atrium", "concourse", "auditorium", "amphitheater",
    "amphitheatre", "stadium", "gymnasium", "courtyard", "nave", "field",
})


def effective_room_size(scene: dict, room_id) -> str:
    """S1e: the room's authored `size`, else a keyword hint from its
    name/desc/notes (hall, warehouse, plaza... -> `large`), else `medium` --
    the safe default the engine already assumed. Derived-with-default; only
    proximity-grade consumers should read it."""
    room = (scene.get("rooms") or {}).get(room_id) or {}
    size = str(room.get("size") or "").strip().casefold()
    # A size outside the vocabulary is not a size. It falls through to the
    # unauthored path rather than being returned verbatim, which is what every
    # consumer was doing with it anyway -- the difference is that the name
    # hint now gets its chance, and `scene_lint` reports the authored word.
    if size in ROOM_SIZES:
        return size
    text = " ".join(str(room.get(key) or "") for key in ("name", "desc", "notes"))
    if set(re.split(r"[^a-z]+", text.casefold())) & _ROOM_SIZE_HINT_WORDS:
        return "large"
    return DEFAULT_ROOM_SIZE


def _occupancy(scene: dict) -> dict:
    counts = {}
    for room_id in ((scene or {}).get("positions") or {}).values():
        counts[str(room_id)] = counts.get(str(room_id), 0) + 1
    return counts


def guessed_room_sizes(scene: dict, prev_scene: dict = None) -> list[dict]:
    """G6: a room that just became shared, whose size nobody ever authored.

    Size used to be prose flavour. It is not any more: `proximity_rel` reads
    it to decide whether two people are `across` a room rather than `near`
    it, and S2a's placement-unknown fallback caps sight in a large room at
    `shapes`. An unauthored size is therefore a perception GRADE the engine
    picked for itself, and it picks silently -- 175 of 392 live rooms carry
    no `size`, of which the keyword hint rescues 24 and 151 fall to
    `medium`.

    Two subtractions keep this readable. Only rooms with two or more
    occupants, because a room with nobody in it has no proximity to grade.
    And only the beat the room CROSSES into being shared -- pass
    `prev_scene` and a scene that sits in the same unsized room for two
    hundred beats says so once, not two hundred times. A standing condition
    reported every beat is one the reader learns to skip, which is the
    failure this warning exists to avoid in the first place.

    `derived` says which way the guess went, so "sized `large` by the word
    'hall'" reads differently from "fell to `medium` because nothing said
    otherwise".

    Returns rows, not warnings -- the seam that knows whose warning list to
    write to does the reporting.
    """
    rooms = (scene or {}).get("rooms") or {}
    counts = _occupancy(scene)
    before = _occupancy(prev_scene) if prev_scene is not None else None
    out = []
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        if str(room.get("size") or "").strip():
            continue
        occupants = counts.get(str(room_id), 0)
        if occupants < 2:
            continue
        if before is not None and before.get(str(room_id), 0) >= 2 \
                and str(room_id) in ((prev_scene or {}).get("rooms") or {}):
            continue                    # already shared, already reported
        derived = effective_room_size(scene, room_id)
        out.append({
            "room": str(room_id),
            "name": str(room.get("name") or room_id),
            "derived": derived,
            "occupants": occupants,
            "by_keyword": derived == "large",
        })
    return sorted(out, key=lambda r: (-r["occupants"], r["room"]))


def proximity_rel(scene: dict, observer: str, target: str) -> Optional[str]:
    """Within-room proximity tier between two entities: 'within_reach' | 'near'
    | 'across', or None when they are not co-located. within_reach: same anchor,
    or a mutual 'near' station link. across: distinct anchors in a room flagged
    size 'large' OR BIGGER -- 'huge' and 'vast' are equally real scene sizes
    (see _ROOM_COST), and gating on 'large' exactly made the two largest floors
    read as more intimate than a merely large one. Otherwise 'near' -- the safe
    default for an ordinary same-room pair, including when no stations exist.

    Note for callers reasoning about distance: 'near' is returned BOTH as a
    measurement and as that default, and the default dominates (6.7% of live
    bodies carry an anchored station). Do not read 'near' as positive evidence
    of separation -- see hear_level's quiet-volume branch."""
    o_room = room_of(scene, observer)
    t_room = room_of(scene, target)
    if not o_room or o_room != t_room:
        return None
    o_st = effective_station(scene, observer)
    t_st = effective_station(scene, target)
    o_at, t_at = o_st.get("at"), t_st.get("at")

    def _in_near(near, who):
        w = str(who or "").strip().casefold()
        return any(str(n).strip().casefold() == w for n in near or [])

    if (o_at and t_at and o_at == t_at) \
            or _in_near(o_st.get("near"), target) \
            or _in_near(t_st.get("near"), observer):
        return "within_reach"
    size = effective_room_size(scene, o_room)
    if o_at and t_at and o_at != t_at and size in ("large", "huge", "vast"):
        return "across"
    return "near"


def measured_proximity_rel(scene: dict, observer: str, target: str) -> Optional[str]:
    """`proximity_rel`, but only when the answer is a MEASUREMENT.

    `proximity_rel` returns "near" both as a real reading (two anchored
    stations a few steps apart) and as its fallback when no station data
    exists -- and station data is mostly absent (measured live: 6.7% of bodies
    carry an anchored station, 8.6% of multi-occupant rooms have two). A
    delivery gate that treats the fallback as positive evidence of separation
    silences legitimate content wholesale: `hear_level` degrades a same-room
    mutter to a fragment at "near", which is the right answer for a measured
    few-steps gap and the wrong answer for nine rooms in ten where "near" just
    means "no one wrote stations".

    within_reach and across already require station data by construction;
    "near" is passed through only when both parties hold an anchor, and
    otherwise collapses to None -- "unknown", which downgrades nothing.
    """
    tier = proximity_rel(scene, observer, target)
    if tier != "near":
        return tier
    if effective_station(scene, observer).get("at") \
            and effective_station(scene, target).get("at"):
        return tier
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
    facing = effective_facing(scene, observer)
    if not facing:
        return None
    o_at = effective_station(scene, observer).get("at")
    t_at = effective_station(scene, target).get("at")
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
    facing = effective_facing(scene, observer)
    anchors = []
    # EFFECTIVE anchors: the look-around map gains its exits as positioned
    # features -- the doorway to the kitchen is a thing in the room with a
    # side, not only an entry in the exits digest.
    for aid, a in effective_anchors(scene, o_room).items():
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
    that person's anchor direction (see spatial_frames.infer_facing). Reads the
    EFFECTIVE station, so a body just through a doorway, or in contact with an
    anchored feature, bears without any authored station."""
    room = room_of(scene, name)
    if not room:
        return None
    return _anchor_dir(scene, room, effective_station(scene, name).get("at"))


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

    for name in list(stations.keys()):
        st = stations.get(name)
        my_room = _ci_get(positions, name)
        if not isinstance(st, dict) or my_room is None:
            stations.pop(name, None)   # tolerant: a case-variant of a positioned name survives
            continue
        # EFFECTIVE anchors, so a station at an implicit door pseudo-anchor
        # ("door:<to>") survives the merge instead of being blanked as a
        # phantom -- a room change still auto-clears it, because the door
        # anchors of the new room name different neighbours.
        anchors = effective_anchors(scene, my_room)
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


_POSE_FIELDS = ("posture", "support", "relative_to", "relation",
                "constraint", "detail")


def _clean_pose(raw):
    """One body's complete current pose snapshot, or None when empty.

    Values stay open strings: fictional bodies and supports are unbounded.
    Structure separates the body's own posture from what supports it and its
    relation to another body, so "lying", "on the table", "beneath Mara" and
    "pinned" cannot collapse into one stale prose field.
    """
    if not isinstance(raw, dict):
        return None
    pose = {
        field: " ".join(str(raw.get(field) or "").split())[:240]
        for field in _POSE_FIELDS
    }
    return pose if any(pose.values()) else None


#: The fields that state HOW a body is arranged. `detail` is deliberately not
#: one of them: it qualifies an arrangement, it does not constitute one.
_POSE_ARRANGEMENT_FIELDS = ("posture", "support", "relative_to", "relation",
                            "constraint")


def _retire_pose_relation(pose, other):
    """Drop the relational half of a pose its partner no longer holds for.

    ONE helper, because the two triggers -- a size change and an enclosure --
    are the same judgment: a relation is a claim about two bodies at the
    geometry they had, while posture is the body's own and survives both.
    `detail` goes only when it NAMES the partner, the same test
    `invalidate_contact_bound_poses` applies with its own vocabulary.
    """
    other = str(other or "").strip()
    pose["relative_to"] = ""
    pose["relation"] = ""
    pose["constraint"] = ""
    if other and re.search(r"\b%s\b" % re.escape(other),
                           pose.get("detail") or "", re.I):
        pose["detail"] = ""
    return pose


def normalize_scene_poses(scene: dict) -> dict:
    """Prune pose relations invalidated by departure or room separation."""
    poses = scene.get("poses")
    if not isinstance(poses, dict):
        scene["poses"] = {}
        return scene
    positions = scene.get("positions") or {}
    stations = scene.get("stations") or {}
    rooms = scene.get("rooms") or {}
    for name in list(poses):
        pose = _clean_pose(poses.get(name))
        my_room = _ci_get(positions, name)
        if pose is None or my_room is None:
            poses.pop(name, None)
            continue
        other = pose.get("relative_to")
        if other:
            # A pose may be relative to a co-located BODY or to a FIXTURE of
            # the body's own room. `support` has always accepted both (see the
            # anchors check below); `relative_to` accepted only bodies, and
            # silently cleared anything else.
            #
            # That asymmetry threw away the only structured record of which way
            # a body had turned. Live (chat 74 turn 57): the Director declared
            # `relative_to: "towel_rack"` for a character who had turned to face
            # the wall, back to the room. `towel_rack` is a real anchor of that
            # room bearing 'ne' -- but it is not a body, so this cleared it, and
            # the only surviving trace was prose in `detail`. `focus` then kept a
            # stale doorway edge from an earlier beat, `infer_facing` pinned the
            # heading to that doorway's 'w', and the adjacent room stayed in
            # full view: the same composed view read "back to the room" and
            # "You see Hinami" a sentence apart.
            #
            # A body turned toward a fixture is exactly as real as a body
            # leaning on one, and the room already says where its fixtures are.
            anchors = effective_anchors(scene, my_room) or {}
            # AN ENCLOSURE IS BETWEEN THEM. A contained body's position
            # DERIVES to its holder's room, so the co-location test below
            # passes for a body shut inside another and the relation stands
            # for the rest of the story. Same side of every enclosure or no
            # relation -- the rule `containment_conceals` already states for
            # sight, asked of arrangement. It covers a fixture too: you are
            # not oriented to the room's hearth from inside something.
            if containment_conceals(scene, name, other) or (
                    other not in anchors
                    and _ci_get(positions, other) != my_room):
                _retire_pose_relation(pose, other)
        support = pose.get("support")
        if support:
            anchors = (rooms.get(my_room) or {}).get("anchors") or {}
            support_is_anchor = support in anchors
            support_room = _ci_get(positions, support)
            if not support_is_anchor and support_room not in (None, my_room):
                pose["support"] = ""
            # Nothing on the far side of an enclosure bears your weight -- a
            # body inside another is not still resting on the room's table.
            if pose["support"] and containment_conceals(scene, name, support):
                pose["support"] = ""
            station = _ci_get(stations, name)
            if support_is_anchor and isinstance(station, dict) \
                    and station.get("at") not in (None, support):
                pose["support"] = ""
        poses[name] = pose
    return scene


_CONTACT_BOUND_POSE_WORDS = frozenset({
    "against", "carried", "carrying", "held", "holding", "pinned",
    "restrained", "supported", "supporting", "borne", "embraced",
    "grappled", "gripped", "lifted", "cradled",
})


def _carriage_labels(scene: dict, object_id) -> list:
    """Every spelling this beat's transfer could be naming the thing by.

    The op's own token, the same token with its underscores opened out (an id
    is written `a_thing`; prose says "a thing"), and -- when the scene HAS a
    record for it -- the entity's display name and aliases. One thing, every
    name it goes by, because the prose that has to be checked was written by a
    different hand than the id.
    """
    text = str(object_id or "").strip()
    if not text:
        return []
    labels = {text, text.replace("_", " ")}
    eid, entity = _unique_entity_keyed(scene, text)
    if eid and isinstance(entity, dict):
        labels.add(str(eid).replace("_", " "))
        labels.add(str(entity.get("name") or ""))
        labels.update(str(alias) for alias in (entity.get("aliases") or []))
    return [label for label in
            {str(label).strip() for label in labels} if label]


def invalidate_moved_body_pose_details(scene: dict, previous_positions) -> list:
    """Retire a pose `detail` that claims to hold a BODY which has just moved.

    THE SAME CLASS AS `invalidate_transferred_pose_details`, one ledger over.
    That function reconciles a possession claim in pose prose against the
    transfer ledger; this one reconciles it against `positions`. A `detail` is
    the one scene field nothing re-derives -- written once, rendered verbatim
    into every view including the body's own interoception, standing until
    some later beat happens to overwrite it -- and when it says a body is
    HOLDING somebody, that is a claim about where the somebody is. Where a
    body is belongs to `positions`.

    Measured live (chat 99): a pose detail written while a shrunken body lay
    in a mouth read "tongue curled around the little fox, holding her at the
    back of the mouth". She was swallowed on the next beat and again on the
    one after -- mouth, throat, stomach -- and the detail followed her owner
    unchanged, so the holder's own interoception went on reporting a body at
    the back of her mouth that was two rooms further down. Nothing was
    remembering wrongly; it was being told.

    THE RULE, and it subtracts only. A body that changed room this beat is
    somewhere else now. Another body's prose does not get to go on holding it
    there. Cleared:
      * the `detail` alone, exactly as the transfer twin clears it. Posture,
        support and the relation fields are the holder's OWN arrangement and
        no move of somebody else's touches them.
    Left alone:
      * the mover's own pose. Their prose is about themselves.
      * a detail that does not NAME the mover, on a word boundary, under any
        spelling the scene knows them by.
      * a detail that names them WITHOUT carriage vocabulary.
        `_CONTACT_BOUND_POSE_WORDS` is the engine's one list for "this clause
        depends on something being held", shared with the transfer twin and
        with `invalidate_contact_bound_poses`; watching somebody leave is not
        a claim to be holding them, and a second competing list is how two
        ledgers start disagreeing.

    `previous_positions` is the room map as it stood BEFORE this beat's
    merge. A body absent from it is newly placed rather than moved, and
    nothing is retired for it.

    Returns [(holder, mover)] for the caller's report; mutates.
    """
    poses = (scene or {}).get("poses")
    positions = (scene or {}).get("positions")
    if not isinstance(poses, dict) or not poses:
        return []
    if not isinstance(positions, dict) or not isinstance(previous_positions, dict):
        return []
    movers = []
    for subject, room in positions.items():
        was = previous_positions.get(subject)
        if not was or not room or str(was) == str(room):
            continue
        if not _moved_subject_is_body(scene, subject):
            continue        # a carried object is the transfer twin's business
        movers.append(subject)
    if not movers:
        return []

    dropped = []
    for holder, pose in poses.items():
        if not isinstance(pose, dict):
            continue
        detail = str(pose.get("detail") or "")
        if not detail:
            continue
        words = set(re.findall(r"[a-z'\u2019-]+", detail.casefold()))
        if not (words & _CONTACT_BOUND_POSE_WORDS):
            continue
        for mover in movers:
            if same_subject(scene, holder, mover):
                continue        # their own pose, about themselves
            if not _detail_names_subject(scene, detail, mover):
                continue
            pose["detail"] = ""
            dropped.append((holder, mover))
            break
    return dropped


def _moved_subject_is_body(scene, subject) -> bool:
    """Is this mover a body, for the purpose of retiring a carriage clause?

    Not `contact_endpoint_is_body`, which answers a different question -- it
    asks whether an endpoint is a body RATHER THAN an entity record, so a
    registered character reads as a thing the moment the scene mints a row
    for them, and live scenes mint one for everybody.

    Here the distinction that matters is only which twin owns the fact: a
    carried OBJECT moving is `invalidate_transferred_pose_details`' business,
    and a body moving is this one's. So a subject counts as a body when the
    wardrobe knows it, when its record says `person`, or when it has no
    record at all -- and a portable thing never does.
    """
    entity = ((scene or {}).get("entities") or {}).get(subject)
    if isinstance(entity, dict):
        if entity.get("portable"):
            return False
        if str(entity.get("kind") or "").strip().casefold() == "person":
            return True
    if subject in ((scene or {}).get("attire") or {}):
        return True
    return entity is None


def _detail_names_subject(scene, detail, subject) -> bool:
    """Does this pose prose name that body, under any spelling the scene has?

    Word-boundary matching on the canonical name, the display name and any
    alias -- the same generosity `_carriage_labels` shows a transferred thing,
    for the same reason: one body, every name it goes by.
    """
    low = str(detail or "").casefold()
    spellings = {str(subject or "").strip()}
    entity = ((scene or {}).get("entities") or {}).get(subject)
    if isinstance(entity, dict):
        spellings.add(str(entity.get("name") or ""))
        for alias in (entity.get("aliases") or []):
            spellings.add(str(alias or ""))
    for spelling in spellings:
        token = spelling.strip().casefold()
        if len(token) > 2 and re.search(
                r"(?<!\w)%s(?!\w)" % re.escape(token), low):
            return True
    return False


def invalidate_transferred_pose_details(scene: dict, inventory_ops) -> list:
    """Retire the possession claim in a pose `detail` for a thing that has
    just changed hands.

    THE CLASS. A pose `detail` is prose that qualifies an arrangement, and it
    is the one scene field nothing ever re-derives: written once, rendered
    verbatim into every view that can see the body -- the body's own
    interoception included -- and standing until some later beat happens to
    overwrite it. When that prose says a body is CARRYING something it is no
    longer only an arrangement; it is a possession claim, and possession is
    the transfer ledger's to state. Two ledgers, one fact, and nothing
    reconciled them: a thing could be handed away in `inventory_ops` and go on
    being held in `poses` for the rest of the story.

    Measured (chat 98): the establishing beat minted no entity for the thing
    at all and wrote its whole existence into one body's pose detail. Four
    beats later a transfer op moved it to another body; the detail did not
    move, and the giver's own composed view still read "... -- holding <it>
    against chest" five beats after she let go, in the interoception channel
    and in every other observer's sight line. The narrator was not
    remembering. It was being told.

    THE RULE, and it subtracts only: a transfer op says where a thing now is.
    A body that the ledger says is not where the thing went does not get to go
    on claiming carriage of it in prose. Cleared:
      * the `detail` alone. Posture, support and the relation fields are the
        body's OWN arrangement and no transfer touches them -- she is still
        standing on the deck; she is simply not holding it.
    Left alone:
      * the body the op names as the destination. It has the thing; the prose
        is true of them.
      * a detail that does not NAME the thing, on a word boundary, under any
        of the spellings it goes by.
      * a detail that names it without carriage vocabulary. Watching a thing,
        or standing beside one, is not a claim to be holding it, and
        `_CONTACT_BOUND_POSE_WORDS` is already the engine's one vocabulary for
        "this pose clause depends on something being held or touched" -- the
        same list `invalidate_contact_bound_poses` asks its own question with.
        A second, competing list is how two ledgers start disagreeing.

    THIS BEAT'S OWN pose declarations are checked too, unlike the scale-change
    retirement's `stated` exemption. That exemption exists because a pose
    restated in the beat that changed the geometry already speaks for the new
    geometry. Here the two halves come from DIFFERENT hands on disjoint scopes
    -- `poses` from the spatial specialist, `inventory_ops` from the objects
    specialist -- so neither is the later word, and between a channel built to
    say where a thing is and prose that mentions it in passing, the channel
    wins.

    Returns [(subject, thing)] for the caller's report; mutates.
    """
    poses = (scene or {}).get("poses")
    if not isinstance(poses, dict) or not poses:
        return []
    if not isinstance(inventory_ops, list) or not inventory_ops:
        return []
    retired = []
    for op in inventory_ops:
        if not isinstance(op, dict):
            continue
        labels = _carriage_labels(scene, op.get("object_id"))
        if not labels:
            continue
        departed = str(op.get("from_id") or "").strip()
        arrived = str(op.get("to_id") or "").strip()
        # A HANDOVER WITH ONE END. An op whose two endpoints are the same body
        # moves nothing, so there is no prose for it to contradict -- and
        # retiring on one would erase the holder's own true carriage clause.
        if departed and arrived and same_subject(scene, departed, arrived):
            continue
        for subject, raw in list(poses.items()):
            pose = _clean_pose(raw)
            if pose is None or not pose.get("detail"):
                continue
            if not str(subject).strip():
                continue
            # `same_subject`, not casefold equality: `positions`, `poses` and
            # a transfer's endpoints are each keyed by whatever their writer
            # reached for -- a uid here and a display name there -- and this
            # module's own loops sixty lines down already ask the question
            # this way. Bare equality silently answers "different body" for
            # two spellings of one, which retires nothing and reports nothing.
            if arrived and same_subject(scene, subject, arrived):
                continue          # they have it; the prose is true of them
            if not (departed and same_subject(scene, subject, departed)) \
                    and not arrived:
                # Neither endpoint names this body and the op does not say
                # where the thing went. Nothing here contradicts anything.
                continue
            detail = str(pose["detail"])
            low = detail.casefold()
            # THE CLAUSE THAT NAMES THE THING IS THE CLAUSE THAT CLAIMS IT.
            # Asking the carriage vocabulary over the WHOLE detail lets an
            # unrelated clause condemn a true one: "watching the padd, braced
            # against the console" carries no possession claim about the padd
            # at all, and was retired because "against" appears in the second
            # clause. A detail is retired only where a carriage word and the
            # thing's own name sit in one clause together.
            claimed = False
            for clause in re.split(r"[,;:.]| -- |—", low):
                if not (set(re.findall(r"[\w'-]+", clause))
                        & _CONTACT_BOUND_POSE_WORDS):
                    continue
                if any(re.search(r"\b%s\b" % re.escape(label.casefold()),
                                 clause) for label in labels):
                    claimed = True
                    break
            if not claimed:
                continue
            pose["detail"] = ""
            poses[subject] = pose
            retired.append((str(subject), str(op.get("object_id") or "")))
    return retired


def invalidate_contact_bound_poses(scene: dict, previous_contacts=None) -> dict:
    """Clear relational pose facts whose physical contact no longer exists.

    Pose and contact are separate ledgers, but some poses explicitly depend on
    contact ("supported by Dana", "held against Reya").  Ending the contact
    used to leave those prose snapshots standing indefinitely.  Non-contact
    relations such as facing, beside, above, or watching remain untouched.
    """
    poses = scene.get("poses")
    if not isinstance(poses, dict) or not poses:
        return scene
    if previous_contacts is None:
        return scene
    positions = scene.get("positions") or {}
    contacts = scene.get("contacts") or []
    old_contacts = previous_contacts or []

    def _is_body(value):
        return bool(value and _ci_get(positions, value) is not None)

    def _touches(left, right):
        a = str(left or "").strip().casefold()
        b = str(right or "").strip().casefold()
        return any(
            isinstance(contact, dict) and {
                str(contact.get("actor") or "").strip().casefold(),
                str(contact.get("target") or "").strip().casefold(),
            } == {a, b}
            for contact in contacts)

    def _touched_before(left, right):
        a = str(left or "").strip().casefold()
        b = str(right or "").strip().casefold()
        return any(
            isinstance(contact, dict) and {
                str(contact.get("actor") or "").strip().casefold(),
                str(contact.get("target") or "").strip().casefold(),
            } == {a, b}
            for contact in old_contacts)

    for subject, raw in list(poses.items()):
        pose = _clean_pose(raw)
        if pose is None:
            continue
        other = pose.get("relative_to")
        support = pose.get("support")
        relation_words = set(re.findall(
            r"[\w'-]+", " ".join((pose.get("relation") or "",
                                   pose.get("constraint") or "",
                                   pose.get("detail") or "")).casefold()))
        contact_bound = bool(relation_words & _CONTACT_BOUND_POSE_WORDS)

        if (_is_body(support) and _touched_before(subject, support)
                and not _touches(subject, support)):
            pose["support"] = ""
            if not other or str(other).casefold() == str(support).casefold():
                pose["constraint"] = ""
        if (_is_body(other) and contact_bound
                and _touched_before(subject, other)
                and not _touches(subject, other)):
            pose["relative_to"] = ""
            pose["relation"] = ""
            pose["constraint"] = ""
            # Detail is part of the invalidated relation only when it carries
            # the same contact-bound vocabulary.  Unrelated posture detail
            # ("breathing hard") remains.
            detail_words = set(re.findall(
                r"[\w'-]+", (pose.get("detail") or "").casefold()))
            if detail_words & _CONTACT_BOUND_POSE_WORDS:
                pose["detail"] = ""
        poses[subject] = pose
    return scene


def poses_broken_by_scale_change(scene: dict, previous_scales,
                                 stated=None) -> list:
    """Retire the pose relations a size change invalidated.

    The sibling of `contacts_broken_by_scale_change` and
    `containment_broken_by_scale_change`, routed through the same
    `scale_changed_names` so all three agree on what counts as a change. A
    relation between two bodies is a fact about the sizes they were, and one
    of them changing does not leave a smaller version of it standing. Posture
    is the body's own and survives. A support that is another BODY does not;
    a room anchor still holds up whatever is put on it at any size.

    `stated` is THIS beat's incoming `poses` map, and a pose in it is
    untouchable -- it already speaks for the new geometry. That exemption is
    load-bearing rather than polite: `apply_pose_diff` has run by the time
    this does, so without it a Director re-declaring the arrangement in the
    same beat as the size change would be wiped -- exactly the ordering the
    contact cancellation avoids by running before this beat's ops, and the
    rule `derive_scene_stations` states for stations.

    Returns the subjects whose relation was retired, for the caller to report.
    """
    poses = scene.get("poses")
    if not isinstance(poses, dict) or not poses:
        return []
    changed = scale_changed_names(previous_scales, scene.get("scales") or {})
    if not changed:
        return []
    spoken = {str(key).strip().casefold() for key in (stated or {})}
    positions = scene.get("positions") or {}
    retired = set()
    for name, raw in list(poses.items()):
        folded = str(name).strip().casefold()
        if folded in spoken:
            continue
        pose = _clean_pose(raw)
        if pose is None:
            continue
        subject_changed = folded in changed
        other = pose.get("relative_to")
        support = pose.get("support")
        if other and (subject_changed
                      or str(other).strip().casefold() in changed):
            _retire_pose_relation(pose, other)
            retired.add(str(name))
        if support and _ci_get(positions, support) is not None and (
                subject_changed
                or str(support).strip().casefold() in changed):
            pose["support"] = ""
            retired.add(str(name))
        poses[name] = pose
    return sorted(retired)


def apply_pose_diff(scene: dict, incoming) -> dict:
    """Replace touched pose snapshots; null/empty explicitly clears one."""
    scene.setdefault("poses", {})
    if not isinstance(scene["poses"], dict):
        scene["poses"] = {}
    if not isinstance(incoming, dict):
        return scene
    for name, raw in incoming.items():
        label = str(name or "").strip()
        if not label:
            continue
        standing = None
        for old in [key for key in scene["poses"]
                    if str(key).strip().casefold() == label.casefold()]:
            standing = _clean_pose(scene["poses"].pop(old, None)) or standing
        pose = _clean_pose(raw)
        if pose is not None:
            # DETAIL ALONE IS NOT AN ARRANGEMENT. A snapshot carrying no
            # arrangement field says nothing about how the body is arranged,
            # so it ANNOTATES the standing pose instead of erasing it.
            #
            # Clearing a pose has its own spelling and keeps it: an entry with
            # nothing in it at all, which `_clean_pose` already turns into
            # None above. This is the other case, and the schema is what makes
            # them collide -- `PoseEntry` defaults every field to `""`
            # (llm/schemas.py), so "I did not mention posture this beat" and
            # "posture ended" arrive identical, and reading both as ended
            # destroys state on the commoner one.
            #
            # Measured by running the merge rather than reading it: merging
            # `poses: {A: {detail: "looks down at her lap"}}` over a standing
            # `{posture: seated, support: low_table, relative_to: B,
            # relation: astride}` left posture, support, relative_to,
            # relation and constraint all empty -- a body that had been seated
            # astride another on a table was, from that beat, nowhere and on
            # nothing.
            if standing and pose["detail"] and not any(
                    pose[field] for field in _POSE_ARRANGEMENT_FIELDS):
                pose = dict(standing, detail=pose["detail"])
            scene["poses"][label] = pose
    return scene


def pose_facts(scene: dict, observer: str, visible_names=()) -> list[str]:
    """Authoritative current body arrangements using observer-safe labels."""
    facts = []
    allowed = {str(name) for name in (visible_names or [])} | {str(observer)}
    for name, raw in ((scene or {}).get("poses") or {}).items():
        if not any(same_subject(scene, name, allowed_name)
                   for allowed_name in allowed):
            continue
        pose = _clean_pose(raw)
        if pose is None:
            continue
        is_self = same_subject(scene, name, observer)
        parts = []
        if pose["posture"]:
            parts.append(f"posture: {pose['posture']}")
        if pose["support"]:
            parts.append(f"support: {pose['support']}")
        if pose["relative_to"]:
            other = ("you" if same_subject(
                scene, pose["relative_to"], observer)
                else pose["relative_to"])
            relation = f" ({pose['relation']})" if pose["relation"] else ""
            parts.append(f"relative to {other}{relation}")
        if pose["constraint"]:
            parts.append(f"constraint: {pose['constraint']}")
        if pose["detail"]:
            parts.append(f"detail: {pose['detail']}")
        if parts:
            prefix = "Your current body pose" if is_self \
                else f"{name}'s current body pose"
            facts.append(prefix + " — " + "; ".join(parts) + ".")
    return facts


def _anchor_for_entity(scene: dict, room_id: str, name: str):
    """The anchor id of the room feature `name` refers to, or None.

    Identifier recognition, never prose: a room's `bed` anchor and its `bed`
    entity are the same bed when their ids, names or aliases slugify the same.
    Anything looser would start reading furniture out of sentences.
    """
    anchors = ((scene.get("rooms") or {}).get(room_id) or {}).get("anchors") or {}
    if not isinstance(anchors, dict) or not anchors:
        return None
    slugs = {re.sub(r"[^a-z0-9]", "", str(a).casefold()): a for a in anchors}
    labels = [name]
    for eid, entity in (scene.get("entities") or {}).items():
        if not isinstance(entity, dict):
            continue
        names = [eid, entity.get("name"), *(entity.get("aliases") or [])]
        if any(str(n or "").strip().casefold() == str(name).strip().casefold()
               for n in names):
            labels.extend(n for n in names if n)
            break
    for label in labels:
        hit = slugs.get(re.sub(r"[^a-z0-9]", "", str(label).casefold()))
        if hit:
            return hit
    return None


def derive_scene_stations(scene: dict, explicit=None, fresh_ops=None) -> dict:
    """Fill in within-room position from what the beat already recorded.

    The Director fills `contact_ops` reliably and `stations` essentially never
    -- 147 contact adds in one measured story against zero stations in the
    whole database. But contact IS position at this grain: a hand on the quilt
    is a body at the bed, and two bodies touching are two bodies within reach.
    So the ledger the models do maintain seeds the one they do not.

    Additive and idempotent, and it never argues with a statement. A station
    named in THIS beat's diff is untouchable. An existing `at` is only replaced
    when the contact deriving it was asserted this beat -- this beat's physical
    evidence outranks a stale record, an old contact does not.

    A derived station outlives the contact that produced it, deliberately: a
    hold ends when the Director stops mentioning it, but you do not leave the
    bed by taking your hand off the quilt. Only a room change clears it, which
    `normalize_scene_stations` already does.
    """
    positions = scene.get("positions") or {}
    if not positions:
        return scene
    stated = {str(k).strip().casefold() for k in (explicit or {})}
    fresh = set()
    for raw in fresh_ops or []:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("op") or "add").strip().casefold() != "add":
            continue
        contact = _clean_contact(raw, scene)
        if contact is not None:
            fresh.add(_contact_key(contact))

    stations = scene.setdefault("stations", {})
    if not isinstance(stations, dict):
        stations = scene["stations"] = {}

    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        recent = _contact_key(_clean_contact(contact, scene) or {}) in fresh
        pair = (contact.get("actor"), contact.get("target"))
        for me, other in (pair, tuple(reversed(pair))):
            me, other = str(me or "").strip(), str(other or "").strip()
            room = _ci_get(positions, me)
            if not me or not other or room is None or me.casefold() in stated:
                continue
            # Only bodies get stationed. A bed touched by a hand is furniture
            # that a body is AT, not a guest with a position in the room.
            #
            # Tested by what the thing IS in the room rather than by
            # `_is_body_entity`, which reads `scene.attire` -- a table commit
            # fills AFTER the merge, so on any beat that establishes a scene it
            # is still empty and every body would fail. A room feature is a
            # thing you stand at; a body never is. Kinds are model-written free
            # text ("kitsune", "succubus", "nine-tailed kitsune" all appear
            # live), so the object list is a DENYLIST -- an unrecognised kind
            # is taken for a body, which is the recoverable direction.
            if _anchor_for_entity(scene, room, me) \
                    or str(_entity_named(scene, me).get("kind") or "").strip(
                        ).casefold() in _NEVER_STATIONED_KINDS:
                continue
            station = stations.setdefault(me, {"at": None, "near": []})
            if not isinstance(station, dict):
                continue
            anchor = _anchor_for_entity(scene, room, other)
            if anchor and (recent or not station.get("at")):
                station["at"] = anchor
            elif not anchor and _ci_get(positions, other) == room:
                # Two bodies in contact are within reach of each other, which
                # is what makes a whisper between them arrive whole.
                near = station.setdefault("near", [])
                if isinstance(near, list) and other not in near:
                    near.append(other)

    # Last resort: the body's own `state.position`. The Director has always
    # written the arrangement there as free text -- "seated_on_bed_edge" is the
    # live record, and it was the ONLY thing in the whole engine that knew she
    # was on the bed, read by nothing. This is identifier recognition, not
    # prose parsing: an anchor id of that body's OWN room, matched as a whole
    # word, and only where nothing better has already spoken. A body that
    # merely walked past the bed can be stationed at it by this, which the
    # Director now sees in its payload and can correct -- against a body that
    # has been sitting on one for seventeen beats with nowhere to say so.
    for name, room in list(positions.items()):
        name = str(name or "").strip()
        if not name or name.casefold() in stated:
            continue
        station = stations.get(name)
        if isinstance(station, dict) and station.get("at"):
            continue
        state = _entity_named(scene, name).get("state")
        if not isinstance(state, dict):
            continue
        words = [w for w in re.split(r"[^a-z0-9]+",
                                     str(state.get("position") or "").casefold()) if w]
        if not words:
            continue
        for word in words:
            anchor = _anchor_for_entity(scene, room, word)
            if anchor:
                stations.setdefault(name, {"at": None, "near": []})["at"] = anchor
                break
    return scene
