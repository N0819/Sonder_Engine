"""Spatial (not temporal) frame splits and merges: two parties simply
far apart RIGHT NOW, not visiting a different era. See frames.py's
module docstring for the visibility-rule side of this (kind="spatial",
parent_frame_id/split_turn_idx/merged_turn_idx, and why the ordinary
ordinal rule is wrong for them). This module owns the OTHER half: the
deterministic detector that decides WHEN to split or merge, and the
mechanics of doing so.

DETECTION IS DELIBERATELY ZONE-BASED, NOT DISTANCE-BASED. spatial.py's
`distance:"far"` just means "no adjacency edge happens to connect these
two rooms" -- true of any two unmapped rooms in the same building, not
evidence of a genuine narrative departure. Splitting on that would
shred ordinary play. Instead, a room may carry an explicit `zone: str`
field (author-declared by the Director/Mapping when a scene genuinely
introduces a disconnected locale -- a second starship, a distant city;
see get_prompt("mapping_commit") for the authoring guidance) -- rooms
carry arbitrary extra keys through commit_scene/merge_scene_with_diff
untouched, so this needed no scene-schema change. A split fires only
when two human parties are standing in rooms with two DIFFERENT
non-empty zones; rooms without a zone never trigger anything.

This is a deterministic, commit-time check -- never a model's free-text
judgment call about when a "split" is dramatically warranted. The
Director/Mapping only ever get to declare a room's zone as part of
otherwise-ordinary, already-validated scene authoring; whether that
zone difference actually produces a split is decided here, the same
division of responsibility as everything else this engine treats as an
objective-truth decision.
"""

from __future__ import annotations

import json

from character_schema import character_name, normalize_persona_data, persona_name
from db import q, qi, transaction, wget, wget_for_frame, wset, wset_for_frame
from frames import create_frame, get_frame
from paradox import get_paradox
from scene import active_cast, persona_of, set_char_state, set_char_status
from spatial import room_of

NOT_A_ZONE = None


def _room_zone(scene, room_name):
    room = (scene.get("rooms") or {}).get(room_name) or {}
    zone = room.get("zone")
    return zone if isinstance(zone, str) and zone.strip() else NOT_A_ZONE


def _effective_zone(scene, name):
    """The zone a party/cast member should be attributed to. Resolved
    through a vehicle's own exterior position when `name` is currently
    standing in one of its interior (parent_entity-linked) rooms --
    vehicle interiors are deliberately never zoned themselves (see
    infer_vehicle_zones's docstring: a ship must not carry a stale zone
    tag it can fly away from), so a party member sitting in the cockpit
    the moment it arrives somewhere new must still count as having
    arrived, not as being nowhere."""
    room_name = room_of(scene, name)
    zone = _room_zone(scene, room_name)
    if zone:
        return zone
    rooms = scene.get("rooms") or {}
    positions = scene.get("positions") or {}
    parent_entity = (rooms.get(room_name) or {}).get("parent_entity")
    seen = set()
    while parent_entity and parent_entity not in seen:
        seen.add(parent_entity)
        ext_room = positions.get(parent_entity)
        zone = _room_zone(scene, ext_room)
        if zone:
            return zone
        parent_entity = (rooms.get(ext_room) or {}).get("parent_entity")
    return None


def _all_party_names(chat_id, frame_id):
    """Every human party member's name (primary player + active personas
    stationed in this frame), regardless of what room they're currently
    in -- unlike zone_groups, which only reports members already
    standing in a zoned room."""
    names = []
    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if chat:
        pers = persona_of(dict(chat))
        if isinstance(pers, dict):
            name = persona_name(pers)
            if name:
                names.append(name)
    for row in q(
        "SELECT p.sheet FROM chat_personas cp JOIN personas p ON p.id=cp.persona_id "
        "WHERE cp.chat_id=? AND cp.status='active' AND cp.frame_id IS ?",
        (chat_id, frame_id),
    ):
        sheet = normalize_persona_data(json.loads(row["sheet"]))
        name = sheet.get("identity", {}).get("name")
        if name:
            names.append(name)
    return names


def _room_graph(rooms):
    """{room_id: {connected_room_id, ...}} from adjacency edges, treated
    as bidirectional for reachability -- barrier type doesn't matter
    here, only whether a room is reachable AT ALL without a vehicle."""
    graph = {rid: set() for rid in rooms}
    for rid, room in rooms.items():
        for edge in (room.get("adjacent") or []):
            if isinstance(edge, dict) and edge.get("to") in rooms:
                graph[rid].add(edge["to"])
                graph.setdefault(edge["to"], set()).add(rid)
    return graph


