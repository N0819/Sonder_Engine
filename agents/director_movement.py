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

import copy
import hashlib
import json
import re

from story.character_schema import character_name_from_text
from world.mechanics import UNCLAIMED_BEAT_SECONDS, read_time_diff, time_diff_claims
from world.spatial import (
    anchor_stand_cell, beside_named, body_cell, free_cell_near, room_grid,
    _ROUTE_MEMORY_BARRIERS,
    door_cell,
    egocentric_frame,
    merge_scene_with_diff,
    neighbor_map,
    normalize_bearing,
    normalize_edge_distance,
    passable_neighbors,
    passable_route_exists,
    paces_for,
    passable_route_next_step,
    room_of,
    spatial_rel,
    walk,
)

from .director_lingua import _ling

#: The ctx side channel the turn's merged route scenes live in.
#:
#: One entry per SCENE OBJECT, holding that scene's latest merge. Not a cap:
#: a resolve asks its route questions of at most two scenes -- the beat's own
#: and the charter view (`common.charter_view_for_rooms`), which stands the
#: town's unpromoted bodies at their cells -- so the table is as large as the
#: number of distinct scenes asked about and the turn's `ctx` takes it away
#: with it. One entry PER SCENE rather than one entry overall is what lets
#: the charter check and the beat's own checks coexist instead of evicting
#: each other every beat (review 2026-09-07 C6).
_ROUTE_MEMO = "_route_scene_memo"


def _route_positions_stamp(scene):
    """`carriers._positions_stamp`'s twin, and for its reason.

    Identity is conservative for a NEW dict and OPTIMISTIC for one mutated
    IN PLACE, which keeps the same `id()`. Positions are the one part of a
    scene this engine has actually been measured moving in place between two
    reads (review 2026-09-07 C9, bench chat 114: `positions["Mora"]` "square"
    -> "road" inside one ctx), and they are what every route answer turns
    on. The stamp costs 0.0085 ms against the 11.1 ms merge it guards, so
    the assumption is bought out rather than argued for.

    A `positions` this cannot order -- a non-string key, which JSON storage
    does not produce -- yields a fresh object equal to nothing, so the memo
    rebuilds. That is the safe direction.
    """
    try:
        return tuple(sorted(((scene or {}).get("positions") or {}).items()))
    except (AttributeError, TypeError):
        return object()


def route_scene_for(ctx, scene, state_diff):
    """The scene as this beat's diff leaves it, for a ROUTE or PLACEMENT
    question -- merged once per turn, per scene, per diff content.

    Eight checks inside one resolve each deep-copied the whole scene and
    re-ran every derivation pass (`merge_scene_with_diff`) to ask the same
    question of the same inputs; between them mostly only the diff's
    positions moved, if that. Measured by replaying every stored resolve
    beat of both bench stories (`tools/bench/route_scene_merges.py`): the
    descent's 123 beats, 38 rooms at their widest, ran 4.06 merges a beat
    and 43.6 ms of merging; the charter town's 13 ran 2.85 and 9.4 ms.
    Answering them from one merge per distinct (scene, diff) leaves 1.80
    and 22.5 ms, and 1.38 and 5.3 ms, with every beat's route decisions
    byte-identical (review 2026-09-07 C6).

    THE KEY IS THE SCENE AND THE DIFF'S WHOLE CONTENT. Narrowing it to the
    channels a route reads would be the unsafe direction -- the merge
    applies every channel, and a route is judged on rooms, doorways, portals
    and carriers that any of them can move -- and it would buy almost
    nothing: fingerprinting the whole diff costs 0.17 ms against the 11.1
    ms a single merge of that scene takes, 1.4% of what it guards.

    Callers READ the result (`known_rooms`, a route, a relation, whether a
    mint landed in a room); none writes to it, which is what makes one
    shared copy safe. A caller that will mutate must merge its own.
    """
    if ctx is None:
        return merge_scene_with_diff(scene, state_diff)
    try:
        fingerprint = hashlib.sha1(json.dumps(
            state_diff, sort_keys=True, default=str,
            ensure_ascii=False).encode("utf-8")).hexdigest()
    except Exception:
        return merge_scene_with_diff(scene, state_diff)
    stamp = _route_positions_stamp(scene)
    memo = ctx.get(_ROUTE_MEMO)
    if not isinstance(memo, dict):
        memo = {}
    held = memo.get(id(scene))
    if isinstance(held, tuple) and len(held) == 4:
        held_scene, held_stamp, held_print, merged = held
        # The scene is checked by IDENTITY as well as by `id()`, because a
        # freed dict's address is reused; holding it here is also what keeps
        # that from happening mid-turn.
        if held_scene is scene and held_stamp == stamp \
                and held_print == fingerprint:
            return merged
    merged = merge_scene_with_diff(scene, state_diff)
    memo[id(scene)] = (scene, stamp, fingerprint, merged)
    try:
        ctx[_ROUTE_MEMO] = memo
    except (TypeError, AttributeError):
        pass                      # a context that keeps no side channels
    return merged


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
        names = [n for n in [p_name] + [character_name_from_text(c["sheet"])
                                        for c in (ctx.cast or [])] if n]
        digest = sight_digest(sc, names)
    except Exception:
        return None
    # WHERE THE LIGHT FALLS AND WHERE THE SOUND IS, per named body: the
    # SAME sentences that body's own view carries (`composer.
    # field_shape_sentence` over `light_shape`/`sound_shape`), so the
    # Director resolving "she steps out of the lamplight" reads exactly what
    # the observer was told and not a number the observer never had. Absent
    # for a body whose room is even, has no geometry, or gives it no cell.
    try:
        from agents import composer
        from world.spatial import light_shape, sound_shape
        language = getattr(ctx, "language", None)
        light = {}
        sound = {}
        for name in names:
            shape = light_shape(sc, name)
            if shape:
                light[name] = composer.field_shape_sentence(
                    "light", shape, language=language)
            shape = sound_shape(sc, name)
            if shape:
                sound[name] = composer.field_shape_sentence(
                    "sound", shape, language=language)
        if light:
            digest["light"] = light
        if sound:
            digest["sound"] = sound
    except Exception:
        pass
    return digest


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


def _planned_elsewhere_view(sc, ctx, briefed):
    """Every planned room the scene does not hold and the brief did not
    cover, as `{room_uid: name}` -- so a place the story has already planned
    can be NAMED from anywhere, not only from beside it.

    `_planned_rooms_view` above is the development brief and stays scoped to
    reach; this is the spelling, and a spelling has to travel as far as the
    player's attention does (`world.structure.planned_room_index`, and
    docs/UNBUILT.md § 1.127 for the town that got built twice).
    """
    try:
        from world.structure import planned_room_index
        index = planned_room_index(ctx.chat["id"], sc)
        for rid in (briefed or ()):
            index.pop(rid, None)
        return index or None
    except Exception:
        return None


def movement_for_resolve(ctx, interp):
    """The beat's declared movement with its destination spelled as the
    world spells it. The compiler (`agents/mapping.classify_movement`)
    resolved the Director's spelling against the scene and the plan and put
    the resolved id on its step; every resolve-side reader of the
    destination -- the planned-room brief, the residue, the figures in
    view, the hands'
    payloads -- takes it from here, so a planned room is furnished under
    its own id rather than minted again beside itself. Unchanged when the
    compiler classified nothing or agreed with the spelling."""
    from core.pipeline_context import canonical_movement
    mv = interp.get("movement") if isinstance(interp, dict) else None
    try:
        compiled = (ctx.world_context() or {}).get("movement")
    except Exception:
        compiled = None
    return canonical_movement(mv, compiled)


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


def _reconcile_near_group_positions(ctx, scene, state_diff, player_name, held=()):
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
    # A follower the carry held where they are this beat (`held`) is in no
    # group: a fresh near link -- theirs, the walker's, or a third body's --
    # must neither carry them off nor drag the walker back (review,
    # 2026-10-05).
    held_keys = {str(_ci_mapping_key(all_positions, h) or h).casefold() for h in held or ()}
    for raw_name, station in stations.items():
        if not isinstance(station, dict):
            continue
        body = _ci_mapping_key(all_positions, raw_name)
        if body is None or str(body).casefold() in held_keys:
            continue
        station_by_body[body] = station
        for raw_other in station.get("near") or []:
            other = _ci_mapping_key(all_positions, raw_other)
            if other is None or other == body or str(other).casefold() in held_keys:
                continue
            declared_near.setdefault(body, set()).add(other)
            graph.setdefault(body, set()).add(other)
            graph.setdefault(other, set()).add(body)

    if not graph:
        return False

    route_scene = route_scene_for(ctx, scene, state_diff)
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
            # Anchor ids are ROOM-scoped: one door has an anchor on each of
            # its sides under the same id (chat 116, 2026-09-04:
            # `station_door` on the platform and on the gallery). A body's
            # anchor is the one in the room it stands in; only when that
            # fails is the id looked up scene-wide.
            own_room = all_positions.get(body)
            if own_room in owners:
                owners = {own_room}
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
                    route_scene, origin, target_room, body=body):
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




def walkers_this_beat(out, player_name, cast=()):
    """The bodies that WALKED this beat -- the travel record's subjects,
    walked by their own declared move or their own follow, and every cast
    member the encoder placed in a room through an event carried out from
    its OWN declaration -- the player aside, whose room the near-group
    repair already never takes from somebody else's station. A walk ends
    where it ended: a near claim, a decoration on the ledger, is not
    evidence it did not happen (scratch story 166, turn 4596).

    The second half because a walk need not pass the travel system: the
    encoder can write a body's room as a `positions` patch with no
    `movement`. Scratch story 166 idx 22: the pilot's own events put her on
    the low walk, she was in no travel record, and the repair pulled her
    back to the landing stage "by fresh anchor" -- so the page walked her to
    her brother's door while the world kept her on the stage."""
    travel = (out or {}).get("travel") if isinstance((out or {}).get("travel"), dict) else {}
    walkers = {str(a.get("subject")) for a in travel.get("advanced") or ()
               if isinstance(a, dict) and a.get("subject")}
    walkers |= {str(x) for x in travel.get("arrived") or () if x}
    names = {}
    for row in cast or ():
        try:
            names[f"character:{row['id']}"] = character_name_from_text(row["sheet"])
        except Exception:
            continue
    events = (((out or {}).get("orchestration") or {}).get("prose_contract") or {}).get("events")
    for event in events or ():
        own = names.get(str((event or {}).get("source_entity_id") or "")) \
            if isinstance(event, dict) else None
        if not own:
            continue
        for transform in event.get("transforms") or ():
            placed = (transform.get("patch") or {}).get("positions") \
                if isinstance(transform, dict) and isinstance(transform.get("patch"), dict) else None
            if isinstance(placed, dict) and any(
                    str(key).strip().casefold() == own.casefold() for key in placed):
                walkers.add(own)
    walkers.discard(str(player_name or ""))
    return walkers


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


def declared_follow_op(assertions, mover):
    """`{op, target?, reason}`: the follow `mover` declared in its own span
    this stage -- the last `following_ops` op the encoder filed for it as
    follower -- or None.

    THE INTERPRET'S `follow_op` IS THIS, RESTORED. The monolithic interpret
    card asked for `follow_op` itself ("FOLLOWING STATE ... Emit follow_op
    ONLY when this beat changes it") and went whole with the causal
    Director's redesign (2026-09-12, c452a50d); under the prose contract a
    player's follow reaches the encoder's `following_ops` channel instead,
    and nothing read it back onto the field every follow reader takes the
    player's decision from -- `_collect_following_ops`, the follow floor
    below, and the resolve's `player_declaration`. Measured: `follow_op` on 8
    of 4,214 stored interprets, all before 2026-09-12; the encoder's player
    follow on 19, none of them on the field. `a_walk_is_its_owners` has
    already refused any op a span wrote for a mind other than its own, so
    an op for `mover` here is the mover's."""
    folded = str(mover or "").strip().casefold()
    if not folded or not isinstance(assertions, dict):
        return None
    found = None
    for raw in assertions.get("following_ops") or ():
        if not isinstance(raw, dict) \
                or str(raw.get("follower") or "").strip().casefold() != folded:
            continue
        op = str(raw.get("op") or "").strip().casefold()
        if op == "start" and str(raw.get("target") or "").strip():
            found = {"op": "start", "target": str(raw["target"]).strip(),
                     "reason": str(raw.get("reason") or "").strip()}
        elif op == "stop":
            found = {"op": "stop", "reason": str(raw.get("reason") or "").strip()}
    return found


