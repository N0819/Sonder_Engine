"""Shared coercion, validation, lore, sequence, and perception helpers."""

from __future__ import annotations

import hashlib
import json
import re

from character_schema import (
    character_knowledge_config,
    character_name,
    normalize_character_data,
    persona_name,
)
from db import q
from llm_quality import complete_validated_json
from memory import chat_lorebook_ids, chat_lorebook_weights
from providers import chat_complete
from scene import get_scene, persona_of
from schemas import normalize_speech_volume
from spatial import has_visual, nearby_rooms, room_of
from theory_of_mind import _TOM_CONFIDENCE_CAPS, cap_mind_model_updates

_REACTIVE_VERBS = {
    "attack", "stab", "shoot", "strike", "grab", "restrain",
    "shove", "throw", "charge", "lunge", "block", "steal",
    "cast", "shoot at", "fire at", "swing at",
}

_REACTIVE_STAGES = {
    "preparation", "approach", "contact", "sustained",
}

ATTEMPT_CUES = (
    "try", "attempt", "aim", "rush", "lunge", "swing at", "reach for",
    "move toward", "charge", "throw at", "shoot at", "fire at",
    "grab for", "lunge at", "dive for", "reach toward",
)

ASSERTION_SKIP_CUES = (
    "try", "attempt", "aim ", "try to", "attempt to",
)

def _dict(value):
    return value if isinstance(value, dict) else {}

def _list(value):
    return value if isinstance(value, list) else []

def _dict_list(value):
    return [item for item in _list(value) if isinstance(item, dict)]

