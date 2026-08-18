"""Director agents for scene establishment, player interpretation, and resolution."""

from __future__ import annotations

import contextvars
import copy
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor

import attire as attire_model
from character_schema import (
    character_abilities,
    character_appearance,
    character_extra_parts,
    character_initial_outfit,
    character_name,
    character_name_from_text,
    character_public_history,
    name_boundary_pattern,
    persona_abilities,
    persona_appearance,
    persona_extra_parts,
    persona_initial_outfit,
    persona_name,
    persona_public_history,
)
from db import get_setting, q, wget
from memory import lorebook_manifest
from paradox import paradox_visible_to
from language_runtime import apply_prompt_policy
from prompts import (
    PROSE_DUTY_CHUNKS,
    get_prompt,
    get_prompt_body,
    interpret_delegation_note,
    prose_author_prompt,
    specialist_prompt,
)
from scene import (
    IMMOBILIZING_RESTRAINTS,
    NON_AWAKE_GATED,
    apply_restraint_diff,
    awareness_conditions,
    restraint_map,
    restraint_of,
    _ability_mod,
    _normalize_awareness_level,
    appearance_of,
    cast_scene_context,
    director_context,
    fiction_model,
    get_scene,
    is_player_speaker,
    persona_of,
    player_authority,
    sanitize_attire_items,
    senses_of,
    sheet_state,
    simulation_clock,
    style_guide,
)
from providers import Aborted, generation_event_sink, token_sink
import schemas
from schemas import validate_llm_output
from survival import survival_enabled, vitals_of
from spatial import (
    apply_contact_ops,
    contact_motion,
    contacts_of,
    contact_relation,
    _merge_entity,
    _merge_room,
    egocentric_frame,
    merge_scene_with_diff,
    normalize_bearing,
    passable_route_exists,
    passable_route_next_step,
    resolve_substance_ops,
    normalize_edge_distance,
    room_of,
    can_perceive_onset,
    same_subject,
    spatial_rel,
    speech_articulation_impediment,
    ARTICULATION_STIFLED,
    sprint_reach,
)

from .common import (
    merge_player_state_assertions,
    preview_player_state_assertions,
    validated_player_state_assertions,
    _agent_json,
    _contextual_rooms,
    _dict,
    _dict_list,
    _extract_authority_claims,
    apply_player_authority,
    _list,
    _normalize_scene_patch,
    _check_character_act_authority,
    _check_character_speech_authority,
    _check_player_act_authority,
    _check_player_interiority_authority,
    _check_presence_knowledge_channel,
    director_may_voice,
    _check_prose_quote_authority,
    _quote_body,
    _unknown_actor_label,
    _requires_reaction_phase,
    _resolve_player_room,
    _sync_sequence_mirrors,
    assign_event_ids,
    authored_other_subject,
    bind_sequence_targets,
    canonicalize_positions,
    character_room,
    character_scene_keys,
    lore_for,
    norm_sequence,
    normalize_character_refs,
    player_speech_lines,
    repair_narrated_speech_elements,
    extra_parts_lines,
    scene_attire_view,
    scene_compact_attire,
    scene_extra_parts,
)

from .director_lingua import (
    _ling,
    _UNCONSCIOUSNESS_CUE,
    _SLEEP_CUE,
    _STAY_UNDER_CUE,
)
from .director_contact import (
    _canonical_scene_subject,
    _validated_player_contact_assertions,
    _merge_player_contact_assertions,
    _validated_character_contact_endings,
    _ACTOR_MATERIAL_FIELDS,
    _character_material_effects,
    _merge_character_material_effects,
    _merge_character_contact_endings,
)

from .director_views import (
    _cast_match_forms,
    _route_authorial_npc_beat,
    _opening_pose_snapshots,
    _extension_director_payload,
    _ROUND_CONDUCT_KEYS,
    _round_conduct,
    _audit_fact_adjudications,
    _unratified_background_claims,
    _report_observer_epithets,
    _crowds_view,
    _couriers_view,
    _artifacts_view,
    _carried_reports_view,
)


def director_establish(ctx, nonce):
    chat = ctx.chat
    pers = persona_of(chat)
    mapping = ctx.mapping_stage or ctx.mapping_quick or {}
    fm = fiction_model(chat.id)

    cast = cast_scene_context(ctx.cast)
    player_name = pers.get("name") or persona_name(pers)
    initial_attire = {
        player_name: persona_initial_outfit(pers),
        **{
            member["name"]: member["initial_outfit"]
            for member in cast
            if member.get("name")
        },
    }

    payload = {
        "scenario": chat.get("scenario"),
        **({"style_guide": style_guide(chat["id"])}
           if style_guide(chat["id"]) else {}),
        "player": {
            "name": player_name,
            "appearance": persona_appearance(pers),
            **({"body_parts": extra_parts_lines(persona_extra_parts(pers))}
               if persona_extra_parts(pers) else {}),
            "initial_outfit": persona_initial_outfit(pers),
            "senses": senses_of(pers),
            "abilities": persona_abilities(pers),
            "public_history": persona_public_history(pers),
        },
        "present_characters": cast,
        "relevant_lore": lore_for(ctx),
        "mapping_scene_proposal": _normalize_scene_patch(mapping.get("scene_patch")),
        "fiction_model": fm,
        "player_seed": ctx.get("input") or "",
        "variant_seed": nonce,
    }

    payload = _extension_director_payload(ctx, payload, phase="establish")

    out = _agent_json(
        "director",
        "director_establish",
        get_prompt("director_establish", ctx.language),
        payload,
        temperature=0.7,
        max_tokens=None,   # the configured ceiling; see complete_validated_json
    )
    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json.
    out, warnings = validate_llm_output("director_establish", out)
    ctx.warnings.extend(warnings)

    attire = out.get("attire") or {}
    for entity, state in attire.items():
        if not isinstance(state, dict):
            continue
        state["wearing"] = sanitize_attire_items(state.get("wearing"))
    # A non-empty authored initial outfit is objective starting state, not a
    # styling suggestion. Restore that narrow public projection after model
    # output so establishment cannot replace it by inferring clothes from body
    # appearance. Empty cards still permit scenario-grounded inference.
    for entity, state in initial_attire.items():
        if not isinstance(state, dict):
            continue
        # Authored regions are restored with the rest. Without this the
        # opening turn is the one beat that silently discards them, and a
        # card's placement would only take effect from turn two onward.
        entry = attire_model.authored_entry(
            sanitize_attire_items(state.get("wearing") or []),
            state.get("state"),
            state.get("regions"),
        )
        if any(entry.values()):
            attire[entity] = entry
    out["attire"] = attire

    out.setdefault("entities", {})
    out.setdefault("sensory_events", [])
    out.setdefault("fiction_frame", {})
    out.setdefault("simulation_clock", {"elapsed_seconds": 0.0, "display": "now"})

    # Opening entity_states historically reached opening perception and then
    # vanished. Seed the durable pose ledger from them so player personas and
    # registered cast do not need duplicate scene entities merely to remain
    # seated/lying/standing after turn zero. An explicit structured pose wins.
    opening_poses = _opening_pose_snapshots(out)

    out["state_diff"] = {
        "rooms": out.get("rooms") if isinstance(out.get("rooms"), dict) else {},
        "entities": out.get("entities") if isinstance(out.get("entities"), dict) else {},
        # Key positions by the registered character name (the convention every
        # reader uses), even when the model keyed a cast member by identity.uid,
        # a 'character:<id>' scheme, or a snake-case variant of the player name.
        "positions": canonicalize_positions(
            out.get("positions") if isinstance(out.get("positions"), dict) else {},
            ctx.cast, player_name=player_name),
        "remove_entities": [],
        "remove_rooms": [],
        "stations": out.get("stations") if isinstance(out.get("stations"), dict) else {},
        "poses": opening_poses,
        # The opening's standing holds, through the same merge every later beat
        # uses (spatial.apply_contact_ops). Without this the one physical act a
        # greeting usually contains -- a grip, a carry, a body pinned -- was
        # unrepresentable at establishment and the scene opened with contacts:[].
        "contact_ops": (out.get("contact_ops")
                        if isinstance(out.get("contact_ops"), list) else []),
        "substance_ops": (out.get("substance_ops")
                          if isinstance(out.get("substance_ops"), list) else []),
        # The channels the opening installs, through the same merge every later
        # beat uses (spatial.apply_comms_ops). Without this a scene BUILT
        # around an intercom -- an observation room, a bridge, a control booth
        # -- could not have one until beat two, which is exactly the beat it
        # was needed for.
        "comms_ops": (out.get("comms_ops")
                      if isinstance(out.get("comms_ops"), list) else []),
        "attire": out.get("attire") if isinstance(out.get("attire"), dict) else {},
        "world_facts": out.get("world_facts") if isinstance(out.get("world_facts"), list) else [],
        "time": None,
    }
    out["resolved_event"] = out.get("scene_description", "")
    out["summary"] = "Scene established: " + (out.get("location") or "")
    out["dialogue_log"] = []
    return out

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


def director_interpret(ctx, nonce):
    chat = ctx.chat
    sc = get_scene(chat["id"], chat)
    pers = persona_of(chat)
    p_room = ctx.get("_player_room")
    if p_room is None:
        p_room = _resolve_player_room(sc, pers, None, ctx.cast, ctx.get("input"))
        ctx["_player_room"] = p_room

    cast_info = []
    for c in ctx.cast:
        sh, _, _ = sheet_state(c)
        cname = character_name(sh)
        cast_info.append({
            "id": c["id"],
            "name": cname,
            "room": room_of(sc, cname),
            # Their heading, on the same terms as the player's above. This
            # stage does not usually relocate a character -- director_resolve
            # does -- but it interprets declarations ABOUT them, and a room
            # with no orientation is the same undirected graph that made
            # "forward" a coin flip for the player.
            "exits": _egocentric_exits(sc, cname),
            "appearance": appearance_of(cname, character_appearance(sh), sc),
            # Authored structured extra body parts (tail, wings...): shown so
            # the Director stops re-inventing them from prose each beat. Key
            # absent for an ordinary body -- defaults stay inert and the
            # payload prefix stays cacheable.
            **({"body_parts": extra_parts_lines(character_extra_parts(sh))}
               if character_extra_parts(sh) else {}),
            "abilities": character_abilities(sh),
        })

    raw_shadow = wget(chat["id"], "shadow_profile", "") or ""
    raw_intents = wget(chat["id"], "standing_intentions", []) or []
    fm = fiction_model(chat["id"])
    clock = simulation_clock(chat["id"])

    # Authored future events the player scheduled on a prior beat and that are
    # due NOW (P4). Delivered with a resolve-now contract; commit_authored_events
    # re-queues any the resolution fails to enact rather than dropping them.
    from authored_events import due_authored_events
    _due_authored = due_authored_events(chat["id"], ctx.turn.idx)

    world_books = [
        {"name": m["name"], "type": m["type"], "summary": (m["summary"] or "")[:240],
         "scope_world_id": m.get("scope_world_id"),
         "scope_location_id": m.get("scope_location_id"),
         "parent_id": m.get("parent_id")}
        for m in lorebook_manifest(chat["id"])["books"]
    ]

    payload = {
        "scene": {
            "location": sc.get("location"),
            "time": sc.get("time"),
            "rooms": _contextual_rooms(sc, ctx.cast, p_room),
            "entities": sc.get("entities"),
            "positions": sc.get("positions"),
            # Where in the room each body stands. Shown so the Director can
            # MAINTAIN the ledger -- it was being asked to write stations it
            # was never allowed to read.
            "stations": sc.get("stations") or {},
            "following": sc.get("following") or {},
            # Needed to distinguish a genuinely new NPC act (not the player's
            # authority) from a first-person refinement of contact already felt.
            "contacts": sc.get("contacts") or [],
        },
        "simulation_clock": clock,
        "paradox": paradox_visible_to(chat["id"], ctx.turn.frame_id),
        "fiction_model": fm,
        "director_recent_messages": director_context(chat["id"], 5),
        "player": {
            "name": pers.get("name") or persona_name(pers),
            "room": p_room,
            "appearance": appearance_of(
                pers.get("name") or persona_name(pers),
                pers.get("appearance") or persona_appearance(pers), sc),
            **({"body_parts": extra_parts_lines(persona_extra_parts(pers))}
               if persona_extra_parts(pers) else {}),
            "abilities": persona_abilities(pers),
            "following": (sc.get("following") or {}).get(
                pers.get("name") or persona_name(pers)),
            "public_shadow_profile": raw_shadow[:1200],
            # Heading, so "forward" and "back" name different doorways.
            "exits": _egocentric_exits(
                sc, pers.get("name") or persona_name(pers)),
        },
        "present_characters": cast_info,
        # Named figures with no character id. `flow.addressed_to` accepts a
        # NAME STRING for exactly these (schemas.py: "the only way the director
        # can address an UNREGISTERED background presence"), and the prompt
        # asks for one -- but this stage was never shown WHICH figures exist,
        # so the instruction named something the model could not see. The
        # channel was documented and unusable.
        #
        # Live, chat 75 turn 60. The player told the intruders in her room to
        # close the door and leave. The only addressable ids in front of the
        # Director were registered cast, so it routed the line to The Doctor,
        # who was standing in the corridor being talked past, and he left.
        #
        # Only figures with a resolvable room are listed -- addressing someone
        # who is nowhere is meaningless -- but co-presence is FLAGGED rather
        # than filtered, because calling through an open doorway is ordinary.
        "addressable_presences": [
            _bp for _bp in (
                {"name": _pn,
                 "room": (room_of(sc, _pn)
                          or ((_pr.get("sketch") or {}).get("station_room") or "")),
                 "same_room_as_player": (
                     (room_of(sc, _pn)
                      or ((_pr.get("sketch") or {}).get("station_room") or ""))
                     == p_room)}
                for _pn, _pr in
                (wget(chat["id"], "background_presences", {}) or {}).items())
            if _bp["room"]
        ],
        "world_books": world_books,
        "standing_intentions": raw_intents[:12],
        "pending": wget(chat["id"], "pending", []),
        # Future beats the PLAYER scheduled earlier ("the elevator crashes next
        # turn") that are due NOW: resolve them as occurring this beat, folded
        # in with whatever the player declares this turn.
        "due_authored_events": [e["summary"] for e in _due_authored],
        # Mechanical notices from the previous commit's transit sweep (e.g.
        # a timed arrival that completed) -- facts the engine already made
        # true, for the director to acknowledge rather than re-invent.
        "engine_notices": wget(chat["id"], "engine_notices", []),
        "player_raw_input": ctx.input,
        # Idle attached players (connected, but declared nothing this beat)
        # are deliberately excluded here -- there's nothing to interpret
        # for them. They still get their own perceiver/narrated view of
        # the beat via perception_outcome/narrator_extra; they just don't
        # need the director's attention.
        "other_players": [
            {"persona_id": p["persona_id"], "name": p["name"], "raw_input": p["input"],
             "following": (sc.get("following") or {}).get(p["name"])}
            for p in ctx.extra_players if not p.get("idle")
        ],
        "variant_seed": nonce,
    }

    # Orchestrated interpret (design note 19): the same sheet plus the
    # delegation note as a SUFFIX -- the monolithic sheet stays
    # byte-identical (and a stable cache prefix), and the note overrides
    # the sheet's own PASS 1 "full structure, no subset" instruction so the
    # stage model stops authoring the channels the dispatched specialists
    # will replace anyway (run 20: every such emission was discarded at
    # assembly, pure output-token latency). One read of the setting serves
    # the prompt and the dispatch below, so they cannot disagree about
    # which path this beat is on.
    payload = _extension_director_payload(ctx, payload, phase="interpret")

    out = _agent_json(
        "director",
        "director_interpret",
        apply_prompt_policy(
            get_prompt_body("director_interpret", ctx.language)
            + interpret_delegation_note(ctx.language),
            ctx.language, "director_interpret"),
        payload,
        max_tokens=None,   # the configured ceiling; see complete_validated_json
    )

    # Warning-only re-normalization; strict validation already ran inside
    # _agent_json (see director_establish above).
    out, warnings = validate_llm_output("director_interpret", out)
    ctx.warnings.extend(warnings)

    norm_sequence(out, warn=lambda _w: ctx.add_warning("player input: %s" % _w))
    # A SILENT BEAT DECLARES NOTHING.
    #
    # With no player input at all there is nothing to interpret, and anything
    # in the sequence is the model supplying conduct on the player's behalf --
    # the one thing the PLAYER AUTHORITY CONTRACT exists to forbid, arriving
    # from the direction nobody guards because there was no declaration to
    # compare against.
    #
    # Live, chat 59 t154. Empty input; interpret emitted
    # speech "Kaa Sama Kaa Sama! You're cooking is simply to good to not
    # indulge in." and action "steps inside the shrine and looks around at the
    # familiar sight of home" -- both the player's turn-150 declaration,
    # verbatim, four beats stale. Tamamo then thanked her for praise she had
    # not given. Across the corpus 10 turns carry an empty input and 2 of them
    # invented player speech, the other newly ("something reassuring").
    #
    # Deterministic, not a prompt request: an empty input is unambiguous, and
    # the check costs nothing on every other beat. Silence remains a thing the
    # player DID -- downstream still receives the beat, and
    # `_player_silence_note` still tells characters about it. What it no longer
    # receives is words.
    if not str(ctx.input or "").strip():
        _invented = [
            e for e in (out.get("sequence") or [])
            if isinstance(e, dict) and (e.get("text") or e.get("attempt"))
        ]
        if _invented or str(out.get("speech") or "").strip():
            ctx.add_warning(
                "director_interpret: player input was empty; discarded "
                f"{len(_invented)} invented declaration(s) and any speech "
                "attributed to the player")
            ctx.tell_director(
                "The player said and did nothing that beat. An empty input is "
                "not a cue to restate what they last said -- their silence is "
                "the whole declaration.")
        out["sequence"] = []
        out["speech"] = None
        out["speech_volume"] = "normal"
        out["action"] = None
        out["actions"] = []
        out["contact_assertions"] = []
        out["state_assertions"] = {}
    # A speech element that swallowed the raw input's narration is repaired
    # BEFORE anything reads it: perception injects these texts verbatim as
    # dialogue, so narration left here is delivered to every hearer as words
    # the player spoke -- in the player's own second person, which points it
    # at the listener.
    for _before, _after in repair_narrated_speech_elements(out):
        ctx.add_warning(
            "director_interpret: speech element carried narration; reduced to "
            f"the spoken words ({len(_before)} -> {len(_after)} chars)")
    _route_authorial_npc_beat(
        ctx, out, [str(pers.get("name") or persona_name(pers) or "").casefold()])
    # Bind the acts the model left unbound BEFORE anything downstream asks
    # whether they land on a character: the reaction-phase gate, claim subject
    # binding and perception's targeted-observer check all read `targets`.
    _, target_forms = _cast_match_forms(ctx.cast)
    bind_sequence_targets(out.get("sequence"), target_forms)
    out["sequence"] = assign_event_ids(
        out.get("sequence"), f"turn:{ctx.turn.id}:player")

    other_players = out.get("other_players")
    if not isinstance(other_players, dict):
        other_players = {}
        out["other_players"] = other_players
    for extra in ctx.extra_players:
        pid = str(extra["persona_id"])
        entry = other_players.get(pid)
        if not isinstance(entry, dict):
            entry = {}
            other_players[pid] = entry
        norm_sequence(entry)
        repair_narrated_speech_elements(entry)
        bind_sequence_targets(entry.get("sequence"), target_forms)
        entry["sequence"] = assign_event_ids(
            entry.get("sequence"), f"turn:{ctx.turn.id}:extra:{pid}")

    p_name = pers.get("name") or persona_name(pers)

    # Orchestrated interpret (design note 19): THE SAME specialists resolve
    # dispatches, scoped to the player's declaration -- interpret is not a
    # lesser authority than resolve, it is the same authority scoped to the
    # player's input, so an orchestration that gave resolve specialists and
    # interpret none would rebuild the pre-8.1 asymmetry by construction.
    # Dispatch is decided HERE from interpret-time facts (the player's own
    # structured declaration; the pre-turn ledgers); nothing is shared with
    # or inherited by resolve's dispatch, which runs after characters have
    # declared and sees a different beat. The specialists' channel output
    # merges into `state_assertions` (contact into `contact_assertions`,
    # the interpret spelling of the same channel) BEFORE the deterministic
    # validators below, so the merged result crosses the exact floor a
    # model-authored copy crosses.
    _idispatch = _dispatch_specialists(ctx, sc, _gate_facts(
        ctx, sc,
        physical=_beat_has_physical_activity(out, {}, []),
        speech=bool(player_speech_lines(out)),
    ))
    _iparts = scene_extra_parts(ctx.cast, pers, p_name)
    try:
        from living_world import living_world_allows, living_world_config
        _iplanning = {
            "enabled": bool(living_world_allows(
                living_world_config(chat["id"]),
                "antagonist_ladder", "floor")),
        }
        if _iplanning["enabled"]:
            _iplanning["plans"] = (
                wget(chat["id"], "offscreen_plans", []) or [])[:8]
    except Exception:
        _iplanning = {"enabled": False, "plans": []}
    _run_specialists(
        ctx, out, sc, _idispatch,
        _interpret_beat_view(ctx, out, p_name),
        {
            "nonce": nonce,
            "clock": clock,
            "active_awareness": _awareness_view(
                chat["id"], clock, out, {}),
            "body_parts": ({name: extra_parts_lines(parts)
                            for name, parts in _iparts.items()}
                           if _iparts else None),
            "contacts": sc.get("contacts") or [],
            "notices": _artifacts_view(chat["id"], sc),
            "movement": out.get("movement"),
            "movers": {p_name: {"exits": _egocentric_exits(sc, p_name)}},
            "proposal": None,
            "crowds": _crowds_view(chat["id"], sc),
            "couriers": _couriers_view(chat["id"], sc),
            "carried_reports": _carried_reports_view(ctx),
            "unratified_claims": _unratified_background_claims(
                chat["id"], ctx.turn["idx"]),
            "offscreen_planning": _iplanning,
        },
        "interpret")

    out["contact_assertions"] = _validated_player_contact_assertions(
        sc, out.get("contact_assertions"), p_name,
        report=lambda note: ctx.add_warning(f"player contact: {note}"),
    )
    out["state_assertions"] = validated_player_state_assertions(
        sc, out.get("state_assertions"), p_name,
        report=lambda note: ctx.add_warning(f"player state: {note}"),
    )

    fl = out.get("flow")
    if not isinstance(fl, dict):
        fl = {}
        out["flow"] = fl

    reactors = fl.get("reactors")
    if not isinstance(reactors, list):
        reactors = []
    tom_triggers = fl.get("tom_triggers")
    if not isinstance(tom_triggers, list):
        tom_triggers = []

    fl["reactors"] = normalize_character_refs(
        reactors + _list(fl.get("reactor_refs")), ctx.cast)
    fl["tom_triggers"] = normalize_character_refs(
        tom_triggers + _list(fl.get("tom_trigger_refs")), ctx.cast)
    fl.pop("reactor_refs", None)
    fl.pop("tom_trigger_refs", None)

    if not fl["reactors"]:
        for c in ctx.cast:
            sh = json.loads(c["sheet"])
            c_room = character_room(sc, sh)
            rel = spatial_rel(sc, p_room, c_room)
            if rel.get("same_room") or can_perceive_onset(sc, p_room, c_room):
                fl["reactors"].append(c["id"])

    fl.setdefault("dialogue_mode", False)
    fl.setdefault("needs_mapping", False)
    if not isinstance(fl.get("dice"), list):
        fl["dice"] = []
    fl.setdefault("mapping_request", "")
    if not isinstance(fl.get("resolution_flags"), dict):
        fl["resolution_flags"] = {}
    if not isinstance(fl.get("generation_requests"), list):
        fl["generation_requests"] = []
    if not isinstance(fl.get("authority_claims"), list):
        fl["authority_claims"] = []
    if not isinstance(fl.get("fiction_frame"), dict):
        fl["fiction_frame"] = {}

    out.setdefault("private_thought", None)
    out.setdefault("movement", None)
    out.setdefault("location_query", None)
    if isinstance(out.get("movement"), dict):
        out["movement"].setdefault("mover", "self")

    # Interpret reconciliation seam (the structural twin of the resolve
    # seam below): deterministic omission detection of player declarations
    # the interpretation dropped, one bounded self-repair, warn-only
    # fallback. Runs BEFORE claims extraction / contested detection /
    # mapping triggers so every downstream deterministic pass sees the
    # repaired sequence.
    _reconcile_interpretation(ctx, out, sc)

    # Any generation request (model-authored, repaired, or synthesized by
    # the seam) needs the full mapping stage to elaborate it.
    if fl.get("generation_requests"):
        fl["needs_mapping"] = True

    # Extract authority claims from the sequence. The player is the declaring
    # actor, so a self-directed effect (no target) resolves to them -- see
    # _extract_authority_claims; this stops the resolve reconciliation flagging
    # the player's own body actions (wave, go rigid) as 'no resolvable subject'.
    # target_forms keeps that fallback off an effect whose text names someone
    # else, so an unbound act never resolves to the player by default.
    fl["authority_claims"] = _extract_authority_claims(
        out.get("sequence"), ctx.input,
        actor_name=(pers.get("name") or persona_name(pers)),
        target_forms=target_forms)

    # PLAYER AUTHORITY MODE, enforced (`Design.md` § Hard mode; UNBUILT §2.4).
    # `schemas.PlayerAuthorityMode` named the ladder when the vocabulary was
    # written and was consumed nowhere -- this is the consumer. It runs HERE,
    # after extraction, because this is the one point where both
    # representations of the same declaration are on the table: the sequence
    # element the beat is resolved from, and the claim the resolve seam holds
    # the diff to. See `apply_player_authority` for why moving one without the
    # other makes a downgrade invisible.
    #
    # `world_author` is the default and grants everything, so an existing story
    # is byte-identical under it and this costs one dict lookup on every beat
    # nobody has changed the dial for.
    _authority_mode = player_authority(chat["id"])["mode"]
    _downgrades = apply_player_authority(out, _authority_mode, p_name)
    if _downgrades:
        # A REFUSED ASSERTION MUST NOT SILENTLY VANISH. The player wrote it for
        # a reason, and dropping their text is the one thing this engine's
        # authority contract has never done. Two surfaces, and deliberately not
        # three: the step record says what the mode moved, and the resolve
        # payload carries `downgraded_assertions` so the Director can answer it
        # in THIS beat -- resolve the declaration as the attempt it now is, or
        # refuse it visibly in the prose where the player can see the refusal.
        #
        # `tell_director` is not the third, though it looks like the natural
        # channel. It lands in `engine_notices` at COMMIT and reaches the NEXT
        # beat, which is a beat too late for the player reading this one -- and
        # under a restricted mode it would repeat, every beat, as past-tense
        # feedback about a beat already resolved.
        out["authority_downgrades"] = _downgrades
        out["authority_mode"] = _authority_mode
        _sync_sequence_mirrors(out)

    # Detect contested actions
    seq = out.get("sequence")
    if not isinstance(seq, list):
        seq = []
    action_texts = " ".join(
        str(e.get("attempt") or "").casefold()
        for e in seq
        if isinstance(e, dict) and e.get("type") == "action"
    )
    valid_actor_ids = {
        int(row["id"])
        for row in ctx.cast
    }

    actor_names = {
        character_name(
            json.loads(row["sheet"])
        ).casefold()
        for row in ctx.cast
    }

    has_reactable_target = any(
        _requires_reaction_phase(
            event,
            valid_actor_ids,
            actor_names,
        )
        for event in seq
    )

    if has_reactable_target:
        fl["resolution_flags"]["contested"] = True
        fl["resolution_flags"]["possible_reactors"] = [
            int(rid)
            for rid in fl["reactors"]
            if str(rid).isdigit()
            and int(rid) in valid_actor_ids
        ]
    else:
        fl["resolution_flags"]["contested"] = False
        fl["resolution_flags"]["possible_reactors"] = []
    lq = out.get("location_query")
    if isinstance(lq, str) and lq.strip():
        fl["needs_mapping"] = True
        mr = fl.get("mapping_request") or ""
        fl["mapping_request"] = (mr + f" Location/system query: {lq.strip()}").strip()
    else:
        out["location_query"] = None

    existing_rooms = set((sc.get("rooms") or {}).keys())
    mv = out.get("movement")
    if isinstance(mv, dict) and mv.get("to_room"):
        if mv["to_room"] not in existing_rooms:
            fl["needs_mapping"] = True
            mr = fl.get("mapping_request") or ""
            extra = (f" Player movement targets new room '{mv['to_room']}' "
                     f"not in scene — generate room description.")
            fl["mapping_request"] = (mr + " " + extra).strip()

    if not (isinstance(mv, dict) and mv.get("to_room")):
        movement_cues = (
            "enter", "step inside", "peer inside", "look inside",
            "go inside", "walk into", "cross threshold",
            "through the door", "step through", "go through",
            "boards", "climbs inside",
        )
        if any(cue in action_texts for cue in movement_cues):
            fl["needs_mapping"] = True
            mr = fl.get("mapping_request") or ""
            extra = (" Player action implies entering/approaching a contained "
                     "space — infer the destination room and generate its description.")
            fl["mapping_request"] = (mr + " " + extra).strip()

    # Broadened world-state mutation detection
    if not fl.get("needs_mapping"):
        input_text = str(ctx.input or "").casefold()
        mutation_text = f"{input_text} {action_texts}"
        mutation_cues = (
            "appears", "materializes", "arrives", "summons", "creates",
            "builds", "opens a portal", "reveals a door", "discovers a room",
            "puts down", "picks up", "hands ", "places ",
            "destroys", "breaks", "collapses", "vanishes", "disappears",
        )
        if any(cue in mutation_text for cue in mutation_cues):
            fl["needs_mapping"] = True
            existing_request = fl.get("mapping_request") or ""
            fl["mapping_request"] = (
                existing_request
                + " Inspect the declaration for new, moved, transferred, "
                  "transformed, opened, destroyed, or contained scene entities "
                  "and propose the minimum scene graph patch."
            ).strip()

    if wget(chat["id"], "pending", []):
        fl["needs_mapping"] = True

    # Carry the due authored events onto the output so director_resolve can
    # enact them, and force mapping when one is due (a scheduled world beat --
    # a crash, an arrival -- may reshape the scene graph).
    out["due_authored_events"] = [e["summary"] for e in _due_authored]
    if _due_authored:
        fl["needs_mapping"] = True

    # Do NOT set ctx["_player_room"] to the declared movement target here.
    # A movement declaration is only a request for director_resolve to
    # validate (it can be blocked by the passable-route check). ctx
    # already holds the player's actual pre-turn room from the resolution
    # above; perception_act (the action-onset pass) must keep using that,
    # not a not-yet-resolved destination — otherwise onset perception
    # treats the player as having already arrived before anyone (the
    # player included) has moved.

    # Interpret's own scope backstop, on the FINAL interpretation -- the
    # same single check resolve runs, pointed at this stage's containers.
    _orchestration_scope_backstop(ctx, out, "interpret")

    return out

# ---------------------------------------------------------------------------
# Interpret reconciliation: the structural TWIN of the resolve seam below,
# run right after director_interpret's LLM call. Where the resolve seam
# catches prose-vs-diff omissions, this one catches INPUT-vs-interpretation
# omissions: a player-declared place/object/event present in the raw input
# but absent from interpret's sequence/movement/mapping channels is a
# dropped declaration -- under the PLAYER AUTHORITY CONTRACT it silently
# never happened, before resolution even began.
#
# Detection is deliberately NOT keyword/verb enumeration of world content
# (the same unwinnable treadmill the resolve seam rejects): it is pure
# LEXICAL COVERAGE -- the raw input is split into declaration units
# (quoted spans + narrative clauses) and each unit's significant tokens
# are checked against every channel that actually carries a declaration
# forward (sequence, movement, mapping_request, location_query,
# generation_requests, private_thought). A unit most of whose tokens
# appear nowhere is a drop, whatever its subject matter.
#
# Disposition mirrors the resolve seam's conservatism: one bounded
# self-repair BY THE DIRECTOR ITSELF (additive only -- existing elements
# and a declared movement are never replaced), deterministic re-check, and
# for anything still uncovered a warn-only fallback that forwards the
# player's VERBATIM clause to mapping as a generation_request (bounded
# additive elaboration: the player owns existence + stated specifics, the
# engine owns only the unstated) -- this engine never fabricates a
# structured act from a heuristic.
# ---------------------------------------------------------------------------



_RECONCILE_INTERPRET_MAX_UNITS = 4
_INTERPRET_COVERAGE_MIN = 0.5

def _decl_tokens(text):
    """Significant tokens of one declaration unit: casefolded alphanumeric
    words, length >= 3, stopwords removed. No domain keyword lists -- pure
    lexical coverage is the anti-treadmill property this seam is built on."""
    tokens = set()
    for tok in re.findall(r"[a-z0-9']+", str(text or "").casefold()):
        tok = tok.strip("'")
        if len(tok) >= 3 and tok not in _ling("_DECL_STOPWORDS"):
            tokens.add(tok)
    return tokens

def _declaration_units(raw_input):
    """Split raw player input into declaration units: quoted spans (each a
    speech declaration) plus narrative clauses split on sentence boundaries
    and coordination. Units with fewer than two significant tokens are
    skipped -- too little signal to judge coverage without false positives
    (the conservative floor)."""
    text = str(raw_input or "")
    units = [m.group(1).strip() for m in _ling("_QUOTED_UNIT_RE").finditer(text)]
    narrative = _ling("_QUOTED_UNIT_RE").sub(" ", text)
    for clause in _ling("_CLAUSE_SPLIT_RE").split(narrative):
        clause = clause.strip(" ,")
        if clause:
            units.append(clause)
    return [u for u in units if len(_decl_tokens(u)) >= 2]

