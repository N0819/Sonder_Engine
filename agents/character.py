"""Character decision agent."""

from __future__ import annotations

import json

from db import q
from character_schema import (
    character_abilities,
    character_name,
    character_psychology,
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
from scene import all_cast_name_to_id, dialogue_budget, get_scene, private_knowledge_for, sheet_state
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

def _recent_self_lines(chat_id, char_name, current_turn_idx, n_turns=3, cap=4):
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
        "WHERE t.chat_id=? AND t.idx < ? ORDER BY t.idx DESC LIMIT ?",
        (chat_id, current_turn_idx, n_turns),
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


def character_step(ctx, cid, nonce):
    chat = ctx.chat
    row = next(c for c in ctx.cast if c["id"] == cid)
    sh, active, stance = sheet_state(row)
    sc = get_scene(chat["id"], chat)

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

    payload = {
        "self": {
            "entity_id": f"character:{cid}",
            "name": character_name(sh),
            "public_history": character_public_history(sh),
            "psychology": character_psychology(sh),
            "stance": stance,
            "active_state": active,
            "voice": character_voice(sh),
            "senses": senses_as_text(character_senses(sh)),
            "abilities": character_abilities(sh),
            "attire": sc.get("attire", {}).get(character_name(sh)),
            "recent_self_lines": _recent_self_lines(
                chat.id, character_name(sh), ctx.turn.idx),
        },
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
        "private_knowledge": private_knowledge_for(chat, character_name(sh), ctx.turn.frame_id),
        "world_knowledge": knowledge,
        "decision": {
            "deep_tom_requested": cid in _tom,
            "dialogue_mode": bool(_flow.get("dialogue_mode", False)),
            "speech_budget": dialogue_budget(chat, ctx.turn, cid, nonce),
        },
        "variant_seed": nonce,
    }

    role = {"bg": "character_bg", "mid": "character_mid",
            "major": "character_major"}.get(character_tier(sh), "character_mid")

    out = _agent_json(
        role,
        "character",
        get_prompt("character").replace(
            "{name}",
            character_name(sh),
        ),
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
