"""Character decision agent."""

from __future__ import annotations

import json

from affect import CRISIS_STRAIN_MIN, RUPTURE_FORCE_AFTER
from db import q
from character_schema import (
    character_abilities,
    character_name,
    character_psychology,
    character_standing_intentions,
    effective_drive,
    character_public_history,
    character_sampler,
    character_senses,
    character_temperature,
    character_tier,
    character_voice,
    senses_as_text,
)
from frames import is_recognized_in_frame
from memory import (
    build_character_memory_context,
    knowledge_for_character,
    relationships_for_payload,
)
from prompts import get_prompt
from scene import (
    NON_AWAKE_GATED,
    all_cast_name_to_id,
    awareness_of,
    dialogue_budget,
    get_scene,
    persona_of,
    private_knowledge_for,
    sheet_state,
)
from schemas import validate_llm_output
from spatial import room_of, spatial_digest
from theory_of_mind import mind_models_for_payload

from .common import (
    _agent_json,
    _books,
    _char_known_tags,
    _dict,
    _list,
    _normalize_character_output,
    assign_event_ids,
    cap_mind_model_updates,
    character_room,
    norm_sequence,
)

def _merge_standing_intentions(authored, emergent):
    """Merge a character's authored standing intentions with the emergent ones
    formed at runtime. Authored intentions are always present (the character's
    defining goals), but an emergent intention whose text closely restates an
    authored one SUPERSEDES it -- the emergent copy carries live progress/status
    (including a `blocked`/nonviable state), so a goal the world has closed does
    not reappear as freshly-active. De-dup is by casefolded intent text."""
    emergent = [i for i in (emergent or []) if isinstance(i, dict)]
    seen = {str(i.get("intent") or "").strip().casefold() for i in emergent}
    kept_authored = [
        a for a in (authored or [])
        if isinstance(a, dict)
        and str(a.get("intent") or "").strip().casefold() not in seen
    ]
    return kept_authored + emergent


def _recent_self_lines(chat_id, char_name, current_turn_idx, n_turns=3, cap=4,
                       frame_id=None):
    """The character's own most-recent spoken lines, verbatim, oldest->newest,
    from the last few committed turns' director_resolve dialogue_log.

    Without this the character agent only ever sees the CURRENT beat plus its
    static sheet, so a character in a standing situation (an escort repeating
    'keep moving' at a checkpoint that will not clear) re-derives the same line
    turn after turn -- verbatim repetition reads as a broken machine. Feeding
    its own recent lines lets it notice the refrain and vary or escalate
    (through specificity/consequence, per the character prompt), never as an
    emotional-volume spike."""
    if current_turn_idx is None:
        return []
    rows = q(
        "SELECT t.idx AS idx, v.content AS content FROM turns t "
        "JOIN steps s ON s.turn_id=t.id AND s.key='director_resolve' "
        "JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx < ? AND t.frame_id IS ? "
        "ORDER BY t.idx DESC LIMIT ?",
        (chat_id, current_turn_idx, frame_id, n_turns),
    )
    cf = str(char_name or "").casefold()
    lines = []
    for r in rows:
        try:
            dr = json.loads(r["content"])
        except (TypeError, ValueError):
            continue
        for d in (dr.get("dialogue_log") or []):
            if str(d.get("speaker") or "").casefold() == cf:
                quote = str(d.get("exact_quote") or "").strip()
                if quote:
                    lines.append({"turn": r["idx"], "said": quote})
    lines.sort(key=lambda x: x["turn"])
    return lines[-cap:]


def _known_pronouns(cast, persona, recognized, exclude=None):
    """Canonical pronouns for the people this character ALREADY KNOWS, so a
    speaker refers to others correctly instead of guessing from a name (W6 --
    Crusher said "her discovery" about a he/him character).

    Info barrier: `recognized` is the character's own relationship/mind-model
    key set, which the caller has already frame-filtered by recognition. A
    stranger in the room is deliberately absent -- you don't know an
    unfamiliar person's pronouns, and handing them over would leak identity
    the character never legitimately acquired.
    """
    sheets = []
    for row in (cast or []):
        try:
            sheets.append((json.loads(row["sheet"]).get("identity") or {}))
        except Exception:
            continue
    if isinstance(persona, dict):
        sheets.append(persona.get("identity") or {})
    out = {}
    skip = {str(n or "").strip().casefold() for n in (exclude or [])}
    known = {str(n or "").strip().casefold() for n in (recognized or [])}
    for ident in sheets:
        name = str(ident.get("name") or "").strip()
        folded = name.casefold()
        if not name or folded in skip or folded not in known:
            continue
        pronouns = ident.get("pronouns") or {}
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if clean:
            out[name] = clean
    return out