def _text_piece(value) -> str:
    """Normalize heterogeneous values for retrieval queries."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )
        except (TypeError, ValueError):
            return ""
    return str(value).strip()

def _join_text(values) -> str:
    """Safely join retrieval-query components."""
    parts = [_text_piece(value) for value in values]
    return " ".join(part for part in parts if part)

def _assert_plan_materialized(turn_id, plan, ctx):
    """Verify that every planned step produced one active result."""
    expected = [key for key, _ in plan]

    rows = q(
        """
        SELECT
            s.key,
            COUNT(v.id) AS active_count
        FROM steps s
        LEFT JOIN variants v
          ON v.step_id=s.id
         AND v.active=1
        WHERE s.turn_id=?
        GROUP BY s.key
        """,
        (turn_id,),
    )

    active_counts = {
        row["key"]: int(row["active_count"])
        for row in rows
    }

    missing_context = [
        key
        for key in expected
        if key not in ctx
    ]

    invalid_results = [
        key
        for key in expected
        if active_counts.get(key, 0) != 1
    ]

    if missing_context or invalid_results:
        details = []

        if missing_context:
            details.append(
                "missing from context: "
                + ", ".join(missing_context)
            )

        if invalid_results:
            details.append(
                "without exactly one active variant: "
                + ", ".join(invalid_results)
            )

        raise RuntimeError(
            "Pipeline completion invariant failed; "
            + "; ".join(details)
        )

def _character_by_id(ctx, char_id):
    return next(row for row in ctx.cast if int(row["id"]) == int(char_id))

def _contextual_rooms(sc, cast, *extra_room_ids, hops=1):
    """The rooms dict to actually serialize into a stage's LLM payload:
    every occupied room (cast members' current rooms plus any extra room
    ids the caller supplies, e.g. the player's room) and their immediate
    neighbors, rather than the full scene.rooms dict. See
    spatial.nearby_rooms for why this exists. Callers must keep using the
    full, unfiltered scene for any deterministic spatial check.
    """
    centers = set()
    for row in cast:
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        r = room_of(sc, character_name(sheet))
        if r:
            centers.add(r)
    for extra in extra_room_ids:
        if extra:
            centers.add(extra)
    return nearby_rooms(sc, centers, hops=hops)

def _char_known_tags(sheet):
    config = character_knowledge_config(sheet)
    tags = [tag for tag in ("common", "scholarly", "esoteric") if config.get(tag)]
    return tags, config.get("excluded_titles") or []

def _character_display_name(row):
    return character_name(json.loads(row["sheet"]))

def _normalize_scene_patch(value):
    patch = dict(value or {})
    for key in ("rooms", "entities", "positions"):
        if not isinstance(patch.get(key), dict):
            patch[key] = {}
    for key in ("remove_entities", "remove_rooms", "remove_adjacent"):
        if not isinstance(patch.get(key), list):
            patch[key] = []
    return patch

def _sequence_has_content(result):
    return any(
        (event.get("text") if event.get("type") == "speech"
         else event.get("attempt"))
        for event in (result.get("sequence") or [])
        if isinstance(event, dict)
    )

def _asks_player(result, chat):
    player_name = persona_name(persona_of(chat))
    interaction = _dict(result.get("interaction"))
    addresses = {
        str(v).casefold()
        for v in _list(interaction.get("addresses"))
    }
    aliases = {"player", "the player", "you", player_name.casefold()}
    if addresses & aliases:
        return True
    for event in _dict_list(result.get("sequence")):
        if event.get("type") != "speech":
            continue
        text = str(event.get("text") or "").strip()
        if text.endswith("?"):
            return True
    return False

def _next_speaker_candidates(ctx, last_actor_id, perceived_by, already_spoke):
    candidates = []
    for row in ctx.cast:
        char_id = int(row["id"])
        if char_id == last_actor_id or char_id not in perceived_by:
            continue
        result = _dict(ctx.character_results.get(char_id))
        interaction = _dict(result.get("interaction"))
        priority = float(interaction.get("urgency", 0.0))
        if char_id not in already_spoke:
            priority += 0.2
        candidates.append((priority, char_id))
    candidates.sort(reverse=True)
    return [char_id for _, char_id in candidates]

def _requires_reaction_phase(event, valid_actor_ids, actor_names):
    """Only genuinely urgent contestable physical actions trigger reactions."""
    if not isinstance(event, dict):
        return False
    if event.get("type") != "action":
        return False
    if event.get("commitment") != "contestable":
        return False

    targets_actor = False
    for target in event.get("targets") or []:
        if isinstance(target, int) and target in valid_actor_ids:
            targets_actor = True
            break
        text = str(target).strip().casefold()
        if text.isdigit() and int(text) in valid_actor_ids:
            targets_actor = True
            break
        if text in actor_names:
            targets_actor = True
            break

    if not targets_actor:
        return False

    verb = str(event.get("verb") or "").casefold()
    attempt = str(event.get("attempt") or "").casefold()
    stage = str(event.get("stage") or "immediate")

    return bool(
        verb in _REACTIVE_VERBS
        or any(term in attempt for term in _REACTIVE_VERBS)
        or (stage in _REACTIVE_STAGES and event.get("intended_effects"))
    )

def _requires_director_resolution(result):
    actions = [
        e for e in _dict_list(result.get("sequence"))
        if e.get("type") == "action"
    ]
    for action in actions:
        text = str(action.get("attempt") or "").casefold()
        if action.get("visibility") == "concealed":
            return True
        if action.get("targets"):
            return True
        conflict_terms = (
            "attack", "grab", "restrain", "steal", "break", "force",
            "cast", "shoot", "stab", "strike", "move into", "leave", "enter",
        )
        if any(term in text for term in conflict_terms):
            return True
    return False

def _classify_action_commitment(raw_text):
    """Classify an action as asserted or contestable."""
    text = (raw_text or "").casefold().strip()
    if not text:
        return "contestable"
    if any(cue in text for cue in ATTEMPT_CUES):
        return "contestable"
    return "asserted"

def _normalize_effect(effect):
    """Coerce a string or partial dict into a full effect dict."""
    if isinstance(effect, str):
        return {"target_id": None, "kind": effect, "details": {}}
    if isinstance(effect, dict):
        return effect
    if effect is None:
        return None
    return {"target_id": None, "kind": str(effect), "details": {}}

def _extract_authority_claims(sequence, raw_input):
    """Extract authority claims from the interpreted sequence."""
    claims = []
    for i, event in enumerate(sequence or []):
        if event.get("type") != "action":
            continue
        commitment = event.get("commitment")
        if commitment is None:
            commitment = _classify_action_commitment(
                event.get("raw_text") or event.get("attempt") or "")
        event["commitment"] = commitment
        if commitment == "asserted":
            for effect_index, effect in enumerate(
                event.get("asserted_effects") or []
            ):
                eff = _normalize_effect(effect)
                if eff is None:
                    continue
                claims.append({
                    "claim_id": f"claim:{i}:effect:{effect_index}",
                    "scope": "effect",
                    "subject_id": eff.get("target_id"),
                    "predicate": eff.get("kind", ""),
                    "value": eff.get("details"),
                    "commitment": "asserted",
                    "source_text": event.get("raw_text") or event.get("attempt") or "",
                })
        else:
            for effect_index, effect in enumerate(
                event.get("intended_effects") or []
            ):
                eff = _normalize_effect(effect)
                if eff is None:
                    continue
                claims.append({
                    "claim_id": f"claim:{i}:intent",
                    "scope": "intent",
                    "subject_id": eff.get("target_id"),
                    "predicate": eff.get("kind", ""),
                    "value": eff.get("details"),
                    "commitment": "contestable",
                    "source_text": event.get("raw_text") or event.get("attempt") or "",
                })
    return claims

def _agent_json(
    role,
    step_key,
    system,
    payload,
    *,
    temperature=None,
    max_tokens=16000,
    sampler=None,
):
    """The STRICT validated-JSON path every state-mutating pipeline stage
    must use for its primary LLM call. complete_validated_json parses
    strictly, runs schemas.validate_llm_output_strict (Pydantic schema +
    semantic checks for step_key), attempts one temperature-0 repair, then
    walks the role's remaining model candidates -- and RAISES if nothing
    validates, so a hopelessly malformed output surfaces as a normal
    rerunnable step error instead of committing junk. The follow-up
    schemas.validate_llm_output calls some stages make on this function's
    return value are warning-only re-normalization of already-validated
    output, NOT the guard -- do not downgrade a stage to jparse or a bare
    chat_complete for output that reaches commit.py.
    """
    return complete_validated_json(
        role=role,
        step_key=step_key,
        system=system,
        payload=payload,
        temperature=temperature,
        max_tokens=max_tokens,
        sampler=sampler,
        repair_attempts=1,
    )

def jparse(text, fallback_key="text", required=False):
    t = re.sub(r"^```[a-zA-Z]*\n?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    try:
        repaired = re.sub(r',\s*([}\]])', r'\1', t)
        return json.loads(repaired)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        block = m.group(0)
        try:
            return json.loads(block)
        except Exception:
            pass
        try:
            repaired = re.sub(r',\s*([}\]])', r'\1', block)
            return json.loads(repaired)
        except Exception:
            pass
    if required:
        raise RuntimeError(
            f"LLM returned unparseable JSON (first 200 chars): {(text or '')[:200]}")
    return {fallback_key: text}

def _books(ctx, refresh=False):
    if refresh or ctx.get("_books") is None:
        ctx["_books"] = chat_lorebook_ids(ctx.chat.id)
    return ctx["_books"]

def _book_weights(ctx, refresh=False):
    if refresh or ctx.get("_book_weights") is None:
        ctx["_book_weights"] = chat_lorebook_weights(ctx.chat.id)
    return ctx["_book_weights"]

def lore_for(ctx):
    entries = ((ctx.get("mapping_stage") or ctx.get("mapping_quick") or {})
               .get("relevant_lore") or [])
    allowed = ("id", "entry_uid", "book_id", "keys", "content", "category", "locked")
    return [{k: e.get(k) for k in allowed if k in e}
            for e in entries if isinstance(e, dict)]

def _room_notes_from_lore(room_id, ctx):
    if not room_id:
        return ""
    sc = get_scene(ctx.chat.id, ctx.chat)
    rdata = (sc.get("rooms") or {}).get(room_id)
    if rdata and rdata.get("notes"):
        return rdata["notes"]
    staged = ((ctx.get("mapping_stage") or {}).get("staged_lore") or []) + \
             ((ctx.get("mapping_quick") or {}).get("staged_lore") or [])
    room_norm = room_id.lower().replace("_", " ")
    for entry in staged:
        keys = (entry.get("keys") or "").lower()
        content = entry.get("content") or ""
        if (room_norm in keys or room_id.lower() in keys) and content:
            return content[:600]
    for entry in lore_for(ctx):
        keys = (entry.get("keys") or "").lower()
        content = entry.get("content") or ""
        if (room_norm in keys or room_id.lower() in keys) and content:
            return content[:600]
    return ""

def norm_sequence(out):
    seq = out.get("sequence")
    if not isinstance(seq, list) or not seq:
        seq = []
        if out.get("speech"):
            seq.append({
                "type": "speech",
                "text": out["speech"],
                "volume": normalize_speech_volume(
                    out.get("speech_volume")
                ),
            })
    acts = out.get("actions")
    if not isinstance(acts, list):
        acts = [out["action"]] if out.get("action") else []
    for a in acts:
        if isinstance(a, dict):
            seq.append({"type": "action", **a})
    clean = []
    for e in seq:
        if not isinstance(e, dict):
            continue
        t = e.get("type") or (
            "speech" if (e.get("text") or e.get("speech")) else "action"
        )
        if t == "speech":
            txt = e.get("text") or e.get("speech")
            if txt:
                # Carry the speech element's OWN concealment through
                # normalization. Dropping it here (as we used to) meant a
                # line the director explicitly marked visibility:'concealed'
                # was re-emitted as overt, so perception_act's onset delivery
                # -- which reads visibility/conceal_from straight off these
                # normalized speech elements -- leaked the private words to
                # every in-range perceiver, including whoever it was
                # concealed from. See tests/test_speech_concealment.py.
                clean.append({
                    "type": "speech",
                    "text": str(txt),
                    "volume": normalize_speech_volume(e.get("volume")),
                    "tone": e.get("tone", ""),
                    "visibility": "concealed" if e.get("visibility") == "concealed" else "overt",
                    "conceal_from": e.get("conceal_from") or [],
                    # raw (pre-normalization) signals, consumed by the
                    # concealment backstop below and stripped before return.
                    "_raw_vis": e.get("visibility"),
                    "_raw_vol": e.get("volume"),
                })
        else:
            att = e.get("attempt")
            if att:
                tg = e.get("targets") or e.get("target") or []
                if not isinstance(tg, list):
                    tg = [tg]
                commitment = e.get("commitment")
                if commitment is None:
                    commitment = _classify_action_commitment(
                        e.get("raw_text") or att
                    )
                raw_intended = e.get("intended_effects") or []
                raw_asserted = e.get("asserted_effects") or []
                intended_effects = [
                    _normalize_effect(eff)
                    for eff in raw_intended
                    if _normalize_effect(eff) is not None
                ]
                asserted_effects = [
                    _normalize_effect(eff)
                    for eff in raw_asserted
                    if _normalize_effect(eff) is not None
                ]
                clean.append({
                    "type": "action",
                    "attempt": att,
                    "visibility": e.get("visibility", "overt"),
                    "conceal_from": e.get("conceal_from") or [],
                    "targets": tg,
                    "commitment": commitment,
                    "verb": e.get("verb", ""),
                    "stage": e.get("stage", "immediate"),
                    "intended_effects": intended_effects,
                    "asserted_effects": asserted_effects,
                })
    # Deterministic concealment backstop (leak-safe). A hushed or unmarked
    # line co-declared with a concealed action is almost always the private
    # communication itself; weak models routinely mark the ACTION concealed
    # (e.g. "open a private channel", "whisper an aside") but leave the SPEECH
    # overt, which would leak the words to everyone in range. So: for every
    # speech element that is not EXPLICITLY public, propagate the union of all
    # concealed actions' conceal_from onto it. "Explicitly public" = the model
    # set an explicit overt visibility, or an explicit loud/shout volume. We
    # never override a speech the model already marked concealed, and we
    # subtract the concealing actions' own targets so the intended addressee
    # is never made deaf. Over-concealment only costs marginal eavesdroppers
    # (the addressee still hears); a leak is irreversible.
    concealed_from_union, conceal_targets = [], []
    for e in clean:
        if e["type"] == "action" and e.get("visibility") == "concealed":
            for cf in e.get("conceal_from") or []:
                if cf not in concealed_from_union:
                    concealed_from_union.append(cf)
            for tg in e.get("targets") or []:
                if tg not in conceal_targets:
                    conceal_targets.append(tg)
    propagate = [cf for cf in concealed_from_union if cf not in conceal_targets]
    if propagate:
        for e in clean:
            if e["type"] != "speech" or e.get("visibility") == "concealed":
                continue
            explicitly_public = (e.get("_raw_vis") == "overt") or (e.get("_raw_vol") in ("loud", "shout"))
            if explicitly_public:
                continue
            e["visibility"] = "concealed"
            e["conceal_from"] = list(propagate)
    for e in clean:
        e.pop("_raw_vis", None)
        e.pop("_raw_vol", None)

    out["sequence"] = clean
    sp = [e for e in clean if e["type"] == "speech"]
    ac = [e for e in clean if e["type"] == "action"]
    out["speech"] = sp[0]["text"] if sp else None
    out["speech_volume"] = (
        sp[0]["volume"] if sp else out.get("speech_volume", "normal")
    )
    out["action"] = (
        {
            "attempt": ac[0]["attempt"],
            "visibility": ac[0]["visibility"],
            "conceal_from": ac[0]["conceal_from"],
            "targets": ac[0]["targets"],
            "commitment": ac[0].get("commitment", "contestable"),
        }
        if ac
        else None
    )
    out["actions"] = ac
    return out

def assign_event_ids(sequence, prefix):
    result = []
    for index, raw in enumerate(sequence or []):
        event = dict(raw)
        event.setdefault("event_id", f"{prefix}:{index}:{event.get('type', 'event')}")
        result.append(event)
    return result

def _stable_event_key(*parts):
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"event:{digest}"

def _lore_fingerprint(entry):
    keys = re.sub(r"\s+", " ", str(entry.get("keys") or "").strip().casefold())
    content = re.sub(r"\s+", " ", str(entry.get("content") or "").strip().casefold())
    digest = hashlib.sha256(f"{keys}\x1f{content}".encode("utf-8")).hexdigest()
    return f"content:{digest}"

def _append_once(view, text, marker=None):
    text = str(text or "").strip()
    if not text:
        return view
    view = str(view or "").strip()
    marker = str(marker or text).strip()
    if marker and marker.casefold() in view.casefold():
        return view
    return f"{view} {text}".strip()

def _unknown_actor_label(actor_name, appearance_text=None):
    # Every unrecognized actor used to render as the exact same generic
    # "the unfamiliar person" -- two strangers in one scene (or the same
    # stranger across a perceiver's dialogue and action lines) were
    # indistinguishable in both prose and any memory recorded from it.
    # Derive a short, stable descriptor from the actor's own appearance
    # summary instead. This is deliberately a short label for repeat/
    # inline reference, not a substitute for the full appearance
    # description a caller surfaces separately on first mention.
    if appearance_text:
        cleaned = re.sub(
            r"^(a|an|the)\s+", "", appearance_text.strip(), flags=re.I,
        ).replace(",", "")
        words = cleaned.split()[:5]
        if words:
            return "the " + " ".join(words).rstrip(".;:").lower()
    return "the unfamiliar person"

def _contains_quote(view, quote):
    body = _quote_body(quote)
    normalized_view = re.sub(r"\s+", " ", str(view or "").casefold())
    normalized_body = re.sub(r"\s+", " ", body.casefold())
    return bool(normalized_body and normalized_body in normalized_view)

def normalize_character_refs(values, cast):
    valid_ids = {int(row["id"]) for row in cast}
    names = {}
    for row in cast:
        try:
            sheet = json.loads(row["sheet"])
            name = character_name(sheet)
        except Exception:
            name = ""
        if name:
            names[name.casefold()] = int(row["id"])
    result = []
    for value in values or []:
        resolved = None
        if isinstance(value, int) and value in valid_ids:
            resolved = value
        elif isinstance(value, str):
            text = value.strip()
            if text.isdigit() and int(text) in valid_ids:
                resolved = int(text)
            else:
                resolved = names.get(text.casefold())
        if resolved is not None and resolved not in result:
            result.append(resolved)
    return result

def character_scene_keys(sheet):
    """Every key a scene might legitimately use to store this character's
    entity/position. The intended convention keys positions by the display
    NAME, but the director sometimes keys by identity.uid (or an alias) -- so
    readers must try all of them. Name first (the intended key), then uid,
    then aliases; de-duplicated case-insensitively, display form preserved."""
    ident = normalize_character_data(sheet).get("identity", {})
    candidates = [ident.get("name"), ident.get("uid")]
    candidates.extend(ident.get("aliases") or [])
    seen, keys = set(), []
    for cand in candidates:
        text = str(cand or "").strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            keys.append(text)
    return keys

def character_room(sc, sheet):
    """Resolve a cast character's room from the scene, tolerating scenes that
    key the entity by identity.uid or an alias rather than the display name.
    Perception was previously blind to a character whose position was stored
    under its uid (e.g. `tenth_doctor` for "The Doctor"), placing them in "an
    unspecified area" and leaking a false empty view."""
    for key in character_scene_keys(sheet):
        room = room_of(sc, key)
        if room:
            return room
    return None

def cast_room(sc, name, cast):
    """Room of a named speaker/actor, mapping the bare name through the cast so
    a character stored under its uid/alias still resolves (the name-string
    counterpart to character_room)."""
    room = room_of(sc, name)
    if room:
        return room
    target = str(name or "").strip().lower()
    if not target:
        return None
    for row in cast or []:
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        if target in {key.lower() for key in character_scene_keys(sheet)}:
            return character_room(sc, sheet)
    return None

def canonicalize_positions(positions, cast):
    """Rewrite any positions key that identifies a registered cast character
    (matched by identity.uid or display name -- exact or alphanumeric-
    normalized) to that character's display name, the positions-key convention
    every reader (perception, commit, spatial) expects. Non-character keys
    (objects, unregistered entities) are left untouched. Deliberately does NOT
    match on aliases: a generic alias (e.g. "John Smith") could collide with a
    genuinely separate entity, and rewriting a write is higher-stakes than a
    read. This keeps a director that keyed a position by uid from hiding a
    character from perception."""
    if not isinstance(positions, dict) or not cast:
        return positions if isinstance(positions, dict) else {}
    keymap = {}
    for row in cast:
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        ident = normalize_character_data(sheet).get("identity", {})
        name = ident.get("name") or character_name(sheet)
        for key in (ident.get("uid"), name):
            text = str(key or "").strip()
            if not text:
                continue
            keymap.setdefault(text.lower(), name)
            norm = re.sub(r"[^a-z0-9]", "", text.lower())
            if norm:
                keymap.setdefault(norm, name)
    result = {}
    for key, room in positions.items():
        text = str(key or "").strip()
        canon = keymap.get(text.lower()) \
            or keymap.get(re.sub(r"[^a-z0-9]", "", text.lower()))
        result[canon or key] = room
    return result

def _append_micro_view(base_view, additions):
    parts = [str(base_view or "").strip()]
    parts.extend(str(item).strip() for item in additions if str(item or "").strip())
    return "\n\n".join(part for part in parts if part)

def _normalize_character_output(out):
    if not out.get("mind_model_updates") and out.get("inference_updates"):
        converted = []
        for update in out["inference_updates"]:
            converted.append({
                "about_entity": str(update.get("about") or "unknown"),
                "kind": "goal",
                "claim": str(update.get("conclusion") or ""),
                "confidence": float(update.get("confidence", 0.5)),
                "evidence": [{"event_id": "", "fact": str(update.get("basis") or "")}],
                "alternatives": [],
            })
        out["mind_model_updates"] = converted
    return out

def player_speech_lines(interp):
    lines = [e.get("text") for e in (interp.get("sequence") or [])
             if e.get("type") == "speech" and e.get("text")]
    if not lines and interp.get("speech"):
        lines = [interp["speech"]]
    return lines

def _quote_body(quote):
    return (quote or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")

def _inject_dialogue(view, display, quote, level, volume, can_see):
    if level == "none":
        return view
    body = _quote_body(quote)
    if not body or _contains_quote(view, body):
        return view
    if level == "fragment":
        words = body.split()
        if len(words) <= 3:
            frag = "...something indistinct..."
        else:
            mid = len(words) // 2
            frag = "...something about " + " ".join(words[mid:mid + 3]) + "..."
        return _append_once(view, f"A muffled voice: {frag}")
    if volume == "shout":
        verb = "shouts"
    elif volume in ("whisper", "mutter"):
        verb = "says under their breath"
    else:
        verb = "says"
    if can_see:
        add = f'{display} {verb}: "{body}"'
    else:
        add = f'You hear {display} {verb}: "{body}"'
    return _append_once(view, add)

def _inject_action(view, display, attempt, can_see, event_id=None, delivered=None):
    if not attempt or not can_see:
        return view
    if delivered is not None and event_id:
        if event_id in delivered:
            return view
        delivered.add(event_id)
    normalized_attempt = re.sub(r"\s+", " ", str(attempt).strip().lower())
    normalized_view = re.sub(r"\s+", " ", str(view or "").lower())
    if normalized_attempt and normalized_attempt in normalized_view:
        return view
    return _append_once(view, f"{display} {attempt}.", marker=f"{display} {attempt}")

def _inject_visible_actor(
    view,
    *,
    display,
    appearance,
    relation,
):
    if not has_visual(relation):
        return view

    text = str(view or "").strip()

    contradiction_patterns = (
        r"\bno visual sign of the speaker is visible\b",
        r"\bno clear figure visible\b",
        r"\bthe speaker is not visible\b",
        r"\bcannot see (?:them|the speaker|anyone)\b",
    )

    for pattern in contradiction_patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.I,
        )

    text = re.sub(r"\s{2,}", " ", text).strip()

    if appearance:
        return _append_once(
            text,
            f"You see {appearance}.",
            marker=appearance,
        )

    return _append_once(
        text,
        f"You see {display}.",
        marker=display,
    )

def _normalise_views(raw_views, perceivers):
    if not isinstance(raw_views, dict):
        raw_views = {}
    # Casefolded map of the literal perceiver ids themselves ("player",
    # "extra:<id>", numeric ids) onto their canonical spelling -- a model
    # returning "Player" or "Extra:12" must fold onto the exact key every
    # consumer reads (views.get("player") etc.) instead of being dropped.
    id_by_fold = {str(p["id"]).casefold(): str(p["id"]) for p in perceivers}
    name_to_id = {}
    for p in perceivers:
        name_to_id[p["name"]] = str(p["id"])
        name_to_id[p["name"].lower()] = str(p["id"])
    clean = {}
    for k, v in raw_views.items():
        sk = str(k).strip()
        if sk.lower() == "player" and "player" not in id_by_fold:
            continue
        canonical_id = id_by_fold.get(sk.casefold())
        if canonical_id is not None:
            sk = canonical_id
        elif not sk.isdigit():
            sk = name_to_id.get(sk) or name_to_id.get(sk.lower()) or sk
        if isinstance(v, str):
            v = v.strip()
            if not v:
                v = None
        clean[sk] = v
    return clean

def _ensure_environment(view, perceiver, display, rel, vis, action_desc):
    if view:
        return view
    parts = [f"You are in {perceiver.get('room_name')}."]
    if perceiver.get("room_notes"):
        parts.append(perceiver["room_notes"])
    if rel.get("same_room"):
        parts.append(f"{display} is here with you.")
        if action_desc:
            parts.append(f"{display} attempts to {action_desc}.")
    elif vis:
        parts.append(f"You can see {display} nearby.")
    return " ".join(parts)

def _fallback_perception_views(perceivers, dlog, resolved_event=None):
    views = {}
    for p in perceivers:
        pid = str(p["id"])
        p_room = p.get("room")
        parts = []
        rname = p.get("room_name")
        rnotes = p.get("room_notes")
        if rname and rname != "None":
            parts.append(f"You are in {rname}.")
        if rnotes:
            parts.append(rnotes)
        for d in dlog:
            spk_room = d.get("speaker_room")
            if spk_room and p_room and spk_room == p_room:
                parts.append(f'{d["speaker"]} says: {d["exact_quote"]}')
        views[pid] = " ".join(parts) if parts else None
    return views

_DANGLING_SPEECH_VERB_RE = re.compile(
    r"\b(say|says|said|ask|asks|asked|tell|tells|told|call|calls|called|"
    r"shout|shouts|shouted|murmur|murmurs|murmured|whisper|whispers|whispered|"
    r"reply|replies|replied|answer|answers|answered)\b,?\s*(?=[.,]|$)",
    re.IGNORECASE,
)

def _strip_player_echo(prose, lines):
    if not prose:
        return prose
    for speech in (lines or []):
        body = (speech or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")
        if not body:
            continue
        # Quoted forms are delimited by quote marks, so stripping them is
        # safe at any length. The bare (unquoted) form is only stripped for
        # longer lines, since a short bare substring (e.g. "no") risks
        # corrupting unrelated words ("know", "not"). Without this split,
        # short player lines (e.g. "Stop!", "Wait!") were never stripped at
        # all and echoed verbatim in narrator prose.
        quoted_forms = ('"%s"' % body, "\u201c%s\u201d" % body)
        matched = any(q in prose for q in quoted_forms)
        if len(body) >= 8 and body in prose:
            matched = True
        if not matched:
            continue
        for quoted in quoted_forms:
            prose = prose.replace(quoted, "")
        if len(body) >= 8:
            prose = prose.replace(body, "")
        # Stripping the quote can leave a dangling speech verb ("you say,",
        # "I ask,", "Alex says.") with nothing after it -- the subject varies
        # with narration_person (first/second/third), so match on the verb
        # rather than assuming "you".
        prose = _DANGLING_SPEECH_VERB_RE.sub(lambda m: f"{m.group(1)} it.", prose)
    return re.sub(r"\s{2,}", " ", prose).strip()

def _word_shingles(text, n=6):
    words = re.findall(r"[a-z0-9']+", str(text or "").lower())
    return {
        " ".join(words[i:i + n])
        for i in range(len(words) - n + 1)
    }

def _already_established_phrases(view, recent_prose, limit=12):
    """Deterministic overlap between THIS turn's raw view and the narrator's
    own recent prose. perception_act/perception_outcome re-describe the full
    room every turn by design (they're a stateless sensory filter with no
    memory of prior turns) -- but that means the narrator's job of "don't
    re-catalog what's unchanged" requires knowing what it already said. Doing
    that by having the model compare two blobs of prose itself is unreliable;
    this hands it a concrete, computed list instead.
    """
    view_shingles = _word_shingles(str(view or ""))
    if not view_shingles:
        return []
    hits = set()
    for prev in recent_prose or []:
        hits |= (view_shingles & _word_shingles(prev))
    return sorted(hits)[:limit]

_NARRATION_QUOTE_RE = re.compile(r'["“][^"“”]*["”]')
_NARRATION_SQUOTE_RE = re.compile(r"(?<!\w)'[^']{3,}?'(?!\w)")
_FIRST_PERSON_RE = re.compile(
    r"\b(i|i'm|i've|i'll|i'd|me|my|mine|myself"
    r"|we|we're|we've|we'll|we'd|us|our|ours|ourselves)\b", re.IGNORECASE)
_SECOND_PERSON_RE = re.compile(
    r"\b(you|you're|you've|you'll|you'd|your|yours|yourself)\b", re.IGNORECASE)
# Third-person player evidence comes almost entirely from the player's NAME
# used as a proper noun; pronouns are inherently ambiguous ("her"/"him"/
# "them" nearly always refer to OTHER people in the scene). We therefore
# count only subjective-form player pronouns and never object/possessive
# ones -- and even those only survive as a tiebreak once hysteresis in
# _resolve_narration_person guards against a lone token flipping the whole
# campaign's established person.
_THIRD_SUBJECT_PRONOUNS = frozenset({"he", "she", "they"})

def _narration_person_counts(raw_input, player_name=None, player_pronouns=None):
    """Weighted first/second/third-person evidence from the player's own
    phrasing this turn, after stripping quoted dialogue (a "you" inside a
    spoken line addresses another character, not the player's narrating
    voice). Precision fixes over a naive word count:

    - Player-name parts are matched CASE-SENSITIVELY as proper nouns, so a
      character named "Will"/"Mark"/"Grace"/"Rose" no longer collects
      spurious third-person hits from the ordinary words "will"/"mark"/etc.
    - Only subjective-form player pronouns (he/she/they) are counted, and
      each distinct pronoun string is counted once -- so an object/possessive
      pronoun referring to someone else ("I gave her the key") and duplicate
      dict values (obj == poss == "her") no longer masquerade as the player
      being narrated in third person.
    """
    narrative = _NARRATION_QUOTE_RE.sub(" ", str(raw_input or ""))
    narrative = _NARRATION_SQUOTE_RE.sub(" ", narrative)
    counts = {
        "first": len(_FIRST_PERSON_RE.findall(narrative)),
        "second": len(_SECOND_PERSON_RE.findall(narrative)),
        "third": 0,
    }
    for part in re.findall(r"[A-Za-z']+", str(player_name or "")):
        # Case-sensitive, and only for parts written as a proper noun; a
        # lowercase name can't be told apart from the common word it collides
        # with, so we decline to guess and let the fallback hold.
        if len(part) >= 3 and part[:1].isupper():
            counts["third"] += len(re.findall(rf"\b{re.escape(part)}\b", narrative))
    seen_pronouns = set()
    for pron in (player_pronouns or {}).values():
        pron = str(pron or "").strip().lower()
        if pron in _THIRD_SUBJECT_PRONOUNS and pron not in seen_pronouns:
            seen_pronouns.add(pron)
            counts["third"] += len(re.findall(rf"\b{re.escape(pron)}\b", narrative, re.IGNORECASE))
    return counts

def _detect_narration_person(raw_input, player_name=None, player_pronouns=None):
    """Guess which grammatical person the PLAYER used to phrase their own
    input this turn -- 'first' ("I open the door"), 'second' ("You open the
    door"), 'third' ("Alex opens the door") -- so the narrator can match it
    instead of always defaulting to 'you'. Whichever person has strictly more
    evidence (see _narration_person_counts) than every other wins. Ties or
    zero matches (e.g. a turn that's pure dialogue with no narrative frame)
    return None -- ambiguous, caller should fall back to whatever was already
    established.
    """
    counts = _narration_person_counts(raw_input, player_name, player_pronouns)
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        return None
    others = [v for k, v in counts.items() if k != best]
    if others and counts[best] <= max(others):
        return None
    return best

def _check_narrator_fidelity(out, view, recent_prose=None, exclude_quotes=None):
    warnings = []
    view_text = str(view or "")
    prose = out.get("prose") or ""
    view_names = set(re.findall(
        r"\b[A-Z][a-z]+(?:\s+(?:of\s+)?(?:the\s+)?[A-Z][a-z]+)+\b", view_text))
    for name in view_names:
        if name.lower() in prose.lower():
            continue
        # Good prose refers to people by surname or first name alone after
        # the first mention ("Voss", "Tommy") rather than repeating a full
        # multi-word name every time; that is not a fidelity violation.
        # Only flag names where NONE of their words appear anywhere.
        name_words = [w for w in name.split() if len(w) >= 3]
        if name_words and not any(w.lower() in prose.lower() for w in name_words):
            warnings.append(f"Proper noun from view missing in narrator prose: '{name}'")

    # recent_prose_for_rhythm is supplied to the narrator as a STYLE
    # reference, but nothing stops the model from reusing its content
    # instead -- especially when the current view covers similar ground
    # (same room, same people) to a recent turn. Two or more shared
    # six-word runs between this turn's prose and a recent turn's prose
    # essentially can't happen by coincidence; it means this turn's beats
    # were recycled rather than drawn from the current view.
    current_shingles = _word_shingles(prose)
    if current_shingles:
        for prev_prose in (recent_prose or []):
            overlap = current_shingles & _word_shingles(prev_prose)
            if len(overlap) >= 2:
                sample = next(iter(overlap))
                warnings.append(
                    "Narrator prose appears to reuse a previous turn's "
                    "content instead of describing this turn's view "
                    f"(shared phrase: '{sample}...')."
                )
                break

    # Any quoted line in the view is dialogue that reached the player at
    # full or fragment clarity (muffled hits render as unquoted "...something
    # about X..." text and are exempt). DIALOGUE FIDELITY requires every such
    # line to survive verbatim -- if the narrator drops, truncates, or
    # paraphrases a quote, the exact substring will no longer be found.
    # EXCEPT the player's own declared lines: PLAYER ECHO RULE requires those
    # to be *excluded*, the exact opposite requirement, so they must never be
    # scored against this check -- otherwise the two rules contradict each
    # other and the retry loop would be pushing the model to violate one to
    # satisfy the other.
    excluded_bodies = {
        re.sub(r"\s+", " ", _quote_body(q).casefold())
        for q in (exclude_quotes or []) if _quote_body(q)
    }
    quote_pattern = re.compile(r'["“]([^"“”]{4,})["”]')
    normalized_prose = re.sub(r"\s+", " ", prose.casefold())
    for match in quote_pattern.finditer(view_text):
        quote = re.sub(r"\s+", " ", match.group(1).strip())
        if not quote:
            continue
        if quote.casefold() in excluded_bodies:
            continue
        if quote.casefold() not in normalized_prose:
            warnings.append(
                f"Dialogue from view missing or altered in narrator prose: \"{quote[:80]}\""
            )

    return warnings

def _llm_resolve_player_room(sc, pers, cast, interp, player_input):
    positions = sc.get("positions") or {}
    if not positions:
        return None
    char_names = []
    for c in (cast or []):
        try:
            char_names.append(character_name(json.loads(c["sheet"])))
        except Exception:
            pass
    payload = {
        "player": {"name": pers.get("name") or persona_name(pers), "appearance": pers.get("appearance"),
                   "senses": pers.get("senses", "")},
        "npc_names": char_names, "position_keys": list(positions.keys()),
        "positions": positions, "rooms": sc.get("rooms", {}),
        "player_input": player_input or "",
        "movement": (interp or {}).get("movement") or {},
        "private_thought": (interp or {}).get("private_thought") or ""
    }
    sys = (
        "You are a position resolver. Given a player persona, a list of NPC character names, "
        "and a set of position keys, identify which position key corresponds to the PLAYER "
        "character. Output STRICT JSON {\"key\": \"<one of the position_keys>\"} or "
        "{\"key\": null} if no match."
    )
    try:
        out = jparse(chat_complete("utility", sys, json.dumps(payload, ensure_ascii=False),
                                   temperature=0.0, max_tokens=1000))
        key = out.get("key") if isinstance(out, dict) else None
        if key and key in positions:
            return positions[key]
    except Exception:
        pass
    return None

def _resolve_player_room(sc, pers, interp, cast, player_input=None):
    # Canonical, committed position always wins over a declared movement
    # target: a `movement.to_room` is only a request for director_resolve
    # to validate (it may be blocked — see director.py's passable-route
    # check). Trusting it here would show the player as already having
    # arrived — during perception_act, before the move is even resolved,
    # or in perception_outcome, even when director_resolve rejected it.
    p_room = room_of(sc, pers.get("name") or persona_name(pers))
    if p_room:
        return p_room
    mv = interp.get("movement") if interp else None
    if isinstance(mv, dict) and mv.get("to_room"):
        return mv["to_room"]
    char_names = set()
    for c in (cast or []):
        try:
            char_names.add(character_name(json.loads(c["sheet"])).lower().strip())
        except Exception:
            pass
    candidates = [v for k, v in (sc.get("positions") or {}).items()
                  if k.lower().strip() not in char_names]
    if len(candidates) == 1:
        return candidates[0]
    if sc.get("positions"):
        llm_room = _llm_resolve_player_room(sc, pers, cast, interp, player_input)
        if llm_room:
            return llm_room
    return None
