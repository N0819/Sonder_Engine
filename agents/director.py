"""Director agents for scene establishment, player interpretation, and resolution."""

from __future__ import annotations

import json
import random

from character_schema import (
    character_abilities,
    character_appearance,
    character_name,
    persona_appearance,
    persona_name,
    persona_public_history,
)
from db import wget
from memory import lorebook_manifest
from paradox import paradox_visible_to
from prompts import get_prompt
from scene import (
    _ability_mod,
    appearance_of,
    cast_scene_context,
    director_context,
    fiction_model,
    get_scene,
    is_player_speaker,
    persona_of,
    sanitize_attire_items,
    senses_of,
    sheet_state,
    simulation_clock,
)
from schemas import validate_llm_output
from spatial import room_of, spatial_rel

from .common import (
    _agent_json,
    _contextual_rooms,
    _dict,
    _dict_list,
    _extract_authority_claims,
    _list,
    _normalize_scene_patch,
    _quote_body,
    _requires_reaction_phase,
    _resolve_player_room,
    assign_event_ids,
    canonicalize_positions,
    lore_for,
    norm_sequence,
    normalize_character_refs,
    player_speech_lines,
)

def director_establish(ctx, nonce):
    chat = ctx.chat
    pers = persona_of(chat)
    mapping = ctx.mapping_stage or ctx.mapping_quick or {}
    fm = fiction_model(chat.id)

    cast = cast_scene_context(ctx.cast)

    payload = {
        "scenario": chat.get("scenario"),
        "player": {
            "name": pers.get("name") or persona_name(pers),
            "appearance": pers.get("appearance"),
            "senses": senses_of(pers),
            "abilities": pers.get("abilities", []),
            "public_history": persona_public_history(pers),
        },
        "present_characters": cast,
        "relevant_lore": lore_for(ctx),
        "mapping_scene_proposal": _normalize_scene_patch(mapping.get("scene_patch")),
        "fiction_model": fm,
        "player_seed": ctx.get("input") or "",
        "variant_seed": nonce,
    }

    out = _agent_json(
        "director",
        "director_establish",
        get_prompt("director_establish"),
        payload,
        temperature=0.7,
        max_tokens=200000,
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

    out.setdefault("entities", {})
    out.setdefault("sensory_events", [])
    out.setdefault("fiction_frame", {})
    out.setdefault("simulation_clock", {"elapsed_seconds": 0.0, "display": "now"})

    out["state_diff"] = {
        "rooms": out.get("rooms") if isinstance(out.get("rooms"), dict) else {},
        "entities": out.get("entities") if isinstance(out.get("entities"), dict) else {},
        # Key positions by the registered character name (the convention every
        # reader uses), even when the model keyed a cast member by identity.uid.
        "positions": canonicalize_positions(
            out.get("positions") if isinstance(out.get("positions"), dict) else {},
            ctx.cast),
        "remove_entities": [],
        "remove_rooms": [],
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
        cast_info.append({
            "id": c["id"],
            "name": character_name(sh),
            "room": room_of(sc, character_name(sh)),
            "appearance": appearance_of(character_name(sh),
                                        character_appearance(sh), sc),
            "abilities": character_abilities(sh),
        })

    raw_shadow = wget(chat["id"], "shadow_profile", "") or ""
    raw_intents = wget(chat["id"], "standing_intentions", []) or []
    fm = fiction_model(chat["id"])
    clock = simulation_clock(chat["id"])

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
            "abilities": pers.get("abilities", []),
            "public_shadow_profile": raw_shadow[:1200],
        },
        "present_characters": cast_info,
        "world_books": world_books,
        "standing_intentions": raw_intents[:12],
        "pending": wget(chat["id"], "pending", []),
        "player_raw_input": ctx.input,
        # Idle attached players (connected, but declared nothing this beat)
        # are deliberately excluded here -- there's nothing to interpret
        # for them. They still get their own perceiver/narrated view of
        # the beat via perception_outcome/narrator_extra; they just don't
        # need the director's attention.
        "other_players": [
            {"persona_id": p["persona_id"], "name": p["name"], "raw_input": p["input"]}
            for p in ctx.extra_players if not p.get("idle")
        ],
        "variant_seed": nonce,
    }

    out = _agent_json(
        "director",
        "director_interpret",
        get_prompt("director_interpret"),
        payload,
        max_tokens=200000,
    )

    # Warning-only re-normalization; strict validation already ran inside
    # _agent_json (see director_establish above).
    out, warnings = validate_llm_output("director_interpret", out)
    ctx.warnings.extend(warnings)

    norm_sequence(out)
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
        entry["sequence"] = assign_event_ids(
            entry.get("sequence"), f"turn:{ctx.turn.id}:extra:{pid}")

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
            c_room = room_of(sc, character_name(sh))
            rel = spatial_rel(sc, p_room, c_room)
            barrier = rel.get("barrier")
            if rel.get("same_room") or barrier in ("open", "open_door",
                                                    "closed_door", "wall"):
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

    # Extract authority claims from the sequence
    fl["authority_claims"] = _extract_authority_claims(
        out.get("sequence"), ctx.input)

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

    # Do NOT set ctx["_player_room"] to the declared movement target here.
    # A movement declaration is only a request for director_resolve to
    # validate (it can be blocked by the passable-route check). ctx
    # already holds the player's actual pre-turn room from the resolution
    # above; perception_act (the action-onset pass) must keep using that,
    # not a not-yet-resolved destination — otherwise onset perception
    # treats the player as having already arrived before anyone (the
    # player included) has moved.

    return out

