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

from story.character_schema import (character_name, normalize_persona_data,
                                    normalized_character_from_text,
                                    persona_name)
from core.db import (_FRAME_KEY_SEP, ERA_WORLD_KEYS, FRAME_SCOPED_WORLD_KEYS, q,
                     qi, transaction, wget, wget_for_frame, wset,
                     wset_for_frame)
from core.frames import create_frame, get_frame
from world.paradox import get_paradox
from story.scene import (CAST_STATUS_ABSENT, active_cast, cast_change_status,
                         persona_of, set_char_state, set_char_status)
from world.spatial import (THRESHOLD_CROSSING_BEATS, _SUBJECT_KEYED, _anchor_dir, _hiding_holders,
                     anchor_bearing_of, effective_adjacent,
                     effective_anchors, has_visual,
                     hear_level, is_alarming, room_of, room_of_record,
                     rooms_adjacent, room_locale, normalize_scene_comms,
                     sound_path, sound_walk_level, spatial_rel,
                     travel_bearing, TURNS, turn_bearing, normalize_bearing,
                     opposite_bearing)

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
    parent_entity = (rooms.get(room_name) or {}).get("parent_entity")
    seen = set()
    while parent_entity and parent_entity not in seen:
        seen.add(parent_entity)
        # `room_of`, not a raw `positions` read: where a holder stands is one
        # question with one resolver (review 2026-09-07, B18), and a vehicle
        # whose position row is filed under its display name or an alias was
        # read here as nowhere -- so a party riding it arrived in no zone.
        ext_room = room_of(scene, parent_entity)
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
    new_positions = new_scene.get("positions") or {}
    entities = new_scene.get("entities") or {}

    party_names = None  # computed lazily -- most commits touch no vehicle at all
    changed = False

    for eid, ent in entities.items():
        if not isinstance(ent, dict) or ent.get("kind") != "vehicle":
            continue
        # The record is in hand, so ask where it IS, not where its id is
        # filed (review 2026-09-07, B18): a ferry whose `positions` row is
        # under "The Ferry" against the id `Ferry_01` crossed the gap
        # unnoticed and stamped no zone on the far side.
        prev_room = room_of_record(prev_scene, eid, ent)
        new_room = room_of_record(new_scene, eid, ent)
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

    # Only a move into a VEHICLE INTERIOR auto-carries co-located companions.
    # Boarding a ship/TARDIS/boat together is a reliable default: people in the
    # room walk aboard with you. A bare GAP-CROSS is NOT -- a teleport or a
    # transporter beam relocates a specific ROSTER ("two to beam down"), and a
    # co-located bystander (the transporter operator at the console, someone
    # left behind) does NOT come along. The gap-cross branch used to carry them
    # anyway, teleporting the operator to the planet surface (TR-1); who moves
    # on a beam/teleport comes from the director/mapping roster, not from here.
    # This restores the function's own stated caution: a gap-cross "risks
    # silently teleporting a character the player actually left behind."
    if not is_vehicle_interior:
        return False

    departed = _cast_changes_leaving(cast_changes)

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


def _cast_changes_leaving(cast_changes):
    """Casefolded names this beat's `cast_changes` send OUT of the scene.

    Reads the STATUS. Three callers of `cast_changes` -- this one, the
    stranded-occupant guard and destruction's vacate -- used to build this set
    from the entries that EXIST, which made an arrival indistinguishable from a
    departure: the same entry that said someone rejoined the story was read as
    proof they had gone.

    ONLY A WORD THE VOCABULARY HOLDS SENDS A BODY OUT (B33). An unrecognized
    status is not an answer, and no reader may turn a non-answer into one:
    `commit_cast_changes` leaves the roster untouched on such a word and warns,
    so counting it as a departure here made the two readers of one entry
    disagree -- the roster said present, the scene said gone. What that cost:
    destruction's vacate pops the position of everyone in this set on the
    stated promise that "the guard has already proven every doomed-room
    occupant repositioned or departed, so this pop can never lose a person",
    and on a word like `"fled"` it lost one -- still `active` in the roster,
    addressable, running a character step every beat, and standing in no room
    at all. Refusing the word here costs at most the stranding raise the guard
    already raises for an occupant with no recorded exit, and that raise names
    the remedy where the silent pop named nothing.
    """
    return {
        str(chg.get("who") or "").casefold()
        for chg in (cast_changes or [])
        if isinstance(chg, dict) and chg.get("who")
        and cast_change_status(chg.get("status")) == CAST_STATUS_ABSENT
    }


def infer_came_from(chat_id, frame_id, prev_scene, new_scene, cast_names):
    """Deterministic per-character orientation, joining the infer_vehicle_zones
    / infer_companion_carry family (called from commit_scene on the merged
    scene before it is persisted).

    When a character's position changes from A to an ADJACENT room B this beat,
    record A as their `came_from` -- the room now at their back, which
    spatial.egocentric_frame reads to place a coherent 'behind'. A non-adjacent
    jump (teleport, gap-cross, long carry) clears came_from AND focus: they are
    disoriented, and asserting a 'behind' would be a guess. Staying put keeps
    the prior orientation. Orientation for a name no longer positioned in the
    scene is pruned. Mutates new_scene['orientation'] in place; returns whether
    anything changed."""
    prev_pos = prev_scene.get("positions") or {}
    new_pos = new_scene.get("positions") or {}
    orientation = new_scene.setdefault("orientation", {})

    names = set(cast_names or [])
    names.update(new_pos.keys())

    changed = False
    for name in names:
        old_r = prev_pos.get(name)
        new_r = new_pos.get(name)
        if not new_r or new_r == old_r:
            continue  # didn't move this beat -> keep existing orientation
        rec = orientation.setdefault(name, {})
        if old_r and rooms_adjacent(prev_scene, old_r, new_r):
            rec["came_from"] = old_r
        else:
            rec["came_from"] = None   # teleport / gap -> disoriented
            rec["focus"] = None
        changed = True

    for name in list(orientation.keys()):
        if name not in new_pos:
            orientation.pop(name, None)  # left the scene
            changed = True

    return changed


def infer_threshold_crossings(chat_id, frame_id, prev_scene, new_scene,
                              cast_names):
    """Deterministic per-body `crossings`, joining the infer_came_from family
    (called from commit_scene on the merged scene, right after it).

    A position field changes in an instant; going through a doorway does not.
    Where the boundary is one sight passes through, that mismatch costs
    nothing -- the room behind keeps watching through the opening. Where the
    boundary is OPAQUE, it made bodies blink out of the world: the beat a body
    stepped through a curtained doorway or into an enclosure, every observer
    behind it lost them completely, mid-step, with nothing narrated as having
    happened.

    So a body that has just crossed an opaque boundary is recorded as still
    crossing: {from, to, beats}. spatial.sight_level floors sight at `shapes`
    for observers in the room they LEFT while the record lives, which is what
    lets them be seen going in without being seen once in. The record is
    decremented each beat the body stays put and dropped the moment it moves
    again or leaves the scene -- so it can only ever make a body visible for
    the crossing itself, never afterwards.

    Mutates new_scene['crossings'] in place; returns whether anything changed.
    """
    prev_pos = prev_scene.get("positions") or {}
    new_pos = new_scene.get("positions") or {}
    crossings = new_scene.get("crossings")
    if not isinstance(crossings, dict):
        crossings = {}

    names = set(cast_names or [])
    names.update(new_pos.keys())
    names.update(crossings.keys())

    changed = False
    for name in names:
        old_r = prev_pos.get(name)
        new_r = new_pos.get(name)

        # A real step this beat, through something sight does not cross.
        if (new_r and old_r and new_r != old_r
                and rooms_adjacent(new_scene, old_r, new_r)
                and not has_visual(spatial_rel(new_scene, old_r, new_r))):
            crossings[name] = {"from": old_r, "to": new_r,
                               "beats": THRESHOLD_CROSSING_BEATS}
            changed = True
            continue

        # The other way a body goes out of sight without changing rooms: being
        # put inside something, or climbing out of it. The room does not change
        # -- a carried body's position is its carrier's -- so the step above
        # cannot see this happen, and without it a body being enclosed would
        # blink out exactly as one crossing a doorway used to.
        #
        # A body with no PREVIOUS position did not climb into anything: it
        # simply came into the scene already inside. `old_r` guards that.
        # Without it the opening turn -- where prev_scene is empty, so every
        # body reads was_hidden=False -- recorded everyone standing in any
        # interior as having just entered it. Observed live: a scene opening
        # inside a vehicle gave BOTH occupants a {from: X, to: X} crossing,
        # including the one whose vehicle it was and who had not moved. The
        # same holds for a body that joins the cast mid-story already enclosed;
        # nobody watched it go in, because it was not there to be watched.
        was_hidden = bool(_hiding_holders(prev_scene, name))
        now_hidden = bool(_hiding_holders(new_scene, name))
        if old_r and new_r and was_hidden != now_hidden:
            crossings[name] = {"from": new_r, "to": new_r,
                               "beats": THRESHOLD_CROSSING_BEATS}
            changed = True
            continue

        rec = crossings.get(name)
        if not isinstance(rec, dict):
            continue

        # Moved on, or gone from the scene: the crossing is over either way.
        if not new_r or new_r != rec.get("to"):
            crossings.pop(name, None)
            changed = True
            continue

        try:
            beats = int(rec.get("beats") or 0) - 1
        except (TypeError, ValueError):
            beats = 0
        if beats > 0:
            crossings[name] = {**rec, "beats": beats}
        else:
            crossings.pop(name, None)
        changed = True

    if changed:
        if crossings:
            new_scene["crossings"] = crossings
        else:
            new_scene.pop("crossings", None)
    return changed


def _thing_forms(text):
    """A label as it is compared: casefolded, collapsed, bare of a leading
    article -- the same normalisation `director._thing_forms` makes, because
    a look names a thing the way the view named it."""
    form = " ".join(str(text or "").split()).casefold()
    for article in ("the ", "a ", "an "):
        if form.startswith(article) and len(form) > len(article):
            return form[len(article):].strip()
    return form


