"""Opening, action-onset, and outcome perception agents."""

from __future__ import annotations

import copy
import json
import re

from character_schema import (
    character_appearance,
    character_name,
    persona_appearance,
    persona_name,
)
from db import wget
from prompts import get_prompt
from scene import (
    NON_AWAKE_GATED,
    active_disguises,
    appearance_of,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    disguise_known_to,
    disguised_visible_appearance,
    get_scene,
    is_player_speaker,
    persona_of,
    senses_of,
    sheet_state,
)
import os

import affect
from spatial import (
    ambient_scope,
    egocentric_frame,
    entity_arc,
    entity_side,
    has_visual,
    hear_level,
    merge_scene_with_diff,
    proximity_rel,
    room_layout,
    room_of,
    spatial_facts,
    spatial_rel,
    visible_adjacent_rooms,
)


def _perceiver_spatial_facts(scene, observer, sources):
    """Env-gated (SPATIAL_SCAFFOLD=1) deterministic ground-truth spatial facts
    for a perceiver -- the same scaffold given to the narrator, applied at the
    perception stage so the VIEW itself is FOV-clean (a rear source rendered as
    sound, not sight). Off by default -> {} (baseline behavior)."""
    if not os.environ.get("SPATIAL_SCAFFOLD"):
        return {}
    names = [s.get("name") for s in sources if s.get("name")]
    facts = spatial_facts(scene, observer, names)
    return {"spatial_facts": facts} if facts else {}

from .common import (
    _agent_json,
    _append_micro_view,
    _append_once,
    _contextual_rooms,
    _dedupe_view_sentences,
    _ensure_environment,
    _fallback_perception_views,
    _inject_action,
    _inject_dialogue,
    _inject_visible_actor,
    _normalise_views,
    _resolve_player_room,
    _room_notes_from_lore,
    _scrub_unknown_identities,
    _scrub_invented_dialogue,
    _scrub_undeclared_player_speech,
    _compose_residue_view,
    observable_action_text,
    player_speech_lines,
    _strip_identity_tokens,
    _unknown_actor_label,
    cast_room,
    character_room,
    character_scene_keys,
)

def _ambient_location_for(sc, room_id):
    """Per-perceiver ambient/location scoping by nesting depth (item 5,
    coarse): the outermost place whose ambience legitimately reaches this
    room. Open to the world -> the scene's location as usual. Sealed
    inside a nested interior (a vehicle mid-transit, a closed elevator)
    -> only the enclosure itself; the outer location's name/ambience must
    not color that perceiver's view. Derived from scene containment
    (spatial.ambient_scope) only -- never from lorebook links."""
    if not room_id:
        return sc.get("location")
    _, open_to_world = ambient_scope(sc, room_id)
    if open_to_world:
        return sc.get("location")
    room = (sc.get("rooms") or {}).get(room_id) or {}
    eid = room.get("parent_entity")
    ent = (sc.get("entities") or {}).get(eid) if eid else None
    label = ((ent or {}).get("name") if isinstance(ent, dict) else None) \
        or eid or room.get("name") or room_id
    return (f"inside {label} (sealed interior -- the outer location's "
            "ambience does not reach here)")

def _identity_roster(p_name, p_appearance, cast):
    """Every identity in play this beat, with the forms (name + uid/aliases)
    and appearance the identity scrub needs: the player plus each cast
    member. Callers extend it with extra players / background speakers."""
    roster = [{"name": p_name, "appearance": p_appearance, "aliases": []}]
    for c in cast:
        sh, _, _ = sheet_state(c)
        keys = character_scene_keys(sh)
        roster.append({
            "name": character_name(sh),
            "appearance": character_appearance(sh),
            "aliases": keys[1:],
        })
    return roster

def _observed_pronouns(chat_id, cast):
    """Canonical pronouns for each cast member a view may refer to in the third
    person, so a view doesn't guess a character's gender from their name and
    flip it between beats (W6).

    A character under an ACTIVE DISGUISE is excluded: their canonical pronouns
    are part of the identity the disguise conceals, and stating them in a view
    an unaware observer receives would out them -- the exact leak the disguise
    machinery above exists to prevent. Their pronouns come from the disguised
    appearance instead, like every other visible feature.
    """
    disguised = active_disguises(chat_id) or {}
    out = {}
    for c in (cast or []):
        sh, _, _ = sheet_state(c)
        name = character_name(sh)
        if not name or str(name).casefold() in disguised:
            continue
        pronouns = ((sh.get("identity") or {}).get("pronouns") or {}
                    if isinstance(sh, dict) else {})
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if clean:
            out[name] = clean
    return out

def _scrub_view_for(ctx, stage, view, perceiver_name, known, roster):
    """Apply the deterministic identity floor to one perceiver's view:
    every roster identity the perceiver does not recognize (and is not) is
    scrubbed outside quoted spans. Surfaces a pipeline warning per leak --
    the original bug was quiet, which is how it went unnoticed."""
    recognized = set(known.get(perceiver_name) or [])
    unknown = [s for s in roster
               if s["name"] != perceiver_name and s["name"] not in recognized]
    view, leaked = _scrub_unknown_identities(
        view,
        allowed_forms=[perceiver_name, *recognized],
        unknown_sources=unknown,
    )
    if leaked:
        ctx.warnings.append(
            f"{stage}: scrubbed unearned identity {leaked} "
            f"from the view of {perceiver_name}")
    return view

