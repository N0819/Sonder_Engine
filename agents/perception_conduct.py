"""Readers of this beat's declared conduct: rapid movement and the open-group
continuity rescue, where a line was said relative to a declared walk, a
crossing's legs and the channel to every leg, the beat's movers and gaits, a
walk left underway, and an act's own looks, sweeps and handled things.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import json
import re
from story.character_schema import character_name_from_text
from core.db import q
from world.spatial import (
    normalize_barrier,
    room_of,
    scene_room_id,
    same_subject,
    spatial_rel,
)

from agents.perception_common import _ling
from agents.perception_senses import _sight_reaches


def _declares_rapid_movement(value):
    """Whether one structured declaration says the actor moves rapidly.

    The verb table is the ACTIVE PACK's (`agents.perception._RAPID_MOVEMENT_VERBS`),
    not seven English words: a Japanese story declaring 走る got no match, so
    the continuity rescue this gates stayed open on exactly the beats it exists
    to close. Matched against the declared verb and the leading word of the
    observable only -- never against free prose -- which is why each pack can
    anchor its own pattern (English `^...s?$`, Japanese unanchored stems)
    without widening what is tested.
    """
    pattern = _ling("_RAPID_MOVEMENT_VERBS")
    sequence = value if isinstance(value, list) else (value or {}).get("sequence")
    for event in sequence or []:
        if not isinstance(event, dict) or event.get("type") != "action":
            continue
        verb = str(event.get("verb") or "").strip().casefold()
        words = str(
            event.get("attempt") or event.get("observable") or ""
        ).strip().casefold().split()
        if (verb and pattern.search(verb)) or (
            words and pattern.search(words[0])
        ):
            return True
    return False


def _open_route_within(scene, start_room, end_room, max_hops=2):
    """True only across a short route of fully open air/doorway edges."""
    if not start_room or not end_room or start_room == end_room:
        return False
    neighbors = {}
    for room_id, room in (scene.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            target = edge.get("to")
            if not target or normalize_barrier(edge.get("barrier")) not in {
                "open", "open_door",
            }:
                continue
            neighbors.setdefault(room_id, set()).add(target)
            neighbors.setdefault(target, set()).add(room_id)

    frontier = [(start_room, 0)]
    seen = {start_room}
    while frontier:
        room_id, hops = frontier.pop(0)
        if hops >= max_hops:
            continue
        for target in neighbors.get(room_id, ()):
            if target == end_room:
                return True
            if target not in seen:
                seen.add(target)
                frontier.append((target, hops + 1))
    return False


def _ci_value(mapping, name):
    wanted = str(name or "").strip().casefold()
    for key, value in (mapping or {}).items():
        if str(key).strip().casefold() == wanted:
            return value
    return None


def _mutually_near(stations, first, second):
    first_station = _ci_value(stations, first)
    second_station = _ci_value(stations, second)
    if not isinstance(first_station, dict) or not isinstance(second_station, dict):
        return False
    first_near = {
        str(value).strip().casefold()
        for value in (first_station.get("near") or [])
    }
    second_near = {
        str(value).strip().casefold()
        for value in (second_station.get("near") or [])
    }
    return (
        str(second).strip().casefold() in first_near
        and str(first).strip().casefold() in second_near
    )


def _previous_open_group_continuity(
        ctx, scene, actor_name, observer_name, observer_id,
        actor_room, observer_room):
    """Rescue hearing from one already-corrupted pre-turn checkpoint.

    Older resolver output could put two ordinary walkers in different path
    rooms while its same state diff explicitly kept them mutually ``near``.
    Reroll restores that contradiction before the repaired resolver gets a
    chance to run, so onset hearing otherwise loses the companion's next line.

    This is evidence recovery, not following or pursuit: both bodies must have
    begun the previous beat co-located, both must have moved, the previous
    result must explicitly keep them mutually near, neither declaration may be
    rapid, neither may stop following, the restored rooms must exactly match
    the contradictory result, and only a two-hop fully-open route qualifies.
    """
    if ctx.turn.idx <= 0 or not _open_route_within(
            scene, actor_room, observer_room, max_hops=2):
        return False

    cache_key = "_previous_open_group_evidence"
    if cache_key not in ctx:
        previous = q(
            "SELECT id FROM turns WHERE chat_id=? AND idx=?",
            (ctx.chat.id, ctx.turn.idx - 1), one=True,
        )
        evidence = {"outputs": {}, "checkpoint": {}}
        if previous:
            rows = q(
                "SELECT s.key,v.content FROM steps s JOIN variants v "
                "ON v.step_id=s.id AND v.active=1 "
                "WHERE s.turn_id=? AND (s.key IN "
                "('director_interpret','interaction_loop','director_resolve') "
                "OR s.key LIKE 'character:%')",
                (previous["id"],),
            )
            for row in rows:
                try:
                    evidence["outputs"][row["key"]] = json.loads(row["content"])
                except (TypeError, ValueError):
                    continue
            checkpoint = q(
                "SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=?",
                (ctx.chat.id, ctx.turn.idx - 1), one=True,
            )
            if checkpoint:
                try:
                    evidence["checkpoint"] = json.loads(checkpoint["blob"])
                except (TypeError, ValueError):
                    pass
        ctx[cache_key] = evidence

    evidence = ctx.get(cache_key) or {}
    outputs = evidence.get("outputs") or {}
    previous_resolve = outputs.get("director_resolve") or {}
    state_diff = previous_resolve.get("state_diff") or {}
    positions = state_diff.get("positions") or {}
    stations = state_diff.get("stations") or {}
    actor_result_room = _ci_value(positions, actor_name)
    observer_result_room = _ci_value(positions, observer_name)
    if (
        actor_result_room != actor_room
        or observer_result_room != observer_room
        or not _mutually_near(stations, actor_name, observer_name)
    ):
        return False

    prior_scene = (
        ((evidence.get("checkpoint") or {}).get("world") or {}).get("scene")
        or {}
    )
    prior_positions = prior_scene.get("positions") or {}
    actor_start = _ci_value(prior_positions, actor_name)
    observer_start = _ci_value(prior_positions, observer_name)
    if (
        not actor_start
        or actor_start != observer_start
        or actor_result_room == actor_start
        or observer_result_room == observer_start
    ):
        return False

    previous_interpret = outputs.get("director_interpret") or {}
    if not isinstance(previous_interpret.get("movement"), dict):
        return False
    interaction = outputs.get("interaction_loop") or {}
    character_results = interaction.get("character_results") or {}
    observer_result = (
        character_results.get(str(observer_id))
        or character_results.get(observer_id)
        or outputs.get(f"character:{observer_id}")
        or {}
    )
    if not any(
        isinstance(event, dict) and event.get("type") == "action"
        for event in (observer_result.get("sequence") or [])
    ):
        return False
    if (
        _declares_rapid_movement(previous_interpret)
        or _declares_rapid_movement(observer_result)
    ):
        return False

    pair = {
        str(actor_name).strip().casefold(),
        str(observer_name).strip().casefold(),
    }
    for op in state_diff.get("following_ops") or []:
        if not isinstance(op, dict) or op.get("op") != "stop":
            continue
        if str(op.get("follower") or "").strip().casefold() in pair:
            return False
    follow_op = observer_result.get("follow_op") or {}
    if isinstance(follow_op, dict) and follow_op.get("op") == "stop":
        return False
    return True


def _declared_arrival_room(sc, interp, p_room):
    """The room this beat's DECLARATION says the player's own body reaches,
    when the scene holds it and it is not where the beat found them.

    "", which every caller reads as "nothing was declared", for a move of a
    vehicle rather than a body (`MovementDecl.mover`), for a declaration that
    only sets off (`arrives: false`), and for a destination no room answers
    to -- the beat cannot grade a channel to a place the world does not have.
    """
    mv = (interp or {}).get("movement")
    if not isinstance(mv, dict) or not mv.get("arrives", True):
        return ""
    if str(mv.get("mover") or "self").strip().casefold() not in ("", "self"):
        return ""
    # The destination as the WORLD spells it: a room answers to its id and
    # its name, folded (`spatial.scene_room_id`), and the resolved id is
    # what every reader below compares against (review 2026-09-07 B2).
    dest = scene_room_id(sc, str(mv.get("to_room") or "").strip())
    if not dest or dest == str(p_room or ""):
        return ""
    return dest


def _speech_room_for(sc, event, arrival_room, p_room):
    """WHERE THE SPEAKER STOOD WHEN THEY SAID IT.

    A line is heard from the room its speaker was in when they spoke, and a
    beat that carries both a walk and a line has two candidate rooms. The
    declaration's own ORDER would settle it and no field carries that order
    (`MovementDecl` has no index into `sequence`), so the beat is asked the
    one thing it does say: WHO the line was aimed at, and where the scene
    stands them.

    Live case, flat turn 20 (2026-09-05): a woman came in from the balcony,
    put a hand flat on a man's shoulder -- the contact landed, with a perfect
    reciprocal touch percept -- and the line she said with her hand on him
    reached both cast views as "A muffled voice: ...going... anything...
    tonight...", graded from the balcony through a shut glass door, and lost
    its speaker with it.

    The floor stays where it was. Only a line the beat aims at somebody the
    scene stands in the DESTINATION is graded there; everything else -- an
    unaddressed line, an addressee in the room left behind, a line before a
    declared departure -- keeps the room the beat found the speaker in.
    Widening a channel is the direction a mistake here would leak in, so it
    is taken only where the declaration itself says the speaker was there.
    """
    if not arrival_room:
        return p_room
    for target in (event or {}).get("targets") or ():
        who = str(target or "").strip()
        if who and room_of(sc, who) == arrival_room:
            return arrival_room
    return p_room


def _looked_vistas(sc, res, interp, name, player_name, ctx, senses=None):
    """The vistas `name`'s own act this beat aimed a `look` at
    (`_own_looks`)."""
    from world.vistas import looked_vistas
    return looked_vistas(sc, _own_looks(res, interp, name, player_name, ctx),
                         name=name, senses=senses)


def _own_looks(res, interp, name, player_name, ctx):
    """Every `look` `name`'s own act aimed this beat, by the looking row's
    actor: the player's rows (`persona:`/self) and each cast member's
    (`character:<id>`), read off the interpret and resolve sequences the way
    `swept_this_beat` reads a sweep. One list for both matchers -- the
    horizon's (`vistas.looked_vistas`) and the far layer's
    (`landscape.looked_far`)."""
    by_id = {}
    for row in (getattr(ctx, "cast", None) or ()):
        try:
            by_id[str(row["id"])] = character_name_from_text(row["sheet"])
        except Exception:
            continue
    looks = []
    rows = list((res or {}).get("sequence") or []) + list((interp or {}).get("sequence") or [])
    for element in rows:
        if not isinstance(element, dict) or not str(element.get("look") or "").strip():
            continue
        actor = str(element.get("actor") or element.get("source_entity_id") or "")
        if actor.startswith("persona:") or actor in ("", "self", "player"):
            who = str(player_name or "")
        elif actor.startswith("character:"):
            who = by_id.get(actor[10:]) or ""
        else:
            who = actor
        if who.strip().casefold() == str(name or "").strip().casefold():
            looks.append(element["look"])
    return looks


def _own_handled(sc, res, name):
    """Every thing this beat's transfers put into `name`'s hands: the
    resolve's `inventory_ops` whose destination is this body, carried in
    view (`relation` held, carried or unstated). Shut away -- a pocket, a
    container -- is not in the hand, and worn is attire's.
    `_things_read_by`'s HANDLED admission."""
    diff = (res or {}).get("state_diff") if isinstance(res, dict) else None
    ops = (diff or {}).get("inventory_ops") if isinstance(diff, dict) else None
    out = []
    for op in ops if isinstance(ops, list) else ():
        if not isinstance(op, dict):
            continue
        if str(op.get("relation") or "").strip().casefold() not in ("", "held", "carried"):
            continue
        thing = str(op.get("object_id") or "").strip()
        if thing and same_subject(sc, str(op.get("to_id") or ""), name):
            out.append(thing)
    return out


