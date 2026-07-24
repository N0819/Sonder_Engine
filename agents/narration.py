"""Player-facing narration agent."""

from __future__ import annotations

import contextvars
import json
from concurrent.futures import ThreadPoolExecutor

from db import get_setting, q, wget, wset
from prompts import get_prompt
from scene import (
    NON_AWAKE_GATED,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    persona_of,
    get_scene,
)
import os
import re

from spatial import spatial_digest, spatial_facts, room_of


def _spatial_facts_field(scene, observer):
    """Env-gated (SPATIAL_SCAFFOLD=1) deterministic ground-truth spatial facts
    for the narrator. Off by default -> {} (no payload change, baseline
    behavior). On -> {'spatial_facts': [...]} the narrator is told not to
    contradict. Sources are everyone co-located with the observer."""
    if not os.environ.get("SPATIAL_SCAFFOLD"):
        return {}
    o_room = room_of(scene, observer)
    positions = scene.get("positions") or {}
    names = [n for n, r in positions.items() if r == o_room and n != observer]
    facts = spatial_facts(scene, observer, names)
    return {"spatial_facts": facts} if facts else {}
from schemas import validate_llm_output

from .common import (
    _agent_json,
    _already_established_phrases,
    _check_narrator_fidelity,
    _dedupe_view_sentences,
    _narration_person_counts,
    _protected_view_quotes,
    _strip_player_echo,
    player_speech_lines,
)