def _behind_rooms(scene, observer):
    """Room ids at the observer's back (the way they came), from their
    egocentric frame. Approximate field of view: an observer does not receive
    NEW VISUAL detail from a room behind them -- they get sound/other channels
    and what they already remember, but not fresh sight (you don't watch the
    room you just walked out of unless you turn). Empty when the observer has
    no movement history, so nothing is gated. See the perception FOV clause."""
    frame = egocentric_frame(scene, observer)
    return [e.get("to") for e in frame.get("behind") or [] if e.get("to")]


def _focus_target(scene, observer):
    """The NAME of the source the observer is attending (their focus), when
    focus rests on a co-located entity/character. Perception gives a focused
    source full visual detail (faces, hands, text, small objects) while an
    in-view but non-focused source is PERIPHERY -- presence, gross motion and
    identity only, no foveal detail. None when focus is an edge (a direction,
    not a source) or unset, in which case no periphery gating applies."""
    f = ((scene.get("orientation") or {}).get(observer) or {}).get("focus") or {}
    if f.get("kind") in ("entity", "target") and f.get("ref"):
        return str(f["ref"])
    return None


def _proximity_to_sources(scene, observer, sources):
    """Per CO-LOCATED source: {tier: within_reach|near|across, side:
    left|right|None, arc: front|rear|None} -- the observer's within-room
    distance, hand-side, and whether the source is in their facing FRONT or REAR
    (blind-spot) arc (Phase 3 FOV). Cross-room sources are omitted. Empty when
    nothing derivable, so absence reads exactly like the pre-Phase-2 payload."""
    out = {}
    for s in sources:
        name = s.get("name")
        if not name or name == observer:
            continue
        tier = proximity_rel(scene, observer, name)
        if tier is None:
            continue
        out[name] = {"tier": tier, "side": entity_side(scene, observer, name),
                     "arc": entity_arc(scene, observer, name)}
    return out


def _behind_sources(scene, observer, sources):
    """CO-LOCATED source names in the observer's REAR arc -- the within-room
    blind spot (Phase 3). Mirrors _behind_rooms for same-room people: a source
    here gives the observer NO NEW VISUAL detail (a silent approach/gesture is
    unseen), though sound still carries. Empty when facing/anchors give no
    basis, so nothing is gated by default (FOV fails open)."""
    return [s.get("name") for s in sources
            if s.get("name") and s.get("name") != observer
            and entity_arc(scene, observer, s.get("name")) == "rear"]


def _delivered_manifest(ctx, scene, observer, sources, known, cast_by_name):
    """Per SOURCE this observer can read: {surface_demeanor, cues:[cue,...]} --
    the interior-depth payoff (Phase 4). A character's `manifest` (surface
    demeanor + physical tells) is authored by that character; the ENGINE decides
    which cues reach THIS observer here, before the LLM call, exactly like the
    dialogue-injection backstop. A tell is delivered iff (a) the observer can
    receive its channel -- a visual tell needs sight (same-visual-channel, not
    in the rear blind spot); a voice/breath tell needs to be audible (same
    room) -- AND (b) affect.tell_gate: subtlety <= acuity + familiarity +
    attention. MEANING and the character's own labels never cross; only the
    observable cue text does."""
    out = {}
    focus = _focus_target(scene, observer)
    behind = set(_behind_sources(scene, observer, sources))
    o_room = room_of(scene, observer)
    for s in sources:
        sname = s.get("name")
        cid = cast_by_name.get(sname) if sname else None
        if not sname or sname == observer or cid is None:
            continue
        manifest = (ctx.character_results.get(cid) or {}).get("manifest") or {}
        demeanor = manifest.get("surface_demeanor")
        tells = [t for t in (manifest.get("tells") or [])
                 if isinstance(t, dict) and t.get("cue")]
        if not demeanor and not tells:
            continue
        rel = spatial_rel(scene, s.get("room"), o_room)
        visible = has_visual(rel) and sname not in behind
        audible = bool(rel.get("same_room"))
        acuity = 0.4
        familiarity = 0.45 if (observer in (known.get(sname) or [])
                               or sname in (known.get(observer) or [])) else 0.15
        attention = 0.4 if focus == sname else 0.15
        cues = []
        for t in tells:
            chan = str(t.get("channel") or "").lower()
            reachable = visible or (chan in ("voice", "breath") and audible)
            if reachable and affect.tell_gate(t, acuity, familiarity, attention):
                cues.append(t.get("cue"))
        entry = {}
        if visible and demeanor:
            entry["surface_demeanor"] = demeanor
        if cues:
            entry["cues"] = cues
        if entry:
            out[sname] = entry
    return out