# Deterministic, WARN-ONLY backstop for the director_resolve prompt's own
# CONDITIONS instruction (see prompts.py), which live play showed can go
# unheeded for a physically consequential state -- a character held at
# gunpoint narrated in resolved_event/dialogue_log but never written to
# state_diff.conditions. This intentionally never synthesizes a condition:
# a wrongly invented restraint tag lingering on a character sheet is worse
# than a stale missing one, so it only ever appends to ctx.warnings. Keep
# the keyword list small and specific so it does not fire on ordinary
# descriptive prose.
_RESTRAINT_KEYWORDS = (
    "held at", "pinned", "rifle to", "gunpoint", "restrained", "hostage",
    "grappled",
)

def _scan_for_untracked_restraint(resolved_event, dialogue_log, conditions,
                                   tracked_names):
    """Return warning strings for named, tracked characters whose mention
    co-occurs with a restraint/duress keyword in resolved_event or a
    dialogue_log exact_quote, but who have no matching state_diff.conditions
    entry (matched by subject_id, casefolded). Factored out of
    director_resolve so it can be exercised directly in isolation.
    """
    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict):
            quote = entry.get("exact_quote")
            if quote:
                text_units.append(str(quote))

    tracked_condition_subjects = {
        str(c.get("subject_id") or "").casefold()
        for c in (conditions or {}).values()
        if isinstance(c, dict)
    }

    flagged_names = set()
    for text in text_units:
        lower = text.casefold()
        if not any(keyword in lower for keyword in _RESTRAINT_KEYWORDS):
            continue
        for name in tracked_names:
            if name and name.casefold() in lower:
                flagged_names.add(name)

    warnings = []
    for name in sorted(flagged_names):
        if name.casefold() not in tracked_condition_subjects:
            warnings.append(
                f"Possible untracked physical restraint/duress detected for "
                f"{name!r} (restraint/duress keyword found alongside their "
                "name in resolved_event or dialogue) but no matching "
                "state_diff.conditions entry was recorded this beat."
            )
    return warnings