def _canonical_following_ops(ops, cast, player_name, turn_idx=None, scene=None):
    """This beat's following ops with each body spelled as the scene keys
    it, and the beat that wrote them on every one.

    The encoder names a body as the beat names it, and now and then by the
    id of its scene record: scratch story 166 turn 4598 filed the player's
    follow of the pilot as target `char_hester_gale`, the pilot's entity id,
    which no positions key answers to, so the ledger dropped it without a
    word (`apply_following_ops` folds case only). Folded with the one
    spelling policy positions use (`common.cast_spelling_policy`), and an
    entity id read as its record's name only where that name is a cast
    member's or the player's -- a thing is keyed by its id, and stays so; a
    spelling nobody registered is left as written."""
    from .common import cast_spelling_policy
    canonical, forms = cast_spelling_policy(cast, player_name, aliases=False)
    entities = (scene or {}).get("entities") if isinstance(scene, dict) else None
    entities = entities if isinstance(entities, dict) else {}

    def spelled(label):
        folded = canonical(label)
        if folded != label:
            return folded
        record = entities.get(label)
        name = str((record or {}).get("name") or "").strip() \
            if isinstance(record, dict) else ""
        return forms.get(name.casefold(), label) if name else label

    out = []
    for raw in ops or ():
        if not isinstance(raw, dict):
            continue
        op = dict(raw)
        for field in ("follower", "target"):
            if str(op.get(field) or "").strip():
                op[field] = spelled(str(op[field]).strip())
        if op.get("turn") is None and turn_idx is not None:
            op["turn"] = turn_idx
        out.append(op)
    return out


def _last_follow_ops(ops):
    """`{folded follower: its last op word}` over this beat's ops: what each
    follower declared last, so a start taken back in the same beat is not a
    follow declared."""
    last = {}
    for raw in ops or ():
        if isinstance(raw, dict) and str(raw.get("follower") or "").strip():
            last[str(raw["follower"]).strip().casefold()] = \
                str(raw.get("op") or "").strip().casefold()
    return last


#: The channels a body's own walk writes about it: which room, where in it,
#: how it stands. Not a cap -- the engine's own channel names. A walk that
#: WAITS on the one it follows (`follow_walk_waits`) is a run of steps that
#: write nothing else about the follower; anything else she did happened
#: where she did it, and keeps the walk where she took it.
_WALK_CHANNELS = ("positions", "stations", "poses")


def _keys_naming(table, scene, who):
    """Every key of `table` that names the body `who`."""
    from world.spatial import same_subject
    folded = str(who or "").strip().casefold()
    return [key for key in (table or {})
            if str(key).strip().casefold() == folded
            or same_subject(scene, str(key), str(who))]


#: How many beats back a follower's ear reaches for the one it follows: the
#: beat it decided on, and the one before -- the last thing a mind took in
#: before it declared. One, because that beat's record still says where both
#: bodies stood when the sound was made (a sound counts only where neither
#: has moved since, `_heard_last_beat`); an older sound has had a beat of
#: moves since it was made, and whether it still says where its maker is
#: would be the engine's guess, not anything the follower perceived.
_FOLLOW_HEARD_BEATS_BACK = 1


def _sees_body(scene, observer, body, senses=None):
    """Whether `observer` SEES `body` in `scene`, by the engine's one rule
    for whether a mind saw a body (`sighted_level`: the pair's graded sight,
    the observer's card senses -- a blind follower sees nothing -- and its
    rear blind spot). A body the scene places nowhere is seen by nobody.
    Graded by the pair alone until 2026-10-09 (review B2), a blind mind was
    walked toward a lit body in the next room."""
    from world.spatial import sighted_level
    if not isinstance(scene, dict) or not room_of(scene, observer) \
            or not room_of(scene, body):
        return False
    return sighted_level(scene, observer, body, senses) != "none"


def _heard_through(pairs, senses):
    """Whether any of `heard_events`' ``(event, level)`` pairs reaches a
    listener with `senses`: the level after its hearing acuity
    (`sense_adjusted`), so a deaf follower hears no footfalls (review B2)."""
    from world.spatial import sense_adjusted
    return any(sense_adjusted(level, "hearing", senses) != "none"
               for _event, level in pairs or ())


def _source_bodies(ctx, player_name):
    """`{folded source_entity_id: body name}` for every mind a beat's ledger
    rows can be sourced to: the player (`persona:<id>` and `persona:primary`),
    each other human player, each cast member (`character:<id>`). A charter
    figure's handle is its name already (`causal_world_index(figures=)`)."""
    index = {"persona:primary": str(player_name or "")}
    chat = getattr(ctx, "chat", None)
    persona_id = chat.get("persona_id") if isinstance(chat, dict) \
        else getattr(chat, "persona_id", None)
    if persona_id is not None:
        index[f"persona:{persona_id}".casefold()] = str(player_name or "")
    for extra in getattr(ctx, "extra_players", None) or ():
        if isinstance(extra, dict) and extra.get("persona_id") is not None:
            index[f"persona:{extra['persona_id']}".casefold()] = str(extra.get("name") or "")
    for row in getattr(ctx, "cast", None) or ():
        try:
            index[f"character:{row['id']}".casefold()] = \
                character_name_from_text(row["sheet"])
        except Exception:
            continue
    return index


def _spoken_by(row, sources, scene, body):
    """Whether ledger `row` is a line `body` itself spoke."""
    from world.spatial import same_subject
    if not isinstance(row, dict) or "speech" not in (row.get("categories") or ()):
        return False
    source = str(row.get("source_entity_id") or "").strip()
    speaker = sources.get(source.casefold()) or source
    return bool(speaker) and (speaker.casefold() == str(body).casefold()
                              or same_subject(scene, speaker, str(body)))


def _follower_id(ctx, follower):
    """The cast id of `follower`, for a concealment list that names it so."""
    for row in getattr(ctx, "cast", None) or ():
        try:
            if character_name_from_text(row["sheet"]).strip().casefold() \
                    == str(follower).strip().casefold():
                return row["id"]
        except Exception:
            continue
    return None


def _voice_reaches(ctx, world, listener, speaker, row, senses):
    """Whether the line ledger `row` records `speaker` saying, in `world`,
    reaches `listener` THROUGH THE AIR -- at the line's own volume, through
    the field and the barriers between their rooms (`spatial_rel_between`,
    `hear_level`, the measured proximity), over the standing noise the
    outcome's field holds -- the story's crowds among it -- through the
    listener's card senses, and not concealed from them. (A beat's one-off
    sounds are moments, never a floor a line is heard over:
    `tests/test_one_off_sounds_are_moments.py`.) The relation carries no live
    channel and no addressed rescue: a voice on a radio, or one named across
    a wall a device must be carrying, says nothing about where its speaker
    stands. The same grading the outcome's speech percepts make (`composer.
    speech_percept`), less the two channels that do not place a body."""
    from world.spatial import (hear_level, measured_proximity_rel,
                               sense_adjusted, sound_field, spatial_rel_between)
    from agents.composer import concealed_from_observer
    if not room_of(world, listener) or not room_of(world, speaker):
        return False
    if concealed_from_observer(row, listener, _follower_id(ctx, listener)):
        return False
    try:
        field = sound_field(world, listener,
                            turn_idx=getattr(getattr(ctx, "turn", None), "idx", None),
                            crowds=_sound_crowds(ctx))
        rel = spatial_rel_between(world, listener, speaker, sound=field)
        level = hear_level(rel, str(row.get("volume") or "normal"),
                           proximity=measured_proximity_rel(world, listener, speaker),
                           level_db=row.get("level_db"))
    except Exception:
        return False
    if senses:
        level = sense_adjusted(level, "hearing", senses)
    return level != "none"


def _sound_crowds(ctx):
    """The story's crowd ledger, as the perception stage reads it for its
    sound fields (`perception._sound_field_for`): a crowd's murmur is noise a
    voice is heard over."""
    crowds = ctx.get("_sound_crowds") if hasattr(ctx, "get") else None
    if crowds is None:
        try:
            from core.db import wget
            from .common import CROWDS_KEY
            crowds = wget(ctx.chat.id, CROWDS_KEY, []) or []
        except Exception:
            crowds = []
        try:
            ctx["_sound_crowds"] = crowds
        except (TypeError, AttributeError):
            pass
    return crowds


def _treads_reach(ctx, world, listener, body, pace, senses=None):
    """Whether `body`'s footfalls at `pace`, where `world` stands it, reach
    `listener` in another room (`tread_events`, `heard_events`: the field
    the outcome grades the beat's treads through), through the listener's
    hearing (`_heard_through`)."""
    from world.spatial import heard_events, tread_events
    if not room_of(world, listener) or not room_of(world, body):
        return False
    try:
        return _heard_through(heard_events(
            world, listener, tread_events(world, {str(body): pace}),
            room=room_of(world, listener),
            turn_idx=getattr(getattr(ctx, "turn", None), "idx", None),
            crowds=_sound_crowds(ctx)), senses)
    except Exception:
        return False


def _sounds_reach(ctx, world, listener, body, events, senses=None):
    """Whether one of `events` -- `sensory_events` rows whose `source` is
    `body` itself -- reaches `listener` where `world` stands them, through
    the listener's hearing (`_heard_through`)."""
    from world.spatial import heard_events, normalize_sensory_event, same_subject
    records = []
    for event in events or ():
        if not isinstance(event, dict):
            continue
        source = str(event.get("source") or "").strip()
        if not source or not (source.casefold() == str(body).casefold()
                              or same_subject(world, source, str(body))):
            continue
        record = normalize_sensory_event(event, rooms=world.get("rooms") or {})
        if record:
            records.append(dict(record, desc=record.get("detail")))
    if not records or not room_of(world, listener):
        return False
    try:
        return _heard_through(heard_events(
            world, listener, records, room=room_of(world, listener),
            turn_idx=getattr(getattr(ctx, "turn", None), "idx", None),
            crowds=_sound_crowds(ctx)), senses)
    except Exception:
        return False


#: The order a beat's stages run in (`causal_program.program_from_history`
#: and its closing engine step): the declaration's onset, then the resolve,
#: then what the engine writes after both. Not a cap.
_STAGE_ORDER = {"interpret": 0, "resolve": 1, "engine": 2}


def _moment_of(steps, stage, chrono):
    """The index of the first of `steps` (a beat's causal steps, or the
    worlds merged from them, in program order) that `stage`'s span `chrono`
    happened at or before: its own step, or -- a span that wrote nothing has
    none -- the next one. `len(steps)` when it came after them all."""
    try:
        key = (_STAGE_ORDER.get(str(stage), 1), int(chrono))
    except (TypeError, ValueError):
        return None
    for i, step in enumerate(steps):
        try:
            here = (_STAGE_ORDER.get(str(step.get("stage")), 1),
                    int(step.get("chrono_id") or 0))
        except (TypeError, ValueError, AttributeError):
            continue
        if here >= key:
            return i
    return len(steps)


def _unplaced_lines(record, stage, scene, body, player_name):
    """The lines `body` spoke in a stage record that keeps no ledger: the
    declaration's own `speech` elements when `body` is the player, and the
    resolve's `dialogue_log` lines spoken by `body`."""
    from world.spatial import same_subject
    if stage == "interpret":
        if str(body).casefold() != str(player_name or "").casefold():
            return []
        return [e for e in record.get("sequence") or ()
                if isinstance(e, dict) and e.get("type") == "speech"]
    return [line for line in record.get("dialogue_log") or ()
            if isinstance(line, dict) and str(line.get("speaker") or "").strip()
            and (str(line["speaker"]).strip().casefold() == str(body).casefold()
                 or same_subject(scene, str(line["speaker"]).strip(), str(body)))]


def _walked_at(travel, body):
    """`body`'s pace when the travel record walked it any paces, else None."""
    for entry in ((travel or {}).get("advanced") or ()) \
            if isinstance(travel, dict) else ():
        if not isinstance(entry, dict) \
                or str(entry.get("subject") or "").strip().casefold() \
                != str(body).strip().casefold():
            continue
        try:
            if float(entry.get("paces") or 0) > 0:
                return str(entry.get("pace") or "walk").strip().casefold() or "walk"
        except (TypeError, ValueError):
            continue
    return None


