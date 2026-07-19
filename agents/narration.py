"""Player-facing narration agent."""

from __future__ import annotations

import contextvars
import json
from concurrent.futures import ThreadPoolExecutor

from db import get_setting, q, wget, wset
from prompts import get_prompt
from scene import persona_of
from schemas import validate_llm_output

from .common import (
    _agent_json,
    _already_established_phrases,
    _check_narrator_fidelity,
    _narration_person_counts,
    _strip_player_echo,
    player_speech_lines,
)

def _resolve_narration_person(chat_id, raw_input, player_name, player_pronouns,
                              key="narration_person"):
    """Which grammatical person renders the player character this turn.
    Detection is per-turn (a player can switch style mid-campaign), but a
    turn with no clear signal -- pure dialogue with no narrative frame, e.g.
    just a quoted line -- falls back to whatever was last established rather
    than snapping back to a default and creating whiplash mid-scene.

    Once a person is established, flipping it requires a DECISIVE signal (the
    winner leading the runner-up by >= 2), not just a bare majority. This is
    the hysteresis that stops a single stray token -- one unquoted "you"
    addressed to an NPC, one sentence-initial name that doubles as a verb --
    from silently switching the whole campaign's narration voice, which is
    exactly the flakiness heuristic person-detection is prone to. `key` lets
    additional human players each keep their own established convention.
    """
    counts = _narration_person_counts(raw_input, player_name, player_pronouns)
    best = max(counts, key=counts.get)
    top = counts[best]
    runner = max((v for k, v in counts.items() if k != best), default=0)
    detected = best if (top > 0 and top > runner) else None
    stored = wget(chat_id, key, None)

    if detected is None:
        return stored or "second"
    if stored is None or detected == stored:
        if detected != stored:
            wset(chat_id, key, detected)
        return detected
    # Established, and this turn disagrees: only override on a decisive lead.
    if top - runner >= 2:
        wset(chat_id, key, detected)
        return detected
    return stored

# Only dropped/altered dialogue is worth the cost of an automatic rewrite --
# it's an ABSOLUTE-tier violation (a player-visible line silently vanishing
# or changing), and forcing a second full narrator call on every occurrence
# doubles that stage's latency. Content-reuse is a softer quality issue (the
# model recycled prior prose instead of describing this turn) that doesn't
# warrant paying that cost automatically; it stays visible via
# fidelity_warnings for manual review instead. Missing-proper-noun warnings
# were never in this list -- that check has real false positives (e.g. a
# location's own name appearing in scenario/lore text the player would never
# actually say aloud).
_ENFORCEABLE_PREFIXES = (
    "Dialogue from view missing or altered",
)

def _generate_narration(payload, view, prev, p_lines, correction_notes=None):
    call_payload = dict(payload)
    if correction_notes:
        call_payload["correction_notes"] = correction_notes
    out = _agent_json(
        "narrator",
        "narrator",
        get_prompt("narrator"),
        call_payload,
        max_tokens=200000,
    )
    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json.
    out, warnings = validate_llm_output("narrator", out)
    out.setdefault("prose", out.get("text", ""))
    out.setdefault("new_specifics", [])
    # The player's own declared lines must NOT count toward DIALOGUE
    # FIDELITY -- PLAYER ECHO RULE requires the opposite of them (excluded,
    # not present), so scoring them here would make the two rules fight and
    # push the retry loop toward violating the echo rule to "fix" a false
    # positive.
    fidelity_warnings = _check_narrator_fidelity(
        out, view, recent_prose=prev, exclude_quotes=p_lines)
    return out, warnings, fidelity_warnings