def _connected_component(graph, start, exclude=None):
    """BFS from `start`, never traversing INTO a room in `exclude` --
    used to isolate a newly-arrived room's own component from the
    departure room's, since ordinary room-creation always adds a
    same-turn adjacency edge back to wherever the mover came from (see
    infer_vehicle_zones's docstring for why that edge must be ignored
    here specifically)."""
    exclude = exclude or set()
    if start is None:
        return set()
    if start not in graph:
        return {start}
    seen = {start}
    queue = [start]
    while queue:
        cur = queue.pop()
        for nxt in graph.get(cur, ()):
            if nxt in seen or nxt in exclude:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _zone_slug(room_id):
    return f"zone_{room_id}"


def infer_vehicle_zones(chat_id, frame_id, prev_scene, new_scene):
    """Deterministic zone stamping on vehicle transit, so a genuine
    "flew to a disconnected place" beat produces a zone difference
    WITHOUT depending on the Director proactively remembering to set an
    extra field it has no standing reason to think about most turns
    (confirmed live: the Director reliably marks a ship as
    kind="vehicle" with parent_entity-linked interior rooms and moves
    its exterior position on every flight -- it just never spontaneously
    tags room.zone, and a separate ROOM CREATION instruction actually
    forces a same-turn adjacency edge back to the departure room,
    directly undermining any prompt-based zone criterion).

    Trigger: a vehicle entity currently carrying a human party member
    (someone positioned in one of its parent_entity-linked interior
    rooms) moved exterior position this turn to a room with NO
    adjacency path from where it started, in the PRE-diff room graph.
    That is a genuine gap-crossing, not routine movement through an
    already-connected location.

    On trigger: the arrival room's own connected component (in the
    POST-diff graph, but excluding every room already in the departure
    room's PRE-diff component -- which neutralizes the forced "connect
    to where the mover came from" edge new rooms always get) is stamped
    with a fresh zone distinct from the departure side's. Vehicle
    interiors (rooms with any parent_entity) are never stamped -- they
    travel with the vehicle, they aren't a place.
    """
    prev_rooms = prev_scene.get("rooms") or {}
    new_rooms = new_scene.get("rooms") or {}
    prev_positions = prev_scene.get("positions") or {}
    new_positions = new_scene.get("positions") or {}
    entities = new_scene.get("entities") or {}

    party_names = None  # computed lazily -- most commits touch no vehicle at all
    changed = False

    for eid, ent in entities.items():
        if not isinstance(ent, dict) or ent.get("kind") != "vehicle":
            continue
        prev_room = prev_positions.get(eid)
        new_room = new_positions.get(eid)
        if not new_room or prev_room == new_room:
            continue

        interior_rooms = {rid for rid, r in new_rooms.items()
                          if isinstance(r, dict) and r.get("parent_entity") == eid}
        if not interior_rooms:
            continue
        if party_names is None:
            party_names = _all_party_names(chat_id, frame_id)
        aboard = any(new_positions.get(name) in interior_rooms for name in party_names)
        if not aboard:
            continue

        prev_graph = _room_graph(prev_rooms)
        component_a = _connected_component(prev_graph, prev_room)
        if new_room in component_a:
            continue  # already reachable pre-diff -- ordinary movement, not a gap crossing

        new_graph = _room_graph(new_rooms)
        component_b = _connected_component(new_graph, new_room, exclude=component_a)

        zone_a = next((new_rooms[r].get("zone") for r in component_a
                       if r in new_rooms and new_rooms[r].get("zone")), None)
        zone_b = next((new_rooms[r].get("zone") for r in component_b
                       if new_rooms[r].get("zone")), None)
        if not zone_a and component_a:
            zone_a = _zone_slug(sorted(component_a)[0])
        if not zone_b and component_b:
            zone_b = _zone_slug(sorted(component_b)[0])
        if not zone_a or not zone_b or zone_a == zone_b:
            continue

        for rid, zone in ((r, zone_a) for r in component_a if r in new_rooms):
            room = new_rooms[rid]
            if not room.get("zone") and not room.get("parent_entity"):
                room["zone"] = zone
                changed = True
        for rid in component_b:
            room = new_rooms.get(rid)
            if isinstance(room, dict) and not room.get("zone") and not room.get("parent_entity"):
                room["zone"] = zone_b
                changed = True

    return changed