def _room_presences_named(chat_id, frame_id, scene, room):
    """``{label or name: name}`` for the background presences standing in
    this room -- what a body in it may have been SHOWN and what to call them.

    Late import and fail-soft: this module is the scene's, and a presence
    ledger it cannot read is a look that does not resolve rather than a beat
    that does not commit.
    """
    try:
        from agents.background import _room_presences_in
    except Exception:
        return {}

    class _Ctx:
        pass

    ctx = _Ctx()
    ctx.chat = type("_Chat", (), {"id": chat_id})()
    ctx.turn = type("_Turn", (), {"frame_id": frame_id, "idx": None})()
    out = {}
    try:
        for name, label in _room_presences_in(ctx, scene, room) or ():
            if name:
                out[str(name)] = str(name)
                if label:
                    out[str(label)] = str(name)
    except Exception:
        return {}
    return out


def infer_focus(chat_id, frame_id, prev_scene, new_scene, dr_output,
                cast_names, looks=None):
    """Deterministic end-of-beat attention `focus` per character (FOV spec
    rules A/D). Focus is what a character is attending at the END of the beat;
    egocentric_frame renders it 'ahead', and perception gives a focused source
    full visual detail vs a coarse periphery. Runs at commit, AFTER
    infer_came_from (which already clears focus on a disorienting jump).

    Precedence, strongest first (first match wins):
      - addressing/replying to someone -> focus them (a conversation thus auto-
        holds mutual focus with no 'I look at them' tax; cross-room -> the
        doorway toward them, UNLESS this beat's pose names a fixture of the
        speaker's own room, which wins -- see address_focus);
      - moving without addressing anyone -> focus clears (locomotion resets gaze;
        egocentric_frame's pass-through inference still supplies 'ahead');
      - being addressed by someone -> focus the speaker;
      - a DECLARED LOOK -> focus what it names (see look_focus_for; ranks
        under the salience-snap, over the pose anchor);
      - a POSE declared relative to a room anchor -> focus that anchor (see
        anchor_focus_for; ranks under a declared look, over persistence);
      - otherwise focus PERSISTS unchanged (no time decay), except a focused
        target who is no longer co-located is garbage-collected to None.

    Reflexive salience-snap (spec B / G2) is now implemented for the one
    loudness signal the beat already carries deterministically: a RAISED
    dialogue volume (spatial.is_alarming). It ranks BELOW addressing/being
    addressed and below locomotion -- a conversation or a move holds its own
    focus -- and above bare persistence: a bystander whose attention nothing
    else claimed this beat spins toward a shout. The snap target is what the
    perceiver legitimately has: the shouter if co-located, else the edge the
    sound arrived through (for a multi-hop shout that is the FIRST edge of
    the sound path out of their own room -- the doorway the bang came
    through, never the unseen source room). A shout nothing connects them to
    (no hearing channel, no sound path) snaps nothing. DELIBERATE SPEC CHANGE
    landed with the S4a bounded loudness walk; richer per-event loudness
    waits on G1's sound surface."""
    positions = new_scene.get("positions") or {}
    prev_pos = prev_scene.get("positions") or {}
    orientation = new_scene.setdefault("orientation", {})
    dlog = (dr_output or {}).get("dialogue_log") or []

    spoke_to, addressed_by = {}, {}
    for d in dlog:
        if not isinstance(d, dict):
            continue
        sp = str(d.get("speaker") or "").strip()
        tg = str(d.get("intended_target") or "").strip()
        if sp and tg and sp != tg:
            spoke_to[sp] = tg            # last line this beat wins
            addressed_by.setdefault(tg, sp)

    def colocated(a, b):
        return a in positions and b in positions and positions[a] == positions[b]

    def focus_on(name, other):
        """Face `other`: the entity if co-located, else the doorway toward
        their room (edge focus)."""
        if colocated(name, other):
            return {"kind": "target", "ref": other}
        room = positions.get(other)
        return {"kind": "edge", "ref": room} if room else None

    shouts = [(str(d.get("speaker") or "").strip(),
               str(d.get("volume") or "").strip().casefold())
              for d in dlog
              if isinstance(d, dict) and is_alarming(loudness=d.get("volume"))]

    def alarm_focus_for(name):
        """G2: the focus a raised voice snaps this perceiver to, or None."""
        room = positions.get(name)
        if not room:
            return None
        for speaker, volume in shouts:
            if not speaker or speaker == name:
                continue
            s_room = positions.get(speaker)
            if not s_room:
                continue
            if s_room == room:
                return {"kind": "target", "ref": speaker}
            volume = "shout" if volume == "violent" else volume
            rel = spatial_rel(new_scene, room, s_room)
            if rel.get("barrier") != "separated" \
                    and hear_level(rel, volume) != "none":
                return {"kind": "edge", "ref": s_room}
            if sound_walk_level(new_scene, room, s_room, volume) != "none":
                path = sound_path(new_scene, room, s_room)
                if path and len(path) > 1:
                    # The first edge out of the perceiver's OWN room: they
                    # spin toward the doorway the sound came through, which
                    # is all the information they legitimately have.
                    return {"kind": "edge", "ref": path[1]}
        return None

    def anchor_focus_for(name):
        """The focus a body's own POSE declares this beat, or None.

        `poses[name].relative_to` may name a FIXTURE of the room -- a rack, a
        hearth, a doorway -- and `normalize_scene_poses` now keeps it when it
        resolves to an anchor. A body turned toward a fixture has a heading,
        and the room already records where its fixtures are, so this is derived
        geometry rather than a guess.

        Ranked below CO-LOCATED addressing and below the salience-snap (a
        conversation or a shout still claims attention) and ABOVE bare
        persistence -- which is the whole point. It also outranks
        addressing someone in another room, because that resolves to an
        edge and an edge is a whole-body turn; see `address_focus`. A persisted focus is a fact about an EARLIER beat; a
        pose declared THIS beat is fresher evidence of where the body turned.
        Letting persistence win is what kept a doorway in a character's face
        for the rest of a scene after he had turned to the wall.

        A BODY referent is deliberately left alone: leaning against someone is
        not the same claim as facing them, and `relative_to` has always carried
        arrangement rather than gaze for bodies.
        """
        room = positions.get(name)
        if not room:
            return None
        pose = ((new_scene.get("poses") or {}).get(name)) or {}
        ref = str(pose.get("relative_to") or "").strip()
        if not ref or colocated(name, ref):
            return None
        if ref in (effective_anchors(new_scene, room) or {}):
            return {"kind": "anchor", "ref": ref}
        return None

    def look_focus_for(name):
        """The focus a body's own DECLARED LOOK claims this beat, or None.

        A POSE SAYS WHERE A BODY IS BRACED; A LOOK SAYS WHERE IT IS AIMED,
        and until 2026-09-19 only the first reached focus. `_declared_looks`
        already reads `ActionElement.look` off the beat for `infer_facing`,
        so the fact was on the table and the ladder had no rung for it.

        Measured (Aldermill, third run, 30 beats): Sal Weatherby sat on a
        bench to watch a kitchen doorway and the staff going through it --
        "absorbing the low hum of conversation, picking up on the nuances of
        what the seniors and house hands are discussing", every beat -- and
        the scene held `focus {"kind": "anchor", "ref": "bench"}`, because
        her pose was relative to the bench she was sitting on. Perception
        grades detail by focus, so the one thing she was deliberately
        reading was the one thing she was not attending to.

        Resolved against what the room actually holds, in the order the
        sheet offers them ("a body, fixture or exit id"): a co-located body,
        then an anchor of her own room, then an adjacent room. A word that
        names none of those -- including the bare turns `left|right|back|
        around`, which turn a body and name nothing to attend to -- claims
        no focus and falls through to the pose rung.
        """
        want = str((looks or {}).get(name) or "").strip()
        room = positions.get(name)
        if not want or not room:
            return None
        if colocated(name, want):
            return {"kind": "target", "ref": want}
        if want in (effective_anchors(new_scene, room) or {}):
            return {"kind": "anchor", "ref": want}
        for edge in effective_adjacent(new_scene, room) or ():
            if isinstance(edge, dict) and str(edge.get("to") or "") == want:
                return {"kind": "edge", "ref": want}
        # ...AND A PERSON WHO HAS NO CHARACTER SHEET IS STILL A PERSON. A
        # background presence is not in `positions`, is not an anchor and is
        # not a room, so every look at one fell through all three -- the same
        # fact that kept presences out of `present_others`.
        #
        # Measured (Aldermill, fifth run, 2026-09-19): Sal Weatherby, whose
        # drive is to learn who really decides things, declared six looks in
        # eleven rounds and four were at the reeve's deputies, named by the
        # appearance labels she had been shown. Her focus read `null`
        # throughout. She was watching the people she came to watch.
        for label, who in (_room_presences_named(
                chat_id, frame_id, new_scene, room) or {}).items():
            if _thing_forms(label) == _thing_forms(want) \
                    or _thing_forms(who) == _thing_forms(want):
                return {"kind": "target", "ref": who}
        return None

    def address_focus(name, other):
        """The focus speaking to `other` claims -- yielding, when `other` is
        in ANOTHER ROOM, to a pose this beat declared against a fixture.

        A VOICE TURNS A HEAD; IT DOES NOT TURN A BODY THAT IS BRACED
        AGAINST SOMETHING. Addressing someone across a doorway resolves to
        an EDGE focus, and `infer_facing` reads an edge focus as the whole
        body's heading -- so a sentence said over the shoulder spun the
        speaker a full 180 degrees away from what their hands were on. Only
        the cross-room case yields: looking at the person you are talking to
        in your own room is right, is what mutual focus is for, and keeps
        its rank.

        Measured (chat 117, turn 45). Aurel stood at a fire door with
        `stations.at = fire_egress_door`, `poses.relative_to =
        fire_egress_door` ("an eye pressed to the narrow seam"), his right
        hand gripping its handle in `contacts`, and a lit cone lamp in his
        left aimed through the gap. He said one line to Sarah, one room
        below. Focus went to the edge toward her room, facing followed it to
        `s`, the door's anchor bearing was `n` -- and the lamp's cone,
        which takes its axis from the holder's facing, pointed at the wall
        behind him. The composer answered "Through the opening, only
        darkness" and it was right about the field it was given. Every
        egocentric reader is downstream of this: sight, the cone, and
        every left/right in the prose.
        """
        focus = focus_on(name, other)
        if isinstance(focus, dict) and focus.get("kind") == "edge":
            return anchor_focus_for(name) or focus
        return focus

    names = set(cast_names or [])
    names.update(positions.keys())

    changed = False
    for name in names:
        if name not in positions:
            continue  # no focus for an unpositioned name (don't mint empty records)
        rec = orientation.setdefault(name, {})
        moved = name in prev_pos and positions.get(name) != prev_pos.get(name)

        if rec.get("came_from") is None and moved:
            new_focus = None                      # disoriented jump
        elif spoke_to.get(name):
            new_focus = address_focus(name, spoke_to[name]) or rec.get("focus")
        elif moved:
            new_focus = None                      # locomotion resets gaze
        elif addressed_by.get(name):
            new_focus = address_focus(
                name, addressed_by[name]) or rec.get("focus")
        else:
            new_focus = alarm_focus_for(name)     # G2 salience-snap
            if new_focus is None:
                new_focus = look_focus_for(name)   # what they said they watch
            if new_focus is None:
                new_focus = anchor_focus_for(name)
            if new_focus is None:
                new_focus = rec.get("focus")      # persist (no decay)
                if isinstance(new_focus, dict) and new_focus.get("kind") == "target" \
                        and not colocated(name, new_focus.get("ref")):
                    new_focus = None              # focused target left -> GC

        if new_focus != rec.get("focus"):
            rec["focus"] = new_focus
            changed = True
    return changed


