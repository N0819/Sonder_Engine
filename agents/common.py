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
from spatial import (
    ambient_scope,
    has_visual,
    nearby_rooms,
    normalize_room_id,
    room_of,
)
from theory_of_mind import _TOM_CONFIDENCE_CAPS, cap_mind_model_updates

_REACTIVE_VERBS = {
    "attack", "stab", "shoot", "strike", "grab", "restrain",
    "shove", "throw", "charge", "lunge", "block", "steal",
    "cast", "shoot at", "fire at", "swing at",
}

_REACTIVE_STAGES = {
    "preparation", "approach", "contact", "sustained",
}

# Verbs whose act is INTERIOR -- it happens inside the actor's mind and has no
# outward manifestation a bystander could perceive. An observer cannot see
# someone "remember" or "decide"; surfacing such an act to another perceiver
# is a pure information-barrier leak (the actor's private cognition). Used by
# norm_sequence to default an action element's `observable` surface to "" (see
# observable_action_text) so the deterministic perception-delivery backstops
# never paste it into an observer's view. A mental act that DOES have an
# outward tell (eyes going distant, a whispered incantation) can still be
# delivered -- the director just authors an explicit `observable` for it,
# which overrides this default.
_MENTAL_VERBS = {
    "recall", "remember", "recollect", "consider", "think", "ponder",
    "reflect", "deliberate", "decide", "resolve", "realize", "realise",
    "understand", "know", "recognize", "recognise", "plan", "intend",
    "imagine", "visualize", "visualise", "concentrate", "focus", "sense",
    "feel", "believe", "assume", "wonder", "hope", "fear", "doubt",
}


def _is_mental_action(verb, attempt):
    """True when an action element is purely interior (no outward surface):
    its declared verb is a mental verb, or -- for a weak model that left verb
    unset -- its attempt LEADS with a mental verb ('remember the runes her
    mother taught her'). Conservative: only the leading token is checked, so a
    physical act that merely mentions thought later ('carve while recalling
    the shape') is NOT suppressed."""
    def _stem(tok):
        for suf in ("ing", "es", "ed", "s"):
            if len(tok) > len(suf) + 2 and tok.endswith(suf):
                return tok[:-len(suf)]
        return tok
    v = str(verb or "").strip().lower()
    if v in _MENTAL_VERBS or _stem(v) in _MENTAL_VERBS:
        return True
    head = re.split(r"[^\w]+", str(attempt or "").strip().lower(), maxsplit=1)
    lead = head[0] if head else ""
    return bool(lead) and (lead in _MENTAL_VERBS or _stem(lead) in _MENTAL_VERBS)


def observable_action_text(elem):
    """The outward, intent-free surface of an action element for delivery to
    OTHER perceivers -- what a bystander literally sees/hears, never the
    actor's purpose, magical intent, or private mental content.

    Prefers the director-authored `observable` surface. An explicit empty
    string means the act has no outward manifestation (a purely mental beat --
    recalling, deciding) and returns "" so the caller SKIPS it. Only when the
    element predates the field entirely (key absent -- e.g. an un-normalized
    character declaration) does it fall back to the raw `attempt`, preserving
    legacy delivery for paths norm_sequence does not touch."""
    obs = elem.get("observable")
    if obs is None:
        return str(elem.get("attempt") or "")
    return str(obs or "")

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

def _conceal_from_targets_observer(conceal_from, observer_id, observer_sheet):
    """True if any conceal_from entry names this observer -- matched by
    numeric id, string id, display name, uid, or alias. conceal_from is an
    absolute exclusion list authored against whatever identity handle the
    speaker knew, so a reader must resolve it against ALL of the observer's
    handles (same tolerance character_room/canonicalize_positions apply)."""
    if not conceal_from:
        return False
    id_forms = {str(observer_id).strip()}
    try:
        keys = {k.casefold() for k in character_scene_keys(observer_sheet)}
    except Exception:
        keys = set()
    for entry in conceal_from:
        if isinstance(entry, bool):
            continue
        if isinstance(entry, int):
            if str(entry) in id_forms:
                return True
            continue
        text = str(entry or "").strip()
        if not text:
            continue
        if text in id_forms or text.casefold() in keys:
            return True
    return False