def narrator(ctx, nonce):
    chat = ctx.chat
    pers = persona_of(chat)
    est = ctx.get("director_establish") or {}
    if est:
        view = (ctx.get("perception_establish", {}).get("views") or {}).get("player") \
            or "You register your immediate surroundings."
    else:
        view = (ctx.get("perception_outcome", {}).get("views") or {}).get("player") \
            or "Nothing in particular reaches you this beat."
    # Frame-filtered: t.idx is GLOBAL play order shared by every frame,
    # so without this an OTHER concurrently-played frame's prior prose
    # would leak into this frame's own rhythm/repetition context.
    rows = q("SELECT v.content FROM turns t "
             "JOIN steps s ON s.turn_id=t.id AND s.key='narrator' "
             "JOIN variants v ON v.step_id=s.id AND v.active=1 "
             "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? ORDER BY t.idx DESC LIMIT 4",
             (chat["id"], ctx.turn["idx"], ctx.turn["frame_id"]))
    prev = [json.loads(r["content"]).get("prose", "") for r in reversed(rows)]
    di = ctx.get("director_interpret") or {}
    p_lines = player_speech_lines(di)

    player_declared = {
        "sequence": di.get("sequence") or [],
        "speech": di.get("speech"),
        "action": (di.get("action") or {}).get("attempt"),
        "private_thought": di.get("private_thought"),
        "raw_input": ctx.input or "",
    }

    player_name = pers.get("identity", {}).get("name") or "Player" if isinstance(pers, dict) else "Player"
    player_pronouns = pers.get("identity", {}).get("pronouns", {}) if isinstance(pers, dict) else {}
    narration_person = _resolve_narration_person(
        chat["id"], ctx.input or "", player_name, player_pronouns)

    payload = {
        "player_view": view,
        "player_declared": player_declared,
        "do_not_quote_verbatim": p_lines,
        "scene_opening": bool(est),
        "private_voice_setting": (
            pers.get("narration", {}).get("voice_setting", "")
            if isinstance(pers, dict) else ""
        ),
        "narration_person": narration_person,
        "player_name": player_name,
        "player_pronouns": player_pronouns,
        "recent_prose_for_rhythm": prev,
        "already_established_phrases": _already_established_phrases(view, prev),
        "exemplars": json.loads(get_setting("exemplars") or "[]"),
        "variant_seed": nonce,
    }
    out, warnings, fidelity_warnings = _generate_narration(payload, view, prev, p_lines)

    enforceable = [w for w in fidelity_warnings if w.startswith(_ENFORCEABLE_PREFIXES)]
    if enforceable:
        correction = ("Your previous draft for THIS turn had these problems -- "
                      "rewrite fixing them, without introducing new ones: "
                      + " | ".join(enforceable))
        out, warnings, fidelity_warnings = _generate_narration(
            payload, view, prev, p_lines, correction_notes=correction)

    ctx.warnings.extend(warnings)
    if fidelity_warnings:
        ctx.warnings.extend(fidelity_warnings)
        # ctx.warnings is accumulated pipeline-wide but never surfaced
        # anywhere (not streamed, not persisted, not logged) -- see
        # AGENTS.md's safe-change workflow: attach directly to this
        # step's own saved output so a content-fidelity failure is at
        # least visible in the step/variant inspector instead of
        # vanishing silently.
        out["fidelity_warnings"] = fidelity_warnings

    out["prose"] = _strip_player_echo(out.get("prose", ""), p_lines)
    return out