def _walk_underway(sc, res, name):
    """`{"to": <destination room name>, "at": <room name>}` when this
    beat's travel record left `name` short of a declared destination, else
    None. Read from the resolve's own `travel.advanced` row for this body."""
    travel = (res or {}).get("travel") if isinstance(res, dict) else None
    rooms = (sc or {}).get("rooms") or {}
    for rec in ((travel or {}).get("advanced") or []) if isinstance(travel, dict) else []:
        if not isinstance(rec, dict) or not rec.get("underway"):
            continue
        if str(rec.get("subject") or "").strip().casefold() != str(name or "").strip().casefold():
            continue
        dest, here = str(rec.get("destination") or ""), str(rec.get("to") or "")
        if not dest or dest == here:
            continue
        name_of = lambda rid: str((rooms.get(rid) or {}).get("name") or rid)
        return {"to": name_of(dest), "at": name_of(here)}
    return None


def _beat_movers(ctx, before=None, after=None, bodies=()) -> dict:
    """{name: pace} for every body the beat walked (the resolve's `travel`
    records, paces > 0): its tread is a sound source at the cell it ended
    on (`spatial_sound_field.sound_sources`). Empty before the resolve has
    run, so the onset pass hears no footfall that has not happened.

    AND EVERY BODY THE BEAT TOOK TO ANOTHER ROOM ON ITS OWN FEET, at a walk:
    `bodies` (the cast and the player) whose room in `after` is not their
    room in `before`, unless something carries them (`contained`). A walk
    need not pass the travel system -- the encoder can write a body's room
    as a `positions` patch with no `movement` -- and that walk made no sound
    anywhere: chat 177 turn 19, Mellisande climbed from the kitchen to the
    room over it and Hinami, under the timber floor, heard nothing
    (DESIGN_SOUND_FIELD § 12)."""
    cached = ctx.get("_beat_movers")
    if cached is not None:
        return cached
    movers = {}
    travel = (ctx.get("director_resolve") or {}).get("travel") or {}
    for rec in (travel.get("advanced") or []) if isinstance(travel, dict) else []:
        if not isinstance(rec, dict):
            continue
        try:
            paces = float(rec.get("paces") or 0)
        except (TypeError, ValueError):
            paces = 0.0
        subject = str(rec.get("subject") or "").strip()
        if subject and paces > 0:
            movers[subject] = str(rec.get("pace") or "walk").strip().casefold() or "walk"
    if isinstance(before, dict) and isinstance(after, dict):
        carried = after.get("contained") or {}
        for name in bodies or ():
            name = str(name or "").strip()
            if not name or name in movers or (isinstance(carried, dict)
                                               and carried.get(name)):
                continue
            was, now = room_of(before, name), room_of(after, name)
            if was and now and str(was) != str(now):
                movers[name] = "walk"
    ctx["_beat_movers"] = movers
    return movers