def _heard_this_beat(ctx, scene, state_diff, interp, out, follower, target,
                     senses, player_name):
    """The room `target` was in when the LAST sound it made this beat that
    reached `follower` was made, or None.

    A SOUND THE BODY MADE, never a channel one could cross: its own lines
    (the ledger rows spoken from its span, at their own volume, graded in the
    world of the moment they were said in -- `_moment_of`), its footfalls
    where the beat walked it (`travel`, graded where the walk ended, as the
    outcome grades a beat's treads), and the noises the beat's diff sources
    to its body (graded where the outcome grades them: in the step they came
    from, else where the beat ends). A silent body that does not move made
    nothing to hear. The follower has not moved: a follower the beat moved
    is not walked after anyone."""
    sources = _source_bodies(ctx, player_name)
    worlds = []
    try:
        end = merge_scene_with_diff(scene, state_diff, causal_worlds=worlds)
    except Exception:
        return None
    worlds = [w for w in worlds if isinstance(w, dict)]
    heard = []                                   # (moment, room)
    stayed = room_of(scene, target) == room_of(end, target)
    for stage, record in (("interpret", interp), ("resolve", out)):
        if not isinstance(record, dict):
            continue
        if not isinstance(record.get("causal_ledger"), list):
            # A record with no ledger (an older shape) gives its lines no
            # moment, so a line counts only where the speaker never changed
            # room: then where it spoke is where it stands.
            if stayed and any(
                    _voice_reaches(ctx, scene, follower, target, line, senses)
                    for line in _unplaced_lines(record, stage, scene, target,
                                                player_name)):
                heard.append((0, room_of(scene, target)))
            continue
        for row in record["causal_ledger"]:
            if not _spoken_by(row, sources, scene, target):
                continue
            moment = _moment_of(worlds, stage, row.get("chrono_id"))
            if moment is None:
                continue
            world = (worlds[moment].get("before") if moment < len(worlds)
                     else end) or {}
            if _voice_reaches(ctx, world, follower, target, row, senses):
                heard.append((moment, room_of(world, target)))
    pace = _walked_at((out or {}).get("travel") if isinstance(out, dict) else None,
                      target)
    if pace and _treads_reach(ctx, end, follower, target, pace, senses):
        moved = [i for i, w in enumerate(worlds)
                 if room_of(w.get("before") or {}, target)
                 != room_of(w.get("after") or {}, target)]
        heard.append((moved[-1] if moved else len(worlds), room_of(end, target)))
    events = state_diff.get("sensory_events") if isinstance(state_diff, dict) else None
    if events:
        at = {str(w.get("chrono_id")): i for i, w in enumerate(worlds)
              if str(w.get("stage") or "") == "resolve"}
        for event in events:
            if not isinstance(event, dict):
                continue
            moment = at.get(str(event.get("from_event")))
            world = (worlds[moment].get("after") or {}) if moment is not None else end
            if _sounds_reach(ctx, world, follower, target, [event], senses):
                heard.append((len(worlds) if moment is None else moment,
                              room_of(world, target)))
    heard = [(moment, room) for moment, room in heard if room]
    return max(heard, key=lambda pair: pair[0])[1] if heard else None


def _heard_last_beat(ctx, scene, follower, target, senses, player_name):
    """The room `target` stands in when a sound it made on the beat before
    this one reached `follower`, or None -- read from that beat's committed
    resolve, as `common.widen_reactors_to_engaged` reads it.

    Only a sound made where both bodies still stand: a step after it that
    moved either of them means it was made, or heard, somewhere the scene no
    longer says, so it is not read (nor is a beat that recorded no steps,
    nor one whose diff left either body in a room other than the one it
    stands in now). What is left is graded in the scene this beat began in,
    which is where that beat left them both."""
    try:
        idx = int(getattr(getattr(ctx, "turn", None), "idx", None))
    except (TypeError, ValueError):
        return None
    if idx - _FOLLOW_HEARD_BEATS_BACK < 0:
        return None
    try:
        from core.db import q
        rows = q("SELECT s.key AS key, v.content AS content FROM turns t "
                 "JOIN steps s ON s.turn_id=t.id "
                 "JOIN variants v ON v.step_id=s.id AND v.active=1 "
                 "WHERE t.chat_id=? AND t.idx=? AND t.frame_id IS ? "
                 "AND s.key IN ('director_interpret','director_resolve')",
                 (ctx.chat.id, idx - _FOLLOW_HEARD_BEATS_BACK,
                  getattr(ctx.turn, "frame_id", None)))
        stored = {row["key"]: json.loads(row["content"]) for row in rows}
    except Exception:
        return None
    resolved = stored.get("director_resolve")
    if not isinstance(resolved, dict):
        return None
    diff = resolved.get("state_diff") if isinstance(resolved.get("state_diff"), dict) else {}
    steps = [s for s in diff.get("causal_steps") or () if isinstance(s, dict)]
    if not steps or not room_of(scene, follower) or not room_of(scene, target):
        return None
    left = diff.get("positions") if isinstance(diff.get("positions"), dict) else {}
    for who in (follower, target):
        if any(str(left[key]) != room_of(scene, who)
               for key in _keys_naming(left, scene, who)):
            return None

    def moved(i, who):
        table = (steps[i].get("patch") or {}).get("positions")
        return bool(_keys_naming(table if isinstance(table, dict) else {},
                                 scene, who))

    still = max((i for i in range(len(steps))
                 if moved(i, follower) or moved(i, target)), default=-1)
    sources = _source_bodies(ctx, player_name)
    for stage, record in (("interpret", stored.get("director_interpret")),
                          ("resolve", resolved)):
        for row in (record or {}).get("causal_ledger") or () \
                if isinstance(record, dict) else ():
            moment = _moment_of(steps, stage, row.get("chrono_id"))
            if moment is not None and moment > still \
                    and _spoken_by(row, sources, scene, target) \
                    and _voice_reaches(ctx, scene, follower, target, row, senses):
                return room_of(scene, target)
    pace = _walked_at(resolved.get("travel"), target)
    walked = [i for i in range(len(steps)) if moved(i, target)]
    if pace and walked and not any(moved(i, follower)
                                   for i in range(walked[-1] + 1, len(steps))) \
            and _treads_reach(ctx, scene, follower, target, pace, senses):
        return room_of(scene, target)
    at = {str(s.get("chrono_id")): i for i, s in enumerate(steps)
          if str(s.get("stage") or "") == "resolve"}
    late = [event for event in diff.get("sensory_events") or ()
            if isinstance(event, dict)
            and at.get(str(event.get("from_event")), len(steps)) > still]
    if late and _sounds_reach(ctx, scene, follower, target, late, senses):
        return room_of(scene, target)
    return None


def _mind_senses(ctx, name, player_name):
    """`(is_mind, senses)` for a follower: whether `name` is a mind -- the
    player, another human player, a registered cast member -- and that mind's
    structured card senses (None where the card gives none or cannot be
    read). Any other body is a figure, whose walk is the world's to carry
    (the charter ruling: pure code off screen): `(False, None)`."""
    folded = str(name or "").strip().casefold()
    if not folded:
        return False, None
    if folded == str(player_name or "").strip().casefold():
        try:
            from story.character_schema import persona_senses
            from story.scene import persona_of
            return True, persona_senses(persona_of(ctx.chat)) or None
        except Exception:
            return True, None
    try:
        extras = list(ctx.extra_players or ())
    except Exception:
        extras = []
    if any(isinstance(extra, dict)
           and str(extra.get("name") or "").strip().casefold() == folded
           for extra in extras):
        return True, None
    try:
        cast = list(ctx.cast or ())
    except Exception:
        cast = []
    for row in cast:
        try:
            if character_name_from_text(row["sheet"]).strip().casefold() != folded:
                continue
        except Exception:
            continue
        try:
            from story.character_schema import (character_senses,
                                                normalized_character_from_text)
            return True, character_senses(
                normalized_character_from_text(row["sheet"])) or None
        except Exception:
            return True, None
    return False, None


def _perceived_room(ctx, scene, end_scene, follower, target, destination,
                    senses, *, state_diff=None, interp=None, out=None,
                    player_name=None):
    """Where a follower goes after `target`: the room where it LAST
    perceived them, latest first -- seen there once the beat's moves are
    made (`end_scene`, the follower still where it stood); heard there this
    beat, the last sound of theirs that reached it (`_heard_this_beat`);
    seen there when the beat began; heard there on the beat before
    (`_heard_last_beat`) -- else None, nothing perceived to follow.

    PERCEIVED, NEVER PERCEIVABLE (review N1, 2026-10-09). Round 2 asked
    whether a NORMAL VOICE WOULD carry between the rooms, never whether the
    one followed made a sound: a silent body behind a curtain, or standing
    in a dark doorway, was walked to, because a voice could have crossed.
    A body that makes no sound is heard by nobody, so only sight and a
    sound it made count -- and never the room the world alone knows it to
    be in."""
    start = room_of(scene, target)
    if destination and destination != start \
            and _sees_body(end_scene, follower, target, senses):
        return destination
    heard = _heard_this_beat(ctx, scene, state_diff, interp, out, follower,
                             target, senses, player_name)
    if heard:
        return heard
    if start and _sees_body(scene, follower, target, senses):
        return start
    return _heard_last_beat(ctx, scene, follower, target, senses, player_name)


def follow_walk_waits(sequence, assertions, scene, follower, follow):
    """The event ids of the declaration's elements whose walk WAITS ON THE
    ONE IT FOLLOWS, or [] when the walk is hers to take at the onset.

    A follow is a walk WITH someone, so it happens when theirs does, and
    that has to be settled before anybody perceives the beat: the cast
    declares from the onset, where the player's declaration has already
    happened (`perception_act`, `loops._beat_onset_scene`, the resolve's
    preview). Walked at the onset, a player who "walks a step behind the
    pilot along the low walk and up the stair" (scratch story 166 turn 4607)
    had gone up the stair before the pilot moved, and the pilot declared
    from a world where she was gone, while the committed beat walked them
    up together (review F3, 2026-10-09). Marked a `continuation` phase, the
    walk is what the engine already makes of a phase that waits for the
    others' answer: the onset preview and the cast's act views leave it out
    (`common.sequence_onset_elements`, the interpret's phase floor), the
    outcome and the page tell it after the answer (`perception.
    _outcome_event_stream`, the narrator's deferred lines), and the resolve
    is where it happens: its author is handed the walk as her input, never
    as done (`director._causal_event_inputs`, `director_prose.
    already_happened`), and where its encoder writes no step of hers she
    walks in the steps that move the one she follows
    (`follow_through_the_steps`).

    Deferred only when all of it holds: her own span declared the follow
    this beat (`follow`, a `start`); the one she follows stands in her room
    when the beat begins, and does not move inside her declaration; and
    every step from the first that changes her room to the end of her
    declaration writes her room and nothing but her walk channels and the
    follow itself -- and those about her alone (`_writes_only`: a dog her
    span walks at her heel in the same step would wait with her, and be
    left out of the beat when the walk was taken from the onset, review
    N3). A line, an act or a hand on something after the walk happened where
    the walk took her, so that walk stays where she took it, and so does
    every walk under a follow from an earlier beat: a walk she declares on
    her own is hers at the onset."""
    if not isinstance(follow, dict) or follow.get("op") != "start":
        return []
    target = str(follow.get("target") or "").strip()
    origin = room_of(scene, follower)
    if not target or not origin or room_of(scene, target) != origin:
        return []
    steps = assertions.get("causal_steps") if isinstance(assertions, dict) else None
    if not isinstance(steps, list) or not steps:
        return []

    def her_room(step):
        patch = step.get("patch") if isinstance(step, dict) else None
        table = patch.get("positions") if isinstance(patch, dict) else None
        keys = _keys_naming(table if isinstance(table, dict) else {}, scene, follower)
        return str(table[keys[-1]]) if keys else None

    first = next((i for i, step in enumerate(steps)
                  if her_room(step) and her_room(step) != origin), None)
    if first is None:
        return []
    # The one she follows moving inside her own declaration -- a figure her
    # span walks, or one she holds -- walks in its chronology already, and
    # her walk beside them with it.
    if any(_keys_naming(((step.get("patch") or {}).get("positions") or {})
                        if isinstance(step, dict) else {}, scene, target)
           for step in steps):
        return []
    walked, before = set(), set()
    for i, step in enumerate(steps):
        events = {str(e) for e in (step.get("events") or ())} \
            if isinstance(step, dict) else set()
        if i < first:
            before |= events
            continue
        patch = step.get("patch") if isinstance(step, dict) else None
        if not isinstance(patch, dict) or not her_room(step) \
                or any(channel not in _WALK_CHANNELS + ("following_ops",)
                       for channel in patch) \
                or not _writes_only(patch, scene, follower):
            return []
        walked |= events
    elements = {str(e.get("event_id")) for e in sequence or ()
                if isinstance(e, dict) and e.get("event_id")}
    waits = (walked & elements) - before
    # An element that also carried an act before the walk cannot wait
    # without taking that act with it.
    if not waits or (walked & elements) & before:
        return []
    return sorted(waits)


