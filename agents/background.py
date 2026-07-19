"""Lightweight, stateless reaction for named background presences.

A background presence (no character sheet, no chat_chars row, no
character_step, no persistent memory) is normally voiced only through the
director's own resolved_event/dialogue_log authorship -- a prompt clause
in prompts.py's director_resolve entry explicitly licenses this. Live play
showed that license goes unused often enough, under enough narrative
pressure, that a deterministic backstop is warranted: exactly the same
"prompt compliance alone is unreliable" lesson already learned for
spatial zone-tagging and speech concealment elsewhere in this codebase.

This stage is deliberately NOT a cheap character_step: no memory, no
mind-models, no relationships, no persistent psychology. It answers one
question for one beat only -- does this specific present bystander
plausibly react right now -- and is gated by a deterministic, LLM-free
check (commit.py's pick_background_reactor) so the common case (no
salient, un-voiced background presence this beat) costs nothing.
"""

from __future__ import annotations

from schemas import validate_llm_output
from prompts import get_prompt

from commit import pick_background_reactor

from .common import _agent_json


def background_react(ctx, nonce):
    dr = ctx.get("director_resolve") or {}
    name = pick_background_reactor(ctx, dr)
    if not name:
        return {"fired": False, "name": None, "dialogue_log_entry": None, "action": ""}

    present_others = []
    pers_name = None
    try:
        from scene import persona_of, persona_name
        pers = persona_of(ctx.chat)
        pers_name = pers.get("name") or persona_name(pers) if isinstance(pers, dict) else None
    except Exception:
        pass
    if pers_name:
        present_others.append(pers_name)
    for row in ctx.cast:
        try:
            import json as _json
            from character_schema import character_name
            present_others.append(character_name(_json.loads(row["sheet"])))
        except Exception:
            continue

    payload = {
        "entity": {"name": name},
        "beat": {
            "resolved_event": dr.get("resolved_event", ""),
            "player_declaration": ctx.input or "",
            "present_others": present_others,
        },
        "variant_seed": nonce,
    }

    out = _agent_json(
        "character_bg",
        "background_react",
        get_prompt("background_react"),
        payload,
        temperature=0.7,
    )
    # Warning-only re-normalization; strict schema validation (with
    # repair/fallback/raise) already ran inside _agent_json.
    out, warnings = validate_llm_output("background_react", out)
    ctx.warnings.extend(warnings)

    if not out.get("reacts") or not out.get("dialogue_log_entry"):
        return {"fired": False, "name": name, "dialogue_log_entry": None, "action": out.get("action", "")}

    entry = dict(out["dialogue_log_entry"])
    entry["speaker"] = name
    entry.setdefault("visibility", "overt")
    entry.setdefault("conceal_from", [])
    return {"fired": True, "name": name, "dialogue_log_entry": entry,
            "action": out.get("action", "")}