def infer_companion_carry(chat_id, frame_id, prev_scene, new_scene, cast_names,
                           cast_changes=None):
    """Deterministic backstop for a companion-position lag: when the
    player's own declared action narrates OTHER present characters
    moving/boarding a vehicle alongside them (a ship, a TARDIS...),
    director_resolve reliably updates the PLAYER's own state_diff.positions
    entry but reliably fails to write the matching entry for those
    companions (confirmed live 3 times: a ship, then a TARDIS, twice).
    Mirrors infer_vehicle_zones' role above -- a narrow, deterministic
    mechanical follow-through for a pattern the model keeps missing, not
    a general "figure out who else moved" solver. The fully general case
    (two people just walk into the next room together) is deliberately
    left unhandled -- that really is NLU-hard, and guessing there risks
    silently teleporting a character the player actually left behind.

    Trigger (all must hold):
    - the player's own position changed this beat;
    - the player's new room is inside a kind="vehicle" entity's interior
      rooms, OR the player's previous and new rooms are in different
      pre-diff connected components (the same "genuine gap-crossing" test
      infer_vehicle_zones uses above, reused rather than reimplemented);
    - a registered cast member was co-located with the player pre-diff;
    - that cast member's position was left untouched by the diff (no
      explicit new position this beat) and no cast_changes entry marks
      them departed/incapacitated/removed this beat.

    On trigger: copies the player's new position onto that cast member's
    entry in new_scene["positions"], mutating `new_scene` in place -- same
    calling convention as infer_vehicle_zones (called from commit.py's
    commit_scene on the same already-merged `sc` object, before it is
    persisted via wset).
    """
    prev_positions = prev_scene.get("positions") or {}
    new_positions = new_scene.setdefault("positions", {})
    prev_rooms = prev_scene.get("rooms") or {}
    new_rooms = new_scene.get("rooms") or {}
    entities = new_scene.get("entities") or {}

    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if not chat:
        return False
    pers = persona_of(dict(chat))
    player_name = persona_name(pers) if isinstance(pers, dict) else None
    if not player_name:
        return False

    prev_room = prev_positions.get(player_name)
    new_room = new_positions.get(player_name)
    if not new_room or new_room == prev_room:
        return False  # player didn't change rooms this beat

    new_room_def = new_rooms.get(new_room) or {}
    parent_entity = new_room_def.get("parent_entity")
    is_vehicle_interior = bool(
        parent_entity
        and isinstance(entities.get(parent_entity), dict)
        and entities[parent_entity].get("kind") == "vehicle"
    )

    crossed_gap = False
    if not is_vehicle_interior and prev_room:
        prev_graph = _room_graph(prev_rooms)
        component = _connected_component(prev_graph, prev_room)
        crossed_gap = new_room not in component

    if not is_vehicle_interior and not crossed_gap:
        return False

    departed = {
        str(chg.get("who") or "").casefold()
        for chg in (cast_changes or [])
        if isinstance(chg, dict) and chg.get("who")
    }

    changed = False
    for name in cast_names:
        if not name or name == player_name:
            continue
        if prev_positions.get(name) != prev_room:
            continue  # not co-located with the player pre-diff
        if name.casefold() in departed:
            continue  # explicitly handled this beat -- don't override
        if new_positions.get(name) != prev_room:
            continue  # diff already moved them somewhere -- don't override
        new_positions[name] = new_room
        changed = True

    return changed


def zone_groups(chat_id, frame_id, scene):
    """{zone: [name, ...]} for every human party member (the primary
    player + every persona stationed in this exact frame) currently
    standing in an EXPLICITLY zoned room. Members in an unzoned room are
    excluded entirely -- only declared zones can ever trigger a split.
    """
    groups = {}

    def add(name):
        if not name:
            return
        zone = _effective_zone(scene, name)
        if zone:
            groups.setdefault(zone, []).append(name)

    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if chat:
        pers = persona_of(dict(chat))
        if isinstance(pers, dict):
            add(persona_name(pers))

    for row in q(
        "SELECT p.sheet FROM chat_personas cp JOIN personas p ON p.id=cp.persona_id "
        "WHERE cp.chat_id=? AND cp.status='active' AND cp.frame_id IS ?",
        (chat_id, frame_id),
    ):
        sheet = normalize_persona_data(json.loads(row["sheet"]))
        add(sheet.get("identity", {}).get("name"))

    return groups