def director_resolve(ctx, nonce):
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
            "speech": next((e.get("text") for e in rseq if e.get("type") == "speech"), None),
            "action": next((e for e in rseq if e.get("type") == "action"), None),
        })

    all_declarations = reaction_declarations + loop_declarations

    if all_declarations:
        for declaration in all_declarations:
            char_id = declaration.get("char_id")
            name = declaration.get("name")
            sequence = declaration.get("sequence") or []
            decls.append({
                "char_id": char_id, "name": name, "sequence": sequence,
                "is_reaction": declaration.get("is_reaction", False),
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
                    char_actions.setdefault(name, event)
    else:
        for c in ctx.cast:
            dk = ctx.character_results.get(c["id"])
            sh = json.loads(c["sheet"])
            cname = character_name(sh)
            if dk:
                decls.append({
                    "name": dk.get("name") or cname,
                    "sequence": dk.get("sequence") or [],
                    "speech": dk.get("speech"), "action": dk.get("action"),
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
                    char_speech[cname] = speeches
                dk_act = dk.get("action") or {}
                if dk_act.get("attempt"):
                    char_actions[cname] = dk_act

    sc = get_scene(chat["id"], chat)
    raw_intents = wget(chat["id"], "standing_intentions", []) or []
    _mv_for_context = interp.get("movement")
    _mv_target = _mv_for_context.get("to_room") if isinstance(_mv_for_context, dict) else None

    payload = {
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
            "attire": sc.get("attire"),
            "time": sc.get("time"),
        },
        "simulation_clock": clock,
        "paradox": paradox_visible_to(chat["id"], ctx.turn.frame_id),
        "fiction_model": fm,
        "fiction_frame": _dict(flow.get("fiction_frame")),
        "mapping_scene_proposal": _normalize_scene_patch(mapping.get("scene_patch")),
        "player_declaration": {
            "ABSOLUTE": True,
            "sequence": interp.get("sequence") or [],
            "speech": interp.get("speech"),
            "speech_volume": interp.get("speech_volume", "normal"),
            "action": interp.get("action"),
            "movement": interp.get("movement"),
            "abilities": pers.get("abilities", []),
            "authority_claims": (interp.get("flow") or {}).get("authority_claims") or [],
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
        "character_abilities": {
            character_name(json.loads(c["sheet"])): character_abilities(json.loads(c["sheet"]))
            for c in ctx.cast
        },
        "dice_results_final": dice,
        "dialogue_mode": bool(flow.get("dialogue_mode", False)),
        "relevant_lore": lore_for(ctx),
        "standing_intentions": raw_intents[:12],
        "interaction_rounds": loop.get("rounds") or [],
        "reaction_rounds": (ctx.reaction_loop or {}).get("rounds") or [],
        "variant_seed": nonce,
    }

    out = _agent_json(
        "director",
        "director_resolve",
        get_prompt("director_resolve"),
        payload,
        temperature=0.5,
        max_tokens=200000,
    )

    # Warning-only re-normalization; strict validation already ran inside
    # _agent_json (see director_establish above).
    out, warnings = validate_llm_output("director_resolve", out)
    ctx.warnings.extend(warnings)

    sd = out.get("state_diff") or {}
    # Safety check: LLM sometimes returns a string instead of an object
    if not isinstance(sd, dict):
        sd = {}
        out["state_diff"] = sd
        
    for k in ("positions", "rooms", "entities", "overlays", "attire", "conditions"):
        if not isinstance(sd.get(k), dict):
            sd[k] = {}
    # Same canonicalization as director_establish: fold any uid/normalized-name
    # position key for a cast member onto the registered name before it reaches
    # perception's mid-turn merge or the commit boundary.
    sd["positions"] = canonicalize_positions(sd["positions"], ctx.cast)
    for k in ("cast_changes", "world_facts", "introductions",
              "remove_entities", "remove_rooms", "remove_adjacent",
              "inventory_ops", "claim_dispositions"):
        if not isinstance(sd.get(k), list):
            sd[k] = []
    sd.setdefault("time", None)
    out["state_diff"] = sd
    out["dice"] = dice if isinstance(dice, list) else []

    staged = ((ctx.get("mapping_stage") or {}).get("staged_lore") or []) + \
             ((ctx.get("mapping_quick") or {}).get("staged_lore") or [])
    mv = interp.get("movement")
    target_room = mv.get("to_room") if isinstance(mv, dict) else None
    for entry in staged:
        if entry.get("category") == "layout" and entry.get("content"):
            room_id = target_room or (entry.get("keys") or "").split(",")[0].strip().replace(" ", "_")
            if room_id and room_id not in sd["rooms"]:
                prev_room = room_of(sc, p_name)
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
        # declaration can teleport the player through a wall or into a
        # disconnected room. Only commit the move if a passable route
        # exists (or the player's current room is unknown, in which case
        # there is nothing to validate against).
        known_rooms = dict(sc.get("rooms") or {})
        known_rooms.update(sd["rooms"])
        prev_room = room_of(sc, p_name)
        blocked = False
        if prev_room and mv["to_room"] != prev_room:
            rel = spatial_rel({"rooms": known_rooms}, prev_room, mv["to_room"])
            blocked = rel.get("barrier") in ("wall", "separated", "unknown")
        if blocked:
            ctx.warnings.append(
                f"Blocked movement: no passable route from '{prev_room}' to "
                f"'{mv['to_room']}' (barrier={rel.get('barrier')}); position unchanged."
            )
        else:
            sd["positions"][p_name] = mv["to_room"]

    if not out.get("resolved_event"):
        parts = []
        p_action = interp.get("action") or {}
        if interp.get("speech"):
            parts.append(f"{p_name} speaks")
        if p_action.get("attempt"):
            parts.append(f"{p_name} attempts to {p_action['attempt']}")
        for cname in char_speech:
            parts.append(f"{cname} speaks")
        for cname, cact in char_actions.items():
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
        character_name(json.loads(c["sheet"])).casefold() for c in ctx.cast
    }
    char_speech_bodies = {
        cname.casefold(): {_quote_body(s["text"]) for s in speeches}
        for cname, speeches in char_speech.items()
    }
    checked_dlog = []
    for d in dlog:
        speaker_cf = str(d.get("speaker") or "").casefold()
        if speaker_cf in cast_names_lower:
            body = _quote_body(d.get("exact_quote", ""))
            if body not in char_speech_bodies.get(speaker_cf, set()):
                ctx.add_warning(
                    f"Dropped director-invented dialogue line for "
                    f"registered character {d.get('speaker')!r}: not "
                    "present in their own declared speech."
                )
                continue
        checked_dlog.append(d)
    dlog = checked_dlog

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

    existing_bodies = set()

    for d in dlog:
        d.setdefault("volume", "normal")
        d.setdefault("intended_target", None)
        d.setdefault("tone", "")
        if is_player_speaker(d.get("speaker", ""), chat):
            d["speaker"] = p_name
        body = _quote_body(d.get("exact_quote", ""))
        key = (str(d.get("speaker") or "").casefold(), body)
        if key in speech_concealment:
            d["visibility"], d["conceal_from"], d["volume"] = speech_concealment[key]
        else:
            d.setdefault("visibility", "overt")
            d.setdefault("conceal_from", [])
        if body:
            existing_bodies.add(body)

    for line in player_speech_lines(interp):
        body = _quote_body(line)
        if body and body not in existing_bodies:
            vis, cf, vol = speech_concealment.get(
                (p_name.casefold(), body), ("overt", [], interp.get("speech_volume", "normal")))
            dlog.append({"speaker": p_name, "exact_quote": line,
                         "volume": vol,
                         "intended_target": None, "tone": "",
                         "visibility": vis, "conceal_from": cf})
            existing_bodies.add(body)

    for cname, speeches in char_speech.items():
        for s in speeches:
            body = _quote_body(s["text"])
            if body and body not in existing_bodies:
                dlog.append({"speaker": cname, "exact_quote": s["text"],
                             "volume": s.get("volume", "normal"),
                             "intended_target": None, "tone": s.get("tone", ""),
                             "visibility": s.get("visibility", "overt"),
                             "conceal_from": s.get("conceal_from") or []})
                existing_bodies.add(body)

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
        character_name(json.loads(c["sheet"])) for c in ctx.cast
    ] + [p_name]
    for restraint_warning in _scan_for_untracked_restraint(
        out.get("resolved_event", ""), out["dialogue_log"],
        sd.get("conditions") or {}, tracked_names,
    ):
        ctx.add_warning(restraint_warning)

    return out