def _act_gait(event) -> str:
    """The gait an act declares for its own walk -- its `movement` record's
    `pace` (`MovementSpec.pace`: run, sneak) -- or "" where it declares
    none. Typed data on the act itself, so an act behind an observer is
    heard at the gait it was made at even before the beat's travel record
    exists (the onset)."""
    movement = (event or {}).get("movement") if isinstance(event, dict) else None
    if not isinstance(movement, dict):
        return ""
    return str(movement.get("pace") or "").strip().casefold()


def _crossing_legs(sc, from_room, to_room):
    """The rooms a body was in while it crossed, from the movement contract.

    Imported from the Director's own module through the facade and at call
    time: the route is the movement contract's knowledge, and perception may
    not take an import-time dependency on the stage that owns it.
    """
    try:
        from .director import crossing_legs
    except Exception:                       # pragma: no cover - import floor
        return ()
    return crossing_legs(sc, from_room, to_room)


def _multi_room_legs(sc, moves):
    """{mover: legs} for the movers who crossed MORE THAN ONE boundary.

    See `director_movement.crossing_legs` for the rule and the live case
    (PA1). One boundary is left alone: both its rooms are rooms the body was
    in with those observers in them, and they are the two ends of one
    doorway. Past one, the beat's single surface covers rooms in the middle
    that neither end has a channel to.
    """
    legs = {}
    for mover, from_room, to_room in moves or ():
        walked = _crossing_legs(sc, from_room, to_room)
        if len(walked) > 2:
            legs[str(mover)] = walked
    return legs