def _subject_disguise_context(chat_id, subject_name, true_appearance, known_map):
    """Resolve a subject's active physical_disguise into perception inputs.

    Returns (visible_appearance, disguise_payload_or_None, known_to_or_None):
    - visible_appearance: what EVERY observer visually perceives -- the
      disguised outward form when a disguise is active (a concealed feature is
      not seen even by someone who knows it is there), else the true
      appearance unchanged.
    - disguise_payload: the block handed to the perception LLM so it can give
      observers in known_to the concealed truth as KNOWLEDGE (never as vision)
      and preserve the subject's real capabilities; None when no disguise.
    - known_to: casefolded names that legitimately know the truth (for the
      leak tripwire), or None.

    Feeding the disguised appearance is the primary, fail-safe fix: the LLM is
    never handed the concealed features, so it cannot render them. The payload
    and tripwire are the knowledge layer and QA around that.
    """
    disguise = active_disguises(chat_id).get(str(subject_name or "").casefold())
    if not disguise:
        return true_appearance, None, None
    known_to = disguise_known_to(disguise, subject_name, known_map)
    visible = disguised_visible_appearance(true_appearance, disguise)
    payload = {
        "active": True,
        "outward_visible_appearance": visible,
        "concealed_truth": disguise.get("description") or "",
        "known_to": sorted(known_to),
        "capability_note": (
            "The disguise conceals APPEARANCE only. The subject's real senses "
            "and abilities are unchanged -- e.g. concealed ears still hear."),
        "instruction": (
            "Every observer VISUALLY perceives only outward_visible_appearance; "
            "never describe a concealed feature as seen. An observer whose name "
            "is in known_to additionally KNOWS (does not see) the concealed_truth "
            "and may act on it; an observer not in known_to has no awareness of it."),
    }
    return visible, payload, known_to


def _disguise_leak_check(ctx, stage, views, perceivers, subject_name,
                         concealed_terms, known_to):
    """Deterministic fidelity tripwire (a WARNING, never a scrubber). Flags an
    UNAWARE perceiver whose view names one of the disguised subject's concealed
    features. Scoped to that subject's own terms, so unrelated lore (a
    'Nine-Tailed Fox' task-force name) is never touched. The real fix is
    upstream -- feeding the disguised appearance so correct text is generated
    -- this only catches a model that leaked anyway."""
    if not concealed_terms:
        return
    known = known_to or set()
    for p in perceivers:
        pid = str(p["id"])
        if pid.casefold() == "player":
            continue  # the player is the subject / always knows
        if str(p.get("name") or "").casefold() in known:
            continue
        v = str(views.get(pid) or "").lower()
        for t in concealed_terms:
            t = str(t).strip().lower()
            if t and re.search(rf"\b{re.escape(t)}\b", v):
                ctx.warnings.append(
                    f"{stage}: disguise leak -- '{t}' (a concealed feature of "
                    f"{subject_name}) surfaced in the view of {p.get('name')}")
                break


