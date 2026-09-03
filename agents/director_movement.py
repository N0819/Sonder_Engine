"""Spatial backstops the Director runs on the merged diff.

Heading-aware exits, near-group cohesion, actor-owned following,
passability floors, multi-beat travel continuation, and the
approach-is-not-arrival guard. These judge the MERGED diff and stay
deterministic; the spatial specialist proposes relocations and never has
the last word on them.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

import re

from story.character_schema import character_name_from_text
from world.spatial import (
    egocentric_frame,
    merge_scene_with_diff,
    normalize_bearing,
    normalize_edge_distance,
    passable_route_exists,
    passable_route_next_step,
    room_of,
)

from .director_lingua import _ling

def _egocentric_exits(sc, observer):
    """Which exits lie AHEAD of this mover, and which are the way they came.

    director_interpret picks movement.to_room from the scene's room graph,
    but the graph is undirected: standing in a corridor, "keep walking
    forward" and "turn back" name the same two doorways. Without the
    observer's heading the choice is a coin flip, and live (Elevator
    Adventure branch 41) it came up tails for twenty consecutive turns --
    the player walked forward every beat and was shuffled between four
    rooms, at one point sent four rooms BACKWARD on "You keep inching
    forwards with her". The engine already derives this frame for
    perception (spatial.egocentric_frame); the Director was simply never
    shown it. Empty buckets are omitted so an unoriented mover (scene
    open, fresh teleport) asserts no direction at all.
    """
    try:
        frame = egocentric_frame(sc, observer) or {}
    except Exception:
        return None
    summary = {}
    bearings = {}
    for bucket in ("ahead", "behind", "left", "right", "aside",
                   "above", "below", "unclassified"):
        rooms = []
        for edge in (frame.get(bucket) or []):
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            rid = str(edge["to"])
            rooms.append(rid)
            # The COMPASS direction, kept rather than discarded. The buckets
            # are egocentric and say nothing about north; a Director with
            # only "ahead: [r0401]" has to invent a direction word for the
            # prose, and inventing it is guessing. Measured in maze arm A11:
            # "Vesk moves north into Chamber 0401" for a move that was west,
            # roughly one movement event in seven. The character then reads
            # that back as his own experience and navigates by it.
            bearing = normalize_bearing(edge.get("dir"))
            if bearing:
                bearings[rid] = bearing
        if rooms:
            summary[bucket] = rooms
    if bearings:
        summary["bearings"] = bearings
    came_from = ((sc.get("orientation") or {}).get(observer) or {}).get(
        "came_from")
    if came_from:
        summary["came_from"] = came_from
    return summary or None


def _sightlines_view(sc, ctx, p_name):
    """The Director's deterministic sight digest: who can see whom, who is
    within reach of whom, and what cover stands between named parties
    (`world.spatial_fov.sight_digest`).

    Objective, un-arguable, and the Director's to READ rather than write:
    it declares through the channels it already owns -- a station `at` or
    `near` an anchor, a station's `cover`, a pose, a facing -- and this is
    what those declarations come to. A pair the layer has no evidence about
    reads as open, never as hidden, so nothing here can talk the Director
    out of a body it can plainly place.
    """
    try:
        from story.character_schema import character_name_from_text
        from world.spatial import sight_digest
        names = [p_name] + [character_name_from_text(c["sheet"])
                            for c in (ctx.cast or [])]
        return sight_digest(sc, [n for n in names if n])
    except Exception:
        return None


def _planned_rooms_view(sc, ctx, focus_room, *extra):
    """The plan's seed for every stub this beat stands in or looks into
    (`world.structure.planned_room_brief` over `rooms_to_develop`), or
    None when none is in reach -- so the payload shape of a story with no
    plan is unchanged.

    The trigger is deterministic and reads no prose: the focus room, the
    declared movement target, and every non-wall neighbour of the focus
    room. Author knowledge, for the Director and its spatial hand only.
    """
    try:
        from world.structure import planned_room_brief, rooms_to_develop
        brief = planned_room_brief(
            ctx.chat["id"], sc, rooms_to_develop(sc, focus_room, extra))
        return brief or None
    except Exception:
        return None


def movement_for_resolve(ctx, interp):
    """The beat's declared movement with its destination spelled as the
    world spells it. The compiler (`agents/mapping.classify_movement`)
    resolved the Director's spelling against the plan and put the plan's id
    on its step; every resolve-side reader of the destination -- the
    planned-room brief, the residue, the figures in view, the hands'
    payloads -- takes it from here, so a planned room is furnished under
    its own id rather than minted again beside itself. Unchanged when the
    compiler classified nothing or agreed with the spelling."""
    mv = interp.get("movement") if isinstance(interp, dict) else None
    if not isinstance(mv, dict) or not mv.get("to_room"):
        return mv
    try:
        compiled = (ctx.world_context() or {}).get("movement")
    except Exception:
        compiled = None
    if not isinstance(compiled, dict) or compiled.get("status") != "planned":
        return mv
    canonical = str(compiled.get("to_room") or "")
    if not canonical or canonical == str(mv.get("to_room")):
        return mv
    out = dict(mv)
    out["declared_as"] = str(mv["to_room"])
    out["to_room"] = canonical
    return out


def _ci_mapping_key(mapping, name):
    """Return the existing key in ``mapping`` that names ``name``.

    Positions are canonicalized before this seam, while stations are still
    model-authored and occasionally differ only in case/whitespace.  The
    reconciliation below must update the key every spatial reader already
    uses rather than minting a second position for the same body.
    """
    if not isinstance(mapping, dict) or not name:
        return None
    if name in mapping:
        return name
    folded = str(name).strip().casefold()
    for key in mapping:
        if str(key).strip().casefold() == folded:
            return key
    return None


def _reconcile_near_group_positions(ctx, scene, state_diff, player_name):
    """Make one fresh, explicit within-room group physically possible.

    ``stations.near`` means two bodies are in the same room, and ``at`` names
    an anchor in that room.  Until now station hygiene silently discarded
    those facts when the resolve model also wrote contradictory room
    positions.  Hearing then trusted the surviving positions and treated a
    shoulder-to-shoulder travelling party as separated.

    This is deliberately not a general companion-carry heuristic.  The
    strongest case remains an unambiguous fresh anchor.  There is one bounded
    fallback for the live travelling-group failure where both station records
    said the pair remained near but neither named a path anchor: an ordinary
    player-led move may carry a mutually-near group to the player's resolved
    room when every member began co-located.

    A group is moved only when THIS beat supplies all of the following
    structured proof:

    * at least two positioned bodies joined by a fresh ``near`` link;
    * either exactly one room owns the group's fresh ``at`` anchor(s), OR the
      unanchored group is mutually near, began co-located, and the player made
      an ordinary (non-running) move to a resolved room;
    * every already-positioned member had a passable route to that room.

    An explicit follow stop always wins.  No near link, ambiguous/conflicting
    anchors, prior separation, rapid movement, or an impassable route means no
    unanchored relocation.  That keeps bystanders, pursuit, teleport
    operators, deliberate departures, and real acoustic barriers outside this
    repair while preventing room granularity from silencing a group that the
    same resolution says is still together.
    """
    positions = state_diff.get("positions") or {}
    stations = state_diff.get("stations") or {}
    if not isinstance(positions, dict) or not isinstance(stations, dict):
        return False

    # Resolve station labels onto the canonical position keys already in use.
    # A body absent from the diff can still be part of the fresh near group, so
    # include its committed position key as well.
    all_positions = dict(scene.get("positions") or {})
    all_positions.update(positions)
    graph = {}
    declared_near = {}
    station_by_body = {}
    for raw_name, station in stations.items():
        if not isinstance(station, dict):
            continue
        body = _ci_mapping_key(all_positions, raw_name)
        if body is None:
            continue
        station_by_body[body] = station
        for raw_other in station.get("near") or []:
            other = _ci_mapping_key(all_positions, raw_other)
            if other is None or other == body:
                continue
            declared_near.setdefault(body, set()).add(other)
            graph.setdefault(body, set()).add(other)
            graph.setdefault(other, set()).add(body)

    if not graph:
        return False

    route_scene = merge_scene_with_diff(scene, state_diff)
    rooms = route_scene.get("rooms") or {}
    # Is the player going anywhere this beat -- by their own declaration, or
    # by a walk already under way that nothing has interrupted? Read once.
    _interp = ctx.get("director_interpret") or {}
    _mv = _interp.get("movement") if isinstance(_interp, dict) else None
    _approach = scene.get("approach") or {}
    if "who" in _approach:
        _approach = {_approach.get("who"): _approach} if _approach.get("who") \
            else {}
    _player_key = _ci_mapping_key(all_positions, player_name)
    _player_room = all_positions.get(_player_key or "")
    _player_is_travelling = bool(
        (isinstance(_mv, dict) and _mv.get("to_room"))
        or (_player_key and isinstance(_approach, dict)
            and _approach.get(_player_key)))
    changed = False
    seen = set()
    for start in list(graph):
        if start in seen:
            continue
        component = set()
        frontier = [start]
        while frontier:
            body = frontier.pop()
            if body in component:
                continue
            component.add(body)
            frontier.extend(graph.get(body) or ())
        seen.update(component)
        if len(component) < 2:
            continue

        anchor_rooms = set()
        ambiguous_anchor = False
        for body in component:
            anchor = (station_by_body.get(body) or {}).get("at")
            if not anchor:
                continue
            owners = {
                room_id for room_id, room in rooms.items()
                if isinstance(room, dict)
                and anchor in (room.get("anchors") or {})
            }
            if len(owners) != 1:
                ambiguous_anchor = True
                break
            anchor_rooms.update(owners)

        names = ", ".join(sorted(str(n) for n in component))
        if ambiguous_anchor or len(anchor_rooms) > 1:
            if anchor_rooms or ambiguous_anchor:
                ctx.warnings.append(
                    f"Near-group position conflict for {names}: fresh station "
                    "anchors do not identify one unambiguous room; positions "
                    "left unchanged."
                )
            continue

        # A STATION SAYS WHERE YOU STAND, NOT WHICH ROOM YOU ARE IN.
        #
        # Live, chat 72 turn 47. The spatial specialist wrote one station --
        # the night clerk `at: "lobby_doorway"`, `near: [Hinami, The
        # Doctor]` -- a correct description of a man in the threshold.
        # `lobby_doorway` is an anchor owned by the BACK OFFICE (its name for
        # the door through to the lobby), so this resolved him into the back
        # office and then used `near` to drag both guests in after him. Its
        # own warning read "contradictory positions were {all three: lobby}":
        # every body was in the lobby and it relocated them anyway.
        #
        # Two rules, both subtractive:
        #
        # AGREEMENT IS NOT CONTRADICTION. This repair exists to settle a
        # disagreement between `positions` and `stations`. Where the bodies
        # already agree there is nothing to settle, and an anchor claim must
        # never outrank the ledger it decorates.
        #
        # AN ANCHOR MAY POSITION, NEVER RELOCATE. A threshold anchor names
        # the room it leads TO, so anchor ownership is not evidence of which
        # side of a door a body stands on -- and moving a body across rooms
        # is movement, which has to survive the movement guards (or the
        # travel continuation) rather than arriving through a decoration.
        # The anchor still settles WHICH of the group's already-occupied
        # rooms wins, which is the disagreement it was built for.
        occupied = {all_positions.get(body) for body in component}
        occupied.discard(None)
        if len(occupied) < 2:
            continue
        # AND THE PLAYER IS NEVER MOVED BY SOMEBODY ELSE'S ANCHOR. Where
        # the group disagrees and nobody is going anywhere, the group
        # resolves to the PLAYER's room: their position is the most
        # authoritative thing in the scene, it is where the story is told
        # from, and a station decoration does not outrank it. Turn 47 is the
        # case exactly -- the pair were in the lobby and a newcomer's doorway
        # anchor took them out of it. Honouring the near-claim by pulling the
        # OTHERS to the player keeps the feature this repair exists for and
        # drops the half that moved the protagonist without anyone saying so.
        target_reason = "fresh anchor"
        if anchor_rooms:
            target_room = next(iter(anchor_rooms))
            # NOBODY GOING ANYWHERE IS NOT A JOURNEY. Both guards apply only
            # when the player has declared no movement and no walk is under
            # way. When they ARE travelling the anchor is the party's
            # destination, and naming a room nobody stands in yet is exactly
            # what this repair was built for (chat 38 t136: two walkers
            # explicitly near at the torii beam, committed into separate
            # rooms, and hearing dropped three lines of four).
            if not _player_is_travelling:
                if _player_room and _player_room in occupied:
                    target_room = _player_room
                    target_reason = (
                        "the player's own room, nobody being under way")
                elif target_room not in occupied:
                    ctx.warnings.append(
                        f"Near-group position conflict for {names}: the "
                        f"fresh station anchor names room '{target_room}', "
                        "which nobody in the group stands in and nobody is "
                        "travelling to -- a station says where a body "
                        "stands, not which room it is in, and a threshold "
                        "anchor names the room it leads to. Positions left "
                        "unchanged."
                    )
                    continue
        else:
            # No anchor: only repair the narrow ordinary-travel shape.  A
            # one-sided model-authored near claim is not enough; both bodies
            # must say they remained together.  Most importantly, they must
            # have begun together -- following state deliberately does not
            # teleport an already-separated follower, and neither may this
            # consistency repair.
            mutual = all(
                other in (declared_near.get(body) or set())
                for body in component
                for other in (graph.get(body) or set())
            )
            start_rooms = {room_of(scene, body) for body in component}
            player_key = _ci_mapping_key(all_positions, player_name)
            player_diff_key = _ci_mapping_key(positions, player_key)
            target_room = positions.get(player_diff_key) if player_diff_key else None
            player_started = room_of(scene, player_key) if player_key else None

            stopped = {
                str(op.get("follower") or "").strip().casefold()
                for op in (state_diff.get("following_ops") or [])
                if isinstance(op, dict) and op.get("op") == "stop"
            }
            component_stopped = any(
                str(body).strip().casefold() in stopped for body in component)

            # A run/flee may leave a willing follower behind.  Check every
            # participant's own declaration, not only the player's, so this
            # fallback cannot become free pursuit in either direction.
            declarations = []
            if player_key in component:
                declarations.append(ctx.get("director_interpret") or {})
            actor_results = {}
            actor_results.update(ctx.reaction_results or {})
            actor_results.update(ctx.character_results or {})
            for row in ctx.cast:
                try:
                    cname = character_name_from_text(row["sheet"])
                except Exception:
                    continue
                body = _ci_mapping_key(all_positions, cname)
                if body not in component:
                    continue
                result = actor_results.get(row["id"]) \
                    or actor_results.get(str(row["id"]))
                if isinstance(result, dict):
                    declarations.append(result)
            rapid = any(_declares_rapid_movement(d) for d in declarations)

            if not (
                mutual
                and player_key in component
                and len(start_rooms) == 1
                and None not in start_rooms
                and target_room
                and target_room != player_started
                and not component_stopped
                and not rapid
            ):
                continue
            target_reason = "ordinary player-led travel"

        blocked = []
        for body in component:
            origin = room_of(scene, body)
            if origin and origin != target_room and not passable_route_exists(
                    route_scene, origin, target_room):
                blocked.append(f"{body} from {origin}")
        if blocked:
            ctx.warnings.append(
                f"Near-group position conflict for {names}: anchor room "
                f"'{target_room}' is not passably reachable by "
                f"{', '.join(blocked)}; positions left unchanged."
            )
            continue

        before = {body: all_positions.get(body) for body in component}
        if all(room == target_room for room in before.values()):
            continue
        for body in component:
            positions[body] = target_room
            all_positions[body] = target_room
        changed = True
        ctx.warnings.append(
            f"Reconciled near group ({names}) to room '{target_room}' by "
            f"{target_reason}; contradictory positions "
            f"were {before}."
        )

    return changed




def _declares_rapid_movement(result):
    """Whether an actor declared pace an ordinary follower cannot inherit."""
    if not isinstance(result, dict):
        return False
    for event in result.get("sequence") or []:
        if not isinstance(event, dict) or event.get("type") != "action":
            continue
        verb = str(event.get("verb") or "").strip().casefold()
        if verb in _ling("_RAPID_FOLLOW_VERBS"):
            return True
        attempt = str(event.get("attempt") or "").strip().casefold()
        # Start-boundary matching avoids treating "runs a hand through hair"
        # as escape pace while still accepting weaker-model empty verb fields.
        if re.match(r"^(?:tries to |attempts to )?(?:run|sprint|flee|dash|bolt|race)\b",
                    attempt):
            return True
    return False


def _follow_op_for_actor(ctx, scene, follower, raw):
    """Validate one actor-owned following decision against positioned actors."""
    if not isinstance(raw, dict):
        return None
    op = str(raw.get("op") or "").strip().casefold()
    follower_key = _ci_mapping_key(scene.get("positions") or {}, follower)
    if op not in ("start", "stop") or follower_key is None:
        return None
    reason = str(raw.get("reason") or "").strip()
    if op == "stop":
        return {"op": "stop", "follower": follower_key,
                "reason": reason, "turn": ctx.turn.idx}
    target = _ci_mapping_key(scene.get("positions") or {}, raw.get("target"))
    if target is None or target.casefold() == follower_key.casefold():
        ctx.warnings.append(
            f"Ignored invalid follow start by {follower_key!r}: target "
            f"{raw.get('target')!r} is not another positioned actor."
        )
        return None
    return {"op": "start", "follower": follower_key, "target": target,
            "reason": reason, "turn": ctx.turn.idx}


def _collect_following_ops(ctx, scene, interp, player_name):
    """Project player interpretation and NPC decisions into one actor-owned ledger."""
    ops = []
    player_op = _follow_op_for_actor(
        ctx, scene, player_name, interp.get("follow_op"))
    if player_op:
        ops.append(player_op)

    for extra in ctx.extra_players:
        raw = (interp.get("other_players") or {}).get(
            str(extra["persona_id"]), {}).get("follow_op")
        op = _follow_op_for_actor(ctx, scene, extra["name"], raw)
        if op:
            ops.append(op)

    actor_results = {}
    actor_results.update(ctx.reaction_results or {})
    actor_results.update(ctx.character_results or {})
    for cast_row in ctx.cast:
        cid = cast_row["id"]
        result = actor_results.get(cid) or actor_results.get(str(cid))
        if not isinstance(result, dict):
            continue
        name = character_name_from_text(cast_row["sheet"])
        op = _follow_op_for_actor(ctx, scene, name, result.get("follow_op"))
        if op:
            ops.append(op)

    # Last declaration by one actor wins inside this beat. This is mainly for
    # a reaction followed by an interaction call, both valid decisions by the
    # same mind at different micro-rounds.
    by_follower = {}
    for op in ops:
        by_follower[op["follower"].casefold()] = op
    return list(by_follower.values())


def _following_record(following, name):
    folded = str(name or "").strip().casefold()
    for follower, record in (following or {}).items():
        if str(follower).strip().casefold() == folded and isinstance(record, dict):
            return follower, record
    return None, None


def _apply_following_movement(ctx, scene, state_diff, interp, player_name):
    """Carry willing followers through ordinary travel, never pursuit.

    The relation is durable intent, not a tether. A follower is moved only
    when they and the target began co-located, the target changed rooms at an
    ordinary pace, and a passable route reaches the destination. Running or
    fleeing leaves the follower behind with the relation still active, so they
    may choose to chase or stop on their next decision. Actor-owned stop ops
    take effect before any carry.
    """
    from world.spatial import apply_following_ops

    ops = list(state_diff.get("following_ops") or [])
    relation_scene = merge_scene_with_diff(scene, {"following_ops": ops})
    following = relation_scene.get("following") or {}
    if not following:
        return False

    rapid = set()
    if _declares_rapid_movement(interp):
        rapid.add(player_name.casefold())
    for extra in ctx.extra_players:
        raw = (interp.get("other_players") or {}).get(str(extra["persona_id"])) or {}
        if _declares_rapid_movement(raw):
            rapid.add(extra["name"].casefold())
    actor_results = {}
    actor_results.update(ctx.reaction_results or {})
    actor_results.update(ctx.character_results or {})
    for row in ctx.cast:
        result = actor_results.get(row["id"]) or actor_results.get(str(row["id"]))
        if _declares_rapid_movement(result):
            rapid.add(character_name_from_text(row["sheet"]).casefold())

    positions = state_diff.get("positions") or {}
    route_scene = merge_scene_with_diff(scene, state_diff)

    # Player agency floor: if the Director omitted follow_op:stop but resolved
    # the player's declared movement somewhere other than the followed target,
    # the physical contradiction itself ends following. NPC autonomy is NOT
    # inferred from resolver positions; NPCs own it through their follow_op.
    p_follow_key, p_follow = _following_record(following, player_name)
    player_move = interp.get("movement")
    if p_follow and isinstance(player_move, dict) \
            and (player_move.get("mover") or "self") == "self":
        target = _ci_mapping_key(
            {**(scene.get("positions") or {}), **positions},
            p_follow.get("target"))
        player_dest = positions.get(player_name)
        target_dest = positions.get(target) if target else None
        if player_dest and target_dest and player_dest != target_dest:
            stop = {"op": "stop", "follower": p_follow_key,
                    "reason": "player declared movement incompatible with following",
                    "turn": ctx.turn.idx}
            ops.append(stop)
            apply_following_ops(relation_scene, [stop])
            following = relation_scene.get("following") or {}
            state_diff["following_ops"] = ops

    changed = False
    # A short fixed-point handles A follows B follows C without making cycles
    # possible (the ledger rejects those at application).
    for _ in range(max(1, len(following))):
        progressed = False
        all_positions = dict(scene.get("positions") or {})
        all_positions.update(positions)
        for raw_follower, record in list(following.items()):
            follower = _ci_mapping_key(all_positions, raw_follower)
            target = _ci_mapping_key(all_positions, record.get("target"))
            if follower is None or target is None:
                continue
            origin = room_of(scene, follower)
            target_origin = room_of(scene, target)
            target_dest = positions.get(target)
            if not origin or origin != target_origin or not target_dest \
                    or target_dest == target_origin:
                continue
            if target.casefold() in rapid:
                continue
            if origin != target_dest and not passable_route_exists(
                    route_scene, origin, target_dest):
                continue
            if positions.get(follower) == target_dest:
                continue
            positions[follower] = target_dest
            progressed = changed = True
        if not progressed:
            break
    return changed

def _unreachable_position_writes(scene, route_scene, positions, bodies,
                                 exempt=()):
    """Position writes with no open route from where the body actually is.

    THE PHYSICAL FLOOR THE DIFF NEVER HAD. `passable_neighbors` is the one
    graph everyone walks -- crowds move on it, couriers move on it, a follower
    is only carried along a route it proves -- and the Director's own
    `state_diff.positions` was never held to it. So a body could be written
    into a room it has no way of reaching, and nothing anywhere objected.

    Live, chat 80 turn 4. The player declared no movement at all
    (`director_interpret.movement` null, its `positions` null) and the spatial
    specialist wrote `{"Hinami": "obs_room"}`. `passable_route_exists` from
    `interview_cell` is False for every room in the scene -- the cell's only
    edges are a `wall` (the two-way mirror) and a `closed_door` -- so she was
    moved through the mirror out of a sealed room, into the room the observers
    were watching her from. The prose author, in the same step, had written her
    correctly as "the young woman in the interview cell" seen "through the
    two-way mirror" with the psychologist's voice arriving "through the PA
    speaker": the diff contradicted the prose beside it.

    Deliberately about REACHABILITY and not about declarations. Being dragged,
    carried, or moved by a lift are all legitimate undeclared moves, and a rule
    keyed on "the player did not say so" would refuse them; what is never
    legitimate, declared or not, is passing through a wall. Portals need no
    exemption either -- `apply_transit_dock_edges` materialises an open
    `state.link` into a real adjacency edge, so the one graph already carries
    them.

    Silent about anything it cannot judge: an unknown origin (a body arriving
    into the scene), an unknown destination (a room this beat is minting), and
    a body that has not moved. Refusing a write this cannot check would be
    inventing a physics from a gap in the map.
    """
    rooms = (route_scene or scene).get("rooms") or {}
    known = {str(b).strip().casefold() for b in (bodies or []) if str(b).strip()}
    spared = {str(b).strip().casefold() for b in (exempt or []) if str(b).strip()}
    refused = []
    for body, dest in list((positions or {}).items()):
        dest = str(dest or "").strip()
        if not dest or dest not in rooms:
            continue
        folded = str(body).strip().casefold()
        # BODIES ONLY. A vehicle is positioned in a room and does not get there
        # by walking: it travels on `state.transit`, and its arrival is what
        # CREATES the dock edge everyone else then uses. Route-checking one
        # strips the very move that opens the door.
        if folded not in known:
            continue
        # A body whose movement somebody DECLARED is the movement backstop's
        # business, and that seam owns the harder question this one must not
        # re-answer: a closed door is CONTESTED, not impossible, and whether it
        # was opened and crossed belongs to the causality owner. This floor is
        # only for a position nobody said anything about.
        if folded in spared:
            continue
        # Origin from the PRE-BEAT scene -- where the body actually was when
        # the beat started -- and the route from the scene as this beat leaves
        # it, so a door the resolve opens is open to the body walking through
        # it. The backstop above splits the two the same way and for the same
        # reason.
        origin = room_of(scene, body)
        if not origin or origin not in rooms or origin == dest:
            continue
        if passable_route_exists(route_scene or scene, origin, dest):
            continue
        refused.append((str(body), origin, dest))
    return refused


def _resolve_movement_mover(sc, sd, mv, p_name):
    """Resolve movement.mover to the position subject the passable-route
    backstop should validate and write.

    Returns (subject_key, subject_room, mover_entity_id):
    - mover 'self'/empty/the player's own name -> (p_name, None, None);
      the caller resolves the player's room as before.
    - an entity id/name/alias found in the scene (or this beat's diff) ->
      (the positions key that entity is actually stored under, its current
      exterior room, its canonical entity id). Driving a vehicle moves the
      ENTITY's position; the player's body stays put.
    - anything unresolvable -> (None, None, None); the caller falls back
      to the player with a warning (the pre-mover behavior, safe default).
    """
    mover = str((mv or {}).get("mover") or "self").strip()
    if not mover or mover.casefold() in ("self", "player") \
            or mover.casefold() == str(p_name or "").casefold():
        return p_name, None, None
    entities = dict(sc.get("entities") or {})
    for eid, ent in (sd.get("entities") or {}).items():
        if isinstance(ent, dict):
            entities[eid] = ent
    positions = sc.get("positions") or {}
    mover_cf = mover.casefold()
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        forms = [str(eid), str(ent.get("name") or "")] + \
            [str(a) for a in (ent.get("aliases") or [])]
        forms = [f for f in forms if f.strip()]
        if mover_cf not in {f.casefold() for f in forms}:
            continue
        # Prefer the key the scene already stores this entity's position
        # under (id, name, or alias); default to the canonical id.
        key = next((f for f in forms if f in positions), str(eid))
        return key, positions.get(key), str(eid)
    return None, None, None



#: Edge distances that take more than one beat to cross. A corridor and a
#: mountain path are both one edge and are nothing alike to walk, and a walk
#: that crosses either in a breath is the reason "realistic" was asked for.
#: Coarse on purpose -- fiction needs the difference between a doorway and a
#: hike, not a stride model.
_LONG_EDGE_DISTANCES = frozenset({"far", "remote"})
_LONG_EDGE_BEATS = 2


# --- one walk, read twice --------------------------------------------------
#
# `_travel_in_flight_view` tells the Director what is already under way;
# `_travel_continues` advances it once the beat is resolved. They are a
# question and its answer about the same standing records, so they have to
# agree about which legs exist, which mover the beat exempted, and how long an
# edge takes -- and they agreed only by both being written out (audit
# DIRECTOR-D10). Read once here, so a change to any of the three is one edit.

def _pending_legs(sc):
    """The standing approach records, keyed by mover.

    The scene-global shape (`{"who": ..., "to_room": ...}`) predates per-mover
    records and is still read, so a save written before that does not lose its
    walker.
    """
    pending = sc.get("approach") or {}
    if "who" in pending:
        pending = ({pending["who"]: {"to_room": pending.get("to_room")}}
                   if pending.get("who") else {})
    return pending if isinstance(pending, dict) else {}


def _declared_movers(interp, p_name):
    """Movers whose own declaration this beat carries.

    Continuation fills a SILENCE and never competes with a live declaration:
    a mover in this set goes through the ordinary movement machinery
    untouched, and is skipped by both the view and the advance.
    """
    mv = interp.get("movement")
    if not isinstance(mv, dict) or not mv.get("to_room"):
        return set()
    who = str(mv.get("mover") or "self")
    return {p_name if who in ("self", "player") else who}


def _edge_to(rooms, here, step):
    """The adjacency record for `here -> step`, or `{}` if the map has none."""
    return next(
        (e for e in ((rooms.get(here) or {}).get("adjacent") or [])
         if isinstance(e, dict) and e.get("to") == step), {})


def _still_crossing(distance, beats_spent):
    """Whether a long edge is mid-crossing after this many beats on it.

    `distance` is already normalized, and `beats_spent` COUNTS THIS BEAT --
    both callers pass `edge_beats + 1`, and passing the stored count instead
    holds every walker one beat too long.
    """
    return (distance in _LONG_EDGE_DISTANCES
            and int(beats_spent) < _LONG_EDGE_BEATS)


def _travel_in_flight_view(sc, interp, p_name):
    """What the Director is told about walks already under way.

    The engine works out the leg BEFORE the prose is written, not after.
    Computing it afterwards would move bodies the resolve had just described
    standing still -- the scenery has to change ON the page, in the same
    breath as everything else the beat does, or the position and the story
    are two accounts of one turn again.

    So this is a fact with an out: here is where they are going, here is the
    room this beat puts them in, narrate it -- unless the beat itself stops
    them, in which case say so in `travel_interrupted` and they stay put.
    """
    pending = _pending_legs(sc)
    if not pending:
        return []
    declared = _declared_movers(interp, p_name)

    rooms = sc.get("rooms") or {}
    view = []
    for subject, leg in sorted(pending.items()):
        if not isinstance(leg, dict) or subject in declared:
            continue
        destination = str(leg.get("to_room") or "").strip()
        here = room_of(sc, subject)
        if not destination or not here or here == destination:
            continue
        step = passable_route_next_step(sc, here, destination)
        if not step:
            continue
        distance = normalize_edge_distance(
            _edge_to(rooms, here, step).get("distance"))
        entry = {
            "subject": subject,
            "destination": destination,
            "destination_name": str(
                (rooms.get(destination) or {}).get("name") or destination),
            "from_room": here,
            "reaches_this_beat": step,
            "reaches_name": str((rooms.get(step) or {}).get("name") or step),
            "distance": distance,
            "final_leg": step == destination,
        }
        if _still_crossing(distance, int(leg.get("edge_beats") or 0) + 1):
            entry["reaches_this_beat"] = None
            entry["reaches_name"] = ""
            entry["still_crossing"] = True
        view.append(entry)
    return view


def _travel_continues(ctx, out, sc, sd, interp, p_name):
    """Advance a declared walk that this beat did not mention.

    THE BURDEN IS INVERTED HERE, deliberately. `commit.py` used to read a
    beat that declared no movement as ABANDONING the walk -- "the walker
    stopped to do something else, and picking the thread back up is a fresh
    declaration". That makes travel survive only by being re-declared every
    beat, which is exactly the sentence nobody wants to keep writing, and it
    is wrong about the commonest thing in fiction: people talk while they
    walk.

    Live, chat 72. The player declared the hotel and was correctly refused
    entry on the beat she was only heading there. Next beat she wrote "You
    grab the doctors shoulders and stare him directly in the eyes" -- no
    movement -- and the engine did two contradictory things at once: it
    recorded that she had abandoned the walk, AND a station anchor moved her
    the exact two rooms the approach guard had just refused, through a
    channel no movement guard inspects. The accident gave the narratively
    right answer; the designed path said she stopped walking while she was
    plainly still walking.

    So silence CONTINUES. Which is also the only reading consistent with
    player authority: the player declared this walk, once, and carrying it
    on executes their declaration -- stopping them without being told is
    what overrides it. An interruption is therefore the thing that has to be
    established, never the default, and it is established two ways:

      * THE DIRECTOR SAYS SO (`travel_interrupted`). "Did what just happened
        stop you walking" is objective causality, it is nuanced beyond
        anything worth enumerating here, and the resolve is the one stage
        that reads the whole beat -- the declaration, every character's act,
        the dice and the room. It is a structured field rather than a prose
        inference for the usual reason: prose matching is the boundary this
        engine exists to stay on the right side of.
      * A DETERMINISTIC FLOOR the Director cannot argue with: no passable
        route left, being carried, or already there. Restraint needs nothing
        here -- writing into `state_diff.positions` puts this through the
        same immobilisation block a declared move goes through, which is the
        point of advancing the walk HERE, before every movement backstop,
        rather than teleporting after them.

    Records what it did on `out['travel']`; `commit.py` reads that to retire
    or keep each standing record, so the ledger and the position can never
    disagree about whether somebody is still under way.
    """
    pending = _pending_legs(sc)
    if not pending:
        return
    declared = _declared_movers(interp, p_name)

    stopped = {
        str(entry.get("subject") or "").strip().casefold(): str(
            entry.get("reason") or "")
        for entry in (out.get("travel_interrupted") or [])
        if isinstance(entry, dict) and str(entry.get("subject") or "").strip()
    }

    route_scene = merge_scene_with_diff(sc, sd)
    rooms = route_scene.get("rooms") or {}
    record = {"advanced": [], "arrived": [], "interrupted": [], "held": []}

    for subject, leg in sorted(pending.items()):
        if not isinstance(leg, dict) or subject in declared:
            continue
        destination = str(leg.get("to_room") or "").strip()
        if not destination:
            continue
        here = room_of(route_scene, subject)
        if here and here == destination:
            record["arrived"].append(subject)
            continue
        reason = stopped.get(str(subject).casefold())
        if reason is not None:
            record["interrupted"].append(
                {"subject": subject, "reason": reason, "source": "director"})
            continue
        # Being carried is somebody else's doing; their walk resumes when
        # they are put down, and until then their position is not theirs.
        if (route_scene.get("contained") or {}).get(subject):
            record["held"].append({"subject": subject, "reason": "carried"})
            continue
        step = passable_route_next_step(route_scene, here, destination)
        if not step:
            record["held"].append(
                {"subject": subject, "reason": "no passable route"})
            continue
        # A long edge is not crossed in a breath. Counted on the standing
        # record so the beats already spent on this leg survive a reroll.
        distance = normalize_edge_distance(
            _edge_to(rooms, here, step).get("distance"))
        spent = int(leg.get("edge_beats") or 0) + 1
        if _still_crossing(distance, spent):
            record["held"].append(
                {"subject": subject, "reason": "still crossing",
                 "edge_beats": spent})
            continue
        sd.setdefault("positions", {})[subject] = step
        record["advanced"].append({"subject": subject, "from": here,
                                   "to": step, "destination": destination})
        if step == destination:
            record["arrived"].append(subject)
        ctx.add_warning(
            f"Travel continues: {subject} declared a walk to "
            f"{destination!r} and this beat did not stop it, so they move "
            f"{here!r} -> {step!r}. Silence continues a declared walk; an "
            "interruption is the Director's to assert.")

    if any(record.values()):
        out["travel"] = record


def _guard_approach_is_not_arrival(ctx, interp, sd, sc, p_name):
    """A declaration that only reaches TOWARD somewhere does not end inside it.

    Observed live, story "The Blizzard", turn 2. The player wrote "You wander
    towards it" of a lit building seen through the snow the beat before.
    `director_interpret` produced `stage: "approach"` and
    `asserted_effects: "progresses across the snowy clearing toward the
    building"` -- and also `movement: {to_room: "distant_mountain_building",
    why: "heading towards the flickering light"}`. The passable-route backstop
    passed it, correctly: the rooms were adjacent and the edge was open.
    `director_resolve` then wrote "she reaches the building, opens the door,
    and steps into its lantern-lit interior" and committed her position inside,
    taking her from `exposure: open` to `exposure: sheltered` -- out of a
    blizzard -- with nobody having said she was going in.

    The fix is `MovementDecl.arrives`, set by the stage that actually read the
    player's sentence. This is the deterministic half: a movement whose own
    declaration says it does not arrive may not commit a position.

    It is a FIELD because the distinction cannot be recovered downstream.
    Measured across the whole live corpus (1249 turns): no test on the
    declaration's text separates "I cross the command deck and head down the
    central corridor TOWARD the med bay" -- an asserted crossing -- from
    "PROGRESSES across the snowy clearing TOWARD the building". Both say
    "toward"; both are staged `approach`; both are `commitment: asserted`. Four
    successive heuristics were tried against the corpus and each one blocked
    legitimate arrivals: last-element stage (3 false positives), presence
    versus progress markers (still 8), single-element beats (still 4). The
    information simply is not in the diff -- only in the sentence, which only
    the interpret sees.

    `stage` is the cautionary tale one field over: an `ActionStage` enum in the
    schema since the beginning, read by NOTHING on the resolve path, so the
    interpret has been classifying these correctly all along to no effect.
    """
    mv = interp.get("movement")
    if not isinstance(mv, dict) or mv.get("arrives", True):
        return
    # A SECOND declaration toward the same place arrives. Without this the
    # feature strands anyone who keeps writing approach-flavoured text: the
    # engine would answer "you get closer" forever, and time spent approaching
    # is time spent standing still -- measured, six hours of "trudging towards
    # the mountain" left the walker in the clearing she started in, under
    # level-12 snowdrifts the weather had piled on a body that never moved.
    # One beat closes the distance, the next one gets there.
    pending = sc.get("approach") or {}
    subject_key = p_name if str(mv.get("mover") or "self") == "self" else str(mv["mover"])
    # Per mover. The scene-global shape ({"who": ...}) is still read so a save
    # written before this does not lose a walker mid-stride.
    if "who" in pending:
        pending = ({pending["who"]: {"to_room": pending.get("to_room")}}
                   if pending.get("who") else {})
    if (pending.get(subject_key) or {}).get("to_room") == mv.get("to_room"):
        ctx.warnings.append(
            f"Approach completed: {subject_key} was already closing on "
            f"'{mv.get('to_room')}' and arrives this beat."
        )
        return
    # Whose move was it. "self" is the player's own body; anything else is the
    # vehicle or mount they declared, and a skiff told to head for the light is
    # as much not-there-yet as the hand on its tiller. Guarding only the player
    # left "I steer us towards the lighthouse" putting the boat on the rock.
    subject = p_name if str(mv.get("mover") or "self") == "self" else str(mv["mover"])
    was = room_of(sc, subject)
    now = (sd.get("positions") or {}).get(subject)
    if not now or now == was:
        return
    # Being moved WITHOUT walking is somebody else's doing -- carried, dragged,
    # shut in a crate -- and that is the resolve's to assert, not this guard's
    # to refuse.
    if (sc.get("contained") or {}).get(subject):
        return
    sd["positions"].pop(subject, None)
    ctx.warnings.append(
        f"Approach is not arrival: {subject}'s declared movement to "
        f"'{mv.get('to_room')}' is marked arrives=false, but the beat placed "
        f"them in '{now}'{f' (from {was!r})' if was else ''}. Position "
        "unchanged -- moving closer to somewhere is not being there, and "
        "reaching a building is not entering it."
    )