def _writes_only(patch, scene, follower):
    """Whether every body a step's walk channels write -- each `positions`,
    `stations` and `poses` key, and each `following_ops` row's follower --
    is `follower`: a walk that is hers alone, which can wait on the one she
    follows without taking anybody else's move out of the beat."""
    for channel in _WALK_CHANNELS:
        table = patch.get(channel)
        if table is None:
            continue
        if not isinstance(table, dict):
            return False
        hers = set(_keys_naming(table, scene, follower))
        if any(key not in hers for key in table):
            return False
    ops = patch.get("following_ops")
    for op in (ops if isinstance(ops, list) else [ops] if ops else []):
        if not isinstance(op, dict) or not _keys_naming(
                {str(op.get("follower") or ""): True}, scene, follower):
            return False
    return True


def _waiting_walk_poses(interp, scene, follower):
    """Her poses from the walk that waited on the one she follows (the
    elements `follow_walk_waits` marked `walks_with`), in order, read off
    the interpret's whole record -- the onset preview lost them with the
    walk."""
    interp = interp if isinstance(interp, dict) else {}
    waiting = {str(e.get("event_id")) for e in interp.get("sequence") or ()
               if isinstance(e, dict) and e.get("walks_with") and e.get("event_id")}
    if not waiting:
        return []
    out = []
    for step in ((interp.get("state_assertions") or {}).get("causal_steps") or ()):
        if not isinstance(step, dict) \
                or not waiting & {str(e) for e in step.get("events") or ()}:
            continue
        table = (step.get("patch") or {}).get("poses")
        table = table if isinstance(table, dict) else {}
        out.extend(table[key] for key in _keys_naming(table, scene, follower))
    return out


def _own_conduct(ctx, interp, out, player_name):
    """`(event ids, resolve chrono ids, walk ids)` of the player's own
    conduct this beat: her declaration's elements and its raw input; the
    resolve's ledger rows sourced from her; and, of those elements, the
    ones that are her walk waiting on the one she follows (`walks_with`)."""
    interp = interp if isinstance(interp, dict) else {}
    elements = [e for e in interp.get("sequence") or ()
                if isinstance(e, dict) and e.get("event_id")]
    ids = {str(e["event_id"]) for e in elements}
    turn_id = getattr(getattr(ctx, "turn", None), "id", None)
    if turn_id is not None:
        ids.add(f"turn:{turn_id}:primary:raw")
    walk = {str(e["event_id"]) for e in elements if e.get("walks_with")}
    folded = str(player_name or "").strip().casefold()
    sources = {key for key, name in _source_bodies(ctx, player_name).items()
               if str(name or "").strip().casefold() == folded}
    chronos = {str(row.get("chrono_id"))
               for row in (out or {}).get("causal_ledger") or ()
               if isinstance(row, dict)
               and str(row.get("source_entity_id") or "").strip().casefold() in sources}
    return frozenset(ids), frozenset(chronos), frozenset(walk)


def follow_through_the_steps(state_diff, scene, follower, target, poses=(),
                             own=None):
    """A FOLLOWER WALKS WHEN THE ONE SHE FOLLOWS WALKS -- in the beat's
    chronology as well as at its end. Writes the follower into the causal
    steps in which the one she follows changes room, beside them, and
    returns True when it did.

    The beat runs the player's declaration first (interpret's steps, the
    onset) and everyone else's after it (resolve's), so a player who
    declared "a step behind the pilot along the low walk and up the stair"
    was walked there at the onset, before the pilot had even stepped off the
    boat; every word the pilot said on the way was graded from where the
    onset had put the player. Scratch story 166 (F88): turn 4598's whispered
    "eyes on the boards, not them" came from two rooms away, and turn 4607's
    directions "a step behind" her came through as fog fragments. A follow
    is a walk WITH someone, so at each step where the one followed changes
    room she changes room with them, her last pose (`poses`, from the walk
    that waited) arriving with them.

    ONLY WHERE NO STEP OF THE BEAT MOVES HER ALREADY. A walk taken at the
    onset happened where the cast perceived it and declared from it -- a
    walk of her own under a follow from an earlier beat, a walk with a line
    or an act after it -- so it stays where she took it; the walk that waits
    is settled before anyone perceives the beat (`follow_walk_waits`) and
    reaches the resolve as her input, so the steps its encoder writes for
    her are the chronology its author gave the walk, and stand. A walk the
    encoder wrote no step for, and a follow with no walk of her own at all,
    ride the steps of the one she follows. Nor where they change no room.

    AND NEVER AHEAD OF AN ACT OF HER OWN (review N2, F2's class): an act of
    hers later in the beat -- a step carrying one of her declaration's
    elements or its raw input, or a resolve row sourced from her (`own`,
    `_own_conduct`), other than the walk itself and the steps that move the
    one she follows -- happened where she stood, so she rides only their
    steps after her last such act. Where none is left, she lands where they
    ended when the beat does, as before: a standing follow of a porter her
    own span walked up the trail, then her hand lifting the latch of the
    gate she still stood at, had put her on the trail before she touched
    the gate.

    The steps are COPIED before they are written: the onset's are the
    interpret's own record's, shared by reference with `ctx.
    director_interpret` (`common.merge_player_state_assertions`), and
    written in place the interpret lost its own steps (review F8,
    2026-10-09)."""
    steps = state_diff.get("causal_steps") if isinstance(state_diff, dict) else None
    if not isinstance(steps, list) or not steps:
        return False

    def positions_of(step):
        patch = step.get("patch") if isinstance(step, dict) else None
        table = patch.get("positions") if isinstance(patch, dict) else None
        return table if isinstance(table, dict) else {}

    if any(_keys_naming(positions_of(step), scene, follower) for step in steps):
        return False
    theirs = []
    for i, step in enumerate(steps):
        keys = _keys_naming(positions_of(step), scene, target)
        if keys:
            theirs.append((i, str(positions_of(step)[keys[-1]])))
    ids, chronos, walk = own if own else (frozenset(), frozenset(), frozenset())
    moving = {i for i, _ in theirs}

    def an_act_of_hers(i, step):
        if i in moving or not isinstance(step, dict):
            return False
        mine = {str(e) for e in step.get("events") or ()} & ids
        if mine and not mine <= walk:
            return True
        return str(step.get("stage") or "") == "resolve" \
            and str(step.get("chrono_id")) in chronos \
            and not ({str(e) for e in step.get("events") or ()} & walk)

    last_act = max((i for i, step in enumerate(steps) if an_act_of_hers(i, step)),
                   default=-1)
    theirs = [(i, room) for i, room in theirs if i > last_act]
    if not theirs:
        return False
    steps = copy.deepcopy(steps)
    last = theirs[-1][0]
    for i, room in theirs:
        patch = steps[i].get("patch")
        if not isinstance(patch, dict):
            patch = steps[i]["patch"] = {}
        patch.setdefault("positions", {})[follower] = room
        patch.setdefault("stations", {})[follower] = {"near": [target]}
        if i == last and poses:
            patch.setdefault("poses", {})[follower] = copy.deepcopy(list(poses)[-1])
    state_diff["causal_steps"] = steps
    return True


def _walk_was_the_follow(out, follower, room):
    """The travel record of a body the follow carried: it went where the one
    it follows went, and it is not under way on its own -- the follow
    carries it on, beat by beat, as long as it lasts. Its footfalls stay on
    the record (`perception._beat_movers` reads its paces), and its own
    approach is retired (`arrived`), so silence never walks it on alone,
    ahead of the one it follows, toward a place they have not reached."""
    travel = _travel_record(out)
    for entry in travel["advanced"]:
        if isinstance(entry, dict) and \
                str(entry.get("subject") or "").strip().casefold() == follower.casefold():
            entry["to"] = room
            entry["destination"] = room
            entry["underway"] = False
    if follower not in travel["arrived"]:
        travel["arrived"].append(follower)


#: The postures nobody walks in (`spatial_fov.posture_word_class`'s classes):
#: the one half of the evidence a follower stayed where they were.
_RESTING_POSTURES = frozenset({"sitting", "kneeling", "crouching", "lying"})


def _set_down_where_they_are(merged, state_diff, body, origin, target, destination,
                             travelling=()):
    """Whether this beat's own evidence leaves `body` resting in `origin`
    while `target` walks off to `destination`: a pose written this beat in a
    posture nobody walks in, on a support that is THERE -- the origin room
    itself, an anchor only the origin owns, or a thing the beat's merged
    scene (`merged`) still has in the origin. Anything else -- no pose,
    standing, a posture this layer does not know, a support at the
    destination, on the one followed or a part of them, or carried by either
    -- is no such evidence, and the relation carries them as before.

    THE BODY'S OWN BEAT OUTRANKS ITS STANDING INTENT. Following is durable
    intent the carry acts on for a follower who is otherwise free to go. Live,
    Kirinoura (scratch chat 167 turn 3, 2026-10-05): the Doctor had started
    following the surveyor two beats before, and told "Stay here a minute"
    he declared crouching over the terrace slabs with his screwdriver while
    she walked down the stair. The diff posed him crouching on the terrace,
    and the carry moved him onto the stair beside her anyway -- two answers
    to where he was, and the view and the page told the second ("within
    arm's reach", "a step and a half below me"). The test is strict on
    purpose: two review rounds found a looser one stranding followers who sat
    down at the destination, walked on origin ground, or rode a support that
    moved (2026-10-05)."""
    from world.spatial import carrier_chain, posture_word_class, same_subject

    poses = state_diff.get("poses") or {}
    if not isinstance(poses, dict):
        return False
    pose = None
    for key, value in poses.items():
        if isinstance(value, dict) and same_subject(merged, key, body):
            pose = value
            break
    if pose is None or posture_word_class(pose.get("posture")) not in _RESTING_POSTURES:
        return False
    support = str(pose.get("support") or "").strip()
    if not support or not origin:
        return False
    # A part is its owner's ("<owner>.<part>", "<owner>'s <part>").
    owner = support.partition(".")[0].strip() if "." in support else support
    for mark in ("'s ", "\u2019s "):
        if mark in owner:
            owner = owner.split(mark, 1)[0].strip()
    # Bodies that go this beat whatever happens to this one: the one followed
    # and every fellow follower of theirs (`travelling`) -- a rider on a
    # fellow follower's back, or on the litter she carries, goes with her
    # (review round 3, 2026-10-05).
    goers = [target, body, *travelling]
    for spelling in {support, owner}:
        if any(same_subject(merged, spelling, g) for g in goers):
            return False
        if any(same_subject(merged, c, g) for c in carrier_chain(merged, spelling)
               for g in goers):
            return False
    rooms = merged.get("rooms") or {}
    room = rooms.get(origin) or {}
    folded = support.casefold()
    if folded in (str(origin).casefold(), str(room.get("name") or "").casefold()):
        return True

    def _owns(room_record):
        anchors = (room_record or {}).get("anchors") or {}
        return isinstance(anchors, dict) and any(
            str(a).casefold() == folded for a in anchors)

    # Anchor ids are room-scoped and repeat across a doorway: only one the
    # destination does not also own says the body is in the origin.
    if _owns(room):
        return not _owns(rooms.get(destination) if destination else None)
    # A part is where its owner is: "Mara.lap" names no room of its own, and
    # a rider on a fellow follower set down herself was carried off her lap
    # (review round 5, 2026-10-05).
    return room_of(merged, support) == origin or (
        owner != support and room_of(merged, owner) == origin)