def _body_key_named(scene, ref):
    """The positions key `ref` denotes -- the key itself, case-tolerant, or
    an entity whose name is `ref` -- or None."""
    positions = (scene or {}).get("positions") or {}
    want = str(ref or "").strip().casefold()
    if not want:
        return None
    for key in positions:
        if str(key).strip().casefold() == want:
            return key
    for eid, ent in ((scene or {}).get("entities") or {}).items():
        if isinstance(ent, dict) and eid in positions \
                and str(ent.get("name") or "").strip().casefold() == want:
            return eid
    return None


def look_bearing(scene, name, look, prev_facing):
    """Where `name` faces after a declared look, and what it now attends.

    Returns `(facing, focus)`. `left`, `right` and `back` turn the body from
    where it faced (`turn_bearing`; from nowhere, nowhere). `around` is a
    sweep: the facing stands and the caller marks the beat. A compass word
    is that bearing. Anything else is a thing looked at: a co-located body
    (bearing from cell to cell, else the anchor it stands at), a fixture of
    the room (its bearing), or an exit (the way to that room) -- and it
    becomes the focus as well, so the frame and the cone agree.
    """
    from world.spatial import (_anchor_dir, anchor_bearing_of, bearing_between,
                               body_cell, effective_anchors)
    look = str(look or "").strip()
    if not look:
        return None, None
    word = look.casefold()
    if word == "around":
        return prev_facing, None
    if word in TURNS:
        return turn_bearing(prev_facing, word), None
    bearing = normalize_bearing(look)
    if bearing:
        return bearing, None
    room = room_of(scene, name)
    if not room:
        return None, None
    other = _body_key_named(scene, look)
    if other and other != name and room_of(scene, other) == room:
        mine, theirs = body_cell(scene, name), body_cell(scene, other)
        if mine is not None and theirs is not None:
            toward = bearing_between(tuple(mine), tuple(theirs))
        else:
            toward = anchor_bearing_of(scene, other)
        return toward, {"kind": "target", "ref": other}
    anchors = effective_anchors(scene, room) or {}
    if look in anchors:
        return _anchor_dir(scene, room, look), {"kind": "anchor", "ref": look}
    rooms = (scene or {}).get("rooms") or {}
    exit_id = look if look in rooms else next(
        (rid for rid, rm in rooms.items()
         if str((rm or {}).get("name") or "").strip().casefold() == word), None)
    if exit_id and exit_id != room:
        return travel_bearing(scene, room, exit_id), {"kind": "edge", "ref": exit_id}
    return None, None


def _cells_bearing(scene, name, other):
    """Bearing from `name`'s cell to `other`'s, when both stand on cells of
    one room; else None."""
    from world.spatial import bearing_between, body_cell
    key = _body_key_named(scene, other)
    if not key or room_of(scene, key) != room_of(scene, name):
        return None
    mine, theirs = body_cell(scene, name), body_cell(scene, key)
    if mine is None or theirs is None:
        return None
    return bearing_between(tuple(mine), tuple(theirs))


def arrival_facing(scene, from_room, to_room):
    """Which way a body faces on arriving in `to_room` from `from_room`:
    the way it travelled through a door, and INTO THE ROOM off a stair.
    A door's two bearings are opposites, so the travel bearing is also the
    bearing away from the wall just crossed. A stair is one shaft and
    keeps its wall on both floors, so a body that climbed the north stair
    stands at the upper floor's north wall and faces south -- the travel
    bearing would have it facing the wall (Skerry Light turn 3,
    2026-09-15: arrived up the north stair, 'n', the gallery door on the
    south wall rendered "to my right")."""
    rooms = (scene or {}).get("rooms") or {}
    back = next((e for e in ((rooms.get(to_room) or {}).get("adjacent") or [])
                 if isinstance(e, dict) and e.get("to") == from_room), None)
    forward = next((e for e in ((rooms.get(from_room) or {}).get("adjacent") or [])
                    if isinstance(e, dict) and e.get("to") == to_room), None)
    vertical = bool((back or {}).get("vertical") or (forward or {}).get("vertical"))
    if vertical:
        wall = normalize_bearing((back or {}).get("dir")) \
            or normalize_bearing((forward or {}).get("dir"))
        return opposite_bearing(wall) if wall else None
    return travel_bearing(scene, from_room, to_room)


def infer_facing(chat_id, frame_id, prev_scene, new_scene, cast_names,
                 looks=None, turn_idx=None):
    """Deterministic per-character `facing` -- an ABSOLUTE compass bearing --
    joining the infer_came_from / infer_focus family. Runs at commit AFTER both
    (it reads the freshly-set came_from and focus). facing is the observer's
    heading; egocentric_frame combines it with each exit's `dir` bearing to
    derive that exit's LEFT/RIGHT (see spatial.lateral_of).

    Rules (first match wins), per character still positioned this beat:
      - moved A->B but the disorienting-jump path cleared came_from -> facing
        None (heading unknown; suppresses all left/right, the same fail-closed
        idiom as came_from);
      - moved A->B through a bearinged edge -> face the travel bearing; if that
        adjacency carries NO bearing, facing None (we will not guess a heading);
      - stayed put but now facing a doorway (focus is an edge) whose edge has a
        bearing -> face that bearing (turned toward someone across the doorway);
      - stayed put with focus on a room ANCHOR -> face that anchor's bearing
        (turned to a fixture: the rack, the hearth, the window). This is how a
        body turns AWAY from anything -- it turns TOWARD something else, and
        the room is what knows which way each of them lies;
      - otherwise facing PERSISTS unchanged (no decay).
    Names no longer positioned are pruned by infer_came_from already. Mutates
    new_scene['orientation'] in place; returns whether anything changed."""
    prev_pos = prev_scene.get("positions") or {}
    new_pos = new_scene.get("positions") or {}
    orientation = new_scene.setdefault("orientation", {})

    names = set(cast_names or [])
    names.update(new_pos.keys())

    changed = False
    for name in names:
        if name not in new_pos:
            continue
        rec = orientation.setdefault(name, {})
        old_r, new_r = prev_pos.get(name), new_pos.get(name)
        moved = bool(new_r) and new_r != old_r
        prev_facing = rec.get("facing")

        declared = (looks or {}).get(name)
        if declared is None:
            declared = next((v for k, v in (looks or {}).items()
                             if str(k).casefold() == str(name).casefold()), None)
        if declared:
            # A DECLARED LOOK OUTRANKS EVERY INFERENCE (the owner,
            # 2026-09-15: turning and looking are acts). A sweep keeps the
            # facing and marks the beat, so perception lifts the cone for
            # it once. Several looks in one beat apply in order, each from
            # the facing the one before it left, and the last the room can
            # place decides.
            looks_in_order = list(declared) if isinstance(declared, (list, tuple)) else [declared]
            faced, focus, sweep = None, None, False
            facing_so_far = prev_facing
            for one in looks_in_order:
                if not str(one or "").strip():
                    continue
                if str(one).strip().casefold() == "around":
                    sweep = True
                    rec["swept_turn"] = turn_idx
                    continue
                got, got_focus = look_bearing(new_scene, name, one, facing_so_far)
                if got_focus:
                    focus = got_focus
                if got is not None:
                    faced = got
                    facing_so_far = got
            if focus:
                rec["focus"] = focus
            if faced is not None:
                if faced != prev_facing:
                    rec["facing"] = faced
                    changed = True
                continue
            # A LOOK THAT SETS NO BEARING -- a sweep, or a target the room
            # cannot place -- leaves the facing to the inferences below: a
            # body that climbed in through the north wall and looked around
            # faces south, not whatever it faced on the floor below (Skerry
            # Light turn 3, 2026-09-15: arrived up a north stair, swept,
            # kept 'e', and the page put the south door "to my right").
        if moved:
            if rec.get("came_from") is None:
                new_facing = None                 # disoriented jump
            else:
                new_facing = arrival_facing(new_scene, old_r, new_r)
        else:
            focus = rec.get("focus") or {}
            ref = focus.get("ref")
            if focus.get("kind") == "edge" and ref:
                turned = travel_bearing(new_scene, new_r, ref)
                new_facing = turned if turned else prev_facing
            elif focus.get("kind") == "target" and ref and _cells_bearing(
                    new_scene, name, ref) is not None:
                # FROM CELL TO CELL: a body attending another turns toward
                # where that body stands, not only toward a fixture it
                # happens to be at (89 of the owner's 104 unresolved focuses
                # were this case, 2026-09-15).
                new_facing = _cells_bearing(new_scene, name, ref)
            elif focus.get("kind") == "target" and ref:
                # Turned to attend a CO-LOCATED person -> face their anchor's
                # bearing, so a rear source you turn toward deterministically
                # enters your front arc (the blind-spot LIFT that must not
                # depend on a strong narrator honouring a prompt exemption).
                toward = anchor_bearing_of(new_scene, ref)
                new_facing = toward if toward else prev_facing
            elif focus.get("kind") == "anchor" and ref:
                # Turned to a FIXTURE of this room -> face its bearing. The
                # counterpart of the lift above, and the case that was missing:
                # turning toward the towel rack is how a body turns AWAY from
                # the doorway behind it, and only the room knows which way
                # either of them lies.
                toward = _anchor_dir(new_scene, new_r, ref)
                new_facing = toward if toward else prev_facing
            else:
                new_facing = prev_facing          # persist (no decay)
            if new_facing is None:
                # A POSE THAT SAYS WHERE A BODY FACES IS A FACING, when
                # nothing else has said one: "standing at the sideboard,
                # facing the door" was written by the spatial hand and read
                # by nobody (5 such poses in the owner's corpus).
                pose = (new_scene.get("poses") or {}).get(name) or {}
                if isinstance(pose, dict) \
                        and str(pose.get("relation") or "").strip().casefold() == "facing" \
                        and str(pose.get("relative_to") or "").strip():
                    posed, _focus = look_bearing(
                        new_scene, name, pose["relative_to"], prev_facing)
                    if posed:
                        new_facing = posed

        if new_facing != prev_facing:
            rec["facing"] = new_facing
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
        # THE MEMO THAT STILL RAISES (C14 rework). Every one of the four
        # frame-surgery reads below used to be `character_name(json.loads(...))`
        # and aborted the split, merge or toll on a card that would not parse;
        # `character_name_from_text` answers "Unnamed" instead, which would
        # zone an unreadable body into a frame under a name it shares with
        # every other unreadable body. A frame is where a body IS -- getting
        # that wrong silently is worse than stopping -- so these read the
        # memoised normalization, which raises what `json.loads` raises.
        name = character_name(normalized_character_from_text(row["sheet"]))
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