def _legs_of_actor(sc, legs_by_mover, actor):
    """This actor's legs, matched the way every other actor lookup matches."""
    if not legs_by_mover:
        return ()
    key = str(actor or "")
    if key in legs_by_mover:
        return legs_by_mover[key]
    for mover, legs in legs_by_mover.items():
        if same_subject(sc, mover, key):
            return legs
    return ()


def _channel_to_every_leg(sc, prev_sc, observer_name, observer_room, legs,
                          senses=None):
    """Did this observer's channel stand in EVERY room the body was in.

    An act that crosses rooms carries one surface for the whole walk, so the
    surface is admitted only where the whole walk was available. An observer
    whose channel reached some of it is not owed a shortened version of the
    sentence -- prose matching is the boundary this engine exists to stay on
    the right side of -- they are owed the legs they did have, which the
    engine already delivers as arrival and departure crossings.

    The observer's own room always counts: whether they SAW the act there is
    the act channel's question and is asked separately. An empty leg is a room
    the outcome scene cannot name (carried, a lift, a door shut behind them)
    and nobody has a channel to it.
    """
    for leg in legs or ():
        if not leg:
            return False
        seen = False
        for scene in (sc, prev_sc):
            if not scene:
                continue
            here = room_of(scene, observer_name) or observer_room
            if not here:
                continue
            if here == leg:
                seen = True
                break
            rel = spatial_rel(scene, here, leg)
            if _sight_reaches(scene, here, leg, senses, rel=rel):
                seen = True
                break
        if not seen:
            return False
    return True