def _apply_following_movement(ctx, scene, state_diff, interp, player_name,
                              out=None, held=None):
    """Carry willing followers through ordinary travel, never pursuit.

    The relation is durable intent, not a tether. A follower is moved only
    when they and the target began co-located, the target changed rooms at an
    ordinary pace, and a passable route reaches the destination. Running or
    fleeing leaves the follower behind with the relation still active, so they
    may choose to chase or stop on their next decision. Actor-owned stop ops
    take effect before any carry.

    THE PLAYER IS CARRIED BY A FOLLOW OF HER OWN (the owner's ruling,
    2026-10-09, D1). "A mind moves only by its own declaration" is honoured
    by a declared follow, not overridden: the follow IS her declaration. She
    goes where they go when she declared no place of her own, and goes when
    they go (`follow_walk_waits`, `follow_through_the_steps`). A place she
    did declare is hers, and wins over a follow declared in the same breath:
    when the one she follows ends somewhere else, the floor below ends the
    follow and her walk stands, with every act she did at its end (review
    F2, 2026-10-09). Scratch story 166 turn 4607 (F101) needed no exemption
    from that floor: once a room the beat builds counts as one the world
    holds (`director._final_movement`), her walk and the pilot's end on the
    same landing. A FOLLOW IS WALKED ALONG WHAT ITS FOLLOWER PERCEIVED: one
    begun toward a body in another room goes where the follower last saw
    them or heard a sound they made, this beat or the one before, and with
    nothing perceived it moves nobody and says so (review F1 and N1) -- the
    world knowing where a body is gives no mind a way to it, and nor does a
    wall a voice could have crossed. A follow nobody declared never moves
    anyone: every op here is its follower's own (`a_walk_is_its_owners`
    refuses one any other span wrote), and pace, barriers and a sprint bound
    her as they bound everyone.
    """
    from world.spatial import apply_following_ops

    ops = list(state_diff.get("following_ops") or [])
    # NOBODY IS FOLLOWING ANYBODY, AND THE MERGE CANNOT MAKE IT SO. The
    # ledger below is `apply_following_ops` run over the scene's own
    # `following`, and that function only ADDS on an op -- so an empty ledger
    # and no ops is an empty ledger, and the deep copy that discovered it was
    # the whole cost of the discovery. Measured (review 2026-09-07 C6): a
    # merge of the descent's 38-room scene is 11.1 ms median, and 120 of its
    # 123 stored beats and 13 of 13 of the charter town's carried neither a
    # ledger nor an op. The three that do merge exactly as before.
    if not (scene.get("following") or ops):
        return False
    ops = _canonical_following_ops(
        ops, getattr(ctx, "cast", None) or (), player_name,
        getattr(getattr(ctx, "turn", None), "idx", None), scene=scene)
    if ops:
        state_diff["following_ops"] = ops
    # What each follower declared LAST this beat: a start taken back in the
    # same beat is no follow declared.
    declared_now = {who for who, op in _last_follow_ops(ops).items() if op == "start"}
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
    route_scene = route_scene_for(ctx, scene, state_diff)

    # Player agency floor: if the Director omitted follow_op:stop but resolved
    # the player's declared movement somewhere other than the followed target,
    # the physical contradiction itself ends following. NPC autonomy is NOT
    # inferred from resolver positions; NPCs own it through their follow_op.
    # HER OWN DECLARED PLACE WINS, a follow declared in the same breath
    # included (D1 with review F2, 2026-10-09): a walk to a place she named,
    # and every act she did at its end, stand where she put them when the
    # one she follows goes somewhere else. Stored firings: scratch story 166
    # idx 6 (turn 4591), the player reaching the chapel while the pilot she
    # had followed since idx 3 was still on the rope bridge; and idx 22
    # (turn 4607, F101), where the landing built that beat, counted as held
    # (`director._final_movement`), ends both walks on one landing, so the
    # floor no longer fires there.
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
            ctx.add_warning(
                f"Follow: {p_follow_key}'s own walk ends in {player_dest!r} and "
                f"{target} went to {target_dest!r}; the place declared stands, "
                "and the follow ends.")

    def _carried(raw_follower, record, all_positions):
        """`(follower, target, origin, destination)` when this beat's carry
        would take the follower along, else None."""
        follower = _ci_mapping_key(all_positions, raw_follower)
        target = _ci_mapping_key(all_positions, (record or {}).get("target"))
        if follower is None or target is None:
            return None
        origin = room_of(scene, follower)
        target_origin = room_of(scene, target)
        target_dest = positions.get(target)
        if not origin or origin != target_origin or not target_dest \
                or target_dest == target_origin or target.casefold() in rapid:
            return None
        return follower, target, origin, target_dest

    # WHO STAYS SET DOWN, decided before anybody is carried: a fellow
    # follower travels only if she does, so a rider on her lap stays with
    # her when her own beat sets her down on a bench (review round 4,
    # 2026-10-05). Starts from everybody travelling and only ever adds a
    # hold, so it settles within one pass a follower.
    _set_down = set()
    for _ in range(max(1, len(following))):
        grew = False
        _all = {**(scene.get("positions") or {}), **positions}
        for raw_follower, record in following.items():
            got = _carried(raw_follower, record, _all)
            if got is None or got[0] in _set_down or positions.get(got[0]):
                continue
            follower, target, origin, target_dest = got
            fellows = [f for f, rec in following.items()
                       if f != raw_follower and isinstance(rec, dict)
                       and str(rec.get("target") or "").casefold() == str(target).casefold()
                       and (_ci_mapping_key(_all, f) or f) not in _set_down]
            if _set_down_where_they_are(route_scene, state_diff, follower, origin,
                                        target, target_dest, travelling=fellows):
                _set_down.add(follower)
                grew = True
        if not grew:
            break

    # AND A MIND KEEPS UP ONLY WITH WHAT IT PERCEIVES (review N1,
    # 2026-10-09): one it saw beside it when the beat began it sees go, and
    # goes with; one it could not see is followed only where the last sound
    # it made that reached the follower came from the room it went to
    # (`_perceived_room`). Lost in the dark to a body that slipped away
    # without a sound, the follower stays where it is, the relation stands,
    # and the beat says so. A figure's carry is the world's, as it was.
    # Measured before it landed: on every stored beat where a mind stood
    # beside the one it followed and that one changed room -- 31 in the play
    # db, 26 in the owner's -- the follower saw them when the beat began, so
    # it refuses none of them.
    _tracked = {}

    def _keeps_track(follower, target, target_dest):
        key = (str(follower).casefold(), str(target).casefold())
        if key not in _tracked:
            is_mind, senses = _mind_senses(ctx, follower, player_name)
            _tracked[key] = (not is_mind) \
                or _sees_body(scene, follower, target, senses) \
                or _perceived_room(
                    ctx, scene, route_scene, follower, target, target_dest,
                    senses, state_diff=state_diff, interp=interp, out=out,
                    player_name=player_name) == target_dest
            if not _tracked[key]:
                ctx.add_warning(
                    f"Follow: {follower} lost {target}, who went from beside "
                    f"them to {target_dest!r} with nothing of it seen or "
                    "heard; nothing perceived to follow, so the relation "
                    "stands and the body stays.")
        return _tracked[key]

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
            fellows = [f for f, rec in following.items()
                       if f != raw_follower and isinstance(rec, dict)
                       and str(rec.get("target") or "").casefold() == str(target).casefold()
                       and (_ci_mapping_key(all_positions, f) or f) not in _set_down]
            # Decided first for everybody the carry can see now (`_set_down`);
            # asked again here for a follower whose target only moved in an
            # earlier pass of this loop (A follows B follows C).
            if follower in _set_down or (not positions.get(follower) and _set_down_where_they_are(
                    route_scene, state_diff, follower, origin, target, target_dest,
                    travelling=fellows)):
                _set_down.add(follower)
                # Held where they are: the near-group repair below is told,
                # so no fresh near link can carry them off after all, nor
                # drag the one who walked back to them (`held`).
                if held is not None:
                    held.add(follower)
                continue
            if origin != target_dest and not passable_route_exists(
                    route_scene, origin, target_dest, body=follower):
                continue
            if positions.get(follower) == target_dest:
                continue
            # THE PLAYER'S ROOM THIS BEAT IS HER OWN DECLARATION'S, or the
            # hold of whoever carries her: the carry never replaces a room
            # the beat already gave her (review F2, 2026-10-09). The floor
            # above has ended a follow her own walk leaves; a walk it could
            # not read as hers -- one with no movement row, one continuing
            # from an earlier beat, a carry -- is not overwritten either,
            # and `program_steps` would have written the overwrite back into
            # the step she walked in, before the one she follows had moved.
            if positions.get(follower) and positions[follower] != origin \
                    and follower.casefold() == str(player_name or "").casefold():
                continue
            if not _keeps_track(follower, target, target_dest):
                continue
            positions[follower] = target_dest
            # BESIDE THE ONE FOLLOWED: a body carried through a doorway
            # with somebody stands next to them, not on the door's cell.
            station = state_diff.setdefault("stations", {})
            entry = station.get(follower) if isinstance(
                station.get(follower), dict) else {}
            near = [n for n in (entry.get("near") or []) if n]
            if target not in near:
                near.append(target)
            entry["near"] = near
            entry.pop("cell", None)
            station[follower] = entry
            progressed = changed = True
        if not progressed:
            break

    # AN APPROACH IS NOT A FOLLOW, AND A FOLLOW BEGUN FROM ANOTHER ROOM IS AN
    # APPROACH. The relation above carries a follower only from beside the
    # target, which is right for travel together and right for a sprint that
    # leaves someone behind. It says nothing about a body that DECIDES to go
    # to somebody who is elsewhere -- and that is what a start op across
    # rooms declares. Left as a relation alone it moved nobody: a world
    # pressure "Captain Hale's approach continues toward Clara" was filed as
    # `following_ops` and ticked on fifteen beats running while the captain
    # sat two rooms away (scratch play 2026-09-14, chat 9 turns 0-15).
    # Offscreen movement on a declared intent is code's to carry (the charter
    # ruling: pure code off screen), so the follower is in the target's room
    # when the beat ends if an open route reaches it; a route that does not
    # exist, a target that is running, or a follower moved this beat by
    # something else leaves the relation standing and the body where it is.
    # The player is carried only by a follow she declared this beat: then
    # going to the one she follows is her own walk (D1). A walk of her own
    # elsewhere this beat still wins below, as anybody's does.
    #
    # AND A MIND GOES ONLY WHERE IT PERCEIVES THE ONE IT FOLLOWS (review F1,
    # 2026-10-09). The route and the room came from the objective scene, so
    # a follow toward someone out of sight and earshot walked the follower
    # straight to them -- code choosing a mind's conduct from a fact it had
    # no channel to, and teaching it where a hidden body was by putting it
    # beside them. A mind (the player, another human player, a registered
    # character) walks toward the room where it last perceived them: SAW
    # them, or HEARD A SOUND THEY MADE, this beat or the one before
    # (`_perceived_room`) -- never a channel a voice could have crossed, so a
    # silent body behind a curtain or in a dark doorway is not walked to
    # (review N1). With nothing perceived the relation stands, the body
    # stays, and the beat says so. A figure's walk is the world's, as it
    # always was. Measured before it landed: no stored beat in the play db or
    # the owner's db walks a follower this way at all, so it refuses nothing
    # measured.
    approached = set()
    for raw in ops:
        if not isinstance(raw, dict) \
                or str(raw.get("op") or "").strip().casefold() != "start":
            continue
        all_positions = dict(scene.get("positions") or {})
        all_positions.update(positions)
        follower = _ci_mapping_key(all_positions, raw.get("follower"))
        target = _ci_mapping_key(all_positions, raw.get("target"))
        if not follower or not target \
                or follower.casefold() == target.casefold():
            continue
        # One start, however many records of it the beat carries (the
        # interpret's `follow_op` and the onset's own op are two).
        if (follower.casefold(), target.casefold()) in approached:
            continue
        approached.add((follower.casefold(), target.casefold()))
        if follower.casefold() == str(player_name or "").casefold() \
                and follower.casefold() not in declared_now:
            continue
        origin = room_of(scene, follower)
        target_room = positions.get(target) or room_of(scene, target)
        if not origin or not target_room or origin == target_room:
            continue
        # A follower the relation loop above set down where they are is not
        # walked after the target by their own start op either (review,
        # 2026-10-05). Only those: a start the relation loop never decided --
        # a chain through an approach, a start refused as a cycle -- walks.
        if held is not None and follower in held:
            continue
        if positions.get(follower) and positions[follower] != origin:
            continue
        if target.casefold() in rapid:
            continue
        where_they_are = target_room
        is_mind, senses = _mind_senses(ctx, follower, player_name)
        if is_mind:
            target_room = _perceived_room(
                ctx, scene, route_scene, follower, target, positions.get(target),
                senses, state_diff=state_diff, interp=interp, out=out,
                player_name=player_name)
            if target_room is None:
                ctx.add_warning(
                    f"Follow: {follower} started following {target} from "
                    f"{origin!r} with nothing of them seen or heard there; "
                    "nothing perceived to follow, so the relation stands and "
                    "the body stays.")
                continue
            if target_room == origin:
                continue
        if not passable_route_exists(route_scene, origin, target_room,
                                     body=follower):
            ctx.add_warning(
                f"{follower} started following {target} from {origin!r}, "
                f"but no open route reaches {target_room!r}; the relation "
                "stands and the body stays.")
            continue
        # OVER THE CELLS, AS FAR AS THE PACES CARRY (`spatial_walk.walk`):
        # the follower is beside the target when the budget reaches them,
        # else mid-way with the walk recorded as under way. Beside them only
        # in the room they are in: a walk to where they were seen last ends
        # there.
        from world.spatial import standing_cell
        landed = walk(route_scene, follower, target_room,
                      paces=paces_for(beat_seconds(ctx, state_diff)),
                      from_room=origin, from_cell=standing_cell(scene, follower),
                      passing=in_transit(scene, route_scene))
        if landed is None:
            continue
        positions[follower] = landed["room"]
        station = state_diff.setdefault("stations", {})
        entry = station.get(follower) if isinstance(
            station.get(follower), dict) else {}
        beside = landed["arrived"] and target_room == where_they_are
        if beside:
            near = [n for n in (entry.get("near") or []) if n]
            if target not in near:
                near.append(target)
            entry["near"] = near
            entry.pop("cell", None)
        else:
            entry["cell"] = list(landed["cell"])
            if not landed["arrived"] and isinstance(out, dict):
                _travel_record(out)["advanced"].append({
                    "subject": follower, "from": origin, "to": landed["room"],
                    "destination": target_room, "paces": landed["paces"],
                    "underway": True})
        station[follower] = entry
        changed = True
        ctx.add_warning(
            f"Approach: {follower} started following {target} from another "
            f"room and walks {landed['paces']} paces toward "
            f"{target_room!r}, "
            + ("arriving beside them." if beside
               else "arriving where they were last seen or heard."
               if landed["arrived"]
               else f"ending the beat in {landed['room']!r}.")
            + " A follow begun from elsewhere is a walk to the one followed.")

    # AND THE PLAYER WHO WENT WITH THEM WENT WHEN THEY DID. Her follow --
    # declared now or standing from an earlier beat, either way her own --
    # took her from the room she shared with the one she follows to where
    # they ended, with no walk of hers at the onset (her walk waited on
    # theirs, `follow_walk_waits`, or she declared none); her walk is theirs,
    # in the beat's chronology (`follow_through_the_steps`) and on the
    # travel record (`_walk_was_the_follow`).
    all_positions = {**(scene.get("positions") or {}), **positions}
    p_follow_key, p_follow = _following_record(
        relation_scene.get("following") or {}, player_name)
    follower = _ci_mapping_key(all_positions, p_follow_key) if p_follow else None
    target = _ci_mapping_key(all_positions, (p_follow or {}).get("target"))
    if follower and target:
        origin = room_of(scene, follower)
        target_dest = positions.get(target)
        ended = positions.get(follower) or origin
        if origin and origin == room_of(scene, target) and target_dest \
                and target_dest != origin and ended == target_dest \
                and follow_through_the_steps(
                    state_diff, scene, follower, target,
                    poses=_waiting_walk_poses(interp, scene, follower),
                    own=_own_conduct(ctx, interp, out, player_name)):
            changed = True
            ctx.add_warning(
                f"Follow: {follower} walks with {target} from {origin!r} "
                f"to {target_dest!r}, room by room as they do; the "
                "declaration was to follow, so the walk is theirs.")
            if isinstance(out, dict):
                _walk_was_the_follow(out, follower, target_dest)
    if changed:
        # `positions` may be a fresh dict when the diff carried an empty one
        # (`state_diff.get("positions") or {}`), so a carry must be attached.
        state_diff["positions"] = positions
    return changed