#: The ledgers a frame split partitions and a merge reunites, by SHAPE.
#: Subject-keyed tables: a row belongs to the frame its subject stands in.
#: Record lists whose rows name their parties: a record belongs to the frame
#: the parties stand in. Room-anchored tables: a record belongs to the frame
#: whose rooms it touches. Rooms and positions are the partition itself.
#:
#: ONE LIST, NOT TWO. This used to read `_SUBJECT_KEYED` plus `("attire",
#: "vitals", "overlays")` -- one of which was already in it and two of which
#: were not, so the split partitioned a body's vitals while the SPELLING fold
#: that runs at every merge did not touch them (review 2026-09-07, Section H
#: residual on B4). Two lists of one thing disagree; `_SUBJECT_KEYED` now
#: names all of them and this reads it.
_FRAME_SUBJECT_LEDGERS = tuple(_SUBJECT_KEYED)
_FRAME_RECORD_LEDGERS = ("contacts", "substances")
_FRAME_ROOM_TABLES = ("entities", "passages", "comms", "scents")


def _cf(value):
    return str(value or "").strip().casefold()


def _record_parties(record):
    """The subjects a contact or substance record names."""
    if not isinstance(record, dict):
        return set()
    return {_cf(record.get(key)) for key in
            ("actor", "target", "source", "subject", "body", "holder")
            if _cf(record.get(key))}


def _touches_rooms(key, value, rooms, positions):
    """Does this room-anchored record belong with `rooms`: keyed by one of
    them, positioned in one of them, or naming one in its `rooms`."""
    if str(key) in rooms or _cf(positions.get(str(key))) in {_cf(r) for r in rooms}:
        return True
    if isinstance(value, dict):
        for room in (value.get("rooms") or ()) if isinstance(value.get("rooms"), (list, tuple)) else ():
            if str(room) in rooms:
                return True
        if str(value.get("room") or "") in rooms:
            return True
    return False


def _partition_scene(scene, subjects, rooms):
    """The slice of `scene` that belongs to the frame holding `subjects` in
    `rooms`: subject-keyed rows for those subjects, records naming them,
    room-anchored tables whole (a merge resolves them by room)."""
    subjects = {_cf(s) for s in subjects}
    out = dict(scene)
    for ledger in _FRAME_SUBJECT_LEDGERS:
        table = scene.get(ledger)
        if isinstance(table, dict):
            out[ledger] = {k: v for k, v in table.items() if _cf(k) in subjects}
    for ledger in _FRAME_RECORD_LEDGERS:
        records = scene.get(ledger)
        if isinstance(records, list):
            out[ledger] = [r for r in records if _record_parties(r) & subjects]
    return out


def merge_frame_scenes(parent_scene, child_scene):
    """The parent's scene with the away party's ledgers carried home.

    `{**parent, rooms, positions}` kept the parent's copy of EVERY other
    ledger from the moment of the split, so a persona who changed clothes,
    shrank, was bound, or minted a thing while away lost all of it on
    reunion -- while `perform_split` had handed the child the full ledgers
    to change. For every subject standing in the child scene the child's
    rows win (attire, poses, stations, scales, containment, orientation,
    vitals, overlays, following); a contact or substance record naming a
    child subject is the child's; an entity, passage, channel or scent in a
    child room is the child's; everything else is the parent's.
    """
    parent_scene = dict(parent_scene or {})
    child_scene = child_scene or {}
    child_positions = dict(child_scene.get("positions") or {})
    child_subjects = {_cf(k) for k in child_positions}
    child_rooms = {str(r) for r in (child_scene.get("rooms") or {})}
    merged = dict(parent_scene)
    merged["rooms"] = {**(parent_scene.get("rooms") or {}),
                       **(child_scene.get("rooms") or {})}
    merged["positions"] = {**(parent_scene.get("positions") or {}),
                           **child_positions}
    for ledger in _FRAME_SUBJECT_LEDGERS:
        if ledger == "positions":
            continue
        parent_table = parent_scene.get(ledger)
        child_table = child_scene.get(ledger)
        if not isinstance(parent_table, dict) and not isinstance(child_table, dict):
            continue
        out = {k: v for k, v in (parent_table or {}).items()
               if _cf(k) not in child_subjects}
        out.update({k: v for k, v in (child_table or {}).items()
                    if _cf(k) in child_subjects})
        merged[ledger] = out
    for ledger in _FRAME_RECORD_LEDGERS:
        parent_records = parent_scene.get(ledger)
        child_records = child_scene.get(ledger)
        if not isinstance(parent_records, list) and not isinstance(child_records, list):
            continue
        out = [r for r in (parent_records or [])
               if not (_record_parties(r) & child_subjects)]
        out.extend(r for r in (child_records or [])
                   if _record_parties(r) & child_subjects)
        merged[ledger] = out
    for ledger in _FRAME_ROOM_TABLES:
        parent_table = parent_scene.get(ledger)
        child_table = child_scene.get(ledger)
        if not isinstance(parent_table, dict) and not isinstance(child_table, dict):
            continue
        out = dict(parent_table or {})
        for key, value in (child_table or {}).items():
            if key not in out or _touches_rooms(key, value, child_rooms,
                                                 child_positions):
                out[key] = value
        merged[ledger] = out
    return merged


