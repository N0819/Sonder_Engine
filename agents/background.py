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

For cheap individuation the payload carries a `sketch` (role_hint,
station_room) that commit.track_background_presences harvested
deterministically from the director's own entity description/position
when this presence was introduced -- replayed self-description, not
remembered psychology. The backstop's authored line is folded back into
the committed event record (see commit.prepare_memory_commit /
track_background_presences) so a repeatedly-voiced presence accrues
toward promotion instead of being invisible to bookkeeping.

When a registered character (or the player) speaks directly to a
presence, the gate (commit.pick_background_reactor) can pick them to
answer -- this beat if the single slot is free, otherwise via a one-beat
`pending_reply` debt (commit.track_background_presences) so the answer
lands next turn instead of never. That owed reply is bounded,
single-slot, and deterministically expired -- conversational state, not
memory.
"""

from __future__ import annotations

from db import wget
from schemas import validate_llm_output
from prompts import get_prompt

from commit import (
    pick_background_reactors,
    _character_address_of,
    _valid_pending_reply,
    _known_name_roster,
)

from .common import _agent_json


def _result(selected, reactions):
    """Uniform stage output. `selected` is every presence the gate picked this
    beat (so commit can discharge their owed replies even if they stayed
    silent); `reactions` is the subset that actually spoke/acted. The legacy
    single-entry keys mirror reactions[0] for callers that predate the list."""
    first = reactions[0] if reactions else {}
    return {
        "fired": bool(reactions),
        "name": first.get("name") or (selected[0] if selected else None),
        "dialogue_log_entry": first.get("dialogue_log_entry"),
        "action": first.get("action", ""),
        "reactions": reactions,
        "selected": selected,
    }


def background_react(ctx, nonce):
    dr = ctx.get("director_resolve") or {}
    try:
        from scene import background_config
        cap = int(background_config(ctx.chat.id).get("max_reactors", 1))
    except Exception:
        cap = 1
    cap = max(1, min(3, cap))  # hard ceiling; beyond this a crowd is a chorus
    names = pick_background_reactors(ctx, dr, cap=cap)
    if not names:
        return _result([], [])

    present_others = _present_others(ctx)
    roster = {n.casefold() for n in _known_name_roster(ctx.chat, ctx.cast)}
    roster |= {(e.get("name") or "").casefold() for e in (ctx.extra_players or [])}
    sc = wget(ctx.chat.id, "scene", {}) or {}
    presences = wget(ctx.chat.id, "background_presences", {}) or {}

    # One independent reactive beat per gated presence. At cap == 1 this is a
    # single call (unchanged behavior). For cap > 1 each extra reacts to the
    # same beat blind to the others -- the prompt forbids them referencing one
    # another, so they cannot form a reply-chain; the accepted tradeoff vs. a
    # single batched call is N calls for possibly-similar reactions, cheaper to
    # reason about than micro-perceiving between them (which would rebuild
    # interaction_loop for minds that lack the state that loop exists to guard).
    reactions = []
    for name in names:
        entry = _react_one(ctx, dr, name, present_others, roster, sc,
                           presences.get(name) or {}, nonce)
        if entry:
            reactions.append(entry)
    return _result(names, reactions)


def _present_others(ctx):
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
    return present_others


def _react_one(ctx, dr, name, present_others, roster, sc, rec, nonce):
    """One presence's single reactive beat, or None if it stays silent."""
    # Cheap individuation: replay the sketch harvested (deterministically, in
    # commit.track_background_presences) from the director's own entity
    # description/position when this presence was introduced.
    sketch = rec.get("sketch") or {}

    # If a registered character (or the player) spoke directly TO this presence
    # -- this beat, or last beat with the gate spent elsewhere -- surface that
    # line so the reaction can answer it. `beats_ago` marks fresh (0) vs owed
    # (1). The line already rendered; the reply is appended after it, no chain.
    addressed_by = None
    fresh = _character_address_of(dr, name, roster, sc, sketch.get("station_room"))
    if fresh:
        addressed_by = {"speaker": fresh.get("speaker"),
                        "exact_quote": fresh.get("exact_quote", ""),
                        "tone": fresh.get("tone", ""), "beats_ago": 0}
    else:
        pr = _valid_pending_reply(rec, ctx.turn.idx)
        if pr:
            addressed_by = {"speaker": pr.get("from"), "exact_quote": pr.get("quote", ""),
                            "tone": pr.get("tone", ""), "beats_ago": 1}

    payload = {
        "entity": {
            "name": name,
            "role_hint": sketch.get("role_hint", ""),
            "station_room": sketch.get("station_room", ""),
        },
        "beat": {
            "resolved_event": dr.get("resolved_event", ""),
            "addressed_by": addressed_by,
            "player_declaration": ctx.input or "",
            "present_others": [p for p in present_others if p != name],
        },
        "variant_seed": nonce,
    }

    out = _agent_json(
        "character_bg", "background_react", get_prompt("background_react"),
        payload, temperature=0.7,
    )
    # Warning-only re-normalization; strict schema validation (with
    # repair/fallback/raise) already ran inside _agent_json.
    out, warnings = validate_llm_output("background_react", out)
    ctx.warnings.extend(warnings)

    if not out.get("reacts") or not out.get("dialogue_log_entry"):
        return None
    entry = dict(out["dialogue_log_entry"])
    entry["speaker"] = name
    entry.setdefault("visibility", "overt")
    entry.setdefault("conceal_from", [])
    return {"name": name, "dialogue_log_entry": entry, "action": out.get("action", "")}
