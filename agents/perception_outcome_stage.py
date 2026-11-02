"""The outcome stage entry point `perception_outcome`: composes the beat scene
once, enriches the dialogue log, builds every perceiver and hands off to
`_composer_outcome`.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import copy
from story.character_schema import (
    character_appearance,
    character_identity,
    character_name,
    character_name_from_text,
    normalized_character_from_text,
    persona_appearance,
    persona_name,
)
from core.db import wget
from story.scene import (
    appearance_of,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    is_player_speaker,
    persona_of,
    senses_of,
    sheet_state,
)
from world.spatial import room_display_name, resolve_substance_ops, room_of
from .common import (
    _appearance_as_prose,
    player_room_in,
    _room_notes_for_view,
    crowds_for_room,
    artifacts_for_room,
    attending_this_room,
    chatter_for_room,
    chatter_inputs,
    couriers_for_room,
    cast_room,
    character_room,
)

from agents.perception_common import _stage_player_room
from agents.perception_bodies import (
    _subject_concealed_terms,
    _subject_disguise_context,
)
from agents.perception_senses import (
    _behind_rooms,
    _behind_sources,
    _focus_target,
    _proximity_to_sources,
    _sense_card,
    _sound_field_for,
    _source_channels,
    _visible_rooms_for,
)
from agents.perception_identity import (
    _ambient_location_for,
    _character_known_places,
    _player_known_places,
    _presence_bodies,
)
from agents.perception_stream import (
    _background_beats,
    _delivered_manifest,
    _settled_character_result,
)
from agents.perception_outcome_views import _composer_outcome


def perception_outcome(ctx, nonce):
    chat = ctx.chat
    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    res = ctx.get("director_resolve", {})
    interp = ctx.get("director_interpret", {})

    # THE SCENE THE COMMIT WILL WRITE, COMPOSED ONCE, HERE.
    #
    # This stage used to compose its own: a deep merge plus attire plus the
    # three orientation inferences, standing beside the commit's composition
    # and drifting from it three separate times. The last drift was measured
    # (review 2026-09-07 A26): the mirror never ran `_refuse_unheld_transfers`,
    # never passed `sleeping`, `carriers` or the report sinks into the merge,
    # and never settled the plan's own exits -- so the narrator, and every
    # memory episode built from this stage's views, could read a handover as
    # done that the commit was about to refuse.
    #
    # `compose_beat_scene` is that one composition (persist/commit_scene_state).
    # Its result is stashed on the context keyed by the stored scene's read
    # token and the active resolve variant, and the commit takes it back
    # rather than composing a second time -- so the beat is composed once per
    # turn instead of twice, and the two cannot disagree by construction.
    # Local import: commit.py must stay ignorant of agent modules (facade
    # rule), so the dependency points this way only (same precedent as
    # commit's own _is_player).
    from persist.commit import compose_beat_scene

    composed = compose_beat_scene(ctx)
    ctx["_composed_beat"] = composed
    # The warnings and the Director notes the composition raised are NOT
    # published here. The commit is the one side that speaks to the Director,
    # and it publishes them when it reads this composition back -- exactly as
    # the mirror discarded them before.
    # THE STAGE THAT RENDERS THE BEAT MAY NOT WRITE THE WORLD. `composed.scene`
    # is the object the commit will persist, and this stage goes on to lay
    # unregistered presence bodies onto the scene it holds (`lay_charter_bodies`
    # below, "the stage's own fresh copy, never the store") -- so it works on
    # a copy. The first A26 patch shared the object, and the skeptic's replay
    # of the descent found a charter creature's position, station and facing
    # committed as durable world state on 7 of 124 beats, with no entity row
    # to match. 3 ms a beat on the descent's widest scene, against the 50-60
    # ms the shared composition saves.
    prev_scene = copy.deepcopy(composed.prev_scene)
    diff = composed.diff
    sc = copy.deepcopy(composed.scene)
    substance_events = resolve_substance_ops(
        prev_scene, diff.get("substance_ops"))
    # The sweep marker was this pass's alone (`effective_facing` reads it);
    # the scene handed on faces as it faces.
    sc.pop("_sweeping", None)
    ctx._extra["outcome_scene"] = sc

    # Prefer re-resolving against the just-merged (post-resolution) scene
    # over reusing ctx["_player_room"]: that value was cached during the
    # action-onset pass (perception_act), before this turn's movement was
    # validated/applied by director_resolve. Reusing it unconditionally
    # would keep describing the player's pre-move surroundings after a
    # successful move, or the (rejected) destination after a blocked one.
    # Only fall back to the cached value when the scene genuinely has no
    # resolvable position for the player (e.g. positions were never
    # tracked for them).
    # The ONE ordering every stage reads (`common.player_room_in`: the scene,
    # then the cache, then the resolver that may cost a model call), and
    # with NO declaration: a declared `movement.to_room` is evidence of
    # intent before resolve and of nothing after it -- the resolver's second
    # rung returned it directly, so a positionless player was placed at the
    # destination resolve had just refused.
    p_name = pers.get("name") or persona_name(pers)
    p_room = player_room_in(sc, ctx, pers=pers, player_name=p_name)
    p_appearance_true = _appearance_as_prose(appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc))
    # Conceal a disguised subject's real appearance in every observer's outcome
    # view: p_appearance becomes the disguised (visible) form, so no percept
    # built below can carry a concealed feature. The knowledge layer is
    # `known_to` alone -- see `_subject_disguise_context`, which also records
    # what went missing when its prose payload did.
    (p_appearance, p_disguise, p_disguise_known,
     p_disguise_conceals) = _subject_disguise_context(
        ctx, p_name, p_appearance_true, known)
    p_disguise_terms = _subject_concealed_terms(ctx, p_name)

    # background_react (agents/background.py) is a separate, later stage
    # in the plan -- its output is merged in HERE rather than by mutating
    # res["dialogue_log"] in place, because director_resolve's own step/
    # variant was already persisted before background_react ran; mutating
    # the shared dict afterward would desync the persisted director_resolve
    # step from what perception/narrator actually rendered, and a rerun
    # from this step onward would silently lose the background reaction.
    _bg_beats = _background_beats(ctx, sc)
    _bg_rooms = {b["name"]: b["room"] for b in _bg_beats if b["room"]}
    # A charter body the Director voiced before resolve speaks from the room
    # its declaration stood it in. It has no scene row, so without this its
    # line had no source room and was refused to a listener at arm's reach
    # (playerless Aldermill round 3, 2026-09-23: 10 of 28 lines).
    for _fd in (res.get("charter_declarations") or []):
        if isinstance(_fd, dict) and _fd.get("name") and _fd.get("room"):
            _bg_rooms.setdefault(str(_fd["name"]), str(_fd["room"]))
    br_entries = [b["entry"] for b in _bg_beats if b["entry"]]

    raw_dlog = list(res.get("dialogue_log") or [])
    # MARKED AS THE BACKGROUND STAGE'S, under the same `source` key
    # `commit_memory` files them by. `_composer_outcome` reads it to notice a
    # produced answer that reached no view at all, which is otherwise
    # indistinguishable from the presence having said nothing.
    raw_dlog.extend({**e, "source": "background_react"} for e in br_entries)
    enriched_dlog = []
    for d in raw_dlog:
        speaker = d.get("speaker", "?")
        if is_player_speaker(speaker, chat):
            sp_room = p_room
        else:
            sp_room = cast_room(sc, speaker, ctx.cast) or _bg_rooms.get(speaker)
        volume = str(d.get("volume") or "normal")
        level_db = None
        if volume.strip().casefold() == "pitched":
            # LOUD ENOUGH FOR THE ONE ADDRESSED AND NO LOUDER: solved once
            # from the addressee's cell, then every observer is graded at
            # that level and the view carries the word it comes to.
            from world.spatial import pitched_level_db, word_for_level
            level_db = pitched_level_db(
                sc, p_name if is_player_speaker(speaker, chat) else speaker,
                d.get("intended_target"))
            volume = word_for_level(level_db)
        enriched_dlog.append({
            "speaker": speaker, "exact_quote": d.get("exact_quote", ""),
            "volume": volume,
            **({"level_db": level_db} if level_db is not None else {}),
            "intended_target": d.get("intended_target"),
            "tone": d.get("tone", ""), "speaker_room": sp_room,
            "visibility": d.get("visibility", "overt"),
            "conceal_from": d.get("conceal_from") or [],
            # medium:'comm' carries a transmitted line to its addressed party
            # across a physical barrier (see the perception_outcome injection).
            "medium": d.get("medium"),
            "source": d.get("source") or "",
        })

    sources = [{"name": p_name, "room": p_room}]
    # Every presence that spoke OR acted -- an act needs a channel to its
    # observer exactly as a line does, and only a source has one.
    for _b in _bg_beats:
        sources.append({"name": _b["name"], "room": _b["room"],
                        "chorus": bool(_b.get("chorus"))})
    for c in ctx.cast:
        d = _settled_character_result(ctx, c["id"])
        # One memoised normalization for the name and the room lookup (C14).
        sh = normalized_character_from_text(c["sheet"])
        if d and (d.get("sequence") or d.get("speech") or d.get("action")):
            sources.append({"name": character_name(sh),
                            "room": character_room(sc, sh)})
    # AND EVERY OTHER BODY THE BEAT MADE ACT: a charter figure voiced before
    # resolve, or one the resolve's own rows are sourced to by name. Neither
    # is a cast member or a background beat, so neither had a channel to
    # anyone, and every act of theirs reached no view -- 0 of 4 on the
    # playerless Aldermill run, round 4 (2026-09-23), a journeyman working the
    # jack "close by" the woman watching him. Placed where the scene stands
    # them, else where the beat's declaration did.
    _sourced = {str(src["name"]).casefold() for src in sources}
    _actors = [str(_fd.get("name") or "")
               for _fd in (res.get("charter_declarations") or [])
               if isinstance(_fd, dict)]
    _actors += [str(_r.get("source_entity_id") or "")
                for _r in (res.get("ledgers") or [])
                if isinstance(_r, dict)
                and ":" not in str(_r.get("source_entity_id") or "")]
    for _actor in _actors:
        if not _actor or _actor.casefold() in _sourced:
            continue
        _room = room_of(sc, _actor) or _bg_rooms.get(_actor)
        if _room:
            sources.append({"name": _actor, "room": _room})
            _sourced.add(_actor.casefold())

    appearances = {p_name: p_appearance}

    # Additional human players: each gets a real perceiver entry at their
    # OWN tracked position (room_of, same lookup used for NPCs and the
    # primary player) -- not hardcoded to the primary player's room. Only
    # fall back to the primary player's room when the extra player has no
    # tracked position yet (e.g. they were only just attached and have
    # never been placed anywhere). They're a genuine dialogue/action source
    # for everyone else's view too, exactly like an NPC -- not a silent
    # observer.
    #
    # Every extra player is appended to `sources` HERE, before any
    # perceiver's spatial_to_sources / visual_channel_to_sources maps are
    # computed below -- previously the primary player's perceiver was built
    # first (so it had no channel to any co-player at all), and each extra
    # player's perceiver was built as its own source-append happened (so
    # extra A had no channel to extra B, only vice versa).
    extra_entries = []
    for extra in ctx.extra_players:
        pid_key = str(extra["persona_id"])
        e_name = extra["name"]
        e_room = room_of(sc, e_name) or p_room
        sources.append({"name": e_name, "room": e_room})
        appearances[e_name] = _appearance_as_prose(appearance_of(
            e_name, extra.get("appearance") or f"{e_name}, a person of unremarkable appearance.", sc))
        extra_entries.append((extra, pid_key, e_name, e_room))

    p_rdata = (sc.get("rooms") or {}).get(p_room) if p_room else None
    # name -> cast id, so perception can pull each present character's authored
    # `manifest` (surface demeanor + tells) and gate delivery per observer.
    cast_by_name = {character_name_from_text(c["sheet"]): c["id"] for c in ctx.cast}

    # One registry read for the whole stage (see `chatter_inputs`).
    chatter = chatter_inputs(ctx.chat.id, sc, turn_idx=ctx.turn.idx)
    perceivers = [{
        "id": "player", "name": p_name, "room": p_room,
        "pronouns": (pers.get("identity") or {}).get("pronouns") or {},
        "room_name": room_display_name(p_rdata, p_room) or "an unspecified area",
        "room_notes": _room_notes_for_view(p_rdata, p_room, ctx, sc),
        "ambient_location": _ambient_location_for(sc, p_room),
        "crowds": crowds_for_room(ctx.chat.id, sc, p_room, chatter),
        "chatter": chatter_for_room(
            ctx.chat.id, sc, p_room, chatter,
            attending=attending_this_room(sc, p_name, p_room)),
        "couriers": couriers_for_room(ctx.chat.id, sc, p_room, chatter),
        "notices": artifacts_for_room(ctx.chat.id, sc, p_room, chatter),
        "visible_rooms": _visible_rooms_for(sc, p_name, p_room),
        "known_places": _player_known_places(ctx),
        "senses": senses_of(pers), "sense_card": _sense_card(pers),
        "attention": "engaged",
        "knows_identity": True,
        **_source_channels(sc, p_name, p_room, sources, prev_sc=prev_scene,
                           senses=_sense_card(pers),
                           sound=_sound_field_for(ctx, sc, p_name, p_room)),
        "proximity_to_sources": _proximity_to_sources(sc, p_name, sources),
        "behind_sources": _behind_sources(sc, p_name, sources),
        "behind_rooms": _behind_rooms(sc, p_name),
        "focus_target": _focus_target(sc, p_name),
        "source_manifest": _delivered_manifest(
            ctx, sc, p_name, sources, known, cast_by_name, pers),
    }]

    for extra, pid_key, e_name, e_room in extra_entries:
        e_rdata = (sc.get("rooms") or {}).get(e_room) if e_room else None
        perceivers.append({
            "id": f"extra:{pid_key}", "name": e_name, "room": e_room,
            "pronouns": (extra.get("identity") or {}).get("pronouns") or {},
            "room_name": room_display_name(e_rdata, e_room) or "an unspecified area",
            "room_notes": _room_notes_for_view(e_rdata, e_room, ctx, sc),
            "ambient_location": _ambient_location_for(sc, e_room),
            "crowds": crowds_for_room(ctx.chat.id, sc, e_room, chatter),
            "chatter": chatter_for_room(
                ctx.chat.id, sc, e_room, chatter,
                attending=attending_this_room(sc, e_name, e_room)),
            "couriers": couriers_for_room(ctx.chat.id, sc, e_room, chatter),
            "notices": artifacts_for_room(ctx.chat.id, sc, e_room, chatter),
            "visible_rooms": _visible_rooms_for(sc, e_name, e_room),
            "known_places": {},
            "senses": senses_of(extra), "sense_card": _sense_card(extra),
            "attention": "engaged",
            "knows_identity": True,
            **_source_channels(sc, e_name, e_room, sources, prev_sc=prev_scene,
                               senses=_sense_card(extra),
                               sound=_sound_field_for(ctx, sc, e_name, e_room)),
            "proximity_to_sources": _proximity_to_sources(sc, e_name, sources),
            "behind_sources": _behind_sources(sc, e_name, sources),
            "behind_rooms": _behind_rooms(sc, e_name),
            "focus_target": _focus_target(sc, e_name),
            "source_manifest": _delivered_manifest(
                ctx, sc, e_name, sources, known, cast_by_name, extra),
        })

    for c in ctx.cast:
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        appearances[character_name(sh)] = _appearance_as_prose(appearance_of(
            character_name(sh), character_appearance(sh), sc))
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "pronouns": character_identity(sh)["pronouns"],
            "room_name": room_display_name(rdata, r) or "an unspecified area",
            "room_notes": _room_notes_for_view(rdata, r, ctx, sc),
            "ambient_location": _ambient_location_for(sc, r),
            "crowds": crowds_for_room(ctx.chat.id, sc, r, chatter),
            "chatter": chatter_for_room(
                ctx.chat.id, sc, r, chatter,
                attending=attending_this_room(sc, character_name(sh), r)),
            "couriers": couriers_for_room(ctx.chat.id, sc, r, chatter),
            "notices": artifacts_for_room(ctx.chat.id, sc, r, chatter),
            "visible_rooms": _visible_rooms_for(sc, character_name(sh), r),
            "known_places": _character_known_places(c),
            "senses": senses_of(sh), "sense_card": _sense_card(sh),
            "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            **_source_channels(sc, character_name(sh), r, sources,
                               prev_sc=prev_scene, senses=_sense_card(sh),
                               sound=_sound_field_for(
                                   ctx, sc, character_name(sh), r)),
            "proximity_to_sources": _proximity_to_sources(sc, character_name(sh), sources),
            "behind_sources": _behind_sources(sc, character_name(sh), sources),
            "behind_rooms": _behind_rooms(sc, character_name(sh)),
            "focus_target": _focus_target(sc, character_name(sh)),
            "source_manifest": _delivered_manifest(
                ctx, sc, character_name(sh), sources, known, cast_by_name, sh),
        })

    # Consciousness gate: overlay THIS beat's just-resolved awareness
    # conditions (a knockout resolves before perception_outcome commits) onto
    # the committed map, then tag every perceiver. A non-awake mind (asleep/
    # sedated/unconscious) is EXCLUDED from the LLM call entirely -- it cannot
    # leak a view it was never asked to write -- and receives a deterministic
    # residue below instead. 'dazed' stays in the call (present but degraded).
    amap = apply_awareness_diff(awareness_map(chat["id"]), diff)
    for p in perceivers:
        p["awareness"] = awareness_of(amap, p["name"])

    return _stage_player_room(_composer_outcome(
        ctx, sc, prev_scene, diff, interp, res, known, p_name,
        p_appearance, p_disguise, p_disguise_known, p_disguise_conceals,
        p_disguise_terms, perceivers, appearances, sources, enriched_dlog,
        substance_events, amap,
        # The room's other people, placed on `sc` before the composer reads
        # it (see `_presence_bodies`). A presence that spoke this beat is
        # already a source; this is everyone who merely stood there, which
        # was nobody.
        _presence_bodies(ctx, sc, [p["room"] for p in perceivers], chatter)),
        ctx)