def perform_split(chat_id, parent_frame_id, turn_idx, away_zone=None, *,
                  bubble=False, away_names=None, away_rooms=None):
    """Creates a new spatial child frame for `away_zone`, seeds its
    frame-scoped world state from the parent, partitions cast/personas,
    and returns the new frame_id. One transaction: a half-completed
    split (personas stationed into a frame whose KV was never seeded)
    would be far worse than not splitting this turn at all.

    `bubble=True` says no human went with them -- a CAUSALITY BUBBLE
    (`world/spatial_bubbles.py`), where the away party is cast alone. The
    mechanics are identical and deliberately so: only `detect_split` ever
    required a persona, and a frame does not care whether the body that
    walked into it was somebody's. What changes is what it is CALLED, in the
    label and the log, because "the party has split" is not true of a villain
    walking out of a room the player is still standing in.

    TWO WAYS TO SAY WHO WENT, because the two detectors know different things.
    `away_zone` is the party split's: a declared locale, and everything
    standing in it goes. `away_names`/`away_rooms` is the bubble's, since a
    range trigger names BODIES rather than a place -- the away side is the
    bodies that left plus the rooms they are standing in, and the parent keeps
    every room as it always has. Exactly one of the two is given; a caller
    that gives neither is asking for a split with no away side at all and gets
    a refusal rather than an empty frame.
    """
    if (away_zone is None) == (away_names is None):
        raise ValueError(
            "perform_split needs an away_zone (a declared locale) or "
            "away_names (the bodies that left), and exactly one of them")
    with transaction():
        scene = wget(chat_id, "scene", {}) or {}
        leaving = {_cf(n) for n in (away_names or [])}
        if away_names is None:
            away_persona_ids = _extra_personas_in_zone(
                chat_id, parent_frame_id, scene, away_zone)
            away_char_ids = _cast_char_ids_in_zone(
                chat_id, parent_frame_id, scene, away_zone)
        else:
            # A bubble is cast alone by construction -- `bubble_split_decision`
            # refuses outright when a human is out there too (refusal 5) -- so
            # there is no persona to station and asking for one would be
            # asking a question whose answer is always the empty list.
            away_persona_ids = []
            away_char_ids = [
                row["id"] for row in active_cast(chat_id, parent_frame_id)
                if _cf(character_name(normalized_character_from_text(row["sheet"])))
                in leaving]
        stay_char_ids = [
            row["id"] for row in active_cast(chat_id, parent_frame_id)
            if row["id"] not in away_char_ids
        ]

        parent = get_frame(parent_frame_id)
        new_frame_id = create_frame(
            chat_id,
            label=(f"Bubble — {', '.join(sorted(away_names))}" if bubble and away_names
                   else f"Bubble — {away_zone}" if bubble
                   else f"Away — {away_zone}"),
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
        # WHAT DESCRIBES THE PARTY IS PARTITIONED; WHAT DESCRIBES THE WORLD
        # IS SHARED. A spatial split is the same era somewhere else -- the
        # child takes the parent's own `ordinal` -- so the town on the other
        # side of the hill is the same town, and a party that walks to it has
        # not left the world, only the room. What is per-PARTY (what they
        # know, their clock, their intentions, their obligations, their log)
        # is theirs and is copied here; what is the WORLD's -- the town's
        # institutions, crowds, roads and notices, the map's regions -- and
        # what is the AUTHOR's -- the Room's mandates, bible and packages --
        # is ONE row per era that every frame of the era resolves to
        # (`db.ERA_WORLD_KEYS`), and is not copied at all.
        #
        # THE WORLD WAS COPIED from 2026-09-17 to 2026-09-23, on the argument
        # that charter is deterministic over one clock so two copies track
        # each other. They did not: each bubble runs its own clock and seeds
        # its own ticks, and a lease wrote only the holding bubble's copy --
        # the same mill hand stood at the weir in one bubble and walked the
        # forecourt in the other (playerless Aldermill, 2026-09-23).
        for key, default in (
            ("known", {}), ("simulation_clock", {}), ("standing_intentions", []),
            ("pending_obligations", []),
            ("shadow_profile", ""), ("background_presences", {}), ("offscreen_log", []),
            # Where the charter's bodies stood at the split: the snapshot
            # this frame's "what moved" is measured against. Without it the
            # child's first beat diffs an empty snapshot and reports the
            # whole population as having just moved.
            ("charter_last_places", {}),
        ):
            wset_for_frame(chat_id, key, wget_for_frame(chat_id, key, parent_frame_id, default),
                           new_frame_id)
        for row in active_cast(chat_id, parent_frame_id):
            name = character_name(normalized_character_from_text(row["sheet"]))
            rel = wget_for_frame(chat_id, f"relationships:{row['id']}", parent_frame_id, None)
            if rel is not None:
                wset_for_frame(chat_id, f"relationships:{row['id']}", rel, new_frame_id)

        if away_names is None:
            # _effective_zone, not a direct room-zone lookup: an occupant
            # inside a vehicle's interior (itself deliberately unzoned) must
            # still be partitioned by where the VEHICLE actually ended up,
            # not silently left out of both sides.
            away_positions = {
                name: room for name, room in (scene.get("positions") or {}).items()
                if _effective_zone(scene, name) == away_zone
            }
        else:
            away_positions = {
                name: room for name, room in (scene.get("positions") or {}).items()
                if _cf(name) in leaving
            }
        # A SPLIT PARTITIONS BODIES, NOT THE MAP. The child used to get a
        # SUBSET of the rooms -- the away zone's and the unzoned ones, or the
        # away party's own reach -- while the parent kept every room including
        # the ones the child took. That asymmetry had no argument behind it
        # and one large consequence: the away frame could never gain a room.
        # The player's frame grows as the Director plants places; the child's
        # map was frozen at the instant of the split, so anywhere the party
        # was GOING did not exist for them.
        #
        # Measured live (Aldermill, `google/gemini-3.8-flash`, 2026-09-17): a
        # companion split off with two rooms, and on all four of her own beats
        # she walked east toward a watermill that was not in her world --
        # "trudges steadily eastward along the packed cart ruts", four times,
        # `state_diff.positions` null every time, her memory of it "I was in
        # River Road." The Director was right to refuse; there was nowhere to
        # put her. The player's frame held sixteen rooms by then and hers
        # still held two.
        #
        # A map is not a perception. Which rooms a scene DESCRIBES says
        # nothing about what a body in it can see or hear -- that is
        # `spatial_rel` and the senses, off positions -- and the parent has
        # always held the whole map without that being a leak. Two rooms in
        # different declared locales report `remote` and no edge joins them,
        # so holding a room is not being able to walk to it either.
        away_rooms = dict(scene.get("rooms") or {})
        # SYMMETRIC PARTITION: each frame carries the subject-keyed rows and
        # the records of the bodies standing in it, and the room-anchored
        # tables whole (the merge resolves those by room). The child used to
        # take every ledger and the parent keep every ledger, and the merge
        # then kept the parent's -- see `merge_frame_scenes`.
        away_scene = {
            **_partition_scene(scene, away_positions, away_rooms),
            "rooms": away_rooms, "positions": away_positions,
        }
        wset_for_frame(chat_id, "scene", away_scene, new_frame_id)

        # Parent keeps everyone/everywhere except what just left.
        parent_positions = {
            name: room for name, room in (scene.get("positions") or {}).items()
            if (name not in away_positions if away_names is not None
                else _effective_zone(scene, name) != away_zone)
        }
        scene = {**_partition_scene(scene, parent_positions, set(scene.get("rooms") or {})),
                 "positions": parent_positions}
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

        notice = {"turn": turn_idx,
                   "kind": "causality_bubble" if bubble else "spatial_split",
                   "zone": away_zone,
                   "characters": sorted(away_names) if away_names else []}
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
    # Merge is one-way and unrecoverable: perform_merge sets merged_turn_idx,
    # which restores permanent bidirectional memory visibility across the two
    # parties. It must therefore fail CLOSED -- require POSITIVE evidence that
    # the parties are genuinely back together before collapsing the split.
    #
    # Two valid signals: (a) both sides positively share a declared zone, or
    # (b) a member of each side is standing in the SAME room (a reunion in an
    # as-yet-unzoned room). The previously-present "both zone sets empty"
    # branch is a bug: two EMPTY zone sets -- e.g. each party in its own
    # newly-created, not-yet-zoned room light-years apart -- is the ABSENCE of
    # evidence, not evidence of reunion, and merging on it leaked permanent
    # bidirectional memory across an active split.
    if parent_zones & child_zones:
        return (parent_id, child_id)
    if _parties_share_a_room(chat_id, parent_id, parent_scene, child_id, child_scene):
        return (parent_id, child_id)
    # A BUBBLE HAS NO HUMAN PARTY, SO NEITHER SIGNAL ABOVE CAN EVER FIRE FOR
    # ONE. Both read `zone_groups`/`_all_party_names`, which are the primary
    # player and the personas stationed in a frame -- a causality bubble has
    # none of either by construction, so its zone set is empty and its party
    # rooms are empty, and a bubble opened once could never close. The bodies
    # a bubble answers for are its CAST, and the question is otherwise the
    # same one: is a body of each side standing in one place.
    if is_bubble_frame(chat_id, child_id) and _bubble_rejoined(
            chat_id, parent_id, parent_scene, child_id, child_scene):
        return (parent_id, child_id)
    return None


def is_bubble_frame(chat_id, frame_id):
    """A live spatial frame no human is playing in.

    DERIVED, never stored. Whether a frame is a bubble is exactly whether any
    body it answers for is a person somebody is playing, and that is already
    written down in two places the engine keeps current -- the persona
    stations and the scene's own positions. A third copy on the frame row
    would be a fact stored twice, free to disagree with both the moment a
    player joins an away party or leaves one.
    """
    frame = get_frame(frame_id)
    if (not frame or frame.get("kind") != "spatial"
            or frame.get("merged_turn_idx") is not None):
        return False
    positions = (wget_for_frame(chat_id, "scene", frame_id, {}) or {}).get("positions") or {}
    placed = {_cf(name) for name in positions}
    return not any(_cf(name) in placed for name in _all_party_names(chat_id, frame_id))


def _bubble_cast_places(chat_id, frame_id, scene):
    """(rooms, zones) the bubble's cast are standing in, in its own scene."""
    rooms, zones = set(), set()
    for row in active_cast(chat_id, frame_id):
        name = character_name(normalized_character_from_text(row["sheet"]))
        if not name:
            continue
        room = room_of(scene, name)
        if room:
            rooms.add(str(room))
        zone = _effective_zone(scene, name)
        if zone:
            zones.add(zone)
    return rooms, zones


def _bubble_rejoined(chat_id, parent_id, parent_scene, child_id, child_scene):
    """Is a bubble's cast back inside the player's causality bubble.

    THE SAME PREDICATE THE SPLIT USED, ASKED BACKWARDS, and it has to be: a
    trigger and a release stated in two vocabularies is a body that leaves on
    one rule and can only return under another. With a zone trigger that was
    survivable -- a zone is a place, and walking back into it is the same fact
    read either way. With a RANGE trigger it is not: a body could step out of
    the beat's reach, get a frame, walk back into the next room, and stay in
    it forever because nobody had labelled anything.

    So: the bubble ends when one of its bodies is standing in a room the
    parent's beat attends to. `in_range_rooms` is computed on the PARENT's
    scene (which keeps every room, so it can name hers) and her position is
    read from her OWN scene (which is the only place it exists after the
    split) -- each side asked about the half it actually holds.

    Fails CLOSED for the reason the merge fails closed everywhere: it is
    one-way, and it restores permanent bidirectional memory visibility.
    """
    from world.spatial_bubbles import in_range_rooms

    in_range = in_range_rooms(parent_scene, _all_party_names(chat_id, parent_id))
    if not in_range:
        return False
    cast_rooms, _zones = _bubble_cast_places(chat_id, child_id, child_scene)
    return bool(cast_rooms & in_range)


def _parties_share_a_room(chat_id, parent_id, parent_scene, child_id, child_scene):
    """True iff at least one member of the parent side and one member of the
    child side are standing in the same room id. This is the only "no
    declared zone yet" reunion signal safe to merge on -- unlike two empty
    zone sets, a shared room id is positive proof of co-location, not merely
    the absence of a zone tag. Rooms live in separate frame-scoped scenes, so
    membership is resolved per side against that side's own positions."""
    parent_positions = parent_scene.get("positions") or {}
    child_positions = child_scene.get("positions") or {}
    parent_rooms = {
        parent_positions.get(name)
        for name in _all_party_names(chat_id, parent_id)
        if parent_positions.get(name)
    }
    if not parent_rooms:
        return False
    for name in _all_party_names(chat_id, child_id):
        if child_positions.get(name) in parent_rooms:
            return True
    return False


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
                    "Relationship record for "
                    f"{character_name(normalized_character_from_text(row['sheet']))} "
                    "diverged during the separation; the parent frame's version was kept."
                )

        parent_scene = wget_for_frame(chat_id, "scene", parent_frame_id, {}) or {}
        child_scene = wget_for_frame(chat_id, "scene", child_frame_id, {}) or {}
        parent_scene = merge_frame_scenes(parent_scene, child_scene)
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


# ===================================================================== couples
#
# A COUPLE CARRIES A VOICE BETWEEN TWO FRAMES AND MOVES NOTHING ELSE. Not a
# body, not a room, not a cast list, not one line of anybody's memory ledger.
# The three ways this feature could destroy the firewall are one mistake
# wearing different clothes -- treating "they can talk" as "they are together"
# -- so every rule below is stated in the direction that keeps them apart.
#
# WHY A FRAME AND NOT A CROSS-FRAME READ. Every reader in `agents/` resolves
# one scene through one active frame (`db.active_frame_id`), so a beat where
# both parties speak has to be played somewhere both parties exist. The couple
# frame is that somewhere: the fused view MATERIALISED as storage, so
# `get_scene`, the composer, `spatial_rel` and `comms_link` all work unchanged
# and do the separation work for free -- two rooms in different locales report
# `remote`, which is opaque to sight, scent and a shout alike.
#
# WHAT IS NOT NEGOTIABLE: `merged_turn_idx` is never touched on either member.
# It is the whole of what keeps the two sides' ledgers incomparable
# (`core/frames.is_memory_visible`), there is no un-merge, and a radio must not
# be able to hand each side the other's entire separation.