def _extra_personas_in_zone(chat_id, frame_id, scene, zone):
    persona_ids = []
    for row in q(
        "SELECT cp.persona_id, p.sheet FROM chat_personas cp "
        "JOIN personas p ON p.id=cp.persona_id "
        "WHERE cp.chat_id=? AND cp.status='active' AND cp.frame_id IS ?",
        (chat_id, frame_id),
    ):
        sheet = normalize_persona_data(json.loads(row["sheet"]))
        name = sheet.get("identity", {}).get("name")
        if name and _effective_zone(scene, name) == zone:
            persona_ids.append(row["persona_id"])
    return persona_ids


def _cast_char_ids_in_zone(chat_id, frame_id, scene, zone):
    char_ids = []
    for row in active_cast(chat_id, frame_id):
        sheet = json.loads(row["sheet"])
        name = character_name(sheet)
        if _effective_zone(scene, name) == zone:
            char_ids.append(row["id"])
    return char_ids


def detect_split(chat_id, frame_id, turn_idx):
    """Returns the away zone's name if a split should happen this
    commit, else None. Never fires: for an already-spatial frame (no
    nested splits in this slice), for a chat with no attached extra
    personas (nobody to split FROM), or with an active paradox in this
    frame (a temporal wound in progress -- see spatial_frames.py's
    check_and_apply_paradox guard for the reverse direction of this
    same "these two mechanics must not cross" rule)."""
    frame = get_frame(frame_id)
    if frame and frame.get("kind") == "spatial" and frame.get("merged_turn_idx") is None:
        return None
    if get_paradox(chat_id, frame_id):
        return None
    if not q(
        "SELECT 1 FROM chat_personas WHERE chat_id=? AND status='active' LIMIT 1",
        (chat_id,), one=True,
    ):
        return None

    scene = wget(chat_id, "scene", None)
    if not isinstance(scene, dict):
        return None
    groups = zone_groups(chat_id, frame_id, scene)
    if len(groups) < 2:
        return None

    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    primary_name = persona_name(persona_of(dict(chat))) if chat else None
    primary_zone = None
    for zone, members in groups.items():
        if primary_name in members:
            primary_zone = zone
            break

    # The primary player's own zone (if any) always stays with the
    # parent frame in this slice; the first OTHER zone found becomes the
    # away party. If the primary isn't in any zoned room at all, there
    # is no clear "staying" reference frame, so no split fires.
    if primary_zone is None:
        return None
    for zone in groups:
        if zone != primary_zone:
            return zone
    return None