def _unreachable_position_writes(scene, route_scene, positions, bodies,
                                 exempt=(), declared=None):
    """Position writes with no open route from where the body actually is.

    `declared` is `{folded body: room}` for crossings the causality owner
    stated: under the prose contract every position the encoder writes is
    the prose's own statement that the body went there
    (`director_prose.declared_moves`). Such a crossing is judged as the
    declared mover's is: a shut door on the way is CONTESTED and the
    statement asserts it, a wall still refuses (`declared_walk_leg`). The
    owner's chat 126 idx 9 (round 4, 2026-09-23): "Hinami steps through the
    threshold into the treatment room" and Mirelle after her, through a
    paneled door the room designer had drawn shut; this floor refused both,
    and the narration stood them in a room the scene never put them in.

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
        if passable_route_exists(route_scene or scene, origin, dest, body=body):
            continue
        if (declared or {}).get(folded) == dest and not declared_walk_leg(
                route_scene or scene, origin, dest, body=body)[2]:
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
    # A BODY THE SCENE STANDS SOMEWHERE IS A MOVER, entity row or none. The
    # positions table is the physical ledger; a cast member whose establish
    # minted no entity record still has a room in it, and a walk of theirs
    # is theirs (scratch play 2026-09-14, chat 9 turn 5: "Captain Edmund
    # Hale" resolved to no entity, the fallback read the walk as the
    # player's, and the widow's companion was stood in the card room she
    # had refused to enter).
    for key in positions:
        if str(key).casefold() == mover_cf:
            return str(key), positions.get(key), None
    return None, None, None



#: How many rooms a declared walk may be judged over. `passable_path` draws
#: the same line for the same reason: past a dozen rooms a single-beat "walk"
#: is a teleport wearing a route.
_WALK_ROUTE_LIMIT = 12


def _open_reach(scene, from_room, limit=_WALK_ROUTE_LIMIT):
    """`({room: hops}, {room: room it was reached from})` over PASSABLE
    doorways alone -- how far a body gets on its own feet without touching
    a door. Breadth-first in sorted order, so a reroll reaches the same
    rooms the same way."""
    from collections import deque
    dist = {str(from_room): 0}
    prev = {str(from_room): None}
    neighbors = passable_neighbors(scene)
    queue = deque([str(from_room)])
    while queue:
        cur = queue.popleft()
        if dist[cur] >= limit:
            continue
        for nxt in sorted(neighbors.get(cur, ())):
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                prev[nxt] = cur
                queue.append(nxt)
    return dist, prev


def _doors_to(scene, to_room, limit=_WALK_ROUTE_LIMIT):
    """From every room, the cheapest way onward to `to_room` counted in SHUT
    DOORS: `{room: (doors, hops, next room on that way)}`.

    A 0/1 breadth-first search backwards from the destination over
    `_ROUTE_MEMORY_BARRIERS`, with an already-passable step costing nothing
    and a shut door costing one. Ties break on hops and then on the room
    id, so the answer is a function of the scene.
    """
    from collections import deque
    route = neighbor_map(scene, _ROUTE_MEMORY_BARRIERS, directional=True)
    passable = passable_neighbors(scene)
    back = {}
    for room, onward in route.items():
        for nxt in onward:
            back.setdefault(nxt, set()).add(room)
    best = {str(to_room): (0, 0, None)}
    queue = deque([str(to_room)])
    while queue:
        cur = queue.popleft()
        doors, hops, _ = best[cur]
        if hops >= limit:
            continue
        for prev_room in sorted(back.get(cur, ())):
            step = doors + (0 if cur in (passable.get(prev_room) or ()) else 1)
            candidate = (step, hops + 1, cur)
            if prev_room not in best or candidate < best[prev_room]:
                best[prev_room] = candidate
                queue.append(prev_room)
    return best


def _door_route(scene, from_room, to_room, limit=_WALK_ROUTE_LIMIT):
    """The walk from one room to another over doorways a body could go
    through NOW OR BY OPENING THEM, as a list of rooms excluding the start.

    `_ROUTE_MEMORY_BARRIERS` is already the engine's name for exactly that
    set -- the passable barriers plus `closed_door` -- and the vocabulary has
    already ruled on its edges: `normalize_barrier` folds locked, jammed and
    padlocked onto `closed_door` (a state of a door), and sealed, bolted,
    welded and bricked onto `wall` (a kind of wall). So this walks doors and
    refuses walls without a second table of its own.

    A BODY'S PATH IS MADE OF DOORWAYS IT MAY CROSS, so the route chosen is
    the LEAST OBSTRUCTED one and not the shortest: fewest shut doors first,
    then the one that carries the body FURTHEST on open doorways before the
    first shut one -- the engine's own "she still got as far as the hall"
    rule, which is what `declared_walk_leg` then reports -- then fewest
    hops, then the room ids, so a reroll reproduces the diff.

    Hop count alone chose a route THROUGH the obstacle the story was about.
    Live, the masque (2026-09-05, PX11): a declared walk from the reception
    room to the servants' passage had two two-hop routes, one through the
    music room's panelled door and one through the locked governor's study
    -- the room the whole plot turned on, which had refused the player two
    beats earlier. The tie broke on the room id, the study won, and the
    arrival was committed with a note saying the walk passed a closed door
    into it. The obstacle held when it was pushed on and was walked through
    when it was not.
    """
    if not from_room or not to_room or from_room == to_room:
        return []
    from_room, to_room = str(from_room), str(to_room)
    open_dist, open_prev = _open_reach(scene, from_room, limit)
    if to_room in open_dist:
        return _walk_back(open_prev, to_room)
    onward = _doors_to(scene, to_room, limit)
    passable = passable_neighbors(scene)
    route = neighbor_map(scene, _ROUTE_MEMORY_BARRIERS, directional=True)
    best = None
    for room, prefix in sorted(open_dist.items()):
        for step in sorted(route.get(room, ())):
            if step in (passable.get(room) or ()) or step not in onward:
                continue                    # not a shut door, or leads nowhere
            doors, hops, _ = onward[step]
            key = (doors + 1, -prefix, prefix + 1 + hops, room, step)
            if best is None or key < best:
                best = key
    if best is None:
        return []
    _, _, _, room, step = best
    path = _walk_back(open_prev, room) + [step]
    cur = step
    while cur != to_room:
        cur = onward[cur][2]
        if cur is None:
            return []
        path.append(cur)
    return path


def _walk_back(prev, room) -> list:
    """The rooms from a breadth-first parent map back to its start, in
    walking order and excluding the start."""
    out = []
    while prev.get(room) is not None:
        out.append(room)
        room = prev[room]
    return list(reversed(out))


def declared_walk_leg(scene, from_room, to_room, body=None):
    """How far a declared walk gets on its own feet, and which door stopped it.

    Returns `(reached, door_to, blocked)`:

    * `reached` -- the last room open doorways alone carry the body to. It is
      `to_room` when the whole route is already open, `from_room` when the
      very first edge is shut, and a room in between otherwise.
    * `door_to` -- the room on the FAR SIDE of the first shut door, or None
      when nothing shut stands on the route.
    * `blocked` -- True when no route reaches `to_room` at all, doors
      counted. That is a wall, and a wall is not a contest.

    THE RULE THIS ANSWERS. A directly adjacent shut door has always been
    CONTESTED here rather than blocked: crossing it takes an action, and the
    resolve owns whether the action succeeded. A shut door two rooms along
    was BLOCKED, and the objection recorded in the backstop was that the
    engine "cannot attribute the contest to one specific door on a multi-hop
    path". This attributes it: the walk is followed edge by edge, and the
    first edge it cannot cross names the door, so the contest has a location
    and the body has somewhere to stop.

    Measured, the flat run of 2026-09-05 (PE2): FOUR of six declared
    inter-room moves in an ordinary flat never committed, every one of them
    because a single interior door on a two-hop path was shut, while the
    identical one-hop crossing would have been allowed. The host had to move
    a body by hand three times for the story to continue.

    WHICH route is `_door_route`'s answer and not this one's, and it is the
    least obstructed one rather than the shortest -- an arrival is not a
    warrant for the route to it (PX11).

    Two rooms of the answer are deliberately separate. How FAR she got is a
    question about the floor plan and is answered here. What happens at the
    door that stopped her is a question about causality and is not: the
    caller hands that to the resolve exactly as the adjacent branch already
    does.
    """
    if not from_room or not to_room or from_room == to_room:
        return (from_room, None, False)
    if passable_route_exists(scene, from_room, to_room, body=body):
        return (to_room, None, False)
    route = _door_route(scene, from_room, to_room)
    if not route:
        return (from_room, None, True)
    passable = passable_neighbors(scene)
    reached = str(from_room)
    for step in route:
        if step not in (passable.get(reached) or ()):
            return (reached, step, False)
        reached = step
    # Unreachable in practice: a fully passable route would have been caught
    # above. Reported as no contest rather than asserting one that is not there.
    return (reached, None, False)


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


def beat_seconds(ctx, sd) -> float:
    """How long this beat is, for a walk's budget: the span the merged diff's
    `time` block asserts (the spatial hand's channel, read the one way the
    clock reads it -- `read_time_diff`, from where the clock stands), else
    the clock's own silent beat, `UNCLAIMED_BEAT_SECONDS`."""
    time_diff = sd.get("time") if isinstance(sd, dict) else None
    if time_diff_claims(time_diff):
        try:
            from story.scene import simulation_clock
            clock = simulation_clock(ctx.chat["id"]) or {}
            was = float(clock.get("elapsed_seconds") or 0.0)
            end = read_time_diff(was, time_diff)[0]
            span = float(end) - was
            if span > 0:
                return span
        except Exception:
            pass
    return float(UNCLAIMED_BEAT_SECONDS)