def _concat_dedup(*value_lists):
    """Union-concatenate list-of-dicts update fields, preserving order and
    dropping exact duplicates (a re-emitted identical update across rounds)."""
    out, seen = [], set()
    for values in value_lists:
        for item in _list(values):
            try:
                key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            except (TypeError, ValueError):
                key = repr(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out

def _merge_character_results(existing, new):
    """Combine a character's earlier-round result with a later one instead of
    overwriting. A character who speaks in more than one micro-round would
    otherwise lose its round-0 sequence/mind_model_updates/etc. at commit,
    which reads ctx.character_results[id] as a single result. Latest scalar
    state (active_state, interaction, salience) wins; the accumulating list
    fields are unioned so no round's declared behavior or inference is lost."""
    if not isinstance(existing, dict):
        return new
    if not isinstance(new, dict):
        return existing
    merged = dict(new)
    merged["sequence"] = _list(existing.get("sequence")) + _list(new.get("sequence"))
    for field in (
        "mind_model_updates",
        "relationship_updates",
        "stance_updates",
        "inference_updates",
    ):
        combined = _concat_dedup(existing.get(field), new.get(field))
        if combined or field in existing or field in new:
            merged[field] = combined
    if not new.get("active_state") and existing.get("active_state"):
        merged["active_state"] = existing.get("active_state")
    return merged

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

def _asks_player(result, chat, cast=None):
    player_name = persona_name(persona_of(chat))
    interaction = _dict(result.get("interaction"))
    addresses = {
        str(v).casefold()
        for v in _list(interaction.get("addresses"))
    }
    aliases = {"player", "the player", "you", player_name.casefold()}
    if addresses & aliases:
        return True
    # The trailing-"?" fallback (a speech line ending in "?" is treated as a
    # question awaiting the player) must fire ONLY when the speaker didn't
    # aim the line at a specific cast member. An NPC asking ANOTHER NPC a
    # question ("Reya, are you sure?") is not awaiting the player, and using
    # "?" alone to end the loop there strands an NPC<->NPC exchange as if the
    # player had been addressed. So: if `addresses` names a registered cast
    # member (and not the player, handled above), never apply the fallback.
    cast_names = set()
    for row in (cast or []):
        try:
            cast_names.add(character_name(json.loads(row["sheet"])).casefold())
        except Exception:
            continue
    if addresses & cast_names:
        return False
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

def _extract_authority_claims(sequence, raw_input, actor_name=None):
    """Extract authority claims from the interpreted sequence.

    raw_input is the player's own declaration and serves as the FALLBACK
    text everywhere an element carries no raw_text/attempt of its own --
    both for commitment classification and for the claim's source_text.
    (It used to be accepted and ignored, so an element the model emitted
    without raw_text produced empty-source claims classified against "".)

    actor_name, when given, is the declaring actor (the player). A
    self-directed action effect -- one whose own target_id is empty AND
    whose parent action names no explicit targets -- is about the actor's
    OWN body (a wave, going rigid, a pleading look), so its subject is the
    actor. Without this those claims carried subject_id=None and tripped
    the resolve reconciliation's 'no resolvable subject' note every beat.
    Scoped deliberately narrow: a transitive effect (the action DOES name
    targets, so a null effect target is a dropped reference, not the self)
    and the actor-less `event` branch (a player-authored WORLD assertion
    like "two guards appear") are left for the director to adjudicate --
    resolving them to the player would silently hand the player authorship
    of world facts."""
    fallback_text = str(raw_input or "")
    claims = []
    for i, event in enumerate(sequence or []):
        if event.get("type") == "event":
            # Actor-less environmental assertion ("the lights go out",
            # "a monster enters") -- a player world assertion under the
            # authority contract: it becomes true, so it is minted as an
            # asserted-effect claim the resolve seam's player-claim
            # coverage check can then hold the diff to.
            description = str(event.get("description") or "").strip()
            if not description:
                continue
            claims.append({
                "claim_id": f"claim:{i}:event",
                "scope": "effect",
                "subject_id": str(event.get("subject") or "") or None,
                "predicate": description,
                "value": None,
                "commitment": "asserted",
                "source_text": event.get("raw_text") or description
                or fallback_text,
            })
            continue
        if event.get("type") != "action":
            continue
        commitment = event.get("commitment")
        if commitment is None:
            commitment = _classify_action_commitment(
                event.get("raw_text") or event.get("attempt")
                or fallback_text)
        event["commitment"] = commitment
        # A null effect target is the actor's own body only when the action
        # named no targets at all; if it did, the null is a dropped reference.
        self_subject = actor_name if not (event.get("targets") or []) else None
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
                    "subject_id": eff.get("target_id") or self_subject,
                    "predicate": eff.get("kind", ""),
                    "value": eff.get("details"),
                    "commitment": "asserted",
                    "source_text": event.get("raw_text")
                    or event.get("attempt") or fallback_text,
                })
        else:
            for effect_index, effect in enumerate(
                event.get("intended_effects") or []
            ):
                eff = _normalize_effect(effect)
                if eff is None:
                    continue
                claims.append({
                    "claim_id": f"claim:{i}:intent:{effect_index}",
                    "scope": "intent",
                    "subject_id": eff.get("target_id") or self_subject,
                    "predicate": eff.get("kind", ""),
                    "value": eff.get("details"),
                    "commitment": "contestable",
                    "source_text": event.get("raw_text")
                    or event.get("attempt") or fallback_text,
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

def _ambient_blocked_slugs(sc, room_id):
    """Item-5 coarse nesting filter: None when the observer's room is open
    to the world (nothing to filter); otherwise the normalized ids/names of
    every room OUTSIDE their ambient scope plus the scene's location label.
    Staged lore keyed to any of those is ancestor-scoped information that
    must not reach a sealed nested observer (the port must not leak into a
    sealed elevator). Reads only scene containment (rooms/entities/derived
    dock edges) -- NEVER lorebook links: currently_within is retrieval
    bookkeeping, not perception authorization."""
    scope, open_to_world = ambient_scope(sc, room_id)
    if open_to_world:
        return None
    blocked = set()
    for rid, room in (sc.get("rooms") or {}).items():
        if rid in scope:
            continue
        slug = normalize_room_id(str(rid))
        if slug:
            blocked.add(slug)
        if isinstance(room, dict) and room.get("name"):
            slug = normalize_room_id(str(room["name"]))
            if slug:
                blocked.add(slug)
    location_slug = normalize_room_id(str(sc.get("location") or ""))
    if location_slug:
        blocked.add(location_slug)
    return blocked

def _keys_reference_blocked(keys, blocked):
    """True when any comma-separated key token names an out-of-scope room
    or the outer location (normalized, substring-tolerant for slugs long
    enough not to false-match)."""
    for token in str(keys or "").split(","):
        slug = normalize_room_id(token)
        if not slug:
            continue
        if slug in blocked:
            return True
        for b in blocked:
            if len(b) >= 5 and (b in slug or slug in b):
                return True
    return False

def _room_notes_from_lore(room_id, ctx, scene=None):
    if not room_id:
        return ""
    sc = scene if scene is not None else get_scene(ctx.chat.id, ctx.chat)
    rdata = (sc.get("rooms") or {}).get(room_id)
    if rdata and rdata.get("notes"):
        return rdata["notes"]
    # Coarse scope-by-nesting-depth: for a sealed nested observer, an entry
    # whose keys ALSO name an ancestor-scope room/location carries ambient
    # information they cannot perceive right now -- skip it.
    blocked = _ambient_blocked_slugs(sc, room_id)
    staged = ((ctx.get("mapping_stage") or {}).get("staged_lore") or []) + \
             ((ctx.get("mapping_quick") or {}).get("staged_lore") or [])
    room_norm = room_id.lower().replace("_", " ")
    for entry in staged:
        _k = entry.get("keys")
        keys = (" ".join(map(str, _k)) if isinstance(_k, list) else str(_k or "")).lower()
        content = entry.get("content") or ""
        if (room_norm in keys or room_id.lower() in keys) and content:
            if blocked and _keys_reference_blocked(keys, blocked):
                continue
            return content[:600]
    for entry in lore_for(ctx):
        _k = entry.get("keys")
        keys = (" ".join(map(str, _k)) if isinstance(_k, list) else str(_k or "")).lower()
        content = entry.get("content") or ""
        if (room_norm in keys or room_id.lower() in keys) and content:
            if blocked and _keys_reference_blocked(keys, blocked):
                continue
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
        elif t in ("event", "environment", "environmental", "world"):
            # Actor-less environmental event ("the lights go out", "a
            # monster enters") declared by the player. These used to be
            # silently DROPPED here (only speech/action survived), so a
            # player world assertion never reached the resolve at all.
            # First-class representation, canonical type "event".
            description = (e.get("description") or e.get("text")
                           or e.get("attempt"))
            if description:
                raw_asserted = e.get("asserted_effects") or []
                asserted_effects = [
                    _normalize_effect(eff)
                    for eff in raw_asserted
                    if _normalize_effect(eff) is not None
                ]
                clean.append({
                    "type": "event",
                    "description": str(description),
                    "subject": str(e.get("subject") or ""),
                    "raw_text": e.get("raw_text") or "",
                    "visibility": "concealed"
                    if e.get("visibility") == "concealed" else "overt",
                    "conceal_from": e.get("conceal_from") or [],
                    "commitment": e.get("commitment") or "asserted",
                    "asserted_effects": asserted_effects,
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
                # The intent-free OUTWARD surface handed to other perceivers
                # (see observable_action_text). `attempt` is the actor's own
                # framing and routinely embeds purpose/magic-intent ("scratch
                # runes of slow and soften", "channel divine heritage") or
                # pure cognition ("remember the rune crafting") -- copying it
                # into an observer's view leaks meaning the perception filter
                # exists to strip. Prefer the director-authored `observable`;
                # default a mental act to "" (imperceptible -> skipped) and a
                # physical act with no authored surface to `attempt` (no
                # delivery regression for un-migrated / plain physical acts).
                observable = e.get("observable")
                if observable is None:
                    observable = "" if _is_mental_action(
                        e.get("verb"), att) else att
                clean.append({
                    "type": "action",
                    "attempt": att,
                    "observable": str(observable),
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
    return _sync_sequence_mirrors(out)

def _sync_sequence_mirrors(out):
    """Recompute the legacy scalar mirrors (speech/speech_volume/action/
    actions) from out['sequence']. Factored out of norm_sequence so the
    interpret-reconciliation seam can re-sync after additively appending
    repaired elements WITHOUT re-running norm_sequence on the whole output
    (which would re-append out['actions'] and duplicate every action)."""
    clean = out.get("sequence") or []
    sp = [e for e in clean if e.get("type") == "speech"]
    ac = [e for e in clean if e.get("type") == "action"]
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

def _identity_token_set(actor_name, aliases=None):
    """Casefolded word tokens of an actor's name and aliases -- the tokens
    that must never surface to an observer who does not recognize them."""
    tokens = set()
    for form in [actor_name] + list(aliases or []):
        for tok in re.split(r"[^\w]+", str(form or "")):
            if tok:
                tokens.add(tok.casefold())
    return tokens

def _unknown_actor_label(actor_name, appearance_text=None, aliases=None):
    # Every unrecognized actor used to render as the exact same generic
    # "the unfamiliar person" -- two strangers in one scene (or the same
    # stranger across a perceiver's dialogue and action lines) were
    # indistinguishable in both prose and any memory recorded from it.
    # Derive a short, stable descriptor from the actor's own appearance
    # summary instead. This is deliberately a short label for repeat/
    # inline reference, not a substitute for the full appearance
    # description a caller surfaces separately on first mention.
    #
    # The label is what a NON-recognizing observer refers to the actor by,
    # and appearance summaries routinely LEAD with the canonical name
    # ("Hinami, a fox-eared young woman..."), so the actor's own name/alias
    # tokens are dropped before the descriptor is built -- otherwise the
    # label itself was a deterministic identity leak walking straight past
    # the knows_identity gate it exists to serve.
    if appearance_text:
        name_tokens = _identity_token_set(actor_name, aliases)
        cleaned = re.sub(
            r"^(a|an|the)\s+", "", appearance_text.strip(), flags=re.I,
        ).replace(",", "")
        words = [w for w in cleaned.split()
                 if re.sub(r"[^\w]", "", w).casefold() not in name_tokens]
        # Dropping a leading name can expose the article that followed it
        # ("Hinami, a fox-eared..." -> "a fox-eared..."); re-strip it.
        while words and words[0].lower() in ("a", "an", "the"):
            words = words[1:]
        words = words[:5]
        # The 5-word cap can slice mid-phrase and leave a dangling function
        # word ("...five-foot-seven-inches with a" / "...appearing in"), which
        # reads as broken prose when this label is injected inline. Trim any
        # trailing article/preposition/conjunction/possessive so the label
        # ends on a content word.
        _DANGLING = {"a", "an", "the", "with", "of", "and", "or", "in", "on",
                     "at", "to", "for", "from", "by", "her", "his", "their",
                     "its", "as"}
        while words and words[-1].lower() in _DANGLING:
            words = words[:-1]
        if words:
            return "the " + " ".join(words).rstrip(".;:").lower()
    return "the unfamiliar person"

def _strip_identity_tokens(text, forms):
    """Remove an actor's name/alias forms from engine-supplied prose (an
    appearance summary, an overlay) before it is surfaced to an observer
    who does not recognize that actor. appearance_of()/persona summaries
    routinely lead with the canonical name, so pasting them verbatim into
    a stranger's view via _inject_visible_actor leaked identity entirely
    deterministically, independent of anything the model wrote."""
    out = str(text or "")
    for form in forms or []:
        form = str(form or "").strip()
        if not form:
            continue
        out = re.sub(
            r"(?<!\w)" + re.escape(form) + r"(?:['’]s)?(?!\w)",
            "", out, flags=re.I,
        )
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,;.!?])", r"\1", out)
    out = re.sub(r"([,;])(\s*[,;])+", r"\1", out)
    return out.strip().lstrip(",;: ").strip()

# Single-token names that are also everyday English words ("Rose walks in"
# vs "the rose garden"). For these, only the exact capitalized form is
# scrubbed, so ordinary lowercase prose is never mangled.
_COMMON_WORD_NAMES = frozenset({
    "amber", "angel", "art", "ash", "autumn", "bear", "bill", "blue",
    "brook", "buck", "chase", "clay", "colt", "daisy", "dawn", "dean",
    "drew", "duke", "earl", "faith", "fern", "fox", "ginger", "glen",
    "grace", "hazel", "heath", "holly", "hope", "hunter", "iris", "ivy",
    "jack", "jade", "jasmine", "joy", "june", "king", "lane", "lily",
    "major", "mark", "may", "melody", "misty", "olive", "pearl", "rain",
    "raven", "red", "reed", "robin", "rose", "ruby", "rusty", "sandy",
    "sky", "star", "storm", "summer", "sunny", "violet", "will", "wolf",
    "wren",
})

# Mirrors _protected_view_quotes' quoted-span shape: a name inside a quote
# is sensory signal the observer legitimately heard (an introduction, a
# name called aloud) and must survive the identity scrub verbatim.
#
# Single-quoted dialogue must be protected too -- the perception model
# routinely renders speech as '...' rather than "...", and the double-quote-
# only form let a name spoken aloud this beat (a self-introduction like
# 'I-I'm Hinami') get scrubbed straight out of what the hearer legitimately
# heard. The single-quote alternative is apostrophe-aware: the opening quote
# must not follow a word char or another quote (so contraction/possessive
# apostrophes -- She's, Hinami's -- never open a span), and an internal '
# counts as content only when a word char follows it (I'm, don't), so the
# span still closes at the real terminating quote.
_QUOTED_SPAN_RE = re.compile(
    r'(["“][^"“”]+["”]'
    r"|(?<![\w'’])'(?:[^']|'(?=\w))*?'(?![\w])"
    r")"
)

def _scrub_unknown_identities(view, *, allowed_forms, unknown_sources):
    """Deterministic identity floor for perception view prose.

    The knows_identity/_unknown_actor_label gate used to be enforced only
    inside the deterministic injection helpers -- the perception LLM's own
    free-text prose was never checked, so a model that wrote a stranger's
    canonical name into a view walked straight past the gate (and no
    prompt paragraph even defined knows_identity, so this was not limited
    to weak models). This pass runs LAST on every view: each unknown
    source's name/alias forms are replaced, outside quoted spans only,
    with that source's unknown-actor descriptor.

    unknown_sources: [{name, appearance, aliases}] the observer does NOT
    recognize. allowed_forms: names the observer legitimately commands
    (their own name/aliases plus their recognized set) -- any colliding
    form is skipped rather than scrubbed.

    Returns (scrubbed_view, leaked_names) so callers can surface a
    warning; a silent leak was exactly how the original bug hid.
    """
    text = str(view or "")
    if not text or not unknown_sources:
        return view, []
    allowed = {str(f or "").strip().casefold()
               for f in (allowed_forms or []) if str(f or "").strip()}
    segments = _QUOTED_SPAN_RE.split(text)
    leaked = []
    for src in unknown_sources:
        name = str(src.get("name") or "").strip()
        if not name or name.casefold() in allowed:
            continue
        label = _unknown_actor_label(
            name, src.get("appearance"), aliases=src.get("aliases"))
        fired = False
        for form in [name] + [str(a or "").strip()
                              for a in (src.get("aliases") or [])]:
            if not form or form.casefold() in allowed:
                continue
            if len(form) < 3 and len(form.split()) == 1:
                continue  # too short to match without false positives
            if len(form.split()) == 1 and form.casefold() in _COMMON_WORD_NAMES:
                # common-word guard: exact capitalized form only
                pat = re.compile(
                    r"(?<!\w)" + re.escape(form[:1].upper() + form[1:])
                    + r"(?!\w)")
            else:
                pat = re.compile(
                    r"(?<!\w)" + re.escape(form) + r"(?!\w)", re.IGNORECASE)
            for i in range(0, len(segments), 2):  # even = outside quotes
                if segments[i] and pat.search(segments[i]):
                    segments[i] = pat.sub(label, segments[i])
                    fired = True
        if fired:
            leaked.append(name)
    if not leaked:
        return view, []
    return "".join(segments), leaked

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

def canonicalize_positions(positions, cast, player_name=None):
    """Rewrite any positions key that identifies a registered cast character
    (or the player) to that person's display name -- the positions-key
    convention every reader (perception, commit, spatial) expects. Recognized
    key forms per person: identity.uid, display name (exact or alphanumeric-
    normalized), AND the director's `character:<id>` scheme (from the cast
    payload's integer ids). Non-person keys (objects, unregistered background
    presences) are left untouched. Deliberately does NOT match on aliases.

    Recognizing `character:<id>` and the player is load-bearing: the director
    model keys the SAME person by different schemes across a turn (Data as
    `character:29` here, `Lt. Commander Data` there), and without collapsing
    them to one canonical key the person acquired TWO position entries in
    conflicting rooms -- observed live, Data was simultaneously on the bridge
    (`character:29`) and in a corridor (`Lt. Commander Data`), so name-lookup
    resolved him to the corridor and perception rendered his bridge station as
    empty. Collapsing to a single key makes a later move update the one entry."""
    if not isinstance(positions, dict):
        return {}
    if not cast and not player_name:
        return positions
    keymap = {}

    def _register(forms, canon):
        for key in forms:
            text = str(key or "").strip()
            if not text:
                continue
            keymap.setdefault(text.lower(), canon)
            norm = re.sub(r"[^a-z0-9]", "", text.lower())
            if norm:
                keymap.setdefault(norm, canon)

    for row in (cast or []):
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        ident = normalize_character_data(sheet).get("identity", {})
        name = ident.get("name") or character_name(sheet)
        forms = [ident.get("uid"), name]
        try:
            rid = row["id"]
        except Exception:
            rid = None
        if rid is not None:
            forms.append(f"character:{rid}")
        _register(forms, name)
    if player_name:
        _register([player_name, "character:player"], player_name)

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

_OBSERVED_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "with",
    "her", "his", "their", "its", "she", "he", "they", "it", "him", "them",
    "as", "into", "toward", "towards", "across", "for", "from", "by", "up",
    "down", "over", "under", "then", "while", "is", "are", "was", "were", "be",
    "been", "this", "that", "these", "those", "your", "you", "herself",
    "himself", "themselves", "itself", "slightly", "slowly", "again",
})


def _content_tokens(text):
    """Distinctive (stopword-stripped, crudely stemmed) word tokens of a phrase
    -- the basis for 'has this beat already been narrated?' overlap."""
    toks = []
    for raw in re.split(r"[^\w]+", str(text or "").lower()):
        if not raw or raw in _OBSERVED_STOPWORDS:
            continue
        for suf in ("ing", "ed", "es", "s"):
            if len(raw) > len(suf) + 2 and raw.endswith(suf):
                raw = raw[:-len(suf)]
                break
        toks.append(raw)
    return toks


def _observable_predicate(display, surface):
    """Compose one clean delivered sentence from an actor `display` label and an
    intent-free `observable` surface, without the double-subject run-ons the
    alpha3.1.2 full-sentence observable produced ('Dr. Moon Dr. Moon tilts...',
    'Dr. Moon The flashlight beam moves...'). Strip a leading occurrence of the
    actor's own name tokens (so an actor-led surface becomes a predicate); then
    if the surface still opens with its OWN capitalized subject (an independent
    clause like 'The flashlight beam moves...'), keep it verbatim as its own
    sentence -- prepending display would double the subject; otherwise it is a
    predicate and takes the display prefix."""
    surface = str(surface or "").strip()
    if not surface:
        return None
    disp_tokens = _identity_token_set(display)
    words = surface.split()
    # Peel leading actor-name tokens / a leading pronoun off the surface.
    while words and (words[0].strip(".,;:'").casefold() in disp_tokens
                     or words[0].casefold() in ("she", "he", "they", "it")):
        words = words[1:]
    stripped = " ".join(words).strip()
    if not stripped:
        return f"{display}."
    first = stripped.split(maxsplit=1)[0]
    # Independent subject clause (starts with a capitalized non-actor word that
    # isn't a normal sentence-initial cap): render as its own sentence.
    independent = first[:1].isupper() and first.casefold() not in disp_tokens
    if independent:
        return stripped if stripped.endswith((".", "!", "?")) else stripped + "."
    body = stripped[0].lower() + stripped[1:]
    return f"{display} {body}."


def _action_already_rendered(view, display, surface):
    """True when the view already narrates this action (so the deterministic
    backstop should stay silent). Upgrades the old exact-substring test to
    content-token overlap, which catches the LLM's paraphrase of the same
    beat. Biases toward silence: since alpha3.1.2 duplication is the common,
    player-visible failure and a missed injection the rare one."""
    surf = set(_content_tokens(surface))
    if not surf:
        return False
    disp_tokens = _identity_token_set(display)
    for sent in re.split(r"(?<=[.!?])\s+", str(view or "")):
        raw = set(re.split(r"[^\w]+", sent.lower()))
        stoks = set(_content_tokens(sent))
        overlap = surf & stoks
        if not overlap:
            continue
        if len(overlap) / len(surf) >= 0.6:
            return True
        if (disp_tokens & raw) and len(overlap) >= 2:
            return True
    return False


def _inject_action(view, display, attempt, can_see, event_id=None, delivered=None):
    if not attempt or not can_see:
        return view
    if delivered is not None and event_id:
        if event_id in delivered:
            return view
        delivered.add(event_id)
    if _action_already_rendered(view, display, attempt):
        return view
    sentence = _observable_predicate(display, attempt)
    if not sentence:
        return view
    return _append_once(view, sentence, marker=sentence)

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

def _compose_residue_view(level, *, targeted=False, loud_event=False, pain=False):
    """The content-free perception RESIDUE for a non-awake mind (asleep /
    sedated / unconscious). An unconscious mind integrates no channel into
    scene, identity, or words -- so this NEVER carries speech content, a name, a
    visual scene, or a spatial fact. It delivers only interoception (pain, being
    moved) and the direction-less trace of the strongest stimuli (a loud event
    as a wordless intrusion). Deterministic and template-built: the perception
    LLM is never asked for a non-awake view (it would leak with the full payload
    in hand), so this IS the whole output. The fragments become, verbatim, that
    mind's fragmentary memory of the beat (commit mints episodic memory from the
    view), which is exactly the vague recovered impression waking should give."""
    lead = {
        "unconscious": "Darkness.",
        "sedated": "A thick, floating dark.",
        "asleep": "You are under, below waking.",
    }.get(level, "Darkness.")
    frag = []
    if pain:
        frag.append("a dull pain, far off, in a body you can't quite feel")
    if targeted:
        frag.append("something shifts you; the world tilts without a direction")
    if loud_event:
        frag.append("a sound, huge and wordless, reaches down and is gone")
    if not frag:
        closing = {"unconscious": " Nothing reaches you.",
                   "sedated": " Nothing holds shape.",
                   "asleep": ""}.get(level, "")
        return (lead + closing).strip()
    body = "; ".join(frag[:2])
    return f"{lead} {body[0].upper()}{body[1:]}."


def _ensure_environment(view, perceiver, display, rel, vis, action_desc):
    if view:
        return view
    parts = [f"You are in {perceiver.get('room_name')}."]
    if perceiver.get("room_notes"):
        parts.append(perceiver["room_notes"])
    if rel.get("same_room"):
        parts.append(f"{display} is here with you.")
        if action_desc:
            # action_desc is now an intent-free `observable` surface (predicate
            # or independent clause); compose it cleanly rather than gluing it
            # after "attempts to" (which double-verbs "attempts to tilts...").
            sentence = _observable_predicate(display, action_desc)
            if sentence:
                parts.append(sentence)
    elif vis:
        parts.append(f"You can see {display} nearby.")
    return " ".join(parts)

def _fallback_perception_views(perceivers, dlog, resolved_event=None, known=None):
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
                speaker = d.get("speaker", "?")
                # Same recognition gate as the main injection paths: a
                # speaker this perceiver has never been introduced to must
                # not be named by the no-LLM fallback either (the quote
                # itself is legitimately heard and stays verbatim).
                if known is not None and speaker != p.get("name") \
                        and speaker not in (known.get(p.get("name")) or []):
                    speaker = _unknown_actor_label(speaker)
                parts.append(f'{speaker} says: {d["exact_quote"]}')
        views[pid] = " ".join(parts) if parts else None
    return views

_DANGLING_SPEECH_VERB_RE = re.compile(
    r"\b(say|says|said|ask|asks|asked|tell|tells|told|call|calls|called|"
    r"shout|shouts|shouted|murmur|murmurs|murmured|whisper|whispers|whispered|"
    r"reply|replies|replied|answer|answers|answered)\b,?\s*(?=[.,]|$)",
    re.IGNORECASE,
)

def _protected_view_quotes(view, player_lines=None):
    """Quoted spans in a perceiver's view that belong to a NON-player speaker
    -- the exact lines DIALOGUE FIDELITY requires the narrator to keep
    verbatim. Excludes the player's own declared lines (those are the ones
    the echo strip is meant to remove). Fed to _strip_player_echo so it never
    corrupts a legitimately-quoted NPC line while stripping a player echo."""
    excluded = {
        re.sub(r"\s+", " ", _quote_body(line).casefold())
        for line in (player_lines or [])
        if _quote_body(line)
    }
    quotes = []
    for match in re.finditer(r'["“]([^"“”]{1,})["”]', str(view or "")):
        body = _quote_body(match.group(1))
        if not body:
            continue
        if re.sub(r"\s+", " ", body.casefold()) in excluded:
            continue
        quotes.append(body)
    return quotes

def _strip_player_echo(prose, lines, protect_quotes=None):
    if not prose:
        return prose
    # DIALOGUE FIDELITY vs PLAYER ECHO: the echo strip removes the player's
    # OWN declared lines from prose, but it must never reach inside a span the
    # narrator legitimately quoted from a NON-player speaker (an NPC line the
    # fidelity check just required verbatim). When a player line coincides
    # with, or is a substring of, an NPC's quoted line, blind stripping would
    # corrupt that protected quote. Mask the NPC-attributed quoted spans out
    # of reach for the duration of the strip, then restore them intact.
    masks = []
    for quote in (protect_quotes or []):
        body = _quote_body(quote)
        if not body:
            continue
        forms = ['"%s"' % body, "“%s”" % body]
        if len(body) >= 8:
            forms.append(body)
        for form in forms:
            start = 0
            while True:
                pos = prose.find(form, start)
                if pos == -1:
                    break
                token = "\x00%d\x00" % len(masks)
                masks.append((token, form))
                prose = prose[:pos] + token + prose[pos + len(form):]
                start = pos + len(token)
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
    for token, form in masks:
        prose = prose.replace(token, form)
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

# Within-view dedupe (W12): the same sentence rendered twice in ONE turn's
# view/prose ("Picard turns his head slightly toward Troi" appearing twice in
# a single beat). Splitting is a plain sentence-boundary regex; a quote whose
# body contains sentence punctuation mis-splits into fragments, but every such
# fragment carries a quote character and is therefore exempt from dropping
# (below), so mis-splits can only UNDER-dedupe, never eat real content.
_SPEECH_VERBS = (
    "say", "says", "said", "saying", "whisper", "whispers", "whispered",
    "whispering", "mutter", "mutters", "muttered", "muttering", "murmur",
    "murmurs", "murmured", "murmuring", "manage", "managed",
    "manages", "breathe", "breathes", "breathed", "gasp", "gasps", "gasped",
    "gasping", "croak", "croaks", "croaked", "rasp", "rasps", "rasped",
    "reply", "replies", "replied", "replying", "answer", "answers",
    "answered", "answering", "hiss", "hisses", "hissed",
    "stammer", "stammers", "stammered", "whimper", "whimpers", "whimpered",
    "choke", "chokes", "force", "forces", "add", "adds", "added", "plead",
    "pleads", "pleaded", "pleading", "beg", "begs", "begged", "begging",
    "cry", "cries", "call", "calls", "called", "get out", "let out",
    "shout", "shouts", "shouted", "shouting", "scream", "screams",
    "screamed", "screaming", "yell", "yells", "yelled", "yelling",
    "ask", "asks", "asked", "asking", "respond", "responds", "responded",
    "sob", "sobs", "sobbed", "sobbing", "snap", "snaps", "snapped",
    "growl", "growls", "growled", "blurt", "blurts", "blurted",
    "exclaim", "exclaims", "exclaimed", "repeat", "repeats", "repeated",
    "insist", "insists", "insisted", "demand", "demands", "demanded",
    "announce", "announces", "announced", "declare", "declares", "declared",
    "wail", "wails", "wailed", "moan", "moans", "moaned",
    "intone", "intones", "intoned", "utter", "utters", "uttered",
    "speak", "speaks", "spoke", "speaking", "tell", "tells", "told",
)
_SPEECH_VERB_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(v) for v in _SPEECH_VERBS) + r")\b", re.I)
# Attribution cue for the dialogue-fidelity floor: a speech verb, or a bare
# voice noun ("A muffled voice: ..."). Deliberately excludes reading verbs
# (reads, is written/painted/carved, displays) so quoted ENVIRONMENTAL text --
# signage, labels, screens -- is never mistaken for dialogue.
_DIALOGUE_CUE_RE = re.compile(
    _SPEECH_VERB_RE.pattern + r"|\bvoices?\b", re.I)