def perform_split(chat_id, parent_frame_id, turn_idx, away_zone):
    """Creates a new spatial child frame for `away_zone`, seeds its
    frame-scoped world state from the parent, partitions cast/personas,
    and returns the new frame_id. One transaction: a half-completed
    split (personas stationed into a frame whose KV was never seeded)
    would be far worse than not splitting this turn at all."""
    with transaction():
        scene = wget(chat_id, "scene", {}) or {}
        away_persona_ids = _extra_personas_in_zone(chat_id, parent_frame_id, scene, away_zone)
        away_char_ids = _cast_char_ids_in_zone(chat_id, parent_frame_id, scene, away_zone)
        stay_char_ids = [
            row["id"] for row in active_cast(chat_id, parent_frame_id)
            if row["id"] not in away_char_ids
        ]

        parent = get_frame(parent_frame_id)
        new_frame_id = create_frame(
            chat_id,
            label=f"Away — {away_zone}",
            ordinal=parent["ordinal"] if parent else 0,
            kind="spatial",
            parent_frame_id=parent_frame_id,
            split_turn_idx=turn_idx,
        )

        # Seed the new frame's scoped keys from the parent -- a
        # never-touched frame otherwise starts blank (frames.py's
        # normal, correct behavior for temporal frames), but a spatial
        # split's away party needs to walk away MID-CONTINUITY, not
        # wake up with amnesia.
        for key, default in (
            ("known", {}), ("simulation_clock", {}), ("standing_intentions", []),
            ("shadow_profile", ""), ("background_presences", {}), ("offscreen_log", []),
        ):
            wset_for_frame(chat_id, key, wget_for_frame(chat_id, key, parent_frame_id, default),
                           new_frame_id)
        for row in active_cast(chat_id, parent_frame_id):
            name = character_name(json.loads(row["sheet"]))
            rel = wget_for_frame(chat_id, f"relationships:{row['id']}", parent_frame_id, None)
            if rel is not None:
                wset_for_frame(chat_id, f"relationships:{row['id']}", rel, new_frame_id)

        away_rooms = {
            rn: r for rn, r in (scene.get("rooms") or {}).items()
            if _room_zone(scene, rn) == away_zone or _room_zone(scene, rn) is None
        }
        # _effective_zone, not a direct room-zone lookup: an occupant
        # inside a vehicle's interior (itself deliberately unzoned) must
        # still be partitioned by where the VEHICLE actually ended up,
        # not silently left out of both sides.
        away_positions = {
            name: room for name, room in (scene.get("positions") or {}).items()
            if _effective_zone(scene, name) == away_zone
        }
        away_scene = {
            **scene, "rooms": away_rooms, "positions": away_positions,
            "entities": scene.get("entities") or {}, "overlays": scene.get("overlays") or {},
            "attire": scene.get("attire") or {},
        }
        wset_for_frame(chat_id, "scene", away_scene, new_frame_id)

        # Parent keeps everyone/everywhere except what just left.
        parent_positions = {
            name: room for name, room in (scene.get("positions") or {}).items()
            if _effective_zone(scene, name) != away_zone
        }
        scene["positions"] = parent_positions
        wset(chat_id, "scene", scene)

        # Cast partition: active_cast folds every base-active character
        # into every frame by default (chat_char_frames overlay falls
        # back to the base row) -- without this, away NPCs would still
        # be "present" back home, and staying NPCs would show up away.
        for char_id in away_char_ids:
            set_char_status(chat_id, char_id, "dormant", frame_id=parent_frame_id)
            set_char_status(chat_id, char_id, "active", frame_id=new_frame_id)
        for char_id in stay_char_ids:
            set_char_status(chat_id, char_id, "dormant", frame_id=new_frame_id)

        if away_persona_ids:
            qi(
                f"UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND persona_id IN "
                f"({','.join('?' * len(away_persona_ids))})",
                (new_frame_id, chat_id, *away_persona_ids),
            )

        notice = {"turn": turn_idx, "kind": "spatial_split", "zone": away_zone}
        for fid in (parent_frame_id, new_frame_id):
            log = wget_for_frame(chat_id, "offscreen_log", fid, [])
            log.append(notice)
            wset_for_frame(chat_id, "offscreen_log", log, fid)

        return new_frame_id


def _spatial_children(chat_id, parent_frame_id):
    # IS, not =: parent_frame_id is None for a split straight off the
    # present, and "x = NULL" is never true in SQL even when x is also
    # NULL -- this would otherwise silently never find children of the
    # present frame.
    return q(
        "SELECT * FROM frames WHERE chat_id=? AND parent_frame_id IS ? "
        "AND kind='spatial' AND merged_turn_idx IS NULL",
        (chat_id, parent_frame_id),
    )


def detect_merge(chat_id, frame_id):
    """Returns (parent_id, child_id) if the given frame's spatial split
    should merge back this commit, else None. Symmetric with
    detect_split: fires when the child's own zone group and the
    parent's now agree on where everyone is standing (same zone, or
    both have no declared zone at all -- either reads as "back
    together"). Works whichever SIDE (parent or child) is the one
    actually committing this turn."""
    frame = get_frame(frame_id)
    if not frame:
        return None
    if frame.get("kind") == "spatial" and frame.get("merged_turn_idx") is None:
        parent_id, child_id = frame.get("parent_frame_id"), frame_id
    else:
        children = _spatial_children(chat_id, frame_id)
        if not children:
            return None
        parent_id, child_id = frame_id, children[0]["id"]

    parent_scene = wget_for_frame(chat_id, "scene", parent_id, {}) or {}
    child_scene = wget_for_frame(chat_id, "scene", child_id, {}) or {}
    parent_zones = set(zone_groups(chat_id, parent_id, parent_scene))
    child_zones = set(zone_groups(chat_id, child_id, child_scene))
    if parent_zones & child_zones:
        return (parent_id, child_id)
    if not parent_zones and not child_zones:
        return (parent_id, child_id)
    return None


