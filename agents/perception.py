"""Opening, action-onset, and outcome perception agents."""

from __future__ import annotations

import json

from character_schema import (
    character_appearance,
    character_name,
    persona_appearance,
    persona_name,
)
from db import wget
from prompts import get_prompt
from scene import (
    appearance_of,
    get_scene,
    is_player_speaker,
    persona_of,
    senses_of,
    sheet_state,
)
from spatial import (
    has_visual,
    hear_level,
    merge_scene_with_diff,
    room_of,
    spatial_rel,
    visible_adjacent_rooms,
)

from .common import (
    _agent_json,
    _append_micro_view,
    _append_once,
    _contextual_rooms,
    _ensure_environment,
    _fallback_perception_views,
    _inject_action,
    _inject_dialogue,
    _inject_visible_actor,
    _normalise_views,
    _resolve_player_room,
    _room_notes_from_lore,
    _unknown_actor_label,
    cast_room,
    character_room,
)

def perception_establish(ctx, nonce):
    chat = ctx.chat
    est = ctx.director_establish or {}
    sc = get_scene(chat["id"], chat)
    diff = est.get("state_diff") or {}
    sc = merge_scene_with_diff(sc, diff)

    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    # persona_of returns the normalized native shape (identity.name,
    # embodiment.visible.summary), not flat "name"/"appearance" keys --
    # this was the one remaining call site in perception.py still using
    # the flat accessor, same class of bug already fixed in
    # perception_act/perception_outcome below. Since this runs on every
    # opening turn (director_establish -> perception_establish -> ...),
    # it meant the player's actual name/appearance was silently never
    # used on turn 0 -- always "the player" with no real appearance.
    p_name = pers.get("name") or persona_name(pers)
    p_appearance = appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc)

    p_room = _resolve_player_room(sc, pers, None, ctx.cast, ctx.get("input"))
    ctx["_player_room"] = p_room
    p_rdata = (sc.get("rooms") or {}).get(p_room) if p_room else None

    sensory_events = est.get("sensory_events") or []
    entity_states = est.get("entity_states") or {}
    p_state = entity_states.get(p_name) or {}

    sources = []
    for c in ctx.cast:
        sh, _, _ = sheet_state(c)
        r = character_room(sc, sh)
        if r:
            sources.append({"name": character_name(sh), "room": r})

    perceivers = [{
        "id": "player", "name": p_name, "room": p_room,
        "room_name": (p_rdata or {}).get("name") or p_room or "an unspecified area",
        "room_notes": ((p_rdata or {}).get("notes") or _room_notes_from_lore(p_room, ctx)),
        "visible_rooms": visible_adjacent_rooms(sc, p_room),
        "senses": senses_of(pers), "attention": "engaged",
        "knows_identity": True,
        "entity_state": p_state,
        "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], p_room) for s in sources},
        "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], p_room)) for s in sources},
    }]

    for c in ctx.cast:
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        c_sources = [s for s in sources if s["name"] != character_name(sh)]
        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx)),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh), "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            "entity_state": entity_states.get(character_name(sh)) or {},
            "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], r) for s in c_sources},
            "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], r)) for s in c_sources},
        })

    declared = {
        "actor_id": "OPENING", "actor_name": p_name,
        "actor_room": p_room,
        "actor_room_name": (p_rdata or {}).get("name") or p_room,
        "actor_present_appearance": p_appearance,
        "entity_state": p_state,
        "sensory_events": sensory_events,
        "player_seed": ctx.get("input") or "",
        "sequence": [], "player_speech": [],
        "speech": None, "speech_volume": "normal",
        "action_attempt": None, "visibility": "overt",
        "conceal_from": [], "targets": [],
    }

    payload = {
        "scene": {"location": sc.get("location"), "time": sc.get("time"),
                  "rooms": sc.get("rooms"), "entities": sc.get("entities")},
        "declared_act": declared,
        "perceivers": perceivers,
        "scene_opening": True,
        "note": "This is a scene opening. Each perceiver perceives their surroundings "
                "and their own initial state. The player's entity_state contains their "
                "opening posture and activity. Sensory_events are objective environmental "
                "signals — filter them by spatial relation and senses for each perceiver.",
        "output_reminder": "You MUST return a view for EVERY perceiver, keyed by 'id'.",
        "variant_seed": nonce,
    }

    out = _agent_json(
        "perception",
        "perception",
        get_prompt("perception"),
        payload,
        temperature=0.4,
    )
    raw_views = out.get("views") if isinstance(out, dict) else {}
    if not raw_views:
        raw_views = _fallback_perception_views(perceivers, [])
    clean_views = _normalise_views(raw_views, perceivers)

    for p in perceivers:
        pid = str(p["id"])
        view = clean_views.get(pid)
        if not view:
            parts = [f"You are in {p.get('room_name')}."]
            if p.get("room_notes"):
                parts.append(p["room_notes"])
            es = p.get("entity_state") or {}
            if es.get("posture"):
                parts.append(f"You are {es['posture']}.")
            if es.get("activity"):
                parts.append(f"You are {es['activity']}.")
            if es.get("held_items"):
                parts.append(f"You hold: {', '.join(es['held_items'])}.")
            view = " ".join(parts)
        clean_views[pid] = view or None

    return {"views": clean_views}