_YOU_RE = re.compile(r"\byou\b|\byour\b", re.I)
_NPC_PRONOUN_RE = re.compile(r"\bshe\b|\bhe\b|\bthey\b|\bher\b|\bhim\b|\bhis\b", re.I)


def _scrub_invented_dialogue(view, spoken_bodies, *, cast_names=(), mode="all"):
    """DIALOGUE-FIDELITY FLOOR at the perception layer: drop any quoted line
    of a perceiver view that is presented as SPEECH but whose body is not in
    the set of lines actually spoken this beat (declared player/character
    speech + dialogue_log). The perception LLM sometimes invents a fresh
    utterance -- often a memory/backstory callback rendered as if freshly
    spoken (live t42: a fabricated player line about "trapped under the
    rubble" injected into Dr. Moon's view) -- which then propagates into
    other minds' character context and durable memory. No stage may author
    words a speaker did not say.

    Kept untouched:
    - any quote whose body matches a spoken line GENEROUSLY (case/whitespace
      normalized; substring either direction, so a distant perceiver's
      legitimate muffled FRAGMENT of a real line survives; an ellipsis-split
      quote survives when every fragment is verbatim from one spoken line);
    - environmental quoted text (mode="all"): signage, labels, screens --
      recognized by the ABSENCE of a speech-attribution cue around the quote
      ("reads"/"is painted" are not speech verbs);
    - quotes with no player attribution (mode="player": only a quote whose
      nearest speaker cue is 'you'/'your' is in scope -- the original
      player-view-only scrub semantics).

    Removal is clause surgery: the quote plus its immediate attribution
    clause (before it, and after it for a trailing '"...," she says.'),
    never the surrounding prose. Returns (scrubbed_view, dropped)."""
    if not view:
        return view, []
    legit = []
    for b in spoken_bodies:
        nb = re.sub(r"\s+", " ", (_quote_body(b) or "")).casefold().strip()
        if nb:
            legit.append(nb)

    def _matches_spoken(raw_body):
        body = re.sub(r"\s+", " ", (_quote_body(raw_body) or "")).casefold().strip()
        if not body or not re.search(r"\w", body):
            return True  # empty / pure punctuation: nothing was authored
        if any(body == L or body in L or L in body for L in legit):
            return True
        core = body.strip(" .…—–-")
        if core and any(core in L for L in legit):
            return True
        # Muffled/partial rendering: an ellipsis-chunked quote is legitimate
        # when EVERY chunk is a verbatim piece of some actually-spoken line.
        chunks = []
        for c in re.split(r"\.{2,}|…", body):
            c = c.strip(" ,;:—–-.!?")
            if c.startswith("something about "):
                c = c[len("something about "):]
            if len(c) >= 3:
                chunks.append(c)
        return bool(chunks) and all(any(c in L for L in legit) for c in chunks)

    name_re = re.compile(
        "|".join(r"\b" + re.escape(str(n).lower()) + r"\b" for n in cast_names if n),
        re.I) if cast_names else None

    # Quoted spans (a body may itself contain '...'/'!' -- so we cannot split
    # into sentences first; we work over the whole view). Clause boundaries are
    # sentence terminators OUTSIDE any quote, plus the END of each quoted span
    # (a new clause almost always begins after a quoted line).
    quote_spans = [(m.start(), m.end(), m.group(1))
                   for m in re.finditer(r'["“]([^"”]*)["”]', view)]
    boundaries = {0}
    inside = False
    for i, ch in enumerate(view):
        if ch in '"“”':
            inside = not inside
        elif ch in ".!?…" and not inside:
            boundaries.add(i + 1)
    for _s, qe, _b in quote_spans:
        boundaries.add(qe)
    boundaries = sorted(boundaries)
    quote_starts = [qs for qs, _qe, _b in quote_spans]

    def _clause_start(pos):
        b = 0
        for bp in boundaries:
            if bp <= pos:
                b = bp
            else:
                break
        while b < len(view) and view[b] in " \n\t":
            b += 1
        return b

    def _tail_stop(pos):
        # The attribution tail of a quote runs to the next sentence boundary,
        # but never INTO a following quote -- a legit quote after 'she says,
        # and X replies,' must survive the surgery.
        stop = len(view)
        for bp in boundaries:
            if bp > pos:
                stop = bp
                break
        for q2 in quote_starts:
            if pos < q2 < stop:
                stop = q2
                break
        return stop

    removals, dropped = [], []
    for qs, qe, raw_body in quote_spans:
        if _matches_spoken(raw_body):
            continue
        if mode == "player":
            # Original player-view semantics: only a quote whose NEAREST
            # speaker cue before it is the player ('you'/'your', closer than
            # any NPC pronoun/cast name) is in scope.
            prefix = view[:qs]
            you = max((mm.start() for mm in _YOU_RE.finditer(prefix)), default=-1)
            npc = max((mm.start() for mm in _NPC_PRONOUN_RE.finditer(prefix)), default=-1)
            if name_re:
                npc = max([npc] + [mm.start() for mm in name_re.finditer(prefix)])
            if you < 0 or you <= npc:
                continue
            start, end = _clause_start(qs), qe
        else:
            cstart = _clause_start(qs)
            pre_attr = bool(_DIALOGUE_CUE_RE.search(view[cstart:qs]))
            tstop = _tail_stop(qe)
            tail = view[qe:tstop]
            tail_lead = tail.lstrip()
            # A trailing attribution ('"...," she says.') continues the same
            # sentence, so it starts lowercase or with a dash -- an uppercase
            # tail is a NEW sentence and out of scope.
            tail_attr = bool(tail_lead) and (
                tail_lead[0].islower() or tail_lead[0] in ",—–-") \
                and bool(_DIALOGUE_CUE_RE.search(tail))
            if not pre_attr and not tail_attr:
                continue  # no speech attribution: environmental text (signage)
            start = cstart if pre_attr else qs
            end = tstop if tail_attr else qe
        while end < len(view) and view[end] in " \n\t":
            end += 1
        removals.append((start, end))
        dropped.append(view[start:qe].strip())

    if not removals:
        return view, []
    out = view
    for start, end in sorted(removals, reverse=True):
        out = out[:start] + out[end:]
    return re.sub(r"\s{2,}", " ", out).strip(), dropped