def character_step(ctx, cid, nonce):
    chat = ctx.chat
    row = next(c for c in ctx.cast if c["id"] == cid)
    sh, active, stance = sheet_state(row)
    sc = get_scene(chat["id"], chat)

    # Consciousness gate (choke point): an unconscious/asleep/sedated mind does
    # not deliberate or act. The planner and both loops already drop non-awake
    # reactors; this guard protects rerun/resume paths that hydrate a stale plan
    # and makes the invariant hold no matter who calls character_step. No LLM
    # call, no manifest (which perception would otherwise deliver as tells).
    if awareness_of(chat["id"], character_name(sh)) in NON_AWAKE_GATED:
        return {"sequence": [], "speech": None, "action": None, "actions": [],
                "manifest": {}, "mind_model_updates": [],
                "_awareness_gated": True}

    interaction_views = ctx.get("interaction_views", {}) or {}
    reaction_views = ctx.get("reaction_views", {}) or {}
    view = reaction_views.get(cid) or interaction_views.get(cid)
    if view is None:
        view = ((ctx.get("perception_act", {}).get("views") or {}).get(str(cid)))

    memory_context = build_character_memory_context(
        chat_id=chat.id, char_id=cid,
        current_turn_idx=ctx.turn.idx,
        current_view=view or "",
        active_state=active,
    )

    char_room = character_room(sc, sh)
    known_tags, excl_titles = _char_known_tags(sh)
    knowledge = knowledge_for_character(_books(ctx), char_room, known_tags, excl_titles)
    stored_state = json.loads(row["cstate"] or "{}")

    _interp = _dict(ctx.director_interpret)
    _flow = _dict(_interp.get("flow"))
    _tom = _list(_flow.get("tom_triggers"))

    relationships = relationships_for_payload(chat.id, cid)
    mind_models = mind_models_for_payload(stored_state.get("mind_models") or {}, ctx.turn.idx)
    frame_id = ctx.turn.frame_id
    if frame_id is not None:
        # A frame's own state-swap already starts blank the first time
        # it's visited, but nonexistent_cast is the deterministic
        # backstop regardless of how relationship/mind-model data got
        # there -- e.g. a character not yet born must never appear known
        # to a native here even if something upstream got it wrong.
        #
        # all_cast_name_to_id (NOT ctx.cast, which is active-only) --
        # a DORMANT cast member must be checked against nonexistent_cast
        # exactly like an active one. Building this from ctx.cast alone
        # made a dormant not-yet-existing character fall through to the
        # -1 fallback below, which reads as "recognized" (-1 is never in
        # a frame's nonexistent_cast list), silently defeating the mask
        # for exactly the case it exists to catch. A name that isn't ANY
        # cast member at all (a background presence, an unsheeted NPC)
        # correctly keeps that same -1/"recognized" fallback -- this
        # mask only ever applies to declared cast members.
        name_to_id = all_cast_name_to_id(chat.id)
        relationships = {
            name: rel for name, rel in relationships.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }
        mind_models = {
            name: mm for name, mm in mind_models.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }

    _interior = stored_state.get("interior") or {}
    _psych = character_psychology(sh)
    # Tier-1: show the EFFECTIVE (possibly rupture-shifted) drive, read-only.
    _psych["drive"] = effective_drive(_psych, _interior)
    # A drive rupture is proposable ONLY inside its open window (see commit's
    # detect_drive_rupture) -- the base contract never documents drive_shift, so
    # the model cannot flip-flop it; it appears here only when the engine opened
    # the window this beat or in the two beats after.
    _rupture = _interior.get("drive_rupture")
    _window_open = bool(isinstance(_rupture, dict)
                        and ctx.turn.idx <= int(_rupture.get("window_expires") or -1))
    # How long the window has been open. Once it has stayed open
    # RUPTURE_FORCE_AFTER turns, the optional "you MAY shift" becomes a FORCED
    # resolution (below) -- the fix for a rupture that the engine keeps holding
    # open while the model quietly declines it every beat (the 23-turn limbo).
    _rupture_turns_open = (
        ctx.turn.idx - int(_rupture.get("opened_turn") or _rupture.get("turn") or ctx.turn.idx)
        if isinstance(_rupture, dict) else 0)
    _rupture_forced = _window_open and _rupture_turns_open >= RUPTURE_FORCE_AFTER
    # Crisis: strain at visible-breaking level. Even before any drive_shift,
    # the flag (plus the CRISIS prompt block below) forces the manifest/tells
    # to show the character cracking instead of playing untouched calm.
    try:
        _strain = float(_interior.get("drive_strain") or 0.0)
    except (TypeError, ValueError):
        _strain = 0.0
    _crisis = _strain >= CRISIS_STRAIN_MIN
    # Recent-tell ledger (written by commit): physical cues already shown,
    # fed back so the model does not reuse the same gesture every beat.
    _recent_tells = [str(t) for t in (stored_state.get("recent_tells") or [])
                     if str(t).strip()]
    _self = {
        "entity_id": f"character:{cid}",
        "name": character_name(sh),
        "public_history": character_public_history(sh),
        "psychology": _psych,
        "stance": stance,
        "active_state": active,
        "voice": character_voice(sh),
        "senses": senses_as_text(character_senses(sh)),
        "abilities": character_abilities(sh),
        "attire": sc.get("attire", {}).get(character_name(sh)),
        "recent_self_lines": _recent_self_lines(
            chat.id, character_name(sh), ctx.turn.idx,
            frame_id=ctx.turn.frame_id),
        # Tier-2 goal hierarchy: the character's AUTHORED standing intentions
        # (its defining goals, always present so it acts proactively) merged
        # with EMERGENT intentions formed at runtime via intent_ops. An emergent
        # intention that restates an authored one wins (it carries live
        # progress/status). Read-only context for deriving this beat's wants.
        "intentions": _merge_standing_intentions(
            character_standing_intentions(sh), _interior.get("intentions") or []),
        # Former drives (scars) give continuity to a character who has changed.
        "former_drives": _interior.get("former_drives") or [],
    }
    if _window_open:
        _self["rupture"] = {"why": _rupture.get("why"), "direction": _rupture.get("direction"),
                            "forced": _rupture_forced}
    if _crisis:
        _self["crisis"] = True
    if _recent_tells:
        _self["recent_tells"] = _recent_tells
    payload = {
        "self": _self,
        "perception": {
            "view": view or "You register nothing new this beat.",
            # This character's OWN egocentric exits (ahead/behind/left/right of
            # the way THEY face) -- grounding for their movement/positioning
            # choices, not a script to narrate. Empty when they have no
            # established orientation.
            "spatial_frame": spatial_digest(sc, character_name(sh)),
        },
        "memory": memory_context,
        "relationships": relationships,
        "mind_models": mind_models,
        "known_pronouns": _known_pronouns(
            ctx.cast, persona_of(chat),
            set(relationships) | set(mind_models),
            exclude=[character_name(sh)]),
        "private_knowledge": private_knowledge_for(chat, character_name(sh), ctx.turn.frame_id),
        "world_knowledge": knowledge,
        "decision": {
            "deep_tom_requested": cid in _tom,
            "dialogue_mode": bool(_flow.get("dialogue_mode", False)),
            "speech_budget": dialogue_budget(chat, ctx.turn, cid, nonce),
        },
        "variant_seed": nonce,
    }

    # Authorial offers (P3): propositions the PLAYER authored about THIS
    # character's interior/behavior, rerouted here instead of being enacted as
    # truth (see director._route_authorial_npc_cognition). The character decides
    # in-character how (or whether) each lands -- its agency is preserved.
    _offers = [o.get("proposition") for o in
               ((ctx.get("director_interpret") or {}).get("authorial_offers") or [])
               if o.get("subject_id") == cid and o.get("proposition")]
    if _offers:
        payload["decision"]["authorial_offers"] = _offers

    role = {"bg": "character_bg", "mid": "character_mid",
            "major": "character_major"}.get(character_tier(sh), "character_mid")

    _cprompt = get_prompt("character").replace("{name}", character_name(sh))
    if _window_open:
        # The base contract never documents drive_shift; the instruction to emit
        # one exists ONLY inside an engine-opened rupture window, so a drive can
        # never flip-flop turn to turn.
        _cprompt += (
            "\n\nDRIVE RUPTURE (window OPEN this beat): a shattering, drive-level "
            "event has cracked what you live for (see self.rupture.why). This event "
            "has ALREADY changed you -- the only question is how the change surfaces. "
            "Denial is a phase, not a stable end: even if you cling to the old drive, "
            "show the crack in your behavior NOW (a ritual performed wrong, a "
            "signature line that dies mid-sentence, a rule reached for and found "
            "hollow). And if your core is genuinely remade, emit drive_shift "
            "{essence, expression, taboo, because}: essence = the new deepest thing "
            "you live for, expression = how it shows, taboo = what you now cannot "
            "do; `because` must name the rupture event. WORKED EXAMPLE: a magistrate "
            "whose drive was 'the law is the only shelter' watches the court execute "
            "the clerk she vouched for. She emits drive_shift {\"essence\": "
            "\"protect the person in front of me, not the rule\", \"expression\": "
            "\"quietly bends procedure to shield people\", \"taboo\": \"never again "
            "hand someone over to process\", \"because\": \"the court executed the "
            "clerk I vouched for\"} -- and her sequence THIS beat already shows it: "
            "she pockets the arrest warrant instead of filing it. A shift is rare "
            "and irreversible -- do not shift for a survivable wound; but do not "
            "play untouched calm either. NEVER announce the change in dialogue; it "
            "shows only in what you do and come to want.")
        if _rupture_forced:
            _cprompt += (
                "\n\nRUPTURE -- FORCED RESOLUTION: this window has now stayed open "
                "several beats and you have kept deferring. Deferral is over. THIS "
                "beat you must LAND it, one way or the other, visibly on the page -- "
                "passive, untouched, wait-and-see calm is NOT an available option "
                "anymore; the strain has been on you far too long for that. Choose "
                "exactly one and enact it in your sequence this beat: (A) emit "
                "drive_shift {essence, expression, taboo, because} AND let your "
                "action/speech this beat already do the new thing -- not a promise "
                "to change, the change itself; or (B) if your core genuinely holds, "
                "stop merely enduring and REAFFIRM it in a concrete, costly act your "
                "pre-rupture self would recognize as doubling down -- a line said, a "
                "hand that acts, a refusal made real. Do not simply describe the "
                "strain again. Resolve it.")
    if _crisis:
        _cprompt += (
            "\n\nCRISIS (self.crisis -- your drive is under extreme strain): what "
            "you live for is under sustained assault and your composure is FAILING. "
            "Your manifest must show it: surface_demeanor cracks at the seams, and "
            "your tells escalate from subtle to VISIBLE (subtlety <= 0.4) -- a "
            "voice that breaks mid-sentence, a hand that will not stay still, a "
            "pause held one beat too long. You need not change what you live for, "
            "but you can no longer look untouched. Do NOT announce the strain in "
            "dialogue; it leaks through the body.")
    if _recent_tells:
        _cprompt += (
            "\n\nTELL VARIETY: self.recent_tells lists the physical cues you have "
            "already shown in recent beats. Do NOT reuse any of them -- or a "
            "near-identical variant -- as this beat's tell; find a DIFFERENT "
            "channel or gesture. A body under the same pressure finds new ways to "
            "betray it: vary the channel (face|eyes|voice|hands|posture|breath) "
            "and the cue itself.")
    out = _agent_json(
        role,
        "character",
        _cprompt,
        payload,
        temperature=character_temperature(sh),
        sampler=character_sampler(sh) or None,
    )

    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json -- a
    # mind_model_updates entry that fails CharacterOutput validation can
    # never reach the cap/commit path below.
    out, warnings = validate_llm_output("character", out)
    ctx.warnings.extend(warnings)

    out = _normalize_character_output(out)
    out["mind_model_updates"] = cap_mind_model_updates(out.get("mind_model_updates") or [])
    norm_sequence(out)
    out["sequence"] = assign_event_ids(
        out.get("sequence"), f"turn:{ctx.turn.id}:character:{cid}")
    out["name"] = character_name(sh)
    out["char_id"] = cid
    return out