def perception_act(ctx, nonce):
    chat = ctx.chat
    interp = ctx.director_interpret
    sc = get_scene(chat["id"], chat)
    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    action = interp.get("action")
    if not isinstance(action, dict):
        action = {}

    p_room = ctx.get("_player_room")
    if p_room is None:
        p_room = _resolve_player_room(sc, pers, interp, ctx.cast, ctx.input)
        ctx["_player_room"] = p_room

    p_rdata = (sc.get("rooms") or {}).get(p_room) if p_room else None
    p_name = pers.get("name") or persona_name(pers)
    p_appearance = appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc)

    speech_elems = [
        e for e in (interp.get("sequence") or [])
        if e.get("type") == "speech" and e.get("text")
    ]
    if not speech_elems and interp.get("speech"):
        speech_elems = [{"type": "speech", "text": interp["speech"],
                         "volume": interp.get("speech_volume", "normal"), "tone": ""}]

    action_desc = ""
    for e in (interp.get("sequence") or []):
        if e.get("type") == "action" and e.get("attempt"):
            action_desc = e["attempt"]
            break
    if not action_desc and action.get("attempt"):
        action_desc = action["attempt"]

    player_speech = [
        {"text": e.get("text"), "volume": e.get("volume", "normal"),
         "tone": e.get("tone", ""),
         "visibility": e.get("visibility", "overt"),
         "conceal_from": e.get("conceal_from") or []}
        for e in speech_elems
    ]

    # Build action onset for reaction eligibility
    action_onset = {
        "actor_id": "PLAYER",
        "actor": p_name,
        "actor_name": p_name,
        "actor_room": p_room,
        "actor_room_name": (p_rdata or {}).get("name") or p_room,
        "actor_present_appearance": p_appearance,
        "sequence": interp.get("sequence") or [],
        "player_speech": player_speech,
        "speech": interp.get("speech"),
        "speech_volume": interp.get("speech_volume") or "normal",
        "action_attempt": action.get("attempt"),
        "visibility": action.get("visibility", "overt"),
        "conceal_from": action.get("conceal_from") or [],
        "targets": action.get("targets") or [],
        "commitment": action.get("commitment", "contestable"),
    }

    perceivers = []
    flow = interp.get("flow")
    if not isinstance(flow, dict):
        flow = {}
        
    for c in ctx.cast:
        if c["id"] not in flow.get("reactors", []):
            continue
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        rel = spatial_rel(sc, p_room, r)
        rdata = (sc.get("rooms") or {}).get(r) if r else None

        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx)),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh),
            "attention": act.get("goal") or "ambient",
            "spatial_to_actor": rel,
            "visual_channel_to_actor": has_visual(rel),
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
        })

    payload = {
        "scene": {"location": sc.get("location"), "time": sc.get("time"),
                  "rooms": _contextual_rooms(sc, ctx.cast, p_room),
                  "entities": sc.get("entities")},
        "declared_act": action_onset,
        "perceivers": perceivers,
        "note": (
            "a private thought exists but its contents are withheld"
            if interp.get("private_thought") else "no private thought"
        ),
        "output_reminder": "You MUST return a view for EVERY perceiver, keyed by 'id'.",
        "variant_seed": nonce,
    }

    out = _agent_json(
        "perception",
        "perception",
        get_prompt("perception"),
        payload,
        temperature=0.4,
    )

    clean_views = _normalise_views(
        out.get("views") if isinstance(out, dict) else {}, perceivers)

    action_elems = [
        e for e in (interp.get("sequence") or [])
        if e.get("type") == "action" and e.get("attempt")
        and e.get("visibility") != "concealed"
    ]
    # Mirror the action_elems concealment filter for speech: a speech
    # element marked visibility:'concealed' must never reach the blanket
    # hear_level-based injection below, which has no concept of an
    # excluded audience -- only the perception LLM (given the full,
    # unfiltered sequence via declared_act above) reasons about who a
    # concealed line legitimately reaches.
    audible_speech_elems = [
        e for e in speech_elems if e.get("visibility") != "concealed"
    ]

    for p in perceivers:
        pid = str(p["id"])
        rel = p.get("spatial_to_actor") or {}
        vis = p.get("visual_channel_to_actor", False)
        knows_identity = bool(p.get("knows_identity"))
        display = p_name if knows_identity else _unknown_actor_label(p_name, p_appearance)
        view = clean_views.get(pid)
        view = _ensure_environment(view, p, display, rel, vis, action_desc)

        if vis:
            visible_description = (
                p_appearance
                if not knows_identity
                else display
            )
            view = _inject_visible_actor(
                view,
                display=display,
                appearance=visible_description,
                relation=rel,
            )

        delivered = set()
        for e in audible_speech_elems:
            level = hear_level(rel, e.get("volume", "normal"))
            view = _inject_dialogue(
                view, display, e.get("text"),
                level, e.get("volume", "normal"),
                rel.get("same_room") or vis,
            )
        can_see = rel.get("same_room") or vis
        for e in action_elems:
            view = _inject_action(
                view, display, e["attempt"], can_see,
                event_id=e.get("event_id"), delivered=delivered,
            )
        clean_views[pid] = view or None

    return {"views": clean_views}