def perform_merge(chat_id, parent_frame_id, child_frame_id, turn_idx):
    """Reconciles the child spatial frame back into its parent. One
    transaction; returns a list of deterministic warning strings
    describing anything that had to be resolved non-trivially (clock
    skew, knowledge/relationship conflicts) so the Narrator can render
    the reunion honestly instead of silently pretending nothing
    diverged."""
    warnings = []
    with transaction():
        parent_clock = wget_for_frame(chat_id, "simulation_clock", parent_frame_id, {}) or {}
        child_clock = wget_for_frame(chat_id, "simulation_clock", child_frame_id, {}) or {}
        p_elapsed = float(parent_clock.get("elapsed_seconds") or 0.0)
        c_elapsed = float(child_clock.get("elapsed_seconds") or 0.0)
        if p_elapsed != c_elapsed:
            merged_clock = dict(parent_clock if p_elapsed >= c_elapsed else child_clock)
            warnings.append(
                f"Reunion clock skew: {abs(p_elapsed - c_elapsed):.0f}s more passed for "
                f"{'the parent party' if p_elapsed > c_elapsed else 'the away party'}."
            )
        else:
            merged_clock = parent_clock
        wset_for_frame(chat_id, "simulation_clock", merged_clock, parent_frame_id)

        parent_known = wget_for_frame(chat_id, "known", parent_frame_id, {}) or {}
        child_known = wget_for_frame(chat_id, "known", child_frame_id, {}) or {}
        for who, learned in child_known.items():
            existing = parent_known.setdefault(who, [])
            for name in learned:
                if name not in existing:
                    existing.append(name)
        wset_for_frame(chat_id, "known", parent_known, parent_frame_id)

        for row in active_cast(chat_id, parent_frame_id) + active_cast(chat_id, child_frame_id):
            key = f"relationships:{row['id']}"
            parent_rel = wget_for_frame(chat_id, key, parent_frame_id, None)
            child_rel = wget_for_frame(chat_id, key, child_frame_id, None)
            if child_rel is None:
                continue
            if parent_rel is None:
                wset_for_frame(chat_id, key, child_rel, parent_frame_id)
                continue
            if parent_rel != child_rel:
                warnings.append(
                    f"Relationship record for {character_name(json.loads(row['sheet']))} "
                    "diverged during the separation; the parent frame's version was kept."
                )

        parent_scene = wget_for_frame(chat_id, "scene", parent_frame_id, {}) or {}
        child_scene = wget_for_frame(chat_id, "scene", child_frame_id, {}) or {}
        merged_rooms = {**(parent_scene.get("rooms") or {}), **(child_scene.get("rooms") or {})}
        merged_positions = {**(parent_scene.get("positions") or {}), **(child_scene.get("positions") or {})}
        parent_scene = {**parent_scene, "rooms": merged_rooms, "positions": merged_positions}
        wset_for_frame(chat_id, "scene", parent_scene, parent_frame_id)

        for row in active_cast(chat_id, child_frame_id):
            set_char_status(chat_id, row["id"], "active", frame_id=parent_frame_id)

        qi(
            "UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND frame_id=?",
            (parent_frame_id, chat_id, child_frame_id),
        )
        qi("UPDATE frames SET merged_turn_idx=? WHERE id=?", (turn_idx, child_frame_id))

        notice = {"turn": turn_idx, "kind": "spatial_merge", "warnings": warnings}
        log = wget_for_frame(chat_id, "offscreen_log", parent_frame_id, [])
        log.append(notice)
        wset_for_frame(chat_id, "offscreen_log", log, parent_frame_id)

    return warnings


def detect_and_reconcile(ctx, nonce):
    """The commit-time entry point, mirroring paradox.check_and_apply_paradox's
    shape: call once per turn, after scene/entities/cast have committed
    this turn's state_diff, so detection runs against what actually just
    got committed."""
    chat_id = ctx.chat.id
    frame_id = ctx.turn.frame_id
    turn_idx = ctx.turn.idx

    merge = detect_merge(chat_id, frame_id)
    if merge:
        parent_id, child_id = merge
        warnings = perform_merge(chat_id, parent_id, child_id, turn_idx)
        for w in warnings:
            ctx.add_warning(w)
        return {"merged": True, "parent_frame_id": parent_id, "child_frame_id": child_id,
                "warnings": warnings}

    away_zone = detect_split(chat_id, frame_id, turn_idx)
    if away_zone:
        new_frame_id = perform_split(chat_id, frame_id, turn_idx, away_zone)
        ctx.add_warning(
            f"The party has split -- part of it is now in a separate zone ({away_zone})."
        )
        return {"split": True, "parent_frame_id": frame_id, "child_frame_id": new_frame_id,
                "zone": away_zone}

    return {"active": False}