def _observer_facing_sequence(sequence):
    """Project a declared action sequence into what OTHER perceivers may be
    handed. Each action element carries only its intent-free `observable`
    surface (via observable_action_text) as `attempt`, with the causal-intent
    ledger (intended_effects/asserted_effects) and the actor's own framing
    (verb, raw attempt) removed; a mental element (observable "") is dropped
    entirely, being imperceptible. Speech/event elements pass through unchanged
    (their concealment is handled separately). This keeps the perception filter
    from ever RECEIVING the actor's purpose ('runes of slow and soften',
    'channel divine heritage') -- honoring the barrier rather than handing over
    hidden intent with an instruction to ignore it (the very pattern the engine
    forbids for character agents)."""
    out = []
    for e in sequence or []:
        if not isinstance(e, dict):
            continue
        if e.get("type") != "action":
            out.append(e)
            continue
        surface = observable_action_text(e)
        if not surface:
            continue
        out.append({
            "type": "action",
            "event_id": e.get("event_id", ""),
            "attempt": surface,
            "visibility": e.get("visibility", "overt"),
            "conceal_from": e.get("conceal_from") or [],
            "targets": e.get("targets") or [],
            "stage": e.get("stage", "immediate"),
        })
    return out


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
        "room_notes": ((p_rdata or {}).get("notes") or _room_notes_from_lore(p_room, ctx, sc)),
        "ambient_location": _ambient_location_for(sc, p_room),
        "visible_rooms": visible_adjacent_rooms(sc, p_room),
        "senses": senses_of(pers), "attention": "engaged",
        "knows_identity": True,
        "entity_state": p_state,
        "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], p_room) for s in sources},
        "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], p_room)) for s in sources},
        "proximity_to_sources": _proximity_to_sources(sc, p_name, sources),
        "behind_sources": _behind_sources(sc, p_name, sources),
        "room_layout": room_layout(sc, p_name),
        "behind_rooms": _behind_rooms(sc, p_name),
        "focus_target": _focus_target(sc, p_name),
        **_perceiver_spatial_facts(sc, p_name, sources),
    }]

    for c in ctx.cast:
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        c_sources = [s for s in sources if s["name"] != character_name(sh)]
        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, r),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh), "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            "entity_state": entity_states.get(character_name(sh)) or {},
            "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], r) for s in c_sources},
            "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], r)) for s in c_sources},
            "proximity_to_sources": _proximity_to_sources(sc, character_name(sh), c_sources),
            "behind_sources": _behind_sources(sc, character_name(sh), c_sources),
            "room_layout": room_layout(sc, character_name(sh)),
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

    # Consciousness gate (rare at opening, but a scenario may start someone
    # unconscious/asleep): overlay the establish diff onto committed conditions.
    amap = apply_awareness_diff(awareness_map(chat["id"]), diff)
    for p in perceivers:
        p["awareness"] = awareness_of(amap, p["name"])
    awake_perceivers = [p for p in perceivers
                        if p.get("awareness") not in NON_AWAKE_GATED]

    payload = {
        "scene": {"location": sc.get("location"), "time": sc.get("time"),
                  "rooms": sc.get("rooms"), "entities": sc.get("entities")},
        "declared_act": declared,
        "perceivers": awake_perceivers,
        "cast_pronouns": _observed_pronouns(chat["id"], ctx.cast),
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
        raw_views = _fallback_perception_views(awake_perceivers, [], known=known)
    clean_views = _normalise_views(raw_views, awake_perceivers)

    roster = _identity_roster(p_name, p_appearance, ctx.cast)
    for p in perceivers:
        pid = str(p["id"])
        if p.get("awareness") in NON_AWAKE_GATED:
            clean_views[pid] = _compose_residue_view(p["awareness"])
            continue
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
        view = _scrub_view_for(
            ctx, "perception_establish", view, p["name"], known, roster)
        clean_views[pid] = _dedupe_view_sentences(view) or None

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
    # A physical disguise conceals the actor's real appearance from observers:
    # p_visible is what is actually SEEN (disguised form when active), fed to
    # both the LLM and the deterministic injection below so a concealed feature
    # is never rendered as perceived.
    p_visible, p_disguise, p_disguise_known = _subject_disguise_context(
        chat["id"], p_name, p_appearance, known)
    p_disguise_terms = (active_disguises(chat["id"]).get(str(p_name).casefold())
                        or {}).get("concealed_terms") or []

    speech_elems = [
        e for e in (interp.get("sequence") or [])
        if e.get("type") == "speech" and e.get("text")
    ]
    if not speech_elems and interp.get("speech"):
        speech_elems = [{"type": "speech", "text": interp["speech"],
                         "volume": interp.get("speech_volume", "normal"), "tone": ""}]

    # Observer-facing action text is the intent-free `observable` surface, never
    # the actor's intent-laden `attempt` -- a mental beat (observable "") is
    # skipped so it never reaches the empty-view fallback below.
    action_desc = ""
    for e in (interp.get("sequence") or []):
        if e.get("type") == "action":
            surface = observable_action_text(e)
            if surface:
                action_desc = surface
                break

    player_speech = [
        {"text": e.get("text"), "volume": e.get("volume", "normal"),
         "tone": e.get("tone", ""),
         "visibility": e.get("visibility", "overt"),
         "conceal_from": e.get("conceal_from") or []}
        for e in speech_elems
    ]

    # The sequence handed to the perception LLM is the observer-facing
    # projection: intent-free surfaces only, intent ledger stripped, mental
    # beats dropped. action_attempt (the scalar mirror) follows the same
    # surface -- action.get("attempt") is the actor's raw framing and, being
    # the FIRST element, is frequently the mental beat ("remember the runes").
    observer_sequence = _observer_facing_sequence(interp.get("sequence"))
    observer_action_attempt = next(
        (e["attempt"] for e in observer_sequence
         if e.get("type") == "action" and e.get("attempt")), None)

    # Build action onset for reaction eligibility
    action_onset = {
        "actor_id": "PLAYER",
        "actor": p_name,
        "actor_name": p_name,
        "actor_room": p_room,
        "actor_room_name": (p_rdata or {}).get("name") or p_room,
        "actor_present_appearance": p_visible,
        "sequence": observer_sequence,
        "player_speech": player_speech,
        "speech": interp.get("speech"),
        "speech_volume": interp.get("speech_volume") or "normal",
        "action_attempt": observer_action_attempt,
        "visibility": action.get("visibility", "overt"),
        "conceal_from": action.get("conceal_from") or [],
        "targets": action.get("targets") or [],
        "commitment": action.get("commitment", "contestable"),
    }
    if p_disguise:
        action_onset["subject_disguise"] = p_disguise

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
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, r),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh),
            "attention": act.get("goal") or "ambient",
            "spatial_to_actor": rel,
            "visual_channel_to_actor": has_visual(rel),
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            "behind_rooms": _behind_rooms(sc, character_name(sh)),
            "focus_target": _focus_target(sc, character_name(sh)),
        })

    # Input-side hygiene (defense-in-depth under the output scrub below):
    # when NO perceiver in this call recognizes the player, the model has
    # no legitimate use for the canonical name at all -- handing it over
    # anyway ("actor_name": "Hinami") is exactly the "objective state
    # copied into a context with an instruction to ignore it" pattern the
    # engine forbids for character agents, and is why even strong models
    # wrote the name into stranger views.
    # Strip identity from the VISIBLE (disguise-adjusted) appearance, never the
    # true one -- otherwise a disguised subject's concealed features leak into
    # the stranger-facing safe form.
    # Consciousness gate: a non-awake reactor is excluded from the LLM call and
    # gets a deterministic residue below (P3 also drops them from flow.reactors
    # upstream; this is defense-in-depth). Onset conditions read the committed
    # map -- a knockout THIS beat resolves later, so the reactor is awake now.
    amap = awareness_map(chat["id"])
    for p in perceivers:
        p["awareness"] = awareness_of(amap, p["name"])
    awake_perceivers = [p for p in perceivers
                        if p.get("awareness") not in NON_AWAKE_GATED]

    p_appearance_safe = _strip_identity_tokens(p_visible, [p_name])
    if awake_perceivers and not any(p.get("knows_identity") for p in awake_perceivers):
        neutral = _unknown_actor_label(p_name, p_visible)
        action_onset = {**action_onset, "actor": neutral,
                        "actor_name": neutral,
                        "actor_present_appearance": p_appearance_safe}

    payload = {
        "scene": {"location": sc.get("location"), "time": sc.get("time"),
                  "rooms": _contextual_rooms(sc, ctx.cast, p_room),
                  "entities": sc.get("entities")},
        "declared_act": action_onset,
        "perceivers": awake_perceivers,
        "cast_pronouns": _observed_pronouns(chat["id"], ctx.cast),
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
        out.get("views") if isinstance(out, dict) else {}, awake_perceivers)

    # Deterministic action delivery uses the intent-free `observable` surface,
    # NOT the raw attempt. Each element is tagged with its surface here; a
    # mental beat (observable "") is dropped so it is never injected into any
    # observer's view (an observer cannot perceive "remember the runes").
    action_elems = []
    for e in (interp.get("sequence") or []):
        if e.get("type") != "action" or e.get("visibility") == "concealed":
            continue
        surface = observable_action_text(e)
        if surface:
            action_elems.append({**e, "_surface": surface})
    # Mirror the action_elems concealment filter for speech: a speech
    # element marked visibility:'concealed' must never reach the blanket
    # hear_level-based injection below, which has no concept of an
    # excluded audience -- only the perception LLM (given the full,
    # unfiltered sequence via declared_act above) reasons about who a
    # concealed line legitimately reaches.
    audible_speech_elems = [
        e for e in speech_elems if e.get("visibility") != "concealed"
    ]

    onset_targets = {str(t).casefold() for t in (action.get("targets") or [])}
    onset_loud = any(str(e.get("volume", "")).lower() in ("loud", "shout")
                     for e in audible_speech_elems)
    for p in perceivers:
        pid = str(p["id"])
        if p.get("awareness") in NON_AWAKE_GATED:
            p_name_cf = p["name"].casefold()
            cause = (amap.get(p_name_cf) or {}).get("cause", "").lower()
            pain = any(w in cause for w in
                       ("injur", "wound", "blood", "hurt", "struck", "broke", "burn"))
            clean_views[pid] = _compose_residue_view(
                p["awareness"], targeted=(p_name_cf in onset_targets),
                loud_event=onset_loud, pain=pain)
            continue
        rel = p.get("spatial_to_actor") or {}
        vis = p.get("visual_channel_to_actor", False)
        knows_identity = bool(p.get("knows_identity"))
        display = p_name if knows_identity else _unknown_actor_label(p_name, p_visible)
        view = clean_views.get(pid)
        view = _ensure_environment(view, p, display, rel, vis, action_desc)

        if vis:
            # For a stranger, the pasted appearance summary must itself be
            # name-stripped -- persona summaries routinely lead with the
            # canonical name, which made this deterministic injection a
            # leak channel of its own.
            visible_description = (
                p_appearance_safe
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
                view, display, e["_surface"], can_see,
                event_id=e.get("event_id"), delivered=delivered,
            )
        # Deterministic identity floor, LAST: the LLM's free prose was
        # never checked against knows_identity, so a model that wrote the
        # player's canonical name into a stranger's view walked straight
        # past the gate above. Quoted speech survives verbatim (a name
        # introduced aloud this beat is legitimate sensory signal;
        # recognition itself only flips at commit).
        if not knows_identity:
            view, leaked = _scrub_unknown_identities(
                view,
                allowed_forms=[p["name"]],
                unknown_sources=[{"name": p_name,
                                  "appearance": p_visible}],
            )
            if leaked:
                ctx.warnings.append(
                    f"perception_act: scrubbed unearned identity {leaked} "
                    f"from the view of {p['name']}")
        clean_views[pid] = _dedupe_view_sentences(view) or None

    _disguise_leak_check(ctx, "perception_act", clean_views, perceivers,
                         p_name, p_disguise_terms, p_disguise_known)
    return {"views": clean_views}