def _interpret_coverage_corpus(out):
    """Token set of every channel that actually carries a declaration
    forward into the turn. Deliberately NOT `notes` -- prose parked in
    notes never enters causality, which is exactly the drop being
    detected."""
    flow = _dict(out.get("flow"))
    pieces = []
    for e in out.get("sequence") or []:
        if not isinstance(e, dict):
            continue
        # `tone` and `observable` are not decorative side channels: they are
        # where interpret carries the player's authored delivery and visible
        # gesture forward.  Omitting them from coverage made reconciliation
        # "repair" a declaration that was already fully represented.  Live
        # (chat 38, turn 125), genuine awe and a teasing smirk were present in
        # the two speech tones and the turn between them was present in the
        # action observable, yet the uncovered-clause check appended a fourth
        # action containing the entire narrative bridge.  Perception then had
        # two competing versions of the same chronology.
        for field in ("text", "attempt", "raw_text", "description",
                      "observable", "tone", "subject", "verb"):
            pieces.append(e.get(field))
        pieces.extend(str(t) for t in (e.get("targets") or []))
        effects = _list(e.get("intended_effects")) + \
            _list(e.get("asserted_effects"))
        for eff in effects:
            if isinstance(eff, dict):
                pieces.append(eff.get("kind"))
                pieces.append(eff.get("target_id"))
                try:
                    pieces.append(json.dumps(eff.get("details") or {},
                                             ensure_ascii=False))
                except (TypeError, ValueError):
                    pass
    mv = out.get("movement")
    if isinstance(mv, dict):
        pieces.append(str(mv.get("to_room") or "").replace("_", " "))
        pieces.append(mv.get("why"))
        pieces.append(str(mv.get("mover") or "").replace("_", " "))
    pieces.append(out.get("private_thought"))
    pieces.append(out.get("location_query"))
    pieces.append(flow.get("mapping_request"))
    for gr in _dict_list(flow.get("generation_requests")):
        pieces.append(gr.get("kind"))
        pieces.append(gr.get("subject"))
        pieces.extend(str(c) for c in (gr.get("constraints") or []))
        pieces.append(str(gr.get("location_id") or "").replace("_", " "))
    tokens = set()
    for piece in pieces:
        tokens |= _decl_tokens(piece)
    return tokens

def _unit_covered(unit, corpus, prefixes):
    """Coverage test for one declaration unit: at least half its
    significant tokens appear in the corpus (exact, or by shared 4-char
    prefix -- crude stemming so 'ducks'/'ducking' covers 'duck')."""
    tokens = _decl_tokens(unit)
    if not tokens:
        return True
    hits = sum(
        1 for t in tokens
        if t in corpus or (len(t) >= 4 and t[:4] in prefixes)
    )
    return hits / len(tokens) >= _INTERPRET_COVERAGE_MIN

def _uncovered_declarations(raw_input, out):
    """Deterministic omission detection: declaration units of the raw input
    whose significant tokens are mostly absent from every channel of the
    interpretation. Capped -- a fully off-the-rails interpretation is
    better re-run than repaired unit by unit."""
    corpus = _interpret_coverage_corpus(out)
    prefixes = {c[:4] for c in corpus if len(c) >= 4}
    uncovered = [
        u for u in _declaration_units(raw_input)
        if not _unit_covered(u, corpus, prefixes)
    ]
    return uncovered[:_RECONCILE_INTERPRET_MAX_UNITS]

def _reconcile_interpretation(ctx, out, sc):
    """The interpret-reconciliation seam (see the block comment above).
    Mutates `out` in place: repaired sequence elements are appended (never
    replacing what interpret already declared), a missing movement may be
    filled (never overwritten), mapping_request/generation_requests are
    extended. Records inspection metadata on out['interpret_reconciliation']
    and appends to ctx.warnings for anything still uncovered."""
    raw_input = str(ctx.get("input") or "")
    fl = _dict(out.get("flow"))
    recon = {"uncovered": [], "repaired": False, "dispositions": [],
             "unresolved": []}
    out["interpret_reconciliation"] = recon
    if not raw_input.strip():
        return

    uncovered = _uncovered_declarations(raw_input, out)
    if not uncovered:
        return
    recon["uncovered"] = list(uncovered)

    # ---- One bounded self-repair by the interpretation's own owner ------
    repair = None
    try:
        repair = _agent_json(
            "director", "interpret_repair",
            get_prompt("interpret_repair", ctx.language),
            {
                "player_raw_input": raw_input,
                "current_interpretation": {
                    "sequence": out.get("sequence") or [],
                    "movement": out.get("movement"),
                    "mapping_request": fl.get("mapping_request") or "",
                    "location_query": out.get("location_query"),
                    "generation_requests":
                        _dict_list(fl.get("generation_requests")),
                },
                "dropped_declarations": uncovered,
                "existing_rooms": sorted((sc.get("rooms") or {}).keys()),
            },
            temperature=0.0, max_tokens=8000,
        )
    except Aborted:
        raise
    except Exception as exc:
        ctx.add_warning(f"Interpret reconciliation repair failed: {exc}")

    if not isinstance(fl.get("generation_requests"), list):
        fl["generation_requests"] = []

    if isinstance(repair, dict):
        additions = {
            "sequence": [e for e in (repair.get("sequence") or [])
                         if isinstance(e, dict)],
        }
        norm_sequence(additions)
        new_elems = assign_event_ids(
            additions["sequence"], f"turn:{ctx.turn.id}:repair")
        if new_elems:
            out["sequence"] = list(out.get("sequence") or []) + new_elems
            _sync_sequence_mirrors(out)
            recon["repaired"] = True
        rmv = repair.get("movement")
        already_moving = isinstance(out.get("movement"), dict) \
            and out["movement"].get("to_room")
        if isinstance(rmv, dict) and rmv.get("to_room") and not already_moving:
            out["movement"] = {
                "to_room": str(rmv["to_room"]),
                "why": str(rmv.get("why") or ""),
                "mover": str(rmv.get("mover") or "self"),
            }
            recon["repaired"] = True
        extra_request = str(repair.get("mapping_request") or "").strip()
        if extra_request:
            fl["mapping_request"] = (
                (fl.get("mapping_request") or "") + " " + extra_request
            ).strip()
        for gr in _dict_list(repair.get("generation_requests")):
            if gr not in fl["generation_requests"]:
                fl["generation_requests"].append(gr)
                recon["repaired"] = True
        recon["dispositions"] = _dict_list(repair.get("dispositions"))

    # The owner explicitly overruled the checker for these units -- believe
    # the rejection rather than warn on a model-vs-checker disagreement
    # (same conservatism as the resolve seam's manifest dispositions).
    already_covered = {
        _norm_subject(d.get("subject"))
        for d in recon["dispositions"]
        if str(d.get("status") or "").casefold() == "already_covered"
    }

    # ---- Deterministic re-check against the merged interpretation -------
    corpus = _interpret_coverage_corpus(out)
    prefixes = {c[:4] for c in corpus if len(c) >= 4}
    for unit in uncovered:
        if _norm_subject(unit) in already_covered:
            continue
        if _unit_covered(unit, corpus, prefixes):
            continue
        # Warn-only fallback: the minimal covering element is the player's
        # VERBATIM clause forwarded to mapping for bounded additive
        # elaboration -- never a fabricated structured act.
        fl["generation_requests"].append({
            "kind": "player_declaration",
            "subject": unit[:240],
            "constraints": [
                "player-declared: existence and stated specifics are fixed",
                "elaborate additively, scoped to the declaration only",
            ],
            "urgency": "now",
        })
        fl["needs_mapping"] = True
        recon["unresolved"].append(unit)
        ctx.add_warning(
            "PLAYER AUTHORITY: declared "
            f"{unit!r} was not captured by director_interpret even after "
            "self-repair; forwarded verbatim to mapping as a generation "
            "request (no structured act was fabricated)."
        )

# ---------------------------------------------------------------------------
# Resolve reconciliation: one general seam catching the recurring failure
# class where director_resolve's resolved_event PROSE asserts a persistent,
# physically consequential change (doors sealed, a passage collapsed, an
# object destroyed, someone restrained) that its structured state_diff
# OMITS -- so commit applies stale objective truth and perception, which
# renders from structured truth rather than prose, contradicts the story
# on the very next turn (live instance: an elevator narrated as sealed and
# descending while the room diff was a blank placeholder, leaving the
# doors objectively "held open" onto the smoke-filled corridor).
#
# Shape of the mechanism, deliberately NOT keyword/verb recognition of
# world events (an unwinnable enumeration treadmill). Three tiers, all
# DETECTION deterministic on the common path (no per-beat LLM call):
#   Tier 0 (deterministic, every beat, zero cost):
#     - blank all-empty placeholder diff entries are pure noise
#       masquerading as a handled change; strip and flag them in code;
#     - the legacy restraint/duress scan (folded in; used to be warn-only
#       and one-off);
#     - PLAYER-CLAIM COVERAGE: every asserted scope='effect' authority
#       claim with a resolvable subject must be encoded somewhere in the
#       diff -- structure minted by director_interpret in a DIFFERENT
#       call, so a resolve-side encoding drop is caught with no same-call
#       self-consistency bias. Null-subject claims degrade to a metadata
#       note, never a warning. The claim_dispositions contract (asserted
#       claims are never rejected/failed) is cross-checked too.
#   Tier 1 (near-zero cost, same call): director_resolve's own
#     changes_asserted manifest -- persistent changes its prose asserts,
#     beyond the player's claims -- checked against the diff with
#     CATEGORY-AWARE evidence classes (an 'adjacency' change needs an
#     adjacency-affecting entry, not merely the subject's name somewhere:
#     the partial-encoding trap that let the elevator through) and
#     ALIAS-AWARE subjects (name/uid/alias via character_scene_keys and
#     entity aliases).
#   Tier 2 (LLM, omission path only): bounded self-repair BY THE DIRECTOR
#     ITSELF (never an external critic writing state): one re-invocation
#     with the specific detected omissions called out, returning a
#     correction delta merged ADDITIVELY over the original diff and
#     re-checked deterministically. Disposition authority is tiered:
#     player-claim omissions are NON-REJECTABLE (honored only when
#     post-merge evidence actually exists) and always warn while
#     unencoded; structural signals warn if unrepaired; manifest
#     (emergent) omissions may be rejected by the owner. Anything still
#     unencoded falls back to ctx.warnings -- this engine never
#     fabricates objective state from a heuristic, because a wrongly
#     invented fact lingering is worse than a stale missing one.
# The standalone resolve_reconcile deep audit is retained behind the
# default-off 'resolve_deep_audit' setting ('1'/'always' = every physical
# beat; 'tripwire' = only when the silent-false-negative tripwire fires:
# successful dice or asserted effect-claims alongside an EMPTY manifest
# and an empty physical diff).
# ---------------------------------------------------------------------------

# Keep the keyword list small and specific so it does not fire on ordinary
# descriptive prose. This is a legacy high-precision detector for one known
# failure (a character held at gunpoint narrated but never written to
# state_diff.conditions); the general omission audit above it is what covers
# the open-ended class.

def _untracked_restraint_subjects(resolved_event, dialogue_log, conditions,
                                  tracked_names):
    """Named, tracked characters whose mention co-occurs with a restraint/
    duress keyword in resolved_event or a dialogue_log exact_quote, but who
    have no matching state_diff.conditions entry (matched by subject_id,
    casefolded). Sorted for deterministic output."""
    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict):
            quote = entry.get("exact_quote")
            if quote:
                text_units.append(str(quote))

    tracked_condition_subjects = set()
    for cond_value in (conditions or {}).values():
        cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
        for c in cond_list:
            if isinstance(c, dict):
                tracked_condition_subjects.add(
                    str(c.get("subject_id") or "").casefold())

    flagged_names = set()
    for text in text_units:
        lower = text.casefold()
        if not any(keyword in lower for keyword in _ling("_RESTRAINT_KEYWORDS")):
            continue
        for name in tracked_names:
            if name and name.casefold() in lower:
                flagged_names.add(name)

    return [name for name in sorted(flagged_names)
            if name.casefold() not in tracked_condition_subjects]

# Consciousness floor (awareness Phase 1). Observed live: an elevator crash
# resolved with the prose narrating the player "unconscious" and "knocked out"
# while state_diff.conditions was null -- so no `awareness` condition was born
# and perception kept handing the unconscious mind a full sighted view for
# turns. High-precision loss-of-consciousness cues, keyed on tracked names, and
# -- unlike the destruction tripwire -- this DOES feed the Tier-2 self-repair:
# an awareness condition is reversible and non-cascading, so a false positive
# costs one degraded beat while a miss is a multi-turn perception-barrier
# breach. HIGH-PRECISION via grammatical-subject attribution (like the
# destruction tripwire): a cue is pinned to the single nearest tracked name in
# the same clause, so a bystander merely co-mentioned with the fallen one ("Dr.
# Moon kneels beside the unconscious anomaly") is never flagged. It is the
# deterministic floor UNDER the broad semantic omission auditor, never the
# mechanism.
# "faint" is a verb and an adjective, and the adjective is far commoner in
# prose. Bare `faints?` matched "a FAINT pulse of rose-gold motes" and, with a
# name five tokens away, told the Director that Elyndra had lost consciousness
# mid-scene -- measured on chat 52's last beat, where she was doing nothing of
# the kind. This scan is the deterministic floor UNDER the semantic auditor, so
# a false positive costs far more than a miss: it instructs the Director to
# knock a character out, and the auditor above it still catches a real faint.
#
# The inflections are unambiguous, and the bare form is admitted only where a
# modal or infinitive marker makes it a verb ("might faint", "about to faint").
# Titles whose trailing period is not a sentence break (so "Dr. Moon" is one
# clause, and "unconscious ... Dr. Moon" across a real "anomaly." break stays
# two clauses).
_MAX_UNCONSCIOUSNESS_GAP = 5  # word tokens between a cue and its subject name


def _sentence_break_positions(low):
    """Offsets in casefolded `low` that terminate a sentence -- a '.', '!',
    '?' or newline -- excluding an abbreviation period (one preceded by a
    short title word in _TITLE_ABBREV). Used as clause barriers so a cue and
    a name on opposite sides of a real break are never paired."""
    breaks = []
    for m in re.finditer(r"[.!?]|\n", low):
        if low[m.start()] == ".":
            wm = re.search(r"([a-z]+)$", low[:m.start()])
            if wm and wm.group(1) in _ling("_TITLE_ABBREV"):
                continue
        breaks.append(m.start())
    return breaks


# The other direction of the consciousness floor above. That one catches a
# knockout the diff FORGOT; this catches a mind the diff took away on nothing.
# Observed live (chat 40 'Hmmm', turn 8): the player wrote "You breath softly as
# you close your eyes wrapping your arms around her", resting against another
# character, and the Director recorded awareness level 'asleep' on the PLAYER
# with cause "settling into rest and protective affection after arrival". Since
# 'asleep' is in NON_AWAKE_GATED the player's own next view became "You are
# under, below waking." -- the scene taken away from them for closing their eyes
# in a cuddle, and only endable by the Director choosing to end it.
#
# The asymmetry that justifies a floor here: for an NPC a spurious non-awake
# level costs one beat of silence, but for the PLAYER it removes both their view
# of the story and their next move, which is the Director overriding declared
# player conduct (AGENTS.md's information/agency boundary) in its strongest
# form. So the player alone is protected, and only against a level that GATES
# ('dazed' is untouched -- present but degraded). Support is read generously and
# from anywhere in the beat, because a false drop must be rarer than the false
# imposition it prevents.


def _awareness_support_in_beat(player_input, resolved_event, dialogue_log):
    """Did anything in this beat actually put the player under?

    Deliberately not subject-attributed, unlike the omission scan: this decides
    whether to KEEP the Director's judgement, so it errs toward keeping. Any
    sleep/knockout language anywhere in the player's own declaration or in the
    beat's prose is enough. What it excludes is the case that went wrong -- a
    beat where nobody said anything about going under at all.
    """
    texts = [str(player_input or ""), str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict) and entry.get("exact_quote"):
            texts.append(str(entry["exact_quote"]))

    return any(_ling("_SLEEP_CUE").search(text.casefold()) for text in texts if text)


def _unsupported_player_awareness(conditions, player_name, player_input,
                                  resolved_event, dialogue_log):
    """Condition keys that gate the PLAYER's mind on no stated basis.

    Returns [(key, level)] for awareness conditions that are ACTIVE, name the
    player as subject, sit at a gated level, and have nothing in the beat
    supporting them. An ending condition (active:0) is never touched -- that is
    the player WAKING, which must always be allowed through.
    """
    if not player_name:
        return []
    if _awareness_support_in_beat(player_input, resolved_event, dialogue_log):
        return []

    target = re.sub(r"[^a-z0-9]", "", str(player_name).casefold())
    if not target:
        return []

    unsupported = []
    for key, cond_value in (conditions or {}).items():
        cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
        for cond in cond_list:
            if not isinstance(cond, dict) or cond.get("kind") != "awareness":
                continue
            try:
                if not int(cond.get("active", 1)):
                    continue  # waking -- always allowed
            except (TypeError, ValueError):
                pass
            subject = re.sub(
                r"[^a-z0-9]", "",
                str(cond.get("subject_id") or "").casefold(),
            )
            if subject != target:
                continue
            level = _normalize_awareness_level(
                (cond.get("state") or {}).get("level")
            )
            if level in NON_AWAKE_GATED:
                unsupported.append((key, level))
                break

    return unsupported


# ---------------------------------------------------------------------------
# WAKING (awareness Phase 1, exit side).
#
# The two floors above police the ONSET of a non-awake state -- one catches a
# knockout the diff forgot, the other catches a mind the diff took away on
# nothing. Neither of them can end one, and until this block nothing else could
# either except the Director choosing to.
#
# Measured against the author's live corpus (engine.db, 1483 director
# resolve/establish variants across 44 chats): 24 `awareness` conditions were
# ever emitted and NOT ONE of them carried `active: 0`. The Director has never
# once ended an awareness condition in real play. The four that ever stopped
# gating stopped because they were born with `expires_at_seconds` and
# mechanics.py's clock expiry closed them; every condition without that field is
# still active, up to 75 turns after it was created. The reported incident is
# the whole class: chat 40 'Hmmm', turn 9 the player declared going to sleep
# (legitimate onset), turn 10 declared "You eventually wake when morning comes",
# turn 11 "You open your eyes and look around" -- and both resolves returned
# state_diff.conditions == {}. Turn 10's own `changes_asserted` said
# "conditions / Hinami / transitions from asleep to awake"; the Tier-1 manifest
# check caught the omission and the Tier-2 self-repair answered
# `already_encoded`, pointing at entities.hinami.state.posture =
# "awake_stirring_in_nest" -- a field nothing reads for awareness. The repair's
# word was taken and the condition stayed on.
#
# Two reasons, and both are fixed here:
#   1. The resolve payload never told the Director that anyone was under, or
#      under which condition_id. It cannot re-emit an id it was never given,
#      and after a context window it cannot remember one either. `_awareness_view`
#      puts the live rows in the payload.
#   2. Nothing deterministic enforced the exit. `_awareness_exits` is that
#      floor, and it covers only the cases where waking is not a judgement call.
#
# Whose call waking is: the WORLD's, never the sleeping mind's. A gated
# character runs no character step at all (agents/character.py's consciousness
# gate), which is correct -- a mind that is out does not deliberate -- but it
# also means an NPC generates no pressure to be woken, so a stuck sleeper reads
# as a quiet one. Every rule below is therefore driven by something outside the
# sleeper: their own player's declaration, another body's hands, or the clock.
_NATURAL_SLEEP_SECONDS = 8 * 3600  # ordinary sleep, on the simulation clock

# A deliberate act of rousing, aimed at a named sleeper. Deliberately narrower
# than "anything loud": attribution is by nearest name in the same clause (the
# `_untracked_unconsciousness_subjects` idiom), which cannot tell "shouts at the
# sleeper" from "shouts across the room the sleeper is in", so shouting/calling
# out is left to the Director rather than made deterministic. Hands on a body,
# or the word "wake" aimed at it, is unambiguous.
# What a PLAYER can say that means "leave me under". `_SLEEP_CUE` plus the
# stayings it does not cover. Kept separate from `_SLEEP_CUE` on purpose:
# that one decides whether to KEEP an onset and errs toward keeping, so
# widening it would make prose more likely to put the player under -- the
# direction the original bug came from.


def _clause_attributed_subjects(text_units, cue_re, subject_names,
                                prefer_object=False):
    """Names from `subject_names` that `cue_re` fires on in the same clause.

    The high-precision attribution `_untracked_unconsciousness_subjects` uses,
    lifted so the rouse scan reads the same way: a cue is pinned to the nearest
    candidate name in the same sentence within `_MAX_UNCONSCIOUSNESS_GAP` word
    tokens, so a bystander merely co-mentioned is never picked up.

    `prefer_object` flips which side of the cue wins, and the two scans need
    opposite answers. An unconsciousness cue is INTRANSITIVE -- "Hinami passes
    out" -- so its subject precedes it. A rouse cue is TRANSITIVE -- "Kaede
    shakes Tamamo awake" -- so the body being woken FOLLOWS it, and the nearest
    name is the waker. With the flag set, a name after the cue wins whenever
    the clause has one, and the preceding name is used only as a fallback ("she
    is shaken awake")."""
    name_res = [(name, re.compile(r"\b" + re.escape(name.casefold()) + r"(?:'s)?\b"))
                for name in subject_names if name]
    if not name_res:
        return set()
    flagged = set()
    for text in text_units:
        low = str(text or "").casefold()
        if not low:
            continue
        name_hits = [(m.start(), m.end(), name)
                     for name, rx in name_res for m in rx.finditer(low)]
        if not name_hits:
            continue
        breaks = _sentence_break_positions(low)
        for cm in cue_re.finditer(low):
            cs, ce = cm.start(), cm.end()
            best = None  # (side_rank, word_gap, name)
            for ns, ne, name in name_hits:
                if ne <= cs:            # name before the cue
                    lo, hi, side = ne, cs, 1 if prefer_object else 0
                elif ns >= ce:          # name after the cue
                    lo, hi, side = ce, ns, 0
                else:                   # overlaps the cue span; skip
                    continue
                if any(lo <= p < hi for p in breaks):
                    continue            # a sentence break separates them
                gap = len(re.findall(r"\w+", low[lo:hi]))
                if gap > _MAX_UNCONSCIOUSNESS_GAP:
                    continue
                if best is None or (side, gap) < best[:2]:
                    best = (side, gap, name)
            if best is not None:
                flagged.add(best[2])
    return flagged


def _declared_act_texts(interp, char_actions):
    """Every declared act in this beat, as text: the player's sequence and each
    character's actions. A rouse is an INTENTION by an agent, so the
    declarations are the primary evidence -- the resolved prose is scanned too,
    but a Director that narrated the shake without encoding it still counts."""
    texts = []
    for event in ((interp or {}).get("sequence") or []):
        if not isinstance(event, dict):
            continue
        texts.append(str(event.get("attempt") or ""))
        texts.append(str(event.get("observable") or ""))
    for _who, acts in (char_actions or {}).items():
        for act in (acts if isinstance(acts, list) else [acts]):
            if isinstance(act, dict):
                texts.append(str(act.get("attempt") or ""))
                texts.append(str(act.get("observable") or ""))
    return [t for t in texts if t]


def _rouse_attempts(interp, char_actions, resolved_event, gated_names):
    """Gated subjects somebody deliberately tried to wake this beat."""
    if not gated_names:
        return set()
    units = _declared_act_texts(interp, char_actions) + [str(resolved_event or "")]
    return _clause_attributed_subjects(units, _ling("_ROUSE_CUE"), gated_names,
                                       prefer_object=True)


def _sleep_elapsed(record, clock, diff_time):
    """Simulation seconds this condition has been in force at the END of this
    beat, or None when the clock cannot say. `started_at_seconds` is
    model-authored, so a negative or absurd span is treated as unknown."""
    end = None
    if isinstance(diff_time, dict):
        for key in ("end_seconds", "start_seconds"):
            try:
                if diff_time.get(key) is not None:
                    end = float(diff_time[key])
                    break
            except (TypeError, ValueError):
                end = None
        if end is not None and diff_time.get("end_seconds") is None:
            try:
                end += float(diff_time.get("duration_seconds") or 0.0)
            except (TypeError, ValueError):
                pass
    if end is None:
        try:
            end = float((clock or {}).get("elapsed_seconds") or 0.0)
        except (TypeError, ValueError):
            return None
    try:
        started = float(record.get("started_at_seconds") or 0.0)
    except (TypeError, ValueError):
        return None
    elapsed = end - started
    return elapsed if elapsed >= 0 else None


def _awareness_view(chat_id, clock, interp, char_actions, sd_time=None):
    """The `active_awareness` block the resolve payload carries.

    The Director has never once ended an awareness condition, and the first
    reason is that it was never shown one. Each entry names the condition_id it
    must re-emit with active:0, what put the subject under, whether someone is
    trying to wake them THIS beat, and whether the clock says an ordinary sleep
    is over."""
    records = awareness_conditions(chat_id)
    if not records:
        return []
    gated = [r for r in records if r["level"] in NON_AWAKE_GATED]
    roused = _rouse_attempts(interp, char_actions, "",
                             [r["subject"] for r in gated])
    view = []
    for record in records:
        elapsed = _sleep_elapsed(record, clock, sd_time)
        view.append({
            "condition_id": record["condition_id"],
            "subject": record["subject"],
            "level": record["level"],
            "cause": record["cause"],
            "rousable_by": record["rousable_by"],
            "gates_this_mind": record["level"] in NON_AWAKE_GATED,
            "under_for_seconds": None if elapsed is None else round(elapsed),
            "natural_wake_due": bool(
                record["level"] == "asleep" and elapsed is not None
                and elapsed >= _NATURAL_SLEEP_SECONDS),
            "someone_is_trying_to_wake_them": record["subject"] in roused,
        })
    return view


def _already_ended(cond_value):
    """Did the diff itself close this condition? Any entry with a falsy
    `active` counts; a re-assertion (active truthy, or absent, which defaults
    to active) does not."""
    for cond in (cond_value if isinstance(cond_value, list) else [cond_value]):
        if not isinstance(cond, dict):
            continue
        try:
            if not int(cond.get("active", 1)):
                return True
        except (TypeError, ValueError):
            continue
    return False


def _ending_condition(record, reason):
    """The same condition, closed. Built from the stored payload so nothing
    authored on it is lost, and keyed by the SAME condition_id -- commit
    UPDATEs on that id, and a fresh one would open a second row."""
    ended = dict(record.get("payload") or {})
    ended["condition_id"] = record["condition_id"]
    ended["subject_id"] = record["subject"]
    ended["kind"] = "awareness"
    ended["active"] = 0
    ended["ended_reason"] = reason
    return ended


def _awareness_exits(chat_id, conditions, player_name, player_input,
                     interp, char_actions, resolved_event, clock, sd_time):
    """Awareness conditions the world has ENDED this beat, whatever the diff says.

    Returns (endings, warnings): endings is {condition_id: [ending_condition]}
    to merge into state_diff.conditions, warnings is prose for ctx.

    Three rules, each driven from outside the sleeping mind, and each covering
    only the part of waking that is not a judgement call:

    1. THE PLAYER DECLARED SOMETHING. Any non-empty player declaration that is
       not itself a request to stay under ends EVERY gated awareness condition
       on the player, at any level. This is the strong rule and it is meant to
       be: the player owns the declaration of their character's conduct
       (AGENTS.md, authority boundaries), the onset floor already refuses to put
       them under without their own input or unmistakable beat prose, and the
       Director keeps every other lever -- it may narrate the attempt failing,
       or impose the condition again with a fresh cause. Being wrong in this
       direction costs one beat the Director can re-narrate. Being wrong in the
       other direction is a chat that cannot be played, which is what the corpus
       actually contains.
    2. SOMEBODY TRIED TO WAKE THEM. A deliberate rouse aimed at a subject who
       is `asleep` ends it -- shaking a shoulder is the world at its least
       ambiguous, and it is the commonest beat in fiction. It does NOT end
       `sedated` or `unconscious`: those bodies do not sit up because they were
       shaken, and the refusal is a fact the Director should narrate, so it
       becomes a warning rather than an ending.
    3. THE NIGHT ENDED. A subject who has been `asleep` for a full ordinary
       sleep on the simulation clock wakes. Only `asleep`: a sedative wearing
       off is dosage, and unconsciousness resolving is medicine -- both belong
       to the Director, which the payload now equips to decide.
    """
    endings, warnings = {}, []
    if not conditions:
        return endings, warnings

    target = re.sub(r"[^a-z0-9]", "", str(player_name or "").casefold())
    gated = [r for r in conditions if r["level"] in NON_AWAKE_GATED]
    if not gated:
        return endings, warnings

    # 1. the player's own declaration
    declared = str(player_input or "").strip()
    player_acts = bool(declared) and not _ling("_STAY_UNDER_CUE").search(declared.casefold())
    if target and player_acts:
        for record in gated:
            subject = re.sub(r"[^a-z0-9]", "", record["subject"].casefold())
            if subject != target:
                continue
            endings[record["condition_id"]] = [
                _ending_condition(record, "player declared conduct while gated")]
            warnings.append(
                f"Ended awareness '{record['level']}' on the player "
                f"({player_name}): they declared conduct this beat, and a "
                "player's declaration of their own character cannot be "
                "overruled by a gate they are given no way to leave. Narrate "
                "the waking, or re-impose the condition with a stated cause. "
                "To stay under deliberately, the player's own input says so "
                "(\"you stay under\", \"you sleep on\", \"you dream of ...\").")

    # 2. somebody deliberately rousing them
    roused = _rouse_attempts(interp, char_actions, resolved_event,
                             [r["subject"] for r in gated])
    for record in gated:
        if record["subject"] not in roused:
            continue
        if record["condition_id"] in endings:
            continue
        if record["level"] == "asleep":
            endings[record["condition_id"]] = [
                _ending_condition(record, "roused by another character")]
            warnings.append(
                f"Ended awareness 'asleep' on {record['subject']}: someone "
                "deliberately woke them this beat and the diff did not record "
                "it. A rouse aimed at a sleeper works.")
        else:
            warnings.append(
                f"A rouse was aimed at {record['subject']}, who is "
                f"'{record['level']}' -- not sleeping. They do not wake from "
                "being shaken, and the resolved_event should say so as a fact "
                "rather than leave the attempt unanswered.")

    # 3. the clock
    for record in gated:
        if record["condition_id"] in endings or record["level"] != "asleep":
            continue
        elapsed = _sleep_elapsed(record, clock, sd_time)
        if elapsed is None or elapsed < _NATURAL_SLEEP_SECONDS:
            continue
        endings[record["condition_id"]] = [
            _ending_condition(record, "a full night's sleep elapsed")]
        warnings.append(
            f"Ended awareness 'asleep' on {record['subject']}: "
            f"{round(elapsed / 3600.0, 1)}h of simulation time have passed "
            "since they went under, which is a full sleep. Nothing else in the "
            "engine wakes a sleeper, so an unended sleep is permanent.")

    return endings, warnings


def _untracked_unconsciousness_subjects(resolved_event, dialogue_log, conditions,
                                        tracked_names):
    """Named, tracked characters narrated as losing consciousness with no
    matching `awareness` condition in the diff. Each cue is attributed to a
    SINGLE subject -- the nearest tracked name in the same sentence within
    _MAX_UNCONSCIOUSNESS_GAP words -- so a bystander merely co-mentioned with
    the fallen one is never flagged. Presence check is specific to
    kind:'awareness'; an unrelated wound/restraint condition on the same
    subject must not suppress the awareness flag."""
    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict) and entry.get("exact_quote"):
            text_units.append(str(entry["exact_quote"]))

    aware_subjects = set()
    for cond_value in (conditions or {}).values():
        for c in (cond_value if isinstance(cond_value, list) else [cond_value]):
            if isinstance(c, dict) and c.get("kind") == "awareness":
                aware_subjects.add(str(c.get("subject_id") or "").casefold())

    flagged = _clause_attributed_subjects(
        text_units, _ling("_UNCONSCIOUSNESS_CUE"), tracked_names)
    return [n for n in sorted(flagged) if n.casefold() not in aware_subjects]

# Destruction tripwire (movement/space Phase 3b follow-up). Observed live:
# the resolved_event narrated a whole-town firestorm consuming a named
# region ward by ward, yet state_diff.destruction was null and remove_rooms
# empty -- so the Phase-3b cascade (which only realizes a DECLARED
# destruction) never fired and the town stayed objectively intact against
# the prose. Same design constraints as the restraint scan: deterministic,
# HIGH-PRECISION, and WARN-ONLY -- this engine never fabricates objective
# state from a heuristic, and a wrongly-invented razing (books retired,
# rooms gone, news minted) would be far worse than a stale-missing one, so
# this detector deliberately does NOT feed the Tier-2 self-repair path.
#
# Precision guard: a bare keyword scan ("the fire spread") or even
# sentence-level co-occurrence ("the letter was destroyed in the hall"
# flagging the hall) false-fires on ordinary flavor. Matching is keyed on
# ACTUAL known place names (scene rooms, the scene location, interior-
# bearing entities, live lorebook names) in destruction-shaped grammatical
# positions only:
#   subject-first:  "<name> ... was razed / burned down / in ruins"
#   verb-object:    "razed/consumed/destroyed (the) <name>"
#   of-phrase:      "ruins/ashes/nothing left of <name>"