def _travel_record(out):
    """`out["travel"]` with every list present -- the validated output
    already carries an empty dict under the key."""
    record = out.get("travel")
    if not isinstance(record, dict):
        record = out["travel"] = {}
    for key in ("advanced", "arrived", "interrupted", "held"):
        if not isinstance(record.get(key), list):
            record[key] = []
    return record


def in_transit(scene, route_scene):
    """The bodies this beat carries from one room to another: in a room as
    the beat began, and in a different one in the scene as the beat's diff
    leaves it. A walk passes them rather than meeting them where they end
    (`spatial_walk.walk`'s `passing`), because a route scene has no clock
    inside the beat -- only its end. A body minted this beat had no room to
    leave and is not among them."""
    before = (scene or {}).get("positions") or {}
    after = (route_scene or {}).get("positions") or {}
    return frozenset(
        str(name) for name, room in after.items()
        if before.get(name) is not None and str(before.get(name)) != str(room))


def walk_declared(ctx, scene, route_scene, sd, out, subject, mv, prev_room,
                  interp=None):
    """Land a declared walk whose route is open: as far as the beat's paces
    carry the body over the cells, through the doorways on the way.

    A body ARRIVES when the budget reaches the destination -- the cell the
    declaration names (`to_cell`), the cell inside the anchor it names
    (`to_anchor`), or one pace inside the door it came through -- and is
    otherwise left where the paces ran out, in whichever room that is, with
    the walk recorded as under way so silence carries it on next beat
    (`_travel_continues`). Where the grid cannot answer (no room, no
    route), the room-granular rule stands: the body is in the destination.
    """
    pace = str(mv.get("pace") or "").strip().casefold()
    if not pace and _declares_rapid_movement(interp):
        pace = "run"
    # THE HAND'S STATION IS THE WALK'S DESTINATION. The spatial hand writes
    # where the mover stops (`stations[mover].at`) with the same beat's
    # ledger in front of it; a declaration that names no feature walks to
    # that fixture rather than to one pace inside the door (Skerry Light
    # turn 1: the hand said "at the shed", the walk ended inside the door).
    if not mv.get("to_anchor") and mv.get("to_cell") is None:
        _st = (sd.get("stations") or {}).get(subject)
        if isinstance(_st, dict) and str(_st.get("at") or "").strip() \
                and _st.get("cell") is None:
            mv = {**mv, "to_anchor": str(_st["at"]).strip()}
        elif isinstance(_st, dict) and _st.get("near") and _st.get("cell") is None:
            # A BODY NAMED IS A DESTINATION TOO, as it is for a walk within
            # a room (`walk_within_room`): the hand said who the mover came
            # to, and beside them is where it stops. The opera test story,
            # 2026-09-26: "sets the proof on the music rest in front of her"
            # ended one pace inside the stage door, 4.5 paces from her, and
            # the stage's ring smeared everything she said to him.
            beside = beside_named(route_scene, mv["to_room"], _st["near"], subject)
            if beside is not None:
                mv = {**mv, "to_cell": list(beside)}
    paces = paces_for(beat_seconds(ctx, sd), pace)
    passing = in_transit(scene, route_scene)
    # FROM WHERE THE BEAT BEGAN. `route_scene` carries this beat's diff, and
    # the diff already holds the declared destination as the body's room
    # (asserted movement enters the preview world at interpret), so the
    # walk starts from the body's room and cell in the scene as it stood.
    from world.spatial import standing_cell
    result = walk(route_scene, subject, mv["to_room"],
                  to_cell=mv.get("to_cell"), to_anchor=mv.get("to_anchor"),
                  paces=paces, from_room=prev_room,
                  from_cell=(standing_cell(scene, subject)
                             if room_of(scene, subject) else None),
                  passing=passing)
    if result is None:
        sd["positions"][subject] = mv["to_room"]
        return None
    sd["positions"][subject] = result["room"]
    station = sd.setdefault("stations", {})
    entry = station.get(subject) if isinstance(station.get(subject), dict) else {}
    entry["cell"] = list(result["cell"])
    station[subject] = entry
    # EVERY WALK IS ON THE RECORD, arrived or not: the beat's footfalls are
    # read off it (`perception._beat_movers`), and only an under-way leg
    # becomes an approach at commit.
    _travel_record(out)["advanced"].append({
        "subject": subject, "from": prev_room, "to": result["room"],
        "destination": mv["to_room"], "to_anchor": mv.get("to_anchor"),
        "to_cell": mv.get("to_cell"), "paces": result["paces"],
        "pace": pace or "walk",
        "underway": not result["arrived"]})
    if result["arrived"] and subject not in _travel_record(out)["arrived"]:
        _travel_record(out)["arrived"].append(subject)
    if not result["arrived"]:
        # A POSE WRITTEN FOR THE ARRIVAL DOES NOT SURVIVE A WALK THAT FELL
        # SHORT. The hands wrote the body at its destination; the walk ended
        # it on the way, and a pose of "standing at the top of the steps
        # looking out over the fair" beside a position at the foot of them
        # is the two-representations disagreement the page then repeats
        # (Coldharbour Fair turn 5, 2026-09-15). The station keeps its cell
        # only; the pose goes, and the beat says so.
        _poses = sd.setdefault("poses", {}) if isinstance(sd.get("poses", {}), dict) else {}
        if subject in _poses:
            ctx.add_warning(
                f"Dropped the pose written for {subject} at {mv['to_room']!r}: "
                "the walk ended short of it, so the body is on its way, not there.")
        _poses[subject] = _on_the_way_pose()
        entry.pop("at", None)
        entry["near"] = []
        ctx.add_warning(
            f"Walk under way: {subject} covers {result['paces']} paces toward "
            f"{mv['to_room']!r} and ends the beat in {result['room']!r} at "
            f"cell {list(result['cell'])}; silence carries the walk on.")
    if result.get("blocked"):
        ctx.add_warning(
            f"Walk stopped: {subject}'s way toward {mv['to_room']!r} is held "
            f"at {result['room']!r} cell {list(result['cell'])}"
            + (" -- a body stands in the doorway." if result.get("held_by") == "doorway"
               else " -- nothing walkable leads on."))
    # EVERYONE WALKING WITH THEM WALKS. A companion the beat sent to the
    # same destination out of the walker's own room walks the same cells
    # at the same pace from where they stood, and ends where their paces
    # end -- beside the walker, or short of the door if they were further
    # from it -- instead of arriving by fiat while the walker is still on
    # the way.
    for other, room in list(sd.get("positions", {}).items()):
        if other == subject or str(room) != str(mv["to_room"]):
            continue
        if room_of(scene, other) != prev_room:
            continue
        # A THING DOES NOT WALK. A lantern the walker carries is moved by
        # the hands' positions and rides the merge; only a body walks the
        # cells beside them (Hollin Mill turn 12, 2026-09-15: `ada_lantern`
        # walked thirteen paces as a companion).
        _ent = (scene.get("entities") or {}).get(other)
        if isinstance(_ent, dict) and str(_ent.get("kind") or "").strip().casefold() != "person":
            continue
        landed = walk(route_scene, other, mv["to_room"],
                      to_cell=mv.get("to_cell"), to_anchor=mv.get("to_anchor"),
                      paces=paces, from_room=prev_room,
                      from_cell=standing_cell(scene, other), passing=passing)
        if landed is None:
            continue
        sd["positions"][other] = landed["room"]
        entry = station.get(other) if isinstance(station.get(other), dict) else {}
        entry["cell"] = list(landed["cell"])
        station[other] = entry
        _travel_record(out)["advanced"].append({
            "subject": other, "from": prev_room, "to": landed["room"],
            "destination": mv["to_room"], "to_anchor": mv.get("to_anchor"),
            "to_cell": mv.get("to_cell"), "paces": landed["paces"],
            "pace": pace or "walk",
            "underway": not landed["arrived"]})
        if landed["arrived"] and other not in _travel_record(out)["arrived"]:
            _travel_record(out)["arrived"].append(other)
        if not landed["arrived"]:
            ctx.add_warning(
                f"Walk under way: {other} walks with {subject}, "
                f"{landed['paces']} paces toward {mv['to_room']!r}, and ends "
                f"the beat in {landed['room']!r}.")
    return result


def _on_the_way_pose():
    """The pose of a body whose walk is under way: standing, nothing more.
    Engine-authored so the beat-old pose ("standing in clear view of the
    boy") cannot outlive the walk that carried the body away from it
    (Coldharbour Fair turn 5, 2026-09-15)."""
    return {"posture": "standing", "support": "", "relative_to": "",
            "relation": "", "constraint": "", "detail": ""}


def walk_within_room(ctx, scene, sd, out, *, exclude=()):
    """A station the hands moved WITHIN a room is walked too. A body the
    beat re-stations across its room -- to a fixture, beside another body,
    onto a cell -- covers the paces at the beat's pace like any walk, and
    where the budget runs short it ends the beat where the paces did, with
    the leg under way (Coldharbour Fair turn 2, 2026-09-15: "step round to
    where I can see him" re-stationed the clerk nine paces across a square
    to arm's reach of the boy, in a beat, with no walk).

    Only for a body whose room did not change (the room walk already
    covered the others, `exclude`), whose cell the scene knows, and whose
    new station the grid can place. Never for a body the beat named as
    carried or that has no measured station: the fail-open answer is the
    station as written."""
    stations = sd.get("stations") if isinstance(sd.get("stations"), dict) else {}
    if not stations:
        return
    positions = sd.get("positions") if isinstance(sd.get("positions"), dict) else {}
    paces = paces_for(beat_seconds(ctx, sd))
    for subject, station in list(stations.items()):
        if subject in exclude or not isinstance(station, dict):
            continue
        room = room_of(scene, subject)
        if not room or (positions.get(subject) and str(positions[subject]) != str(room)):
            continue
        here = body_cell(scene, subject)
        if here is None:
            continue
        # The fixture named outranks a pinned cell, and a body named
        # outranks both: a station's `cell` is often the body's OLD cell
        # echoed beside a new `at`, and the new `at` is what moved.
        goal = None
        if str(station.get("at") or "").strip():
            goal = anchor_stand_cell(scene, room, str(station["at"]).strip(), near=here)
        if goal is None and station.get("near"):
            goal = beside_named(scene, room, station["near"], subject)
        if goal is None and station.get("cell") is not None:
            try:
                goal = room_grid(scene, room).nearest((int(station["cell"][0]), int(station["cell"][1])))
            except (TypeError, ValueError, IndexError):
                goal = None
        if goal is None or tuple(goal) == tuple(here):
            continue
        landed = walk(scene, subject, room, to_cell=list(goal), paces=paces,
                      from_room=room, from_cell=here)
        if landed is None or landed.get("arrived"):
            continue
        # SHORT OF IT: the body stands where the paces ran out, the station
        # it was written keeps only what the cell can honour, and the leg
        # carries on next beat.
        station["cell"] = list(landed["cell"])
        station.pop("at", None)
        station["near"] = []
        stations[subject] = station
        if isinstance(sd.get("poses", {}), dict):
            sd.setdefault("poses", {})[subject] = _on_the_way_pose()
        _travel_record(out)["advanced"].append({
            "subject": subject, "from": room, "to": room, "destination": room,
            "to_cell": [int(goal[0]), int(goal[1])], "paces": landed["paces"],
            "pace": "walk", "underway": True})
        ctx.add_warning(
            f"Walk under way: {subject} covers {landed['paces']} paces across "
            f"{room!r} toward cell {list(goal)} and ends the beat at "
            f"{list(landed['cell'])}; silence carries the walk on.")