def _scrub_undeclared_player_speech(view, declared_bodies, protected_bodies=(),
                                    cast_names=()):
    """PLAYER-SPEECH AUTHORITY at the perception layer: drop any sentence of the
    PLAYER's own view that quotes a player-attributed line the player did NOT
    declare this beat (live: the turn-39 fragment "The same..." resurfaced as
    "Same... the one who... did this... before." in a later turn's view).
    Thin wrapper over _scrub_invented_dialogue's player mode; NPC lines the
    player legitimately heard ride in as protected_bodies. Returns
    (scrubbed_view, dropped_sentences)."""
    return _scrub_invented_dialogue(
        view, list(declared_bodies) + list(protected_bodies),
        cast_names=cast_names, mode="player")


_VIEW_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])(\s+)")
# Double-quote characters only: curly/straight single quotes double as
# apostrophes in ordinary prose and cannot mark dialogue reliably.
_VIEW_QUOTE_CHARS = ('"', "“", "”")
_VIEW_DEDUPE_MIN_WORDS = 5

def _dedupe_view_sentences(text):
    """Drop a sentence that repeats an EARLIER sentence of the same text
    verbatim (case/whitespace/terminal-punctuation-insensitive), keeping the
    first occurrence. Deterministic and deliberately conservative:

    - sentences containing quoted dialogue are never dropped -- quotes must
      survive verbatim (dialogue fidelity), and a character repeating a line
      on purpose is legitimate;
    - short sentences (< 5 words) are never dropped -- intentional beats
      ("No. No.") and terse stage directions must survive;
    - only exact normalized repeats go; paraphrase is out of scope.

    Returns the text unchanged (same object) when nothing repeats.
    """
    text = str(text or "")
    if not text.strip():
        return text
    pieces = _VIEW_SENTENCE_SPLIT_RE.split(text)
    seen = set()
    kept = []
    dropped = False
    # pieces alternates [sentence, separator, sentence, separator, ...];
    # each sentence is kept/dropped together with ITS OWN trailing
    # separator, so removing a duplicate leaves the surrounding
    # whitespace/paragraph structure intact.
    for i in range(0, len(pieces), 2):
        sent = pieces[i]
        sep = pieces[i + 1] if i + 1 < len(pieces) else ""
        key = re.sub(r"\s+", " ", sent).strip().strip(".!?…").casefold()
        droppable = (
            len(key.split()) >= _VIEW_DEDUPE_MIN_WORDS
            and not any(qc in sent for qc in _VIEW_QUOTE_CHARS)
        )
        if droppable:
            if key in seen:
                dropped = True
                continue
            seen.add(key)
        kept.append(sent)
        kept.append(sep)
    if not dropped:
        return text
    return "".join(kept).rstrip()

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