#: One live couple's partition map, chat-global (it must be readable from any
#: frame, including from neither). Deleted by `close_couple`.
COUPLE_MAP_PREFIX = "couple:"

#: The scene tables a couple partitions back by RECORDED OWNERSHIP rather than
#: by shape. `_partition_scene` answers by subject and `_touches_rooms` by
#: room, and both are the right question for a SPLIT -- which starts from one
#: scene and has to decide where each row goes. A couple starts from two
#: scenes that already decided, so the answer is simply what each side brought:
#: recorded at open, restored at close, with only genuinely NEW keys needing a
#: rule. That is what makes the close total rather than best-effort.
_COUPLE_DICT_TABLES = ("rooms", "positions") + tuple(
    k for k in _FRAME_SUBJECT_LEDGERS if k != "positions") + _FRAME_ROOM_TABLES


#: "this frame has no row for that key", which is NOT the same answer as "its
#: row holds null". `wget` returns a stored JSON null verbatim and its default
#: only when the ROW is missing, so copying a key a frame does not have into
#: the couple and back would write an explicit null where there had been
#: nothing -- and every reader that passes a real default (`{}`, `[]`) would
#: get None from then on, per key, per call, forever.
_ABSENT = object()


def _copy_key(chat_id, key, src_frame, dst_frame):
    """Copy one frame-scoped key between frames, absence included."""
    value = wget_for_frame(chat_id, key, src_frame, _ABSENT)
    if value is not _ABSENT:
        wset_for_frame(chat_id, key, value, dst_frame)


def couple_map_key(couple_frame_id):
    return f"{COUPLE_MAP_PREFIX}{couple_frame_id}"


def couple_map(chat_id, couple_frame_id):
    """The map recorded when this couple opened, or {} when it is not live."""
    if couple_frame_id is None:
        return {}
    value = wget(chat_id, couple_map_key(couple_frame_id), None)
    return value if isinstance(value, dict) else {}


def live_couple_for(chat_id, frame_id):
    """The couple frame currently fusing `frame_id` with another, or None.

    Answered off the frames table rather than off a scan of world rows: a
    couple frame names its home member as `parent_frame_id`, and the map names
    both. `merged_turn_idx` on the COUPLE's own row is what "the call ended"
    means -- it says nothing about either member.
    """
    for row in q(
        "SELECT id FROM frames WHERE chat_id=? AND kind='couple' "
        "AND merged_turn_idx IS NULL",
        (chat_id,),
    ):
        if frame_id in (couple_map(chat_id, row["id"]).get("members") or []):
            return row["id"]
    return None


def couple_member_frame(chat_id, frame_id, *, char_id=None, name=None):
    """Which MEMBER frame a mind belongs to while a couple is open.

    `frame_id` unchanged for every frame that is not a live couple, which is
    almost every call -- an ordinary chat never reaches past the first line.

    This is the function that keeps a coupled beat from having a shared era.
    A memory formed during a call is stamped with its subject's own member
    frame, and a mind reading its ledger during a call reads it as a native of
    that same frame. If a couple frame id ever reached either side of that,
    the two ledgers would share an era and the incomparability rule would have
    nothing to bite on.

    Falls back to the HOME member when the subject cannot be placed on either
    side -- never to the couple frame itself, which is the one answer that
    could do damage.
    """
    themap = couple_map(chat_id, frame_id)
    if not themap:
        return frame_id
    home = themap.get("home")
    if char_id is not None:
        for side in ("a", "b"):
            if int(char_id) in (themap.get("cast") or {}).get(side, []):
                return (themap.get("members") or [home, home])[0 if side == "a" else 1]
    if not name:
        row = q("SELECT sheet FROM characters WHERE id=?", (char_id,), one=True) \
            if char_id is not None else None
        if row:
            name = character_name(normalized_character_from_text(row["sheet"]))
    if name:
        owner = (themap.get("bodies") or {}).get(str(name))
        if owner is not None:
            return (themap.get("members") or [home, home])[0 if owner == "a" else 1]
    return home


def _side_of_room(themap, room_id):
    return (themap.get("rooms") or {}).get(str(room_id))


def _recorded_side_scene(themap, side):
    return (themap.get("sides") or {}).get(side) or {}


def _stamp_locales(fused, themap):
    """Say, on the rooms themselves, which locale each one is in.

    A couple fuses two room dicts into one, and `spatial_rel` then reports
    `separated` for any pair with no edge between them -- which is the right
    answer for two rooms in one building and the wrong one for two rooms a
    frame split put in different places, because `hear_level` gives
    `separated` a shout as a `fragment`. A declared `zone` already says
    "somewhere else" and is read as a locale; a room the split carried away
    WITHOUT a zone of its own says nothing, and those are the ones stamped.

    Occupancy decides first, because a shared, unzoned room id exists on both
    sides by construction (`perform_split` gives the child every unzoned room
    while the parent keeps all of them) and only one side is standing in it --
    `couple_decision` refuses outright when both are.
    """
    rooms = fused.get("rooms") or {}
    for room_id, room in rooms.items():
        if not isinstance(room, dict) or room_locale(room):
            continue
        side = _side_of_room(themap, room_id)
        if side:
            room["locale"] = f"frame:{side}"
    return fused


def _strip_locales(scene):
    for room in (scene.get("rooms") or {}).values():
        if isinstance(room, dict):
            room.pop("locale", None)
    return scene


def _channel_touches(channel, rooms, positions):
    """Does this comm channel belong to the side holding `rooms`/`positions`.

    Its own rule rather than `_touches_rooms`, which answers for entities,
    passages and scents and would drop a handset from BOTH sides: a carried
    channel names no room at all, which is the one channel shape that is even
    expressible across a split.
    """
    if not isinstance(channel, dict):
        return False
    for room_id in (channel.get("rooms") or []):
        if str(room_id) in rooms:
            return True
    for carrier in (channel.get("carriers") or []):
        if _cf(positions.get(str(carrier))) in {_cf(r) for r in rooms} or \
                str(carrier) in positions:
            return True
    return False


def detect_couple(chat_id, frame_id):
    """`(home_frame_id, away_frame_id)` if a live channel should be joining
    these two frames right now, else None. Read-only.

    Asked the same way whether or not a couple is already open, which is what
    makes it usable for both ends of the call: the caller opens on a pair it
    has no couple for, and closes an open couple the moment this answers None.
    Liveness is a fact about the world, not a mode the couple latches --
    somebody keying a handset off must end the fusion on that beat.

    Canonical order is (parent, child): a couple is always between a spatial
    split and the frame it split from, and the parent is HOME -- the side the
    primary player stays with by construction (`perform_split` never moves
    them), and therefore the side everything not about a body belongs to.
    """
    from world import spatial_bubbles

    frame = get_frame(frame_id)
    if frame is None:
        return None

    if frame.get("kind") == "couple" and frame.get("merged_turn_idx") is None:
        themap = couple_map(chat_id, frame_id)
        members = themap.get("members") or []
        if len(members) != 2:
            return None
        if get_paradox(chat_id, members[0]) or get_paradox(chat_id, members[1]):
            return None
        scene = wget_for_frame(chat_id, "scene", frame_id, {}) or {}
        names_a = list((themap.get("names") or {}).get("a") or [])
        names_b = list((themap.get("names") or {}).get("b") or [])
        ended = spatial_bubbles.uncouple_decision(scene, names_a, names_b)
        return None if ended else (members[0], members[1])

    if frame.get("kind") == "spatial" and frame.get("merged_turn_idx") is None:
        pairs = [(frame.get("parent_frame_id"), frame_id)]
    else:
        pairs = [(frame_id, row["id"])
                 for row in _spatial_children(chat_id, frame_id)]

    for parent_id, child_id in pairs:
        if live_couple_for(chat_id, child_id):
            continue
        if spatial_bubbles.detect_couple_between_frames(chat_id, parent_id, child_id):
            return (parent_id, child_id)
    return None