def _resolve_narration_person(chat_id, raw_input, player_name, player_pronouns,
                              key="narration_person", pending=None):
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

    `pending`: when a dict is supplied, the newly established/overridden
    person is RECORDED there ({key: person}) instead of written durably --
    the narrator stages stash it on their returned step content so that
    commit.py (the sole persistence boundary) applies the wset at commit
    time; model-era output stays provisional until then. Without `pending`
    the write happens immediately (direct/legacy callers).
    """
    def _record(value):
        if pending is None:
            wset(chat_id, key, value)
        else:
            pending[key] = value

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
            _record(detected)
        return detected
    # Established, and this turn disagrees: only override on a decisive lead.
    if top - runner >= 2:
        _record(detected)
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
    # A cast member's pronouns flipping mid-scene is the same tier of failure
    # as a dropped line -- the reader sees a character silently change -- and
    # the check that raises it (agents/common.py's _check_pronoun_fidelity)
    # only fires on unambiguous flips, so it is cheap enough to enforce.
    "Pronoun mismatch for",
    # PERSON DISCIPLINE is called an ABSOLUTE, hard error by the narrator
    # prompt itself, and the check that raises it (agents/common.py's
    # _check_player_person) only fires on the player's literal name outside
    # quoted dialogue -- unambiguous enough to spend a rewrite on.
    "Player named in third person",
)

# Deterministic craft screen: AI-tell phrases the PROSE CRAFT prompt bans. A
# draft containing any triggers ONE rewrite naming them (reusing the correction
# loop). Conservative -- only clear tells, to avoid false positives on ordinary
# prose. Dialogue is exempt (quotes are fixed); we scan the whole draft but the
# patterns don't match normal speech.
_CRAFT_TELLS = [
    (r"\bshift(?:s|ed|ing)?\s+(?:her|his|their|my|its)\s+weight\b", "shifts weight"),
    (r"\beyes?\s+flick(?:s|ed|ing)?\b", "eyes flick"),
    (r"\btake[sn]?\s+the\s+(?:\w+\s+){1,2}in\b(?!\s+(?:his|her|their|both|one|two)\s+hands?)",
     "'take the room in' (filtering)"),
    (r"\btak(?:e|es|ing)\s+in\s+the\s+\w+\b", "'take in the room' (filtering)"),
    (r"\bI'?m\s+aware\s+of\b", "'I'm aware of' (filtering)"),
    (r"\bwash(?:es|ed)?\s+over\s+(?:me|you|him|her|them|us)\b", "washes over (emotion)"),
    (r"\bhang(?:s|ing|ed)?\s+in\s+the\s+air\b|\bhung\s+in\s+the\s+air\b", "hangs in the air"),
    (r"\bmiddle\s+distance\b", "middle distance"),
    (r"\bfull\s+height\b", "full height"),
    (r"\bclose\s+air\b", "the close air"),
    (r"\b(?:deliberate|deliberately|unhurried|unhurriedly|pointedly|casually)\b",
     "adverb tell (deliberate/unhurried/pointedly/casually)"),
    (r"\bslow\s+and\s+steady\b", "slow and steady"),
    (r"\b(?:muted|soft|softly|dim|dimly|faint|faintly|diffused|warm|low)\s+"
     r"(?:\w+\s+){0,2}(?:glow|glimmer|gleam|light|murmur|hum|clink|drone)\b",
     "generic muted/dim + light/sound"),
]


def _craft_tells(prose: str) -> list:
    """Banned AI tells present in a narrator draft (deduped, ordered). Quoted
    dialogue is masked before scanning -- quotes are fixed (reproduced verbatim),
    so a tell inside a spoken line is not the narrator's prose and could never be
    rewritten away, which would burn a pointless retry every turn."""
    if not prose:
        return []
    # Mask curly-quoted dialogue too -- models routinely emit it, and every
    # other dialogue regex in the pipeline (agents/common.py) accepts it; a
    # tell inside curly quotes would otherwise burn unwinnable retries.
    scan = re.sub(r'"[^"]*"|“[^“”]*”', " ", prose)
    found = []
    for pat, label in _CRAFT_TELLS:
        if re.search(pat, scan, re.I):
            found.append(label)
    return list(dict.fromkeys(found))

def _cast_pronouns(cast):
    """Authoritative pronouns per cast member, so the narrator renders each
    named character in third person with their GIVEN pronouns instead of
    guessing from the name (which flipped Vorne he/she across beats). W6.
    Also the reference the deterministic pronoun-fidelity check scores against
    (agents/common.py's _check_pronoun_fidelity)."""
    out = {}
    for row in (cast or []):
        try:
            ident = (json.loads(row["sheet"]).get("identity") or {})
        except Exception:
            continue
        name = str(ident.get("name") or "").strip()
        pronouns = ident.get("pronouns") or {}
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if name and clean:
            out[name] = clean
    return out


def _generate_narration(payload, view, prev, p_lines, correction_notes=None):
    call_payload = dict(payload)
    if correction_notes:
        call_payload["correction_notes"] = correction_notes
    out = _agent_json(
        "narrator",
        "narrator",
        get_prompt("narrator"),
        call_payload,
        max_tokens=16000,
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
        out, view, recent_prose=prev, exclude_quotes=p_lines,
        cast_pronouns=call_payload.get("cast_pronouns"),
        player_name=call_payload.get("player_name"),
        narration_person=call_payload.get("narration_person"))
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

    # (x or {}) rather than .get(key, {}): a hand-edited sheet with an
    # explicit "identity": null defeats the .get default and would crash
    # the narrator stage every turn.
    player_name = (pers.get("identity") or {}).get("name") or "Player" if isinstance(pers, dict) else "Player"
    player_pronouns = (pers.get("identity") or {}).get("pronouns", {}) if isinstance(pers, dict) else {}
    # Durable persistence of a newly detected person is deferred to commit
    # (commit.py's commit_narration_person) via this pending sink -- the
    # narrator stage itself must not write world state before the commit
    # boundary validates the turn.
    pending_person_writes = {}
    narration_person = _resolve_narration_person(
        chat["id"], ctx.input or "", player_name, player_pronouns,
        pending=pending_person_writes)

    cast_pronouns = _cast_pronouns(ctx.cast)

    # Consciousness gate: when the player is non-awake, their `player_view` is
    # already the deterministic residue (perception_outcome). Do NOT also hand
    # the narrator the room's spatial frame/facts -- passing scene layout with
    # an instruction to render only a residue is exactly the "objective state +
    # instruction to ignore it" pattern the engine forbids. Gate the payload,
    # not the prose: the narrator renders an honest fade-out from the residue.
    _res_diff = (ctx.get("director_resolve") or {}).get("state_diff") or {}
    player_awareness = awareness_of(
        apply_awareness_diff(awareness_map(chat["id"]), _res_diff), player_name)
    _scene_for_frame = ctx.get("outcome_scene") or get_scene(chat["id"], chat)
    _spatial_fields = ({} if player_awareness in NON_AWAKE_GATED else {
        "spatial_frame": spatial_digest(_scene_for_frame, player_name),
        **_spatial_facts_field(_scene_for_frame, player_name),
    })

    payload = {
        "player_view": view,
        "player_declared": player_declared,
        "cast_pronouns": cast_pronouns,
        "do_not_quote_verbatim": p_lines,
        "scene_opening": bool(est),
        "player_awareness": player_awareness,
        "private_voice_setting": (
            (pers.get("narration") or {}).get("voice_setting", "")
            if isinstance(pers, dict) else ""
        ),
        "narration_person": narration_person,
        "player_name": player_name,
        "player_pronouns": player_pronouns,
        # perception_outcome stashes this turn's post-move, orientation-refreshed
        # scene; fall back to the committed KV on the opening turn (establish),
        # where no movement has happened and orientation is fresh anyway. Using
        # the committed scene here would describe the space with LAST beat's
        # facing on movement beats (commit runs after this stage).
        **_spatial_fields,
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

    # Craft screen: while the accepted draft carries banned AI tells, spend a
    # rewrite naming them (bounded to 2). Keep a rewrite ONLY if it preserves
    # dialogue fidelity AND strictly reduces the tell count -- prose quality
    # never costs a dropped line, and we never accept a lateral swap that just
    # trades one tell for another.
    best_tells = _craft_tells(out.get("prose", ""))
    _retry_cap = 0 if os.environ.get("NARRATOR_CRAFT_RETRY") == "0" else 2
    craft_attempts = 0
    while best_tells and craft_attempts < _retry_cap:
        craft_attempts += 1
        craft_note = ("Your previous draft for THIS turn used banned AI tells / weak "
                      "phrasing -- rewrite the PROSE to remove every one, keeping all "
                      "dialogue verbatim and every fact intact: " + "; ".join(best_tells))
        r_out, r_warnings, r_fid = _generate_narration(
            payload, view, prev, p_lines, correction_notes=craft_note)
        r_enforceable = [w for w in r_fid if w.startswith(_ENFORCEABLE_PREFIXES)]
        r_tells = _craft_tells(r_out.get("prose", ""))
        if not r_enforceable and len(r_tells) < len(best_tells):
            out, warnings, fidelity_warnings = r_out, r_warnings, r_fid
            best_tells = r_tells
        else:
            break

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

    if pending_person_writes:
        out["narration_person_writes"] = pending_person_writes
    # Within-view dedupe (W12): a duplicated beat -- the same sentence
    # rendered twice in one turn's prose -- is dropped deterministically.
    # Quoted dialogue and short sentences are exempt (see the helper).
    out["prose"] = _dedupe_view_sentences(_strip_player_echo(
        out.get("prose", ""), p_lines,
        protect_quotes=_protected_view_quotes(view, p_lines),
    ))
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

        # Deferred to commit exactly like narrator() above -- each pending
        # write rides this persona's own returned entry.
        pending_person_writes = {}
        narration_person = _resolve_narration_person(
            chat["id"], extra.get("input") or "", extra.get("name"),
            extra.get("pronouns") or {}, key=f"narration_person:extra:{pid}",
            pending=pending_person_writes)

        payload = {
            "player_view": view,
            "player_declared": player_declared,
            "cast_pronouns": _cast_pronouns(ctx.cast),
            "do_not_quote_verbatim": p_lines,
            "scene_opening": bool(est),
            "private_voice_setting": "",
            "narration_person": narration_person,
            "player_name": extra.get("name") or "Player",
            "player_pronouns": extra.get("pronouns") or {},
            "spatial_frame": spatial_digest(
                ctx.get("outcome_scene") or get_scene(chat["id"], chat),
                extra.get("name") or ""),
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

        if pending_person_writes:
            out["narration_person_writes"] = pending_person_writes
        # Within-view dedupe (W12) -- see the matching comment in narrator().
        out["prose"] = _dedupe_view_sentences(_strip_player_echo(
            out.get("prose", ""), p_lines,
            protect_quotes=_protected_view_quotes(view, p_lines),
        ))
        return pid_key, out, warnings, fidelity_warnings

    # Each extra player's narration only reads data already computed before
    # this step runs (director_interpret/perception_outcome) and never reads
    # another extra player's own output -- genuinely independent work, same
    # as the mapping+perception_act pairing elsewhere in the pipeline. Each
    # render_one only READS its own distinct per-persona world key
    # (narration_person:extra:<pid>); the corresponding write is recorded on
    # that persona's returned entry and applied at commit, so concurrent
    # execution is safe;
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