def perception_outcome(ctx, nonce):
    chat = ctx.chat
    sc = get_scene(chat["id"], chat)
    pers = persona_of(chat)
    known = wget(chat["id"], "known", {})
    res = ctx.get("director_resolve", {})
    interp = ctx.get("director_interpret", {})
    reactors = set((interp.get("flow") or {}).get("reactors") or [])

    # Room dedup runs BEFORE this stage's merge (Phase-2 re-scope of the
    # Phase-1 one-beat skew): commit will deterministically rekey/redirect
    # colliding minted room keys, and it is a pure function of the stored
    # scene + registry + diff -- all unchanged between here and commit --
    # so running it on a COPY of the diff yields the exact same renames.
    # Without this, perception_outcome rendered the pre-dedup key for one
    # beat while the committed world carried the canonical one. Local
    # import: commit.py must stay ignorant of agent modules (facade rule),
    # so the dependency points this way only (same precedent as commit's
    # own _is_player).
    from commit import dedup_minted_rooms

    diff = copy.deepcopy(res.get("state_diff") or {})
    dedup_minted_rooms(chat["id"], sc, diff)
    prev_scene = sc
    sc = merge_scene_with_diff(sc, diff)

    # Refresh per-character orientation (came_from/focus/facing) on the merged
    # scene. infer_* run at COMMIT, which is AFTER the narrator -- so without
    # this, the FOV/egocentric derivations below AND the narrator's spatial
    # frame would use LAST beat's facing/came_from on exactly the movement beats
    # they exist for (a room just entered, rendered with the prior heading; the
    # deterministic spatial_facts contradicting the correct view). Pure and
    # deterministic given (prev_scene, sc) -- commit re-runs them to the same
    # result. Stashed on ctx so the narrator derives its spatial_frame/
    # spatial_facts from this same oriented scene, not the stale committed KV.
    try:
        from spatial_frames import infer_came_from, infer_focus, infer_facing
        _o_names = [character_name(json.loads(c["sheet"])) for c in ctx.cast]
        infer_came_from(chat["id"], ctx.turn.frame_id, prev_scene, sc, _o_names)
        infer_focus(chat["id"], ctx.turn.frame_id, prev_scene, sc, res, _o_names)
        infer_facing(chat["id"], ctx.turn.frame_id, prev_scene, sc, _o_names)
    except Exception as _oe:  # orientation is best-effort here; commit is authoritative
        ctx.warnings.append(f"perception_outcome: orientation refresh skipped ({_oe})")
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
    p_room = _resolve_player_room(sc, pers, interp, ctx.cast, ctx.input) \
        or ctx.get("_player_room")
    ctx["_player_room"] = p_room

    p_name = pers.get("name") or persona_name(pers)
    p_appearance_true = appearance_of(
        p_name, pers.get("appearance") or persona_appearance(pers), sc)
    # Conceal a disguised subject's real appearance in every observer's outcome
    # view: p_appearance becomes the disguised (visible) form, so present_
    # appearances and the deterministic injection below never expose concealed
    # features. The knowledge layer (who KNOWS the truth) rides the payload.
    p_appearance, p_disguise, p_disguise_known = _subject_disguise_context(
        chat["id"], p_name, p_appearance_true, known)
    p_disguise_terms = (active_disguises(chat["id"]).get(str(p_name).casefold())
                        or {}).get("concealed_terms") or []

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
        if isinstance(a, dict) and a.get("visibility") == "concealed":
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
    other_players = interp.get("other_players") or {}
    extra_entries = []
    for extra in ctx.extra_players:
        pid_key = str(extra["persona_id"])
        e_name = extra["name"]
        e_room = room_of(sc, e_name) or p_room
        sources.append({"name": e_name, "room": e_room})
        appearances[e_name] = appearance_of(
            e_name, extra.get("appearance") or f"{e_name}, a person of unremarkable appearance.", sc)
        entry = other_players.get(pid_key) or {}
        for e in (entry.get("sequence") or []):
            if e.get("type") == "action" and e.get("attempt") and e.get("visibility") == "concealed":
                concealed.append({"actor": e_name, "attempt": e.get("attempt"),
                                  "conceal_from": e.get("conceal_from") or []})
        extra_entries.append((extra, pid_key, e_name, e_room))

    p_rdata = (sc.get("rooms") or {}).get(p_room) if p_room else None
    # name -> cast id, so perception can pull each present character's authored
    # `manifest` (surface demeanor + tells) and gate delivery per observer.
    cast_by_name = {character_name(json.loads(c["sheet"])): c["id"] for c in ctx.cast}

    perceivers = [{
        "id": "player", "name": p_name, "room": p_room,
        "room_name": (p_rdata or {}).get("name") or p_room or "an unspecified area",
        "room_notes": ((p_rdata or {}).get("notes") or _room_notes_from_lore(p_room, ctx, sc)),
        "ambient_location": _ambient_location_for(sc, p_room),
        "visible_rooms": visible_adjacent_rooms(sc, p_room),
        "senses": senses_of(pers), "attention": "engaged",
        "knows_identity": True,
        "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], p_room) for s in sources},
        "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], p_room)) for s in sources},
        "proximity_to_sources": _proximity_to_sources(sc, p_name, sources),
        "behind_sources": _behind_sources(sc, p_name, sources),
        "room_layout": room_layout(sc, p_name),
        "behind_rooms": _behind_rooms(sc, p_name),
        "focus_target": _focus_target(sc, p_name),
        "source_manifest": _delivered_manifest(ctx, sc, p_name, sources, known, cast_by_name),
        **_perceiver_spatial_facts(sc, p_name, sources),
    }]

    for extra, pid_key, e_name, e_room in extra_entries:
        e_rdata = (sc.get("rooms") or {}).get(e_room) if e_room else None
        perceivers.append({
            "id": f"extra:{pid_key}", "name": e_name, "room": e_room,
            "room_name": (e_rdata or {}).get("name") or e_room or "an unspecified area",
            "room_notes": ((e_rdata or {}).get("notes") or _room_notes_from_lore(e_room, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, e_room),
            "visible_rooms": visible_adjacent_rooms(sc, e_room),
            "senses": senses_of(extra), "attention": "engaged",
            "knows_identity": True,
            "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], e_room) for s in sources},
            "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], e_room)) for s in sources},
            "proximity_to_sources": _proximity_to_sources(sc, e_name, sources),
            "behind_sources": _behind_sources(sc, e_name, sources),
            "room_layout": room_layout(sc, e_name),
            "behind_rooms": _behind_rooms(sc, e_name),
            "focus_target": _focus_target(sc, e_name),
            "source_manifest": _delivered_manifest(ctx, sc, e_name, sources, known, cast_by_name),
            **_perceiver_spatial_facts(sc, e_name, sources),
        })

    for c in ctx.cast:
        sh, act, _ = sheet_state(c)
        r = character_room(sc, sh)
        appearances[character_name(sh)] = appearance_of(
            character_name(sh), character_appearance(sh), sc)
        rdata = (sc.get("rooms") or {}).get(r) if r else None
        perceivers.append({
            "id": c["id"], "name": character_name(sh), "room": r,
            "room_name": (rdata or {}).get("name") or r or "an unspecified area",
            "room_notes": ((rdata or {}).get("notes") or _room_notes_from_lore(r, ctx, sc)),
            "ambient_location": _ambient_location_for(sc, r),
            "visible_rooms": visible_adjacent_rooms(sc, r),
            "senses": senses_of(sh),
            "attention": act.get("goal") or "ambient",
            "knows_identity": p_name in (known.get(character_name(sh)) or []),
            "spatial_to_sources": {s["name"]: spatial_rel(sc, s["room"], r) for s in sources},
            "visual_channel_to_sources": {s["name"]: has_visual(spatial_rel(sc, s["room"], r)) for s in sources},
            "proximity_to_sources": _proximity_to_sources(sc, character_name(sh), sources),
            "behind_sources": _behind_sources(sc, character_name(sh), sources),
            "room_layout": room_layout(sc, character_name(sh)),
            "behind_rooms": _behind_rooms(sc, character_name(sh)),
            "focus_target": _focus_target(sc, character_name(sh)),
            "source_manifest": _delivered_manifest(
                ctx, sc, character_name(sh), sources, known, cast_by_name),
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
    awake_perceivers = [p for p in perceivers
                        if p.get("awareness") not in NON_AWAKE_GATED]

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
        **({"subject_disguise": p_disguise} if p_disguise else {}),
        "concealed_actions": concealed,
        "scene": {"location": sc.get("location"), "time": sc.get("time"),
                  "rooms": _contextual_rooms(sc, ctx.cast, p_room),
                  "entities": sc.get("entities")},
        "perceivers": awake_perceivers,
        "cast_pronouns": _observed_pronouns(chat["id"], ctx.cast),
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
        raw_views = _fallback_perception_views(awake_perceivers, npc_dlog, known=known)
    clean_views = _normalise_views(raw_views, awake_perceivers)

    # Identity roster for the deterministic scrub below: every named
    # source/appearance in play this beat, with the uid/alias forms a
    # scene may also carry for cast members.
    cast_aliases = {}
    for c in ctx.cast:
        sh = json.loads(c["sheet"])
        cast_aliases[character_name(sh)] = character_scene_keys(sh)[1:]
    ident_roster = [
        {"name": nm, "appearance": ap, "aliases": cast_aliases.get(nm) or []}
        for nm, ap in appearances.items()
    ]
    for s in sources:
        if s.get("name") and all(r["name"] != s["name"] for r in ident_roster):
            ident_roster.append(
                {"name": s["name"], "appearance": None, "aliases": []})

    # Only the LAST overt sub-action of each actor's sequence represents
    # their terminal, currently-visible state. Earlier sub-actions (e.g.
    # "stand up", "walk across the room") may have happened before any
    # barrier made them visible to a given perceiver, and this pass has no
    # per-stage room/barrier snapshot to check -- only the post-resolution
    # end state. Injecting every sub-action under that end-state visibility
    # would retroactively grant sight through what was, at the time, a
    # closed door or wall.
    # Delivered as the intent-free `observable` surface, never the raw attempt;
    # a mental beat (observable "") is skipped, so the "last overt action" is
    # the last PERCEIVABLE one (a terminal "remember the runes" does not become
    # what observers see the actor do).
    last_overt_by_actor = {}
    for e in (interp.get("sequence") or []):
        if e.get("type") == "action" and e.get("visibility") != "concealed":
            surface = observable_action_text(e)
            if surface:
                last_overt_by_actor[p_name] = {"actor": p_name, "attempt": surface}
    for c in ctx.cast:
        d = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        cname = character_name(sh)
        for e in ((d or {}).get("sequence") or []):
            if e.get("type") == "action" and e.get("visibility") != "concealed":
                surface = observable_action_text(e)
                if surface:
                    last_overt_by_actor[cname] = {"actor": cname, "attempt": surface}

    # DIALOGUE-FIDELITY FLOOR: the complete set of lines actually spoken this
    # beat. Any quoted line in ANY perceiver's view presented as speech whose
    # body is not (a generous substring/fragment match of) one of these is
    # invented -- the perception LLM confabulates memory/backstory callbacks,
    # and director_resolve's resolved_event PROSE can itself carry a line its
    # own dialogue_log backstop already dropped (live t42: a fabricated
    # "trapped under the rubble" player line reached Dr. Moon's view via the
    # prose even though dialogue_log was clean).
    spoken_lines = list(player_speech_lines(interp))
    spoken_lines += [d.get("exact_quote") for d in enriched_dlog]
    for _rmap in (ctx.character_results, ctx.reaction_results):
        for _d in (_rmap or {}).values():
            if not isinstance(_d, dict):
                continue
            for _e in (_d.get("sequence") or []):
                if _e.get("type") == "speech" and _e.get("text"):
                    spoken_lines.append(_e["text"])
            if _d.get("speech"):
                spoken_lines.append(_d["speech"])
    for _entry in (interp.get("other_players") or {}).values():
        for _e in ((_entry or {}).get("sequence") or []):
            if _e.get("type") == "speech" and _e.get("text"):
                spoken_lines.append(_e["text"])

    for p in perceivers:
        pid = str(p["id"])
        # Consciousness gate: a non-awake mind gets ONLY the deterministic
        # residue -- no LLM view (it was excluded from the call), no injection
        # backstops (they would re-create the leak at zero temperature). The
        # residue becomes its fragmentary memory of the beat (commit mints
        # memory from the view), which is the right recovered impression.
        if p.get("awareness") in NON_AWAKE_GATED:
            p_name_cf = p["name"].casefold()
            loud_event = any(
                str(d.get("volume", "")).lower() in ("loud", "shout")
                for d in npc_dlog)
            targeted = any(
                str(d.get("intended_target") or "").casefold() == p_name_cf
                for d in enriched_dlog)
            cause = (amap.get(p_name_cf) or {}).get("cause", "").lower()
            pain = any(w in cause for w in
                       ("injur", "wound", "blood", "hurt", "struck", "broke", "burn"))
            clean_views[pid] = _compose_residue_view(
                p["awareness"], targeted=targeted,
                loud_event=loud_event, pain=pain)
            continue
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
                # doesn't have. Name-stripped first: appearance summaries
                # routinely lead with the canonical name this perceiver is
                # not entitled to.
                appearance_text = _strip_identity_tokens(
                    appearances.get(d_speaker),
                    [d_speaker, *(cast_aliases.get(d_speaker) or [])],
                ) or None
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
                appearance_text = _strip_identity_tokens(
                    appearances.get(act["actor"]),
                    [act["actor"], *(cast_aliases.get(act["actor"]) or [])],
                ) or None
                if act["actor"] not in described_this_pass:
                    if appearance_text:
                        view = _append_once(view, appearance_text, marker=appearance_text)
                    described_this_pass.add(act["actor"])
                display = _unknown_actor_label(act["actor"], appearance_text)
            view = _inject_action(view, display, act["attempt"], can_see)
        # Deterministic identity floor, LAST (see perception_act): the
        # model's free prose is scrubbed per-source against THIS
        # perceiver's recognized set; quoted speech survives verbatim.
        view = _scrub_view_for(
            ctx, "perception_outcome", view, p["name"], known, ident_roster)
        # PLAYER-SPEECH AUTHORITY (perception layer): the player's OWN view must
        # not put words in the player's mouth. Drop any player-attributed quote
        # the player did not declare this beat (the perception LLM sometimes
        # invents one, often echoing a past player line). NPC lines the player
        # legitimately heard (npc_dlog) are protected.
        if pid == "player":
            view, _leaked = _scrub_undeclared_player_speech(
                view,
                declared_bodies=player_speech_lines(interp),
                protected_bodies=[d.get("exact_quote") for d in npc_dlog],
                cast_names=[r["name"] for r in ident_roster])
            if _leaked:
                ctx.warnings.append(
                    "perception_outcome: dropped undeclared player-attributed "
                    f"speech from the player's view: {_leaked}")
        # DIALOGUE-FIDELITY FLOOR (every view, every speaker): drop any quote
        # presented as speech whose body is not in spoken_lines. This closes
        # the gap the player-only scrub left open -- in an NPC's view the
        # player is referred to by name/descriptor, never "you", so an
        # invented player line there survived the scrub above and propagated
        # into that NPC's next-turn context and memory. Muffled fragments of
        # real lines and quoted environmental text (signage, labels) survive
        # by construction -- see _scrub_invented_dialogue.
        view, _invented = _scrub_invented_dialogue(
            view, spoken_lines, cast_names=[r["name"] for r in ident_roster])
        if _invented:
            ctx.warnings.append(
                "perception_outcome: dropped invented dialogue from view "
                f"'{pid}': {_invented}")
        clean_views[pid] = _dedupe_view_sentences(view) or None

    loop = ctx.interaction_loop or {}
    for round_data in loop.get("rounds") or []:
        for perceiver_id, additions in (round_data.get("delivered_views") or {}).items():
            key = str(perceiver_id)
            if key == "player":
                continue
            current = clean_views.get(key) or ""
            # Interaction-round additions can restate a beat the base view
            # already carries -- same within-view dedupe as the per-perceiver
            # pass above.
            clean_views[key] = _dedupe_view_sentences(
                _append_micro_view(current, additions))

    _disguise_leak_check(ctx, "perception_outcome", clean_views, perceivers,
                         p_name, p_disguise_terms, p_disguise_known)
    return {"views": clean_views}
