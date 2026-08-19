"""Director agents for scene establishment, player interpretation, and resolution."""

from __future__ import annotations

import contextvars
import copy
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor

from story import attire as attire_model
from story.attire import sanitize_attire_items
from story.character_schema import (
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
from core.db import get_setting, q, wget
from mind.memory import lorebook_manifest
from world.paradox import paradox_visible_to
from language_runtime import apply_prompt_policy
from llm.prompts import (
    PROSE_DUTY_CHUNKS,
    get_prompt,
    get_prompt_body,
    interpret_delegation_note,
    prose_author_prompt,
    specialist_prompt,
)
from story.scene import (
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
    senses_of,
    sheet_state,
    simulation_clock,
    style_guide,
)
from llm.providers import Aborted, generation_event_sink, token_sink
from llm import schemas
from llm.schemas import validate_llm_output
from world.survival import survival_enabled, vitals_of
from world.spatial import (
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
from .director_movement import (
    _egocentric_exits,
    _ci_mapping_key,
    _reconcile_near_group_positions,
    _declares_rapid_movement,
    _follow_op_for_actor,
    _collect_following_ops,
    _following_record,
    _apply_following_movement,
    _unreachable_position_writes,
    _resolve_movement_mover,
    _LONG_EDGE_DISTANCES,
    _LONG_EDGE_BEATS,
    _pending_legs,
    _declared_movers,
    _edge_to,
    _still_crossing,
    _travel_in_flight_view,
    _travel_continues,
    _guard_approach_is_not_arrival,
)
from .director_floors import (
    _untracked_restraint_subjects,
    _MAX_UNCONSCIOUSNESS_GAP,
    _sentence_break_positions,
    _awareness_support_in_beat,
    _unsupported_player_awareness,
    _NATURAL_SLEEP_SECONDS,
    _clause_attributed_subjects,
    _declared_act_texts,
    _rouse_attempts,
    _sleep_elapsed,
    _awareness_view,
    _already_ended,
    _ending_condition,
    _awareness_exits,
    _untracked_unconsciousness_subjects,
    _destruction_name_pattern,
    _narrated_destruction_subjects,
    _scan_for_untracked_restraint,
)
from .director_evidence import (
    _RECONCILE_INTERPRET_MAX_UNITS,
    _INTERPRET_COVERAGE_MIN,
    _decl_tokens,
    _declaration_units,
    _interpret_coverage_corpus,
    _unit_covered,
    _uncovered_declarations,
    _output_field_names,
    _OUTPUT_FIELD_NAMES,
    _normalize_diff_shape,
    _is_blank_placeholder,
    _strip_blank_diff_placeholders,
    _diff_is_substantive,
    _beat_has_physical_activity,
    _reconcile_scene_slice,
    _merge_repair_into_diff,
    _norm_subject,
    _claim_subject_is_referrable,
    _subject_match_forms,
    _make_subject_hit,
    _omission_subject_encoded,
    _normalize_omission_category,
    _entity_state_has_transit,
    _evidence_present,
    _RECONCILE_MAX_MANIFEST_ITEMS,
    _manifest_items,
    _DERIVED_OF_ATTIRE,
    _fold_derived_manifest_events,
)
from .director_scopes import (
    SPECIALISTS,
    _DELEGATED_CHANNELS,
    _CATEGORY_CHANNELS,
    _LIST_DELEGATED,
    _CHANNEL_GATES,
    _CHANNEL_SPECIALISTS,
    _default_channel_gate,
    _rebuild_channel_owners,
    register_specialist,
    unregister_specialists,
    _extension_specialist_call,
    _shipped_transit_state,
    _shipped_darkened_room,
    _shipped_bodiless_definition,
    _PROSE_DUTY_SHIPPED,
    _gate_facts,
    _dispatch_specialists,
)
from .director_fanout import (
    fanout_is_parallel,
    _resolve_beat_view,
    _interpret_beat_view,
    _specialist_manifest_slice,
    _specialist_payload,
    _stage_container,
    _normalized_channel_value,
    _EVENT_VERDICTS,
    _resolved_event_verdicts,
    _index_addressed_events,
    _STRUCTURAL_CHANNEL_FACTS,
    _structurally_absent_channels,
    _orchestration_scope_backstop,
)
from .director_reconcile import (
    _deep_audit_mode,
    _player_claim_findings,
    _public_omission,
    _stamp_dialogue_articulation,
    _SETTLING_VERDICTS,
    _verify_already_true,
    _acquit_addressed_events,
    _REROUTE_FULL_SCOPE,
    _route_repair_omissions,
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
    from story.authored_events import due_authored_events
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
        from world.living_world import living_world_allows, living_world_config
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


_RECONCILE_MAX_AUDIT_OMISSIONS = 6
_RECONCILE_MIN_CONFIDENCE = 0.4


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
        from story.scene import ubiquitous_speaker_names
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
        from world.spatial import effective_light
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
    from persist.commit import pending_obligation_view, world_pressure_view
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
        from world.living_world import living_world_allows, living_world_config
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
                from world.routines import residue_for
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
    # key, schema and payload; the instruction sheet is lean because the
    # delegated machinery is cold-stored in the specialists.
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
    _prose_scope = _prose_author_scope(ctx, sc, payload, _orch_facts, p_name)
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
            from persist.commit import _presence_speech_verdict
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