def perception_outcome(ctx, nonce):
    chat = ctx.chat
    sc = get_scene(chat["id"], chat)
    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    res = ctx.get("director_resolve", {})
    interp = ctx.get("director_interpret", {})
    reactors = set((interp.get("flow") or {}).get("reactors") or [])

    diff = res.get("state_diff") or {}
    sc = merge_scene_with_diff(sc, diff)

    # Prefer re-resolving against the just-merged (post-resolution) scene
    # over reusing ctx["_player_room"]: that value was cached during the
    # action-onset pass (perception_act), before this turn's movement was
    # validated/applied by director_resolve. Reusing it unconditionally
    # would keep describing the player's pre-move surroundings after a
    # successful move, or the (rejected) destination after a blocked one.
    # Only fall back to the cached value when the scene genuinely has no
    # resolvable position for the player (e.g. positions were never
    # tracked for them).
    p_room = _resolve_player_room(sc, pers, interp, ctx.cast, ctx.input) \
        or ctx.get("_player_room")
    ctx["_player_room"] = p_room

    p_name = pers.get("name") or persona_name(pers)
    p_appearance = appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc)

    # background_react (agents/background.py) is a separate, later stage
    # in the plan -- its output is merged in HERE rather than by mutating
    # res["dialogue_log"] in place, because director_resolve's own step/
    # variant was already persisted before background_react ran; mutating
    # the shared dict afterward would desync the persisted director_resolve
    # step from what perception/narrator actually rendered, and a rerun
    # from this step onward would silently lose the background reaction.
    br = ctx.get("background_react") or {}
    _fired = br.get("reactions")
    if _fired is None:  # legacy single-entry shape
        _fired = ([{"name": br.get("name"), "dialogue_log_entry": br["dialogue_log_entry"],
                    "action": br.get("action", "")}]
                  if br.get("fired") and br.get("dialogue_log_entry") else [])
    else:
        _fired = [r for r in _fired if isinstance(r, dict) and r.get("dialogue_log_entry")]
    br_entries = [r["dialogue_log_entry"] for r in _fired]

    raw_dlog = list(res.get("dialogue_log") or [])
    raw_dlog.extend(br_entries)
    enriched_dlog = []
    for d in raw_dlog:
        speaker = d.get("speaker", "?")
        if is_player_speaker(speaker, chat):
            sp_room = p_room
        else:
            sp_room = cast_room(sc, speaker, ctx.cast)
        enriched_dlog.append({
            "speaker": speaker, "exact_quote": d.get("exact_quote", ""),
            "volume": d.get("volume", "normal"),
            "intended_target": d.get("intended_target"),
            "tone": d.get("tone", ""), "speaker_room": sp_room,
            "visibility": d.get("visibility", "overt"),
            "conceal_from": d.get("conceal_from") or [],
        })

    # A concealed line must never reach the blanket hear_level-based
    # backstop injection below (mirrors last_overt_by_actor excluding
    # concealed actions) -- only the perception LLM, given the full
    # dialogue_log (including concealed entries) via the payload below,
    # reasons about which specific perceivers a concealed line reaches.
    npc_dlog = [d for d in enriched_dlog
                if not is_player_speaker(d.get("speaker", ""), chat)
                and d.get("visibility") != "concealed"]

    sources = [{"name": p_name, "room": p_room}]
    for _e in br_entries:
        sources.append({"name": _e.get("speaker"), "room": cast_room(sc, _e.get("speaker"), ctx.cast)})
    concealed = []
    for a in (interp.get("actions") or
              ([interp["action"]] if interp.get("action") else [])):
        if a and a.get("visibility") == "concealed":
            concealed.append({"actor": p_name, "attempt": a.get("attempt"),
                              "conceal_from": a.get("conceal_from") or []})
    for d in enriched_dlog:
        if d.get("visibility") == "concealed":
            concealed.append({"actor": d.get("speaker"), "attempt": d.get("exact_quote"),
                              "conceal_from": d.get("conceal_from") or []})

    for c in ctx.cast:
        d = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        if d and (d.get("sequence") or d.get("speech") or d.get("action")):
            sources.append({"name": character_name(sh),
                            "room": character_room(sc, sh)})
        for a in ((d or {}).get("actions") or []):
            if a.get("visibility") == "concealed":
                concealed.append({"actor": character_name(sh),
                                  "attempt": a.get("attempt"),
                                  "conceal_from": a.get("conceal_from") or []})

    appearances = {p_name: p_appearance}
    p_rdata = (sc.get("rooms") or {}).get(p_room) if p_room else None
    perceivers = [{
        "id": "player", "name": p_name, "room": p_room,
        "room_name": (p_rdata or {}).get("name") or p_room or "an unspecified area",
        "room_notes": ((p_rdata or {}).get("notes") or _room_notes_from_lore(p_room, ctx)),
        "visible_rooms": visible_adjacent_rooms(sc, p_room),
        "senses": senses_of(pers), "attention": "engaged",
        "knows_identity": True,
        "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], p_room) for s in sources},
        "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], p_room)) for s in sources},
    }]

    # Additional human players: each gets a real perceiver entry at their
    # OWN tracked position (room_of, same lookup used for NPCs and the
    # primary player) -- not hardcoded to the primary player's room. Only
    # fall back to the primary player's room when the extra player has no
    # tracked position yet (e.g. they were only just attached and have
    # never been placed anywhere). They're a genuine dialogue/action source
    # for everyone else's view too, exactly like an NPC -- not a silent
    # observer.
    other_players = interp.get("other_players") or {}
    for extra in ctx.extra_players:
        pid = extra["persona_id"]
        pid_key = str(pid)
        e_name = extra["name"]
        e_room = room_of(sc, e_name) or p_room
        sources.append({"name": e_name, "room": e_room})
        appearances[e_name] = appearance_of(
            e_name, extra.get("appearance") or f"{e_name}, a person of unremarkable appearance.", sc)
        e_rdata = (sc.get("rooms") or {}).get(e_room) if e_room else None
        perceivers.append({
            "id": f"extra:{pid_key}", "name": e_name, "room": e_room,
            "room_name": (e_rdata or {}).get("name") or e_room or "an unspecified area",
            "room_notes": ((e_rdata or {}).get("notes") or _room_notes_from_lore(e_room, ctx)),
            "visible_rooms": visible_adjacent_rooms(sc, e_room),
            "senses": senses_of(extra), "attention": "engaged",
            "knows_identity": True,
            "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], e_room) for s in sources},
            "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], e_room)) for s in sources},
        })
        entry = other_players.get(pid_key) or {}
        for e in (entry.get("sequence") or []):
            if e.get("type") == "action" and e.get("attempt") and e.get("visibility") == "concealed":
                concealed.append({"actor": e_name, "attempt": e.get("attempt"),
                                  "conceal_from": e.get("conceal_from") or []})

    for c in ctx.cast:
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        appearances[character_name(sh)] = appearance_of(
            character_name(sh), character_appearance(sh), sc)
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx)),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh),
            "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], r) for s in sources},
            "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], r)) for s in sources},
        })

    resolved_event_text = res.get("resolved_event", "")
    _br_actions = [f"{r.get('name')}: {r['action']}" for r in _fired if r.get("action")]
    if _br_actions:
        resolved_event_text = (resolved_event_text + " " + "; ".join(_br_actions)).strip()

    payload = {
        "resolved_event": resolved_event_text,
        "dialogue_order": res.get("dialogue_order"),
        "dialogue_log": enriched_dlog,
        "sources": sources,
        "present_appearances": appearances,
        "concealed_actions": concealed,
        "scene": {"location": sc.get("location"), "time": sc.get("time"),
                  "rooms": _contextual_rooms(sc, ctx.cast, p_room),
                  "entities": sc.get("entities")},
        "perceivers": perceivers,
        "output_reminder": (
            "You MUST return a view for EVERY perceiver in the perceivers list, "
            "keyed by their 'id' field exactly as given."
        ),
        "variant_seed": nonce,
    }

    out = _agent_json(
        "perception",
        "perception",
        get_prompt("perception"),
        payload,
        temperature=0.4,
    )
    raw_views = out.get("views") if isinstance(out, dict) else {}
    if not raw_views:
        raw_views = _fallback_perception_views(perceivers, npc_dlog)
    clean_views = _normalise_views(raw_views, perceivers)

    # Only the LAST overt sub-action of each actor's sequence represents
    # their terminal, currently-visible state. Earlier sub-actions (e.g.
    # "stand up", "walk across the room") may have happened before any
    # barrier made them visible to a given perceiver, and this pass has no
    # per-stage room/barrier snapshot to check -- only the post-resolution
    # end state. Injecting every sub-action under that end-state visibility
    # would retroactively grant sight through what was, at the time, a
    # closed door or wall.
    last_overt_by_actor = {}
    for e in (interp.get("sequence") or []):
        if e.get("type") == "action" and e.get("attempt") and e.get("visibility") != "concealed":
            last_overt_by_actor[p_name] = {"actor": p_name, "attempt": e["attempt"]}
    for c in ctx.cast:
        d = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        cname = character_name(sh)
        for e in ((d or {}).get("sequence") or []):
            if e.get("type") == "action" and e.get("attempt") and e.get("visibility") != "concealed":
                last_overt_by_actor[cname] = {"actor": cname, "attempt": e["attempt"]}

    for p in perceivers:
        pid = str(p["id"])
        spatial = p.get("spatial_to_sources") or {}
        visual = p.get("visual_channel_to_sources") or {}
        # Per-source recognition: whether THIS perceiver (player or NPC)
        # has actually been introduced to each speaker/actor. A perceiver
        # may recognize some sources and not others, so this cannot be a
        # single scalar the way action-onset "knows_identity" is.
        recognized_sources = set(known.get(p["name"]) or [])
        view = clean_views.get(pid)
        if not view:
            parts = [f"You are in {p.get('room_name')}."]
            if p.get("room_notes"):
                parts.append(p["room_notes"])
            view = " ".join(parts)
        # Track actors whose full appearance description has already been
        # surfaced in THIS view during this pass, so a second mention (a
        # dialogue line after an action, or vice versa) refers back to them
        # instead of re-pasting the whole appearance paragraph again.
        described_this_pass = set()
        for d in npc_dlog:
            d_speaker = d.get("speaker", "?")
            if d_speaker == p["name"]:
                continue
            rel = spatial.get(d_speaker)
            if rel is None:
                sp_room = d.get("speaker_room") or room_of(sc, d_speaker)
                rel = spatial_rel(sc, sp_room, p.get("room"))
            can_see = visual.get(d_speaker, False) or rel.get("same_room", False)
            if d_speaker in recognized_sources:
                display = d_speaker
            else:
                # A full appearance description is its own complete,
                # self-terminated paragraph. Gluing a dialogue/action clause
                # directly onto it as if it were the same sentence's subject
                # produces a run-on ("...guarded demeanor Pushes through the
                # door..."). Surface the appearance once as its own addition,
                # then refer to the actor with a short label for the actual
                # clause -- two clean sentences instead of one broken one.
                # Only do this when the perceiver can actually SEE the
                # speaker: a voice heard over a comm channel or through a
                # wall is audible without being visible, and _inject_dialogue
                # below already renders that case as "You hear X says..."
                # without a display name -- pasting a full visual appearance
                # onto an unseen voice would hallucinate sight the perceiver
                # doesn't have.
                appearance_text = appearances.get(d_speaker)
                if can_see and d_speaker not in described_this_pass:
                    if appearance_text:
                        view = _append_once(view, appearance_text, marker=appearance_text)
                    described_this_pass.add(d_speaker)
                display = _unknown_actor_label(d_speaker, appearance_text)
            level = hear_level(rel, d.get("volume", "normal"))
            view = _inject_dialogue(view, display, d.get("exact_quote"),
                                    level, d.get("volume", "normal"), can_see)
        for act in last_overt_by_actor.values():
            if act["actor"] == p["name"]:
                continue
            rel = spatial.get(act["actor"])
            if rel is None:
                continue
            can_see = visual.get(act["actor"], False) or rel.get("same_room", False)
            if not can_see:
                continue
            if act["actor"] in recognized_sources:
                display = act["actor"]
            else:
                appearance_text = appearances.get(act["actor"])
                if act["actor"] not in described_this_pass:
                    if appearance_text:
                        view = _append_once(view, appearance_text, marker=appearance_text)
                    described_this_pass.add(act["actor"])
                display = _unknown_actor_label(act["actor"], appearance_text)
            view = _inject_action(view, display, act["attempt"], can_see)
        clean_views[pid] = view or None

    loop = ctx.interaction_loop or {}
    for round_data in loop.get("rounds") or []:
        for perceiver_id, additions in (round_data.get("delivered_views") or {}).items():
            key = str(perceiver_id)
            if key == "player":
                continue
            current = clean_views.get(key) or ""
            clean_views[key] = _append_micro_view(current, additions)

    return {"views": clean_views}