def narrator_extra(ctx, nonce):
    """Renders one prose view per additional human player declaring in this
    beat (ctx.extra_players), mirroring narrator() above but keyed by
    persona_id rather than hardcoded to the single primary player. A
    deliberately separate function rather than a refactor of narrator()
    itself -- narrator() is exercised by every existing single-player chat,
    and this only ever runs when ctx.extra_players is non-empty, so it
    can't regress anything by construction.
    """
    if not ctx.extra_players:
        return {}

    chat = ctx.chat
    est = ctx.get("director_establish") or {}
    outcome_views = (ctx.get("perception_outcome", {}) or {}).get("views") or {}
    establish_views = (ctx.get("perception_establish", {}) or {}).get("views") or {}
    di = ctx.get("director_interpret") or {}
    other_players = di.get("other_players") or {}

    # Frame-filtered -- see the matching comment in narrator() above.
    rows = q("SELECT v.content FROM turns t "
             "JOIN steps s ON s.turn_id=t.id AND s.key='narrator_extra' "
             "JOIN variants v ON v.step_id=s.id AND v.active=1 "
             "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? ORDER BY t.idx DESC LIMIT 4",
             (chat["id"], ctx.turn["idx"], ctx.turn["frame_id"]))
    per_persona_prev = [json.loads(r["content"]) for r in reversed(rows)]

    def render_one(extra):
        pid = extra["persona_id"]
        pid_key = str(pid)
        entry = other_players.get(pid_key) or {}
        p_lines = player_speech_lines(entry)

        view = (establish_views.get(f"extra:{pid_key}") if est else
                outcome_views.get(f"extra:{pid_key}")) \
            or "Nothing in particular reaches you this beat."

        prev = [d.get(pid_key, {}).get("prose", "") for d in per_persona_prev]

        player_declared = {
            "sequence": entry.get("sequence") or [],
            "speech": entry.get("speech"),
            "action": (entry.get("action") or {}).get("attempt"),
            "private_thought": entry.get("private_thought"),
            "raw_input": extra.get("input") or "",
        }

        narration_person = _resolve_narration_person(
            chat["id"], extra.get("input") or "", extra.get("name"),
            extra.get("pronouns") or {}, key=f"narration_person:extra:{pid}")

        payload = {
            "player_view": view,
            "player_declared": player_declared,
            "do_not_quote_verbatim": p_lines,
            "scene_opening": bool(est),
            "private_voice_setting": "",
            "narration_person": narration_person,
            "player_name": extra.get("name") or "Player",
            "player_pronouns": extra.get("pronouns") or {},
            "recent_prose_for_rhythm": prev,
            "already_established_phrases": _already_established_phrases(view, prev),
            "exemplars": json.loads(get_setting("exemplars") or "[]"),
            "variant_seed": nonce,
        }
        out, warnings, fidelity_warnings = _generate_narration(payload, view, prev, p_lines)

        enforceable = [w for w in fidelity_warnings if w.startswith(_ENFORCEABLE_PREFIXES)]
        if enforceable:
            correction = ("Your previous draft for THIS turn had these problems -- "
                          "rewrite fixing them, without introducing new ones: "
                          + " | ".join(enforceable))
            out, warnings, fidelity_warnings = _generate_narration(
                payload, view, prev, p_lines, correction_notes=correction)

        if fidelity_warnings:
            out["fidelity_warnings"] = fidelity_warnings

        out["prose"] = _strip_player_echo(out.get("prose", ""), p_lines)
        return pid_key, out, warnings, fidelity_warnings

    # Each extra player's narration only reads data already computed before
    # this step runs (director_interpret/perception_outcome) and never reads
    # another extra player's own output -- genuinely independent work, same
    # as the mapping+perception_act pairing elsewhere in the pipeline. wget/
    # wset calls inside render_one write to distinct per-persona keys
    # (narration_person:extra:<pid>), so concurrent execution is safe;
    # ctx.warnings mutation is deferred to the main thread below rather than
    # done inside each worker, avoiding any concurrent-list-mutation risk.
    #
    # context.run(...) below is load-bearing, not decoration:
    # ThreadPoolExecutor workers do NOT inherit the submitting thread's
    # contextvars the way agents/runtime.py's own bespoke thread-spawning
    # helpers (_stream_one/_stream_parallel) do -- those explicitly
    # contextvars.copy_context() before starting each thread. Without this,
    # providers.cancel_event/token_sink (set by the step-level worker
    # thread that's currently running this whole narrator_extra call)
    # would read back as their thread-default None inside render_one,
    # silently making an in-flight abort unable to interrupt these calls
    # and dropping their streamed tokens from the event bus.
    # A fresh copy per job, not one copy shared across jobs -- a single
    # Context object cannot be entered by more than one thread at once
    # (contextvars.Context.run raises RuntimeError if already running
    # elsewhere), and these jobs run concurrently on the pool.
    jobs = [
        (lambda extra=extra, cv=contextvars.copy_context(): cv.run(render_one, extra))
        for extra in ctx.extra_players
    ]
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(ctx.extra_players))) as pool:
        for pid_key, out, warnings, fidelity_warnings in pool.map(lambda f: f(), jobs):
            ctx.warnings.extend(warnings)
            if fidelity_warnings:
                ctx.warnings.extend(fidelity_warnings)
            results[pid_key] = out

    return results