# Third-person paradigms screened by _check_pronoun_fidelity. Only these three
# closed sets are checked: a character whose declared pronouns fall outside the
# table (neopronouns, mixed sets like she/them) is skipped entirely rather than
# guessed at -- the check exists to catch UNAMBIGUOUS flips, so anything it
# can't be certain about is not its business.
_PRONOUN_GROUPS = {
    "he": ("he", "him", "his", "himself"),
    "she": ("she", "her", "hers", "herself"),
    "they": ("they", "them", "their", "theirs", "themselves", "themself"),
}
_PRONOUN_TO_GROUP = {w: g for g, ws in _PRONOUN_GROUPS.items() for w in ws}

# Splits a sentence into clauses. A pronoun is only scored against a name in
# the SAME clause, which is what keeps "Vorne glanced at the ensign; her hands
# shook" (referent is the ensign, not Vorne) out of the check.
_CLAUSE_SPLIT = re.compile(
    r"[,;:()\[\]—–]|\s+(?:and|but|while|as|when|then|though|although"
    r"|so|yet|because|before|after|until|which|who|whose|that)\s+",
    re.I,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Names that are also ordinary capitalized English words. A cast member called
# one of these can't be told apart from the common word, so we decline to score
# their clauses rather than burn a rewrite on "Will you hand him the padd".
_AMBIGUOUS_NAME_WORDS = {
    "will", "may", "art", "grace", "hope", "rose", "mark", "bill", "dawn",
    "sky", "rain", "storm", "ray", "faith", "joy", "sun", "star",
}


def _pronoun_group(pronouns):
    """The closed paradigm a declared pronoun set belongs to, or None when the
    declared forms are absent, unknown, or disagree with each other."""
    if not isinstance(pronouns, dict):
        return None
    groups = set()
    for key in ("subject", "object", "possessive"):
        word = str(pronouns.get(key) or "").strip().lower()
        if not word:
            continue
        group = _PRONOUN_TO_GROUP.get(word)
        if group is None:
            return None
        groups.add(group)
    return groups.pop() if len(groups) == 1 else None


def _check_pronoun_fidelity(prose, cast_pronouns):
    """Third-person pronoun flips the narrator prose commits against a cast
    member's canonical pronouns (W6).

    The PRONOUN CONSISTENCY prompt rule reduces but does not enforce this --
    a he/him character still picked up a "her" in live play. Deliberately
    narrow: a clause must OPEN with exactly one known cast name and then use a
    pronoun from a different paradigm, so the named subject is the only
    possible referent. Anything looser (a second name in the clause, a bare
    pronoun in a following sentence, an unnamed role noun) is left alone --
    a false positive costs a needless full narrator rewrite.
    """
    if not prose or not isinstance(cast_pronouns, dict):
        return []

    # name token -> (canonical name, group). Good prose drops to a surname or
    # first name alone after the first mention, so each word of a multi-word
    # name is a referent in its own right. A token two cast members share is
    # dropped: it no longer identifies one of them.
    token_owner = {}
    for name, pronouns in cast_pronouns.items():
        group = _pronoun_group(pronouns)
        canonical = str(name or "").strip()
        if not group or not canonical:
            continue
        for token in re.findall(r"[A-Za-z']+", canonical):
            if len(token) < 3 or not token[:1].isupper():
                continue
            if token.lower() in _AMBIGUOUS_NAME_WORDS:
                continue
            if token in token_owner and token_owner[token][0] != canonical:
                token_owner[token] = None
            elif token not in token_owner:
                token_owner[token] = (canonical, group)
    token_owner = {t: v for t, v in token_owner.items() if v}
    if not token_owner:
        return []

    # A pronoun inside quoted dialogue belongs to the speaker talking about
    # whoever they mean -- often someone the clause never names -- so it can't
    # be scored against the clause's named subject.
    scan = re.sub(r'"[^"]*"|“[^“”]*”', " ", prose)

    warnings = []
    flagged = set()
    for sentence in _SENTENCE_SPLIT.split(scan):
        for clause in _CLAUSE_SPLIT.split(sentence):
            words = re.findall(r"[A-Za-z']+", clause)
            if len(words) < 2:
                continue
            present = {token_owner[w] for w in words if w in token_owner}
            if len(present) != 1:
                continue
            canonical, group = next(iter(present))
            # The name must OPEN the clause: only then is it unambiguously the
            # subject the following pronoun refers back to.
            head = next(i for i, w in enumerate(words) if w in token_owner)
            if head > 1:
                continue
            for word in words[head + 1:]:
                other = _PRONOUN_TO_GROUP.get(word.lower())
                # A stray "they" is routinely a group ("Vorne watched them
                # scatter"), so only a GENDERED singular counts as a flip.
                if not other or other == group or other == "they":
                    continue
                key = (canonical, word.lower())
                if key in flagged:
                    break
                flagged.add(key)
                expected = "/".join(_PRONOUN_GROUPS[group][:3])
                warnings.append(
                    f"Pronoun mismatch for '{canonical}' (canonical {expected}): "
                    f"prose renders '{word}'"
                )
                break
    return warnings


def _check_narrator_fidelity(out, view, recent_prose=None, exclude_quotes=None,
                             cast_pronouns=None):
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

    warnings.extend(_check_pronoun_fidelity(prose, cast_pronouns))

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