def open_couple(chat_id, a_id, b_id, *, turn_idx):
    """Fuse two spatial frames into a temporary couple frame. Returns its id.

    One transaction: a half-opened couple -- a frame holding a fused scene
    with no map to partition it back by -- is unrecoverable, where not
    coupling this beat costs one beat of a conversation.

    WHAT IS RECORDED, and why it is each side's whole scene rather than a
    clever summary: the close has to be TOTAL. A couple opens and closes
    repeatedly over one conversation, so anything the round trip drops is
    dropped again per cycle -- invisible on the first and total by the tenth.
    Ownership answered from "what each side brought" cannot drop anything,
    because every key that existed is in exactly one of the two records.
    """
    from world import spatial_bubbles

    with transaction():
        scene_a = wget_for_frame(chat_id, "scene", a_id, {}) or {}
        scene_b = wget_for_frame(chat_id, "scene", b_id, {}) or {}
        parent = get_frame(a_id)
        away = get_frame(b_id)

        couple_id = create_frame(
            chat_id,
            label=f"Coupled — {(away or {}).get('label') or 'away'}",
            ordinal=(parent or {}).get("ordinal", 0),
            kind="couple",
            parent_frame_id=a_id,
            split_turn_idx=turn_idx,
        )

        rooms_a = {str(r) for r in (scene_a.get("rooms") or {})}
        rooms_b = {str(r) for r in (scene_b.get("rooms") or {})}
        occupied_a = {str(r) for r in (scene_a.get("positions") or {}).values() if r}
        occupied_b = {str(r) for r in (scene_b.get("positions") or {}).values() if r}
        room_side = {}
        for room_id in rooms_a | rooms_b:
            if room_id in occupied_a:
                room_side[room_id] = "a"
            elif room_id in occupied_b:
                room_side[room_id] = "b"
            elif room_id in rooms_a and room_id not in rooms_b:
                room_side[room_id] = "a"
            elif room_id in rooms_b and room_id not in rooms_a:
                room_side[room_id] = "b"
            else:
                room_side[room_id] = "a"

        bodies = {str(n): "a" for n in (scene_a.get("positions") or {})}
        bodies.update({str(n): "b" for n in (scene_b.get("positions") or {})})

        cast = {
            "a": [int(r["id"]) for r in active_cast(chat_id, a_id)],
            "b": [int(r["id"]) for r in active_cast(chat_id, b_id)],
        }
        names = {
            "a": spatial_bubbles.frame_body_names(chat_id, a_id),
            "b": spatial_bubbles.frame_body_names(chat_id, b_id),
        }
        personas = {
            str(row["persona_id"]): row["frame_id"]
            for row in q(
                "SELECT persona_id, frame_id FROM chat_personas "
                "WHERE chat_id=? AND status='active' AND (frame_id IS ? OR frame_id IS ?)",
                (chat_id, a_id, b_id),
            )
        }
        clocks = {
            "a": wget_for_frame(chat_id, "simulation_clock", a_id, {}) or {},
            "b": wget_for_frame(chat_id, "simulation_clock", b_id, {}) or {},
        }

        themap = {
            "members": [a_id, b_id], "home": a_id, "opened_turn": turn_idx,
            "rooms": room_side, "bodies": bodies, "cast": cast, "names": names,
            "personas": personas, "clocks": clocks,
            "sides": {"a": scene_a, "b": scene_b},
            # What the fuse produced for the keys BOTH sides brought, and only
            # those: the close compares against it to tell the fuse's own
            # choice from a change the beat made. Only the overlap, because
            # only the overlap had a choice to make.
            "fused_at_open": {},
        }

        # The fused scene. `merge_frame_scenes` is the reunion's own fuser and
        # is reused deliberately: the view a couple plays in is exactly the
        # view a reunion would produce, and one fuser cannot drift from
        # another. `comms` is the exception -- the channel rule is the
        # bubbles module's (silence is not refusal, hanging up is, a contested
        # channel is no channel) and it is the whole predicate this feature
        # rests on.
        fused = merge_frame_scenes(scene_a, scene_b)
        # A REFUSED CHANNEL IS A DEVICE, NOT A NOTHING. `fuse_comms` answers
        # which channels the two frames can be HELD to -- silence on one side
        # is not refusal, hanging up is, and a channel whose two copies
        # disagree has no fact of the matter -- and that is the right question
        # for the decision. It is the wrong answer for the SCENE: dropping the
        # ones it refuses would delete a dead intercom in the away frame the
        # first time anybody made an unrelated phone call, and again per call.
        # They come through the call as records that are not carrying, which
        # is what a hung-up handset is, and the close hands each side its own
        # copy back untouched.
        carried = spatial_bubbles.fuse_comms(scene_a, scene_b)
        every = {**((scene_b.get("comms") or {}) if isinstance(
                       scene_b.get("comms"), dict) else {}),
                 **((scene_a.get("comms") or {}) if isinstance(
                       scene_a.get("comms"), dict) else {})}
        fused["comms"] = {**{cid: {**chan, "live": False}
                             for cid, chan in every.items() if cid not in carried},
                          **carried}
        _stamp_locales(fused, themap)
        # Rooms have just changed, and `comms_link` does not prune a channel
        # naming a room nobody can stand in -- `normalize_scene_comms` does,
        # once rooms have settled. They have settled here.
        normalize_scene_comms(fused)
        themap["fused_at_open"] = _overlap_snapshot(fused, scene_a, scene_b)
        wset_for_frame(chat_id, "scene", fused, couple_id)

        # `known` is keyed by WHO, so fusing it is a union of two disjoint
        # answers rather than a judgement; the close hands each key back to
        # the side that brought it.
        raw_a = wget_for_frame(chat_id, "known", a_id, _ABSENT)
        raw_b = wget_for_frame(chat_id, "known", b_id, _ABSENT)
        known_a = raw_a if isinstance(raw_a, dict) else {}
        known_b = raw_b if isinstance(raw_b, dict) else {}
        themap["known"] = {"a": sorted(known_a), "b": sorted(known_b),
                           # Absence again, and `known` is the one fused key
                           # where it can arise on either side: a story that
                           # has never learned a name has no row, and a close
                           # that wrote `{}` back would invent one.
                           "had": {"a": raw_a is not _ABSENT,
                                   "b": raw_b is not _ABSENT}}
        if raw_a is not _ABSENT or raw_b is not _ABSENT:
            wset_for_frame(chat_id, "known", {**known_a, **known_b}, couple_id)

        # Every other frame-scoped key is the HOME frame's. A couple is the
        # home frame's beat with a voice from elsewhere in it. An era key --
        # a charter, a crowd, a courier on the road, the room's own mandates
        # -- is not copied at all: the couple is the same era, so it already
        # reads the one row (`db.ERA_WORLD_KEYS`), and copying it would write
        # that row onto itself.
        for key in sorted(FRAME_SCOPED_WORLD_KEYS):
            if key in ("scene", "known") or key in ERA_WORLD_KEYS:
                continue
            _copy_key(chat_id, key, a_id, couple_id)
        for side, member in (("a", a_id), ("b", b_id)):
            for char_id in cast[side]:
                _copy_key(chat_id, f"relationships:{char_id}", member, couple_id)

        # THE COUPLE'S CAST IS THE UNION OF ITS TWO MEMBERS' AND NOTHING ELSE.
        # `active_cast` falls back to the BASE `chat_chars` row in a frame that
        # has no override, which is exactly right for a fresh spatial child
        # walking away mid-continuity and exactly wrong here: a character
        # `perform_split` made dormant in BOTH frames still reads active off
        # the base row, so a body nobody's story has on stage would have walked
        # into the call. Stated explicitly, per character, and deleted whole at
        # close.
        in_call = set(cast["a"]) | set(cast["b"])
        for row in q("SELECT char_id FROM chat_chars WHERE chat_id=? AND status='active'",
                     (chat_id,)):
            char_id = int(row["char_id"])
            set_char_status(chat_id, char_id, "active" if char_id in in_call else "dormant",
                            frame_id=couple_id)

        if personas:
            qi(
                f"UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND persona_id IN "
                f"({','.join('?' * len(personas))})",
                (couple_id, chat_id, *[int(p) for p in personas]),
            )

        wset(chat_id, couple_map_key(couple_id), themap)

        notice = {"turn": turn_idx, "kind": "couple_open",
                  "frames": [a_id, b_id]}
        log = wget_for_frame(chat_id, "offscreen_log", couple_id, []) or []
        log.append(notice)
        wset_for_frame(chat_id, "offscreen_log", log, couple_id)

        return couple_id


def _overlap_snapshot(fused, scene_a, scene_b):
    """The fused value of every key BOTH sides brought, per table."""
    out = {}
    for ledger in ("rooms",) + _FRAME_ROOM_TABLES:
        table = fused.get(ledger)
        if not isinstance(table, dict):
            continue
        in_a = set(scene_a.get(ledger) or {}) if isinstance(
            scene_a.get(ledger), dict) else set()
        in_b = set(scene_b.get(ledger) or {}) if isinstance(
            scene_b.get(ledger), dict) else set()
        shared = {k: v for k, v in table.items() if k in in_a and k in in_b}
        if shared:
            out[ledger] = shared
    return out


def _own_or_fused(fused_now, own, fused_at_open):
    """Which copy of a key BOTH sides brought this side gets back.

    The fuse has to pick ONE copy of each shared key to play in -- one scene
    cannot hold two versions of one room -- and the CLOSE must not let that
    choice propagate. A split hands the child every unzoned room and every
    room-anchored table whole while the parent keeps all of them, so the two
    id spaces overlap by construction and then diverge independently for as
    long as the parties are apart. Handing the fused copy back to both sides
    would overwrite the home frame's attic with the away frame's every time
    somebody picked up a radio, and again per call.

    The test is UNTOUCHED SINCE THE FUSE, compared against what the fuse
    itself produced rather than against the other side's copy. Two things need
    the stricter question. A channel `fuse_comms` REFUSED -- hung up on one
    side, or contested -- is carried into the call as not-live rather than
    dropped, so it matches neither side's copy and would otherwise come back
    dead to both; and a beat that edits a shared room to exactly what the
    other side happened to be holding is a real edit, not the fuse's choice.

    So: untouched since the fuse means this side gets its own copy back.
    Changed during the call means the beat did that, and both sides get it --
    somebody did it to the one room both frames answer for.
    """
    if own is not _ABSENT and fused_at_open is not _ABSENT \
            and fused_now == fused_at_open:
        return own
    return fused_now


def _partition_side(fused, themap, side):
    """One member's scene, back out of the fused view.

    RECORDED OWNERSHIP FIRST, a rule only for what is new. Everything the side
    brought is its own again; a room a body walked into comes with the body,
    because a body must never be positioned in a room its own frame does not
    hold; and a key neither side brought is assigned by the same touch rules a
    split uses, falling back to home so that nothing is ever simply dropped.
    """
    home_side = "a" if themap.get("home") == (themap.get("members") or [None])[0] else "b"
    brought = _recorded_side_scene(themap, side)
    out = {}

    fused_rooms = fused.get("rooms") or {}
    fused_positions = fused.get("positions") or {}

    rooms = {str(r) for r in (brought.get("rooms") or {}) if str(r) in fused_rooms}
    positions = {}
    for name, room in fused_positions.items():
        owner = (themap.get("bodies") or {}).get(str(name))
        if owner is None:
            owner = _side_of_room(themap, room) or home_side
        if owner == side:
            positions[str(name)] = room
            if room:
                rooms.add(str(room))            # they walked there; it is theirs now
    for room_id in fused_rooms:
        if room_id in rooms:
            continue
        if _side_of_room(themap, room_id) is None:
            # Minted during the call. It belongs to whoever is standing in it,
            # and to home when nobody is.
            standing = {str(n) for n, r in fused_positions.items() if str(r) == str(room_id)}
            owner = next((themap.get("bodies", {}).get(n) for n in sorted(standing)
                          if themap.get("bodies", {}).get(n)), None) or home_side
            if owner == side:
                rooms.add(str(room_id))

    at_open = themap.get("fused_at_open") or {}
    out["rooms"] = {
        rid: _own_or_fused(fused_rooms[rid],
                           (brought.get("rooms") or {}).get(rid, _ABSENT),
                           (at_open.get("rooms") or {}).get(rid, _ABSENT))
        for rid in sorted(rooms) if rid in fused_rooms
    }
    out["positions"] = positions

    subjects = {_cf(n) for n in positions}
    for ledger in _FRAME_SUBJECT_LEDGERS:
        if ledger == "positions":
            continue
        table = fused.get(ledger)
        if not isinstance(table, dict):
            continue
        out[ledger] = {k: v for k, v in table.items() if _cf(k) in subjects}
    for ledger in _FRAME_RECORD_LEDGERS:
        records = fused.get(ledger)
        if not isinstance(records, list):
            continue
        kept = []
        for record in records:
            parties = _record_parties(record)
            if parties & subjects:
                kept.append(record)
            elif not parties and side == home_side:
                kept.append(record)         # names nobody: never simply dropped
        out[ledger] = kept
    other_brought = _recorded_side_scene(themap, "b" if side == "a" else "a")
    for ledger in _FRAME_ROOM_TABLES:
        table = fused.get(ledger)
        if not isinstance(table, dict):
            continue
        brought_keys = set((brought.get(ledger) or {}) if isinstance(
            brought.get(ledger), dict) else ())
        other_keys = set(other_brought.get(ledger) or {}) if isinstance(
            other_brought.get(ledger), dict) else set()
        own_table = brought.get(ledger) if isinstance(brought.get(ledger), dict) else {}
        open_table = at_open.get(ledger) or {}
        kept = {}
        for key, value in table.items():
            if key in brought_keys:
                kept[key] = _own_or_fused(value,
                                          own_table.get(key, _ABSENT),
                                          open_table.get(key, _ABSENT))
                continue
            if key in other_keys:
                continue                       # the other side brought it
            touches = (_channel_touches(value, rooms, positions) if ledger == "comms"
                       else _touches_rooms(key, value, rooms, positions))
            if touches or (side == home_side and not _touches_rooms(
                    key, value, set(out["rooms"]), positions)):
                kept[key] = value
        out[ledger] = kept

    # Everything the scene carries that is not a table either side partitions
    # -- `location`, `time`, the weather, whatever a later beat adds. The home
    # side keeps the fused value; the away side keeps what it brought.
    for key, value in fused.items():
        if key in out:
            continue
        out[key] = value if side == home_side else brought.get(key, value)
    for key in brought:
        if key not in out:
            out[key] = brought[key]
    return _strip_locales(out)