# ---------------------------------------------------------------------------
# The composer path -- which is now the only path.
#
# Layer A/B live in agents/composer.py; this section is the orchestrator that
# assembles each stage's typed inputs and calls down into it. Zero model
# calls, and no view is BUILT from `resolved_event`: the Director's
# omniscient account of the beat reaches no percept, so the per-observer
# surgery that used to cut it down (redaction, surface translation) has
# nothing left to cut and went with the model path.
#
# It is read in exactly one place, and stating that precisely matters more
# than the tidier sentence: `_inverted_motion_check` compares the FINISHED
# view against the resolved event, as a tripwire. Nothing flows from the
# event into the view -- the comparison runs the other way, and its only
# output is a warning.
#
# The scrub chain does not run here as repair; the checkers run as TRIPWIRES
# (`_composer_tripwires`): a firing tripwire is a composer defect and says so
# in its warning. Audit history's lesson stands -- real leaks are guards that
# cannot fire -- so the guards are kept armed even though the composer makes
# their firing structurally impossible on every path it controls. What each
# tripwire may DO to the text differs, and is argued at that function: a
# repair that deletes entitled content is not defence in depth, it is the
# regression, and that was measured rather than supposed.
# ---------------------------------------------------------------------------

def _explicit_look_intent(interp):
    """Did the player explicitly look/examine this beat? Read from the
    Director's structured interpretation (location_query, or a declared
    action whose leading verb is a look verb), never from raw input. An
    explicit look re-renders the player's full standing state instead of the
    delta.

    The verb table is the ACTIVE PACK's (`agents.perception._LOOK_VERBS`). A
    Japanese story never re-earned a full render on an explicit look, because
    the eleven English words could not match 見回す."""
    if not isinstance(interp, dict):
        return False
    if str(interp.get("location_query") or "").strip():
        return True
    # A DECLARED LOOK FIRST (the owner, 2026-09-15): the interpret's row says
    # `look: around` when the player sweeps the room, and that field speaks
    # for a character too. The pack's look-verb table stays as the fallback
    # for a model that writes the act and omits the field.
    for event in interp.get("sequence") or []:
        if isinstance(event, dict) \
                and str(event.get("look") or "").strip().casefold() == "around":
            return True
    for event in interp.get("sequence") or []:
        if not isinstance(event, dict) or event.get("type") != "action":
            continue
        text = str(event.get("attempt") or event.get("observable") or "")
        words = text.strip().split()
        verb = str(event.get("verb") or (words[0] if words else ""))
        verb = re.sub(r"[^\w]", "", verb).strip().casefold()
        if verb and _ling("_LOOK_VERBS").search(verb):
            return True
    return False


def swept_this_beat(res, p_name, cast, interp=None):
    """The names of every body whose act this beat swept the room
    (`look: around` on the resolve's sequence): the player's and the
    cast's alike."""
    by_id = {}
    for row in cast or ():
        try:
            by_id[str(row["id"])] = character_name_from_text(row["sheet"])
        except Exception:
            continue
    swept = set()
    rows = list((res or {}).get("sequence") or [])
    rows.extend((interp or {}).get("sequence") or [])
    for element in rows:
        if not isinstance(element, dict):
            continue
        if str(element.get("look") or "").strip().casefold() != "around":
            continue
        actor = str(element.get("actor") or element.get("source_entity_id") or "")
        if actor.startswith("persona:") or actor in ("", "self", "player"):
            swept.add(str(p_name or ""))
        elif actor.startswith("character:"):
            swept.add(by_id.get(actor[10:]) or "")
        else:
            swept.add(actor)
    return {n for n in swept if n}