def _destruction_name_pattern(name_cf):
    """One compiled pattern per known place name covering the three
    destruction-shaped positions above. Bounded word-gaps, not free
    sentence co-occurrence.

    The name boundary is script-aware and the gaps allow an unspaced run:
    `\\b` never fires against a Japanese particle, and `\\s+` between a cue and
    a name assumes words are spaced, so all three positions were dead in
    Japanese. The English genitive and determiners stay OPTIONAL rather than
    being removed -- a Japanese story still carries them through
    code-switching and imported names.
    """
    name = name_boundary_pattern(name_cf)
    gap = r"[,\s]*"
    return re.compile(
        rf"{name}(?:'s)?{gap}(?:\S+\s+){{0,4}}?{_ling("_DESTRUCTION_TERMINAL_CUES")}"
        rf"|{_ling("_DESTRUCTION_VERB_OBJECT")}{gap}"
        rf"(?:the\s+|all\s+of\s+|the\s+whole\s+|the\s+entire\s+|most\s+of\s+)?"
        rf"{name}"
        rf"|{_ling("_DESTRUCTION_OF_PHRASE")}{gap}(?:the\s+)?{name}"
    )

def _narrated_destruction_subjects(resolved_event, dialogue_log, sd, sc,
                                   extra_names=()):
    """Named, KNOWN places (scene rooms, the scene location, interior-
    bearing entities, plus extra_names -- live lorebook names) that the
    prose asserts destroyed while the diff encodes neither
    state_diff.destruction nor a remove_rooms/remove_entities entry
    covering them. Sorted labels for deterministic output.

    Any declared destruction this beat suppresses the whole scan: scoping
    what the cascade covers is commit's job, not a text heuristic's.
    """
    destruction = sd.get("destruction")
    if isinstance(destruction, dict) and destruction.get("target_id"):
        return []

    candidates = {}

    def _add(label, room_ids=(), entity_ids=()):
        label = str(label or "").strip()
        if len(label) < 3:
            return
        key = label.casefold()
        cand = candidates.setdefault(key, {
            "label": label, "room_ids": set(), "entity_ids": set(),
            "pattern": _destruction_name_pattern(key),
        })
        # Prefer a display-cased label (room "name") over a lowercased
        # id-derived one for the same key -- it names the warning.
        if cand["label"].islower() and not label.islower():
            cand["label"] = label
        cand["room_ids"].update(room_ids)
        cand["entity_ids"].update(entity_ids)

    for rid, room in (sc.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        _add(str(rid).replace("_", " "), room_ids={str(rid)})
        _add(room.get("name"), room_ids={str(rid)})
    location = str(sc.get("location") or "").strip()
    if location:
        _add(location)
        _add(re.split(r"[,—]", location)[0])
    for eid, ent in (sc.get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        kind = str(ent.get("kind") or "").casefold()
        if not (ent.get("interior_rooms")
                or kind in ("vehicle", "building", "structure")):
            continue
        _add(ent.get("name"), entity_ids={str(eid)})
        _add(str(eid).replace("_", " "), entity_ids={str(eid)})
        for alias in (ent.get("aliases") or []):
            _add(alias, entity_ids={str(eid)})
    for name in extra_names:
        _add(name)

    removed_rooms = {str(r) for r in (sd.get("remove_rooms") or [])}
    removed_entities = {str(e).casefold()
                        for e in (sd.get("remove_entities") or [])}

    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict) and entry.get("exact_quote"):
            text_units.append(str(entry["exact_quote"]))

    flagged = {}
    for text in text_units:
        lower = text.casefold()
        for key, cand in candidates.items():
            if key in flagged:
                continue
            if not cand["pattern"].search(lower):
                continue
            if cand["room_ids"] & removed_rooms:
                continue
            if {e.casefold() for e in cand["entity_ids"]} & removed_entities:
                continue
            flagged[key] = cand["label"]
    return [flagged[key] for key in sorted(flagged)]

def _scan_for_untracked_restraint(resolved_event, dialogue_log, conditions,
                                   tracked_names):
    """Return warning strings for the subjects _untracked_restraint_subjects
    flags. Kept as a stable, directly-testable entry point; director_resolve
    now routes these through the reconciliation seam (which may repair the
    diff first) and emits this exact text only for what remains unencoded.
    """
    return [
        f"Possible untracked physical restraint/duress detected for "
        f"{name!r} (restraint/duress keyword found alongside their "
        "name in resolved_event or dialogue) but no matching "
        "state_diff.conditions entry was recorded this beat."
        for name in _untracked_restraint_subjects(
            resolved_event, dialogue_log, conditions, tracked_names)
    ]

def _output_field_names():
    """Every top-level key the Director's own output shapes declare.

    SOURCED FROM THE SCHEMAS, never hand-listed: the whole failure being
    guarded is a model nesting one of these keys inside `rooms`, so a list
    that can drift out of step with the real shape would go stale exactly
    when a new field started leaking.
    """
    models = [getattr(schemas, "StateDiff", None)]
    # Every Director-side stage, INCLUDING the specialists -- `resolved_events`
    # is a specialist echo field and was one of the two that actually leaked.
    models += [cls for key, cls in (getattr(schemas, "SCHEMA_MAP", {}) or {}
                                    ).items() if key.startswith("director_")]
    names = set()
    for cls in models:
        fields = getattr(cls, "model_fields", None) or getattr(
            cls, "__fields__", None) or {}
        names.update(str(f).casefold() for f in fields)
    # Container names that ARE legitimate diff keys are not room ids either,
    # but they are already handled above; what matters here is that a room
    # can never be called one of these.
    return frozenset(names)


_OUTPUT_FIELD_NAMES = _output_field_names()


def _normalize_diff_shape(sd):
    """Coerce a state_diff (from the main resolve output or a repair delta)
    to the canonical container shapes every downstream reader assumes.
    Safety net for the LLM returning a string/list where an object belongs."""
    if not isinstance(sd, dict):
        sd = {}
    for k in ("positions", "stations", "poses", "rooms", "entities", "overlays", "attire",
              "conditions", "scales", "containment", "vitals"):
        if not isinstance(sd.get(k), dict):
            sd[k] = {}
    for k in ("cast_changes", "world_facts", "introductions", "following_ops",
              "remove_entities", "remove_rooms", "remove_adjacent",
              "inventory_ops", "contact_ops", "substance_ops", "claim_dispositions",
              "consequences", "offscreen_plan_ops", "crowd_ops",
              "telling_ops"):
        if not isinstance(sd.get(k), list):
            sd[k] = []
    # A SCHEMA FIELD NAME IS NOT A ROOM. Live, chat 72 turn 44: `rooms` came
    # back carrying `resolved_events` and `notes` alongside two real rooms,
    # and the coercion above dutifully made each a room dict. That story's
    # map now has a blank-named room called `resolved_events` adjacent to
    # the hotel lobby, and every route query walks through it.
    #
    # These are not typos, they are keys from the output shape the model was
    # just asked to produce -- an ordinary nesting slip, and one the engine
    # can recognise for certain: no fiction names a room after a JSON key.
    # Whole-id match only, so a genuine `notes_office` survives. Rooms are
    # the only container this applies to; elsewhere the key is a body or an
    # object name where a collision means nothing.
    rooms = sd.get("rooms")
    if isinstance(rooms, dict):
        for _key in [k for k in rooms if str(k).strip().casefold()
                     in _OUTPUT_FIELD_NAMES]:
            rooms.pop(_key, None)
    sd.setdefault("time", None)
    return sd


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
    from spatial import apply_following_ops

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


def _is_blank_placeholder(entry):
    """True when a diff entry encodes nothing at all -- every field an empty
    string/list/dict or zero (e.g. {"name":"","desc":"","adjacent":[],
    "notes":""}, observed live as an elevator room's entire 'change'). Such
    an entry commits as if the change were handled while changing nothing:
    pure noise, and a cheap deterministic divergence signal."""
    if not isinstance(entry, dict):
        return False
    for value in entry.values():
        if isinstance(value, (dict, list)):
            if value:
                return False
        elif isinstance(value, bool):
            if value:
                return False
        elif isinstance(value, (int, float)):
            if value:
                return False
        elif str(value or "").strip():
            return False
    return True

def _strip_blank_diff_placeholders(sd):
    """Remove empty-placeholder entries from the diff's keyed containers and
    return one structural divergence signal per stripped key. Runs on both
    the original diff and any repair delta (a repair may not reintroduce
    noise). conditions values are lists of condition dicts; a key whose list
    is empty or all-blank is the same noise in that shape."""
    signals = []

    def flag(category, subject, field):
        signals.append({
            "category": category, "subject": str(subject),
            "change": (f"state_diff.{field}[{subject!r}] was an empty "
                       "placeholder encoding no change at all"),
            "evidence": "", "source": "structural",
        })

    for field, category in (("rooms", "rooms"), ("entities", "entities"),
                            ("attire", "attire"), ("poses", "poses")):
        table = sd.get(field)
        if not isinstance(table, dict):
            continue
        for key in [k for k, v in table.items() if _is_blank_placeholder(v)]:
            table.pop(key)
            flag(category, key, field)

    conditions = sd.get("conditions")
    if isinstance(conditions, dict):
        for key in list(conditions.keys()):
            value = conditions[key]
            entries = value if isinstance(value, list) else [value]
            if all(_is_blank_placeholder(e) or e is None for e in entries):
                conditions.pop(key)
                flag("conditions", key, "conditions")

    positions = sd.get("positions")
    if isinstance(positions, dict):
        for key in [k for k, v in positions.items()
                    if not str(v or "").strip()]:
            positions.pop(key)
            flag("positions", key, "positions")

    return signals

def _diff_is_substantive(sd):
    """True when the diff asserts any physical change at all (post-strip)."""
    for key in ("rooms", "entities", "conditions", "attire", "overlays",
                "positions", "poses", "remove_entities", "remove_rooms",
                "remove_adjacent", "inventory_ops", "contact_ops",
                "substance_ops", "cast_changes"):
        if sd.get(key):
            return True
    return False

def _beat_has_physical_activity(interp, char_actions, dice):
    """Deterministic gate input: did anyone attempt a physical act this
    beat? Structural only (sequence element types, movement, dice) -- no
    prose keyword matching."""
    mv = interp.get("movement")
    if isinstance(mv, dict) and mv.get("to_room"):
        return True
    if dice or char_actions:
        return True
    sequences = [interp.get("sequence") or []]
    for entry in (interp.get("other_players") or {}).values():
        if isinstance(entry, dict):
            sequences.append(entry.get("sequence") or [])
    for seq in sequences:
        for e in seq:
            if isinstance(e, dict) and e.get("type") == "action" \
                    and e.get("attempt"):
                return True
    return False

def _reconcile_scene_slice(sc, cast, p_room, sd):
    """Compact prior-scene payload for the audit/repair calls: occupied and
    diff-touched rooms plus immediate neighbors (same trimming rationale as
    _contextual_rooms everywhere else), full positions/entities."""
    extra = [p_room] + list((sd.get("rooms") or {}).keys())
    return {
        "rooms": _contextual_rooms(sc, cast, *extra),
        "positions": sc.get("positions") or {},
        "entities": sc.get("entities") or {},
        "poses": sc.get("poses") or {},
        "substances": sc.get("substances") or [],
    }

def _merge_repair_into_diff(sd, patch):
    """Additively merge the Director's correction delta into the original
    state_diff. Conservative contract: a repair may ADD or refine encodings
    but can never silently delete what the original diff already asserted.
    Rooms merge edge-aware (spatial._merge_room, upsert by 'to'); the other
    keyed containers upsert per key, except positions which are add-only --
    the original diff's positions include the deterministically validated
    player move (passable-route check) and must stand. List categories
    union with dedup; time fills only if the original had none."""
    for room_id, incoming in (patch.get("rooms") or {}).items():
        if not isinstance(incoming, dict):
            continue
        existing = sd["rooms"].get(room_id)
        sd["rooms"][room_id] = (
            _merge_room(existing, incoming, room_id)
            if isinstance(existing, dict) else incoming
        )
    # Entities merge field-aware for the same reason rooms merge edge-aware:
    # both sides here are partial, so an absent field is silence rather than
    # an erasure (see spatial._merge_entity).
    for key, incoming in (patch.get("entities") or {}).items():
        existing = sd["entities"].get(key)
        sd["entities"][key] = (
            _merge_entity(key, existing, incoming)
            if isinstance(existing, dict) and isinstance(incoming, dict)
            else incoming
        )
    for field in ("attire", "overlays"):
        for key, incoming in (patch.get(field) or {}).items():
            sd[field][key] = incoming
    for key, incoming in (patch.get("conditions") or {}).items():
        incoming_list = incoming if isinstance(incoming, list) else [incoming]
        incoming_list = [c for c in incoming_list if isinstance(c, dict)]
        existing = sd["conditions"].get(key)
        if isinstance(existing, list):
            existing.extend(c for c in incoming_list if c not in existing)
        else:
            sd["conditions"][key] = incoming_list
    for key, room in (patch.get("positions") or {}).items():
        sd["positions"].setdefault(key, room)
    for key, pose in (patch.get("poses") or {}).items():
        sd["poses"].setdefault(key, pose)
    # Stations add-only for the positions/poses reason: the original diff's
    # stations stand, and a partial per-entity update must never be filled
    # out with defaults that clobber the standing roster (see AGENTS.md's
    # stations row). Before this, a repair delta's stations were silently
    # dropped on the floor.
    for key, station in (patch.get("stations") or {}).items():
        sd.setdefault("stations", {}).setdefault(key, station)
    for field in ("remove_entities", "remove_rooms", "remove_adjacent",
                  "inventory_ops", "contact_ops", "substance_ops", "cast_changes", "world_facts",
                  "introductions"):
        for item in (patch.get(field) or []):
            if item not in sd[field]:
                sd[field].append(item)
    if sd.get("time") is None and patch.get("time") is not None:
        sd["time"] = patch["time"]
    return sd

def _norm_subject(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())

def _claim_subject_is_referrable(subject, forms, sc, player_input):
    """Can anyone point at what this claim is about?

    Two independent channels, either of which qualifies (see the block
    comment at the call site for the live case that made this necessary):

      * THE WORLD KNOWS IT -- `_subject_match_forms` found more than the
        bare string it was handed, meaning the subject matched a cast
        member's scene keys or an entity's ids and aliases, or the subject
        names a room in the scene.
      * THE PLAYER SAID IT -- the subject's words appear in what the player
        typed. This is the channel that keeps "I shatter the vault door" a
        real claim about a door no scene contains yet, which is exactly
        what player authority exists to do.

    Normalized to letters and digits on both sides, so `vault_door` matches
    "the vault door" and casing and punctuation cannot decide it. Fails
    open: anything this cannot evaluate is referrable, because refusing a
    claim is the direction that costs the player their authority.
    """
    normalized = _norm_subject(subject)
    if not normalized:
        return False
    if len(forms or []) > 1:
        return True
    rooms = ((sc or {}).get("rooms") or {})
    room_forms = set(rooms)
    for rid, room in rooms.items():
        if isinstance(room, dict) and room.get("name"):
            room_forms.add(str(room["name"]))
    if any(_norm_subject(r) == normalized for r in room_forms):
        return True
    return normalized in _norm_subject(player_input)


def _subject_match_forms(subject, cast, sc):
    """Every identity form an omission subject may legitimately appear under
    in the diff: the subject itself, plus -- when it names a registered cast
    member -- all of that character's scene keys (name/uid/aliases via
    character_scene_keys), plus -- when it names a known scene entity -- that
    entity's id, name, and aliases. Closes the aliasing hole where a repair
    encodes under 'tenth_doctor' what the manifest called 'The Doctor'."""
    subject = str(subject or "").strip()
    forms = {subject} if subject else set()
    subject_cf = subject.casefold()
    if not subject_cf:
        return []
    for row in cast or []:
        try:
            keys = character_scene_keys(json.loads(row["sheet"]))
        except Exception:
            continue
        if subject_cf in {k.casefold() for k in keys}:
            forms.update(keys)
    for eid, ent in ((sc or {}).get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        names = {str(eid)} | {str(ent.get("name") or "")} \
            | {str(a) for a in (ent.get("aliases") or [])}
        names = {n for n in names if n.strip()}
        if subject_cf in {n.casefold() for n in names}:
            forms.update(names)
    return [f for f in forms if f.strip()]

def _make_subject_hit(subject, forms=None):
    """A predicate testing whether a diff value references the subject under
    any of its identity forms (normalized, substring-tolerant so 'elevator'
    matches 'elevator_interior' -- but only for forms long enough not to
    false-match short generic fragments like 'hall' in 'smokehallway')."""
    targets = {_norm_subject(f) for f in ([subject] + list(forms or []))}
    targets = {t for t in targets if t}

    def hits(value):
        norm = _norm_subject(value)
        if not norm:
            return False
        for target in targets:
            if norm == target:
                return True
            shorter, longer = sorted((norm, target), key=len)
            if len(shorter) >= 5 and shorter in longer:
                return True
        return False

    return hits if targets else (lambda value: False)

def _omission_subject_encoded(sd, subject, forms=None):
    """Deterministic containment check: does ANY diff field reference this
    subject (under any identity form)? Intentionally shallow -- it verifies
    the diff addressed the subject at all, not that the encoding is
    semantically right; the Director owns the semantics. Category-agnostic
    fallback; _evidence_present is the category-aware form."""
    hits = _make_subject_hit(subject, forms)

    for field in ("rooms", "entities", "attire", "positions", "poses"):
        for key, value in (sd.get(field) or {}).items():
            if hits(key):
                return True
            if isinstance(value, dict) and hits(value.get("name")):
                return True
    for cond_value in (sd.get("conditions") or {}).values():
        cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
        for c in cond_list:
            if isinstance(c, dict) and (hits(c.get("subject_id"))
                                        or hits(c.get("condition_id"))):
                return True
    for item in (sd.get("remove_entities") or []) + (sd.get("remove_rooms") or []):
        if hits(item):
            return True
    for edge in (sd.get("remove_adjacent") or []):
        if isinstance(edge, dict) and (hits(edge.get("room"))
                                       or hits(edge.get("to"))):
            return True
    for chg in (sd.get("cast_changes") or []):
        if isinstance(chg, dict) and hits(chg.get("who")):
            return True
    for op in (sd.get("inventory_ops") or []):
        if isinstance(op, dict) and (hits(op.get("object_id"))
                                     or hits(op.get("from_id"))
                                     or hits(op.get("to_id"))):
            return True
    for op in (sd.get("contact_ops") or []):
        if not isinstance(op, dict):
            continue
        if hits(op.get("actor")) or hits(op.get("target")):
            return True
        if _norm_subject(subject) in ("contact", "contacts"):
            return True
    for op in (sd.get("substance_ops") or []):
        if not isinstance(op, dict):
            continue
        if (hits(op.get("source")) or hits(op.get("target"))
                or hits(op.get("substance"))):
            return True
        if _norm_subject(subject) in ("substance", "substances", "material"):
            return True
    return False

# Category synonyms a model may plausibly write in a manifest entry, folded
# onto the canonical evidence-class names.

def _normalize_omission_category(category):
    cat = str(category or "").strip().casefold()
    return _ling("_OMISSION_CATEGORY_ALIASES").get(cat, cat) or "other"

def _entity_state_has_transit(entity_def):
    state = entity_def.get("state") if isinstance(entity_def, dict) else None
    return isinstance(state, dict) and ("transit" in state or "link" in state)

def _evidence_present(sd, omission, forms=None):
    """CATEGORY-AWARE evidence check: is the omission's subject touched in
    the RIGHT dimension of the diff, not merely mentioned somewhere? This is
    what closes the partial-encoding trap -- a room whose desc was updated
    but whose narrated adjacency change was dropped passes bare containment
    yet fails the 'adjacency' evidence class. Unknown/other categories fall
    back to the shallow containment check."""
    category = _normalize_omission_category(omission.get("category"))
    subject = omission.get("subject")
    hits = _make_subject_hit(subject, forms)

    def room_hit_with_adjacency():
        for key, rd in (sd.get("rooms") or {}).items():
            if (hits(key) or (isinstance(rd, dict) and hits(rd.get("name")))) \
                    and isinstance(rd, dict) and rd.get("adjacent"):
                return True
        return False

    def removal_edge_hit():
        for edge in (sd.get("remove_adjacent") or []):
            if isinstance(edge, dict) and (hits(edge.get("room"))
                                           or hits(edge.get("to"))):
                return True
        return False

    def entity_transit_hit():
        for eid, ed in (sd.get("entities") or {}).items():
            named = hits(eid) or (isinstance(ed, dict) and (
                hits(ed.get("name"))
                or any(hits(a) for a in (ed.get("aliases") or []))))
            if named and _entity_state_has_transit(ed):
                return True
        return False

    if category == "time":
        return sd.get("time") is not None
    if category == "stations":
        # Sixteen resolves across the database asserted a station change in
        # changes_asserted and encoded it nowhere, and the shallow containment
        # fallback marked every one of them covered. Moving to a different
        # ROOM counts too: that is a position change, and it carries the
        # within-room one with it.
        return any(hits(k) for k in (sd.get("stations") or {})) \
            or any(hits(k) for k in (sd.get("positions") or {}))
    if category == "poses":
        return any(hits(k) for k in (sd.get("poses") or {}))
    if category in ("adjacency", "transit"):
        if room_hit_with_adjacency() or removal_edge_hit() \
                or entity_transit_hit():
            return True
        if category == "transit":
            # An arrival encodes as the entity's own position change.
            return any(hits(k) for k in (sd.get("positions") or {}))
        return False
    if category == "rooms":
        for key, rd in (sd.get("rooms") or {}).items():
            if hits(key) or (isinstance(rd, dict) and hits(rd.get("name"))):
                return True
        return any(hits(r) for r in (sd.get("remove_rooms") or []))
    if category == "positions":
        if any(hits(k) for k in (sd.get("positions") or {})):
            return True
        # A within-room placement is a change the model files under
        # 'positions' ("dropped from the platform edge to the stone floor")
        # while the diff legitimately encodes it as a STATION -- the room is
        # unchanged, so sd.positions is rightly silent. Live case: chat 71
        # turn 2354 v26634 carried stations {"lightweight travel jacket":
        # {at: null}} plus an inventory transfer and the entity's own state,
        # and this class reported the jacket unencoded anyway, which fed a
        # false repair and a false staleness warning. The mirror of the
        # stations class above accepting a positions hit.
        if any(hits(k) for k in (sd.get("stations") or {})):
            return True
        return any(isinstance(c, dict) and hits(c.get("who"))
                   for c in (sd.get("cast_changes") or []))
    if category == "entities":
        for eid, ed in (sd.get("entities") or {}).items():
            if hits(eid) or (isinstance(ed, dict) and (
                    hits(ed.get("name"))
                    or any(hits(a) for a in (ed.get("aliases") or [])))):
                return True
        return any(hits(e) for e in (sd.get("remove_entities") or []))
    if category == "conditions":
        # Any conditions entry for the subject counts, INCLUDING an ending
        # one (active:0 / expires_at set) -- 'the fire burns out' is encoded
        # by expiry, not by neglect.
        for key, cond_value in (sd.get("conditions") or {}).items():
            cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
            if hits(key):
                return True
            for c in cond_list:
                if isinstance(c, dict) and (hits(c.get("subject_id"))
                                            or hits(c.get("condition_id"))):
                    return True
        return False
    if category == "attire":
        # The channel is keyed by WEARER; the manifest subject is worded
        # freely and is at least as often the GARMENT ("lightweight travel
        # jacket" -- chat 71 turn 2354 v26625, where attire.Hinami.remove
        # carried exactly that garment and this class reported it unencoded,
        # because it read only the wearer keys). Both spellings of the same
        # change must count, so the garment handles inside each wearer's
        # entry are checked too.
        for wearer, entry in (sd.get("attire") or {}).items():
            if hits(wearer):
                return True
            if not isinstance(entry, dict):
                continue
            for field in ("add", "remove"):
                for garment in entry.get(field) or []:
                    if isinstance(garment, dict):
                        garment = garment.get("name") \
                            or garment.get("garment")
                    if hits(garment):
                        return True
            for garment in list(entry.get("conditions") or {}) \
                    + list(entry.get("coverage") or {}):
                if hits(garment):
                    return True
        return False
    if category == "contacts":
        manifest_actor = str(omission.get("actor") or "").strip()
        manifest_actor_part = str(omission.get("actor_part") or "").strip()
        manifest_target = str(omission.get("target") or "").strip()
        manifest_target_part = str(omission.get("target_part") or "").strip()
        has_manifest_endpoints = bool(manifest_actor and manifest_target)
        change = str(omission.get("change") or "").casefold()
        subject_is_ledger = _norm_subject(subject) in ("contact", "contacts")

        def endpoint_matches(op):
            """Does this op encode this exact manifested contact relation?

            New outputs carry structured endpoints. Saved/weak outputs may not;
            for those, require at least one op-specific part/manner phrase in the
            manifest prose whenever the op supplies one. That conservative
            fallback may request an idempotent repair for an underspecified
            manifest, but it cannot let an unrelated contact silently stand in
            for the asserted one.
            """
            if has_manifest_endpoints:
                if not (_make_subject_hit(manifest_actor)(op.get("actor"))
                        and _make_subject_hit(manifest_target)(op.get("target"))):
                    return False
                if manifest_actor_part and _norm_subject(
                        manifest_actor_part) != _norm_subject(op.get("actor_part")):
                    return False
                if manifest_target_part:
                    part = _norm_subject(manifest_target_part)
                    # A 'cross' op relocates a standing endpoint: the ENDED
                    # contact lives in crossed_target_part, the new one in
                    # target_part, and one op encodes both halves of the
                    # transition -- the repair sheet itself prescribes it.
                    # Comparing manifests against target_part alone made the
                    # ended half uncoverable by the very op that ends it
                    # (chat 71 turn 2354 v26643).
                    if part != _norm_subject(op.get("target_part")) \
                            and part != _norm_subject(
                                op.get("crossed_target_part")):
                        return False
                return True

            if subject_is_ledger:
                return True
            discriminators = [
                str(op.get(field) or "").strip().casefold()
                for field in ("actor_part", "target_part", "manner")
                if str(op.get(field) or "").strip()
            ]
            if not discriminators:
                return True
            return any(re.search(r"\b%s\b" % re.escape(term), change)
                       for term in discriminators)

        for op in (sd.get("contact_ops") or []):
            if not isinstance(op, dict):
                continue
            # The subject gate exists for manifests with NO structured
            # endpoints, where the free-text subject is all there is to
            # anchor on. When the manifest carries endpoints, they ARE the
            # subject and endpoint_matches is the whole (stricter) test --
            # demanding the free-text subject ALSO name a participant made
            # coverage depend on wording: 'Elyra hand on Hinami stomach
            # ends' passed while 'contact_end' and 'prior hand-to-stomach
            # contact' failed against the identical ops, reroll to reroll
            # on one live beat (chat 71 turn 2354).
            if (subject_is_ledger or has_manifest_endpoints
                    or hits(op.get("actor")) or hits(op.get("target"))) \
                    and endpoint_matches(op):
                return True
        return False
    if category == "substances":
        manifested_substance = str(omission.get("substance") or "").strip()
        manifested_placement = str(omission.get("placement") or "").strip()
        manifested_target = str(omission.get("target") or "").strip()
        manifested_interior = str(
            omission.get("target_interior") or "").strip()
        subject_is_ledger = _norm_subject(subject) in (
            "substance", "substances", "material")
        for op in (sd.get("substance_ops") or []):
            if not isinstance(op, dict):
                continue
            if not (subject_is_ledger or hits(op.get("source"))
                    or hits(op.get("target")) or hits(op.get("substance"))):
                continue
            if manifested_substance and _norm_subject(
                    manifested_substance) != _norm_subject(op.get("substance")):
                continue
            if manifested_target and not _make_subject_hit(
                    manifested_target)(op.get("target")):
                continue
            if manifested_placement and _norm_subject(
                    manifested_placement) != _norm_subject(op.get("placement")):
                continue
            if manifested_interior and _norm_subject(
                    manifested_interior) != _norm_subject(
                        op.get("target_interior")):
                continue
            return True
        return False
    if category == "inventory":
        return any(
            isinstance(op, dict) and (hits(op.get("object_id"))
                                      or hits(op.get("from_id"))
                                      or hits(op.get("to_id")))
            for op in (sd.get("inventory_ops") or [])
        )
    if category == "cast_changes":
        if any(isinstance(c, dict) and hits(c.get("who"))
               for c in (sd.get("cast_changes") or [])):
            return True
        return any(hits(k) for k in (sd.get("positions") or {}))
    return _omission_subject_encoded(sd, subject, forms)

# At most one deep audit + one self-repair per director_resolve execution.
# A rerun of the stage naturally re-runs the seam once -- there is no
# cross-turn or cross-variant accumulation to double-charge.
_RECONCILE_MAX_MANIFEST_ITEMS = 8
_RECONCILE_MAX_AUDIT_OMISSIONS = 6
_RECONCILE_MIN_CONFIDENCE = 0.4

def fanout_is_parallel():
    """Whether the Director's specialists run at once (default) or in turn.

    PARALLEL IS THE DEFAULT and is what the fan-out is for: the specialists
    are handed disjoint channels of the same finished beat, so they have
    nothing to say to each other and the beat's cost is its slowest hand
    rather than the sum of them.

    Sequential exists because concurrency is not free everywhere -- a
    provider with a one-request-at-a-time key, a rate limit measured in
    concurrent connections, a local runtime serving one model on one GPU.
    Under those, parallel dispatch does not go faster and can fail. It is
    NOT a fallback to the monolith: the same specialists run with the same
    scopes, assembled in the same canonical order, and a beat still
    dispatches a mean 1.75 of 6 hands carrying 1-4k sheets. Sequential
    fan-out is expected to beat the single ~21k-token sheet it replaced;
    parallel simply beats it by more.
    """
    value = str(get_setting("director_fanout_mode") or "").strip().casefold()
    return value not in ("sequential", "serial", "one_at_a_time")


def _deep_audit_mode():
    """The default-off standalone resolve_reconcile audit: 'off' (default),
    'always' (every physical beat -- the pre-manifest behavior, kept as a
    belt-and-suspenders option), or 'tripwire' (only when the silent-false-
    negative tripwire fires)."""
    value = str(get_setting("resolve_deep_audit") or "").strip().casefold()
    if value in ("1", "always", "on", "true"):
        return "always"
    if value == "tripwire":
        return "tripwire"
    return "off"

def _manifest_items(out):
    """director_resolve's own changes_asserted manifest, normalized to the
    seam's omission shape (source 'manifest').

    Numbered here, by the ENGINE, in the order the resolve emitted them --
    which is the order it narrated them, so the ids are the beat's own
    chronology (design note 21). The model is never asked for the number:
    an id it authored could repeat, skip, or reorder, and every downstream
    use assumes the ids are a dense sequence over exactly this manifest.
    Numbering runs BEFORE the length clamp so an id always indexes the item
    a specialist was actually handed.
    """
    items = []
    raw = out.get("changes_asserted")
    for item in (raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        change = str(item.get("change") or "").strip()
        if not change:
            continue
        normalized = {
            "category": _normalize_omission_category(item.get("category")),
            "subject": str(item.get("subject") or "").strip(),
            "change": change, "evidence": "", "source": "manifest",
            "event_id": len(items) + 1,
        }
        # Preserve the historical public manifest shape for every non-contact
        # change; endpoint keys exist only when the model actually supplied
        # them, rather than four empty strings appearing on every item.
        for field in ("actor", "actor_part", "target", "target_part",
                      "substance", "placement", "target_interior"):
            value = str(item.get(field) or "").strip()
            if value:
                normalized[field] = value
        items.append(normalized)
    items = _fold_derived_manifest_events(items)
    return items[:_RECONCILE_MAX_MANIFEST_ITEMS]


#: Categories whose entry may be the ENGINE'S OWN consequence of an attire
#: removal rather than a second change. A garment coming off is one event;
#: the object on the floor is what `commit._mint_shed_garments` does about
#: it, not a separate thing that happened.
_DERIVED_OF_ATTIRE = frozenset({"entities", "inventory"})


def _fold_derived_manifest_events(items):
    """One real-world change is ONE numbered event.

    The manifest may truthfully describe a single change twice -- "the sash
    is removed" (attire) and "the sash is created on the floor" (entities)
    are both true of one act. Numbered separately, they are routed to two
    different owners, and each faithfully authors its own record of the
    same garment. Measured live: five entity records for two garments, one
    beat after the previous duplication was repaired.

    So a derived entry folds into the attire event it follows from: one id,
    one owner, both categories remembered. Deterministic and engine-side,
    never a prompt rule -- the prompt half asks for one event per change,
    but a manifest is model-authored and this is the floor under it.

    Conservative by construction: only entities/inventory entries, only
    where `attire.resolve_garment` says the subject names the same garment
    as an attire entry in the SAME beat. Positions/stations/poses are
    deliberately not in this family -- those are three different facts
    about a body, not three descriptions of one.
    """
    from attire import resolve_garment

    attire_items = [i for i in items if i["category"] == "attire"]
    if not attire_items:
        return items
    folded = []
    for item in items:
        if item["category"] not in _DERIVED_OF_ATTIRE:
            folded.append(item)
            continue
        handles = [str(item.get("subject") or ""),
                   str(item.get("target") or "")]
        handles = [h for h in handles if h.strip()]
        parent = None
        for candidate in attire_items:
            names = [str(candidate.get("subject") or ""),
                     str(candidate.get("change") or "")]
            if any(resolve_garment(h, [names[0]]) for h in handles if h):
                parent = candidate
                break
            # The attire entry often names the WEARER as subject and the
            # garment inside `change` ("utility sash removed"), which is
            # the shape the live beat produced.
            if any(h and h.casefold() in names[1].casefold() for h in handles):
                parent = candidate
                break
        if parent is None:
            folded.append(item)
            continue
        also = parent.setdefault("also_described_as", [])
        if item["category"] not in also:
            also.append(item["category"])
    for index, item in enumerate(folded):
        item["event_id"] = index + 1
    return folded

def _player_claim_findings(out, sd, interp, cast, sc, player_input=""):
    """Tier 0 player-authority coverage: every asserted scope='effect'
    authority claim with a resolvable subject must be encoded SOMEWHERE in
    the diff (shallow containment -- the claim's free-text predicate cannot
    be mapped to one category deterministically). Returns (omissions,
    notes, contract_warnings): null-subject claims become metadata notes
    only; an asserted claim the resolve marked rejected/failed is a player-
    authority contract violation surfaced as a deterministic warning."""
    omissions, notes, contract_warnings = [], [], []
    claims = _dict_list(_dict(interp.get("flow")).get("authority_claims"))
    if not claims:
        return omissions, notes, contract_warnings

    statuses = {}
    for d in _dict_list(out.get("claim_dispositions")) + \
            _dict_list(sd.get("claim_dispositions")):
        cid = str(d.get("claim_id") or "")
        if cid:
            statuses[cid] = str(d.get("status") or "").strip().casefold()

    for claim in claims:
        if str(claim.get("scope") or "") != "effect":
            continue  # contestable intents are the director's to resolve
        status = statuses.get(str(claim.get("claim_id") or ""), "")
        if status in ("rejected", "failed"):
            contract_warnings.append(
                "PLAYER AUTHORITY: asserted claim "
                f"{claim.get('claim_id')!r} ({claim.get('predicate')!r} on "
                f"{claim.get('subject_id')!r}) was marked {status!r} -- "
                "asserted effects occur as declared and may not be rejected."
            )
        subject = str(claim.get("subject_id") or "").strip()
        if not subject:
            notes.append({
                "claim_id": claim.get("claim_id"),
                "predicate": claim.get("predicate"),
                "note": "no resolvable subject; coverage not checkable",
            })
            continue
        forms = _subject_match_forms(subject, cast, sc)
        # A SUBJECT NOBODY CAN POINT AT is the null-subject case wearing a
        # word, and it has to degrade the same way -- because a player claim
        # is NON-REJECTABLE, so an unsatisfiable one warns every beat
        # forever and buys the full-core repair every beat forever.
        #
        # Live, chat 72 turn 45: the player added an aside addressed to the
        # ENGINE -- "(it is a hotel. even at late hour someone should be
        # staffing it, use logic and reasoning instead of assuming no one is
        # there)" -- and interpret minted two asserted completed effects on a
        # subject called `narrative_assertion`, split at a comma. Neither
        # could ever be encoded, so they bought the most expensive retry the
        # engine has and warned anyway; the repair answered 'already_encoded'
        # for both and non-rejectability correctly refused to hear it.
        #
        # Two channels qualify a subject and only failing BOTH disqualifies:
        #   * the WORLD knows it -- `_subject_match_forms` found cast keys or
        #     entity aliases beyond the bare string, or it names a room;
        #   * the PLAYER SAID IT -- the words are in their own input, which
        #     is what makes "I shatter the vault door" a real claim about a
        #     door no scene contains yet. Asserting a thing into existence is
        #     precisely what player authority is for.
        # Folded to words so punctuation and case cannot decide it.
        if not _claim_subject_is_referrable(subject, forms, sc, player_input):
            notes.append({
                "claim_id": claim.get("claim_id"),
                "predicate": claim.get("predicate"),
                "note": ("subject names nothing in the world and nothing the "
                         "player typed; coverage not checkable"),
            })
            continue
        if not _omission_subject_encoded(sd, subject, forms):
            omissions.append({
                "category": "other", "subject": subject,
                "change": (f"player-asserted completed effect "
                           f"{str(claim.get('predicate') or '')!r} on "
                           f"{subject}"),
                "evidence": str(claim.get("source_text") or ""),
                "source": "player_claim", "_forms": forms,
            })
    return omissions, notes, contract_warnings

def _deep_audit_omissions(ctx, out, sd, scene_slice, dlog_compact,
                          tracked_names, recon):
    """The retained standalone audit call (default off; see
    _deep_audit_mode). Emits omissions with source 'audit'."""
    try:
        audit = _agent_json(
            "director", "resolve_reconcile",
            get_prompt("resolve_reconcile", ctx.language),
            {
                "resolved_event": out.get("resolved_event", ""),
                "dialogue_log": dlog_compact,
                "state_diff": sd,
                "prior_scene": scene_slice,
                "cast_names": tracked_names,
                # What the resolve declared it left out ON PURPOSE, because
                # it was interior. The audit's whole job is to find what the
                # prose asserted and the diff does not carry, and a thought
                # is precisely that shape while being precisely not a defect
                # -- so it is handed the declaration rather than left to
                # rediscover each interior moment as a missing encoding.
                # Commits nothing; the audit reads it and nothing else does.
                "declared_interior": recon.get("thoughts_omitted") or [],
            },
            temperature=0.0, max_tokens=8000,
        )
    except Aborted:
        raise
    except Exception as exc:
        ctx.add_warning(f"Resolve reconciliation audit failed: {exc}")
        return []
    audit_omissions = []
    raw_omissions = audit.get("omissions")
    for om in (raw_omissions if isinstance(raw_omissions, list) else []):
        if not isinstance(om, dict) or not str(om.get("change") or "").strip():
            continue
        try:
            confidence = float(om.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        entry = {
            "category": _normalize_omission_category(om.get("category")),
            "subject": str(om.get("subject") or ""),
            "change": str(om.get("change") or ""),
            "evidence": str(om.get("evidence") or ""),
            "confidence": confidence,
            "source": "audit",
        }
        if confidence < _RECONCILE_MIN_CONFIDENCE:
            # Low-confidence critic guesses are recorded for inspection but
            # never drive a repair or a warning -- the conservative floor.
            recon.setdefault("low_confidence", []).append(entry)
            continue
        audit_omissions.append(entry)
    return audit_omissions[:_RECONCILE_MAX_AUDIT_OMISSIONS]

def _public_omission(omission):
    return {k: v for k, v in omission.items() if not k.startswith("_")}


def _stamp_dialogue_articulation(sc, sd, dialogue_log):
    """Stamp each line with how it was FORMED; notice the impossible ones.

    Articulation is a property of the utterance at the moment it is produced
    -- the sibling of `volume`, which nobody considers a rewrite -- so it is
    stamped HERE, where the post-op ledger and the log meet, and rendered
    identically for every listener downstream. It is deliberately not a
    hearing level: a wall degrades sound in transit, differently per
    listener; an engaged tongue malforms the sound at the source, the same
    for everyone in the room, and a listener close by hears the slur BETTER,
    not less of it.

    The stamp is authoritative in both directions -- it sets and it CLEARS --
    so a model-invented value never survives and the field always reflects
    the ledger. The quotes themselves are never touched: `exact_quote` stays
    verbatim (the reconciliation contract), and the fidelity scrubs keep
    matching it.

    Notices go out only for the STIFLED kind at spoken volume: a full
    sentence with a filled mouth remains a fiction problem the Director
    should resolve (end the contact, or a word or two at 'mutter'), while a
    slurred line is now simply rendered as what it is. Checked against the
    POST-op ledger so a beat that ends the contact before the line is not
    scolded for it.
    """
    preview = dict(sc or {})
    preview["contacts"] = copy.deepcopy((sc or {}).get("contacts") or [])
    apply_contact_ops(preview, (sd or {}).get("contact_ops") or [])
    notices, noticed = [], set()
    impediments = {}
    for entry in dialogue_log or []:
        if not isinstance(entry, dict):
            continue
        speaker = str(entry.get("speaker") or "").strip()
        if not speaker:
            continue
        key = speaker.casefold()
        if key not in impediments:
            impediments[key] = speech_articulation_impediment(
                preview, speaker)
        kind, reason = impediments[key]
        entry["articulation"] = kind
        volume = str(entry.get("volume") or "normal").strip().casefold()
        if kind == ARTICULATION_STIFLED and key not in noticed \
                and volume in ("normal", "loud", "shout"):
            noticed.add(key)
            notices.append(
                f"speech: {speaker} spoke at volume '{volume}' while "
                f"{reason}. Either end that contact in contact_ops before "
                "the line, or keep the line to a word or two at volume "
                "'mutter' -- muffled against what blocks it.")
    return notices


#: Verdicts that settle an event without a second call. `not_mine` is
#: deliberately absent: a specialist saying the change needs a channel it
#: was not granted is REPORTING A GAP, not closing one, and that gap is
#: exactly what the repair tier exists for.
_SETTLING_VERDICTS = frozenset({"encoded", "already_true"})


def _verify_already_true(om, sc):
    """Deterministic standing-state check behind an `already_true` verdict.

    Returns (ok, reason). ok=False means the acquittal is REFUSED: standing
    state provably cannot carry ANY definite fact about this subject in this
    category, so a specialist's "the change is already the standing state"
    is resting on a ledger that does not support definite claims -- the
    chat 70/71 corruption exactly (a garment marked `removed` while still
    resident in three regions), where a specialist reading the ledger could
    honestly answer `already_true` about a change standing state did NOT
    properly carry.

    WHAT THIS DELIBERATELY IS NOT: a proof that the change is already true.
    The manifest's structure carries no DIRECTION -- whether the change puts
    the garment on or takes it off, starts the contact or ends it, lives
    only in the `change` prose, and prose matching is the boundary this
    whole design exists to get away from (both end states are legitimate
    no-op targets, so an undirected presence check is vacuous). So this is
    a defect detector, scoped to what is deterministically decidable:

    - attire: a subject-hit garment resident in a wearer's regions with
      state 'removed' (removed means GONE -- `release_removed_garments` is
      the canonical repair), or wearing/regions membership drift for a hit
      garment when both representations are populated (`rederive_entry`'s
      fork case). An incoherent wardrobe supports no definite claim.
    - positions/stations: a subject-hit standing position whose value is
      not a room in the scene -- the category error every spatial query
      answers as `unknown`, which looks exactly like distance.
    - inventory: a subject-hit body tracked in `contained` while carrying
      its OWN positions entry that disagrees with its holder's -- a carried
      body's position is derived from its carrier's, so two answers is a
      corrupt ledger.
    - contacts, conditions: no refusal is decidable (a relation ledger
      cannot be incoherent about presence; either end state is a legitimate
      no-op) -- trusted, now deliberately rather than by omission.

    Anything this cannot decide returns ok=True and the acquittal proceeds
    exactly as before. Fail open: an exception anywhere reads as ok=True.
    """
    try:
        category = _normalize_omission_category(om.get("category"))
        hits = _make_subject_hit(om.get("subject"),
                                 list(om.get("_forms") or [])
                                 + [om.get("target")])

        if category == "attire":
            for wearer, entry in (sc.get("attire") or {}).items():
                if not isinstance(entry, dict):
                    continue
                wearer_hit = hits(wearer)
                wearing = [str(n) for n in (entry.get("wearing") or [])
                           if str(n or "").strip()]
                resident = []      # (name, state) seated in regions
                for region_entry in (entry.get("regions") or {}).values():
                    if not isinstance(region_entry, dict):
                        continue
                    for garment in region_entry.get("garments") or []:
                        if isinstance(garment, dict) \
                                and str(garment.get("name") or "").strip():
                            resident.append(
                                (str(garment.get("name")),
                                 str(garment.get("state") or "")))
                for name, state in resident:
                    if state.casefold() == "removed" \
                            and (wearer_hit or hits(name)):
                        return False, (
                            f"standing attire for {wearer!r} still seats "
                            f"{name!r} in regions marked 'removed' -- "
                            "removed means gone from the body "
                            "(attire.release_removed_garments is the "
                            "canonical repair)")
                if wearing and resident:
                    for name, state in resident:
                        if state.casefold() == "removed":
                            continue
                        if (wearer_hit or hits(name)) \
                                and attire_model.resolve_garment(
                                    name, wearing) is None:
                            return False, (
                                f"standing attire for {wearer!r} seats "
                                f"{name!r} in regions but not in wearing "
                                "-- the representations disagree")
                    region_names = [n for n, s in resident
                                    if s.casefold() != "removed"]
                    for name in wearing:
                        if (wearer_hit or hits(name)) \
                                and attire_model.resolve_garment(
                                    name, region_names) is None:
                            return False, (
                                f"standing attire for {wearer!r} lists "
                                f"{name!r} in wearing but seats it in no "
                                "region -- the representations disagree")
            return True, None

        if category in ("positions", "stations"):
            rooms = sc.get("rooms") or {}
            for key, value in (sc.get("positions") or {}).items():
                if hits(key) and str(value or "") \
                        and str(value) not in rooms:
                    return False, (
                        f"standing position for {key!r} is {value!r}, "
                        "which is not a room in the scene -- a category "
                        "error every spatial query answers as unknown")
            return True, None

        if category == "inventory":
            contained = sc.get("contained") or {}
            positions = sc.get("positions") or {}
            for key, record in contained.items():
                if not hits(key):
                    continue
                holder = record.get("in") if isinstance(record, dict) \
                    else record
                own = positions.get(key)
                holder_pos = positions.get(str(holder or ""))
                if own and holder_pos and str(own) != str(holder_pos):
                    return False, (
                        f"{key!r} is contained by {holder!r} yet carries "
                        f"its own position {own!r} against the holder's "
                        f"{holder_pos!r} -- a carried body's position is "
                        "derived from its carrier's")
            return True, None

        return True, None
    except Exception:
        return True, None


def _acquit_addressed_events(out, omissions, sc=None):
    """Split detected omissions into (owed a repair, acquitted, refused).

    An omission is acquitted when it carries an event_id that the specialist
    OWNING that event answered with a settling verdict this beat. Ownership
    is implicit and cannot be forged: an id only reaches the index through
    the specialist that was handed it, by the same category filter that
    built its payload, and only if that call actually ran.

    An `already_true` verdict is additionally checked against standing
    state (`_verify_already_true`): a ledger that provably cannot carry any
    definite fact about the subject earns no acquittal, and the refusal is
    returned as a named defect -- the omission stays owed, so the repair
    tier still sees the gap.

    Everything without an event_id -- signals, player claims, deep-audit
    findings, and every omission on the monolithic path, where no specialist
    ran and the index is empty -- falls through unchanged. That is what
    keeps the monolithic repair path byte-identical.
    """
    record = out.get("orchestration")
    index = (record or {}).get("events_addressed") or {}
    if not isinstance(index, dict) or not index:
        return omissions, [], []
    owed, acquitted, refused = [], [], []
    for om in omissions:
        entry = index.get(om.get("event_id")) or index.get(
            str(om.get("event_id")))
        status = (entry or {}).get("status")
        if entry and status in _SETTLING_VERDICTS:
            if status == "already_true":
                ok, reason = _verify_already_true(om, sc or {})
                if not ok:
                    refused.append({
                        "event_id": om.get("event_id"),
                        "category": om.get("category"),
                        "subject": om.get("subject"),
                        "owner": entry.get("owner"),
                        "reason": reason,
                    })
                    owed.append(om)
                    continue
            acquitted.append({
                "event_id": om.get("event_id"),
                "category": om.get("category"),
                "subject": om.get("subject"),
                "owner": entry.get("owner"),
                "status": status,
            })
        else:
            owed.append(om)
    return owed, acquitted, refused


#: Sentinel channel for a REROUTED omission: the hand that declined the
#: event named the owner but not which of its channels fits -- only the
#: owner knows that -- so it repairs with its full granted scope.
_REROUTE_FULL_SCOPE = "*"


def _route_repair_omissions(omissions, addressed=None):
    """Partition detected omissions by REPAIRER, for the orchestrated path.

    Returns (routed, core): `routed` maps specialist name -> [(channel,
    omission), ...] for every omission whose category names a delegated
    channel -- that channel's owner is who should be asked again, with its
    own 1-4k sheet, not the prose author with the full core. `core` keeps
    everything only a whole-diff authority can answer: player claims (their
    coverage check is whole-diff and they are non-rejectable), and
    categories no specialist owns (time, transit, 'other').
    """
    routed, core = {}, []
    index = addressed or {}
    for om in omissions:
        if om.get("source") == "player_claim":
            core.append(om)
            continue
        # A FORWARDING NOTE BEATS THE CATEGORY MAP. The hand that was given
        # this event declined it AND named the hand it belongs to, in a
        # structured field. Routing by category here would re-ask the hand
        # that just said no -- measured live, where contact and objects both
        # explained in prose that a posture change was not theirs while the
        # category kept sending it back. The address is a PROPOSAL, checked
        # against the roster before it is acted on: an unknown name, or a
        # hand that already had this event, falls back to the category.
        entry = index.get(om.get("event_id")) or index.get(
            str(om.get("event_id")))
        target = str((entry or {}).get("reroute_to") or "").strip()
        if (target in SPECIALISTS and target != (entry or {}).get("owner")
                and om.get("event_id")):
            routed.setdefault(target, []).append((_REROUTE_FULL_SCOPE, om))
            continue
        channel = _CATEGORY_CHANNELS.get(
            _normalize_omission_category(om.get("category")))
        owner = _CHANNEL_SPECIALISTS.get(channel) if channel else None
        if owner:
            routed.setdefault(owner, []).append((channel, om))
        else:
            core.append(om)
    return routed, core


def _specialist_repairs(ctx, sc, sd, routed, view, extras, recon):
    """Tier 2 on the orchestrated path: the omitted channel's OWNER repairs.

    Measured reason (chat 71 turn 10): the seam's one repair call re-ran the
    PROSE AUTHOR -- an extra sequential call on the director role with the
    full-core repair sheet -- to re-encode a change one specialist owned,
    and still shipped `state_diff still does not encode it` warnings. Under
    orchestration the wrong repairer was asked: a scoped specialist call
    measured ~1s against a full-core resolve at tens of seconds, and the
    specialist is the authority the omitted channel already belongs to.

    Detection is untouched -- this changes only WHO repairs (the
    `changes_asserted` seam stays the single reconciliation mechanism). At
    most ONE call per owning specialist, no retries beyond `_agent_json`'s
    own validation ladder: a repair that cannot succeed stops, and the
    residual reaches the existing unresolved/warning channel below instead
    of a repeat spend. Merging is the same additive `_merge_repair_into_
    diff` contract as the core repair -- scoped to the specialist's granted
    channels, never deleting what the diff already asserts. A failed call
    is fail-open exactly like the fan-out: warn, keep the beat, let the
    re-check below file the omission as unresolved.

    Returns (repaired, verdicts). `verdicts` maps event_id -> the settling
    answer its owner gave ON THE REPAIR CALL, which is the fan-out's
    analogue of the core repair's `dispositions` and closes the same hole
    the monolith closed: a hand asked to encode something it can see is
    ALREADY carried could otherwise only mend or stay silent, and silence
    ships a `still does not encode it` warning against a change the owner
    just certified (v26625, on the core path). Believing it costs nothing:
    an `encoded` claim is still checked against the merged diff by
    `_evidence_present` downstream, and an `already_true` against standing
    state by `_verify_already_true`, exactly as a dispatch verdict is.
    """
    repaired = False
    reports = {}
    verdicts = {}
    for name in SPECIALISTS:          # canonical order, like the fan-out
        entries = routed.get(name)
        if not entries:
            continue
        spec = SPECIALISTS[name]
        omitted = {channel for channel, _om in entries}
        scope = ([ch for ch in spec["channels"]]
                 if _REROUTE_FULL_SCOPE in omitted
                 else [ch for ch in spec["channels"] if ch in omitted])
        report = {"scope": scope, "ok": False}
        reports[name] = report
        payload = _specialist_payload(name, ctx, sc, view, extras)
        payload["previous_channels"] = {
            ch: copy.deepcopy(sd.get(ch)) for ch in scope}
        payload["detected_omissions"] = [
            {k: om.get(k) for k in ("category", "subject", "change",
                                    "evidence", "source")}
            for _ch, om in entries]
        payload["correction_notes"] = (
            "REPAIR PASS: the finished beat asserts persistent changes in "
            "your channels that the committed encoding does not carry -- "
            "detected_omissions lists them, previous_channels is what "
            "currently stands. Your answer is merged ADDITIVELY over "
            "previous_channels (it cannot delete existing entries), so "
            "emit ONLY your channels, encoding each detected omission; "
            "leave a channel empty when its omission is already covered. "
            "Echo every listed event in resolved_events with its verdict -- "
            "'encoded' when you are adding it here, 'already_true' when "
            "standing state carries it and no delta is correct. Silence on "
            "an event reads as unencoded and ships a staleness warning "
            "against the beat, so say already_true rather than nothing when "
            "that is the answer.")
        try:
            if spec.get("ext_id"):
                result = _extension_specialist_call(
                    spec, scope, payload, ctx.language)
            else:
                result = _agent_json(
                    spec["role"], spec["step_key"],
                    specialist_prompt(name, scope, ctx.language), payload,
                    temperature=0.0,
                    max_tokens=None,   # the configured ceiling
                )
        except Aborted:
            raise
        except Exception as exc:
            report["error"] = str(exc)
            ctx.add_warning(
                f"{name} specialist repair failed; the unencoded change "
                f"will be warned, never fabricated (fail-open): {exc}")
            continue
        report["ok"] = True
        # The owner's verdict on the events it was handed AGAIN. Same
        # filter as the dispatch echo: an id this call was not given is
        # discarded, so a repairer cannot acquit a sibling's omission.
        granted_ids = [om.get("event_id") for _ch, om in entries
                       if om.get("event_id")]
        settled = _resolved_event_verdicts(result, granted_ids)
        if settled:
            report["events_resolved"] = settled
            for entry in settled:
                if entry["status"] in _SETTLING_VERDICTS:
                    verdicts[entry["event_id"]] = {
                        "status": entry["status"], "owner": name}
        patch = {}
        for channel in scope:
            value = _normalized_channel_value(channel, result.get(channel))
            if value:
                patch[channel] = value
        if not patch:
            continue
        # Same hygiene as the core repair: canonical shapes, no reintroduced
        # placeholder noise, canonicalized position keys, additive merge.
        patch = _normalize_diff_shape(patch)
        _strip_blank_diff_placeholders(patch)
        patch["positions"] = canonicalize_positions(
            patch.get("positions") or {}, ctx.cast)
        report["channels"] = sorted(
            ch for ch in scope if patch.get(ch))
        _merge_repair_into_diff(sd, patch)
        repaired = True
    recon["specialist_repairs"] = reports
    return repaired, verdicts


def _reconcile_resolution(ctx, out, sc, interp, char_actions, dice,
                          tracked_names):
    """The resolve-reconciliation seam (see the block comment above).
    Mutates out['state_diff'] in place (strip + merged repair delta only),
    records inspection metadata on out['reconciliation'], and appends to
    ctx.warnings for anything that remains unencoded. resolved_event and the
    WORDS of dialogue_log are never modified -- the prose is the account
    being reconciled against, not the thing under repair. The one exception
    is deliberate and additive: `articulation` is stamped onto each dialogue
    entry (see _stamp_dialogue_articulation) because how a sound was formed
    is derived delivery metadata in the same class as `volume`, not part of
    the account; every `exact_quote` and `speaker` stays verbatim."""
    sd = _normalize_diff_shape(out.get("state_diff"))
    out["state_diff"] = sd
    resolved_event = out.get("resolved_event", "")
    dialogue_log = out.get("dialogue_log") or []

    # An explicitly shed clothing entity is already a structured assertion
    # that the named garment left the named wearer. Promote that relation into
    # the attire/position fields before omission detection, so the same
    # resolution cannot create a floor object while leaving it on the body.
    # Pure structured recovery only: the garment must resolve uniquely against
    # the prior wardrobe; no prose is parsed.
    for recovered in attire_model.recover_shed_entity_changes(sc, sd):
        if recovered.get("garment"):
            ctx.tell_director(
                "attire: read explicitly shed clothing entity "
                f"{recovered['entity_id']!r} as removing "
                f"{recovered['garment']!r} from {recovered['owner']!r}.")

    for notice in _stamp_dialogue_articulation(sc, sd, dialogue_log):
        ctx.tell_director(notice)

    # ---- Tier 0: deterministic floor -------------------------------------
    # Runs BEFORE the omission scans below so they read the corrected diff. The
    # two cannot fight: this only drops a gated level that no cue supports, and
    # the unconsciousness scan only fires where a cue exists.
    _pers = persona_of(ctx.chat)
    player_name = _pers.get("name") or persona_name(_pers)
    for key, level in _unsupported_player_awareness(
            sd.get("conditions") or {}, player_name, ctx.input,
            resolved_event, dialogue_log):
        (sd.get("conditions") or {}).pop(key, None)
        ctx.add_warning(
            f"Dropped awareness '{level}' on the player ({player_name}): "
            "nothing in the beat or in the player's own input put them under, "
            "and a gated level would have taken away their view and their next "
            "move."
        )

    # The exit side of the same floor (see the WAKING block above). The onset
    # guard above only ever refused to START a gate; nothing could END one, and
    # across the author's whole corpus the Director never once did. Runs AFTER
    # the onset drop so a condition dropped this beat is not also "ended", and
    # writes only where waking is not a judgement call.
    _live_awareness = awareness_conditions(ctx.chat["id"])
    if _live_awareness:
        _exits, _exit_warnings = _awareness_exits(
            ctx.chat["id"], _live_awareness, player_name, ctx.input,
            interp, char_actions, resolved_event,
            simulation_clock(ctx.chat["id"]), sd.get("time"),
        )
        if _exits:
            sd.setdefault("conditions", {})
            for _cond_id, _cond in _exits.items():
                # An ending the Director DID write wins -- it carries the
                # Director's own cause and is already consistent with the
                # prose. A RE-ASSERTION does not: re-emitting the same id as
                # still active is precisely how a gate the world has ended
                # survives, so the floor overwrites that.
                _existing = sd["conditions"].get(_cond_id)
                if _existing is not None and _already_ended(_existing):
                    continue
                sd["conditions"][_cond_id] = _cond
        for _w in _exit_warnings:
            ctx.add_warning(_w)
        # Surfaced on the step itself, not only in ctx.warnings, which is
        # accumulated pipeline-wide and never shown (the lesson the player-act
        # authority retry above records). A refused rouse -- someone shaking a
        # sedated body that does not wake -- writes NO diff at all, so the step
        # inspector is the only place it can be seen.
        if _exit_warnings:
            out["awareness_warnings"] = list(_exit_warnings)

    # Restraint, enforced rather than merely detected. The omission scan below
    # has always asked the Director to RECORD a binding; nothing ever read the
    # result, so a character bound hand and foot could still walk out. A
    # restraint that is in force -- including one applied this same beat --
    # blocks that body from relocating itself. Everything subtler (what they
    # can still reach, whether they can work free) stays the Director's call.
    _rmap = apply_restraint_diff(restraint_map(ctx.chat["id"]), sd)
    if _rmap and isinstance(sd.get("positions"), dict):
        _prior = (sc.get("positions") or {})
        for _who in list(sd["positions"]):
            _record = restraint_of(_rmap, _who)
            if not _record or _record["level"] not in IMMOBILIZING_RESTRAINTS:
                continue
            _was = _prior.get(_who)
            if _was is None or sd["positions"][_who] == _was:
                continue
            # Being CARRIED somewhere while bound is legitimate -- that is the
            # restrainer moving them, not them walking off.
            if (sc.get("contained") or {}).get(_who):
                continue
            sd["positions"].pop(_who, None)
            ctx.add_warning(
                f"Blocked a move by {_who}, who is {_record['level']}"
                + (f" by {_record['by']}" if _record["by"] else "")
                + ": a restrained body cannot relocate itself. Release the "
                "restraint first, or have someone carry them."
            )

    signals = _strip_blank_diff_placeholders(sd)
    for name in _untracked_restraint_subjects(
            resolved_event, dialogue_log, sd.get("conditions") or {},
            tracked_names):
        signals.append({
            "category": "conditions", "subject": name,
            "change": (f"{name} is under physical restraint/duress in the "
                       "prose but has no state_diff.conditions entry"),
            "evidence": "", "source": "restraint_scan",
        })
    for name in _untracked_unconsciousness_subjects(
            resolved_event, dialogue_log, sd.get("conditions") or {},
            tracked_names):
        signals.append({
            "category": "conditions", "subject": name,
            "change": (f"{name} is narrated as losing consciousness (knocked "
                       "out / unconscious / faints) but has no awareness "
                       "condition -- add a state_diff.conditions entry of "
                       "kind:'awareness' with state.level (unconscious|asleep|"
                       "sedated|dazed) for them"),
            "evidence": "", "source": "unconsciousness_scan",
        })

    claim_omissions, claim_notes, contract_warnings = _player_claim_findings(
        out, sd, interp, ctx.cast, sc, ctx.input or "")
    for warning in contract_warnings:
        ctx.add_warning(warning)

    # ---- Tier 1: the same-call manifest, checked deterministically -------
    manifest = _manifest_items(out)
    manifest_omissions = []
    for item in manifest:
        forms = _subject_match_forms(item["subject"], ctx.cast, sc)
        if not _evidence_present(sd, item, forms):
            manifest_omissions.append({**item, "_forms": forms})

    # Destruction tripwire (see _narrated_destruction_subjects): a named,
    # KNOWN place narrated as destroyed while the diff declares no
    # destruction and removes nothing. Deliberately warn-only and OUTSIDE
    # the Tier-2 repair routing -- a self-repair must never be talked into
    # fabricating a region cascade from a text heuristic.
    book_names = []
    try:
        book_names = [
            b.get("name") for b in lorebook_manifest(ctx.chat["id"])["books"]
            if b.get("name")
            and str(b.get("type") or "") in ("general", "world", "location",
                                             "vehicle")
        ]
    except Exception:
        pass  # candidate enrichment only; the scene-derived names still run
    destruction_flags = _narrated_destruction_subjects(
        resolved_event, dialogue_log, sd, sc, extra_names=book_names)
    for place in destruction_flags:
        ctx.add_warning(
            f"Possible unencoded destruction: resolved_event narrates the "
            f"destruction of {place!r} (a named, known place) but "
            "state_diff.destruction is null and remove_rooms/remove_entities "
            "do not cover it. The Phase-3b cascade only realizes a DECLARED "
            "destruction, so objective state still has this place fully "
            "intact while the prose claims otherwise."
        )

    recon = {
        "signals": [dict(s) for s in signals],
        "manifest": [dict(m) for m in manifest],
        "claim_notes": claim_notes,
        "destruction_scan": list(destruction_flags),
        "audited": False, "tripwire": False,
        "omissions": [], "repaired": False,
        "dispositions": [], "unresolved": [],
    }
    out["reconciliation"] = recon

    # Silent-false-negative tripwire: the beat provably did something
    # physical (successful dice, asserted effect-claims) yet the manifest
    # AND every physical diff category are empty. Metadata always; a deep
    # audit only when the operator opted in.
    claims = _dict_list(_dict(interp.get("flow")).get("authority_claims"))
    provably_physical = any(
        str(d.get("outcome") or "") == "success" for d in (dice or [])
    ) or any(str(c.get("scope") or "") == "effect" for c in claims)
    # The omitted-thought ledger, which COMMITS NOTHING. It cannot excuse a
    # beat that provably did something physical -- a successful roll or an
    # asserted effect-claim moved the world, and no amount of interiority
    # accounts for an empty manifest there, which is exactly what the
    # tripwire is for. What it does account for is the quiet case: no
    # physical proof, nothing encoded, and the resolve saying plainly that
    # what happened was interior. Recorded either way, so the drawer shows
    # what the beat declared it left out.
    thoughts = [t for t in _dict_list(out.get("thoughts_omitted"))
                if str(t.get("thought") or "").strip()]
    if thoughts:
        recon["thoughts_omitted"] = [
            {"subject": str(t.get("subject") or "").strip(),
             "thought": str(t.get("thought") or "").strip()}
            for t in thoughts
        ]
    if provably_physical and not manifest and not _diff_is_substantive(sd):
        recon["tripwire"] = True

    deep_mode = _deep_audit_mode()
    run_deep = (
        deep_mode == "always"
        and (bool(signals) or _diff_is_substantive(sd)
             or _beat_has_physical_activity(interp, char_actions, dice))
    ) or (deep_mode == "tripwire" and recon["tripwire"])

    scene_slice = None
    dlog_compact = [
        {"speaker": d.get("speaker"), "exact_quote": d.get("exact_quote")}
        for d in dialogue_log[:20] if isinstance(d, dict)
    ]
    audit_omissions = []
    if run_deep:
        recon["audited"] = True
        scene_slice = _reconcile_scene_slice(
            sc, ctx.cast, ctx.get("_player_room"), sd)
        audit_omissions = _deep_audit_omissions(
            ctx, out, sd, scene_slice, dlog_compact, tracked_names, recon)

    omissions = signals + claim_omissions + manifest_omissions + audit_omissions
    recon["omissions"] = [_public_omission(o) for o in omissions]

    # DETECTION IS UNTOUCHED ABOVE; what changes here is who gets ASKED
    # AGAIN. An event whose owning specialist already answered it this beat
    # buys no second call -- the measured waste (chat 71 turn 10) was a
    # full-core repair spending 105-225s to re-ask a change the owner had
    # correctly encoded or correctly declined, whose answer was then
    # discarded on a subject-text mismatch. The acquittal is bookkeeping,
    # not belief: the encoding still had to pass _evidence_present, and an
    # unaddressed event still buys its repair.
    omissions, acquitted, at_refused = _acquit_addressed_events(
        out, omissions, sc)
    if acquitted:
        recon["acquitted"] = acquitted
    # Every forwarding note is a recorded vote that _CATEGORY_CHANNELS sent
    # this event to the wrong hand. `overlays` and `vitals` were reachable
    # by no category for a whole release and nobody noticed; a routing table
    # that is corrected from data rather than guessed at is worth as much as
    # the reroute itself.
    _addressed = ((out.get("orchestration") or {}).get("events_addressed")
                  or {})
    _notes = [
        {"event_id": eid, "declined_by": e.get("owner"),
         "reroute_to": e.get("reroute_to"),
         "category": next((str(m.get("category")) for m in manifest
                           if m.get("event_id") == int(eid)), "")}
        for eid, e in _addressed.items()
        if isinstance(e, dict) and e.get("reroute_to")
    ]
    if _notes:
        recon["reroutes"] = _notes
    # An `already_true` the standing scene provably cannot support is a
    # NAMED defect, never a silence: the omission stays owed (the repair
    # tier still sees the gap), and the ledger corruption itself -- the
    # thing the specialist honestly misread -- is reported on the step and
    # to the next beat's Director.
    if at_refused:
        recon["already_true_refused"] = at_refused
        for refusal in at_refused:
            note = (
                f"already_true refused for event {refusal.get('event_id')} "
                f"({refusal.get('owner')} specialist, subject "
                f"{refusal.get('subject')!r}): {refusal.get('reason')}")
            ctx.add_warning(note)
            ctx.tell_director(note)
    if not omissions:
        return

    # ---- Tier 2: bounded self-repair (the only common-path LLM spend,
    # and only on a real detected gap). One shot per repairer. ------------
    #
    # WHO repairs depends on the path. Monolithic: the Director itself, with
    # the full-core repair sheet, exactly as always. Orchestrated: each
    # omission in a delegated channel goes to that channel's OWNING
    # specialist (~1s scoped call), and only the omissions no specialist can
    # answer -- player claims, undelegated categories -- still buy the
    # full-core call. Detection above is identical on both paths; only the
    # repairer changes (see _specialist_repairs).
    core_omissions = omissions
    repair_verdicts = {}
    orch_repair = None
    _orch_record = out.get("orchestration")
    if isinstance(_orch_record, dict) and _orch_record.get("enabled"):
        orch_repair = ctx.get("_orch_repair")
    if isinstance(orch_repair, dict) \
            and isinstance(orch_repair.get("view"), dict):
        routed, core_omissions = _route_repair_omissions(
            omissions,
            (_orch_record or {}).get('events_addressed'))
        if routed:
            _mended, repair_verdicts = _specialist_repairs(
                ctx, sc, sd, routed,
                orch_repair["view"], orch_repair.get("extras") or {},
                recon)
            if _mended:
                recon["repaired"] = True

    dispositions = []
    if core_omissions:
        if scene_slice is None:
            scene_slice = _reconcile_scene_slice(
                sc, ctx.cast, ctx.get("_player_room"), sd)
        try:
            repair = _agent_json(
                "director", "resolve_repair",
                get_prompt("resolve_repair", ctx.language),
                {
                    "resolved_event": resolved_event,
                    "dialogue_log": dlog_compact,
                    "previous_state_diff": sd,
                    "detected_omissions": [
                        {k: o.get(k) for k in ("category", "subject",
                                               "change", "evidence",
                                               "source")}
                        for o in core_omissions
                    ],
                    "non_rejectable_subjects": sorted({
                        o["subject"] for o in core_omissions
                        if o.get("source") == "player_claim"
                        and o.get("subject")
                    }),
                    "prior_scene": scene_slice,
                    "cast_names": tracked_names,
                },
                temperature=0.0,
            )
        except Aborted:
            raise
        except Exception as exc:
            ctx.add_warning(f"Resolve reconciliation repair failed: {exc}")
            repair = None

        if isinstance(repair, dict):
            patch = _normalize_diff_shape(repair.get("state_diff"))
            # A repair may not reintroduce the very noise this seam strips.
            _strip_blank_diff_placeholders(patch)
            patch["positions"] = canonicalize_positions(
                patch.get("positions") or {}, ctx.cast)
            _merge_repair_into_diff(sd, patch)
            dispositions = [d for d in (repair.get("dispositions") or [])
                            if isinstance(d, dict)]
            recon["repaired"] = True
            recon["dispositions"] = dispositions

    # Disposition -> omission matching carries the same substring tolerance
    # _make_subject_hit gives every other subject comparison in this seam.
    # Exact normalized equality lost real verdicts: the repair writes
    # descriptive subjects ("lightweight travel jacket — fully removed from
    # shoulder, falls onto velvet"), and on chat 71 turn 2354 v26625 every
    # 'already_encoded' answer was discarded to a failed exact match, so the
    # staleness warning shipped against a beat the repair had just certified.
    _disp_pairs = [
        (_norm_subject(d.get("subject")),
         str(d.get("status") or "").casefold())
        for d in dispositions
    ]

    def _disposition_for(subject):
        ns = _norm_subject(subject)
        if not ns:
            return ""
        for dn, status in _disp_pairs:
            if not dn:
                continue
            if dn == ns:
                return status
            shorter, longer = sorted((dn, ns), key=len)
            if len(shorter) >= 5 and shorter in longer:
                return status
        return ""

    for om in omissions:
        source = om.get("source")
        if source == "restraint_scan":
            continue  # re-checked precisely below, with the legacy wording
        forms = om.get("_forms") or _subject_match_forms(
            om.get("subject"), ctx.cast, sc)
        if source == "player_claim":
            encoded = _omission_subject_encoded(sd, om.get("subject"), forms)
        else:
            encoded = _evidence_present(sd, om, forms)
        if encoded:
            continue
        status = _disposition_for(om.get("subject"))
        if not status:
            # No core repair ran for this one (its channel has an owner), so
            # its verdict is the owner's own echo. `already_true` is the
            # specialist spelling of the core repair's `already_encoded` --
            # the same claim about the same beat, and it earns the same
            # conservatism: believed only where standing state can carry it.
            _repair_said = (repair_verdicts.get(om.get("event_id")) or {}
                            ).get("status")
            if _repair_said == "already_true" \
                    and _verify_already_true(om, sc or {})[0]:
                status = "already_encoded"
        if source == "player_claim":
            # NON-REJECTABLE: the player authority contract makes the effect
            # true; a disposition cannot argue it away -- only actual
            # post-merge evidence silences this warning.
            recon["unresolved"].append(
                {**_public_omission(om), "disposition": status or "none"})
            ctx.add_warning(
                "PLAYER AUTHORITY: "
                f"{om.get('change')} is not encoded in state_diff even "
                "after self-repair; objective state contradicts the "
                "player's asserted effect."
            )
            continue
        if source in ("manifest", "audit") and status in ("rejected",
                                                          "already_encoded"):
            # The owner overruled an emergent detection; conservatism says
            # believe the rejection rather than warn on a model-vs-model
            # disagreement.
            recon["unresolved"].append(
                {**_public_omission(om), "disposition": status})
            continue
        recon["unresolved"].append(
            {**_public_omission(om), "disposition": status or "none"})
        ctx.add_warning(
            "Resolve reconciliation: prose asserts "
            f"{om.get('change')!r} (subject {om.get('subject')!r}) but "
            "state_diff still does not encode it after self-repair; "
            "objective state may be stale."
        )

    # Restraint detector re-run against the FINAL merged diff: silent when
    # the repair encoded the condition, the exact legacy warning otherwise.
    for restraint_warning in _scan_for_untracked_restraint(
            resolved_event, dialogue_log, sd.get("conditions") or {},
            tracked_names):
        ctx.add_warning(restraint_warning)

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
    pending = sc.get("approach") or {}
    if "who" in pending:
        pending = ({pending["who"]: {"to_room": pending.get("to_room")}}
                   if pending.get("who") else {})
    if not isinstance(pending, dict) or not pending:
        return []
    mv = interp.get("movement")
    declared = set()
    if isinstance(mv, dict) and mv.get("to_room"):
        who = str(mv.get("mover") or "self")
        declared.add(p_name if who in ("self", "player") else who)

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
        edge = next(
            (e for e in ((rooms.get(here) or {}).get("adjacent") or [])
             if isinstance(e, dict) and e.get("to") == step), {})
        entry = {
            "subject": subject,
            "destination": destination,
            "destination_name": str(
                (rooms.get(destination) or {}).get("name") or destination),
            "from_room": here,
            "reaches_this_beat": step,
            "reaches_name": str((rooms.get(step) or {}).get("name") or step),
            "distance": normalize_edge_distance(edge.get("distance")),
            "final_leg": step == destination,
        }
        if entry["distance"] in _LONG_EDGE_DISTANCES \
                and int(leg.get("edge_beats") or 0) + 1 < _LONG_EDGE_BEATS:
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
    pending = sc.get("approach") or {}
    # The scene-global shape ({"who": ...}) predates per-mover records and is
    # still read so a save written before that does not lose a walker.
    if "who" in pending:
        pending = ({pending["who"]: {"to_room": pending.get("to_room")}}
                   if pending.get("who") else {})
    if not isinstance(pending, dict) or not pending:
        return

    # A mover who declared their own movement this beat goes through the
    # ordinary machinery untouched: continuation fills a SILENCE and never
    # competes with a live declaration.
    mv = interp.get("movement")
    declared = set()
    if isinstance(mv, dict) and mv.get("to_room"):
        who = str(mv.get("mover") or "self")
        declared.add(p_name if who in ("self", "player") else who)

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
        edge = next(
            (e for e in ((rooms.get(here) or {}).get("adjacent") or [])
             if isinstance(e, dict) and e.get("to") == step), {})
        spent = int(leg.get("edge_beats") or 0) + 1
        if normalize_edge_distance(edge.get("distance")) in \
                _LONG_EDGE_DISTANCES and spent < _LONG_EDGE_BEATS:
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


# ---------------------------------------------------------------------------
# Director orchestration (design note 19, `docs/UNBUILT.md` §2.18).
#
# The resolve stage stays ONE pipeline step -- one steps/variants row, the
# same step key, nothing new in agents/runtime.py -- and fans out INSIDE
# itself, on every beat: a deterministic
# dispatch decides which scoped specialists this beat needs, one prose author
# owns resolved_event (with the delegated instruction blocks cold-stored out
# of its sheet), each dispatched specialist reads the finished prose and owns
# its state_diff channels, and deterministic assembly merges the channels
# back before the existing cross-channel seams (movement backstop,
# reconciliation, restraint floor) run on the merged diff exactly as they do
# on an unsplit one. There is no unsplit path any more: it shipped behind
# a flag while the two were measured against each other, the fan-out won on
# stability, tokens and wall clock, and keeping the loser would only have
# preserved a way to make the engine worse. What remains a choice is
# CONCURRENCY -- see `fanout_is_parallel`.
#
# THE GATE FAILS OPEN AND KEYS ON SCENE STATE, never on the beat's prose --
# prose matching as a boundary is the silent-drop surface `docs/UNBUILT.md`
# §3.1 refuses. Where structure cannot decide, the specialist runs: a scoped
# specialist costs little to run needlessly, and that asymmetry is what makes
# a generous gate affordable. A wrongly-skipped specialist is never silent:
# `_orchestration_gate_backstop` is `changes_asserted` reconciliation pointed
# at the GATE, and reports the misprediction through `tell_director`.
#
# Dispatch is decided at THIS stage's time, from what is true then. Nothing
# here assumes a plan fixed at the top of the turn: when `director_interpret`
# grows its own specialists it will call its own dispatch against the state
# it sees, because characters declare between the two stages and bring
# channels into play nothing at interpret time could predict.
# ---------------------------------------------------------------------------

#: The specialists, one authority for channel ownership on the runtime side.
#: prompts.SPECIALIST_PROMPT_SPECS holds each one's sheet material keyed by
#: the same channel names, and schemas.SPECIALIST_CHANNELS the same map by
#: step key; tools/project_check.py holds all three level. Dict order is the
#: CANONICAL assembly order: merges happen in this order whatever order the
#: parallel calls complete in, so a rerun with the same inputs produces the
#: same merged diff.
SPECIALISTS = {
    "body": {
        "step_key": "director_body",
        "role": "director_body",
        "channels": ("attire", "conditions", "vitals", "overlays"),
    },
    "social": {
        "step_key": "director_social",
        "role": "director_social",
        # `following_ops` belongs to this family in the corpus table but is
        # NOT owned here: following is actor-owned and engine-projected
        # (`_collect_following_ops` overwrites the channel deterministically
        # every resolve), so no model authors it -- a specialist "owning" it
        # would own a channel whose content is discarded.
        "channels": ("cast_changes", "introductions", "world_facts"),
    },
    "contact": {
        "step_key": "director_contact",
        "role": "director_contact",
        "channels": ("contact_ops", "substance_ops", "containment",
                     "scales"),
    },
    "objects": {
        "step_key": "director_objects",
        "role": "director_objects",
        "channels": ("entities", "remove_entities", "inventory_ops",
                     "artifact_ops", "destruction"),
    },
    # The geography. Carved LAST by design: the movement backstop, the
    # following projection, approach semantics and the near-group
    # reconciliation all judge the MERGED diff and stay with the
    # orchestrator -- this specialist proposes relocations and never has
    # the last word on them.
    "spatial": {
        "step_key": "director_spatial",
        "role": "director_spatial",
        "channels": ("positions", "rooms", "remove_rooms",
                     "remove_adjacent", "stations", "poses", "comms_ops"),
    },
    # The world's traffic. The ops surface ONLY -- the offscreen SIMULATOR
    # (design note 19's out-of-band parallel) remains owner-deferred, and
    # nothing here schedules or simulates anything. Genuinely dispatchable:
    # it runs whenever its subjects exist in scene (crowds, couriers,
    # carried reports, unratified hearsay, the planning floor switched on),
    # and is cold in practice only because most scenes contain none.
    "offscreen": {
        "step_key": "director_offscreen",
        "role": "director_offscreen",
        "channels": ("crowd_ops", "courier_ops", "telling_ops",
                     "offscreen_plan_ops", "ratified_claims",
                     "contradicted_claims"),
    },
}

_DELEGATED_CHANNELS = tuple(
    channel for spec in SPECIALISTS.values() for channel in spec["channels"])

#: `changes_asserted` category -> the delegated channel that answers for it.
#: Categories with no delegated channel (time, transit, other, ...) stay
#: the prose author's own and are not the scope backstop's business.
#:
#: KEYED ON THE NORMALIZED CATEGORY NAMES (_normalize_omission_category's
#: output: 'contacts', 'substances', 'poses', ...): every reader of this map
#: looks up items that already went through _manifest_items, which
#: normalizes. The original raw spellings ('contact', 'substance', 'pose')
#: are kept as tolerance for a caller that never normalized, but for two
#: releases they were the ONLY keys -- so a manifest entry asserting a
#: contact, substance or pose change could never reach the scope backstop
#: or be sliced into its specialist's payload, silently.
_CATEGORY_CHANNELS = {
    "attire": "attire",
    "conditions": "conditions",
    "cast_changes": "cast_changes",
    "contact": "contact_ops",
    "contacts": "contact_ops",
    "substance": "substance_ops",
    "substances": "substance_ops",
    "inventory": "inventory_ops",
    "entities": "entities",
    "positions": "positions",
    "rooms": "rooms",
    # An adjacency change is either a rooms-edge edit or a severance; the
    # rooms gate and the remove_adjacent gate are the same fact, so either
    # served scope answers for the category.
    "adjacency": "rooms",
    "pose": "poses",
    "poses": "poses",
    "stations": "stations",
    # Equipment that carries a voice, not the doorway it carries it past. A
    # beat that keys a mic, kills an intercom or hands someone a radio is
    # categorized here, so it reaches the specialist that owns the channel
    # rather than being detected as an omission every beat and repaired by a
    # mind that never saw it.
    "comms": "comms_ops",
    "comms_ops": "comms_ops",
    # The remaining delegated families. A category that reaches no channel
    # is a change nobody is handed and nobody can encode, so it is detected
    # as an omission every beat and buys a repair from a mind that never
    # saw it -- measured live at 49.2s for two such events in one beat.
    "overlays": "overlays",
    "vitals": "vitals",
    "containment": "containment",
    "scales": "scales",
    "destruction": "destruction",
    "artifacts": "artifact_ops",
    "introductions": "introductions",
    "world_facts": "world_facts",
}

#: channel -> the specialist that owns it (derived, so the two cannot
#: disagree). The reconciliation repair router reads this: an omission in a
#: delegated channel is that channel's OWNER's to repair, at specialist
#: cost, never the prose author's at full-core cost.
_LIST_DELEGATED = frozenset({
    "cast_changes", "introductions", "world_facts", "contact_ops",
    "substance_ops", "remove_entities", "inventory_ops", "artifact_ops",
    "remove_rooms", "remove_adjacent", "crowd_ops", "courier_ops",
    "telling_ops", "offscreen_plan_ops", "ratified_claims",
    "contradicted_claims", "comms_ops",
})

#: Per-CHANNEL work gates: does this beat have possible work in this
#: channel? Every input is standing scene state or a structured declaration
#: -- never prose. FAIL OPEN is the rule: a channel is gated out only when
#: its subject provably does not exist (nobody wears anything, no vitals
#: tracked, no notice posted and nothing carried to post, nothing
#: destructible standing); where structure cannot decide, the channel is in
#: scope, which is why most gates degrade to `physical_beat`. The scope a
#: specialist is granted is the union the orchestrator measures itself by
#: (scope_report), and `_orchestration_scope_backstop` reports any channel
#: that shipped content without having been in a served scope.
#:
#: Two residuals are documented rather than closed, both backstopped:
#: dressing a fully bare body (attire gated on `anyone_wears`; caught by the
#: manifest half of the backstop) and posting an INVENTED claim with no
#: notice standing and nothing carried (artifact_ops; caught by the
#: reconciliation seam). `destruction` gates on a destructible ENTITY;
#: a narrated destruction of a bare room keeps its own deterministic
#: tripwire (`_narrated_destruction_subjects`), which stays core.
_CHANNEL_GATES = {
    "attire": lambda f: f["physical_beat"] and f["anyone_wears"],
    "conditions": lambda f: f["physical_beat"] or f["active_conditions"],
    "vitals": lambda f: f["physical_beat"] and f["vitals_tracked"],
    "overlays": lambda f: f["physical_beat"] or f["overlays_present"],
    "cast_changes": lambda f: f["physical_beat"],
    "introductions": lambda f: f["speech_present"],
    "world_facts": lambda f: f["speech_present"] or f["physical_beat"],
    "contact_ops": lambda f: f["physical_beat"] or f["contacts_standing"],
    "substance_ops": lambda f: (f["physical_beat"]
                                or f["material_effects_declared"]),
    "containment": lambda f: f["physical_beat"] or f["containment_active"],
    "scales": lambda f: f["physical_beat"] or f["scales_active"],
    "entities": lambda f: f["physical_beat"],
    "remove_entities": lambda f: f["physical_beat"],
    "inventory_ops": lambda f: f["physical_beat"],
    "artifact_ops": lambda f: f["physical_beat"] and (
        f["notices_in_scene"] or f["reports_carried"]),
    "destruction": lambda f: f["physical_beat"] and f["destructible_entity"],
    # Geography: every one of these changes by an act (moving, building,
    # sealing, sitting, rising), so the structural physical-beat fact is the
    # gate. Residual: a room's light changing on a pure time-skip beat
    # (dusk falls) is undecidable from state and is caught by the manifest
    # half of the backstop.
    "positions": lambda f: f["physical_beat"],
    "rooms": lambda f: f["physical_beat"],
    "remove_rooms": lambda f: f["physical_beat"],
    "remove_adjacent": lambda f: f["physical_beat"],
    "stations": lambda f: f["physical_beat"],
    "poses": lambda f: f["physical_beat"],
    # A channel is opened, closed, carried or installed by an ACT, so the
    # structural physical-beat fact gates it -- but a beat where anyone is
    # SPEAKING can also key a mic, which is the ordinary way an intercom gets
    # used. Fails open across both, per the rule this table follows.
    "comms_ops": lambda f: f["physical_beat"] or f["speech_present"],
    # The world's traffic: gated on its subjects EXISTING, which is what
    # makes this family cold in practice (0 fires in 2,243 beats) while
    # staying genuinely dispatchable the moment a crowd stands in a room or
    # a report is carried. Residuals, documented: a send/telling built on an
    # INVENTED claim with nothing carried, and minting a brand-new crowd in
    # a scene that had none -- both undecidable from state, both left to
    # the reconciliation seam, and both 0-fire channels today.
    "crowd_ops": lambda f: f["crowds_present"],
    "courier_ops": lambda f: f["couriers_present"] or f["reports_carried"],
    "telling_ops": lambda f: f["reports_carried"] or f["crowds_present"],
    "offscreen_plan_ops": lambda f: f["offscreen_planning_enabled"],
    "ratified_claims": lambda f: f["unratified_claims_present"],
    "contradicted_claims": lambda f: f["unratified_claims_present"],
}


# ---------------------------------------------------------------- extensions
#
# A seventh family, and an eighth, authored outside this tree.
#
# Every registry above is one an extension could only reach by mutating a
# module global, and there are SIX of them (`SPECIALISTS`, `_CHANNEL_GATES`,
# `_CHANNEL_SPECIALISTS`, `schemas.SPECIALIST_CHANNELS` + a model +
# `SCHEMA_MAP`, `prompts.SPECIALIST_PROMPT_SPECS`, `providers.ROLES`). Patching
# five of the six is not a degraded specialist -- `_dispatch_specialists` reads
# `SPECIALISTS` live and then indexes `_CHANNEL_GATES` by channel, so an
# unregistered gate is a KeyError inside the Director on every beat. This is
# the same shape `add_stage` was built to end: the execution half already
# worked, the REGISTRATION half was the part that forced a third party to edit
# an engine file.
#
# Three deliberate differences from an in-tree specialist, each because the
# alternative would be a quiet lie:
#
# * **Channels are namespaced `ext:<id>:<channel>`.** A family that could claim
#   `attire` would silently take ownership of the body specialist's channel and
#   replace it in the merged diff.
# * **Its channels are EVIDENCE, not causality.** No commit domain reads an
#   `ext:` channel, so a registered specialist's output lands in `state_diff`
#   and changes nothing by itself. The extension acts on it from its own commit
#   domain or stage -- which keeps the engine's own persistence honest and is
#   the same annotator default `ext:` steps already have.
# * **No prose-author chunk.** `PROSE_AUTHOR_SHEET` and its one-owner test live
#   in this tree; an extension cannot add a block to the sheet, so a registered
#   channel is written to the ledger and NOT narrated. Stated plainly in the
#   guide, because "it committed but nobody mentioned it" is otherwise a
#   fifty-beat mystery.
#
# The default gate fails open on `physical_beat`, which is the rule
# `_CHANNEL_GATES` already states: over-dispatch costs one call, under-dispatch
# silently drops work.

#: Channels a specialist family owns, recomputed rather than frozen at import.
#: It WAS a module-level comprehension over `SPECIALISTS`, which meant a family
#: registered afterwards was invisible to `_route_repair_omissions` while being
#: perfectly visible to dispatch -- a split that routes a repair to nobody.
_CHANNEL_SPECIALISTS = {
    channel: name
    for name, spec in SPECIALISTS.items() for channel in spec["channels"]
}


def _default_channel_gate(facts):
    return facts["physical_beat"]


def _rebuild_channel_owners():
    _CHANNEL_SPECIALISTS.clear()
    for name, spec in SPECIALISTS.items():
        for channel in spec["channels"]:
            _CHANNEL_SPECIALISTS[channel] = name


def register_specialist(ext_id, name, *, channels, prompt, gate=None,
                        role="default", label=None):
    """Add a Director specialist family owned by an extension.

    Returns its registered name. Raises on a name or channel that would
    collide with the engine's own, because a silent collision here transfers
    ownership of a real channel.
    """
    ext_id = str(ext_id or "").strip()
    name = str(name or "").strip()
    if not ext_id or not name:
        raise ValueError("a specialist needs an extension id and a name")
    full_name = f"ext:{ext_id}:{name}"
    wanted = [str(channel or "").strip() for channel in (channels or [])]
    if not wanted or not all(wanted):
        raise ValueError(f"specialist {full_name!r} declares no channels")
    if not str(prompt or "").strip():
        raise ValueError(f"specialist {full_name!r} declares no prompt")
    owned = [f"ext:{ext_id}:{channel}" for channel in wanted]
    for channel in owned:
        existing = _CHANNEL_SPECIALISTS.get(channel)
        if existing and existing != full_name:
            raise ValueError(
                f"channel {channel!r} already belongs to {existing!r}")

    SPECIALISTS[full_name] = {
        "step_key": full_name,
        "role": str(role or "default"),
        "channels": tuple(owned),
        "ext_id": ext_id,
        "prompt": str(prompt),
        "label": str(label or f"Specialist · {ext_id} · {name}"),
    }
    for channel in owned:
        _CHANNEL_GATES[channel] = gate if callable(gate) else _default_channel_gate
    _rebuild_channel_owners()
    return full_name


def unregister_specialists(ext_id):
    """Drop every specialist one extension registered. Returns their names."""
    prefix = f"ext:{str(ext_id or '')}:"
    dropped = [name for name in SPECIALISTS if name.startswith(prefix)]
    for name in dropped:
        for channel in SPECIALISTS[name]["channels"]:
            _CHANNEL_GATES.pop(channel, None)
        del SPECIALISTS[name]
    _rebuild_channel_owners()
    return dropped


def _extension_specialist_call(spec, scope, payload, language=None):
    """Run an extension-owned specialist. The CALL itself lives elsewhere.

    Deliberately a one-line delegation to `extension_runtime`. An extension
    owns the shape of its own channels, so its call cannot go through
    `_agent_json` -- that path validates against `schemas.SCHEMA_MAP`, which
    only knows this engine's own steps. But the permissive parse that follows
    from that must not live in THIS file: `test_stage_modules_stay_on_strict_path`
    forbids `jparse` in a stage module, and the rule is right -- a Director
    stage's own output reaches `commit.py` and must be strictly validated. The
    extension's does not (no commit domain reads an `ext:` channel), so the
    looseness is correct and belongs in the extension package, where it cannot
    be reached for by a future engine stage.
    """
    from extension_runtime import run_specialist_call

    return run_specialist_call(spec, scope, payload)

#: Prose-duty gates for the orchestrated PROSE AUTHOR's own sheet (the same
#: mechanism as _CHANNEL_GATES, pointed at prompts.PROSE_AUTHOR_SHEET's
#: chunks): per chunk, does this beat have possible work for that prose
#: duty? Same rules, verbatim: every input is standing scene state, a
#: structured declaration, or the payload ledger the duty is ABOUT -- never
#: prose -- and FAIL OPEN is the rule, which matters MORE here than for the
#: specialists: a needlessly-run specialist costs a second and a few hundred
#: tokens, while a wrongly-omitted prose block changes what the Director
#: WRITES. A chunk is gated out only when its subject provably does not
#: exist; several gates are EXACT (the duty is about a payload list, and the
#: gate reads that list), and the rest degrade to `physical_beat`/
#: `speech_present` where structure cannot decide.
#:
#: KNOWLEDGE FIREWALL, CHANGES MANIFEST, PLAYER-ASSERTED FACTS, DIALOGUE
#: LOG, the authority contract, the delegation contract, CONSEQUENCES ON THE
#: CLOCK and WEATHER have no gate here ON PURPOSE: the first five are
#: every-beat contract blocks (the firewall is an invariant, not an
#: optimization target), and the last two are undecidable from state (any
#: beat can set a future consequence; a window can show a changed sky from
#: an "enclosed" room) -- considered and left loaded rather than gated
#: optimistically.
#:
#: Documented residuals, all in the wrongly-cheap direction and all caught
#: by the prose half of `_orchestration_scope_backstop`: a bodiless voice
#: DEFINED on the very beat it first speaks (voices gates on one already
#: existing); a brand-new vehicle minted in a scene that had none (transit);
#: a light doused mid-beat in a fully-lit scene (light); a size change cast
#: on a beat the gate read as speech-only cannot happen (size gates on
#: physical_beat, and a spell is a declared action).
_PROSE_DUTY_GATES = {
    "voices": lambda f: f["bodiless_present"],
    "obligations": lambda f: (f["obligations_pending"]
                              or f["speech_present"]),
    "other_players": lambda f: f["other_players_declared"],
    "comm": lambda f: f["minds_apart"] or f["physical_beat"],
    "transit": lambda f: f["transit_capable"],
    # Exact presence, not a prediction: the payload either lists somebody
    # under way or it does not, and it is empty on the great majority of
    # beats -- so this is one of the few duties that genuinely costs nothing
    # when it is not needed.
    "travel": lambda f: f["travel_in_flight"],
    "mapping_proposal": lambda f: f["proposal_present"],
    "hearsay": lambda f: f["unratified_claims_present"],
    "road": lambda f: f["road_subjects_present"],
    "approach": lambda f: f["physical_beat"],
    "due_events": lambda f: f["due_events_present"],
    "world_pressure": lambda f: f["pressure_ledger_open"],
    "residue": lambda f: f["residue_present"],
    "light": lambda f: f["scene_not_fully_lit"],
    "size": lambda f: f["scales_active"] or f["physical_beat"],
}


def _true_on_error(read):
    """Fail open, per fact: a fact whose read fails is True, so its duty
    block loads. Never gate a prose block out on an error."""
    try:
        return bool(read())
    except Exception:
        return True


def _prose_gate_facts(ctx, sc, payload, facts, p_name):
    """The scene facts the prose-duty gates read, computed once at resolve
    time on top of the channel-gate facts (one `_gate_facts` call feeds
    both levels, so they cannot disagree about the scene). Standing scene
    state and the payload ledgers only; no prose anywhere."""

    def bodiless():
        from scene import ubiquitous_speaker_names
        return ubiquitous_speaker_names(sc)

    def minds_apart():
        # A remote listener is possible unless every tracked mind (player,
        # active cast, background presences) stands in ONE known room. Any
        # unknown position is undecidable -> True.
        names = [p_name] + [character_name_from_text(c["sheet"])
                            for c in ctx.cast]
        rooms = set()
        for name in names:
            room = room_of(sc, name)
            if not room:
                return True
            rooms.add(room)
        for presence in payload.get("background_presence_knowledge") or []:
            room = (presence or {}).get("room")
            if not room:
                return True
            rooms.add(room)
        return len(rooms) > 1

    def transit_capable():
        if sc.get("contained"):
            return True
        for room in (sc.get("rooms") or {}).values():
            if isinstance(room, dict) and room.get("parent_entity"):
                return True
        for entity in (sc.get("entities") or {}).values():
            if not isinstance(entity, dict):
                continue
            if entity.get("interior_rooms") or entity.get("parent_entity"):
                return True
            state = entity.get("state") \
                if isinstance(entity.get("state"), dict) else {}
            if state.get("transit") or state.get("link"):
                return True
        return False

    def proposal_content():
        # _normalize_scene_patch always yields the container keys, so an
        # empty proposal is a dict of empty containers -- content, not
        # truthiness, is the exact fact.
        proposal = payload.get("mapping_scene_proposal")
        if not isinstance(proposal, dict):
            return proposal
        return any(bool(value) for value in proposal.values())

    def not_fully_lit():
        # The engine's own sight semantics (spatial.effective_light: absent
        # means lit, spill lifts dark to dim): the light block is dead
        # weight only when EVERY room provably offers ordinary sight.
        from spatial import effective_light
        rooms = sc.get("rooms") or {}
        if not rooms:
            return True
        return any(effective_light(sc, rid) not in ("lit", "bright")
                   for rid in rooms)

    return {
        "physical_beat": facts["physical_beat"],
        "speech_present": facts["speech_present"],
        "scales_active": facts["scales_active"],
        "unratified_claims_present": facts["unratified_claims_present"],
        "road_subjects_present": (
            facts["crowds_present"] or facts["couriers_present"]
            or facts["reports_carried"] or facts["notices_in_scene"]),
        "bodiless_present": _true_on_error(bodiless),
        "obligations_pending": _true_on_error(
            lambda: payload.get("pending_obligations")),
        "other_players_declared": _true_on_error(
            lambda: payload.get("other_players_declarations")),
        "minds_apart": _true_on_error(minds_apart),
        "transit_capable": _true_on_error(transit_capable),
        "travel_in_flight": _true_on_error(
            lambda: payload.get("travel_in_flight")),
        "proposal_present": _true_on_error(proposal_content),
        "due_events_present": _true_on_error(
            lambda: payload.get("due_authored_events")),
        "pressure_ledger_open": _true_on_error(
            lambda: payload.get("world_pressure")),
        "residue_present": _true_on_error(
            lambda: payload.get("destination_residue")),
        "scene_not_fully_lit": _true_on_error(not_fully_lit),
    }


def _prose_author_scope(ctx, sc, payload, facts, p_name):
    """The prose author's granted scope: every prose-duty chunk whose gate
    reads possible work this beat. The same value selects the sheet
    (prompts.prose_author_prompt) and is what the backstop audits shipped
    duties against -- one computation, so the sheet and the audit cannot
    disagree. Fails open at every level: a failed fact read grants its
    chunk, a failed gate grants its chunk, and a failure computing the
    facts at all grants everything."""
    try:
        prose_facts = _prose_gate_facts(ctx, sc, payload, facts, p_name)
    except Exception:
        return list(PROSE_DUTY_CHUNKS)
    scope = []
    for name in PROSE_DUTY_CHUNKS:
        gate = _PROSE_DUTY_GATES.get(name)
        try:
            granted = True if gate is None else bool(gate(prose_facts))
        except Exception:
            granted = True
        if granted:
            scope.append(name)
    return scope


def _shipped_transit_state(sd):
    for entity in (sd.get("entities") or {}).values():
        if not isinstance(entity, dict):
            continue
        if entity.get("interior_rooms"):
            return True
        state = entity.get("state") \
            if isinstance(entity.get("state"), dict) else {}
        if state.get("transit") or state.get("link"):
            return True
    return any(isinstance(room, dict) and room.get("parent_entity")
               for room in (sd.get("rooms") or {}).values())


def _shipped_darkened_room(sd):
    from spatial import normalize_light
    return any(
        isinstance(room, dict) and room.get("light") is not None
        and normalize_light(room.get("light")) in ("dim", "dark")
        for room in (sd.get("rooms") or {}).values())


def _shipped_bodiless_definition(sd):
    from scene import is_ubiquitous_entity
    return any(is_ubiquitous_entity(entity)
               for entity in (sd.get("entities") or {}).values()
               if isinstance(entity, dict))


#: The prose half of the scope backstop: per gated chunk, deterministic
#: evidence in the FINAL output that its duty shipped anyway. Only the
#: chunks whose gate is a PREDICTION appear here; the exact-payload gates
#: (other_players, mapping_proposal, hearsay, due_events, world_pressure,
#: residue) read the very list their duty is about and cannot mispredict,
#: and `road`'s op channels are already audited by the specialist-channel
#: half (its gate facts are a superset of the offscreen dispatch gates).
_PROSE_DUTY_SHIPPED = {
    "voices": lambda out, sd: (
        "a bodiless (ubiquitous) voice was defined"
        if _shipped_bodiless_definition(sd) else None),
    "obligations": lambda out, sd: (
        "obligation ops shipped" if out.get("obligations") else None),
    "comm": lambda out, sd: (
        "a medium:'comm' line shipped"
        if any(isinstance(d, dict)
               and str(d.get("medium") or "").strip().lower() == "comm"
               for d in out.get("dialogue_log") or []) else None),
    "transit": lambda out, sd: (
        "transit/moving-room state was encoded"
        if _shipped_transit_state(sd) else None),
    "approach": lambda out, sd: (
        "a body was relocated" if sd.get("positions") else None),
    "light": lambda out, sd: (
        "a room was set dim or dark"
        if _shipped_darkened_room(sd) else None),
    "size": lambda out, sd: (
        "a size change was encoded" if sd.get("scales") else None),
}


def _gate_facts(ctx, sc, *, physical, speech, material_effects=False):
    """The scene facts every channel gate reads, computed once per stage,
    at that stage's own time. Standing scene state (ledgers, settings) plus
    the two structured beat facts the caller supplies; no prose anywhere.
    A fact whose read fails degrades to True -- fail open, never gate a
    channel out on an error."""
    chat_id = ctx.chat["id"]
    entities = sc.get("entities") or {}
    destructible = any(
        isinstance(e, dict) and (
            str(e.get("kind") or "").strip().casefold() in (
                "vehicle", "building", "structure", "ship", "boat")
            or e.get("interior_rooms"))
        for e in entities.values())
    try:
        notices = bool(_artifacts_view(chat_id, sc))
    except Exception:
        notices = True
    try:
        reports = bool(_carried_reports_view(ctx))
    except Exception:
        reports = True
    try:
        crowds = bool(_crowds_view(chat_id, sc))
    except Exception:
        crowds = True
    try:
        couriers = bool(_couriers_view(chat_id, sc))
    except Exception:
        couriers = True
    try:
        unratified = bool(_unratified_background_claims(
            chat_id, ctx.turn["idx"]))
    except Exception:
        unratified = True
    try:
        from living_world import living_world_allows, living_world_config
        planning = bool(living_world_allows(
            living_world_config(chat_id), "antagonist_ladder", "floor"))
    except Exception:
        # The one deliberate deviation from fail-open-on-error: plan ops are
        # refused deterministically at commit unless this setting is on, so
        # granting the chunk on a failed read could never yield an op commit
        # would accept -- it would only spend tokens on a dead channel.
        planning = False
    return {
        "physical_beat": bool(physical),
        "speech_present": bool(speech),
        "anyone_wears": any(
            bool(entry) for entry in (sc.get("attire") or {}).values()),
        "active_conditions": bool(q(
            "SELECT 1 FROM world_conditions WHERE chat_id=? AND active=1 "
            "LIMIT 1", (chat_id,))),
        "overlays_present": any(
            bool(v) for v in (sc.get("overlays") or {}).values()),
        "vitals_tracked": survival_enabled(chat_id),
        "contacts_standing": bool(sc.get("contacts")),
        "containment_active": bool(sc.get("contained")),
        "scales_active": any(
            isinstance(v, (int, float)) and float(v) != 1.0
            for v in (sc.get("scales") or {}).values()),
        "material_effects_declared": bool(material_effects),
        "notices_in_scene": notices,
        "reports_carried": reports,
        "destructible_entity": destructible,
        "crowds_present": crowds,
        "couriers_present": couriers,
        "unratified_claims_present": unratified,
        "offscreen_planning_enabled": planning,
    }


def _dispatch_specialists(ctx, sc, facts):
    """The orchestrator measuring how much of a job each specialist needs
    to do: per specialist, the SCOPE -- the set of its channels with
    possible work this beat. Everything else follows from that one value:
    an empty scope is a specialist not dispatched at all; a non-empty scope
    is dispatched with its sheet assembled from exactly those channels'
    chunks (prompts.specialist_prompt). Dispatch is `bool(scope)`, not a
    second decision that could disagree with the sheet assembly, and the
    single backstop below audits shipped content against the same value."""
    dispatch = {}
    for name, spec in SPECIALISTS.items():
        # `.get` with a fail-open default, not `[]`: a channel whose gate is
        # missing is a registration bug, and raising KeyError here would turn
        # it into a dead Director on every beat rather than one specialist
        # running more often than it needs to.
        scope = [channel for channel in spec["channels"]
                 if _CHANNEL_GATES.get(channel, _default_channel_gate)(facts)]
        dispatch[name] = {
            "run": bool(scope),
            "scope": scope,
            "channels": list(spec["channels"]),
            "facts": facts,
        }
    return dispatch


def _resolve_beat_view(out, decls, char_actions, dice, p_name, interp):
    """The finished beat as every resolve-side specialist reads it."""
    declared = {}
    for name, acts in (char_actions or {}).items():
        attempts = [str(a.get("attempt") or "") for a in acts
                    if isinstance(a, dict) and a.get("attempt")]
        if attempts:
            declared[name] = attempts
    player_attempts = [
        str(e.get("attempt") or "")
        for e in (interp.get("sequence") or [])
        if isinstance(e, dict) and e.get("type") == "action"
        and e.get("attempt")
    ]
    if player_attempts:
        declared[p_name] = player_attempts
    return {
        "source": "resolved_beat",
        "prose": out.get("resolved_event") or "",
        "dialogue": [
            {"speaker": d.get("speaker"), "exact_quote": d.get("exact_quote")}
            for d in (out.get("dialogue_log") or [])[:20]
            if isinstance(d, dict)
        ],
        "manifest": _manifest_items(out),
        "declared_actions": declared,
        "dice": dice if isinstance(dice, list) else [],
        "player": p_name,
        "cast": [str(d.get("name") or "") for d in decls if d.get("name")],
    }


def _interpret_beat_view(ctx, out, p_name):
    """The player's declaration as every interpret-side specialist reads
    it: the structured sequence (each element the player's own declared
    span), speech and movement -- NEVER `ctx.input` or `private_thought`,
    which can carry a private thought only the interpreting Director is
    entitled to read (the X19 lesson)."""
    sequence = []
    for element in (out.get("sequence") or []):
        if not isinstance(element, dict):
            continue
        sequence.append({
            k: element.get(k)
            for k in ("type", "text", "attempt", "raw_text", "commitment",
                      "targets", "asserted_effects", "intended_effects",
                      "volume")
            if element.get(k) is not None
        })
    declared = {}
    attempts = [str(e.get("attempt") or "") for e in sequence
                if e.get("type") == "action" and e.get("attempt")]
    if attempts:
        declared[p_name] = attempts
    return {
        "source": "player_declaration",
        "declaration": {
            "sequence": sequence,
            "speech": out.get("speech"),
            "movement": out.get("movement"),
        },
        "manifest": [],
        "declared_actions": declared,
        "dice": [],
        "player": p_name,
        "cast": [character_name_from_text(c["sheet"]) for c in ctx.cast],
    }


def _specialist_manifest_slice(name, view):
    """The numbered manifest entries in one specialist's categories.

    One definition, read twice: once to build the payload the specialist is
    given, once to record which ids it was HANDED (design note 21). Two
    spellings of this filter would mean a specialist could be judged on an
    event it never received.
    """
    channels = SPECIALISTS[name]["channels"]
    return [
        item for item in (view.get("manifest") or [])
        if _CATEGORY_CHANNELS.get(item.get("category")) in channels
    ]


def _specialist_payload(name, ctx, sc, view, extras):
    """One specialist's scoped payload -- its written entitlement, applied
    to whichever stage's beat view it was handed. Shared part: the beat
    (prose+dialogue at resolve, the declaration at interpret), declared
    action attempts, final dice, the beat's manifest entries in this
    specialist's categories, and the roster. Per-specialist part: its OWN
    ledgers, and a minimal name index where its subjects need naming. What
    is absent is the entitlement's other half: no room graph, no lore, no
    minds, no world machinery, never the raw player input, and never
    another specialist's ledgers."""
    spec = SPECIALISTS[name]
    payload = {
        "source": view["source"],
        "player": view["player"],
        "cast": view["cast"],
        "declared_actions": view["declared_actions"],
        "dice_results_final": view["dice"],
        "variant_seed": extras.get("nonce"),
    }
    if view["source"] == "resolved_beat":
        payload["resolved_event"] = view["prose"]
        payload["dialogue_log"] = view["dialogue"]
    else:
        payload["player_declaration"] = view["declaration"]
    manifest = _specialist_manifest_slice(name, view)
    if manifest:
        payload["changes_asserted"] = manifest

    rooms_index = {
        rid: str((room or {}).get("name") or rid)
        for rid, room in (sc.get("rooms") or {}).items()
    }
    # WORN GARMENTS, NAMEABLE BY EVERY HAND. Identity only -- the name and
    # whose body it is on -- never the wardrobe's state, coverage or
    # condition, which stay the body specialist's.
    #
    # A worn garment exists only inside sc.attire, so a specialist that
    # needed to name one could not: the contact specialist's live note says
    # it could not encode dampness on the shorts because "objects not in
    # entity_names", and the objects specialist minted `hinami_shorts` for
    # the same reason and said so. A hand that cannot name a thing invents
    # one, and the invention becomes a second record of a garment that
    # already existed.
    #
    # This widens who can be NAMED, not what is KNOWN -- the same category
    # as `rooms` and `entity_names`, which every relevant specialist
    # already carries. It is not another specialist's ledger: no state
    # crosses, and the firewall's subject is minds, which this does not
    # touch.
    worn_index = [
        {"name": str(garment), "worn_by": str(who)}
        for who, entry in (sc.get("attire") or {}).items()
        if isinstance(entry, dict)
        for garment in (entry.get("wearing") or [])
        if str(garment).strip()
    ]
    if name == "body":
        payload.update({
            "attire": scene_compact_attire(sc),
            "overlays": sc.get("overlays") or {},
            "active_awareness": extras.get("active_awareness"),
            "simulation_clock": extras.get("clock"),
            "rooms": rooms_index,
        })
        if extras.get("body_parts"):
            payload["body_parts"] = extras["body_parts"]
        if survival_enabled(ctx.chat["id"]):
            names = [view["player"]] + list(view["cast"])
            payload["vitals"] = {
                n: vitals_of(sc, n) for n in names if n
            }
    elif name == "social":
        payload["background_presences"] = sorted(
            (wget(ctx.chat["id"], "background_presences", {}) or {}).keys())
    elif name == "contact":
        payload.update({
            "contacts": extras.get("contacts")
                        if extras.get("contacts") is not None
                        else (sc.get("contacts") or []),
            "contained": sc.get("contained") or {},
            "scales": sc.get("scales") or {},
            "rooms": rooms_index,
            "entity_names": {
                eid: str((e or {}).get("name") or eid)
                for eid, e in (sc.get("entities") or {}).items()
            },
            "worn_garments": worn_index,
        })
        if extras.get("body_parts"):
            payload["body_parts"] = extras["body_parts"]
        if extras.get("contact_endings") is not None:
            payload["character_contact_endings"] = extras["contact_endings"]
        if extras.get("material_effects") is not None:
            payload["character_material_effects"] = extras["material_effects"]
    elif name == "objects":
        payload.update({
            "entities": sc.get("entities") or {},
            "rooms": rooms_index,
            "notices": extras.get("notices") or [],
            "worn_garments": worn_index,
        })
        if extras.get("proposal"):
            payload["mapping_scene_proposal"] = extras["proposal"]
    elif name == "spatial":
        # The one specialist entitled to the full graph: it is the graph's
        # keeper. Everything else here is the geography's own ledgers plus
        # each declared mover's heading -- never lore, minds, or bodies.
        payload.update({
            "rooms": sc.get("rooms") or {},
            "positions": sc.get("positions") or {},
            "stations": sc.get("stations") or {},
            "poses": sc.get("poses") or {},
            "contained": sc.get("contained") or {},
            "movement": extras.get("movement"),
            "movers": extras.get("movers") or {},
        })
        if extras.get("proposal"):
            payload["mapping_scene_proposal"] = extras["proposal"]
    elif name == "offscreen":
        # The traffic ledgers, exactly as the monolithic payload delivers
        # them (built precisely so a Director could name the uids its ops
        # require): crowds and couriers in reach, who carries which report,
        # the standing hearsay, the planning switch and its open plans.
        payload.update({
            "crowds": extras.get("crowds") or [],
            "couriers": extras.get("couriers") or [],
            "carried_reports": extras.get("carried_reports") or [],
            "unratified_claims": extras.get("unratified_claims") or [],
            "offscreen_planning": extras.get("offscreen_planning")
                                  or {"enabled": False, "plans": []},
            "rooms": rooms_index,
        })
    return payload


def _stage_container(out, stage, channel):
    """Where a channel lives in this stage's output: the resolve diff, or
    interpret's state_assertions -- except interpret's contact channel,
    which the interpret contract spells `contact_assertions` (the same ops,
    validated by `_validated_player_contact_assertions` downstream exactly
    as a model-authored copy would be)."""
    if stage == "interpret" and channel == "contact_ops":
        return out, "contact_assertions"
    key = "state_diff" if stage == "resolve" else "state_assertions"
    container = out.get(key)
    if not isinstance(container, dict):
        container = {}
        out[key] = container
    return container, channel


def _normalized_channel_value(channel, value):
    if channel == "destruction":
        return value if isinstance(value, dict) and value else None
    if channel in _LIST_DELEGATED:
        return value if isinstance(value, list) else []
    return value if isinstance(value, dict) else {}


#: The verdicts a specialist may return on a numbered event. Anything else
#: -- a blank, a synonym, a sentence -- is dropped rather than guessed at:
#: an unrecognized verdict must read as "this event was not addressed", the
#: same as silence, because the whole point of the echo is that only a
#: DELIBERATE answer counts as one.
_EVENT_VERDICTS = frozenset({"encoded", "already_true", "not_mine"})


def _resolved_event_verdicts(result, granted_ids):
    """One specialist's resolved_events, kept only where they answer an
    event this call was actually handed.

    An id outside `granted_ids` is discarded: a specialist cannot acquit an
    event it never saw, and a model that echoes the whole manifest back
    would otherwise silence every omission in the beat. Last verdict wins
    on a duplicated id -- deterministic, and the shape is already degenerate.
    """
    granted = {int(i) for i in granted_ids}
    verdicts = {}
    for entry in (result.get("resolved_events") or []):
        if not isinstance(entry, dict):
            continue
        try:
            event_id = int(entry.get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        status = str(entry.get("status") or "").strip().casefold()
        if event_id in granted and status in _EVENT_VERDICTS:
            record = {"status": status}
            # An address is only meaningful ON a decline, and only when it
            # names a hand that exists. Anything else is dropped rather
            # than carried into routing as a half-fact.
            target = str(entry.get("reroute_to") or "").strip().casefold()
            if status == "not_mine" and target in SPECIALISTS:
                record["reroute_to"] = target
            verdicts[event_id] = record
    return [{"event_id": eid, **verdicts[eid]}
            for eid in sorted(verdicts)]


def _index_addressed_events(dispatch):
    """event_id -> {owner, status}, across every specialist that ran.

    The beat-wide answer to "was this event addressed by the mind that owns
    it?". Only a specialist that RAN contributes: a failed call leaves its
    events unaddressed, which is what keeps a fail-open failure from
    silently acquitting the changes it was supposed to encode.
    """
    index = {}
    for name, state in (dispatch or {}).items():
        if not isinstance(state, dict) or not state.get("ran"):
            continue
        for entry in (state.get("events_resolved") or []):
            index[int(entry["event_id"])] = {
                "owner": name, "status": entry["status"],
                **({"reroute_to": entry["reroute_to"]}
                   if entry.get("reroute_to") else {})}
    return index


def _run_specialists(ctx, out, sc, dispatch, view, extras, stage):
    """Fan out to every dispatched specialist and assemble by ownership.

    Runs AFTER the stage's own output has settled (retries and validation
    done), because every specialist reads the finished beat; and BEFORE the
    stage's deterministic seams, so the movement backstop, the assertion
    validators, the restraint floor and the reconciliation manifest all
    judge the MERGED result -- the cross-channel judgments stay with the
    orchestrator, which is the deterministic code downstream of this call.

    Assembly is ownership per GRANTED channel: a specialist's answer
    replaces the stage model's content in the channels it was scoped to
    (the lean sheet told the author to leave them empty). A channel the
    specialist emitted OUTSIDE its scope -- despite its sheet carrying no
    block for it -- is under-grant evidence: never discarded (fail-open, it
    merges wherever the author left the channel empty) and always reported.
    A specialist that FAILS leaves the author's channels standing untouched
    and never kills the beat; the scope backstop reports its granted scope
    as unserved rather than letting the failure pass silently."""
    record = {"enabled": True, "stage": stage, "specialists": dispatch}
    out["orchestration"] = record

    # ---- Fan out: genuinely parallel, never streaming ------------------
    # Specialists produce structured output, not player-facing prose, so
    # they do not stream and there is nothing to interleave: each call runs
    # under a COPY of the caller's context with both streaming sinks
    # cleared. THE COPY IS MADE IN THE PARENT, ONE PER JOB, and handed to
    # the worker -- the narration.py precedent, whose comment is the whole
    # law: ThreadPoolExecutor workers do NOT inherit the submitting
    # thread's contextvars, so `contextvars.copy_context()` executed
    # INSIDE the worker copies an EMPTY context. This function did exactly
    # that for one release, and everything the copy exists to carry was
    # silently None inside every multi-specialist fan-out: `cancel_event`
    # (an aborted turn could not interrupt in-flight specialists),
    # `call_ledger_sink` (five specialist calls per resolve, zero ledger
    # entries -- measured on live variant v26648, one recorded call
    # against five ran=True specialists), `current_warning_sink` (a repair
    # ladder firing inside a specialist left no stored trace), and db's
    # `active_frame_id` (a frame-scoped read inside the fan-out resolved
    # to the PRESENT frame). The single-specialist path ran in the parent
    # thread and worked, which is what kept the defect quiet. A fresh copy
    # per job, never one shared -- a Context can only be entered by one
    # thread at a time.
    #
    # With the parent context carried in, `current_step_key` inside a
    # specialist call is the STAGE's own key, so its ledger entries and
    # warnings persist on the stage variant that owns the fan-out; the
    # entry's `role` (director_body, ...) keeps saying which specialist it
    # was. Results are collected per specialist and merged BELOW in
    # canonical SPECIALISTS order, never completion order, so the same
    # inputs produce the same merged diff on a rerun whatever order the
    # network answered in. A failed call becomes that specialist's
    # recorded error and never touches a sibling's completed work; Aborted
    # is the one exception that propagates, because a cancelled turn has
    # no beat to fail open into.
    def _call_isolated(name, state, context):
        def run():
            token_sink.set(None)
            generation_event_sink.set(None)
            spec = SPECIALISTS[name]
            if spec.get("ext_id"):
                # An extension-owned family: same isolation, same fail-open,
                # same canonical merge below -- only the sheet and the
                # validation differ, because neither prompts.py nor
                # schemas.SCHEMA_MAP knows a step key from outside this tree.
                return _extension_specialist_call(
                    spec, state["scope"],
                    _specialist_payload(name, ctx, sc, view, extras),
                    ctx.language)
            return _agent_json(
                spec["role"],
                spec["step_key"],
                specialist_prompt(name, state["scope"], ctx.language),
                _specialist_payload(name, ctx, sc, view, extras),
                temperature=0.2,
                max_tokens=None,   # the configured ceiling
            )
        return context.run(run)

    jobs = [(name, state) for name, state in dispatch.items()
            if state.get("run")]
    # Recorded BEFORE the call, from the same filter that builds the
    # payload: which numbered events this specialist is answerable for.
    # A verdict on anything else is discarded (_resolved_event_verdicts).
    for name, state in jobs:
        state["event_ids"] = [
            int(item["event_id"])
            for item in _specialist_manifest_slice(name, view)
            if item.get("event_id")
        ]
    results = {}
    if len(jobs) > 1 and not fanout_is_parallel():
        # SEQUENTIAL, by host choice. Same context copy per job, same
        # canonical assembly below, same fail-open -- the only difference is
        # that the calls do not overlap. Still cheaper than the monolith
        # was: a beat dispatches a mean 1.75 of 6 specialists and each
        # carries a 1-4k sheet against the single sheet's ~21k, so the work
        # is smaller even when none of it runs at once.
        for name, state in jobs:
            try:
                results[name] = _call_isolated(name, state,
                                               contextvars.copy_context())
            except Aborted:
                raise
            except Exception as exc:
                results[name] = exc
    elif len(jobs) == 1:
        name, state = jobs[0]
        try:
            results[name] = _call_isolated(name, state,
                                           contextvars.copy_context())
        except Aborted:
            raise
        except Exception as exc:
            results[name] = exc
    elif jobs:
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            # The comprehension runs on THIS thread, so every copy is of
            # the parent's live context (see the fan-out comment above).
            futures = {
                name: pool.submit(_call_isolated, name, state,
                                  contextvars.copy_context())
                for name, state in jobs
            }
        # The pool's __exit__ has joined every worker, so collection below
        # cannot block out of order and a first failure cannot orphan a
        # sibling still in flight.
        aborted = None
        for name, _state in jobs:
            try:
                results[name] = futures[name].result()
            except Aborted as exc:
                aborted = exc
            except Exception as exc:
                results[name] = exc
        if aborted is not None:
            raise aborted

    # ---- Assemble: canonical order, ownership per granted channel ------
    for name in SPECIALISTS:
        state = dispatch.get(name)
        if not state or not state.get("run"):
            continue
        result = results.get(name)
        if result is None or isinstance(result, Exception):
            state["ran"] = False
            state["error"] = str(result) if result is not None \
                else "no result"
            ctx.add_warning(
                f"{name} specialist failed; the stage model's own channels "
                f"stand (fail-open): {state['error']}")
            continue
        spec = SPECIALISTS[name]
        state["ran"] = True
        replaced, outside, filled = [], [], []
        for channel in spec["channels"]:
            container, key = _stage_container(out, stage, channel)
            authored = container.get(key)
            owned = _normalized_channel_value(channel, result.get(channel))
            if channel in state["scope"]:
                if authored and authored != owned:
                    replaced.append(channel)
                    ctx.add_warning(
                        f"orchestration: the stage model emitted {channel} "
                        f"despite the delegation; the {name} specialist's "
                        "channel replaced it (ownership).")
                container[key] = owned
                if owned:
                    filled.append(channel)
            elif owned:
                # Emitted with no chunk for it: scope under-grant. Fail
                # open -- asserted state is never discarded -- and report.
                outside.append(channel)
                if not authored:
                    container[key] = owned
        state["channels_replaced"] = replaced
        # What this specialist actually CONTRIBUTED -- distinct from
        # `channels_replaced`, which counts author content that lost to
        # ownership and is therefore [] on every healthy beat (the lean
        # author is told to leave delegated channels empty). Two separate
        # investigations of one live beat read replaced=[] as "the
        # specialists assembled nothing" while the merged diff carried
        # their encodings; this field is what lets the record say so.
        state["channels_filled"] = filled
        if outside:
            state["outside_scope"] = outside
            note = (
                f"orchestration scope: the {name} specialist emitted "
                + ", ".join(outside) + " outside its granted scope "
                f"({state['scope']}). Content was kept (fail-open); the "
                "scope gate under-granted and should be widened if this "
                "recurs.")
            ctx.tell_director(note)
            ctx.add_warning(note)
        # The numbered manifest slice, answered. Kept per specialist AND
        # folded into one beat-wide index below, because the question the
        # repair seam asks is "did the mind that OWNS this event address
        # it?" -- an id claimed by a specialist that was never handed it is
        # not an answer, so the owner is recorded with the verdict.
        state["events_resolved"] = _resolved_event_verdicts(
            result, state.get("event_ids") or [])

        notes = [str(n) for n in (result.get("notes") or [])
                 if str(n).strip()]
        if notes:
            state["notes"] = notes
            for note in notes:
                ctx.add_warning(f"{name} specialist: {note}")
                ctx.tell_director(f"{name} specialist: {note}")

    record["events_addressed"] = _index_addressed_events(dispatch)



#: Channels whose existence is a property of the STORY, not of the beat: the
#: gate is false because the ledger is switched off, so no beat can ever put
#: work in them and an unserved one is never a mispredict.
_STRUCTURAL_CHANNEL_FACTS = {"vitals": "vitals_tracked"}


def _structurally_absent_channels(specialists):
    """Channels that cannot be served in this story whatever the beat holds."""
    facts = {}
    for state in (specialists or {}).values():
        if isinstance(state, dict) and isinstance(state.get("facts"), dict):
            facts = state["facts"]
            break
    return {channel for channel, fact in _STRUCTURAL_CHANNEL_FACTS.items()
            if fact in facts and not facts.get(fact)}


def _orchestration_scope_backstop(ctx, out, stage):
    """`changes_asserted` reconciliation pointed at the SCOPE.

    Runs LAST, on the final reconciled output, and only on the orchestrated
    path. One check covers both a wrongly-skipped specialist and a wrongly
    omitted chunk, because both are the same fact: a channel was not in any
    SERVED scope (granted to a specialist that ran) and content for it
    shipped anyway -- a manifest entry in that channel's category, or
    channel content in the final output (the stage model's own, or the
    repair seam's). Every such channel is REPORTED through `tell_director`
    and never dropped: fail-open means the unowned content stands and the
    existing deterministic seams keep judging it.

    The record also carries the per-beat scope measurement the experiment
    is judged by: granted vs served vs produced, where over-grant is only
    cost and under-grant is the dangerous direction this backstop exists
    to catch."""
    record = out.get("orchestration") or {}
    if not record.get("enabled"):
        return
    specialists = record.get("specialists") or {}
    granted, served = set(), set()
    failed = []
    for name, state in specialists.items():
        scope = set(state.get("scope") or ())
        granted |= scope
        if state.get("run") and state.get("ran"):
            served |= scope
        elif state.get("run"):
            failed.append(name)
    produced = []
    flags = []
    for channel in _DELEGATED_CHANNELS:
        container, key = _stage_container(out, stage, channel)
        if container.get(key):
            produced.append(channel)
            if channel not in served:
                flags.append(f"{key} carries content for {channel!r}")
    if stage == "resolve":
        # A channel can be unserved for two different reasons, and only one
        # of them is a gate mispredict. "No work in it THIS BEAT" is a
        # prediction, and a manifest item naming it is evidence the
        # prediction was wrong. "This story has no such ledger AT ALL" is
        # not a prediction -- a story with survival off has no vitals to
        # change, ever -- so a manifest item naming it says the Director
        # mis-categorised, not that the gate misfired.
        #
        # Measured live (chat 71, survival off): the resolve filed a
        # climax's spent-ness under `vitals` because 8.2.2 told it to take
        # the CLOSEST category and never omit, and the backstop announced
        # "the scope gate mispredicted" about a channel that shipped
        # nothing and could never have shipped anything. A warning that
        # fires when nothing is wrong is how a reader learns to skip
        # warnings, so this one is told apart from the real thing and sent
        # to the Director as the categorisation note it actually is.
        structural = _structurally_absent_channels(specialists)
        for item in _manifest_items(out):
            channel = _CATEGORY_CHANNELS.get(item.get("category"))
            if not channel or channel in served:
                continue
            subject = item.get("subject") or "an unnamed subject"
            if channel in structural:
                ctx.tell_director(
                    f"categorisation: a {item['category']} change was "
                    f"asserted for {subject!r}, but this story keeps no "
                    f"{channel} ledger, so nothing can record it. File a "
                    f"change like this under the closest category this "
                    f"story DOES keep, or leave it to the prose.")
                continue
            flags.append(
                f"the prose asserts a {item['category']} change for "
                f"{subject!r} ({channel} was not in any served scope)")
    # The prose half, same mechanism: the beat's final output shows a duty
    # whose prose-author block was not loaded. Only on records that carry a
    # prose scope (the orchestrated resolve; interpret's sheet is not yet
    # leaned), and only for the chunks whose gate is a prediction
    # (_PROSE_DUTY_SHIPPED). Reported, never dropped: the model did the
    # duty anyway, so the flag is gate-misprediction evidence, not a loss.
    prose = record.get("prose_scope")
    if stage == "resolve" and isinstance(prose, dict):
        prose_granted = set(prose.get("granted") or ())
        final_diff = out.get("state_diff")
        final_diff = final_diff if isinstance(final_diff, dict) else {}
        for name, probe in _PROSE_DUTY_SHIPPED.items():
            if name in prose_granted:
                continue
            try:
                evidence = probe(out, final_diff)
            except Exception:
                evidence = None
            if evidence:
                flags.append(
                    f"{evidence}, and the prose author's {name!r} duty "
                    "block was not loaded (widen its gate if this recurs)")
    record["scope_report"] = {
        "granted": sorted(granted),
        "served": sorted(served),
        "produced": sorted(produced),
    }
    if not flags:
        return
    # A FAILED specialist is not a mispredicted gate. Its scope was granted
    # correctly and simply went unserved, so the author's own content
    # standing in that channel is fail-open working exactly as designed --
    # blaming the gate for it sends the next reader to widen a gate that
    # was already right. Measured live: a contact call died on a provider
    # returning reasoning with no answer, and the backstop reported "the
    # scope gate mispredicted" for a channel the gate had granted.
    if failed:
        note = (
            "orchestration: "
            + ", ".join(failed) + " specialist call(s) failed, so their "
            "granted scope went unserved and the stage model's own content "
            "stands there (fail-open, working as designed) -- "
            + "; ".join(flags)
            + ". Nothing was dropped and the reconciliation seam stands. "
            "The gate is not implicated; the CALL failed.")
        ctx.tell_director(note)
        ctx.add_warning(note)
        return
    why = "the scope gate read the scene as having no such work"
    note = (
        "orchestration gate: content shipped for channels or prose duties "
        "outside any served scope -- " + why + " -- "
        + "; ".join(flags)
        + ". Nothing was dropped (fail-open); the stage model's encoding "
        "and the reconciliation seam stand. The scope gate mispredicted."
    )
    record["gate_flags"] = flags
    ctx.tell_director(note)
    ctx.add_warning(note)


class CampaignInvariantError(RuntimeError):
    """An extension's campaign rule the Director could not be made to obey.

    Raised only by a validator registered `on_error="fail"`, and only after the
    one correction attempt has come back still in violation. It ends the beat
    before commit opens a transaction, which is the whole point: a campaign
    whose rules were broken is worse than a beat that did not happen, and a
    turn that fails here leaves nothing behind to unpick.
    """


def director_resolve(ctx, nonce, _corrections=None):
    chat = ctx.chat
    interp = _dict(ctx.director_interpret)
    flow = _dict(interp.get("flow"))
    turn = ctx.turn
    pers = persona_of(chat)
    p_name = pers.get("name") or persona_name(pers)
    mapping = ctx.mapping_stage or ctx.mapping_quick or {}
    fm = fiction_model(chat["id"])
    clock = simulation_clock(chat["id"])

    dice = []
    for d in _dict_list(flow.get("dice")):
        seed = f"{chat['id']}:{turn['idx']}:{nonce}:{d.get('actor')}:{d.get('attempt')}"
        rng = random.Random(seed)
        roll = rng.randint(1, 20)
        mod = _ability_mod(d.get("actor"), d.get("ability"), ctx)
        dc = {"easy": 8, "medium": 12, "hard": 16, "extreme": 20}.get(
            str(d.get("difficulty", "medium")).lower(), 12)
        dice.append({
            **d, "seed": seed, "roll": roll, "modifier": mod,
            "dc": dc, "outcome": "success" if roll + mod >= dc else "failure",
            "margin": roll + mod - dc,
        })

    decls = []
    char_speech = {}
    char_actions = {}

    loop = ctx.interaction_loop or {}
    loop_declarations = loop.get("combined_declarations") or []

    # Include reaction results
    reaction_loop_result = ctx.reaction_loop or {}
    reaction_declarations = []
    for r_round in (reaction_loop_result.get("rounds") or []):
        rid = r_round.get("reactor_id")
        rname = r_round.get("reactor")
        rseq = (r_round.get("result") or {}).get("sequence") or []
        reaction_declarations.append({
            "char_id": rid, "name": rname, "sequence": rseq,
            "is_reaction": True,
            "follow_op": (r_round.get("result") or {}).get("follow_op"),
            "material_effects": (
                (r_round.get("result") or {}).get("material_effects") or []),
            "speech": next((e.get("text") for e in rseq if e.get("type") == "speech"), None),
            "action": next((e for e in rseq if e.get("type") == "action"), None),
        })

    all_declarations = reaction_declarations + loop_declarations

    # Which character ids the reaction/interaction loops already speak for.
    # Any cast member with a character_results entry NOT covered here (a
    # parallel character:<id> step, including ones hydrated from an older
    # persisted plan shape) is merged below rather than silently dropped --
    # previously the mere presence of loop declarations made this function
    # ignore ctx.character_results entirely, so those characters' speech
    # never reached dialogue_log even though perception_outcome still
    # injected their actions.
    covered_ids = set()
    for declaration in all_declarations:
        try:
            covered_ids.add(int(declaration.get("char_id")))
        except (TypeError, ValueError):
            continue

    for declaration in all_declarations:
        char_id = declaration.get("char_id")
        name = declaration.get("name")
        sequence = declaration.get("sequence") or []
        decls.append({
            "char_id": char_id, "name": name, "sequence": sequence,
            "is_reaction": declaration.get("is_reaction", False),
            "follow_op": declaration.get("follow_op"),
            "material_effects": declaration.get("material_effects") or [],
            "speech": next((e.get("text") for e in sequence
                            if e.get("type") == "speech"), None),
            "action": next((e for e in sequence
                            if e.get("type") == "action"), None),
        })
        speeches = [{"text": e["text"], "volume": e.get("volume", "normal"),
                     "tone": e.get("tone", ""),
                     "visibility": e.get("visibility", "overt"),
                     "conceal_from": e.get("conceal_from") or []}
                    for e in sequence if e.get("type") == "speech" and e.get("text")]
        if speeches:
            char_speech.setdefault(name, []).extend(speeches)
        for event in sequence:
            if event.get("type") == "action" and event.get("attempt"):
                char_actions.setdefault(name, []).append(event)

    for c in ctx.cast:
        if int(c["id"]) in covered_ids:
            continue
        dk = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        cname = character_name(sh)
        if dk:
            decls.append({
                "char_id": c["id"],
                "name": dk.get("name") or cname,
                "sequence": dk.get("sequence") or [],
                "speech": dk.get("speech"), "action": dk.get("action"),
                "follow_op": dk.get("follow_op"),
                "material_effects": dk.get("material_effects") or [],
            })
            speeches = []
            for e in (dk.get("sequence") or []):
                if e.get("type") == "speech" and e.get("text"):
                    speeches.append({"text": e["text"],
                                     "volume": e.get("volume", "normal"),
                                     "tone": e.get("tone", ""),
                                     "visibility": e.get("visibility", "overt"),
                                     "conceal_from": e.get("conceal_from") or []})
            if not speeches and dk.get("speech"):
                speeches.append({"text": dk["speech"], "volume": "normal", "tone": "",
                                  "visibility": "overt", "conceal_from": []})
            if speeches:
                char_speech.setdefault(cname, []).extend(speeches)
            # The SEQUENCE first, exactly as the loop branch above reads it.
            # This branch used to read `dk["action"]` alone, so a declaration
            # that carried its acts only in the sequence -- the canonical
            # field, which is why `_sync_sequence_mirrors` exists -- produced
            # an EMPTY char_actions entry for a character who had plainly
            # acted. Latent while nothing consequential read char_actions for
            # this branch; character-act authority reads it to decide whether
            # a character declared any act at all, and an empty entry there
            # means "declared nothing", which is the strictest reading there
            # is. It also fed `_declared_act_texts` and the resolve payload
            # short.
            acts = [e for e in (dk.get("sequence") or [])
                    if e.get("type") == "action" and e.get("attempt")]
            dk_act = dk.get("action") or {}
            if not acts and dk_act.get("attempt"):
                acts = [dk_act]
            if acts:
                char_actions.setdefault(cname, []).extend(acts)

    sc = get_scene(chat["id"], chat)
    onset_contacts = interp.get("contact_assertions") or []
    character_contact_endings = _validated_character_contact_endings(
        ctx, sc, report=lambda note: ctx.add_warning(
            f"character contact: {note}"))
    character_material_effects = _character_material_effects(
        ctx, report=lambda note: ctx.add_warning(
            f"character material: {note}"))
    # The assertion is already true at action onset: show it to the resolving
    # Director as the standing relation reactions were based on. Copy-only;
    # durable state is composed into the final diff below.
    resolve_sc = apply_contact_ops(
        json.loads(json.dumps(sc)), onset_contacts, _age=False)
    # Same for everything else the player asserted: the resolving Director
    # must see the body the reactors saw, or it re-resolves the beat against
    # an outfit already off and a posture already changed when they decided.
    onset_state = interp.get("state_assertions")
    onset_state = onset_state if isinstance(onset_state, dict) else {}
    resolve_sc = preview_player_state_assertions(
        resolve_sc, onset_state, ctx, p_name)
    # Each declaring character's own heading, exactly as the player already
    # gets one in director_interpret. The room graph is undirected, so
    # "steps through the doorway" and "turns west" name a set of doorways
    # without saying which -- and resolving that without a heading is the
    # coin flip _egocentric_exits was written to end. It was only ever
    # wired to the player: a character declaring "turn west and step
    # through" was measured (maze arm A11, beat 11) being moved NORTH,
    # back the way he came, into the room he had just left, while the
    # resolved event still narrated it as west. He then reasoned from that
    # prose, so one coin flip corrupts every beat after it.
    for declaration in decls:
        if not declaration.get("name"):
            continue
        declaration["exits"] = _egocentric_exits(sc, declaration["name"])
        # What a RUN buys this mover, per passage: the engine's own figure,
        # from room size and how far the passage can be seen along. Given
        # here so a declared sprint resolves against a computed ceiling
        # rather than the Director's sense of how fast a person is.
        here = room_of(sc, declaration["name"])
        if here:
            declaration["sprint_reach"] = sprint_reach(sc, here)
    raw_intents = wget(chat["id"], "standing_intentions", []) or []
    # Lazy import: commit.py owns the ledger's deterministic semantics
    # (OBLIGATION_OVERDUE_AGE, the commit-side re-deferral reminder); the
    # payload view is built there so the flag the prompt's hard rule keys
    # on and the flag commit warns on can never disagree. world_pressure_view
    # rides the same convention (F5).
    from commit import pending_obligation_view, world_pressure_view
    _mv_for_context = interp.get("movement")
    _mv_target = _mv_for_context.get("to_room") if isinstance(_mv_for_context, dict) else None

    # Living world, approach A: when this beat moves the party into a room
    # they have been away from, hand the resolve the capped present-tense
    # diff (routines.residue_for) so the room is staged as it now stands
    # rather than as last seen. Movement-gated -- a quiet beat gets no
    # residue to be tempted by -- and deterministic, so a reroll stages the
    # same room the same way. Delivered to THIS payload only: no character
    # receives it; what a mind knows about a room rides its own gap record.
    _destination_residue = None
    _offscreen_planning = {"enabled": False, "plans": []}
    try:
        from living_world import living_world_allows, living_world_config
        _living_cfg = living_world_config(chat["id"])
        _offscreen_planning["enabled"] = living_world_allows(
            _living_cfg, "antagonist_ladder", "floor")
        if _offscreen_planning["enabled"]:
            _offscreen_planning["plans"] = (
                wget(chat["id"], "offscreen_plans", []) or [])[:8]
    except Exception as exc:
        ctx.add_warning(f"offscreen plan context skipped: {exc}")
    if _mv_target:
        try:
            if living_world_allows(_living_cfg,
                                   "routine_residue", "floor"):
                from routines import residue_for
                _destination_residue = residue_for(
                    chat["id"], sc, _mv_target,
                    frame_id=ctx.turn.frame_id,
                    now_seconds=float(
                        (clock or {}).get("elapsed_seconds") or 0.0))
                # Instrumentation, stashed for the commit blob: residue is
                # payload-side, so `tools/fire_rates.py` (which reads commit
                # results) could never see it -- the one living-world floor
                # with no measurable denominator, in the codebase whose
                # costliest recurring discovery is mechanisms nobody could
                # tell were dead. Opportunity = a movement-declaring beat
                # with the floor on; fires = facts actually delivered.
                ctx["_destination_residue_report"] = {
                    "to_room": str(_mv_target),
                    "delivered": len((_destination_residue or {})
                                     .get("facts") or []),
                }
        except Exception as exc:
            ctx.add_warning(f"destination residue skipped: {exc}")

    # W5's light authority appraisal hint: each present person's evident
    # public role/standing (never private history), for the prompt's
    # AUTHORITY APPRAISAL rule -- an order across a standing gap is
    # contestable, not auto-executed.
    social_standing = {
        character_name_from_text(c["sheet"]):
            (character_public_history(json.loads(c["sheet"])) or "")[:240]
        for c in ctx.cast
    }
    social_standing[p_name] = (persona_public_history(pers) or "")[:240]

    # Authored structured extra body parts, card-read: {} for ordinary casts.
    _resolve_parts = scene_extra_parts(ctx.cast, pers, p_name)

    payload = {
        # Authored house style, for the prose and any world detail this stage
        # mints. director_interpret deliberately does NOT get it: that stage
        # reads what the player declared, and a style note there would bias
        # interpretation of the player's own words rather than shape new content.
        **({"style_guide": style_guide(chat["id"])}
           if style_guide(chat["id"]) else {}),
        "scene": {
            "location": sc.get("location"),
            # Filtered to nearby rooms for the payload only -- the
            # deterministic passable-route check below keeps using the
            # full, unfiltered `sc`.
            "rooms": _contextual_rooms(
                sc, ctx.cast, ctx.get("_player_room"), _mv_target,
            ),
            "entities": sc.get("entities"),
            "positions": sc.get("positions"),
            "stations": sc.get("stations") or {},
            "following": sc.get("following") or {},
            # The contact ledger it is asked to MAINTAIN. Withheld until now,
            # which is the cause of the drift the displacement rule repairs
            # downstream: a Director that cannot see it wrote `hand -> waist`
            # one beat and `hand -> side` the next, not renaming anything but
            # writing fresh each time, blind. Showing the exact part nouns
            # already on record is what lets a re-assertion BE one.
            "contacts": resolve_sc.get("contacts") or [],
            # One line per body instead of the structured view: 3,789 chars
            # to 1,314 on chat 67, ~618 tokens off every resolve call. The
            # names the Director writes back are all still here, and
            # `attire.resolve_garment` was already built to bind the loose
            # handles it writes against what the body actually wears.
            "attire": scene_compact_attire(sc),
            # Authored structured extra body parts, one line list per body
            # that declared any (see character_schema.EXTRA_PART_ASPECTS).
            # Their part nouns are valid contact endpoints; clothing over the
            # attachment region does not remove a through-clothing part. Key
            # absent when nobody declared one, so the shape -- and therefore
            # the provider prefix cache -- is unchanged for ordinary casts.
            **({"body_parts": {
                    name: extra_parts_lines(parts)
                    for name, parts in _resolve_parts.items()}}
               if _resolve_parts else {}),
            "time": sc.get("time"),
        },
        "simulation_clock": clock,
        # Who is currently under, and the condition_id each one must be
        # re-emitted with to END it (see the WAKING block). Without this the
        # Director could not close a condition even when it wanted to: it was
        # never shown the id, and across 1483 live resolves it never once did.
        "active_awareness": _awareness_view(
            chat["id"], clock, interp, char_actions),
        "paradox": paradox_visible_to(chat["id"], ctx.turn.frame_id),
        "fiction_model": fm,
        "fiction_frame": _dict(flow.get("fiction_frame")),
        "mapping_scene_proposal": _normalize_scene_patch(mapping.get("scene_patch")),
        # Walks already under way that this beat did not mention. Handed to
        # the author BEFORE the prose is written so the scenery changes on
        # the page, in the same breath as everything else the beat does --
        # computing the leg afterwards would move bodies the resolve had
        # just described standing still.
        "travel_in_flight": _travel_in_flight_view(sc, interp, p_name),
        "player_declaration": {
            "ABSOLUTE": True,
            "sequence": interp.get("sequence") or [],
            "speech": interp.get("speech"),
            "speech_volume": interp.get("speech_volume", "normal"),
            "action": interp.get("action"),
            "movement": interp.get("movement"),
            "follow_op": interp.get("follow_op"),
            "contact_assertions": onset_contacts,
            "abilities": persona_abilities(pers),
            "authority_claims": (interp.get("flow") or {}).get("authority_claims") or [],
            # PLAYER AUTHORITY MODE. `ABSOLUTE` above is unchanged by it and
            # always will be: what the player SAID and ATTEMPTED is fixed in
            # every mode, and no mode has ever let this stage rewrite it. What
            # a restricted mode moves is the part of a declaration that
            # asserted an OUTCOME -- those arrive here already downgraded to
            # contestable intents, so the ordinary machinery adjudicates them
            # with no special case.
            #
            # The list is here so the downgrade can be ANSWERED in the same
            # beat. `tell_director` reaches the next one, which is a beat too
            # late for the player who is reading this one.
            **({"authority_mode": interp.get("authority_mode"),
                "downgraded_assertions": interp.get("authority_downgrades")}
               if interp.get("authority_downgrades") else {}),
        },
        "other_players_declarations": [
            {
                "persona_id": extra["persona_id"],
                "name": extra["name"],
                "ABSOLUTE": True,
                "sequence": (interp.get("other_players") or {}).get(str(extra["persona_id"]), {}).get("sequence") or [],
                "speech": (interp.get("other_players") or {}).get(str(extra["persona_id"]), {}).get("speech"),
                "action": (interp.get("other_players") or {}).get(str(extra["persona_id"]), {}).get("action"),
            }
            for extra in ctx.extra_players
        ],
        "character_declarations": decls,
        # Completed, self-owned contact endings declared structurally by the
        # character stage.  These exact onset-ledger removals are projected at
        # the commit seam below; resolve should narrate their consequences and
        # must not echo the ended contact as current state.
        "character_contact_endings": character_contact_endings,
        # Completed actor-owned physical outputs. The Director renders these;
        # the projection below also commits valid ones if prose/diff omits
        # them, just as character-owned contact endings survive omission.
        "character_material_effects": character_material_effects,
        "character_abilities": {
            character_name_from_text(c["sheet"]): character_abilities(json.loads(c["sheet"]))
            for c in ctx.cast
        },
        "dice_results_final": dice,
        "dialogue_mode": bool(flow.get("dialogue_mode", False)),
        "relevant_lore": lore_for(ctx),
        "standing_intentions": raw_intents[:12],
        "offscreen_planning": _offscreen_planning,
        "pending_obligations": pending_obligation_view(chat["id"], turn["idx"]),
        # F5: the world-pressure ledger -- every open ongoing off-character
        # process, each of which the prompt's WORLD PRESSURE rule requires
        # this resolve to tick, hold, or resolve. Deterministic floor: the
        # must-tick retry below plus commit_world_pressure's implicit-hold
        # warnings make silence a recorded choice, never a default.
        "world_pressure": world_pressure_view(chat["id"], turn["idx"]),
        # The crowds standing in rooms the party can reach, WITH their uids.
        # Without this the resolve prompt asks the Director to "use the
        # crowd_id perception showed you" and then shows it nothing: `move`,
        # `split`, `emerge`, `absorb` and `disperse` all require an id the
        # Director had no way to learn, so only minting a new crowd was
        # reachable and every other op refused. Found by reading the captured
        # payload as the model, which is the only way to find it -- the schema
        # check cannot see a field that exists and is never delivered.
        "crowds": _crowds_view(chat["id"], sc),
        # The couriers on the road, WITH their uids -- same defect class as
        # the crowd uid: `question` and `silence` require a courier_id the
        # Director could otherwise never have seen, and `send` needs to know
        # the road is not already full.
        "couriers": _couriers_view(chat["id"], sc),
        # The notices standing in scene rooms, WITH their uids and their
        # claims: `read` and `remove` require an artifact_id, and resolving
        # "she reads the bill" requires the Director -- who owns objective
        # causality and is entitled to omniscience -- to know what the bill
        # says. Perception deliberately shows every other mind only that
        # paper hangs there.
        "notices": _artifacts_view(chat["id"], sc),
        # The reports this beat's characters are carrying, as ids the Director
        # can name in `telling_ops`. Same defect, same cause: the prompt asks
        # for a `world_event_id` and the Director never saw one, so a
        # character could invent a claim and could never pass on a true one.
        "carried_reports": _carried_reports_view(ctx),
        "social_standing": social_standing,
        # Player-authored future beats scheduled earlier and due NOW: enact them
        # as occurring this beat (see director_interpret). commit re-queues any
        # left unresolved rather than dropping them.
        "due_authored_events": (ctx.director_interpret or {}).get("due_authored_events") or [],
        # See director_interpret: already-completed mechanical transitions
        # (timed arrivals) the prose should acknowledge, not re-resolve.
        "engine_notices": wget(chat["id"], "engine_notices", []),
        # Living world, approach A: the entered room's capped present-tense
        # diff, staged as current state (see the DESTINATION RESIDUE prompt
        # rule). Absent on beats without an eligible re-entry, so the
        # default path is byte-identical to a world without the feature.
        **({"destination_residue": _destination_residue}
           if _destination_residue else {}),
        # Hearsay a background presence asserted on an earlier beat, still
        # unratified. You are the only ratifier -- adopt, contradict, or ignore
        # (background_claims.py).
        "unratified_claims": _unratified_background_claims(chat["id"], turn["idx"]),
        # The epistemic envelope of every voiceable presence: where it stands
        # and when it appeared. YOU are entitled to the omniscient record; a
        # presence you voice is not -- it knows its role, its own room as
        # anyone standing there sees it now, and what was said in its earshot
        # since it appeared. The deterministic floor on dialogue_log enforces
        # the entity-reference slice of this; the rest rides on the prompt's
        # presence-knowledge rule keying off this block.
        "background_presence_knowledge": [
            {"name": _pn,
             "room": room_of(sc, _pn)
                     or ((_pr.get("sketch") or {}).get("station_room") or ""),
             "appeared_turn": _pr.get("first_turn")}
            for _pn, _pr in
            (wget(chat["id"], "background_presences", {}) or {}).items()
        ],
        "interaction_rounds": _round_conduct(loop.get("rounds")),
        "reaction_rounds": _round_conduct((ctx.reaction_loop or {}).get("rounds")),
        "variant_seed": nonce,
    }

    # Orchestrated Director (design note 19): dispatch -- the scope each
    # specialist is granted -- is decided HERE, at this stage's own time,
    # from the scene as it stands after every character declared, never
    # inherited from interpret. The prose author keeps the same role, step
    # key, schema and payload either way; only the instruction sheet is
    # lean when the delegated machinery is cold-stored in the specialists.
    _orch_dispatch = None
    _prose_scope = None
    if True:
        _orch_facts = _gate_facts(
            ctx, sc,
            physical=_beat_has_physical_activity(interp, char_actions, dice),
            speech=bool(char_speech) or bool(player_speech_lines(interp)),
            material_effects=bool(character_material_effects),
        )
        _orch_dispatch = _dispatch_specialists(ctx, sc, _orch_facts)
        # The prose author's OWN scope (same mechanism as the specialists'
        # channel scopes, same facts, same fail-open): which conditional
        # prose-duty blocks this beat can have work for. The sheet is
        # assembled from the core plus exactly those chunks; the scope is
        # persisted below and audited by the same backstop.
        _prose_scope = _prose_author_scope(
            ctx, sc, payload, _orch_facts, p_name)
    _resolve_prompt = prose_author_prompt(_prose_scope, ctx.language)

    # AFTER the prose-author scope is computed, deliberately: which conditional
    # duty blocks this beat can have work for is an engine judgement about the
    # beat, and an extension that could widen it would be buying prompt chunks
    # rather than contributing context. The retries below inherit this payload.
    payload = _extension_director_payload(ctx, payload, phase="resolve")
    # The second pass, when an extension refused the first answer. Delivered on
    # the channel the stage's own retries already use, so the Director reads a
    # campaign violation exactly the way it reads a player-authority one --
    # attributed, specific, and about THIS beat.
    if _corrections:
        payload = {**payload, "campaign_violations": _corrections,
                   "correction_notes": _campaign_correction_note(_corrections)}

    out = _agent_json(
        "director",
        "director_resolve",
        _resolve_prompt,
        payload,
        temperature=0.5,
        max_tokens=None,   # the configured ceiling; see complete_validated_json
    )

    # WORLD PRESSURE must-tick floor (F5), enforced. The ledger + prompt rule
    # ask the resolve to tick or hold every open pressure; commit warns on
    # silence. But a pressure the payload flags must_tick_this_beat has
    # ALREADY been held past its window -- the DW-2 lesson (and the spatial
    # zone-tagging one before it) is that a prompt rule alone goes unused
    # under sustained narrative pressure, so a violated flag buys exactly one
    # correction retry, kept only if it actually covers more of the flagged
    # pressures. Runs BEFORE the player-act authority retry below so player
    # authority always gets the last word.
    _pressures = payload.get("world_pressure") or []
    _must_tick = [p for p in _pressures if p.get("must_tick_this_beat")]

    def _unticked_pressures(res_out):
        ops = res_out.get("world_pressure")
        ops = ops if isinstance(ops, list) else []
        tick_ids, tick_subjects = set(), []
        for op in ops:
            if isinstance(op, dict) \
                    and str(op.get("op") or "").strip().lower() == "tick":
                tick_ids.add(str(op.get("id") or "").strip())
                subj = str(op.get("subject") or "").strip().casefold()
                if subj:
                    tick_subjects.append(subj)
        missing = []
        for p in _must_tick:
            pid = str(p.get("id") or "").strip()
            subj = str(p.get("subject") or "").strip().casefold()
            if pid and pid in tick_ids:
                continue
            if subj and any(subj in s or s in subj for s in tick_subjects):
                continue
            missing.append(p)
        return missing

    _wp_missing = _unticked_pressures(out)
    if _wp_missing:
        _wp_note = (
            "WORLD PRESSURE HARD RULE violated: these ongoing world processes "
            "have already been held past their window and MUST advance this "
            "beat -- "
            + "; ".join(f"{p.get('id')}: {p.get('subject')}"
                        for p in _wp_missing)
            + ". Rewrite your resolution keeping every player and character "
            "fact identical, but make each listed process visibly act ON-PAGE "
            "this beat: one concrete external development drawn from the "
            "process itself (a reading changes, a response arrives, the "
            "hazard spreads, the authority moves), emit {op:'tick', id, note} "
            "for it in world_pressure, and encode any persistent effect in "
            "state_diff."
        )
        _wp_retry = _agent_json(
            "director",
            "director_resolve",
            _resolve_prompt,
            {**payload, "correction_notes": _wp_note},
            temperature=0.3,
            max_tokens=None,   # the configured ceiling; see complete_validated_json
        )
        if len(_unticked_pressures(_wp_retry)) < len(_wp_missing):
            out = _wp_retry
            _wp_missing = _unticked_pressures(out)
        for _p in _wp_missing:
            ctx.add_warning(
                f"World pressure must-tick violated: {_p.get('subject')!r} "
                f"(id {_p.get('id')}) was not ticked this beat despite being "
                "flagged must_tick_this_beat."
            )

    # PLAYER-ACT AUTHORITY, enforced. The prompt rule alone measurably reduced
    # this (a live reroll dropped an invented drink-and-nod down to a single
    # invented "Hinami straightens") but did not eliminate it, and a warning
    # was worth nothing on its own: ctx.warnings is accumulated pipeline-wide
    # and never surfaced, so flagging an invented act neither removed it nor
    # told anyone. resolved_event feeds perception -> narrator -> memory, so a
    # fabricated act becomes canon and then replays when the player declares it
    # for real a beat later. One correction retry, mirroring the narrator's
    # enforceable-warning loop; the retry is kept only if it actually reduces
    # the violation count, so a worse rewrite can never win.
    _declared_player_actions = [
        e for e in (interp.get("sequence") or [])
        if isinstance(e, dict) and e.get("type") == "action"
        and (e.get("attempt") or e.get("observable"))
    ]
    _player_name = (pers.get("name") or persona_name(pers)) if pers else ""
    # CHARACTER-SPEECH AUTHORITY, the mirror of the below. A character owns
    # their own speech exactly as the player owns theirs, and only the player
    # had a guard: live, a character declared silence and the resolve said it
    # "adds a further comment" anyway. Every name that was ASKED this beat and
    # produced no speech -- `char_speech` is keyed by the same display name
    # `_declared_act_texts` and the dialogue log use.
    _silent_names = [
        str(d.get("name") or "").strip() for d in decls
        if str(d.get("name") or "").strip()
        and not (char_speech.get(str(d.get("name") or "").strip()))
    ]
    # Every body the prose could be talking about. Subject resolution needs the
    # full roster, not just the accused: it is the presence of the OTHER names
    # that stops a pronoun being bound to the wrong person (see
    # `_sentence_subjects`).
    _declared_names = [
        str(d.get("name") or "").strip() for d in decls
        if str(d.get("name") or "").strip()
    ]
    _all_names = [n for n in ([_player_name] + _declared_names) if n]
    _mute = _check_character_speech_authority(
        out.get("resolved_event") or "", _silent_names, _all_names)
    # CHARACTER-ACT AUTHORITY. The third side of the boundary, and the one
    # nothing held: act authority was enforced for the player alone, so the
    # Director could hand a character conduct freely. Live (chat 56 t1391) it
    # moved a character who had declared a scan "from several feet away" and
    # whose own declared want was to act "without crowding her".
    _cacts = []
    for _cname in _declared_names:
        _cacts.extend(_check_character_act_authority(
            out.get("resolved_event") or "",
            char_actions.get(_cname) or [], _cname, _all_names))
    # PROSE-QUOTE AUTHORITY. The dialogue_log backstop further down drops an
    # invented line for a registered character, but only one that reached the
    # LOG; t1391's fabrication lived solely in resolved_event prose, with
    # dialogue_log empty, so that guard never saw it. `_allowed_quote_bodies`
    # is everything legitimately declared this beat -- the player's lines, every
    # character's lines, and any line the resolve attributes to a speaker who
    # is neither cast nor the player (the prompt licenses the Director to voice
    # unsheeted background presences).
    _allowed_quote_bodies = {
        _quote_body(s) for s in player_speech_lines(interp)}
    for _speeches in char_speech.values():
        _allowed_quote_bodies.update(_quote_body(s["text"]) for s in _speeches)
    for _d in (out.get("dialogue_log") or []):
        _spk = str(_d.get("speaker") or "")
        if (_spk.casefold() not in {
                character_name_from_text(c["sheet"]).casefold()
                for c in ctx.cast}
                and not is_player_speaker(_spk, chat)):
            _allowed_quote_bodies.add(_quote_body(_d.get("exact_quote", "")))
    _quotes = _check_prose_quote_authority(
        out.get("resolved_event") or "", _allowed_quote_bodies)
    # The player's own raw text is what their declaration MEANS -- the
    # interpret stage's `observable` compresses it, and an act is elaboration
    # only against what the player actually wrote.
    _player_declared_text = " ".join(str(x) for x in (
        ctx.input or "",
        (interp.get("speech") or ""),
        json.dumps(interp.get("sequence") or [])))
    _invented = _check_player_act_authority(
        out.get("resolved_event") or "", _declared_player_actions, _player_name,
        _all_names, ctx.input or "")
    # What the player FEELS is theirs as much as what they do. Everything the
    # player wrote this beat is exempt -- declared feeling is declared.
    _felt = _check_player_interiority_authority(
        out.get("resolved_event") or "", _player_name,
        _player_declared_text, _all_names)
    if _invented or _mute or _felt or _cacts or _quotes:
        # ONE retry covering every violation. They are the same boundary from
        # several sides, they are detected at the same moment, and asking
        # separately would cost a call apiece to say the same thing.
        _parts = []
        if _invented:
            _parts.append(
                "Your previous resolved_event gave the PLAYER physical acts they "
                "did not declare this beat. The player declared "
                + ("no action at all -- only speech."
                   if not _declared_player_actions else "only the listed actions.")
                + " Rewrite it keeping every other fact identical: describe what "
                "OTHER characters do, and the player ONLY as they declared. An NPC "
                "may offer, hold out, brace or wait -- the player accepts on their "
                "own turn. You may add sensory detail to a declared act; you may "
                "not add an act. Offending sentences: "
                + " | ".join(w.split(": ", 1)[-1] for w in _invented))
        if _felt:
            _parts.append(
                "Your previous resolved_event named what the PLAYER FEELS. "
                "Their interior state is theirs to declare, not yours to "
                "assert -- and an observer cannot know it is genuine. Report "
                "only what a body SHOWS (trembling, wide eyes, a shrill cry, "
                "a step back) and let the reader infer the rest. Rewrite "
                "keeping every other fact identical. Offending sentences: "
                + " | ".join(w.split(": ", 1)[-1] for w in _felt))
        if _mute:
            _parts.append(
                "Your previous resolved_event attributed SPEECH to a character "
                "who declared none this beat. Silence is a declaration: a "
                "character who said nothing said nothing, and you may not give "
                "them a comment, a reply or a murmur. They may still act, react "
                "and be described -- write what they DO, or let the silence "
                "stand. Offending sentences: "
                + " | ".join(w.split(": ", 1)[-1] for w in _mute))
        if _cacts:
            _parts.append(
                "Your previous resolved_event gave a CHARACTER physical acts "
                "they did not declare this beat -- most likely moving someone "
                "who declared no movement. A character's declared act is "
                "yours to RESOLVE, not to extend: you decide whether it "
                "works, what it achieves and what it costs. You do not decide "
                "that they also stepped closer, reached out or turned away. "
                "Distance especially is theirs -- a character who chose to "
                "keep their distance kept it. Rewrite keeping every other "
                "fact identical. Offending sentences: "
                + " | ".join(w.split(": ", 1)[-1] for w in _cacts))
        if _quotes:
            _parts.append(
                "Your previous resolved_event contains spoken lines that "
                "nobody declared this beat. You may not write dialogue for a "
                "character with a sheet -- their words come from their own "
                "declaration and from nowhere else, and a line you invent for "
                "them becomes their memory of having said it. Remove the "
                "invented lines; describe what is done and let the silence "
                "stand. Offending lines: "
                + " | ".join(w.split(": ", 1)[-1] for w in _quotes))
        _note = " ".join(_parts)
        _retry = _agent_json(
            "director",
            "director_resolve",
            _resolve_prompt,
            {**payload, "correction_notes": _note},
            temperature=0.0,
            max_tokens=None,   # the configured ceiling; see complete_validated_json
        )
        _retry_invented = _check_player_act_authority(
            _retry.get("resolved_event") or "",
            _declared_player_actions, _player_name, _all_names,
            ctx.input or "")
        _retry_mute = _check_character_speech_authority(
            _retry.get("resolved_event") or "", _silent_names, _all_names)
        _retry_cacts = []
        for _cname in _declared_names:
            _retry_cacts.extend(_check_character_act_authority(
                _retry.get("resolved_event") or "",
                char_actions.get(_cname) or [], _cname, _all_names))
        _retry_quotes = _check_prose_quote_authority(
            _retry.get("resolved_event") or "", _allowed_quote_bodies)
        _retry_felt = _check_player_interiority_authority(
            _retry.get("resolved_event") or "", _player_name,
            _player_declared_text, _all_names)
        # Kept only if it reduces the TOTAL, so a rewrite that fixes the
        # player's acts by inventing a line for a silent character loses.
        if (len(_retry_invented) + len(_retry_mute) + len(_retry_felt)
                + len(_retry_cacts) + len(_retry_quotes)
                < len(_invented) + len(_mute) + len(_felt)
                + len(_cacts) + len(_quotes)):
            out, _invented, _mute, _felt, _cacts, _quotes = (
                _retry, _retry_invented, _retry_mute, _retry_felt,
                _retry_cacts, _retry_quotes)
        for _w in _invented + _mute + _felt + _cacts + _quotes:
            ctx.add_warning(_w)
    # Surfaced on the step itself, not only in ctx.warnings -- a content
    # violation that survives the retry must at least be visible in the
    # step/variant inspector rather than vanishing.
    if _invented or _mute or _felt or _cacts or _quotes:
        out["player_act_warnings"] = (
            _invented + _mute + _felt + _cacts + _quotes)

    # Warning-only re-normalization; strict validation already ran inside
    # _agent_json (see director_establish above).
    out, warnings = validate_llm_output("director_resolve", out)
    ctx.warnings.extend(warnings)

    # Surfaced on the step itself, not only in ctx.warnings -- attached AFTER
    # validation (the schema dump drops unknown keys).
    if _wp_missing:
        out["world_pressure_warnings"] = [
            f"must-tick pressure not ticked: {p.get('id')}: "
            f"{p.get('subject')}" for p in _wp_missing
        ]

    # Orchestrated fan-out (design note 19): specialists read the FINAL
    # prose, so they run after the authority retries and validation have
    # settled it -- and before every deterministic seam below, so the
    # movement backstop, the restraint floor and the reconciliation manifest
    # all judge the MERGED diff exactly as they judge a monolithic one.
    _orch_view = _resolve_beat_view(out, decls, char_actions, dice,
                                    p_name, interp)
    _orch_extras = {
        "nonce": nonce,
        "clock": clock,
        "active_awareness": payload.get("active_awareness"),
        "body_parts": (payload.get("scene") or {}).get("body_parts"),
        "contacts": resolve_sc.get("contacts") or [],
        "contact_endings": character_contact_endings,
        "material_effects": character_material_effects,
        "notices": payload.get("notices") or [],
        "movement": interp.get("movement"),
        "movers": {
            str(d.get("name")): {
                "exits": d.get("exits"),
                "sprint_reach": d.get("sprint_reach"),
            }
            for d in decls if d.get("name")
        },
        "proposal": payload.get("mapping_scene_proposal"),
        "crowds": payload.get("crowds") or [],
        "couriers": payload.get("couriers") or [],
        "carried_reports": payload.get("carried_reports") or [],
        "unratified_claims": payload.get("unratified_claims") or [],
        "offscreen_planning": payload.get("offscreen_planning")
                              or {"enabled": False, "plans": []},
    }
    _run_specialists(ctx, out, sc, _orch_dispatch, _orch_view,
                     _orch_extras, "resolve")
    # Kept for the reconciliation seam below: when it detects an
    # omission in a delegated channel, the CHANNEL'S OWNER is re-asked
    # with the same beat view and entitlement slice, never the prose
    # author with the full core (see _specialist_repairs). In-memory
    # only -- never persisted with the step.
    ctx["_orch_repair"] = {"view": _orch_view, "extras": _orch_extras}
    # The prose author's granted scope, persisted beside the
    # specialists' -- what the scope backstop audits shipped prose
    # duties against, and the per-beat measurement the sheet scoping
    # is judged by (gated_out is the saving; a prose gate_flag below
    # is the misprediction).
    out["orchestration"]["prose_scope"] = {
        "granted": sorted(_prose_scope or ()),
        "gated_out": sorted(
            set(PROSE_DUTY_CHUNKS) - set(_prose_scope or ())),
    }

    # Safety net: LLM sometimes returns a string/list where an object belongs.
    sd = _normalize_diff_shape(out.get("state_diff"))
    # Same canonicalization as director_establish: fold any uid/normalized-name
    # position key for a cast member onto the registered name before it reaches
    # perception's mid-turn merge or the commit boundary.
    sd["positions"] = canonicalize_positions(sd["positions"], ctx.cast, player_name=p_name)
    # Following is actor-owned. Never trust director_resolve to invent or end
    # it: project only the player's interpreted decision and each NPC's own
    # character result into the objective diff.
    sd["following_ops"] = _collect_following_ops(ctx, sc, interp, p_name)
    resolved_contact_ops = _merge_character_contact_endings(
        character_contact_endings, sd.get("contact_ops"),
        report=lambda note: ctx.add_warning(f"character contact: {note}"),
    )
    sd["contact_ops"] = _merge_player_contact_assertions(
        onset_contacts, resolved_contact_ops,
        report=lambda note: ctx.add_warning(f"player contact: {note}"),
    )
    sd["substance_ops"] = _merge_character_material_effects(
        resolve_sc, sd.get("substance_ops"), character_material_effects,
        report=lambda note: ctx.add_warning(f"character material: {note}"),
    )
    if onset_state:
        sd.update(merge_player_state_assertions(
            onset_state, sd, p_name,
            report=lambda note: ctx.add_warning(f"player state: {note}"),
        ))
    out["state_diff"] = sd
    out["dice"] = dice if isinstance(dice, list) else []

    # A walk the player declared once and this beat did not mention carries
    # on. Written HERE, before every movement backstop, so a continued leg
    # is judged by exactly the machinery a declared move is judged by --
    # restraint, passable route, near-group, approach semantics -- rather
    # than arriving after them as an unexamined teleport.
    _travel_continues(ctx, out, sc, sd, interp, p_name)

    staged = ((ctx.get("mapping_stage") or {}).get("staged_lore") or []) + \
             ((ctx.get("mapping_quick") or {}).get("staged_lore") or [])
    mv = interp.get("movement")
    target_room = mv.get("to_room") if isinstance(mv, dict) else None

    # Who is actually relocating this beat (movement.mover): the player's
    # own body, or a vehicle the player is driving/piloting. Resolved once
    # here and used by both the staged-layout adjacency fallback and the
    # passable-route backstop below -- without it, "I drive the van onto
    # the ferry" was structurally identical to walking there and moved the
    # player's body instead of the van.
    move_subject = mover_room = mover_eid = None
    if isinstance(mv, dict) and mv.get("to_room"):
        move_subject, mover_room, mover_eid = _resolve_movement_mover(
            sc, sd, mv, p_name)
        if move_subject is None:
            ctx.warnings.append(
                f"movement.mover {mv.get('mover')!r} does not resolve to a "
                "known entity; treating the move as the player's own."
            )
            move_subject, mover_room, mover_eid = p_name, None, None
    subject_prev_room = mover_room if mover_eid else room_of(sc, p_name)

    for entry in staged:
        if entry.get("category") == "layout" and entry.get("content"):
            room_id = target_room or (entry.get("keys") or "").split(",")[0].strip().replace(" ", "_")
            # Only MATERIALIZE a room that does not exist yet. Testing the
            # diff alone re-created rooms already in the scene, and the
            # placeholder name below then overwrote the authored one through
            # _merge_room -- live (Elevator Adventure branch 41) mapping's
            # "Branching Junction" became "Site17 Deep Shelter Branching
            # Junction", the id slug, as the player-visible location label.
            if room_id and room_id not in sd["rooms"] \
                    and room_id not in (sc.get("rooms") or {}):
                prev_room = subject_prev_room
                adj = []
                if prev_room:
                    adj.append({"to": prev_room, "barrier": "open", "distance": "near"})
                sd["rooms"][room_id] = {
                    "name": room_id.replace("_", " ").title(),
                    "desc": entry["content"], "adjacent": adj,
                    "notes": entry["content"][:500],
                }

    if isinstance(mv, dict) and mv.get("to_room"):
        # director_interpret derives `movement` purely from the LLM's
        # reading of the player's declared intent, with no adjacency
        # check. Without a deterministic backstop here, a misparsed
        # declaration can teleport the mover through a wall or into a
        # disconnected room. Only commit the move if a passable route
        # exists from the MOVER's current room (or that room is unknown,
        # in which case there is nothing to validate against).
        #
        # Validate against this beat's WOULD-BE merged scene, built the
        # same way commit builds it (merge_scene_with_diff deep-copies its
        # inputs -- nothing persisted is mutated). That merge recomputes
        # derived dock/portal edges, so a vehicle that docks THIS beat
        # already exposes its interior->destination doorway here and an
        # occupant can step out on the same beat it arrives -- previously
        # the dock edge only appeared at commit, AFTER this check, so the
        # same-beat deboard was wrongly blocked.
        route_scene = merge_scene_with_diff(sc, sd)
        known_rooms = route_scene["rooms"]
        prev_room = subject_prev_room
        blocked = contested = False
        rel = None
        if prev_room and mv["to_room"] != prev_room:
            rel = spatial_rel(route_scene, prev_room, mv["to_room"])
            if rel.get("barrier") == "separated":
                # Not directly adjacent. A multi-room walk whose every
                # doorway is ALREADY passable (open/open_door) is a
                # legitimate single-beat traversal, not a teleport --
                # observed live: a valid three-hop walk through open doors
                # was dropped while the narration described arriving. A
                # route that would require passing a still-closed door
                # does NOT count: the backstop cannot attribute the
                # contest to one specific door on a multi-hop path, so
                # such a move stays blocked until the door is opened (a
                # door the resolve opens this beat is already open in
                # route_scene and makes the route passable).
                blocked = not passable_route_exists(
                    route_scene, prev_room, mv["to_room"])
            else:
                # Directly adjacent: the single edge's barrier decides.
                blocked = rel.get("barrier") in ("wall", "unknown")
                # route_scene already carries this beat's diff, so a door
                # the resolve opened this beat reads open_door here.
                # Still-closed means the move is CONTESTED: crossing
                # requires an action whose outcome the resolve owns.
                contested = rel.get("barrier") == "closed_door"
        if blocked:
            ctx.warnings.append(
                f"Blocked movement: no passable route from '{prev_room}' to "
                f"'{mv['to_room']}' (barrier={rel.get('barrier')}); position unchanged."
            )
            # The resolve LLM may itself have asserted the impossible move;
            # a blocked route must strip it, not just warn.
            if sd["positions"].get(move_subject) == mv["to_room"]:
                sd["positions"].pop(move_subject)
            # AND EVERYONE ELSE THE SAME BEAT SENT THERE.
            #
            # The block above protects ONE body. Nobody else's position is
            # route-checked -- an NPC arrives wherever the resolve diff says
            # -- so a group that declared one movement had exactly half of it
            # stopped, and the guard that exists to keep the player out of a
            # wall became the thing that walked her companion through it
            # without her.
            #
            # Live (chat 74): "you step into the elevator", the car minted
            # with a walled edge to the lobby. She stayed; The Doctor went up.
            # They spent the next beat in different rooms, so the beat where
            # her glamour came undone reached him not at all -- he saw
            # nothing, heard nothing, and went on seeing a human woman for
            # the rest of the story. Nothing in the output looked wrong: he
            # simply had nothing to react to.
            #
            # Scoped to THIS destination, deliberately. An NPC moving
            # somewhere else this beat is doing their own thing and is none
            # of this guard's business; one who is going exactly where the
            # blocked declaration was going is part of the movement that was
            # blocked. Their prior position stands, which is the same
            # "position unchanged" the mover just got.
            stranded = [
                subject for subject, room in list(sd["positions"].items())
                if room == mv["to_room"] and subject != move_subject
            ]
            for subject in stranded:
                sd["positions"].pop(subject, None)
            if stranded:
                ctx.warnings.append(
                    "Blocked movement also held back "
                    + ", ".join(sorted(stranded))
                    + f": the same beat sent them to '{mv['to_room']}', and "
                    "stopping only the declarer would have split the group "
                    "into rooms that cannot reach each other."
                )
        elif contested and sd["positions"].get(move_subject) != mv["to_room"]:
            # Don't force interpret's declared intent through a door that is
            # still closed after this beat's diff -- observed live as the
            # narration describing a bump against a sealed door while the
            # committed position walked through it. The resolve diff owns
            # contested outcomes; without its assertion, no move.
            ctx.warnings.append(
                f"Contested movement: barrier closed_door from '{prev_room}' "
                f"to '{mv['to_room']}' not opened this beat and the resolve "
                "diff did not assert the move; position unchanged."
            )
        elif mv.get("arrives", True):
            sd["positions"][move_subject] = mv["to_room"]
        else:
            # Declared as heading there, not getting there. The destination is
            # still what they are moving toward -- it is the arrival that this
            # beat does not contain.
            ctx.warnings.append(
                f"Movement to '{mv['to_room']}' declared arrives=false: "
                f"{move_subject} is heading there, not there. No position "
                "committed this beat."
            )

        if mover_eid is not None:
            # Driver-conflation guard: a vehicle move relocates the ENTITY;
            # the player stays in its interior (carried implicitly -- the
            # interior rooms travel with the vehicle by identity, and the
            # dock edges recompute from the entity's new position at
            # merge). A resolve diff that ALSO moved the player's body to
            # the vehicle's destination while they sit inside it is the
            # exact conflation this field exists to prevent -- strip it.
            player_room_now = room_of(sc, p_name)
            interior = {
                rid for rid, room in known_rooms.items()
                if isinstance(room, dict)
                and room.get("parent_entity") == mover_eid
            }
            if sd["positions"].get(p_name) == mv["to_room"] \
                    and player_room_now in interior:
                sd["positions"].pop(p_name, None)
                ctx.warnings.append(
                    f"Vehicle movement (mover={mover_eid!r}): stripped a "
                    f"resolve-asserted move of {p_name!r} to "
                    f"'{mv['to_room']}' -- the player rides inside the "
                    "vehicle's interior; only the vehicle's position moves."
                )

    # Durable following supplies ordinary group travel, bounded by pace and
    # route. It runs after the movement backstop has finalized the player's
    # destination, so it follows physical truth rather than interpret intent.
    _apply_following_movement(ctx, sc, sd, interp, p_name)

    # A fresh station is structured within-room evidence.  Reconcile the
    # narrow provable case before approach semantics gets final authority over
    # whether the player's own movement arrived this beat.
    _reconcile_near_group_positions(ctx, sc, sd, p_name)

    # THE PHYSICAL FLOOR, for the writes nothing above was watching.
    #
    # The movement backstop over this line is thorough and is scoped to a
    # DECLARED movement: it reads `interp["movement"]`, checks the route, and
    # strips the mover and anyone the same beat sent after them. A position
    # the diff writes for a body that declared no movement at all never
    # reaches it -- and that is the whole of the gap, because a body can be
    # written into a room without anybody having said it was going there.
    #
    # Live, chat 80 turn 4: `interp["movement"]` was null and the spatial
    # specialist wrote {"Hinami": "obs_room"}, moving a restrained subject
    # through a two-way mirror out of a cell whose only other edge is a closed
    # door, into the room she was being observed FROM. The prose author had her
    # correctly in the cell in the same step.
    #
    # Runs AFTER the backstop and after following/near-group reconciliation, so
    # every seam that legitimately writes a position has already had its say
    # and this only reads what survived. Reachability, never declaration:
    # dragged, carried and lift-borne moves are all legitimate and undeclared,
    # and none of them passes through a wall.
    _bodies = [p_name] + [str(x.get("name") or "") for x in ctx.extra_players]
    for _row in ctx.cast:
        try:
            _bodies.append(character_name_from_text(_row["sheet"]))
        except Exception:
            continue
    # The declared mover, and anyone the same beat sent where they were going:
    # both belong to the movement backstop above, which has already ruled on
    # them and may legitimately have honoured a contested crossing.
    _spared = set()
    if isinstance(mv, dict) and mv.get("to_room"):
        if move_subject:
            _spared.add(move_subject)
        _spared.update(
            subject for subject, room in (sd["positions"] or {}).items()
            if room == mv.get("to_room"))
    for _body, _from, _to in _unreachable_position_writes(
            sc, merge_scene_with_diff(sc, sd), sd["positions"],
            _bodies, exempt=_spared):
        sd["positions"].pop(_body, None)
        ctx.add_warning(
            f"Unreachable position: nothing declared a move for {_body}, and "
            f"there is no passable route from '{_from}' to '{_to}'; "
            "position unchanged.")

    # `_guard_approach_is_not_arrival` used to run HERE and was undone on every
    # beat it fired. It now runs at the END of this function; see the call site
    # for why the order is load-bearing.

    if not out.get("resolved_event"):
        parts = []
        p_action = interp.get("action") or {}
        if interp.get("speech"):
            parts.append(f"{p_name} speaks")
        if p_action.get("attempt"):
            parts.append(f"{p_name} attempts to {p_action['attempt']}")
        for cname in char_speech:
            parts.append(f"{cname} speaks")
        for cname, cacts in char_actions.items():
            for cact in cacts:
                parts.append(f"{cname} attempts to {cact.get('attempt', '')}")
        for d in dice:
            parts.append(f"{d.get('actor', 'someone')} "
                         f"({d['roll']}+{d['modifier']} vs {d['dc']}: {d['outcome']})")
        out["resolved_event"] = ". ".join(parts) if parts else "Nothing notable occurs."

    if not out.get("summary"):
        out["summary"] = (out.get("resolved_event") or "")[:200]

    dlog = out.get("dialogue_log") or []

    # The prompt now explicitly invites the director to voice unsheeted
    # background presences (see prompts.py's DIALOGUE LOG instruction),
    # but that license is scoped to entities with no character sheet --
    # a REGISTERED cast member speaks only through their own character_
    # step declaration (char_speech, built above from actual character_
    # results/interaction_loop/reaction_loop output), never through the
    # director inventing additional lines for them. Drop any dialogue_log
    # entry attributed to a cast member whose exact_quote doesn't appear
    # in that character's own declared speech -- a deterministic backstop
    # regardless of how well the prompt's scoping is actually followed.
    cast_names_lower = {
        character_name_from_text(c["sheet"]).casefold() for c in ctx.cast
    }
    char_speech_bodies = {
        cname.casefold(): {_quote_body(s["text"]) for s in speeches}
        for cname, speeches in char_speech.items()
    }
    # PLAYER-SPEECH AUTHORITY: the Director may never author the player's
    # words. The same backstop as the cast check below, applied to the player:
    # observed live (Elevator Adventure t42) the director took the player's
    # wordless cry "AaUaa!" and silently ADDED a second player line, an
    # invented refusal "Can't... not now...", to dialogue_log -- which then
    # propagated as canonical player speech through perception -> narrator ->
    # memory. Any player-attributed entry whose quote is not among the player's
    # OWN declared speech this beat is dropped.
    player_speech_bodies = {_quote_body(s) for s in player_speech_lines(interp)}

    # PLAYER-ACT AUTHORITY for the player's CONDUCT is enforced earlier, at the
    # point resolved_event is generated (correction retry). The loop below is
    # the matching guard for their WORDS.
    #
    # PRESENCE-KNOWLEDGE CHANNEL: the third mouth in this log. The prompt
    # licenses the Director to voice unsheeted background presences, and the
    # Director is entitled to omniscience -- so a voiced presence spoke from
    # the omniscient working state with no perception object at all (chat 65
    # t2148: Kadoman, minted turn 9 in eastern_market, referring to "the
    # strange coins and notes" shown once at turn 4 in fountain_plaza).
    # The floor is subtractive and costs no call: a presence line making a
    # DEFINITE reference to a scene entity the presence has no channel to is
    # dropped, and the presence stays ignorant -- which is the firewall being
    # visible, and worth more than the smoothness of the dropped line.
    # Generic knowledge survives on purpose: _check_presence_knowledge_channel
    # gates single-word matches on the definite article precisely so "local
    # trade runs on copper and silver" can never be flagged.
    _xp_names_cf = {str((e or {}).get("name") or "").casefold()
                    for e in (ctx.extra_players or [])}
    _bg_recs = wget(chat["id"], "background_presences", {}) or {}
    _all_quotes = [(str(d.get("speaker") or "").casefold(),
                    str(d.get("exact_quote") or "")) for d in dlog]
    checked_dlog = []
    _routed_to_background = []
    for d in dlog:
        speaker = d.get("speaker") or ""
        speaker_cf = str(speaker).casefold()
        if speaker_cf in cast_names_lower:
            body = _quote_body(d.get("exact_quote", ""))
            if body not in char_speech_bodies.get(speaker_cf, set()):
                ctx.add_warning(
                    f"Dropped director-invented dialogue line for "
                    f"registered character {d.get('speaker')!r}: not "
                    "present in their own declared speech."
                )
                continue
        elif is_player_speaker(speaker, chat):
            body = _quote_body(d.get("exact_quote", ""))
            if body not in player_speech_bodies:
                ctx.add_warning(
                    f"Dropped director-invented dialogue line for the PLAYER "
                    f"{speaker!r}: not in the player's declared speech "
                    "(player-speech authority)."
                )
                continue
        elif speaker_cf and speaker_cf not in _xp_names_cf:
            _rec = _bg_recs.get(str(speaker).strip()) or {}
            # DIALOGUE BELONGS TO THE BACKGROUND STAGE, MINTING STAYS HERE.
            # The Director keeps every authority over what EXISTS -- it mints
            # the presence, places it, moves it, gives it an action -- and
            # gives up authoring its WORDS unless it is a simple creature
            # whose speech a dedicated call could not improve
            # (`director_may_voice`). Dropping the line here is what makes the
            # speaker eligible again: `pick_background_reactors` stands down
            # for anyone already in `dialogue_log`, so removing the line hands
            # them to the stage that gives them their own call, their own
            # perception object and their own recognition of the room.
            from commit import _presence_speech_verdict
            if (not director_may_voice(speaker, sc, _rec)
                    and _presence_speech_verdict(sc, speaker, _rec) != "thing"):
                # Only a possible PERSON is re-homed to the background stage.
                # A bodiless voice or a thing that speaks (a PA, a ship
                # computer, an enchanted object) is the Director's own mouth
                # -- the resolve prompt's contract -- and routing one handed
                # it to the stage that voices people: with the speech gate
                # now refusing things there, routing would delete the line
                # and replace it with nothing, which is the chat 72 "a guard
                # that deletes lines" failure in new clothes.
                ctx.add_warning(
                    f"Routed {speaker!r}'s line to the background stage: the "
                    "Director mints presences and moves them; it does not "
                    "write their dialogue.")
                if str(speaker).strip() not in _routed_to_background:
                    _routed_to_background.append(str(speaker).strip())
                continue
            _heard = " ".join(
                [q for s, q in _all_quotes if s != speaker_cf]
                + [str(interp.get("speech") or ""), str(ctx.input or "")]
                + [str(r.get("text") or "")
                   for r in (_rec.get("recent") or []) if isinstance(r, dict)]
                + [str(v) for v in (_rec.get("blurb") or {}).values()]
                + [str((_rec.get("sketch") or {}).get("role_hint") or "")])
            _pleaks = _check_presence_knowledge_channel(
                speaker, d.get("exact_quote", ""), sc, _rec, _heard)
            if _pleaks:
                for _w in _pleaks:
                    ctx.add_warning("Dropped dialogue line: " + _w)
                continue
        checked_dlog.append(d)
    dlog = checked_dlog
    # Read by commit.pick_background_reactors as a FORCED pick: a presence the
    # Director wanted to speak for is salient by construction, and without this
    # the backstop's own salience test could drop the line entirely rather than
    # re-home it -- trading clunky dialogue for silence, which is worse.
    out["routed_to_background"] = _routed_to_background

    # `dialogue_order` is a bare list of names carried to perception, and
    # nothing checked it against who actually spoke. In chat 56 t1391 it read
    # ["The Doctor"] on a beat where he declared no speech and dialogue_log was
    # empty -- a registered character marked as a speaker with no line anywhere
    # to support it. Drop any cast name that has no surviving declared speech;
    # names that are not cast are left alone, since the Director may voice an
    # unsheeted background presence.
    _ordered = []
    _surviving_speakers = {str(d.get("speaker") or "").casefold() for d in dlog}
    for _spk in (out.get("dialogue_order") or []):
        _cf = str(_spk).casefold()
        if _cf in cast_names_lower and _cf not in char_speech_bodies:
            ctx.add_warning(
                f"Dropped {_spk!r} from dialogue_order: a registered "
                "character with no declared speech this beat."
            )
            continue
        # A non-cast name whose every line the presence-knowledge floor
        # dropped must not survive as a bare speaker either -- t1391's
        # speaker-with-no-line shape, from the other direction.
        if (_cf not in cast_names_lower
                and not is_player_speaker(_spk, chat)
                and _cf not in _surviving_speakers):
            ctx.add_warning(
                f"Dropped {_spk!r} from dialogue_order: no surviving "
                "dialogue_log line for this speaker."
            )
            continue
        _ordered.append(_spk)
    out["dialogue_order"] = _ordered

    # Deterministic concealment backstop: the director model is asked to
    # carry visibility/conceal_from/volume onto each dialogue_log entry,
    # but that is prompt compliance and has proven unreliable elsewhere in
    # this engine (see spatial 'zone' tagging) -- and live play confirmed
    # it here too: a whisper declared on the original sequence element
    # came back as dialogue_log volume:'normal', which would have let
    # hear_level() carry a 200-meter-shaft whisper as if it were spoken at
    # normal volume. The true attributes of a line are whatever the
    # ORIGINAL speech declaration (player sequence, or a character's own
    # sequence) said -- always trust that over whatever the director
    # transcribed, keyed by (speaker, quote body) so a dropped/altered
    # dialogue_log tag can never leak concealed or quieted speech.
    speech_concealment = {}
    for e in (interp.get("sequence") or []):
        if e.get("type") == "speech" and e.get("text"):
            speech_concealment[(p_name.casefold(), _quote_body(e["text"]))] = (
                e.get("visibility", "overt"), e.get("conceal_from") or [],
                e.get("volume", "normal"))
    for cname, speeches in char_speech.items():
        for s in speeches:
            speech_concealment[(cname.casefold(), _quote_body(s["text"]))] = (
                s.get("visibility", "overt"), s.get("conceal_from") or [],
                s.get("volume", "normal"))

    # S3-B1. Two defects lived in this backstop, both from keying the
    # already-present check on the quote BODY alone.
    #
    # The validation loop above drops a director-invented line only for
    # registered cast and the primary player, so a line attributed to any OTHER
    # name survives -- a resolve model that transcribes a character's whisper
    # under speaker "the barkeep" kept the wrong entry, and because the body was
    # then in existing_bodies, the deterministic re-append of the character's
    # OWN declaration was suppressed. The wrong speaker displaced the true one
    # permanently: the concealment restore is keyed (speaker, body) so the
    # whisper also lost its tag, views injected the wrong attribution, and every
    # hearer minted a memory of it (the memory gate checks only that the quote
    # reached the view, not who the view said spoke).
    #
    # The same key also silently dropped a second speaker legitimately saying
    # the same words -- "I know." from two people is one line, not a duplicate.
    #
    # So: a body that WAS declared, attributed to someone who did not declare
    # it, is a mis-transcription. Re-attribute it when exactly one speaker
    # declared it, drop it when the true speaker is ambiguous, and track
    # presence per (speaker, body) from here on.
    declarers_by_body = {}
    for (speaker_cf, body) in speech_concealment:
        if body:
            declarers_by_body.setdefault(body, set()).add(speaker_cf)

    existing_keys = set()
    retagged = []
    for d in dlog:
        d.setdefault("volume", "normal")
        d.setdefault("intended_target", None)
        d.setdefault("tone", "")
        if is_player_speaker(d.get("speaker", ""), chat):
            d["speaker"] = p_name
        body = _quote_body(d.get("exact_quote", ""))
        speaker_cf = str(d.get("speaker") or "").casefold()
        declarers = declarers_by_body.get(body) or set()
        if body and declarers and speaker_cf not in declarers:
            if len(declarers) == 1:
                true_cf = next(iter(declarers))
                true_name = next(
                    (n for n in (*char_speech, p_name)
                     if str(n).casefold() == true_cf), None)
                if true_name:
                    ctx.add_warning(
                        f"Re-attributed a declared line transcribed under "
                        f"{d.get('speaker')!r} back to its declarer "
                        f"{true_name!r} (player/character speech authority).")
                    d["speaker"] = true_name
                    speaker_cf = true_cf
            else:
                ctx.add_warning(
                    f"Dropped a line attributed to {d.get('speaker')!r} whose "
                    "quote was declared by someone else and the true speaker "
                    "is ambiguous.")
                continue
        key = (speaker_cf, body)
        if key in speech_concealment:
            d["visibility"], d["conceal_from"], d["volume"] = speech_concealment[key]
        else:
            d.setdefault("visibility", "overt")
            d.setdefault("conceal_from", [])
        if body:
            existing_keys.add(key)
        retagged.append(d)
    dlog = retagged

    for line in player_speech_lines(interp):
        body = _quote_body(line)
        if body and (p_name.casefold(), body) not in existing_keys:
            vis, cf, vol = speech_concealment.get(
                (p_name.casefold(), body), ("overt", [], interp.get("speech_volume", "normal")))
            dlog.append({"speaker": p_name, "exact_quote": line,
                         "volume": vol,
                         "intended_target": None, "tone": "",
                         "visibility": vis, "conceal_from": cf})
            existing_keys.add((p_name.casefold(), body))

    for cname, speeches in char_speech.items():
        for s in speeches:
            body = _quote_body(s["text"])
            if body and (str(cname).casefold(), body) not in existing_keys:
                dlog.append({"speaker": cname, "exact_quote": s["text"],
                             "volume": s.get("volume", "normal"),
                             "intended_target": None, "tone": s.get("tone", ""),
                             "visibility": s.get("visibility", "overt"),
                             "conceal_from": s.get("conceal_from") or []})
                existing_keys.add((str(cname).casefold(), body))

    for d in dlog:
        eq = d.get("exact_quote", "")
        if eq and not (eq.startswith('"') or eq.startswith("'")
                       or eq.startswith('\u201c') or eq.startswith('\u201d')):
            d["exact_quote"] = '"' + eq + '"'

    seen_quotes = {}
    deduped = []
    for d in dlog:
        key = (str(d.get("speaker") or "").lower().strip(),
               _quote_body(d.get("exact_quote", "")),
               str(d.get("intended_target") or "").lower().strip())
        if key in seen_quotes:
            old_idx = seen_quotes[key]
            old = deduped[old_idx]
            if not old.get("tone") and d.get("tone"):
                deduped[old_idx] = d
            continue
        seen_quotes[key] = len(deduped)
        deduped.append(d)

    out["dialogue_log"] = deduped

    tracked_names = [
        character_name_from_text(c["sheet"]) for c in ctx.cast
    ] + [p_name]

    # W2 backstop: warn on any player-authored world assertion the resolve
    # left in assertion limbo (no confirmed/contested/false verdict).
    _audit_fact_adjudications(ctx, out, interp)

    # Report-only: an observer-relative appearance label in the objective
    # account. The prose consequence has a deterministic floor downstream
    # (the composer's identity floor); this teaches the Director, and names
    # the structured cost the floor cannot reach.
    _report_observer_epithets(ctx, out, sc, p_name)

    # One general prose-vs-diff reconciliation pass (subsumes the old
    # warn-only restraint backstop): deterministic placeholder floor,
    # gated omission audit, bounded Director self-repair, warnings for
    # whatever remains unencoded. See the seam's block comment above.
    _reconcile_resolution(ctx, out, sc, interp, char_actions, dice,
                          tracked_names)

    # LAST, and the order is the whole fix. This guard DELETES a position, and
    # a deletion is indistinguishable from an omission: the reconciliation pass
    # above scans the prose for anything the diff fails to encode and merges a
    # repair delta back in. So the beat's prose ("she crosses the tatami and
    # slides one panel open, revealing the stairway beyond") kept re-supplying
    # the very position the guard had just refused, and the guard's own warning
    # -- "Position unchanged" -- was written into the same step that shipped
    # the position.
    #
    # Live, chat 63 turn 165. The player wrote "You walk towards the shoji
    # leading to the upstairs opening it". `director_interpret` read it
    # correctly and set `arrives: false`; the guard fired and said so; and
    # Hinami was committed upstairs anyway, on the beat she opened the door.
    # Opening a door is not walking through it.
    #
    # Running it after reconciliation costs nothing -- nothing between the two
    # points reads `sd` -- and gives the deterministic refusal the last word,
    # which is what it was always documented to have.
    _guard_approach_is_not_arrival(ctx, interp, out["state_diff"], sc, p_name)

    # Orchestration's scope backstop runs on the FINAL output -- after the
    # reconciliation seam, whose repair can itself recover a delegated
    # change the prose asserted -- so a wrongly-skipped specialist or a
    # wrongly-omitted chunk is reported against what actually ships, never
    # against a draft.
    _orchestration_scope_backstop(ctx, out, "resolve")

    # EXTENSION RESULT VALIDATION, last of all and deliberately so. A validator
    # judges the merged result AFTER every deterministic floor this engine owns
    # has had its say -- player-act authority, the movement backstop, the
    # passability floor, the reconciliation repair -- so what it is shown is
    # what would actually be committed rather than a prose-author draft or one
    # specialist's fragment.
    #
    # A refusal buys exactly ONE re-resolution, and it re-enters this whole
    # function rather than patching the answer in place. That is what makes the
    # corrected result trustworthy: every floor above runs again over it, in
    # order, and the validators run again over that. Patching here would give a
    # campaign rule the last word over the engine's own physics, which is the
    # wrong way round.
    #
    # `_corrections` is the recursion guard and the bound in one: the second
    # pass carries the violations, and a second pass never validates again.
    if _corrections is None:
        _violations, _fatal = _validate_campaign_result(ctx, out)
        if _violations:
            for _v in _violations:
                ctx.add_warning(
                    f"campaign rule {_v['code']!r} ({_v['extension']}): "
                    f"{_v['message']}")
            out = director_resolve(ctx, nonce, _corrections=_violations)
            _again, _again_fatal = _validate_campaign_result(ctx, out)
            if _again:
                out["campaign_violations"] = _again
                for _v in _again:
                    ctx.add_warning(
                        f"campaign rule {_v['code']!r} ({_v['extension']}) "
                        f"survived correction: {_v['message']}")
                if _again_fatal:
                    raise CampaignInvariantError(
                        "; ".join(f"{v['extension']}:{v['code']}"
                                  for v in _again))

    return out


def _campaign_correction_note(violations):
    """The violations as one instruction, in the Director's own retry idiom."""
    parts = [
        "An installed campaign layer refused your previous resolution. These "
        "are its rules for this story, not suggestions: re-resolve the beat so "
        "that none of them is broken, keeping every other fact identical."
    ]
    for item in violations or []:
        line = f"[{item.get('extension')}/{item.get('code')}] {item.get('message')}"
        evidence = item.get("evidence")
        if evidence is not None:
            line += f" (evidence: {json.dumps(evidence, ensure_ascii=False)[:200]})"
        parts.append(line)
    return " ".join(parts)


def _validate_campaign_result(ctx, out):
    """Ask installed extensions whether this result may stand.

    Total in the way every extension seam here is total: an unreachable or
    broken registry leaves the beat exactly as the engine resolved it. The one
    thing that is NOT swallowed is a validator that declared `on_error="fail"`
    and refused -- that is an extension asking for the beat to be lost rather
    than for its campaign to be wrong, and honouring it is the whole reason the
    option exists.
    """
    try:
        import extension_runtime

        return extension_runtime.validate_director_result(ctx, out)
    except Exception:
        return [], False