def _travel_in_flight_view(sc, interp, p_name):
    """What the Director is told about walks already under way.

    The engine works out the leg BEFORE the prose is written, not after.
    Computing it afterwards would move bodies the resolve had just described
    standing still -- the scenery has to change ON the page, in the same
    breath as everything else the beat does, or the position and the story
    are two accounts of one turn again.

    So this is a fact with an out: here is where they are going, here is the
    room this beat puts them in, narrate it -- unless the beat itself stops
    them, which the decision model then reads off the passage, one question
    per walker (`director_prose.walks_in_flight`), and they stay put.
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

      * THE PASSAGE SAYS SO. "Did what just happened stop you walking" is
        objective causality, nuanced beyond anything worth enumerating here,
        and the resolve's account is the one text that holds the whole beat
        -- the declaration, every character's act, the dice and the room.
        The Director writes that account and the decision model is asked, per
        walker, whether it stops them (`director_prose.select_channels`,
        `record["stopped"]` on the prose contract's `jev`): a model reading
        the passage, never a string match against it. This was the causal
        Director's own field, `travel_interrupted`, which nothing wrote once
        the Director wrote prose (UNBUILT_PIPELINE §1.1).
      * A DETERMINISTIC FLOOR the Director cannot argue with: no passable
        route left, being carried, restrained, or already there.

    Records what it did on `out['travel']`; `commit.py` reads that to retire
    or keep each standing record, so the ledger and the position can never
    disagree about whether somebody is still under way.
    """
    pending = _pending_legs(sc)
    if not pending:
        return
    declared = _declared_movers(interp, p_name)

    jev = (((out.get("orchestration") or {}).get("prose_contract") or {})
           .get("jev") or {})
    weights = jev.get("walks") if isinstance(jev.get("walks"), dict) else {}
    stopped = {
        str(subject).strip().casefold(): (
            "the passage stops them (decision model %.2f)"
            % float(weights.get(subject) or 0.0))
        for subject in (jev.get("stopped") or []) if str(subject).strip()
    }

    route_scene = route_scene_for(ctx, sc, sd)
    rooms = route_scene.get("rooms") or {}
    record = {"advanced": [], "arrived": [], "interrupted": [], "held": []}

    # RESTRAINT IS JUDGED HERE, not left to a floor that runs later. A later
    # floor would pop the position and leave this record saying the walker
    # advanced or arrived, and the commit retires an arrived walk -- so a
    # body tied to a chair would lose its errand for walking there. And the
    # floor this relied on, `_reconcile_resolution`'s restraint block, never
    # ran on a prose beat at all (UNBUILT_PIPELINE §1.1). The same per-record
    # judgement the block makes (`_restraint_blocked_moves`): a standing
    # binding always, a live hold while its holder is here and awake.
    from story.scene import (apply_awareness_diff, apply_restraint_records_diff,
                             awareness_map, restraint_conditions)
    from .director_floors import _restraint_blocked_moves, _restraint_holder_pool
    chat = getattr(ctx, "chat", None)
    chat_id = chat["id"] if isinstance(chat, dict) else getattr(chat, "id", None)
    restraints = (apply_restraint_records_diff(restraint_conditions(chat_id), sd)
                  if chat_id is not None else [])
    if restraints:
        amap = apply_awareness_diff(awareness_map(chat_id), sd)
        holders = _restraint_holder_pool(sc, [
            character_name_from_text(row["sheet"]) for row in (ctx.cast or [])] + [p_name])

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
                {"subject": subject, "reason": reason, "source": "decision"})
            continue
        # Being carried is somebody else's doing; their walk resumes when
        # they are put down, and until then their position is not theirs.
        if (route_scene.get("contained") or {}).get(subject):
            record["held"].append({"subject": subject, "reason": "carried"})
            continue
        if restraints and _restraint_blocked_moves(
                {"positions": {subject: destination}}, sc, restraints, amap, holders):
            record["held"].append({"subject": subject, "reason": "restrained"})
            continue
        step = passable_route_next_step(route_scene, here, destination)
        if not step:
            record["held"].append(
                {"subject": subject, "reason": "no passable route"})
            continue
        # A long edge is not crossed in a breath. Counted on the standing
        # record so the beats already spent on this leg survive a reroll.
        # The body walks to the doorway meanwhile and waits there.
        distance = normalize_edge_distance(
            _edge_to(rooms, here, step).get("distance"))
        spent = int(leg.get("edge_beats") or 0) + 1
        paces = paces_for(beat_seconds(ctx, sd))
        if _still_crossing(distance, spent):
            at_door = door_cell(route_scene, here, step)
            if at_door is not None:
                waited = walk(route_scene, subject, here, to_cell=list(at_door),
                              paces=paces)
                if waited is not None:
                    sd.setdefault("stations", {}).setdefault(subject, {})[
                        "cell"] = list(waited["cell"])
            record["held"].append(
                {"subject": subject, "reason": "still crossing",
                 "edge_beats": spent})
            continue
        # OVER THE CELLS, AS FAR AS THE PACES CARRY. The walk goes to the
        # destination's cell or anchor when the record names one, else one
        # pace inside the door it comes through; a budget that runs out
        # leaves the body mid-way, in whichever room that is.
        landed = walk(route_scene, subject, destination,
                      to_cell=leg.get("to_cell"), to_anchor=leg.get("to_anchor"),
                      paces=paces)
        if landed is None:
            record["held"].append(
                {"subject": subject, "reason": "no passable route"})
            continue
        sd.setdefault("positions", {})[subject] = landed["room"]
        sd.setdefault("stations", {}).setdefault(subject, {})[
            "cell"] = list(landed["cell"])
        if not landed["arrived"] and isinstance(sd.get("poses", {}), dict):
            sd.setdefault("poses", {})[subject] = _on_the_way_pose()
        # THE WALK KEEPS ITS END. The feature or cell the declaration
        # named rides every continued leg's record, so the commit's
        # approach still says where in the room the walk ends and the last
        # leg lands there rather than one pace inside the opening (Skerry
        # Light turn 12, 2026-09-15: `to_anchor: path_track` was dropped on
        # the second leg and the keeper arrived at the yard wall's gap).
        record["advanced"].append({"subject": subject, "from": here,
                                   "to": landed["room"],
                                   "destination": destination,
                                   **({"to_anchor": leg.get("to_anchor")}
                                      if leg.get("to_anchor") else {}),
                                   **({"to_cell": leg.get("to_cell")}
                                      if leg.get("to_cell") is not None else {}),
                                   "paces": landed["paces"],
                                   "underway": not landed["arrived"]})
        if landed["arrived"]:
            record["arrived"].append(subject)
        ctx.add_warning(
            f"Travel continues: {subject} declared a walk to "
            f"{destination!r} and this beat did not stop it, so they walk "
            f"{landed['paces']} paces, {here!r} -> {landed['room']!r}"
            + (" and arrive." if landed["arrived"] else
               f", cell {list(landed['cell'])}.")
            + " Silence continues a declared walk; an interruption is the "
            "Director's to assert.")

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
    # A heading that crosses an intermediate room is an ARRIVAL in that room.
    # `arrives=false` says the body did not reach `to_room`, not that it did
    # not move: a walker who leaves the radio room for the shed is in the
    # gallery between, and refusing the leg left the body in the room its own
    # beat had walked it out of, narrated from the next one (chat 116, beat
    # 3, 2026-09-04). The leg is accepted when the placed room is a passable
    # step from where the body was and is not the destination; reaching the
    # destination itself is still refused -- reaching a building is not
    # entering it.
    if now != str(mv.get("to_room") or ""):
        from world.spatial import passable_neighbors
        if now in (passable_neighbors(sc).get(was) or ()):
            ctx.warnings.append(
                f"Approach leg: {subject} walked {was!r} -> {now!r} on the way "
                f"to '{mv.get('to_room')}' and is not there yet.")
            return
    sd["positions"].pop(subject, None)
    ctx.warnings.append(
        f"Approach is not arrival: {subject}'s declared movement to "
        f"'{mv.get('to_room')}' is marked arrives=false, but the beat placed "
        f"them in '{now}'{f' (from {was!r})' if was else ''}. Position "
        "unchanged -- moving closer to somewhere is not being there, and "
        "reaching a building is not entering it."
    )


def crossing_legs(scene, from_room, to_room):
    """The rooms a body is in while it crosses from one room to another.

    THE RULE THIS SERVES: a body that crosses rooms performs one act per room
    it is in, and an observer is entitled to the legs that happened where
    their channel stood. The engine already emits one CROSSING per boundary
    (`composer.crossing_percept`); what it lacked was the other half -- that
    the beat's single observable surface belongs to every room the body was
    in, not to the room the walk started in.

    Live, "The Lamp at Sorrow Point" turn 16 (PA1). Wren left the watch room
    and walked down three rooms; Ivo, who stayed behind, received on the SIGHT
    channel "descends the spiral stair, passing through the store below and
    stepping into the kitchen", cited it as present evidence, and it became
    rows 69 and 77 of his `memories`. The stair is dark and the last hop is
    through a door. Nothing was wrong with `act_percept`, which graded one
    surface against one relation exactly as asked: the surface described three
    rooms and the relation knew about one.

    ONE BOUNDARY IS NOT THE CLASS. Where a body crosses a single doorway,
    every observer of either side stood in a room the body was in this beat,
    and the two rooms are the two ends of a doorway they can both see -- which
    is the engine's own standing convention, written into the arrival and
    departure bands in `composer`: a crossing BOUNDS the beat for that body.
    Past one boundary that stops being true: there are rooms in the middle
    that neither end has a channel to, and one surface covers all of them.

    Returns the ordered rooms, first to last. `()` when neither room is
    known; a one-room tuple when nothing crossed. Where the outcome scene can
    show no walkable route (carried, a lift, a door shut behind them) the
    rooms between are real and unnameable, and an empty string stands in for
    them so no observer is credited with a channel to a room the engine
    cannot name.
    """
    from_room = str(from_room or "").strip()
    to_room = str(to_room or "").strip()
    if not from_room or not to_room:
        return tuple(room for room in (from_room, to_room) if room)
    if from_room == to_room:
        return (from_room,)
    # Direct adjacency is one boundary WHATEVER the barrier: a door opened,
    # crossed and shut in one beat leaves no passable route behind it, and
    # that walk is still one step through one doorway.
    if str(spatial_rel(scene, from_room, to_room).get("barrier")
           or "") != "separated":
        return (from_room, to_room)
    legs = [from_room]
    here = from_room
    # One step per room in the map is the loop's own ceiling: a shortest walk
    # cannot revisit a room, so it cannot be longer than the graph.
    for _ in range(len(scene.get("rooms") or {}) + 1):
        step = passable_route_next_step(scene, here, to_room)
        if not step:
            break
        legs.append(step)
        here = step
        if here == to_room:
            return tuple(legs)
    return (from_room, "", to_room)