def close_couple(chat_id, couple_frame_id, *, turn_idx):
    """End a call and partition the couple frame back to its two members.

    Returns a list of deterministic warning strings. One transaction, for
    `perform_split`'s reason inverted: a half-closed couple would leave two
    frames whose bodies are in a third.

    `merged_turn_idx` is set on the COUPLE's own row and on neither member's.
    """
    warnings = []
    themap = couple_map(chat_id, couple_frame_id)
    members = themap.get("members") or []
    if len(members) != 2:
        return warnings
    a_id, b_id = members

    with transaction():
        fused = wget_for_frame(chat_id, "scene", couple_frame_id, {}) or {}
        for side, member in (("a", a_id), ("b", b_id)):
            scene = _partition_side(fused, themap, side)
            normalize_scene_comms(scene)
            wset_for_frame(chat_id, "scene", scene, member)

        known = wget_for_frame(chat_id, "known", couple_frame_id, {}) or {}
        recorded = themap.get("known") or {}
        home_side = "a"
        for side, member in (("a", a_id), ("b", b_id)):
            brought = set(recorded.get(side) or [])
            other = set(recorded.get("b" if side == "a" else "a") or [])
            out = {}
            for who, learned in known.items():
                if str(who) in brought:
                    out[who] = learned
                elif str(who) in other:
                    continue
                else:
                    owner = (themap.get("bodies") or {}).get(str(who)) or home_side
                    if owner == side:
                        out[who] = learned
            if out or ((recorded.get("had") or {}).get(side)):
                wset_for_frame(chat_id, "known", out, member)

        for key in sorted(FRAME_SCOPED_WORLD_KEYS):
            if key in ("scene", "known") or key in ERA_WORLD_KEYS:
                continue
            _copy_key(chat_id, key, couple_frame_id, a_id)
        for side, member in (("a", a_id), ("b", b_id)):
            for char_id in (themap.get("cast") or {}).get(side, []):
                _copy_key(chat_id, f"relationships:{char_id}", couple_frame_id, member)

        # THE AWAY SIDE LIVED THROUGH THE CALL TOO. The home frame's clock is
        # the one a coupled beat advances, so handing the away frame back its
        # frozen copy would make every call a silent gap in its own history --
        # and the next reunion would report the skew the couple invented.
        opened = themap.get("clocks") or {}
        home_open = float((opened.get("a") or {}).get("elapsed_seconds") or 0.0)
        away_open = float((opened.get("b") or {}).get("elapsed_seconds") or 0.0)
        couple_clock = wget_for_frame(chat_id, "simulation_clock",
                                      couple_frame_id, {}) or {}
        elapsed = float(couple_clock.get("elapsed_seconds") or 0.0) - home_open
        if elapsed:
            away_clock = dict(couple_clock)
            away_clock["elapsed_seconds"] = away_open + elapsed
            wset_for_frame(chat_id, "simulation_clock", away_clock, b_id)

        for persona_id, station in (themap.get("personas") or {}).items():
            qi("UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND persona_id=?",
               (station, chat_id, int(persona_id)))

        # The couple frame must hold nothing: a live scene left behind is a
        # third world that `detect_split`/`detect_merge` would iterate and a
        # later checkpoint would snapshot.
        qi("DELETE FROM world WHERE chat_id=? AND key LIKE ?",
           (chat_id, f"%{_FRAME_KEY_SEP}{couple_frame_id}"))
        qi("DELETE FROM chat_char_frames WHERE chat_id=? AND frame_id=?",
           (chat_id, couple_frame_id))
        qi("DELETE FROM world WHERE chat_id=? AND key=?",
           (chat_id, couple_map_key(couple_frame_id)))
        qi("UPDATE frames SET merged_turn_idx=? WHERE id=?",
           (turn_idx, couple_frame_id))

        notice = {"turn": turn_idx, "kind": "couple_close", "frames": [a_id, b_id]}
        log = wget_for_frame(chat_id, "offscreen_log", a_id, []) or []
        log.append(notice)
        wset_for_frame(chat_id, "offscreen_log", log, a_id)

    return warnings


def detect_and_reconcile(ctx, nonce):
    """The commit-time entry point, mirroring paradox.check_and_apply_paradox's
    shape: call once per turn, after scene/entities/cast have committed
    this turn's state_diff, so detection runs against what actually just
    got committed.

    FIVE STRUCTURAL CHANGES, AT MOST ONE PER COMMIT, in the order a beat can
    produce them. Each returns immediately, matching `detect_split`'s
    one-split-per-commit shape: a second one is next beat's question, asked
    against a world that has settled.

      * A COUPLE FRAME asks only whether its call is still up. Nothing else
        may happen inside one -- an ordinary split or merge in a fused view
        would partition a world that is about to be partitioned by a map, and
        the two answers would disagree.
      * A PARTY MERGE and a PARTY SPLIT, unchanged: two humans reunited, two
        humans separated.
      * A COUPLE OPENS when a live channel joins a split to the frame it
        split from, whether the away party is a player's or a bubble's. The
        voice needs somewhere both parties exist to be spoken in.
      * A BUBBLE OPENS for cast who walked into a zone with no human in it
        and no voice reaching them. Last, because every cheaper answer above
        is a reason it should not: a channel that still carries makes the
        bubble's sixth refusal fire, and that refusal lifting by itself on a
        later beat is the whole of the uncouple driver.
    """
    chat_id = ctx.chat.id
    frame_id = ctx.turn.frame_id
    turn_idx = ctx.turn.idx

    frame = get_frame(frame_id)
    if frame and frame.get("kind") == "couple" and frame.get("merged_turn_idx") is None:
        if detect_couple(chat_id, frame_id):
            return {"coupled": True, "couple_frame_id": frame_id}
        themap = couple_map(chat_id, frame_id)
        warnings = close_couple(chat_id, frame_id, turn_idx=turn_idx)
        for w in warnings:
            ctx.add_warning(w)
        members = themap.get("members") or [None, None]
        ctx.add_warning("The channel has closed; the two parties are apart again.")
        return {"uncoupled": True, "couple_frame_id": frame_id,
                "parent_frame_id": members[0], "child_frame_id": members[1],
                "warnings": warnings}

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

    pair = detect_couple(chat_id, frame_id)
    if pair:
        parent_id, child_id = pair
        couple_id = open_couple(chat_id, parent_id, child_id, turn_idx=turn_idx)
        return {"coupled": True, "couple_frame_id": couple_id,
                "parent_frame_id": parent_id, "child_frame_id": child_id}

    from world import spatial_bubbles
    bubble = spatial_bubbles.detect_bubble(chat_id, frame_id, turn_idx)
    if bubble:
        # HOW MANY THREADS THIS STORY IS PAYING FOR (`dialogue_config
        # ["max_bubbles"]`, the owner's dial of 2026-09-20). A live bubble costs
        # a character call and a Director resolve every committed beat, forever,
        # so the one honest place to say "no more" is BEFORE a seventh thread
        # starts -- not by standing an open one still, which is the cap the
        # owner struck down on 2026-09-17 ("a character should never freeze
        # unless they've been made dormant"). Every bubble that exists runs
        # every beat; a character refused one is where every absent character
        # was before bubbles existed, and Charter still moves them.
        #
        # SAID OUT LOUD, because a silent refusal is how a feature comes to
        # look broken: the next beat asks again, so the refusal lifts by itself
        # the moment a bubble merges.
        from agents.offscreen_beat import live_bubbles
        from story.scene import dialogue_config
        _cap = int((dialogue_config(chat_id) or {}).get("max_bubbles", 3))
        _open = len(live_bubbles(chat_id, frame_id))
        if _open >= _cap:
            ctx.add_warning(
                "%s walked out of reach and no bubble opened: this story "
                "carries %d of %d at once. They are off screen as anyone was "
                "before bubbles, and the next beat asks again."
                % (", ".join(bubble["characters"]) or "somebody", _open, _cap))
            return {"active": False, "bubble_refused": "max_bubbles",
                    "open_bubbles": _open, "max_bubbles": _cap}
        new_frame_id = perform_split(
            chat_id, frame_id, turn_idx, bubble=True,
            away_names=bubble["characters"], away_rooms=bubble["rooms"])
        return {"bubble": True, "parent_frame_id": frame_id,
                "child_frame_id": new_frame_id,
                "characters": bubble["characters"], "rooms": bubble["rooms"]}

    return {"active": False}
